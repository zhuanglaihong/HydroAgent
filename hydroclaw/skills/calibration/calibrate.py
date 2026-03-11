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
        algorithm_params: Dict of algorithm parameter overrides. Must be a dict, NOT a string.
            Pass None to use project defaults (recommended for most cases).
            SCE_UA keys: rep (total evaluations), ngs (complexes), kstop (convergence steps).
              e.g. {"rep": 200, "ngs": 50} for a quick test, {"rep": 1500, "ngs": 300} for
              high-quality results. Default: rep=750, ngs=200.
            GA keys: pop_size, n_generations. e.g. {"pop_size": 20, "n_generations": 10}.
            scipy keys: method ("SLSQP"/"L-BFGS-B"), max_iterations. e.g. {"method": "SLSQP", "max_iterations": 30}.
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

    output_dir = config["training_cfgs"]["output_dir"]

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
                return _calibration_error(str(e2), output_dir)
        else:
            return _calibration_error(error_msg, output_dir)

    # Parse results - hydromodel calibrate() only returns best_params + objective_value,
    # NOT NSE/KGE metrics. To get metrics, call evaluate_model() explicitly afterwards.
    parsed = parse_calibration_result(result, config)
    cal_dir = parsed.get("calibration_dir", "")

    # Build list of key files the Agent can read to observe the calibration output
    observable_files = {}
    if cal_dir:
        from pathlib import Path as _Path
        _d = _Path(cal_dir)
        for fname in ["calibration_results.json", "basins_denorm_params.csv",
                      "param_range.yaml", "calibration_config.yaml"]:
            if (_d / fname).exists():
                observable_files[fname] = str(_d / fname)

    return {
        "best_params": parsed.get("best_params", {}),
        "calibration_dir": cal_dir,
        "train_period": config["data_cfgs"]["train_period"],
        "test_period": config["data_cfgs"]["test_period"],
        "output_files": parsed.get("output_files", []),
        "observable_files": observable_files,
        "model_name": model_name,
        "algorithm": algorithm,
        "basin_ids": basin_ids,
        "success": True,
        "next_steps": [
            f"Call evaluate_model('{cal_dir}', eval_period=train_period) to get train NSE/KGE.",
            f"Call evaluate_model('{cal_dir}', eval_period=test_period) to get test NSE/KGE.",
            "Or call inspect_dir(calibration_dir) to see all output files.",
            "Or call read_file(observable_files['calibration_results.json']) to inspect raw parameters.",
        ],
    }


def _calibration_error(error_msg: str, output_dir: str) -> dict:
    """Return a diagnostic error dict so the Agent can reason about what went wrong."""
    from pathlib import Path as _Path
    p = _Path(output_dir)
    diagnosis = {
        "output_dir_exists": p.exists(),
        "files_found": [f.name for f in p.iterdir() if f.is_file()] if p.exists() else [],
    }
    hint = ""
    if "HDF error" in error_msg or "NetCDF" in error_msg:
        hint = "HDF/NetCDF file lock — try again or call inspect_dir(output_dir) to check partial output."
    elif "No such file" in error_msg or "dataset" in error_msg.lower():
        hint = "Dataset path issue — check DATASET_DIR in configs/private.py points to the parent of CAMELS_US/."
    elif not diagnosis["output_dir_exists"]:
        hint = "Output directory was never created — calibration likely failed before writing any files."
    else:
        hint = f"Use inspect_dir('{output_dir}') to see what was produced before the failure."

    return {
        "error": f"Calibration failed: {error_msg}",
        "success": False,
        "diagnosis": diagnosis,
        "hint": hint,
    }



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


calibrate_model.__agent_hint__ = (
    "Returns calibration_dir and best_params — NO metrics (NSE/KGE). "
    "Must call evaluate_model(calibration_dir=...) separately to get metrics. "
    "If NSE is low, check if params hit boundaries via read_file(calibration_results.json)."
)
