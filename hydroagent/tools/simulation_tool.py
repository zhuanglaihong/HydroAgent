"""
Author: HydroAgent Team
Date: 2025-12-24 20:00:00
LastEditTime: 2025-12-24 20:00:00
LastEditors: Claude
Description: Model simulation tool for generating predictions with given parameters
FilePath: /HydroAgent/hydroagent/tools/simulation_tool.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from hydroagent.tools.base_tool import (
    BaseTool,
    ToolResult,
    ToolMetadata,
    ToolCategory,
)
from typing import Dict, Any
import logging
import sys
from io import StringIO

logger = logging.getLogger(__name__)


class SimulationTool(BaseTool):
    """
    Hydrological model simulation tool.

    **Purpose:**
    - Generate streamflow predictions using calibrated parameters
    - Can run simulation on any time period (train, test, or custom)
    - Useful for scenario analysis or prediction tasks

    **Key Difference from CalibrationTool:**
    - Uses GIVEN parameters (no optimization)
    - Focuses on prediction rather than parameter fitting

    Dependencies:
    - Can be used independently OR after calibration
    - If used after calibration: depends on calibrate tool
    """

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)

    def _define_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="simulate",
            description="执行水文模型模拟预测 (Run hydrological model simulation)",
            category=ToolCategory.SIMULATION,
            version="1.0.0",
            input_schema={
                "config": "Dict - Hydromodel configuration dictionary",
                "params": "Dict - Model parameters for each basin (optional if loading from calibration)",
                "calibration_dir": "str - Calibration directory to load parameters from (optional)",
                "show_progress": "bool - Whether to show progress (default: True)"
            },
            output_schema={
                "simulation_dir": "str - Output directory path",
                "predictions": "Dict - Simulated streamflow for each basin",
                "output_files": "List[str] - Generated output files",
                "raw_result": "Any - Raw hydromodel result"
            },
            dependencies=[],  # Optional dependency on calibrate
            required_config_keys=["config"]
        )

    def execute(self, inputs: Dict[str, Any]) -> ToolResult:
        """
        Execute model simulation.

        Args:
            inputs: Simulation parameters
                - config: Hydromodel configuration
                - params: Model parameters (optional if loading from calibration)
                - calibration_dir: Calibration directory (optional)
                - show_progress: Show progress (default: True)

        Returns:
            ToolResult: Simulation result
        """
        config = inputs["config"]
        params = inputs.get("params")
        calibration_dir = inputs.get("calibration_dir")
        show_progress = inputs.get("show_progress", True)

        try:
            # Import hydromodel
            try:
                from hydromodel import UnifiedSimulator
                from hydroagent.utils import result_parser
                from pathlib import Path
                import json
                import numpy as np
            except ImportError as e:
                self.logger.error(f"[SimulationTool] Failed to import dependencies: {e}")
                return ToolResult(
                    success=False,
                    error=f"Required dependencies not available: {str(e)}"
                )

            # Determine parameter source
            if params is None and calibration_dir is None:
                return ToolResult(
                    success=False,
                    error="Either 'params' or 'calibration_dir' must be provided"
                )

            # Load parameters from calibration if needed
            if params is None and calibration_dir:
                self.logger.info(f"[SimulationTool] Loading parameters from: {calibration_dir}")
                try:
                    import json
                    calib_path = Path(calibration_dir)
                    results_file = calib_path / "calibration_results.json"

                    if not results_file.exists():
                        return ToolResult(
                            success=False,
                            error=f"Calibration results file not found: {results_file}"
                        )

                    with open(results_file, 'r', encoding='utf-8') as f:
                        calib_results = json.load(f)

                    # Extract parameters from calibration results
                    # Structure: {"basin_id": {"best_params": {"model_name": {...}}}}
                    params = {}
                    for basin_id, basin_data in calib_results.items():
                        if "best_params" in basin_data:
                            params[basin_id] = basin_data["best_params"]

                    if not params:
                        return ToolResult(
                            success=False,
                            error="No parameters found in calibration results"
                        )

                    self.logger.info(f"[SimulationTool] Loaded parameters for {len(params)} basin(s)")

                except Exception as e:
                    return ToolResult(
                        success=False,
                        error=f"Failed to load parameters from calibration: {str(e)}"
                    )

            # Capture output
            stdout_capture = StringIO()
            stderr_capture = StringIO()
            old_stdout = sys.stdout
            old_stderr = sys.stderr

            try:
                if show_progress:
                    self.logger.info("[SimulationTool] Running simulation (showing progress)...")
                else:
                    self.logger.info("[SimulationTool] Running simulation (silent mode)...")
                    sys.stdout = stdout_capture
                    sys.stderr = stderr_capture

                # Run simulation using evaluate() function
                # Note: evaluate() internally performs simulation and handles all data loading
                self.logger.info("[SimulationTool] Running simulation via evaluate()")

                # Determine simulation period (use test period by default)
                sim_period = config.get("data_cfgs", {}).get("test_period",
                                                              config.get("data_cfgs", {}).get("train_period"))

                self.logger.info(f"[SimulationTool] Simulation period: {sim_period}")

                # Use evaluate function which internally handles:
                # - Data loading with correct variable name mapping
                # - Parameter loading from calibration_dir
                # - Running simulation with UnifiedSimulator
                from hydromodel import evaluate

                result = evaluate(
                    config,
                    param_dir=calibration_dir,
                    eval_period=sim_period,
                    eval_output_dir=None
                )

                # Restore stdout/stderr
                sys.stdout = old_stdout
                sys.stderr = old_stderr

                # Parse and save result
                self.logger.info("[SimulationTool] Simulation completed successfully")

                # Extract info for saving
                basin_ids = config.get("data_cfgs", {}).get("basin_ids", [])

                # Create output directory
                output_dir = config.get("training_cfgs", {}).get("output_dir", "results")
                output_dir = Path(output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)

                # Save simulation results
                simulation_file = output_dir / "simulation_results.json"
                with open(simulation_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        "basin_ids": basin_ids,
                        "simulation_period": sim_period,
                        "note": "Simulation performed using hydromodel.evaluate() function"
                    }, f, indent=2)

                parsed = {
                    "simulation_dir": str(output_dir),
                    "predictions": result.get("simulation") if isinstance(result, dict) else None,
                    "observation": result.get("observation") if isinstance(result, dict) else None,
                    "output_files": [str(simulation_file)],
                    "raw_result": result
                }

                self.logger.info(f"[SimulationTool] Simulation completed")
                self.logger.info(f"[SimulationTool] Output directory: {parsed.get('simulation_dir')}")

                return ToolResult(
                    success=True,
                    data={
                        "simulation_dir": parsed.get("simulation_dir"),
                        "predictions": parsed.get("predictions", {}),
                        "output_files": parsed.get("output_files", []),
                        "raw_result": result
                    }
                )

            except Exception as e:
                # Restore stdout/stderr on error
                sys.stdout = old_stdout
                sys.stderr = old_stderr

                self.logger.error(f"[SimulationTool] Simulation failed: {str(e)}")
                return ToolResult(
                    success=False,
                    error=f"Simulation failed: {str(e)}",
                    data={
                        "stdout": stdout_capture.getvalue(),
                        "stderr": stderr_capture.getvalue()
                    }
                )

        except Exception as e:
            self.logger.error(f"[SimulationTool] Unexpected error: {str(e)}")
            return ToolResult(
                success=False,
                error=f"Unexpected error: {str(e)}"
            )
