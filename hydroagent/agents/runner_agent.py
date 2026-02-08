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

from typing import Dict, Any, Optional, List
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
from ..utils.iterative_plotting import create_iterative_calibration_plots

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
        use_tool_system: Optional[bool] = None,  # 🆕 Phase 1: Tool System
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
            use_tool_system: 🆕 Phase 1: Whether to use tool system (default: read from config)
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

        # 🆕 Phase 1: Tool System Integration
        # Determine if tool system should be used
        # Priority: explicit parameter > config.USE_TOOL_SYSTEM > default False
        if use_tool_system is None:
            try:
                from configs import config as global_config
                use_tool_system = getattr(global_config, 'USE_TOOL_SYSTEM', False)
            except ImportError:
                use_tool_system = False

        self.use_tool_system = use_tool_system

        if self.use_tool_system:
            # Initialize tool executor and register tools
            from hydroagent.tools.executor import ToolExecutor
            from hydroagent.tools.registry import registry
            from hydroagent.tools.validation_tool import DataValidationTool
            from hydroagent.tools.calibration_tool import CalibrationTool
            from hydroagent.tools.evaluation_tool import EvaluationTool
            from hydroagent.tools.visualization_tool import VisualizationTool
            from hydroagent.tools.code_generation_tool import CodeGenerationTool
            from hydroagent.tools.custom_analysis_tool import CustomAnalysisTool
            from hydroagent.tools.simulation_tool import SimulationTool

            self.tool_executor = ToolExecutor(registry)

            # Register core tools
            registry.register(DataValidationTool())
            registry.register(CalibrationTool())
            registry.register(EvaluationTool())
            registry.register(SimulationTool())  # Phase 2: Simulation tool
            registry.register(VisualizationTool())

            # Register analysis tools (实验4)
            # Use code_llm for code generation, fallback to general llm if not available
            registry.register(CodeGenerationTool(llm_interface=self.code_llm or llm_interface))
            registry.register(CustomAnalysisTool(llm_interface=self.code_llm or llm_interface, tool_registry=registry))

            logger.info(
                f"[RunnerAgent v5.0] Tool system ENABLED - {len(registry)} tools registered"
            )
        else:
            self.tool_executor = None
            logger.info("[RunnerAgent v5.0] Tool system DISABLED - using legacy mode")

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
        # ✅ v6.0: All tasks use tool system (Legacy mode removed)
        logger.info("[RunnerAgent v6.0] Executing via tool system")
        return self._process_with_tools(input_data)

    # ========================================================================

    # ========================================================================
    # ❌ v6.0: Legacy execution methods REMOVED (~1600 lines deleted)
    # All tasks now use _process_with_tools() - unified tool chain execution
    # Removed methods:
    #   - _process_legacy_DEPRECATED()
    #   - _run_calibration_DEPRECATED()
    #   - _run_evaluation_DEPRECATED()
    #   - _run_simulation_DEPRECATED()
    #   - _run_boundary_check_recalibration_DEPRECATED()
    #   - _run_statistical_analysis_DEPRECATED()
    #   - _run_custom_analysis_DEPRECATED()
    #   - _run_auto_iterative_calibration_DEPRECATED()
    # See git history for removed code
    # ========================================================================

    def _process_with_tools(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process execution using tool system with execution modes support.
        使用工具系统执行（支持执行模式）。

        Supported execution modes:
        - simple: 一次性执行工具链
        - iterative: 循环执行工具链直到NSE达标（实验3）
        - repeated: 重复执行工具链N次（实验5）

        Args:
            input_data: Input containing tool_chain, execution_mode, and mode_params
                Expected format from TaskPlanner:
                {
                    "tool_chain": [...],
                    "execution_mode": "simple" | "iterative" | "repeated",
                    "mode_params": {...},
                    "task_type": "calibration",
                    ...
                }

        Returns:
            Dict: Execution results from tool chain
        """
        logger.info("[RunnerAgent] Executing with tool system")

        # Extract parameters
        tool_chain = input_data.get("tool_chain", [])
        execution_mode = input_data.get("execution_mode", "simple")
        mode_params = input_data.get("mode_params", {})

        if not tool_chain:
            # ❌ v6.0: No Legacy fallback - all tasks must use tool system
            logger.error("[RunnerAgent v6.0] No tool_chain found in input_data - all tasks must use tool system")
            return {
                "success": False,
                "error": "No tool_chain found - v6.0 requires tool system execution",
                "output": {},
                "error_type": "MISSING_TOOL_CHAIN"
            }

        logger.info(f"[RunnerAgent] Tool chain has {len(tool_chain)} steps, execution_mode={execution_mode}")

        # Route to appropriate execution mode
        try:
            if execution_mode == "iterative":
                return self._execute_iterative_mode(tool_chain, mode_params, input_data)
            elif execution_mode == "repeated":
                return self._execute_repeated_mode(tool_chain, mode_params, input_data)
            else:  # simple mode
                return self._execute_simple_mode(tool_chain, input_data)

        except Exception as e:
            logger.error(f"[RunnerAgent] Tool chain execution failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Tool chain execution error: {str(e)}",
                "execution_mode": execution_mode
            }

    def _execute_simple_mode(
        self,
        tool_chain: List[Dict[str, Any]],
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute tool chain once (simple mode).
        一次性执行工具链。

        Args:
            tool_chain: Tool chain to execute
            input_data: Full input data

        Returns:
            Dict: Execution results
        """
        logger.info("[RunnerAgent] Executing in SIMPLE mode")

        # Inject workspace_dir into validate_data tool's inputs
        if self.workspace_dir:
            for tool_step in tool_chain:
                if tool_step.get("tool") == "validate_data":
                    if "inputs" not in tool_step:
                        tool_step["inputs"] = {}
                    tool_step["inputs"]["output_dir"] = str(self.workspace_dir)
                    logger.debug(f"[RunnerAgent] Injected output_dir={self.workspace_dir} to validate_data")

        # Inject additional parameters into custom_analysis tool
        for tool_step in tool_chain:
            if tool_step.get("tool") == "custom_analysis":
                if "inputs" not in tool_step:
                    tool_step["inputs"] = {}
                # Inject workspace_dir
                if self.workspace_dir:
                    tool_step["inputs"]["workspace_dir"] = str(self.workspace_dir)
                # Inject user_question (from intent_result)
                intent_result = input_data.get("intent_result", {})
                user_question = intent_result.get("original_query") or input_data.get("query", "")
                if user_question:
                    tool_step["inputs"]["user_question"] = user_question
                logger.debug(f"[RunnerAgent] Injected workspace_dir and user_question to custom_analysis")

        results = self.tool_executor.execute_chain(
            tool_chain=tool_chain,
            stop_on_error=True
        )

        return self._aggregate_results(results, tool_chain, execution_mode="simple")

    def _execute_iterative_mode(
        self,
        tool_chain: List[Dict[str, Any]],
        mode_params: Dict[str, Any],
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute tool chain iteratively with parameter range adjustment (实验3).
        迭代执行工具链，自动调整参数范围。

        Workflow:
        1. 率定 → 评估
        2. 检查NSE是否达标
        3. 如果不达标且参数在边界，调整参数范围（使用utils）
        4. 重复1-3直到达标或达到最大迭代次数

        Args:
            tool_chain: Tool chain to execute (should contain calibrate + evaluate)
            mode_params: Iteration parameters (max_iterations, nse_threshold, etc.)
            input_data: Full input data

        Returns:
            Dict: Execution results with iteration history
        """
        logger.info("[RunnerAgent] Executing in ITERATIVE mode")

        max_iterations = mode_params.get("max_iterations", 5)
        nse_threshold = mode_params.get("nse_threshold", 0.65)
        boundary_threshold = mode_params.get("boundary_threshold", 0.05)
        min_nse_improvement = mode_params.get("min_nse_improvement", 0.01)

        iteration_history = []
        previous_nse = None

        # Track previous calibration_dir for param range adjustment
        prev_calibration_dir = None

        # Track adjusted param_range for next iteration
        self._prev_adjusted_param_range = None

        for iteration in range(1, max_iterations + 1):
            logger.info(f"[RunnerAgent] === Iteration {iteration}/{max_iterations} ===")

            # 🔧 为每次迭代设置独立的calibration_dir
            # 例如：auto_iterative_calibration_1, auto_iterative_calibration_2, ...
            if self.workspace_dir:
                iteration_dir = self.workspace_dir / f"iteration_{iteration}"
                iteration_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"[RunnerAgent] Iteration {iteration} output dir: {iteration_dir}")
            else:
                iteration_dir = None

            # Inject workspace_dir into validate_data tool's inputs (first iteration only)
            if iteration == 1 and self.workspace_dir:
                for tool_step in tool_chain:
                    if tool_step.get("tool") == "validate_data":
                        if "inputs" not in tool_step:
                            tool_step["inputs"] = {}
                        tool_step["inputs"]["output_dir"] = str(self.workspace_dir)
                        logger.debug(f"[RunnerAgent] Injected output_dir={self.workspace_dir} to validate_data")

            # 🔧 更新calibrate工具的config（设置独立的output_dir和调整后的param_range）
            for tool_step in tool_chain:
                if tool_step.get("tool") == "calibrate":
                    if "inputs" not in tool_step:
                        tool_step["inputs"] = {}

                    # 获取或创建config
                    if "config" not in tool_step["inputs"]:
                        tool_step["inputs"]["config"] = {}

                    config = tool_step["inputs"]["config"]

                    # 设置独立的output_dir
                    if iteration_dir:
                        if "training_cfgs" not in config:
                            config["training_cfgs"] = {}
                        config["training_cfgs"]["output_dir"] = str(iteration_dir)
                        logger.info(f"[RunnerAgent] Set calibration output_dir: {iteration_dir}")

                    # 🔧 CRITICAL: Iteration 2+需要使用上一次调整后的param_range
                    # 解决方案: 使用param_range_file而非model_cfgs.param_range
                    # hydromodel的param_range读取优先级: param_range_file > model_cfgs.param_range
                    if iteration_dir and iteration > 1:
                        # 从prev_adjusted_param_range获取调整后的范围（在上次迭代结束时保存）
                        if hasattr(self, '_prev_adjusted_param_range') and self._prev_adjusted_param_range:
                            logger.info(f"[RunnerAgent] 使用调整后的param_range: {self._prev_adjusted_param_range}")

                            # ⭐ 方案1: 保存adjusted_param_range到YAML文件，通过param_range_file传递给hydromodel
                            import yaml
                            model_name = config.get("model_cfgs", {}).get("model_name", "gr4j")
                            param_range_input_file = iteration_dir / "param_range_input.yaml"

                            # 构建hydromodel期望的YAML格式
                            param_range_data = {
                                model_name: {
                                    "param_name": list(self._prev_adjusted_param_range.keys()),
                                    "param_range": self._prev_adjusted_param_range
                                }
                            }

                            with open(param_range_input_file, "w") as f:
                                yaml.dump(param_range_data, f, default_flow_style=False)

                            logger.info(f"[RunnerAgent] ✓ 已保存param_range到: {param_range_input_file}")

                            # 设置param_range_file路径（这是hydromodel的首选方式）
                            if "training_cfgs" not in config:
                                config["training_cfgs"] = {}
                            config["training_cfgs"]["param_range_file"] = str(param_range_input_file)

                            # ⭐ 关键修复: 改变random_seed以探索不同的搜索路径
                            # random_seed需要设置在algorithm_params中，hydromodel才会使用
                            if "algorithm_params" not in config["training_cfgs"]:
                                config["training_cfgs"]["algorithm_params"] = {}

                            # 获取基础seed并递增
                            base_seed = config["training_cfgs"]["algorithm_params"].get("random_seed", 1234)
                            if base_seed == 1234:  # 如果是默认值，可能没有在algorithm_params中
                                base_seed = config["training_cfgs"].get("random_seed", 1234)

                            new_seed = base_seed + iteration - 1
                            config["training_cfgs"]["algorithm_params"]["random_seed"] = new_seed

                            logger.info(f"[RunnerAgent] ✓ 已设置param_range_file: {param_range_input_file}")
                            logger.info(f"[RunnerAgent] ✓ 已更新algorithm_params.random_seed: {new_seed} (base={base_seed}, iteration={iteration})")
                        else:
                            logger.warning(f"[RunnerAgent] Iteration {iteration} but no previous adjusted param_range found")

            # Execute tool chain
            results = self.tool_executor.execute_chain(
                tool_chain=tool_chain,
                stop_on_error=True
            )

            # 🔧 提取calibration_dir用于下次迭代的参数范围调整
            current_calibration_dir = None
            for result in results:
                if result.success and "calibration_dir" in result.data:
                    current_calibration_dir = result.data["calibration_dir"]
                    logger.info(f"[RunnerAgent] Extracted calibration_dir: {current_calibration_dir}")
                    break

            # Extract NSE from evaluation result
            current_nse = None
            for result in reversed(results):
                if result.success and "metrics" in result.data:
                    metrics = result.data["metrics"]
                    if isinstance(metrics, dict) and "NSE" in metrics:
                        current_nse = metrics["NSE"]
                    break

            if current_nse is None:
                logger.warning(f"[RunnerAgent] Cannot extract NSE from iteration {iteration}")
                break

            logger.info(f"[RunnerAgent] Iteration {iteration}: NSE={current_nse:.4f}")

            # Record iteration
            iteration_history.append({
                "iteration": iteration,
                "iteration_dir": str(iteration_dir) if iteration_dir else None,
                "nse": current_nse,
                "results": [r.to_dict() for r in results]
            })

            # Check stopping conditions
            # Condition 1: NSE达标
            if current_nse >= nse_threshold:
                logger.info(f"[RunnerAgent] ✓ NSE达标 ({current_nse:.4f} >= {nse_threshold}), 停止迭代")
                break

            # Condition 2: NSE改善但幅度不足
            # 注意：只有当NSE确实改善（improvement > 0）但幅度太小时才停止
            # 如果NSE变差（improvement < 0），应该继续迭代，因为可能是随机性
            if previous_nse is not None:
                improvement = current_nse - previous_nse
                if 0 < improvement < min_nse_improvement:
                    # NSE有改善但幅度太小
                    logger.info(f"[RunnerAgent] NSE改善幅度不足 ({improvement:.4f} < {min_nse_improvement}), 停止迭代")
                    break
                elif improvement <= 0:
                    # NSE变差或无变化，记录但继续迭代
                    logger.info(f"[RunnerAgent] NSE变差或无改善 ({improvement:.4f}), 继续尝试下一次迭代")

            # Condition 3: 达到最大迭代次数
            if iteration >= max_iterations:
                logger.info(f"[RunnerAgent] 达到最大迭代次数 ({max_iterations}), 停止迭代")
                break

            # 🔧 调用已有的参数范围调整工具
            logger.info(f"[RunnerAgent] NSE未达标，准备调整参数范围...")

            if current_calibration_dir:
                try:
                    from hydroagent.utils.param_range_adjuster import adjust_from_previous_calibration

                    # 调用参数范围调整工具
                    adjustment_result = adjust_from_previous_calibration(
                        prev_calibration_dir=current_calibration_dir,
                        range_scale=0.6,  # 默认缩小到60%
                        boundary_threshold=boundary_threshold,
                        boundary_expand_factor=1.5,  # 边界扩展1.5倍
                        smart_adjustment=True  # 启用智能调整
                    )

                    if adjustment_result.get("success"):
                        new_param_range = adjustment_result.get("new_param_range", {})
                        logger.info(f"[RunnerAgent] ✓ 参数范围调整成功")
                        logger.info(f"[RunnerAgent] 调整后的参数范围: {new_param_range}")

                        # 🔧 保存调整后的param_range到实例变量
                        # 下次迭代开始时会从这里读取并注入到config
                        self._prev_adjusted_param_range = new_param_range
                        logger.info(f"[RunnerAgent] ✓ 已保存调整后的param_range到_prev_adjusted_param_range")
                    else:
                        logger.warning(f"[RunnerAgent] 参数范围调整失败: {adjustment_result.get('message', 'Unknown error')}")

                except Exception as e:
                    logger.error(f"[RunnerAgent] 调用param_range_adjuster失败: {e}", exc_info=True)
            else:
                logger.warning(f"[RunnerAgent] 未能提取calibration_dir，无法调整参数范围")

            # 保存当前calibration_dir供下次迭代使用
            prev_calibration_dir = current_calibration_dir
            previous_nse = current_nse

        # Return aggregated results with iteration history
        final_results = iteration_history[-1]["results"] if iteration_history else []
        aggregated = self._aggregate_results(
            [r for r in results],  # Use last iteration results
            tool_chain,
            execution_mode="iterative"
        )
        aggregated["iteration_history"] = iteration_history
        aggregated["total_iterations"] = len(iteration_history)

        # 🎨 Create visualization plots for iterative calibration
        try:
            logger.info("[RunnerAgent] Creating visualization plots for iterative calibration...")

            # Get workspace directory (parent of iteration_1, iteration_2, etc.)
            if iteration_history and len(iteration_history) > 0:
                first_iter_dir = iteration_history[0].get("iteration_dir")
                if first_iter_dir:
                    workspace_dir = Path(first_iter_dir).parent
                    model_name = config.get("model_cfgs", {}).get("model_name", "gr4j")

                    # Extract target_nse from mode_params
                    target_nse = mode_params.get("target_nse")

                    # Create plots
                    plot_results = create_iterative_calibration_plots(
                        workspace_dir=workspace_dir,
                        model_name=model_name,
                        target_nse=target_nse
                    )

                    logger.info(f"[RunnerAgent] ✓ Visualization plots created: {plot_results}")
                    aggregated["visualization_plots"] = plot_results
                else:
                    logger.warning("[RunnerAgent] No iteration_dir found in iteration_history")
            else:
                logger.warning("[RunnerAgent] No iteration_history available for visualization")

        except Exception as e:
            logger.error(f"[RunnerAgent] Failed to create visualization plots: {e}", exc_info=True)
            # Don't fail the entire process if visualization fails
            aggregated["visualization_plots"] = {"error": str(e)}

        return aggregated

    def _execute_repeated_mode(
        self,
        tool_chain: List[Dict[str, Any]],
        mode_params: Dict[str, Any],
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute tool chain repeatedly N times (实验5).
        重复执行工具链N次（稳定性验证）。

        Workflow:
        1. 重复执行工具链N次
        2. 收集所有结果
        3. 后处理分析由DeveloperAgent完成（不在此处）

        Args:
            tool_chain: Tool chain to execute
            mode_params: Repetition parameters (repeat_times)
            input_data: Full input data

        Returns:
            Dict: Execution results with repetition history
        """
        logger.info("[RunnerAgent] Executing in REPEATED mode")

        repeat_times = mode_params.get("repeat_times", 5)
        repetition_history = []

        for repetition in range(1, repeat_times + 1):
            logger.info(f"[RunnerAgent] === Repetition {repetition}/{repeat_times} ===")

            # Inject workspace_dir into validate_data tool's inputs (first repetition only)
            if repetition == 1 and self.workspace_dir:
                for tool_step in tool_chain:
                    if tool_step.get("tool") == "validate_data":
                        if "inputs" not in tool_step:
                            tool_step["inputs"] = {}
                        tool_step["inputs"]["output_dir"] = str(self.workspace_dir)
                        logger.debug(f"[RunnerAgent] Injected output_dir={self.workspace_dir} to validate_data")

            # Execute tool chain
            results = self.tool_executor.execute_chain(
                tool_chain=tool_chain,
                stop_on_error=True
            )

            # Record repetition
            repetition_history.append({
                "repetition": repetition,
                "results": [r.to_dict() for r in results],
                "success": all(r.success for r in results)
            })

        # Return aggregated results with repetition history
        aggregated = self._aggregate_results(
            results,  # Use last repetition results
            tool_chain,
            execution_mode="repeated"
        )
        aggregated["repetition_history"] = repetition_history
        aggregated["total_repetitions"] = len(repetition_history)

        return aggregated

    def _aggregate_results(
        self,
        results: List,
        tool_chain: List[Dict[str, Any]],
        execution_mode: str
    ) -> Dict[str, Any]:
        """
        Aggregate tool execution results into final format.
        聚合工具执行结果。

        Args:
            results: Tool execution results
            tool_chain: Tool chain
            execution_mode: Execution mode

        Returns:
            Dict: Aggregated results
        """
        # Check if all REQUIRED tools succeeded (ignore optional tool failures)
        # A tool is considered required if "required" is True or not specified (default True)
        required_tools_success = all(
            r.success
            for idx, r in enumerate(results)
            if tool_chain[idx].get("required", True)  # Only check required tools
        )

        # Log optional tool failures (informational only)
        optional_failures = [
            tool_chain[idx].get("tool", f"tool_{idx}")
            for idx, r in enumerate(results)
            if not r.success and not tool_chain[idx].get("required", True)
        ]
        if optional_failures:
            logger.info(
                f"[RunnerAgent] Optional tools failed (non-critical): {optional_failures}"
            )

        all_success = required_tools_success

        # Aggregate results by tool name
        aggregated_data = {}
        for idx, result in enumerate(results):
            tool_name = tool_chain[idx].get("tool", f"tool_{idx}")
            aggregated_data[tool_name] = result.data

        # Find the last successful result for key metrics
        final_metrics = {}
        final_output_files = []

        for result in reversed(results):
            if result.success:
                # Extract metrics from evaluation or calibration
                if "metrics" in result.data:
                    final_metrics = result.data["metrics"]
                    break

        # Collect all output files
        for result in results:
            if result.success and "output_files" in result.data:
                final_output_files.extend(result.data["output_files"])
            if result.success and "plot_files" in result.data:
                final_output_files.extend(result.data["plot_files"])
            if result.success and "generated_files" in result.data:
                final_output_files.extend(result.data["generated_files"])

        logger.info(
            f"[RunnerAgent] Tool chain execution completed: "
            f"{sum(1 for r in results if r.success)}/{len(results)} succeeded"
        )

        # Add tool_name to each result for better analysis
        tool_results_with_names = []
        for idx, result in enumerate(results):
            result_dict = result.to_dict()
            result_dict["tool_name"] = tool_chain[idx].get("tool", f"tool_{idx}")
            tool_results_with_names.append(result_dict)

        return {
            "success": all_success,
            "tool_results": tool_results_with_names,
            "aggregated_data": aggregated_data,
            "metrics": final_metrics,
            "output_files": final_output_files,
            "execution_mode": execution_mode
        }
