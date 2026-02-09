"""
Author: HydroClaw Team
Date: 2026-02-08
Description: Model evaluation tool.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def evaluate_model(
    calibration_dir: str,
    test_period: list[str] | None = None,
    _workspace: Path | None = None,
    _cfg: dict | None = None,
) -> dict:
    """Evaluate a calibrated hydrological model on the test period.

    Args:
        calibration_dir: Path to calibration output directory
        test_period: Test period ["YYYY-MM-DD", "YYYY-MM-DD"], loaded from config if not given

    Returns:
        {"metrics": {"NSE": ..., "RMSE": ..., ...}, "calibration_dir": "...", "output_files": [...]}
    """
    from hydroclaw.utils.result_parser import parse_evaluation_result

    try:
        from hydromodel.trainers.unified_evaluate import evaluate
        from hydromodel.configs.config_manager import load_config_from_calibration
    except ImportError as e:
        return {"error": f"hydromodel not available: {e}", "success": False}

    logger.info(f"Evaluating model from: {calibration_dir}")

    try:
        config = load_config_from_calibration(calibration_dir)
        eval_period = test_period or config["data_cfgs"]["test_period"]

        result = evaluate(
            config,
            param_dir=calibration_dir,
            eval_period=eval_period,
            eval_output_dir=None,
        )

        parsed = parse_evaluation_result(result, calibration_dir=calibration_dir)

        return {
            "metrics": parsed.get("metrics", {}),
            "calibration_dir": calibration_dir,
            "output_files": parsed.get("output_files", []),
            "test_period": eval_period,
            "success": True,
        }

    except Exception as e:
        logger.error(f"Evaluation failed: {e}", exc_info=True)
        return {"error": f"Evaluation failed: {e}", "success": False}
