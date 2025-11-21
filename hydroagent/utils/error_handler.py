r"""
Author: Claude & zhuanglaihong
Date: 2025-01-20 20:00:00
LastEditTime: 2025-01-20 20:00:00
LastEditors: Claude
Description: Error interception and feedback loop handler (Tech 4.5)
             异常拦截与反馈回路处理器
FilePath: \HydroAgent\hydroagent\utils\error_handler.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from typing import Dict, Any, Optional, List
import logging
import traceback
import re

logger = logging.getLogger(__name__)


class ErrorHandler:
    """
    Error interception and feedback loop handler (Tech 4.5).
    异常拦截与反馈回路处理器。

    Purpose:
    - Capture Python tracebacks from hydromodel
    - Transform technical errors into natural language feedback
    - Provide actionable suggestions for correction
    - Enable agent self-repair mechanisms

    Converts cryptic error messages into LLM-understandable guidance.
    """

    def __init__(self):
        """Initialize ErrorHandler with common error mappings."""
        self.error_mappings = self._build_error_mappings()

    def _build_error_mappings(self) -> Dict[str, Dict[str, str]]:
        """
        Build error pattern to suggestion mappings.
        构建错误模式到建议的映射。

        Returns:
            Error mapping dictionary
        """
        return {
            "KeyError": {
                "prec": {
                    "message": "Variable name error",
                    "suggestion": "In hydromodel, precipitation variable is typically 'prcp' or 'precipitation', not 'prec'"
                },
                "temp": {
                    "message": "Variable name error",
                    "suggestion": "Temperature variable should be 'tmean', 'tmin', or 'tmax', not 'temp'"
                }
            },
            "FileNotFoundError": {
                "datasets-origin": {
                    "message": "Data path configuration error",
                    "suggestion": "Check 'datasets-origin' path in config. Ensure it points to valid data directory"
                },
                "basin": {
                    "message": "Basin data not found",
                    "suggestion": "Basin ID may be incorrect or data not downloaded. Verify basin_id exists in dataset"
                }
            },
            "ValueError": {
                "date": {
                    "message": "Invalid date format",
                    "suggestion": "Time periods must use format: YYYY-MM-DD (e.g., '2000-01-01')"
                },
                "parameter": {
                    "message": "Invalid parameter value",
                    "suggestion": "Check parameter ranges in param_range.yaml. Values must be within specified bounds"
                }
            },
            "ImportError": {
                "hydromodel": {
                    "message": "hydromodel module not found",
                    "suggestion": "Install hydromodel: pip install git+https://github.com/OuyangWenyu/hydromodel.git"
                },
                "module": {
                    "message": "Missing required dependency",
                    "suggestion": "Install missing package using pip or conda"
                }
            },
            "TypeError": {
                "NoneType": {
                    "message": "Unexpected None value",
                    "suggestion": "A required value is None. Check if data was loaded correctly"
                },
                "array": {
                    "message": "Type mismatch in array operation",
                    "suggestion": "Data type conversion issue. Ensure numeric data is properly formatted"
                }
            }
        }

    def handle_exception(
        self,
        exception: Exception,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Handle an exception and generate feedback.
        处理异常并生成反馈。

        Args:
            exception: The exception that occurred
            context: Optional context information (config, task, etc.)

        Returns:
            Error analysis dictionary with suggestions
        """
        error_info = {
            "error_type": type(exception).__name__,
            "error_message": str(exception),
            "traceback": self._format_traceback(),
            "analysis": {},
            "suggestions": [],
            "severity": "error"
        }

        # Analyze error
        analysis = self._analyze_error(exception, context)
        error_info["analysis"] = analysis

        # Generate suggestions
        suggestions = self._generate_suggestions(exception, analysis, context)
        error_info["suggestions"] = suggestions

        # Determine severity
        error_info["severity"] = self._determine_severity(exception)

        logger.error(f"[ErrorHandler] {error_info['error_type']}: {error_info['error_message']}")

        return error_info

    def _format_traceback(self) -> str:
        """
        Format current exception traceback.
        格式化当前异常回溯。

        Returns:
            Formatted traceback string
        """
        return traceback.format_exc()

    def _analyze_error(
        self,
        exception: Exception,
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze exception to extract key information.
        分析异常以提取关键信息。

        Args:
            exception: The exception
            context: Context information

        Returns:
            Analysis dictionary
        """
        analysis = {
            "error_category": "unknown",
            "likely_cause": "Unknown error",
            "affected_component": "unknown"
        }

        error_type = type(exception).__name__
        error_message = str(exception)

        # Categorize error
        if error_type in ["KeyError", "AttributeError"]:
            analysis["error_category"] = "configuration"
            analysis["likely_cause"] = "Configuration or data field mismatch"
            analysis["affected_component"] = "config/data"

        elif error_type in ["FileNotFoundError", "IOError"]:
            analysis["error_category"] = "data"
            analysis["likely_cause"] = "Missing or inaccessible file/data"
            analysis["affected_component"] = "data loading"

        elif error_type in ["ValueError", "TypeError"]:
            analysis["error_category"] = "data_validation"
            analysis["likely_cause"] = "Invalid data type or value"
            analysis["affected_component"] = "data processing"

        elif error_type in ["ImportError", "ModuleNotFoundError"]:
            analysis["error_category"] = "dependency"
            analysis["likely_cause"] = "Missing required package"
            analysis["affected_component"] = "environment"

        elif "numerical" in error_message.lower() or "nan" in error_message.lower():
            analysis["error_category"] = "numerical"
            analysis["likely_cause"] = "Numerical instability or invalid computation"
            analysis["affected_component"] = "model computation"

        return analysis

    def _generate_suggestions(
        self,
        exception: Exception,
        analysis: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> List[str]:
        """
        Generate actionable suggestions for fixing the error.
        生成修复错误的可操作建议。

        Args:
            exception: The exception
            analysis: Error analysis result
            context: Context information

        Returns:
            List of suggestion strings
        """
        suggestions = []

        error_type = type(exception).__name__
        error_message = str(exception)

        # Check error mappings
        if error_type in self.error_mappings:
            type_mappings = self.error_mappings[error_type]

            for key_pattern, mapping in type_mappings.items():
                if key_pattern.lower() in error_message.lower():
                    suggestions.append(f"{mapping['message']}: {mapping['suggestion']}")

        # Category-specific suggestions
        if analysis["error_category"] == "configuration":
            suggestions.append("Review configuration file for typos or incorrect field names")
            suggestions.append("Compare with hydromodel's example_config.yaml")

        elif analysis["error_category"] == "data":
            suggestions.append("Verify data paths in config are correct and accessible")
            suggestions.append("Check if required data files exist in specified directory")

        elif analysis["error_category"] == "data_validation":
            suggestions.append("Validate input data ranges and formats")
            suggestions.append("Check for NaN or infinite values in data")

        elif analysis["error_category"] == "dependency":
            suggestions.append("Install missing dependencies: pip install -r requirements.txt")
            suggestions.append("Verify virtual environment is activated")

        elif analysis["error_category"] == "numerical":
            suggestions.append("Check parameter ranges - values may be causing numerical instability")
            suggestions.append("Increase warmup period to stabilize model")

        # Context-specific suggestions
        if context:
            if "config" in context:
                suggestions.append("Review generated configuration for potential issues")

        # Default suggestion if none matched
        if not suggestions:
            suggestions.append("Review error traceback for specific line causing issue")
            suggestions.append("Check hydromodel documentation for API requirements")

        return suggestions

    def _determine_severity(self, exception: Exception) -> str:
        """
        Determine error severity level.
        确定错误严重程度。

        Args:
            exception: The exception

        Returns:
            Severity level: "critical", "error", "warning"
        """
        error_type = type(exception).__name__

        # Critical errors
        if error_type in ["ImportError", "ModuleNotFoundError", "MemoryError"]:
            return "critical"

        # Standard errors
        elif error_type in ["FileNotFoundError", "ValueError", "TypeError", "KeyError"]:
            return "error"

        # Warnings
        elif error_type in ["UserWarning", "RuntimeWarning"]:
            return "warning"

        else:
            return "error"

    def format_error_feedback(self, error_info: Dict[str, Any]) -> str:
        """
        Format error information into human-readable feedback.
        将错误信息格式化为人类可读的反馈。

        Args:
            error_info: Error information dictionary

        Returns:
            Formatted error feedback string
        """
        lines = []

        # Header
        severity_emoji = {
            "critical": "🔴",
            "error": "⚠️",
            "warning": "⚡"
        }
        emoji = severity_emoji.get(error_info["severity"], "❌")

        lines.append(f"{emoji} {error_info['error_type']}: {error_info['error_message']}\n")

        # Analysis
        analysis = error_info.get("analysis", {})
        if analysis:
            lines.append("Analysis:")
            lines.append(f"  Category: {analysis.get('error_category', 'unknown')}")
            lines.append(f"  Likely cause: {analysis.get('likely_cause', 'unknown')}")
            lines.append(f"  Affected: {analysis.get('affected_component', 'unknown')}")
            lines.append("")

        # Suggestions
        suggestions = error_info.get("suggestions", [])
        if suggestions:
            lines.append("Suggestions to fix:")
            for i, suggestion in enumerate(suggestions, 1):
                lines.append(f"  {i}. {suggestion}")
            lines.append("")

        # Traceback (shortened)
        if "traceback" in error_info:
            tb = error_info["traceback"]
            tb_lines = tb.split("\n")
            # Show only last 10 lines of traceback
            if len(tb_lines) > 10:
                lines.append("Traceback (last 10 lines):")
                lines.append("  " + "\n  ".join(tb_lines[-10:]))
            else:
                lines.append("Traceback:")
                lines.append("  " + "\n  ".join(tb_lines))

        return "\n".join(lines)

    def create_retry_config(
        self,
        original_config: Dict[str, Any],
        error_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create modified config for retry based on error analysis.
        基于错误分析创建重试的修改配置。

        Args:
            original_config: Original configuration that failed
            error_info: Error information from handle_exception

        Returns:
            Modified configuration for retry
        """
        retry_config = original_config.copy()

        # TODO: Implement intelligent config modification based on error type
        # Examples:
        # - If KeyError for variable name, fix variable names
        # - If FileNotFoundError, adjust paths
        # - If numerical error, adjust parameter ranges

        logger.info("[ErrorHandler] Generated retry configuration")

        return retry_config
