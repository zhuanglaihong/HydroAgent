"""
param_boxplot_comparison.py

A HydroClaw tool for comparing parameter distributions between two calibration 
result directories and generating box plots for visual comparison.

This tool reads calibration_results.json files from two directories, extracts 
optimal parameters, and creates box plots to help analyze parameter differences 
between different calibration strategies or models.
"""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def param_boxplot_comparison(
    dir1: str,
    dir2: str,
    output_dir: str,
    labels: list[str] | None = None,
    _workspace: Path | None = None,
    _cfg: dict | None = None,
    _llm: object | None = None,
) -> dict[str, Any]:
    """
    对比两个率定结果目录的参数分布，生成箱线图。
    
    读取两个 calibration_results.json 文件，提取最优参数，绘制参数分布
    箱线图进行直观对比，帮助分析不同率定策略或模型之间的参数差异。

    Args:
        dir1: 第一个率定结果目录路径
        dir2: 第二个率定结果目录路径
        output_dir: 输出目录路径，用于保存生成的箱线图
        labels: 可选的标签列表，用于图例显示，默认使用目录名
        _workspace: 工作目录路径（自动注入）
        _cfg: 全局配置字典（自动注入）
        _llm: LLM客户端对象（自动注入）

    Returns:
        包含操作结果的字典，至少包含 "success" 键：
        - success: bool，操作是否成功
        - output_path: str，生成的箱线图文件路径（成功时）
        - error: str，错误信息（失败时）
        - details: dict，详细的参数统计信息（成功时）
    """
    # Lazy imports to avoid startup errors
    import json
    import os

    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd

    # Resolve paths
    workspace = _workspace or Path.cwd()
    dir1_path = Path(dir1) if Path(dir1).is_absolute() else workspace / dir1
    dir2_path = Path(dir2) if Path(dir2).is_absolute() else workspace / dir2
    output_path = Path(output_dir) if Path(output_dir).is_absolute() else workspace / output_dir

    # Default labels
    if labels is None:
        labels = [dir1_path.name, dir2_path.name]

    try:
        # Validate directories exist
        if not dir1_path.exists():
            return {"success": False, "error": f"Directory not found: {dir1_path}"}
        if not dir2_path.exists():
            return {"success": False, "error": f"Directory not found: {dir2_path}"}

        # Create output directory if it doesn't exist
        output_path.mkdir(parents=True, exist_ok=True)

        # Read calibration results from both directories
        file1 = dir1_path / "calibration_results.json"
        file2 = dir2_path / "calibration_results.json"

        if not file1.exists():
            return {"success": False, "error": f"calibration_results.json not found in {dir1_path}"}
        if not file2.exists():
            return {"success": False, "error": f"calibration_results.json not found in {dir2_path}"}

        with open(file1, "r", encoding="utf-8") as f:
            data1 = json.load(f)
        with open(file2, "r", encoding="utf-8") as f:
            data2 = json.load(f)

        # Extract optimal parameters from both results
        params1 = _extract_optimal_params(data1)
        params2 = _extract_optimal_params(data2)

        if not params1:
            return {"success": False, "error": "No optimal parameters found in first calibration result"}
        if not params2:
            return {"success": False, "error": "No optimal parameters found in second calibration result"}

        # Get common parameters
        common_params = sorted(set(params1.keys()) & set(params2.keys()))
        if not common_params:
            return {"success": False, "error": "No common parameters found between the two results"}

        # Prepare data for box plot
        param_data = {param: [params1.get(param, 0), params2.get(param, 0)] for param in common_params}

        # Create DataFrame for plotting
        df = pd.DataFrame(param_data)

        # Create box plot
        fig, ax = plt.subplots(figsize=(12, 6))

        # Prepare data in format suitable for boxplot
        box_data = [df[param].values for param in df.columns]
        positions = range(len(df.columns))

        bp = ax.boxplot(
            box_data,
            positions=positions,
            patch_artist=True,
            labels=df.columns,
        )

        # Customize colors
        colors = ["#3498db", "#e74c3c"]
        for patch, color in zip(bp["boxes"], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        # Customize plot appearance
        ax.set_xlabel("Parameters", fontsize=12)
        ax.set_ylabel("Parameter Value", fontsize=12)
        ax.set_title(f"Parameter Distribution Comparison: {labels[0]} vs {labels[1]}", fontsize=14)
        ax.grid(True, alpha=0.3)
        ax.legend([bp["boxes"][0], bp["boxes"][1]], labels, loc="upper right")

        # Add value annotations
        for i, param in enumerate(df.columns):
            for j, (val, label) in enumerate(zip(df[param].values, labels)):
                offset = 0.1 if j == 0 else -0.1
                ax.annotate(
                    f"{val:.4f}",
                    xy=(i, val),
                    xytext=(offset, 5),
                    textcoords="offset points",
                    fontsize=8,
                    ha="center",
                )

        plt.tight_layout()

        # Save the figure
        output_file = output_path / "param_boxplot_comparison.png"
        plt.savefig(output_file, dpi=150, bbox_inches="tight")
        plt.close()

        # Calculate statistics for details
        details = {
            "parameters": common_params,
            "statistics": {
                param: {
                    labels[0]: params1.get(param),
                    labels[1]: params2.get(param),
                    "difference": params1.get(param, 0) - params2.get(param, 0),
                }
                for param in common_params
            },
            "labels": labels,
        }

        logger.info(f"Parameter boxplot comparison saved to: {output_file}")

        return {
            "success": True,
            "output_path": str(output_file),
            "details": details,
        }

    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {e}")
        return {"success": False, "error": f"Failed to parse calibration_results.json: {str(e)}"}
    except KeyError as e:
        logger.error(f"Missing expected key in calibration data: {e}")
        return {"success": False, "error": f"Missing expected key in calibration data: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error during parameter comparison: {e}")
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


def _extract_optimal_params(data: dict) -> dict[str, float]:
    """
    从率定结果数据中提取最优参数。

    Args:
        data: calibration_results.json 解析后的字典数据

    Returns:
        最优参数字典，键为参数名，值为参数值
    """
    params = {}

    # Try different possible structures
    if isinstance(data, dict):
        # Check if optimal_params exists directly
        if "optimal_params" in data:
            optimal = data["optimal_params"]
            if isinstance(optimal, dict):
                return optimal

        # Check for parameters key
        if "parameters" in data:
            params_data = data["parameters"]
            if isinstance(params_data, dict):
                # Check for optimal values
                if "optimal" in params_data:
                    return params_data["optimal"]
                # Return all as optimal
                return {k: float(v) for k, v in params_data.items() if isinstance(v, (int, float))}

        # Check for best_params or similar
        for key in ["best_params", "best_parameters", "optimal"]:
            if key in data:
                val = data[key]
                if isinstance(val, dict):
                    return val

        # Try to find parameters in results
        if "results" in data:
            results = data["results"]
            if isinstance(results, list) and len(results) > 0:
                # Get the best result (first one, assuming sorted by performance)
                best = results[0]
                if isinstance(best, dict) and "params" in best:
                    return best["params"]

    return params