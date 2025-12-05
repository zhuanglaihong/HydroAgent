"""
Author: Claude
Date: 2025-12-04 10:30:00
LastEditTime: 2025-12-04 10:30:00
LastEditors: Claude
Description: Exp 1a - 标准率定测试 (40个基础率定任务: 20 GR4J + 20 XAJ)
FilePath: /HydroAgent/experiment/exp_1a_standard_calibration.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import argparse
from pathlib import Path
from base_experiment import create_experiment

# 测试集: 40个标准率定查询
TEST_QUERIES = [
    # GR4J 标准率定 (20个)
    "率定GR4J模型，流域01539000",
    "用GR4J率定流域02070000",
    "率定流域03346000，模型用GR4J",
    "GR4J模型率定，流域03500000",
    "率定GR4J，流域11532500",
    "用GR4J模型率定流域12145500",
    "流域12025000，率定GR4J模型",
    "率定流域14306500的GR4J模型",
    "GR4J率定，流域14301000",
    "用GR4J率定流域11532500",
    "率定GR4J模型，流域12145500",
    "流域12145500，率定GR4J",
    "GR4J模型率定流域01195100",
    "率定流域12025000，用GR4J",
    "流域12145500的GR4J率定",
    "率定GR4J，流域03500000",
    "用GR4J率定流域01539000",
    "GR4J率定流域03346000",
    "流域14306500，率定GR4J模型",
    "率定流域14301000的GR4J",

    # XAJ 标准率定 (20个)
    "率定XAJ模型，流域01539000",
    "用XAJ率定流域02070000",
    "率定流域02177000，模型用XAJ",
    "XAJ模型率定，流域03346000",
    "率定XAJ，流域03500000",
    "用XAJ模型率定流域11532500",
    "流域12145500，率定XAJ模型",
    "率定流域12025000的XAJ模型",
    "XAJ率定，流域14301000",
    "用XAJ率定流域14306500",
    "率定XAJ模型，流域12145500",
    "流域12145500，率定XAJ",
    "XAJ模型率定流域01195100",
    "率定流域12025000，用XAJ",
    "流域12145500的XAJ率定",
    "率定XAJ，流域03500000",
    "用XAJ率定流域01539000",
    "XAJ率定流域03346000",
    "流域14306500，率定XAJ模型",
    "率定流域14301000的XAJ",
]


def main():
    """运行 Exp 1a: 标准率定测试"""
    parser = argparse.ArgumentParser(description="Exp 1a - 标准率定测试")
    parser.add_argument("--backend", type=str, default="api", choices=["api", "ollama"],
                        help="LLM后端 (默认: api)")
    parser.add_argument("--mock", action="store_true", default=False,
                        help="使用mock模式 (默认: True)")
    parser.add_argument("--no-mock", dest="mock", action="store_false",
                        help="使用真实hydromodel执行")
    args = parser.parse_args()

    print("=" * 80)
    print("🧪 Exp 1a: 标准率定测试")
    print("=" * 80)
    print(f"📋 测试集规模: {len(TEST_QUERIES)} 个查询")
    print(f"   - GR4J: 20 个")
    print(f"   - XAJ: 20 个")
    print(f"🔧 配置:")
    print(f"   - LLM后端: {args.backend}")
    print(f"   - Mock模式: {args.mock}")
    print("=" * 80)

    # 创建实验
    exp = create_experiment(
        exp_name="exp_1a_standard_calibration",
        exp_description="标准率定测试: 验证系统对基础率定任务的处理能力"
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

    # 添加额外的分析
    gr4j_results = [r for r in results if "GR4J" in r.get("query", "").upper()]
    xaj_results = [r for r in results if "XAJ" in r.get("query", "").upper()]

    gr4j_success = sum(1 for r in gr4j_results if r.get("success", False))
    xaj_success = sum(1 for r in xaj_results if r.get("success", False))

    additional_sections = {
        "模型分析": f"""
### 按模型统计

| 模型 | 测试数 | 成功数 | 成功率 |
|------|--------|--------|--------|
| GR4J | {len(gr4j_results)} | {gr4j_success} | {gr4j_success/len(gr4j_results):.1%} |
| XAJ  | {len(xaj_results)} | {xaj_success} | {xaj_success/len(xaj_results):.1%} |

**分析**:
- GR4J 模型成功率: {gr4j_success/len(gr4j_results):.1%}
- XAJ 模型成功率: {xaj_success/len(xaj_results):.1%}
"""
    }

    exp.generate_report(results, metrics, additional_sections=additional_sections)

    # 生成可视化
    print("\n📈 生成可视化...")
    exp.plot_results(results, "success_rate")
    exp.plot_results(results, "time_distribution")

    print("\n" + "=" * 80)
    print("✅ Exp 1a 完成!")
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
    print(f"   成功率: {metrics.get('success_rate', 0):.1%}")
    print(f"   平均耗时: {metrics.get('average_time', 0):.2f}s")
    print(f"   中位数耗时: {metrics.get('median_time', 0):.2f}s")

    if metrics.get('ci_95_lower') is not None:
        print(f"   95%置信区间: [{metrics['ci_95_lower']:.1%}, {metrics['ci_95_upper']:.1%}]")


if __name__ == "__main__":
    main()
