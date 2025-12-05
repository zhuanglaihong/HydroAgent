"""
Author: Claude
Date: 2025-12-05 15:05:00
LastEditTime: 2025-12-05 15:05:00
LastEditors: Claude
Description: Exp 7 - 大规模任务处理测试 (三个规模: 10/50/100流域)
FilePath: /HydroAgent/experiment/exp_7_large_scale.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import argparse
from pathlib import Path
from base_experiment import create_experiment

# 流域列表 (100个CAMELS流域)
ALL_BASINS = [
    "01013500", "01022500", "01030500", "01031500", "01047000",
    "01052500", "01054200", "01055000", "01057000", "01170100",
    "01181000", "01187300", "01188000", "01195100", "01196500",
    "01208500", "01333000", "01350000", "01411300", "01413500",
    "01414500", "01415000", "01417000", "01418000", "01420500",
    "01423000", "01434000", "01435000", "01436000", "01438500",
    "01440000", "01442500", "01445500", "01447500", "01448000",
    "01449000", "01450500", "01463500", "01466500", "01470500",
    "01473500", "01474500", "01475000", "01481000", "01481500",
    "01487000", "01491000", "01518000", "01520000", "01520500",
    "01532000", "01534000", "01536000", "01539000", "01540500",
    "01541000", "01541500", "01542500", "01542810", "01543000",
    "01544000", "01545000", "01545500", "01546000", "01547000",
    "01548500", "01549500", "01550000", "01551000", "01552000",
    "01553500", "01555000", "01556000", "01557500", "01558000",
    "01559000", "01560000", "01568000", "01570000", "01570500",
    "01571000", "01571500", "01572000", "01573000", "01574000",
    "01576000", "01578310", "01580000", "01580520", "01581000",
    "01582000", "01583000", "01584050", "01585000", "01586000",
    "01589000", "01591000", "01592000", "01594000", "01594100",
]

# 小规模: 10个流域
SMALL_BASINS = ALL_BASINS[:10]
SMALL_QUERY = f"批量率定流域{'、'.join(SMALL_BASINS)}，使用GR4J模型"

# 中规模: 50个流域
MEDIUM_BASINS = ALL_BASINS[:50]
MEDIUM_QUERY = f"批量率定流域{'、'.join(MEDIUM_BASINS)}，使用GR4J模型"

# 大规模: 100个流域
LARGE_BASINS = ALL_BASINS
LARGE_QUERY = f"批量率定流域{'、'.join(LARGE_BASINS)}，使用GR4J模型"


def main():
    """运行 Exp 7: 大规模任务处理测试"""
    parser = argparse.ArgumentParser(description="Exp 7 - 大规模任务处理测试")
    parser.add_argument("--backend", type=str, default="api", choices=["api", "ollama"],
                        help="LLM后端 (默认: api)")
    parser.add_argument("--mock", action="store_true", default=False,
                        help="使用mock模式 (默认: True, 大规模测试建议使用mock)")
    parser.add_argument("--no-mock", dest="mock", action="store_false",
                        help="使用真实hydromodel执行")
    parser.add_argument("--scale", type=str, default="all", choices=["small", "medium", "large", "all"],
                        help="运行哪个规模: small=10流域, medium=50流域, large=100流域, all=全部规模 (默认: all)")
    args = parser.parse_args()

    print("=" * 80)
    print("🧪 Exp 7: 大规模任务处理测试")
    print("=" * 80)
    print(f"🔧 配置:")
    print(f"   - LLM后端: {args.backend}")
    print(f"   - Mock模式: {args.mock}")
    print(f"   - 测试规模: {args.scale}")
    print(f"📝 测试梯度:")
    print(f"   - 小规模: 10个流域")
    print(f"   - 中规模: 50个流域")
    print(f"   - 大规模: 100个流域")
    print(f"⚠️  大规模测试建议使用mock模式以节省时间")
    print("=" * 80)

    results_all = {}
    metrics_all = {}

    if args.scale in ["small", "all"]:
        print("\n" + "="*80)
        print(f"📍 小规模测试: {len(SMALL_BASINS)} 个流域")
        print("="*80)

        exp_small = create_experiment(
            exp_name="exp_7_large_scale_small",
            exp_description="大规模测试-小规模: 10个流域"
        )

        print("\n🚀 开始执行小规模测试...")
        results_small = exp_small.run_batch([SMALL_QUERY], backend=args.backend, use_mock=args.mock)

        print("\n💾 保存结果...")
        exp_small.save_results(results_small)

        print("\n📊 计算指标...")
        metrics_small = exp_small.calculate_metrics(results_small)
        exp_small.save_metrics(metrics_small)

        results_all["small"] = results_small
        metrics_all["small"] = metrics_small

        print(f"\n✅ 小规模测试完成! 成功率: {metrics_small.get('success_rate', 0):.1%}, 耗时: {metrics_small.get('average_time', 0):.2f}s")

    if args.scale in ["medium", "all"]:
        print("\n" + "="*80)
        print(f"📍 中规模测试: {len(MEDIUM_BASINS)} 个流域")
        print("="*80)

        exp_medium = create_experiment(
            exp_name="exp_7_large_scale_medium",
            exp_description="大规模测试-中规模: 50个流域"
        )

        print("\n🚀 开始执行中规模测试...")
        results_medium = exp_medium.run_batch([MEDIUM_QUERY], backend=args.backend, use_mock=args.mock)

        print("\n💾 保存结果...")
        exp_medium.save_results(results_medium)

        print("\n📊 计算指标...")
        metrics_medium = exp_medium.calculate_metrics(results_medium)
        exp_medium.save_metrics(metrics_medium)

        results_all["medium"] = results_medium
        metrics_all["medium"] = metrics_medium

        print(f"\n✅ 中规模测试完成! 成功率: {metrics_medium.get('success_rate', 0):.1%}, 耗时: {metrics_medium.get('average_time', 0):.2f}s")

    if args.scale in ["large", "all"]:
        print("\n" + "="*80)
        print(f"📍 大规模测试: {len(LARGE_BASINS)} 个流域")
        print("="*80)

        exp_large = create_experiment(
            exp_name="exp_7_large_scale_large",
            exp_description="大规模测试-大规模: 100个流域"
        )

        print("\n🚀 开始执行大规模测试...")
        results_large = exp_large.run_batch([LARGE_QUERY], backend=args.backend, use_mock=args.mock)

        print("\n💾 保存结果...")
        exp_large.save_results(results_large)

        print("\n📊 计算指标...")
        metrics_large = exp_large.calculate_metrics(results_large)
        exp_large.save_metrics(metrics_large)

        # 生成汇总报告
        scale_table = "| 规模 | 流域数 | 成功率 | 平均耗时(s) | 总耗时(s) |\n|------|--------|--------|------------|----------|\n"
        for scale in ["small", "medium", "large"]:
            if scale in metrics_all:
                m = metrics_all[scale]
                scale_table += f"| {scale} | {len(SMALL_BASINS) if scale=='small' else len(MEDIUM_BASINS) if scale=='medium' else len(LARGE_BASINS)} | {m.get('success_rate', 0):.1%} | {m.get('average_time', 0):.2f} | {m.get('total_time', 0):.2f} |\n"

        additional_sections = {
            "规模对比分析": f"""
### 规模对比分析

{scale_table}

**性能分析**:
- 总体成功率: {metrics_large.get('success_rate', 0):.1%} @ 100流域 (目标: ≥90%)
- 平均单任务时间: 观察是否随规模线性增长
- 总执行时间: 观察是否符合预期

**资源监控** (需手动记录):
- 内存占用峰值: 应<8GB
- CPU使用率平均: 应<80%
- 磁盘I/O: 记录总量
- 网络流量: 记录API调用次数
""",
            "稳定性评估": f"""
### 稳定性评估

**关键指标**:
- 系统崩溃率: 应为0%
- Checkpoint保存成功率: 应为100%
- 失败分布: 分析失败原因

**可扩展性**:
- 小规模(10) vs 中规模(50): 5倍流域，耗时是否≈5倍？
- 中规模(50) vs 大规模(100): 2倍流域，耗时是否≈2倍？
- 成功率是否随规模下降？

**关键发现**:
- 系统能否稳定处理100个流域？
- 资源占用是否在可接受范围？
- 是否存在明显的性能瓶颈？
"""
        }

        exp_large.generate_report(results_large, metrics_large, additional_sections=additional_sections)

        print("\n📈 生成可视化...")
        exp_large.plot_results(results_large, "success_rate")
        exp_large.plot_results(results_large, "time_distribution")

        results_all["large"] = results_large
        metrics_all["large"] = metrics_large

        print(f"\n✅ 大规模测试完成! 成功率: {metrics_large.get('success_rate', 0):.1%}, 耗时: {metrics_large.get('average_time', 0):.2f}s")

    # 打印汇总信息
    print("\n" + "=" * 80)
    print("🎉 Exp 7 全部完成!")
    print("=" * 80)

    print("\n📊 规模对比总结:")
    for scale, metrics in metrics_all.items():
        basin_count = len(SMALL_BASINS) if scale=="small" else len(MEDIUM_BASINS) if scale=="medium" else len(LARGE_BASINS)
        print(f"   {scale.capitalize()}: {basin_count}个流域, 成功率{metrics.get('success_rate', 0):.1%}, 耗时{metrics.get('average_time', 0):.2f}s")


if __name__ == "__main__":
    main()
