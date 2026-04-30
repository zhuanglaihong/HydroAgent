"""
Author: HydroAgent Team
Date: 2026-02-08
Description: Model evaluation tool - routes to the appropriate PackageAdapter.
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
    from hydroagent.adapters import get_adapter

    # data_source/model_name not needed here since hydromodel adapter handles all calibration dirs
    adapter = get_adapter("camels_us", "")
    return adapter.execute("evaluate",
        workspace=_workspace or Path("."),
        calibration_dir=calibration_dir,
        eval_period=eval_period,
        output_subdir=output_subdir,
        _workspace=_workspace,
        _cfg=_cfg,
    )


evaluate_model.__agent_hint__ = (
    "Requires calibration_dir from calibrate_model. "
    "eval_period=None uses the test period from calibration config (typical for final evaluation). "
    "Call twice -- once with train period, once with None -- to get both train and test metrics."
)
