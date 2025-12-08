"""
Author: Claude
Date: 2025-12-06 15:00:00
LastEditTime: 2025-12-06 15:00:00
LastEditors: Claude
Description: Exp 1a - 标准问题模板测试 (精简版: 15个代表性模板)
FilePath: /HydroAgent/experiment/exp_1a_standard_calibration.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import argparse
from pathlib import Path
from base_experiment import create_experiment

# 测试集: 15个标准问题模板，覆盖所有主要功能
TEST_QUERIES = [
    # ========== 率定任务模板 ==========

    # 全参数率定 - 包含所有可能的参数（完整的模板）
    "率定GR4J模型，流域11532500，使用SCE-UA算法，迭代600轮，复合体数量200，训练期1985-1995，测试期2005-2014，warmup期365天",

    # ========== 其他任务类型模板 (7个) ==========

    # 评估任务 - evaluation
    "评估GR4J模型在流域12025000上的性能，测试期2010-2015",

    # 模拟任务 - simulation
    "使用GR4J模型模拟流域14301000的径流，时间段2010-2015",

    # 扩展分析 - 计算径流系数
    "率定GR4J模型，流域14306500，完成后计算径流系数",

    # 扩展分析 - 绘制FDC曲线
    "率定XAJ模型，流域14325000，完成后画流量历时曲线",

    # 迭代优化 - 参数边界调整
    "率定GR4J模型，流域02070000，如果参数收敛到边界则调整参数范围重新率定",

    # 迭代优化 - NSE目标驱动
    "率定XAJ模型，流域02177000，如果NSE低于0.7则增加迭代轮数重新率定",

    # 复杂组合 - 算法参数 + 扩展分析
    "率定GR4J模型，流域03346000，使用SCE-UA算法，迭代500轮，完成后计算径流系数",

]


def main():
    """运行 Exp 1a: 标准问题模板测试"""
    parser = argparse.ArgumentParser(description="Exp 1a - 标准问题模板测试")
    parser.add_argument("--backend", type=str, default="api", choices=["api", "ollama"],
                        help="LLM后端 (默认: api)")
    parser.add_argument("--mock", action="store_true", default=False,
                        help="使用mock模式 (默认: False)")
    parser.add_argument("--no-mock", dest="mock", action="store_false",
                        help="使用真实hydromodel执行")
    args = parser.parse_args()

    print("=" * 80)
    print("🧪 Exp 1a: 标准问题模板测试 (精简版)")
    print("=" * 80)
    print(f"📋 测试集规模: {len(TEST_QUERIES)} 个代表性模板")
    print(f"")
    print(f"📦 模板分类:")
    print(f"   - 率定任务模板: 1 个")
    print(f"     2. 全参数率定（最完整）")
    print(f"")
    print(f"   - 其他任务类型: 7 个")
    print(f"     评估任务 (evaluation)")
    print(f"     模拟任务 (simulation)")
    print(f"     扩展分析 (extended_analysis)")
    print(f"     迭代优化 (iterative_optimization)")
    print(f"     复杂组合")
    print(f"")
    print(f"🔧 配置:")
    print(f"   - LLM后端: {args.backend}")
    print(f"   - Mock模式: {args.mock}")
    print("=" * 80)

    # 创建实验
    exp = create_experiment(
        exp_name="exp_1a_standard_calibration",
        exp_description="标准问题模板测试: 验证系统对各类任务的处理能力（精简版）"
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

    # 按任务类型分类
    calibration_queries = TEST_QUERIES[0:6]
    other_queries = TEST_QUERIES[6:]

    calibration_results = [r for r in results if r.get("query", "") in calibration_queries]
    other_results = [r for r in results if r.get("query", "") in other_queries]

    calibration_success = sum(1 for r in calibration_results if r.get("success", False))
    other_success = sum(1 for r in other_results if r.get("success", False))

    additional_sections = {
        "模板分析": f"""
### 按模板类型统计

| 模板类型 | 测试数 | 成功数 | 成功率 |
|---------|--------|--------|--------|
| 率定任务模板 | {len(calibration_results)} | {calibration_success} | {calibration_success/len(calibration_results) if calibration_results else 0:.1%} |
| 其他任务类型 | {len(other_results)} | {other_success} | {other_success/len(other_results) if other_results else 0:.1%} |

**分析**:
- 率定任务模板涵盖从最简单到最复杂的6种参数组合
- 其他任务类型包括evaluation、simulation、extended_analysis、iterative_optimization
- 这15个模板代表了HydroAgent的核心功能
""",
        "模板详情": """
### 标准问题模板详情

#### 率定任务模板

1. **基础率定** (最简单)
   - 格式: `率定{模型}模型，流域{basin_id}`
   - 示例: `率定GR4J模型，流域01539000`
   - 用途: 验证最基本的率定功能

2. **指定算法**
   - 格式: `率定{模型}模型，流域{basin_id}，使用{算法}算法`
   - 示例: `率定XAJ模型，流域02070000，使用SCE-UA算法`
   - 用途: 验证算法选择功能

3. **指定算法参数**
   - 格式: `率定{模型}模型，流域{basin_id}，使用{算法}算法，迭代{n}轮`
   - 示例: `率定GR4J模型，流域02177000，使用SCE-UA算法，迭代500轮`
   - 用途: 验证算法参数提取

4. **指定时间期**
   - 格式: `率定{模型}模型，流域{basin_id}，训练期{start}-{end}，测试期{start}-{end}`
   - 示例: `率定XAJ模型，流域03346000，训练期1990-2000，测试期2005-2015`
   - 用途: 验证时间期设置

5. **指定warmup**
   - 格式: `率定{模型}模型，流域{basin_id}，warmup期{n}天`
   - 示例: `率定GR4J模型，流域03500000，warmup期365天`
   - 用途: 验证warmup参数设置

6. **全参数率定** (最完整)
   - 格式: 包含所有可能的参数
   - 示例: `率定GR4J模型，流域11532500，使用SCE-UA算法，迭代600轮，复合体数量200，训练期1985-1995，测试期2005-2014，warmup期365天`
   - 用途: 验证完整参数处理能力

#### 其他任务类型

7. **评估任务** (evaluation)
   - 格式: `评估{模型}模型在流域{basin_id}上的性能，测试期{start}-{end}`
   - 用途: 验证模型评估功能

8. **模拟任务** (simulation)
   - 格式: `使用{模型}模型模拟流域{basin_id}的径流，时间段{start}-{end}`
   - 用途: 验证径流模拟功能

9-11. **扩展分析** (extended_analysis)
   - 格式: `率定...，完成后{分析任务}`
   - 用途: 验证代码生成和自定义分析能力

12-13. **迭代优化** (iterative_optimization)
   - 格式: `率定...，如果{条件}则{优化动作}`
   - 用途: 验证多轮迭代优化能力

14-15. **复杂组合**
   - 用途: 验证多功能组合处理能力
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
    print(f"   ├─ session_*/           # HydroAgent 执行记录 (15个)")
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

    print("\n📊 按模板类型统计:")
    print(f"   率定任务模板: {calibration_success}/{len(calibration_results)} ({calibration_success/len(calibration_results) if calibration_results else 0:.1%})")
    print(f"   其他任务类型: {other_success}/{len(other_results)} ({other_success/len(other_results) if other_results else 0:.1%})")

    if metrics.get('ci_95_lower') is not None:
        print(f"\n   95%置信区间: [{metrics['ci_95_lower']:.1%}, {metrics['ci_95_upper']:.1%}]")


if __name__ == "__main__":
    main()
