"""
Author: Claude & zhuanglaihong
Date: 2025-01-20 20:00:00
LastEditTime: 2025-11-29 15:00:00
LastEditors: Claude
Description: Utils module initialization - 工具层模块统一导出
FilePath: \\HydroAgent\\hydroagent\\utils\\__init__.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from .schema_validator import SchemaValidator
from .result_parser import ResultParser
from .error_handler import ErrorHandler, GracefulErrorHandler
from .code_sandbox import CodeSandbox
from .prompt_manager import PromptManager, AgentContext
from .path_manager import PathManager
from .plotting import PlottingToolkit
from .data_loader import DataLoader
from .report_generator import ReportGenerator
from .post_processor import PostProcessingEngine
from .task_detector import TaskTypeDetector

# Code Generation & Execution
from .code_generator import (
    generate_code_with_feedback,
    extract_code_from_markdown,
    generate_analysis_code,
    execute_generated_code,
)

# Error Handling
from .error_handler import (
    handle_pipeline_error,
    format_traceback,
    analyze_execution_error,
)

# Path Management
from .path_manager import scan_output_files, configure_task_output_dir

# Prompt Building
from .prompt_manager import build_code_generation_prompt

# Result Parsing
from .result_parser import parse_calibration_result, parse_evaluation_result

# Parameter Range Adjustment
from .param_range_adjuster import adjust_from_previous_calibration

# Task Type Detection
from .task_detector import get_task_type_description

# ============================================================================
# Public API (__all__)
# ============================================================================

__all__ = [
    # ========== Classes ==========
    # Validators & Parsers
    "SchemaValidator",
    "ResultParser",
    # Error Handling
    "ErrorHandler",
    "GracefulErrorHandler",
    # Code Execution
    "CodeSandbox",
    # Prompt & Context Management
    "PromptManager",
    "AgentContext",
    # Path & File Management
    "PathManager",
    # Visualization
    "PlottingToolkit",
    # Data Loading
    "DataLoader",
    # Reporting
    "ReportGenerator",
    # Post-Processing
    "PostProcessingEngine",
    # Task Detection
    "TaskTypeDetector",
    # ========== Functions ==========
    # Code Generation & Execution
    "generate_code_with_feedback",
    "extract_code_from_markdown",
    "generate_analysis_code",
    "execute_generated_code",
    # Error Handling Functions
    "handle_pipeline_error",
    "format_traceback",
    "analyze_execution_error",
    # Path Management Functions
    "scan_output_files",
    "configure_task_output_dir",
    # Prompt Building Functions
    "build_code_generation_prompt",
    # Result Parsing Functions
    "parse_calibration_result",
    "parse_evaluation_result",
    # Parameter Adjustment Functions
    "adjust_from_previous_calibration",
    # Task Detection Functions
    "get_task_type_description",
]
