"""
Author: HydroClaw Team
Date: 2026-02-08
Description: Model calibration tool - calls hydromodel for parameter optimization.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
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

    logger.info(
        f"Starting calibration: {model_name}/{algorithm} for basins {basin_ids}"
    )

    # Run calibration with timeout and retry
    timeout_seconds = 7200
    max_retries = 3
    result = None

    for attempt in range(max_retries + 1):
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(hm_calibrate, config)
                start = time.time()
                while True:
                    try:
                        result = future.result(timeout=0.5)
                        break
                    except FutureTimeoutError:
                        if time.time() - start > timeout_seconds:
                            future.cancel()
                            return {"error": f"Calibration timed out after {timeout_seconds}s", "success": False}
                    except KeyboardInterrupt:
                        logger.warning("Calibration interrupted by user")
                        future.cancel()
                        raise
            break  # Success

        except KeyboardInterrupt:
            raise
        except Exception as e:
            error_msg = str(e)
            is_retryable = "NetCDF: HDF error" in error_msg or "KeyError" in error_msg
            if is_retryable and attempt < max_retries:
                logger.warning(f"Retryable error (attempt {attempt+1}): {e}")
                _clear_caches()
                time.sleep(0.5 * (2 ** attempt))
                continue
            return {"error": f"Calibration failed: {e}", "success": False}

    # Parse results
    parsed = parse_calibration_result(result, config)

    return {
        "best_params": parsed.get("best_params", {}),
        "metrics": parsed.get("metrics", {}),
        "calibration_dir": parsed.get("calibration_dir", ""),
        "output_files": parsed.get("output_files", []),
        "model_name": model_name,
        "algorithm": algorithm,
        "basin_ids": basin_ids,
        "success": True,
    }


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
