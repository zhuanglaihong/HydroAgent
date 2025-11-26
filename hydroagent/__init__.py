"""
Author: zhuanglaihong & Claude
Date: 2025-11-13 20:00:00
LastEditTime: 2025-11-20 20:05:00
LastEditors: Claude
Description: HydroAgent - Intelligent Hydrological Model Calibration System
             Multi-agent architecture for automated hydrological modeling
FilePath: \HydroAgent\hydroagent\__init__.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

# Version
__version__ = "0.2.0-alpha"

# Core components
from .core import BaseAgent, LLMInterface
from .core.llm_interface import create_llm_interface, OpenAIInterface, ClaudeInterface, OllamaInterface

# Agents
from .agents import (
    Orchestrator,
    IntentAgent,
    ConfigAgent,
    RunnerAgent,
    DeveloperAgent,
)

# System API - Main entry point
from .system import HydroAgent, create_hydro_agent, run_query

# Utilities
from .utils import (
    SchemaValidator,
    ResultParser,
    ErrorHandler,
    CodeSandbox,
)

# Resources
from .resources import (
    RESOURCE_DIR,
    SCHEMA_DEFINITION,
    API_SIGNATURES,
)

__all__ = [
    # Version
    '__version__',

    # System API (Recommended)
    'HydroAgent',
    'create_hydro_agent',
    'run_query',

    # Core
    'BaseAgent',
    'LLMInterface',
    'create_llm_interface',
    'OpenAIInterface',
    'ClaudeInterface',
    'OllamaInterface',

    # Agents
    'Orchestrator',
    'IntentAgent',
    'ConfigAgent',
    'RunnerAgent',
    'DeveloperAgent',

    # Utilities
    'SchemaValidator',
    'ResultParser',
    'ErrorHandler',
    'CodeSandbox',

    # Resources
    'RESOURCE_DIR',
    'SCHEMA_DEFINITION',
    'API_SIGNATURES',
]

# Package metadata
__author__ = "zhuanglaihong & Claude"
__email__ = "your.email@example.com"
__description__ = "Intelligent hydrological model calibration system with multi-agent architecture"
__url__ = "https://github.com/yourusername/HydroAgent"
