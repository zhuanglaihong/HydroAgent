"""
Author: zhuanglaihong
Date: 2024-09-26 16:40:00
LastEditTime: 2024-09-26 16:40:00
LastEditors: zhuanglaihong
Description: 任务数据模型
FilePath: \HydroAgent\executor\models\task.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

from typing import Dict, List, Any, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field, validator
from datetime import datetime


class TaskType(str, Enum):
    """任务类型枚举"""
    SIMPLE = "simple"    # 简单任务，直接调用工具
    COMPLEX = "complex"  # 复杂任务，需要LLM+RAG解决


class TaskPriority(int, Enum):
    """任务优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class SuccessCriteria(BaseModel):
    """任务成功标准"""
    expected_outputs: List[str] = Field(default_factory=list, description="期望的输出字段")
    validation_rules: List[str] = Field(default_factory=list, description="验证规则")
    performance_thresholds: Dict[str, float] = Field(default_factory=dict, description="性能阈值")

    class Config:
        json_schema_extra = {
            "example": {
                "expected_outputs": ["calibration_results", "model_parameters"],
                "validation_rules": ["nse_above_threshold", "file_exists"],
                "performance_thresholds": {"NSE": 0.7, "RMSE": 10.0}
            }
        }


class Task(BaseModel):
    """工作流任务模型"""
    task_id: str = Field(..., description="唯一任务ID")
    name: str = Field(..., description="任务名称")
    type: TaskType = Field(..., description="任务类型")
    priority: TaskPriority = Field(default=TaskPriority.NORMAL, description="任务优先级")

    # 简单任务字段
    tool_name: Optional[str] = Field(None, description="工具名称(简单任务)")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="工具参数")

    # 复杂任务字段
    description: Optional[str] = Field(None, description="任务描述(复杂任务)")
    knowledge_query: Optional[str] = Field(None, description="知识库查询(复杂任务)")

    # 通用字段
    dependencies: List[str] = Field(default_factory=list, description="依赖任务ID列表")
    success_criteria: SuccessCriteria = Field(default_factory=SuccessCriteria, description="成功标准")
    timeout: Optional[int] = Field(None, description="超时时间(秒)")
    retry_count: int = Field(default=0, description="重试次数")
    conditions: Dict[str, Any] = Field(default_factory=dict, description="执行条件")

    @validator('tool_name')
    def validate_simple_task(cls, v, values):
        """验证简单任务必须有工具名称"""
        if values.get('type') == TaskType.SIMPLE and not v:
            raise ValueError("Simple tasks must have a tool_name")
        return v

    @validator('description')
    def validate_complex_task(cls, v, values):
        """验证复杂任务必须有描述"""
        if values.get('type') == TaskType.COMPLEX and not v:
            raise ValueError("Complex tasks must have a description")
        return v

    def resolve_parameters(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """解析参数中的引用"""
        resolved_params = {}
        for key, value in self.parameters.items():
            if isinstance(value, str) and value.startswith("${"):
                # 解析参数引用，如 ${task_001.output.data_dir}
                resolved_params[key] = self._resolve_reference(value, context)
            else:
                resolved_params[key] = value
        return resolved_params

    def _resolve_reference(self, reference: str, context: Dict[str, Any]) -> Any:
        """解析参数引用"""
        # 移除 ${ 和 }
        ref_path = reference[2:-1]
        parts = ref_path.split('.')

        value = context
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                raise ValueError(f"Cannot resolve reference: {reference}")

        return value

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task_001",
                "name": "数据准备",
                "type": "simple",
                "priority": 2,
                "tool_name": "prepare_data",
                "parameters": {
                    "data_dir": "data/camels_11532500",
                    "target_data_scale": "D"
                },
                "dependencies": [],
                "success_criteria": {
                    "expected_outputs": ["processed_data_path"],
                    "validation_rules": ["file_exists", "data_format_valid"]
                }
            }
        }