"""
Author: Claude
Date: 2025-12-05 14:55:00
LastEditTime: 2025-12-05 14:55:00
LastEditors: Claude
Description: Exp 5 - 错误恢复机制测试 (60个错误场景，验证FeedbackRouter智能路由)
FilePath: /HydroAgent/experiment/exp_5_error_recovery.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import argparse
from pathlib import Path
from base_experiment import create_experiment

# 测试集: 60个错误场景，测试FeedbackRouter的错误分类和恢复能力
# 注意: 在mock模式下，这些错误可能无法真实触发，需要在真实模式下测试
TEST_QUERIES = [
    # timeout (10个) - 迭代参数过大导致超时
    "率定GR4J模型，流域01013500，SCE-UA算法，迭代2000轮",
    "用XAJ率定流域01055000，scipy，种群1000",
    "率定流域01030500的GR4J，GA，代数1500，种群800",
    "率定XAJ，流域01031500，SCE-UA，复合体500，迭代1800轮",
    "用GR4J率定流域01047000，scipy，迭代2500轮",
    "率定流域01052500的XAJ，GA，代数2000，种群1000",
    "GR4J率定流域01054200，SCE-UA，迭代3000轮",
    "用XAJ模型率定流域01057000，scipy，种群1500",
    "率定GR4J，流域01170100，GA，代数2500",
    "率定XAJ模型，流域01181000，SCE-UA，迭代2200轮",

    # configuration_error (15个) - 配置参数错误
    "率定GR4J模型，流域99999999",  # 流域不存在
    "用BADMODEL率定流域01013500",  # 无效模型
    "率定流域01187300，算法INVALIDALG",  # 无效算法
    "用GR4J率定流域01188000，迭代-100轮",  # 负数迭代
    "率定XAJ，流域01195100，训练期2020-2010",  # 时间倒置
    "用GR4J率定流域01196500，测试期1970-1975",  # 测试期太早
    "率定流域01208500的XAJ，warmup10000天",  # warmup过长
    "GR4J率定流域01333000，种群-50",  # 负数种群
    "用XAJ率定流域01350000，代数0",  # 代数为0
    "率定GR4J，流域01411300，SCE-UA，复合体-20",  # 负数复合体
    "用XAJ模型率定流域01423000，种群99999",  # 种群过大
    "率定流域01434000的GR4J，代数10000",  # 代数过大
    "GR4J率定流域01440000，warmup-100天",  # 负数warmup
    "用XAJ率定流域01445500，训练期2025-2030",  # 未来时间
    "率定GR4J，流域01463500，测试期2050-2055",  # 未来时间

    # numerical_error (15个) - 数值计算错误（极端参数）
    "率定GR4J模型，流域12025000，迭代5轮",  # 极少迭代
    "用XAJ率定流域14301000，scipy，种群3",  # 极小种群
    "率定流域14306500的GR4J，GA，代数3，种群2",  # 极小参数组合
    "率定XAJ，流域01466500，SCE-UA，复合体5，迭代10轮",  # 极小复合体
    "用GR4J率定流域01481500，训练期1980-1981",  # 极短训练期
    "率定流域01491000的XAJ，测试期2020-2020",  # 1年测试期
    "GR4J率定流域01518000，warmup1天",  # 极短warmup
    "用XAJ模型率定流域01539000，scipy，种群5",  # 种群太小
    "率定GR4J，流域01542810，GA，代数8",  # 代数太少
    "率定XAJ模型，流域01543000，迭代8轮",  # 迭代太少
    "用GR4J率定流域12025000，复合体8",  # 复合体太小
    "率定流域14301000的XAJ，种群6",  # 种群太小（scipy）
    "GR4J率定流域14306500，代数7，种群4",  # GA参数太小
    "用XAJ率定流域01055000，训练期1985-1986",  # 训练期太短
    "率定GR4J，流域01030500，测试期2015-2015",  # 测试期太短

    # memory_error (10个) - 内存错误（大规模任务）
    "批量率定20个流域，使用GR4J模型",  # 流域过多
    "率定流域01013500、01055000、01030500、01031500、01047000、01052500、01054200、01057000、01170100、01181000",  # 10个流域
    "用XAJ同时率定15个流域",  # 流域过多（口语化）
    "率定所有CAMELS数据集的流域",  # 数量过大
    "用GR4J批量率定流域01187300到01333000之间的所有流域",  # 范围过大
    "率定GR4J模型，流域01013500，scipy，种群5000",  # 种群过大
    "用XAJ率定流域01055000，GA，代数5000，种群3000",  # 参数过大
    "率定流域01030500的GR4J，SCE-UA，复合体2000，迭代5000轮",  # 复合体过大
    "同时率定GR4J和XAJ两个模型，流域01031500",  # 多模型
    "批量率定8个流域，测试4种算法",  # 组合过多

    # data_not_found (5个) - 数据未找到
    "率定GR4J模型，流域00000000",  # 不存在的流域ID
    "用XAJ率定流域99999999",  # 不存在的流域ID
    "率定流域ABCD1234的GR4J",  # 无效流域ID格式
    "用GR4J率定流域123",  # 流域ID格式错误
    "率定流域01013500，数据路径/invalid/path/to/data",  # 自定义路径不存在

    # dependency_error (5个) - 依赖错误
    "率定GR4J模型，流域01047000，使用不存在的Python包",  # 依赖缺失（理论上）
    "用自定义算法MyCustomAlg率定流域01052500",  # 自定义算法不存在
    "率定流域01054200，使用未安装的优化库",  # 库缺失
    "用GR4J率定流域01057000，调用外部脚本/path/to/missing/script.py",  # 脚本不存在
    "率定XAJ模型，流域01170100，依赖缺失的配置文件",  # 配置缺失
]

def main():
    """运行 Exp 5: 错误恢复机制测试"""
    parser = argparse.ArgumentParser(description="Exp 5 - 错误恢复机制测试")
    parser.add_argument("--backend", type=str, default="api", choices=["api", "ollama"],
                        help="LLM后端 (默认: api)")
    parser.add_argument("--mock", action="store_true", default=False,
                        help="使用mock模式 (默认: False, 建议使用真实模式)")
    parser.add_argument("--no-mock", dest="mock", action="store_false",
                        help="使用真实hydromodel执行")
    args = parser.parse_args()

    print("=" * 80)
    print("🧪 Exp 5: 错误恢复机制测试")
    print("=" * 80)
    print(f"📋 测试集规模: {len(TEST_QUERIES)} 个错误场景")
    print(f"   - timeout: 10 个")
    print(f"   - configuration_error: 15 个")
    print(f"   - numerical_error: 15 个")
    print(f"   - memory_error: 10 个")
    print(f"   - data_not_found: 5 个")
    print(f"   - dependency_error: 5 个")
    print(f"🔧 配置:")
    print(f"   - LLM后端: {args.backend}")
    print(f"   - Mock模式: {args.mock}")
    print(f"   - ⚠️  建议使用真实模式以触发实际错误")
    print("=" * 80)

    exp = create_experiment(
        exp_name="exp_5_error_recovery",
        exp_description="错误恢复机制测试: 验证FeedbackRouter智能路由的有效性"
    )

    print("\n🚀 开始执行测试...")
    results = exp.run_batch(TEST_QUERIES, backend=args.backend, use_mock=args.mock)

    print("\n💾 保存结果...")
    exp.save_results(results)

    print("\n📊 计算评估指标...")
    metrics = exp.calculate_metrics(results)
    exp.save_metrics(metrics)

    print("\n📝 生成实验报告...")

    error_types = {
        "timeout": TEST_QUERIES[:10],
        "configuration_error": TEST_QUERIES[10:25],
        "numerical_error": TEST_QUERIES[25:40],
        "memory_error": TEST_QUERIES[40:50],
        "data_not_found": TEST_QUERIES[50:55],
        "dependency_error": TEST_QUERIES[55:60],
    }

    error_stats = {}
    for error_type, queries in error_types.items():
        type_results = [r for r in results if r.get("query", "") in queries]
        error_stats[error_type] = {
            "total": len(type_results),
            "success": sum(1 for r in type_results if r.get("success", False)),
        }

    error_table = "| 错误类型 | 测试数 | 恢复成功 | 恢复率 |\n|---------|--------|----------|--------|\n"
    for error_type, stats in error_stats.items():
        recovery_rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0
        error_table += f"| {error_type} | {stats['total']} | {stats['success']} | {recovery_rate:.1%} |\n"

    additional_sections = {
        "按错误类型统计": f"""
### 按错误类型统计

{error_table}

**路由策略验证**:
- timeout → retry_with_reduce_iterations: 目标恢复率≥85%
- configuration_error → regenerate_config: 目标恢复率≥90%
- numerical_error → retry_with_default_config: 目标恢复率≥80%
- memory_error → reduce_complexity: 目标恢复率≥75%
- data_not_found → fail_with_error: 应正确识别并报告
- dependency_error → fail_with_error: 应正确识别并报告
""",
        "恢复机制评估": f"""
### 恢复机制评估

**核心指标**:
1. **错误类型识别准确率**: {metrics.get('success_rate', 0):.1%} (目标: ≥95%)
2. **路由决策准确率**: 需手动检查路由是否正确 (目标: ≥90%)
3. **总体恢复成功率**: {metrics.get('success_rate', 0):.1%} (目标: v5.0 85% vs 基准60%)
4. **平均恢复尝试次数**: 应 < 简单重试

**对照实验**:
- 简单重试策略: 假设60%成功率
- v5.0 FeedbackRouter: 目标85%成功率
- 期望提升: +42%

**关键发现**:
- 哪些错误类型恢复效果最好？
- FeedbackRouter的智能路由是否有效？
- 是否减少了无效的重试次数？
"""
    }

    exp.generate_report(results, metrics, additional_sections=additional_sections)

    print("\n📈 生成可视化...")
    exp.plot_results(results, "success_rate")
    exp.plot_results(results, "time_distribution")

    print("\n" + "=" * 80)
    print("✅ Exp 5 完成!")
    print(f"📁 结果目录: {exp.workspace}")
    print("=" * 80)

    print("\n📊 关键指标:")
    print(f"   总体恢复率: {metrics.get('success_rate', 0):.1%}")
    print(f"   平均耗时: {metrics.get('average_time', 0):.2f}s")

    print("\n📊 按错误类型统计:")
    for error_type, stats in error_stats.items():
        recovery_rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0
        print(f"   {error_type}: {stats['success']}/{stats['total']} ({recovery_rate:.1%})")

    if metrics.get('ci_95_lower') is not None:
        print(f"\n   95%置信区间: [{metrics['ci_95_lower']:.1%}, {metrics['ci_95_upper']:.1%}]")


if __name__ == "__main__":
    main()
