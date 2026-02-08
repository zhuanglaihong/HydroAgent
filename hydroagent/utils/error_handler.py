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
                    "suggestion": "In hydromodel, precipitation variable is typically 'prcp' or 'precipitation', not 'prec'",
                },
                "temp": {
                    "message": "Variable name error",
                    "suggestion": "Temperature variable should be 'tmean', 'tmin', or 'tmax', not 'temp'",
                },
            },
            "FileNotFoundError": {
                "datasets-origin": {
                    "message": "Data path configuration error",
                    "suggestion": "Check 'datasets-origin' path in config. Ensure it points to valid data directory",
                },
                "basin": {
                    "message": "Basin data not found",
                    "suggestion": "Basin ID may be incorrect or data not downloaded. Verify basin_id exists in dataset",
                },
            },
            "ValueError": {
                "date": {
                    "message": "Invalid date format",
                    "suggestion": "Time periods must use format: YYYY-MM-DD (e.g., '2000-01-01')",
                },
                "parameter": {
                    "message": "Invalid parameter value",
                    "suggestion": "Check parameter ranges in param_range.yaml. Values must be within specified bounds",
                },
            },
            "ImportError": {
                "hydromodel": {
                    "message": "hydromodel module not found",
                    "suggestion": "Install hydromodel: pip install git+https://github.com/OuyangWenyu/hydromodel.git",
                },
                "module": {
                    "message": "Missing required dependency",
                    "suggestion": "Install missing package using pip or conda",
                },
            },
            "TypeError": {
                "NoneType": {
                    "message": "Unexpected None value",
                    "suggestion": "A required value is None. Check if data was loaded correctly",
                },
                "array": {
                    "message": "Type mismatch in array operation",
                    "suggestion": "Data type conversion issue. Ensure numeric data is properly formatted",
                },
            },
        }

    def handle_exception(
        self, exception: Exception, context: Optional[Dict[str, Any]] = None
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
            "severity": "error",
        }

        # Analyze error
        analysis = self._analyze_error(exception, context)
        error_info["analysis"] = analysis

        # Generate suggestions
        suggestions = self._generate_suggestions(exception, analysis, context)
        error_info["suggestions"] = suggestions

        # Determine severity
        error_info["severity"] = self._determine_severity(exception)

        logger.error(
            f"[ErrorHandler] {error_info['error_type']}: {error_info['error_message']}"
        )

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
        self, exception: Exception, context: Optional[Dict[str, Any]]
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
            "affected_component": "unknown",
        }

        error_type = type(exception).__name__
        error_message = str(exception).lower()

        # ✅ Enhanced categorization: Network, API, Code, Data, Config, etc.

        # 🔧 v6.1 Fix: Message-based classification (highest priority for Experiment C)
        # These rules check error message content for accurate classification
        # IMPORTANT: More specific rules must come BEFORE general rules

        # Configuration errors (most specific: "configuration validation failed")
        if "configuration validation failed" in error_message or "配置验证失败" in error_message:
            analysis["error_category"] = "configuration"
            analysis["likely_cause"] = "Configuration validation failed"
            analysis["affected_component"] = "configuration"

        # Data file errors (训练期太短, 数据不足) - before general "训练期" rule
        elif any(keyword in error_message for keyword in ["训练期太短", "测试期太短", "数据不足", "insufficient data", "data length"]):
            analysis["error_category"] = "data"
            analysis["likely_cause"] = "Insufficient or missing data"
            analysis["affected_component"] = "data loading"

        # Intent recognition errors
        elif "intent recognition failed" in error_message:
            analysis["error_category"] = "data_validation"  # Treat as validation error (invalid query)
            analysis["likely_cause"] = "Invalid or malformed query"
            analysis["affected_component"] = "intent analysis"

        # Data validation errors (流域ID) - specific basin validation
        elif any(keyword in error_message for keyword in ["流域", "basin"]) and ("验证失败" in error_message or "validation failed" in error_message):
            analysis["error_category"] = "data_validation"
            analysis["likely_cause"] = "Basin ID or data validation failed"
            analysis["affected_component"] = "data validation"

        # Configuration errors (general: time periods, warmup) - less specific
        elif any(keyword in error_message for keyword in ["训练期", "测试期", "warmup", "train period", "test period"]) and "validation" in error_message:
            analysis["error_category"] = "configuration"
            analysis["likely_cause"] = "Configuration validation failed"
            analysis["affected_component"] = "configuration"

        # Numerical computation errors (参数范围过窄, 数值计算)
        elif any(keyword in error_message for keyword in ["numerical", "nan", "inf", "参数范围", "parameter range"]):
            analysis["error_category"] = "numerical"
            analysis["likely_cause"] = "Numerical computation error or parameter issue"
            analysis["affected_component"] = "model computation"

        # Runtime errors (算法参数错误, ngs=1等)
        elif any(keyword in error_message for keyword in ["algorithm", "ngs", "rep", "算法"]):
            analysis["error_category"] = "runtime"
            analysis["likely_cause"] = "Algorithm parameter error"
            analysis["affected_component"] = "calibration"

        # Code generation errors (生成代码失败, sklearn等)
        elif any(keyword in error_message for keyword in ["code generation", "生成代码", "sklearn", "import"]):
            analysis["error_category"] = "code"
            analysis["likely_cause"] = "Code generation or execution failed"
            analysis["affected_component"] = "code generation"

        # Type-based classification (fallback for unmatched messages)
        # Only apply if message-based classification didn't match
        elif analysis["error_category"] == "unknown":
            # 1. Network and API errors (highest priority)
            if error_type in ["APITimeoutError", "TimeoutError", "RequestException", "ConnectionError"]:
                analysis["error_category"] = "network"
                analysis["likely_cause"] = "Network connection timeout or API request timeout"
                analysis["affected_component"] = "network/api"
            elif "timeout" in error_message or "timed out" in error_message:
                analysis["error_category"] = "network"
                analysis["likely_cause"] = "Request timeout (network or API)"
                analysis["affected_component"] = "network/api"
            elif "connection" in error_message or "connect" in error_message:
                analysis["error_category"] = "network"
                analysis["likely_cause"] = "Network connection failed"
                analysis["affected_component"] = "network"

            # 2. LLM-specific errors
            elif "LLMTimeoutError" in error_type or "llm" in error_message:
                analysis["error_category"] = "llm_api"
                analysis["likely_cause"] = "LLM API request failed or timeout"
                analysis["affected_component"] = "llm_interface"

            # 3. Code errors (NameError, SyntaxError, etc.)
            elif error_type in ["NameError", "SyntaxError", "IndentationError"]:
                analysis["error_category"] = "code"
                analysis["likely_cause"] = "Code error (undefined variable or syntax error)"
                analysis["affected_component"] = "code"

            # 4. Configuration errors
            elif error_type in ["KeyError", "AttributeError"]:
                analysis["error_category"] = "configuration"
                analysis["likely_cause"] = "Configuration or data field mismatch"
                analysis["affected_component"] = "config/data"

            # 5. Data errors
            elif error_type in ["FileNotFoundError", "IOError"]:
                analysis["error_category"] = "data"
                analysis["likely_cause"] = "Missing or inaccessible file/data"
                analysis["affected_component"] = "data loading"
            elif "netcdf" in error_message or "hdf" in error_message:
                analysis["error_category"] = "data"
                analysis["likely_cause"] = "Data file format error or corrupted file"
                analysis["affected_component"] = "data loading"

            # 6. Data validation errors
            elif error_type in ["ValueError", "TypeError"]:
                analysis["error_category"] = "data_validation"
                analysis["likely_cause"] = "Invalid data type or value"
                analysis["affected_component"] = "data processing"

            # 7. Dependency errors
            elif error_type in ["ImportError", "ModuleNotFoundError"]:
                analysis["error_category"] = "dependency"
                analysis["likely_cause"] = "Missing required package"
                analysis["affected_component"] = "environment"

            # 8. Numerical errors
            elif "numerical" in error_message or "nan" in error_message:
                analysis["error_category"] = "numerical"
                analysis["likely_cause"] = "Numerical instability or invalid computation"
                analysis["affected_component"] = "model computation"

            # 9. Runtime errors
            elif error_type in ["RuntimeError", "AssertionError"]:
                analysis["error_category"] = "runtime"
                analysis["likely_cause"] = "Runtime error or assertion failed"
                analysis["affected_component"] = "execution"

        return analysis

    def _generate_suggestions(
        self,
        exception: Exception,
        analysis: Dict[str, Any],
        context: Optional[Dict[str, Any]],
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

        # ✅ Enhanced category-specific suggestions with detailed steps

        if analysis["error_category"] == "network":
            suggestions.append("🌐 Network Error - Possible Solutions:")
            suggestions.append("  1. Check your internet connection")
            suggestions.append("  2. If using proxy, verify proxy settings")
            suggestions.append("  3. Increase timeout value in config (e.g., timeout=120)")
            suggestions.append("  4. Try again after a few minutes (server may be temporarily down)")
            suggestions.append("  5. Check firewall settings blocking API requests")

        elif analysis["error_category"] == "llm_api":
            suggestions.append("🤖 LLM API Error - Possible Solutions:")
            suggestions.append("  1. Verify API key in configs/definitions_private.py:")
            suggestions.append("     - Check OPENAI_API_KEY is set correctly")
            suggestions.append("     - Ensure no extra spaces or quotes")
            suggestions.append("  2. Check API quota/balance:")
            suggestions.append("     - Visit your cloud provider dashboard")
            suggestions.append("     - Verify free tier limits not exceeded")
            suggestions.append("  3. Try using a different model (e.g., switch to qwen-turbo)")
            suggestions.append("  4. If using Ollama, ensure service is running: ollama serve")

        elif analysis["error_category"] == "code":
            suggestions.append("💻 Code Error - Possible Solutions:")
            suggestions.append("  1. Review the generated Python code in logs")
            suggestions.append("  2. Check for undefined variables (NameError):")
            suggestions.append("     - Ensure all variables are defined before use")
            suggestions.append("  3. Check for syntax errors (SyntaxError):")
            suggestions.append("     - Verify parentheses, brackets, quotes are balanced")
            suggestions.append("  4. If custom code generation, simplify the analysis request")
            suggestions.append("  5. Report issue if error persists (include traceback)")

        elif analysis["error_category"] == "configuration":
            suggestions.append("⚙️ Configuration Error - Possible Solutions:")
            suggestions.append("  1. Check configs/config.py for typos:")
            suggestions.append("     - Verify variable names (e.g., prcp not prec)")
            suggestions.append("     - Ensure data types match (int, str, list, etc.)")
            suggestions.append("  2. Check configs/definitions_private.py:")
            suggestions.append("     - DATASET_DIR path exists and is accessible")
            suggestions.append("     - PROJECT_DIR points to correct location")
            suggestions.append("  3. Compare with example_definitions_private.py")
            suggestions.append("  4. Ensure all required config fields are set")

        elif analysis["error_category"] == "data":
            suggestions.append("📁 Data File Error - Possible Solutions:")
            suggestions.append("  1. Check data file integrity:")
            suggestions.append("     - If NetCDF/HDF error, data file may be corrupted")
            suggestions.append("     - Delete and re-download: rm ~/.cache/camels_us*")
            suggestions.append("  2. Verify DATASET_DIR in config points to valid path")
            suggestions.append("  3. Ensure sufficient disk space for data files")
            suggestions.append("  4. Check file permissions (read access required)")
            suggestions.append("  5. If using custom data, verify format matches CAMELS structure")

        elif analysis["error_category"] == "data_validation":
            suggestions.append("✅ Data Validation Error - Possible Solutions:")
            suggestions.append("  1. Verify basin ID exists in CAMELS dataset:")
            suggestions.append("     - Valid IDs are 8-digit USGS gage IDs")
            suggestions.append("     - Check available basins at: https://ral.ucar.edu/solutions/products/camels")
            suggestions.append("  2. Check time period validity:")
            suggestions.append("     - CAMELS data covers 1980-2014")
            suggestions.append("     - Ensure train_period is before test_period")
            suggestions.append("  3. Validate parameter ranges:")
            suggestions.append("     - Iterations/repetitions must be positive integers")
            suggestions.append("     - NSE threshold must be in [0, 1]")

        elif analysis["error_category"] == "dependency":
            suggestions.append("📦 Dependency Error - Possible Solutions:")
            suggestions.append("  1. Install missing package:")
            suggestions.append("     - hydromodel: pip install git+https://github.com/OuyangWenyu/hydromodel.git")
            suggestions.append("     - spotpy: pip install spotpy")
            suggestions.append("     - Other: pip install -r requirements.txt")
            suggestions.append("  2. Verify virtual environment:")
            suggestions.append("     - Activate: .venv/Scripts/activate (Windows) or source .venv/bin/activate (Linux/Mac)")
            suggestions.append("     - Check: which python (should point to .venv)")
            suggestions.append("  3. Upgrade outdated packages: pip install --upgrade <package>")

        elif analysis["error_category"] == "numerical":
            suggestions.append("🔢 Numerical Error - Possible Solutions:")
            suggestions.append("  1. Adjust parameter ranges in param_range.yaml:")
            suggestions.append("     - Avoid extreme values (e.g., [0, 1e10])")
            suggestions.append("     - Use reasonable ranges for your basin")
            suggestions.append("  2. Reduce iteration count if numerical overflow occurs")
            suggestions.append("  3. Check input data for NaN or infinite values")
            suggestions.append("  4. Try a different calibration algorithm (e.g., DE instead of SCE-UA)")
            suggestions.append("  5. Ensure sufficient warmup period (recommend ≥365 days)")

        elif analysis["error_category"] == "runtime":
            suggestions.append("⚠️ Runtime Error - Possible Solutions:")
            suggestions.append("  1. Check error message and traceback for specific issue")
            suggestions.append("  2. If memory error:")
            suggestions.append("     - Reduce batch size (fewer basins at once)")
            suggestions.append("     - Close other applications to free memory")
            suggestions.append("  3. If algorithm initialization error:")
            suggestions.append("     - Check algorithm parameters (e.g., ngs ≥ 2 for SCE-UA)")
            suggestions.append("     - Ensure parameters don't conflict")
            suggestions.append("  4. If model computation error:")
            suggestions.append("     - Verify model name is correct (GR4J, XAJ, etc.)")
            suggestions.append("     - Check if warmup period is too short (use ≥365 days)")

        # Add generic fallback suggestions if no category-specific ones were added
        if not suggestions:
            suggestions.append("Review error message and stack trace for details")
            suggestions.append("Check system logs for additional information")
            suggestions.append("Ensure all dependencies are properly installed")

        # Context-specific suggestions
        if context:
            if "config" in context:
                suggestions.append(
                    "Review generated configuration for potential issues"
                )

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
        severity_emoji = {"critical": "🔴", "error": "⚠️", "warning": "⚡"}
        emoji = severity_emoji.get(error_info["severity"], "❌")

        lines.append(
            f"{emoji} {error_info['error_type']}: {error_info['error_message']}\n"
        )

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
        self, original_config: Dict[str, Any], error_info: Dict[str, Any]
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


class GracefulErrorHandler:
    """
    优雅的错误处理器，提供简洁的终端输出和详细的日志记录。

    Purpose:
    - Format errors for clean terminal display (user-friendly)
    - Log detailed error information (developer-friendly)
    - Generate standardized error responses
    - Centralize error handling logic in hydroagent core
    """

    @staticmethod
    def format_error_for_terminal(
        error: Exception, context: str = "执行过程", max_length: int = 150
    ) -> str:
        """
        格式化错误信息供终端显示（简洁版）。

        Args:
            error: 捕获的异常
            context: 错误发生的上下文描述
            max_length: 错误信息最大长度

        Returns:
            格式化的简洁错误信息
        """
        error_type = type(error).__name__
        error_msg = str(error)

        # 截断过长的错误信息
        if len(error_msg) > max_length:
            error_msg = error_msg[:max_length] + "..."

        return f"[{error_type}] {error_msg}"

    @staticmethod
    def log_detailed_error(
        error: Exception,
        context: str = "执行过程",
        phase: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> None:
        """
        记录详细的错误信息到日志（包含完整堆栈）。

        Args:
            error: 捕获的异常
            context: 错误发生的上下文
            phase: 当前执行阶段（如 "intent", "runner"）
            task_id: 当前任务ID
        """
        error_type = type(error).__name__
        error_msg = str(error)

        log_prefix = f"[{context}]"
        if phase:
            log_prefix += f" [Phase: {phase}]"
        if task_id:
            log_prefix += f" [Task: {task_id}]"

        # 记录错误摘要
        logger.error(f"{log_prefix} {error_type}: {error_msg}")

        # 记录完整堆栈（exc_info=True 自动包含堆栈）
        logger.error(f"{log_prefix} Full traceback:", exc_info=True)

    @staticmethod
    def create_error_response(
        error: Exception,
        context: str = "pipeline",
        session_id: Optional[str] = None,
        workspace=None,
        additional_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        创建标准化的错误响应字典。

        Args:
            error: 捕获的异常
            context: 错误发生的上下文
            session_id: 会话ID
            workspace: 工作目录 (Path or str)
            additional_info: 额外信息

        Returns:
            标准化的错误响应
        """
        error_response = {
            "success": False,
            "error": str(error),
            "error_type": type(error).__name__,
            "context": context,
        }

        if session_id:
            error_response["session_id"] = session_id

        if workspace:
            error_response["workspace"] = str(workspace)

        if additional_info:
            error_response.update(additional_info)

        return error_response

    @staticmethod
    def print_terminal_error(
        error: Exception,
        context: str = "执行过程",
        log_file=None,
        workspace=None,
        elapsed_time: Optional[float] = None,
        checkpoint_file=None,
    ) -> None:
        """
        打印格式化的错误信息到终端（用户友好）。

        Args:
            error: 捕获的异常
            context: 错误发生的上下文
            log_file: 日志文件路径 (Path or str)
            workspace: 工作目录 (Path or str)
            elapsed_time: 已执行时长（秒）
            checkpoint_file: Checkpoint文件路径 (Path or str)
        """
        error_type = type(error).__name__
        error_msg = str(error)

        # 截断过长的错误信息
        max_length = 150
        if len(error_msg) > max_length:
            error_msg = error_msg[:max_length] + "..."

        # 格式化输出
        print("\n" + "=" * 70)
        print(f"执行中断: {context}")
        print("=" * 70)
        print(f"\n错误类型: {error_type}")
        print(f"错误信息: {error_msg}")

        if log_file:
            print(f"\n详细日志: {log_file}")

        if workspace:
            print(f"工作目录: {workspace}")

        if checkpoint_file:
            print(f"Checkpoint: {checkpoint_file}")

        if elapsed_time is not None:
            print(f"已执行时长: {elapsed_time:.1f}s")

        print("\n" + "=" * 70)


def handle_pipeline_error(
    error: Exception,
    phase: str,
    session_id: Optional[str] = None,
    workspace=None,
    checkpoint_manager=None,
) -> Dict[str, Any]:
    """
    处理 pipeline 执行错误的便捷函数。

    This is a convenience function that:
    1. Logs detailed error information
    2. Marks checkpoint as failed (if checkpoint_manager provided)
    3. Returns standardized error response

    Args:
        error: 捕获的异常
        phase: 当前执行阶段 (e.g., "intent", "planner", "runner")
        session_id: 会话ID
        workspace: 工作目录 (Path or str)
        checkpoint_manager: Checkpoint管理器实例

    Returns:
        标准化的错误响应字典
    """
    handler = GracefulErrorHandler()

    # 记录详细日志
    handler.log_detailed_error(
        error=error, context="Orchestrator Pipeline", phase=phase
    )

    # 标记 checkpoint 失败
    if checkpoint_manager:
        try:
            checkpoint_manager.mark_experiment_failed(str(error))
        except Exception as e:
            logger.warning(f"Failed to mark checkpoint as failed: {e}")

    # 创建错误响应
    return handler.create_error_response(
        error=error,
        context=f"pipeline_phase_{phase}",
        session_id=session_id,
        workspace=workspace,
    )


def format_traceback() -> str:
    """
    Format current exception traceback.
    格式化当前异常回溯。

    Returns:
        Formatted traceback string
    """
    return traceback.format_exc()


def analyze_execution_error(
    error_message: str, code_content: str, execution_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    分析代码执行错误并提供修复建议（v4.0）。
    Analyze code execution error and provide fix suggestions.

    Args:
        error_message: 错误信息（stderr）
        code_content: 原始代码内容
        execution_context: 执行上下文（参数、数据路径等）

    Returns:
        错误分析结果
        {
            "error_type": str,  # import_error, runtime_error, data_error, etc.
            "root_cause": str,  # 根本原因
            "fix_suggestions": List[str],  # 修复建议
            "needs_config_update": bool,  # 是否需要更新config
            "needs_code_regeneration": bool  # 是否需要重新生成代码
        }
    """
    logger.info("[ErrorAnalyzer] 分析执行错误...")

    analysis = {
        "error_type": "unknown",
        "root_cause": "",
        "fix_suggestions": [],
        "needs_config_update": False,
        "needs_code_regeneration": False,
    }

    error_lower = error_message.lower()

    # 1. 导入错误
    if "importerror" in error_lower or "modulenotfounderror" in error_lower:
        analysis["error_type"] = "import_error"
        analysis["root_cause"] = "缺少必要的Python库"
        analysis["fix_suggestions"].append("安装缺失的依赖包")
        analysis["needs_code_regeneration"] = True

    # 2. 文件未找到错误
    elif "filenotfounderror" in error_lower or "no such file" in error_lower:
        analysis["error_type"] = "data_error"
        analysis["root_cause"] = "数据文件路径不正确或文件不存在"
        analysis["fix_suggestions"].append("检查数据文件路径")
        analysis["fix_suggestions"].append("确认calibration已完成并生成了结果文件")
        analysis["needs_config_update"] = True  # 可能需要更新数据路径

    # 3. KeyError / IndexError
    elif "keyerror" in error_lower or "indexerror" in error_lower:
        analysis["error_type"] = "data_structure_error"
        analysis["root_cause"] = "数据结构不匹配或字段缺失"
        analysis["fix_suggestions"].append("检查数据文件格式")
        analysis["fix_suggestions"].append("更新代码以适配实际数据结构")
        analysis["needs_code_regeneration"] = True

    # 4. ValueError / TypeError
    elif "valueerror" in error_lower or "typeerror" in error_lower:
        analysis["error_type"] = "runtime_error"
        analysis["root_cause"] = "数据类型或值不符合预期"
        analysis["fix_suggestions"].append("检查输入数据的类型和范围")
        analysis["fix_suggestions"].append("添加数据验证和类型转换")
        analysis["needs_code_regeneration"] = True

    # 5. 其他运行时错误
    else:
        analysis["error_type"] = "general_runtime_error"
        analysis["root_cause"] = "代码执行过程中发生未预期的错误"
        analysis["fix_suggestions"].append("检查完整的错误堆栈信息")
        analysis["fix_suggestions"].append("可能需要重新生成代码")
        analysis["needs_code_regeneration"] = True

    logger.info(f"[ErrorAnalyzer] 错误类型: {analysis['error_type']}")
    logger.info(f"[ErrorAnalyzer] 根本原因: {analysis['root_cause']}")

    return analysis
