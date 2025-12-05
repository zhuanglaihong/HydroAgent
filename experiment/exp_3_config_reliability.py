"""
Author: Claude
Date: 2025-12-05 14:45:00
LastEditTime: 2025-12-05 14:45:00
LastEditors: Claude
Description: Exp 3 - 配置生成可靠性测试 (60个配置生成任务，不执行hydromodel)
FilePath: /HydroAgent/experiment/exp_3_config_reliability.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import argparse
from pathlib import Path
from base_experiment import create_experiment

# 测试集: 60个配置生成任务（测试ConfigAgent的可靠性，不实际执行hydromodel）
TEST_QUERIES = [
    # 标准配置 - 完整参数 (30个)
    "率定GR4J模型，流域01013500，使用SCE-UA算法，迭代500轮",
    "用XAJ率定流域01055000，算法scipy，种群200，训练期1990-2000",
    "率定流域01030500的GR4J，GA算法，代数300，种群150，测试期2005-2015",
    "率定XAJ模型，流域01031500，SCE-UA算法，复合体200，warmup365天",
    "用GR4J率定流域01047000，scipy算法，迭代400轮",
    "率定流域01052500的XAJ，GA算法，代数200，训练期1985-1995",
    "GR4J率定流域01054200，SCE-UA，迭代600轮，测试期2010-2015",
    "用XAJ模型率定流域01057000，scipy，种群250",
    "率定GR4J，流域01170100，GA，代数250，种群100",
    "用SCE-UA率定流域01181000的XAJ，复合体150，迭代550轮",
    "率定GR4J模型，流域01187300，算法scipy，迭代450轮",
    "XAJ率定流域01188000，GA算法，代数350，训练期1990-2005",
    "率定流域01195100的GR4J，SCE-UA，复合体180，测试期2005-2014",
    "用XAJ率定流域01196500，scipy，种群220，warmup180天",
    "GR4J率定流域01208500，GA，代数280，种群120",
    "率定XAJ模型，流域01333000，SCE-UA，迭代520轮",
    "用GR4J率定流域01350000，scipy，迭代380轮，训练期1988-1998",
    "率定流域01411300的XAJ，GA，代数220，测试期2008-2013",
    "GR4J模型率定流域01423000，SCE-UA，复合体170，迭代480轮",
    "用XAJ率定流域01434000，scipy，种群230",
    "率定GR4J，流域01440000，GA，代数260，种群140",
    "XAJ率定流域01445500，SCE-UA，复合体190，warmup270天",
    "率定流域01463500的GR4J，scipy，迭代420轮",
    "用XAJ模型率定流域01466500，GA，代数240，训练期1992-2002",
    "GR4J率定流域01481500，SCE-UA，迭代540轮，测试期2006-2011",
    "率定XAJ，流域01491000，scipy，种群210",
    "用GR4J率定流域01518000，GA，代数290，种群130",
    "率定流域01539000的XAJ，SCE-UA，复合体160",
    "GR4J模型率定流域01542810，scipy，迭代460轮，warmup300天",
    "用XAJ率定流域01543000，GA，代数270，训练期1987-1997",

    # 缺省配置 - 部分参数缺失，需自动补全 (20个)
    "率定GR4J模型，流域12025000",  # 缺少算法，应使用默认
    "用XAJ率定流域14301000",  # 缺少算法
    "率定流域14306500，模型GR4J",  # 缺少算法
    "GR4J率定流域01013500，迭代300轮",  # 缺少算法，但有参数
    "用XAJ率定流域01055000，训练期1995-2005",  # 缺少算法和测试期
    "率定流域01030500的GR4J，测试期2010-2020",  # 缺少算法和训练期
    "率定XAJ模型，流域01031500，warmup180天",  # 缺少算法和时间期
    "用GR4J率定流域01047000，复合体150",  # 算法参数不匹配（复合体是SCE-UA的）
    "率定流域01052500，模型XAJ，代数200",  # 缺少算法（代数暗示GA）
    "GR4J率定流域01054200，种群100",  # 缺少算法（种群暗示scipy或GA）
    "用XAJ模型率定流域01057000",  # 完全缺省
    "率定GR4J，流域01170100，SCE-UA算法",  # 缺少迭代参数
    "用XAJ率定流域01181000，scipy算法",  # 缺少种群参数
    "率定流域01187300的GR4J，GA算法",  # 缺少代数和种群
    "率定XAJ模型，流域01188000，训练期只需10年",  # 需推断具体时间
    "用GR4J率定流域01195100，测试期也是10年",  # 需推断具体时间
    "率定流域01196500的XAJ，warmup半年",  # 需转换为天数
    "GR4J率定流域01208500，迭代不用太多，300轮够了",  # 口语化参数
    "用XAJ率定流域01333000，快速率定即可",  # 需推断减少迭代
    "率定流域01350000，用最常用的模型和算法",  # 需推断GR4J和SCE-UA

    # 边界配置 - 极端参数值 (10个)
    "率定GR4J模型，流域01411300，SCE-UA算法，迭代10轮",  # 极小迭代
    "用XAJ率定流域01423000，scipy，种群5",  # 极小种群
    "率定流域01434000的GR4J，GA，代数5，种群5",  # 极小代数和种群
    "率定XAJ，流域01440000，SCE-UA，迭代2000轮",  # 极大迭代
    "用GR4J率定流域01445500，scipy，种群1000",  # 极大种群
    "率定流域01463500的XAJ，GA，代数1000，种群500",  # 极大代数和种群
    "GR4J率定流域01466500，训练期1980-1981",  # 极短训练期（1年）
    "用XAJ率定流域01481500，测试期2020-2021",  # 极短测试期（1年）
    "率定流域01491000的GR4J，warmup1天",  # 极短warmup
    "率定XAJ模型，流域01518000，warmup730天",  # 极长warmup（2年）
]


def main():
    """运行 Exp 3: 配置生成可靠性测试"""
    parser = argparse.ArgumentParser(description="Exp 3 - 配置生成可靠性测试")
    parser.add_argument("--backend", type=str, default="api", choices=["api", "ollama"],
                        help="LLM后端 (默认: api)")
    parser.add_argument("--config-only", action="store_true", default=True,
                        help="仅测试配置生成，不执行hydromodel (默认: True)")
    args = parser.parse_args()

    print("=" * 80)
    print("🧪 Exp 3: 配置生成可靠性测试")
    print("=" * 80)
    print(f"📋 测试集规模: {len(TEST_QUERIES)} 个配置任务")
    print(f"   - 标准配置（完整参数）: 30 个")
    print(f"   - 缺省配置（需自动补全）: 20 个")
    print(f"   - 边界配置（极端参数值）: 10 个")
    print(f"🔧 配置:")
    print(f"   - LLM后端: {args.backend}")
    print(f"   - 仅配置生成: {args.config_only}")
    print(f"   - ⚠️  本实验不执行hydromodel，仅验证配置生成的正确性")
    print("=" * 80)

    # 创建实验
    exp = create_experiment(
        exp_name="exp_3_config_reliability",
        exp_description="配置生成可靠性测试: 验证ConfigAgent的配置生成成功率和正确性"
    )

    # 批量执行（仅到配置生成阶段）
    print("\n🚀 开始执行测试...")
    # 注意: 这里需要修改run_batch以支持config_only模式
    # 或者直接使用mock模式，因为我们不关心hydromodel执行结果
    results = exp.run_batch(TEST_QUERIES, backend=args.backend, use_mock=True)

    # 保存结果
    print("\n💾 保存结果...")
    exp.save_results(results)

    # 计算指标
    print("\n📊 计算评估指标...")
    metrics = exp.calculate_metrics(results)
    exp.save_metrics(metrics)

    # 生成报告
    print("\n📝 生成实验报告...")

    # 按配置类型统计
    config_types = {
        "标准配置": TEST_QUERIES[:30],
        "缺省配置": TEST_QUERIES[30:50],
        "边界配置": TEST_QUERIES[50:60],
    }

    config_stats = {}
    for config_type, queries in config_types.items():
        type_results = [r for r in results if r.get("query", "") in queries]
        config_stats[config_type] = {
            "total": len(type_results),
            "success": sum(1 for r in type_results if r.get("success", False)),
        }

    # 生成配置类型统计表格
    config_table = "| 配置类型 | 测试数 | 成功数 | 成功率 |\n|---------|--------|--------|--------|\n"
    for config_type, stats in config_stats.items():
        success_rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0
        config_table += f"| {config_type} | {stats['total']} | {stats['success']} | {success_rate:.1%} |\n"

    additional_sections = {
        "按配置类型统计": f"""
### 按配置类型统计

{config_table}

**分析**:
- 测试了 3 种类型的配置生成场景
- 验证ConfigAgent在不同复杂度下的配置生成能力
- 观察缺省配置的自动补全效果
""",
        "配置可靠性评估": f"""
### 配置可靠性评估

**评估指标**:
- **配置生成成功率**: {metrics.get('success_rate', 0):.1%} (目标: ≥92%)
- **配置验证通过率**: 需检查生成的config是否符合hydromodel规范
- **默认参数补全率**: 需检查缺省配置是否正确补全
- **平均重试次数**: 理想情况<1.0（无需重试或重试很少）

**按配置类型分析**:

1. **标准配置** ({config_stats['标准配置']['success'] / config_stats['标准配置']['total'] if config_stats['标准配置']['total'] > 0 else 0:.1%})
   - 完整参数的配置生成
   - 测试基本的参数提取和映射能力
   - 期望成功率≥95%

2. **缺省配置** ({config_stats['缺省配置']['success'] / config_stats['缺省配置']['total'] if config_stats['缺省配置']['total'] > 0 else 0:.1%})
   - 部分参数缺失，需要自动补全
   - 测试默认值填充能力
   - 测试参数推断能力（如"代数200"暗示GA算法）
   - 期望成功率≥90%

3. **边界配置** ({config_stats['边界配置']['success'] / config_stats['边界配置']['total'] if config_stats['边界配置']['total'] > 0 else 0:.1%})
   - 极端参数值的处理
   - 测试参数范围验证
   - 测试边界情况的容错能力
   - 期望成功率≥85%

**关键检查项**:
1. ✅ 所有必需字段是否完整（basin_ids, model_name, train_period等）
2. ✅ 算法参数是否匹配（如SCE-UA对应rep/ngs，GA对应gens/pop_size）
3. ✅ 时间期是否合理（训练期在测试期之前，warmup合理）
4. ✅ 参数值是否在有效范围内

**对照实验（如果有v4.0）**:
- v4.0简单重试: 假设成功率75%
- v5.0 FeedbackRouter + PromptPool: 目标92%
- 期望提升: +23%
"""
    }

    exp.generate_report(results, metrics, additional_sections=additional_sections)

    # 生成可视化
    print("\n📈 生成可视化...")
    exp.plot_results(results, "success_rate")
    exp.plot_results(results, "time_distribution")

    print("\n" + "=" * 80)
    print("✅ Exp 3 完成!")
    print(f"📁 结果目录: {exp.workspace}")
    print("=" * 80)

    # 打印关键指标
    print("\n📊 关键指标:")
    print(f"   配置生成成功率: {metrics.get('success_rate', 0):.1%}")
    print(f"   平均耗时: {metrics.get('average_time', 0):.2f}s")

    print("\n📊 按配置类型统计:")
    for config_type, stats in config_stats.items():
        success_rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0
        print(f"   {config_type}: {stats['success']}/{stats['total']} ({success_rate:.1%})")

    if metrics.get('ci_95_lower') is not None:
        print(f"\n   95%置信区间: [{metrics['ci_95_lower']:.1%}, {metrics['ci_95_upper']:.1%}]")


if __name__ == "__main__":
    main()
