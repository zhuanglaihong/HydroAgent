"""
Author: HydroClaw Team
Date: 2026-02-08
Description: Model simulation tool - run model with given parameters.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def run_simulation(
    calibration_dir: str,
    sim_period: list[str] | None = None,
    params: dict | None = None,
    _workspace: Path | None = None,
    _cfg: dict | None = None,
) -> dict:
    """Run a hydrological model simulation with calibrated or given parameters.

    Args:
        calibration_dir: Path to calibration directory (to load config and params)
        sim_period: Simulation period ["YYYY-MM-DD", "YYYY-MM-DD"], defaults to test period
        params: Optional parameter dict override (if not loading from calibration)

    Returns:
        {"metrics": {...}, "simulation_dir": "...", "success": bool}
    """
    try:
        from hydromodel import evaluate as hm_evaluate
        from hydromodel.configs.config_manager import load_config_from_calibration
    except ImportError as e:
        return {"error": f"hydromodel not available: {e}", "success": False}

    logger.info(f"Running simulation from: {calibration_dir}")

    try:
        config = load_config_from_calibration(calibration_dir)
        period = sim_period or config.get("data_cfgs", {}).get("test_period")

        result = hm_evaluate(
            config,
            param_dir=calibration_dir,
            eval_period=period,
            eval_output_dir=None,
        )

        return {
            "simulation_dir": calibration_dir,
            "sim_period": period,
            "raw_result": str(type(result)),
            "success": True,
        }

    except Exception as e:
        logger.error(f"Simulation failed: {e}", exc_info=True)
        return {"error": f"Simulation failed: {e}", "success": False}
