"""
Author: HydroAgent Team
Date: 2025-01-25 11:00:00
LastEditTime: 2025-01-25 11:00:00
LastEditors: HydroAgent Team
Description: Model calibration tool (decoupled from evaluation and visualization)
FilePath: /HydroAgent/hydroagent/tools/calibration_tool.py
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

# 🔧 Fix tkinter threading issues in matplotlib
# Force matplotlib to use non-GUI backend (Agg) before any imports that might use it
import matplotlib
matplotlib.use('Agg')  # Must be before importing pyplot or any plotting code

logger = logging.getLogger(__name__)


class CalibrationTool(BaseTool):
    """
    Hydrological model calibration tool.

    **Key Difference from RunnerAgent._run_calibration():**
    - This tool ONLY performs calibration
    - NO automatic evaluation
    - NO automatic visualization
    - Evaluation and visualization are now separate tools

    Dependencies:
    - validate_data: Data must be validated before calibration
    """

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)

    def _define_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="calibrate",
            description="执行水文模型参数率定 (Calibrate hydrological model parameters)",
            category=ToolCategory.CALIBRATION,
            version="1.0.0",
            input_schema={
                "config": "Dict - Hydromodel configuration dictionary with data_cfgs, model_cfgs, training_cfgs",
                "show_progress": "bool - Whether to show progress (default: True)"
            },
            output_schema={
                "calibration_dir": "str - Output directory path",
                "best_params": "Dict - Optimized parameters for each basin",
                "calibration_metrics": "Dict - Training period metrics",
                "output_files": "List[str] - Generated output files",
                "raw_result": "Any - Raw hydromodel result"
            },
            dependencies=["validate_data"],
            required_config_keys=["config"]
        )

    def execute(self, inputs: Dict[str, Any]) -> ToolResult:
        """
        Execute model calibration.

        Args:
            inputs: Calibration parameters

        Returns:
            ToolResult: Calibration result
        """
        config = inputs["config"]
        show_progress = inputs.get("show_progress", True)
        use_mock = inputs.get("use_mock", False)  # 🆕 Mock mode support

        # 🆕 Mock mode for testing
        if use_mock:
            self.logger.info("[CalibrationTool] Using MOCK mode for testing")
            return self._execute_mock(config)

        try:
            # Import hydromodel
            try:
                from hydromodel import calibrate
                from hydroagent.utils import result_parser
            except ImportError as e:
                self.logger.error(f"[CalibrationTool] Failed to import hydromodel: {e}")
                return ToolResult(
                    success=False,
                    error=f"hydromodel not available: {str(e)}"
                )

            # 🔧 DEBUG: Log complete config structure before calling hydromodel
            # import json
            # self.logger.info(f"[CalibrationTool] DEBUG: 完整的model_cfgs:")
            # self.logger.info(json.dumps(config.get("model_cfgs", {}), indent=2, ensure_ascii=False))
            # self.logger.info(f"[CalibrationTool] DEBUG: 完整的training_cfgs:")
            # self.logger.info(json.dumps(config.get("training_cfgs", {}), indent=2, ensure_ascii=False))

            # Capture output
            stdout_capture = StringIO()
            stderr_capture = StringIO()
            old_stdout = sys.stdout
            old_stderr = sys.stderr

            try:
                if show_progress:
                    # Show progress to user (simplified - no filtering)
                    # In production, could use TeeIO for better control
                    self.logger.info("[CalibrationTool] Running calibration (showing progress)...")
                else:
                    # Silent mode
                    sys.stdout = stdout_capture
                    sys.stderr = stderr_capture
                    self.logger.info("[CalibrationTool] Running calibration (silent mode)...")

                # Execute calibration with retry for NetCDF errors
                self.logger.info("[CalibrationTool] Calling calibrate(config)")

                # 🚨 CRITICAL FIX: Retry on NetCDF HDF errors
                # xarray's file cache can become corrupted in batch processing
                max_retries = 5  # 增加重试次数
                result = None
                last_error = None

                for attempt in range(max_retries + 1):
                    try:
                        # 🆕 添加超时机制（防止死锁，但给复杂任务足够时间）
                        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
                        import time

                        # 超时设置：7200秒 = 2小时
                        # 理由：XAJ+GA(100代)或SCE-UA(rep=500)等复杂任务可能需要1-2小时
                        # 用户可随时通过Ctrl+C中断
                        timeout_seconds = 7200  # 2 hours
                        self.logger.info(f"[CalibrationTool] Starting calibration with {timeout_seconds}s timeout...")

                        with ThreadPoolExecutor(max_workers=1) as executor:
                            future = executor.submit(calibrate, config)

                            # 🔧 Improved: Use polling to check for KeyboardInterrupt
                            # Instead of blocking with future.result(timeout), poll every 0.1s for faster response
                            start_time = time.time()
                            poll_interval = 0.1  # 🔧 Reduced from 0.5s to 0.1s for faster Ctrl+C response
                            interrupt_count = 0  # Track consecutive Ctrl+C presses

                            try:
                                while True:
                                    try:
                                        # Try to get result with short timeout (non-blocking polling)
                                        result = future.result(timeout=poll_interval)
                                        # Success - break out of BOTH while loop AND retry for loop
                                        break
                                    except FutureTimeoutError:
                                        # Check if overall timeout exceeded
                                        elapsed = time.time() - start_time
                                        if elapsed > timeout_seconds:
                                            self.logger.error(f"[CalibrationTool] Calibration timed out after {timeout_seconds}s")
                                            future.cancel()
                                            executor.shutdown(wait=False, cancel_futures=True)
                                            raise TimeoutError(f"Calibration exceeded {timeout_seconds}s timeout")
                                        # Otherwise, continue polling (this allows KeyboardInterrupt to be caught)
                            except KeyboardInterrupt:
                                interrupt_count += 1
                                if interrupt_count == 1:
                                    # First Ctrl+C: try graceful shutdown
                                    self.logger.warning("[CalibrationTool] ⚠️ User interrupted calibration (Ctrl+C)")
                                    self.logger.warning("[CalibrationTool] Waiting for current iteration to complete...")
                                    self.logger.warning("[CalibrationTool] Press Ctrl+C again to force exit")
                                    future.cancel()  # Try to cancel the running task
                                    executor.shutdown(wait=True, cancel_futures=True)  # Wait for cleanup
                                    raise KeyboardInterrupt("Calibration interrupted by user")
                                else:
                                    # Second Ctrl+C: force exit
                                    self.logger.error("[CalibrationTool] 🚨 Force exit requested!")
                                    executor.shutdown(wait=False, cancel_futures=True)  # Force shutdown
                                    raise KeyboardInterrupt("Calibration force-exited by user")

                        # 🔧 If we got here and have a result, break out of retry loop
                        if result is not None:
                            break
                    except KeyboardInterrupt:
                        # 🔧 Re-raise KeyboardInterrupt without retry
                        self.logger.warning("[CalibrationTool] Calibration interrupted by user, exiting...")
                        raise
                    except Exception as e:
                        error_msg = str(e)
                        last_error = e

                        # Check if it's a NetCDF cache error or timeout
                        is_netcdf_cache_error = (
                            "NetCDF: HDF error" in error_msg or
                            "KeyError" in error_msg and "netCDF4" in error_msg or
                            "xarray.backends.lru_cache" in error_msg
                        )
                        is_timeout = isinstance(e, TimeoutError) or "timeout" in error_msg.lower()
                        is_retryable = is_netcdf_cache_error or is_timeout

                        if is_retryable and attempt < max_retries:
                            error_type = "Timeout" if is_timeout else "NetCDF cache error"
                            self.logger.warning(
                                f"[CalibrationTool] {error_type} (attempt {attempt+1}/{max_retries+1}), "
                                "clearing cache and retrying..."
                            )

                            # Clear xarray file cache
                            try:
                                import xarray as xr
                                if hasattr(xr.backends.file_manager, '_FILE_CACHE'):
                                    xr.backends.file_manager._FILE_CACHE.clear()
                                    self.logger.info("[CalibrationTool] Cleared xarray file cache")
                            except Exception as cache_error:
                                self.logger.warning(f"[CalibrationTool] Failed to clear cache: {cache_error}")

                            # Clear Python's module cache for data loaders
                            try:
                                import gc
                                gc.collect()  # Force garbage collection
                                self.logger.info("[CalibrationTool] Forced garbage collection")
                            except Exception as gc_error:
                                self.logger.warning(f"[CalibrationTool] GC failed: {gc_error}")

                            # Wait longer before retry (exponential backoff)
                            import time
                            wait_time = 0.5 * (2 ** attempt)  # 0.5, 1, 2, 4, 8 seconds
                            self.logger.info(f"[CalibrationTool] Waiting {wait_time}s before retry...")
                            time.sleep(wait_time)
                            continue
                        else:
                            # Not a cache error or max retries reached, re-raise
                            raise

                if result is None:
                    # All retries failed
                    raise last_error

            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr

            self.logger.info("[CalibrationTool] Calibration completed")

            # Parse result
            parsed_result = result_parser.parse_calibration_result(result, config)
            calibration_dir = parsed_result.get("calibration_dir")

            if not calibration_dir:
                self.logger.warning("[CalibrationTool] No calibration directory returned")
                return ToolResult(
                    success=False,
                    error="Calibration failed: no output directory"
                )

            self.logger.info(f"[CalibrationTool] Results saved to: {calibration_dir}")

            # ⭐ KEY DIFFERENCE: Return ONLY calibration results
            # NO automatic evaluation or visualization
            return ToolResult(
                success=True,
                data={
                    "calibration_dir": calibration_dir,
                    "best_params": parsed_result.get("best_params", {}),
                    "calibration_metrics": parsed_result.get("metrics", {}),
                    "output_files": parsed_result.get("output_files", []),
                    "raw_result": result
                },
                metadata={
                    "basin_count": len(config.get("data_cfgs", {}).get("basin_ids", [])),
                    "model": config.get("model_cfgs", {}).get("model_name", "unknown"),
                    "algorithm": config.get("training_cfgs", {}).get("algorithm", "unknown")
                }
            )

        except Exception as e:
            self.logger.error(f"[CalibrationTool] Calibration failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                error=f"Calibration error: {str(e)}"
            )

    def _execute_mock(self, config: Dict[str, Any]) -> ToolResult:
        """
        Execute mock calibration for testing.

        Args:
            config: Calibration configuration

        Returns:
            ToolResult: Mock calibration result
        """
        import json

        # Get output directory from config
        output_dir = config.get("training_cfgs", {}).get("output_dir")
        if not output_dir:
            return ToolResult(success=False, error="No output_dir in config")

        # Create output directory
        from pathlib import Path
        calibration_dir = Path(output_dir)
        calibration_dir.mkdir(parents=True, exist_ok=True)

        # Get basin IDs
        basin_ids = config.get("data_cfgs", {}).get("basin_ids", ["01013500"])
        model_name = config.get("model_cfgs", {}).get("model_name", "gr4j")

        # Create mock calibration results
        mock_params = {
            "gr4j": [350.0, -2.0, 50.0, 1.5],
            "xaj": [0.5, 0.3, 0.2, 0.1, 0.4, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5]
        }

        params = mock_params.get(model_name, [1.0, 2.0, 3.0, 4.0])

        calibration_results = {}
        for basin_id in basin_ids:
            calibration_results[basin_id] = {
                "params": params,
                "metrics": {
                    "NSE": 0.75,
                    "RMSE": 1.2,
                    "KGE": 0.70,
                    "PBIAS": -5.5
                }
            }

        # Save calibration_results.json
        results_file = calibration_dir / "calibration_results.json"
        with open(results_file, "w") as f:
            json.dump(calibration_results, f, indent=2)

        self.logger.info(f"[CalibrationTool] Mock calibration results saved to: {calibration_dir}")

        return ToolResult(
            success=True,
            data={
                "calibration_dir": str(calibration_dir),
                "best_params": {basin_ids[0]: params} if basin_ids else {},
                "calibration_metrics": calibration_results.get(basin_ids[0], {}).get("metrics", {}) if basin_ids else {},
                "output_files": [str(results_file)],
                "raw_result": calibration_results
            },
            metadata={
                "basin_count": len(basin_ids),
                "model": model_name,
                "algorithm": "mock",
                "mock_mode": True
            }
        )

    def validate_inputs(self, inputs: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate calibration inputs.

        Args:
            inputs: Input parameters

        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        # Call parent validation
        is_valid, error = super().validate_inputs(inputs)
        if not is_valid:
            return is_valid, error

        # Check config structure
        config = inputs.get("config")
        if not isinstance(config, dict):
            return False, "config must be a dictionary"

        # Check required config sections
        required_sections = ["data_cfgs", "model_cfgs", "training_cfgs"]
        missing = [s for s in required_sections if s not in config]
        if missing:
            return False, f"config missing required sections: {missing}"

        # Check basin_ids in data_cfgs
        data_cfgs = config.get("data_cfgs", {})
        basin_ids = data_cfgs.get("basin_ids")
        if not basin_ids or not isinstance(basin_ids, list):
            return False, "data_cfgs.basin_ids must be a non-empty list"

        return True, None
