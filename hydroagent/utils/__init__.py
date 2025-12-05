"""
Author: Claude & zhuanglaihong
Date: 2025-11-20 20:00:00
LastEditTime: 2025-12-03 18:00:00
LastEditors: Claude
Description: Utils module initialization - 工具层模块统一导出
FilePath: \\HydroAgent\\hydroagent\\utils\\__init__.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

14个核心工具模块:
✅ code_generator - 代码生成 (RunnerAgent使用)
✅ config_validator - 配置验证 (IntentAgent, InterpreterAgent, RunnerAgent使用)
✅ data_loader - 数据加载 (DeveloperAgent, PostProcessor使用)
✅ error_handler - 错误处理 (Orchestrator, DeveloperAgent, RunnerAgent使用)
✅ llm_config_reviewer - LLM配置审查 (InterpreterAgent使用)
✅ param_range_adjuster - 参数范围调整 (RunnerAgent使用)
✅ path_manager - 路径管理 (多个Agent使用)
✅ plotting - 可视化绘图 (DeveloperAgent使用)
✅ post_processor - 后处理引擎 (DeveloperAgent使用)
✅ prompt_manager - 提示管理 (IntentAgent, DeveloperAgent, RunnerAgent使用)
✅ report_generator - 报告生成 (DeveloperAgent使用)
✅ result_parser - 结果解析 (RunnerAgent使用)
✅ session_summary - 会话总结 (DeveloperAgent使用)
✅ task_detector - 任务类型检测 (DeveloperAgent使用)

"""

# ============================================================================
# 核心类导入 (按功能分组)
# ============================================================================

# 结果解析 (RunnerAgent使用)
from .result_parser import ResultParser

# 错误处理 (Orchestrator, DeveloperAgent, RunnerAgent使用)
from .error_handler import ErrorHandler, GracefulErrorHandler

# 提示管理 (IntentAgent, DeveloperAgent, RunnerAgent使用)
from .prompt_manager import PromptManager, AgentContext

# 路径管理 (多个Agent使用)
from .path_manager import PathManager

# 可视化工具 (DeveloperAgent使用)
from .plotting import PlottingToolkit

# 数据加载 (DeveloperAgent, PostProcessor使用)
from .data_loader import DataLoader

# 报告生成 (DeveloperAgent使用)
from .report_generator import ReportGenerator

# 后处理引擎 (DeveloperAgent使用 - 实验3/4/5后处理)
from .post_processor import PostProcessingEngine

# 任务类型检测 (DeveloperAgent使用 - v4.1新增)
from .task_detector import TaskTypeDetector

# 会话总结 (DeveloperAgent使用 - 日志汇总)
from .session_summary import SessionSummaryCollector, SessionSummaryGenerator

# ============================================================================
# 功能函数导入 (按用途分组)
# ============================================================================

# 代码生成与执行 (RunnerAgent使用 - 实验4代码生成)
from .code_generator import (
    generate_code_with_feedback,  # LLM代码生成
    extract_code_from_markdown,   # 从Markdown提取代码
    generate_analysis_code,        # 生成分析代码
    execute_generated_code,        # 执行生成的代码
)

# 错误处理函数 (Orchestrator, RunnerAgent使用)
from .error_handler import (
    handle_pipeline_error,    # 处理流水线错误
    format_traceback,         # 格式化异常堆栈
    analyze_execution_error,  # 分析执行错误
)

# 路径管理函数 (多个Agent使用)
from .path_manager import (
    scan_output_files,         # 扫描输出文件
    configure_task_output_dir, # 配置任务输出目录
)

# 提示构建函数 (RunnerAgent使用)
from .prompt_manager import build_code_generation_prompt

# 结果解析函数 (RunnerAgent使用)
from .result_parser import (
    parse_calibration_result,  # 解析率定结果
    parse_evaluation_result,   # 解析评估结果
)

# 结果序列化函数 (Orchestrator使用 - 清理numpy数组等不可序列化对象)
from .result_serializer import (
    sanitize_for_json,    # 递归清理对象
    sanitize_result,      # 清理单个结果
    sanitize_results,     # 清理结果列表
)

# 参数范围调整 (RunnerAgent使用 - 实验3边界检测)
from .param_range_adjuster import adjust_from_previous_calibration

# 任务类型检测函数 (DeveloperAgent使用)
from .task_detector import get_task_type_description

# ============================================================================
# Public API (__all__)
# ============================================================================

__all__ = [
    # ========== 核心类 (Classes) ==========

    # 结果解析 (Result Parsing)
    "ResultParser",  # 结果解析器 - RunnerAgent用于解析hydromodel输出

    # 错误处理 (Error Handling)
    "ErrorHandler",  # 错误处理器 - 统一的错误处理
    "GracefulErrorHandler",  # 优雅错误处理器 - 带恢复策略

    # 提示与上下文管理 (Prompt & Context Management)
    "PromptManager",  # 提示管理器 - 动态提示系统
    "AgentContext",  # Agent上下文 - 存储Agent执行上下文

    # 路径与文件管理 (Path & File Management)
    "PathManager",  # 路径管理器 - 统一的路径配置

    # 可视化 (Visualization)
    "PlottingToolkit",  # 绘图工具包 - 生成出版级图表

    # 数据加载 (Data Loading)
    "DataLoader",  # 数据加载器 - 加载CAMELS数据

    # 报告生成 (Reporting)
    "ReportGenerator",  # 报告生成器 - 生成分析报告

    # 后处理 (Post-Processing)
    "PostProcessingEngine",  # 后处理引擎 - 多任务结果汇总

    # 任务检测 (Task Detection)
    "TaskTypeDetector",  # 任务类型检测器 - 识别任务类型

    # 会话总结 (Session Summary)
    "SessionSummaryCollector",  # 会话总结收集器 - 收集日志
    "SessionSummaryGenerator",  # 会话总结生成器 - 生成总结

    # ========== 功能函数 (Functions) ==========

    # 代码生成与执行 (Code Generation & Execution)
    "generate_code_with_feedback",  # 生成代码（带反馈） - 实验4
    "extract_code_from_markdown",  # 从Markdown提取代码
    "generate_analysis_code",  # 生成分析代码
    "execute_generated_code",  # 执行生成的代码

    # 错误处理函数 (Error Handling Functions)
    "handle_pipeline_error",  # 处理流水线错误
    "format_traceback",  # 格式化异常堆栈
    "analyze_execution_error",  # 分析执行错误类型

    # 路径管理函数 (Path Management Functions)
    "scan_output_files",  # 扫描输出文件
    "configure_task_output_dir",  # 配置任务输出目录

    # 提示构建函数 (Prompt Building Functions)
    "build_code_generation_prompt",  # 构建代码生成提示

    # 结果解析函数 (Result Parsing Functions)
    "parse_calibration_result",  # 解析率定结果
    "parse_evaluation_result",  # 解析评估结果

    # 结果序列化函数 (Result Serialization Functions)
    "sanitize_for_json",  # 递归清理对象，移除不可序列化内容
    "sanitize_result",  # 清理单个结果字典
    "sanitize_results",  # 清理结果列表

    # 参数调整函数 (Parameter Adjustment Functions)
    "adjust_from_previous_calibration",  # 从前次率定调整参数范围 - 实验3

    # 任务检测函数 (Task Detection Functions)
    "get_task_type_description",  # 获取任务类型描述
]
