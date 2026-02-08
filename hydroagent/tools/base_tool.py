"""
Author: HydroAgent Team
Date: 2025-01-25 10:00:00
LastEditTime: 2025-01-25 10:00:00
LastEditors: HydroAgent Team
Description: Base tool abstraction for HydroAgent tool system
FilePath: /HydroAgent/hydroagent/tools/base_tool.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum


class ToolCategory(Enum):
    """Tool category classification"""
    VALIDATION = "validation"
    CALIBRATION = "calibration"
    EVALUATION = "evaluation"
    SIMULATION = "simulation"
    VISUALIZATION = "visualization"
    ANALYSIS = "analysis"
    UTILITY = "utility"


@dataclass
class ToolMetadata:
    """
    Tool metadata containing descriptive information.

    Attributes:
        name: Unique tool identifier
        description: Human-readable description
        category: Tool category
        version: Tool version string
        input_schema: Description of expected inputs
        output_schema: Description of outputs
        dependencies: List of tool names this tool depends on
        required_config_keys: Required keys in input config
    """
    name: str
    description: str
    category: ToolCategory
    version: str = "1.0.0"
    input_schema: Dict[str, str] = field(default_factory=dict)
    output_schema: Dict[str, str] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    required_config_keys: List[str] = field(default_factory=list)


@dataclass
class ToolResult:
    """
    Unified result wrapper for tool execution.

    Attributes:
        success: Whether execution succeeded
        data: Output data dictionary
        error: Error message if failed
        metadata: Additional execution metadata
    """
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary"""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata
        }


class BaseTool(ABC):
    """
    Abstract base class for all tools in HydroAgent.

    Subclasses must implement:
    - _define_metadata(): Return ToolMetadata
    - execute(inputs): Execute tool logic and return ToolResult

    Optional overrides:
    - validate_inputs(inputs): Custom input validation
    """

    def __init__(self):
        self._metadata = self._define_metadata()

    @abstractmethod
    def _define_metadata(self) -> ToolMetadata:
        """
        Define tool metadata.

        Returns:
            ToolMetadata: Tool metadata object
        """
        pass

    @abstractmethod
    def execute(self, inputs: Dict[str, Any]) -> ToolResult:
        """
        Execute tool core logic.

        Args:
            inputs: Tool input parameters

        Returns:
            ToolResult: Execution result
        """
        pass

    def validate_inputs(self, inputs: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate input parameters.

        Args:
            inputs: Input parameters to validate

        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        # Check required keys
        required_keys = self._metadata.required_config_keys
        missing_keys = [k for k in required_keys if k not in inputs]

        if missing_keys:
            return False, f"Missing required keys: {missing_keys}"

        # Subclasses can override for custom validation
        return True, None

    def get_metadata(self) -> ToolMetadata:
        """Get tool metadata"""
        return self._metadata

    @property
    def name(self) -> str:
        """Tool name"""
        return self._metadata.name

    @property
    def category(self) -> ToolCategory:
        """Tool category"""
        return self._metadata.category

    @property
    def version(self) -> str:
        """Tool version"""
        return self._metadata.version

    @property
    def dependencies(self) -> List[str]:
        """Tool dependencies"""
        return self._metadata.dependencies
