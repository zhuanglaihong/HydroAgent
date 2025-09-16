"""
MCP工具参数模式定义
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class MCPToolSchema(BaseModel):
    """MCP工具基础模式"""
    name: str
    description: str
    inputSchema: Dict[str, Any]


class GetModelParamsSchema(MCPToolSchema):
    """获取模型参数工具模式"""
    name: str = "get_model_params"
    description: str = "获取指定水文模型的参数信息，包括参数名称、取值范围和物理意义"
    inputSchema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "model_name": {
                "type": "string",
                "description": "模型名称，如 'gr4j', 'xaj', 'sac-sma' 等",
                "enum": ["gr4j", "gr2m", "gr3j", "gr5j", "gr6j", "xaj", "hymod"]
            }
        },
        "required": ["model_name"]
    }


class PrepareDataSchema(MCPToolSchema):
    """准备数据工具模式"""
    name: str = "prepare_data"
    description: str = "准备和预处理水文数据，将原始数据转换为模型训练格式"
    inputSchema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "data_dir": {
                "type": "string",
                "description": "数据目录路径，包含原始水文数据文件"
            },
            "target_data_scale": {
                "type": "string",
                "description": "目标数据时间尺度",
                "enum": ["D", "M", "Y"],
                "default": "D"
            }
        },
        "required": ["data_dir"]
    }


class CalibrateModelSchema(MCPToolSchema):
    """模型率定工具模式"""
    name: str = "calibrate_model"
    description: str = "率定水文模型参数，使用优化算法寻找最佳参数组合"
    inputSchema: Dict[str, Any] = {
        "type": "object", 
        "properties": {
            "model_name": {
                "type": "string",
                "description": "要率定的模型名称",
                "enum": ["gr4j", "gr2m", "gr3j", "gr5j", "gr6j", "xaj", "hymod"],
                "default": "gr4j"
            },
            "data_dir": {
                "type": "string",
                "description": "数据目录路径"
            },
            "data_type": {
                "type": "string",
                "description": "数据类型",
                "default": "owndata"
            },
            "exp_name": {
                "type": "string",
                "description": "实验名称，用于区分不同的率定实验",
                "default": "model_calibration"
            },
            "result_dir": {
                "type": "string", 
                "description": "结果保存目录"
            },
            "basin_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "流域ID列表",
                "default": ["11532500"]
            },
            "calibrate_period": {
                "type": "array",
                "items": {"type": "string"},
                "description": "率定时间段 [开始日期, 结束日期]",
                "default": ["2013-01-01", "2018-12-31"]
            },
            "test_period": {
                "type": "array", 
                "items": {"type": "string"},
                "description": "测试时间段 [开始日期, 结束日期]",
                "default": ["2019-01-01", "2023-12-31"]
            },
            "warmup": {
                "type": "integer",
                "description": "模型预热期长度（天数）",
                "default": 720
            },
            "cv_fold": {
                "type": "integer",
                "description": "交叉验证折数",
                "default": 1
            }
        },
        "required": ["model_name", "data_dir"]
    }


class EvaluateModelSchema(MCPToolSchema):
    """模型评估工具模式"""
    name: str = "evaluate_model"
    description: str = "评估已率定模型的性能，计算各种统计指标"
    inputSchema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "model_name": {
                "type": "string", 
                "description": "模型名称",
                "enum": ["gr4j", "gr2m", "gr3j", "gr5j", "gr6j", "xaj", "hymod"],
                "default": "gr4j"
            },
            "result_dir": {
                "type": "string",
                "description": "率定结果保存目录"
            },
            "exp_name": {
                "type": "string",
                "description": "实验名称，应与率定时使用的名称一致",
                "default": "model_calibration"
            },
            "cv_fold": {
                "type": "integer",
                "description": "交叉验证折数",
                "default": 1
            }
        },
        "required": ["result_dir", "exp_name"]
    }


# 工具模式映射
TOOL_SCHEMAS = {
    "get_model_params": GetModelParamsSchema(),
    "prepare_data": PrepareDataSchema(),
    "calibrate_model": CalibrateModelSchema(),
    "evaluate_model": EvaluateModelSchema()
}
