"""
Template for Flow Duration Curve (FDC) plotting
Placeholders: {{NC_FILE_PATH}}, {{BASIN_ID}}, {{OUTPUT_DIR}}
"""
# -*- coding: utf-8 -*-
"""
流量历时曲线（FDC）绘制脚本
用于绘制观测流量和模拟流量的流量历时曲线对比图
"""

import os
import xarray as xr
import numpy as np
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt

# 配置matplotlib中文显示
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


def calculate_fdc(flow_data: np.ndarray) -> tuple:
    """
    计算流量历时曲线

    Args:
        flow_data: 流量时间序列数据

    Returns:
        tuple: (exceedance_probability, sorted_flow)
    """
    # Remove NaN values
    flow_valid = flow_data[~np.isnan(flow_data)]

    # Sort in descending order
    sorted_flow = np.sort(flow_valid)[::-1]

    # Calculate exceedance probability
    n = len(sorted_flow)
    exceedance_prob = np.arange(1, n + 1) / (n + 1) * 100

    return exceedance_prob, sorted_flow


def plot_fdc(nc_file_path: str, basin_id: str, output_dir: str) -> str:
    """
    绘制流量历时曲线（FDC）

    Args:
        nc_file_path: NetCDF数据文件路径
        basin_id: 流域ID
        output_dir: 输出目录

    Returns:
        str: 图片文件路径

    Raises:
        FileNotFoundError: 当数据文件不存在时
        ValueError: 当数据无效时
    """
    print(f"[INFO] 正在为流域 {basin_id} 绘制FDC曲线...")

    # 1. Validate file exists
    nc_path = Path(nc_file_path)
    if not nc_path.exists():
        raise FileNotFoundError(f"数据文件不存在: {nc_file_path}")

    print(f"[INFO] 数据文件: {nc_file_path}")

    # 2. Read data
    try:
        ds = xr.open_dataset(nc_file_path)
        print(f"[INFO] 数据集变量: {list(ds.data_vars)}")

        # Extract observed and simulated flow
        # Try common variable names for observed flow
        if 'qobs' in ds:
            qobs = ds['qobs'].values.flatten()
        elif 'streamflow_obs' in ds:
            qobs = ds['streamflow_obs'].values.flatten()
        elif 'flow_obs' in ds:
            qobs = ds['flow_obs'].values.flatten()
        else:
            raise ValueError("未找到观测流量变量（尝试了qobs, streamflow_obs, flow_obs）")

        # Try common variable names for simulated flow
        qsim = None
        for var_name in ['qsim', 'streamflow_sim', 'flow_sim', 'sim']:
            if var_name in ds:
                qsim = ds[var_name].values.flatten()
                break

        ds.close()

        print(f"[INFO] 观测流量数据点数: {len(qobs)}")
        if qsim is not None:
            print(f"[INFO] 模拟流量数据点数: {len(qsim)}")

        # 3. Calculate FDC
        exc_prob_obs, flow_obs_sorted = calculate_fdc(qobs)

        exc_prob_sim = None
        flow_sim_sorted = None
        if qsim is not None:
            exc_prob_sim, flow_sim_sorted = calculate_fdc(qsim)

        # 4. Create plot
        fig, ax = plt.subplots(figsize=(10, 6))

        # Plot observed FDC
        ax.plot(exc_prob_obs, flow_obs_sorted, 'b-', linewidth=2, label='观测流量', alpha=0.8)

        # Plot simulated FDC if available
        if qsim is not None:
            ax.plot(exc_prob_sim, flow_sim_sorted, 'r--', linewidth=2, label='模拟流量', alpha=0.8)

        # Formatting
        ax.set_xlabel('超过概率 (%)', fontsize=12)
        ax.set_ylabel('流量 (m³/s)', fontsize=12)
        ax.set_title(f'流域 {basin_id} 流量历时曲线 (FDC)', fontsize=14, fontweight='bold')
        ax.set_yscale('log')
        ax.grid(True, alpha=0.3, which='both')
        ax.legend(fontsize=11, loc='upper right')

        plt.tight_layout()

        # 5. Save plot
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"FDC_{basin_id}.png")
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()

        print(f"[OK] FDC曲线已保存到: {output_path}")

        return output_path

    except Exception as e:
        print(f"[ERROR] 绘图失败: {str(e)}")
        raise


def save_fdc_data(nc_file_path: str, basin_id: str, output_dir: str) -> str:
    """
    保存FDC数据到CSV文件

    Args:
        nc_file_path: NetCDF数据文件路径
        basin_id: 流域ID
        output_dir: 输出目录

    Returns:
        str: CSV文件路径
    """
    print(f"[INFO] 正在保存FDC数据...")

    # Read data
    nc_path = Path(nc_file_path)
    if not nc_path.exists():
        raise FileNotFoundError(f"数据文件不存在: {nc_file_path}")

    ds = xr.open_dataset(nc_file_path)

    # Extract flows
    if 'qobs' in ds:
        qobs = ds['qobs'].values.flatten()
    else:
        raise ValueError("未找到观测流量变量")

    qsim = None
    for var_name in ['qsim', 'streamflow_sim', 'flow_sim', 'sim']:
        if var_name in ds:
            qsim = ds[var_name].values.flatten()
            break

    ds.close()

    # Calculate FDC
    exc_prob_obs, flow_obs_sorted = calculate_fdc(qobs)

    # Create dataframe
    data = {
        'exceedance_probability': exc_prob_obs,
        'observed_flow': flow_obs_sorted
    }

    if qsim is not None:
        exc_prob_sim, flow_sim_sorted = calculate_fdc(qsim)
        # Interpolate to match lengths if needed
        if len(exc_prob_sim) != len(exc_prob_obs):
            from scipy.interpolate import interp1d
            f = interp1d(exc_prob_sim, flow_sim_sorted, bounds_error=False, fill_value='extrapolate')
            data['simulated_flow'] = f(exc_prob_obs)
        else:
            data['simulated_flow'] = flow_sim_sorted

    df = pd.DataFrame(data)

    # Save to CSV
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"FDC_data_{basin_id}.csv")
    df.to_csv(output_path, index=False, encoding='utf-8')

    print(f"[OK] FDC数据已保存到: {output_path}")

    return output_path


def main():
    """主函数"""
    print("=" * 80)
    print("流量历时曲线（FDC）绘制工具")
    print("=" * 80)

    # Configuration - These will be filled by TemplateManager
    NC_FILE_PATH = r"{{NC_FILE_PATH}}"
    BASIN_ID = "{{BASIN_ID}}"
    OUTPUT_DIR = r"{{OUTPUT_DIR}}"

    try:
        # Generate FDC plot
        plot_path = plot_fdc(NC_FILE_PATH, BASIN_ID, OUTPUT_DIR)

        # Save FDC data
        csv_path = save_fdc_data(NC_FILE_PATH, BASIN_ID, OUTPUT_DIR)

        print("\n" + "=" * 80)
        print("绘图完成!")
        print(f"FDC图片: {plot_path}")
        print(f"FDC数据: {csv_path}")
        print("=" * 80)

        return 0

    except Exception as e:
        print("\n" + "=" * 80)
        print(f"[ERROR] 执行失败: {str(e)}")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
