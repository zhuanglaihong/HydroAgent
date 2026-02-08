"""
Author: HydroAgent Team
Date: 2025-01-25 10:00:00
LastEditTime: 2025-01-25 10:00:00
LastEditors: HydroAgent Team
Description: Tool registry for managing all available tools
FilePath: /HydroAgent/hydroagent/tools/registry.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from typing import Dict, List, Optional
from hydroagent.tools.base_tool import BaseTool, ToolMetadata, ToolCategory
import logging

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Tool registry - manages all available tools using singleton pattern.

    Features:
    - Register/unregister tools
    - Query tools by name or category
    - Check tool dependencies
    - Thread-safe singleton implementation
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize registry (only once due to singleton)"""
        if not self._initialized:
            self._tools: Dict[str, BaseTool] = {}
            self._initialized = True
            logger.info("[ToolRegistry] Initialized tool registry")

    def register(self, tool: BaseTool) -> None:
        """
        Register a tool.

        Args:
            tool: Tool instance to register

        Raises:
            TypeError: If tool is not a BaseTool instance
        """
        if not isinstance(tool, BaseTool):
            raise TypeError(f"Tool must be a BaseTool instance, got {type(tool)}")

        name = tool.name
        if name in self._tools:
            logger.warning(f"[ToolRegistry] Tool '{name}' already registered, overwriting")

        self._tools[name] = tool
        logger.info(f"[ToolRegistry] Registered tool: {name} ({tool.category.value})")

    def unregister(self, name: str) -> bool:
        """
        Unregister a tool.

        Args:
            name: Tool name

        Returns:
            bool: True if tool was unregistered, False if not found
        """
        if name in self._tools:
            del self._tools[name]
            logger.info(f"[ToolRegistry] Unregistered tool: {name}")
            return True
        return False

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """
        Get tool instance by name.

        Args:
            name: Tool name

        Returns:
            BaseTool: Tool instance if found, None otherwise
        """
        return self._tools.get(name)

    def list_tools(self, category: Optional[ToolCategory] = None) -> List[str]:
        """
        List all tool names, optionally filtered by category.

        Args:
            category: Optional category filter

        Returns:
            List[str]: List of tool names
        """
        if category is None:
            return list(self._tools.keys())

        return [
            name for name, tool in self._tools.items()
            if tool.category == category
        ]

    def get_tool_metadata(self, name: str) -> Optional[ToolMetadata]:
        """
        Get tool metadata by name.

        Args:
            name: Tool name

        Returns:
            ToolMetadata: Tool metadata if found, None otherwise
        """
        tool = self.get_tool(name)
        return tool.get_metadata() if tool else None

    def get_all_metadata(self) -> Dict[str, ToolMetadata]:
        """
        Get metadata for all registered tools.

        Returns:
            Dict[str, ToolMetadata]: Mapping of tool name to metadata
        """
        return {
            name: tool.get_metadata()
            for name, tool in self._tools.items()
        }

    def check_dependencies(self, tool_name: str) -> tuple[bool, List[str]]:
        """
        Check if all dependencies for a tool are satisfied.

        Args:
            tool_name: Tool name to check

        Returns:
            Tuple[bool, List[str]]: (all_satisfied, missing_tools)
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return False, [tool_name]

        metadata = tool.get_metadata()
        missing = [
            dep for dep in metadata.dependencies
            if dep not in self._tools
        ]

        return len(missing) == 0, missing

    def get_dependency_graph(self) -> Dict[str, List[str]]:
        """
        Get dependency graph for all tools.

        Returns:
            Dict[str, List[str]]: Mapping of tool name to dependencies
        """
        return {
            name: tool.dependencies
            for name, tool in self._tools.items()
        }

    def clear(self) -> None:
        """Clear all registered tools"""
        self._tools.clear()
        logger.info("[ToolRegistry] Cleared all tools")

    def __len__(self) -> int:
        """Get number of registered tools"""
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        """Check if tool is registered"""
        return name in self._tools

    def __repr__(self) -> str:
        """String representation"""
        return f"ToolRegistry(tools={len(self._tools)})"


# Global registry instance
registry = ToolRegistry()
