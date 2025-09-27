"""
Author: zhuanglaihong
Date: 2024-09-26 16:40:00
LastEditTime: 2024-09-26 16:40:00
LastEditors: zhuanglaihong
Description: 水文模型专业可视化工具 - 生成论文级别的水文建模图表
FilePath: \HydroAgent\executor\visualization\hydro_visualizer.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import seaborn as sns
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timedelta
import logging
from scipy import stats
from sklearn.metrics import r2_score
import warnings
warnings.filterwarnings('ignore')

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 设置论文级别的matplotlib样式
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette("husl")

# 定义论文级别的颜色方案
PAPER_COLORS = {
    'primary': '#2E86AB',      # 主要蓝色
    'secondary': '#A23B72',    # 辅助紫红色
    'success': '#F18F01',      # 成功橙色
    'warning': '#C73E1D',      # 警告红色
    'observed': '#1f77b4',     # 观测值蓝色
    'simulated': '#ff7f0e',    # 模拟值橙色
    'calibration': '#2ca02c',  # 率定期绿色
    'validation': '#d62728',   # 验证期红色
    'grid': '#e6e6e6',         # 网格线灰色
    'text': '#333333'          # 文本颜色
}


class HydroVisualizer:
    """水文模型专业可视化工具"""

    def __init__(self, output_dir: str = "output/hydro_visualizations", dpi: int = 300):
        """
        初始化水文可视化器

        Args:
            output_dir: 输出目录
            dpi: 图片分辨率（论文级别推荐300）
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.dpi = dpi
        self.logger = logging.getLogger(__name__)

        # 设置全局字体大小（适合论文）
        self.font_sizes = {
            'title': 14,
            'label': 12,
            'tick': 10,
            'legend': 11,
            'annotation': 10
        }

        self.logger.info("水文模型可视化器初始化完成")

    def plot_calibration_results(
        self,
        observed: Union[np.ndarray, List[float]],
        simulated: Union[np.ndarray, List[float]],
        dates: Union[np.ndarray, List[datetime]] = None,
        model_name: str = "Hydrological Model",
        metrics: Dict[str, float] = None,
        save_path: str = None
    ) -> str:
        """
        绘制模型率定结果对比图

        Args:
            observed: 观测径流数据
            simulated: 模拟径流数据
            dates: 时间序列
            model_name: 模型名称
            metrics: 性能指标字典
            save_path: 保存路径

        Returns:
            str: 保存的图片路径
        """
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)

        observed = np.array(observed)
        simulated = np.array(simulated)

        if dates is None:
            dates = pd.date_range('2010-01-01', periods=len(observed), freq='D')
        elif not isinstance(dates[0], (pd.Timestamp, datetime)):
            dates = pd.to_datetime(dates)

        # 上图：时间序列对比
        ax1.plot(dates, observed, color=PAPER_COLORS['observed'],
                label='Observed', linewidth=1.5, alpha=0.8)
        ax1.plot(dates, simulated, color=PAPER_COLORS['simulated'],
                label='Simulated', linewidth=1.5, alpha=0.8)

        ax1.set_ylabel('Discharge (m³/s)', fontsize=self.font_sizes['label'])
        ax1.set_title(f'{model_name} Calibration Results',
                     fontsize=self.font_sizes['title'], fontweight='bold')
        ax1.legend(fontsize=self.font_sizes['legend'])
        ax1.grid(True, alpha=0.3)

        # 设置时间轴格式
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=6))

        # 下图：散点图对比
        ax2.scatter(observed, simulated, alpha=0.6, s=20,
                   color=PAPER_COLORS['primary'], edgecolors='white', linewidth=0.5)

        # 1:1线
        max_val = max(np.max(observed), np.max(simulated))
        min_val = min(np.min(observed), np.min(simulated))
        ax2.plot([min_val, max_val], [min_val, max_val],
                'r--', linewidth=2, label='1:1 Line', alpha=0.8)

        # 拟合线
        z = np.polyfit(observed, simulated, 1)
        p = np.poly1d(z)
        ax2.plot(observed, p(observed), color=PAPER_COLORS['success'],
                linewidth=2, label=f'Fit Line (y={z[0]:.2f}x+{z[1]:.2f})')

        ax2.set_xlabel('Observed Discharge (m³/s)', fontsize=self.font_sizes['label'])
        ax2.set_ylabel('Simulated Discharge (m³/s)', fontsize=self.font_sizes['label'])
        ax2.set_title('Observed vs Simulated Scatter Plot', fontsize=self.font_sizes['label'])
        ax2.legend(fontsize=self.font_sizes['legend'])
        ax2.grid(True, alpha=0.3)

        # 添加性能指标文本框
        if metrics:
            textstr = '\n'.join([f'{k}: {v:.3f}' for k, v in metrics.items()])
            props = dict(boxstyle='round', facecolor='wheat', alpha=0.8)
            ax2.text(0.05, 0.95, textstr, transform=ax2.transAxes, fontsize=self.font_sizes['annotation'],
                    verticalalignment='top', bbox=props)

        plt.tight_layout()

        # 保存图片
        if save_path is None:
            save_path = self.output_dir / f"{model_name.lower().replace(' ', '_')}_calibration.png"

        plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight', facecolor='white')
        plt.close()

        self.logger.info(f"率定结果图已保存: {save_path}")
        return str(save_path)

    def plot_model_performance_metrics(
        self,
        metrics_data: Dict[str, Dict[str, float]],
        model_names: List[str] = None,
        save_path: str = None
    ) -> str:
        """
        绘制模型性能指标对比图

        Args:
            metrics_data: 指标数据，格式：{'model1': {'NSE': 0.8, 'KGE': 0.75, ...}, ...}
            model_names: 模型名称列表
            save_path: 保存路径

        Returns:
            str: 保存的图片路径
        """
        if model_names is None:
            model_names = list(metrics_data.keys())

        # 准备数据
        df_metrics = pd.DataFrame(metrics_data).T

        # 创建子图
        n_metrics = len(df_metrics.columns)
        fig, axes = plt.subplots(1, n_metrics, figsize=(4*n_metrics, 6))
        if n_metrics == 1:
            axes = [axes]

        colors = sns.color_palette("husl", len(model_names))

        for i, metric in enumerate(df_metrics.columns):
            ax = axes[i]

            # 柱状图
            bars = ax.bar(model_names, df_metrics[metric],
                         color=colors, alpha=0.7, edgecolor='black', linewidth=0.5)

            # 添加数值标签
            for j, bar in enumerate(bars):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height + 0.01,
                       f'{height:.3f}', ha='center', va='bottom',
                       fontsize=self.font_sizes['annotation'])

            ax.set_title(f'{metric} Performance', fontsize=self.font_sizes['title'], fontweight='bold')
            ax.set_ylabel(metric, fontsize=self.font_sizes['label'])
            ax.grid(True, alpha=0.3, axis='y')

            # 设置Y轴范围
            if metric.upper() in ['NSE', 'KGE', 'R2']:
                ax.set_ylim(-0.1, 1.1)
            elif metric.upper() in ['PBIAS']:
                ax.set_ylim(-100, 100)

            # 旋转X轴标签
            plt.setp(ax.get_xticklabels(), rotation=45, ha='right')

        plt.tight_layout()

        # 保存图片
        if save_path is None:
            save_path = self.output_dir / "model_performance_metrics.png"

        plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight', facecolor='white')
        plt.close()

        self.logger.info(f"性能指标对比图已保存: {save_path}")
        return str(save_path)

    def plot_flow_duration_curve(
        self,
        observed: Union[np.ndarray, List[float]],
        simulated: Union[np.ndarray, List[float]],
        model_name: str = "Hydrological Model",
        save_path: str = None
    ) -> str:
        """
        绘制流量历时曲线（Flow Duration Curve）

        Args:
            observed: 观测径流数据
            simulated: 模拟径流数据
            model_name: 模型名称
            save_path: 保存路径

        Returns:
            str: 保存的图片路径
        """
        fig, ax = plt.subplots(1, 1, figsize=(10, 6))

        observed = np.array(observed)
        simulated = np.array(simulated)

        # 计算超过概率
        obs_sorted = np.sort(observed)[::-1]  # 降序排列
        sim_sorted = np.sort(simulated)[::-1]
        n = len(observed)
        exceedance_prob = np.arange(1, n+1) / n * 100

        # 绘制FDC
        ax.semilogy(exceedance_prob, obs_sorted, color=PAPER_COLORS['observed'],
                   linewidth=2, label='Observed', alpha=0.8)
        ax.semilogy(exceedance_prob, sim_sorted, color=PAPER_COLORS['simulated'],
                   linewidth=2, label='Simulated', alpha=0.8)

        ax.set_xlabel('Exceedance Probability (%)', fontsize=self.font_sizes['label'])
        ax.set_ylabel('Discharge (m³/s)', fontsize=self.font_sizes['label'])
        ax.set_title(f'{model_name} - Flow Duration Curve',
                    fontsize=self.font_sizes['title'], fontweight='bold')
        ax.legend(fontsize=self.font_sizes['legend'])
        ax.grid(True, alpha=0.3)
        ax.set_xlim(0, 100)

        plt.tight_layout()

        # 保存图片
        if save_path is None:
            save_path = self.output_dir / f"{model_name.lower().replace(' ', '_')}_fdc.png"

        plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight', facecolor='white')
        plt.close()

        self.logger.info(f"流量历时曲线已保存: {save_path}")
        return str(save_path)

    def plot_hydrograph_separation(
        self,
        observed: Union[np.ndarray, List[float]],
        simulated: Union[np.ndarray, List[float]],
        dates: Union[np.ndarray, List[datetime]],
        cal_start: str = None,
        cal_end: str = None,
        val_start: str = None,
        val_end: str = None,
        model_name: str = "Hydrological Model",
        save_path: str = None
    ) -> str:
        """
        绘制率定期和验证期分离的水文过程线

        Args:
            observed: 观测径流数据
            simulated: 模拟径流数据
            dates: 时间序列
            cal_start: 率定期开始时间
            cal_end: 率定期结束时间
            val_start: 验证期开始时间
            val_end: 验证期结束时间
            model_name: 模型名称
            save_path: 保存路径

        Returns:
            str: 保存的图片路径
        """
        fig, ax = plt.subplots(1, 1, figsize=(14, 8))

        observed = np.array(observed)
        simulated = np.array(simulated)

        if not isinstance(dates[0], (pd.Timestamp, datetime)):
            dates = pd.to_datetime(dates)

        # 绘制完整时间序列
        ax.plot(dates, observed, color=PAPER_COLORS['observed'],
               label='Observed', linewidth=1.5, alpha=0.8)
        ax.plot(dates, simulated, color=PAPER_COLORS['simulated'],
               label='Simulated', linewidth=1.5, alpha=0.8)

        # 标记率定期和验证期
        if cal_start and cal_end:
            cal_start_dt = pd.to_datetime(cal_start)
            cal_end_dt = pd.to_datetime(cal_end)
            ax.axvspan(cal_start_dt, cal_end_dt, alpha=0.2, color=PAPER_COLORS['calibration'],
                      label='Calibration Period')

        if val_start and val_end:
            val_start_dt = pd.to_datetime(val_start)
            val_end_dt = pd.to_datetime(val_end)
            ax.axvspan(val_start_dt, val_end_dt, alpha=0.2, color=PAPER_COLORS['validation'],
                      label='Validation Period')

        ax.set_xlabel('Date', fontsize=self.font_sizes['label'])
        ax.set_ylabel('Discharge (m³/s)', fontsize=self.font_sizes['label'])
        ax.set_title(f'{model_name} - Hydrograph with Calibration/Validation Periods',
                    fontsize=self.font_sizes['title'], fontweight='bold')
        ax.legend(fontsize=self.font_sizes['legend'])
        ax.grid(True, alpha=0.3)

        # 设置时间轴格式
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
        plt.setp(ax.get_xticklabels(), rotation=45, ha='right')

        plt.tight_layout()

        # 保存图片
        if save_path is None:
            save_path = self.output_dir / f"{model_name.lower().replace(' ', '_')}_hydrograph_separation.png"

        plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight', facecolor='white')
        plt.close()

        self.logger.info(f"分期水文过程线已保存: {save_path}")
        return str(save_path)

    def plot_residual_analysis(
        self,
        observed: Union[np.ndarray, List[float]],
        simulated: Union[np.ndarray, List[float]],
        model_name: str = "Hydrological Model",
        save_path: str = None
    ) -> str:
        """
        绘制残差分析图

        Args:
            observed: 观测径流数据
            simulated: 模拟径流数据
            model_name: 模型名称
            save_path: 保存路径

        Returns:
            str: 保存的图片路径
        """
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))

        observed = np.array(observed)
        simulated = np.array(simulated)
        residuals = observed - simulated

        # 1. 残差时间序列图
        ax1 = axes[0, 0]
        ax1.plot(residuals, color=PAPER_COLORS['primary'], linewidth=1, alpha=0.7)
        ax1.axhline(y=0, color='red', linestyle='--', alpha=0.8)
        ax1.set_title('Residuals Time Series', fontsize=self.font_sizes['label'], fontweight='bold')
        ax1.set_xlabel('Time Index', fontsize=self.font_sizes['label'])
        ax1.set_ylabel('Residuals (m³/s)', fontsize=self.font_sizes['label'])
        ax1.grid(True, alpha=0.3)

        # 2. 残差 vs 模拟值散点图
        ax2 = axes[0, 1]
        ax2.scatter(simulated, residuals, alpha=0.6, s=20,
                   color=PAPER_COLORS['secondary'], edgecolors='white', linewidth=0.5)
        ax2.axhline(y=0, color='red', linestyle='--', alpha=0.8)
        ax2.set_title('Residuals vs Simulated', fontsize=self.font_sizes['label'], fontweight='bold')
        ax2.set_xlabel('Simulated Discharge (m³/s)', fontsize=self.font_sizes['label'])
        ax2.set_ylabel('Residuals (m³/s)', fontsize=self.font_sizes['label'])
        ax2.grid(True, alpha=0.3)

        # 3. 残差直方图
        ax3 = axes[1, 0]
        ax3.hist(residuals, bins=30, alpha=0.7, color=PAPER_COLORS['success'],
                edgecolor='black', linewidth=0.5)
        ax3.axvline(x=0, color='red', linestyle='--', alpha=0.8)
        ax3.set_title('Residuals Distribution', fontsize=self.font_sizes['label'], fontweight='bold')
        ax3.set_xlabel('Residuals (m³/s)', fontsize=self.font_sizes['label'])
        ax3.set_ylabel('Frequency', fontsize=self.font_sizes['label'])
        ax3.grid(True, alpha=0.3)

        # 4. Q-Q图
        ax4 = axes[1, 1]
        stats.probplot(residuals, dist="norm", plot=ax4)
        ax4.set_title('Q-Q Plot (Normality Test)', fontsize=self.font_sizes['label'], fontweight='bold')
        ax4.grid(True, alpha=0.3)

        plt.tight_layout()

        # 保存图片
        if save_path is None:
            save_path = self.output_dir / f"{model_name.lower().replace(' ', '_')}_residual_analysis.png"

        plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight', facecolor='white')
        plt.close()

        self.logger.info(f"残差分析图已保存: {save_path}")
        return str(save_path)

    def plot_parameter_sensitivity(
        self,
        param_names: List[str],
        param_values: List[List[float]],
        param_sensitivities: List[float],
        model_name: str = "Hydrological Model",
        save_path: str = None
    ) -> str:
        """
        绘制参数敏感性分析图

        Args:
            param_names: 参数名称列表
            param_values: 参数值列表的列表
            param_sensitivities: 参数敏感性值列表
            model_name: 模型名称
            save_path: 保存路径

        Returns:
            str: 保存的图片路径
        """
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

        # 1. 参数敏感性柱状图
        colors = plt.cm.viridis(np.linspace(0, 1, len(param_names)))
        bars = ax1.barh(param_names, param_sensitivities, color=colors, alpha=0.7, edgecolor='black')

        # 添加数值标签
        for i, bar in enumerate(bars):
            width = bar.get_width()
            ax1.text(width + 0.001, bar.get_y() + bar.get_height()/2,
                    f'{width:.3f}', ha='left', va='center', fontsize=self.font_sizes['annotation'])

        ax1.set_xlabel('Sensitivity Index', fontsize=self.font_sizes['label'])
        ax1.set_title('Parameter Sensitivity Analysis', fontsize=self.font_sizes['title'], fontweight='bold')
        ax1.grid(True, alpha=0.3, axis='x')

        # 2. 参数值范围箱线图
        param_data = []
        param_labels = []
        for i, (name, values) in enumerate(zip(param_names, param_values)):
            param_data.append(values)
            param_labels.append(name)

        box_plot = ax2.boxplot(param_data, labels=param_labels, patch_artist=True)

        # 设置箱线图颜色
        for patch, color in zip(box_plot['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        ax2.set_ylabel('Parameter Values', fontsize=self.font_sizes['label'])
        ax2.set_title('Parameter Value Distributions', fontsize=self.font_sizes['title'], fontweight='bold')
        ax2.grid(True, alpha=0.3, axis='y')
        plt.setp(ax2.get_xticklabels(), rotation=45, ha='right')

        plt.tight_layout()

        # 保存图片
        if save_path is None:
            save_path = self.output_dir / f"{model_name.lower().replace(' ', '_')}_parameter_sensitivity.png"

        plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight', facecolor='white')
        plt.close()

        self.logger.info(f"参数敏感性分析图已保存: {save_path}")
        return str(save_path)

    def calculate_hydro_metrics(
        self,
        observed: Union[np.ndarray, List[float]],
        simulated: Union[np.ndarray, List[float]]
    ) -> Dict[str, float]:
        """
        计算水文模型评估指标

        Args:
            observed: 观测值
            simulated: 模拟值

        Returns:
            Dict[str, float]: 指标字典
        """
        observed = np.array(observed)
        simulated = np.array(simulated)

        # 去除NaN值
        valid_mask = ~(np.isnan(observed) | np.isnan(simulated))
        obs_clean = observed[valid_mask]
        sim_clean = simulated[valid_mask]

        if len(obs_clean) == 0:
            return {}

        # Nash-Sutcliffe Efficiency
        nse = 1 - np.sum((obs_clean - sim_clean) ** 2) / np.sum((obs_clean - np.mean(obs_clean)) ** 2)

        # Kling-Gupta Efficiency
        r = np.corrcoef(obs_clean, sim_clean)[0, 1]
        alpha = np.std(sim_clean) / np.std(obs_clean)
        beta = np.mean(sim_clean) / np.mean(obs_clean)
        kge = 1 - np.sqrt((r - 1) ** 2 + (alpha - 1) ** 2 + (beta - 1) ** 2)

        # R-squared
        r2 = r2_score(obs_clean, sim_clean)

        # Percent Bias
        pbias = 100 * np.sum(sim_clean - obs_clean) / np.sum(obs_clean)

        # Root Mean Square Error
        rmse = np.sqrt(np.mean((obs_clean - sim_clean) ** 2))

        # Mean Absolute Error
        mae = np.mean(np.abs(obs_clean - sim_clean))

        return {
            'NSE': nse,
            'KGE': kge,
            'R2': r2,
            'PBIAS': pbias,
            'RMSE': rmse,
            'MAE': mae
        }

    def plot_multi_model_comparison(
        self,
        model_results: Dict[str, Dict[str, Union[np.ndarray, List[float]]]],
        dates: Union[np.ndarray, List[datetime]] = None,
        save_path: str = None
    ) -> str:
        """
        绘制多模型对比图

        Args:
            model_results: 模型结果字典，格式：{'model1': {'observed': [...], 'simulated': [...]}, ...}
            dates: 时间序列
            save_path: 保存路径

        Returns:
            str: 保存的图片路径
        """
        n_models = len(model_results)
        fig, axes = plt.subplots(n_models, 1, figsize=(14, 4*n_models), sharex=True)

        if n_models == 1:
            axes = [axes]

        colors = sns.color_palette("husl", n_models)

        for i, (model_name, results) in enumerate(model_results.items()):
            ax = axes[i]

            observed = np.array(results['observed'])
            simulated = np.array(results['simulated'])

            if dates is None:
                dates = pd.date_range('2010-01-01', periods=len(observed), freq='D')
            elif not isinstance(dates[0], (pd.Timestamp, datetime)):
                dates = pd.to_datetime(dates)

            # 绘制观测值和模拟值
            ax.plot(dates, observed, color=PAPER_COLORS['observed'],
                   label='Observed', linewidth=1.5, alpha=0.8)
            ax.plot(dates, simulated, color=colors[i],
                   label=f'Simulated ({model_name})', linewidth=1.5, alpha=0.8)

            # 计算并显示指标
            metrics = self.calculate_hydro_metrics(observed, simulated)
            textstr = f"NSE: {metrics.get('NSE', 0):.3f}, KGE: {metrics.get('KGE', 0):.3f}, R²: {metrics.get('R2', 0):.3f}"
            ax.text(0.02, 0.95, textstr, transform=ax.transAxes, fontsize=self.font_sizes['annotation'],
                   verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

            ax.set_ylabel('Discharge (m³/s)', fontsize=self.font_sizes['label'])
            ax.set_title(f'{model_name} Model Results', fontsize=self.font_sizes['title'], fontweight='bold')
            ax.legend(fontsize=self.font_sizes['legend'])
            ax.grid(True, alpha=0.3)

        # 设置底部图的X轴
        axes[-1].set_xlabel('Date', fontsize=self.font_sizes['label'])
        axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        axes[-1].xaxis.set_major_locator(mdates.MonthLocator(interval=6))
        plt.setp(axes[-1].get_xticklabels(), rotation=45, ha='right')

        plt.tight_layout()

        # 保存图片
        if save_path is None:
            save_path = self.output_dir / "multi_model_comparison.png"

        plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight', facecolor='white')
        plt.close()

        self.logger.info(f"多模型对比图已保存: {save_path}")
        return str(save_path)