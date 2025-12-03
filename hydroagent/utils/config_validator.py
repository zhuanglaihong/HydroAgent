"""
Author: Claude
Date: 2025-12-01 10:45:00
LastEditTime: 2025-12-01 10:45:00
LastEditors: Claude
Description: Configuration validation utilities for hydromodel configs
             配置验证工具，用于检查流域ID、算法参数等的合法性
FilePath: /HydroAgent/hydroagent/utils/config_validator.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from typing import Dict, Any, List, Tuple, Optional
import logging
import re

logger = logging.getLogger(__name__)


class ConfigValidator:
    """
    Configuration validator for hydromodel configs.
    配置验证器，用于验证hydromodel配置的合法性。

    Responsibilities:
    1. Validate basin IDs (format and range)
    2. Validate algorithm parameters (positive values, ranges)
    3. Validate time periods (date format and logic)
    4. Provide friendly error messages for users
    """

    # CAMELS-US流域ID范围 (8位数字，通常为 01000000 - 14400000)
    # 参考: https://ral.ucar.edu/solutions/products/camels
    CAMELS_US_BASIN_ID_MIN = 1000000
    CAMELS_US_BASIN_ID_MAX = 14500000

    # 算法参数的合理范围
    ALGORITHM_PARAM_RANGES = {
        "SCE_UA": {
            "rep": {"min": 1, "max": 50000, "description": "迭代轮数"},
            "ngs": {"min": 1, "max": 1000, "description": "复合体数量"},
            "kstop": {"min": 1, "max": 10000, "description": "停止准则"},
            "pcento": {"min": 0.0, "max": 1.0, "description": "收敛阈值"},
            "peps": {"min": 0.0, "max": 1.0, "description": "参数收敛阈值"},
        },
        "GA": {
            "generations": {"min": 1, "max": 10000, "description": "迭代代数"},
            "population_size": {"min": 2, "max": 10000, "description": "种群大小"},
            "crossover_prob": {"min": 0.0, "max": 1.0, "description": "交叉概率"},
            "mutation_prob": {"min": 0.0, "max": 1.0, "description": "变异概率"},
        },
        "DE": {
            "max_generations": {"min": 1, "max": 10000, "description": "最大迭代代数"},
            "pop_size": {"min": 4, "max": 10000, "description": "种群大小"},
            "F": {"min": 0.0, "max": 2.0, "description": "缩放因子"},
            "CR": {"min": 0.0, "max": 1.0, "description": "交叉概率"},
        },
        "PSO": {
            "max_iterations": {"min": 1, "max": 10000, "description": "最大迭代次数"},
            "swarm_size": {"min": 2, "max": 10000, "description": "粒子群大小"},
        },
    }

    def validate_config(self, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        全面验证配置字典。

        Args:
            config: hydromodel配置字典

        Returns:
            Tuple[bool, List[str]]: (is_valid, error_messages)
        """
        errors = []

        # 检查是否为custom_analysis任务（跳过hydromodel验证）
        task_metadata = config.get("task_metadata", {})
        if task_metadata.get("task_type") == "custom_analysis":
            logger.info("[ConfigValidator] Custom analysis task, skipping hydromodel validation")
            return True, []

        # 1. 验证 data_cfgs
        if "data_cfgs" in config:
            data_errors = self.validate_data_cfgs(config["data_cfgs"])
            errors.extend(data_errors)

        # 2. 验证 model_cfgs
        if "model_cfgs" in config:
            model_errors = self.validate_model_cfgs(config["model_cfgs"])
            errors.extend(model_errors)

        # 3. 验证 training_cfgs
        if "training_cfgs" in config:
            training_errors = self.validate_training_cfgs(config["training_cfgs"])
            errors.extend(training_errors)

        is_valid = len(errors) == 0
        return is_valid, errors

    def validate_data_cfgs(self, data_cfgs: Dict[str, Any]) -> List[str]:
        """验证数据配置。"""
        errors = []

        # 验证basin_ids
        basin_ids = data_cfgs.get("basin_ids", [])
        if basin_ids:
            for basin_id in basin_ids:
                basin_error = self.validate_basin_id(basin_id)
                if basin_error:
                    errors.append(basin_error)

        # 验证时间段
        train_period = data_cfgs.get("train_period", [])
        test_period = data_cfgs.get("test_period", [])

        if train_period:
            period_error = self.validate_time_period(train_period, "训练时间段")
            if period_error:
                errors.append(period_error)

        if test_period:
            period_error = self.validate_time_period(test_period, "测试时间段")
            if period_error:
                errors.append(period_error)

        return errors

    def validate_model_cfgs(self, model_cfgs: Dict[str, Any]) -> List[str]:
        """验证模型配置。"""
        errors = []

        # 验证模型名称
        model_name = model_cfgs.get("model_name")
        valid_models = ["xaj", "xaj_mz", "gr4j", "gr5j", "gr6j", "gr1y", "gr2m"]

        if model_name and model_name not in valid_models:
            errors.append(
                f"无效的模型名称: {model_name}。"
                f"有效的模型包括: {', '.join(valid_models)}"
            )

        return errors

    def validate_training_cfgs(self, training_cfgs: Dict[str, Any]) -> List[str]:
        """验证训练配置。"""
        errors = []

        # 验证算法名称
        algorithm_name = training_cfgs.get("algorithm_name")
        if not algorithm_name:
            return errors

        # 验证算法参数
        algorithm_params = training_cfgs.get("algorithm_params", {})

        if algorithm_name in self.ALGORITHM_PARAM_RANGES:
            param_ranges = self.ALGORITHM_PARAM_RANGES[algorithm_name]

            for param_name, param_value in algorithm_params.items():
                if param_name in param_ranges:
                    param_error = self.validate_algorithm_param(
                        algorithm_name,
                        param_name,
                        param_value,
                        param_ranges[param_name]
                    )
                    if param_error:
                        errors.append(param_error)

        return errors

    def validate_basin_id(self, basin_id: str) -> Optional[str]:
        """
        验证流域ID的格式和范围。

        Args:
            basin_id: 流域ID字符串

        Returns:
            错误信息（如果无效），否则返回None
        """
        # 检查格式：应为8位数字
        if not isinstance(basin_id, str):
            return f"流域ID必须是字符串格式，当前类型: {type(basin_id).__name__}"

        if not re.match(r'^\d{8}$', basin_id):
            return (
                f"流域ID格式错误: {basin_id}。"
                f"流域ID应为8位数字（如 01013500）"
            )

        # 检查范围：CAMELS-US流域ID通常在 01000000 - 14500000 之间
        basin_id_int = int(basin_id)
        if not (self.CAMELS_US_BASIN_ID_MIN <= basin_id_int <= self.CAMELS_US_BASIN_ID_MAX):
            return (
                f"流域ID超出CAMELS数据集范围: {basin_id}。"
                f"有效范围: {self.CAMELS_US_BASIN_ID_MIN:08d} - {self.CAMELS_US_BASIN_ID_MAX:08d}。"
                f"\n💡 提示: 请检查流域ID是否正确，或访问 https://ral.ucar.edu/solutions/products/camels 查看可用流域列表"
            )

        return None

    def validate_algorithm_param(
        self,
        algorithm_name: str,
        param_name: str,
        param_value: Any,
        param_range: Dict[str, Any]
    ) -> Optional[str]:
        """
        验证算法参数的范围。

        Args:
            algorithm_name: 算法名称
            param_name: 参数名称
            param_value: 参数值
            param_range: 参数范围定义

        Returns:
            错误信息（如果无效），否则返回None
        """
        min_val = param_range.get("min")
        max_val = param_range.get("max")
        description = param_range.get("description", param_name)

        # 检查类型
        if not isinstance(param_value, (int, float)):
            return (
                f"算法参数类型错误: {algorithm_name}.{param_name} = {param_value}。"
                f"参数 '{description}' 必须是数字，当前类型: {type(param_value).__name__}"
            )

        # 检查范围
        if min_val is not None and param_value < min_val:
            return (
                f"算法参数超出范围: {algorithm_name}.{param_name} = {param_value}。"
                f"参数 '{description}' 不能小于 {min_val}。"
                f"\n💡 提示: 请使用正数值（建议范围: {min_val} - {max_val}）"
            )

        if max_val is not None and param_value > max_val:
            return (
                f"算法参数超出范围: {algorithm_name}.{param_name} = {param_value}。"
                f"参数 '{description}' 不能大于 {max_val}。"
                f"\n💡 提示: 过大的值可能导致计算时间过长（建议范围: {min_val} - {max_val}）"
            )

        return None

    def validate_time_period(
        self, time_period: List[str], period_name: str = "时间段"
    ) -> Optional[str]:
        """
        验证时间段格式和逻辑。

        Args:
            time_period: 时间段列表 [start_date, end_date]
            period_name: 时间段名称（用于错误信息）

        Returns:
            错误信息（如果无效），否则返回None
        """
        if not isinstance(time_period, list) or len(time_period) != 2:
            return f"{period_name}格式错误：必须是包含两个日期的列表 [开始日期, 结束日期]"

        start_date, end_date = time_period

        # 检查日期格式 (YYYY-MM-DD)
        date_pattern = r'^\d{4}-\d{2}-\d{2}$'

        if not re.match(date_pattern, start_date):
            return f"{period_name}开始日期格式错误: {start_date}。应使用 YYYY-MM-DD 格式（如 2000-01-01）"

        if not re.match(date_pattern, end_date):
            return f"{period_name}结束日期格式错误: {end_date}。应使用 YYYY-MM-DD 格式（如 2010-12-31）"

        # 检查逻辑：开始日期应早于结束日期
        if start_date >= end_date:
            return (
                f"{period_name}逻辑错误: 开始日期 ({start_date}) 必须早于结束日期 ({end_date})"
            )

        # 检查年份合理性（避免未来时间）
        from datetime import datetime
        current_year = datetime.now().year

        start_year = int(start_date.split('-')[0])
        end_year = int(end_date.split('-')[0])

        if start_year > current_year or end_year > current_year:
            return (
                f"{period_name}包含未来时间: {start_date} - {end_date}。"
                f"\n💡 提示: CAMELS数据集通常包含1980-2014年的数据，请使用历史时间段"
            )

        if start_year < 1900:
            return (
                f"{period_name}年份过早: {start_date}。"
                f"\n💡 提示: 请使用1980年之后的时间段（CAMELS数据集的覆盖范围）"
            )

        return None

    def format_validation_errors(self, errors: List[str]) -> str:
        """
        格式化验证错误为友好的提示信息。

        Args:
            errors: 错误信息列表

        Returns:
            格式化的错误信息
        """
        if not errors:
            return ""

        lines = [
            "❌ 配置验证失败，发现以下问题：",
            ""
        ]

        for i, error in enumerate(errors, 1):
            lines.append(f"{i}. {error}")
            lines.append("")

        lines.append("请修正以上问题后重试。")

        return "\n".join(lines)


# 创建全局验证器实例
validator = ConfigValidator()


def validate_config(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    便捷函数：验证配置。

    Args:
        config: hydromodel配置字典

    Returns:
        Tuple[bool, List[str]]: (is_valid, error_messages)
    """
    return validator.validate_config(config)


def validate_basin_id(basin_id: str) -> Optional[str]:
    """
    便捷函数：验证流域ID。

    Args:
        basin_id: 流域ID

    Returns:
        错误信息（如果无效），否则返回None
    """
    return validator.validate_basin_id(basin_id)
