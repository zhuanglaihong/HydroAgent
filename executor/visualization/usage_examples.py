"""
Author: zhuanglaihong
Date: 2025-01-25 18:45:00
LastEditTime: 2025-01-25 18:45:00
LastEditors: zhuanglaihong
Description: 水文模型可视化工具使用示例 - 展示如何生成论文级别的图表
FilePath: \HydroAgent\executor\visualization\usage_examples.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

from .hydro_visualizer import HydroVisualizer
from .optimization_visualizer import OptimizationVisualizer
from .statistics_visualizer import StatisticsVisualizer


def generate_sample_hydro_data():
    """生成示例水文数据用于演示"""
    # 生成时间序列
    dates = pd.date_range('2010-01-01', '2015-12-31', freq='D')
    n_days = len(dates)

    # 生成模拟的观测径流数据（包含季节性变化和随机波动）
    t = np.arange(n_days)
    seasonal = 50 + 30 * np.sin(2 * np.pi * t / 365.25)  # 季节性变化
    trend = 0.001 * t  # 轻微趋势
    noise = 10 * np.random.randn(n_days)  # 随机噪声
    observed = np.maximum(0.1, seasonal + trend + noise)  # 确保径流为正值

    # 生成模拟径流数据（带有系统性偏差和随机误差）
    model_bias = 0.9  # 模型偏差
    model_noise = 5 * np.random.randn(n_days)
    simulated = np.maximum(0.1, model_bias * observed + model_noise)

    return dates, observed, simulated


def generate_sample_optimization_data():
    """生成示例优化数据用于演示"""
    n_generations = 100
    n_parameters = 4

    # 生成收敛历史
    best_values = []
    mean_values = []
    worst_values = []

    initial_best = 0.2
    final_best = 0.85

    for gen in range(n_generations):
        # 指数收敛
        progress = 1 - np.exp(-gen / 30)
        best = initial_best + (final_best - initial_best) * progress
        best_values.append(best + 0.02 * np.random.randn())

        mean = best - 0.1 - 0.05 * np.random.rand()
        mean_values.append(max(0, mean))

        worst = best - 0.2 - 0.1 * np.random.rand()
        worst_values.append(max(0, worst))

    # 生成参数历史
    param_names = ['X1', 'X2', 'X3', 'X4']
    param_ranges = {'X1': (0, 1000), 'X2': (0, 5), 'X3': (0, 100), 'X4': (1, 5)}
    param_history = {}

    for param in param_names:
        min_val, max_val = param_ranges[param]
        # 参数逐渐收敛到最优值
        target_val = min_val + (max_val - min_val) * 0.7
        values = []
        current_val = min_val + (max_val - min_val) * np.random.rand()

        for gen in range(n_generations):
            # 向目标值收敛
            current_val += 0.05 * (target_val - current_val) + 0.02 * (max_val - min_val) * np.random.randn()
            current_val = np.clip(current_val, min_val, max_val)
            values.append(current_val)

        param_history[param] = values

    # 生成参数样本（用于相关性分析）
    n_samples = 1000
    parameter_samples = {}
    objective_values = []

    for param in param_names:
        min_val, max_val = param_ranges[param]
        samples = np.random.uniform(min_val, max_val, n_samples)
        parameter_samples[param] = samples.tolist()

    # 生成对应的目标函数值
    for i in range(n_samples):
        # 简化的目标函数
        obj_val = np.random.beta(2, 3)  # 偏向较低的值
        objective_values.append(obj_val)

    return {
        'convergence_history': {
            'best_values': best_values,
            'mean_values': mean_values,
            'worst_values': worst_values,
            'target_value': 0.8
        },
        'parameter_history': param_history,
        'parameter_ranges': param_ranges,
        'parameter_samples': parameter_samples,
        'objective_values': objective_values
    }


def generate_sample_statistics_data():
    """生成示例统计数据用于演示"""
    # 工作流结果
    workflow_results = {
        'GR4J_Calibration': {
            'success_rate': 0.92,
            'total_tasks': 8,
            'execution_time': 245.6
        },
        'XAJ_Calibration': {
            'success_rate': 0.87,
            'total_tasks': 12,
            'execution_time': 356.2
        },
        'GR5J_Evaluation': {
            'success_rate': 0.95,
            'total_tasks': 6,
            'execution_time': 123.8
        },
        'Multi_Model_Comparison': {
            'success_rate': 0.75,
            'total_tasks': 15,
            'execution_time': 567.4
        }
    }

    # 任务结果
    task_results = {}
    task_types = ['prepare_data', 'calibrate_model', 'evaluate_model', 'generate_plots']

    for i in range(50):
        task_id = f'task_{i:03d}'
        task_type = np.random.choice(task_types)
        success_prob = {'prepare_data': 0.98, 'calibrate_model': 0.85,
                       'evaluate_model': 0.92, 'generate_plots': 0.96}

        task_results[task_id] = {
            'type': task_type,
            'success': np.random.rand() < success_prob[task_type],
            'time': np.random.exponential(30 if task_type == 'prepare_data'
                                        else 120 if task_type == 'calibrate_model'
                                        else 60 if task_type == 'evaluate_model'
                                        else 20),
            'error_type': 'none' if np.random.rand() < success_prob[task_type]
                         else np.random.choice(['data_error', 'model_error', 'system_error'])
        }

    # 执行历史
    execution_history = []
    base_time = datetime(2024, 1, 1)

    for i in range(200):
        timestamp = base_time + timedelta(hours=i * 2 + np.random.randint(0, 4))
        success = np.random.rand() < 0.88  # 88% 成功率
        exec_time = np.random.exponential(150)

        execution_history.append({
            'timestamp': timestamp.isoformat(),
            'success': success,
            'execution_time': exec_time,
            'workflow_id': f'workflow_{i % 10}'
        })

    # 对比数据
    comparison_data = {
        'GR4J': {
            'accuracy': 0.85,
            'efficiency': 0.92,
            'reliability': 0.88,
            'robustness': 0.80
        },
        'GR5J': {
            'accuracy': 0.87,
            'efficiency': 0.85,
            'reliability': 0.90,
            'robustness': 0.83
        },
        'XAJ': {
            'accuracy': 0.82,
            'efficiency': 0.78,
            'reliability': 0.85,
            'robustness': 0.88
        },
        'GR6J': {
            'accuracy': 0.89,
            'efficiency': 0.80,
            'reliability': 0.92,
            'robustness': 0.85
        }
    }

    return {
        'workflow_results': workflow_results,
        'task_results': task_results,
        'execution_history': execution_history,
        'comparison_data': comparison_data,
        'comparison_type': 'models',
        'total_workflows': len(workflow_results),
        'overall_success_rate': np.mean([wr['success_rate'] for wr in workflow_results.values()]),
        'avg_execution_time': np.mean([wr['execution_time'] for wr in workflow_results.values()]),
        'system_uptime': 0.976
    }


def demo_hydro_visualization():
    """演示水文模型可视化功能"""
    print("=== 水文模型可视化演示 ===")

    # 生成示例数据
    dates, observed, simulated = generate_sample_hydro_data()

    # 初始化可视化器
    hydro_viz = HydroVisualizer(output_dir="demo_output/hydro")

    # 计算评估指标
    metrics = hydro_viz.calculate_hydro_metrics(observed, simulated)
    print(f"计算得到的水文指标: {metrics}")

    # 1. 生成率定结果对比图
    calibration_path = hydro_viz.plot_calibration_results(
        observed=observed[:1000],  # 前1000天用于率定
        simulated=simulated[:1000],
        dates=dates[:1000],
        model_name="GR4J Model",
        metrics=metrics
    )
    print(f"率定结果图已保存: {calibration_path}")

    # 2. 生成流量历时曲线
    fdc_path = hydro_viz.plot_flow_duration_curve(
        observed=observed,
        simulated=simulated,
        model_name="GR4J Model"
    )
    print(f"流量历时曲线已保存: {fdc_path}")

    # 3. 生成分期水文过程线
    hydrograph_path = hydro_viz.plot_hydrograph_separation(
        observed=observed,
        simulated=simulated,
        dates=dates,
        cal_start='2010-01-01',
        cal_end='2012-12-31',
        val_start='2013-01-01',
        val_end='2015-12-31',
        model_name="GR4J Model"
    )
    print(f"分期水文过程线已保存: {hydrograph_path}")

    # 4. 生成残差分析图
    residual_path = hydro_viz.plot_residual_analysis(
        observed=observed,
        simulated=simulated,
        model_name="GR4J Model"
    )
    print(f"残差分析图已保存: {residual_path}")

    # 5. 生成多模型对比图（模拟数据）
    model_results = {
        'GR4J': {'observed': observed, 'simulated': simulated},
        'XAJ': {'observed': observed, 'simulated': simulated * 0.95 + 5},
        'GR5J': {'observed': observed, 'simulated': simulated * 1.05 - 3}
    }

    comparison_path = hydro_viz.plot_multi_model_comparison(
        model_results=model_results,
        dates=dates
    )
    print(f"多模型对比图已保存: {comparison_path}")


def demo_optimization_visualization():
    """演示优化过程可视化功能"""
    print("\n=== 优化过程可视化演示 ===")

    # 生成示例数据
    opt_data = generate_sample_optimization_data()

    # 初始化可视化器
    opt_viz = OptimizationVisualizer(output_dir="demo_output/optimization")

    # 1. 生成收敛历史图
    conv_path = opt_viz.plot_convergence_history(
        best_values=opt_data['convergence_history']['best_values'],
        mean_values=opt_data['convergence_history']['mean_values'],
        worst_values=opt_data['convergence_history']['worst_values'],
        target_value=opt_data['convergence_history']['target_value'],
        algorithm_name="Genetic Algorithm",
        metric_name="NSE Coefficient"
    )
    print(f"收敛历史图已保存: {conv_path}")

    # 2. 生成参数进化图
    param_path = opt_viz.plot_parameter_evolution(
        parameter_history=opt_data['parameter_history'],
        parameter_ranges=opt_data['parameter_ranges'],
        algorithm_name="Genetic Algorithm"
    )
    print(f"参数进化图已保存: {param_path}")

    # 3. 生成参数相关性矩阵
    corr_path = opt_viz.plot_parameter_correlation_matrix(
        parameter_samples=opt_data['parameter_samples'],
        objective_values=opt_data['objective_values'],
        algorithm_name="Genetic Algorithm"
    )
    print(f"参数相关性矩阵已保存: {corr_path}")

    # 4. 生成综合优化报告
    report_data = {
        'final_best': opt_data['convergence_history']['best_values'][-1],
        'total_generations': len(opt_data['convergence_history']['best_values']),
        'total_evaluations': len(opt_data['convergence_history']['best_values']) * 50,
        'convergence_generation': 60,
        'convergence_history': opt_data['convergence_history'],
        'parameter_history': opt_data['parameter_history'],
        'parameter_ranges': opt_data['parameter_ranges'],
        'parameter_samples': opt_data['parameter_samples'],
        'objective_values': opt_data['objective_values']
    }

    report_path = opt_viz.create_optimization_report(
        optimization_data=report_data,
        algorithm_name="Genetic Algorithm"
    )
    print(f"优化报告已生成: {report_path}")


def demo_statistics_visualization():
    """演示统计分析可视化功能"""
    print("\n=== 统计分析可视化演示 ===")

    # 生成示例数据
    stats_data = generate_sample_statistics_data()

    # 初始化可视化器
    stats_viz = StatisticsVisualizer(output_dir="demo_output/statistics")

    # 1. 生成工作流成功率分析图
    success_path = stats_viz.plot_workflow_success_rates(
        workflow_results=stats_data['workflow_results']
    )
    print(f"工作流成功率分析图已保存: {success_path}")

    # 2. 生成任务性能矩阵图
    task_path = stats_viz.plot_task_performance_matrix(
        task_results=stats_data['task_results']
    )
    print(f"任务性能矩阵图已保存: {task_path}")

    # 3. 生成系统可靠性分析图
    reliability_path = stats_viz.plot_system_reliability_analysis(
        execution_history=stats_data['execution_history']
    )
    print(f"系统可靠性分析图已保存: {reliability_path}")

    # 4. 生成对比分析图
    comparison_path = stats_viz.plot_comparative_analysis(
        comparison_data=stats_data['comparison_data'],
        comparison_type='models'
    )
    print(f"模型对比分析图已保存: {comparison_path}")

    # 5. 生成综合性能分析报告
    report_path = stats_viz.generate_comprehensive_report(
        report_data=stats_data,
        report_title="HydroAgent Performance Analysis"
    )
    print(f"综合分析报告已生成: {report_path}")


def main():
    """主演示函数"""
    print("🌊 HydroAgent 可视化工具演示")
    print("生成论文级别的水文模型分析图表")
    print("=" * 60)

    # 创建输出目录
    Path("demo_output").mkdir(exist_ok=True)

    try:
        # 运行各种演示
        demo_hydro_visualization()
        demo_optimization_visualization()
        demo_statistics_visualization()

        print("\n" + "=" * 60)
        print("✅ 所有演示完成！")
        print("📊 生成的图表保存在 demo_output/ 目录中")
        print("🎯 所有图表均为论文级别质量，可直接用于学术发表")
        print("\n主要特点:")
        print("• 300 DPI 高分辨率，适合论文印刷")
        print("• 专业配色方案和字体设置")
        print("• 支持中英文标签")
        print("• 包含详细的统计分析")
        print("• 自动生成HTML报告")

    except Exception as e:
        print(f"\n❌ 演示过程中出现错误: {e}")
        print("请确保已安装必要的依赖包: matplotlib, seaborn, pandas, numpy, scipy, scikit-learn")


if __name__ == "__main__":
    main()