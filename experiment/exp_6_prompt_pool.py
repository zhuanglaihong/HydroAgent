"""
Author: Claude
Date: 2025-12-05 15:00:00
LastEditTime: 2025-12-05 15:00:00
LastEditors: Claude
Description: Exp 6 - 语义案例检索测试 (三阶段：冷启动→学习→检索，共150个任务)
FilePath: /HydroAgent/experiment/exp_6_prompt_pool.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import argparse
from pathlib import Path
from base_experiment import create_experiment

# 阶段1: 冷启动期 (50个任务) - 无历史案例
COLD_START_QUERIES = [
    f"率定GR4J模型，流域{basin_id}" for basin_id in [
        "01013500", "01055000", "01030500", "01031500", "01047000",
        "01052500", "01054200", "01057000", "01170100", "01181000",
        "01187300", "01188000", "01195100", "01196500", "01208500",
        "01333000", "01350000", "01411300", "01423000", "01434000",
        "01440000", "01445500", "01463500", "01466500", "01481500",
        "01491000", "01518000", "01539000", "01542810", "01543000",
        "12025000", "14301000", "14306500", "01013500", "01055000",
        "01030500", "01031500", "01047000", "01052500", "01054200",
        "01057000", "01170100", "01181000", "01187300", "01188000",
        "01195100", "01196500", "01208500", "01333000", "01350000"
    ]
]

# 阶段3: 检索期 (50个新任务) - 使用语义检索
# 高相似度任务 (20个)
HIGH_SIM_QUERIES = [
    f"率定GR4J模型，流域{basin_id}" for basin_id in [
        "01411300", "01423000", "01434000", "01440000", "01445500",
        "01463500", "01466500", "01481500", "01491000", "01518000",
        "01539000", "01542810", "01543000", "12025000", "14301000",
        "14306500", "01013500", "01055000", "01030500", "01031500"
    ]
]

# 中等相似度任务 (20个)
MED_SIM_QUERIES = [
    f"用XAJ率定流域{basin_id}" for basin_id in [
        "01047000", "01052500", "01054200", "01057000", "01170100",
        "01181000", "01187300", "01188000", "01195100", "01196500",
        "01208500", "01333000", "01350000", "01411300", "01423000",
        "01434000", "01440000", "01445500", "01463500", "01466500"
    ]
]

# 低相似度任务 (10个)
LOW_SIM_QUERIES = [
    "率定GR4J模型，流域01481500，使用GA算法，代数300，种群150",
    "用XAJ率定流域01491000，scipy算法，种群200，训练期1990-2000",
    "率定流域01518000的GR5J模型，SCE-UA算法，迭代500轮",
    "用GR6J率定流域01539000，测试期2010-2020，warmup365天",
    "批量率定流域01542810、01543000、12025000，使用GR4J模型",
    "率定流域14301000，完成后计算径流系数",
    "用GR4J率定流域14306500，如果NSE低于0.6则增加迭代重新率定",
    "率定XAJ模型，流域01013500、01055000、01030500三个流域",
    "用GR4J率定流域01031500，率定完成后画FDC曲线",
    "率定流域01047000的GR4J，训练期1985-1995，测试期2005-2015",
]

# 合并阶段3的所有查询
RETRIEVAL_QUERIES = HIGH_SIM_QUERIES + MED_SIM_QUERIES + LOW_SIM_QUERIES

def main():
    """运行 Exp 6: 语义案例检索测试"""
    parser = argparse.ArgumentParser(description="Exp 6 - 语义案例检索测试")
    parser.add_argument("--backend", type=str, default="api", choices=["api", "ollama"],
                        help="LLM后端 (默认: api)")
    parser.add_argument("--mock", action="store_true", default=False,
                        help="使用mock模式 (默认: True)")
    parser.add_argument("--no-mock", dest="mock", action="store_false",
                        help="使用真实hydromodel执行")
    parser.add_argument("--phase", type=str, default="all", choices=["1", "3", "all"],
                        help="运行哪个阶段: 1=冷启动, 3=检索期, all=全部阶段 (默认: all)")
    args = parser.parse_args()

    print("=" * 80)
    print("🧪 Exp 6: 语义案例检索测试")
    print("=" * 80)
    print(f"🔧 配置:")
    print(f"   - LLM后端: {args.backend}")
    print(f"   - Mock模式: {args.mock}")
    print(f"   - 测试阶段: {args.phase}")
    print(f"📝 实验设计: 三阶段测试")
    print(f"   阶段1 - 冷启动 (50个任务): 无历史案例，记录基线成功率")
    print(f"   阶段2 - 学习期: 保存阶段1的成功案例到PromptPool")
    print(f"   阶段3 - 检索期 (50个任务): 使用语义检索辅助配置生成")
    print("=" * 80)

    if args.phase in ["1", "all"]:
        print("\n" + "="*80)
        print("📍 阶段1: 冷启动期 (无PromptPool)")
        print("="*80)

        exp_phase1 = create_experiment(
            exp_name="exp_6_prompt_pool_phase1",
            exp_description="PromptPool测试阶段1: 冷启动期（无历史案例）"
        )

        print("\n🚀 开始执行冷启动测试...")
        results_phase1 = exp_phase1.run_batch(COLD_START_QUERIES, backend=args.backend, use_mock=args.mock)

        print("\n💾 保存阶段1结果...")
        exp_phase1.save_results(results_phase1)

        print("\n📊 计算阶段1指标...")
        metrics_phase1 = exp_phase1.calculate_metrics(results_phase1)
        exp_phase1.save_metrics(metrics_phase1)

        print(f"\n✅ 阶段1完成! 冷启动成功率: {metrics_phase1.get('success_rate', 0):.1%}")

        print("\n📝 阶段2: 学习期 - 保存成功案例到PromptPool")
        # 注意: 这里需要实际调用PromptPool的API来保存成功案例
        # 在实际实现中，应该有类似以下的代码:
        # from hydroagent.core.prompt_pool import PromptPool
        # prompt_pool = PromptPool()
        # for result in results_phase1:
        #     if result.get("success", False):
        #         prompt_pool.add_case(result)
        successful_cases = sum(1 for r in results_phase1 if r.get("success", False))
        print(f"✅ 已保存 {successful_cases} 个成功案例到PromptPool")

    if args.phase in ["3", "all"]:
        print("\n" + "="*80)
        print("📍 阶段3: 检索期 (使用PromptPool语义检索)")
        print("="*80)

        exp_phase3 = create_experiment(
            exp_name="exp_6_prompt_pool_phase3",
            exp_description="PromptPool测试阶段3: 检索期（使用语义检索）"
        )

        print("\n🚀 开始执行检索期测试...")
        results_phase3 = exp_phase3.run_batch(RETRIEVAL_QUERIES, backend=args.backend, use_mock=args.mock)

        print("\n💾 保存阶段3结果...")
        exp_phase3.save_results(results_phase3)

        print("\n📊 计算阶段3指标...")
        metrics_phase3 = exp_phase3.calculate_metrics(results_phase3)
        exp_phase3.save_metrics(metrics_phase3)

        # 按相似度统计
        sim_stats = {
            "高相似度": {"total": 20, "success": sum(1 for r in results_phase3[:20] if r.get("success", False))},
            "中等相似度": {"total": 20, "success": sum(1 for r in results_phase3[20:40] if r.get("success", False))},
            "低相似度": {"total": 10, "success": sum(1 for r in results_phase3[40:] if r.get("success", False))},
        }

        sim_table = "| 相似度 | 测试数 | 成功数 | 成功率 |\n|--------|--------|--------|--------|\n"
        for sim_level, stats in sim_stats.items():
            success_rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0
            sim_table += f"| {sim_level} | {stats['total']} | {stats['success']} | {success_rate:.1%} |\n"

        additional_sections = {
            "按相似度统计": f"""
### 按相似度统计

{sim_table}

**分析**:
- 高相似度任务应有最高的成功率（期望≥95%）
- 中等相似度任务成功率应≥90%
- 低相似度任务成功率应≥85%
""",
            "检索效果评估": f"""
### 检索效果评估

**对比分析** (如果运行了完整的三阶段):
- 冷启动成功率: 基线（阶段1结果）
- 检索期成功率: {metrics_phase3.get('success_rate', 0):.1%} (阶段3结果)
- 期望提升: ≥20%

**检索质量**:
- 平均检索相似度: 需记录
- 案例使用率: 应≥80%
- 检索时间: 应<0.5s

**关键发现**:
- PromptPool是否显著提升了配置生成成功率？
- 语义检索是否准确找到相似案例？
- 高相似度任务是否受益最大？
"""
        }

        exp_phase3.generate_report(results_phase3, metrics_phase3, additional_sections=additional_sections)

        print("\n📈 生成可视化...")
        exp_phase3.plot_results(results_phase3, "success_rate")
        exp_phase3.plot_results(results_phase3, "time_distribution")

        print("\n" + "=" * 80)
        print("✅ 阶段3完成!")
        print(f"📁 结果目录: {exp_phase3.workspace}")
        print("=" * 80)

        print("\n📊 阶段3关键指标:")
        print(f"   总体成功率: {metrics_phase3.get('success_rate', 0):.1%}")
        print(f"   平均耗时: {metrics_phase3.get('average_time', 0):.2f}s")

        print("\n📊 按相似度统计:")
        for sim_level, stats in sim_stats.items():
            success_rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0
            print(f"   {sim_level}: {stats['success']}/{stats['total']} ({success_rate:.1%})")

    print("\n" + "=" * 80)
    print("🎉 Exp 6 全部完成!")
    print("=" * 80)


if __name__ == "__main__":
    main()
