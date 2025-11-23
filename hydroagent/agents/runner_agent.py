"""
Author: zhuanglaihong
Date: 2025-01-20 19:55:00
LastEditTime: 2025-01-20 19:55:00
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
    """

    def __init__(
        self,
        llm_interface: LLMInterface,
        workspace_dir: Optional[Path] = None,
        timeout: int = 3600,
        show_progress: bool = True,
        **kwargs
    ):
        """
        Initialize RunnerAgent.

        Args:
            llm_interface: LLM API interface
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
        执行 hydromodel 工作流（Phase 3增强：支持新任务类型）。
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

        # 推断执行模式
        if task_type == "boundary_check_recalibration":
            mode = "boundary_check"
        elif task_type == "statistical_analysis":
            mode = "statistical_analysis"
        elif task_type == "custom_analysis":
            mode = "custom_analysis"
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

                # 查找最新的实验目录（通常是按时间戳命名）
                if output_path.exists():
                    experiment_dirs = sorted([d for d in output_path.iterdir() if d.is_dir()],
                                           key=lambda x: x.stat().st_mtime,
                                           reverse=True)

                    if experiment_dirs:
                        calibration_dir = str(experiment_dirs[0])
                        logger.info(f"[RunnerAgent] 找到率定目录: {calibration_dir}")
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
                        logger.warning(f"[RunnerAgent] 输出目录中没有实验目录: {output_path}")
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

            initial_result = self._run_calibration(config)

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
                new_config["model_cfgs"]["param_range_file"] = adjust_result["output_file"]

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
        执行自定义分析代码（实验4）。
        Execute custom analysis code (Experiment 4).

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

        # 自定义分析需要DeveloperAgent生成代码后执行
        # 这里RunnerAgent只是标记需要执行自定义分析
        # 实际的代码生成和执行由DeveloperAgent完成

        return {
            "status": "pending_code_generation",
            "analysis_type": analysis_type,
            "basin_id": basin_id,
            "model_name": model_name,
            "message": "自定义分析需要DeveloperAgent生成代码"
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
                prev_param_range = yaml.safe_load(f)

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
            # 假设第一列是 basin_id 或类似的标识符，其余是参数
            param_columns = [col for col in df.columns if col not in ['basin_id', 'basin', 'id']]
            best_params = {col: param_row[col] for col in param_columns}

            logger.info(f"[RunnerAgent] 最佳参数（反归一化）: {best_params}")

            # 3. 计算新的参数范围
            # 格式: {param_name: [min, max]}
            new_param_range = {}

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

                logger.info(f"[RunnerAgent] 参数 {param_name}:")
                logger.info(f"  原范围: [{prev_min}, {prev_max}] (长度: {prev_length})")
                logger.info(f"  最佳值: {best_value}")
                logger.info(f"  新范围: [{new_min:.4f}, {new_max:.4f}] (长度: {new_max - new_min:.4f})")

            # 4. 保存新的参数范围
            if output_yaml_path is None:
                # 默认保存在当前工作目录
                output_yaml_path = self.workspace_dir / "adjusted_param_range.yaml" if self.workspace_dir else Path("adjusted_param_range.yaml")
            else:
                output_yaml_path = Path(output_yaml_path)

            output_yaml_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_yaml_path, 'w', encoding='utf-8') as f:
                yaml.dump(new_param_range, f, default_flow_style=False, allow_unicode=True)

            logger.info(f"[RunnerAgent] 新参数范围已保存: {output_yaml_path}")

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
