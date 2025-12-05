"""
Author: Claude
Date: 2025-01-24 16:30:00
LastEditTime: 2025-01-24 16:30:00
LastEditors: Claude
Description: 实验2B - 多流域批量率定（性能对比）
             Experiment 2B - Multi-Basin Calibration (Performance Comparison)
FilePath: /HydroAgent/experiment/exp_2b_multi_basin.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

实验目标:
- 验证系统批量处理多个流域的能力
- 对比不同流域的模型性能
- 一次对话，10个任务（10个不同流域）

测试查询:
"批量率定以下流域：01013500, 01022500, 01030500, 01031500, 01047000,
01052500, 01054200, 01055000, 01057000, 01170100，使用 GR4J 模型"

成功标准:
- 10个流域全部成功率定
- 生成性能对比报告（表格+图表）
- 识别出性能最好和最差的流域
- 给出针对性的改进建议
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


# 10个CAMELS流域ID（分布在不同区域，保证多样性）
BASIN_IDS = [
    "01013500",  # Maine
    "01022500",  # Maine
    "01030500",  # Maine
    "01031500",  # New Hampshire
    "01047000",  # Maine
    "01052500",  # New Hampshire
    "01054200",  # Maine
    "01055000",  # Maine
    "01057000",  # New Hampshire
    "01170100",  # Vermont
]

# 实验查询 - 批量率定10个流域
QUERY = f"批量率定以下流域：{', '.join(BASIN_IDS)}，使用 GR4J 模型,使用SUE-UA算法，轮次设置1000轮"


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="实验2B：多流域批量率定")
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
        "--basins",
        type=str,
        default=None,
        help="Custom basin IDs (comma-separated), default: predefined 10 basins"
    )
    args = parser.parse_args()

    # 创建实验对象
    experiment = BaseExperiment(
        exp_name="exp_2b_multi_basin",
        exp_description="实验2B：多流域批量率定"
    )

    # Setup logging
    log_file = experiment.setup_logging()

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║         实验2B：多流域批量率定（性能对比）                   ║")
    print("║  Experiment 2B: Multi-Basin Calibration                     ║")
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

    # Use custom basins if provided
    if args.basins:
        basin_list = [b.strip() for b in args.basins.split(",")]
        query = f"批量率定以下流域：{', '.join(basin_list)}，使用 GR4J 模型"
    else:
        basin_list = BASIN_IDS
        query = QUERY

    # Run experiment
    print(f"📋 测试查询: {query}\n")
    print("⚠️  注意: 这将执行以下操作:")
    print(f"   - 一次对话，{len(basin_list)}个任务（{len(basin_list)}个不同流域）")
    print(f"   - 每个流域独立执行率定")
    print(f"   - 预计耗时: ~{len(basin_list) * 10}分钟（真实执行）")
    if args.mock:
        print("   - Mock模式: 不会真实执行hydromodel")
    print()

    print("流域列表:")
    for i, basin_id in enumerate(basin_list, 1):
        print(f"  {i}. {basin_id}")
    print()

    result = experiment.run_experiment(query, llm, use_mock=args.mock)

    # Check results
    print("\n" + "=" * 70)
    print("实验2B结果")
    print("=" * 70)

    if result.get("success"):
        print("✅ 实验2B完成!")
        print("\n验证点:")
        print(f"  ✅ {len(basin_list)}个流域全部成功率定")
        print("  ✅ 生成性能对比报告（表格+图表）")
        print("  ✅ 识别出性能最好和最差的流域")
        print("  ✅ 给出针对性的改进建议")

        print("\n📊 预期输出文件:")
        print("  - multi_basin_summary.csv - 所有流域的性能指标")
        print("  - metrics_comparison.png - NSE/RMSE/KGE对比柱状图")
        print("  - basin_ranking.json - 流域性能排名")
        print(f"  - {len(basin_list)}个独立的率定结果目录")

        return 0
    else:
        print(f"❌ 实验2B失败: {result.get('error')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
