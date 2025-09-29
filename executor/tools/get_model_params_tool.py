"""
Author: zhuanglaihong
Date: 2024-09-26 16:40:00
LastEditTime: 2024-09-26 16:40:00
LastEditors: zhuanglaihong
Description: 获取模型参数工具
FilePath: \HydroAgent\executor\tools\get_model_params_tool.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any
import logging

# 添加项目根路径
repo_path = Path(os.path.abspath(__file__)).parent.parent.parent.parent
sys.path.append(str(repo_path))

from .base_tool import BaseTool, ToolResult

# 尝试导入水文模型模块
try:
    from hydromodel.models.model_config import MODEL_PARAM_DICT

    HYDROMODEL_AVAILABLE = True
except ImportError as e:
    logging.warning(f"水文模型模块导入失败: {e}")
    HYDROMODEL_AVAILABLE = False
    MODEL_PARAM_DICT = {}


class GetModelParamsTool(BaseTool):
    """获取模型参数工具"""

    def __init__(self):
        super().__init__(
            name="get_model_params", description="获取指定水文模型的参数名称和范围信息"
        )

    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """验证输入参数"""
        try:
            # 检查必需参数
            if "model_name" not in parameters:
                self.logger.error("缺少必需参数: model_name")
                return False

            # 检查参数类型
            if not isinstance(parameters["model_name"], str):
                self.logger.error("model_name 必须是字符串")
                return False

            # 检查模型名称是否为空
            if not parameters["model_name"].strip():
                self.logger.error("model_name 不能为空")
                return False

            return True

        except Exception as e:
            self.logger.error(f"参数验证失败: {e}")
            return False

    def get_parameter_schema(self) -> Dict[str, Any]:
        """获取参数模式定义"""
        return {
            "type": "object",
            "properties": {
                "model_name": {
                    "type": "string",
                    "description": "模型名称，如 'gr4j', 'xaj', 'sac-sma' 等",
                    "examples": [
                        "gr4j",
                        "xaj",
                        "sac-sma",
                        "gr1y",
                        "gr2m",
                        "gr5j",
                        "gr6j",
                    ],
                }
            },
            "required": ["model_name"],
            "additionalProperties": False,
        }

    def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """执行获取模型参数"""
        if not HYDROMODEL_AVAILABLE:
            return self._create_error_result(
                "水文模型模块不可用，请检查 hydromodel 依赖安装"
            )

        model_name = parameters["model_name"].strip().lower()

        try:
            # 检查模型是否支持
            if model_name not in MODEL_PARAM_DICT:
                available_models = list(MODEL_PARAM_DICT.keys())
                return self._create_error_result(
                    f"不支持的模型 '{model_name}'。可用模型: {available_models}"
                )

            # 获取参数信息
            param_info = MODEL_PARAM_DICT[model_name]

            output = {
                "model_name": model_name,
                "param_names": param_info.get("param_name", []),
                "param_ranges": param_info.get("param_range", []),
                "param_count": len(param_info.get("param_name", [])),
                "description": f"{model_name.upper()} 模型参数信息",
                # 添加兼容性字段，用于工作流引用
                "param_range_file": f"{model_name}_param_ranges.json",
            }

            # 添加详细的参数信息
            if "param_name" in param_info and "param_range" in param_info:
                param_details = []
                param_names = param_info["param_name"]
                param_ranges = param_info["param_range"]

                for i, (name, range_info) in enumerate(zip(param_names, param_ranges)):
                    param_details.append(
                        {
                            "index": i + 1,
                            "name": name,
                            "min_value": range_info[0] if len(range_info) > 0 else None,
                            "max_value": range_info[1] if len(range_info) > 1 else None,
                            "range": range_info,
                        }
                    )

                output["param_details"] = param_details
                # 添加适合模型校准工具使用的字段
                output["param_range_file"] = param_details

            self.logger.info(f"成功获取模型 {model_name} 参数信息")
            return self._create_success_result(output)

        except Exception as e:
            error_msg = f"获取模型参数失败: {str(e)}"
            self.logger.error(error_msg)
            return self._create_error_result(error_msg)

    def get_supported_models(self) -> list:
        """获取支持的模型列表"""
        if not HYDROMODEL_AVAILABLE:
            return []
        return list(MODEL_PARAM_DICT.keys())

    def validate_model_name(self, model_name: str) -> bool:
        """验证模型名称是否支持"""
        if not HYDROMODEL_AVAILABLE:
            return False
        return model_name.lower() in MODEL_PARAM_DICT
