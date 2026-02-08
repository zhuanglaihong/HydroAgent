"""
Author: Claude
Date: 2025-12-30 17:30:00
LastEditTime: 2025-12-30 17:30:00
LastEditors: Claude
Description: Specialized plotting utilities for iterative calibration
             为迭代率定提供专用的可视化功能
FilePath: /HydroAgent/hydroagent/utils/iterative_plotting.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any
import logging
import json

logger = logging.getLogger(__name__)


def _configure_matplotlib_for_english():
    """
    Configure matplotlib to use English fonts only.
    配置matplotlib使用英文字体，避免中文显示问题。
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib

        # Use non-interactive backend
        matplotlib.use("Agg")

        # Configure to use standard English fonts
        plt.rcParams['font.family'] = 'DejaVu Sans'
        plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']
        plt.rcParams['axes.unicode_minus'] = False  # Fix minus sign display

        logger.debug("[IterativePlotting] Matplotlib configured for English fonts")
    except Exception as e:
        logger.warning(f"[IterativePlotting] Failed to configure matplotlib: {str(e)}")


def plot_nse_evolution(
    iteration_dirs: List[Path],
    output_path: Path,
    target_nse: Optional[float] = None,
) -> bool:
    """
    Plot NSE evolution across iterations.
    绘制NSE随迭代次数的变化曲线。

    Args:
        iteration_dirs: List of iteration directories (sorted)
        output_path: Output file path
        target_nse: Target NSE threshold (optional, draws horizontal line)

    Returns:
        Success status
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib
        matplotlib.use("Agg")
        import numpy as np

        _configure_matplotlib_for_english()

        # Extract NSE values from each iteration
        nse_values = []
        iteration_numbers = []

        for iter_dir in iteration_dirs:
            # Extract iteration number from directory name (e.g., "iteration_1" -> 1)
            iter_num = int(iter_dir.name.split('_')[1])
            iteration_numbers.append(iter_num)

            # Read NSE from basins_metrics.csv
            metrics_file = iter_dir / "basins_metrics.csv"
            if metrics_file.exists():
                with open(metrics_file, 'r') as f:
                    lines = f.readlines()
                    if len(lines) > 1:
                        header = lines[0].strip().split(',')
                        values = lines[1].strip().split(',')
                        if 'NSE' in header:
                            nse_idx = header.index('NSE')
                            nse = float(values[nse_idx])
                            nse_values.append(nse)
                        else:
                            nse_values.append(None)
                    else:
                        nse_values.append(None)
            else:
                nse_values.append(None)

        # Remove None values
        valid_data = [(n, v) for n, v in zip(iteration_numbers, nse_values) if v is not None]
        if not valid_data:
            logger.warning("[IterativePlotting] No valid NSE data found")
            return False

        iteration_numbers, nse_values = zip(*valid_data)

        # Create plot
        fig, ax = plt.subplots(figsize=(10, 6))

        # Plot NSE evolution
        ax.plot(
            iteration_numbers,
            nse_values,
            marker='o',
            linestyle='-',
            linewidth=2.5,
            markersize=10,
            color='#2E86AB',
            label='NSE',
            markerfacecolor='white',
            markeredgewidth=2,
            markeredgecolor='#2E86AB'
        )

        # Add value labels on points
        for i, (iter_num, nse) in enumerate(zip(iteration_numbers, nse_values)):
            ax.text(
                iter_num,
                nse,
                f'{nse:.4f}',
                ha='center',
                va='bottom',
                fontsize=9,
                fontweight='bold'
            )

        # Add target NSE line if provided
        if target_nse is not None:
            ax.axhline(
                y=target_nse,
                color='#BC4749',
                linestyle='--',
                linewidth=2,
                label=f'Target NSE = {target_nse}',
                alpha=0.7
            )

        # Find best NSE
        best_nse = max(nse_values)
        best_iter = iteration_numbers[nse_values.index(best_nse)]
        ax.scatter(
            [best_iter],
            [best_nse],
            s=300,
            color='#F18F01',
            marker='*',
            edgecolors='black',
            linewidths=1.5,
            label=f'Best NSE = {best_nse:.4f} (Iter {best_iter})',
            zorder=5
        )

        # Styling
        ax.set_xlabel('Iteration Number', fontsize=14, fontweight='bold')
        ax.set_ylabel('NSE', fontsize=14, fontweight='bold')
        ax.set_title('NSE Evolution Across Iterations', fontsize=16, fontweight='bold')
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.legend(fontsize=11, loc='best')

        # Set x-axis to show integer iteration numbers
        ax.set_xticks(iteration_numbers)

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()

        logger.info(f"[IterativePlotting] NSE evolution plot saved: {output_path}")
        return True

    except ImportError:
        logger.warning("[IterativePlotting] matplotlib not installed")
        return False
    except Exception as e:
        logger.error(f"[IterativePlotting] Failed to plot NSE evolution: {str(e)}", exc_info=True)
        return False


def plot_parameter_evolution(
    iteration_dirs: List[Path],
    model_name: str,
    output_path: Path,
    max_params_per_plot: int = 8,
) -> bool:
    """
    Plot best parameter values evolution across iterations (normalized).
    绘制最佳参数值随迭代次数的演化（归一化版本）。

    Strategy:
    - Show ONLY best parameter values (not ranges) for clarity
    - Normalize all parameters to [0, 1] using their ranges
    - Use single plot for ≤8 params, multiple subplots for >8 params
    - Simple line plot with markers for easy interpretation

    Args:
        iteration_dirs: List of iteration directories (sorted)
        model_name: Model name (e.g., "gr4j", "xaj")
        output_path: Output file path
        max_params_per_plot: Maximum parameters per subplot (default: 8)

    Returns:
        Success status
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib
        matplotlib.use("Agg")
        import numpy as np
        import yaml

        _configure_matplotlib_for_english()

        # Collect data from all iterations
        iteration_data = []

        for iter_dir in iteration_dirs:
            iter_num = int(iter_dir.name.split('_')[1])

            # Read parameter ranges (for normalization)
            param_range_file = iter_dir / "param_range_input.yaml"
            if not param_range_file.exists():
                param_range_file = iter_dir / "param_range.yaml"

            if not param_range_file.exists():
                logger.warning(f"[IterativePlotting] No param_range file in {iter_dir.name}")
                continue

            with open(param_range_file) as f:
                param_range_data = yaml.safe_load(f)

            param_ranges = param_range_data.get(model_name, {}).get('param_range', {})

            # Read best parameters (denormalized)
            denorm_file = iter_dir / "basins_denorm_params.csv"
            best_params = {}

            if denorm_file.exists():
                with open(denorm_file) as f:
                    lines = f.readlines()
                    if len(lines) > 1:
                        header = [h.strip() for h in lines[0].split(',')]
                        values = [v.strip() for v in lines[1].split(',')]

                        # Skip first column (basin_id)
                        param_names = header[1:]
                        param_values = values[1:]

                        for name, val in zip(param_names, param_values):
                            try:
                                best_params[name] = float(val)
                            except ValueError:
                                best_params[name] = None

            iteration_data.append({
                'iteration': iter_num,
                'param_ranges': param_ranges,
                'best_params': best_params
            })

        if not iteration_data:
            logger.warning("[IterativePlotting] No iteration data found")
            return False

        # Get all parameter names (from first iteration)
        all_param_names = list(iteration_data[0]['param_ranges'].keys())
        num_params = len(all_param_names)

        if num_params == 0:
            logger.warning("[IterativePlotting] No parameters found")
            return False

        # Determine subplot layout
        num_plots = (num_params + max_params_per_plot - 1) // max_params_per_plot

        # Create figure with subplots
        if num_plots == 1:
            fig, ax = plt.subplots(1, 1, figsize=(14, 7))
            axes = [ax]
        else:
            fig, axes = plt.subplots(num_plots, 1, figsize=(14, 6 * num_plots))
            if num_plots == 1:
                axes = [axes]

        # Color palette for parameters (using tab20 for better distinction)
        if num_params <= 10:
            colors = plt.cm.tab10(np.linspace(0, 1, num_params))
        else:
            colors = plt.cm.tab20(np.linspace(0, 1, num_params))

        # Plot each group of parameters
        for plot_idx in range(num_plots):
            ax = axes[plot_idx]

            # Get parameter subset for this plot
            start_idx = plot_idx * max_params_per_plot
            end_idx = min(start_idx + max_params_per_plot, num_params)
            param_subset = all_param_names[start_idx:end_idx]

            # Prepare data for each parameter
            for local_idx, param_name in enumerate(param_subset):
                global_idx = start_idx + local_idx
                color = colors[global_idx]

                # Extract data across iterations
                iterations = []
                normalized_vals = []

                for data in iteration_data:
                    iterations.append(data['iteration'])

                    # Get parameter range for normalization
                    param_range = data['param_ranges'].get(param_name, [0, 1])
                    pmin, pmax = param_range[0], param_range[1]

                    # Get best value
                    best_val = data['best_params'].get(param_name, None)

                    if best_val is not None and pmax > pmin:
                        # Normalize to [0, 1]
                        normalized = (best_val - pmin) / (pmax - pmin)
                        normalized_vals.append(normalized)
                    else:
                        normalized_vals.append(np.nan)

                # Plot normalized best parameter line
                ax.plot(
                    iterations,
                    normalized_vals,
                    marker='o',
                    linestyle='-',
                    linewidth=2.5,
                    markersize=9,
                    color=color,
                    label=param_name,
                    markerfacecolor='white',
                    markeredgewidth=2.5,
                    markeredgecolor=color
                )

                # Add value labels on last point
                if not np.isnan(normalized_vals[-1]):
                    ax.text(
                        iterations[-1] + 0.1,
                        normalized_vals[-1],
                        param_name,
                        fontsize=8,
                        va='center',
                        color=color,
                        fontweight='bold'
                    )

            # Styling
            ax.set_xlabel('Iteration Number', fontsize=13, fontweight='bold')
            ax.set_ylabel('Normalized Parameter Value [0, 1]', fontsize=13, fontweight='bold')

            if num_plots == 1:
                title = f'Parameter Evolution - Best Values (Normalized)\nModel: {model_name.upper()}'
            else:
                title = f'Parameter Evolution - Group {plot_idx + 1} (Normalized)\nModel: {model_name.upper()}'

            ax.set_title(title, fontsize=15, fontweight='bold', pad=15)
            ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.8)

            # Set y-axis limits
            ax.set_ylim(-0.05, 1.05)

            # Set x-axis to show integer iteration numbers
            all_iterations = [d['iteration'] for d in iteration_data]
            ax.set_xticks(all_iterations)

            # Legend (only if ≤ max_params_per_plot)
            if len(param_subset) <= max_params_per_plot:
                ax.legend(fontsize=10, loc='center left', bbox_to_anchor=(1, 0.5), framealpha=0.9)

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()

        logger.info(f"[IterativePlotting] Parameter evolution plot saved: {output_path}")
        return True

    except ImportError:
        logger.warning("[IterativePlotting] matplotlib/yaml not installed")
        return False
    except Exception as e:
        logger.error(f"[IterativePlotting] Failed to plot parameter evolution: {str(e)}", exc_info=True)
        return False


def plot_parameter_heatmap(
    iteration_dirs: List[Path],
    model_name: str,
    output_path: Path,
) -> bool:
    """
    Plot parameter evolution as a heatmap (all parameters in one figure).
    以热力图形式展示参数演化（所有参数在一张图上）。

    Strategy:
    - Heatmap: rows = parameters, columns = iterations
    - Color represents normalized parameter value [0, 1]
    - Easy to spot which parameters are changing vs stable
    - Annotate each cell with the normalized value

    Args:
        iteration_dirs: List of iteration directories (sorted)
        model_name: Model name (e.g., "gr4j", "xaj")
        output_path: Output file path

    Returns:
        Success status
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib
        matplotlib.use("Agg")
        import numpy as np
        import yaml

        _configure_matplotlib_for_english()

        # Collect data from all iterations
        iteration_data = []

        for iter_dir in iteration_dirs:
            iter_num = int(iter_dir.name.split('_')[1])

            # Read parameter ranges (for normalization)
            param_range_file = iter_dir / "param_range_input.yaml"
            if not param_range_file.exists():
                param_range_file = iter_dir / "param_range.yaml"

            if not param_range_file.exists():
                logger.warning(f"[IterativePlotting] No param_range file in {iter_dir.name}")
                continue

            with open(param_range_file) as f:
                param_range_data = yaml.safe_load(f)

            param_ranges = param_range_data.get(model_name, {}).get('param_range', {})

            # Read best parameters (denormalized)
            denorm_file = iter_dir / "basins_denorm_params.csv"
            best_params = {}

            if denorm_file.exists():
                with open(denorm_file) as f:
                    lines = f.readlines()
                    if len(lines) > 1:
                        header = [h.strip() for h in lines[0].split(',')]
                        values = [v.strip() for v in lines[1].split(',')]

                        # Skip first column (basin_id)
                        param_names = header[1:]
                        param_values = values[1:]

                        for name, val in zip(param_names, param_values):
                            try:
                                best_params[name] = float(val)
                            except ValueError:
                                best_params[name] = None

            iteration_data.append({
                'iteration': iter_num,
                'param_ranges': param_ranges,
                'best_params': best_params
            })

        if not iteration_data:
            logger.warning("[IterativePlotting] No iteration data found")
            return False

        # Get all parameter names
        all_param_names = list(iteration_data[0]['param_ranges'].keys())
        num_params = len(all_param_names)
        num_iterations = len(iteration_data)

        if num_params == 0:
            logger.warning("[IterativePlotting] No parameters found")
            return False

        # Build heatmap matrix (params × iterations)
        heatmap_data = np.full((num_params, num_iterations), np.nan)

        for iter_idx, data in enumerate(iteration_data):
            for param_idx, param_name in enumerate(all_param_names):
                # Get parameter range for normalization
                param_range = data['param_ranges'].get(param_name, [0, 1])
                pmin, pmax = param_range[0], param_range[1]

                # Get best value
                best_val = data['best_params'].get(param_name, None)

                if best_val is not None and pmax > pmin:
                    # Normalize to [0, 1]
                    normalized = (best_val - pmin) / (pmax - pmin)
                    heatmap_data[param_idx, iter_idx] = normalized

        # Create figure
        fig, ax = plt.subplots(figsize=(max(10, num_iterations * 1.5), max(8, num_params * 0.6)))

        # Plot heatmap
        im = ax.imshow(heatmap_data, cmap='RdYlGn', aspect='auto', vmin=0, vmax=1)

        # Set ticks
        iteration_numbers = [d['iteration'] for d in iteration_data]
        ax.set_xticks(np.arange(num_iterations))
        ax.set_yticks(np.arange(num_params))
        ax.set_xticklabels([f'Iter {n}' for n in iteration_numbers])
        ax.set_yticklabels(all_param_names)

        # Rotate x labels
        plt.setp(ax.get_xticklabels(), rotation=0, ha="center", fontsize=11, fontweight='bold')
        plt.setp(ax.get_yticklabels(), fontsize=11, fontweight='bold')

        # Add colorbar
        cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.ax.set_ylabel('Normalized Value [0=min, 1=max]', rotation=270, va='bottom', fontsize=11, fontweight='bold')
        cbar.ax.tick_params(labelsize=10)

        # Annotate cells with values
        for i in range(num_params):
            for j in range(num_iterations):
                val = heatmap_data[i, j]
                if not np.isnan(val):
                    # Choose text color based on background
                    text_color = 'white' if val < 0.5 else 'black'
                    ax.text(j, i, f'{val:.2f}',
                           ha="center", va="center",
                           color=text_color, fontsize=9, fontweight='bold')

        # Title and labels
        ax.set_title(f'Parameter Evolution Heatmap - {model_name.upper()}\n(Normalized Values: 0=Min Range, 1=Max Range)',
                    fontsize=14, fontweight='bold', pad=20)
        ax.set_xlabel('Iteration', fontsize=12, fontweight='bold')
        ax.set_ylabel('Parameter', fontsize=12, fontweight='bold')

        # Grid
        ax.set_xticks(np.arange(num_iterations) - 0.5, minor=True)
        ax.set_yticks(np.arange(num_params) - 0.5, minor=True)
        ax.grid(which="minor", color="gray", linestyle='-', linewidth=1.5)
        ax.tick_params(which="minor", size=0)

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()

        logger.info(f"[IterativePlotting] Parameter heatmap saved: {output_path}")
        return True

    except ImportError:
        logger.warning("[IterativePlotting] matplotlib/yaml not installed")
        return False
    except Exception as e:
        logger.error(f"[IterativePlotting] Failed to plot parameter heatmap: {str(e)}", exc_info=True)
        return False


def create_iterative_calibration_plots(
    workspace_dir: Path,
    model_name: str,
    target_nse: Optional[float] = None,
) -> Dict[str, bool]:
    """
    Create all visualization plots for iterative calibration.
    为迭代率定创建所有可视化图表。

    Args:
        workspace_dir: Workspace directory containing iteration_* subdirectories
        model_name: Model name (e.g., "gr4j", "xaj")
        target_nse: Target NSE threshold (optional)

    Returns:
        Dictionary with plot names and success status
        {
            'nse_evolution': True/False,
            'parameter_evolution': True/False,
            'parameter_heatmap': True/False
        }
    """
    results = {
        'nse_evolution': False,
        'parameter_evolution': False,
        'parameter_heatmap': False
    }

    try:
        # Find all iteration directories
        iteration_dirs = sorted(workspace_dir.glob("iteration_*"))

        if not iteration_dirs:
            logger.warning(f"[IterativePlotting] No iteration directories found in {workspace_dir}")
            return results

        logger.info(f"[IterativePlotting] Found {len(iteration_dirs)} iterations")

        # Create NSE evolution plot
        nse_plot_path = workspace_dir / "nse_evolution.png"
        results['nse_evolution'] = plot_nse_evolution(
            iteration_dirs=iteration_dirs,
            output_path=nse_plot_path,
            target_nse=target_nse
        )

        # Create parameter evolution plot (line chart)
        param_plot_path = workspace_dir / "parameter_evolution.png"
        results['parameter_evolution'] = plot_parameter_evolution(
            iteration_dirs=iteration_dirs,
            model_name=model_name,
            output_path=param_plot_path
        )

        # Create parameter heatmap (all parameters in one figure)
        heatmap_path = workspace_dir / "parameter_heatmap.png"
        results['parameter_heatmap'] = plot_parameter_heatmap(
            iteration_dirs=iteration_dirs,
            model_name=model_name,
            output_path=heatmap_path
        )

        # Summary
        logger.info("[IterativePlotting] Visualization summary:")
        logger.info(f"  - NSE evolution: {'OK' if results['nse_evolution'] else 'FAIL'}")
        logger.info(f"  - Parameter evolution: {'OK' if results['parameter_evolution'] else 'FAIL'}")
        logger.info(f"  - Parameter heatmap: {'OK' if results['parameter_heatmap'] else 'FAIL'}")

        return results

    except Exception as e:
        logger.error(f"[IterativePlotting] Failed to create plots: {str(e)}", exc_info=True)
        return results
