"""
Author: HydroClaw Team
Date: 2026-02-08
Description: LLM-as-Calibrator - LLM acts as a "virtual hydrologist" for parameter tuning.
             Reference: Zhu et al. (2026), GRL, doi:10.1029/2025GL120043
"""

import json
import logging
from pathlib import Path

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

EXPERT_PROMPT_TEMPLATE = """You are a senior hydrological model calibration expert. Your task is to suggest parameter values for the {model_name} model to achieve the best fit between simulated and observed streamflow.

## Model: {model_name}
## Parameter Ranges:
{param_ranges_text}

## Guidelines:
1. Start with physically reasonable initial values (middle of range or literature values).
2. After each iteration, analyze the metrics (NSE, RMSE, PBIAS) to understand model behavior.
3. Adjust parameters based on hydrological understanding:
   - Low NSE + High RMSE: Major structural mismatch, adjust dominant parameters first
   - Good NSE but High PBIAS: Volume bias, adjust water balance parameters
   - Poor peak flows: Adjust routing/timing parameters
4. Make targeted adjustments (1-2 parameters at a time for sensitivity understanding).
5. Avoid extreme values near parameter bounds unless physically justified.

## Response Format:
Always respond with a JSON block containing your suggested parameters:
```json
{{"x1": value, "x2": value, ...}}
```
Follow the JSON with a brief explanation of your reasoning."""


def llm_calibrate(
    basin_ids: list[str],
    model_name: str = "gr4j",
    max_iterations: int = 200,
    nse_target: float = 0.75,
    param_ranges: dict | None = None,
    train_period: list[str] | None = None,
    test_period: list[str] | None = None,
    _workspace: Path | None = None,
    _cfg: dict | None = None,
    _llm: object | None = None,
) -> dict:
    """Calibrate a hydrological model using LLM as a virtual hydrologist.

    The LLM analyzes simulation results and intelligently suggests parameter
    adjustments based on hydrological expertise, achieving faster convergence
    than traditional algorithms.
    Reference: Zhu et al. (2026), GRL, doi:10.1029/2025GL120043

    Args:
        basin_ids: CAMELS basin ID list
        model_name: Hydrological model name ("gr4j", "xaj")
        max_iterations: Maximum number of LLM-guided iterations
        nse_target: Target NSE value for early stopping
        param_ranges: Parameter name to [min, max] range dict, uses defaults if not given
        train_period: Training period ["YYYY-MM-DD", "YYYY-MM-DD"]
        test_period: Testing period ["YYYY-MM-DD", "YYYY-MM-DD"]

    Returns:
        {"best_params": {...}, "best_nse": float, "iterations": int, "history": [...]}
    """
    if _llm is None:
        return {"error": "LLM client required for LLM calibration", "success": False}

    ranges = param_ranges or DEFAULT_PARAM_RANGES.get(model_name, {})
    if not ranges:
        return {"error": f"No default parameter ranges for model {model_name}", "success": False}

    # Build expert prompt
    ranges_text = "\n".join(
        f"  - {name}: [{r[0]}, {r[1]}]" for name, r in ranges.items()
    )
    expert_prompt = EXPERT_PROMPT_TEMPLATE.format(
        model_name=model_name,
        param_ranges_text=ranges_text,
    )

    messages = [{"role": "system", "content": expert_prompt}]
    messages.append({
        "role": "user",
        "content": f"Please suggest initial parameter values for basin {basin_ids} using the {model_name} model. Respond with a JSON block.",
    })

    history = []
    best_nse = -999.0
    best_params = None

    for i in range(max_iterations):
        # Get LLM suggestion
        response = _llm.chat(messages)
        params = _parse_params(response.text, ranges)

        if params is None:
            logger.warning(f"Iteration {i}: Failed to parse params from LLM response")
            messages.append({"role": "assistant", "content": response.text})
            messages.append({
                "role": "user",
                "content": "I couldn't parse your parameters. Please respond with a JSON block like: ```json\n{\"x1\": value, ...}\n```",
            })
            continue

        # Run simulation with these parameters
        metrics = _run_with_params(basin_ids, model_name, params, train_period, test_period, _cfg, _workspace)

        if "error" in metrics:
            logger.warning(f"Iteration {i}: Simulation error: {metrics['error']}")
            messages.append({"role": "assistant", "content": response.text})
            messages.append({
                "role": "user",
                "content": f"Simulation failed: {metrics['error']}. Please try different parameters.",
            })
            continue

        nse = metrics.get("NSE", -999)
        history.append({"iteration": i, "params": params, "metrics": metrics})

        if nse > best_nse:
            best_nse = nse
            best_params = dict(params)

        logger.info(f"Iteration {i}: NSE={nse:.4f} (best={best_nse:.4f})")

        # Early stopping
        if best_nse >= nse_target:
            logger.info(f"Target NSE {nse_target} reached at iteration {i}")
            break

        # Convergence check (after 10+ iterations)
        if i >= 10 and len(history) >= 2:
            prev_nse = history[-2]["metrics"].get("NSE", -999)
            if abs(nse - prev_nse) < 0.0001:
                logger.info(f"Converged at iteration {i} (NSE change < 0.0001)")
                break

        # Feedback to LLM
        messages.append({"role": "assistant", "content": response.text})
        feedback = (
            f"Iteration {i+1} results: NSE={nse:.4f}, "
            f"RMSE={metrics.get('RMSE', 'N/A')}, "
            f"PBIAS={metrics.get('PBIAS', 'N/A')}%.\n"
            f"Best NSE so far: {best_nse:.4f}.\n"
            f"Please analyze the results and suggest adjusted parameters."
        )
        messages.append({"role": "user", "content": feedback})

        # Keep context manageable (sliding window)
        if len(messages) > 40:
            # Keep system prompt + last 30 messages
            messages = messages[:1] + messages[-30:]

    return {
        "best_params": best_params or {},
        "best_nse": best_nse,
        "iterations": len(history),
        "history": history,
        "model_name": model_name,
        "basin_ids": basin_ids,
        "success": best_nse > -999,
    }


def _parse_params(text: str, ranges: dict) -> dict | None:
    """Parse parameter values from LLM response text."""
    import re

    # Try to find JSON block
    json_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
    matches = re.findall(json_pattern, text, re.DOTALL)

    for match in matches:
        try:
            params = json.loads(match.strip())
            if isinstance(params, dict):
                # Validate and clip to ranges
                valid = {}
                for name, value in params.items():
                    if name in ranges:
                        lo, hi = ranges[name]
                        valid[name] = max(lo, min(hi, float(value)))
                if valid:
                    return valid
        except (json.JSONDecodeError, ValueError):
            continue

    # Try to find inline JSON
    try:
        json_match = re.search(r'\{[^{}]+\}', text)
        if json_match:
            params = json.loads(json_match.group())
            if isinstance(params, dict):
                valid = {}
                for name, value in params.items():
                    if name in ranges:
                        lo, hi = ranges[name]
                        valid[name] = max(lo, min(hi, float(value)))
                if valid:
                    return valid
    except (json.JSONDecodeError, ValueError):
        pass

    return None


def _run_with_params(
    basin_ids, model_name, params, train_period, test_period, cfg, workspace
) -> dict:
    """Run simulation with given parameters and return metrics."""
    # TODO: Implement direct parameter injection into hydromodel simulation
    # For now, this is a placeholder that would need hydromodel's simulation API
    try:
        from hydroclaw.config import build_hydromodel_config

        config = build_hydromodel_config(
            basin_ids=basin_ids,
            model_name=model_name,
            train_period=train_period,
            test_period=test_period,
            cfg=cfg,
        )

        # Use hydromodel's evaluate with custom parameters
        # This requires hydromodel to support parameter injection
        from hydromodel import evaluate as hm_evaluate

        result = hm_evaluate(config, params=params)

        # Extract metrics
        if isinstance(result, dict):
            for basin_id, basin_data in result.items():
                if isinstance(basin_data, dict) and "metrics" in basin_data:
                    import numpy as np
                    metrics = {}
                    for k, v in basin_data["metrics"].items():
                        if isinstance(v, (list, np.ndarray)):
                            metrics[k] = float(v[0]) if len(v) > 0 else None
                        else:
                            metrics[k] = v
                    return metrics

        return {"error": "Could not extract metrics from simulation result"}

    except Exception as e:
        return {"error": str(e)}
