"""
Author: zhuanglaihong
Date: 2024-09-26 16:40:00
LastEditTime: 2024-09-26 16:40:00
LastEditors: zhuanglaihong
Description: 基础工具接口定义
FilePath: \HydroAgent\executor\tools\base_tool.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
import logging


class ToolResult(BaseModel):
    """工具执行结果"""

    success: bool = Field(..., description="是否成功")
    output: Dict[str, Any] = Field(default_factory=dict, description="输出数据")
    error: Optional[str] = Field(None, description="错误信息")
    execution_time: Optional[float] = Field(None, description="执行时间(秒)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")

    def add_output(self, key: str, value: Any):
        """添加输出数据"""
        self.output[key] = value

    def set_error(self, error_msg: str):
        """设置错误信息"""
        self.success = False
        self.error = error_msg

    def add_metadata(self, key: str, value: Any):
        """添加元数据"""
        self.metadata[key] = value


class BaseTool(ABC):
    """基础工具抽象类"""

    def __init__(self, name: str, description: str):
        """
        初始化工具

        Args:
            name: 工具名称
            description: 工具描述
        """
        self.name = name
        self.description = description
        self.logger = logging.getLogger(f"hydrotool.tools.{name}")

    @abstractmethod
    def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """
        执行工具

        Args:
            parameters: 输入参数

        Returns:
            ToolResult: 执行结果
        """
        pass

    @abstractmethod
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """
        验证输入参数

        Args:
            parameters: 输入参数

        Returns:
            bool: 参数是否有效
        """
        pass

    @abstractmethod
    def get_parameter_schema(self) -> Dict[str, Any]:
        """
        获取参数模式定义

        Returns:
            Dict[str, Any]: 参数模式
        """
        pass

    def _create_success_result(
        self, output: Dict[str, Any] = None, execution_time: float = None
    ) -> ToolResult:
        """创建成功结果"""
        return ToolResult(
            success=True, output=output or {}, execution_time=execution_time
        )

    def _create_error_result(
        self, error_msg: str, execution_time: float = None
    ) -> ToolResult:
        """创建错误结果"""
        return ToolResult(success=False, error=error_msg, execution_time=execution_time)

    def _measure_execution_time(func):
        """执行时间测量装饰器"""

        def wrapper(self, *args, **kwargs):
            start_time = datetime.now()
            try:
                result = func(self, *args, **kwargs)
                end_time = datetime.now()
                execution_time = (end_time - start_time).total_seconds()

                if isinstance(result, ToolResult):
                    result.execution_time = execution_time

                return result
            except Exception as e:
                end_time = datetime.now()
                execution_time = (end_time - start_time).total_seconds()
                return self._create_error_result(str(e), execution_time)

        return wrapper
