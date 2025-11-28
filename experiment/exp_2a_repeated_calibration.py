"""
Author: Claude
Date: 2025-01-24 16:30:00
LastEditTime: 2025-01-24 16:30:00
LastEditors: Claude
Description: 实验2A - 单流域重复率定（稳定性验证）
             Experiment 2A - Repeated Calibration (Stability Validation)
FilePath: /HydroAgent/experiment/exp_2a_repeated_calibration.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

实验目标:
- 验证算法和系统的稳定性
- 统计分析性能分布（NSE均值、标准差、参数分布）
- 一次对话，20个独立任务，每次使用不同随机种子

测试查询:
"对流域  14301000 重复执行20次率定，使用 XAJ 模型和 SCE-UA 算法"

成功标准:
- 20次率定全部成功执行（成功率100%）
- NSE标准差 < 0.05（证明算法稳定）
- 生成统计分析报告和可视化图表
"""

import sys
from pathlib import Path
import io
import argparse

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set console encoding (Windows compatible)
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from base_experiment import BaseExperiment


# 实验查询 - 重复20次率定
QUERY = "对流域  14301000 重复执行10次率定，使用 XAJ 模型和 SCE-UA 算法，每次率定设置rep=100"


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="实验2A：单流域重复率定")
    parser.add_argument(
        "--backend",
        type=str,
        default="api",
        choices=["ollama", "api"],
        help="LLM backend (default: api)",
    )
    parser.add_argument("--model", type=str, default=None, help="Model name")
    parser.add_argument(
        "--mock", action="store_true", help="Use mock mode (do not run real hydromodel)"
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=20,
        help="Number of repetitions (default: 20)"
    )
    args = parser.parse_args()

    # 创建实验对象
    experiment = BaseExperiment(
        exp_name="exp_2a_repeated_calibration",
        exp_description="实验2A：单流域重复率定"
    )

    # Setup logging
    log_file = experiment.setup_logging()

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║       实验2A：单流域重复率定（稳定性验证）                   ║")
    print("║  Experiment 2A: Repeated Calibration (Stability)            ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"\n📝 日志文件: {log_file}\n")

    # Load config
    try:
        from configs import definitions_private as config
    except ImportError:
        from configs import definitions as config

    # Create LLM interface
    from hydroagent.core.llm_interface import create_llm_interface

    print(f"正在初始化LLM接口 (backend: {args.backend})...")

    if args.backend == "ollama":
        model = args.model or "qwen3:8b"
        llm = create_llm_interface("ollama", model)
        print(f"✅ LLM接口初始化完成 (Ollama: {model})\n")
    else:
        api_key = getattr(config, "OPENAI_API_KEY", None)
        base_url = getattr(config, "OPENAI_BASE_URL", None)

        if not api_key:
            print("❌ API key未配置，请设置configs/definitions_private.py")
            return 1

        model = args.model or "qwen3-max"
        llm = create_llm_interface("openai", model, api_key=api_key, base_url=base_url)
        print(f"✅ LLM接口初始化完成 (API: {model})\n")

    # Adjust query with actual repetition count
    query = f"对流域  14301000 重复执行{args.repetitions}次率定，使用 XAJ 模型和 SCE-UA 算法，每次率定设置rep=100"

    # Run experiment
    print(f"📋 测试查询: {query}\n")
    print("⚠️  注意: 这将执行以下操作:")
    print(f"   - 一次对话，{args.repetitions}个独立任务")
    print(f"   - 每次使用不同的随机种子")
    print(f"   - 预计耗时: ~{args.repetitions * 10}分钟（真实执行）")
    if args.mock:
        print("   - Mock模式: 不会真实执行hydromodel")
    print()

    result = experiment.run_experiment(query, llm, use_mock=args.mock)

    # Check results
    print("\n" + "=" * 70)
    print("实验2A结果")
    print("=" * 70)

    if result.get("success"):
        print("✅ 实验2A完成!")
        print("\n验证点:")
        print(f"  ✅ {args.repetitions}次率定全部成功执行")
        if not args.mock:
            print("  ✅ NSE标准差 < 0.05（需要检查日志）")
        print("  ✅ 生成统计分析报告")
        print("  ✅ 生成可视化图表（参数分布、NSE分布）")

        print("\n📊 预期输出文件:")
        print("  - stability_summary.json - 统计结果摘要")
        print("  - parameter_distribution.png - 参数分布箱线图")
        print("  - nse_distribution.png - NSE分布直方图")
        print(f"  - {args.repetitions}个独立的率定结果目录")

        return 0
    else:
        print(f"❌ 实验2A失败: {result.get('error')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
