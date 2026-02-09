"""
Author: HydroClaw Team
Date: 2026-02-08
LastEditTime: 2026-02-09
Description: LLM-guided iterative calibration - LLM acts as a "virtual hydrologist"
             that adjusts parameter RANGES between SCE-UA calibration rounds.
             Inspired by: Zhu et al. (2026), GRL, doi:10.1029/2025GL120043
"""

import json
import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

# Default parameter ranges for supported models
DEFAULT_PARAM_RANGES = {
    "gr4j": {
        "x1": [1.0, 2000.0],    # Production store capacity (mm)
        "x2": [-10.0, 10.0],     # Groundwater exchange coefficient (mm/d)
        "x3": [1.0, 500.0],      # Routing store capacity (mm)
        "x4": [0.5, 10.0],       # Unit hydrograph time base (d)
    },
    "xaj": {
        "binfilt": [0.01, 0.99],  # B exponent
        "Dsmax": [0.1, 30.0],     # Maximum subsurface flow rate (mm/d)
        "Ds": [0.001, 1.0],       # Fraction of Dsmax
        "Ws": [0.1, 1.0],         # Fraction of maximum soil moisture
        "soil_d2": [0.1, 3.0],    # Soil layer depth (m)
    },
}

RANGE_ADVISOR_PROMPT = """You are a senior hydrological model calibration expert.
Your role is to analyze SCE-UA calibration results and decide whether to adjust parameter ranges for a re-calibration round.

## Model: {model_name}

## Current Parameter Ranges:
{param_ranges_text}

## Your Task:
1. Analyze the calibration results (best parameters, NSE, RMSE, etc.)
2. Check for boundary effects: if a parameter's best value is within 5% of its range boundary, the search space may be too restrictive.
3. Decide whether to adjust parameter ranges:
   - If a parameter hits the upper boundary → expand the upper bound (e.g., x1.5 or x2)
   - If a parameter hits the lower boundary → expand the lower bound
   - If NSE is already good (>= target) → no adjustment needed
   - Keep ranges physically reasonable (no negative capacities, etc.)

## Response Format:
If adjustment is needed, respond with a JSON block of NEW parameter ranges:
```json
{{"x1": [new_min, new_max], "x2": [new_min, new_max], ...}}
```
Then explain your reasoning.

If NO adjustment is needed (results are satisfactory), respond with:
```json
{{"no_change": true}}
```
Then explain why the current results are acceptable."""


def llm_calibrate(
    basin_ids: list[str],
    model_name: str = "gr4j",
    max_rounds: int = 5,
    nse_target: float = 0.75,
    param_ranges: dict | None = None,
    algorithm: str = "SCE_UA",
    algorithm_params: dict | None = None,
    train_period: list[str] | None = None,
    test_period: list[str] | None = None,
    _workspace: Path | None = None,
    _cfg: dict | None = None,
    _llm: object | None = None,
) -> dict:
    """LLM-guided iterative calibration using SCE-UA as the optimizer.

    Each round: SCE-UA optimizes within current parameter ranges → LLM analyzes
    results and adjusts ranges → next round. Typically converges in 2-3 rounds.

    Args:
        basin_ids: CAMELS basin ID list
        model_name: Hydrological model name ("gr4j", "xaj")
        max_rounds: Maximum number of LLM-guided rounds (each runs a full SCE-UA)
        nse_target: Target NSE value for early stopping
        param_ranges: Initial parameter ranges dict, uses defaults if not given
        algorithm: Calibration algorithm, default "SCE_UA"
        algorithm_params: Algorithm parameter overrides, e.g. {"rep": 500}
        train_period: Training period ["YYYY-MM-DD", "YYYY-MM-DD"]
        test_period: Testing period ["YYYY-MM-DD", "YYYY-MM-DD"]

    Returns:
        {"best_params": {...}, "best_nse": float, "rounds": int, "history": [...]}
    """
    if _llm is None:
        return {"error": "LLM client required for LLM calibration", "success": False}

    current_ranges = dict(param_ranges or DEFAULT_PARAM_RANGES.get(model_name, {}))
    if not current_ranges:
        return {"error": f"No default parameter ranges for model {model_name}", "success": False}

    from hydroclaw.tools.calibrate import calibrate_model

    history = []
    best_nse = -999.0
    best_params = None
    best_result = None

    for round_idx in range(max_rounds):
        logger.info(f"=== LLM Calibration Round {round_idx + 1}/{max_rounds} ===")

        # Write current ranges to YAML for this round
        param_range_file = None
        if round_idx > 0:
            # Only use custom range file from round 2 onwards
            range_dir = _workspace or Path(".")
            param_range_file = str(range_dir / f"_llm_param_ranges_round{round_idx}.yaml")
            with open(param_range_file, "w") as f:
                yaml.dump({model_name: current_ranges}, f, default_flow_style=False)
            logger.info(f"Custom param ranges written to {param_range_file}")

        # Run SCE-UA calibration
        result = calibrate_model(
            basin_ids=basin_ids,
            model_name=model_name,
            algorithm=algorithm,
            train_period=train_period,
            test_period=test_period,
            algorithm_params=algorithm_params,
            param_range_file=param_range_file,
            output_dir=str(((_workspace or Path("results")) / f"llm_round_{round_idx}")),
            _workspace=_workspace,
            _cfg=_cfg,
        )

        if not result.get("success"):
            logger.warning(f"Round {round_idx + 1} calibration failed: {result.get('error')}")
            history.append({"round": round_idx + 1, "error": result.get("error")})
            continue

        nse = result.get("metrics", {}).get("NSE", -999)
        round_params = result.get("best_params", {})

        round_record = {
            "round": round_idx + 1,
            "param_ranges": dict(current_ranges),
            "best_params": round_params,
            "metrics": result.get("metrics", {}),
            "nse": nse,
        }
        history.append(round_record)

        if nse > best_nse:
            best_nse = nse
            best_params = dict(round_params)
            best_result = result

        logger.info(f"Round {round_idx + 1}: NSE={nse:.4f} (best={best_nse:.4f})")

        # Early stopping if target reached
        if best_nse >= nse_target:
            logger.info(f"Target NSE {nse_target} reached at round {round_idx + 1}")
            break

        # Last round - no need to ask LLM for adjustments
        if round_idx >= max_rounds - 1:
            break

        # Ask LLM to analyze results and suggest range adjustments
        new_ranges = _ask_llm_for_range_adjustment(
            _llm, model_name, current_ranges, round_params,
            result.get("metrics", {}), nse_target, round_idx + 1,
        )

        if new_ranges is None:
            logger.info("LLM suggests no further adjustment needed")
            break

        current_ranges = new_ranges
        logger.info(f"LLM adjusted ranges: {current_ranges}")

    return {
        "best_params": best_params or {},
        "best_nse": best_nse,
        "rounds": len(history),
        "history": history,
        "model_name": model_name,
        "basin_ids": basin_ids,
        "calibration_dir": best_result.get("calibration_dir", "") if best_result else "",
        "success": best_nse > -999,
    }


def _ask_llm_for_range_adjustment(
    llm, model_name, current_ranges, best_params, metrics, nse_target, round_num
) -> dict | None:
    """Ask LLM to analyze results and suggest new parameter ranges.

    Returns new ranges dict, or None if no adjustment needed.
    """
    ranges_text = "\n".join(
        f"  - {name}: [{r[0]}, {r[1]}]" for name, r in current_ranges.items()
    )
    system_prompt = RANGE_ADVISOR_PROMPT.format(
        model_name=model_name,
        param_ranges_text=ranges_text,
    )

    # Build boundary analysis for context
    boundary_info = []
    for name, value in best_params.items():
        if name in current_ranges:
            lo, hi = current_ranges[name]
            span = hi - lo
            if span > 0:
                lo_pct = (value - lo) / span * 100
                hi_pct = (hi - value) / span * 100
                status = ""
                if lo_pct < 5:
                    status = " ** HITS LOWER BOUND **"
                elif hi_pct < 5:
                    status = " ** HITS UPPER BOUND **"
                boundary_info.append(
                    f"  {name} = {value:.4f}  (range [{lo}, {hi}], "
                    f"at {lo_pct:.1f}% from lower){status}"
                )

    user_msg = (
        f"Round {round_num} SCE-UA calibration results:\n"
        f"  NSE = {metrics.get('NSE', 'N/A')}\n"
        f"  RMSE = {metrics.get('RMSE', 'N/A')}\n"
        f"  KGE = {metrics.get('KGE', 'N/A')}\n"
        f"  Target NSE = {nse_target}\n\n"
        f"Best parameters and boundary analysis:\n"
        + "\n".join(boundary_info) + "\n\n"
        f"Should we adjust parameter ranges for the next calibration round?"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_msg},
    ]

    response = llm.chat(messages)
    return _parse_ranges(response.text, current_ranges)


def _parse_ranges(text: str, current_ranges: dict) -> dict | None:
    """Parse parameter range adjustments from LLM response.

    Returns new ranges dict, or None if LLM says no change needed.
    """
    import re

    # Try to find JSON block
    json_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
    matches = re.findall(json_pattern, text, re.DOTALL)

    for match in matches:
        try:
            data = json.loads(match.strip())
            if isinstance(data, dict):
                if data.get("no_change"):
                    return None
                # Validate: each value should be [min, max]
                new_ranges = dict(current_ranges)
                for name, bounds in data.items():
                    if name in current_ranges and isinstance(bounds, list) and len(bounds) == 2:
                        lo, hi = float(bounds[0]), float(bounds[1])
                        if lo < hi:
                            new_ranges[name] = [lo, hi]
                if new_ranges != current_ranges:
                    return new_ranges
                return None
        except (json.JSONDecodeError, ValueError, TypeError):
            continue

    # Try inline JSON
    try:
        json_match = re.search(r'\{[^{}]+\}', text)
        if json_match:
            data = json.loads(json_match.group())
            if isinstance(data, dict):
                if data.get("no_change"):
                    return None
                new_ranges = dict(current_ranges)
                for name, bounds in data.items():
                    if name in current_ranges and isinstance(bounds, list) and len(bounds) == 2:
                        lo, hi = float(bounds[0]), float(bounds[1])
                        if lo < hi:
                            new_ranges[name] = [lo, hi]
                if new_ranges != current_ranges:
                    return new_ranges
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    return None
