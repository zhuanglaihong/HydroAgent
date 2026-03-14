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

# Default algorithm params — ensures adaptive scaling always has a baseline
_DEFAULT_ALGO_PARAMS = {
    "SCE_UA": {"rep": 750, "ngs": 200, "kstop": 10},
    "GA": {"pop_size": 50, "n_generations": 50},
}

# Default parameter ranges for supported models
DEFAULT_PARAM_RANGES = {
    "gr4j": {
        "x1": [1.0, 2000.0],    # Production store capacity (mm)
        "x2": [-10.0, 10.0],    # Groundwater exchange coefficient (mm/d)
        "x3": [1.0, 500.0],     # Routing store capacity (mm)
        "x4": [0.5, 10.0],      # Unit hydrograph time base (d)
    },
    "gr5j": {
        "x1": [1.0, 2000.0],    # Production store capacity (mm)
        "x2": [-10.0, 10.0],    # Groundwater exchange coefficient (mm/d)
        "x3": [1.0, 500.0],     # Routing store capacity (mm)
        "x4": [0.5, 10.0],      # Unit hydrograph time base (d)
        "x5": [0.0, 1.0],       # Interception store capacity (mm)
    },
    "gr6j": {
        "x1": [1.0, 2000.0],    # Production store capacity (mm)
        "x2": [-10.0, 10.0],    # Groundwater exchange coefficient (mm/d)
        "x3": [1.0, 500.0],     # Routing store capacity (mm)
        "x4": [0.5, 10.0],      # Unit hydrograph time base (d)
        "x5": [0.0, 1.0],       # Interception store capacity (mm)
        "x6": [0.0, 20.0],      # Exponential store depletion coefficient
    },
    "xaj": {
        "binfilt": [0.01, 0.99],  # B exponent for spatial distribution of soil moisture
        "Dsmax": [0.1, 30.0],     # Maximum subsurface flow rate (mm/d)
        "Ds": [0.001, 1.0],       # Fraction of Dsmax for non-linear baseflow
        "Ws": [0.1, 1.0],         # Fraction of maximum soil moisture for non-linear baseflow
        "soil_d2": [0.1, 3.0],    # Lower zone soil layer depth (m)
    },
}

RANGE_ADVISOR_PROMPT = """You are a senior hydrological model calibration expert.
Your role is to analyze SCE-UA calibration results and recommend adjustments for the next round.
You may adjust BOTH parameter ranges AND optimization algorithm parameters.

## Model: {model_name}

## Current Parameter Ranges:
{param_ranges_text}

## Current SCE-UA Algorithm Parameters:
{algo_params_text}

## Your Task:
1. Check for boundary effects: if a parameter value is within 5% of its range boundary, expand that boundary.
2. If NSE is poor but NO boundary hits, the optimizer budget may be insufficient — recommend increasing rep/ngs.
3. If NSE >= target, stop (no adjustment needed).

## Algorithm Parameter Guidance:
- rep (total evaluations): Default 750. If NSE < 0.4 and no boundary hits → try 1500-2000.
- ngs (complexes): Rule of thumb = 2 × n_params. GR4J→8 min; use 100-300 for quality. If NSE very low → try increasing by 50-100.
- kstop: Leave as default (10) unless results oscillate.

## Response Format:
Include ONLY fields that need changing. Examples:

Parameter range change only:
```json
{{"x1": [200, 1500], "x4": [0.5, 15.0]}}
```

Algorithm params change only (ranges are fine):
```json
{{"no_change": true, "algorithm_params": {{"rep": 1500, "ngs": 300}}}}
```

Both ranges and algorithm params:
```json
{{"x1": [200, 1500], "algorithm_params": {{"rep": 1500, "ngs": 300}}}}
```

No adjustment needed at all:
```json
{{"no_change": true}}
```

Always explain your reasoning after the JSON block."""


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
    _ui=None,
) -> dict:
    """LLM-guided iterative calibration using SCE-UA as the optimizer.

    Each round: SCE-UA optimizes within current parameter ranges → LLM analyzes
    results and adjusts ranges → next round. Typically converges in 2-3 rounds.

    Args:
        basin_ids: CAMELS basin ID list
        model_name: Hydrological model name ("gr4j", "xaj", "gr5j", "gr6j")
        max_rounds: Maximum number of LLM-guided rounds (each runs a full SCE-UA)
        nse_target: Target NSE value for early stopping
        param_ranges: Initial parameter ranges dict, uses defaults if not given
        algorithm: Calibration algorithm, default "SCE_UA"
        algorithm_params: Algorithm parameter overrides as a dict, e.g. {"rep": 500, "ngs": 200}. Must be a dict, NOT a string.
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

    from hydroclaw.skills.calibration.calibrate import calibrate_model
    from hydroclaw.skills.evaluation.evaluate import evaluate_model

    history = []
    best_nse = -999.0
    best_params = None
    best_result = None

    # Resolve base algorithm params once so we can adapt per round.
    # If not explicitly provided, fall back to config defaults so the adaptive
    # scaling has a concrete baseline to work from (e.g. rep=750 -> 562 -> 450 -> 375).
    if isinstance(algorithm_params, dict) and algorithm_params:
        _base_algo_params = dict(algorithm_params)
    else:
        if algorithm_params is not None and not isinstance(algorithm_params, dict):
            logger.warning(
                f"algorithm_params must be a dict, got {type(algorithm_params).__name__}: "
                f"{algorithm_params!r}. Falling back to config defaults."
            )
        _base_algo_params = dict(
            (_cfg or {}).get("algorithms", {}).get(algorithm, {})
        )
    # Ensure baseline always has values so adaptive scaling has something to work with
    if not _base_algo_params:
        _base_algo_params = dict(_DEFAULT_ALGO_PARAMS.get(algorithm, {}))

    for round_idx in range(max_rounds):
        logger.info(f"=== LLM Calibration Round {round_idx + 1}/{max_rounds} ===")

        # Write current ranges to YAML (hydromodel format) for this round
        param_range_file = None
        if round_idx > 0:
            range_dir = _workspace or Path(".")
            param_range_file = str(range_dir / f"_llm_param_ranges_round{round_idx}.yaml")
            param_names = list(current_ranges.keys())
            range_yaml = {
                model_name: {
                    "param_name": param_names,
                    "param_range": {k: v for k, v in current_ranges.items()},
                }
            }
            with open(param_range_file, "w") as f:
                yaml.dump(range_yaml, f, default_flow_style=False, allow_unicode=True)
            logger.info(f"Custom param ranges written to {param_range_file}")

        # Adaptive budget: round 1 uses full budget; later rounds scale down.
        # Later rounds have narrower ranges so fewer evaluations are needed to
        # find the optimum — this saves compute without sacrificing quality.
        round_algo_params = _adaptive_algo_params(
            _base_algo_params, algorithm, round_idx, max_rounds
        )

        # Vary random seed per round so SCE-UA explores different starting points.
        # hydromodel SCE-UA defaults to random_seed=1234 every run — without this fix,
        # same seed + same ranges = identical result every round, making multi-round
        # calibration useless.
        if algorithm == "SCE_UA" and "random_seed" not in round_algo_params:
            round_algo_params = dict(round_algo_params)
            round_algo_params["random_seed"] = 1234 + round_idx * 137
        if round_algo_params != _base_algo_params:
            logger.info(
                f"Round {round_idx + 1}: adaptive budget "
                f"{_base_algo_params} -> {round_algo_params}"
            )

        # Run calibration (pass _ui so progress events are emitted each round)
        result = calibrate_model(
            basin_ids=basin_ids,
            model_name=model_name,
            algorithm=algorithm,
            train_period=train_period,
            test_period=test_period,
            algorithm_params=round_algo_params if round_algo_params else None,
            param_range_file=param_range_file,
            output_dir=str(((_workspace or Path("results")) / f"llm_round_{round_idx}")),
            _workspace=_workspace,
            _cfg=_cfg,
            _ui=_ui,
            _round_label=f"Round {round_idx + 1}/{max_rounds}",
        )

        if not result.get("success"):
            logger.warning(f"Round {round_idx + 1} calibration failed: {result.get('error')}")
            history.append({
                "round": round_idx + 1,
                "error": result.get("error"),
                "diagnosis": result.get("diagnosis", {}),
            })
            continue

        round_params = result.get("best_params", {})
        cal_dir = result.get("calibration_dir", "")

        # Evaluate on training period to get NSE — calibrate_model only returns params
        train_eval = evaluate_model(
            calibration_dir=cal_dir,
            eval_period=result.get("train_period"),
            _cfg=_cfg,
        )
        train_metrics = train_eval.get("metrics", {}) if train_eval.get("success") else {}
        nse = train_metrics.get("NSE", -999.0)
        if not isinstance(nse, float):
            nse = -999.0

        # Detect which parameters are near their boundaries (<5% of range span)
        boundary_hits = _detect_boundary_hits(round_params, current_ranges)

        round_record = {
            "round": round_idx + 1,
            "param_ranges": dict(current_ranges),
            "best_params": round_params,
            "train_metrics": train_metrics,
            "nse": nse,
            "boundary_hits": boundary_hits,
            "calibration_dir": cal_dir,
        }
        history.append(round_record)

        if nse > best_nse:
            best_nse = nse
            best_params = dict(round_params)
            best_result = result

        logger.info(
            f"Round {round_idx + 1}: train NSE={nse:.4f} (best={best_nse:.4f}), "
            f"boundary_hits={[h['param'] for h in boundary_hits]}"
        )

        # Early stopping if target reached
        if best_nse >= nse_target:
            logger.info(f"Target NSE {nse_target} reached at round {round_idx + 1}")
            break

        # Last round - no need to ask LLM for adjustments
        if round_idx >= max_rounds - 1:
            break

        # Ask LLM to analyze results and suggest adjustments (ranges + algo params)
        adj = _ask_llm_for_adjustments(
            _llm, model_name, current_ranges, round_params,
            train_metrics, nse_target, round_idx + 1,
            current_algo_params=round_algo_params,
        )

        if adj is None:
            logger.info("LLM suggests no further adjustment needed")
            break

        new_ranges = adj.get("ranges")
        new_algo_params = adj.get("algo_params")

        if new_ranges:
            current_ranges = new_ranges
            logger.info(f"LLM adjusted ranges: {current_ranges}")
        if new_algo_params:
            _base_algo_params.update(new_algo_params)
            logger.info(f"LLM adjusted algorithm params: {new_algo_params}")

    final_boundary_hits = _detect_boundary_hits(
        best_params or {}, current_ranges
    )
    return {
        "best_params": best_params or {},
        "best_nse": best_nse if best_nse > -998.0 else None,
        "rounds": len(history),
        "nse_history": [h.get("nse") for h in history],  # compact, preserved in summary
        "history": history,
        "final_boundary_hits": final_boundary_hits,
        "model_name": model_name,
        "basin_ids": basin_ids,
        "calibration_dir": best_result.get("calibration_dir", "") if best_result else "",
        "success": best_nse > -998.0,
        "observation_hint": (
            f"Each round's boundary_hits shows which params hit their range limits. "
            f"final_boundary_hits={final_boundary_hits}. "
            "If any param still hits boundary after all rounds, consider expanding ranges further."
        ),
    }


def _adaptive_algo_params(base: dict, algorithm: str, round_idx: int, max_rounds: int) -> dict:
    """Scale down SCE-UA/GA budget for later rounds.

    Round 1 runs at full budget (wide global search).
    Subsequent rounds run at reduced budget because the parameter range
    has been narrowed by the LLM advisor, requiring fewer evaluations
    to find the optimum within the tighter space.

    Scale schedule: round 1=100%, round 2=75%, round 3=60%, round 4+=50%.
    """
    if round_idx == 0 or algorithm not in ("SCE_UA", "GA"):
        return base

    scales = [1.0, 0.75, 0.60, 0.50]
    scale = scales[min(round_idx, len(scales) - 1)]

    result = dict(base)
    if algorithm == "SCE_UA":
        for key in ("rep", "ngs", "kstop"):
            if key in result:
                result[key] = max(50, int(result[key] * scale))
    elif algorithm == "GA":
        for key in ("pop_size", "n_generations"):
            if key in result:
                result[key] = max(10, int(result[key] * scale))
    return result


def _detect_boundary_hits(params: dict, ranges: dict, threshold_pct: float = 5.0) -> list:
    """Return list of params that are within threshold_pct% of their range boundary."""
    hits = []
    for name, value in params.items():
        if name not in ranges:
            continue
        lo, hi = ranges[name]
        span = hi - lo
        if span <= 0:
            continue
        lo_pct = (value - lo) / span * 100
        hi_pct = (hi - value) / span * 100
        if lo_pct < threshold_pct:
            hits.append({"param": name, "boundary": "lower",
                         "value": value, "bound": lo, "pct_from_bound": round(lo_pct, 1)})
        elif hi_pct < threshold_pct:
            hits.append({"param": name, "boundary": "upper",
                         "value": value, "bound": hi, "pct_from_bound": round(hi_pct, 1)})
    return hits


def _ask_llm_for_adjustments(
    llm, model_name, current_ranges, best_params, metrics, nse_target, round_num,
    current_algo_params: dict | None = None,
) -> dict | None:
    """Ask LLM to analyze results and suggest adjustments to parameter ranges and/or algorithm params.

    Returns {"ranges": dict|None, "algo_params": dict|None}, or None if no change needed.
    """
    ranges_text = "\n".join(
        f"  - {name}: [{r[0]}, {r[1]}]" for name, r in current_ranges.items()
    )
    algo_text = "\n".join(
        f"  - {k}: {v}" for k, v in (current_algo_params or {}).items()
    ) or "  (using defaults)"

    system_prompt = RANGE_ADVISOR_PROMPT.format(
        model_name=model_name,
        param_ranges_text=ranges_text,
        algo_params_text=algo_text,
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

    nse_val = metrics.get("NSE", "N/A")
    no_boundary = not any("HITS" in line for line in boundary_info)
    extra_hint = ""
    if no_boundary and isinstance(nse_val, float) and nse_val < nse_target:
        extra_hint = (
            "\nNo boundary hits detected but NSE is still below target. "
            "Consider recommending larger rep or ngs to improve optimizer coverage."
        )

    user_msg = (
        f"Round {round_num} SCE-UA calibration results:\n"
        f"  NSE = {nse_val}\n"
        f"  RMSE = {metrics.get('RMSE', 'N/A')}\n"
        f"  KGE = {metrics.get('KGE', 'N/A')}\n"
        f"  Target NSE = {nse_target}\n\n"
        f"Best parameters and boundary analysis:\n"
        + "\n".join(boundary_info)
        + extra_hint + "\n\n"
        "What adjustments do you recommend for the next calibration round?"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_msg},
    ]

    response = llm.chat(messages)
    return _parse_adjustments(response.text, current_ranges)


def _parse_adjustments(text: str, current_ranges: dict) -> dict | None:
    """Parse parameter range and/or algorithm param adjustments from LLM response.

    Returns {"ranges": new_ranges|None, "algo_params": dict|None},
    or None if no adjustment at all.
    """
    import re

    def _extract_data(raw_text):
        # Try code-fenced JSON blocks first
        json_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
        matches = re.findall(json_pattern, raw_text, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match.strip())
            except (json.JSONDecodeError, ValueError, TypeError):
                continue
        # Try parsing the whole text (for test/direct JSON input)
        try:
            stripped = raw_text.strip()
            if stripped.startswith("{"):
                return json.loads(stripped)
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
        # Fallback: find outermost {...} block (handles nested braces)
        start = raw_text.find("{")
        if start >= 0:
            depth = 0
            for i, ch in enumerate(raw_text[start:], start):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(raw_text[start:i + 1])
                        except (json.JSONDecodeError, ValueError, TypeError):
                            break
        return None

    data = _extract_data(text)
    if not isinstance(data, dict):
        return None

    no_range_change = bool(data.get("no_change"))
    algo_params_raw = data.get("algorithm_params")

    # Parse new parameter ranges
    new_ranges = None
    if not no_range_change:
        candidate = dict(current_ranges)
        changed = False
        for name, bounds in data.items():
            if name in ("no_change", "algorithm_params"):
                continue
            if name in current_ranges and isinstance(bounds, list) and len(bounds) == 2:
                try:
                    lo, hi = float(bounds[0]), float(bounds[1])
                    if lo < hi:
                        candidate[name] = [lo, hi]
                        changed = True
                except (ValueError, TypeError):
                    continue
        if changed:
            new_ranges = candidate

    # Parse algorithm param suggestions
    new_algo_params = None
    if isinstance(algo_params_raw, dict) and algo_params_raw:
        parsed_algo = {}
        for k, v in algo_params_raw.items():
            try:
                parsed_algo[k] = int(v) if isinstance(v, (int, float)) else v
            except (ValueError, TypeError):
                pass
        if parsed_algo:
            new_algo_params = parsed_algo

    if new_ranges is None and new_algo_params is None:
        return None

    return {"ranges": new_ranges, "algo_params": new_algo_params}


llm_calibrate.__agent_hint__ = (
    "LLM-guided iterative calibration: each round runs SCE-UA with a DIFFERENT random seed, "
    "LLM analyzes results and adjusts BOTH parameter ranges AND algorithm params (rep/ngs). "
    "Random seed varies automatically per round to avoid identical results. "
    "If NSE is low with no boundary hits, LLM recommends increasing rep/ngs automatically. "
    "Pass algorithm_params={'rep': 1500, 'ngs': 300} for difficult basins (semiarid, negative NSE). "
    "Returns best_nse and best_params directly. Still call evaluate_model(calibration_dir=...) for test period."
)
