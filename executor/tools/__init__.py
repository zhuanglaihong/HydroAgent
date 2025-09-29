"""
Author: zhuanglaihong
Date: 2024-09-24 16:47:00
LastEditTime: 2024-09-26 16:35:00
LastEditors: zhuanglaihong
Description: 工具模块 - 水文工具集合和注册表
FilePath: \HydroAgent\executor\tools\__init__.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

from .registry import HydroToolRegistry, ToolInfo
from .base_tool import BaseTool, ToolResult
from .get_model_params_tool import GetModelParamsTool
from .prepare_data_tool import PrepareDataTool
from .calibrate_model_tool import CalibrateModelTool
from .evaluate_model_tool import EvaluateModelTool

# Import registry as ToolRegistry for backward compatibility
ToolRegistry = HydroToolRegistry

__all__ = [
    "HydroToolRegistry",
    "ToolRegistry",
    "ToolInfo",
    "BaseTool",
    "ToolResult",
    "GetModelParamsTool",
    "PrepareDataTool",
    "CalibrateModelTool",
    "EvaluateModelTool",
]
