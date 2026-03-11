"""
Author: HydroClaw Team
Date: 2026-02-08
Description: Model evaluation tool - evaluate a calibrated model on any time period.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def evaluate_model(
    calibration_dir: str,
    eval_period: list[str] | None = None,
    output_subdir: str | None = None,
    _workspace: Path | None = None,
    _cfg: dict | None = None,
) -> dict:
    """Evaluate a calibrated hydrological model on any time period.

    Call this after calibrate_model to get NSE/KGE/RMSE metrics. Can be called
    multiple times with different eval_period to get both train and test metrics.

    Args:
        calibration_dir: Path to calibration output directory (from calibrate_model)
        eval_period: Evaluation period ["YYYY-MM-DD", "YYYY-MM-DD"].
                     If None, uses the test_period saved in calibration config.
        output_subdir: Subdirectory name inside calibration_dir for saving results.
                       Defaults to "train_metrics" or "test_metrics" based on eval_period
                       vs the config's train/test split.

    Returns:
        {"metrics": {"NSE": ..., "KGE": ..., "RMSE": ..., ...},
         "eval_period": [...], "metrics_dir": "...", "output_files": [...], "success": True}
    """
    from hydroclaw.utils.result_parser import parse_evaluation_result

    try:
        from hydromodel.trainers.unified_evaluate import evaluate
        from hydromodel.configs.config_manager import load_config_from_calibration
    except ImportError as e:
        return {"error": f"hydromodel not available: {e}", "success": False}

    logger.info(f"Evaluating model from: {calibration_dir}")

    cal_path = Path(calibration_dir)

    # --- Pre-flight checks: give Agent actionable diagnosis before even trying ---
    if not cal_path.exists():
        return {
            "error": f"calibration_dir not found: {calibration_dir}",
            "success": False,
            "diagnosis": {"calibration_dir_exists": False},
            "hint": "Check that calibrate_model completed successfully and returned the correct calibration_dir.",
        }

    config_candidates = list(cal_path.glob("calibration_config.yaml"))
    if not config_candidates:
        files_present = [f.name for f in cal_path.iterdir() if f.is_file()]
        return {
            "error": "calibration_config.yaml not found — cannot load calibration config.",
            "success": False,
            "diagnosis": {
                "calibration_dir_exists": True,
                "files_found": files_present,
            },
            "hint": (
                "calibration_config.yaml is missing. "
                f"Files present: {files_present}. "
                "This may mean calibration did not complete. "
                f"Call inspect_dir('{calibration_dir}') to investigate."
            ),
        }

    try:
        config = load_config_from_calibration(calibration_dir)
        actual_period = eval_period or config["data_cfgs"]["test_period"]

        # Auto-name output subdir based on period vs config train/test split
        if output_subdir is None:
            train_period = config["data_cfgs"].get("train_period", [])
            test_period = config["data_cfgs"].get("test_period", [])
            if actual_period == train_period:
                output_subdir = "train_metrics"
            elif actual_period == test_period:
                output_subdir = "test_metrics"
            else:
                start = actual_period[0][:7].replace("-", "")
                end = actual_period[1][:7].replace("-", "")
                output_subdir = f"eval_{start}_{end}"

        metrics_dir = cal_path / output_subdir
        metrics_dir.mkdir(exist_ok=True)

        # hydromodel prints emoji (e.g. 📊) which crashes on GBK terminals (Windows).
        # Temporarily reconfigure stdout to utf-8 with replacement for unknown chars.
        import sys as _sys
        if hasattr(_sys.stdout, "reconfigure"):
            try:
                _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

        result = evaluate(
            config,
            param_dir=calibration_dir,
            eval_period=actual_period,
            eval_output_dir=str(metrics_dir),
        )

        parsed = parse_evaluation_result(result, calibration_dir=str(metrics_dir))
        metrics = parsed.get("metrics", {})

        # Point Agent to the exact CSV file it can read for full metric details
        metrics_csv = metrics_dir / "basins_metrics.csv"
        observable = {"metrics_csv": str(metrics_csv)} if metrics_csv.exists() else {}

        return {
            "metrics": metrics,
            "eval_period": actual_period,
            "metrics_dir": str(metrics_dir),
            "observable_files": observable,
            "output_files": parsed.get("output_files", []),
            "success": True,
            "hint": (
                f"Full metrics saved to {metrics_dir / 'basins_metrics.csv'}. "
                "Call read_file(observable_files['metrics_csv']) to see all columns."
            ) if metrics_csv.exists() else None,
        }

    except Exception as e:
        logger.error(f"Evaluation failed: {e}", exc_info=True)
        files_present = [f.name for f in cal_path.iterdir() if f.is_file()]
        return {
            "error": f"Evaluation failed: {e}",
            "success": False,
            "diagnosis": {
                "calibration_dir_exists": True,
                "files_found": files_present,
                "eval_period_requested": eval_period,
            },
            "hint": (
                f"Calibration directory exists with files: {files_present}. "
                f"Call read_file('{calibration_dir}/calibration_config.yaml') "
                "to inspect the config and verify train/test periods match your request."
            ),
        }


evaluate_model.__agent_hint__ = (
    "Requires calibration_dir from calibrate_model. "
    "eval_period=None uses the test period from calibration config (typical for final evaluation). "
    "Call twice — once with train period, once with None — to get both train and test metrics."
)
