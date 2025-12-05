"""
Author: Claude
Date: 2025-12-05 14:35:00
LastEditTime: 2025-12-05 14:35:00
LastEditors: Claude
Description: Exp 1d - 批量处理测试 (10个多流域批量率定任务)
FilePath: /HydroAgent/experiment/exp_1d_batch_processing.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import argparse
from pathlib import Path
from base_experiment import create_experiment

# 测试集: 10个批量处理查询（多流域同时率定）
TEST_QUERIES = [
    # 2个流域 (3个)
    "率定GR4J模型，流域02177000和03346000",
    "用XAJ率定流域11532500、12145500",
    "率定流域14301000和14306500的GR4J模型",

    # 3个流域 (3个)
    "GR4J率定流域01539000、02070000、02177000",
    "用XAJ模型率定流域03346000、03500000、11532500",
    "率定流域12145500、12025000、14301000，模型用GR4J",

    # 4个流域 (2个)
    "率定GR4J模型，流域12025000,14301000,14306500,14325000",
    "用XAJ率定流域02070000,02177000,03346000,03500000",

    # 5个流域 (2个)
    "批量率定流域01539000,02070000,02177000,03346000,03500000使用GR4J模型",
    "用XAJ模型批量率定流域11532500,12025000,14301000,14306500,14325000",
]


def main():
    """运行 Exp 1d: 批量处理测试"""
    parser = argparse.ArgumentParser(description="Exp 1d - 批量处理测试")
    parser.add_argument("--backend", type=str, default="api", choices=["api", "ollama"],
                        help="LLM后端 (默认: api)")
    parser.add_argument("--mock", action="store_true", default=False,
                        help="使用mock模式 (默认: True)")
    parser.add_argument("--no-mock", dest="mock", action="store_false",
                        help="使用真实hydromodel执行")
    args = parser.parse_args()

    print("=" * 80)
    print("🧪 Exp 1d: 批量处理测试")
    print("=" * 80)
    print(f"📋 测试集规模: {len(TEST_QUERIES)} 个查询")
    print(f"   - 2个流域: 3 个查询")
    print(f"   - 3个流域: 3 个查询")
    print(f"   - 4个流域: 2 个查询")
    print(f"   - 5个流域: 2 个查询")
    print(f"   - 总流域数: 30+ 个")
    print(f"🔧 配置:")
    print(f"   - LLM后端: {args.backend}")
    print(f"   - Mock模式: {args.mock}")
    print("=" * 80)

    # 创建实验
    exp = create_experiment(
        exp_name="exp_1d_batch_processing",
        exp_description="批量处理测试: 验证系统对多流域批量率定的处理能力"
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

    # 按流域数量统计
    def count_basins(query):
        """统计查询中包含的流域数量"""
        import re
        basins = re.findall(r'\d{8}', query)
        return len(basins)

    basin_counts = {}
    for r in results:
        count = count_basins(r.get("query", ""))
        if count not in basin_counts:
            basin_counts[count] = {"total": 0, "success": 0}
        basin_counts[count]["total"] += 1
        if r.get("success", False):
            basin_counts[count]["success"] += 1

    # 生成流域数量统计表格
    basin_table = "| 流域数 | 测试数 | 成功数 | 成功率 |\n|--------|--------|--------|--------|\n"
    for count in sorted(basin_counts.keys()):
        stats = basin_counts[count]
        success_rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0
        basin_table += f"| {count} | {stats['total']} | {stats['success']} | {success_rate:.1%} |\n"

    additional_sections = {
        "按流域数量统计": f"""
### 按流域数量统计

{basin_table}

**分析**:
- 测试了 2-5 个流域的批量率定场景
- 验证系统对多流域批量处理的支持能力
- 观察成功率是否随流域数量增加而下降
""",
        "批量处理能力评估": f"""
### 批量处理能力评估

**1. 流域列表解析**
- IntentAgent能否正确识别多个流域ID？
- 流域分隔符识别（顿号、逗号、"和"、"、"）是否准确？

**2. 任务拆解能力**
- TaskPlanner能否将批量任务拆解为多个独立的率定子任务？
- 每个流域是否都生成了对应的subtask？

**3. 配置生成正确性**
- ConfigAgent为每个流域生成的配置是否正确？
- basin_ids列表是否完整？

**4. 执行稳定性**
- 批量执行时是否稳定？
- 是否存在某个流域失败导致整体失败的情况？

**5. 结果汇总**
- DeveloperAgent能否汇总多个流域的率定结果？
- 报告是否包含所有流域的性能指标？

**关键指标**:
- 流域列表解析准确率: 应≥95%
- 批量任务拆解成功率: 应≥90%
- 整体执行成功率: 应≥85%

**期望观察**:
- 小批量（2-3流域）成功率应≥90%
- 中批量（4-5流域）成功率应≥80%
- 成功率不应随流域数量线性下降（如果下降明显，说明存在稳定性问题）
"""
    }

    exp.generate_report(results, metrics, additional_sections=additional_sections)

    # 生成可视化
    print("\n📈 生成可视化...")
    exp.plot_results(results, "success_rate")
    exp.plot_results(results, "time_distribution")

    print("\n" + "=" * 80)
    print("✅ Exp 1d 完成!")
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

    print("\n📊 按流域数量统计:")
    for count in sorted(basin_counts.keys()):
        stats = basin_counts[count]
        success_rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0
        print(f"   {count}个流域: {stats['success']}/{stats['total']} ({success_rate:.1%})")

    if metrics.get('ci_95_lower') is not None:
        print(f"\n   95%置信区间: [{metrics['ci_95_lower']:.1%}, {metrics['ci_95_upper']:.1%}]")


if __name__ == "__main__":
    main()
