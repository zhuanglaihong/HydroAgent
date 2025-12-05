"""
Author: Claude
Date: 2025-12-05 14:40:00
LastEditTime: 2025-12-05 14:40:00
LastEditors: Claude
Description: Exp 2 - 自然语言理解鲁棒性测试 (60个包含"噪音"的查询)
FilePath: /HydroAgent/experiment/exp_2_nlp_robustness.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import argparse
from pathlib import Path
from base_experiment import create_experiment

# 测试集: 60个包含"噪音"的查询，测试系统容错能力
TEST_QUERIES = [
    # 拼写错误 (15个)
    "率顶GR4J摸型，流域01013500",  # 率定→率顶，模型→摸型
    "用XAJ率定流阈01055000",  # 流域→流阈
    "率定流域01030500的GR4J模形",  # 模型→模形
    "率定GR4J，柳域01031500",  # 流域→柳域
    "用XAJ率定刘域01047000",  # 流域→刘域
    "率订GR4J模型，流域01052500",  # 率定→率订
    "用XAJ摸型率定流域01054200",  # 模型→摸型
    "率定流域01057000的GR4J模行",  # 模型→模行
    "GR4J率定，流育01170100",  # 流域→流育
    "用XAJ率定刘与01181000",  # 流域→刘与
    "率定流域01187300，摸型用GR4J",  # 模型→摸型
    "XAJ率订流域01188000",  # 率定→率订
    "率定流与01195100的GR4J",  # 流域→流与
    "用GR4J率顶流域01196500",  # 率定→率顶
    "律定XAJ模型，流域01208500",  # 率定→律定

    # 标点异常 (15个)
    "率定GR4J模型流域01333000",  # 缺少逗号
    "用XAJ率定流域01350000。",  # 句号
    "率定流域01411300的GR4J模型！",  # 感叹号
    "GR4J率定，，流域01423000",  # 双逗号
    "用XAJ率定流域01434000、、",  # 双顿号
    "率定GR4J..流域01440000",  # 双句号
    "用XAJ模型率定流域01445500?",  # 问号
    "率定流域01463500  的GR4J",  # 多余空格
    "GR4J率定流域　01466500",  # 全角空格
    "用XAJ率定,流域01481500",  # 中英文逗号混用
    "率定流域01491000，GR4J模型；",  # 分号
    "用XAJ率定流域:01518000",  # 冒号
    "率定GR4J~流域01539000",  # 波浪号
    "用XAJ模型(率定)流域01542810",  # 括号
    "率定流域01543000[GR4J]",  # 方括号

    # 参数顺序混乱 (10个)
    "流域01013500，率定GR4J模型",  # 流域在前
    "01055000流域用XAJ率定",  # 流域ID在最前
    "GR4J模型，流域01030500，率定",  # 率定在最后
    "使用SCE-UA算法，率定GR4J，流域01031500",  # 算法在前
    "流域01047000的GR4J模型率定",  # 流域-模型-动作
    "01052500流域，XAJ模型，率定",  # 全乱序
    "率定，流域01054200，模型GR4J",  # 动作-流域-模型
    "XAJ，01057000，率定",  # 最简乱序
    "迭代500轮，使用SCE-UA算法，率定GR4J，流域01170100",  # 参数在最前
    "流域01181000，训练期1990-2000，率定XAJ模型",  # 流域-训练期-动作-模型

    # 口语化表达 (10个)
    "帮我跑一下01187300这个流域",
    "能不能用GR4J率定一下01188000",
    "我想看看01195100的率定结果",
    "麻烦率定下01196500的流域",
    "请帮忙率定流域01208500吧",
    "可以用XAJ帮我率定01333000吗",
    "想让你率定一下01350000这个流域",
    "能否率定下GR4J模型在01411300上的表现",
    "帮忙跑个率定，流域是01423000",
    "麻烦用XAJ给我率定01434000这个流域",

    # 中英混合 (10个)
    "calibrate GR4J模型，流域01440000",
    "用XAJ model率定流域01445500",
    "率定basin 01463500的GR4J",
    "GR4J率定，basin ID是01466500",
    "用XAJ calibrate流域01481500",
    "率定流域01491000 using GR4J",
    "用SCE-UA algorithm率定01518000",
    "calibration of 01539000 with XAJ",
    "率定01542810，model type是GR4J",
    "basin 12025000用XAJ率定",
]


def main():
    """运行 Exp 2: 自然语言理解鲁棒性测试"""
    parser = argparse.ArgumentParser(description="Exp 2 - 自然语言理解鲁棒性测试")
    parser.add_argument("--backend", type=str, default="api", choices=["api", "ollama"],
                        help="LLM后端 (默认: api)")
    parser.add_argument("--mock", action="store_true", default=False,
                        help="使用mock模式 (默认: True)")
    parser.add_argument("--no-mock", dest="mock", action="store_false",
                        help="使用真实hydromodel执行")
    args = parser.parse_args()

    print("=" * 80)
    print("🧪 Exp 2: 自然语言理解鲁棒性测试")
    print("=" * 80)
    print(f"📋 测试集规模: {len(TEST_QUERIES)} 个查询")
    print(f"   - 拼写错误: 15 个")
    print(f"   - 标点异常: 15 个")
    print(f"   - 参数顺序混乱: 10 个")
    print(f"   - 口语化表达: 10 个")
    print(f"   - 中英混合: 10 个")
    print(f"🔧 配置:")
    print(f"   - LLM后端: {args.backend}")
    print(f"   - Mock模式: {args.mock}")
    print("=" * 80)

    # 创建实验
    exp = create_experiment(
        exp_name="exp_2_nlp_robustness",
        exp_description="自然语言鲁棒性测试: 验证系统对非标准输入的容错能力"
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

    # 按噪音类型统计
    noise_types = {
        "拼写错误": TEST_QUERIES[:15],
        "标点异常": TEST_QUERIES[15:30],
        "参数顺序混乱": TEST_QUERIES[30:40],
        "口语化表达": TEST_QUERIES[40:50],
        "中英混合": TEST_QUERIES[50:60],
    }

    noise_stats = {}
    for noise_type, queries in noise_types.items():
        type_results = [r for r in results if r.get("query", "") in queries]
        noise_stats[noise_type] = {
            "total": len(type_results),
            "success": sum(1 for r in type_results if r.get("success", False)),
        }

    # 生成噪音类型统计表格
    noise_table = "| 噪音类型 | 测试数 | 成功数 | 成功率 |\n|---------|--------|--------|--------|\n"
    for noise_type, stats in noise_stats.items():
        success_rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0
        noise_table += f"| {noise_type} | {stats['total']} | {stats['success']} | {success_rate:.1%} |\n"

    additional_sections = {
        "按噪音类型统计": f"""
### 按噪音类型统计

{noise_table}

**分析**:
- 测试了 5 种类型的"噪音"输入
- 验证系统的容错能力和自然语言理解鲁棒性
- 观察不同类型噪音对成功率的影响
""",
        "鲁棒性评估": f"""
### 鲁棒性评估

**评估指标**:
- **噪音容忍率**: {metrics.get('success_rate', 0):.1%} (目标: ≥85%)
- **关键信息提取率**: 需检查Intent结果的准确性
- **错误恢复率**: 系统能否从噪音输入中恢复并正确理解意图

**按噪音类型分析**:

1. **拼写错误** ({noise_stats['拼写错误']['success_rate'] if '拼写错误' in noise_stats else 0:.1%})
   - 测试LLM对常见拼写错误的纠正能力
   - 关键字识别（率定、模型、流域）的鲁棒性

2. **标点异常** ({noise_stats['标点异常']['success_rate'] if '标点异常' in noise_stats else 0:.1%})
   - 测试系统对标点符号的依赖程度
   - 分词和语义理解的准确性

3. **参数顺序混乱** ({noise_stats['参数顺序混乱']['success_rate'] if '参数顺序混乱' in noise_stats else 0:.1%})
   - 测试系统对参数位置的容错能力
   - 语义理解而非规则匹配的能力

4. **口语化表达** ({noise_stats['口语化表达']['success_rate'] if '口语化表达' in noise_stats else 0:.1%})
   - 测试系统对日常用语的理解
   - 意图识别的准确性

5. **中英混合** ({noise_stats['中英混合']['success_rate'] if '中英混合' in noise_stats else 0:.1%})
   - 测试系统对双语输入的处理能力
   - 跨语言关键字识别

**期望结果**:
- 总体成功率应≥85%
- 拼写错误和标点异常成功率应≥90%
- 参数顺序混乱成功率应≥85%
- 口语化和中英混合成功率应≥75%
"""
    }

    # 计算各类型成功率并添加到stats
    for noise_type in noise_stats:
        if noise_stats[noise_type]["total"] > 0:
            noise_stats[noise_type]["success_rate"] = (
                noise_stats[noise_type]["success"] / noise_stats[noise_type]["total"]
            )
        else:
            noise_stats[noise_type]["success_rate"] = 0

    exp.generate_report(results, metrics, additional_sections=additional_sections)

    # 生成可视化
    print("\n📈 生成可视化...")
    exp.plot_results(results, "success_rate")
    exp.plot_results(results, "time_distribution")

    print("\n" + "=" * 80)
    print("✅ Exp 2 完成!")
    print(f"📁 结果目录: {exp.workspace}")
    print("=" * 80)

    # 打印关键指标
    print("\n📊 关键指标:")
    print(f"   总体噪音容忍率: {metrics.get('success_rate', 0):.1%}")
    print(f"   平均耗时: {metrics.get('average_time', 0):.2f}s")

    print("\n📊 按噪音类型统计:")
    for noise_type, stats in noise_stats.items():
        success_rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0
        print(f"   {noise_type}: {stats['success']}/{stats['total']} ({success_rate:.1%})")

    if metrics.get('ci_95_lower') is not None:
        print(f"\n   95%置信区间: [{metrics['ci_95_lower']:.1%}, {metrics['ci_95_upper']:.1%}]")


if __name__ == "__main__":
    main()
