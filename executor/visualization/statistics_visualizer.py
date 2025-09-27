"""
Author: zhuanglaihong
Date: 2024-09-26 16:40:00
LastEditTime: 2024-09-26 16:40:00
LastEditors: zhuanglaihong
Description: 统计分析和成功率可视化工具 - 用于系统性能分析和论文展示
FilePath: \HydroAgent\executor\visualization\statistics_visualizer.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timedelta
import logging
from scipy import stats
from sklearn.metrics import confusion_matrix
import warnings
warnings.filterwarnings('ignore')

# 设置中文字体和论文级样式
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
plt.style.use('seaborn-v0_8-whitegrid')

# 定义统计图表的颜色方案
STAT_COLORS = {
    'success': '#27ae60',       # 成功绿色
    'failure': '#e74c3c',       # 失败红色
    'warning': '#f39c12',       # 警告橙色
    'info': '#3498db',          # 信息蓝色
    'primary': '#2c3e50',       # 主要深色
    'secondary': '#95a5a6',     # 辅助灰色
    'accent': '#9b59b6',        # 强调紫色
    'background': '#ecf0f1',    # 背景色
}


class StatisticsVisualizer:
    """统计分析和成功率可视化工具"""

    def __init__(self, output_dir: str = "output/statistics_visualizations", dpi: int = 300):
        """
        初始化统计可视化器

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
            'title': 14,
            'label': 12,
            'tick': 10,
            'legend': 11,
            'annotation': 10
        }

        self.logger.info("统计可视化器初始化完成")

    def plot_workflow_success_rates(
        self,
        workflow_results: Dict[str, Dict[str, Any]],
        save_path: str = None
    ) -> str:
        """
        绘制工作流成功率统计图

        Args:
            workflow_results: 工作流结果，格式：{'workflow_id': {'success_rate': 0.85, 'total_tasks': 10, ...}}
            save_path: 保存路径

        Returns:
            str: 保存的图片路径
        """
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        workflows = list(workflow_results.keys())
        success_rates = [workflow_results[wf]['success_rate'] for wf in workflows]
        total_tasks = [workflow_results[wf]['total_tasks'] for wf in workflows]
        execution_times = [workflow_results[wf].get('execution_time', 0) for wf in workflows]

        # 1. 成功率柱状图
        ax1 = axes[0, 0]
        bars1 = ax1.bar(workflows, success_rates, color=STAT_COLORS['success'], alpha=0.7,
                       edgecolor='black', linewidth=0.5)

        # 添加数值标签
        for i, bar in enumerate(bars1):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height + 0.01,
                    f'{height:.1%}', ha='center', va='bottom',
                    fontsize=self.font_sizes['annotation'])

        ax1.set_ylabel('Success Rate', fontsize=self.font_sizes['label'])
        ax1.set_title('Workflow Success Rates', fontsize=self.font_sizes['title'], fontweight='bold')
        ax1.set_ylim(0, 1.1)
        ax1.grid(True, alpha=0.3, axis='y')
        plt.setp(ax1.get_xticklabels(), rotation=45, ha='right')

        # 2. 任务数量分布
        ax2 = axes[0, 1]
        ax2.hist(total_tasks, bins=min(10, len(set(total_tasks))), color=STAT_COLORS['info'],
                alpha=0.7, edgecolor='black', linewidth=0.5)
        ax2.set_xlabel('Number of Tasks', fontsize=self.font_sizes['label'])
        ax2.set_ylabel('Frequency', fontsize=self.font_sizes['label'])
        ax2.set_title('Task Count Distribution', fontsize=self.font_sizes['title'], fontweight='bold')
        ax2.grid(True, alpha=0.3)

        # 3. 成功率 vs 任务数量散点图
        ax3 = axes[1, 0]
        scatter = ax3.scatter(total_tasks, success_rates, c=execution_times, cmap='viridis',
                             s=100, alpha=0.7, edgecolors='black', linewidth=0.5)

        # 添加颜色条
        cbar = plt.colorbar(scatter, ax=ax3)
        cbar.set_label('Execution Time (s)', fontsize=self.font_sizes['label'])

        ax3.set_xlabel('Number of Tasks', fontsize=self.font_sizes['label'])
        ax3.set_ylabel('Success Rate', fontsize=self.font_sizes['label'])
        ax3.set_title('Success Rate vs Task Complexity', fontsize=self.font_sizes['title'], fontweight='bold')
        ax3.grid(True, alpha=0.3)

        # 4. 执行时间箱线图
        ax4 = axes[1, 1]
        # 按成功率分组
        high_success = []
        medium_success = []
        low_success = []

        for i, sr in enumerate(success_rates):
            if sr >= 0.8:
                high_success.append(execution_times[i])
            elif sr >= 0.5:
                medium_success.append(execution_times[i])
            else:
                low_success.append(execution_times[i])

        box_data = []
        box_labels = []
        if high_success:
            box_data.append(high_success)
            box_labels.append('High (≥80%)')
        if medium_success:
            box_data.append(medium_success)
            box_labels.append('Medium (50-80%)')
        if low_success:
            box_data.append(low_success)
            box_labels.append('Low (<50%)')

        if box_data:
            box_plot = ax4.boxplot(box_data, labels=box_labels, patch_artist=True)
            colors = [STAT_COLORS['success'], STAT_COLORS['warning'], STAT_COLORS['failure']]
            for patch, color in zip(box_plot['boxes'], colors[:len(box_data)]):
                patch.set_facecolor(color)
                patch.set_alpha(0.7)

        ax4.set_xlabel('Success Rate Category', fontsize=self.font_sizes['label'])
        ax4.set_ylabel('Execution Time (s)', fontsize=self.font_sizes['label'])
        ax4.set_title('Execution Time by Success Category', fontsize=self.font_sizes['title'], fontweight='bold')
        ax4.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()

        # 保存图片
        if save_path is None:
            save_path = self.output_dir / "workflow_success_analysis.png"

        plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight', facecolor='white')
        plt.close()

        self.logger.info(f"工作流成功率分析图已保存: {save_path}")
        return str(save_path)

    def plot_task_performance_matrix(
        self,
        task_results: Dict[str, Dict[str, Any]],
        task_types: List[str] = None,
        save_path: str = None
    ) -> str:
        """
        绘制任务性能矩阵图

        Args:
            task_results: 任务结果，格式：{'task_id': {'type': 'calibrate', 'success': True, 'time': 120, ...}}
            task_types: 任务类型列表
            save_path: 保存路径

        Returns:
            str: 保存的图片路径
        """
        # 准备数据
        df_data = []
        for task_id, result in task_results.items():
            df_data.append({
                'task_id': task_id,
                'task_type': result.get('type', 'unknown'),
                'success': result.get('success', False),
                'execution_time': result.get('time', 0),
                'error_type': result.get('error_type', 'none' if result.get('success', False) else 'unknown')
            })

        df = pd.DataFrame(df_data)

        if task_types is None:
            task_types = df['task_type'].unique().tolist()

        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        # 1. 任务类型成功率热力图
        ax1 = axes[0, 0]
        success_matrix = df.groupby('task_type')['success'].agg(['mean', 'count']).reset_index()
        success_matrix.columns = ['task_type', 'success_rate', 'count']

        # 创建矩阵数据用于热力图
        matrix_data = success_matrix.pivot_table(index='task_type', values=['success_rate'], fill_value=0)

        sns.heatmap(matrix_data, annot=True, cmap='RdYlGn', center=0.5,
                   square=True, linewidths=.5, cbar_kws={"shrink": .8}, ax=ax1,
                   fmt='.2f', annot_kws={'fontsize': self.font_sizes['annotation']})
        ax1.set_title('Task Type Success Rate Matrix', fontsize=self.font_sizes['title'], fontweight='bold')

        # 2. 执行时间分布
        ax2 = axes[0, 1]
        success_times = df[df['success'] == True]['execution_time']
        failure_times = df[df['success'] == False]['execution_time']

        ax2.hist([success_times, failure_times], bins=20, alpha=0.7,
                label=['Successful', 'Failed'], color=[STAT_COLORS['success'], STAT_COLORS['failure']],
                edgecolor='black', linewidth=0.5)

        ax2.set_xlabel('Execution Time (s)', fontsize=self.font_sizes['label'])
        ax2.set_ylabel('Frequency', fontsize=self.font_sizes['label'])
        ax2.set_title('Execution Time Distribution', fontsize=self.font_sizes['title'], fontweight='bold')
        ax2.legend(fontsize=self.font_sizes['legend'])
        ax2.grid(True, alpha=0.3)

        # 3. 错误类型分布饼图
        ax3 = axes[1, 0]
        error_counts = df['error_type'].value_counts()

        colors = [STAT_COLORS['success'] if error == 'none' else STAT_COLORS['failure']
                 for error in error_counts.index]

        wedges, texts, autotexts = ax3.pie(error_counts.values, labels=error_counts.index,
                                          autopct='%1.1f%%', startangle=90, colors=colors)

        ax3.set_title('Error Type Distribution', fontsize=self.font_sizes['title'], fontweight='bold')

        # 美化饼图
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
            autotext.set_fontsize(self.font_sizes['annotation'])

        # 4. 任务类型性能对比雷达图
        ax4 = axes[1, 1]

        # 计算每种任务类型的性能指标
        performance_metrics = {}
        for task_type in task_types:
            type_data = df[df['task_type'] == task_type]
            if len(type_data) > 0:
                performance_metrics[task_type] = {
                    'success_rate': type_data['success'].mean(),
                    'avg_time': type_data['execution_time'].mean(),
                    'reliability': 1 - type_data['execution_time'].std() / (type_data['execution_time'].mean() + 1e-6)
                }

        if performance_metrics:
            # 准备雷达图数据
            metrics_names = ['Success Rate', 'Speed (1/Time)', 'Reliability']

            # 转换数据到0-1范围
            max_time = max([m['avg_time'] for m in performance_metrics.values()]) + 1e-6

            for i, (task_type, metrics) in enumerate(performance_metrics.items()):
                values = [
                    metrics['success_rate'],
                    1 - (metrics['avg_time'] / max_time),  # 时间越短越好，所以用1减去归一化时间
                    max(0, metrics['reliability'])  # 确保reliability不为负
                ]

                # 角度计算
                angles = np.linspace(0, 2 * np.pi, len(metrics_names), endpoint=False).tolist()
                values += values[:1]  # 闭合多边形
                angles += angles[:1]

                color = plt.cm.Set1(i / len(performance_metrics))
                ax4.plot(angles, values, 'o-', linewidth=2, label=task_type, color=color)
                ax4.fill(angles, values, alpha=0.25, color=color)

            ax4.set_xticks(angles[:-1])
            ax4.set_xticklabels(metrics_names)
            ax4.set_ylim(0, 1)
            ax4.set_title('Task Type Performance Radar', fontsize=self.font_sizes['title'], fontweight='bold')
            ax4.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0))
            ax4.grid(True)

        plt.tight_layout()

        # 保存图片
        if save_path is None:
            save_path = self.output_dir / "task_performance_matrix.png"

        plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight', facecolor='white')
        plt.close()

        self.logger.info(f"任务性能矩阵图已保存: {save_path}")
        return str(save_path)

    def plot_system_reliability_analysis(
        self,
        execution_history: List[Dict[str, Any]],
        time_window_hours: int = 24,
        save_path: str = None
    ) -> str:
        """
        绘制系统可靠性分析图

        Args:
            execution_history: 执行历史记录
            time_window_hours: 时间窗口（小时）
            save_path: 保存路径

        Returns:
            str: 保存的图片路径
        """
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        # 转换为DataFrame
        df = pd.DataFrame(execution_history)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')

        # 1. 时间序列成功率
        ax1 = axes[0, 0]

        # 计算滑动窗口成功率
        df['success_numeric'] = df['success'].astype(int)
        window_size = max(10, len(df) // 20)  # 自适应窗口大小
        df['rolling_success_rate'] = df['success_numeric'].rolling(window=window_size, min_periods=1).mean()

        ax1.plot(df['timestamp'], df['rolling_success_rate'], color=STAT_COLORS['primary'],
                linewidth=2, label=f'Success Rate (Window={window_size})')

        # 添加成功/失败事件点
        success_points = df[df['success'] == True]
        failure_points = df[df['success'] == False]

        ax1.scatter(success_points['timestamp'], [1.05] * len(success_points),
                   color=STAT_COLORS['success'], alpha=0.6, s=20, marker='^', label='Success')
        ax1.scatter(failure_points['timestamp'], [-0.05] * len(failure_points),
                   color=STAT_COLORS['failure'], alpha=0.6, s=20, marker='v', label='Failure')

        ax1.set_ylabel('Success Rate', fontsize=self.font_sizes['label'])
        ax1.set_title('System Reliability Over Time', fontsize=self.font_sizes['title'], fontweight='bold')
        ax1.legend(fontsize=self.font_sizes['legend'])
        ax1.grid(True, alpha=0.3)
        ax1.set_ylim(-0.1, 1.15)

        # 2. 故障间隔时间分析
        ax2 = axes[0, 1]

        failure_times = df[df['success'] == False]['timestamp']
        if len(failure_times) > 1:
            time_between_failures = []
            for i in range(1, len(failure_times)):
                time_diff = (failure_times.iloc[i] - failure_times.iloc[i-1]).total_seconds() / 3600  # 转换为小时
                time_between_failures.append(time_diff)

            if time_between_failures:
                ax2.hist(time_between_failures, bins=20, color=STAT_COLORS['warning'],
                        alpha=0.7, edgecolor='black', linewidth=0.5)
                ax2.axvline(np.mean(time_between_failures), color='red', linestyle='--',
                           label=f'Mean: {np.mean(time_between_failures):.1f}h')
                ax2.legend()

        ax2.set_xlabel('Time Between Failures (hours)', fontsize=self.font_sizes['label'])
        ax2.set_ylabel('Frequency', fontsize=self.font_sizes['label'])
        ax2.set_title('Mean Time Between Failures', fontsize=self.font_sizes['title'], fontweight='bold')
        ax2.grid(True, alpha=0.3)

        # 3. 每小时执行量和成功率
        ax3 = axes[1, 0]

        df['hour'] = df['timestamp'].dt.hour
        hourly_stats = df.groupby('hour').agg({
            'success_numeric': ['sum', 'count', 'mean']
        }).round(3)

        hourly_stats.columns = ['successful_executions', 'total_executions', 'success_rate']
        hours = hourly_stats.index

        # 双轴图
        ax3_twin = ax3.twinx()

        bars = ax3.bar(hours, hourly_stats['total_executions'], alpha=0.6,
                      color=STAT_COLORS['info'], label='Total Executions')
        line = ax3_twin.plot(hours, hourly_stats['success_rate'], color=STAT_COLORS['success'],
                           marker='o', linewidth=2, label='Success Rate')

        ax3.set_xlabel('Hour of Day', fontsize=self.font_sizes['label'])
        ax3.set_ylabel('Number of Executions', fontsize=self.font_sizes['label'])
        ax3_twin.set_ylabel('Success Rate', fontsize=self.font_sizes['label'])
        ax3.set_title('Hourly System Activity', fontsize=self.font_sizes['title'], fontweight='bold')

        # 合并图例
        lines1, labels1 = ax3.get_legend_handles_labels()
        lines2, labels2 = ax3_twin.get_legend_handles_labels()
        ax3.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

        ax3.grid(True, alpha=0.3)

        # 4. 系统负载 vs 成功率
        ax4 = axes[1, 1]

        # 计算系统负载（每小时执行数）
        df['load_level'] = pd.cut(df.groupby(df['timestamp'].dt.floor('H'))['timestamp'].transform('count'),
                                 bins=3, labels=['Low', 'Medium', 'High'])

        load_success = df.groupby('load_level')['success_numeric'].agg(['mean', 'count']).reset_index()
        load_success.columns = ['load_level', 'success_rate', 'count']

        bars = ax4.bar(load_success['load_level'], load_success['success_rate'],
                      color=[STAT_COLORS['success'], STAT_COLORS['warning'], STAT_COLORS['failure']],
                      alpha=0.7, edgecolor='black', linewidth=0.5)

        # 添加数值标签
        for i, bar in enumerate(bars):
            height = bar.get_height()
            count = load_success.iloc[i]['count']
            ax4.text(bar.get_x() + bar.get_width()/2., height + 0.01,
                    f'{height:.2%}\n(n={count})', ha='center', va='bottom',
                    fontsize=self.font_sizes['annotation'])

        ax4.set_xlabel('System Load Level', fontsize=self.font_sizes['label'])
        ax4.set_ylabel('Success Rate', fontsize=self.font_sizes['label'])
        ax4.set_title('Success Rate vs System Load', fontsize=self.font_sizes['title'], fontweight='bold')
        ax4.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()

        # 保存图片
        if save_path is None:
            save_path = self.output_dir / "system_reliability_analysis.png"

        plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight', facecolor='white')
        plt.close()

        self.logger.info(f"系统可靠性分析图已保存: {save_path}")
        return str(save_path)

    def plot_comparative_analysis(
        self,
        comparison_data: Dict[str, Dict[str, Any]],
        comparison_type: str = "models",
        save_path: str = None
    ) -> str:
        """
        绘制对比分析图

        Args:
            comparison_data: 对比数据
            comparison_type: 对比类型（models/algorithms/systems）
            save_path: 保存路径

        Returns:
            str: 保存的图片路径
        """
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        names = list(comparison_data.keys())
        n_items = len(names)

        # 准备数据
        metrics = ['accuracy', 'efficiency', 'reliability', 'robustness']
        data_matrix = []

        for name in names:
            item_data = comparison_data[name]
            row = []
            for metric in metrics:
                row.append(item_data.get(metric, 0))
            data_matrix.append(row)

        data_matrix = np.array(data_matrix)

        # 1. 雷达图对比
        ax1 = axes[0, 0]
        angles = np.linspace(0, 2 * np.pi, len(metrics), endpoint=False).tolist()
        angles += angles[:1]

        colors = plt.cm.Set1(np.linspace(0, 1, n_items))

        for i, name in enumerate(names):
            values = data_matrix[i].tolist()
            values += values[:1]

            ax1.plot(angles, values, 'o-', linewidth=2, label=name, color=colors[i])
            ax1.fill(angles, values, alpha=0.25, color=colors[i])

        ax1.set_xticks(angles[:-1])
        ax1.set_xticklabels([m.capitalize() for m in metrics])
        ax1.set_ylim(0, 1)
        ax1.set_title(f'{comparison_type.capitalize()} Performance Radar',
                     fontsize=self.font_sizes['title'], fontweight='bold')
        ax1.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0))
        ax1.grid(True)

        # 2. 性能指标热力图
        ax2 = axes[0, 1]
        sns.heatmap(data_matrix, xticklabels=[m.capitalize() for m in metrics],
                   yticklabels=names, annot=True, cmap='RdYlGn', center=0.5,
                   square=True, linewidths=.5, cbar_kws={"shrink": .8}, ax=ax2,
                   fmt='.3f', annot_kws={'fontsize': self.font_sizes['annotation']})
        ax2.set_title(f'{comparison_type.capitalize()} Performance Heatmap',
                     fontsize=self.font_sizes['title'], fontweight='bold')

        # 3. 综合得分排名
        ax3 = axes[1, 0]
        overall_scores = data_matrix.mean(axis=1)
        sorted_indices = np.argsort(overall_scores)[::-1]
        sorted_names = [names[i] for i in sorted_indices]
        sorted_scores = [overall_scores[i] for i in sorted_indices]

        bars = ax3.barh(sorted_names, sorted_scores, color=colors[sorted_indices],
                       alpha=0.7, edgecolor='black', linewidth=0.5)

        # 添加数值标签
        for i, bar in enumerate(bars):
            width = bar.get_width()
            ax3.text(width + 0.01, bar.get_y() + bar.get_height()/2.,
                    f'{width:.3f}', ha='left', va='center',
                    fontsize=self.font_sizes['annotation'])

        ax3.set_xlabel('Overall Score', fontsize=self.font_sizes['label'])
        ax3.set_title(f'{comparison_type.capitalize()} Overall Ranking',
                     fontsize=self.font_sizes['title'], fontweight='bold')
        ax3.grid(True, alpha=0.3, axis='x')

        # 4. 详细指标对比柱状图
        ax4 = axes[1, 1]
        x = np.arange(len(names))
        width = 0.8 / len(metrics)

        for i, metric in enumerate(metrics):
            offset = (i - len(metrics)/2 + 0.5) * width
            bars = ax4.bar(x + offset, data_matrix[:, i], width,
                          label=metric.capitalize(), alpha=0.7)

        ax4.set_xlabel(comparison_type.capitalize(), fontsize=self.font_sizes['label'])
        ax4.set_ylabel('Score', fontsize=self.font_sizes['label'])
        ax4.set_title(f'Detailed {comparison_type.capitalize()} Comparison',
                     fontsize=self.font_sizes['title'], fontweight='bold')
        ax4.set_xticks(x)
        ax4.set_xticklabels(names, rotation=45, ha='right')
        ax4.legend(fontsize=self.font_sizes['legend'])
        ax4.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()

        # 保存图片
        if save_path is None:
            save_path = self.output_dir / f"{comparison_type}_comparative_analysis.png"

        plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight', facecolor='white')
        plt.close()

        self.logger.info(f"{comparison_type}对比分析图已保存: {save_path}")
        return str(save_path)

    def generate_comprehensive_report(
        self,
        report_data: Dict[str, Any],
        report_title: str = "HydroAgent Performance Analysis",
        save_path: str = None
    ) -> str:
        """
        生成综合性能分析报告

        Args:
            report_data: 报告数据
            report_title: 报告标题
            save_path: 保存路径

        Returns:
            str: 报告路径
        """
        charts = {}

        # 生成各类图表
        if 'workflow_results' in report_data:
            charts['workflow_success'] = self.plot_workflow_success_rates(
                report_data['workflow_results']
            )

        if 'task_results' in report_data:
            charts['task_performance'] = self.plot_task_performance_matrix(
                report_data['task_results'],
                report_data.get('task_types')
            )

        if 'execution_history' in report_data:
            charts['system_reliability'] = self.plot_system_reliability_analysis(
                report_data['execution_history']
            )

        if 'comparison_data' in report_data:
            charts['comparative_analysis'] = self.plot_comparative_analysis(
                report_data['comparison_data'],
                report_data.get('comparison_type', 'models')
            )

        # 生成HTML报告
        if save_path is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            save_path = self.output_dir / f"comprehensive_report_{timestamp}.html"

        html_content = self._generate_comprehensive_report_html(
            report_data, charts, report_title
        )

        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        self.logger.info(f"综合分析报告已生成: {save_path}")
        return str(save_path)

    def _generate_comprehensive_report_html(
        self,
        data: Dict[str, Any],
        charts: Dict[str, str],
        title: str
    ) -> str:
        """生成综合报告HTML"""
        html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6; color: #333; background: #f8f9fa;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        .header {{
            text-align: center; margin-bottom: 40px; padding: 30px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; border-radius: 15px; box-shadow: 0 8px 32px rgba(0,0,0,0.1);
        }}
        .header h1 {{ font-size: 2.5em; margin-bottom: 10px; }}
        .header p {{ font-size: 1.2em; opacity: 0.9; }}
        .summary-section {{
            background: white; padding: 30px; margin-bottom: 30px;
            border-radius: 10px; box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        }}
        .summary-grid {{
            display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px; margin-top: 20px;
        }}
        .summary-card {{
            background: linear-gradient(135deg, #74b9ff 0%, #0984e3 100%);
            color: white; padding: 25px; border-radius: 12px; text-align: center;
            transform: translateY(0); transition: transform 0.3s ease;
        }}
        .summary-card:hover {{ transform: translateY(-5px); }}
        .metric-value {{ font-size: 2.2em; font-weight: bold; margin-bottom: 5px; }}
        .metric-label {{ font-size: 1em; opacity: 0.9; }}
        .chart-section {{
            background: white; padding: 30px; margin-bottom: 30px;
            border-radius: 10px; box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        }}
        .chart-section h2 {{
            color: #2d3436; margin-bottom: 20px; padding-bottom: 10px;
            border-bottom: 3px solid #74b9ff; font-size: 1.8em;
        }}
        .chart-grid {{
            display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 30px;
        }}
        .chart-item {{
            text-align: center; padding: 20px; background: #f8f9fa;
            border-radius: 10px; border: 1px solid #e9ecef;
        }}
        .chart-item img {{
            max-width: 100%; height: auto; border-radius: 8px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }}
        .chart-title {{
            font-size: 1.3em; font-weight: 600; margin-bottom: 15px; color: #2d3436;
        }}
        .footer {{
            text-align: center; margin-top: 40px; padding: 20px;
            background: #2d3436; color: white; border-radius: 10px;
        }}
        .highlight {{ background: #fff3cd; padding: 15px; border-radius: 8px; margin: 15px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{title}</h1>
            <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>

        <div class="summary-section">
            <h2>Executive Summary</h2>
            <div class="summary-grid">
        """

        # 添加关键指标
        if 'total_workflows' in data:
            html += f"""
                <div class="summary-card">
                    <div class="metric-value">{data['total_workflows']}</div>
                    <div class="metric-label">Total Workflows</div>
                </div>
            """

        if 'overall_success_rate' in data:
            html += f"""
                <div class="summary-card">
                    <div class="metric-value">{data['overall_success_rate']:.1%}</div>
                    <div class="metric-label">Overall Success Rate</div>
                </div>
            """

        if 'avg_execution_time' in data:
            html += f"""
                <div class="summary-card">
                    <div class="metric-value">{data['avg_execution_time']:.1f}s</div>
                    <div class="metric-label">Average Execution Time</div>
                </div>
            """

        if 'system_uptime' in data:
            html += f"""
                <div class="summary-card">
                    <div class="metric-value">{data['system_uptime']:.1%}</div>
                    <div class="metric-label">System Uptime</div>
                </div>
            """

        html += """
            </div>
            <div class="highlight">
                <strong>Key Insights:</strong>
                This report provides comprehensive analysis of the HydroAgent system performance,
                including workflow success rates, task performance metrics, and system reliability statistics.
            </div>
        </div>
        """

        # 添加图表部分
        html += """
        <div class="chart-section">
            <h2>Performance Analysis Charts</h2>
            <div class="chart-grid">
        """

        chart_titles = {
            'workflow_success': 'Workflow Success Analysis',
            'task_performance': 'Task Performance Matrix',
            'system_reliability': 'System Reliability Analysis',
            'comparative_analysis': 'Comparative Analysis'
        }

        for chart_key, chart_path in charts.items():
            if chart_path:
                title = chart_titles.get(chart_key, chart_key.title())
                chart_filename = Path(chart_path).name
                html += f"""
                <div class="chart-item">
                    <div class="chart-title">{title}</div>
                    <img src="{chart_filename}" alt="{title}">
                </div>
                """

        html += """
            </div>
        </div>

        <div class="footer">
            <p>This report was automatically generated by the HydroAgent Statistics Visualizer.</p>
            <p>All charts are publication-ready and optimized for academic use.</p>
        </div>
    </div>
</body>
</html>
        """

        return html