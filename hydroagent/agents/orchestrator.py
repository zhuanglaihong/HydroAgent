"""
Author: Claude & zhuanglaihong
Date: 2025-11-20 19:55:00
LastEditTime: 2025-11-20 19:55:00
LastEditors: Claude
Description: Central orchestrator agent - the brain of HydroAgent system
             中央编排器智能体 - HydroAgent 系统的大脑
FilePath: \HydroAgent\hydroagent\agents\orchestrator.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from typing import Dict, Any, Optional, List
from pathlib import Path
import logging
import uuid
from datetime import datetime

from ..core.base_agent import BaseAgent
from ..core.llm_interface import LLMInterface
from ..utils.error_handler import handle_pipeline_error

logger = logging.getLogger(__name__)


class Orchestrator(BaseAgent):
    """
    Central orchestrator agent coordinating all sub-agents.
    中央编排器智能体，协调所有子智能体。

    Responsibilities:
    - Maintain conversation state and context
    - Manage workspace directory creation
    - Route tasks to appropriate agents
    - Handle multi-turn interactions
    - Aggregate results from sub-agents
    """

    def __init__(
        self,
        llm_interface: LLMInterface,
        workspace_root: Optional[Path] = None,
        show_progress: bool = True,
        enable_code_gen: bool = True,
        enable_checkpoint: bool = True,
        code_llm_interface: Optional[LLMInterface] = None,
        **kwargs,
    ):
        """
        Initialize the Orchestrator.

        Args:
            llm_interface: LLM API interface (通用模型)
            workspace_root: Root directory for all workspaces
            show_progress: Whether to show hydromodel execution progress
            enable_code_gen: Whether to enable code generation in DeveloperAgent
            enable_checkpoint: Whether to enable checkpoint/resume functionality
            code_llm_interface: Optional code-specialized LLM (代码专用模型, v4.0)
                                If provided, RunnerAgent will use it for code generation
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
        self.current_session_id: Optional[str] = None
        self.current_workspace: Optional[Path] = None
        self.conversation_history: List[Dict[str, Any]] = []
        self.checkpoint_manager = None  # Will be initialized per session

        # Sub-agents will be initialized when session starts
        self.intent_agent = None
        self.config_agent = None
        self.runner_agent = None
        self.developer_agent = None

        logger.info("Orchestrator initialized")

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
        prompt_pool = PromptPool(pool_dir=self.current_workspace / "prompt_pool")
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
        Main orchestration logic - coordinates all 5 agents (完整流程).
        主编排逻辑 - 协调全部5个智能体（完整流程）。

        完整的5-Agent流程：
        1. IntentAgent: 意图识别和任务类型判断
        2. TaskPlanner: 任务拆解（支持多任务：批量、重复、矩阵等）
        3. InterpreterAgent: 为每个子任务生成hydromodel配置
        4. RunnerAgent: 执行每个子任务（支持checkpoint）
        5. DeveloperAgent: 分析结果并生成报告

        Args:
            input_data: User query and context
                {
                    "query": str,
                    "mode": str (optional: "calibration", "evaluation", "simulation"),
                    "context": dict (optional: additional context),
                    "use_mock": bool (optional: 是否使用Mock模式)
                }

        Returns:
            Dict containing orchestration results
                {
                    "success": bool,
                    "session_id": str,
                    "workspace": str,
                    "intent": dict,
                    "task_plan": dict,
                    "configs": list,
                    "execution_results": list,
                    "analysis": dict,
                    "summary": str,
                    "elapsed_time": float
                }
        """
        query = input_data.get("query", "")
        use_mock = input_data.get("use_mock", False)

        if not query:
            return {
                "success": False,
                "error": "No query provided",
                "session_id": self.current_session_id,
            }

        logger.info(f"[Orchestrator] Processing query: {query}")

        # Ensure session is started
        if self.current_session_id is None:
            logger.info("[Orchestrator] No active session, starting new session...")
            self.start_new_session()

        # Initialize checkpoint if enabled
        if self.enable_checkpoint and self.checkpoint_manager:
            self.checkpoint_manager.initialize(
                experiment_name=f"session_{self.current_session_id}",
                query=query,
                total_tasks=0,  # Will be updated after TaskPlanner
            )

        # Add to conversation history
        self.conversation_history.append(
            {"role": "user", "content": query, "timestamp": datetime.now().isoformat()}
        )

        import time

        start_time = time.time()

        try:
            # ====================================================================
            # Step 1: Intent Recognition
            # ====================================================================
            logger.info("[Orchestrator] Step 1/5: Intent Recognition")
            if self.checkpoint_manager:
                self.checkpoint_manager.update_phase("intent")

            intent_result = self._process_intent(query)
            intent_data = intent_result.get("intent_result", {})

            if self.checkpoint_manager:
                self.checkpoint_manager.save_intent_result(intent_result)

            # ====================================================================
            # Step 2: Task Planning
            # ====================================================================
            logger.info("[Orchestrator] Step 2/5: Task Planning")
            if self.checkpoint_manager:
                self.checkpoint_manager.update_phase("planner")

            task_plan_result = self._plan_tasks(intent_data)
            task_plan = task_plan_result.get("task_plan", {})
            subtasks = task_plan.get("subtasks", [])

            if self.checkpoint_manager:
                self.checkpoint_manager.save_task_plan(task_plan)

            logger.info(f"[Orchestrator] {len(subtasks)} subtasks planned")

            # ====================================================================
            # Step 3: Configuration Generation
            # ====================================================================
            logger.info("[Orchestrator] Step 3/5: Configuration Generation")
            if self.checkpoint_manager:
                self.checkpoint_manager.update_phase("interpreter")

            configs = self._generate_configs(subtasks, intent_data)
            logger.info(f"[Orchestrator] {len(configs)} configs generated")

            # ====================================================================
            # Step 4: Execution (支持多任务 + checkpoint)
            # ====================================================================
            logger.info("[Orchestrator] Step 4/5: Execution")
            if self.checkpoint_manager:
                self.checkpoint_manager.update_phase("runner")

            execution_results = self._execute_subtasks(configs, use_mock)
            logger.info(f"[Orchestrator] {len(execution_results)} tasks executed")

            # ====================================================================
            # Step 5: Result Analysis
            # ====================================================================
            logger.info("[Orchestrator] Step 5/5: Result Analysis")
            if self.checkpoint_manager:
                self.checkpoint_manager.update_phase("developer")

            # 合并所有执行结果用于分析
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

            elapsed_time = time.time() - start_time

            # Mark experiment as completed in checkpoint
            if self.checkpoint_manager and overall_success:
                self.checkpoint_manager.mark_experiment_completed(analysis_result)

            # Save history to PromptPool (for future case retrieval)
            if (
                hasattr(self.task_planner, "prompt_pool")
                and self.task_planner.prompt_pool
            ):
                for i, subtask_result in enumerate(execution_results):
                    self.task_planner.prompt_pool.add_history(
                        task_type=subtask_result.get("task_type", "unknown"),
                        intent=intent_data,
                        config=configs[i] if i < len(configs) else {},
                        result=subtask_result,
                        success=subtask_result.get("success", False),
                    )
                logger.info(
                    f"[Orchestrator] Added {len(execution_results)} records to PromptPool history"
                )

            # Generate summary
            summary = self._generate_summary_v2(
                intent_result, task_plan, execution_results, analysis_result
            )

            # Add to conversation history
            self.conversation_history.append(
                {
                    "role": "assistant",
                    "content": summary,
                    "timestamp": datetime.now().isoformat(),
                }
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
                "elapsed_time": elapsed_time,
            }

            logger.info(f"[Orchestrator] Pipeline completed in {elapsed_time:.1f}s")
            return result

        except Exception as e:
            # 使用优雅的错误处理器 (集中错误处理逻辑)
            return handle_pipeline_error(
                error=e,
                phase=(
                    self.checkpoint_manager.checkpoint_data.get(
                        "current_phase", "unknown"
                    )
                    if self.checkpoint_manager
                    else "unknown"
                ),
                session_id=self.current_session_id,
                workspace=self.current_workspace,
                checkpoint_manager=self.checkpoint_manager,
            )

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
            config_result = self.interpreter_agent.process(
                {"subtask": subtask, "intent_result": intent_result}
            )

            if not config_result.get("success"):
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
            raise RuntimeError(f"Intent analysis failed: {result.get('error')}")

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
