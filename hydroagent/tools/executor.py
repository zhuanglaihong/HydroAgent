"""
Author: HydroAgent Team
Date: 2025-01-25 10:00:00
LastEditTime: 2025-01-25 10:00:00
LastEditors: HydroAgent Team
Description: Tool executor for unified tool execution
FilePath: /HydroAgent/hydroagent/tools/executor.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from typing import Dict, Any, List, Optional
from hydroagent.tools.base_tool import ToolResult, BaseTool
from hydroagent.tools.registry import ToolRegistry
import logging
import hashlib
import json

logger = logging.getLogger(__name__)


class ToolExecutionError(Exception):
    """Tool execution error"""
    pass


class ToolExecutor:
    """
    Tool executor - unified interface for executing tools.

    Features:
    - Execute single tool or tool chain
    - Input validation
    - Result caching
    - Error handling
    - Dependency checking
    """

    def __init__(self, registry: Optional[ToolRegistry] = None):
        """
        Initialize tool executor.

        Args:
            registry: Tool registry (default: global registry)
        """
        from hydroagent.tools.registry import registry as global_registry
        self.registry = registry or global_registry
        self.result_cache: Dict[str, ToolResult] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def execute_tool(
        self,
        tool_name: str,
        inputs: Dict[str, Any],
        use_cache: bool = True
    ) -> ToolResult:
        """
        Execute a single tool.

        Args:
            tool_name: Tool name
            inputs: Input parameters
            use_cache: Whether to use cached results

        Returns:
            ToolResult: Execution result
        """
        # Check cache
        cache_key = self._make_cache_key(tool_name, inputs)
        if use_cache and cache_key in self.result_cache:
            self.logger.info(f"[ToolExecutor] Using cached result for {tool_name}")
            return self.result_cache[cache_key]

        # Get tool from registry
        tool = self.registry.get_tool(tool_name)
        if not tool:
            error_msg = f"Tool '{tool_name}' not found in registry"
            self.logger.error(f"[ToolExecutor] {error_msg}")
            return ToolResult(
                success=False,
                error=error_msg
            )

        # Check dependencies
        deps_ok, missing = self.registry.check_dependencies(tool_name)
        if not deps_ok:
            error_msg = f"Missing dependencies for '{tool_name}': {missing}"
            self.logger.error(f"[ToolExecutor] {error_msg}")
            return ToolResult(
                success=False,
                error=error_msg
            )

        # Validate inputs
        is_valid, error_msg = tool.validate_inputs(inputs)
        if not is_valid:
            error_full = f"Input validation failed for '{tool_name}': {error_msg}"
            self.logger.error(f"[ToolExecutor] {error_full}")
            return ToolResult(
                success=False,
                error=error_full
            )

        # Execute tool
        try:
            self.logger.info(f"[ToolExecutor] Executing tool: {tool_name}")
            result = tool.execute(inputs)

            # Cache successful results
            if use_cache and result.success:
                self.result_cache[cache_key] = result

            self.logger.info(
                f"[ToolExecutor] Tool '{tool_name}' executed "
                f"{'successfully' if result.success else 'with errors'}"
            )
            return result

        except Exception as e:
            error_msg = f"Execution error in '{tool_name}': {str(e)}"
            self.logger.error(f"[ToolExecutor] {error_msg}", exc_info=True)
            return ToolResult(
                success=False,
                error=error_msg
            )

    def execute_chain(
        self,
        tool_chain: List[Dict[str, Any]],
        stop_on_error: bool = True
    ) -> List[ToolResult]:
        """
        Execute a chain of tools sequentially.

        Args:
            tool_chain: List of tool specifications, format:
                [
                    {"tool": "tool_name", "inputs": {...}},
                    ...
                ]
            stop_on_error: Whether to stop on first error

        Returns:
            List[ToolResult]: Results for each tool in chain
        """
        results = []
        context = {}  # For passing data between tools

        self.logger.info(f"[ToolExecutor] Executing tool chain ({len(tool_chain)} tools)")

        for idx, step in enumerate(tool_chain):
            tool_name = step.get("tool")
            inputs = step.get("inputs", {})

            if not tool_name:
                error_msg = f"Tool chain step {idx}: missing 'tool' key"
                self.logger.error(f"[ToolExecutor] {error_msg}")
                results.append(ToolResult(success=False, error=error_msg))
                if stop_on_error:
                    break
                continue

            # Resolve references to previous tool outputs (Phase 2 feature)
            inputs = self._resolve_references(inputs, context)

            # Special handling for custom_analysis: auto-inject calibration_metrics from evaluate
            if tool_name == "custom_analysis" and "calibration_metrics" not in inputs:
                # Look for evaluate results in context
                if "evaluate" in context:
                    evaluate_data = context["evaluate"]
                    calibration_metrics = evaluate_data.get("metrics") or evaluate_data.get("performance")
                    if calibration_metrics:
                        inputs["calibration_metrics"] = calibration_metrics
                        self.logger.debug(f"[ToolExecutor] Auto-injected calibration_metrics into custom_analysis")

            # Execute tool
            result = self.execute_tool(tool_name, inputs)
            results.append(result)

            # Update context with tool output
            if result.success:
                context[tool_name] = result.data
                self.logger.debug(f"[ToolExecutor] Added '{tool_name}' output to context")

            # Handle error - check if tool is optional
            if not result.success:
                # Check if tool is required (default True if not specified)
                is_required = step.get("required", True)

                if not is_required:
                    # Optional tool failed - log warning but continue
                    self.logger.warning(
                        f"[ToolExecutor] Optional tool '{tool_name}' failed at step {idx}, continuing..."
                    )
                    # Don't break - continue to next tool
                elif stop_on_error:
                    # Required tool failed - stop execution
                    self.logger.warning(
                        f"[ToolExecutor] Required tool '{tool_name}' failed at step {idx}, stopping"
                    )
                    break

        self.logger.info(
            f"[ToolExecutor] Tool chain completed: "
            f"{sum(1 for r in results if r.success)}/{len(results)} succeeded"
        )
        return results

    def _make_cache_key(self, tool_name: str, inputs: Dict[str, Any]) -> str:
        """
        Generate cache key from tool name and inputs.

        Args:
            tool_name: Tool name
            inputs: Input parameters

        Returns:
            str: Cache key (MD5 hash)
        """
        try:
            input_str = json.dumps(inputs, sort_keys=True)
            hash_val = hashlib.md5(input_str.encode()).hexdigest()
            return f"{tool_name}:{hash_val}"
        except Exception as e:
            # If inputs not JSON-serializable, use str representation
            self.logger.debug(f"[ToolExecutor] Failed to hash inputs: {e}")
            return f"{tool_name}:{str(inputs)}"

    def _resolve_references(
        self,
        inputs: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Resolve references in inputs to previous tool outputs.

        Example: {"result_dir": "${calibrate.output_dir}"}

        Phase 2 implementation: Recursively resolve ${tool.field} references

        Args:
            inputs: Input parameters with potential references
            context: Context with previous tool outputs

        Returns:
            Dict[str, Any]: Resolved inputs
        """
        import re

        def resolve_value(value):
            """Recursively resolve a single value"""
            if isinstance(value, str):
                # Pattern: ${tool_name.field.subfield}
                pattern = r'\$\{([^}]+)\}'
                matches = re.findall(pattern, value)

                for match in matches:
                    parts = match.split('.')
                    tool_name = parts[0]

                    if tool_name not in context:
                        self.logger.warning(
                            f"[ToolExecutor] Reference '${{{match}}}' not found: "
                            f"tool '{tool_name}' not in context"
                        )
                        continue

                    # Navigate through nested fields
                    resolved = context[tool_name]
                    for part in parts[1:]:
                        if isinstance(resolved, dict) and part in resolved:
                            resolved = resolved[part]
                        else:
                            self.logger.warning(
                                f"[ToolExecutor] Reference '${{{match}}}' failed: "
                                f"field '{part}' not found"
                            )
                            resolved = None
                            break

                    if resolved is not None:
                        # Replace reference with resolved value
                        value = value.replace(f"${{{match}}}", str(resolved))
                        self.logger.debug(
                            f"[ToolExecutor] Resolved '${{{match}}}' → '{resolved}'"
                        )

                return value

            elif isinstance(value, dict):
                return {k: resolve_value(v) for k, v in value.items()}

            elif isinstance(value, list):
                return [resolve_value(v) for v in value]

            else:
                return value

        return resolve_value(inputs)

    def clear_cache(self) -> None:
        """Clear result cache"""
        self.result_cache.clear()
        self.logger.info("[ToolExecutor] Cleared result cache")

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        return {
            "cached_results": len(self.result_cache)
        }
