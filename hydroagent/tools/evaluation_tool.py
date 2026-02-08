"""
Author: HydroAgent Team
Date: 2025-01-25 11:15:00
LastEditTime: 2025-01-25 11:15:00
LastEditors: HydroAgent Team
Description: Model evaluation tool (independent from calibration)
FilePath: /HydroAgent/hydroagent/tools/evaluation_tool.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from hydroagent.tools.base_tool import (
    BaseTool,
    ToolResult,
    ToolMetadata,
    ToolCategory,
)
from typing import Dict, Any
import logging
import sys
from io import StringIO

logger = logging.getLogger(__name__)


class EvaluationTool(BaseTool):
    """
    Hydrological model evaluation tool.

    Evaluates calibrated models on test period.
    Can be used standalone or after calibration.
    """

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)

    def _define_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="evaluate",
            description="评估水文模型性能 (Evaluate hydrological model performance)",
            category=ToolCategory.EVALUATION,
            version="1.0.0",
            input_schema={
                "calibration_dir": "str - Calibration directory containing results",
                "config": "Optional[Dict] - Config dict (can be loaded from calibration_dir)"
            },
            output_schema={
                "metrics": "Dict - Evaluation metrics (NSE, RMSE, KGE, etc.)",
                "performance": "Dict - Performance statistics",
                "output_files": "List[str] - Generated output files",
                "raw_result": "Any - Raw hydromodel result"
            },
            dependencies=[],  # Optional dependency on calibrate
            required_config_keys=["calibration_dir"]
        )

    def execute(self, inputs: Dict[str, Any]) -> ToolResult:
        """
        Execute model evaluation.

        Args:
            inputs: Evaluation parameters

        Returns:
            ToolResult: Evaluation result
        """
        calibration_dir = inputs["calibration_dir"]
        config = inputs.get("config")

        try:
            # Import hydromodel
            try:
                from hydromodel.trainers.unified_evaluate import evaluate
                from hydromodel.configs.config_manager import load_config_from_calibration
                from hydroagent.utils import result_parser
            except ImportError as e:
                self.logger.error(f"[EvaluationTool] Failed to import hydromodel: {e}")
                return ToolResult(
                    success=False,
                    error=f"hydromodel not available: {str(e)}"
                )

            # Capture output
            stdout_capture = StringIO()
            stderr_capture = StringIO()
            old_stdout = sys.stdout
            old_stderr = sys.stderr

            try:
                # Silent mode for evaluation
                sys.stdout = stdout_capture
                sys.stderr = stderr_capture
                self.logger.info(f"[EvaluationTool] Loading config from {calibration_dir}")

                # Load config from calibration directory
                if not config:
                    config = load_config_from_calibration(calibration_dir)

                test_period = config["data_cfgs"]["test_period"]
                self.logger.info(f"[EvaluationTool] Test period: {test_period}")

                # Execute evaluation
                self.logger.info("[EvaluationTool] Calling evaluate()")
                result = evaluate(
                    config,
                    param_dir=calibration_dir,
                    eval_period=test_period,
                    eval_output_dir=None
                )

            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr

            self.logger.info("[EvaluationTool] Evaluation completed")

            # Parse result - 🔧 传递calibration_dir以支持批量处理
            parsed_result = result_parser.parse_evaluation_result(result, calibration_dir=calibration_dir)

            # 🔧 构建返回数据 - 包含basins_metrics_file（如果有）
            result_data = {
                "metrics": parsed_result.get("metrics", {}),
                "performance": parsed_result.get("performance", {}),
                "output_files": parsed_result.get("output_files", []),
                "raw_result": result
            }

            # 🔧 添加批量处理相关字段
            if "basins_metrics_file" in parsed_result:
                result_data["basins_metrics_file"] = parsed_result["basins_metrics_file"]
                self.logger.info(f"[EvaluationTool] 批量处理: 添加basins_metrics_file到返回数据")

            if "basin_count" in parsed_result and parsed_result["basin_count"] > 1:
                result_data["basin_count"] = parsed_result["basin_count"]
                self.logger.info(f"[EvaluationTool] 批量处理: {parsed_result['basin_count']}个流域")

            return ToolResult(
                success=True,
                data=result_data,
                metadata={
                    "calibration_dir": calibration_dir,
                    "test_period": test_period
                }
            )

        except Exception as e:
            self.logger.error(f"[EvaluationTool] Evaluation failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                error=f"Evaluation error: {str(e)}"
            )
