"""
Author: zhuanglaihong
Date: 2024-09-26 16:40:00
LastEditTime: 2024-09-26 16:40:00
LastEditors: zhuanglaihong
Description: 模型优化过程可视化工具 - 专门用于显示率定过程和优化收敛
FilePath: \HydroAgent\executor\visualization\optimization_visualizer.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.animation import FuncAnimation
import seaborn as sns
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime
import logging
from mpl_toolkits.mplot3d import Axes3D
from scipy.interpolate import griddata
from matplotlib.colors import LinearSegmentedColormap
import warnings

warnings.filterwarnings("ignore")

# 设置中文字体和论文级样式
plt.rcParams["font.sans-serif"] = ["SimHei", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
plt.style.use("seaborn-v0_8-whitegrid")

# 定义优化过程的颜色方案
OPT_COLORS = {
    "best": "#e74c3c",  # 最优解红色
    "current": "#3498db",  # 当前解蓝色
    "population": "#95a5a6",  # 种群灰色
    "progress": "#2ecc71",  # 进度绿色
    "convergence": "#f39c12",  # 收敛橙色
    "feasible": "#9b59b6",  # 可行域紫色
    "infeasible": "#e67e22",  # 不可行域橘色
}


class OptimizationVisualizer:
    """模型优化过程可视化工具"""

    def __init__(
        self, output_dir: str = "output/optimization_visualizations", dpi: int = 300
    ):
        """
        初始化优化可视化器

        Args:
            output_dir: 输出目录
            dpi: 图片分辨率
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.dpi = dpi
        self.logger = logging.getLogger(__name__)

        # 设置字体大小
        self.font_sizes = {
            "title": 14,
            "label": 12,
            "tick": 10,
            "legend": 11,
            "annotation": 10,
        }

        self.logger.info("优化过程可视化器初始化完成")

    def plot_convergence_history(
        self,
        best_values: List[float],
        mean_values: List[float] = None,
        worst_values: List[float] = None,
        target_value: float = None,
        generations: List[int] = None,
        algorithm_name: str = "Optimization Algorithm",
        metric_name: str = "Objective Function",
        save_path: str = None,
    ) -> str:
        """
        绘制优化收敛历史图

        Args:
            best_values: 每代最优值
            mean_values: 每代平均值
            worst_values: 每代最差值
            target_value: 目标值
            generations: 代数列表
            algorithm_name: 算法名称
            metric_name: 指标名称
            save_path: 保存路径

        Returns:
            str: 保存的图片路径
        """
        fig, ax = plt.subplots(1, 1, figsize=(10, 6))

        if generations is None:
            generations = list(range(1, len(best_values) + 1))

        # 绘制收敛曲线
        ax.plot(
            generations,
            best_values,
            color=OPT_COLORS["best"],
            linewidth=2.5,
            marker="o",
            markersize=4,
            label="Best Value",
            alpha=0.9,
        )

        if mean_values:
            ax.plot(
                generations,
                mean_values,
                color=OPT_COLORS["current"],
                linewidth=2,
                marker="s",
                markersize=3,
                label="Mean Value",
                alpha=0.8,
            )

        if worst_values:
            ax.plot(
                generations,
                worst_values,
                color=OPT_COLORS["population"],
                linewidth=1.5,
                marker="^",
                markersize=3,
                label="Worst Value",
                alpha=0.7,
            )

        # 添加目标线
        if target_value is not None:
            ax.axhline(
                y=target_value,
                color=OPT_COLORS["convergence"],
                linestyle="--",
                linewidth=2,
                alpha=0.8,
                label=f"Target ({target_value:.3f})",
            )

        # 填充区域
        if mean_values and worst_values:
            ax.fill_between(
                generations,
                mean_values,
                worst_values,
                color=OPT_COLORS["population"],
                alpha=0.2,
                label="Value Range",
            )

        ax.set_xlabel("Generation", fontsize=self.font_sizes["label"])
        ax.set_ylabel(metric_name, fontsize=self.font_sizes["label"])
        ax.set_title(
            f"{algorithm_name} - Convergence History",
            fontsize=self.font_sizes["title"],
            fontweight="bold",
        )
        ax.legend(fontsize=self.font_sizes["legend"])
        ax.grid(True, alpha=0.3)

        # 添加收敛信息文本框
        if best_values:
            final_best = best_values[-1]
            improvement = (
                abs(best_values[0] - final_best) if len(best_values) > 1 else 0
            )
            textstr = f"Final Best: {final_best:.4f}\nImprovement: {improvement:.4f}\nGenerations: {len(best_values)}"
            props = dict(boxstyle="round", facecolor="lightblue", alpha=0.8)
            ax.text(
                0.02,
                0.98,
                textstr,
                transform=ax.transAxes,
                fontsize=self.font_sizes["annotation"],
                verticalalignment="top",
                bbox=props,
            )

        plt.tight_layout()

        # 保存图片
        if save_path is None:
            save_path = (
                self.output_dir
                / f"{algorithm_name.lower().replace(' ', '_')}_convergence.png"
            )

        plt.savefig(save_path, dpi=self.dpi, bbox_inches="tight", facecolor="white")
        plt.close()

        self.logger.info(f"收敛历史图已保存: {save_path}")
        return str(save_path)

    def plot_parameter_evolution(
        self,
        parameter_history: Dict[str, List[float]],
        parameter_ranges: Dict[str, Tuple[float, float]] = None,
        generations: List[int] = None,
        algorithm_name: str = "Optimization Algorithm",
        save_path: str = None,
    ) -> str:
        """
        绘制参数进化过程图

        Args:
            parameter_history: 参数历史，格式：{'param1': [values], 'param2': [values], ...}
            parameter_ranges: 参数范围，格式：{'param1': (min, max), ...}
            generations: 代数列表
            algorithm_name: 算法名称
            save_path: 保存路径

        Returns:
            str: 保存的图片路径
        """
        n_params = len(parameter_history)
        if n_params == 0:
            return None

        # 计算子图布局
        n_cols = min(3, n_params)
        n_rows = (n_params + n_cols - 1) // n_cols

        fig, axes = plt.subplots(n_rows, n_cols, figsize=(5 * n_cols, 4 * n_rows))
        if n_params == 1:
            axes = [axes]
        elif n_rows == 1:
            axes = [axes]
        else:
            axes = axes.flatten()

        if generations is None:
            generations = list(range(1, len(list(parameter_history.values())[0]) + 1))

        colors = plt.cm.tab10(np.linspace(0, 1, n_params))

        for i, (param_name, values) in enumerate(parameter_history.items()):
            ax = axes[i]

            # 绘制参数进化曲线
            ax.plot(
                generations,
                values,
                color=colors[i],
                linewidth=2,
                marker="o",
                markersize=4,
                alpha=0.8,
            )

            # 添加参数范围
            if parameter_ranges and param_name in parameter_ranges:
                min_val, max_val = parameter_ranges[param_name]
                ax.axhline(
                    y=min_val, color="red", linestyle="--", alpha=0.5, label="Min Bound"
                )
                ax.axhline(
                    y=max_val, color="red", linestyle="--", alpha=0.5, label="Max Bound"
                )
                ax.fill_between(generations, min_val, max_val, alpha=0.1, color="gray")

            ax.set_xlabel("Generation", fontsize=self.font_sizes["label"])
            ax.set_ylabel(param_name, fontsize=self.font_sizes["label"])
            ax.set_title(
                f"{param_name} Evolution",
                fontsize=self.font_sizes["label"],
                fontweight="bold",
            )
            ax.grid(True, alpha=0.3)

            # 添加最终值注释
            if values:
                final_val = values[-1]
                ax.annotate(
                    f"{final_val:.3f}",
                    xy=(generations[-1], final_val),
                    xytext=(10, 10),
                    textcoords="offset points",
                    fontsize=self.font_sizes["annotation"],
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.7),
                    arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=0"),
                )

        # 隐藏多余的子图
        for i in range(n_params, len(axes)):
            axes[i].set_visible(False)

        plt.suptitle(
            f"{algorithm_name} - Parameter Evolution",
            fontsize=self.font_sizes["title"],
            fontweight="bold",
        )
        plt.tight_layout()

        # 保存图片
        if save_path is None:
            save_path = (
                self.output_dir
                / f"{algorithm_name.lower().replace(' ', '_')}_parameter_evolution.png"
            )

        plt.savefig(save_path, dpi=self.dpi, bbox_inches="tight", facecolor="white")
        plt.close()

        self.logger.info(f"参数进化图已保存: {save_path}")
        return str(save_path)

    def plot_parameter_correlation_matrix(
        self,
        parameter_samples: Dict[str, List[float]],
        objective_values: List[float] = None,
        algorithm_name: str = "Optimization Algorithm",
        save_path: str = None,
    ) -> str:
        """
        绘制参数相关性矩阵

        Args:
            parameter_samples: 参数样本
            objective_values: 目标函数值
            algorithm_name: 算法名称
            save_path: 保存路径

        Returns:
            str: 保存的图片路径
        """
        # 创建DataFrame
        df = pd.DataFrame(parameter_samples)
        if objective_values:
            df["Objective"] = objective_values

        # 计算相关性矩阵
        corr_matrix = df.corr()

        # 创建图形
        fig, ax = plt.subplots(1, 1, figsize=(10, 8))

        # 创建热力图
        mask = np.triu(np.ones_like(corr_matrix, dtype=bool))
        sns.heatmap(
            corr_matrix,
            mask=mask,
            annot=True,
            cmap="RdBu_r",
            center=0,
            square=True,
            linewidths=0.5,
            cbar_kws={"shrink": 0.8},
            ax=ax,
            fmt=".3f",
            annot_kws={"fontsize": self.font_sizes["annotation"]},
        )

        ax.set_title(
            f"{algorithm_name} - Parameter Correlation Matrix",
            fontsize=self.font_sizes["title"],
            fontweight="bold",
        )

        plt.tight_layout()

        # 保存图片
        if save_path is None:
            save_path = (
                self.output_dir
                / f"{algorithm_name.lower().replace(' ', '_')}_correlation_matrix.png"
            )

        plt.savefig(save_path, dpi=self.dpi, bbox_inches="tight", facecolor="white")
        plt.close()

        self.logger.info(f"参数相关性矩阵已保存: {save_path}")
        return str(save_path)

    def plot_pareto_front(
        self,
        objective1_values: List[float],
        objective2_values: List[float],
        pareto_indices: List[int] = None,
        obj1_name: str = "Objective 1",
        obj2_name: str = "Objective 2",
        algorithm_name: str = "Multi-Objective Optimization",
        save_path: str = None,
    ) -> str:
        """
        绘制帕累托前沿图（多目标优化）

        Args:
            objective1_values: 目标1值列表
            objective2_values: 目标2值列表
            pareto_indices: 帕累托最优解索引
            obj1_name: 目标1名称
            obj2_name: 目标2名称
            algorithm_name: 算法名称
            save_path: 保存路径

        Returns:
            str: 保存的图片路径
        """
        fig, ax = plt.subplots(1, 1, figsize=(10, 8))

        # 绘制所有解
        ax.scatter(
            objective1_values,
            objective2_values,
            color=OPT_COLORS["population"],
            alpha=0.6,
            s=50,
            label="All Solutions",
            edgecolors="white",
            linewidth=0.5,
        )

        # 绘制帕累托前沿
        if pareto_indices:
            pareto_obj1 = [objective1_values[i] for i in pareto_indices]
            pareto_obj2 = [objective2_values[i] for i in pareto_indices]

            # 排序以便连线
            pareto_points = list(zip(pareto_obj1, pareto_obj2))
            pareto_points.sort()
            pareto_obj1_sorted, pareto_obj2_sorted = zip(*pareto_points)

            ax.scatter(
                pareto_obj1_sorted,
                pareto_obj2_sorted,
                color=OPT_COLORS["best"],
                s=80,
                alpha=0.9,
                label="Pareto Front",
                edgecolors="black",
                linewidth=1,
                marker="D",
            )

            # 连接帕累托前沿点
            ax.plot(
                pareto_obj1_sorted,
                pareto_obj2_sorted,
                color=OPT_COLORS["best"],
                linewidth=2,
                alpha=0.7,
                linestyle="-",
            )

        ax.set_xlabel(obj1_name, fontsize=self.font_sizes["label"])
        ax.set_ylabel(obj2_name, fontsize=self.font_sizes["label"])
        ax.set_title(
            f"{algorithm_name} - Pareto Front",
            fontsize=self.font_sizes["title"],
            fontweight="bold",
        )
        ax.legend(fontsize=self.font_sizes["legend"])
        ax.grid(True, alpha=0.3)

        # 添加统计信息
        total_solutions = len(objective1_values)
        pareto_solutions = len(pareto_indices) if pareto_indices else 0
        textstr = f"Total Solutions: {total_solutions}\nPareto Solutions: {pareto_solutions}\nPareto Ratio: {pareto_solutions/total_solutions:.2%}"
        props = dict(boxstyle="round", facecolor="lightgreen", alpha=0.8)
        ax.text(
            0.02,
            0.98,
            textstr,
            transform=ax.transAxes,
            fontsize=self.font_sizes["annotation"],
            verticalalignment="top",
            bbox=props,
        )

        plt.tight_layout()

        # 保存图片
        if save_path is None:
            save_path = (
                self.output_dir
                / f"{algorithm_name.lower().replace(' ', '_')}_pareto_front.png"
            )

        plt.savefig(save_path, dpi=self.dpi, bbox_inches="tight", facecolor="white")
        plt.close()

        self.logger.info(f"帕累托前沿图已保存: {save_path}")
        return str(save_path)

    def plot_objective_surface(
        self,
        param1_values: List[float],
        param2_values: List[float],
        objective_values: List[float],
        param1_name: str = "Parameter 1",
        param2_name: str = "Parameter 2",
        objective_name: str = "Objective Function",
        best_point: Tuple[float, float, float] = None,
        save_path: str = None,
    ) -> str:
        """
        绘制目标函数表面图（3D）

        Args:
            param1_values: 参数1值列表
            param2_values: 参数2值列表
            objective_values: 目标函数值列表
            param1_name: 参数1名称
            param2_name: 参数2名称
            objective_name: 目标函数名称
            best_point: 最优点坐标 (param1, param2, objective)
            save_path: 保存路径

        Returns:
            str: 保存的图片路径
        """
        fig = plt.figure(figsize=(12, 9))
        ax = fig.add_subplot(111, projection="3d")

        # 创建网格
        xi = np.linspace(min(param1_values), max(param1_values), 50)
        yi = np.linspace(min(param2_values), max(param2_values), 50)
        Xi, Yi = np.meshgrid(xi, yi)

        # 插值生成表面
        try:
            Zi = griddata(
                (param1_values, param2_values),
                objective_values,
                (Xi, Yi),
                method="linear",
            )

            # 绘制表面
            surf = ax.plot_surface(
                Xi, Yi, Zi, cmap="viridis", alpha=0.8, linewidth=0, antialiased=True
            )

            # 添加颜色条
            fig.colorbar(surf, ax=ax, shrink=0.5, aspect=20)

        except Exception as e:
            self.logger.warning(f"无法生成表面图: {e}，改为绘制散点图")

        # 绘制样本点
        scatter = ax.scatter(
            param1_values,
            param2_values,
            objective_values,
            c=objective_values,
            cmap="plasma",
            s=30,
            alpha=0.8,
        )

        # 标记最优点
        if best_point:
            ax.scatter(
                [best_point[0]],
                [best_point[1]],
                [best_point[2]],
                color=OPT_COLORS["best"],
                s=200,
                marker="*",
                label=f"Best Point ({best_point[2]:.3f})",
                edgecolors="black",
            )

        ax.set_xlabel(param1_name, fontsize=self.font_sizes["label"])
        ax.set_ylabel(param2_name, fontsize=self.font_sizes["label"])
        ax.set_zlabel(objective_name, fontsize=self.font_sizes["label"])
        ax.set_title(
            "Objective Function Surface",
            fontsize=self.font_sizes["title"],
            fontweight="bold",
        )

        if best_point:
            ax.legend(fontsize=self.font_sizes["legend"])

        plt.tight_layout()

        # 保存图片
        if save_path is None:
            save_path = self.output_dir / "objective_function_surface.png"

        plt.savefig(save_path, dpi=self.dpi, bbox_inches="tight", facecolor="white")
        plt.close()

        self.logger.info(f"目标函数表面图已保存: {save_path}")
        return str(save_path)

    def plot_optimization_statistics(
        self,
        statistics_data: Dict[str, Any],
        algorithm_name: str = "Optimization Algorithm",
        save_path: str = None,
    ) -> str:
        """
        绘制优化统计信息图表

        Args:
            statistics_data: 统计数据，包含各种优化指标
            algorithm_name: 算法名称
            save_path: 保存路径

        Returns:
            str: 保存的图片路径
        """
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))

        # 1. 收敛速度分布
        if "convergence_generations" in statistics_data:
            ax1 = axes[0, 0]
            conv_gens = statistics_data["convergence_generations"]
            ax1.hist(
                conv_gens,
                bins=20,
                color=OPT_COLORS["progress"],
                alpha=0.7,
                edgecolor="black",
                linewidth=0.5,
            )
            ax1.axvline(
                np.mean(conv_gens),
                color="red",
                linestyle="--",
                label=f"Mean: {np.mean(conv_gens):.1f}",
            )
            ax1.set_xlabel("Convergence Generation")
            ax1.set_ylabel("Frequency")
            ax1.set_title("Convergence Speed Distribution")
            ax1.legend()
            ax1.grid(True, alpha=0.3)

        # 2. 参数值分布
        if "final_parameters" in statistics_data:
            ax2 = axes[0, 1]
            param_data = statistics_data["final_parameters"]
            param_names = list(param_data.keys())
            param_values = [param_data[name] for name in param_names]

            box_plot = ax2.boxplot(param_values, labels=param_names, patch_artist=True)
            colors = plt.cm.Set3(np.linspace(0, 1, len(param_names)))
            for patch, color in zip(box_plot["boxes"], colors):
                patch.set_facecolor(color)
                patch.set_alpha(0.7)

            ax2.set_ylabel("Parameter Values")
            ax2.set_title("Final Parameter Distributions")
            ax2.grid(True, alpha=0.3, axis="y")
            plt.setp(ax2.get_xticklabels(), rotation=45, ha="right")

        # 3. 目标函数改进
        if "improvement_history" in statistics_data:
            ax3 = axes[1, 0]
            improvements = statistics_data["improvement_history"]
            generations = range(1, len(improvements) + 1)
            ax3.plot(
                generations,
                improvements,
                color=OPT_COLORS["current"],
                linewidth=2,
                marker="o",
                markersize=4,
            )
            ax3.set_xlabel("Generation")
            ax3.set_ylabel("Improvement")
            ax3.set_title("Objective Function Improvement")
            ax3.grid(True, alpha=0.3)

        # 4. 算法性能指标
        if "performance_metrics" in statistics_data:
            ax4 = axes[1, 1]
            metrics = statistics_data["performance_metrics"]
            metric_names = list(metrics.keys())
            metric_values = list(metrics.values())

            bars = ax4.bar(
                metric_names, metric_values, color=OPT_COLORS["feasible"], alpha=0.7
            )
            for i, bar in enumerate(bars):
                height = bar.get_height()
                ax4.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    height + 0.01,
                    f"{height:.3f}",
                    ha="center",
                    va="bottom",
                    fontsize=self.font_sizes["annotation"],
                )

            ax4.set_ylabel("Metric Value")
            ax4.set_title("Performance Metrics")
            ax4.grid(True, alpha=0.3, axis="y")
            plt.setp(ax4.get_xticklabels(), rotation=45, ha="right")

        plt.suptitle(
            f"{algorithm_name} - Optimization Statistics",
            fontsize=self.font_sizes["title"],
            fontweight="bold",
        )
        plt.tight_layout()

        # 保存图片
        if save_path is None:
            save_path = (
                self.output_dir
                / f"{algorithm_name.lower().replace(' ', '_')}_statistics.png"
            )

        plt.savefig(save_path, dpi=self.dpi, bbox_inches="tight", facecolor="white")
        plt.close()

        self.logger.info(f"优化统计图已保存: {save_path}")
        return str(save_path)

    def create_optimization_report(
        self,
        optimization_data: Dict[str, Any],
        algorithm_name: str = "Optimization Algorithm",
        save_path: str = None,
    ) -> str:
        """
        创建完整的优化报告

        Args:
            optimization_data: 优化数据
            algorithm_name: 算法名称
            save_path: 保存路径

        Returns:
            str: 报告路径
        """
        charts = {}

        # 生成各类图表
        if "convergence_history" in optimization_data:
            conv_data = optimization_data["convergence_history"]
            charts["convergence"] = self.plot_convergence_history(
                conv_data.get("best_values", []),
                conv_data.get("mean_values"),
                conv_data.get("worst_values"),
                conv_data.get("target_value"),
                algorithm_name=algorithm_name,
            )

        if "parameter_history" in optimization_data:
            charts["parameters"] = self.plot_parameter_evolution(
                optimization_data["parameter_history"],
                optimization_data.get("parameter_ranges"),
                algorithm_name=algorithm_name,
            )

        if "parameter_samples" in optimization_data:
            charts["correlation"] = self.plot_parameter_correlation_matrix(
                optimization_data["parameter_samples"],
                optimization_data.get("objective_values"),
                algorithm_name=algorithm_name,
            )

        if "statistics" in optimization_data:
            charts["statistics"] = self.plot_optimization_statistics(
                optimization_data["statistics"], algorithm_name=algorithm_name
            )

        # 生成HTML报告
        if save_path is None:
            save_path = (
                self.output_dir
                / f"{algorithm_name.lower().replace(' ', '_')}_optimization_report.html"
            )

        html_content = self._generate_optimization_report_html(
            optimization_data, charts, algorithm_name
        )

        with open(save_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        self.logger.info(f"优化报告已生成: {save_path}")
        return str(save_path)

    def _generate_optimization_report_html(
        self, data: Dict[str, Any], charts: Dict[str, str], algorithm_name: str
    ) -> str:
        """生成优化报告HTML"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{algorithm_name} - 优化报告</title>
    <style>
        body {{ font-family: 'Arial', sans-serif; margin: 20px; background: #f8f9fa; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
        .header {{ text-align: center; margin-bottom: 30px; padding-bottom: 20px; border-bottom: 3px solid #007bff; }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 30px 0; }}
        .summary-card {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }}
        .chart-section {{ margin: 40px 0; }}
        .chart-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }}
        .chart-card {{ background: #f8f9fa; padding: 20px; border-radius: 10px; text-align: center; border: 1px solid #dee2e6; }}
        .chart-card img {{ max-width: 100%; height: auto; border-radius: 5px; }}
        .chart-title {{ font-size: 16px; font-weight: bold; margin-bottom: 15px; color: #495057; }}
        h1 {{ color: #007bff; margin-bottom: 10px; }}
        h2 {{ color: #495057; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        .metric-value {{ font-size: 24px; font-weight: bold; margin: 10px 0; }}
        .metric-label {{ font-size: 14px; opacity: 0.9; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{algorithm_name}</h1>
            <h2>优化过程分析报告</h2>
            <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>

        <div class="summary-grid">
        """

        # 添加摘要信息
        if "final_best" in data:
            html += f"""
            <div class="summary-card">
                <div class="metric-label">最优目标值</div>
                <div class="metric-value">{data['final_best']:.6f}</div>
            </div>
            """

        if "total_generations" in data:
            html += f"""
            <div class="summary-card">
                <div class="metric-label">总代数</div>
                <div class="metric-value">{data['total_generations']}</div>
            </div>
            """

        if "total_evaluations" in data:
            html += f"""
            <div class="summary-card">
                <div class="metric-label">总评估次数</div>
                <div class="metric-value">{data['total_evaluations']}</div>
            </div>
            """

        if "convergence_generation" in data:
            html += f"""
            <div class="summary-card">
                <div class="metric-label">收敛代数</div>
                <div class="metric-value">{data['convergence_generation']}</div>
            </div>
            """

        html += """
        </div>

        <div class="chart-section">
            <h2>优化过程可视化</h2>
            <div class="chart-grid">
        """

        # 添加图表
        chart_titles = {
            "convergence": "收敛历史",
            "parameters": "参数进化",
            "correlation": "参数相关性",
            "statistics": "统计信息",
        }

        for chart_key, chart_path in charts.items():
            if chart_path:
                title = chart_titles.get(chart_key, chart_key)
                chart_filename = Path(chart_path).name
                html += f"""
                <div class="chart-card">
                    <div class="chart-title">{title}</div>
                    <img src="{chart_filename}" alt="{title}">
                </div>
                """

        html += """
            </div>
        </div>

        <div class="chart-section">
            <h2>说明</h2>
            <p>本报告展示了优化算法的完整运行过程，包括收敛历史、参数演化、相关性分析等关键信息。</p>
            <p>所有图表均采用论文级别的质量设置，可直接用于学术发表。</p>
        </div>
    </div>
</body>
</html>
        """

        return html
