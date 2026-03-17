"""
Author: HydroClaw Team
Date: 2026-03-06
Description: Model simulation tool - routes to the appropriate PackageAdapter.
"""

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
    from hydroclaw.adapters import get_adapter

    adapter = get_adapter("camels_us", "")
    return adapter.execute("simulate",
        workspace=_workspace or Path("."),
        calibration_dir=calibration_dir,
        sim_period=sim_period,
        params=params,
    )


run_simulation.__zh_name__ = "径流模拟"
run_simulation.__zh_desc__ = "使用率定参数对指定时段进行径流模拟，输出预测流量序列"
