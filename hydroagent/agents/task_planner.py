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

        # ❌ v6.0: decomposition_methods removed - all tasks use tool system

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
    # ❌ v6.0: Legacy decomposition methods REMOVED (~858 lines deleted)
    # All tasks now use _process_with_tools() - unified tool chain execution
    # See git history for removed methods: _decompose_task(), _decompose_*(), etc.
    # ========================================================================

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
