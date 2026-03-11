"""
Author: HydroClaw Team
Date: 2026-02-08
Description: Parse hydromodel calibration and evaluation results.
             Reuses core logic from HydroAgent's result_parser.
"""

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def parse_calibration_result(result: Any, config: dict) -> dict:
    """Parse hydromodel calibrate() return value.

    Args:
        result: Return value from hydromodel.calibrate()
        config: The config dict used for calibration

    Returns:
        {"calibration_dir": str, "best_params": dict, "metrics": dict, "output_files": list}
    """
    parsed = {
        "metrics": {},
        "best_params": {},
        "output_files": [],
        "calibration_dir": None,
    }

    try:
        output_dir = config.get("training_cfgs", {}).get("output_dir")
        if not output_dir:
            return parsed

        output_path = Path(output_dir)
        if not output_path.exists():
            return parsed

        # Find calibration_results.json
        results_file = output_path / "calibration_results.json"

        if results_file.exists():
            # Direct mode (experiment_name="")
            parsed["calibration_dir"] = str(output_path)
            _extract_params(results_file, parsed)
        else:
            # Subdirectory mode
            subdirs = sorted(
                [d for d in output_path.iterdir() if d.is_dir()],
                key=lambda x: x.stat().st_mtime,
                reverse=True,
            )
            if subdirs:
                parsed["calibration_dir"] = str(subdirs[0])
                sub_results = subdirs[0] / "calibration_results.json"
                if sub_results.exists():
                    _extract_params(sub_results, parsed)

        # Note: hydromodel calibrate() (SCE-UA/GA/scipy) never returns "metrics".
        # It only returns best_params + objective_value. Actual NSE/KGE metrics
        # are obtained via _evaluate_train() or evaluate_model() separately.

    except Exception as e:
        logger.error(f"Error parsing calibration result: {e}", exc_info=True)

    return parsed


def _extract_params(results_file: Path, parsed: dict):
    """Extract and denormalize parameters from calibration_results.json.

    hydromodel stores best_params as normalized values in [0, 1].
    We read param_range.yaml from the same directory to recover physical values:
        physical = lo + normalized * (hi - lo)
    """
    try:
        with open(results_file, "r") as f:
            data = json.load(f)

        if not data:
            return

        basin_id = next(iter(data))
        basin_data = data[basin_id]

        if "best_params" in basin_data:
            model_params = basin_data["best_params"]
            if model_params:
                model_name = next(iter(model_params))
                norm_params = model_params[model_name]

                # Try to denormalize using param_range.yaml in the same dir
                param_ranges = _load_param_ranges(results_file.parent, model_name)
                if param_ranges:
                    parsed["best_params"] = {
                        k: _denormalize(v, param_ranges.get(k))
                        for k, v in norm_params.items()
                    }
                else:
                    # No range file found — store as-is and warn
                    logger.warning(
                        f"param_range.yaml not found in {results_file.parent}; "
                        "best_params are normalized [0,1] values, not physical units"
                    )
                    parsed["best_params"] = norm_params

        parsed["output_files"].append(str(results_file))

    except Exception as e:
        logger.warning(f"Failed to extract params from {results_file}: {e}")


def _load_param_ranges(cal_dir: Path, model_name: str) -> dict:
    """Load parameter ranges from param_range.yaml. Returns {param: [lo, hi]} or {}."""
    try:
        import yaml
        range_file = cal_dir / "param_range.yaml"
        if not range_file.exists():
            return {}
        with open(range_file, "r") as f:
            data = yaml.safe_load(f)
        model_data = data.get(model_name, {})
        ranges = model_data.get("param_range", {})
        # Normalize to {name: [lo, hi]} regardless of list/dict format
        result = {}
        for name, bounds in ranges.items():
            if isinstance(bounds, (list, tuple)) and len(bounds) == 2:
                result[name] = [float(bounds[0]), float(bounds[1])]
        return result
    except Exception as e:
        logger.debug(f"Could not load param_range.yaml from {cal_dir}: {e}")
        return {}


def _denormalize(normalized: float, bounds: list | None) -> float:
    """Convert a [0,1] normalized value back to physical units."""
    if bounds is None or not isinstance(normalized, (int, float)):
        return normalized
    lo, hi = bounds
    return lo + float(normalized) * (hi - lo)


def parse_evaluation_result(result: Any, calibration_dir: str | None = None) -> dict:
    """Parse hydromodel evaluate() return value.

    Args:
        result: Return value from hydromodel evaluate()
        calibration_dir: Optional calibration directory for finding metric files

    Returns:
        {"metrics": dict, "output_files": list}
    """
    parsed = {"metrics": {}, "output_files": [], "performance": {}}

    try:
        if isinstance(result, dict):
            # hydromodel returns {basin_id: {"metrics": {...}, ...}}
            basin_ids = [k for k in result if isinstance(result.get(k), dict)]

            if basin_ids:
                first_basin = result[basin_ids[0]]
                if isinstance(first_basin, dict) and "metrics" in first_basin:
                    metrics = first_basin["metrics"]
                    flat = {}
                    for key, value in metrics.items():
                        if isinstance(value, (list, np.ndarray)):
                            flat[key] = float(value[0]) if len(value) > 0 else None
                        else:
                            flat[key] = value
                    parsed["metrics"] = flat
                    parsed["performance"] = flat

            # Check for basins_metrics.csv
            if calibration_dir:
                metrics_file = Path(calibration_dir) / "basins_metrics.csv"
                if metrics_file.exists():
                    parsed["output_files"].append(str(metrics_file))
                    parsed["basins_metrics_file"] = str(metrics_file)

    except Exception as e:
        logger.warning(f"Error parsing evaluation result: {e}", exc_info=True)

    return parsed
