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
        执行 hydromodel 工作流。
        Execute hydromodel workflow.

        Args:
            input_data: 执行配置 Execution configuration
                {
                    "success": True,
                    "config": {...},  # ConfigAgent生成的配置dict
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
        # 从ConfigAgent的输出中提取config
        if "config" in input_data:
            config = input_data["config"]
        else:
            logger.error("[RunnerAgent] No config found in input_data")
            return {
                "success": False,
                "error": "Missing 'config' in input_data"
            }

        # 推断执行模式（从intent或config中）
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

        logger.info(f"[RunnerAgent] 开始执行 {mode} 模式")
        logger.info(f"[RunnerAgent] 模型: {config.get('model_cfgs', {}).get('model_name', 'N/A')}")
        logger.info(f"[RunnerAgent] 流域: {config.get('data_cfgs', {}).get('basin_ids', [])}")

        try:
            if mode == "calibrate":
                result = self._run_calibration(config)
            elif mode == "evaluate":
                result = self._run_evaluation(config)
            elif mode == "simulate":
                result = self._run_simulation(config)
            else:
                raise ValueError(f"未知的执行模式: {mode}")

            logger.info(f"[RunnerAgent] 执行成功完成")

            return {
                "success": True,
                "mode": mode,
                "result": result,
                "execution_log": self.last_execution_log
            }

        except Exception as e:
            logger.error(f"[RunnerAgent] 执行失败: {str(e)}", exc_info=True)

            return {
                "success": False,
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
