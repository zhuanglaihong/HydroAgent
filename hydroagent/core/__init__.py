"""
Author: Claude & zhuanglaihong
Date: 2025-01-20 19:55:00
LastEditTime: 2025-12-05 21:00:00
LastEditors: Claude
Description: Core module initialization - 核心基础类模块
             v2.0: Added LLM exceptions and token tracking
FilePath: \HydroAgent\hydroagent\core\__init__.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from .base_agent import BaseAgent
from .llm_interface import (
    LLMInterface,
    LLMTimeoutError,
    LLMConnectionError,
    TokenUsageTracker,
)

__all__ = [
    'BaseAgent',
    'LLMInterface',
    'LLMTimeoutError',        # 🆕 v2.0 Timeout exception
    'LLMConnectionError',     # 🆕 v2.0 Connection exception
    'TokenUsageTracker',      # 🆕 v2.0 Token usage tracking
]
