# -*- coding: utf-8 -*-
"""
HydroClaw Tool Module: runoff_fdc_analysis

计算流域径流系数和流量历时曲线(FDC)的分析工具。
功能包括：径流系数计算、FDC生成、可视化、统计分析。
"""

from pathlib import Path
from typing import Any

import logging

logger = logging.getLogger(__name__)


def runoff_fdc_analysis(
    qobs_path: str,
    prcp_path: str | None = None,
    output_dir: str = "./output",
    basin_id: str | None = None,
    time_freq: str = "M",
    _workspace: Path | None = None,
    _cfg: dict | None = None,
) -> dict[str, Any]:
    """计算流域径流系数和流量历时曲线(FDC)分析。

    基于降水和径流数据计算年/月径流系数，生成FDC曲线，
    计算Q90、Q50、Q10等特征流量，并输出可视化图表。

    Args:
        qobs_path: 径流观测数据CSV文件路径，需包含日期索引和流量列
        prcp_path: 降水数据CSV文件路径，需包含日期索引和降水量列。
            若为None，则仅进行FDC分析而不计算径流系数。
        output_dir: 输出目录路径，用于保存结果CSV和图表
        basin_id: 流域标识符，用于输出文件名。若为None，使用qobs文件名
        time_freq: 径流系数计算的时间频率，'Y'为年，'M'为月，'D'为日
        _workspace: 工作目录（由agent注入）
        _cfg: 全局配置（由agent注入）

    Returns:
        包含分析结果的字典，结构如下：
        {
            "success": bool,
            "runoff_coefficient": dict | None,  # 径流系数统计结果
            "fdc_features": dict,               # FDC特征值
            "output_files": dict,               # 输出文件路径
            "error": str | None                 # 错误信息
        }
    """
    import pandas as pd
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')  # 非交互式后端
    import matplotlib.pyplot as plt
    import seaborn as sns

    result = {
        "success": False,
        "runoff_coefficient": None,
        "fdc_features": {},
        "output_files": {},
        "error": None,
    }

    try:
        # 解析路径
        if _workspace is not None:
            base_path = _workspace
        else:
            base_path = Path.cwd()

        qobs_file = base_path / qobs_path
        out_dir = base_path / output_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        # 确定流域ID
        if basin_id is None:
            basin_id = Path(qobs_path).stem

        # 读取径流数据
        logger.info(f"Reading discharge data from {qobs_file}")
        if not qobs_file.exists():
            result["error"] = f"Discharge file not found: {qobs_file}"
            return result

        qobs = pd.read_csv(qobs_file, index_col=0, parse_dates=True)
        if qobs.empty or len(qobs.columns) == 0:
            result["error"] = "Discharge data is empty or has no columns"
            return result

        # 假设第一列为流量数据
        q_col = qobs.columns[0]
        q_series = qobs[q_col].dropna()
        
        if len(q_series) == 0:
            result["error"] = "No valid discharge data after dropping NaN"
            return result

        # ==================== FDC计算 ====================
        logger.info("Calculating Flow Duration Curve (FDC)")
        
        # 计算FDC: 从100%到0%的百分位数
        exceedance_probs = np.arange(100, -1, -1)
        fdc_values = np.percentile(q_series, 100 - exceedance_probs)
        
        # FDC特征值
        fdc_features = {
            "Q_max": float(np.max(q_series)),
            "Q_min": float(np.min(q_series)),
            "Q_mean": float(np.mean(q_series)),
            "Q_median": float(np.median(q_series)),
            "Q90": float(np.percentile(q_series, 10)),   # 90%时间超过的流量
            "Q50": float(np.percentile(q_series, 50)),   # 中值流量
            "Q10": float(np.percentile(q_series, 90)),   # 10%时间超过的流量
            "Q95": float(np.percentile(q_series, 5)),    # 95%时间超过的流量
            "Q05": float(np.percentile(q_series, 95)),   # 5%时间超过的流量
        }
        result["fdc_features"] = fdc_features

        # 保存FDC数据
        fdc_df = pd.DataFrame({
            "exceedance_probability": exceedance_probs,
            "discharge": fdc_values
        })
        fdc_csv_path = out_dir / f"{basin_id}_fdc.csv"
        fdc_df.to_csv(fdc_csv_path, index=False)
        result["output_files"]["fdc_data"] = str(fdc_csv_path)

        # ==================== 径流系数计算 ====================
        runoff_coeff_result = None
        
        if prcp_path is not None:
            prcp_file = base_path / prcp_path
            
            if not prcp_file.exists():
                logger.warning(f"Precipitation file not found: {prcp_file}, skipping runoff coefficient calculation")
            else:
                logger.info(f"Reading precipitation data from {prcp_file}")
                prcp = pd.read_csv(prcp_file, index_col=0, parse_dates=True)
                
                if prcp.empty or len(prcp.columns) == 0:
                    logger.warning("Precipitation data is empty, skipping runoff coefficient calculation")
                else:
                    p_col = prcp.columns[0]
                    p_series = prcp[p_col].dropna()
                    
                    # 对齐时间序列
                    common_idx = q_series.index.intersection(p_series.index)
                    if len(common_idx) == 0:
                        logger.warning("No overlapping dates between Q and P data")
                    else:
                        q_aligned = q_series.loc[common_idx]
                        p_aligned = p_series.loc[common_idx]
                        
                        # 按时间频率重采样
                        freq_map = {"Y": "YE", "M": "ME", "D": "D"}  # pandas 2.0+兼容
                        resample_freq = freq_map.get(time_freq, time_freq)
                        
                        q_resampled = q_aligned.resample(resample_freq).sum()
                        p_resampled = p_aligned.resample(resample_freq).sum()
                        
                        # 计算径流系数 (R = Q / P)
                        # 注意：需要单位转换，假设Q是m3/s，P是mm
                        # 这里简化处理，直接计算比值
                        runoff_coeff = q_resampled / p_resampled.replace(0, np.nan)
                        runoff_coeff = runoff_coeff.dropna()
                        
                        # 限制合理范围
                        runoff_coeff = runoff_coeff[(runoff_coeff >= 0) & (runoff_coeff <= 1)]
                        
                        if len(runoff_coeff) > 0:
                            runoff_coeff_result = {
                                "mean": float(runoff_coeff.mean()),
                                "median": float(runoff_coeff.median()),
                                "std": float(runoff_coeff.std()),
                                "min": float(runoff_coeff.min()),
                                "max": float(runoff_coeff.max()),
                                "count": int(len(runoff_coeff)),
                            }
                            
                            # 保存径流系数时间序列
                            rc_df = pd.DataFrame({
                                "runoff_coefficient": runoff_coeff
                            })
                            rc_df.index.name = "time"
                            rc_csv_path = out_dir / f"{basin_id}_runoff_coefficient_{time_freq}.csv"
                            rc_df.to_csv(rc_csv_path)
                            result["output_files"]["runoff_coefficient_timeseries"] = str(rc_csv_path)
                            
                            # 保存统计结果
                            stats_df = pd.DataFrame([runoff_coeff_result])
                            stats_csv_path = out_dir / f"{basin_id}_runoff_coefficient_stats.csv"
                            stats_df.to_csv(stats_csv_path, index=False)
                            result["output_files"]["runoff_coefficient_stats"] = str(stats_csv_path)

        result["runoff_coefficient"] = runoff_coeff_result

        # ==================== 可视化 ====================
        logger.info("Generating visualizations")
        
        # 设置样式
        sns.set_style("whitegrid")
        plt.rcParams['font.size'] = 10
        
        # 图1: FDC曲线
        fig1, ax1 = plt.subplots(figsize=(10, 6))
        ax1.semilogy(exceedance_probs, fdc_values, 'b-', linewidth=2, label='FDC')
        ax1.axhline(y=fdc_features["Q90"], color='r', linestyle='--', alpha=0.7, label=f'Q90={fdc_features["Q90"]:.2f}')
        ax1.axhline(y=fdc_features["Q50"], color='g', linestyle='--', alpha=0.7, label=f'Q50={fdc_features["Q50"]:.2f}')
        ax1.axhline(y=fdc_features["Q10"], color='orange', linestyle='--', alpha=0.7, label=f'Q10={fdc_features["Q10"]:.2f}')
        ax1.set_xlabel('Exceedance Probability (%)')
        ax1.set_ylabel('Discharge')
        ax1.set_title(f'Flow Duration Curve - {basin_id}')
        ax1.legend(loc='upper right')
        ax1.set_xlim(0, 100)
        ax1.grid(True, which="both", ls="-", alpha=0.2)
        
        fdc_plot_path = out_dir / f"{basin_id}_fdc_plot.png"
        fig1.tight_layout()
        fig1.savefig(fdc_plot_path, dpi=300, bbox_inches='tight')
        plt.close(fig1)
        result["output_files"]["fdc_plot"] = str(fdc_plot_path)

        # 图2: 径流时间序列（如果有降水数据则一起绘制）
        fig2, axes = plt.subplots(2 if prcp_path and runoff_coeff_result else 1, 1, 
                                   figsize=(12, 8 if prcp_path and runoff_coeff_result else 4),
                                   sharex=True)
        if not isinstance(axes, np.ndarray):
            axes = [axes]
        
        # 子图1: 流量时间序列
        ax_q = axes[0]
        ax_q.plot(q_series.index, q_series.values, 'b-', linewidth=0.8, alpha=0.8, label='Discharge')
        ax_q.set_ylabel('Discharge')
        ax_q.set_title(f'Discharge Time Series - {basin_id}')
        ax_q.legend(loc='upper right')
        ax_q.grid(True, alpha=0.3)
        
        # 子图2: 径流系数时间序列（如果可用）
        if prcp_path and runoff_coeff_result and runoff_coeff_result.get("count", 0) > 0:
            ax_rc = axes[1]
            # 重新获取数据用于绘图
            prcp_file = base_path / prcp_path
            prcp = pd.read_csv(prcp_file, index_col=0, parse_dates=True)
            p_series = prcp.iloc[:, 0].dropna()
            common_idx = q_series.index.intersection(p_series.index)
            q_aligned = q_series.loc[common_idx]
            p_aligned = p_series.loc[common_idx]
            resample_freq = {"Y": "YE", "M": "ME", "D": "D"}.get(time_freq, time_freq)
            q_resampled = q_aligned.resample(resample_freq).sum()
            p_resampled = p_aligned.resample(resample_freq).sum()
            runoff_coeff_plot = (q_resampled / p_resampled.replace(0, np.nan)).dropna()
            runoff_coeff_plot = runoff_coeff_plot[(runoff_coeff_plot >= 0) & (runoff_coeff_plot <= 1)]
            
            ax_rc.bar(runoff_coeff_plot.index, runoff_coeff_plot.values, width=20, color='steelblue', alpha=0.7)
            ax_rc.axhline(y=runoff_coeff_result["mean"], color='r', linestyle='--', 
                         label=f'Mean RC={runoff_coeff_result["mean"]:.3f}')
            ax_rc.set_ylabel('Runoff Coefficient')
            ax_rc.set_xlabel('Time')
            ax_rc.set_title(f'Runoff Coefficient ({time_freq}) - {basin_id}')
            ax_rc.set_ylim(0, min(1, runoff_coeff_plot.max() * 1.2 + 0.1))
            ax_rc.legend(loc='upper right')
            ax_rc.grid(True, alpha=0.3)
        
        ts_plot_path = out_dir / f"{basin_id}_timeseries_plot.png"
        fig2.tight_layout()
        fig2.savefig(ts_plot_path, dpi=300, bbox_inches='tight')
        plt.close(fig2)
        result["output_files"]["timeseries_plot"] = str(ts_plot_path)

        result["success"] = True
        logger.info(f"Analysis completed successfully for basin {basin_id}")

    except Exception as e:
        logger.exception("Error in runoff_fdc_analysis")
        result["error"] = f"Analysis failed: {str(e)}"
        result["success"] = False

    return result


def _validate_frequency(freq: str) -> str:
    """验证并标准化时间频率字符串。
    
    Args:
        freq: 输入的频率字符串
        
    Returns:
        标准化的频率字符串
    """
    valid_freqs = {"Y": "Y", "YE": "Y", "A": "Y", "M": "M", "ME": "M", "D": "D"}
    return valid_freqs.get(freq.upper(), "M")