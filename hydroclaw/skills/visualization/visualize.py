"""
Author: HydroClaw Team
Date: 2026-02-08
Description: Visualization tool for model results.
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
    plot_types = plot_types or ["timeseries", "scatter"]

    try:
        from hydromodel.datasets.data_visualize import visualize_evaluation
    except ImportError as e:
        return {"error": f"hydromodel visualization not available: {e}", "plot_files": [], "plot_count": 0}

    calib_path = Path(calibration_dir)
    eval_dirs = list(calib_path.glob("evaluation_*"))
    if not eval_dirs:
        eval_dirs = [calib_path]

    plot_files = []

    for eval_dir in eval_dirs:
        try:
            # Map user-friendly names to hydromodel names
            hydro_types = []
            for pt in plot_types:
                if pt == "hydrograph":
                    hydro_types.append("timeseries")
                elif pt == "metrics":
                    hydro_types.append("scatter")
                else:
                    hydro_types.append(pt)

            visualize_evaluation(
                eval_dir=str(eval_dir),
                output_dir=None,
                plot_types=hydro_types or ["timeseries", "scatter"],
                basins=basin_ids,
            )

            figures_dir = eval_dir / "figures"
            if figures_dir.exists():
                for f in figures_dir.glob("*.png"):
                    plot_files.append(str(f))

        except Exception as e:
            logger.warning(f"Failed to visualize {eval_dir}: {e}")

    logger.info(f"Generated {len(plot_files)} plots")
    return {"plot_files": plot_files, "plot_count": len(plot_files)}


visualize.__agent_hint__ = (
    "Requires calibration_dir (from calibrate_model) or eval_dirs list. "
    "plot_types defaults to ['timeseries', 'scatter']. "
    "Returns plot_files paths — tell user where to find the images."
)
