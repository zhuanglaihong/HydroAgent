"""
Author: HydroAgent Team
Date: 2025-01-25 14:30:00
LastEditTime: 2025-01-25 14:30:00
LastEditors: HydroAgent Team
Description: Custom analysis tool with LLM-assisted execution planning
FilePath: /HydroAgent/hydroagent/tools/custom_analysis_tool.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from hydroagent.tools.base_tool import (
    BaseTool,
    ToolResult,
    ToolMetadata,
    ToolCategory,
)
from typing import Dict, Any, List, Optional
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class CustomAnalysisTool(BaseTool):
    """
    Custom analysis tool with LLM-assisted execution planning.
    自定义分析工具 - 使用LLM辅助执行未预见的分析任务。

    This tool handles unforeseen analysis requests by:
    1. Using LLM to understand the analysis requirements
    2. Deciding execution strategy:
       - Generate custom code (via CodeGenerationTool)
       - Call existing hydromodel functions
       - Compose multiple tools
    3. Execute the chosen strategy

    用于处理完全未预见的任务（方案B+C结合）：
    - 用户需求："帮我分析流域的水量平衡"
    - CustomAnalysisTool使用LLM理解需求
    - LLM决定：需要生成代码计算入流、出流、蒸发
    - 调用CodeGenerationTool生成代码
    """

    def __init__(self, llm_interface=None, tool_registry=None):
        """
        Initialize custom analysis tool.

        Args:
            llm_interface: LLM interface for task understanding
            tool_registry: Tool registry for accessing other tools
        """
        super().__init__()
        self.llm_interface = llm_interface
        self.tool_registry = tool_registry
        self.logger = logging.getLogger(self.__class__.__name__)

    def _define_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="custom_analysis",
            description="LLM辅助的自定义分析工具 (LLM-assisted custom analysis)",
            category=ToolCategory.ANALYSIS,
            version="1.0.0",
            input_schema={
                "analysis_request": "str - Natural language description of analysis request",
                "calibration_dir": "Optional[str] - Calibration directory (if applicable)",
                "basin_ids": "Optional[List[str]] - Basin IDs (if applicable)",
                "data_source": "Optional[str] - Data source (default: 'camels_us')",
                "context": "Optional[Dict] - Additional context (previous results, etc.)"
            },
            output_schema={
                "strategy": "str - Chosen execution strategy (code_generation, hydromodel_call, tool_composition)",
                "execution_result": "Dict - Execution results",
                "generated_files": "Optional[List[str]] - Generated files (if code generation)"
            },
            dependencies=[],  # Can work independently
            required_config_keys=["analysis_request"]
        )

    def execute(self, inputs: Dict[str, Any]) -> ToolResult:
        """
        Execute custom analysis with LLM assistance.

        Args:
            inputs: Custom analysis parameters

        Returns:
            ToolResult: Analysis results
        """
        analysis_request = inputs["analysis_request"]
        calibration_dir = inputs.get("calibration_dir")
        basin_ids = inputs.get("basin_ids")
        data_source = inputs.get("data_source", "camels_us")
        context = inputs.get("context", {})

        self.logger.info(f"[CustomAnalysisTool] Processing custom request: {analysis_request}")

        try:
            # Step 1: Use LLM to understand analysis requirements
            task_understanding = self._understand_task(
                analysis_request=analysis_request,
                context=context
            )

            if not task_understanding["success"]:
                return ToolResult(
                    success=False,
                    error=f"Failed to understand task: {task_understanding.get('error')}"
                )

            self.logger.info(f"[CustomAnalysisTool] Task understanding: {task_understanding['strategy']}")

            # Step 2: Execute based on chosen strategy
            strategy = task_understanding["strategy"]

            if strategy == "code_generation":
                # Generate custom code
                result = self._execute_code_generation(
                    task_understanding=task_understanding,
                    calibration_dir=calibration_dir,
                    basin_ids=basin_ids,
                    data_source=data_source
                )

            elif strategy == "hydromodel_call":
                # Call existing hydromodel function
                result = self._execute_hydromodel_call(
                    task_understanding=task_understanding,
                    calibration_dir=calibration_dir
                )

            elif strategy == "tool_composition":
                # Compose multiple tools
                result = self._execute_tool_composition(
                    task_understanding=task_understanding
                )

            else:
                self.logger.warning(f"[CustomAnalysisTool] Unknown strategy: {strategy}, using code generation")
                result = self._execute_code_generation(
                    task_understanding=task_understanding,
                    calibration_dir=calibration_dir,
                    basin_ids=basin_ids,
                    data_source=data_source
                )

            return ToolResult(
                success=result.get("success", False),
                data={
                    "strategy": strategy,
                    "execution_result": result,
                    "generated_files": result.get("generated_files", []),
                    "task_understanding": task_understanding
                },
                metadata={
                    "analysis_request": analysis_request,
                    "strategy": strategy
                }
            )

        except Exception as e:
            self.logger.error(f"[CustomAnalysisTool] Custom analysis failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                error=f"Custom analysis error: {str(e)}"
            )

    def _understand_task(
        self,
        analysis_request: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Use LLM to understand analysis requirements and choose strategy.

        Args:
            analysis_request: User's analysis request
            context: Additional context

        Returns:
            Dict: Task understanding result with chosen strategy
        """
        if self.llm_interface is None:
            # Fallback: default to code generation
            self.logger.warning("[CustomAnalysisTool] No LLM interface, defaulting to code_generation strategy")
            return {
                "success": True,
                "strategy": "code_generation",
                "analysis_types": ["custom"],
                "reasoning": "No LLM available, defaulting to code generation"
            }

        # Prepare prompt for LLM
        prompt = f"""你是一个水文分析专家，负责理解用户的分析需求并选择执行策略。

用户需求：{analysis_request}

上下文信息：{json.dumps(context, ensure_ascii=False, indent=2)}

请分析这个需求，并返回JSON格式的执行计划：
{{
    "strategy": "code_generation | hydromodel_call | tool_composition",
    "reasoning": "选择此策略的原因",
    "analysis_types": ["分析类型1", "分析类型2"],  // 如果是code_generation
    "function_name": "函数名",  // 如果是hydromodel_call
    "tools": ["工具1", "工具2"]  // 如果是tool_composition
}}

策略说明：
- code_generation: 需要生成自定义代码（如径流系数、FDC曲线、水量平衡等）
- hydromodel_call: 可以直接调用hydromodel现有函数（如calibrate, evaluate, simulate）
- tool_composition: 需要组合多个已有工具完成任务

只返回JSON，不要额外解释。
"""

        try:
            response = self.llm_interface.generate(
                system_prompt="你是一个水文分析专家，负责理解用户的分析需求并选择执行策略。",
                user_prompt=prompt,
                temperature=0.1
            )

            # Parse JSON response
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()

            task_plan = json.loads(response)
            task_plan["success"] = True

            self.logger.info(f"[CustomAnalysisTool] LLM strategy: {task_plan['strategy']}")
            return task_plan

        except Exception as e:
            self.logger.error(f"[CustomAnalysisTool] Failed to parse LLM response: {e}")
            # Fallback to code generation
            return {
                "success": True,
                "strategy": "code_generation",
                "analysis_types": ["custom"],
                "reasoning": f"LLM parsing failed, defaulting to code generation. Error: {str(e)}"
            }

    def _execute_code_generation(
        self,
        task_understanding: Dict[str, Any],
        calibration_dir: Optional[str],
        basin_ids: Optional[List[str]],
        data_source: str
    ) -> Dict[str, Any]:
        """
        Execute code generation strategy.

        Args:
            task_understanding: Task understanding from LLM
            calibration_dir: Calibration directory
            basin_ids: Basin IDs
            data_source: Data source

        Returns:
            Dict: Execution result
        """
        self.logger.info("[CustomAnalysisTool] Executing code_generation strategy")

        # Get CodeGenerationTool from registry
        if self.tool_registry is None:
            from hydroagent.tools.registry import registry
            self.tool_registry = registry

        code_gen_tool = self.tool_registry.get_tool("code_generation")
        if code_gen_tool is None:
            return {
                "success": False,
                "error": "CodeGenerationTool not available in registry"
            }

        # Prepare inputs
        analysis_types = task_understanding.get("analysis_types", ["custom"])
        inputs = {
            "analysis_types": analysis_types,
            "calibration_dir": calibration_dir,
            "basin_ids": basin_ids,
            "data_source": data_source
        }

        # Execute code generation tool
        result = code_gen_tool.execute(inputs)

        return {
            "success": result.success,
            "generated_files": result.data.get("generated_files", []) if result.success else [],
            "execution_results": result.data.get("execution_results", []) if result.success else [],
            "error": result.error if not result.success else None
        }

    def _execute_hydromodel_call(
        self,
        task_understanding: Dict[str, Any],
        calibration_dir: Optional[str]
    ) -> Dict[str, Any]:
        """
        Execute hydromodel function call strategy.

        Args:
            task_understanding: Task understanding from LLM
            calibration_dir: Calibration directory

        Returns:
            Dict: Execution result
        """
        self.logger.info("[CustomAnalysisTool] Executing hydromodel_call strategy")

        function_name = task_understanding.get("function_name")
        if not function_name:
            return {
                "success": False,
                "error": "No function_name specified in task understanding"
            }

        # Call hydromodel function (to be implemented)
        self.logger.warning(f"[CustomAnalysisTool] hydromodel_call not fully implemented for: {function_name}")

        return {
            "success": False,
            "error": f"hydromodel_call strategy not yet fully implemented for {function_name}"
        }

    def _execute_tool_composition(
        self,
        task_understanding: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute tool composition strategy.

        Args:
            task_understanding: Task understanding from LLM

        Returns:
            Dict: Execution result
        """
        self.logger.info("[CustomAnalysisTool] Executing tool_composition strategy")

        tools = task_understanding.get("tools", [])
        if not tools:
            return {
                "success": False,
                "error": "No tools specified in task understanding"
            }

        # Compose and execute tools (to be implemented)
        self.logger.warning(f"[CustomAnalysisTool] tool_composition not fully implemented for: {tools}")

        return {
            "success": False,
            "error": f"tool_composition strategy not yet fully implemented for {tools}"
        }
