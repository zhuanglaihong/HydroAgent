"""
Author: Claude
Date: 2025-12-03 15:30:00
LastEditTime: 2025-12-03 15:30:00
LastEditors: Claude
Description: Orchestrator state machine for HydroAgent v5.0
             决策式状态机 - 管理Orchestrator的状态转移和决策逻辑
FilePath: /HydroAgent/hydroagent/core/state_machine.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

核心功能:
1. OrchestratorState: 状态枚举 (10-15个状态)
2. StateTransition: 状态转移规则 (条件+动作)
3. StateMachine: 状态机核心逻辑 (转移执行+历史记录)
"""

from enum import Enum, auto
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class OrchestratorState(Enum):
    """
    Orchestrator状态枚举 (简化版,共15个状态)

    状态分类:
    - 初始化阶段: INIT, WAITING_USER_INPUT
    - 意图识别阶段: ANALYZING_INTENT, INTENT_CONFIRMED
    - 任务规划阶段: PLANNING_TASKS, PLAN_READY
    - 配置生成阶段: GENERATING_CONFIG, CONFIG_READY
    - 执行阶段: EXECUTING_TASK, EXECUTION_SUCCESS, EXECUTION_FAILED_RETRYABLE
    - 分析阶段: ANALYZING_RESULTS, RESULTS_ACCEPTABLE
    - 反馈优化阶段: ITERATING
    - 终止状态: COMPLETED_SUCCESS, FAILED_UNRECOVERABLE
    """
    # 初始化阶段
    INIT = auto()
    WAITING_USER_INPUT = auto()

    # 意图识别阶段
    ANALYZING_INTENT = auto()
    INTENT_CONFIRMED = auto()

    # 任务规划阶段
    PLANNING_TASKS = auto()
    PLAN_READY = auto()

    # 配置生成阶段
    GENERATING_CONFIG = auto()
    CONFIG_READY = auto()

    # 执行阶段
    EXECUTING_TASK = auto()
    EXECUTION_SUCCESS = auto()
    EXECUTION_FAILED_RETRYABLE = auto()  # 可重试的失败

    # 分析阶段
    ANALYZING_RESULTS = auto()
    RESULTS_ACCEPTABLE = auto()

    # 反馈优化阶段
    ITERATING = auto()  # 迭代优化中

    # 终止状态
    COMPLETED_SUCCESS = auto()
    FAILED_UNRECOVERABLE = auto()


class StateTransition:
    """
    状态转移规则

    职责:
    - 定义从某状态到另一状态的转移条件
    - 可选地在转移时执行特定动作
    """

    def __init__(
        self,
        from_state: OrchestratorState,
        to_state: OrchestratorState,
        condition: Callable[[Dict[str, Any]], bool],
        action: Optional[Callable[[Dict[str, Any]], None]] = None,
        description: str = ""
    ):
        """
        初始化状态转移规则

        Args:
            from_state: 起始状态
            to_state: 目标状态
            condition: 转移条件函数 (接收context,返回bool)
            action: 转移时执行的动作函数 (可选)
            description: 转移规则描述 (用于调试和日志)
        """
        self.from_state = from_state
        self.to_state = to_state
        self.condition = condition
        self.action = action
        self.description = description or f"{from_state.name} → {to_state.name}"


class StateMachine:
    """
    Orchestrator状态机核心逻辑

    职责:
    - 维护当前状态
    - 执行状态转移
    - 记录状态历史
    - 管理全局上下文
    """

    def __init__(self, max_transitions: int = 100):
        """
        初始化状态机

        Args:
            max_transitions: 最大转移次数限制 (防止死循环)
        """
        self.current_state = OrchestratorState.INIT
        self.transitions: List[StateTransition] = []
        self.state_history: List[Dict[str, Any]] = []
        self.context: Dict[str, Any] = {}
        self.max_transitions = max_transitions
        self.transition_count = 0

    def add_transition(self, transition: StateTransition):
        """添加状态转移规则"""
        self.transitions.append(transition)
        logger.debug(f"[StateMachine] Added transition: {transition.description}")

    def add_transitions(self, transitions: List[StateTransition]):
        """批量添加状态转移规则"""
        for trans in transitions:
            self.add_transition(trans)

    def update_context(self, updates: Dict[str, Any]):
        """更新全局上下文"""
        self.context.update(updates)

    def get_context(self, key: str, default: Any = None) -> Any:
        """获取上下文变量"""
        return self.context.get(key, default)

    def transition(self, context_updates: Optional[Dict[str, Any]] = None) -> OrchestratorState:
        """
        执行状态转移

        流程:
        1. 更新上下文
        2. 遍历所有转移规则,找到第一个满足条件的
        3. 执行转移动作(如果有)
        4. 更新状态
        5. 记录历史

        Args:
            context_updates: 上下文更新字典

        Returns:
            转移后的新状态

        Raises:
            RuntimeError: 如果达到最大转移次数
        """
        # 检查转移次数限制
        if self.transition_count >= self.max_transitions:
            raise RuntimeError(
                f"[StateMachine] Exceeded max transitions ({self.max_transitions}). "
                f"Possible infinite loop detected."
            )

        # 更新上下文
        if context_updates:
            self.update_context(context_updates)

        # 查找匹配的转移规则
        old_state = self.current_state
        for trans in self.transitions:
            if trans.from_state == self.current_state:
                try:
                    # 检查转移条件
                    if trans.condition(self.context):
                        # 执行转移动作
                        if trans.action:
                            logger.info(f"[StateMachine] Executing action for: {trans.description}")
                            trans.action(self.context)

                        # 更新状态
                        self.current_state = trans.to_state
                        self.transition_count += 1

                        # 记录历史
                        self._record_history(old_state, trans.to_state, trans.description)

                        logger.info(
                            f"[StateMachine] State transition #{self.transition_count}: "
                            f"{old_state.name} → {trans.to_state.name}"
                        )

                        return self.current_state

                except Exception as e:
                    logger.error(
                        f"[StateMachine] Error in transition {trans.description}: {str(e)}",
                        exc_info=True
                    )
                    # 继续尝试下一个转移规则

        # 无匹配转移,保持当前状态
        logger.debug(f"[StateMachine] No matching transition from {old_state.name}, staying in current state")
        return self.current_state

    def _record_history(self, from_state: OrchestratorState, to_state: OrchestratorState, description: str):
        """记录状态转移历史"""
        self.state_history.append({
            "transition_id": self.transition_count,
            "from_state": from_state.name,
            "to_state": to_state.name,
            "description": description,
            "timestamp": datetime.now().isoformat(),
            "context_snapshot": self.context.copy()
        })

    def is_terminal_state(self) -> bool:
        """判断当前状态是否为终止状态"""
        terminal_states = {
            OrchestratorState.COMPLETED_SUCCESS,
            OrchestratorState.FAILED_UNRECOVERABLE
        }
        return self.current_state in terminal_states

    def get_history_summary(self) -> str:
        """获取状态历史摘要 (用于调试和日志)"""
        if not self.state_history:
            return "No state transitions recorded"

        lines = [f"State Transition History ({len(self.state_history)} transitions):"]
        for i, record in enumerate(self.state_history, 1):
            lines.append(
                f"  {i}. [{record['timestamp']}] {record['from_state']} → {record['to_state']}"
            )

        return "\n".join(lines)

    def reset(self):
        """重置状态机 (用于测试或重新开始)"""
        logger.info("[StateMachine] Resetting state machine")
        self.current_state = OrchestratorState.INIT
        self.state_history.clear()
        self.context.clear()
        self.transition_count = 0


# ============================================================================
# 辅助函数
# ============================================================================

def _has_pending_subtasks(ctx: Dict[str, Any]) -> bool:
    """
    检查执行上下文中是否还有待执行的子任务。

    Args:
        ctx: Orchestrator执行上下文

    Returns:
        bool: True if there are pending subtasks, False otherwise
    """
    task_plan = ctx.get("task_plan", {})
    subtasks = task_plan.get("subtasks", [])

    if not subtasks:
        return False

    # Get completed subtask IDs from execution_results
    execution_results = ctx.get("execution_results", [])
    completed_ids = set()
    for result in execution_results:
        if result.get("success", False):
            task_id = result.get("task_id")
            if task_id:
                completed_ids.add(task_id)

    # Check if there are any subtasks not completed
    for subtask in subtasks:
        task_id = subtask.get("task_id")
        if task_id and task_id not in completed_ids:
            logger.debug(f"[StateMachine] Found pending subtask: {task_id}")
            return True

    logger.debug("[StateMachine] No pending subtasks remaining")
    return False


# ============================================================================
# 默认状态转移规则构建器
# ============================================================================

def build_default_transitions() -> List[StateTransition]:
    """
    构建默认的状态转移规则集

    这是一个简化版本,Orchestrator可以根据需要自定义或扩展

    Returns:
        状态转移规则列表
    """
    transitions = []

    # ======== 初始化阶段 ========
    transitions.append(StateTransition(
        from_state=OrchestratorState.INIT,
        to_state=OrchestratorState.WAITING_USER_INPUT,
        condition=lambda ctx: True,  # 总是转移
        description="Init → Waiting for user input"
    ))

    transitions.append(StateTransition(
        from_state=OrchestratorState.WAITING_USER_INPUT,
        to_state=OrchestratorState.ANALYZING_INTENT,
        condition=lambda ctx: ctx.get("query") is not None,
        description="Got user query → Analyzing intent"
    ))

    # ======== 意图识别阶段 ========
    transitions.append(StateTransition(
        from_state=OrchestratorState.ANALYZING_INTENT,
        to_state=OrchestratorState.INTENT_CONFIRMED,
        condition=lambda ctx: (
            not ctx.get("intent_analysis_failed", False) and
            ctx.get("intent_result", {}).get("intent") != "UNKNOWN" and
            ctx.get("intent_confidence", 0) >= 0.6
        ),
        description="Intent analyzed successfully → Intent confirmed"
    ))

    transitions.append(StateTransition(
        from_state=OrchestratorState.ANALYZING_INTENT,
        to_state=OrchestratorState.FAILED_UNRECOVERABLE,
        condition=lambda ctx: (
            ctx.get("intent_analysis_failed", False) or
            ctx.get("intent_result", {}).get("intent") == "UNKNOWN"
        ),
        description="Intent analysis failed → Failed"
    ))

    # ======== 任务规划阶段 ========
    transitions.append(StateTransition(
        from_state=OrchestratorState.INTENT_CONFIRMED,
        to_state=OrchestratorState.PLANNING_TASKS,
        condition=lambda ctx: True,
        description="Intent confirmed → Planning tasks"
    ))

    transitions.append(StateTransition(
        from_state=OrchestratorState.PLANNING_TASKS,
        to_state=OrchestratorState.PLAN_READY,
        condition=lambda ctx: ctx.get("task_plan_result", {}).get("success", False),
        description="Task plan generated → Plan ready"
    ))

    transitions.append(StateTransition(
        from_state=OrchestratorState.PLANNING_TASKS,
        to_state=OrchestratorState.FAILED_UNRECOVERABLE,
        condition=lambda ctx: not ctx.get("task_plan_result", {}).get("success", False),
        description="Task planning failed → Failed"
    ))

    # ======== 配置生成阶段 ========
    transitions.append(StateTransition(
        from_state=OrchestratorState.PLAN_READY,
        to_state=OrchestratorState.GENERATING_CONFIG,
        condition=lambda ctx: True,
        description="Plan ready → Generating config"
    ))

    transitions.append(StateTransition(
        from_state=OrchestratorState.GENERATING_CONFIG,
        to_state=OrchestratorState.CONFIG_READY,
        condition=lambda ctx: ctx.get("config_result", {}).get("success", False),
        description="Config generated → Config ready"
    ))

    transitions.append(StateTransition(
        from_state=OrchestratorState.GENERATING_CONFIG,
        to_state=OrchestratorState.PLANNING_TASKS,
        condition=lambda ctx: (
            not ctx.get("config_result", {}).get("success", False) and
            ctx.get("config_retry_count", 0) < 3
        ),
        description="Config failed → Retry planning"
    ))

    transitions.append(StateTransition(
        from_state=OrchestratorState.GENERATING_CONFIG,
        to_state=OrchestratorState.FAILED_UNRECOVERABLE,
        condition=lambda ctx: (
            not ctx.get("config_result", {}).get("success", False) and
            ctx.get("config_retry_count", 0) >= 3
        ),
        description="Config retry exhausted → Failed"
    ))

    # ======== 执行阶段 ========
    transitions.append(StateTransition(
        from_state=OrchestratorState.CONFIG_READY,
        to_state=OrchestratorState.EXECUTING_TASK,
        condition=lambda ctx: True,
        description="Config ready → Executing task"
    ))

    transitions.append(StateTransition(
        from_state=OrchestratorState.EXECUTING_TASK,
        to_state=OrchestratorState.EXECUTION_SUCCESS,
        condition=lambda ctx: ctx.get("execution_result", {}).get("success", False),
        description="Execution successful → Execution success"
    ))

    transitions.append(StateTransition(
        from_state=OrchestratorState.EXECUTING_TASK,
        to_state=OrchestratorState.EXECUTION_FAILED_RETRYABLE,
        condition=lambda ctx: (
            not ctx.get("execution_result", {}).get("success", False) and
            ctx.get("execution_result", {}).get("retryable", False) and
            ctx.get("execution_retry_count", 0) < 3
        ),
        description="Execution failed (retryable) → Retry"
    ))

    transitions.append(StateTransition(
        from_state=OrchestratorState.EXECUTION_FAILED_RETRYABLE,
        to_state=OrchestratorState.GENERATING_CONFIG,
        condition=lambda ctx: ctx.get("execution_retry_count", 0) < 3,
        description="Retry execution → Regenerate config"
    ))

    transitions.append(StateTransition(
        from_state=OrchestratorState.EXECUTING_TASK,
        to_state=OrchestratorState.FAILED_UNRECOVERABLE,
        condition=lambda ctx: (
            not ctx.get("execution_result", {}).get("success", False) and
            (not ctx.get("execution_result", {}).get("retryable", False) or
             ctx.get("execution_retry_count", 0) >= 3)
        ),
        description="Execution failed (unrecoverable) → Failed"
    ))

    # ======== 分析阶段 ========
    transitions.append(StateTransition(
        from_state=OrchestratorState.EXECUTION_SUCCESS,
        to_state=OrchestratorState.ANALYZING_RESULTS,
        condition=lambda ctx: True,
        description="Execution success → Analyzing results"
    ))

    # ⭐ CRITICAL FIX: Only iterate for iterative_optimization task type
    transitions.append(StateTransition(
        from_state=OrchestratorState.ANALYZING_RESULTS,
        to_state=OrchestratorState.RESULTS_ACCEPTABLE,
        condition=lambda ctx: (
            ctx.get("analysis_result", {}).get("success", False) and
            ctx.get("nse", 0) >= ctx.get("nse_target", 0.7)
        ),
        description="Results meet threshold → Results acceptable"
    ))

    transitions.append(StateTransition(
        from_state=OrchestratorState.ANALYZING_RESULTS,
        to_state=OrchestratorState.ITERATING,
        condition=lambda ctx: (
            ctx.get("analysis_result", {}).get("success", False) and
            ctx.get("intent_result", {}).get("task_type") == "iterative_optimization" and  # ⭐ ONLY for iterative tasks
            ctx.get("nse", 0) < ctx.get("nse_target", 0.7) and
            ctx.get("iteration_count", 0) < ctx.get("max_iterations", 10)
        ),
        description="Results below threshold (iterative task) → Iterating"
    ))

    transitions.append(StateTransition(
        from_state=OrchestratorState.ITERATING,
        to_state=OrchestratorState.PLANNING_TASKS,
        condition=lambda ctx: True,
        description="Iterating → Replan with adjusted params"
    ))

    # ⭐ NEW: Check for remaining subtasks before completing
    # For multi-task scenarios (extended_analysis, batch_processing, etc.)
    transitions.append(StateTransition(
        from_state=OrchestratorState.ANALYZING_RESULTS,
        to_state=OrchestratorState.GENERATING_CONFIG,
        condition=lambda ctx: (
            ctx.get("analysis_result", {}).get("success", False) and
            _has_pending_subtasks(ctx)  # Check if there are more subtasks to execute
        ),
        description="Analysis complete, more subtasks remaining → Continue to next subtask"
    ))

    # ⭐ CRITICAL FIX: For standard_calibration, complete after analysis
    transitions.append(StateTransition(
        from_state=OrchestratorState.ANALYZING_RESULTS,
        to_state=OrchestratorState.COMPLETED_SUCCESS,
        condition=lambda ctx: (
            ctx.get("analysis_result", {}).get("success", False) and
            ctx.get("intent_result", {}).get("task_type") != "iterative_optimization" and  # ⭐ Complete for non-iterative tasks
            not _has_pending_subtasks(ctx)  # ⭐ AND no more subtasks remaining
        ),
        description="Analysis complete (standard task, no more subtasks) → Completed"
    ))

    transitions.append(StateTransition(
        from_state=OrchestratorState.ANALYZING_RESULTS,
        to_state=OrchestratorState.COMPLETED_SUCCESS,
        condition=lambda ctx: (
            ctx.get("analysis_result", {}).get("success", False) and
            ctx.get("intent_result", {}).get("task_type") == "iterative_optimization" and
            ctx.get("iteration_count", 0) >= ctx.get("max_iterations", 10)
        ),
        description="Max iterations reached (iterative task) → Completed"
    ))

    # ======== 成功终止 ========
    # ⭐ CRITICAL FIX: Check for pending subtasks before completing
    transitions.append(StateTransition(
        from_state=OrchestratorState.RESULTS_ACCEPTABLE,
        to_state=OrchestratorState.GENERATING_CONFIG,
        condition=lambda ctx: _has_pending_subtasks(ctx),
        description="Results acceptable but more subtasks remaining → Continue to next subtask"
    ))

    transitions.append(StateTransition(
        from_state=OrchestratorState.RESULTS_ACCEPTABLE,
        to_state=OrchestratorState.COMPLETED_SUCCESS,
        condition=lambda ctx: not _has_pending_subtasks(ctx),
        description="Results acceptable and no more subtasks → Completed success"
    ))

    return transitions
