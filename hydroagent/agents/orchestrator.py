"""
Author: Claude & zhuanglaihong
Date: 2025-01-25 11:00:00
LastEditTime: 2025-01-25 11:00:00
LastEditors: Claude
Description: Central orchestrator agent - v5.0 State Machine Driven Controller
             中央编排器智能体 - v5.0 状态机驱动控制器
FilePath: \HydroAgent\hydroagent\agents\orchestrator.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

v5.0 Architecture Update:
- State machine driven execution (vs fixed pipeline)
- Feedback routing between agents
- Goal tracking and trend analysis
- Automatic error recovery and retry
- Dynamic task planning (no hardcoded task types)
"""

from typing import Dict, Any, Optional, List
from pathlib import Path
import logging
import uuid
from datetime import datetime

from ..core.base_agent import BaseAgent
from ..core.llm_interface import LLMInterface
from ..utils.error_handler import handle_pipeline_error
from ..utils.result_serializer import sanitize_result
from ..core.state_machine import StateMachine, OrchestratorState
from ..core.goal_tracker import GoalTracker
from ..core.feedback_router import FeedbackRouter

logger = logging.getLogger(__name__)


class Orchestrator(BaseAgent):
    """
    v5.0 Central orchestrator agent - State Machine Driven Controller.
    中央编排器智能体 - 状态机驱动控制器。

    v5.0 Responsibilities:
    - **Decision Control**: Decide next action based on current state and feedback
    - **State Management**: Maintain global state machine and manage transitions
    - **Feedback Routing**: Route agent outputs to appropriate upstream agents
    - **Goal Tracking**: Monitor task goals, progress, and error trends
    - **Abort Judgment**: Decide termination based on multiple conditions
    - **Error Recovery**: Automatic retry and fallback strategies

    Key Differences from v3.5:
    - v3.5: Sequential execution (Intent → Plan → Config → Run → Analyze)
    - v5.0: State machine loop with dynamic decision making
    """

    def __init__(
        self,
        llm_interface: LLMInterface,
        workspace_root: Optional[Path] = None,
        show_progress: bool = True,
        enable_code_gen: bool = True,
        enable_checkpoint: bool = True,
        code_llm_interface: Optional[LLMInterface] = None,
        max_state_transitions: int = 100,
        enable_faiss: bool = False,  # 🆕 FAISS historical case learning
        faiss_timeout: int = 60,  # 🆕 FAISS initialization timeout
        **kwargs,
    ):
        """
        Initialize the Orchestrator (v5.0).

        Args:
            llm_interface: LLM API interface (通用模型)
            workspace_root: Root directory for all workspaces
            show_progress: Whether to show hydromodel execution progress
            enable_code_gen: Whether to enable code generation in DeveloperAgent
            enable_checkpoint: Whether to enable checkpoint/resume functionality
            code_llm_interface: Optional code-specialized LLM (代码专用模型, v4.0)
            max_state_transitions: Maximum state transitions before aborting (防止无限循环)
            enable_faiss: 🆕 Whether to enable FAISS semantic search (default: False)
            faiss_timeout: 🆕 FAISS initialization timeout in seconds (default: 60)
            **kwargs: Additional configuration
        """
        workspace_root = workspace_root or Path.cwd() / "results"
        super().__init__(
            name="Orchestrator",
            llm_interface=llm_interface,
            workspace_dir=workspace_root,
            **kwargs,
        )

        self.workspace_root = workspace_root
        self.show_progress = show_progress
        self.enable_code_gen = enable_code_gen
        self.enable_checkpoint = enable_checkpoint
        self.code_llm = code_llm_interface  # 🆕 v4.0: 代码专用LLM
        self.max_state_transitions = max_state_transitions
        self.enable_faiss = enable_faiss  # 🆕 FAISS config
        self.faiss_timeout = faiss_timeout  # 🆕 Timeout config

        # Session state
        self.current_session_id: Optional[str] = None
        self.current_workspace: Optional[Path] = None
        self.conversation_history: List[Dict[str, Any]] = []
        self.checkpoint_manager = None  # Will be initialized per session

        # 🆕 v5.0: State Machine Components
        self.state_machine: Optional[StateMachine] = None
        self.goal_tracker: Optional[GoalTracker] = None
        self.feedback_router: FeedbackRouter = FeedbackRouter()

        # Global execution context (shared across state transitions)
        self.execution_context: Dict[str, Any] = {}

        # Sub-agents will be initialized when session starts
        self.intent_agent = None
        self.task_planner = None
        self.interpreter_agent = None
        self.config_agent = None  # Alias for interpreter_agent
        self.runner_agent = None
        self.developer_agent = None

        logger.info("Orchestrator v5.0 initialized (State Machine Driven)")

    def _get_default_system_prompt(self) -> str:
        """Return default system prompt for orchestrator."""
        return """You are the central orchestrator of HydroAgent, a multi-agent system for hydrological modeling.

Your responsibilities:
1. Analyze user queries and determine which agents to invoke
2. Coordinate information flow between agents
3. Maintain conversation context and state
4. Handle errors and retry logic
5. Present final results to the user

Available agents:
- IntentAgent: Parse user intent and validate data availability
- ConfigAgent: Generate hydromodel configuration files
- RunnerAgent: Execute hydromodel and monitor progress
- DeveloperAgent: Analyze results and generate custom code

Always think step-by-step and explain your reasoning."""

    def start_new_session(self, session_id: Optional[str] = None) -> str:
        """
        Start a new workflow session and initialize all sub-agents.
        开始一个新的工作流会话并初始化所有子智能体。

        Args:
            session_id: Optional custom session ID

        Returns:
            Session ID
        """
        self.current_session_id = session_id or self._generate_session_id()
        self.current_workspace = self.workspace_root / self.current_session_id
        self.current_workspace.mkdir(parents=True, exist_ok=True)

        self.conversation_history.clear()
        self.clear_context()

        # Initialize checkpoint manager if enabled
        if self.enable_checkpoint:
            from ..core.checkpoint_manager import CheckpointManager

            self.checkpoint_manager = CheckpointManager(self.current_workspace)
            logger.info("Checkpoint manager initialized")

        # Initialize all sub-agents for this session
        self._initialize_agents()

        logger.info(f"Started new session: {self.current_session_id}")
        logger.info(f"Workspace: {self.current_workspace}")

        return self.current_session_id

    def resume_session(self, workspace_path: Path) -> str:
        """
        Resume a previous session from checkpoint.
        从检查点恢复之前的会话。

        Args:
            workspace_path: Path to the workspace containing checkpoint.json

        Returns:
            Session ID

        Raises:
            FileNotFoundError: If checkpoint file not found
            RuntimeError: If checkpoint cannot be resumed
        """
        workspace_path = Path(workspace_path)
        if not workspace_path.exists():
            raise FileNotFoundError(f"Workspace not found: {workspace_path}")

        # Initialize checkpoint manager and load checkpoint
        from ..core.checkpoint_manager import CheckpointManager

        self.checkpoint_manager = CheckpointManager(workspace_path)

        if not self.checkpoint_manager.exists():
            raise FileNotFoundError(f"No checkpoint found in: {workspace_path}")

        self.checkpoint_manager.load()

        if not self.checkpoint_manager.can_resume():
            raise RuntimeError(
                f"Cannot resume: experiment already completed or no pending tasks"
            )

        # Restore session state
        self.current_session_id = workspace_path.name
        self.current_workspace = workspace_path

        # Initialize agents
        self._initialize_agents()

        progress = self.checkpoint_manager.get_progress_summary()
        logger.info(f"Resumed session: {self.current_session_id}")
        logger.info(
            f"Progress: {progress['completed']}/{progress['total']} tasks completed"
        )

        return self.current_session_id

    def _initialize_agents(self) -> None:
        """
        Initialize all sub-agents with current workspace.
        使用当前工作空间初始化所有子智能体。

        完整的5-Agent架构：
        IntentAgent → TaskPlanner → InterpreterAgent → RunnerAgent → DeveloperAgent
        """
        from .intent_agent import IntentAgent
        from .task_planner import TaskPlanner
        from .interpreter_agent import InterpreterAgent
        from .runner_agent import RunnerAgent
        from .developer_agent import DeveloperAgent
        from ..core.prompt_pool import PromptPool

        logger.info("[Orchestrator] Initializing 5-Agent pipeline...")

        # Agent 1: Intent Recognition
        self.intent_agent = IntentAgent(llm_interface=self.llm)

        # Agent 2: Task Planning (多任务拆解)
        # ⭐ PERFORMANCE: FAISS controlled by enable_faiss parameter
        # - False (default): Fast startup, rule-based matching
        # - True: Semantic search + incremental learning (5-10s startup, needs network)

        logger.info(f"[Orchestrator] Initializing PromptPool (FAISS={'enabled' if self.enable_faiss else 'disabled'})")

        if self.enable_faiss:
            # ⭐ Timeout protection for FAISS initialization (cross-platform)
            import threading
            import time

            prompt_pool = None
            exception_holder = [None]  # Mutable to capture exceptions from thread

            def init_faiss_with_timeout():
                try:
                    nonlocal prompt_pool
                    prompt_pool = PromptPool(
                        pool_dir=self.current_workspace / "prompt_pool",
                        use_faiss=True,
                        llm_interface=self.llm
                    )
                except Exception as e:
                    exception_holder[0] = e

            # Start FAISS initialization in separate thread
            init_thread = threading.Thread(target=init_faiss_with_timeout, daemon=True)
            init_thread.start()
            init_thread.join(timeout=self.faiss_timeout)

            if init_thread.is_alive():
                # Timeout occurred
                logger.warning(f"[Orchestrator] FAISS initialization timeout ({self.faiss_timeout}s)")
                logger.warning("[Orchestrator] Possible causes: Slow network, first-time model download, slow CPU")
                logger.info("[Orchestrator] Falling back to rule-based PromptPool")

                prompt_pool = PromptPool(
                    pool_dir=self.current_workspace / "prompt_pool",
                    use_faiss=False  # Fallback to rule-based
                )
            elif exception_holder[0] is not None:
                # Exception occurred
                e = exception_holder[0]
                logger.warning(f"[Orchestrator] FAISS initialization failed ({e.__class__.__name__}): {e}")
                logger.warning("[Orchestrator] Possible causes: Missing dependencies (faiss-cpu, sentence-transformers)")
                logger.info("[Orchestrator] Falling back to rule-based PromptPool")

                prompt_pool = PromptPool(
                    pool_dir=self.current_workspace / "prompt_pool",
                    use_faiss=False  # Fallback to rule-based
                )
            else:
                # Success
                logger.info(f"[Orchestrator] FAISS initialized successfully")
        else:
            prompt_pool = PromptPool(
                pool_dir=self.current_workspace / "prompt_pool",
                use_faiss=False
            )

        self.task_planner = TaskPlanner(
            llm_interface=self.llm,
            prompt_pool=prompt_pool,
            workspace_dir=self.current_workspace,
        )

        # Agent 3: Configuration Interpretation (配置生成)
        self.interpreter_agent = InterpreterAgent(
            llm_interface=self.llm, workspace_dir=self.current_workspace
        )

        # Agent 4: Model Runner (执行) - v4.0: 支持代码生成
        self.runner_agent = RunnerAgent(
            llm_interface=self.llm,
            workspace_dir=self.current_workspace,
            show_progress=self.show_progress,
            code_llm_interface=self.code_llm,  # 🆕 v4.0: 传入代码专用LLM
        )

        # Agent 5: Result Developer (分析)
        self.developer_agent = DeveloperAgent(
            llm_interface=self.llm, workspace_dir=self.current_workspace
        )

        # 保留旧的config_agent引用（向后兼容）
        self.config_agent = self.interpreter_agent

        logger.info("[Orchestrator] All 5 agents initialized")

    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        uid = str(uuid.uuid4())[:8]
        return f"session_{timestamp}_{uid}"

    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        🆕 v5.0 State Machine Driven Process Loop.
        状态机驱动的处理循环。

        Key Changes from v3.5:
        - ❌ No fixed pipeline (Intent → Plan → Config → Run → Analyze)
        - ✅ State machine loop with dynamic decision making
        - ✅ Automatic error recovery and retry
        - ✅ Feedback routing between agents
        - ✅ Goal-driven termination (not just sequential completion)

        Args:
            input_data: User query and context
                {
                    "query": str,
                    "mode": str (optional),
                    "use_mock": bool (optional),
                    "use_v5": bool (optional: True to enable v5.0 state machine)
                }

        Returns:
            Orchestration results with state machine history
        """
        query = input_data.get("query", "")
        use_mock = input_data.get("use_mock", False)
        use_v5 = input_data.get("use_v5", True)  # v5.0 by default

        if not query:
            return {
                "success": False,
                "error": "No query provided",
                "session_id": self.current_session_id,
            }

        logger.info(f"[Orchestrator v5.0] Processing query: {query}")

        # Ensure session is started
        if self.current_session_id is None:
            self.start_new_session()

        # Add to conversation history
        self.conversation_history.append(
            {"role": "user", "content": query, "timestamp": datetime.now().isoformat()}
        )

        import time
        start_time = time.time()

        try:
            if use_v5:
                # 🆕 v5.0: State Machine Driven
                result = self._process_v5_state_machine(query, use_mock)
            else:
                # Legacy v3.5 pipeline (kept for compatibility)
                result = self._process_v3_pipeline(query, use_mock)

            elapsed_time = time.time() - start_time
            result["elapsed_time"] = elapsed_time

            logger.info(f"[Orchestrator] Completed in {elapsed_time:.1f}s")
            return result

        except Exception as e:
            return handle_pipeline_error(
                error=e,
                phase="unknown",
                session_id=self.current_session_id,
                workspace=self.current_workspace,
                checkpoint_manager=self.checkpoint_manager,
            )

    def _process_v5_state_machine(
        self, query: str, use_mock: bool = False
    ) -> Dict[str, Any]:
        """
        🆕 v5.0 State Machine Driven Process.
        状态机驱动的核心处理逻辑。

        State Machine Loop:
        1. Initialize state machine and goal tracker
        2. Loop until terminal state reached:
           - Execute action for current state
           - Collect result/feedback
           - Route feedback to appropriate agent
           - Update goal tracker
           - Transition to next state
        3. Return final result

        Args:
            query: User query
            use_mock: Whether to use mock mode

        Returns:
            Final orchestration result
        """
        from ..core.state_machine import StateMachine, OrchestratorState, build_default_transitions
        from ..core.goal_tracker import create_calibration_goal_tracker

        logger.info("[Orchestrator] 🚀 Starting v5.0 State Machine execution")

        # ====================================================================
        # Phase 1: Initialize State Machine and Checkpoint
        # ====================================================================
        self.state_machine = StateMachine(max_transitions=self.max_state_transitions)
        self.state_machine.add_transitions(build_default_transitions())

        # Initialize checkpoint if enabled
        if self.enable_checkpoint and self.checkpoint_manager:
            self.checkpoint_manager.initialize(
                experiment_name=f"session_{self.current_session_id}",
                query=query,
                total_tasks=0,  # Will be updated after task planning
            )
            logger.info("[Orchestrator] Checkpoint initialized for v5.0")

        # Initialize execution context
        self.execution_context = {
            "query": query,
            "use_mock": use_mock,
            "session_id": self.current_session_id,
            "workspace": str(self.current_workspace),
            "retry_counts": {},
            "iteration_count": 0,
            "max_iterations": 10,
            "nse_target": 0.7,
        }

        # Will be initialized after intent analysis
        self.goal_tracker = None

        # ====================================================================
        # Phase 2: State Machine Loop
        # ====================================================================
        logger.info("[Orchestrator] Starting state machine loop...")

        while not self.state_machine.is_terminal_state():
            current_state = self.state_machine.current_state
            logger.info(f"[StateMachine] Current state: {current_state.name}")

            # Execute action for current state
            try:
                state_result = self._execute_state_action(current_state)
            except Exception as e:
                logger.error(f"[StateMachine] Error in state {current_state.name}: {str(e)}", exc_info=True)
                # Mark as unrecoverable failure
                self.execution_context["error"] = str(e)
                self.state_machine.update_context({"execution_result": {"success": False, "retryable": False}})
                self.state_machine.transition()
                continue

            # Update execution context with result
            self.execution_context.update(state_result.get("context_updates", {}))

            # Route feedback (if applicable)
            if "agent_result" in state_result:
                routing_decision = self.feedback_router.route_feedback(
                    source_agent=state_result.get("source_agent", "Unknown"),
                    feedback=state_result["agent_result"],
                    orchestrator_context=self.execution_context,
                )

                logger.info(f"[FeedbackRouter] Action: {routing_decision.get('action')}")
                self.execution_context["routing_decision"] = routing_decision

            # Update goal tracker (if initialized and result available)
            if self.goal_tracker and "execution_result" in self.execution_context:
                exec_result = self.execution_context["execution_result"]
                if exec_result.get("success"):
                    self.goal_tracker.update(exec_result)

                    # Check termination conditions
                    should_terminate, reason = self.goal_tracker.should_terminate()
                    if should_terminate:
                        logger.info(f"[GoalTracker] Termination triggered: {reason}")
                        self.execution_context["termination_reason"] = reason

            # Transition to next state
            next_state = self.state_machine.transition(self.execution_context)

            if next_state == current_state and not self.state_machine.is_terminal_state():
                logger.warning(f"[StateMachine] No transition from {current_state.name}, aborting")
                break

        # ====================================================================
        # Phase 3: Collect Final Result
        # ====================================================================
        final_state = self.state_machine.current_state
        logger.info(f"[StateMachine] Reached terminal state: {final_state.name}")

        # Determine overall success
        overall_success = final_state == OrchestratorState.COMPLETED_SUCCESS

        # Generate summary
        summary = self._generate_state_machine_summary(self.execution_context, self.state_machine)

        result = {
            "success": overall_success,
            "session_id": self.current_session_id,
            "workspace": str(self.current_workspace),
            "final_state": final_state.name,
            "intent": self.execution_context.get("intent_result"),
            "task_plan": self.execution_context.get("task_plan"),
            "execution_results": self.execution_context.get("execution_results", []),
            "analysis": self.execution_context.get("analysis_result"),
            "summary": summary,
            "state_history": self.state_machine.state_history,
            "total_transitions": self.state_machine.transition_count,
        }

        # Add error information if failed
        if not overall_success:
            error_msg = self.execution_context.get("error", "Unknown error")
            error_phase = self.execution_context.get("error_phase", "unknown")
            result["error"] = error_msg
            result["error_phase"] = error_phase
            logger.error(f"[Orchestrator] Task failed in {error_phase}: {error_msg}")

        if self.goal_tracker:
            result["goal_progress"] = self.goal_tracker.get_progress_summary()

        # Mark checkpoint as completed or failed
        if self.checkpoint_manager:
            if overall_success:
                analysis_result = self.execution_context.get("analysis_result", {})
                self.checkpoint_manager.mark_experiment_completed(analysis_result)
                logger.info("[Orchestrator] Checkpoint marked as completed")
            else:
                error_msg = self.execution_context.get("error", "Unknown error")
                self.checkpoint_manager.mark_experiment_failed(error_msg)
                logger.info("[Orchestrator] Checkpoint marked as failed")

        # 🔧 清理结果，确保可JSON序列化（移除numpy数组等）
        result = sanitize_result(result)

        return result

    def _execute_state_action(self, state: OrchestratorState) -> Dict[str, Any]:
        """
        Execute the action corresponding to a specific state.
        执行特定状态对应的动作。

        Args:
            state: Current state

        Returns:
            State execution result:
            {
                "context_updates": dict,  # Updates to execution context
                "source_agent": str,      # Agent that produced this result
                "agent_result": dict      # Raw agent result
            }
        """
        if state == OrchestratorState.WAITING_USER_INPUT:
            return {"context_updates": {"query": self.execution_context.get("query")}}

        elif state == OrchestratorState.ANALYZING_INTENT:
            intent_result = self._process_intent(self.execution_context["query"])
            intent_data = intent_result.get("intent_result", {})

            # Check if intent analysis failed
            if not intent_result.get("success", False):
                error_msg = intent_result.get("error", "Unknown intent analysis error")
                logger.error(f"[Orchestrator] Intent analysis failed: {error_msg}")
                return {
                    "context_updates": {
                        "intent_analysis_failed": True,
                        "error": error_msg,
                        "error_phase": "intent_analysis",
                    },
                    "source_agent": "IntentAgent",
                    "agent_result": intent_result,
                }

            # Initialize goal tracker after intent is known
            if intent_data.get("task_type") == "calibration":
                from ..core.goal_tracker import create_calibration_goal_tracker
                self.goal_tracker = create_calibration_goal_tracker(
                    target_nse=self.execution_context.get("nse_target", 0.7),
                    max_iterations=self.execution_context.get("max_iterations", 10),
                )

            # Save to checkpoint
            if self.checkpoint_manager:
                self.checkpoint_manager.update_phase("intent")
                self.checkpoint_manager.save_intent_result(intent_result)

            return {
                "context_updates": {
                    "intent_result": intent_data,
                    "intent_confidence": intent_data.get("confidence", 0),
                    "intent_analysis_failed": False,
                },
                "source_agent": "IntentAgent",
                "agent_result": intent_result,
            }

        elif state == OrchestratorState.PLANNING_TASKS:
            task_plan_result = self._plan_tasks(self.execution_context.get("intent_result", {}))
            task_plan = task_plan_result.get("task_plan", {})

            # Save to checkpoint and update total tasks
            if self.checkpoint_manager:
                self.checkpoint_manager.update_phase("planner")
                self.checkpoint_manager.save_task_plan(task_plan)
                logger.info(f"[Orchestrator] Checkpoint updated with {len(task_plan.get('subtasks', []))} subtasks")

            return {
                "context_updates": {"task_plan_result": task_plan_result, "task_plan": task_plan},
                "source_agent": "TaskPlanner",
                "agent_result": task_plan_result,
            }

        elif state == OrchestratorState.GENERATING_CONFIG:
            subtasks = self.execution_context.get("task_plan", {}).get("subtasks", [])
            intent_result = self.execution_context.get("intent_result", {})

            if not subtasks:
                return {
                    "context_updates": {"config_result": {"success": False}},
                }

            # ⭐ CRITICAL FIX: Select next pending subtask, not always the first one
            # Get completed subtask IDs
            execution_results = self.execution_context.get("execution_results", [])
            completed_ids = {r.get("task_id") for r in execution_results if r.get("success")}

            # Find first pending subtask
            subtask = None
            for st in subtasks:
                if st.get("task_id") not in completed_ids:
                    subtask = st
                    break

            if subtask is None:
                # All subtasks completed (should not reach here if state transitions are correct)
                logger.warning("[Orchestrator] All subtasks completed, but still in GENERATING_CONFIG state")
                return {
                    "context_updates": {"config_result": {"success": False, "error": "No pending subtasks"}},
                }

            logger.info(f"[Orchestrator] Generating config for next pending subtask: {subtask.get('task_id')}")
            subtask["user_query"] = self.execution_context.get("query", "")

            try:
                # ⭐ CRITICAL FIX: Route analysis/code_generation tasks differently
                # Analysis tasks don't need hydromodel configs - they need code generation
                task_type = subtask.get("task_type", "")

                if task_type in ["analysis", "code_generation", "visualization", "custom_analysis"]:
                    # Skip InterpreterAgent for these tasks - they don't need hydromodel configs
                    logger.info(f"[Orchestrator] Skipping InterpreterAgent for {task_type} task - using minimal metadata config")

                    # ⭐ Add previous_results to parameters for code generation
                    # This allows Code LLM to access data from previous calibration/evaluation tasks
                    task_params = subtask.get("parameters", {}).copy()
                    task_params["previous_results"] = self.execution_context.get("execution_results", [])

                    config_result = {
                        "success": True,
                        "config": {
                            "task_metadata": {
                                "task_type": task_type,
                                "task_id": subtask.get("task_id"),
                                "parameters": task_params,  # ⭐ Use enhanced parameters
                                "description": subtask.get("description", ""),
                                "user_query": subtask.get("user_query", ""),
                            }
                        },
                        "task_id": subtask.get("task_id")
                    }

                    return {
                        "context_updates": {
                            "config_result": config_result,
                            "current_config": config_result.get("config"),
                        },
                        "source_agent": "Orchestrator",  # Direct routing, no InterpreterAgent
                        "agent_result": config_result,
                    }

                # For calibration/evaluation/simulation, use InterpreterAgent normally
                config_result = self.interpreter_agent.process(
                    {"subtask": subtask, "intent_result": intent_result}
                )

                # Track retry count for config generation
                if not config_result.get("success"):
                    retry_count = self.execution_context.get("config_retry_count", 0) + 1
                    return {
                        "context_updates": {
                            "config_result": config_result,
                            "config_retry_count": retry_count,
                        },
                        "source_agent": "InterpreterAgent",
                        "agent_result": config_result,
                    }

                return {
                    "context_updates": {
                        "config_result": config_result,
                        "current_config": config_result.get("config"),
                    },
                    "source_agent": "InterpreterAgent",
                    "agent_result": config_result,
                }

            except Exception as e:
                logger.error(f"[Orchestrator] Config generation error: {str(e)}", exc_info=True)
                retry_count = self.execution_context.get("config_retry_count", 0) + 1
                return {
                    "context_updates": {
                        "config_result": {"success": False, "error": str(e)},
                        "config_retry_count": retry_count,
                    },
                }

        elif state == OrchestratorState.EXECUTING_TASK:
            config_result = self.execution_context.get("config_result", {})
            use_mock = self.execution_context.get("use_mock", False)

            # ⭐ CRITICAL FIX: Get task_id from config_result to track which subtask is being executed
            task_id = config_result.get("task_id")

            try:
                # Apply mock mode if requested
                if use_mock:
                    from unittest.mock import patch, Mock, MagicMock
                    mock_result = {
                        "best_params": {"x1": 350.0, "x2": 0.5},
                        "metrics": {"NSE": 0.68, "RMSE": 2.5},
                        "output_files": ["calibration_results.json"],
                    }
                    mock_hydromodel = MagicMock()
                    mock_hydromodel.calibrate = Mock(return_value=mock_result)
                    mock_hydromodel.evaluate = Mock(return_value=mock_result)

                    with patch.dict("sys.modules", {"hydromodel": mock_hydromodel}):
                        runner_result = self.runner_agent.process(config_result)
                else:
                    runner_result = self.runner_agent.process(config_result)

                # ⭐ CRITICAL FIX: Ensure task_id is in runner_result for tracking
                if task_id and "task_id" not in runner_result:
                    runner_result["task_id"] = task_id

                # Track retry count for execution
                if not runner_result.get("success"):
                    retry_count = self.execution_context.get("execution_retry_count", 0) + 1
                    # Save failed execution to checkpoint
                    if self.checkpoint_manager:
                        self.checkpoint_manager.update_phase("runner")
                        # Mark subtask as failed if we have task_id
                        task_plan = self.execution_context.get("task_plan", {})
                        subtasks = task_plan.get("subtasks", [])
                        if subtasks:
                            task_id = subtasks[0].get("task_id", "subtask_1")
                            self.checkpoint_manager.mark_subtask_failed(task_id, str(runner_result.get("error", "Unknown error")))

                    return {
                        "context_updates": {
                            "execution_result": runner_result,
                            "execution_retry_count": retry_count,
                        },
                        "source_agent": "RunnerAgent",
                        "agent_result": runner_result,
                    }

                # Save successful execution to checkpoint
                if self.checkpoint_manager:
                    self.checkpoint_manager.update_phase("runner")
                    task_plan = self.execution_context.get("task_plan", {})
                    subtasks = task_plan.get("subtasks", [])
                    # ⭐ CRITICAL FIX: Use actual task_id from runner_result, not always subtasks[0]
                    task_id = runner_result.get("task_id")
                    if not task_id and subtasks:
                        # Fallback: find the task_id from current config
                        config_result = self.execution_context.get("config_result", {})
                        task_id = config_result.get("task_id", subtasks[0].get("task_id", "subtask_1"))

                    if task_id:
                        self.checkpoint_manager.mark_subtask_completed(task_id, runner_result)
                        logger.info(f"[Orchestrator] Checkpoint: subtask {task_id} completed")

                # ⭐ CRITICAL FIX: Append to execution_results, don't overwrite
                existing_results = self.execution_context.get("execution_results", [])
                updated_results = existing_results + [runner_result]

                return {
                    "context_updates": {
                        "execution_result": runner_result,
                        "execution_results": updated_results,  # ⭐ Append, not overwrite
                    },
                    "source_agent": "RunnerAgent",
                    "agent_result": runner_result,
                }

            except Exception as e:
                logger.error(f"[Orchestrator] Execution error: {str(e)}", exc_info=True)
                retry_count = self.execution_context.get("execution_retry_count", 0) + 1
                return {
                    "context_updates": {
                        "execution_result": {"success": False, "error": str(e), "retryable": False},
                        "execution_retry_count": retry_count,
                    },
                }

        elif state == OrchestratorState.EXECUTION_FAILED_RETRYABLE:
            # Log retry attempt
            retry_count = self.execution_context.get("execution_retry_count", 0)
            logger.info(f"[Orchestrator] Execution failed, retry attempt {retry_count}/3")

            # Reset retry counter will be handled in next config generation
            return {"context_updates": {}}

        elif state == OrchestratorState.ANALYZING_RESULTS:
            execution_result = self.execution_context.get("execution_result", {})

            try:
                analysis_result = self._analyze_results(execution_result)

                # Extract NSE for goal tracking
                metrics = analysis_result.get("analysis", {}).get("metrics", {})
                nse = metrics.get("NSE", 0)

                return {
                    "context_updates": {
                        "analysis_result": analysis_result,
                        "nse": nse,
                    },
                    "source_agent": "DeveloperAgent",
                    "agent_result": analysis_result,
                }

            except Exception as e:
                logger.error(f"[Orchestrator] Analysis error: {str(e)}", exc_info=True)
                return {
                    "context_updates": {
                        "analysis_result": {"success": False, "error": str(e)},
                    },
                }

        elif state == OrchestratorState.ITERATING:
            # Increment iteration count
            iteration_count = self.execution_context.get("iteration_count", 0) + 1
            logger.info(f"[Orchestrator] Starting iteration {iteration_count}")

            # Reset retry counters for next iteration
            return {
                "context_updates": {
                    "iteration_count": iteration_count,
                    "config_retry_count": 0,
                    "execution_retry_count": 0,
                }
            }

        elif state in [OrchestratorState.INTENT_CONFIRMED, OrchestratorState.PLAN_READY,
                       OrchestratorState.CONFIG_READY, OrchestratorState.EXECUTION_SUCCESS,
                       OrchestratorState.RESULTS_ACCEPTABLE]:
            # These are intermediate states that don't require actions
            return {"context_updates": {}}

        elif state in [OrchestratorState.COMPLETED_SUCCESS, OrchestratorState.FAILED_UNRECOVERABLE]:
            # Terminal states - save to PromptPool if applicable
            if state == OrchestratorState.COMPLETED_SUCCESS:
                self._save_to_prompt_pool()

            return {"context_updates": {}}

        else:
            # No-op for other states
            logger.debug(f"[Orchestrator] No action defined for state: {state.name}")
            return {"context_updates": {}}

    def _save_to_prompt_pool(self):
        """
        Save successful execution to PromptPool for future retrieval.
        将成功的执行结果保存到PromptPool以供将来检索。
        """
        try:
            if not hasattr(self.task_planner, "prompt_pool") or not self.task_planner.prompt_pool:
                logger.debug("[Orchestrator] PromptPool not available, skipping save")
                return

            intent = self.execution_context.get("intent_result", {})
            config = self.execution_context.get("current_config", {})
            exec_result = self.execution_context.get("execution_result", {})

            if exec_result.get("success"):
                self.task_planner.prompt_pool.add_history(
                    task_type=intent.get("task_type", "unknown"),
                    intent=intent,
                    config=config,
                    result=exec_result,
                    success=True,
                )
                logger.info("[Orchestrator] Execution saved to PromptPool")

        except Exception as e:
            logger.error(f"[Orchestrator] Error saving to PromptPool: {str(e)}", exc_info=True)

    def _generate_state_machine_summary(
        self, context: Dict[str, Any], state_machine: StateMachine
    ) -> str:
        """Generate summary for state machine execution."""
        summary_parts = []

        # Intent summary
        intent = context.get("intent_result", {})
        summary_parts.append(f"任务类型: {intent.get('task_type', 'unknown').upper()}")
        summary_parts.append(f"模型: {intent.get('model_name', 'N/A')}")

        # State transitions
        summary_parts.append(f"\n状态转移次数: {state_machine.transition_count}")

        # Execution summary
        exec_results = context.get("execution_results", [])
        if exec_results:
            successful = sum(1 for r in exec_results if r.get("success", False))
            summary_parts.append(f"执行成功: {successful}/{len(exec_results)}")

        # Analysis summary
        analysis = context.get("analysis_result", {})
        if analysis.get("success"):
            analysis_data = analysis.get("analysis", {})
            quality = analysis_data.get("quality", "N/A")
            summary_parts.append(f"\n质量评估: {quality}")

        # Goal tracker summary
        if self.goal_tracker:
            progress = self.goal_tracker.get_progress_summary()
            current_val = progress.get('current_value')
            target_val = progress.get('target_value')

            if current_val is not None and target_val is not None:
                summary_parts.append(
                    f"\n目标进度: {current_val:.4f} / {target_val:.4f}"
                )

        return "\n".join(summary_parts)

    def _process_v3_pipeline(self, query: str, use_mock: bool = False) -> Dict[str, Any]:
        """
        Legacy v3.5 Fixed Pipeline (kept for backward compatibility).
        遗留的 v3.5 固定流程（保留以向后兼容）。

        This is the original 5-stage pipeline.
        """
        logger.info("[Orchestrator] Using legacy v3.5 pipeline")

        # Initialize checkpoint if enabled
        if self.enable_checkpoint and self.checkpoint_manager:
            self.checkpoint_manager.initialize(
                experiment_name=f"session_{self.current_session_id}",
                query=query,
                total_tasks=0,
            )

        # Step 1: Intent Recognition
        logger.info("[Orchestrator] Step 1/5: Intent Recognition")
        if self.checkpoint_manager:
            self.checkpoint_manager.update_phase("intent")

        intent_result = self._process_intent(query)
        intent_data = intent_result.get("intent_result", {})

        if self.checkpoint_manager:
            self.checkpoint_manager.save_intent_result(intent_result)

        # Step 2: Task Planning
        logger.info("[Orchestrator] Step 2/5: Task Planning")
        if self.checkpoint_manager:
            self.checkpoint_manager.update_phase("planner")

        task_plan_result = self._plan_tasks(intent_data)
        task_plan = task_plan_result.get("task_plan", {})
        subtasks = task_plan.get("subtasks", [])

        if self.checkpoint_manager:
            self.checkpoint_manager.save_task_plan(task_plan)

        logger.info(f"[Orchestrator] {len(subtasks)} subtasks planned")

        # Step 3: Configuration Generation
        logger.info("[Orchestrator] Step 3/5: Configuration Generation")
        if self.checkpoint_manager:
            self.checkpoint_manager.update_phase("interpreter")

        configs = self._generate_configs(subtasks, intent_data)
        logger.info(f"[Orchestrator] {len(configs)} configs generated")

        # Step 4: Execution
        logger.info("[Orchestrator] Step 4/5: Execution")
        if self.checkpoint_manager:
            self.checkpoint_manager.update_phase("runner")

        execution_results = self._execute_subtasks(configs, use_mock)
        logger.info(f"[Orchestrator] {len(execution_results)} tasks executed")

        # Step 5: Result Analysis
        logger.info("[Orchestrator] Step 5/5: Result Analysis")
        if self.checkpoint_manager:
            self.checkpoint_manager.update_phase("developer")

        combined_result = {
            "subtask_results": execution_results,
            "task_plan": task_plan,
            "intent": intent_data,
        }
        analysis_result = self._analyze_results(combined_result)

        # Check overall success
        all_tasks_success = all(r.get("success", False) for r in execution_results)
        overall_success = (
            intent_result.get("success", False)
            and task_plan_result.get("success", False)
            and all_tasks_success
        )

        # Mark experiment as completed
        if self.checkpoint_manager and overall_success:
            self.checkpoint_manager.mark_experiment_completed(analysis_result)

        # Save to PromptPool
        if hasattr(self.task_planner, "prompt_pool") and self.task_planner.prompt_pool:
            for i, subtask_result in enumerate(execution_results):
                self.task_planner.prompt_pool.add_history(
                    task_type=subtask_result.get("task_type", "unknown"),
                    intent=intent_data,
                    config=configs[i] if i < len(configs) else {},
                    result=subtask_result,
                    success=subtask_result.get("success", False),
                )

        # Generate summary
        summary = self._generate_summary_v2(
            intent_result, task_plan, execution_results, analysis_result
        )

        self.conversation_history.append(
            {"role": "assistant", "content": summary, "timestamp": datetime.now().isoformat()}
        )

        result = {
            "success": overall_success,
            "session_id": self.current_session_id,
            "workspace": str(self.current_workspace),
            "intent": intent_result,
            "task_plan": task_plan,
            "configs": configs,
            "execution_results": execution_results,
            "analysis": analysis_result,
            "summary": summary,
        }

        # Generate session summary
        try:
            session_summary = self.developer_agent.generate_session_summary(
                orchestrator_output=result,
                session_id=self.current_session_id,
                query=query,
            )
            result["session_summary"] = session_summary

            if session_summary.get("success"):
                logger.info(f"[Orchestrator] Session summary saved to: {session_summary['report_path']}")
        except Exception as e:
            logger.error(f"[Orchestrator] Session summary error: {str(e)}", exc_info=True)
            result["session_summary"] = {"success": False, "error": str(e)}

        # 🔧 清理结果，确保可JSON序列化（移除numpy数组等）
        result = sanitize_result(result)

        return result

    def _plan_tasks(self, intent_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        使用TaskPlanner拆解任务。

        Args:
            intent_result: IntentAgent的结果

        Returns:
            任务计划结果
        """
        if self.task_planner is None:
            raise RuntimeError("TaskPlanner not initialized")

        return self.task_planner.process({"intent_result": intent_result})

    def _generate_configs(
        self, subtasks: List[Dict], intent_result: Dict
    ) -> List[Dict]:
        """
        为每个子任务生成配置。

        Args:
            subtasks: 子任务列表
            intent_result: Intent结果

        Returns:
            配置列表
        """
        if self.interpreter_agent is None:
            raise RuntimeError("InterpreterAgent not initialized")

        configs = []
        for subtask in subtasks:
            # Add user query to subtask for LLM review context
            subtask["user_query"] = self.conversation_history[-1].get("content", "") if self.conversation_history else ""

            config_result = self.interpreter_agent.process(
                {"subtask": subtask, "intent_result": intent_result}
            )

            if not config_result.get("success"):
                error_type = config_result.get("error_type", "ConfigGenerationError")

                # For user-friendly errors (LLM review errors), raise ValueError
                if error_type == "LLMConfigReviewError":
                    logger.error(f"[Orchestrator] {config_result.get('error')}")
                    raise ValueError(config_result.get("error", "Configuration review failed"))
                else:
                    raise RuntimeError(f"Config generation failed for {subtask['task_id']}")

            configs.append(config_result)

        return configs

    def _execute_subtasks(
        self, configs: List[Dict], use_mock: bool = False
    ) -> List[Dict]:
        """
        执行所有子任务（支持checkpoint恢复）。

        Args:
            configs: 配置列表
            use_mock: 是否使用Mock模式

        Returns:
            执行结果列表
        """
        if self.runner_agent is None:
            raise RuntimeError("RunnerAgent not initialized")

        execution_results = []

        # Mock模式设置
        if use_mock:
            from unittest.mock import patch, Mock, MagicMock

            mock_result = {
                "best_params": {"x1": 350.0, "x2": 0.5},
                "metrics": {"NSE": 0.68, "RMSE": 2.5},
                "output_files": ["calibration_results.json"],
            }
            mock_hydromodel = MagicMock()
            mock_hydromodel.calibrate = Mock(return_value=mock_result)
            mock_hydromodel.evaluate = Mock(return_value=mock_result)

        for i, config_result in enumerate(configs, 1):
            task_id = config_result.get("task_id", f"task_{i}")

            # 检查checkpoint：是否已完成
            if self.checkpoint_manager:
                task_status = self.checkpoint_manager.checkpoint_data.get(
                    "subtasks_status", {}
                ).get(task_id, {})
                if task_status.get("status") == "completed":
                    logger.info(
                        f"[Orchestrator] Task {task_id} already completed (from checkpoint)"
                    )
                    execution_results.append(task_status.get("result", {}))
                    continue

            # 标记任务开始
            if self.checkpoint_manager:
                self.checkpoint_manager.mark_subtask_started(
                    task_id, config_result.get("config", {})
                )

            # 执行任务
            logger.info(f"[Orchestrator] Executing task {task_id} ({i}/{len(configs)})")

            try:
                if use_mock:
                    with patch.dict("sys.modules", {"hydromodel": mock_hydromodel}):
                        runner_result = self.runner_agent.process(config_result)
                else:
                    runner_result = self.runner_agent.process(config_result)

                # 🔧 清理runner_result，确保可JSON序列化
                runner_result = sanitize_result(runner_result)

                if not runner_result.get("success"):
                    logger.error(
                        f"[Orchestrator] Task {task_id} failed: {runner_result.get('error')}"
                    )
                    if self.checkpoint_manager:
                        self.checkpoint_manager.mark_subtask_failed(
                            task_id, runner_result.get("error", "Unknown error")
                        )
                    # 继续执行其他任务，不中断整个流程
                    execution_results.append(runner_result)
                    continue

                # 标记任务完成
                if self.checkpoint_manager:
                    self.checkpoint_manager.mark_subtask_completed(
                        task_id, runner_result
                    )

                execution_results.append(runner_result)

            except Exception as e:
                logger.error(
                    f"[Orchestrator] Task {task_id} exception: {str(e)}", exc_info=True
                )
                if self.checkpoint_manager:
                    self.checkpoint_manager.mark_subtask_failed(task_id, str(e))
                execution_results.append(
                    {"success": False, "task_id": task_id, "error": str(e)}
                )

        return execution_results

    def _generate_summary_v2(
        self,
        intent_result: Dict,
        task_plan: Dict,
        execution_results: List[Dict],
        analysis_result: Dict,
    ) -> str:
        """
        生成完整流程的摘要（支持多任务）。

        Args:
            intent_result: Intent结果
            task_plan: 任务计划
            execution_results: 执行结果列表
            analysis_result: 分析结果

        Returns:
            摘要文本
        """
        summary_parts = []

        # Intent summary
        intent_data = intent_result.get("intent_result", {})
        task_type = intent_data.get("task_type", "unknown")
        model = intent_data.get("model_name", "N/A")

        summary_parts.append(f"任务类型: {task_type.upper()}")
        summary_parts.append(f"模型: {model}")

        # Task plan summary
        subtasks = task_plan.get("subtasks", [])
        summary_parts.append(f"子任务数量: {len(subtasks)}")

        # Execution summary
        successful_tasks = sum(1 for r in execution_results if r.get("success", False))
        summary_parts.append(f"执行成功: {successful_tasks}/{len(execution_results)}")

        # Analysis summary
        if analysis_result.get("success"):
            # 🔧 v4.0: 支持多子任务分析结果展示
            if "subtask_analyses" in analysis_result:
                # 多子任务模式：逐个展示
                subtask_analyses = analysis_result.get("subtask_analyses", [])
                summary_parts.append(f"\n📊 详细结果:")

                for i, subtask_analysis in enumerate(subtask_analyses, 1):
                    analysis_data = subtask_analysis.get("analysis", {})
                    mode = subtask_analysis.get("mode", "unknown")

                    summary_parts.append(
                        f"\n  任务 {i}/{len(subtask_analyses)} ({mode}):"
                    )

                    # 率定/评估结果
                    if mode in ["calibrate", "evaluate"]:
                        quality = analysis_data.get("quality", "N/A")
                        metrics = analysis_data.get("metrics", {})

                        summary_parts.append(f"    质量: {quality}")
                        if "NSE" in metrics:
                            summary_parts.append(f"    NSE: {metrics['NSE']:.4f}")

                    # 🆕 v4.0: 自定义分析结果
                    elif mode == "custom_analysis":
                        exec_status = analysis_data.get("execution_status", "unknown")
                        code_location = analysis_data.get("code_location", "")
                        summary_parts.append(f"    {exec_status}")

                        if code_location:
                            summary_parts.append(f"    {code_location}")

                        # 显示输出文件
                        output_files = analysis_data.get("output_files", [])
                        if output_files:
                            summary_parts.append(
                                f"    📁 输出文件: {', '.join(output_files)}"
                            )

                        # 显示错误信息（如果失败）
                        if "error" in analysis_data:
                            error = analysis_data["error"]
                            summary_parts.append(f"    ⚠️ 错误: {error[:100]}...")

            else:
                # 单任务模式：原有逻辑
                analysis_data = analysis_result.get("analysis", {})
                quality = analysis_data.get("quality", "N/A")
                summary_parts.append(f"\n质量评估: {quality}")

                recommendations = analysis_data.get("recommendations", [])
                if recommendations:
                    summary_parts.append(f"\n改进建议:")
                    for i, rec in enumerate(recommendations[:3], 1):
                        summary_parts.append(f"  {i}. {rec}")

        return "\n".join(summary_parts)

    def _generate_summary(
        self,
        intent_result: Dict,
        config_result: Dict,
        execution_result: Dict,
        analysis_result: Dict,
    ) -> str:
        """
        Generate a summary of the entire pipeline execution.
        生成整个管道执行的摘要。

        Args:
            intent_result: Intent analysis result
            config_result: Config generation result
            execution_result: Execution result
            analysis_result: Analysis result

        Returns:
            Summary text
        """
        summary_parts = []

        # Intent summary
        intent_data = intent_result.get("intent_result", {})
        intent = intent_data.get("intent", "unknown")
        model = intent_data.get("model_name", "N/A")
        basin = intent_data.get("basin_id", "N/A")

        summary_parts.append(f"任务类型: {intent.upper()}")
        summary_parts.append(f"模型: {model}, 流域: {basin}")

        # Execution summary
        if execution_result.get("success"):
            result_data = execution_result.get("result", {})
            metrics = result_data.get("metrics", {})

            if metrics:
                summary_parts.append("\n性能指标:")
                for key, value in metrics.items():
                    summary_parts.append(f"  {key}: {value}")

        # Analysis summary
        if analysis_result.get("success"):
            analysis_data = analysis_result.get("analysis", {})
            quality = analysis_data.get("quality", "N/A")
            summary_parts.append(f"\n质量评估: {quality}")

            recommendations = analysis_data.get("recommendations", [])
            if recommendations:
                summary_parts.append(f"\n改进建议:")
                for i, rec in enumerate(recommendations[:3], 1):  # Show max 3
                    summary_parts.append(f"  {i}. {rec}")

        return "\n".join(summary_parts)

    def _process_intent(self, query: str) -> Dict[str, Any]:
        """
        Process user intent using IntentAgent.
        使用 IntentAgent 处理用户意图。

        Args:
            query: User query

        Returns:
            Intent analysis result
        """
        logger.info("[Orchestrator] Step 1/4: Processing intent...")

        if self.intent_agent is None:
            raise RuntimeError(
                "IntentAgent not initialized. Call start_new_session() first."
            )

        result = self.intent_agent.process({"query": query})

        if not result.get("success"):
            error_msg = result.get("error", "Unknown error")
            error_type = result.get("error_type", "IntentAnalysisError")

            # For user-friendly errors, return detailed message without wrapping
            if error_type in ["BasinIDValidationError", "AlgorithmParameterValidationError"]:
                logger.error(f"[Orchestrator] {error_msg}")
                # Return the error directly without wrapping in RuntimeError
                raise ValueError(error_msg)
            else:
                raise RuntimeError(f"Intent analysis failed: {error_msg}")

        logger.info(f"[Orchestrator] Intent: {result['intent_result'].get('intent')}")
        return result

    def _generate_config(self, intent_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate configuration using ConfigAgent.
        使用 ConfigAgent 生成配置。

        Args:
            intent_result: Result from IntentAgent

        Returns:
            Configuration generation result
        """
        logger.info("[Orchestrator] Step 2/4: Generating configuration...")

        if self.config_agent is None:
            raise RuntimeError(
                "ConfigAgent not initialized. Call start_new_session() first."
            )

        result = self.config_agent.process(intent_result)

        if not result.get("success"):
            raise RuntimeError(f"Config generation failed: {result.get('error')}")

        logger.info("[Orchestrator] Configuration generated successfully")
        return result

    def _execute_workflow(self, config_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute workflow using RunnerAgent.
        使用 RunnerAgent 执行工作流。

        Args:
            config_result: Result from ConfigAgent

        Returns:
            Execution result
        """
        logger.info("[Orchestrator] Step 3/4: Executing workflow...")

        if self.runner_agent is None:
            raise RuntimeError(
                "RunnerAgent not initialized. Call start_new_session() first."
            )

        result = self.runner_agent.process(config_result)

        if not result.get("success"):
            logger.error(f"[Orchestrator] Execution failed: {result.get('error')}")
            # Still return result for DeveloperAgent to analyze the failure
            return result

        logger.info("[Orchestrator] Workflow executed successfully")
        return result

    def _analyze_results(self, execution_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze results using DeveloperAgent.
        使用 DeveloperAgent 分析结果。

        Args:
            execution_result: Result from RunnerAgent

        Returns:
            Analysis result
        """
        logger.info("[Orchestrator] Step 4/4: Analyzing results...")

        if self.developer_agent is None:
            raise RuntimeError(
                "DeveloperAgent not initialized. Call start_new_session() first."
            )

        result = self.developer_agent.process(execution_result)

        if not result.get("success"):
            logger.warning(
                f"[Orchestrator] Analysis completed with issues: {result.get('error')}"
            )
            # Return result even if analysis has issues
            return result

        logger.info("[Orchestrator] Results analyzed successfully")
        return result

    def register_agents(
        self,
        intent_agent: "IntentAgent",
        config_agent: "ConfigAgent",
        runner_agent: "RunnerAgent",
        developer_agent: "DeveloperAgent",
    ) -> None:
        """
        Register all sub-agents.
        注册所有子智能体。

        Args:
            intent_agent: IntentAgent instance
            config_agent: ConfigAgent instance
            runner_agent: RunnerAgent instance
            developer_agent: DeveloperAgent instance
        """
        self.intent_agent = intent_agent
        self.config_agent = config_agent
        self.runner_agent = runner_agent
        self.developer_agent = developer_agent

        logger.info("All sub-agents registered")

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """
        Get conversation history for current session.

        Returns:
            List of conversation messages
        """
        return self.conversation_history.copy()

    def get_workspace_path(self) -> Optional[Path]:
        """
        Get current workspace path.

        Returns:
            Path to current workspace directory
        """
        return self.current_workspace
