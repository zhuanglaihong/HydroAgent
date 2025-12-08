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

# 测试集: 10个批量处理查询
TEST_QUERIES = [
    # Group 1: 基础多流域批量率定 (2-3个流域)
    "率定GR4J模型，流域02177000和03346000",
    "用XAJ率定流域11532500、12145500",
    "率定流域14301000和14306500的GR4J模型",

    # Group 2: 中等批量率定 (5个流域)
    "GR4J率定流域01539000,02070000,02177000,03346000,03500000",
    "用XAJ模型率定流域11532500,12025000,14301000,14306500,14325000",
    "率定流域11532500和12025000、12145500、12025000、14301000，模型用GR5J",

    # Group 3: 多流域+代码生成
    "率定流域01539000和02070000的GR4J模型，完成后计算径流系数",
    "用XAJ率定流域03346000、03500000，然后画出FDC曲线",

    # Group 4: 多流域+迭代优化 
    "率定流域11532500和12025000的GR4J模型，如果参数收敛到边界就调整范围重新率定",
    "用XAJ率定流域14301000、14306500，采用两阶段迭代优化策略",
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
    print("🧪 Exp 1d: 批量处理与组合功能测试")
    print("=" * 80)
    print(f"📋 测试集规模: {len(TEST_QUERIES)} 个查询")
    print(f"   - Group 1: 基础多流域批量率定 (3个查询, 2-3流域)")
    print(f"   - Group 2: 中等批量率定 (3个查询, 3流域)")
    print(f"   - Group 3: 多流域+代码生成 (2个查询, 测试Exp4功能)")
    print(f"   - Group 4: 多流域+迭代优化 (2个查询, 测试Exp3功能)")
    print(f"   - 总流域数: ~20 个")
    print(f"🔧 配置:")
    print(f"   - LLM后端: {args.backend}")
    print(f"   - Mock模式: {args.mock}")
    print("=" * 80)

    # 创建实验
    exp = create_experiment(
        exp_name="exp_1d_batch_processing",
        exp_description="批量处理与组合功能测试: 验证多流域批量率定及其与代码生成、迭代优化功能的组合能力"
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

    # 统计分析
    def count_basins(query):
        """统计查询中包含的流域数量"""
        import re
        basins = re.findall(r'\d{8}', query)
        return len(basins)

    def detect_query_type(query):
        """检测查询类型"""
        q_lower = query.lower()
        if "径流系数" in q_lower or "fdc" in q_lower or "画" in q_lower or "完成后" in q_lower:
            return "多流域+代码生成"
        elif "边界" in q_lower or "迭代优化" in q_lower or "两阶段" in q_lower or "调整范围" in q_lower:
            return "多流域+迭代优化"
        else:
            return "基础批量率定"

    basin_counts = {}
    query_type_counts = {}

    for r in results:
        query = r.get("query", "")
        count = count_basins(query)
        query_type = detect_query_type(query)

        # 流域数量统计
        if count not in basin_counts:
            basin_counts[count] = {"total": 0, "success": 0}
        basin_counts[count]["total"] += 1
        if r.get("success", False):
            basin_counts[count]["success"] += 1

        # 查询类型统计
        if query_type not in query_type_counts:
            query_type_counts[query_type] = {"total": 0, "success": 0}
        query_type_counts[query_type]["total"] += 1
        if r.get("success", False):
            query_type_counts[query_type]["success"] += 1

    # 生成流域数量统计表格
    basin_table = "| 流域数 | 测试数 | 成功数 | 成功率 |\n|--------|--------|--------|--------|\n"
    for count in sorted(basin_counts.keys()):
        stats = basin_counts[count]
        success_rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0
        basin_table += f"| {count} | {stats['total']} | {stats['success']} | {success_rate:.1%} |\n"

    # 生成查询类型统计表格
    type_table = "| 查询类型 | 测试数 | 成功数 | 成功率 |\n|----------|--------|--------|--------|\n"
    for qtype in ["基础批量率定", "多流域+代码生成", "多流域+迭代优化"]:
        if qtype in query_type_counts:
            stats = query_type_counts[qtype]
            success_rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0
            type_table += f"| {qtype} | {stats['total']} | {stats['success']} | {success_rate:.1%} |\n"

    additional_sections = {
        "按流域数量统计": f"""
### 按流域数量统计

{basin_table}

**分析**:
- 测试了 2-3 个流域的批量率定场景
- 验证系统对多流域批量处理的支持能力
- 观察成功率是否随流域数量增加而下降
""",
        "按查询类型统计": f"""
### 按查询类型统计

{type_table}

**分析**:
- **基础批量率定**: 纯多流域批量率定（6个查询）
- **多流域+代码生成**: 批量率定后生成分析代码（2个查询，测试Exp4功能组合）
- **多流域+迭代优化**: 批量率定使用迭代优化策略（2个查询，测试Exp3功能组合）

**关键观察**:
- 基础批量率定应达到最高成功率（≥90%）
- 组合功能测试验证系统的功能集成能力
- 多流域+代码生成测试是否能为每个流域生成独立的分析脚本
- 多流域+迭代优化测试是否能对每个流域独立进行参数范围调整
""",
        "批量处理能力评估": f"""
### 批量处理能力评估

**1. 流域列表解析（IntentAgent）**
- 能否正确识别多个流域ID？
- 流域分隔符识别（顿号、逗号、"和"、"、"）是否准确？
- **新增**: 识别组合任务（批量+代码生成/迭代优化）

**2. 任务拆解能力（TaskPlanner）**
- ⭐ **FIXED**: 强制使用规则分解（避免LLM误判）
- 每个流域是否都生成了对应的subtask？
- 组合任务是否正确拆解为 calibration + analysis/iterative 子任务？

**3. 配置生成正确性（InterpreterAgent）**
- 为每个流域生成的配置是否正确？
- basin_id字段是否对应正确？
- ⭐ **FIXED**: 使用实际数据集验证流域ID（不再使用硬编码范围）

**4. 执行稳定性（RunnerAgent）**
- 批量执行时是否稳定？
- 是否存在某个流域失败导致整体失败的情况？

**5. 结果汇总（DeveloperAgent）**
- 能否汇总多个流域的率定结果？
- 报告是否包含所有流域的性能指标？

**关键指标**:
- 流域列表解析准确率: 应≥95%
- 批量任务拆解成功率: 应≥95% (规则分解)
- 基础批量率定成功率: 应≥90%
- 组合功能测试成功率: 应≥80%

**期望观察**:
- 基础批量率定（2-3流域）成功率应≥90%
- 多流域+代码生成成功率应≥80%
- 多流域+迭代优化成功率应≥80%
- ⭐ **修复验证**: 流域ID如11532500等不应再被错误拒绝
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

    print("\n📊 按查询类型统计:")
    for qtype in ["基础批量率定", "多流域+代码生成", "多流域+迭代优化"]:
        if qtype in query_type_counts:
            stats = query_type_counts[qtype]
            success_rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0
            print(f"   {qtype}: {stats['success']}/{stats['total']} ({success_rate:.1%})")

    if metrics.get('ci_95_lower') is not None:
        print(f"\n   95%置信区间: [{metrics['ci_95_lower']:.1%}, {metrics['ci_95_upper']:.1%}]")


if __name__ == "__main__":
    main()
