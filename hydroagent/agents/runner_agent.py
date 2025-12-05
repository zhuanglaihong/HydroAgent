"""
Author: zhuanglaihong & Claude
Date: 2025-11-20 19:55:00
LastEditTime: 2025-12-03 18:00:00
LastEditors: Claude
Description: Execution and monitoring agent - v5.0 with timeout and retry logic
             执行监控智能体 - v5.0 支持超时和重试逻辑
FilePath: /HydroAgent/hydroagent/agents/runner_agent.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

v5.0 Enhancements:
- Timeout protection with configurable limits
- Automatic retry with exponential backoff
- Error classification for intelligent recovery
- Complexity reduction on timeout
"""

from typing import Dict, Any, Optional
from pathlib import Path
import logging
import subprocess
import sys
from io import StringIO
import json
import numpy as np

from ..core.base_agent import BaseAgent
from ..core.llm_interface import LLMInterface
from ..utils.path_manager import PathManager
from ..utils import result_parser
from ..utils import error_handler
from ..utils import param_range_adjuster
from ..utils import code_generator
from ..utils.prompt_manager import build_code_generation_prompt
from ..utils.path_manager import scan_output_files
from ..utils.config_validator import ConfigValidator

logger = logging.getLogger(__name__)


class TeeIO:
    """
    同时写入多个输出流的IO类，支持过滤特定输出。
    用于实时显示hydromodel进度条的同时保存日志，但隐藏metrics表格。

    A Tee-like IO class that writes to multiple streams simultaneously with filtering.
    Used to display hydromodel progress bars in real-time while saving logs,
    but hiding metrics tables.
    """

    def __init__(self, *streams, filter_patterns=None):
        """
        初始化TeeIO。

        Args:
            *streams: 要同时写入的输出流
            filter_patterns: 要过滤（不显示）的文本模式列表
        """
        self.streams = streams
        self.filter_patterns = filter_patterns or []
        self._buffer = ""  # 缓冲区，用于检测多行模式

    def write(self, data):
        """写入数据到所有流，对显示流应用逐行过滤器"""
        if not self.streams:
            return

        # 第一个stream是capture（总是记录），其余是显示流（应用过滤）
        capture_stream = self.streams[0] if len(self.streams) > 0 else None
        display_streams = self.streams[1:] if len(self.streams) > 1 else []

        # 总是写入capture stream（完整日志）
        if capture_stream:
            capture_stream.write(data)
            if hasattr(capture_stream, "flush"):
                capture_stream.flush()

        # 对显示流应用过滤器
        if display_streams and self.filter_patterns:
            # 累积到缓冲区
            self._buffer += data

            # 处理完整行
            if "\n" in self._buffer:
                lines = self._buffer.split("\n")
                # 最后一个可能是不完整的行，保留在缓冲区
                complete_lines = lines[:-1]
                self._buffer = lines[-1]

                # 逐行检查是否应该过滤
                for line in complete_lines:
                    should_filter = False
                    for pattern in self.filter_patterns:
                        if pattern in line:
                            should_filter = True
                            break

                    # 如果不过滤，写入显示流
                    if not should_filter:
                        for stream in display_streams:
                            stream.write(line + "\n")
                            if hasattr(stream, "flush"):
                                stream.flush()
            # 如果是进度条更新（没有换行符，使用\r），直接显示
            elif "\r" in data:
                # 进度条通常不包含过滤模式，直接显示
                should_filter = False
                for pattern in self.filter_patterns:
                    if pattern in data:
                        should_filter = True
                        break

                if not should_filter:
                    for stream in display_streams:
                        stream.write(data)
                        if hasattr(stream, "flush"):
                            stream.flush()
                # 清空缓冲区，因为\r会覆盖当前行
                self._buffer = ""

        elif display_streams:
            # 没有过滤模式，直接显示所有内容
            for stream in display_streams:
                stream.write(data)
                if hasattr(stream, "flush"):
                    stream.flush()

    def flush(self):
        """刷新所有流"""
        for stream in self.streams:
            if hasattr(stream, "flush"):
                stream.flush()

    def isatty(self):
        """检查是否为终端（进度条需要）"""
        # 如果任一流是终端，返回True
        return any(hasattr(s, "isatty") and s.isatty() for s in self.streams)


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
    -   Generate and execute custom analysis code (v4.0)
    """

    def __init__(
        self,
        llm_interface: LLMInterface,
        code_llm_interface: Optional[LLMInterface] = None,  #   代码专用LLM
        workspace_dir: Optional[Path] = None,
        timeout: int = 3600,
        show_progress: bool = True,
        max_retries: int = 3,  # 🆕 v5.0
        retry_backoff: float = 2.0,  # 🆕 v5.0
        **kwargs,
    ):
        """
        Initialize RunnerAgent (v5.0 with retry logic).

        Args:
            llm_interface: LLM API interface
            code_llm_interface:   Optional LLM interface for code generation
                Examples: qwen-coder-turbo, deepseek-coder:6.7b
            workspace_dir: Working directory
            timeout: Execution timeout in seconds
            show_progress: 是否显示实时进度（进度条等）
                          Whether to show real-time progress (progress bars, etc.)
            max_retries: 🆕 v5.0 Maximum number of retries on recoverable errors
            retry_backoff: 🆕 v5.0 Exponential backoff factor (seconds)
            **kwargs: Additional configuration
        """
        super().__init__(
            name="RunnerAgent",
            llm_interface=llm_interface,
            workspace_dir=workspace_dir,
            **kwargs,
        )

        self.timeout = timeout
        self.show_progress = show_progress
        self.last_execution_log = None

        # 🆕 v5.0: Retry configuration
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff

        # Initialize config validator
        self.validator = ConfigValidator()

        #   代码生成LLM
        self.code_llm = code_llm_interface if code_llm_interface else None
        if self.code_llm:
            logger.info(
                f"[RunnerAgent v5.0] Code generation enabled with model: {self.code_llm.model_name}"
            )
        else:
            logger.info(
                "[RunnerAgent v5.0] Code generation not configured (code_llm_interface not provided)"
            )

        logger.info(
            f"[RunnerAgent v5.0] Initialized with timeout={timeout}s, max_retries={max_retries}"
        )

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
        执行 hydromodel 工作流。
        Execute hydromodel workflow (Phase 3 enhanced: support new task types).

        Args:
            input_data: 执行配置 Execution configuration
                {
                    "success": True,
                    "config": {...},  # ConfigAgent或InterpreterAgent生成的配置dict
                    "task_id": "task_1",  # 子任务ID（Phase 3新增）
                    "config_summary": "..."
                }
                或
                {
                    "config": {...},  # 直接传入配置dict
                    "intent": "calibration"|"evaluation"|"simulation"
                }

        Returns:
            Dict containing execution result:
                {
                    "success": True/False,
                    "result": {...},  # 执行结果
                    "metrics": {...},  # 评估指标
                    "execution_log": {...},  # 执行日志
                    "output_files": [...],  # 输出文件列表
                }
        """
        # 从ConfigAgent/InterpreterAgent的输出中提取config
        if "config" in input_data:
            config = input_data["config"]
        else:
            logger.error("[RunnerAgent] No config found in input_data")
            return {"success": False, "error": "Missing 'config' in input_data"}

        # Phase 3: 支持从config的parameters中获取task_type
        parameters = config.get("parameters", {})
        task_type = parameters.get("task_type")
        task_id = input_data.get("task_id", "unknown")

        # 推断执行模式 TODO
        if task_type == "boundary_check_recalibration":
            mode = "boundary_check"
        elif task_type == "statistical_analysis":
            mode = "statistical_analysis"
        elif task_type == "custom_analysis":
            mode = "custom_analysis"
        elif task_type == "auto_iterative_calibration":
            mode = "auto_iterative"
        else:
            # 传统模式：从intent推断
            intent = input_data.get("intent_result", {}).get(
                "intent"
            ) or input_data.get("intent", "calibration")

            # 将intent映射到执行模式
            if intent in ["calibration", "training"]:
                mode = "calibrate"
            elif intent in ["evaluation", "test"]:
                mode = "evaluate"
            elif intent == "simulation":
                mode = "simulate"
            else:
                mode = "calibrate"  # 默认为率定

        logger.info(f"[RunnerAgent] 开始执行任务: {task_id}, 模式: {mode}")

        # For custom_analysis tasks, get metadata from task_metadata or parameters
        if mode == "custom_analysis":
            task_metadata = config.get("task_metadata", {})
            model_name = task_metadata.get("model_name") or parameters.get(
                "model_name", "N/A"
            )
            basin_ids = task_metadata.get("basin_id") or parameters.get(
                "basin_id", "N/A"
            )
            logger.info(f"[RunnerAgent] 模型: {model_name}")
            logger.info(f"[RunnerAgent] 流域: {basin_ids}")
        else:
            logger.info(
                f"[RunnerAgent] 模型: {config.get('model_cfgs', {}).get('model_name', 'N/A')}"
            )
            logger.info(
                f"[RunnerAgent] 流域: {config.get('data_cfgs', {}).get('basin_ids', [])}"
            )

        # 🆕 Pre-execution validation (最后一道防线)
        # Only validate hydromodel tasks (skip custom_analysis)
        if mode not in ["custom_analysis", "statistical_analysis"]:
            is_valid, validation_errors = self.validator.validate_config(config)

            if not is_valid:
                error_message = self.validator.format_validation_errors(validation_errors)
                logger.error(f"[RunnerAgent] 配置验证失败:\n{error_message}")

                return {
                    "success": False,
                    "task_id": task_id,
                    "mode": mode,
                    "error": error_message,
                    "error_type": "ConfigValidationError",
                    "validation_errors": validation_errors,
                }

        try:
            if mode == "calibrate":
                result = self._run_calibration(config)
            elif mode == "evaluate":
                result = self._run_evaluation(config)
            elif mode == "simulate":
                result = self._run_simulation(config)
            elif mode == "boundary_check":
                result = self._run_boundary_check_recalibration(config, parameters)
            elif mode == "statistical_analysis":
                result = self._run_statistical_analysis(config, parameters, input_data)
            elif mode == "custom_analysis":
                result = self._run_custom_analysis(config, parameters)
            elif mode == "auto_iterative":  #   v4.0
                result = self._run_auto_iterative_calibration(config, parameters)
            else:
                raise ValueError(f"未知的执行模式: {mode}")

            logger.info(f"[RunnerAgent] 执行成功完成")

            return {
                "success": True,
                "task_id": task_id,
                "mode": mode,
                "result": result,
                "execution_log": self.last_execution_log,
            }

        except Exception as e:
            logger.error(f"[RunnerAgent] 执行失败: {str(e)}", exc_info=True)

            return {
                "success": False,
                "task_id": task_id,
                "mode": mode,
                "error": str(e),
                "traceback": error_handler.format_traceback(),
                "execution_log": self.last_execution_log,
            }

    def _run_calibration(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        运行 hydromodel 率定。
        Run hydromodel calibration.

        Args:
            config: 配置字典 (来自ConfigAgent)

        Returns:
            率定结果 Calibration result
        """
        logger.info("[RunnerAgent] 开始率定...")

        try:
            # 导入hydromodel的率定函数（从顶层导入，避免Mock测试问题）
            from hydromodel import calibrate

            # 捕获stdout/stderr
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            stdout_capture = StringIO()
            stderr_capture = StringIO()

            try:
                if self.show_progress:
                    # 定义要过滤的hydromodel装饰性输出模式
                    # 只保留进度条，隐藏emoji和格式化信息
                    filter_patterns = [
                        "🚀 =====",  # 分隔线
                        "▶️  =====",  # 分隔线
                        "🔧 =====",  # 分隔线
                        "✅ =====",  # 分隔线
                        "🚀 Starting",  # 开始信息
                        "▶️  Basin",  # Basin信息（已被分隔线过滤）
                        "🔧 Starting",  # 优化开始
                        "📋 SCE-UA parameters:",  # 参数详情
                        "   •",  # 参数列表项
                        "✅ SCE-UA optimization completed",  # 完成信息
                        "📊 Best objective value:",  # 目标值
                        "📊 Best parameters",  # 参数详情
                        "      •",  # 参数列表
                        "✅ Basin",  # Basin完成
                        " Saving calibration",  # 保存信息
                        " Results saved to:",  # 结果路径
                        "💾 Saved",  # 保存确认
                        "All calibrations completed",  # 全部完成
                        "Total basins calibrated:",  # 统计信息
                        "Using data paths",  # 数据路径
                        "dynamic data already exists",  # 数据存在提示
                        "Remote service setup failed",  # 远程服务错误（不重要）
                        "Remote service setup failed: Invalid endpoint:",
                        "🧬 ====== ",
                        "🧬 Starting ",
                    ]

                    # 使用TeeIO同时显示进度和保存日志，过滤装饰性输出
                    sys.stdout = TeeIO(
                        stdout_capture, old_stdout, filter_patterns=filter_patterns
                    )
                    sys.stderr = TeeIO(
                        stderr_capture, old_stderr, filter_patterns=filter_patterns
                    )
                    logger.info("[RunnerAgent] 执行率定（显示进度条，隐藏详细输出）...")
                else:
                    # 只保存日志，不显示进度
                    sys.stdout = stdout_capture
                    sys.stderr = stderr_capture
                    logger.info("[RunnerAgent] 执行率定（后台模式）...")

                # 运行率定 - 直接传入config dict
                logger.info("[RunnerAgent] 调用 calibrate(config)")
                # print('config',config)
                result = calibrate(config)

            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr

                # 存储捕获的输出
                self.last_execution_log = {
                    "stdout": stdout_capture.getvalue(),
                    "stderr": stderr_capture.getvalue(),
                }

            logger.info("[RunnerAgent] 率定完成")

            # 解析率定结果 - calibrate()会保存参数到文件，不直接返回
            parsed_result = result_parser.parse_calibration_result(result, config)

            # ✅ 自动在测试期进行评估（标准水文模型流程）
            eval_result = None
            eval_metrics = {}
            calibration_dir = parsed_result.get("calibration_dir")

            if calibration_dir:
                logger.info(f"[RunnerAgent] 率定完成，参数保存在: {calibration_dir}")
                logger.info("[RunnerAgent] 开始在测试期进行评估...")
                try:
                    eval_result = self._run_evaluation_from_calibration(
                        calibration_dir, config
                    )
                    eval_metrics = eval_result.get("metrics", {})
                    logger.info(
                        f"[RunnerAgent] 评估完成，NSE={eval_metrics.get('NSE', 'N/A')}"
                    )
                except Exception as e:
                    logger.warning(f"[RunnerAgent] 评估失败: {str(e)}", exc_info=True)
            else:
                logger.warning("[RunnerAgent] 未获得率定输出目录，跳过评估")

            # ✅ 自动绘图（率定-评估-可视化三步走）
            plot_files = []
            if calibration_dir:
                try:
                    from configs import config as global_config

                    if global_config.ENABLE_AUTO_PLOT:
                        logger.info("[RunnerAgent] 开始自动绘图...")
                        plot_files = self._run_visualize(calibration_dir, config)
                        if plot_files:
                            logger.info(
                                f"[RunnerAgent] 生成了 {len(plot_files)} 个图表"
                            )
                except Exception as e:
                    logger.warning(
                        f"[RunnerAgent] 自动绘图失败: {str(e)}", exc_info=True
                    )

            return {
                "status": "success",
                "calibration_result": result,
                "calibration_dir": calibration_dir,
                "calibration_metrics": parsed_result.get("metrics", {}),
                "best_params": parsed_result.get("best_params", {}),
                "evaluation_result": eval_result,
                "metrics": eval_metrics,  # ✅ 使用评估期的metrics（更准确）
                "output_files": parsed_result.get("output_files", []),
                "plot_files": plot_files,  # ✅ 新增：绘图文件列表
                "output_captured": True,
            }

        except ImportError as e:
            logger.error(f"[RunnerAgent] 无法导入hydromodel: {str(e)}")
            raise ImportError(
                "hydromodel未安装或无法导入。请确保hydromodel已正确安装。\n"
                f"错误详情: {str(e)}"
            )

        except Exception as e:
            logger.error(f"[RunnerAgent] 率定失败: {str(e)}", exc_info=True)
            raise

    def _run_evaluation_from_calibration(
        self, calibration_dir: str, original_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        从率定目录运行评估。
        Run evaluation from calibration directory.

        Args:
            calibration_dir: 率定结果目录（包含calibration_results.json）
            original_config: 原始配置（用于获取test_period等）

        Returns:
            评估结果
        """
        logger.info(f"[RunnerAgent] 从率定目录进行评估: {calibration_dir}")

        try:
            # 导入hydromodel的evaluate和config_manager
            # from hydromodel import evaluate
            from hydromodel.trainers.unified_evaluate import evaluate
            from hydromodel.configs.config_manager import load_config_from_calibration

            # 捕获stdout/stderr
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            stdout_capture = StringIO()
            stderr_capture = StringIO()

            try:
                # 评估时完全隐藏hydromodel输出，只记录到日志
                # （评估很快，不需要显示进度；且hydromodel输出格式化表格会干扰用户界面）
                sys.stdout = stdout_capture
                sys.stderr = stderr_capture
                logger.info("[RunnerAgent] 执行评估（后台模式，输出已重定向到日志）...")

                # 从率定目录加载配置（包含参数）
                logger.info(
                    f"[RunnerAgent] 加载配置: load_config_from_calibration({calibration_dir})"
                )
                config = load_config_from_calibration(calibration_dir)

                # 获取test period
                test_period = config["data_cfgs"]["test_period"]
                logger.info(f"[RunnerAgent] 测试期: {test_period}")

                # 运行评估 - hydromodel的evaluate会自动从calibration_dir读取参数
                logger.info(
                    f"[RunnerAgent] 调用 evaluate(config, param_dir={calibration_dir})"
                )
                result = evaluate(
                    config,
                    param_dir=calibration_dir,
                    eval_period=test_period,
                    eval_output_dir=None,  # 使用默认输出目录
                )

            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr

                # 更新执行日志
                eval_log = {
                    "stdout": stdout_capture.getvalue(),
                    "stderr": stderr_capture.getvalue(),
                }
                if self.last_execution_log:
                    self.last_execution_log["evaluation"] = eval_log
                else:
                    self.last_execution_log = eval_log

            logger.info("[RunnerAgent] 评估完成")
            logger.info(f"[RunnerAgent] evaluate()返回类型: {type(result)}")
            logger.info(
                f"[RunnerAgent] evaluate()返回keys: {list(result.keys()) if isinstance(result, dict) else 'N/A'}"
            )
            if isinstance(result, dict) and result:
                first_key = list(result.keys())[0]
                logger.info(
                    f"[RunnerAgent] result['{first_key}']的keys: {list(result[first_key].keys()) if isinstance(result[first_key], dict) else 'N/A'}"
                )

            # 解析结果
            parsed_result = result_parser.parse_evaluation_result(result)

            return {
                "status": "success",
                "evaluation_result": result,
                "metrics": parsed_result.get("metrics", {}),
                "performance": parsed_result.get("performance", {}),
                "output_files": parsed_result.get("output_files", []),
            }

        except ImportError as e:
            logger.error(f"[RunnerAgent] 无法导入hydromodel: {str(e)}")
            raise ImportError(f"hydromodel或config_manager未安装或无法导入: {str(e)}")

        except Exception as e:
            logger.error(f"[RunnerAgent] 评估失败: {str(e)}", exc_info=True)
            raise

    def _run_evaluation(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        运行 hydromodel 评估。
        Run hydromodel evaluation.

        Args:
            config: 配置字典 (来自ConfigAgent)

        Returns:
            评估结果 Evaluation result
        """
        logger.info("[RunnerAgent] 开始评估...")

        try:
            # 导入hydromodel的评估函数（从顶层导入，避免Mock测试问题）
            # from hydromodel import evaluate
            from hydromodel.trainers.unified_evaluate import evaluate

            # 捕获输出
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            stdout_capture = StringIO()
            stderr_capture = StringIO()

            try:
                if self.show_progress:
                    # 使用TeeIO同时显示进度和保存日志
                    sys.stdout = TeeIO(stdout_capture, old_stdout)
                    sys.stderr = TeeIO(stderr_capture, old_stderr)
                    logger.info("[RunnerAgent] 执行评估（显示进度）...")
                else:
                    # 只保存日志，不显示进度
                    sys.stdout = stdout_capture
                    sys.stderr = stderr_capture
                    logger.info("[RunnerAgent] 执行评估（后台模式）...")

                # 运行评估 - 直接传入config dict
                logger.info("[RunnerAgent] 调用 evaluate(config)")
                result = evaluate(config)

            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr

                self.last_execution_log = {
                    "stdout": stdout_capture.getvalue(),
                    "stderr": stderr_capture.getvalue(),
                }

            logger.info("[RunnerAgent] 评估完成")

            # 解析结果
            parsed_result = result_parser.parse_evaluation_result(result)

            return {
                "status": "success",
                "evaluation_result": result,
                "metrics": parsed_result.get("metrics", {}),
                "performance": parsed_result.get("performance", {}),
                "output_files": parsed_result.get("output_files", []),
                "output_captured": True,
            }

        except ImportError as e:
            logger.error(f"[RunnerAgent] 无法导入hydromodel: {str(e)}")
            raise ImportError(
                "hydromodel未安装或无法导入。请确保hydromodel已正确安装。\n"
                f"错误详情: {str(e)}"
            )

        except Exception as e:
            logger.error(f"[RunnerAgent] 评估失败: {str(e)}", exc_info=True)
            raise

    def _run_simulation(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        运行 hydromodel 模拟。
        Run hydromodel simulation.

        Args:
            config: 配置字典 (来自ConfigAgent)

        Returns:
            模拟结果 Simulation result
        """
        logger.info("[RunnerAgent] 开始模拟...")

        try:
            # hydromodel可能没有独立的simulate函数，使用calibrate的预测功能
            # 从顶层导入，避免Mock测试问题
            from hydromodel import calibrate

            # 捕获输出
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            stdout_capture = StringIO()
            stderr_capture = StringIO()

            try:
                if self.show_progress:
                    # 使用TeeIO同时显示进度和保存日志
                    sys.stdout = TeeIO(stdout_capture, old_stdout)
                    sys.stderr = TeeIO(stderr_capture, old_stderr)
                    logger.info("[RunnerAgent] 执行模拟（显示进度）...")
                else:
                    # 只保存日志，不显示进度
                    sys.stdout = stdout_capture
                    sys.stderr = stderr_capture
                    logger.info("[RunnerAgent] 执行模拟（后台模式）...")

                # 运行模拟
                logger.info("[RunnerAgent] 调用 calibrate(config) 进行模拟")
                result = calibrate(config)

            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr

                self.last_execution_log = {
                    "stdout": stdout_capture.getvalue(),
                    "stderr": stderr_capture.getvalue(),
                }

            logger.info("[RunnerAgent] 模拟完成")

            return {
                "status": "success",
                "simulation_result": result,
                "output_captured": True,
            }

        except ImportError as e:
            logger.error(f"[RunnerAgent] 无法导入hydromodel: {str(e)}")
            raise ImportError(
                "hydromodel未安装或无法导入。请确保hydromodel已正确安装。\n"
                f"错误详情: {str(e)}"
            )

        except Exception as e:
            logger.error(f"[RunnerAgent] 模拟失败: {str(e)}", exc_info=True)
            raise

    def _run_visualize(self, calibration_dir: str, config: Dict[str, Any]) -> list[str]:
        """
        自动绘制率定/评估结果图（使用hydromodel的绘图接口）

        Args:
            calibration_dir: 率定结果目录
            config: 配置字典

        Returns:
            生成的图表文件路径列表
        """
        try:
            from hydromodel.datasets.data_visualize import plot_sim_and_obs
            from configs import config as global_config
            from pathlib import Path
            import xarray as xr

            logger.info(f"[RunnerAgent] 从 {calibration_dir} 加载结果进行绘图")

            plot_files = []
            calibration_path = Path(calibration_dir)

            # 查找模拟结果NetCDF文件
            nc_files = list(calibration_path.glob("*.nc"))
            if not nc_files:
                logger.warning("[RunnerAgent] 未找到NetCDF文件，无法绘图")
                return []

            # 通常有两个nc文件：训练期和测试期
            for nc_file in nc_files:
                logger.info(f"[RunnerAgent] 处理文件: {nc_file.name}")

                try:
                    # 读取NetCDF数据
                    ds = xr.open_dataset(nc_file)

                    # 提取数据
                    # hydromodel的NetCDF格式：time, basin, qobs, qsim, prcp等
                    if (
                        "time" in ds.coords
                        and "qobs" in ds.variables
                        and "qsim" in ds.variables
                    ):
                        # ✅ 转换numpy.datetime64为pandas DatetimeIndex（hydromodel绘图兼容）
                        import pandas as pd

                        time = pd.to_datetime(ds["time"].values)
                        obs = ds["qobs"].values.flatten()
                        sim = ds["qsim"].values.flatten()

                        # 检查是否有降水数据
                        prcp = None
                        if (
                            "prcp" in ds.variables
                            and global_config.PLOT_WITH_PRECIPITATION
                        ):
                            prcp = ds["prcp"].values.flatten()

                        # 确定绘图文件名
                        period_name = nc_file.stem  # 如 "eval_test_period"
                        if prcp is not None:
                            plot_filename = (
                                f"{period_name}_with_prcp.{global_config.PLOT_FORMAT}"
                            )
                        else:
                            plot_filename = (
                                f"{period_name}_streamflow.{global_config.PLOT_FORMAT}"
                            )

                        plot_path = calibration_path / plot_filename

                        # 调用hydromodel的绘图函数
                        if prcp is not None:
                            # 带降水的对比图
                            plot_sim_and_obs(
                                date=time,
                                prcp=prcp,
                                sim=sim,
                                obs=obs,
                                save_fig=str(plot_path),
                                basin_id=config.get("data_cfgs", {}).get(
                                    "basin_ids", [""]
                                )[0],
                                title_suffix=period_name,
                            )
                        else:
                            # 仅径流对比图（使用简单版本）
                            from hydromodel.datasets.data_visualize import (
                                plot_sim_and_obs_streamflow,
                            )
                            import matplotlib.pyplot as plt

                            fig, ax = plt.subplots(figsize=(14, 6))
                            plot_sim_and_obs_streamflow(
                                date=time,
                                sim=sim,
                                obs=obs,
                                ax=ax,
                                basin_id=config.get("data_cfgs", {}).get(
                                    "basin_ids", [""]
                                )[0],
                                title_suffix=period_name,
                            )
                            plt.savefig(
                                plot_path,
                                dpi=global_config.PLOT_DPI,
                                bbox_inches="tight",
                            )
                            plt.close(fig)

                        plot_files.append(str(plot_path))
                        logger.info(f"[RunnerAgent] 图表已保存: {plot_path}")

                    else:
                        logger.warning(
                            f"[RunnerAgent] NetCDF文件缺少必要变量: {nc_file.name}"
                        )

                    ds.close()

                except Exception as e:
                    logger.error(
                        f"[RunnerAgent] 处理 {nc_file.name} 时出错: {str(e)}",
                        exc_info=True,
                    )

            return plot_files

        except ImportError as e:
            logger.warning(f"[RunnerAgent] 无法导入绘图模块: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"[RunnerAgent] 绘图失败: {str(e)}", exc_info=True)
            return []

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

    def _run_boundary_check_recalibration(
        self, config: Dict[str, Any], parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        检查参数边界并重新率定（实验3 - 迭代优化版本）。
        Check parameter boundaries and recalibrate iteratively (Experiment 3).

        Args:
            config: 配置字典
            parameters: 任务参数
                - boundary_threshold: 边界阈值（默认0.05）
                - nse_threshold: NSE达标阈值（默认0.5）
                - max_iterations: 最大迭代次数（默认5）
                - min_nse_improvement: 最小NSE改善幅度（默认0.01）
                - initial_range_scale: 初始缩放比例（默认0.6）

        Returns:
            迭代优化结果
        """
        logger.info("[RunnerAgent] 开始自适应迭代率定...")

        # 迭代控制参数
        max_iterations = parameters.get("max_iterations", 5)
        nse_threshold = parameters.get("nse_threshold", 0.5)
        min_nse_improvement = parameters.get("min_nse_improvement", 0.01)
        initial_range_scale = parameters.get("initial_range_scale", 0.6)

        logger.info(f"[RunnerAgent] 迭代配置:")
        logger.info(f"  - 最大迭代次数: {max_iterations}")
        logger.info(f"  - NSE达标阈值: {nse_threshold}")
        logger.info(f"  - 最小改善幅度: {min_nse_improvement}")
        logger.info(f"  - 初始缩放比例: {initial_range_scale}")

        try:
            from pathlib import Path
            import json

            # 执行初始率定（Iteration 0）
            logger.info("\n" + "=" * 70)
            logger.info("🚀 Iteration 0: 初始率定（使用默认参数范围）")
            logger.info("=" * 70)

            # ⭐ 为初始率定设置唯一的输出目录（使用PathManager）
            initial_config = config.copy()
            if "training_cfgs" in initial_config and self.workspace_dir:
                initial_config["training_cfgs"] = config["training_cfgs"].copy()
                # 使用 PathManager 配置路径（扁平结构，避免嵌套）
                initial_config = PathManager.configure_hydromodel_output(
                    config=initial_config,
                    session_dir=self.workspace_dir,
                    task_id="calibration_iter0",
                    use_flat_structure=True,
                )
                logger.info(
                    f"[RunnerAgent] Iteration 0 输出目录: {initial_config['training_cfgs']['output_dir']}"
                )

            initial_result = self._run_calibration(initial_config)

            if not initial_result.get("status") == "success":
                logger.error("[RunnerAgent] 初始率定失败")
                return {
                    "status": "initial_calibration_failed",
                    "error": "Initial calibration failed",
                    "iterations": [],
                }

            # 获取初始NSE
            initial_nse = initial_result.get("metrics", {}).get("NSE", 0.0)
            initial_calib_dir = initial_result.get("calibration_dir")

            logger.info(f"✅ 初始率定完成: NSE={initial_nse:.4f}")
            logger.info(f"   率定目录: {initial_calib_dir}")

            # 迭代历史
            iteration_history = [
                {
                    "iteration": 0,
                    "nse": initial_nse,
                    "calibration_dir": initial_calib_dir,
                    "range_scale": None,
                    "metrics": initial_result.get("metrics", {}),
                    "status": "completed",
                }
            ]

            # 检查是否已经达标
            if initial_nse >= nse_threshold:
                logger.info(
                    f"🎉 初始NSE={initial_nse:.4f} 已达标（>= {nse_threshold}），无需迭代优化"
                )
                return {
                    "status": "already_optimal",
                    "iterations": iteration_history,
                    "total_iterations": 0,
                    "final_nse": initial_nse,
                    "final_metrics": initial_result.get("metrics", {}),
                    "message": f"Initial NSE {initial_nse:.4f} already meets threshold {nse_threshold}",
                    "output_dir": (
                        str(self.workspace_dir) if self.workspace_dir else None
                    ),
                }

            # 开始迭代优化
            best_nse = initial_nse
            best_iteration = 0
            prev_calib_dir = initial_calib_dir
            consecutive_no_improvement = 0

            for iteration in range(1, max_iterations + 1):
                logger.info("\n" + "=" * 70)
                logger.info(
                    f"🔄 Iteration {iteration}/{max_iterations}: 自适应范围调整"
                )
                logger.info("=" * 70)

                # 动态计算 range_scale（逐渐缩小）
                # 策略: 0.6 -> 0.4 -> 0.3 -> 0.2 -> 0.15
                range_scale = initial_range_scale * (0.7**iteration)
                range_scale = max(range_scale, 0.1)  # 最小不低于10%

                logger.info(f"📏 当前缩放比例: {range_scale:.2%} (第{iteration}次迭代)")

                # 调整参数范围
                logger.info(f"📂 基于上次结果调整范围: {prev_calib_dir}")

                adjust_result = param_range_adjuster.adjust_from_previous_calibration(
                    prev_calibration_dir=prev_calib_dir,
                    range_scale=range_scale,
                    output_yaml_path=(
                        str(
                            Path(self.workspace_dir)
                            / f"param_range_iter{iteration}.yaml"
                        )
                        if self.workspace_dir
                        else None
                    ),
                    workspace_dir=self.workspace_dir,
                )

                if not adjust_result["success"]:
                    logger.error(f"❌ 参数范围调整失败: {adjust_result.get('error')}")
                    iteration_history.append(
                        {
                            "iteration": iteration,
                            "nse": None,
                            "range_scale": range_scale,
                            "status": "adjustment_failed",
                            "error": adjust_result.get("error"),
                        }
                    )
                    break

                logger.info(f"✅ 参数范围调整完成: {adjust_result['output_file']}")

                # 更新config，使用新的参数范围文件
                new_config = config.copy()
                new_config["model_cfgs"] = config["model_cfgs"].copy()
                # ⭐ 保存到 model_cfgs 用于记录（在 calibration_config.yaml 中）
                new_config["model_cfgs"]["param_range_file"] = adjust_result[
                    "output_file"
                ]

                # ⭐ 为每次迭代设置唯一的输出目录（使用PathManager）
                if "training_cfgs" in new_config:
                    new_config["training_cfgs"] = config["training_cfgs"].copy()
                    # 🔧 FIX: hydromodel 只从 training_cfgs 读取 param_range_file
                    # 必须设置到 training_cfgs，否则会使用内置的 MODEL_PARAM_DICT（原始范围）
                    new_config["training_cfgs"]["param_range_file"] = adjust_result[
                        "output_file"
                    ]
                    logger.info(
                        f"[RunnerAgent] 设置参数范围文件: {adjust_result['output_file']}"
                    )

                    # 使用 PathManager 配置路径（扁平结构，避免嵌套）
                    if self.workspace_dir:
                        new_config = PathManager.configure_hydromodel_output(
                            config=new_config,
                            session_dir=self.workspace_dir,
                            task_id=f"calibration_iter{iteration}",
                            use_flat_structure=True,
                        )
                        logger.info(
                            f"[RunnerAgent] Iteration {iteration} 输出目录: {new_config['training_cfgs']['output_dir']}"
                        )

                # 执行率定
                logger.info(f"🚀 执行第 {iteration} 次率定...")
                iter_result = self._run_calibration(new_config)

                if not iter_result.get("status") == "success":
                    logger.error(f"❌ 第 {iteration} 次率定失败")
                    iteration_history.append(
                        {
                            "iteration": iteration,
                            "nse": None,
                            "range_scale": range_scale,
                            "status": "calibration_failed",
                            "error": "Calibration execution failed",
                        }
                    )
                    break

                # 获取本次NSE
                current_nse = iter_result.get("metrics", {}).get("NSE", 0.0)
                current_calib_dir = iter_result.get("calibration_dir")

                logger.info(f"📊 第 {iteration} 次率定完成: NSE={current_nse:.4f}")
                logger.info(f"   率定目录: {current_calib_dir}")

                # 记录历史
                iteration_history.append(
                    {
                        "iteration": iteration,
                        "nse": current_nse,
                        "nse_improvement": current_nse - best_nse,
                        "calibration_dir": current_calib_dir,
                        "range_scale": range_scale,
                        "metrics": iter_result.get("metrics", {}),
                        "param_range_adjustment": adjust_result,
                        "status": "completed",
                    }
                )

                # 判断是否改善
                nse_improvement = current_nse - best_nse

                if nse_improvement > min_nse_improvement:
                    logger.info(
                        f"✅ NSE改善: {best_nse:.4f} -> {current_nse:.4f} (+{nse_improvement:.4f})"
                    )
                    best_nse = current_nse
                    best_iteration = iteration
                    prev_calib_dir = current_calib_dir
                    consecutive_no_improvement = 0

                    # 检查是否达标
                    if current_nse >= nse_threshold:
                        logger.info(
                            f"🎉 NSE={current_nse:.4f} 已达标（>= {nse_threshold}），停止迭代"
                        )
                        return {
                            "status": "converged",
                            "iterations": iteration_history,
                            "total_iterations": iteration,
                            "best_iteration": best_iteration,
                            "final_nse": current_nse,
                            "final_metrics": iter_result.get("metrics", {}),
                            "message": f"Converged at iteration {iteration} with NSE {current_nse:.4f}",
                            "output_dir": (
                                str(self.workspace_dir) if self.workspace_dir else None
                            ),
                        }
                else:
                    consecutive_no_improvement += 1
                    logger.warning(
                        f"⚠️  NSE无改善或下降: {best_nse:.4f} -> {current_nse:.4f} ({nse_improvement:+.4f})"
                    )
                    logger.warning(f"   连续无改善次数: {consecutive_no_improvement}")

                    # 连续2次无改善，提前停止
                    if consecutive_no_improvement >= 2:
                        logger.warning(
                            f"⛔ 连续 {consecutive_no_improvement} 次无改善，提前停止迭代"
                        )
                        logger.warning(f"   建议人工检查参数范围或模型设置")
                        return {
                            "status": "no_improvement",
                            "iterations": iteration_history,
                            "total_iterations": iteration,
                            "best_iteration": best_iteration,
                            "final_nse": best_nse,
                            "final_metrics": iteration_history[best_iteration][
                                "metrics"
                            ],
                            "message": f"No improvement after {consecutive_no_improvement} iterations. Best NSE: {best_nse:.4f} at iteration {best_iteration}",
                            "recommendation": "建议人工设置更合理的参数范围或检查模型配置",
                            "output_dir": (
                                str(self.workspace_dir) if self.workspace_dir else None
                            ),
                        }

            # 达到最大迭代次数
            logger.warning(f"⚠️  达到最大迭代次数 {max_iterations}，停止")
            logger.info(f"   最佳NSE: {best_nse:.4f} (第{best_iteration}次迭代)")

            if best_nse < nse_threshold:
                logger.warning(f"   未达标（< {nse_threshold}），建议人工介入")
                return {
                    "status": "max_iterations_reached",
                    "iterations": iteration_history,
                    "total_iterations": max_iterations,
                    "best_iteration": best_iteration,
                    "final_nse": best_nse,
                    "final_metrics": iteration_history[best_iteration]["metrics"],
                    "message": f"Reached max iterations. Best NSE: {best_nse:.4f} at iteration {best_iteration}",
                    "recommendation": "建议人工设置更合理的参数范围或检查模型配置",
                    "output_dir": (
                        str(self.workspace_dir) if self.workspace_dir else None
                    ),
                }
            else:
                return {
                    "status": "converged_at_max",
                    "iterations": iteration_history,
                    "total_iterations": max_iterations,
                    "best_iteration": best_iteration,
                    "final_nse": best_nse,
                    "final_metrics": iteration_history[best_iteration]["metrics"],
                    "message": f"Converged at max iterations. Best NSE: {best_nse:.4f}",
                    "output_dir": (
                        str(self.workspace_dir) if self.workspace_dir else None
                    ),
                }

        except Exception as e:
            logger.error(f"[RunnerAgent] 迭代优化失败: {str(e)}", exc_info=True)
            raise

    def _run_statistical_analysis(
        self,
        config: Dict[str, Any],
        parameters: Dict[str, Any],
        input_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        统计分析多次重复实验的结果
        Statistical analysis of repeated experiments (Experiment 5).

        Args:
            config: 配置字典
            parameters: 任务参数
                - n_repeats: 重复次数
                - analysis_type: 分析类型
            input_data: 包含前置任务结果的输入数据

        Returns:
            统计分析结果
        """
        logger.info("[RunnerAgent] 开始统计分析...")

        n_repeats = parameters.get("n_repeats", 10)
        analysis_type = parameters.get("analysis_type", "stability_validation")

        # 收集所有重复实验的结果
        # 实际应该从workspace_dir中读取所有task_*_repeat的结果
        try:
            from pathlib import Path
            import json
            import numpy as np

            # ⭐ Use PathManager to collect results
            workspace_dir = Path(
                config.get("training_cfgs", {}).get("output_dir", ".")
            ).parent
            logger.info(
                f"[RunnerAgent] 使用PathManager从 {workspace_dir} 收集重复实验结果..."
            )

            # 使用PathManager收集所有重复任务的结果
            collection_result = PathManager.collect_repeated_calibration_results(
                session_dir=workspace_dir,
                n_repeats=n_repeats,
                task_id_pattern="task_{i}_repeat",
            )

            if collection_result["found_count"] == 0:
                logger.warning("[RunnerAgent] 没有找到任何重复实验结果")
                return {"status": "no_data", "n_repeats": n_repeats, "found_results": 0}

            logger.info(
                f"[RunnerAgent] 找到 {collection_result['found_count']}/{collection_result['total_count']} 个结果"
            )

            # 提取指标和参数
            all_metrics = []
            all_params = {}

            for item in collection_result["results"]:
                data = item["data"]
                metrics = data.get("metrics", {})
                best_params = data.get("best_params", {})

                all_metrics.append(metrics)

                # 收集参数值
                for param_name, param_value in best_params.items():
                    if param_name not in all_params:
                        all_params[param_name] = []
                    all_params[param_name].append(param_value)

            # 计算统计指标
            stats = {}

            # 性能指标统计
            metric_names = ["NSE", "RMSE", "KGE", "PBIAS"]
            for metric_name in metric_names:
                values = [m.get(metric_name) for m in all_metrics if metric_name in m]
                if values:
                    stats[metric_name] = {
                        "mean": float(np.mean(values)),
                        "std": float(np.std(values)),
                        "min": float(np.min(values)),
                        "max": float(np.max(values)),
                        "cv": (
                            float(np.std(values) / np.mean(values))
                            if np.mean(values) != 0
                            else 0
                        ),
                    }

            # 参数统计
            param_stats = {}
            for param_name, param_values in all_params.items():
                if param_values:
                    param_stats[param_name] = {
                        "mean": float(np.mean(param_values)),
                        "std": float(np.std(param_values)),
                        "min": float(np.min(param_values)),
                        "max": float(np.max(param_values)),
                        "cv": (
                            float(np.std(param_values) / np.mean(param_values))
                            if np.mean(param_values) != 0
                            else 0
                        ),
                    }

            # 稳定性评估
            # NSE的变异系数 < 0.1 为稳定
            nse_cv = stats.get("NSE", {}).get("cv", 1.0)
            stability = "stable" if nse_cv < 0.1 else "unstable"

            logger.info(f"[RunnerAgent] 统计分析完成，稳定性: {stability}")

            return {
                "status": "success",
                "n_repeats": n_repeats,
                "found_results": len(all_metrics),
                "metric_statistics": stats,
                "parameter_statistics": param_stats,
                "stability": stability,
                "nse_cv": nse_cv,
            }

        except Exception as e:
            logger.error(f"[RunnerAgent] 统计分析失败: {str(e)}", exc_info=True)
            raise

    def _run_custom_analysis(
        self, config: Dict[str, Any], parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行自定义分析（包括代码生成和执行）- v4.0增强版。
        Execute custom analysis (including code generation and execution) - v4.0 enhanced.

        Args:
            config: 配置字典
            parameters: 任务参数
                - analysis_type: 分析类型（runoff_coefficient, FDC等）
                - basin_id: 流域ID
                - model_name: 模型名称

        Returns:
            自定义分析结果
        """
        logger.info("[RunnerAgent] 开始自定义分析...")

        analysis_type = parameters.get("analysis_type", "unknown")
        basin_id = parameters.get("basin_id")
        model_name = parameters.get("model_name")

        logger.info(f"[RunnerAgent] 分析类型: {analysis_type}")
        logger.info(f"[RunnerAgent] 流域: {basin_id}, 模型: {model_name}")

        #   v4.0: RunnerAgent负责代码生成和执行（带错误反馈循环）
        if not self.code_llm:
            logger.warning(
                "[RunnerAgent] Code LLM not configured, cannot generate code"
            )
            return {
                "status": "code_llm_not_configured",
                "analysis_type": analysis_type,
                "basin_id": basin_id,
                "model_name": model_name,
                "message": "Code LLM未配置，无法生成代码。请在创建RunnerAgent时提供code_llm_interface参数。",
            }

        #   v4.0: 使用带错误反馈的代码生成方法
        logger.info("[RunnerAgent] 开始代码生成和执行（带错误反馈循环）...")
        max_retries = parameters.get("code_gen_max_retries", 3)

        result = code_generator.generate_code_with_feedback(
            code_llm=self.code_llm,
            workspace_dir=self.workspace_dir,
            timeout=self.timeout,
            analysis_type=analysis_type,
            params=parameters,
            max_retries=max_retries,
        )

        # 处理结果
        if result.get("status") == "success":
            logger.info(
                f"[RunnerAgent] ✅ 自定义分析成功（尝试{result.get('attempts')}次）"
            )
            exec_result = result.get("execution_result", {})

            return {
                "status": "success",
                "analysis_type": analysis_type,
                "basin_id": basin_id,
                "model_name": model_name,
                "code_file": result["code_file"],
                "generated_code_path": result[
                    "code_file"
                ],  # 🔧 标准字段名，供DeveloperAgent使用
                "execution_output": exec_result,
                "generated_files": exec_result.get("output_files", []),
                "output_files": exec_result.get(
                    "output_files", []
                ),  # 🔧 别名，供DeveloperAgent使用
                "stdout": exec_result.get("stdout", ""),
                "stderr": exec_result.get("stderr", ""),  # 🔧 添加stderr
                "retry_count": result.get(
                    "attempts", 1
                ),  # 🔧 标准字段名，供DeveloperAgent使用
                "attempts": result.get("attempts", 1),
                "error_history": result.get("error_history", []),
                "message": f"✅ 自定义分析 '{analysis_type}' 执行成功\n📄 生成的代码: {result['code_file']}\n🔄 尝试次数: {result.get('attempts', 1)}",
            }
        else:
            # 代码生成或执行失败
            logger.error(f"[RunnerAgent] ❌ 自定义分析失败: {result.get('error')}")
            last_code_file = result.get("last_error", {}).get("code_file")
            return {
                "status": result.get("status", "failed"),
                "analysis_type": analysis_type,
                "basin_id": basin_id,
                "model_name": model_name,
                "code_file": last_code_file,
                "generated_code_path": last_code_file,  # 🔧 标准字段名，供DeveloperAgent使用
                "error": result.get("error"),
                "stderr": result.get("last_error", {}).get(
                    "stderr", ""
                ),  # 🔧 添加stderr
                "error_history": result.get("error_history", []),
                "retry_count": result.get("attempts", 0),  # 🔧 标准字段名
                "attempts": result.get("attempts", 0),
                "message": f"❌ 自定义分析 '{analysis_type}' 执行失败\n📄 最后生成的代码: {last_code_file or 'N/A'}\n🔄 尝试次数: {result.get('attempts', 0)}\n⚠️ 错误: {result.get('error')}",
            }

    #  自动迭代率定方法
    def _run_auto_iterative_calibration(
        self, config: Dict[str, Any], parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        自动迭代率定，直到NSE达标或达到最大次数（v4.0新功能）。
        Auto-iterative calibration until NSE threshold is met or max iterations reached.

        Args:
            config: 配置字典
            parameters: 任务参数
                - nse_threshold: 目标NSE阈值（默认0.7）
                - max_iterations: 最大迭代次数（默认10）
                - plot_each_iteration: 是否每轮绘图（默认True）

        Returns:
            迭代历史和结果
        """
        nse_threshold = parameters.get("nse_threshold", 0.7)
        max_iterations = parameters.get("max_iterations", 10)
        plot_each = parameters.get("plot_each_iteration", True)

        logger.info(f"[RunnerAgent] 🔄 开始自动迭代率定 (v4.0)")
        logger.info(f"  目标NSE: >= {nse_threshold}")
        logger.info(f"  最大次数: {max_iterations}")
        logger.info(f"  每轮绘图: {plot_each}")

        iteration_history = []
        converged = False

        for iteration in range(max_iterations):
            logger.info(f"\n{'='*70}")
            logger.info(f"🔄 Iteration {iteration + 1}/{max_iterations}")
            logger.info(f"{'='*70}")

            # 执行率定
            try:
                result = self._run_calibration(config)

                if not result.get("status") == "success":
                    logger.error(f"❌ Iteration {iteration + 1} failed")
                    iteration_history.append(
                        {
                            "iteration": iteration + 1,
                            "status": "failed",
                            "error": result.get("error", "Unknown error"),
                        }
                    )
                    break

                # 获取NSE
                nse = result.get("metrics", {}).get("NSE", 0.0)
                calibration_dir = result.get("calibration_dir")

                logger.info(f"📊 Iteration {iteration + 1} NSE: {nse:.4f}")

                # 记录历史
                iteration_history.append(
                    {
                        "iteration": iteration + 1,
                        "nse": nse,
                        "calibration_dir": calibration_dir,
                        "metrics": result.get("metrics", {}),
                        "status": "completed",
                    }
                )

                # 判断是否达标
                if nse >= nse_threshold:
                    logger.info(f"🎉 NSE达标！({nse:.4f} >= {nse_threshold})")
                    converged = True
                    break
                else:
                    logger.info(
                        f"⚠️  NSE未达标 ({nse:.4f} < {nse_threshold})，继续下一轮..."
                    )

            except Exception as e:
                logger.error(
                    f"❌ Iteration {iteration + 1} error: {str(e)}", exc_info=True
                )
                iteration_history.append(
                    {"iteration": iteration + 1, "status": "error", "error": str(e)}
                )
                break

        # 汇总结果
        if converged:
            status = "converged"
            message = (
                f"Successfully converged after {len(iteration_history)} iterations"
            )
        elif len(iteration_history) == max_iterations:
            status = "max_iterations_reached"
            message = f"Reached maximum iterations ({max_iterations})"
        else:
            status = "failed"
            message = "Calibration failed during iteration"

        final_nse = iteration_history[-1].get("nse", 0.0) if iteration_history else 0.0

        logger.info(f"\n{'='*70}")
        logger.info(f"✅ 自动迭代率定完成")
        logger.info(f"  状态: {status}")
        logger.info(f"  总迭代次数: {len(iteration_history)}")
        logger.info(f"  最终NSE: {final_nse:.4f}")
        logger.info(f"{'='*70}\n")

        return {
            "status": status,
            "converged": converged,
            "total_iterations": len(iteration_history),
            "final_nse": final_nse,
            "nse_threshold": nse_threshold,
            "iteration_history": iteration_history,
            "message": message,
        }

    # ========================================================================
    # 🆕 v5.0: Timeout and Retry Methods
    # ========================================================================

    def _execute_with_timeout(
        self, func: callable, timeout_seconds: int, *args, **kwargs
    ) -> Dict[str, Any]:
        """
        🆕 v5.0 Execute a function with timeout protection.
        使用超时保护执行函数。

        Args:
            func: Function to execute
            timeout_seconds: Timeout in seconds
            *args, **kwargs: Arguments to pass to func

        Returns:
            Result dict with success status and result/error
        """
        import signal
        import time

        def timeout_handler(signum, frame):
            raise TimeoutError(f"Execution exceeded timeout of {timeout_seconds}s")

        # Set timeout alarm (Unix only, Windows not supported)
        original_handler = None
        try:
            if hasattr(signal, 'SIGALRM'):  # Unix systems
                original_handler = signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(timeout_seconds)

            start_time = time.time()
            result = func(*args, **kwargs)
            elapsed_time = time.time() - start_time

            logger.info(f"[RunnerAgent] Execution completed in {elapsed_time:.1f}s")

            return {
                "success": True,
                "result": result,
                "elapsed_time": elapsed_time,
                "retryable": False,
            }

        except TimeoutError as e:
            logger.error(f"[RunnerAgent] Timeout error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "timeout",
                "retryable": True,
            }

        except Exception as e:
            logger.error(f"[RunnerAgent] Execution error: {str(e)}", exc_info=True)
            # Classify error
            error_type = self._classify_execution_error(e)
            retryable = self._is_retryable_error(error_type)

            return {
                "success": False,
                "error": str(e),
                "error_type": error_type,
                "retryable": retryable,
            }

        finally:
            # Cancel alarm
            if hasattr(signal, 'SIGALRM') and original_handler is not None:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, original_handler)

    def _execute_with_retry(
        self, func: callable, *args, **kwargs
    ) -> Dict[str, Any]:
        """
        🆕 v5.0 Execute a function with automatic retry on recoverable errors.
        在可恢复错误时自动重试执行函数。

        Args:
            func: Function to execute
            *args, **kwargs: Arguments to pass to func

        Returns:
            Final execution result
        """
        import time

        retry_count = 0
        last_error = None

        while retry_count < self.max_retries:
            logger.info(f"[RunnerAgent] Attempt {retry_count + 1}/{self.max_retries}")

            # Execute with timeout
            result = self._execute_with_timeout(func, self.timeout, *args, **kwargs)

            if result["success"]:
                if retry_count > 0:
                    logger.info(f"[RunnerAgent] ✅ Succeeded after {retry_count} retries")
                return result

            # Execution failed
            last_error = result
            error_type = result.get("error_type", "unknown")

            if not result.get("retryable", False):
                logger.error(f"[RunnerAgent] Unrecoverable error: {error_type}")
                return result

            # Wait before retry (exponential backoff)
            wait_time = self.retry_backoff ** retry_count
            logger.warning(
                f"[RunnerAgent] Retrying in {wait_time:.1f}s (error: {error_type})"
            )
            time.sleep(wait_time)

            retry_count += 1

        # Max retries exhausted
        logger.error(f"[RunnerAgent] ❌ Failed after {self.max_retries} retries")
        return {
            "success": False,
            "error": f"Max retries ({self.max_retries}) exhausted. Last error: {last_error.get('error')}",
            "error_type": "max_retries_exhausted",
            "retryable": False,
            "retry_count": self.max_retries,
        }

    def _classify_execution_error(self, error: Exception) -> str:
        """
        🆕 v5.0 Classify execution error type for intelligent recovery.
        分类执行错误类型以进行智能恢复。

        Args:
            error: Exception object

        Returns:
            Error type string
        """
        error_str = str(error).lower()
        error_name = error.__class__.__name__

        if "timeout" in error_str or error_name == "TimeoutError":
            return "timeout"
        elif "keyerror" in error_str or error_name == "KeyError":
            return "configuration_error"
        elif "filenotfound" in error_str or error_name == "FileNotFoundError":
            return "data_not_found"
        elif "importerror" in error_str or error_name == "ImportError":
            return "dependency_error"
        elif "nan" in error_str or "inf" in error_str:
            return "numerical_error"
        elif "memory" in error_str or error_name == "MemoryError":
            return "memory_error"
        else:
            return "unknown"

    def _is_retryable_error(self, error_type: str) -> bool:
        """
        🆕 v5.0 Determine if error type is retryable.
        判断错误类型是否可重试。

        Args:
            error_type: Error type string

        Returns:
            True if retryable
        """
        retryable_errors = {
            "timeout",
            "configuration_error",
            "numerical_error",
            "memory_error",
        }

        return error_type in retryable_errors

    def _reduce_complexity_on_timeout(
        self, config: Dict[str, Any], reduction_factor: float = 0.7
    ) -> Dict[str, Any]:
        """
        🆕 v5.0 Reduce algorithm complexity after timeout.
        超时后减少算法复杂度。

        Args:
            config: Original configuration
            reduction_factor: Factor to reduce iterations (default: 0.7)

        Returns:
            Modified configuration with reduced complexity
        """
        new_config = config.copy()

        # Reduce algorithm iterations
        training_cfgs = new_config.get("training_cfgs", {})
        if "algorithm" in training_cfgs:
            algorithm_params = training_cfgs.get("algorithm", {})

            # Reduce rep/max_generations/max_iterations
            if "rep" in algorithm_params:
                old_rep = algorithm_params["rep"]
                new_rep = int(old_rep * reduction_factor)
                algorithm_params["rep"] = max(new_rep, 100)  # Minimum 100
                logger.info(f"[RunnerAgent] Reduced rep: {old_rep} → {algorithm_params['rep']}")

            elif "max_generations" in algorithm_params:
                old_gen = algorithm_params["max_generations"]
                new_gen = int(old_gen * reduction_factor)
                algorithm_params["max_generations"] = max(new_gen, 50)
                logger.info(f"[RunnerAgent] Reduced generations: {old_gen} → {algorithm_params['max_generations']}")

            elif "max_iterations" in algorithm_params:
                old_iter = algorithm_params["max_iterations"]
                new_iter = int(old_iter * reduction_factor)
                algorithm_params["max_iterations"] = max(new_iter, 50)
                logger.info(f"[RunnerAgent] Reduced iterations: {old_iter} → {algorithm_params['max_iterations']}")

            new_config["training_cfgs"]["algorithm"] = algorithm_params

        return new_config
