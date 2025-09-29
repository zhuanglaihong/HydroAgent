"""
Author: zhuanglaihong
Date: 2024-09-26 16:40:00
LastEditTime: 2024-09-26 16:40:00
LastEditors: zhuanglaihong
Description: 工具注册表 - 管理所有可用工具
FilePath: \HydroAgent\executor\tools\registry.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import logging
from typing import Dict, Any, Optional, List, Callable, Type
from pydantic import BaseModel, Field
from datetime import datetime

from .base_tool import BaseTool, ToolResult


class ToolInfo(BaseModel):
    """工具信息"""

    name: str = Field(..., description="工具名称")
    description: str = Field(..., description="工具描述")
    tool_class: str = Field(..., description="工具类名")
    parameter_schema: Dict[str, Any] = Field(..., description="参数模式")
    registered_at: datetime = Field(
        default_factory=datetime.now, description="注册时间"
    )
    version: str = Field(default="1.0.0", description="工具版本")
    category: str = Field(default="general", description="工具分类")


class HydroToolRegistry:
    """水文工具注册表"""

    def __init__(self):
        """初始化工具注册表"""
        self.tools: Dict[str, BaseTool] = {}
        self.tool_info: Dict[str, ToolInfo] = {}
        self.categories: Dict[str, List[str]] = {}
        self.logger = logging.getLogger(__name__)

        # 注册默认工具
        self._register_default_tools()

        self.logger.info("工具注册表初始化完成")

    def register_tool(
        self, tool: BaseTool, category: str = "general", version: str = "1.0.0"
    ) -> bool:
        """
        注册工具

        Args:
            tool: 工具实例
            category: 工具分类
            version: 工具版本

        Returns:
            bool: 是否注册成功
        """
        try:
            if tool.name in self.tools:
                self.logger.warning(f"工具 {tool.name} 已存在，将被覆盖")

            # 验证工具
            if not self._validate_tool(tool):
                self.logger.error(f"工具 {tool.name} 验证失败")
                return False

            # 注册工具
            self.tools[tool.name] = tool

            # 注册工具信息
            self.tool_info[tool.name] = ToolInfo(
                name=tool.name,
                description=tool.description,
                tool_class=tool.__class__.__name__,
                parameter_schema=tool.get_parameter_schema(),
                version=version,
                category=category,
            )

            # 更新分类索引
            if category not in self.categories:
                self.categories[category] = []
            if tool.name not in self.categories[category]:
                self.categories[category].append(tool.name)

            self.logger.info(f"工具 {tool.name} 注册成功")
            return True

        except Exception as e:
            self.logger.error(f"注册工具 {tool.name} 失败: {e}")
            return False

    def unregister_tool(self, tool_name: str) -> bool:
        """
        取消注册工具

        Args:
            tool_name: 工具名称

        Returns:
            bool: 是否取消成功
        """
        if tool_name not in self.tools:
            self.logger.warning(f"工具 {tool_name} 不存在")
            return False

        # 从分类中移除
        tool_category = self.tool_info[tool_name].category
        if tool_category in self.categories:
            self.categories[tool_category] = [
                name for name in self.categories[tool_category] if name != tool_name
            ]

        # 移除工具
        del self.tools[tool_name]
        del self.tool_info[tool_name]

        self.logger.info(f"工具 {tool_name} 已取消注册")
        return True

    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """
        获取工具实例

        Args:
            tool_name: 工具名称

        Returns:
            Optional[BaseTool]: 工具实例，如果不存在返回None
        """
        return self.tools.get(tool_name)

    def get_tool_info(self, tool_name: str) -> Optional[ToolInfo]:
        """
        获取工具信息

        Args:
            tool_name: 工具名称

        Returns:
            Optional[ToolInfo]: 工具信息，如果不存在返回None
        """
        return self.tool_info.get(tool_name)

    def list_tools(self, category: str = None) -> List[str]:
        """
        列出所有工具名称

        Args:
            category: 可选的分类过滤

        Returns:
            List[str]: 工具名称列表
        """
        if category:
            return self.categories.get(category, [])
        return list(self.tools.keys())

    def list_categories(self) -> List[str]:
        """
        列出所有分类

        Returns:
            List[str]: 分类列表
        """
        return list(self.categories.keys())

    def call_tool(self, tool_name: str, parameters: Dict[str, Any]) -> ToolResult:
        """
        调用工具

        Args:
            tool_name: 工具名称
            parameters: 输入参数

        Returns:
            ToolResult: 执行结果
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolResult(success=False, error=f"工具 {tool_name} 不存在")

        try:
            # 验证参数
            if not tool.validate_parameters(parameters):
                return ToolResult(success=False, error=f"工具 {tool_name} 参数验证失败")

            # 执行工具
            result = tool.execute(parameters)
            self.logger.info(f"工具 {tool_name} 执行完成")
            return result

        except Exception as e:
            self.logger.error(f"工具 {tool_name} 执行失败: {e}")
            return ToolResult(
                success=False, error=f"工具 {tool_name} 执行失败: {str(e)}"
            )

    def get_registry_stats(self) -> Dict[str, Any]:
        """
        获取注册表统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        return {
            "total_tools": len(self.tools),
            "categories": {cat: len(tools) for cat, tools in self.categories.items()},
            "tool_list": list(self.tools.keys()),
        }

    def _validate_tool(self, tool: BaseTool) -> bool:
        """验证工具是否符合规范"""
        try:
            # 检查必要属性
            if not hasattr(tool, "name") or not tool.name:
                return False
            if not hasattr(tool, "description") or not tool.description:
                return False

            # 检查必要方法
            if not hasattr(tool, "execute") or not callable(tool.execute):
                return False
            if not hasattr(tool, "validate_parameters") or not callable(
                tool.validate_parameters
            ):
                return False
            if not hasattr(tool, "get_parameter_schema") or not callable(
                tool.get_parameter_schema
            ):
                return False

            return True

        except Exception as e:
            self.logger.error(f"工具验证失败: {e}")
            return False

    def _register_default_tools(self):
        """注册默认工具"""
        # 这里将在稍后实现具体的水文工具注册
        pass

    def export_tool_definitions(self) -> Dict[str, Any]:
        """
        导出工具定义

        Returns:
            Dict[str, Any]: 工具定义字典
        """
        return {
            tool_name: {"info": info.dict(), "schema": info.parameter_schema}
            for tool_name, info in self.tool_info.items()
        }

    def import_tool_definitions(self, definitions: Dict[str, Any]) -> bool:
        """
        导入工具定义（用于配置加载）

        Args:
            definitions: 工具定义字典

        Returns:
            bool: 是否导入成功
        """
        # 这里可以实现从配置文件加载工具定义的逻辑
        # 目前暂时跳过，直接返回True
        return True
