"""
Author: HydroClaw Team
Date: 2026-02-08
Description: Model calibration tool - calls hydromodel for parameter optimization.
"""

import logging
from pathlib import Path

# Force non-GUI matplotlib backend
import matplotlib
matplotlib.use("Agg")

logger = logging.getLogger(__name__)


def calibrate_model(
    basin_ids: list[str],
    model_name: str = "xaj",
    algorithm: str = "SCE_UA",
    train_period: list[str] | None = None,
    test_period: list[str] | None = None,
    algorithm_params: dict | None = None,
    param_range_file: str | None = None,
    output_dir: str | None = None,
    _workspace: Path | None = None,
    _cfg: dict | None = None,
) -> dict:
    """Calibrate a hydrological model using the specified algorithm.

    Calls hydromodel to perform parameter optimization (e.g., SCE-UA, GA, scipy).
    Results are saved to the output directory.

    Args:
        basin_ids: CAMELS basin ID list, e.g. ["12025000"]
        model_name: Model name ("gr4j", "xaj", "gr5j", "gr6j")
        algorithm: Optimization algorithm ("SCE_UA", "GA", "scipy")
        train_period: Training period ["YYYY-MM-DD", "YYYY-MM-DD"]
        test_period: Testing period ["YYYY-MM-DD", "YYYY-MM-DD"]
        algorithm_params: Algorithm parameter overrides as a dict, e.g. {"rep": 500, "ngs": 200}. Must be a dict, NOT a string.
        param_range_file: Path to custom parameter range YAML file for boundary expansion
        output_dir: Output directory for results

    Returns:
        {"best_params": {...}, "metrics": {"NSE": ..., ...}, "calibration_dir": "...", "output_files": [...]}
    """
    from hydroclaw.config import build_hydromodel_config
    from hydroclaw.utils.result_parser import parse_calibration_result

    config = build_hydromodel_config(
        basin_ids=basin_ids,
        model_name=model_name,
        algorithm=algorithm,
        train_period=train_period,
        test_period=test_period,
        algorithm_params=algorithm_params,
        param_range_file=param_range_file,
        output_dir=output_dir,
        cfg=_cfg,
    )

    try:
        from hydromodel import calibrate as hm_calibrate
    except ImportError as e:
        return {"error": f"hydromodel not available: {e}", "success": False}

    # Inject negated loss functions so minimization-based optimizers (SCE-UA/GA)
    # can correctly maximize NSE/KGE (which are "higher is better" metrics).
    _inject_negated_losses()

    logger.info(
        f"Starting calibration: {model_name}/{algorithm} for basins {basin_ids}"
    )

    try:
        result = hm_calibrate(config)
    except KeyboardInterrupt:
        logger.warning("Calibration interrupted by user")
        raise
    except Exception as e:
        error_msg = str(e)
        is_retryable = "NetCDF: HDF error" in error_msg or "KeyError" in error_msg
        if is_retryable:
            _clear_caches()
            try:
                result = hm_calibrate(config)
            except Exception as e2:
                return {"error": f"Calibration failed: {e2}", "success": False}
        else:
            return {"error": f"Calibration failed: {e}", "success": False}

    # Parse results
    parsed = parse_calibration_result(result, config)

    # Evaluate on training period and save to <calibration_dir>/train_metrics/
    train_metrics = {}
    cal_dir = parsed.get("calibration_dir")
    if cal_dir:
        actual_train_period = config["data_cfgs"]["train_period"]
        train_metrics = _evaluate_train(cal_dir, actual_train_period)

    return {
        "best_params": parsed.get("best_params", {}),
        "metrics": parsed.get("metrics", {}),
        "train_metrics": train_metrics,
        "calibration_dir": parsed.get("calibration_dir", ""),
        "output_files": parsed.get("output_files", []),
        "model_name": model_name,
        "algorithm": algorithm,
        "basin_ids": basin_ids,
        "success": True,
    }


def _evaluate_train(calibration_dir: str, train_period: list) -> dict:
    """Evaluate on training period and save metrics to <calibration_dir>/train_metrics/.

    Returns metrics dict, or empty dict on failure.
    """
    import csv
    try:
        from hydromodel.trainers.unified_evaluate import evaluate
        from hydromodel.configs.config_manager import load_config_from_calibration

        config = load_config_from_calibration(calibration_dir)
        train_dir = Path(calibration_dir) / "train_metrics"
        train_dir.mkdir(exist_ok=True)

        result = evaluate(
            config,
            param_dir=calibration_dir,
            eval_period=train_period,
            eval_output_dir=str(train_dir),
        )

        # Primary: read from train_dir/basins_metrics.csv
        metrics_file = train_dir / "basins_metrics.csv"
        if metrics_file.exists():
            with open(metrics_file, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    return {
                        k: float(v)
                        for k, v in row.items()
                        if k and k.strip() and v and v.strip()
                    }

        # Fallback: parse directly from result dict
        import numpy as np
        if isinstance(result, dict):
            basin_ids = [k for k in result if isinstance(result.get(k), dict)]
            if basin_ids:
                first = result[basin_ids[0]]
                if isinstance(first, dict) and "metrics" in first:
                    flat = {}
                    for k, v in first["metrics"].items():
                        if isinstance(v, (list, np.ndarray)):
                            flat[k] = float(v[0]) if len(v) > 0 else None
                        else:
                            flat[k] = v
                    # Also save to json for traceability
                    import json
                    (train_dir / "metrics.json").write_text(
                        json.dumps(flat, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                    return flat

    except Exception as e:
        logger.warning(f"Train period evaluation failed: {e}")
    return {}


def _inject_negated_losses():
    """Add neg_nashsutcliffe / neg_kge / neg_lognashsutcliffe to hydromodel's LOSS_DICT.

    SCE-UA and GA both *minimize* the objective. For metrics where higher is
    better (NSE, KGE, LogNSE) we must negate the function so that minimizing
    the negated value equals maximizing the original metric.
    """
    try:
        import spotpy.objectivefunctions as _sof
        from hydromodel.models.model_dict import LOSS_DICT

        if "neg_nashsutcliffe" not in LOSS_DICT:
            LOSS_DICT["neg_nashsutcliffe"] = lambda obs, sim: -_sof.nashsutcliffe(obs, sim)
        if "neg_kge" not in LOSS_DICT:
            LOSS_DICT["neg_kge"] = lambda obs, sim: -_sof.kge(obs, sim)
        if "neg_lognashsutcliffe" not in LOSS_DICT:
            LOSS_DICT["neg_lognashsutcliffe"] = lambda obs, sim: -_sof.lognashsutcliffe(obs, sim)
    except Exception:
        pass


def _clear_caches():
    """Clear xarray and gc caches for retry."""
    try:
        import xarray as xr
        if hasattr(xr.backends, "file_manager") and hasattr(xr.backends.file_manager, "_FILE_CACHE"):
            xr.backends.file_manager._FILE_CACHE.clear()
    except Exception:
        pass
    try:
        import gc
        gc.collect()
    except Exception:
        pass
