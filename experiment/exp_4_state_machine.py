"""
Author: Claude
Date: 2025-12-05 14:50:00
LastEditTime: 2025-12-05 14:50:00
LastEditors: Claude
Description: Exp 4 - 状态机智能编排测试 (50个任务，覆盖正常和异常场景)
FilePath: /HydroAgent/experiment/exp_4_state_machine.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import argparse
from pathlib import Path
from base_experiment import create_experiment

# 测试集: 50个任务，覆盖正常场景和异常场景（配置错误、执行错误）
TEST_QUERIES = [
    # 正常场景 (30个) - 顺利执行，测试状态转换效率
    "率定GR4J模型，流域01013500",
    "用XAJ率定流域01055000",
    "率定流域01030500的GR4J，使用SCE-UA算法，迭代300轮",
    "用XAJ模型率定流域01031500，scipy算法，种群150",
    "率定GR4J，流域01047000，GA算法，代数200",
    "GR4J率定流域01052500，训练期1990-2000",
    "用XAJ率定流域01054200，测试期2005-2015",
    "率定流域01057000的GR4J，warmup180天",
    "用GR4J模型率定流域01170100",
    "XAJ率定流域01181000",
    "率定GR4J，流域01187300，SCE-UA，迭代400轮",
    "用XAJ率定流域01188000，scipy，种群200",
    "率定流域01195100的GR4J，GA，代数250",
    "GR4J模型率定流域01196500",
    "用XAJ率定流域01208500",
    "率定GR4J，流域01333000，训练期1985-1995",
    "用XAJ模型率定流域01350000，测试期2010-2020",
    "率定流域01411300的GR4J，warmup365天",
    "GR4J率定流域01423000",
    "用XAJ率定流域01434000",
    "率定GR4J模型，流域01440000，SCE-UA，迭代350轮",
    "用XAJ率定流域01445500，scipy，种群180",
    "率定流域01463500的GR4J，GA，代数220",
    "GR4J模型率定流域01466500",
    "用XAJ率定流域01481500",
    "率定GR4J，流域01491000，训练期1992-2002",
    "用XAJ模型率定流域01518000，测试期2008-2013",
    "率定流域01539000的GR4J，warmup270天",
    "GR4J率定流域01542810",
    "用XAJ率定流域01543000",

    # 配置错误场景 (10个) - 触发配置重试
    "率定GR4J模型，流域99999999",  # 不存在的流域
    "用INVALID模型率定流域01013500",  # 无效的模型名
    "率定流域01055000，算法BADALGORITM",  # 无效的算法名
    "用GR4J率定流域01030500，迭代-100轮",  # 负数迭代
    "率定XAJ，流域01031500，训练期2020-2010",  # 训练期时间倒置
    "用GR4J率定流域01047000，测试期1980-1985",  # 测试期早于训练期
    "率定流域01052500的XAJ，warmup9999天",  # warmup过长
    "GR4J率定流域01054200，种群-50",  # 负数种群
    "用XAJ率定流域01057000，代数0",  # 代数为0
    "率定GR4J，流域01170100，SCE-UA，复合体0",  # 复合体为0

    # 执行错误场景 (10个) - 触发执行重试
    # 注意: 这些场景在mock模式下可能不会触发真实错误
    # 但可以在实际执行时测试状态机的错误处理能力
    "率定GR4J模型，流域12025000，迭代5轮",  # 极少迭代可能导致收敛失败
    "用XAJ率定流域14301000，种群5",  # 极小种群可能导致收敛失败
    "率定流域14306500的GR4J，GA，代数5，种群3",  # 极小参数可能失败
    "率定XAJ，流域01181000，训练期1980-1982",  # 极短训练期可能数据不足
    "用GR4J率定流域01187300，测试期2020-2021",  # 可能数据不完整
    "率定流域01188000的XAJ，warmup1天",  # 极短warmup可能影响率定
    "GR4J率定流域01195100，SCE-UA，迭代10轮",  # 迭代太少
    "用XAJ率定流域01196500，scipy，种群10",  # 种群太小
    "率定GR4J，流域01208500，GA，代数10",  # 代数太少
    "率定XAJ模型，流域01333000，SCE-UA，复合体10",  # 复合体太小
]

def main():
    """运行 Exp 4: 状态机智能编排测试"""
    parser = argparse.ArgumentParser(description="Exp 4 - 状态机智能编排测试")
    parser.add_argument("--backend", type=str, default="api", choices=["api", "ollama"],
                        help="LLM后端 (默认: api)")
    parser.add_argument("--mock", action="store_true", default=False,
                        help="使用mock模式 (默认: True)")
    parser.add_argument("--no-mock", dest="mock", action="store_false",
                        help="使用真实hydromodel执行")
    args = parser.parse_args()

    print("=" * 80)
    print("🧪 Exp 4: 状态机智能编排测试")
    print("=" * 80)
    print(f"📋 测试集规模: {len(TEST_QUERIES)} 个任务")
    print(f"   - 正常场景: 30 个（测试状态转换效率）")
    print(f"   - 配置错误场景: 10 个（测试配置重试）")
    print(f"   - 执行错误场景: 10 个（测试执行重试）")
    print(f"🔧 配置:")
    print(f"   - LLM后端: {args.backend}")
    print(f"   - Mock模式: {args.mock}")
    print(f"   - 📝 本实验验证v5.0状态机架构的效率和错误恢复能力")
    print("=" * 80)

    exp = create_experiment(
        exp_name="exp_4_state_machine",
        exp_description="状态机智能编排测试: 验证状态机架构的效率和可维护性"
    )

    print("\n🚀 开始执行测试...")
    results = exp.run_batch(TEST_QUERIES, backend=args.backend, use_mock=args.mock)

    print("\n💾 保存结果...")
    exp.save_results(results)

    print("\n📊 计算评估指标...")
    metrics = exp.calculate_metrics(results)
    exp.save_metrics(metrics)

    print("\n📝 生成实验报告...")

    scenario_types = {
        "正常场景": TEST_QUERIES[:30],
        "配置错误": TEST_QUERIES[30:40],
        "执行错误": TEST_QUERIES[40:50],
    }

    scenario_stats = {}
    for scenario_type, queries in scenario_types.items():
        type_results = [r for r in results if r.get("query", "") in queries]
        scenario_stats[scenario_type] = {
            "total": len(type_results),
            "success": sum(1 for r in type_results if r.get("success", False)),
        }

    scenario_table = "| 场景类型 | 测试数 | 成功数 | 成功率 |\n|---------|--------|--------|--------|\n"
    for scenario_type, stats in scenario_stats.items():
        success_rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0
        scenario_table += f"| {scenario_type} | {stats['total']} | {stats['success']} | {success_rate:.1%} |\n"

    additional_sections = {
        "按场景类型统计": f"""
### 按场景类型统计

{scenario_table}

**分析**:
- 正常场景成功率: 应≥95%
- 配置错误恢复率: 应≥85%
- 执行错误恢复率: 应≥80%
""",
        "状态机效率评估": f"""
### 状态机效率评估

**评估维度**:

1. **状态转换效率**
   - 平均状态转换次数: 记录
   - 状态转换开销: 应<5%
   - 执行时间对比: v5.0 ≈ 基准±5%

2. **错误恢复能力**
   - 配置错误恢复成功率: {scenario_stats['配置错误']['success'] / scenario_stats['配置错误']['total'] if scenario_stats['配置错误']['total'] > 0 else 0:.1%}
   - 执行错误恢复成功率: {scenario_stats['执行错误']['success'] / scenario_stats['执行错误']['total'] if scenario_stats['执行错误']['total'] > 0 else 0:.1%}
   - 平均恢复时间: 记录

3. **状态流分析**
   - 正常流程: IDLE → RECOGNIZING_INTENT → PLANNING_TASKS → 
               GENERATING_CONFIG → EXECUTING_CALIBRATION → 
               ANALYZING_RESULTS → COMPLETED
   - 配置错误流程: ... → GENERATING_CONFIG → CONFIG_RETRY → GENERATING_CONFIG → ...
   - 执行错误流程: ... → EXECUTING_CALIBRATION → EXECUTION_RETRY → EXECUTING_CALIBRATION → ...

**关键发现**:
- 状态机架构是否提升了系统的可维护性？
- 错误恢复是否比简单重试更高效？
- 状态转换开销是否可接受？
"""
    }

    exp.generate_report(results, metrics, additional_sections=additional_sections)

    print("\n📈 生成可视化...")
    exp.plot_results(results, "success_rate")
    exp.plot_results(results, "time_distribution")

    print("\n" + "=" * 80)
    print("✅ Exp 4 完成!")
    print(f"📁 结果目录: {exp.workspace}")
    print("=" * 80)

    print("\n📊 关键指标:")
    print(f"   总体成功率: {metrics.get('success_rate', 0):.1%}")
    print(f"   平均耗时: {metrics.get('average_time', 0):.2f}s")

    print("\n📊 按场景类型统计:")
    for scenario_type, stats in scenario_stats.items():
        success_rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0
        print(f"   {scenario_type}: {stats['success']}/{stats['total']} ({success_rate:.1%})")

    if metrics.get('ci_95_lower') is not None:
        print(f"\n   95%置信区间: [{metrics['ci_95_lower']:.1%}, {metrics['ci_95_upper']:.1%}]")


if __name__ == "__main__":
    main()
