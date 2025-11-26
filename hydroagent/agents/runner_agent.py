"""
Author: zhuanglaihong
Date: 2025-11-20 19:55:00
LastEditTime: 2025-11-20 19:55:00
LastEditors: zhuanglaihong
Description: Execution and monitoring agent - runs hydromodel and captures output
             执行监控智能体 - 运行 hydromodel 并捕获输出
FilePath: /HydroAgent/hydroagent/agents/runner_agent.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
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
            if hasattr(capture_stream, 'flush'):
                capture_stream.flush()

        # 对显示流应用过滤器
        if display_streams and self.filter_patterns:
            # 累积到缓冲区
            self._buffer += data

            # 处理完整行
            if '\n' in self._buffer:
                lines = self._buffer.split('\n')
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
                            stream.write(line + '\n')
                            if hasattr(stream, 'flush'):
                                stream.flush()
            # 如果是进度条更新（没有换行符，使用\r），直接显示
            elif '\r' in data:
                # 进度条通常不包含过滤模式，直接显示
                should_filter = False
                for pattern in self.filter_patterns:
                    if pattern in data:
                        should_filter = True
                        break

                if not should_filter:
                    for stream in display_streams:
                        stream.write(data)
                        if hasattr(stream, 'flush'):
                            stream.flush()
                # 清空缓冲区，因为\r会覆盖当前行
                self._buffer = ""

        elif display_streams:
            # 没有过滤模式，直接显示所有内容
            for stream in display_streams:
                stream.write(data)
                if hasattr(stream, 'flush'):
                    stream.flush()

    def flush(self):
        """刷新所有流"""
        for stream in self.streams:
            if hasattr(stream, 'flush'):
                stream.flush()

    def isatty(self):
        """检查是否为终端（进度条需要）"""
        # 如果任一流是终端，返回True
        return any(hasattr(s, 'isatty') and s.isatty() for s in self.streams)


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
        **kwargs
    ):
        """
        Initialize RunnerAgent.

        Args:
            llm_interface: LLM API interface
            code_llm_interface:   Optional LLM interface for code generation
                Examples: qwen-coder-turbo, deepseek-coder:6.7b
            workspace_dir: Working directory
            timeout: Execution timeout in seconds
            show_progress: 是否显示实时进度（进度条等）
                          Whether to show real-time progress (progress bars, etc.)
            **kwargs: Additional configuration
        """
        super().__init__(
            name="RunnerAgent",
            llm_interface=llm_interface,
            workspace_dir=workspace_dir,
            **kwargs
        )

        self.timeout = timeout
        self.show_progress = show_progress
        self.last_execution_log = None

        #   代码生成LLM
        self.code_llm = code_llm_interface if code_llm_interface else None
        if self.code_llm:
            logger.info(f"[RunnerAgent] Code generation enabled with model: {self.code_llm.model_name}")
        else:
            logger.info("[RunnerAgent] Code generation not configured (code_llm_interface not provided)")

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
            return {
                "success": False,
                "error": "Missing 'config' in input_data"
            }

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
            intent = input_data.get("intent_result", {}).get("intent") or input_data.get("intent", "calibration")

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
            model_name = task_metadata.get("model_name") or parameters.get("model_name", "N/A")
            basin_ids = task_metadata.get("basin_id") or parameters.get("basin_id", "N/A")
            logger.info(f"[RunnerAgent] 模型: {model_name}")
            logger.info(f"[RunnerAgent] 流域: {basin_ids}")
        else:
            logger.info(f"[RunnerAgent] 模型: {config.get('model_cfgs', {}).get('model_name', 'N/A')}")
            logger.info(f"[RunnerAgent] 流域: {config.get('data_cfgs', {}).get('basin_ids', [])}")

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
                "execution_log": self.last_execution_log
            }

        except Exception as e:
            logger.error(f"[RunnerAgent] 执行失败: {str(e)}", exc_info=True)

            return {
                "success": False,
                "task_id": task_id,
                "mode": mode,
                "error": str(e),
                "traceback": self._format_traceback(),
                "execution_log": self.last_execution_log
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
                    ]

                    # 使用TeeIO同时显示进度和保存日志，过滤装饰性输出
                    sys.stdout = TeeIO(stdout_capture, old_stdout, filter_patterns=filter_patterns)
                    sys.stderr = TeeIO(stderr_capture, old_stderr, filter_patterns=filter_patterns)
                    logger.info("[RunnerAgent] 执行率定（显示进度条，隐藏详细输出）...")
                else:
                    # 只保存日志，不显示进度
                    sys.stdout = stdout_capture
                    sys.stderr = stderr_capture
                    logger.info("[RunnerAgent] 执行率定（后台模式）...")

                # 运行率定 - 直接传入config dict
                logger.info("[RunnerAgent] 调用 calibrate(config)")
                result = calibrate(config)

            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr

                # 存储捕获的输出
                self.last_execution_log = {
                    "stdout": stdout_capture.getvalue(),
                    "stderr": stderr_capture.getvalue()
                }

            logger.info("[RunnerAgent] 率定完成")

            # 解析率定结果 - calibrate()会保存参数到文件，不直接返回
            parsed_result = self._parse_calibration_result(result, config)

            # ✅ 自动在测试期进行评估（标准水文模型流程）
            eval_result = None
            eval_metrics = {}
            calibration_dir = parsed_result.get("calibration_dir")

            if calibration_dir:
                logger.info(f"[RunnerAgent] 率定完成，参数保存在: {calibration_dir}")
                logger.info("[RunnerAgent] 开始在测试期进行评估...")
                try:
                    eval_result = self._run_evaluation_from_calibration(
                        calibration_dir,
                        config
                    )
                    eval_metrics = eval_result.get("metrics", {})
                    logger.info(f"[RunnerAgent] 评估完成，NSE={eval_metrics.get('NSE', 'N/A')}")
                except Exception as e:
                    logger.warning(f"[RunnerAgent] 评估失败: {str(e)}", exc_info=True)
            else:
                logger.warning("[RunnerAgent] 未获得率定输出目录，跳过评估")

            return {
                "status": "success",
                "calibration_result": result,
                "calibration_dir": calibration_dir,
                "calibration_metrics": parsed_result.get("metrics", {}),
                "best_params": parsed_result.get("best_params", {}),
                "evaluation_result": eval_result,
                "metrics": eval_metrics,  # ✅ 使用评估期的metrics（更准确）
                "output_files": parsed_result.get("output_files", []),
                "output_captured": True
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
        self,
        calibration_dir: str,
        original_config: Dict[str, Any]
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
            from hydromodel import evaluate
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
                logger.info(f"[RunnerAgent] 加载配置: load_config_from_calibration({calibration_dir})")
                config = load_config_from_calibration(calibration_dir)

                # 获取test period
                test_period = config["data_cfgs"]["test_period"]
                logger.info(f"[RunnerAgent] 测试期: {test_period}")

                # 运行评估 - hydromodel的evaluate会自动从calibration_dir读取参数
                logger.info(f"[RunnerAgent] 调用 evaluate(config, param_dir={calibration_dir})")
                result = evaluate(
                    config,
                    param_dir=calibration_dir,
                    eval_period=test_period,
                    eval_output_dir=None  # 使用默认输出目录
                )

            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr

                # 更新执行日志
                eval_log = {
                    "stdout": stdout_capture.getvalue(),
                    "stderr": stderr_capture.getvalue()
                }
                if self.last_execution_log:
                    self.last_execution_log["evaluation"] = eval_log
                else:
                    self.last_execution_log = eval_log

            logger.info("[RunnerAgent] 评估完成")
            logger.info(f"[RunnerAgent] evaluate()返回类型: {type(result)}")
            logger.info(f"[RunnerAgent] evaluate()返回keys: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
            if isinstance(result, dict) and result:
                first_key = list(result.keys())[0]
                logger.info(f"[RunnerAgent] result['{first_key}']的keys: {list(result[first_key].keys()) if isinstance(result[first_key], dict) else 'N/A'}")

            # 解析结果
            parsed_result = self._parse_evaluation_result(result)

            return {
                "status": "success",
                "evaluation_result": result,
                "metrics": parsed_result.get("metrics", {}),
                "performance": parsed_result.get("performance", {}),
                "output_files": parsed_result.get("output_files", [])
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
            from hydromodel import evaluate

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
                    "stderr": stderr_capture.getvalue()
                }

            logger.info("[RunnerAgent] 评估完成")

            # 解析结果
            parsed_result = self._parse_evaluation_result(result)

            return {
                "status": "success",
                "evaluation_result": result,
                "metrics": parsed_result.get("metrics", {}),
                "performance": parsed_result.get("performance", {}),
                "output_files": parsed_result.get("output_files", []),
                "output_captured": True
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
                    "stderr": stderr_capture.getvalue()
                }

            logger.info("[RunnerAgent] 模拟完成")

            return {
                "status": "success",
                "simulation_result": result,
                "output_captured": True
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

    def _parse_calibration_result(self, result: Any, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析率定结果。
        Parse calibration result.

        Args:
            result: hydromodel calibrate() 的返回值
            config: 原始配置（用于获取输出目录）

        Returns:
            解析后的结果字典，包含calibration_dir
        """
        parsed = {
            "metrics": {},
            "best_params": {},
            "output_files": [],
            "calibration_dir": None
        }

        try:
            # hydromodel的calibrate()会保存结果到output_dir，并返回结果字典
            logger.info(f"[RunnerAgent] calibrate()返回类型: {type(result)}")

            # 获取输出目录
            output_dir = config.get("training_cfgs", {}).get("output_dir")
            if output_dir:
                from pathlib import Path
                import json

                output_path = Path(output_dir)
                logger.info(f"[RunnerAgent] 查找率定输出目录: {output_path}")

                # 🔧 FIX: 支持两种情况
                # 1. 有子目录: output_dir/experiment_name/calibration_results.json (旧版)
                # 2. 无子目录: output_dir/calibration_results.json (experiment_name="" 时)
                if output_path.exists():
                    # 先检查是否直接在 output_path 中有 calibration_results.json
                    results_file_direct = output_path / "calibration_results.json"

                    if results_file_direct.exists():
                        # 情况2：直接保存在 output_dir（experiment_name=""）
                        calibration_dir = str(output_path)
                        logger.info(f"[RunnerAgent] 找到率定目录（直接模式）: {calibration_dir}")
                        parsed["calibration_dir"] = calibration_dir

                        # 读取 calibration_results.json
                        with open(results_file_direct, 'r') as f:
                            calib_results = json.load(f)
                            logger.info(f"[RunnerAgent] 读取calibration_results.json")

                            # 提取第一个basin的参数
                            if calib_results:
                                basin_id = list(calib_results.keys())[0]
                                basin_data = calib_results[basin_id]

                                if "best_params" in basin_data:
                                    # best_params格式: {"gr4j": {"x1": ..., "x2": ...}}
                                    model_params = basin_data["best_params"]
                                    # 提取第一个模型的参数
                                    if model_params:
                                        model_name = list(model_params.keys())[0]
                                        parsed["best_params"] = model_params[model_name]
                                        logger.info(f"[RunnerAgent] 提取参数: {parsed['best_params']}")
                    else:
                        # 情况1：查找最新的实验子目录（旧版逻辑）
                        experiment_dirs = sorted([d for d in output_path.iterdir() if d.is_dir()],
                                               key=lambda x: x.stat().st_mtime,
                                               reverse=True)

                        if experiment_dirs:
                            calibration_dir = str(experiment_dirs[0])
                            logger.info(f"[RunnerAgent] 找到率定目录（子目录模式）: {calibration_dir}")
                            parsed["calibration_dir"] = calibration_dir

                            # 尝试读取calibration_results.json
                            results_file = Path(calibration_dir) / "calibration_results.json"
                            if results_file.exists():
                                with open(results_file, 'r') as f:
                                    calib_results = json.load(f)
                                    logger.info(f"[RunnerAgent] 读取calibration_results.json")

                                    # 提取第一个basin的参数
                                    if calib_results:
                                        basin_id = list(calib_results.keys())[0]
                                        basin_data = calib_results[basin_id]

                                        if "best_params" in basin_data:
                                            # best_params格式: {"gr4j": {"x1": ..., "x2": ...}}
                                            model_params = basin_data["best_params"]
                                            # 提取第一个模型的参数
                                            if model_params:
                                                model_name = list(model_params.keys())[0]
                                                parsed["best_params"] = model_params[model_name]
                                                logger.info(f"[RunnerAgent] 提取参数: {parsed['best_params']}")
                            else:
                                logger.warning(f"[RunnerAgent] 未找到calibration_results.json: {results_file}")
                        else:
                            logger.warning(f"[RunnerAgent] 输出目录中没有实验目录或结果文件: {output_path}")
                else:
                    logger.warning(f"[RunnerAgent] 输出目录不存在: {output_path}")
            else:
                logger.warning("[RunnerAgent] 配置中没有output_dir")

            # 如果result是dict，也尝试从中提取信息
            if isinstance(result, dict):
                logger.info(f"[RunnerAgent] result的keys: {list(result.keys())}")

                if "metrics" in result:
                    parsed["metrics"] = result["metrics"]
                elif "performance" in result:
                    parsed["metrics"] = result["performance"]

            logger.info(f"[RunnerAgent] 解析结果: calibration_dir={parsed['calibration_dir']}, best_params={len(parsed['best_params'])}个")

        except Exception as e:
            logger.error(f"[RunnerAgent] 解析率定结果时出错: {str(e)}", exc_info=True)

        return parsed

    def _parse_evaluation_result(self, result: Any) -> Dict[str, Any]:
        """
        解析评估结果。
        Parse evaluation result.

        Args:
            result: hydromodel evaluate() 的返回值
                    格式: {basin_id: {"metrics": {...}, "parameters": {...}}, ...}

        Returns:
            解析后的结果字典
        """
        parsed = {
            "metrics": {},
            "performance": {},
            "output_files": []
        }

        try:
            if isinstance(result, dict):
                # hydromodel的evaluate()返回格式: {basin_id: {"metrics": {...}, "parameters": {...}}}
                # 提取第一个basin的metrics（通常只有一个basin）
                if result:
                    first_basin_id = list(result.keys())[0]
                    basin_result = result[first_basin_id]

                    if isinstance(basin_result, dict):
                        # 提取metrics
                        if "metrics" in basin_result:
                            metrics = basin_result["metrics"]
                            # hydromodel返回的metrics可能是dict或有数组值的dict
                            # 例如: {"NSE": array([0.85]), "RMSE": array([1.23])}
                            # 将数组值转换为标量
                            flat_metrics = {}
                            for key, value in metrics.items():
                                if isinstance(value, (list, np.ndarray)):
                                    flat_metrics[key] = float(value[0]) if len(value) > 0 else None
                                else:
                                    flat_metrics[key] = value

                            parsed["metrics"] = flat_metrics
                            parsed["performance"] = flat_metrics
                            logger.info(f"[RunnerAgent] 提取basin {first_basin_id}的metrics: {list(flat_metrics.keys())}")

                        # 提取parameters
                        if "parameters" in basin_result:
                            parsed["parameters"] = basin_result["parameters"]

                # 旧格式兼容（直接包含metrics的情况）
                elif "metrics" in result:
                    parsed["metrics"] = result["metrics"]
                    parsed["performance"] = result["metrics"]
                elif "performance" in result:
                    parsed["performance"] = result["performance"]
                    parsed["metrics"] = result["performance"]

                # 提取输出文件
                if "output_files" in result:
                    parsed["output_files"] = result["output_files"]
                elif "files" in result:
                    parsed["output_files"] = result["files"]

            logger.debug(f"[RunnerAgent] 解析评估结果: {len(parsed['metrics'])} 个指标")

        except Exception as e:
            logger.warning(f"[RunnerAgent] 解析评估结果时出错: {str(e)}", exc_info=True)

        return parsed

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

    # ========================================================================
    # Phase 3: 新增任务类型支持
    # ========================================================================

    def _run_boundary_check_recalibration(
        self,
        config: Dict[str, Any],
        parameters: Dict[str, Any]
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

            # ⭐ 为初始率定设置唯一的输出目录
            initial_config = config.copy()
            if "training_cfgs" in initial_config:
                initial_config["training_cfgs"] = config["training_cfgs"].copy()
                # 设置输出目录名为 calibration_iter0
                if self.workspace_dir:
                    initial_config["training_cfgs"]["output_dir"] = str(self.workspace_dir / "calibration_iter0")
                    # ⭐ 清空 experiment_name，避免 hydromodel 创建额外的子目录
                    initial_config["training_cfgs"]["experiment_name"] = ""
                    logger.info(f"[RunnerAgent] Iteration 0 输出目录: {initial_config['training_cfgs']['output_dir']}")

            initial_result = self._run_calibration(initial_config)

            if not initial_result.get("status") == "success":
                logger.error("[RunnerAgent] 初始率定失败")
                return {
                    "status": "initial_calibration_failed",
                    "error": "Initial calibration failed",
                    "iterations": []
                }

            # 获取初始NSE
            initial_nse = initial_result.get("metrics", {}).get("NSE", 0.0)
            initial_calib_dir = initial_result.get("calibration_dir")

            logger.info(f"✅ 初始率定完成: NSE={initial_nse:.4f}")
            logger.info(f"   率定目录: {initial_calib_dir}")

            # 迭代历史
            iteration_history = [{
                "iteration": 0,
                "nse": initial_nse,
                "calibration_dir": initial_calib_dir,
                "range_scale": None,
                "metrics": initial_result.get("metrics", {}),
                "status": "completed"
            }]

            # 检查是否已经达标
            if initial_nse >= nse_threshold:
                logger.info(f"🎉 初始NSE={initial_nse:.4f} 已达标（>= {nse_threshold}），无需迭代优化")
                return {
                    "status": "already_optimal",
                    "iterations": iteration_history,
                    "total_iterations": 0,
                    "final_nse": initial_nse,
                    "final_metrics": initial_result.get("metrics", {}),
                    "message": f"Initial NSE {initial_nse:.4f} already meets threshold {nse_threshold}"
                }

            # 开始迭代优化
            best_nse = initial_nse
            best_iteration = 0
            prev_calib_dir = initial_calib_dir
            consecutive_no_improvement = 0

            for iteration in range(1, max_iterations + 1):
                logger.info("\n" + "=" * 70)
                logger.info(f"🔄 Iteration {iteration}/{max_iterations}: 自适应范围调整")
                logger.info("=" * 70)

                # 动态计算 range_scale（逐渐缩小）
                # 策略: 0.6 -> 0.4 -> 0.3 -> 0.2 -> 0.15
                range_scale = initial_range_scale * (0.7 ** iteration)
                range_scale = max(range_scale, 0.1)  # 最小不低于10%

                logger.info(f"📏 当前缩放比例: {range_scale:.2%} (第{iteration}次迭代)")

                # 调整参数范围
                logger.info(f"📂 基于上次结果调整范围: {prev_calib_dir}")

                adjust_result = self.adjust_param_range_from_previous_calibration(
                    prev_calibration_dir=prev_calib_dir,
                    range_scale=range_scale,
                    output_yaml_path=str(Path(self.workspace_dir) / f"param_range_iter{iteration}.yaml") if self.workspace_dir else None
                )

                if not adjust_result["success"]:
                    logger.error(f"❌ 参数范围调整失败: {adjust_result.get('error')}")
                    iteration_history.append({
                        "iteration": iteration,
                        "nse": None,
                        "range_scale": range_scale,
                        "status": "adjustment_failed",
                        "error": adjust_result.get("error")
                    })
                    break

                logger.info(f"✅ 参数范围调整完成: {adjust_result['output_file']}")

                # 更新config，使用新的参数范围文件
                new_config = config.copy()
                new_config["model_cfgs"] = config["model_cfgs"].copy()
                # ⭐ 保存到 model_cfgs 用于记录（在 calibration_config.yaml 中）
                new_config["model_cfgs"]["param_range_file"] = adjust_result["output_file"]

                # ⭐ 为每次迭代设置唯一的输出目录
                if "training_cfgs" in new_config:
                    new_config["training_cfgs"] = config["training_cfgs"].copy()
                    # 🔧 FIX: hydromodel 只从 training_cfgs 读取 param_range_file
                    # 必须设置到 training_cfgs，否则会使用内置的 MODEL_PARAM_DICT（原始范围）
                    new_config["training_cfgs"]["param_range_file"] = adjust_result["output_file"]
                    logger.info(f"[RunnerAgent] 设置参数范围文件: {adjust_result['output_file']}")

                    # 设置输出目录名为 calibration_iter{N}
                    if self.workspace_dir:
                        new_config["training_cfgs"]["output_dir"] = str(self.workspace_dir / f"calibration_iter{iteration}")
                        # ⭐ 清空 experiment_name，避免 hydromodel 创建额外的子目录
                        new_config["training_cfgs"]["experiment_name"] = ""
                        logger.info(f"[RunnerAgent] Iteration {iteration} 输出目录: {new_config['training_cfgs']['output_dir']}")

                # 执行率定
                logger.info(f"🚀 执行第 {iteration} 次率定...")
                iter_result = self._run_calibration(new_config)

                if not iter_result.get("status") == "success":
                    logger.error(f"❌ 第 {iteration} 次率定失败")
                    iteration_history.append({
                        "iteration": iteration,
                        "nse": None,
                        "range_scale": range_scale,
                        "status": "calibration_failed",
                        "error": "Calibration execution failed"
                    })
                    break

                # 获取本次NSE
                current_nse = iter_result.get("metrics", {}).get("NSE", 0.0)
                current_calib_dir = iter_result.get("calibration_dir")

                logger.info(f"📊 第 {iteration} 次率定完成: NSE={current_nse:.4f}")
                logger.info(f"   率定目录: {current_calib_dir}")

                # 记录历史
                iteration_history.append({
                    "iteration": iteration,
                    "nse": current_nse,
                    "nse_improvement": current_nse - best_nse,
                    "calibration_dir": current_calib_dir,
                    "range_scale": range_scale,
                    "metrics": iter_result.get("metrics", {}),
                    "param_range_adjustment": adjust_result,
                    "status": "completed"
                })

                # 判断是否改善
                nse_improvement = current_nse - best_nse

                if nse_improvement > min_nse_improvement:
                    logger.info(f"✅ NSE改善: {best_nse:.4f} -> {current_nse:.4f} (+{nse_improvement:.4f})")
                    best_nse = current_nse
                    best_iteration = iteration
                    prev_calib_dir = current_calib_dir
                    consecutive_no_improvement = 0

                    # 检查是否达标
                    if current_nse >= nse_threshold:
                        logger.info(f"🎉 NSE={current_nse:.4f} 已达标（>= {nse_threshold}），停止迭代")
                        return {
                            "status": "converged",
                            "iterations": iteration_history,
                            "total_iterations": iteration,
                            "best_iteration": best_iteration,
                            "final_nse": current_nse,
                            "final_metrics": iter_result.get("metrics", {}),
                            "message": f"Converged at iteration {iteration} with NSE {current_nse:.4f}"
                        }
                else:
                    consecutive_no_improvement += 1
                    logger.warning(f"⚠️  NSE无改善或下降: {best_nse:.4f} -> {current_nse:.4f} ({nse_improvement:+.4f})")
                    logger.warning(f"   连续无改善次数: {consecutive_no_improvement}")

                    # 连续2次无改善，提前停止
                    if consecutive_no_improvement >= 2:
                        logger.warning(f"⛔ 连续 {consecutive_no_improvement} 次无改善，提前停止迭代")
                        logger.warning(f"   建议人工检查参数范围或模型设置")
                        return {
                            "status": "no_improvement",
                            "iterations": iteration_history,
                            "total_iterations": iteration,
                            "best_iteration": best_iteration,
                            "final_nse": best_nse,
                            "final_metrics": iteration_history[best_iteration]["metrics"],
                            "message": f"No improvement after {consecutive_no_improvement} iterations. Best NSE: {best_nse:.4f} at iteration {best_iteration}",
                            "recommendation": "建议人工设置更合理的参数范围或检查模型配置"
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
                    "recommendation": "建议人工设置更合理的参数范围或检查模型配置"
                }
            else:
                return {
                    "status": "converged_at_max",
                    "iterations": iteration_history,
                    "total_iterations": max_iterations,
                    "best_iteration": best_iteration,
                    "final_nse": best_nse,
                    "final_metrics": iteration_history[best_iteration]["metrics"],
                    "message": f"Converged at max iterations. Best NSE: {best_nse:.4f}"
                }

        except Exception as e:
            logger.error(f"[RunnerAgent] 迭代优化失败: {str(e)}", exc_info=True)
            raise

    def _run_statistical_analysis(
        self,
        config: Dict[str, Any],
        parameters: Dict[str, Any],
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        统计分析多次重复实验的结果（实验5）。
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

            workspace_dir = Path(config.get("training_cfgs", {}).get("output_dir", ".")).parent
            logger.info(f"[RunnerAgent] 从 {workspace_dir} 收集重复实验结果...")

            # 收集所有重复任务的结果
            all_metrics = []
            all_params = {}

            for i in range(n_repeats):
                task_dir = workspace_dir / f"task_{i+1}_repeat"
                result_file = task_dir / "calibration_results.json"

                if result_file.exists():
                    with open(result_file, 'r', encoding='utf-8') as f:
                        result = json.load(f)

                    metrics = result.get("metrics", {})
                    best_params = result.get("best_params", {})

                    all_metrics.append(metrics)

                    # 收集参数值
                    for param_name, param_value in best_params.items():
                        if param_name not in all_params:
                            all_params[param_name] = []
                        all_params[param_name].append(param_value)

                else:
                    logger.warning(f"[RunnerAgent] 结果文件不存在: {result_file}")

            if not all_metrics:
                logger.warning("[RunnerAgent] 没有找到任何重复实验结果")
                return {
                    "status": "no_data",
                    "n_repeats": n_repeats,
                    "found_results": 0
                }

            logger.info(f"[RunnerAgent] 收集到 {len(all_metrics)} 个结果")

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
                        "cv": float(np.std(values) / np.mean(values)) if np.mean(values) != 0 else 0
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
                        "cv": float(np.std(param_values) / np.mean(param_values)) if np.mean(param_values) != 0 else 0
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
                "nse_cv": nse_cv
            }

        except Exception as e:
            logger.error(f"[RunnerAgent] 统计分析失败: {str(e)}", exc_info=True)
            raise

    def _run_custom_analysis(
        self,
        config: Dict[str, Any],
        parameters: Dict[str, Any]
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
            logger.warning("[RunnerAgent] Code LLM not configured, cannot generate code")
            return {
                "status": "code_llm_not_configured",
                "analysis_type": analysis_type,
                "basin_id": basin_id,
                "model_name": model_name,
                "message": "Code LLM未配置，无法生成代码。请在创建RunnerAgent时提供code_llm_interface参数。"
            }

        #   v4.0: 使用带错误反馈的代码生成方法
        logger.info("[RunnerAgent] 开始代码生成和执行（带错误反馈循环）...")
        max_retries = parameters.get("code_gen_max_retries", 3)

        result = self._generate_code_with_feedback(
            analysis_type=analysis_type,
            params=parameters,
            max_retries=max_retries
        )

        # 处理结果
        if result.get("status") == "success":
            logger.info(f"[RunnerAgent] ✅ 自定义分析成功（尝试{result.get('attempts')}次）")
            exec_result = result.get("execution_result", {})

            return {
                "status": "success",
                "analysis_type": analysis_type,
                "basin_id": basin_id,
                "model_name": model_name,
                "code_file": result["code_file"],
                "generated_code_path": result["code_file"],  # 🔧 标准字段名，供DeveloperAgent使用
                "execution_output": exec_result,
                "generated_files": exec_result.get("output_files", []),
                "output_files": exec_result.get("output_files", []),  # 🔧 别名，供DeveloperAgent使用
                "stdout": exec_result.get("stdout", ""),
                "stderr": exec_result.get("stderr", ""),  # 🔧 添加stderr
                "retry_count": result.get("attempts", 1),  # 🔧 标准字段名，供DeveloperAgent使用
                "attempts": result.get("attempts", 1),
                "error_history": result.get("error_history", []),
                "message": f"✅ 自定义分析 '{analysis_type}' 执行成功\n📄 生成的代码: {result['code_file']}\n🔄 尝试次数: {result.get('attempts', 1)}"
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
                "stderr": result.get("last_error", {}).get("stderr", ""),  # 🔧 添加stderr
                "error_history": result.get("error_history", []),
                "retry_count": result.get("attempts", 0),  # 🔧 标准字段名
                "attempts": result.get("attempts", 0),
                "message": f"❌ 自定义分析 '{analysis_type}' 执行失败\n📄 最后生成的代码: {last_code_file or 'N/A'}\n🔄 尝试次数: {result.get('attempts', 0)}\n⚠️ 错误: {result.get('error')}"
            }

    # ========================================================================
    # 智能参数范围调整工具
    # ========================================================================

    def adjust_param_range_from_previous_calibration(
        self,
        prev_calibration_dir: str,
        range_scale: float = 0.6,
        output_yaml_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        从上一次率定结果中智能调整参数范围。

        核心思路:
        1. 读取上一次的参数范围 (param_range.yaml)
        2. 读取上一次的最佳参数 (basins_denorm_params.csv，注意是反归一化的)
        3. 以最佳参数为中心点，缩小搜索范围（例如原范围长度 * 60%）
        4. 保持物理意义，确保新范围在合理区间内
        5. 生成新的 param_range.yaml

        Args:
            prev_calibration_dir: 上一次率定结果目录
                例如: "results/20251121_211408/gr4j_SCE_UA_20251121_211414"
            range_scale: 新范围长度占原范围长度的比例（默认0.6，即60%）
            output_yaml_path: 输出的新参数范围YAML文件路径（可选）

        Returns:
            调整后的参数范围信息
            {
                "success": True/False,
                "prev_param_range": {...},  # 上一次的参数范围
                "best_params": {...},       # 最佳参数（反归一化）
                "new_param_range": {...},   # 新的参数范围
                "output_file": "path/to/new_param_range.yaml"
            }
        """
        logger.info(f"[RunnerAgent] 开始智能参数范围调整")
        logger.info(f"[RunnerAgent] 读取上一次率定结果: {prev_calibration_dir}")
        logger.info(f"[RunnerAgent] 范围缩放比例: {range_scale}")

        try:
            from pathlib import Path
            import yaml
            import pandas as pd

            prev_dir = Path(prev_calibration_dir)

            # 1. 读取上一次的参数范围
            param_range_file = prev_dir / "param_range.yaml"
            if not param_range_file.exists():
                logger.error(f"[RunnerAgent] 参数范围文件不存在: {param_range_file}")
                return {
                    "success": False,
                    "error": f"param_range.yaml not found in {prev_dir}"
                }

            with open(param_range_file, 'r', encoding='utf-8') as f:
                param_range_data = yaml.safe_load(f)

            # ⭐ BUG FIX: 提取实际的参数范围字典
            # param_range.yaml 格式可能是:
            # 1. {model_name: {param_range: {...}}}  # hydromodel标准格式
            # 2. {param_name: [...]}                 # 直接格式
            if isinstance(param_range_data, dict):
                # 检查是否有模型名作为第一层key（如 'xaj', 'gr4j'）
                model_names = ['xaj', 'gr4j', 'gr5j', 'gr6j', 'lstm']  # 常见模型名
                found_model = None
                for model_name in model_names:
                    if model_name in param_range_data:
                        found_model = model_name
                        break

                if found_model and 'param_range' in param_range_data[found_model]:
                    # 格式1: {model_name: {param_range: {...}}}
                    prev_param_range = param_range_data[found_model]['param_range']
                    logger.info(f"[RunnerAgent] 检测到模型: {found_model}")
                else:
                    # 格式2: 直接就是参数范围字典
                    prev_param_range = param_range_data
            else:
                prev_param_range = param_range_data

            logger.info(f"[RunnerAgent] 上一次参数范围: {prev_param_range}")

            # 2. 读取最佳参数（反归一化）
            best_params_file = prev_dir / "basins_denorm_params.csv"
            if not best_params_file.exists():
                logger.error(f"[RunnerAgent] 最佳参数文件不存在: {best_params_file}")
                return {
                    "success": False,
                    "error": f"basins_denorm_params.csv not found in {prev_dir}"
                }

            # 读取CSV（通常第一列是basin_id，其余是参数）
            df = pd.read_csv(best_params_file)
            logger.info(f"[RunnerAgent] basins_denorm_params.csv columns: {df.columns.tolist()}")

            # 提取第一个流域的参数
            # 假设格式: basin_id, x1, x2, x3, x4, ...
            if len(df) == 0:
                logger.error("[RunnerAgent] basins_denorm_params.csv 是空的")
                return {"success": False, "error": "Empty parameter file"}

            # 获取第一行（第一个流域）
            param_row = df.iloc[0]

            # ⭐ BUG FIX: 排除流域ID列（可能的列名变体）
            # hydromodel可能生成的流域ID列名: 'Unnamed: 0', 'basin_id', 'basin', 'id', 'index'
            id_column_patterns = ['unnamed', 'basin_id', 'basin', 'id', 'index']

            param_columns = [
                col for col in df.columns
                if not any(pattern in col.lower() for pattern in id_column_patterns)
            ]

            # 如果没有找到参数列（所有列都被排除了），使用除第一列外的所有列
            if not param_columns and len(df.columns) > 1:
                logger.warning("[RunnerAgent] 无法识别ID列，使用除第一列外的所有列作为参数")
                param_columns = df.columns[1:].tolist()

            best_params = {col: param_row[col] for col in param_columns}

            logger.info(f"[RunnerAgent] 参数列: {param_columns}")
            logger.info(f"[RunnerAgent] 最佳参数（反归一化）: {best_params}")

            # 3. 计算新的参数范围
            # 格式: {param_name: [min, max]}
            new_param_range = {}
            param_name_list = []  # 保存参数名列表（用于生成标准格式）

            for param_name, best_value in best_params.items():
                if param_name not in prev_param_range:
                    logger.warning(f"[RunnerAgent] 参数 {param_name} 不在 param_range.yaml 中，跳过")
                    continue

                prev_range = prev_param_range[param_name]
                if not isinstance(prev_range, (list, tuple)) or len(prev_range) != 2:
                    logger.warning(f"[RunnerAgent] 参数 {param_name} 的范围格式不正确: {prev_range}")
                    continue

                prev_min, prev_max = prev_range
                prev_length = prev_max - prev_min

                # 新范围长度 = 原范围长度 * range_scale
                new_length = prev_length * range_scale

                # 以最佳参数为中心点
                new_min = best_value - new_length / 2
                new_max = best_value + new_length / 2

                # 确保不超出原始范围（保持物理意义）
                # 同时确保不超出合理的物理范围（例如参数不能为负）
                new_min = max(new_min, prev_min)
                new_max = min(new_max, prev_max)

                # 如果最佳值接近边界，调整范围
                if new_min == prev_min:
                    # 最佳值在下边界附近，向上扩展
                    new_max = min(new_min + new_length, prev_max)
                if new_max == prev_max:
                    # 最佳值在上边界附近，向下扩展
                    new_min = max(new_max - new_length, prev_min)

                new_param_range[param_name] = [float(new_min), float(new_max)]
                param_name_list.append(param_name)  # 记录参数名

                logger.info(f"[RunnerAgent] 参数 {param_name}:")
                logger.info(f"  原范围: [{prev_min}, {prev_max}] (长度: {prev_length})")
                logger.info(f"  最佳值: {best_value}")
                logger.info(f"  新范围: [{new_min:.4f}, {new_max:.4f}] (长度: {new_max - new_min:.4f})")

            # 4. 保存新的参数范围（使用标准格式）
            if output_yaml_path is None:
                # 默认保存在当前工作目录
                output_yaml_path = self.workspace_dir / "adjusted_param_range.yaml" if self.workspace_dir else Path("adjusted_param_range.yaml")
            else:
                output_yaml_path = Path(output_yaml_path)

            output_yaml_path.parent.mkdir(parents=True, exist_ok=True)

            # ⭐ 生成标准格式的YAML（与原始param_range.yaml格式一致）
            # 检测模型名（如果原始YAML有嵌套结构）
            if found_model:
                # 格式1: {model_name: {param_name: [...], param_range: {...}}}
                standard_format_yaml = {
                    found_model: {
                        'param_name': param_name_list,
                        'param_range': new_param_range
                    }
                }
            else:
                # 格式2: 直接格式（保持向后兼容）
                standard_format_yaml = new_param_range

            with open(output_yaml_path, 'w', encoding='utf-8') as f:
                yaml.dump(standard_format_yaml, f, default_flow_style=False, allow_unicode=True)

            logger.info(f"[RunnerAgent] 新参数范围已保存: {output_yaml_path}")
            logger.info(f"[RunnerAgent] 使用格式: {'标准格式 (含模型名)' if found_model else '简化格式'}")

            return {
                "success": True,
                "prev_param_range": prev_param_range,
                "best_params": best_params,
                "new_param_range": new_param_range,
                "output_file": str(output_yaml_path),
                "scale": range_scale
            }

        except Exception as e:
            logger.error(f"[RunnerAgent] 参数范围调整失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    # ========================================================================
    #   v4.0: 代码生成和执行方法
    # ========================================================================

    def _generate_analysis_code(
        self,
        analysis_type: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        调用Code LLM生成分析代码。
        Call Code LLM to generate analysis code.

        Args:
            analysis_type: 分析类型（runoff_coefficient, FDC等）
            params: 参数字典

        Returns:
            生成结果 {"code_file": str, "code": str} 或 {"error": str}
        """
        if not self.code_llm:
            return {"error": "Code LLM not configured"}

        # 构建代码生成提示词
        prompt = self._build_code_generation_prompt(analysis_type, params)

        try:
            # 使用Code LLM生成代码
            logger.info(f"[RunnerAgent] 调用Code LLM: {self.code_llm.model_name}")
            code = self.code_llm.generate(
                system_prompt="你是一个专业的Python代码生成助手，擅长编写水文数据分析和可视化代码。",
                user_prompt=prompt,
                temperature=0.1,  # 低温度确保代码准确性
                max_tokens=2000
            )

            # 提取代码（去除markdown格式）
            if "```python" in code:
                code = code.split("```python")[1].split("```")[0].strip()
            elif "```" in code:
                code = code.split("```")[1].split("```")[0].strip()

            # 保存代码到文件（统一保存到项目 generated_code 目录）
            # 获取项目根目录
            project_root = Path(__file__).parent.parent.parent
            generated_code_dir = project_root / "generated_code"
            generated_code_dir.mkdir(exist_ok=True)

            # 生成带时间戳的文件名，方便查看历史记录
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            code_file = generated_code_dir / f"{analysis_type}_analysis_{timestamp}.py"
            code_file.write_text(code, encoding='utf-8')

            logger.info(f"[RunnerAgent] Generated code saved to: {code_file}")
            logger.info(f"[RunnerAgent] 💡 Code saved to project directory for easy inspection")

            return {
                "code_file": str(code_file),
                "code": code
            }

        except Exception as e:
            logger.error(f"[RunnerAgent] Code generation failed: {str(e)}", exc_info=True)
            return {"error": str(e)}

    def _execute_generated_code(self, code_file: str) -> Dict[str, Any]:
        """
        执行生成的代码。
        Execute generated code.

        Args:
            code_file: 代码文件路径

        Returns:
            执行结果
        """
        import subprocess

        logger.info(f"[RunnerAgent] Executing code: {code_file}")

        try:
            # 使用subprocess执行代码
            result = subprocess.run(
                [sys.executable, code_file],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.workspace_dir
            )

            if result.returncode == 0:
                logger.info("[RunnerAgent] Code execution successful")
                return {
                    "status": "success",
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "output_files": self._scan_output_files()
                }
            else:
                logger.error(f"[RunnerAgent] Code execution failed with return code {result.returncode}")
                return {
                    "status": "failed",
                    "error": result.stderr,
                    "stdout": result.stdout,
                    "returncode": result.returncode
                }

        except subprocess.TimeoutExpired:
            logger.error(f"[RunnerAgent] Code execution timeout ({self.timeout}s)")
            return {
                "status": "timeout",
                "error": f"Execution timeout after {self.timeout} seconds"
            }

        except Exception as e:
            logger.error(f"[RunnerAgent] Code execution error: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    def _build_code_generation_prompt(
        self,
        analysis_type: str,
        params: Dict[str, Any]
    ) -> str:
        """
        构建代码生成提示词。
        Build code generation prompt.

        Args:
            analysis_type: 分析类型
            params: 参数字典

        Returns:
            完整的提示词
        """
        basin_id = params.get("basin_id", "N/A")
        model_name = params.get("model_name", "N/A")

        # 预定义的分析类型模板
        templates = {
            "runoff_coefficient": f"""
请生成Python代码，计算流域 {basin_id} 的径流系数。

具体要求：
1. 从率定结果目录读取流量和降水数据
2. 计算总径流量和总降水量
3. 径流系数 = 总径流量 / 总降水量
4. 打印结果，保存到CSV文件（runoff_coefficient.csv）
5. 如果可能，绘制时间序列对比图

数据源：
- 从 calibration_results.json 或 NetCDF 文件读取
- 或使用 hydrodataset 加载原始数据

代码要求：
- 使用 type hints
- 添加详细注释
- 包含错误处理
- 打印进度信息

🔧 **CRITICAL: 中文显示配置**
如果使用 matplotlib 绘图，必须在代码开头添加：
```python
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
```
""",

            "FDC": f"""
请生成Python代码，绘制流域 {basin_id} 的流量历时曲线（Flow Duration Curve, FDC）。

具体要求：
1. 从率定结果读取流量数据（观测值和模拟值）
2. 对流量数据进行降序排序
3. 计算超越概率（exceedance probability）
4. 绘制FDC曲线（使用对数坐标）
5. 同时绘制观测值和模拟值的FDC，进行对比
6. 保存高分辨率图片（fdc_curve.png, 300 DPI）

🔧 **CRITICAL: matplotlib 中文显示配置**
必须在导入matplotlib后立即添加：
```python
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
```

绘图要求：
- 使用 matplotlib 并配置中文字体
- 图表清晰美观，包含图例、网格
- 保存为PNG格式

代码要求：
- 使用 type hints
- 添加详细注释
- 包含错误处理
""",

            "water_balance": f"""
请生成Python代码，分析流域 {basin_id} 的水量平衡。

具体要求：
1. 读取降水、蒸散发、径流数据
2. 计算水量平衡：P = ET + Q + ΔS
3. 分析各项占比（降水、蒸散发、径流）
4. 绘制水量平衡饼图或柱状图
5. 计算和显示误差项
6. 保存结果到CSV和图片

🔧 **CRITICAL: matplotlib 中文显示配置**
必须在导入matplotlib后立即添加：
```python
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
```

代码要求：
- 使用 type hints
- 添加详细注释
- 包含错误处理
""",

            "seasonal_analysis": f"""
请生成Python代码，进行流域 {basin_id} 的季节性分析。

具体要求：
1. 读取多年流量数据
2. 按季节（春夏秋冬）分组统计
3. 计算每个季节的平均流量、最大流量、最小流量
4. 绘制季节性变化箱线图
5. 分析径流的季节性特征
6. 保存统计结果和图表

🔧 **CRITICAL: matplotlib 中文显示配置**
必须在导入matplotlib后立即添加：
```python
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
```

代码要求：
- 使用 type hints
- 添加详细注释
- 包含错误处理
"""
        }

        # 获取对应的模板，如果没有则使用通用模板
        if analysis_type in templates:
            return templates[analysis_type]
        else:
            # 通用模板
            return f"""
请生成Python代码，进行流域 {basin_id} 的 {analysis_type} 分析。

具体要求：
1. 从率定结果目录读取必要的数据
2. 进行 {analysis_type} 相关的计算和分析
3. 如果适用，生成可视化图表
4. 将结果保存到文件（CSV或图片）
5. 打印清晰的分析结果

数据源：
- 从 workspace_dir 中的 calibration_results.json 或 NetCDF 文件读取
- 使用 {model_name} 模型的输出结果

🔧 **CRITICAL: matplotlib 中文显示配置**
如果使用 matplotlib 绘图，必须在导入后立即添加：
```python
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
```

代码要求：
- 使用 type hints
- 添加详细注释
- 包含错误处理
- 打印进度信息
"""

    def _scan_output_files(self) -> list[str]:
        """
        扫描生成的输出文件。
        Scan generated output files.

        Returns:
            输出文件路径列表
        """
        output_files = []
        if self.workspace_dir:
            workspace_path = Path(self.workspace_dir)
            for ext in ['.csv', '.png', '.pdf', '.json', '.txt']:
                output_files.extend(
                    [str(f) for f in workspace_path.glob(f'*{ext}')]
                )
        return output_files

    def _analyze_execution_error(
        self,
        error_message: str,
        code_content: str,
        execution_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        分析代码执行错误并提供修复建议（v4.0）。
        Analyze code execution error and provide fix suggestions.

        Args:
            error_message: 错误信息（stderr）
            code_content: 原始代码内容
            execution_context: 执行上下文（参数、数据路径等）

        Returns:
            错误分析结果
            {
                "error_type": str,  # import_error, runtime_error, data_error, etc.
                "root_cause": str,  # 根本原因
                "fix_suggestions": List[str],  # 修复建议
                "needs_config_update": bool,  # 是否需要更新config
                "needs_code_regeneration": bool  # 是否需要重新生成代码
            }
        """
        logger.info("[RunnerAgent] 分析执行错误...")

        analysis = {
            "error_type": "unknown",
            "root_cause": "",
            "fix_suggestions": [],
            "needs_config_update": False,
            "needs_code_regeneration": False
        }

        error_lower = error_message.lower()

        # 1. 导入错误
        if "importerror" in error_lower or "modulenotfounderror" in error_lower:
            analysis["error_type"] = "import_error"
            analysis["root_cause"] = "缺少必要的Python库"
            analysis["fix_suggestions"].append("安装缺失的依赖包")
            analysis["needs_code_regeneration"] = True

        # 2. 文件未找到错误
        elif "filenotfounderror" in error_lower or "no such file" in error_lower:
            analysis["error_type"] = "data_error"
            analysis["root_cause"] = "数据文件路径不正确或文件不存在"
            analysis["fix_suggestions"].append("检查数据文件路径")
            analysis["fix_suggestions"].append("确认calibration已完成并生成了结果文件")
            analysis["needs_config_update"] = True  # 可能需要更新数据路径

        # 3. KeyError / IndexError
        elif "keyerror" in error_lower or "indexerror" in error_lower:
            analysis["error_type"] = "data_structure_error"
            analysis["root_cause"] = "数据结构不匹配或字段缺失"
            analysis["fix_suggestions"].append("检查数据文件格式")
            analysis["fix_suggestions"].append("更新代码以适配实际数据结构")
            analysis["needs_code_regeneration"] = True

        # 4. ValueError / TypeError
        elif "valueerror" in error_lower or "typeerror" in error_lower:
            analysis["error_type"] = "runtime_error"
            analysis["root_cause"] = "数据类型或值不符合预期"
            analysis["fix_suggestions"].append("检查输入数据的类型和范围")
            analysis["fix_suggestions"].append("添加数据验证和类型转换")
            analysis["needs_code_regeneration"] = True

        # 5. 其他运行时错误
        else:
            analysis["error_type"] = "general_runtime_error"
            analysis["root_cause"] = "代码执行过程中发生未预期的错误"
            analysis["fix_suggestions"].append("检查完整的错误堆栈信息")
            analysis["fix_suggestions"].append("可能需要重新生成代码")
            analysis["needs_code_regeneration"] = True

        logger.info(f"[RunnerAgent] 错误类型: {analysis['error_type']}")
        logger.info(f"[RunnerAgent] 根本原因: {analysis['root_cause']}")

        return analysis

    def _generate_code_with_feedback(
        self,
        analysis_type: str,
        params: Dict[str, Any],
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        带错误反馈的代码生成（v4.0增强）。
        Code generation with error feedback loop.

        流程：
        1. 生成代码
        2. 尝试执行
        3. 如果失败，分析错误
        4. 根据错误类型决定：
           - 重新生成代码（附带错误信息）
           - 更新参数
           - 或放弃并返回错误
        5. 循环直到成功或达到最大重试次数

        Args:
            analysis_type: 分析类型
            params: 参数字典
            max_retries: 最大重试次数

        Returns:
            生成和执行结果
        """
        logger.info(f"[RunnerAgent] 开始代码生成（带错误反馈），最大重试{max_retries}次")

        error_history = []  # 记录错误历史

        for attempt in range(1, max_retries + 1):
            logger.info(f"[RunnerAgent] 尝试 {attempt}/{max_retries}")

            # 1. 生成代码（第一次用原始prompt，后续附带错误信息）
            if attempt == 1:
                # 初次生成
                code_result = self._generate_analysis_code(analysis_type, params)
            else:
                # 重新生成，附带错误信息
                last_error = error_history[-1]
                enhanced_params = params.copy()
                enhanced_params["previous_error"] = last_error["error_message"]
                enhanced_params["error_analysis"] = last_error["analysis"]
                enhanced_params["retry_attempt"] = attempt

                code_result = self._generate_analysis_code(analysis_type, enhanced_params)

            if "error" in code_result:
                logger.error(f"[RunnerAgent] 代码生成失败: {code_result['error']}")
                return {
                    "status": "code_generation_failed",
                    "error": code_result["error"],
                    "attempt": attempt
                }

            code_file = code_result["code_file"]
            code_content = code_result["code"]

            # 2. 执行代码
            exec_result = self._execute_generated_code(code_file)

            # 3. 检查执行结果
            if exec_result.get("status") == "success":
                logger.info(f"[RunnerAgent] 代码执行成功（尝试 {attempt}/{max_retries}）")
                return {
                    "status": "success",
                    "code_file": code_file,
                    "code": code_content,
                    "execution_result": exec_result,
                    "attempts": attempt,
                    "error_history": error_history
                }

            # 4. 执行失败，分析错误
            error_msg = exec_result.get("error", "") or exec_result.get("stderr", "")
            logger.warning(f"[RunnerAgent] 代码执行失败（尝试 {attempt}/{max_retries}）")

            error_analysis = self._analyze_execution_error(
                error_message=error_msg,
                code_content=code_content,
                execution_context=params
            )

            error_history.append({
                "attempt": attempt,
                "error_message": error_msg,
                "analysis": error_analysis,
                "code_file": code_file
            })

            # 5. 决定是否继续重试
            if not error_analysis["needs_code_regeneration"] and not error_analysis["needs_config_update"]:
                # 不可恢复的错误，立即停止
                logger.error("[RunnerAgent] 检测到不可恢复的错误，停止重试")
                break

            logger.info(f"[RunnerAgent] 错误可能可修复，准备重试...")

        # 所有重试都失败
        logger.error(f"[RunnerAgent] 代码生成和执行在{max_retries}次尝试后仍然失败")
        return {
            "status": "failed_after_retries",
            "error": "代码执行在多次重试后仍然失败",
            "error_history": error_history,
            "attempts": max_retries,
            "last_error": error_history[-1] if error_history else {}
        }

    # ========================================================================
    #   v4.0: 自动迭代率定方法
    # ========================================================================

    def _run_auto_iterative_calibration(
        self,
        config: Dict[str, Any],
        parameters: Dict[str, Any]
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
                    iteration_history.append({
                        "iteration": iteration + 1,
                        "status": "failed",
                        "error": result.get("error", "Unknown error")
                    })
                    break

                # 获取NSE
                nse = result.get("metrics", {}).get("NSE", 0.0)
                calibration_dir = result.get("calibration_dir")

                logger.info(f"📊 Iteration {iteration + 1} NSE: {nse:.4f}")

                # 记录历史
                iteration_history.append({
                    "iteration": iteration + 1,
                    "nse": nse,
                    "calibration_dir": calibration_dir,
                    "metrics": result.get("metrics", {}),
                    "status": "completed"
                })

                # 判断是否达标
                if nse >= nse_threshold:
                    logger.info(f"🎉 NSE达标！({nse:.4f} >= {nse_threshold})")
                    converged = True
                    break
                else:
                    logger.info(f"⚠️  NSE未达标 ({nse:.4f} < {nse_threshold})，继续下一轮...")

            except Exception as e:
                logger.error(f"❌ Iteration {iteration + 1} error: {str(e)}", exc_info=True)
                iteration_history.append({
                    "iteration": iteration + 1,
                    "status": "error",
                    "error": str(e)
                })
                break

        # 汇总结果
        if converged:
            status = "converged"
            message = f"Successfully converged after {len(iteration_history)} iterations"
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
            "message": message
        }
