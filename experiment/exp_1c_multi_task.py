"""
Author: Claude
Date: 2025-12-05 14:30:00
LastEditTime: 2025-12-05 14:30:00
LastEditors: Claude
Description: Exp 1c - 多任务查询测试 (20个: 代码生成、参数调整等复杂任务)
FilePath: /HydroAgent/experiment/exp_1c_multi_task.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import argparse
from pathlib import Path
from base_experiment import create_experiment

# 测试集: 20个多任务查询（代码生成、参数调整、迭代优化等）
TEST_QUERIES = [
    # 代码生成任务 (8个)
    "率定GR4J模型，流域01539000，完成后计算径流系数",
    "用XAJ率定流域02070000，率定完成后画FDC曲线",
    "率定流域02177000的GR4J，然后计算径流系数和画FDC曲线",
    "率定完成后，帮我计算流域03346000的年均径流量",
    "用GR4J率定流域03500000，完成后分析洪峰流量特征",
    "率定XAJ模型，流域11532500，并生成月径流统计图",
    "率定流域12145500，完成后计算枯水期径流系数",
    "GR4J率定流域14301000，率定后画降雨-径流散点图",

    # 参数调整任务 (8个)
    "率定GR4J模型，流域01539000，使用SCE-UA算法，迭代300轮",
    "用XAJ率定流域02070000，算法用scipy，种群大小200",
    "率定流域02177000的GR4J，GA算法，代数100，种群100",
    "率定XAJ，流域03346000，SCE-UA算法，复合体数量150",
    "用GR4J率定流域03500000，迭代只需要200轮就行",
    "率定流域12145500的XAJ，训练期用1990到2000年",
    "GR4J率定流域12025000，测试期用2010到2015年",
    "率定XAJ模型，流域14306500，warmup期设为180天",

    # 迭代优化任务 (4个)
    "率定GR4J模型，流域02177000，如果参数收敛到边界则调整参数范围重新率定",
    "用XAJ率定流域03346000，如果NSE低于0.7则增加迭代轮数重新率定,每次增加1000轮",
    "率定流域11532500的GR4J，如果效果不好就换个算法再试",
    "率定XAJ模型，流域14325000，不断优化直到NSE达到0.7以上",
]


def main():
    """运行 Exp 1c: 多任务查询测试"""
    parser = argparse.ArgumentParser(description="Exp 1c - 多任务查询测试")
    parser.add_argument("--backend", type=str, default="api", choices=["api", "ollama"],
                        help="LLM后端 (默认: api)")
    parser.add_argument("--mock", action="store_true", default=False,
                        help="使用mock模式 (默认: True)")
    parser.add_argument("--no-mock", dest="mock", action="store_false",
                        help="使用真实hydromodel执行")
    args = parser.parse_args()

    print("=" * 80)
    print("🧪 Exp 1c: 多任务查询测试")
    print("=" * 80)
    print(f"📋 测试集规模: {len(TEST_QUERIES)} 个查询")
    print(f"   - 代码生成任务: 8 个")
    print(f"   - 参数调整任务: 8 个")
    print(f"   - 迭代优化任务: 4 个")
    print(f"🔧 配置:")
    print(f"   - LLM后端: {args.backend}")
    print(f"   - Mock模式: {args.mock}")
    print("=" * 80)

    # 创建实验
    exp = create_experiment(
        exp_name="exp_1c_multi_task",
        exp_description="多任务查询测试: 验证系统对复杂多步骤任务的处理能力"
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

    # 按任务类型统计
    code_gen = [r for r in results if any(kw in r.get("query", "")
                for kw in ["计算", "画", "分析", "生成", "统计"])]
    param_adj = [r for r in results if any(kw in r.get("query", "")
                 for kw in ["迭代", "轮", "代数", "种群", "复合体", "训练期", "测试期", "warmup"])]
    iterative = [r for r in results if any(kw in r.get("query", "")
                 for kw in ["如果", "则", "重新", "不断", "直到"])]

    code_gen_success = sum(1 for r in code_gen if r.get("success", False))
    param_adj_success = sum(1 for r in param_adj if r.get("success", False))
    iterative_success = sum(1 for r in iterative if r.get("success", False))

    additional_sections = {
        "按任务类型统计": f"""
### 按任务类型统计

| 任务类型 | 测试数 | 成功数 | 成功率 |
|---------|--------|--------|--------|
| 代码生成 | {len(code_gen)} | {code_gen_success} | {code_gen_success/len(code_gen) if code_gen else 0:.1%} |
| 参数调整 | {len(param_adj)} | {param_adj_success} | {param_adj_success/len(param_adj) if param_adj else 0:.1%} |
| 迭代优化 | {len(iterative)} | {iterative_success} | {iterative_success/len(iterative) if iterative else 0:.1%} |

**分析**:
- 代码生成成功率: {code_gen_success/len(code_gen) if code_gen else 0:.1%} (测试DeveloperAgent的代码生成能力)
- 参数调整成功率: {param_adj_success/len(param_adj) if param_adj else 0:.1%} (测试IntentAgent的参数提取能力)
- 迭代优化成功率: {iterative_success/len(iterative) if iterative else 0:.1%} (测试TaskPlanner的多步骤规划能力)
""",
        "能力评估": f"""
### 系统能力评估

**1. 多任务识别能力**
- 系统能否正确识别一个查询中包含的多个子任务？
- TaskPlanner能否正确拆解为多个subtask？

**2. 任务依赖关系处理**
- 系统能否理解"率定完成后"、"然后"等时序依赖？
- 任务执行顺序是否正确？

**3. 代码生成能力**
- DeveloperAgent能否生成正确的分析代码？
- 生成的代码是否可执行且结果正确？

**4. 参数提取准确性**
- IntentAgent能否准确提取自定义参数（迭代轮数、种群大小等）？
- 参数是否正确传递到ConfigAgent？

**5. 迭代优化能力**
- 系统能否理解条件判断（"如果...则..."）？
- 能否执行多轮优化直到满足条件？

**关键观察**:
- 多任务查询的成功率应≥80%
- 代码生成任务的成功率应≥75%
- 迭代优化任务的成功率应≥70% (更复杂)
"""
    }

    exp.generate_report(results, metrics, additional_sections=additional_sections)

    # 生成可视化
    print("\n📈 生成可视化...")
    exp.plot_results(results, "success_rate")
    exp.plot_results(results, "time_distribution")

    print("\n" + "=" * 80)
    print("✅ Exp 1c 完成!")
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

    print("\n📊 按任务类型统计:")
    print(f"   代码生成: {code_gen_success}/{len(code_gen)} ({code_gen_success/len(code_gen) if code_gen else 0:.1%})")
    print(f"   参数调整: {param_adj_success}/{len(param_adj)} ({param_adj_success/len(param_adj) if param_adj else 0:.1%})")
    print(f"   迭代优化: {iterative_success}/{len(iterative)} ({iterative_success/len(iterative) if iterative else 0:.1%})")

    if metrics.get('ci_95_lower') is not None:
        print(f"\n   95%置信区间: [{metrics['ci_95_lower']:.1%}, {metrics['ci_95_upper']:.1%}]")


if __name__ == "__main__":
    main()
