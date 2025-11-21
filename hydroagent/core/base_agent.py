"""
Author: Claude & zhuanglaihong
Date: 2025-01-20 19:55:00
LastEditTime: 2025-01-20 19:55:00
LastEditors: Claude
Description: Base agent class defining common interfaces and prompt handling for all agents
             智能体基类 - 定义所有智能体的通用接口和提示词处理
FilePath: \HydroAgent\hydroagent\core\base_agent.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all HydroAgent agents.
    所有 HydroAgent 智能体的抽象基类。

    This class defines the common interface and shared functionality
    that all specialized agents must implement.
    定义所有专门智能体必须实现的通用接口和共享功能。

    Key responsibilities:
    - Prompt management and generation
    - Context handling
    - LLM interaction interface
    - Error handling and logging
    """

    def __init__(
        self,
        name: str,
        llm_interface: 'LLMInterface',
        system_prompt: Optional[str] = None,
        workspace_dir: Optional[Path] = None
    ):
        """
        Initialize base agent.

        Args:
            name: Agent identifier name
            llm_interface: LLM API interface instance
            system_prompt: System-level instruction for this agent
            workspace_dir: Working directory for file I/O
        """
        self.name = name
        self.llm = llm_interface
        self.system_prompt = system_prompt or self._get_default_system_prompt()
        self.workspace_dir = workspace_dir or Path.cwd() / "workspace"
        self.context: Dict[str, Any] = {}

        logger.info(f"Initialized {self.__class__.__name__}: {self.name}")

    @abstractmethod
    def _get_default_system_prompt(self) -> str:
        """
        Return the default system prompt for this agent.
        Each agent must implement its own specialized prompt.

        Returns:
            str: Default system prompt
        """
        pass

    @abstractmethod
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main processing method for the agent.
        智能体的主处理方法。

        Args:
            input_data: Input data dictionary containing task information

        Returns:
            Dict containing processing results and metadata
        """
        pass

    def update_context(self, key: str, value: Any) -> None:
        """
        Update agent's internal context.
        更新智能体的内部上下文。

        Args:
            key: Context key
            value: Context value
        """
        self.context[key] = value
        logger.debug(f"[{self.name}] Context updated: {key}")

    def get_context(self, key: str, default: Any = None) -> Any:
        """
        Retrieve value from context.

        Args:
            key: Context key
            default: Default value if key not found

        Returns:
            Context value or default
        """
        return self.context.get(key, default)

    def clear_context(self) -> None:
        """Clear all context data."""
        self.context.clear()
        logger.debug(f"[{self.name}] Context cleared")

    def call_llm(
        self,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Call LLM with the agent's system prompt.
        使用智能体的系统提示词调用 LLM。

        Args:
            user_prompt: User/task specific prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            LLM response text
        """
        try:
            response = self.llm.generate(
                system_prompt=self.system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens
            )
            logger.debug(f"[{self.name}] LLM call successful")
            return response
        except Exception as e:
            logger.error(f"[{self.name}] LLM call failed: {str(e)}")
            raise

    def ensure_workspace(self) -> Path:
        """
        Ensure workspace directory exists.
        确保工作目录存在。

        Returns:
            Path to workspace directory
        """
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        return self.workspace_dir

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name='{self.name}')>"
