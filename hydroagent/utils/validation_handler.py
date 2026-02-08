"""
Author: HydroAgent Team
Date: 2025-01-25 10:30:00
LastEditTime: 2025-01-25 10:30:00
LastEditors: HydroAgent Team
Description: Handler for validation failure scenarios
FilePath: /HydroAgent/hydroagent/utils/validation_handler.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class ValidationFailureHandler:
    """
    Handler for processing validation failures.

    Implements different strategies based on severity:
    - All basins invalid → Abort with error report
    - Partial basins invalid → Return confirmation request for user
    - Only warnings → Log and continue

    User preference: Interactive mode (ask user if continue)
    """

    @staticmethod
    def handle_failure(
        validation_result: Dict[str, Any],
        user_query: str = ""
    ) -> Dict[str, Any]:
        """
        Handle validation failure and determine action.

        Args:
            validation_result: Validation tool result data
            user_query: Original user query (for context)

        Returns:
            Dict with keys:
                - action: "abort" | "confirm" | "warn_and_continue" | "continue"
                - message: User-facing message
                - valid_basins: List of valid basins (if any)
                - metadata: Additional info
        """
        valid_basins = validation_result.get("valid_basins", [])
        invalid_basins = validation_result.get("invalid_basins", [])
        warnings = validation_result.get("warnings", [])
        data_availability = validation_result.get("data_availability", {})

        # Scenario 1: All basins invalid - Abort
        if not valid_basins and invalid_basins:
            error_details = "\n".join([
                f"  - {item['basin_id']}: {item['reason']}"
                for item in invalid_basins
            ])

            return {
                "action": "abort",
                "message": (
                    "❌ 数据验证失败：所有流域均无效\n\n"
                    f"错误详情:\n{error_details}\n\n"
                    "💡 建议:\n"
                    "  - 检查流域ID是否正确（应为8位数字）\n"
                    "  - 确认数据集已下载到正确路径\n"
                    "  - 验证时间范围在数据集范围内"
                ),
                "valid_basins": [],
                "metadata": {
                    "invalid_count": len(invalid_basins),
                    "error_type": "all_invalid"
                }
            }

        # Scenario 2: Partial failure - Ask user
        if valid_basins and invalid_basins:
            invalid_summary = [
                f"  - {item['basin_id']}: {item['reason']}"
                for item in invalid_basins[:5]  # Show first 5
            ]
            if len(invalid_basins) > 5:
                invalid_summary.append(f"  ... 还有 {len(invalid_basins) - 5} 个无效流域")

            return {
                "action": "confirm",
                "message": (
                    f"⚠️  数据验证部分失败\n\n"
                    f"✓ 有效流域: {len(valid_basins)} 个\n"
                    f"✗ 无效流域: {len(invalid_basins)} 个\n\n"
                    f"无效流域详情:\n" + "\n".join(invalid_summary) + "\n\n"
                    f"💬 有效流域列表: {', '.join(valid_basins[:10])}"
                    f"{'...' if len(valid_basins) > 10 else ''}\n\n"
                    "❓ 是否使用有效流域继续执行？"
                ),
                "valid_basins": valid_basins,
                "invalid_basins": invalid_basins,
                "metadata": {
                    "valid_count": len(valid_basins),
                    "invalid_count": len(invalid_basins),
                    "error_type": "partial_invalid"
                }
            }

        # Scenario 3: Only warnings - Continue with warnings
        if valid_basins and warnings:
            warning_summary = "\n".join([f"  - {w}" for w in warnings[:5]])
            if len(warnings) > 5:
                warning_summary += f"\n  ... 还有 {len(warnings) - 5} 个警告"

            return {
                "action": "warn_and_continue",
                "message": (
                    f"⚠️  数据验证通过，但存在 {len(warnings)} 个警告:\n\n"
                    f"{warning_summary}\n\n"
                    "✓ 将继续执行，但建议检查警告信息"
                ),
                "valid_basins": valid_basins,
                "metadata": {
                    "valid_count": len(valid_basins),
                    "warning_count": len(warnings),
                    "error_type": "warnings_only"
                }
            }

        # Scenario 4: All passed - Continue
        return {
            "action": "continue",
            "message": (
                f"✅ 数据验证通过\n"
                f"  - 验证流域数: {len(valid_basins)}\n"
                f"  - 数据完整性: 良好"
            ),
            "valid_basins": valid_basins,
            "metadata": {
                "valid_count": len(valid_basins),
                "error_type": "none"
            }
        }

    @staticmethod
    def format_validation_report(
        validation_result: Dict[str, Any],
        verbose: bool = False
    ) -> str:
        """
        Format validation result as human-readable report.

        Args:
            validation_result: Validation result data
            verbose: Whether to include detailed information

        Returns:
            str: Formatted report
        """
        valid_basins = validation_result.get("valid_basins", [])
        invalid_basins = validation_result.get("invalid_basins", [])
        warnings = validation_result.get("warnings", [])
        data_availability = validation_result.get("data_availability", {})

        lines = ["=" * 60]
        lines.append("数据验证报告 (Data Validation Report)")
        lines.append("=" * 60)

        # Summary
        lines.append(f"\n【验证摘要】")
        lines.append(f"  总流域数: {len(valid_basins) + len(invalid_basins)}")
        lines.append(f"  有效流域: {len(valid_basins)}")
        lines.append(f"  无效流域: {len(invalid_basins)}")
        lines.append(f"  警告数量: {len(warnings)}")

        # Valid basins
        if valid_basins:
            lines.append(f"\n【有效流域】")
            if verbose:
                lines.append(f"  {', '.join(valid_basins)}")
            else:
                preview = ', '.join(valid_basins[:10])
                if len(valid_basins) > 10:
                    preview += f" ... 还有 {len(valid_basins) - 10} 个"
                lines.append(f"  {preview}")

        # Invalid basins
        if invalid_basins:
            lines.append(f"\n【无效流域】")
            for item in invalid_basins[:10]:
                lines.append(f"  ✗ {item['basin_id']}: {item['reason']}")
            if len(invalid_basins) > 10:
                lines.append(f"  ... 还有 {len(invalid_basins) - 10} 个")

        # Warnings
        if warnings:
            lines.append(f"\n【警告信息】")
            for warning in warnings[:10]:
                lines.append(f"  ⚠️  {warning}")
            if len(warnings) > 10:
                lines.append(f"  ... 还有 {len(warnings) - 10} 个")

        # Data availability (verbose mode)
        if verbose and data_availability:
            lines.append(f"\n【数据可用性详情】")
            for basin_id, avail in list(data_availability.items())[:5]:
                lines.append(f"  {basin_id}:")
                lines.append(f"    - 数据完整性: {avail.get('coverage_rate', 'N/A')}")
                lines.append(f"    - 缺失时段: {avail.get('missing_periods', [])}")

        lines.append("=" * 60)
        return "\n".join(lines)
