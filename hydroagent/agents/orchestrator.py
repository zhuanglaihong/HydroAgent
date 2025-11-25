"""
Author: Claude & zhuanglaihong
Date: 2025-01-20 19:55:00
LastEditTime: 2025-01-20 19:55:00
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
        **kwargs
    ):
        """
        Initialize the Orchestrator.

        Args:
            llm_interface: LLM API interface
            workspace_root: Root directory for all workspaces
            show_progress: Whether to show hydromodel execution progress
            enable_code_gen: Whether to enable code generation in DeveloperAgent
            enable_checkpoint: Whether to enable checkpoint/resume functionality
            **kwargs: Additional configuration
        """
        workspace_root = workspace_root or Path.cwd() / "results"
        super().__init__(
            name="Orchestrator",
            llm_interface=llm_interface,
            workspace_dir=workspace_root,
            **kwargs
        )

        self.workspace_root = workspace_root
        self.show_progress = show_progress
        self.enable_code_gen = enable_code_gen
        self.enable_checkpoint = enable_checkpoint
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
        """
        from .intent_agent import IntentAgent
        from .config_agent import ConfigAgent
        from .runner_agent import RunnerAgent
        from .developer_agent import DeveloperAgent

        logger.info("[Orchestrator] Initializing sub-agents...")

        self.intent_agent = IntentAgent(llm_interface=self.llm)
        self.config_agent = ConfigAgent(
            llm_interface=self.llm,
            workspace_dir=self.current_workspace
        )
        self.runner_agent = RunnerAgent(
            llm_interface=self.llm,
            workspace_dir=self.current_workspace,
            show_progress=self.show_progress
        )
        self.developer_agent = DeveloperAgent(
            llm_interface=self.llm,
            workspace_dir=self.current_workspace,
            enable_code_gen=self.enable_code_gen
        )

        logger.info("[Orchestrator] All sub-agents initialized")

    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        uid = str(uuid.uuid4())[:8]
        return f"session_{timestamp}_{uid}"

    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main orchestration logic - coordinates all 4 agents.
        主编排逻辑 - 协调全部4个智能体。

        Args:
            input_data: User query and context
                {
                    "query": str,
                    "mode": str (optional: "calibration", "evaluation", "simulation"),
                    "context": dict (optional: additional context)
                }

        Returns:
            Dict containing orchestration results
                {
                    "success": bool,
                    "session_id": str,
                    "workspace": str,
                    "intent": dict,
                    "config": dict,
                    "execution": dict,
                    "analysis": dict,
                    "summary": str
                }
        """
        query = input_data.get("query", "")

        if not query:
            return {
                "success": False,
                "error": "No query provided",
                "session_id": self.current_session_id
            }

        logger.info(f"[Orchestrator] Processing query: {query}")

        # Ensure session is started
        if self.current_session_id is None:
            logger.info("[Orchestrator] No active session, starting new session...")
            self.start_new_session()

        # Add to conversation history
        self.conversation_history.append({
            "role": "user",
            "content": query,
            "timestamp": datetime.now().isoformat()
        })

        import time
        start_time = time.time()

        try:
            # Step 1: Intent recognition
            intent_result = self._process_intent(query)

            # Step 2: Configuration generation
            config_result = self._generate_config(intent_result)

            # Step 3: Execution
            execution_result = self._execute_workflow(config_result)

            # Step 4: Result analysis
            analysis_result = self._analyze_results(execution_result)

            # Check overall success
            overall_success = (
                intent_result.get("success", False) and
                config_result.get("success", False) and
                execution_result.get("success", False)
                # Note: analysis can fail but we still consider it success if execution worked
            )

            elapsed_time = time.time() - start_time

            # Generate summary
            summary = self._generate_summary(
                intent_result, config_result, execution_result, analysis_result
            )

            # Add to conversation history
            self.conversation_history.append({
                "role": "assistant",
                "content": summary,
                "timestamp": datetime.now().isoformat()
            })

            result = {
                "success": overall_success,
                "session_id": self.current_session_id,
                "workspace": str(self.current_workspace),
                "intent": intent_result,
                "config": config_result,
                "execution": execution_result,
                "analysis": analysis_result,
                "summary": summary,
                "elapsed_time": elapsed_time
            }

            logger.info(f"[Orchestrator] Pipeline completed in {elapsed_time:.1f}s")
            return result

        except Exception as e:
            logger.error(f"[Orchestrator] Pipeline failed: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "session_id": self.current_session_id,
                "workspace": str(self.current_workspace) if self.current_workspace else None
            }

    def _generate_summary(
        self, intent_result: Dict, config_result: Dict,
        execution_result: Dict, analysis_result: Dict
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
            raise RuntimeError("IntentAgent not initialized. Call start_new_session() first.")

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
            raise RuntimeError("ConfigAgent not initialized. Call start_new_session() first.")

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
            raise RuntimeError("RunnerAgent not initialized. Call start_new_session() first.")

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
            raise RuntimeError("DeveloperAgent not initialized. Call start_new_session() first.")

        result = self.developer_agent.process(execution_result)

        if not result.get("success"):
            logger.warning(f"[Orchestrator] Analysis completed with issues: {result.get('error')}")
            # Return result even if analysis has issues
            return result

        logger.info("[Orchestrator] Results analyzed successfully")
        return result

    def register_agents(
        self,
        intent_agent: 'IntentAgent',
        config_agent: 'ConfigAgent',
        runner_agent: 'RunnerAgent',
        developer_agent: 'DeveloperAgent'
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
