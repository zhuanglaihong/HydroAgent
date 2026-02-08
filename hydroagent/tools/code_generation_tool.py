"""
Author: HydroAgent Team
Date: 2025-01-25 14:00:00
LastEditTime: 2025-01-25 14:00:00
LastEditors: HydroAgent Team
Description: Code generation tool for custom hydrological analysis
FilePath: /HydroAgent/hydroagent/tools/code_generation_tool.py
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
from pathlib import Path

logger = logging.getLogger(__name__)


class CodeGenerationTool(BaseTool):
    """
    Code generation tool for custom hydrological analysis.
    代码生成工具 - 为自定义水文分析生成Python代码。

    This tool generates executable Python code for analysis tasks beyond
    hydromodel's native capabilities, such as:
    - Runoff coefficient calculation
    - Flow duration curves (FDC)
    - Custom hydrological indicators
    - Data visualization scripts

    使用场景（实验4）：
    - 用户需求："率定完成后，请帮我计算流域的径流系数，并画FDC曲线"
    - IntentAgent识别需要代码生成
    - TaskPlanner生成工具链：[validate_data, calibrate, evaluate, code_generation]
    - CodeGenerationTool生成并执行代码
    """

    def __init__(self, llm_interface=None):
        """
        Initialize code generation tool.

        Args:
            llm_interface: LLM interface for code generation (uses code-specific model)
        """
        super().__init__()
        self.llm_interface = llm_interface
        self.logger = logging.getLogger(self.__class__.__name__)

    def _define_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="code_generation",
            description="生成自定义分析代码 (Generate custom analysis code)",
            category=ToolCategory.ANALYSIS,
            version="1.0.0",
            input_schema={
                "analysis_types": "List[str] - Analysis types to generate code for (e.g., ['runoff_coefficient', 'fdc'])",
                "calibration_dir": "str - Calibration directory containing results",
                "basin_ids": "Optional[List[str]] - Basin IDs to analyze",
                "data_source": "Optional[str] - Data source (default: 'camels_us')",
                "workspace_dir": "Optional[str] - Directory to save generated code (default: 'generated_code/')",
                "execute_code": "Optional[bool] - Whether to execute generated code immediately (default: True)",
                "max_retries": "Optional[int] - Max retries for code generation with error feedback (default: 3)"
            },
            output_schema={
                "generated_files": "List[str] - List of generated code file paths",
                "execution_results": "List[Dict] - Execution results for each generated file",
                "success_count": "int - Number of successfully generated and executed scripts",
                "failed_count": "int - Number of failed scripts"
            },
            dependencies=["calibrate"],  # Usually runs after calibration
            required_config_keys=["analysis_types", "calibration_dir"]
        )

    def execute(self, inputs: Dict[str, Any]) -> ToolResult:
        """
        Execute code generation for custom analysis.

        Args:
            inputs: Code generation parameters

        Returns:
            ToolResult: Code generation and execution results
        """
        analysis_types = inputs["analysis_types"]
        calibration_dir = inputs["calibration_dir"]
        basin_ids = inputs.get("basin_ids")
        data_source = inputs.get("data_source", "camels_us")
        workspace_dir = inputs.get("workspace_dir", "generated_code")
        execute_code = inputs.get("execute_code", True)
        max_retries = inputs.get("max_retries", 3)

        if not isinstance(analysis_types, list):
            analysis_types = [analysis_types]

        self.logger.info(f"[CodeGenerationTool] Generating code for {len(analysis_types)} analysis types")

        try:
            # Import code generation utilities
            from hydroagent.utils.code_generator import generate_code_with_feedback

            # Use the LLM interface passed during initialization
            # This should be a code-specific LLM (qwen-coder-turbo for API, deepseek-coder for Ollama)
            if self.llm_interface is None:
                raise ValueError(
                    "CodeGenerationTool requires llm_interface to be set. "
                    "Please provide a code-specific LLM when initializing the tool."
                )

            code_llm = self.llm_interface

            # Prepare workspace directory
            workspace_path = Path(workspace_dir)
            workspace_path.mkdir(parents=True, exist_ok=True)

            generated_files = []
            execution_results = []
            success_count = 0
            failed_count = 0

            # Generate code for each analysis type
            for analysis_type in analysis_types:
                self.logger.info(f"[CodeGenerationTool] Processing: {analysis_type}")

                # Prepare parameters
                params = {
                    "analysis_type": analysis_type,
                    "calibration_dir": calibration_dir,
                    "basin_ids": basin_ids,
                    "data_source": data_source,
                    "workspace_dir": str(workspace_path),
                }

                # Generate code with error feedback loop
                result = generate_code_with_feedback(
                    code_llm=code_llm,
                    workspace_dir=str(workspace_path),
                    timeout=300,  # 5 minutes per script
                    analysis_type=analysis_type,
                    params=params,
                    max_retries=max_retries
                )

                # Collect results
                if result.get("status") == "success":
                    self.logger.info(f"[CodeGenerationTool] ✓ {analysis_type} succeeded")
                    generated_files.append(result["code_file"])
                    execution_results.append({
                        "analysis_type": analysis_type,
                        "status": "success",
                        "code_file": result["code_file"],
                        "attempts": result.get("attempts", 1),
                        "execution_result": result.get("execution_result", {})
                    })
                    success_count += 1
                else:
                    self.logger.warning(f"[CodeGenerationTool] ✗ {analysis_type} failed: {result.get('error', 'Unknown error')}")
                    execution_results.append({
                        "analysis_type": analysis_type,
                        "status": "failed",
                        "error": result.get("error", "Unknown error"),
                        "attempts": result.get("attempts", max_retries),
                        "error_history": result.get("error_history", [])
                    })
                    failed_count += 1

            # Summary
            self.logger.info(f"[CodeGenerationTool] Code generation complete: {success_count} succeeded, {failed_count} failed")

            return ToolResult(
                success=success_count > 0,  # Success if at least one script worked
                data={
                    "generated_files": generated_files,
                    "execution_results": execution_results,
                    "success_count": success_count,
                    "failed_count": failed_count
                },
                metadata={
                    "analysis_types": analysis_types,
                    "calibration_dir": calibration_dir,
                    "workspace_dir": str(workspace_path),
                    "total_analysis": len(analysis_types)
                }
            )

        except Exception as e:
            self.logger.error(f"[CodeGenerationTool] Code generation failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                error=f"Code generation error: {str(e)}"
            )
