"""
Author: Claude
Date: 2025-12-04 10:35:00
LastEditTime: 2025-12-05 14:00:00
LastEditors: Claude
Description: Exp 1b - 算法×模型全覆盖测试 (3算法×4模型×3流域 = 36组合)
FilePath: /HydroAgent/experiment/exp_1b_algorithm_model_coverage.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import argparse
from pathlib import Path
from base_experiment import create_experiment

# 测试矩阵
ALGORITHMS = ["SCE_UA", "scipy", "GA"]
MODELS = ["XAJ", "gr4j", "gr5j", "gr6j"]
BASINS = ["12025000", "14301000", "14306500"]

# 生成测试查询 (3×4×3 = 36个组合)
TEST_QUERIES = []

# 为每个组合生成查询（使用不同的措辞）
query_templates = [
    "率定{model}模型，流域{basin}，使用{algorithm}算法",
    "用{algorithm}算法率定流域{basin}的{model}模型",
    "流域{basin}，{model}率定，算法用{algorithm}",
    "{model}模型率定，流域{basin}，{algorithm}算法",
]

idx = 0
for algorithm in ALGORITHMS:
    for model in MODELS:
        for basin in BASINS:
            template = query_templates[idx % len(query_templates)]
            query = template.format(model=model, basin=basin, algorithm=algorithm)
            TEST_QUERIES.append(query)
            idx += 1


def main():
    """运行 Exp 1b: 算法×模型全覆盖测试"""
    parser = argparse.ArgumentParser(description="Exp 1b - 算法×模型全覆盖测试")
    parser.add_argument("--backend", type=str, default="api", choices=["api", "ollama"],
                        help="LLM后端 (默认: api)")
    parser.add_argument("--mock", action="store_true", default=False,
                        help="使用mock模式 (默认: True)")
    parser.add_argument("--no-mock", dest="mock", action="store_false",
                        help="使用真实hydromodel执行")
    args = parser.parse_args()

    print("=" * 80)
    print("🧪 Exp 1b: 算法×模型全覆盖测试")
    print("=" * 80)
    print(f"📋 测试集规模: {len(TEST_QUERIES)} 个组合")
    print(f"   - 算法: {', '.join(ALGORITHMS)} (3种)")
    print(f"   - 模型: {', '.join(MODELS)} (4种)")
    print(f"   - 流域: {', '.join(BASINS)} (3个)")
    print(f"   - 总组合: {len(ALGORITHMS)} × {len(MODELS)} × {len(BASINS)} = {len(TEST_QUERIES)}")
    print(f"🔧 配置:")
    print(f"   - LLM后端: {args.backend}")
    print(f"   - Mock模式: {args.mock}")
    print("=" * 80)

    # 创建实验
    exp = create_experiment(
        exp_name="exp_1b_algorithm_model_coverage",
        exp_description="算法×模型全覆盖测试: 验证系统对所有算法和模型组合的支持能力"
    )

    # 批量执行
    print("\n🚀 开始执行测试...")
    results = exp.run_batch(TEST_QUERIES, backend=args.backend, use_mock=args.mock)

    # 保存结果
    print("\n💾 保存结果...")
    exp.save_results(results)

    # 计算指标
    print("\n📊 计算评估指标...")
    metrics = exp.calculate_metrics(results)
    exp.save_metrics(metrics)

    # 生成报告
    print("\n📝 生成实验报告...")

    # 添加额外的分析 - 按算法和模型统计
    algo_stats = {}
    model_stats = {}

    for algo in ALGORITHMS:
        algo_results = [r for r in results if algo in r.get("query", "")]
        algo_stats[algo] = {
            "total": len(algo_results),
            "success": sum(1 for r in algo_results if r.get("success", False)),
            "success_rate": sum(1 for r in algo_results if r.get("success", False)) / len(algo_results) if algo_results else 0
        }

    for model in MODELS:
        model_results = [r for r in results if model in r.get("query", "").lower()]
        model_stats[model] = {
            "total": len(model_results),
            "success": sum(1 for r in model_results if r.get("success", False)),
            "success_rate": sum(1 for r in model_results if r.get("success", False)) / len(model_results) if model_results else 0
        }

    # 生成算法统计表格
    algo_table = "| 算法 | 测试数 | 成功数 | 成功率 |\n|------|--------|--------|--------|\n"
    for algo in ALGORITHMS:
        stats = algo_stats[algo]
        algo_table += f"| {algo} | {stats['total']} | {stats['success']} | {stats['success_rate']:.1%} |\n"

    # 生成模型统计表格
    model_table = "| 模型 | 测试数 | 成功数 | 成功率 |\n|------|--------|--------|--------|\n"
    for model in MODELS:
        stats = model_stats[model]
        model_table += f"| {model} | {stats['total']} | {stats['success']} | {stats['success_rate']:.1%} |\n"

    additional_sections = {
        "按算法统计": f"""
### 按算法统计

{algo_table}

**分析**:
- 测试了 {len(ALGORITHMS)} 种算法，每种算法 {len(MODELS) * len(BASINS)} 个测试
- 算法成功率对比:
  - SCE_UA: {algo_stats['SCE_UA']['success_rate']:.1%}
  - scipy: {algo_stats['scipy']['success_rate']:.1%}
  - GA: {algo_stats['GA']['success_rate']:.1%}
""",
        "按模型统计": f"""
### 按模型统计

{model_table}

**分析**:
- 测试了 {len(MODELS)} 种模型，每种模型 {len(ALGORITHMS) * len(BASINS)} 个测试
- 模型成功率对比:
  - XAJ: {model_stats['XAJ']['success_rate']:.1%}
  - gr4j: {model_stats['gr4j']['success_rate']:.1%}
  - gr5j: {model_stats['gr5j']['success_rate']:.1%}
  - gr6j: {model_stats['gr6j']['success_rate']:.1%}
""",
        "覆盖度分析": f"""
### 覆盖度分析

**测试矩阵完整性**:
- 算法覆盖: {len(ALGORITHMS)}/3 (SCE_UA, scipy, GA)
- 模型覆盖: {len(MODELS)}/4 (XAJ, gr4j, gr5j, gr6j)
- 流域覆盖: {len(BASINS)}/3 (12025000, 14301000, 14306500)
- 总组合数: {len(TEST_QUERIES)}

**关键发现**:
- 系统是否支持所有算法×模型组合？
- 是否存在特定组合的失败模式？
- 不同流域的成功率是否一致？

**建议**:
- 如果某个算法成功率明显低于其他算法，需要检查该算法的参数配置
- 如果某个模型成功率明显低于其他模型，需要检查模型的参数范围设置
- 关注失败案例的共同特征（算法、模型、流域）
"""
    }

    exp.generate_report(results, metrics, additional_sections=additional_sections)

    # 生成可视化
    print("\n📈 生成可视化...")
    exp.plot_results(results, "success_rate")
    exp.plot_results(results, "time_distribution")

    print("\n" + "=" * 80)
    print("✅ Exp 1b 完成!")
    print(f"📁 结果目录: {exp.workspace}")
    print(f"   ├─ session_*/           # HydroAgent 执行记录")
    print(f"   ├─ figures/             # 汇总图表")
    print(f"   ├─ data/                # 汇总数据")
    print(f"   ├─ results.json         # 详细结果")
    print(f"   ├─ results.csv          # 表格数据")
    print(f"   ├─ metrics.json         # 评估指标")
    print(f"   ├─ report.md            # 实验报告")
    print(f"   └─ *.png                # 可视化图表")
    print("=" * 80)

    # 打印关键指标
    print("\n📊 关键指标:")
    print(f"   总体成功率: {metrics.get('success_rate', 0):.1%}")
    print(f"   平均耗时: {metrics.get('average_time', 0):.2f}s")
    print(f"   中位数耗时: {metrics.get('median_time', 0):.2f}s")

    print("\n📊 按算法统计:")
    for algo in ALGORITHMS:
        stats = algo_stats[algo]
        print(f"   {algo}: {stats['success']}/{stats['total']} ({stats['success_rate']:.1%})")

    print("\n📊 按模型统计:")
    for model in MODELS:
        stats = model_stats[model]
        print(f"   {model}: {stats['success']}/{stats['total']} ({stats['success_rate']:.1%})")

    if metrics.get('ci_95_lower') is not None:
        print(f"\n   95%置信区间: [{metrics['ci_95_lower']:.1%}, {metrics['ci_95_upper']:.1%}]")


if __name__ == "__main__":
    main()
