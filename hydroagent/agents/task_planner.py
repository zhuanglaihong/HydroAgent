"""
Author: Claude
Date: 2025-11-22 16:00:00
LastEditTime: 2025-12-03 22:00:00
LastEditors: Claude
Description: Task Planner Agent - v5.0 LLM-driven dynamic task decomposition
             任务规划智能体 - v5.0 LLM驱动的动态任务拆解
FilePath: /HydroAgent/hydroagent/agents/task_planner.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

v5.0 Enhancements:
- LLM-based dynamic task decomposition (no hardcoded rules)
- FAISS-based historical case retrieval
- Automatic prompt generation for InterpreterAgent
- Fallback to rule-based methods if LLM fails
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
from dataclasses import dataclass, asdict
import logging

from ..core.base_agent import BaseAgent
from ..core.llm_interface import LLMInterface
from ..core.prompt_pool import PromptPool

# Import config for iterative optimization defaults
try:
    from configs import config
except ImportError:
    config = None

logger = logging.getLogger(__name__)


@dataclass
class SubTask:
    """
    Represents a single subtask in the task plan.
    表示任务计划中的单个子任务。
    """

    task_id: str  # e.g., "task_1", "task_2a", "task_2b"
    task_type: str  # Type of subtask (calibration, evaluation, etc.)
    description: str  # Human-readable description
    prompt: str  # Complete prompt for InterpreterAgent
    parameters: Dict[str, Any]  # Parameters specific to this subtask
    dependencies: List[str] = None  # List of task_ids this depends on

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class TaskPlanner(BaseAgent):
    """
    Task Planner Agent - Handles tactical task decomposition.
    任务规划智能体 - 处理战术层面的任务拆解。

    Responsibilities (职责):
    1. Decompose high-level tasks based on task_type (基于任务类型拆解高层任务)
    2. Generate prompts for each subtask (为每个子任务生成提示词)
    3. Use PromptPool for historical cases (使用提示词池获取历史案例)
    4. Handle dependencies between subtasks (处理子任务间的依赖关系)
    5. Return structured task plan (返回结构化任务计划)

    Key Design:
    - IntentAgent decides "what to do" (战略决策)
    - TaskPlanner decides "how to do it" (战术决策)
    - Logical complexity handled here, execution in RunnerAgent

    Task Types Supported:
    1. standard_calibration: Single basin, single algorithm
    2. info_completion: Fill missing info, then calibrate
    3. iterative_optimization: Two-phase calibration (Exp 3)
    4. repeated_experiment: Multiple runs with different seeds (Exp 5)
    5. extended_analysis: Calibration + custom analysis (Exp 4)
    6. batch_processing: Multiple basins/algorithms/models
    7. custom_data: Use custom data path
    """

    def __init__(
        self,
        llm_interface: LLMInterface,
        prompt_pool: Optional[PromptPool] = None,
        workspace_dir: Optional[Path] = None,
        use_llm_planning: bool = True,  # 🆕 v5.0
        use_tool_system: Optional[bool] = None,  # 🆕 Phase 1: Tool System
        **kwargs,
    ):
        """
        Initialize TaskPlanner (v5.0 with LLM planning).

        Args:
            llm_interface: LLM API interface
            prompt_pool: PromptPool instance for historical cases
            workspace_dir: Working directory for results
            use_llm_planning: 🆕 v5.0 Whether to use LLM for dynamic planning (default: True)
            use_tool_system: 🆕 Phase 1: Whether to use tool system (default: read from config)
            **kwargs: Additional configuration
        """
        super().__init__(
            name="TaskPlanner",
            llm_interface=llm_interface,
            workspace_dir=workspace_dir,
            **kwargs,
        )

        # 🆕 v5.0: LLM planning flag
        self.use_llm_planning = use_llm_planning

        # Initialize PromptPool
        self.prompt_pool = prompt_pool or PromptPool(
            pool_dir=workspace_dir / "prompt_pool" if workspace_dir else None
        )

        # 🆕 v5.0: Task decomposition mapping (kept as fallback)
        self.decomposition_methods = {
            "standard_calibration": self._decompose_standard_calibration,
            "info_completion": self._decompose_info_completion,
            "iterative_optimization": self._decompose_iterative_optimization,
            "repeated_experiment": self._decompose_repeated_experiment,
            "extended_analysis": self._decompose_extended_analysis,
            "batch_processing": self._decompose_batch_processing,
            "custom_data": self._decompose_custom_data,
            "auto_iterative_calibration": self._decompose_auto_iterative_calibration,
        }

        # 🆕 Phase 1: Tool Orchestrator Integration
        # Check if tool system is enabled (parameter takes priority over config)
        if use_tool_system is None:
            try:
                from configs import config as global_config
                use_tool_system = getattr(global_config, 'USE_TOOL_SYSTEM', False)
            except ImportError:
                use_tool_system = False

        self.use_tool_system = use_tool_system

        if self.use_tool_system:
            from hydroagent.agents.tool_orchestrator import ToolOrchestrator
            self.orchestrator = ToolOrchestrator(llm_interface=self.llm)
            logger.info("[TaskPlanner v5.0] Tool orchestrator ENABLED with LLM support")
        else:
            self.orchestrator = None
            logger.info("[TaskPlanner v5.0] Tool orchestrator DISABLED - using legacy decomposition")

        logger.info(
            f"[TaskPlanner v5.0] Initialized with LLM planning={'enabled' if use_llm_planning else 'disabled'}"
        )

    def _get_default_system_prompt(self) -> str:
        """Return default system prompt for TaskPlanner."""
        return """You are the Task Planner of HydroAgent.

Your role is to decompose high-level tasks into concrete, executable subtasks.

Key responsibilities:
1. Break down complex tasks into simple, sequential steps
2. Generate clear prompts for each subtask
3. Identify dependencies between subtasks
4. Leverage historical successful cases
5. Handle variable combinations and logical dependencies

Always create structured, actionable task plans."""

    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        🆕 v6.0: All tasks use tool system (Legacy mode removed).
        所有任务都使用工具系统（Legacy模式已移除）。

        Args:
            input_data: Intent result from IntentAgent
                {
                    "intent_result": {
                        "task_type": "iterative_optimization",
                        "model_name": "gr4j",
                        "basin_id": "01013500",
                        ...
                    },
                    "error_log": "..."  # Optional: error from previous attempt
                }

        Returns:
            Dict containing:
                {
                    "success": True,
                    "tool_chain": [...],  # Tool execution sequence
                    "execution_mode": "simple|iterative|repeated",
                    "mode_params": {...}
                }
                或 (多模型组合时):
                {
                    "success": True,
                    "task_plan": {
                        "subtasks": [...],  # Multiple tool_chain subtasks
                        "use_tool_chains": True
                    }
                }
        """
        intent_result = input_data.get("intent_result", {})
        task_type = intent_result.get("task_type", "standard_calibration")

        logger.info(f"[TaskPlanner v6.0] Processing task: {task_type} (tool system only)")

        # ✅ v6.0: All tasks use tool system
        return self._process_with_tools(intent_result, task_type)

    # ========================================================================
    # ⚠️ DEPRECATED (v6.0): Legacy decomposition methods no longer used
    # All tasks now use tool chains, not subtask-based decomposition
    # Kept for reference, may be removed in future versions
    # ========================================================================

    def _decompose_task(self, intent_result: Dict[str, Any]) -> List[SubTask]:
        """
        🆕 v5.0: Decompose task using LLM or fallback to rule-based.
        使用 LLM 动态拆解或回退到规则方法。

        Args:
            intent_result: Intent analysis result with task_type

        Returns:
            List of SubTask objects
        """
        task_type = intent_result.get("task_type", "standard_calibration")

        # ⭐ OPTIMIZATION: Skip LLM for simple standard tasks (faster performance)
        # batch_processing added: LLM struggles with multi-basin decomposition
        simple_tasks = {"standard_calibration", "info_completion", "custom_data", "batch_processing"}
        force_rule_based = task_type in simple_tasks

        if force_rule_based:
            logger.info(f"[TaskPlanner] Using optimized rule-based decomposition for simple task: {task_type}")
            decomposition_method = self.decomposition_methods.get(task_type, self._decompose_standard_calibration)
            return decomposition_method(intent_result)

        # 🆕 v5.0: Try LLM-based decomposition for complex tasks
        if self.use_llm_planning:
            try:
                logger.info(f"[TaskPlanner v5.0] Using LLM for task decomposition: {task_type}")
                subtasks = self._decompose_task_with_llm(intent_result)

                if subtasks:
                    logger.info(f"[TaskPlanner v5.0] LLM generated {len(subtasks)} subtasks")
                    return subtasks
                else:
                    logger.warning("[TaskPlanner v5.0] LLM returned no subtasks, falling back to rules")

            except Exception as e:
                logger.warning(
                    f"[TaskPlanner v5.0] LLM decomposition failed: {str(e)}, falling back to rules"
                )

        # Fallback to rule-based decomposition
        logger.info(f"[TaskPlanner] Using rule-based decomposition for: {task_type}")
        decomposition_method = self.decomposition_methods.get(task_type)

        if not decomposition_method:
            logger.warning(
                f"[TaskPlanner] Unknown task_type: {task_type}, using standard"
            )
            decomposition_method = self._decompose_standard_calibration

        return decomposition_method(intent_result)

    # ========================================================================
    # Task-Specific Decomposition Methods
    # ========================================================================

    def _extract_time_periods(self, intent: Dict[str, Any]) -> tuple:
        """
        Extract train_period and test_period from intent.
        从intent中提取train_period和test_period。

        IntentAgent fills time_period as: {"train": [...], "test": [...]}
        We need to split it into separate fields for InterpreterAgent.

        Args:
            intent: Intent result dictionary

        Returns:
            Tuple of (train_period, test_period)
        """
        time_period = intent.get("time_period", {})
        if isinstance(time_period, dict):
            return time_period.get("train"), time_period.get("test")
        return None, None

    def _decompose_standard_calibration(self, intent: Dict[str, Any]) -> List[SubTask]:
        """
        实验1：标准单任务率定
        Decompose standard calibration task.

        Flow: Calibration → Evaluation (single task)
        """
        train_period, test_period = self._extract_time_periods(intent)

        subtasks = [
            SubTask(
                task_id="task_1",
                task_type="calibration",
                description=f"Calibrate {intent.get('model_name', 'model')} on basins {intent.get('basin_ids', ['N/A'])}",
                prompt="",  # Will be filled by _generate_subtask_prompt
                parameters={
                    "model_name": intent.get("model_name"),
                    "basin_ids": intent.get("basin_ids"),
                    "algorithm": intent.get("algorithm"),
                    "train_period": train_period,
                    "test_period": test_period,
                    "extra_params": intent.get("extra_params", {}),
                    "auto_evaluate": True,  # Auto-run evaluation after calibration
                },
                dependencies=[],
            )
        ]

        return subtasks

    def _decompose_info_completion(self, intent: Dict[str, Any]) -> List[SubTask]:
        """
        实验2B：缺省信息补全型率定
        Decompose info completion task.

        Flow: Same as standard, but with auto-filled defaults
        Note: IntentAgent already completed missing info
        """
        # Same as standard calibration since IntentAgent filled missing info
        return self._decompose_standard_calibration(intent)

    def _decompose_iterative_optimization(
        self, intent: Dict[str, Any]
    ) -> List[SubTask]:
        """
        实验3：迭代优化 (循环式参数范围调整)
        Decompose iterative optimization task.

        ⭐ NEW DESIGN (2025-01-24):
        创建1个循环迭代任务，由RunnerAgent内部完成多轮率定，直到：
        - NSE达到阈值 (default: 0.5)
        - 达到最大轮数 (default: 5)
        - 连续N轮无改善 (default: 2)

        每轮迭代自动调整参数范围：
        - range_scale = initial_scale × (decay_factor ^ iteration)
        - 以上一轮最佳参数为中心
        """
        strategy = intent.get("strategy", {})

        # Get defaults from config.py (or use fallback values)
        max_iterations = getattr(config, "MAX_ITERATIONS", 5) if config else 5
        nse_threshold = (
            getattr(config, "NSE_THRESHOLD_FOR_ITERATION", 0.65) if config else 0.65
        )
        min_nse_improvement = (
            getattr(config, "MIN_NSE_IMPROVEMENT", 0.01) if config else 0.01
        )
        initial_range_scale = (
            getattr(config, "INITIAL_RANGE_SCALE", 0.6) if config else 0.6
        )

        subtasks = [
            SubTask(
                task_id="iterative_boundary_optimization",
                task_type="boundary_check_recalibration",
                description=f"Iterative optimization for {intent.get('basin_ids', ['N/A'])} (internal loop until convergence)",
                prompt="",
                parameters={
                    "model_name": intent.get("model_name"),
                    "basin_ids": intent.get("basin_ids"),
                    "algorithm": intent.get("algorithm"),
                    "time_period": intent.get("time_period"),
                    "extra_params": intent.get("extra_params", {}),
                    # ⭐ 迭代控制参数 (从 config.py 读取，可被 strategy 覆盖)
                    "max_iterations": strategy.get("max_iterations", max_iterations),
                    "nse_threshold": strategy.get("nse_threshold", nse_threshold),
                    "min_nse_improvement": strategy.get(
                        "min_nse_improvement", min_nse_improvement
                    ),
                    "initial_range_scale": strategy.get(
                        "initial_range_scale", initial_range_scale
                    ),
                    "range_scale_decay": strategy.get("range_scale_decay", 0.7),
                    "consecutive_no_improvement_limit": strategy.get(
                        "consecutive_no_improvement_limit", 2
                    ),
                },
                dependencies=[],
            )
        ]

        return subtasks

    def _decompose_repeated_experiment(self, intent: Dict[str, Any]) -> List[SubTask]:
        """
        实验5：稳定性验证 - 重复实验
        Decompose repeated experiment task.

        Flow: N parallel calibrations with different random seeds
        """
        n_repeats = intent.get("n_repeats", 10)

        subtasks = []
        for i in range(n_repeats):
            # Create separate subtask for each repetition
            extra_params = intent.get("extra_params", {}).copy()
            extra_params["random_seed"] = 42 + i  # Different seed for each run

            subtasks.append(
                SubTask(
                    task_id=f"task_{i+1}_repeat",
                    task_type="calibration",
                    description=f"Repetition {i+1}/{n_repeats} with seed={42+i}",
                    prompt="",
                    parameters={
                        "model_name": intent.get("model_name"),
                        "basin_ids": intent.get("basin_ids"),
                        "algorithm": intent.get("algorithm"),
                        "time_period": intent.get("time_period"),
                        "extra_params": extra_params,
                        "repetition_id": i + 1,
                        "auto_evaluate": True,
                    },
                    dependencies=[],  # All can run in parallel
                )
            )

        # Add statistical analysis task (depends on all repetitions)
        subtasks.append(
            SubTask(
                task_id="task_stats",
                task_type="statistical_analysis",
                description=f"Aggregate statistics from {n_repeats} repetitions",
                prompt="",
                parameters={
                    "n_repeats": n_repeats,
                    "analysis_type": "stability_validation",
                },
                dependencies=[f"task_{i+1}_repeat" for i in range(n_repeats)],
            )
        )

        return subtasks

    def _decompose_extended_analysis(self, intent: Dict[str, Any]) -> List[SubTask]:
        """
        实验4：扩展分析 - 超出hydromodel功能
        Decompose extended analysis task.

        Flow:
        1. Standard calibration
        2. Custom analysis (runoff coefficient, FDC, etc.)
        """
        needs = intent.get("needs", [])

        # Extract time_period and split into train/test
        time_period = intent.get("time_period", {})
        if isinstance(time_period, dict):
            train_period = time_period.get("train")
            test_period = time_period.get("test")
        else:
            train_period = None
            test_period = None

        # Task 1: Standard calibration
        subtasks = [
            SubTask(
                task_id="task_1_calibration",
                task_type="calibration",
                description=f"Calibrate {intent.get('model_name', 'model')} on basins {intent.get('basin_ids', ['N/A'])}",
                prompt="",
                parameters={
                    "model_name": intent.get("model_name"),
                    "basin_ids": intent.get("basin_ids"),
                    "algorithm": intent.get("algorithm"),
                    "train_period": train_period,
                    "test_period": test_period,
                    "extra_params": intent.get("extra_params", {}),
                    "auto_evaluate": True,
                },
                dependencies=[],
            )
        ]

        # Task 2+: Extended analysis tasks
        for i, need in enumerate(needs, start=2):
            subtasks.append(
                SubTask(
                    task_id=f"task_{i}_analysis",
                    task_type="custom_analysis",
                    description=f"Custom analysis: {need}",
                    prompt="",
                    parameters={
                        "task_type": "custom_analysis",  # ⭐ CRITICAL: RunnerAgent needs this
                        "analysis_type": need,
                        "basin_ids": intent.get("basin_ids"),
                        "model_name": intent.get("model_name"),
                    },
                    dependencies=["task_1_calibration"],  # Depends on calibration
                )
            )

        return subtasks

    def _decompose_batch_processing(self, intent: Dict[str, Any]) -> List[SubTask]:
        """
        批量处理 - 多流域/多算法/多模型
        Decompose batch processing task.

        Flow:
        1. Multiple calibrations for basins × algorithms × models (parallel)
        2. Optional: Aggregated analysis tasks (depend on all calibrations)

        Example: "批量率定3个流域，完成后计算各流域的径流系数"
        → Creates 3 parallel calibration tasks + 1 aggregated analysis task
        """
        basins = intent.get("basin_ids", [])
        algorithms = intent.get("algorithms", [intent.get("algorithm")])
        models = intent.get("model_names", [intent.get("model_name")])
        needs = intent.get("needs", [])

        # Ensure basins/algorithms/models are lists
        if not isinstance(basins, list):
            basins = [basins] if basins else []
        if isinstance(algorithms, str):
            algorithms = [algorithms]
        if isinstance(models, str):
            models = [models]

        subtasks = []
        task_counter = 1

        # ========== STEP 1: Create parallel calibration tasks ==========
        # Create combinations of basins × algorithms × models
        for basin in basins:
            for algorithm in algorithms:
                for model in models:
                    subtasks.append(
                        SubTask(
                            task_id=f"task_{task_counter}",
                            task_type="calibration",
                            description=f"Calibrate basin {basin} with {model} using {algorithm}",
                            prompt="",
                            parameters={
                                "model_name": model,
                                "basin_ids": [basin],  # hydromodel requires array format
                                "algorithm": algorithm,
                                "time_period": intent.get("time_period"),
                                "extra_params": intent.get("extra_params", {}),
                                "auto_evaluate": True,
                            },
                            dependencies=[],  # All can run in parallel
                        )
                    )
                    task_counter += 1

        # ========== STEP 2: Create aggregated analysis tasks if needed ==========
        if needs:
            # Collect all calibration task IDs for dependency
            calib_task_ids = [f"task_{i+1}" for i in range(len(subtasks))]

            # Create one analysis task for each "need"
            for need in needs:
                subtasks.append(
                    SubTask(
                        task_id=f"task_{task_counter}_analysis",
                        task_type="custom_analysis",
                        description=f"Aggregated analysis: {need} for {len(basins)} basin(s)",
                        prompt="",
                        parameters={
                            "task_type": "custom_analysis",  # ⭐ CRITICAL: RunnerAgent needs this
                            "analysis_type": need,
                            "basin_ids": basins,  # All basins for aggregation
                            "model_name": models[0] if models else intent.get("model_name"),
                        },
                        dependencies=calib_task_ids,  # Depends on ALL calibration tasks
                    )
                )
                task_counter += 1

        return subtasks

    def _decompose_custom_data(self, intent: Dict[str, Any]) -> List[SubTask]:
        """
        实验2C：自定义数据路径
        Decompose custom data task.

        Flow: Same as standard, but with custom data_source_path
        """
        subtasks = [
            SubTask(
                task_id="task_1",
                task_type="calibration",
                description=f"Calibrate with custom data from {intent.get('data_source', 'custom path')}",
                prompt="",
                parameters={
                    "model_name": intent.get("model_name"),
                    "basin_ids": intent.get("basin_ids"),
                    "algorithm": intent.get("algorithm"),
                    "time_period": intent.get("time_period"),
                    "extra_params": intent.get("extra_params", {}),
                    "data_source_type": "custom",
                    "data_source_path": intent.get("data_source"),
                    "auto_evaluate": True,
                },
                dependencies=[],
            )
        ]

        return subtasks

    def _decompose_auto_iterative_calibration(
        self, intent: Dict[str, Any]
    ) -> List[SubTask]:
        """
        🆕 v4.0: 自动迭代率定（直到NSE达标或达到最大次数）
        Decompose auto-iterative calibration task (v4.0 new feature).

        与iterative_optimization的区别：
        - iterative_optimization: 参数范围自适应调整（实验3）
        - auto_iterative_calibration: 自动多次率定直到NSE达标（v4.0新功能）

        Flow: 自动多次率定 → 每轮生成径流拟合图 → 最终生成NSE收敛图
        """
        nse_threshold = intent.get("nse_threshold", 0.7)
        max_iterations = intent.get("max_iterations", 10)

        subtasks = [
            SubTask(
                task_id="auto_iterative_calib",
                task_type="auto_iterative_calibration",
                description=f"Auto-iterative calibration until NSE >= {nse_threshold} (max {max_iterations} iterations)",
                prompt="",
                parameters={
                    "model_name": intent.get("model_name"),
                    "basin_ids": intent.get("basin_ids"),
                    "algorithm": intent.get("algorithm"),
                    "time_period": intent.get("time_period"),
                    "extra_params": intent.get("extra_params", {}),
                    # 🆕 迭代控制参数
                    "nse_threshold": nse_threshold,
                    "max_iterations": max_iterations,
                    "plot_each_iteration": True,  # 每轮绘图
                },
                dependencies=[],
            )
        ]

        return subtasks

    # ========================================================================
    # Prompt Generation
    # ========================================================================

    def _generate_subtask_prompt(
        self,
        subtask: SubTask,
        intent_result: Dict[str, Any],
        error_log: Optional[str] = None,
    ) -> str:
        """
        Generate prompt for a subtask using PromptPool.
        使用提示词池为子任务生成提示词。

        Args:
            subtask: SubTask object
            intent_result: Original intent result
            error_log: Optional error log from previous attempt

        Returns:
            Complete prompt string
        """
        # Base prompt based on subtask type
        base_prompt = self._get_base_prompt(subtask.task_type)

        # Add task-specific parameters to prompt
        base_prompt = self._inject_parameters(base_prompt, subtask.parameters)

        # Use PromptPool to add historical context
        complete_prompt = self.prompt_pool.generate_context_prompt(
            base_prompt=base_prompt, intent=intent_result, error_log=error_log
        )

        return complete_prompt

    def _get_base_prompt(self, task_type: str) -> str:
        """
        Get base prompt template for a task type.
        获取任务类型的基础提示词模板。

        Args:
            task_type: Type of subtask

        Returns:
            Base prompt string
        """
        # Base prompts for different task types
        prompts = {
            "calibration": """
## 任务：水文模型率定

请生成hydromodel配置字典，用于率定水文模型。

**要求**:
1. 使用统一配置格式（unified format）
2. 配置应包含 data_cfgs, model_cfgs, training_cfgs 三个部分
3. 确保所有必需字段都已填写
4. 算法参数应根据模型复杂度调整

**输出**: 完整的配置字典（JSON格式）
""",
            "boundary_check_recalibration": """
## 任务：边界检查与重新率定

基于Phase 1的率定结果，检查参数是否收敛到边界，如需要则调整参数范围重新率定。

**检查逻辑**:
1. 读取Phase 1的最优参数
2. 检查是否有参数接近边界（距离 < boundary_threshold）
3. 如有边界参数，扩展参数范围
4. 生成新的配置并重新率定

**输出**: 配置字典（如需重新率定）或跳过信号
""",
            "statistical_analysis": """
## 任务：统计分析

对多次重复实验的结果进行统计分析。

**分析内容**:
1. 计算性能指标的均值、标准差、变异系数
2. 计算参数的均值、标准差
3. 评估模型稳定性
4. 生成可视化图表（箱线图、分布图）

**输出**: 统计分析报告
""",
            "custom_analysis": """
## 任务：自定义分析

执行超出hydromodel标准功能的自定义分析。

**分析类型**: {analysis_type}

**输出**: Python代码 + 分析结果
""",
        }

        return prompts.get(task_type, prompts["calibration"])

    def _inject_parameters(self, base_prompt: str, parameters: Dict[str, Any]) -> str:
        """
        Inject parameters into base prompt.
        将参数注入基础提示词。

        Args:
            base_prompt: Base prompt template
            parameters: Parameter dictionary

        Returns:
            Prompt with parameters injected
        """
        # Add parameter section
        param_lines = ["\n### 任务参数\n"]

        for key, value in parameters.items():
            if value is not None:
                param_lines.append(f"- **{key}**: {value}")

        return base_prompt + "\n".join(param_lines)

    # ========================================================================
    # 🆕 v5.0: LLM-Based Dynamic Task Decomposition
    # ========================================================================

    def _decompose_task_with_llm(self, intent_result: Dict[str, Any]) -> List[SubTask]:
        """
        🆕 v5.0: Use LLM to dynamically decompose task into subtasks.
        使用 LLM 动态拆解任务为子任务。

        Strategy:
        1. Retrieve similar historical cases from PromptPool (FAISS)
        2. Build prompt with intent + historical examples
        3. Call LLM to generate subtask decomposition
        4. Parse LLM response into SubTask objects

        Args:
            intent_result: Intent from IntentAgent

        Returns:
            List of SubTask objects (empty if LLM fails)
        """
        import json

        # Step 1: Retrieve similar historical cases
        historical_cases = self._retrieve_historical_cases(intent_result)

        # Step 2: Build decomposition prompt
        decomposition_prompt = self._build_decomposition_prompt(
            intent_result, historical_cases
        )

        # Step 3: Call LLM
        try:
            response = self.llm.generate(
                system_prompt=self._get_llm_planning_system_prompt(),
                user_prompt=decomposition_prompt,
                temperature=0.1,
                max_tokens=2000
            )

            # Step 4: Parse LLM response
            subtasks = self._parse_llm_decomposition(response, intent_result)

            return subtasks

        except Exception as e:
            logger.error(f"[TaskPlanner v5.0] LLM call failed: {str(e)}", exc_info=True)
            return []

    def _retrieve_historical_cases(
        self, intent_result: Dict[str, Any], top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Retrieve similar historical cases from PromptPool using FAISS.
        从 PromptPool 使用 FAISS 检索相似的历史案例。

        Args:
            intent_result: Current intent
            top_k: Number of cases to retrieve

        Returns:
            List of historical case dictionaries
        """
        if not self.prompt_pool or not self.prompt_pool.use_faiss or not self.prompt_pool.faiss_index:
            logger.info("[TaskPlanner v5.0] FAISS not available, no historical cases retrieved")
            return []

        # Build query from intent
        query_text = self._intent_to_query_text(intent_result)

        # Search in PromptPool
        try:
            similar_cases = self.prompt_pool.search_similar(query_text, top_k=top_k)
            logger.info(f"[TaskPlanner v5.0] Retrieved {len(similar_cases)} similar cases")
            return similar_cases
        except Exception as e:
            logger.warning(f"[TaskPlanner v5.0] FAISS search failed: {str(e)}")
            return []

    def _intent_to_query_text(self, intent_result: Dict[str, Any]) -> str:
        """
        Convert intent to query text for FAISS search.
        将 intent 转换为用于 FAISS 检索的查询文本。

        Args:
            intent_result: Intent dictionary

        Returns:
            Query text string
        """
        parts = []

        task_type = intent_result.get("task_type", "")
        model_name = intent_result.get("model_name", "")
        algorithm = intent_result.get("algorithm", "")

        if task_type:
            parts.append(f"任务类型: {task_type}")
        if model_name:
            parts.append(f"模型: {model_name}")
        if algorithm:
            parts.append(f"算法: {algorithm}")

        return " ".join(parts)

    def _build_decomposition_prompt(
        self, intent_result: Dict[str, Any], historical_cases: List[Dict[str, Any]]
    ) -> str:
        """
        Build prompt for LLM task decomposition.
        构建 LLM 任务拆解的提示词。

        Args:
            intent_result: Current intent
            historical_cases: Retrieved historical cases

        Returns:
            Complete prompt string
        """
        import json

        prompt_parts = []

        # Part 1: Current task description
        prompt_parts.append("## 当前任务\n")
        prompt_parts.append(json.dumps(intent_result, indent=2, ensure_ascii=False))

        # Part 2: Historical examples (if available)
        if historical_cases:
            prompt_parts.append("\n## 历史参考案例\n")
            for i, case in enumerate(historical_cases, 1):
                prompt_parts.append(f"\n### 案例 {i}")
                prompt_parts.append(json.dumps(case, indent=2, ensure_ascii=False))

        # Part 3: Instructions
        prompt_parts.append("\n## 任务要求\n")
        prompt_parts.append(
            "请根据当前任务的 intent 信息,将其拆解为具体的子任务。\n"
            "每个子任务需要包含:\n"
            "1. task_id: 唯一标识 (如 task_1, task_2)\n"
            "2. task_type: 任务类型 (calibration, evaluation, analysis等)\n"
            "3. description: 人类可读的描述\n"
            "4. parameters: 任务参数字典\n"
            "   - ⚠️ **CRITICAL**: 对于 task_type='analysis' 的任务，parameters 中**必须**包含 'analysis_type' 字段\n"
            "   - analysis_type 可选值: FDC, runoff_coefficient, water_balance, seasonal_analysis 等\n"
            "   - 从 intent.needs 数组中获取具体的分析类型（如 needs=['FDC'] → analysis_type='FDC'）\n"
            "5. dependencies: 依赖的任务ID列表 (可选)\n\n"
            "请以JSON格式返回子任务列表,格式如下:\n"
            "```json\n"
            "[\n"
            '  {"task_id": "task_1", "task_type": "calibration", '
            '"description": "...", "parameters": {...}, "dependencies": []},\n'
            '  {"task_id": "task_2", "task_type": "evaluation", '
            '"description": "...", "parameters": {...}, "dependencies": ["task_1"]},\n'
            '  {"task_id": "task_3", "task_type": "analysis", '
            '"description": "...", "parameters": {"analysis_type": "FDC", ...}, "dependencies": ["task_1"]}\n'
            "]\n"
            "```\n\n"
            "示例: 如果 intent.needs = ['FDC'], 则 task_3 的 parameters 应包含 'analysis_type': 'FDC'"
        )

        return "\n".join(prompt_parts)

    def _get_llm_planning_system_prompt(self) -> str:
        """
        Get system prompt for LLM-based planning.
        获取 LLM 规划的系统提示词。

        Returns:
            System prompt string
        """
        return """你是 HydroAgent 的任务规划专家。

你的职责是将用户的高层意图拆解为具体、可执行的子任务序列。

核心原则:
1. **清晰拆解**: 每个子任务应该明确、独立、可执行
2. **依赖管理**: 正确识别任务间的依赖关系
3. **参数完整**: 为每个子任务提供必要的参数
4. **参考历史**: 学习历史成功案例的拆解模式

任务类型:
- calibration: 模型参数率定
- evaluation: 模型性能评估
- simulation: 模型预测模拟
- analysis: 自定义分析 (如径流系数、FDC曲线)
- boundary_check_recalibration: 参数边界检查和重新率定 (迭代优化)
- statistical_analysis: 统计分析 (重复实验)

请始终以结构化的JSON格式返回子任务列表。"""

    def _parse_llm_decomposition(
        self, llm_response: str, intent_result: Dict[str, Any]
    ) -> List[SubTask]:
        """
        Parse LLM response into SubTask objects.
        解析 LLM 响应为 SubTask 对象。

        Args:
            llm_response: LLM response text
            intent_result: Original intent (for fallback)

        Returns:
            List of SubTask objects
        """
        import json
        import re

        # Try to extract JSON from response (may be wrapped in ```json...```)
        json_match = re.search(r"```json\s*(\[.*?\])\s*```", llm_response, re.DOTALL)

        if json_match:
            json_text = json_match.group(1)
        else:
            # Try to find bare JSON array
            json_match = re.search(r"(\[.*\])", llm_response, re.DOTALL)
            if json_match:
                json_text = json_match.group(1)
            else:
                logger.error("[TaskPlanner v5.0] No JSON found in LLM response")
                return []

        try:
            subtasks_data = json.loads(json_text)

            if not isinstance(subtasks_data, list):
                logger.error("[TaskPlanner v5.0] LLM response is not a list")
                return []

            # Convert to SubTask objects
            subtasks = []
            for i, st_data in enumerate(subtasks_data):
                # Validate required fields
                if not all(k in st_data for k in ["task_id", "task_type", "description"]):
                    logger.warning(
                        f"[TaskPlanner v5.0] Subtask {i} missing required fields, skipping"
                    )
                    continue

                # Get parameters from LLM
                parameters = st_data.get("parameters", {})

                # ⭐ FIX: Ensure critical fields from intent are propagated
                # LLM may forget to include test_period, algorithm, etc.
                task_type = st_data.get("task_type", "calibration")

                if task_type in ["calibration", "evaluation"]:
                    # Extract time_period from intent
                    time_period = intent_result.get("time_period", {})

                    # Ensure train_period and test_period are set
                    if "train_period" not in parameters or not parameters.get("train_period"):
                        if isinstance(time_period, dict):
                            parameters["train_period"] = time_period.get("train")
                        elif isinstance(time_period, list) and len(time_period) == 2:
                            # Legacy format: [train_start, train_end]
                            parameters["train_period"] = time_period

                    if "test_period" not in parameters or not parameters.get("test_period"):
                        if isinstance(time_period, dict):
                            parameters["test_period"] = time_period.get("test")
                        # Else leave as None/empty - it's optional for some workflows

                    # Ensure other critical fields
                    if "model_name" not in parameters:
                        parameters["model_name"] = intent_result.get("model_name")
                    if "basin_ids" not in parameters:
                        parameters["basin_ids"] = intent_result.get("basin_ids")
                    if "algorithm" not in parameters:
                        parameters["algorithm"] = intent_result.get("algorithm")

                    logger.debug(f"[TaskPlanner] Auto-filled parameters for {st_data.get('task_id')}: "
                                f"train_period={parameters.get('train_period')}, "
                                f"test_period={parameters.get('test_period')}")

                subtask = SubTask(
                    task_id=st_data.get("task_id", f"task_{i+1}"),
                    task_type=task_type,
                    description=st_data.get("description", ""),
                    prompt="",  # Will be generated later
                    parameters=parameters,
                    dependencies=st_data.get("dependencies", [])
                )

                subtasks.append(subtask)

            return subtasks

        except json.JSONDecodeError as e:
            logger.error(f"[TaskPlanner v5.0] JSON decode error: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"[TaskPlanner v5.0] Parse error: {str(e)}", exc_info=True)
            return []

    def _process_with_tools(
        self,
        intent_result: Dict[str, Any],
        task_type: str
    ) -> Dict[str, Any]:
        """
        Process task using tool orchestrator (Phase 1 implementation).
        使用工具编排器处理任务（Phase 1实现）。

        Args:
            intent_result: Intent recognition result
            task_type: Task type

        Returns:
            Dict containing tool_chain instead of subtasks
        """
        try:
            # ✅ v6.0: Multi-model combination support via tool_chain subtasks
            # Decompose into multiple single-combination tool chains and let Orchestrator loop
            if task_type == "batch_processing":
                models = intent_result.get("model_names", [intent_result.get("model_name")])
                basins = intent_result.get("basin_ids", [])
                algorithms = intent_result.get("algorithms", [intent_result.get("algorithm")])

                # Normalize to lists
                if isinstance(models, str):
                    models = [models]
                if not isinstance(basins, list):
                    basins = [basins] if basins else []
                if isinstance(algorithms, str):
                    algorithms = [algorithms]

                # Check if we have multiple combinations
                num_combinations = len(models) * len(basins) * len(algorithms)
                if num_combinations > 1:
                    logger.info(
                        f"[TaskPlanner v6.0] Detected multi-combination batch: {len(models)} model(s) × {len(basins)} basin(s) × {len(algorithms)} algorithm(s) = {num_combinations} combinations"
                    )
                    logger.info("[TaskPlanner v6.0] Generating tool_chain subtasks (Orchestrator will loop)")

                    # ✅ Generate tool_chain for each combination
                    subtasks = []
                    task_counter = 1

                    for model in models:
                        for basin in basins:
                            for algorithm in algorithms:
                                task_id = f"task_{task_counter}"

                                # Create sub-intent for this combination (single model × single basin)
                                sub_intent = {
                                    **intent_result,
                                    "model_name": model,
                                    "basin_ids": [basin],  # Single basin
                                    "algorithm": algorithm
                                }

                                # Generate tool chain for this single combination
                                logger.info(f"[TaskPlanner v6.0] Generating tool_chain for {task_id}: {model} × {basin} × {algorithm}")
                                tool_chain_result = self.orchestrator.generate_tool_chain(
                                    task_type="standard_calibration",  # Each combination is a standard calibration
                                    intent_result=sub_intent,
                                    use_llm=False  # Use rule-based for efficiency
                                )

                                if not tool_chain_result.get("success", True):
                                    logger.error(f"[TaskPlanner] Tool chain generation failed for {task_id}")
                                    continue

                                # Create subtask with tool_chain
                                subtasks.append({
                                    "task_id": task_id,
                                    "description": f"Calibrate {model} on basin {basin} with {algorithm}",
                                    "tool_chain": tool_chain_result.get("tool_chain"),
                                    "execution_mode": tool_chain_result.get("execution_mode", "simple"),
                                    "mode_params": tool_chain_result.get("mode_params", {}),
                                    "intent_result": sub_intent,  # Store intent for config generation
                                })

                                task_counter += 1

                    logger.info(f"[TaskPlanner v6.0] Generated {len(subtasks)} tool_chain subtasks")

                    # Return in task_plan format for Orchestrator to loop
                    return {
                        "success": True,
                        "task_plan": {
                            "task_type": task_type,
                            "subtasks": subtasks,
                            "use_tool_chains": True,  # ✅ Flag: subtasks contain tool_chains
                            "total_subtasks": len(subtasks)
                        }
                    }

            # Generate tool chain using orchestrator (returns dict with tool_chain + execution_mode)
            orchestration_result = self.orchestrator.generate_tool_chain(
                task_type=task_type,
                intent_result=intent_result,
                use_llm=True  # Enable LLM-based intelligent orchestration (with rule-based fallback)
            )

            tool_chain = orchestration_result["tool_chain"]
            execution_mode = orchestration_result["execution_mode"]
            mode_params = orchestration_result["mode_params"]
            # 🆕 Get updated task_type (may have been upgraded by ToolOrchestrator)
            updated_task_type = orchestration_result.get("task_type", task_type)

            # Validate tool chain
            is_valid, error = self.orchestrator.validate_tool_chain(tool_chain)
            if not is_valid:
                logger.error(f"[TaskPlanner] Invalid tool chain: {error}")
                return {
                    "success": False,
                    "error": f"Tool chain validation failed: {error}"
                }

            # Get tool chain summary for logging
            summary = self.orchestrator.get_tool_chain_summary(tool_chain)
            logger.info(f"[TaskPlanner] Generated tool chain ({execution_mode} mode):\n{summary}")

            # Return tool chain format (different from legacy subtasks format)
            return {
                "success": True,
                "task_type": updated_task_type,  # 🆕 Use updated task_type from orchestrator
                "tool_chain": tool_chain,  # List of tool calls
                "execution_mode": execution_mode,  # simple/iterative/repeated
                "mode_params": mode_params,  # Parameters for execution mode
                "total_tools": len(tool_chain)
            }

        except Exception as e:
            logger.error(
                f"[TaskPlanner] Tool orchestration failed: {str(e)}",
                exc_info=True
            )
            return {
                "success": False,
                "error": f"Tool orchestration error: {str(e)}"
            }
