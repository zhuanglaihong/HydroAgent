"""
Author: HydroAgent Team
Date: 2026-02-08
Description: Visualization tool - routes to the appropriate PackageAdapter.
"""

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

logger = logging.getLogger(__name__)


def visualize(
    calibration_dir: str,
    plot_types: list[str] | None = None,
    basin_ids: list[str] | None = None,
    _workspace: Path | None = None,
) -> dict:
    """Generate visualization plots for calibration/evaluation results.

    Args:
        calibration_dir: Path to calibration output directory
        plot_types: Plot types to generate, e.g. ["timeseries", "scatter"]. Defaults to ["timeseries", "scatter"]
        basin_ids: Specific basin IDs to plot, defaults to all

    Returns:
        {"plot_files": [...], "plot_count": int}
    """
    from hydroagent.adapters import get_adapter

    adapter = get_adapter("camels_us", "")
    return adapter.execute("visualize",
        workspace=_workspace or Path("."),
        calibration_dir=calibration_dir,
        plot_types=plot_types,
        basin_ids=basin_ids,
        _workspace=_workspace,
    )


visualize.__agent_hint__ = (
    "Requires calibration_dir (from calibrate_model) or eval_dirs list. "
    "plot_types defaults to ['timeseries', 'scatter']. "
    "The web UI will automatically display the images inline in the chat -- "
    "do NOT say you cannot show images. Just tell the user the plots have been generated "
    "and briefly describe what each figure shows."
)
