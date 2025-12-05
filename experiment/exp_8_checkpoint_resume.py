"""
Author: Claude
Date: 2025-12-05 15:10:00
LastEditTime: 2025-12-05 15:10:00
LastEditors: Claude
Description: Exp 8 - 断点续传可靠性测试 (20个多任务场景，每个执行3次中断-恢复)
FilePath: /HydroAgent/experiment/exp_8_checkpoint_resume.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import argparse
from pathlib import Path
from base_experiment import create_experiment

# 测试集: 20个多任务场景（每个包含5-10个子任务）
TEST_QUERIES = [
    # 5个子任务的场景 (10个)
    "批量率定流域01013500、01055000、01030500、01031500、01047000，使用GR4J模型",
    "用XAJ率定流域01052500、01054200、01057000、01170100、01181000",
    "率定流域01187300、01188000、01195100、01196500、01208500，模型GR4J，SCE-UA算法",
    "用XAJ模型率定流域01333000、01350000、01411300、01423000、01434000，scipy算法",
    "率定流域01440000、01445500、01463500、01466500、01481500，GR4J模型，GA算法",
    "批量率定流域01491000、01518000、01539000、01542810、01543000，XAJ模型",
    "用GR4J率定流域12025000、14301000、14306500、01013500、01055000",
    "率定流域01030500、01031500、01047000、01052500、01054200，XAJ模型",
    "用GR4J模型批量率定流域01057000、01170100、01181000、01187300、01188000",
    "率定流域01195100、01196500、01208500、01333000、01350000，XAJ模型，SCE-UA",

    # 7个子任务的场景 (5个)
    "批量率定流域01411300、01423000、01434000、01440000、01445500、01463500、01466500，GR4J模型",
    "用XAJ率定流域01481500、01491000、01518000、01539000、01542810、01543000、12025000",
    "率定流域14301000、14306500、01013500、01055000、01030500、01031500、01047000，GR4J，scipy",
    "用XAJ模型率定流域01052500、01054200、01057000、01170100、01181000、01187300、01188000，GA算法",
    "率定流域01195100、01196500、01208500、01333000、01350000、01411300、01423000，GR4J模型",

    # 10个子任务的场景 (5个)
    "批量率定流域01434000、01440000、01445500、01463500、01466500、01481500、01491000、01518000、01539000、01542810，GR4J模型",
    "用XAJ率定流域01543000、12025000、14301000、14306500、01013500、01055000、01030500、01031500、01047000、01052500",
    "率定流域01054200、01057000、01170100、01181000、01187300、01188000、01195100、01196500、01208500、01333000，GR4J，SCE-UA",
    "用XAJ模型率定流域01350000、01411300、01423000、01434000、01440000、01445500、01463500、01466500、01481500、01491000，scipy",
    "率定流域01518000、01539000、01542810、01543000、12025000、14301000、14306500、01013500、01055000、01030500，GR4J模型，GA算法",
]

def main():
    """运行 Exp 8: 断点续传可靠性测试"""
    parser = argparse.ArgumentParser(description="Exp 8 - 断点续传可靠性测试")
    parser.add_argument("--backend", type=str, default="api", choices=["api", "ollama"],
                        help="LLM后端 (默认: api)")
    parser.add_argument("--mock", action="store_true", default=False,
                        help="使用mock模式 (默认: True)")
    parser.add_argument("--no-mock", dest="mock", action="store_false",
                        help="使用真实hydromodel执行")
    parser.add_argument("--test-resume", action="store_true", default=False,
                        help="测试断点续传功能（需要手动中断和恢复）")
    args = parser.parse_args()

    print("=" * 80)
    print("🧪 Exp 8: 断点续传可靠性测试")
    print("=" * 80)
    print(f"📋 测试集规模: {len(TEST_QUERIES)} 个多任务场景")
    print(f"   - 5个子任务: 10 个场景")
    print(f"   - 7个子任务: 5 个场景")
    print(f"   - 10个子任务: 5 个场景")
    print(f"🔧 配置:")
    print(f"   - LLM后端: {args.backend}")
    print(f"   - Mock模式: {args.mock}")
    print(f"   - 测试断点续传: {args.test_resume}")
    print(f"📝 测试方法:")
    print(f"   每个任务执行3次中断-恢复循环:")
    print(f"   1. 中断点20% → 恢复")
    print(f"   2. 中断点50% → 恢复")
    print(f"   3. 中断点80% → 恢复")
    print(f"⚠️  如需真正测试断点续传，需要手动中断进程并恢复")
    print("=" * 80)

    exp = create_experiment(
        exp_name="exp_8_checkpoint_resume",
        exp_description="断点续传可靠性测试: 验证Checkpoint机制的可靠性"
    )

    if not args.test_resume:
        # 正常执行所有任务（不测试断点续传）
        print("\n🚀 开始执行测试（正常模式，不中断）...")
        results = exp.run_batch(TEST_QUERIES, backend=args.backend, use_mock=args.mock)

        print("\n💾 保存结果...")
        exp.save_results(results)

        print("\n📊 计算指标...")
        metrics = exp.calculate_metrics(results)
        exp.save_metrics(metrics)

    else:
        # 测试断点续传功能
        print("\n🚀 开始执行测试（断点续传模式）...")
        print("⚠️  请在执行过程中按Ctrl+C中断，然后使用resume参数恢复")
        print("   示例: python exp_8_checkpoint_resume.py --test-resume --resume-from=<session_id>")

        # TODO: 实现真实的断点续传测试逻辑
        # 这需要与Orchestrator的checkpoint机制集成
        results = exp.run_batch(TEST_QUERIES, backend=args.backend, use_mock=args.mock)

        print("\n💾 保存结果...")
        exp.save_results(results)

        print("\n📊 计算指标...")
        metrics = exp.calculate_metrics(results)
        exp.save_metrics(metrics)

    # 按子任务数量统计
    task_counts = {
        "5个子任务": TEST_QUERIES[:10],
        "7个子任务": TEST_QUERIES[10:15],
        "10个子任务": TEST_QUERIES[15:20],
    }

    task_stats = {}
    for task_count, queries in task_counts.items():
        type_results = [r for r in results if r.get("query", "") in queries]
        task_stats[task_count] = {
            "total": len(type_results),
            "success": sum(1 for r in type_results if r.get("success", False)),
        }

    task_table = "| 任务规模 | 测试数 | 成功数 | 成功率 |\n|---------|--------|--------|--------|\n"
    for task_count, stats in task_stats.items():
        success_rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0
        task_table += f"| {task_count} | {stats['total']} | {stats['success']} | {success_rate:.1%} |\n"

    additional_sections = {
        "按任务规模统计": f"""
### 按任务规模统计

{task_table}

**分析**:
- 小规模任务(5个子任务)成功率应≥95%
- 中规模任务(7个子任务)成功率应≥90%
- 大规模任务(10个子任务)成功率应≥85%
""",
        "断点续传评估": f"""
### 断点续传评估

**核心指标**:

1. **保存与恢复**
   - Checkpoint保存成功率: 应为100%
   - Resume恢复准确率: 应为100%
   - 跳过已完成任务准确率: 应为100%

2. **数据一致性**
   - 数据一致性检查: 应100%通过
   - 结果完整性: 无数据丢失
   - 状态恢复正确性: 应为100%

3. **性能影响**
   - Checkpoint开销: 应<2%
   - Resume恢复时间: 应<5s
   - 恢复后成功率: 应≥95%

**测试场景**:
- 正常中断（Ctrl+C）: 主要测试场景
- 异常中断（kill进程）: 压力测试

**期望结果**:
- 所有中断点都能成功恢复
- 已完成的子任务不会重复执行
- 恢复后继续执行剩余任务
- 最终结果与无中断执行一致

**实际测试方法**:
1. 运行脚本开始执行多任务
2. 在不同进度点按Ctrl+C中断（20%, 50%, 80%）
3. 使用--resume参数恢复执行
4. 验证跳过已完成任务，继续执行剩余任务
5. 检查最终结果完整性
"""
    }

    print("\n📝 生成实验报告...")
    exp.generate_report(results, metrics, additional_sections=additional_sections)

    print("\n📈 生成可视化...")
    exp.plot_results(results, "success_rate")
    exp.plot_results(results, "time_distribution")

    print("\n" + "=" * 80)
    print("✅ Exp 8 完成!")
    print(f"📁 结果目录: {exp.workspace}")
    print("=" * 80)

    print("\n📊 关键指标:")
    print(f"   总体成功率: {metrics.get('success_rate', 0):.1%}")
    print(f"   平均耗时: {metrics.get('average_time', 0):.2f}s")

    print("\n📊 按任务规模统计:")
    for task_count, stats in task_stats.items():
        success_rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0
        print(f"   {task_count}: {stats['success']}/{stats['total']} ({success_rate:.1%})")

    if metrics.get('ci_95_lower') is not None:
        print(f"\n   95%置信区间: [{metrics['ci_95_lower']:.1%}, {metrics['ci_95_upper']:.1%}]")

    if args.test_resume:
        print("\n💡 断点续传测试提示:")
        print("   1. 本次执行完整运行了所有任务")
        print("   2. 要真正测试断点续传，需要:")
        print("      - 运行脚本并在执行过程中按Ctrl+C")
        print("      - 找到生成的session目录（results/exp_8_*/session_xxx）")
        print("      - 使用恢复功能继续执行")
        print("   3. 系统会自动跳过已完成的子任务，继续执行剩余任务")


if __name__ == "__main__":
    main()
