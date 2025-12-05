"""
Author: Claude
Date: 2025-01-28 00:00:00
LastEditTime: 2025-01-28 00:00:00
LastEditors: Claude
Description: 参数范围智能调整工具 - Parameter Range Adjustment Utilities
             从RunnerAgent中提取的工具函数，用于基于上一次率定结果智能调整参数范围
FilePath: /HydroAgent/hydroagent/utils/param_range_adjuster.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional
import yaml
import pandas as pd

logger = logging.getLogger(__name__)


def adjust_from_previous_calibration(
    prev_calibration_dir: str,
    range_scale: float = 0.6,
    output_yaml_path: Optional[str] = None,
    workspace_dir: Optional[Path] = None,
    boundary_threshold: float = 0.1,
    boundary_expand_factor: float = 1.5,
    smart_adjustment: bool = True,
) -> Dict[str, Any]:
    """
    从上一次率定结果中智能调整参数范围。

    核心思路（v2.0 智能边界自适应调整）:
    1. 读取上一次的参数范围 (param_range.yaml)
    2. 读取上一次的最佳参数 (basins_denorm_params.csv，注意是反归一化的)
    3. **智能判断每个参数是否需要调整**:
       - 如果参数接近上/下边界 → 扩展该边界
       - 如果参数在中间区域 → 可选择缩小范围或保持不变
       - 如果参数已收敛良好 → 保持不变
    4. 保持物理意义，确保新范围在合理区间内
    5. 生成新的 param_range.yaml

    Args:
        prev_calibration_dir: 上一次率定结果目录
            例如: "results/20251121_211408/gr4j_SCE_UA_20251121_211414"
        range_scale: 新范围长度占原范围长度的比例（默认0.6，即60%，用于缩小范围）
        output_yaml_path: 输出的新参数范围YAML文件路径（可选）
        workspace_dir: 工作空间目录（用于默认输出路径）
        boundary_threshold: 边界判断阈值（默认0.1，即10%），
            如果最佳值距离边界 < threshold * range_length，认为接近边界
        boundary_expand_factor: 边界扩展因子（默认1.5，即扩展50%）
        smart_adjustment: 是否启用智能调整（默认True）
            - True: 只调整接近边界的参数
            - False: 调整所有参数（旧版本行为）

    Returns:
        调整后的参数范围信息
        {
            "success": True/False,
            "prev_param_range": {...},  # 上一次的参数范围
            "best_params": {...},       # 最佳参数（反归一化）
            "new_param_range": {...},   # 新的参数范围
            "adjustment_log": {...},    # 调整日志（记录每个参数的调整策略）
            "output_file": "path/to/new_param_range.yaml"
        }
    """
    logger.info(f"[ParamRangeAdjuster] 开始智能参数范围调整")
    logger.info(f"[ParamRangeAdjuster] 读取上一次率定结果: {prev_calibration_dir}")
    logger.info(f"[ParamRangeAdjuster] 范围缩放比例: {range_scale}")

    try:
        prev_dir = Path(prev_calibration_dir)

        # 1. 读取上一次的参数范围
        param_range_file = prev_dir / "param_range.yaml"
        if not param_range_file.exists():
            logger.error(f"[ParamRangeAdjuster] 参数范围文件不存在: {param_range_file}")
            return {
                "success": False,
                "error": f"param_range.yaml not found in {prev_dir}",
            }

        with open(param_range_file, "r", encoding="utf-8") as f:
            param_range_data = yaml.safe_load(f)

        # ⭐ BUG FIX: 提取实际的参数范围字典
        # param_range.yaml 格式可能是:
        # 1. {model_name: {param_range: {...}}}  # hydromodel标准格式
        # 2. {param_name: [...]}                 # 直接格式
        found_model = None
        if isinstance(param_range_data, dict):
            # 检查是否有模型名作为第一层key（如 'xaj', 'gr4j'）
            model_names = ["xaj", "gr4j", "gr5j", "gr6j", "lstm"]  # 常见模型名
            for model_name in model_names:
                if model_name in param_range_data:
                    found_model = model_name
                    break

            if found_model and "param_range" in param_range_data[found_model]:
                # 格式1: {model_name: {param_range: {...}}}
                prev_param_range = param_range_data[found_model]["param_range"]
                logger.info(f"[ParamRangeAdjuster] 检测到模型: {found_model}")
            else:
                # 格式2: 直接就是参数范围字典
                prev_param_range = param_range_data
        else:
            prev_param_range = param_range_data

        logger.info(f"[ParamRangeAdjuster] 上一次参数范围: {prev_param_range}")

        # 2. 读取最佳参数（反归一化）
        best_params_file = prev_dir / "basins_denorm_params.csv"
        if not best_params_file.exists():
            logger.error(f"[ParamRangeAdjuster] 最佳参数文件不存在: {best_params_file}")
            return {
                "success": False,
                "error": f"basins_denorm_params.csv not found in {prev_dir}",
            }

        # 读取CSV（通常第一列是basin_id，其余是参数）
        df = pd.read_csv(best_params_file)
        logger.info(
            f"[ParamRangeAdjuster] basins_denorm_params.csv columns: {df.columns.tolist()}"
        )

        # 提取第一个流域的参数
        # 假设格式: basin_id, x1, x2, x3, x4, ...
        if len(df) == 0:
            logger.error("[ParamRangeAdjuster] basins_denorm_params.csv 是空的")
            return {"success": False, "error": "Empty parameter file"}

        # 获取第一行（第一个流域）
        param_row = df.iloc[0]

        # ⭐ BUG FIX: 排除流域ID列（可能的列名变体）
        # hydromodel可能生成的流域ID列名: 'Unnamed: 0', 'basin_id', 'basin', 'id', 'index'
        id_column_patterns = ["unnamed", "basin_id", "basin", "id", "index"]

        param_columns = [
            col
            for col in df.columns
            if not any(pattern in col.lower() for pattern in id_column_patterns)
        ]

        # 如果没有找到参数列（所有列都被排除了），使用除第一列外的所有列
        if not param_columns and len(df.columns) > 1:
            logger.warning(
                "[ParamRangeAdjuster] 无法识别ID列，使用除第一列外的所有列作为参数"
            )
            param_columns = df.columns[1:].tolist()

        best_params = {col: param_row[col] for col in param_columns}

        logger.info(f"[ParamRangeAdjuster] 参数列: {param_columns}")
        logger.info(f"[ParamRangeAdjuster] 最佳参数（反归一化）: {best_params}")

        # 3. 计算新的参数范围（智能边界自适应调整）
        # 格式: {param_name: [min, max]}
        new_param_range = {}
        param_name_list = []  # 保存参数名列表（用于生成标准格式）
        adjustment_log = {}  # 记录每个参数的调整策略

        logger.info(f"[ParamRangeAdjuster] 智能调整模式: {'启用' if smart_adjustment else '禁用（旧版本行为）'}")
        logger.info(f"[ParamRangeAdjuster] 边界阈值: {boundary_threshold} (距离边界 < {boundary_threshold*100}% 认为接近边界)")
        logger.info(f"[ParamRangeAdjuster] 边界扩展因子: {boundary_expand_factor}")

        for param_name, best_value in best_params.items():
            if param_name not in prev_param_range:
                logger.warning(
                    f"[ParamRangeAdjuster] 参数 {param_name} 不在 param_range.yaml 中，跳过"
                )
                continue

            prev_range = prev_param_range[param_name]
            if not isinstance(prev_range, (list, tuple)) or len(prev_range) != 2:
                logger.warning(
                    f"[ParamRangeAdjuster] 参数 {param_name} 的范围格式不正确: {prev_range}"
                )
                continue

            prev_min, prev_max = prev_range
            prev_length = prev_max - prev_min

            # ⭐ 核心改进：智能边界自适应调整
            if smart_adjustment:
                # 计算最佳值到边界的距离
                dist_to_lower = best_value - prev_min
                dist_to_upper = prev_max - best_value

                # 判断是否接近边界
                near_lower = dist_to_lower < boundary_threshold * prev_length
                near_upper = dist_to_upper < boundary_threshold * prev_length

                if near_lower:
                    # 🔽 接近下边界 → 向下扩展下边界
                    strategy = "expand_lower_boundary"
                    extend_amount = prev_length * (boundary_expand_factor - 1.0)
                    new_min = prev_min - extend_amount
                    new_max = prev_max  # 保持上边界不变

                    # 确保不出现不合理的负值（根据参数物理意义）
                    # 例如：流域面积、蓄水容量等不能为负
                    if new_min < 0 and prev_min >= 0:
                        new_min = 0.0

                    logger.info(f"[ParamRangeAdjuster] 参数 {param_name}: 接近下边界 (距离={dist_to_lower:.4f} < {boundary_threshold * prev_length:.4f})")
                    logger.info(f"  策略: 向下扩展下边界 ({boundary_expand_factor}x)")

                elif near_upper:
                    # 🔼 接近上边界 → 向上扩展上边界
                    strategy = "expand_upper_boundary"
                    extend_amount = prev_length * (boundary_expand_factor - 1.0)
                    new_min = prev_min  # 保持下边界不变
                    new_max = prev_max + extend_amount

                    logger.info(f"[ParamRangeAdjuster] 参数 {param_name}: 接近上边界 (距离={dist_to_upper:.4f} < {boundary_threshold * prev_length:.4f})")
                    logger.info(f"  策略: 向上扩展上边界 ({boundary_expand_factor}x)")

                else:
                    # ✅ 在中间区域 → 可选择缩小范围或保持不变
                    # 默认：保持不变（因为参数已经收敛良好）
                    strategy = "keep_unchanged"
                    new_min = prev_min
                    new_max = prev_max

                    logger.info(f"[ParamRangeAdjuster] 参数 {param_name}: 在中间区域 (下距={dist_to_lower:.4f}, 上距={dist_to_upper:.4f})")
                    logger.info(f"  策略: 保持范围不变（参数收敛良好）")

            else:
                # 旧版本行为：所有参数统一缩小
                strategy = "uniform_shrink"
                new_length = prev_length * range_scale
                new_min = best_value - new_length / 2
                new_max = best_value + new_length / 2

                # 确保不超出原始范围
                new_min = max(new_min, prev_min)
                new_max = min(new_max, prev_max)

                # 如果最佳值接近边界，调整范围
                if new_min == prev_min:
                    new_max = min(new_min + new_length, prev_max)
                if new_max == prev_max:
                    new_min = max(new_max - new_length, prev_min)

                logger.info(f"[ParamRangeAdjuster] 参数 {param_name}: 使用旧版本行为（统一缩小）")

            new_param_range[param_name] = [float(new_min), float(new_max)]
            param_name_list.append(param_name)  # 记录参数名

            # 记录调整策略
            adjustment_log[param_name] = {
                "strategy": strategy,
                "prev_range": [prev_min, prev_max],
                "best_value": best_value,
                "new_range": [new_min, new_max],
                "range_change": f"{prev_length:.4f} → {new_max - new_min:.4f}",
            }

            logger.info(f"[ParamRangeAdjuster] 参数 {param_name}:")
            logger.info(f"  原范围: [{prev_min}, {prev_max}] (长度: {prev_length})")
            logger.info(f"  最佳值: {best_value}")
            logger.info(
                f"  新范围: [{new_min:.4f}, {new_max:.4f}] (长度: {new_max - new_min:.4f})"
            )
            logger.info(f"  调整策略: {strategy}")

        # 4. 保存新的参数范围（使用标准格式）
        if output_yaml_path is None:
            # 默认保存在当前工作目录
            output_yaml_path = (
                workspace_dir / "adjusted_param_range.yaml"
                if workspace_dir
                else Path("adjusted_param_range.yaml")
            )
        else:
            output_yaml_path = Path(output_yaml_path)

        output_yaml_path.parent.mkdir(parents=True, exist_ok=True)

        # ⭐ 生成标准格式的YAML（与原始param_range.yaml格式一致）
        # 检测模型名（如果原始YAML有嵌套结构）
        if found_model:
            # 格式1: {model_name: {param_name: [...], param_range: {...}}}
            standard_format_yaml = {
                found_model: {
                    "param_name": param_name_list,
                    "param_range": new_param_range,
                }
            }
        else:
            # 格式2: 直接格式（保持向后兼容）
            standard_format_yaml = new_param_range

        with open(output_yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(
                standard_format_yaml, f, default_flow_style=False, allow_unicode=True
            )

        logger.info(f"[ParamRangeAdjuster] 新参数范围已保存: {output_yaml_path}")
        logger.info(
            f"[ParamRangeAdjuster] 使用格式: {'标准格式 (含模型名)' if found_model else '简化格式'}"
        )

        return {
            "success": True,
            "prev_param_range": prev_param_range,
            "best_params": best_params,
            "new_param_range": new_param_range,
            "adjustment_log": adjustment_log,  # 🆕 调整日志
            "output_file": str(output_yaml_path),
            "scale": range_scale,
            "boundary_threshold": boundary_threshold,
            "boundary_expand_factor": boundary_expand_factor,
            "smart_adjustment": smart_adjustment,
        }

    except Exception as e:
        logger.error(f"[ParamRangeAdjuster] 参数范围调整失败: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}
