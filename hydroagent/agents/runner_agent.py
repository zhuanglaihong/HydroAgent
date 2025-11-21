"""
Author: Claude & zhuanglaihong
Date: 2025-01-20 19:55:00
LastEditTime: 2025-01-20 19:55:00
LastEditors: Claude
Description: Execution and monitoring agent - runs hydromodel and captures output
             执行监控智能体 - 运行 hydromodel 并捕获输出
FilePath: \HydroAgent\hydroagent\agents\runner_agent.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from typing import Dict, Any, Optional
from pathlib import Path
import logging
import subprocess
import sys
from io import StringIO

from ..core.base_agent import BaseAgent
from ..core.llm_interface import LLMInterface

logger = logging.getLogger(__name__)


class RunnerAgent(BaseAgent):
    """
    Execution and monitoring agent.
    执行监控智能体。

    Similar to OpenFOAMGPT's Simulator.

    Responsibilities:
    - Execute hydromodel calibration/evaluation via API calls
    - Monitor process execution (stdout/stderr)
    - Capture errors and tracebacks
    - Provide feedback to Orchestrator for error recovery
    - Manage execution timeout and resource limits
    """

    def __init__(
        self,
        llm_interface: LLMInterface,
        workspace_dir: Optional[Path] = None,
        timeout: int = 3600,
        **kwargs
    ):
        """
        Initialize RunnerAgent.

        Args:
            llm_interface: LLM API interface
            workspace_dir: Working directory
            timeout: Execution timeout in seconds
            **kwargs: Additional configuration
        """
        super().__init__(
            name="RunnerAgent",
            llm_interface=llm_interface,
            workspace_dir=workspace_dir,
            **kwargs
        )

        self.timeout = timeout
        self.last_execution_log = None

    def _get_default_system_prompt(self) -> str:
        """Return default system prompt for RunnerAgent."""
        return """You are the Runner Agent of HydroAgent, responsible for executing hydromodel tasks.

Your tasks:
1. **API Execution**: Call hydromodel functions
   - calibrate() for parameter training
   - evaluate() for model testing
   - Proper error handling and logging

2. **Process Monitoring**: Track execution progress
   - Capture stdout and stderr
   - Monitor resource usage
   - Detect hanging processes

3. **Error Handling**: Capture and report errors
   - Python tracebacks
   - Configuration errors
   - Data loading failures
   - Numerical errors

4. **Result Collection**: Gather outputs
   - Calibration results (JSON, CSV)
   - Performance metrics (NSE, RMSE, etc.)
   - Generated plots and figures
   - Log files

If errors occur, provide detailed diagnostic information to help fix the issue."""

    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute hydromodel workflow.
        执行 hydromodel 工作流。

        Args:
            input_data: Execution configuration
                {
                    "config_path": str,
                    "mode": "calibrate"|"evaluate",
                    "workspace_dir": Path
                }

        Returns:
            Dict containing execution result
        """
        config_path = input_data.get("config_path")
        mode = input_data.get("mode", "calibrate")
        workspace_dir = input_data.get("workspace_dir", self.workspace_dir)

        logger.info(f"[RunnerAgent] Executing {mode} with config: {config_path}")

        try:
            if mode == "calibrate":
                result = self._run_calibration(config_path, workspace_dir)
            elif mode == "evaluate":
                result = self._run_evaluation(config_path, workspace_dir)
            else:
                raise ValueError(f"Unknown execution mode: {mode}")

            logger.info(f"[RunnerAgent] Execution completed successfully")

            return {
                "success": True,
                "result": result,
                "execution_log": self.last_execution_log
            }

        except Exception as e:
            logger.error(f"[RunnerAgent] Execution failed: {str(e)}")

            return {
                "success": False,
                "error": str(e),
                "traceback": self._format_traceback(),
                "execution_log": self.last_execution_log
            }

    def _run_calibration(self, config_path: str, workspace_dir: Path) -> Dict[str, Any]:
        """
        Run hydromodel calibration.
        运行 hydromodel 率定。

        Args:
            config_path: Path to configuration file
            workspace_dir: Working directory

        Returns:
            Calibration result
        """
        logger.info("[RunnerAgent] Starting calibration...")

        try:
            # Try to import and run calibration
            from hydromodel.trainers.unified_calibrate import calibrate

            # Capture stdout/stderr
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            stdout_capture = StringIO()
            stderr_capture = StringIO()

            try:
                sys.stdout = stdout_capture
                sys.stderr = stderr_capture

                # Run calibration
                result = calibrate(config_path)

            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr

                # Store captured output
                self.last_execution_log = {
                    "stdout": stdout_capture.getvalue(),
                    "stderr": stderr_capture.getvalue()
                }

            logger.info("[RunnerAgent] Calibration completed")
            return {
                "status": "success",
                "result": result,
                "output_captured": True
            }

        except ImportError as e:
            logger.error(f"Failed to import hydromodel: {str(e)}")
            # Fallback: run as subprocess
            return self._run_as_subprocess("calibrate", config_path, workspace_dir)

        except Exception as e:
            logger.error(f"Calibration failed: {str(e)}")
            raise

    def _run_evaluation(self, config_path: str, workspace_dir: Path) -> Dict[str, Any]:
        """
        Run hydromodel evaluation.
        运行 hydromodel 评估。

        Args:
            config_path: Path to configuration file
            workspace_dir: Working directory

        Returns:
            Evaluation result
        """
        logger.info("[RunnerAgent] Starting evaluation...")

        try:
            from hydromodel.trainers.unified_evaluate import evaluate

            # Capture output
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            stdout_capture = StringIO()
            stderr_capture = StringIO()

            try:
                sys.stdout = stdout_capture
                sys.stderr = stderr_capture

                result = evaluate(config_path)

            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr

                self.last_execution_log = {
                    "stdout": stdout_capture.getvalue(),
                    "stderr": stderr_capture.getvalue()
                }

            logger.info("[RunnerAgent] Evaluation completed")
            return {
                "status": "success",
                "result": result,
                "output_captured": True
            }

        except ImportError as e:
            logger.error(f"Failed to import hydromodel: {str(e)}")
            return self._run_as_subprocess("evaluate", config_path, workspace_dir)

        except Exception as e:
            logger.error(f"Evaluation failed: {str(e)}")
            raise

    def _run_as_subprocess(
        self,
        mode: str,
        config_path: str,
        workspace_dir: Path
    ) -> Dict[str, Any]:
        """
        Run hydromodel as subprocess (fallback method).
        作为子进程运行 hydromodel（后备方法）。

        Args:
            mode: Execution mode (calibrate/evaluate)
            config_path: Configuration file path
            workspace_dir: Working directory

        Returns:
            Execution result
        """
        logger.info(f"[RunnerAgent] Running {mode} as subprocess...")

        # TODO: Implement subprocess execution
        # This would call a Python script that runs the calibration/evaluation

        raise NotImplementedError("Subprocess execution not yet implemented")

    def _format_traceback(self) -> str:
        """
        Format current exception traceback.
        格式化当前异常回溯。

        Returns:
            Formatted traceback string
        """
        import traceback
        return traceback.format_exc()

    def check_hydromodel_available(self) -> bool:
        """
        Check if hydromodel is installed and accessible.
        检查 hydromodel 是否已安装且可访问。

        Returns:
            True if hydromodel is available
        """
        try:
            import hydromodel
            logger.info(f"hydromodel version: {hydromodel.__version__}")
            return True
        except ImportError:
            logger.warning("hydromodel not installed")
            return False
        except AttributeError:
            logger.warning("hydromodel installed but no version info")
            return True
