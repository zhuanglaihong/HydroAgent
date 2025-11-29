"""
Author: Claude
Date: 2025-11-22 16:00:00
LastEditTime: 2025-11-22 16:00:00
LastEditors: Claude
Description: Task Planner Agent - Decomposes high-level tasks into subtasks with prompts
             任务规划智能体 - 将高层任务拆解为带提示词的子任务
FilePath: /HydroAgent/hydroagent/agents/task_planner.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
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
    task_id: str                    # e.g., "task_1", "task_2a", "task_2b"
    task_type: str                  # Type of subtask (calibration, evaluation, etc.)
    description: str                # Human-readable description
    prompt: str                     # Complete prompt for InterpreterAgent
    parameters: Dict[str, Any]      # Parameters specific to this subtask
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
        **kwargs
    ):
        """
        Initialize TaskPlanner.

        Args:
            llm_interface: LLM API interface
            prompt_pool: PromptPool instance for historical cases
            workspace_dir: Working directory for results
            **kwargs: Additional configuration
        """
        super().__init__(
            name="TaskPlanner",
            llm_interface=llm_interface,
            workspace_dir=workspace_dir,
            **kwargs
        )

        # Initialize PromptPool
        self.prompt_pool = prompt_pool or PromptPool(
            pool_dir=workspace_dir / "prompt_pool" if workspace_dir else None
        )

        # Task decomposition mapping
        self.decomposition_methods = {
            "standard_calibration": self._decompose_standard_calibration,
            "info_completion": self._decompose_info_completion,
            "iterative_optimization": self._decompose_iterative_optimization,
            "repeated_experiment": self._decompose_repeated_experiment,
            "extended_analysis": self._decompose_extended_analysis,
            "batch_processing": self._decompose_batch_processing,
            "custom_data": self._decompose_custom_data,
            "auto_iterative_calibration": self._decompose_auto_iterative_calibration,  # 🆕 v4.0
        }

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
        Decompose task into subtasks with prompts.
        将任务拆解为带提示词的子任务。

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
                    "task_plan": {
                        "task_type": "iterative_optimization",
                        "subtasks": [SubTask, SubTask, ...],
                        "total_subtasks": 2
                    }
                }
        """
        intent_result = input_data.get("intent_result", {})
        error_log = input_data.get("error_log")

        task_type = intent_result.get("task_type", "standard_calibration")

        logger.info(f"[TaskPlanner] Decomposing task: {task_type}")

        try:
            # Step 1: Decompose task into subtasks
            subtasks = self._decompose_task(intent_result)

            # Step 2: Generate prompts for each subtask
            for subtask in subtasks:
                subtask.prompt = self._generate_subtask_prompt(
                    subtask, intent_result, error_log
                )

                # Store prompt in PromptPool
                self.prompt_pool.store_prompt(
                    task_id=subtask.task_id,
                    prompt=subtask.prompt,
                    params=subtask.parameters
                )

            # Step 3: Create task plan
            task_plan = {
                "task_type": task_type,
                "subtasks": [st.to_dict() for st in subtasks],
                "total_subtasks": len(subtasks)
            }

            logger.info(f"[TaskPlanner] Task plan created: {len(subtasks)} subtasks")

            return {
                "success": True,
                "task_plan": task_plan
            }

        except Exception as e:
            logger.error(f"[TaskPlanner] Task decomposition failed: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def _decompose_task(self, intent_result: Dict[str, Any]) -> List[SubTask]:
        """
        Decompose task based on task_type.
        根据任务类型拆解任务。

        Args:
            intent_result: Intent analysis result with task_type

        Returns:
            List of SubTask objects
        """
        task_type = intent_result.get("task_type", "standard_calibration")

        # Get appropriate decomposition method
        decomposition_method = self.decomposition_methods.get(task_type)

        if not decomposition_method:
            logger.warning(f"[TaskPlanner] Unknown task_type: {task_type}, using standard")
            decomposition_method = self._decompose_standard_calibration

        return decomposition_method(intent_result)

    # ========================================================================
    # Task-Specific Decomposition Methods
    # ========================================================================

    def _decompose_standard_calibration(self, intent: Dict[str, Any]) -> List[SubTask]:
        """
        实验1：标准单任务率定
        Decompose standard calibration task.

        Flow: Calibration → Evaluation (single task)
        """
        subtasks = [
            SubTask(
                task_id="task_1",
                task_type="calibration",
                description=f"Calibrate {intent.get('model_name', 'model')} on basin {intent.get('basin_id', 'N/A')}",
                prompt="",  # Will be filled by _generate_subtask_prompt
                parameters={
                    "model_name": intent.get("model_name"),
                    "basin_id": intent.get("basin_id"),
                    "algorithm": intent.get("algorithm"),
                    "time_period": intent.get("time_period"),
                    "extra_params": intent.get("extra_params", {}),
                    "auto_evaluate": True  # Auto-run evaluation after calibration
                },
                dependencies=[]
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

    def _decompose_iterative_optimization(self, intent: Dict[str, Any]) -> List[SubTask]:
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
        max_iterations = getattr(config, 'MAX_ITERATIONS', 5) if config else 5
        nse_threshold = getattr(config, 'NSE_THRESHOLD_FOR_ITERATION', 0.65) if config else 0.65
        min_nse_improvement = getattr(config, 'MIN_NSE_IMPROVEMENT', 0.01) if config else 0.01
        initial_range_scale = getattr(config, 'INITIAL_RANGE_SCALE', 0.6) if config else 0.6

        subtasks = [
            SubTask(
                task_id="iterative_boundary_optimization",
                task_type="boundary_check_recalibration",
                description=f"Iterative optimization for {intent.get('basin_id', 'N/A')} (internal loop until convergence)",
                prompt="",
                parameters={
                    "model_name": intent.get("model_name"),
                    "basin_id": intent.get("basin_id"),
                    "algorithm": intent.get("algorithm"),
                    "time_period": intent.get("time_period"),
                    "extra_params": intent.get("extra_params", {}),
                    # ⭐ 迭代控制参数 (从 config.py 读取，可被 strategy 覆盖)
                    "max_iterations": strategy.get("max_iterations", max_iterations),
                    "nse_threshold": strategy.get("nse_threshold", nse_threshold),
                    "min_nse_improvement": strategy.get("min_nse_improvement", min_nse_improvement),
                    "initial_range_scale": strategy.get("initial_range_scale", initial_range_scale),
                    "range_scale_decay": strategy.get("range_scale_decay", 0.7),
                    "consecutive_no_improvement_limit": strategy.get("consecutive_no_improvement_limit", 2)
                },
                dependencies=[]
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
                        "basin_id": intent.get("basin_id"),
                        "algorithm": intent.get("algorithm"),
                        "time_period": intent.get("time_period"),
                        "extra_params": extra_params,
                        "repetition_id": i + 1,
                        "auto_evaluate": True
                    },
                    dependencies=[]  # All can run in parallel
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
                    "analysis_type": "stability_validation"
                },
                dependencies=[f"task_{i+1}_repeat" for i in range(n_repeats)]
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

        # Task 1: Standard calibration
        subtasks = [
            SubTask(
                task_id="task_1_calibration",
                task_type="calibration",
                description=f"Calibrate {intent.get('model_name', 'model')} on basin {intent.get('basin_id', 'N/A')}",
                prompt="",
                parameters={
                    "model_name": intent.get("model_name"),
                    "basin_id": intent.get("basin_id"),
                    "algorithm": intent.get("algorithm"),
                    "time_period": intent.get("time_period"),
                    "extra_params": intent.get("extra_params", {}),
                    "auto_evaluate": True
                },
                dependencies=[]
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
                        "basin_id": intent.get("basin_id"),
                        "model_name": intent.get("model_name")
                    },
                    dependencies=["task_1_calibration"]  # Depends on calibration
                )
            )

        return subtasks

    def _decompose_batch_processing(self, intent: Dict[str, Any]) -> List[SubTask]:
        """
        批量处理 - 多流域/多算法/多模型
        Decompose batch processing task.

        Flow: Multiple calibrations for basins × algorithms × models
        """
        basins = intent.get("basin_ids", [intent.get("basin_id")])
        algorithms = intent.get("algorithms", [intent.get("algorithm")])
        models = intent.get("model_names", [intent.get("model_name")])

        # Handle single basin/algorithm/model case
        if isinstance(basins, str):
            basins = [basins]
        if isinstance(algorithms, str):
            algorithms = [algorithms]
        if isinstance(models, str):
            models = [models]

        subtasks = []
        task_counter = 1

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
                                "basin_id": basin,
                                "algorithm": algorithm,
                                "time_period": intent.get("time_period"),
                                "extra_params": intent.get("extra_params", {}),
                                "auto_evaluate": True
                            },
                            dependencies=[]  # All can run in parallel
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
                    "basin_id": intent.get("basin_id"),
                    "algorithm": intent.get("algorithm"),
                    "time_period": intent.get("time_period"),
                    "extra_params": intent.get("extra_params", {}),
                    "data_source_type": "custom",
                    "data_source_path": intent.get("data_source"),
                    "auto_evaluate": True
                },
                dependencies=[]
            )
        ]

        return subtasks

    def _decompose_auto_iterative_calibration(self, intent: Dict[str, Any]) -> List[SubTask]:
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
                    "basin_id": intent.get("basin_id"),
                    "algorithm": intent.get("algorithm"),
                    "time_period": intent.get("time_period"),
                    "extra_params": intent.get("extra_params", {}),
                    # 🆕 迭代控制参数
                    "nse_threshold": nse_threshold,
                    "max_iterations": max_iterations,
                    "plot_each_iteration": True  # 每轮绘图
                },
                dependencies=[]
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
        error_log: Optional[str] = None
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
            base_prompt=base_prompt,
            intent=intent_result,
            error_log=error_log
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
