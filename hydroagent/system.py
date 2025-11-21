"""
Author: Claude & zhuanglaihong
Date: 2025-11-21 15:30:00
LastEditTime: 2025-11-21 15:30:00
LastEditors: Claude
Description: HydroAgent system API - unified interface for the entire system
             HydroAgent 系统API - 整个系统的统一接口
FilePath: \HydroAgent\hydroagent\system.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from typing import Dict, Any, Optional
from pathlib import Path
import logging

from .core.llm_interface import LLMInterface, create_llm_interface
from .agents.orchestrator import Orchestrator

logger = logging.getLogger(__name__)


class HydroAgent:
    """
    Main entry point for HydroAgent system.
    HydroAgent系统的主入口点。

    This class provides a simple, unified API for interacting with the
    entire HydroAgent multi-agent system.
    """

    def __init__(
        self,
        llm_interface: Optional[LLMInterface] = None,
        backend: str = "ollama",
        model: str = None,
        api_key: str = None,
        base_url: str = None,
        workspace_root: Optional[Path] = None,
        show_progress: bool = True,
        enable_code_gen: bool = True,
        **kwargs
    ):
        """
        Initialize HydroAgent system.

        Args:
            llm_interface: Pre-configured LLM interface (if provided, backend/model/api_key are ignored)
            backend: LLM backend ('ollama', 'openai', or 'api')
            model: Model name (default: 'qwen3:8b' for ollama, 'qwen-turbo' for api)
            api_key: API key for OpenAI-compatible APIs
            base_url: Base URL for OpenAI-compatible APIs
            workspace_root: Root directory for all workspaces
            show_progress: Whether to show hydromodel execution progress
            enable_code_gen: Whether to enable code generation in DeveloperAgent
            **kwargs: Additional configuration

        Example:
            >>> # Using Ollama
            >>> agent = HydroAgent(backend='ollama', model='qwen3:8b')
            >>>
            >>> # Using API
            >>> agent = HydroAgent(backend='api', model='qwen-turbo',
            ...                    api_key='your-key', base_url='your-url')
            >>>
            >>> # Process query
            >>> result = agent.run("率定GR4J模型，流域01013500")
        """
        # Create LLM interface if not provided
        if llm_interface is None:
            # Load config from definitions files
            try:
                from configs import definitions_private as config
            except ImportError:
                from configs import definitions as config

            # Determine model and backend
            if backend == "api":
                backend = "openai"

            if model is None:
                model = "qwen3:8b" if backend == "ollama" else "qwen-turbo"

            # Get API credentials
            if api_key is None:
                api_key = getattr(config, 'OPENAI_API_KEY', None)
            if base_url is None:
                base_url = getattr(config, 'OPENAI_BASE_URL', None)

            # Create LLM interface
            if backend == "ollama":
                llm_interface = create_llm_interface('ollama', model)
            elif backend == "openai":
                if not api_key:
                    raise ValueError(
                        "API key required for OpenAI backend. Please provide api_key parameter "
                        "or set OPENAI_API_KEY in configs/definitions_private.py"
                    )
                llm_interface = create_llm_interface(
                    'openai', model,
                    api_key=api_key,
                    base_url=base_url
                )
            else:
                raise ValueError(f"Unsupported backend: {backend}")

        self.llm = llm_interface
        self.orchestrator = Orchestrator(
            llm_interface=llm_interface,
            workspace_root=workspace_root,
            show_progress=show_progress,
            enable_code_gen=enable_code_gen,
            **kwargs
        )

        logger.info("HydroAgent system initialized")

    def run(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Run a query through the HydroAgent system.
        通过HydroAgent系统运行查询。

        Args:
            query: User query in natural language
            **kwargs: Additional context

        Returns:
            Dict containing complete pipeline results

        Example:
            >>> agent = HydroAgent()
            >>> result = agent.run("率定GR4J模型，流域01013500")
            >>> print(result['summary'])
        """
        return self.orchestrator.process({"query": query, **kwargs})

    def start_session(self, session_id: Optional[str] = None) -> str:
        """
        Start a new session.
        开始新会话。

        Args:
            session_id: Optional custom session ID

        Returns:
            Session ID

        Example:
            >>> agent = HydroAgent()
            >>> session_id = agent.start_session()
            >>> print(f"Session started: {session_id}")
        """
        return self.orchestrator.start_new_session(session_id)

    def get_workspace(self) -> Optional[Path]:
        """
        Get current workspace directory.
        获取当前工作目录。

        Returns:
            Path to workspace directory
        """
        return self.orchestrator.get_workspace_path()

    def get_history(self) -> list:
        """
        Get conversation history for current session.
        获取当前会话的对话历史。

        Returns:
            List of conversation messages
        """
        return self.orchestrator.get_conversation_history()


def create_hydro_agent(
    backend: str = "ollama",
    model: str = None,
    **kwargs
) -> HydroAgent:
    """
    Factory function to create HydroAgent instance.
    创建HydroAgent实例的工厂函数。

    Args:
        backend: LLM backend ('ollama', 'openai', or 'api')
        model: Model name
        **kwargs: Additional configuration

    Returns:
        HydroAgent instance

    Example:
        >>> agent = create_hydro_agent(backend='ollama', model='qwen3:8b')
        >>> result = agent.run("评估XAJ模型")
    """
    return HydroAgent(backend=backend, model=model, **kwargs)


# Convenience function for quick usage
def run_query(query: str, backend: str = "ollama", model: str = None, **kwargs) -> Dict[str, Any]:
    """
    Quick function to run a single query.
    快速运行单个查询的函数。

    Args:
        query: User query
        backend: LLM backend
        model: Model name
        **kwargs: Additional configuration

    Returns:
        Pipeline results

    Example:
        >>> from hydroagent import run_query
        >>> result = run_query("率定GR4J模型，流域01013500")
        >>> print(result['summary'])
    """
    agent = HydroAgent(backend=backend, model=model, **kwargs)
    return agent.run(query)
