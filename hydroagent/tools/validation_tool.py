"""
Author: HydroAgent Team
Date: 2025-01-25 10:30:00
LastEditTime: 2025-01-25 10:30:00
LastEditors: HydroAgent Team
Description: Data validation tool for HydroAgent
FilePath: /HydroAgent/hydroagent/tools/validation_tool.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from hydroagent.tools.base_tool import (
    BaseTool,
    ToolResult,
    ToolMetadata,
    ToolCategory,
)
from hydroagent.utils.basin_validator import BasinValidator
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class DataValidationTool(BaseTool):
    """
    Data validation tool for hydrological datasets.

    Validates:
    - Basin ID existence in dataset
    - Time range availability
    - Required variables availability

    User-selected validation scope:
    - ✅ Basin ID existence
    - ✅ Time range availability
    - ✅ Variable validity
    """

    def __init__(self):
        super().__init__()
        self.validator = BasinValidator()
        self.logger = logging.getLogger(self.__class__.__name__)

    def _define_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="validate_data",
            description="验证流域数据的可用性和完整性 (Validate basin data availability and integrity)",
            category=ToolCategory.VALIDATION,
            version="1.0.0",
            input_schema={
                "basin_ids": "List[str] - Basin ID list to validate",
                "train_period": "List[str] - Training period [start, end] in 'YYYY-MM-DD' format",
                "test_period": "Optional[List[str]] - Test period [start, end]",
                "data_source": "str - Data source name (default: 'camels')",
                "required_variables": "Optional[List[str]] - Required variables (default: ['streamflow'])",
                "output_dir": "Optional[str] - Output directory for validation report (default: project root)"
            },
            output_schema={
                "valid_basins": "List[str] - List of valid basin IDs",
                "invalid_basins": "List[Dict] - Invalid basins with reasons",
                "data_availability": "Dict - Data availability details per basin",
                "warnings": "List[str] - Warning messages"
            },
            dependencies=[],  # No dependencies
            required_config_keys=["basin_ids", "train_period"]
        )

    def execute(self, inputs: Dict[str, Any]) -> ToolResult:
        """
        Execute data validation.

        Args:
            inputs: Validation parameters

        Returns:
            ToolResult: Validation result
        """
        basin_ids = inputs["basin_ids"]
        train_period = inputs["train_period"]
        test_period = inputs.get("test_period")
        data_source = inputs.get("data_source", "camels_us")
        required_variables = inputs.get("required_variables", ["streamflow"])
        output_dir = inputs.get("output_dir")  # Optional output directory

        self.logger.info(
            f"[DataValidationTool] Validating {len(basin_ids)} basins, "
            f"period: {train_period}"
        )

        valid_basins = []
        invalid_basins = []
        warnings = []
        data_availability = {}

        # ========== Step 1: Validate Basin IDs ==========
        self.logger.info("[DataValidationTool] Step 1: Validating basin IDs...")
        for basin_id in basin_ids:
            is_valid, error_msg = self.validator.validate_basin_id(
                basin_id=basin_id,
                data_source=data_source
            )

            if is_valid:
                valid_basins.append(basin_id)
                self.logger.debug(f"  ✓ {basin_id}: Valid")
            else:
                invalid_basins.append({
                    "basin_id": basin_id,
                    "reason": error_msg or "Unknown error"
                })
                self.logger.warning(f"  ✗ {basin_id}: {error_msg}")

        if not valid_basins:
            self.logger.error("[DataValidationTool] No valid basins found")
            return ToolResult(
                success=False,
                error=f"No valid basins. All {len(basin_ids)} basins failed validation.",
                data={
                    "valid_basins": [],
                    "invalid_basins": invalid_basins,
                    "data_availability": {},
                    "warnings": []
                }
            )

        self.logger.info(
            f"[DataValidationTool] Basin ID validation: "
            f"{len(valid_basins)}/{len(basin_ids)} valid"
        )

        # ========== Step 2: Validate Time Ranges ==========
        self.logger.info("[DataValidationTool] Step 2: Validating time ranges...")

        # Validate training period
        is_train_valid, train_error = self.validator.validate_time_range(
            time_range=train_period,
            data_source=data_source
        )
        if not is_train_valid:
            self.logger.error(f"  ✗ Training period invalid: {train_error}")
            return ToolResult(
                success=False,
                error=f"Training period validation failed: {train_error}",
                data={
                    "valid_basins": valid_basins,
                    "invalid_basins": invalid_basins,
                    "data_availability": {},
                    "warnings": []
                }
            )
        self.logger.debug(f"  ✓ Training period valid: {train_period}")

        # Validate test period if provided
        if test_period:
            is_test_valid, test_error = self.validator.validate_time_range(
                time_range=test_period,
                data_source=data_source
            )
            if not is_test_valid:
                warnings.append(f"测试期时间范围无效: {test_error}")
                self.logger.warning(f"  ⚠️  Test period invalid: {test_error}")
            else:
                self.logger.debug(f"  ✓ Test period valid: {test_period}")

        # ========== Step 3: Validate Required Variables ==========
        self.logger.info(
            f"[DataValidationTool] Step 3: Validating variables "
            f"{required_variables}..."
        )

        are_vars_valid, missing_vars = self.validator.validate_variables(
            var_list=required_variables,
            data_source=data_source
        )

        if not are_vars_valid:
            warnings.append(
                f"部分变量不可用: {missing_vars}. "
                f"建议检查数据源配置或使用其他变量。"
            )
            self.logger.warning(
                f"  ⚠️  Variables not available: {missing_vars}"
            )
        else:
            self.logger.debug(f"  ✓ All variables available: {required_variables}")

        # ========== Step 4: Collect Data Availability Info ==========
        # Simplified version - detailed checking can be added in Phase 2
        for basin_id in valid_basins:
            data_availability[basin_id] = {
                "has_data": True,
                "train_period": train_period,
                "test_period": test_period,
                "available_variables": required_variables,
                "missing_variables": missing_vars if not are_vars_valid else []
            }

        # ========== Save Validation Report to File ==========
        try:
            from pathlib import Path
            from datetime import datetime
            import json

            # Determine output location
            if output_dir:
                # Save to session-specific directory
                report_dir = Path(output_dir)
                report_dir.mkdir(parents=True, exist_ok=True)
                report_file = report_dir / "validation_report.json"
            else:
                # Save to project root (backward compatible)
                report_dir = Path("validation_reports")
                report_dir.mkdir(exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                report_file = report_dir / f"validation_report_{timestamp}.json"

            # Prepare validation report
            validation_report = {
                "timestamp": datetime.now().isoformat(),
                "summary": {
                    "total_basins": len(basin_ids),
                    "valid_basins": len(valid_basins),
                    "invalid_basins": len(invalid_basins),
                    "warnings": len(warnings)
                },
                "data_source": data_source,
                "train_period": train_period,
                "test_period": test_period,
                "required_variables": required_variables,
                "validation_results": {
                    "valid_basins": valid_basins,
                    "invalid_basins": invalid_basins,
                    "data_availability": data_availability,
                    "warnings": warnings
                }
            }

            # Save to file
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(validation_report, f, indent=2, ensure_ascii=False)

            self.logger.info(f"[DataValidationTool] Validation report saved: {report_file}")
            report_path = str(report_file)

        except Exception as e:
            self.logger.warning(f"[DataValidationTool] Failed to save report: {e}")
            report_path = None

        # ========== Final Result ==========
        self.logger.info(
            f"[DataValidationTool] Validation completed: "
            f"{len(valid_basins)} valid, {len(invalid_basins)} invalid, "
            f"{len(warnings)} warnings"
        )

        return ToolResult(
            success=True,
            data={
                "valid_basins": valid_basins,
                "invalid_basins": invalid_basins,
                "data_availability": data_availability,
                "warnings": warnings,
                "validation_report_file": report_path  # Add report file path
            },
            metadata={
                "validated_count": len(basin_ids),
                "valid_count": len(valid_basins),
                "invalid_count": len(invalid_basins),
                "warning_count": len(warnings),
                "data_source": data_source,
                "report_saved": report_path is not None
            }
        )

    def validate_inputs(self, inputs: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate inputs with additional checks.

        Args:
            inputs: Input parameters

        Returns:
            Tuple[bool, str]: (is_valid, error_message)
        """
        # Call parent validation
        is_valid, error = super().validate_inputs(inputs)
        if not is_valid:
            return is_valid, error

        # Check basin_ids is a list
        basin_ids = inputs.get("basin_ids")
        if not isinstance(basin_ids, list) or not basin_ids:
            return False, "basin_ids must be a non-empty list"

        # Check train_period format
        train_period = inputs.get("train_period")
        if not isinstance(train_period, list) or len(train_period) != 2:
            return False, "train_period must be a list of two dates [start, end]"

        # Check test_period format if provided
        test_period = inputs.get("test_period")
        if test_period is not None:
            if not isinstance(test_period, list) or len(test_period) != 2:
                return False, "test_period must be a list of two dates [start, end]"

        return True, None
