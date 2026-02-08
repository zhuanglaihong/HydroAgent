"""
Author: HydroAgent Team
Date: 2025-01-25 11:15:00
LastEditTime: 2025-01-25 11:15:00
LastEditors: HydroAgent Team
Description: Visualization tool for plotting model results
FilePath: /HydroAgent/hydroagent/tools/visualization_tool.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from hydroagent.tools.base_tool import (
    BaseTool,
    ToolResult,
    ToolMetadata,
    ToolCategory,
)
from typing import Dict, Any, List
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class VisualizationTool(BaseTool):
    """
    Visualization tool for hydrological model results.

    Generates plots for:
    - Hydrographs (observed vs simulated)
    - Metrics visualization
    - Parameter distributions
    """

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)

    def _define_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="visualize",
            description="绘制模型结果可视化图表 (Visualize model results)",
            category=ToolCategory.VISUALIZATION,
            version="1.0.0",
            input_schema={
                "calibration_dir": "str - Calibration directory",
                "basin_ids": "Optional[List[str]] - Basin IDs to plot (default: all)",
                "plot_types": "Optional[List[str]] - Plot types (default: ['hydrograph', 'metrics'])"
            },
            output_schema={
                "plot_files": "List[str] - Generated plot file paths",
                "plot_count": "int - Number of plots generated"
            },
            dependencies=[],  # Can be used after calibrate or evaluate
            required_config_keys=["calibration_dir"]
        )

    def execute(self, inputs: Dict[str, Any]) -> ToolResult:
        """
        Execute visualization.

        Args:
            inputs: Visualization parameters

        Returns:
            ToolResult: Visualization result
        """
        calibration_dir = inputs["calibration_dir"]
        basin_ids = inputs.get("basin_ids")
        plot_types = inputs.get("plot_types", ["timeseries", "scatter"])

        try:
            # Import hydromodel plotting
            try:
                from hydromodel.datasets.data_visualize import visualize_evaluation
            except ImportError as e:
                self.logger.error(f"[VisualizationTool] Failed to import hydromodel: {e}")
                return ToolResult(
                    success=False,
                    error=f"hydromodel plotting not available: {str(e)}"
                )

            self.logger.info(f"[VisualizationTool] Generating plots for {calibration_dir}")

            # Find evaluation directories under calibration_dir
            from pathlib import Path
            calib_path = Path(calibration_dir)

            # Look for evaluation_* directories
            eval_dirs = list(calib_path.glob("evaluation_*"))

            if not eval_dirs:
                # No evaluation directory found, try to use calibration_dir directly
                # This might work if NetCDF files are in the calibration directory
                self.logger.warning(f"[VisualizationTool] No evaluation_* directories found in {calibration_dir}")
                self.logger.info(f"[VisualizationTool] Attempting to visualize using calibration directory directly")
                eval_dirs = [calib_path]

            plot_files = []
            all_success = True

            # Generate plots for each evaluation directory
            for eval_dir in eval_dirs:
                self.logger.info(f"[VisualizationTool] Visualizing: {eval_dir}")

                try:
                    # Map plot types (HydroAgent uses different names than hydromodel)
                    # HydroAgent: hydrograph, metrics
                    # hydromodel: timeseries, scatter, fdc, monthly
                    hydro_plot_types = []
                    for pt in plot_types:
                        if pt == "hydrograph":
                            hydro_plot_types.append("timeseries")
                        elif pt == "metrics":
                            hydro_plot_types.append("scatter")
                        else:
                            hydro_plot_types.append(pt)

                    # Use default if no mapping found
                    if not hydro_plot_types:
                        hydro_plot_types = ["timeseries", "scatter"]

                    self.logger.info(f"[VisualizationTool] Plot types: {hydro_plot_types}")

                    # Call hydromodel's visualize_evaluation
                    visualize_evaluation(
                        eval_dir=str(eval_dir),
                        output_dir=None,  # Use default: eval_dir/figures
                        plot_types=hydro_plot_types,
                        basins=basin_ids
                    )

                    # Collect generated plot files
                    figures_dir = eval_dir / "figures"
                    if figures_dir.exists():
                        for plot_file in figures_dir.glob("*.png"):
                            plot_files.append(str(plot_file))

                    self.logger.info(f"[VisualizationTool] Successfully visualized {eval_dir.name}")

                except Exception as e:
                    self.logger.warning(f"[VisualizationTool] Failed to visualize {eval_dir}: {e}")
                    all_success = False

            if not plot_files and not all_success:
                return ToolResult(
                    success=False,
                    error="All visualization attempts failed"
                )

            self.logger.info(f"[VisualizationTool] Generated {len(plot_files)} plots")

            return ToolResult(
                success=True,
                data={
                    "plot_files": plot_files,
                    "plot_count": len(plot_files)
                },
                metadata={
                    "calibration_dir": calibration_dir,
                    "evaluation_dirs": [str(d) for d in eval_dirs],
                    "basin_count": len(basin_ids) if basin_ids else 0,
                    "plot_types": plot_types
                }
            )

        except Exception as e:
            self.logger.error(f"[VisualizationTool] Visualization failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                error=f"Visualization error: {str(e)}"
            )
