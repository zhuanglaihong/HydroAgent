# -*- coding: utf-8 -*-
# Template for runoff coefficient calculation (v5.1)
# Auto-generated from template, placeholders replaced
"""
流域径流系数计算脚本
用于计算指定流域的时间序列径流系数（每个时间步的径流量/降水量）
绘制类似降雨径流双坐标图的时序图
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


def calculate_runoff_coefficient(nc_file_path: str, basin_id: str) -> tuple:
    """
    计算时间序列径流系数

    Args:
        nc_file_path: NetCDF数据文件路径
        basin_id: 流域ID

    Returns:
        tuple: (时间序列, 降水, 径流, 径流系数时序, 平均径流系数)

    Raises:
        FileNotFoundError: 当数据文件不存在时
        ValueError: 当数据无效时
    """
    print(f"[INFO] 正在计算流域 {basin_id} 的时间序列径流系数...")

    # 1. Validate file exists
    nc_path = Path(nc_file_path)
    if not nc_path.exists():
        raise FileNotFoundError(f"数据文件不存在: {nc_file_path}")

    print(f"[INFO] 数据文件: {nc_file_path}")

    # 2. Read data with try-except
    try:
        ds = xr.open_dataset(nc_file_path)
        print(f"[INFO] 数据集变量: {list(ds.data_vars)}")
        print(f"[INFO] 数据集维度: {list(ds.dims)}")

        # Extract time coordinate
        if 'time' in ds:
            time = pd.to_datetime(ds['time'].values)
            print(f"[INFO] 时间范围: {time[0]} 至 {time[-1]}")
        else:
            # Create sequential time index
            print(f"[WARNING] 未找到time维度，使用序列索引")
            time = pd.date_range(start='2000-01-01', periods=len(ds[list(ds.data_vars)[0]]), freq='D')

        # Extract observed flow and precipitation
        # Try common variable names
        if 'qobs' in ds:
            qobs = ds['qobs'].values.flatten()
        elif 'streamflow' in ds:
            qobs = ds['streamflow'].values.flatten()
        elif 'flow' in ds:
            qobs = ds['flow'].values.flatten()
        else:
            raise ValueError(f"未找到流量变量（尝试了qobs, streamflow, flow）")

        if 'prcp' in ds:
            prcp = ds['prcp'].values.flatten()
        elif 'precipitation' in ds:
            prcp = ds['precipitation'].values.flatten()
        else:
            raise ValueError(f"未找到降水变量（尝试了prcp, precipitation）")

        ds.close()

        # 3. Calculate per-timestep runoff coefficient
        # Handle zero/small precipitation: set coefficient to NaN when precip < threshold
        precip_threshold = 0.1  # mm/day

        # Initialize runoff coefficient array
        rc_series = np.zeros_like(qobs)

        # Calculate per-timestep coefficients
        for i in range(len(qobs)):
            if prcp[i] >= precip_threshold:
                rc_series[i] = qobs[i] / prcp[i]
            else:
                rc_series[i] = np.nan  # 降水太小时设为NaN

        # Calculate overall average (excluding NaN)
        valid_indices = ~np.isnan(rc_series)
        mean_rc = np.nanmean(rc_series)

        # Also calculate total-based coefficient for comparison
        total_runoff = np.sum(qobs[~np.isnan(qobs)])
        total_precip = np.sum(prcp[~np.isnan(prcp)])
        total_based_rc = total_runoff / total_precip if total_precip > 0 else 0

        print(f"[INFO] 数据点数: {len(qobs)}")
        print(f"[INFO] 有效径流系数点数: {np.sum(valid_indices)} (降水>={precip_threshold}mm的点)")
        print(f"[INFO] 平均径流系数: {mean_rc:.4f}")
        print(f"[INFO] 总量法径流系数: {total_based_rc:.4f}")
        print(f"[INFO] 总径流量: {total_runoff:.2f} mm")
        print(f"[INFO] 总降水量: {total_precip:.2f} mm")

        print(f"[OK] 流域 {basin_id} 时间序列径流系数计算完成")

        return time, prcp, qobs, rc_series, mean_rc

    except Exception as e:
        print(f"[ERROR] 计算失败: {str(e)}")
        raise


def save_results(basin_id: str, time, prcp, qobs, rc_series, mean_rc, output_dir: str) -> str:
    """
    保存计算结果到CSV文件

    Args:
        basin_id: 流域ID
        time: 时间序列
        prcp: 降水时序
        qobs: 径流时序
        rc_series: 径流系数时序
        mean_rc: 平均径流系数
        output_dir: 输出目录

    Returns:
        str: 结果文件路径
    """
    print(f"[INFO] 正在保存结果...")

    # Create output directory if not exists
    os.makedirs(output_dir, exist_ok=True)

    # Create time series dataframe
    ts_df = pd.DataFrame({
        'time': time,
        'precipitation_mm': prcp,
        'runoff_mm': qobs,
        'runoff_coefficient': rc_series
    })

    # Save time series to CSV
    ts_path = os.path.join(output_dir, f"runoff_coefficient_timeseries_{basin_id}.csv")
    ts_df.to_csv(ts_path, index=False, encoding='utf-8')
    print(f"[OK] 时间序列数据已保存到: {ts_path}")

    # Save summary statistics
    summary_df = pd.DataFrame({
        'basin_id': [basin_id],
        'mean_runoff_coefficient': [mean_rc],
        'total_runoff_mm': [np.sum(qobs[~np.isnan(qobs)])],
        'total_precip_mm': [np.sum(prcp[~np.isnan(prcp)])],
        'data_points': [len(prcp)],
        'valid_rc_points': [np.sum(~np.isnan(rc_series))]
    })

    summary_path = os.path.join(output_dir, f"runoff_coefficient_summary_{basin_id}.csv")
    summary_df.to_csv(summary_path, index=False, encoding='utf-8')
    print(f"[OK] 汇总统计已保存到: {summary_path}")

    return ts_path


def plot_summary(basin_id: str, time, prcp, qobs, rc_series, mean_rc, output_dir: str) -> str:
    """
    绘制径流系数时间序列图（类似降雨径流双坐标图）

    Args:
        basin_id: 流域ID
        time: 时间序列
        prcp: 降水时序
        qobs: 径流时序
        rc_series: 径流系数时序
        mean_rc: 平均径流系数
        output_dir: 输出目录

    Returns:
        str: 图片文件路径
    """
    print(f"[INFO] 正在生成时间序列图...")

    # Create output directory if not exists
    os.makedirs(output_dir, exist_ok=True)

    # Create figure with 2 subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)

    # Subplot 1: Precipitation and Runoff (dual-axis, similar to rain-runoff plot)
    ax1_twin = ax1.twinx()

    # Plot precipitation as bars (inverted on top axis)
    ax1.bar(time, prcp, color='skyblue', alpha=0.6, label='降水', width=1.0)
    ax1.set_ylabel('降水 (mm)', fontsize=11, color='blue')
    ax1.tick_params(axis='y', labelcolor='blue')
    ax1.invert_yaxis()  # Invert to show precip from top
    ax1.set_ylim(max(prcp) * 1.2, 0)  # Set limits for inverted axis

    # Plot runoff as line (on bottom axis)
    ax1_twin.plot(time, qobs, color='darkblue', linewidth=1.5, label='径流', alpha=0.8)
    ax1_twin.set_ylabel('径流 (mm)', fontsize=11, color='darkblue')
    ax1_twin.tick_params(axis='y', labelcolor='darkblue')

    ax1.set_title(f'流域 {basin_id} - 降水与径流时间序列', fontsize=13, fontweight='bold')
    ax1.grid(axis='x', alpha=0.3)

    # Add legends
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax1_twin.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right', fontsize=10)

    # Subplot 2: Runoff Coefficient Time Series
    ax2.plot(time, rc_series, color='green', linewidth=1.2, alpha=0.7, label='径流系数')
    ax2.axhline(y=mean_rc, color='red', linestyle='--', linewidth=2, label=f'平均值 = {mean_rc:.4f}')

    ax2.set_xlabel('时间', fontsize=11)
    ax2.set_ylabel('径流系数 (径流/降水)', fontsize=11)
    ax2.set_title(f'流域 {basin_id} - 径流系数时间序列', fontsize=13, fontweight='bold')
    ax2.grid(alpha=0.3)
    ax2.legend(loc='upper right', fontsize=10)

    # Format x-axis for better date display
    import matplotlib.dates as mdates
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax2.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')

    # Set y-axis limits for coefficient plot
    rc_valid = rc_series[~np.isnan(rc_series)]
    if len(rc_valid) > 0:
        y_min = max(0, np.percentile(rc_valid, 1))
        y_max = min(np.percentile(rc_valid, 99), 3.0)  # Cap at 3.0 for readability
        ax2.set_ylim(y_min, y_max * 1.1)

    plt.tight_layout()

    # Save figure
    output_path = os.path.join(output_dir, f"runoff_coefficient_{basin_id}.png")
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()

    print(f"[OK] 时间序列图已保存到: {output_path}")

    return output_path


def main():
    """主函数"""
    print("=" * 80)
    print("流域径流系数计算工具（时间序列分析）")
    print("=" * 80)

    # Configuration - These will be filled by TemplateManager
    NC_FILE_PATH = r"{{NC_FILE_PATH}}"
    BASIN_ID = "{{BASIN_ID}}"
    OUTPUT_DIR = r"{{OUTPUT_DIR}}"

    try:
        # Calculate runoff coefficient (time series)
        time, prcp, qobs, rc_series, mean_rc = calculate_runoff_coefficient(NC_FILE_PATH, BASIN_ID)

        # Save results
        csv_path = save_results(BASIN_ID, time, prcp, qobs, rc_series, mean_rc, OUTPUT_DIR)

        # Generate plot
        plot_path = plot_summary(BASIN_ID, time, prcp, qobs, rc_series, mean_rc, OUTPUT_DIR)

        print("\n" + "=" * 80)
        print("计算完成!")
        print(f"平均径流系数: {mean_rc:.4f}")
        print(f"时间序列数据: {csv_path}")
        print(f"时间序列图: {plot_path}")
        print("=" * 80)

        return 0

    except Exception as e:
        print("\n" + "=" * 80)
        print(f"[ERROR] 执行失败: {str(e)}")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
