"""
Author: Claude
Date: 2025-01-27 10:30:00
LastEditTime: 2025-01-27 10:30:00
LastEditors: Claude
Description: Generic plotting utilities for HydroAgent
             通用绘图工具，供DeveloperAgent调用
FilePath: /HydroAgent/hydroagent/utils/plotting.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging

logger = logging.getLogger(__name__)


class PlottingToolkit:
    """
    通用绘图工具集

    设计原则：
    1. 提供通用的绘图函数，而非针对特定实验
    2. 由DeveloperAgent的LLM决定调用哪些函数
    3. 每个函数只做一件事，保持简单
    """

    @staticmethod
    def plot_time_series(
        data: Dict[str, List[float]],
        x_label: str,
        y_label: str,
        title: str,
        output_path: Path,
        show_stats: bool = True,
        **kwargs
    ) -> bool:
        """
        绘制时间序列图（通用）

        Args:
            data: 数据字典 {"series_name": [values], ...}
            x_label: X轴标签
            y_label: Y轴标签
            title: 图表标题
            output_path: 输出路径
            show_stats: 是否显示统计信息（均值、标准差）
            **kwargs: 其他matplotlib参数

        Returns:
            是否成功
        """
        try:
            import matplotlib.pyplot as plt
            import matplotlib
            matplotlib.use('Agg')
            import numpy as np

            plt.figure(figsize=kwargs.get('figsize', (12, 6)))

            colors = kwargs.get('colors', ['#2E86AB', '#A23B72', '#F18F01', '#6A994E'])

            for i, (name, values) in enumerate(data.items()):
                color = colors[i % len(colors)]
                x = kwargs.get('x_values', list(range(1, len(values) + 1)))

                plt.plot(x, values, marker='o', linestyle='-', linewidth=2,
                        markersize=8, label=name, color=color)

                # 显示统计信息
                if show_stats:
                    mean_val = np.mean(values)
                    std_val = np.std(values)

                    plt.axhline(y=mean_val, color=color, linestyle='--',
                               linewidth=1.5, alpha=0.6,
                               label=f'{name} Mean: {mean_val:.3f}')

                    if kwargs.get('show_std', True):
                        plt.fill_between(x,
                                        mean_val - std_val,
                                        mean_val + std_val,
                                        alpha=0.15, color=color)

            plt.xlabel(x_label, fontsize=14, fontweight='bold')
            plt.ylabel(y_label, fontsize=14, fontweight='bold')
            plt.title(title, fontsize=16, fontweight='bold')
            plt.grid(True, alpha=0.3, linestyle='--')
            plt.legend(fontsize=12, loc='best')
            plt.tight_layout()

            plt.savefig(output_path, dpi=kwargs.get('dpi', 300), bbox_inches='tight')
            plt.close()

            logger.info(f"[PlottingToolkit] 时间序列图已保存: {output_path}")
            return True

        except ImportError:
            logger.warning("[PlottingToolkit] matplotlib未安装，无法绘图")
            return False
        except Exception as e:
            logger.error(f"[PlottingToolkit] 绘图失败: {str(e)}", exc_info=True)
            return False

    @staticmethod
    def plot_boxplot(
        data: Dict[str, List[float]],
        x_label: str,
        y_label: str,
        title: str,
        output_path: Path,
        **kwargs
    ) -> bool:
        """
        绘制箱线图（通用）

        Args:
            data: 数据字典 {"param_name": [values], ...}
            x_label: X轴标签
            y_label: Y轴标签
            title: 图表标题
            output_path: 输出路径
            **kwargs: 其他参数

        Returns:
            是否成功
        """
        try:
            import matplotlib.pyplot as plt
            import matplotlib
            matplotlib.use('Agg')

            labels = list(data.keys())
            values = [data[label] for label in labels]

            fig, ax = plt.subplots(figsize=kwargs.get('figsize', (max(10, len(labels)*1.5), 6)))

            bp = ax.boxplot(values, labels=labels, patch_artist=True,
                           notch=True, showmeans=True)

            # 美化
            box_color = kwargs.get('box_color', '#6A994E')
            for patch in bp['boxes']:
                patch.set_facecolor(box_color)
                patch.set_alpha(0.7)

            for whisker in bp['whiskers']:
                whisker.set(linewidth=1.5, color='#386641')

            for cap in bp['caps']:
                cap.set(linewidth=1.5, color='#386641')

            for median in bp['medians']:
                median.set(linewidth=2, color='#BC4749')

            for mean in bp['means']:
                mean.set(marker='D', markerfacecolor='#F2CC8F', markeredgecolor='#81B29A')

            ax.set_xlabel(x_label, fontsize=14, fontweight='bold')
            ax.set_ylabel(y_label, fontsize=14, fontweight='bold')
            ax.set_title(title, fontsize=16, fontweight='bold')
            ax.grid(True, alpha=0.3, linestyle='--', axis='y')

            if kwargs.get('rotate_labels', True):
                plt.xticks(rotation=45, ha='right')

            plt.tight_layout()
            plt.savefig(output_path, dpi=kwargs.get('dpi', 300), bbox_inches='tight')
            plt.close()

            logger.info(f"[PlottingToolkit] 箱线图已保存: {output_path}")
            return True

        except ImportError:
            logger.warning("[PlottingToolkit] matplotlib未安装")
            return False
        except Exception as e:
            logger.error(f"[PlottingToolkit] 绘图失败: {str(e)}", exc_info=True)
            return False

    @staticmethod
    def plot_histogram(
        data: List[float],
        x_label: str,
        y_label: str,
        title: str,
        output_path: Path,
        bins: int = 30,
        **kwargs
    ) -> bool:
        """
        绘制直方图（通用）

        Args:
            data: 数据列表
            x_label: X轴标签
            y_label: Y轴标签
            title: 图表标题
            output_path: 输出路径
            bins: 柱子数量
            **kwargs: 其他参数

        Returns:
            是否成功
        """
        try:
            import matplotlib.pyplot as plt
            import matplotlib
            matplotlib.use('Agg')
            import numpy as np

            plt.figure(figsize=kwargs.get('figsize', (10, 6)))

            n, bins_edges, patches = plt.hist(data, bins=bins,
                                              color=kwargs.get('color', '#2E86AB'),
                                              alpha=0.7, edgecolor='black')

            # 添加统计线
            mean_val = np.mean(data)
            std_val = np.std(data)

            plt.axvline(mean_val, color='#A23B72', linestyle='--',
                       linewidth=2, label=f'Mean: {mean_val:.3f}')
            plt.axvline(mean_val + std_val, color='#F18F01', linestyle=':',
                       linewidth=1.5, label=f'Std: ±{std_val:.3f}')
            plt.axvline(mean_val - std_val, color='#F18F01', linestyle=':',
                       linewidth=1.5)

            plt.xlabel(x_label, fontsize=14, fontweight='bold')
            plt.ylabel(y_label, fontsize=14, fontweight='bold')
            plt.title(title, fontsize=16, fontweight='bold')
            plt.legend(fontsize=12)
            plt.grid(True, alpha=0.3, linestyle='--', axis='y')
            plt.tight_layout()

            plt.savefig(output_path, dpi=kwargs.get('dpi', 300), bbox_inches='tight')
            plt.close()

            logger.info(f"[PlottingToolkit] 直方图已保存: {output_path}")
            return True

        except ImportError:
            logger.warning("[PlottingToolkit] matplotlib未安装")
            return False
        except Exception as e:
            logger.error(f"[PlottingToolkit] 绘图失败: {str(e)}", exc_info=True)
            return False

    @staticmethod
    def plot_scatter(
        x_data: List[float],
        y_data: List[float],
        x_label: str,
        y_label: str,
        title: str,
        output_path: Path,
        add_1to1_line: bool = False,
        **kwargs
    ) -> bool:
        """
        绘制散点图（通用）

        Args:
            x_data: X轴数据
            y_data: Y轴数据
            x_label: X轴标签
            y_label: Y轴标签
            title: 图表标题
            output_path: 输出路径
            add_1to1_line: 是否添加1:1线
            **kwargs: 其他参数

        Returns:
            是否成功
        """
        try:
            import matplotlib.pyplot as plt
            import matplotlib
            matplotlib.use('Agg')
            import numpy as np

            plt.figure(figsize=kwargs.get('figsize', (8, 8)))

            plt.scatter(x_data, y_data,
                       color=kwargs.get('color', '#2E86AB'),
                       alpha=kwargs.get('alpha', 0.6),
                       s=kwargs.get('s', 50),
                       edgecolors='black',
                       linewidths=0.5)

            # 1:1线
            if add_1to1_line:
                min_val = min(min(x_data), min(y_data))
                max_val = max(max(x_data), max(y_data))
                plt.plot([min_val, max_val], [min_val, max_val],
                        'r--', linewidth=2, label='1:1 Line', alpha=0.7)

            # 拟合线
            if kwargs.get('add_fit_line', False):
                z = np.polyfit(x_data, y_data, 1)
                p = np.poly1d(z)
                plt.plot(x_data, p(x_data),
                        color='#A23B72', linewidth=2,
                        label=f'Fit: y={z[0]:.2f}x+{z[1]:.2f}')

            # 计算R²
            if kwargs.get('show_r2', True):
                from scipy import stats
                r_value = stats.pearsonr(x_data, y_data)[0]
                r2 = r_value ** 2
                plt.text(0.05, 0.95, f'R² = {r2:.3f}',
                        transform=plt.gca().transAxes,
                        fontsize=14, verticalalignment='top',
                        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

            plt.xlabel(x_label, fontsize=14, fontweight='bold')
            plt.ylabel(y_label, fontsize=14, fontweight='bold')
            plt.title(title, fontsize=16, fontweight='bold')
            plt.grid(True, alpha=0.3, linestyle='--')
            plt.legend(fontsize=12)
            plt.tight_layout()

            plt.savefig(output_path, dpi=kwargs.get('dpi', 300), bbox_inches='tight')
            plt.close()

            logger.info(f"[PlottingToolkit] 散点图已保存: {output_path}")
            return True

        except ImportError:
            logger.warning("[PlottingToolkit] matplotlib/scipy未安装")
            return False
        except Exception as e:
            logger.error(f"[PlottingToolkit] 绘图失败: {str(e)}", exc_info=True)
            return False

    @staticmethod
    def plot_heatmap(
        data: List[List[float]],
        x_labels: List[str],
        y_labels: List[str],
        title: str,
        output_path: Path,
        **kwargs
    ) -> bool:
        """
        绘制热力图（通用）

        Args:
            data: 2D数据
            x_labels: X轴标签列表
            y_labels: Y轴标签列表
            title: 图表标题
            output_path: 输出路径
            **kwargs: 其他参数

        Returns:
            是否成功
        """
        try:
            import matplotlib.pyplot as plt
            import matplotlib
            matplotlib.use('Agg')
            import numpy as np

            fig, ax = plt.subplots(figsize=kwargs.get('figsize', (10, 8)))

            im = ax.imshow(data, cmap=kwargs.get('cmap', 'RdYlGn'), aspect='auto')

            # 设置刻度
            ax.set_xticks(np.arange(len(x_labels)))
            ax.set_yticks(np.arange(len(y_labels)))
            ax.set_xticklabels(x_labels)
            ax.set_yticklabels(y_labels)

            # 旋转标签
            plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")

            # 添加颜色条
            cbar = plt.colorbar(im, ax=ax)
            cbar.ax.set_ylabel(kwargs.get('cbar_label', 'Value'), rotation=-90, va="bottom")

            # 添加数值
            if kwargs.get('show_values', True):
                for i in range(len(y_labels)):
                    for j in range(len(x_labels)):
                        text = ax.text(j, i, f'{data[i][j]:.2f}',
                                     ha="center", va="center", color="black", fontsize=9)

            ax.set_title(title, fontsize=16, fontweight='bold')
            plt.tight_layout()

            plt.savefig(output_path, dpi=kwargs.get('dpi', 300), bbox_inches='tight')
            plt.close()

            logger.info(f"[PlottingToolkit] 热力图已保存: {output_path}")
            return True

        except ImportError:
            logger.warning("[PlottingToolkit] matplotlib未安装")
            return False
        except Exception as e:
            logger.error(f"[PlottingToolkit] 绘图失败: {str(e)}", exc_info=True)
            return False

    @staticmethod
    def plot_metrics_comparison(
        basin_ids: List[str],
        nse_values: List[float],
        rmse_values: List[float],
        kge_values: List[float],
        output_path: Path,
        **kwargs
    ) -> bool:
        """
        绘制多指标对比柱状图（NSE, RMSE, KGE）

        Args:
            basin_ids: 流域ID列表
            nse_values: NSE值列表
            rmse_values: RMSE值列表
            kge_values: KGE值列表
            output_path: 输出路径
            **kwargs: 其他参数

        Returns:
            是否成功
        """
        try:
            import matplotlib.pyplot as plt
            import matplotlib
            matplotlib.use('Agg')
            import numpy as np

            fig, axes = plt.subplots(1, 3, figsize=kwargs.get('figsize', (18, 6)))

            # NSE柱状图
            axes[0].bar(range(len(basin_ids)), nse_values, color='skyblue', alpha=0.8)
            axes[0].set_xlabel('Basin ID', fontsize=12)
            axes[0].set_ylabel('NSE', fontsize=12)
            axes[0].set_title('Nash-Sutcliffe Efficiency (NSE)', fontsize=14, fontweight='bold')
            axes[0].set_xticks(range(len(basin_ids)))
            axes[0].set_xticklabels(basin_ids, rotation=45, ha='right')
            axes[0].grid(axis='y', alpha=0.3)

            # RMSE柱状图
            axes[1].bar(range(len(basin_ids)), rmse_values, color='lightcoral', alpha=0.8)
            axes[1].set_xlabel('Basin ID', fontsize=12)
            axes[1].set_ylabel('RMSE', fontsize=12)
            axes[1].set_title('Root Mean Square Error (RMSE)', fontsize=14, fontweight='bold')
            axes[1].set_xticks(range(len(basin_ids)))
            axes[1].set_xticklabels(basin_ids, rotation=45, ha='right')
            axes[1].grid(axis='y', alpha=0.3)

            # KGE柱状图
            axes[2].bar(range(len(basin_ids)), kge_values, color='lightgreen', alpha=0.8)
            axes[2].set_xlabel('Basin ID', fontsize=12)
            axes[2].set_ylabel('KGE', fontsize=12)
            axes[2].set_title('Kling-Gupta Efficiency (KGE)', fontsize=14, fontweight='bold')
            axes[2].set_xticks(range(len(basin_ids)))
            axes[2].set_xticklabels(basin_ids, rotation=45, ha='right')
            axes[2].grid(axis='y', alpha=0.3)

            plt.tight_layout()
            plt.savefig(output_path, dpi=kwargs.get('dpi', 300), bbox_inches='tight')
            plt.close()

            logger.info(f"[PlottingToolkit] 指标对比图已保存: {output_path}")
            return True

        except ImportError:
            logger.warning("[PlottingToolkit] matplotlib未安装")
            return False
        except Exception as e:
            logger.error(f"[PlottingToolkit] 绘图失败: {str(e)}", exc_info=True)
            return False


# 便捷函数别名
plot_line = PlottingToolkit.plot_time_series
plot_box = PlottingToolkit.plot_boxplot
plot_hist = PlottingToolkit.plot_histogram
