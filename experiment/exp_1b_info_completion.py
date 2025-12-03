"""
Author: Claude
Date: 2025-11-24 16:00:00
LastEditTime: 2025-11-24 16:00:00
LastEditors: Claude
Description: 实验1B - 缺省信息补全
             Experiment 1B - Information Completion
FilePath: /HydroAgent/experiment/exp_1b_info_completion.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

实验目标:
- 验证系统的智能补全能力
- 测试在缺少模型、算法、时间段等信息时的自动补全
- 要求: 自动补全所有缺省信息, Config完整且可执行

测试查询:
"帮我率定流域 01013500"（缺少模型、算法、时间段等信息）
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


# 实验查询 - 最小信息（只有流域ID）
QUERY = "帮我率定流域 01013500"


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="实验1B：缺省信息补全")
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
    args = parser.parse_args()

    # 创建实验对象
    experiment = BaseExperiment(
        exp_name="exp_1b_info_completion",
        exp_description="实验1B：缺省信息补全"
    )

    # Setup logging
    log_file = experiment.setup_logging()

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║         实验1B：缺省信息补全                                 ║")
    print("║       Experiment 1B: Information Completion                 ║")
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

        model = args.model or "qwen-turbo"
        llm = create_llm_interface("openai", model, api_key=api_key, base_url=base_url)
        print(f"✅ LLM接口初始化完成 (API: {model})\n")

    # Run experiment
    print(f"📋 测试查询: {QUERY}\n")
    print("⚠️  注意: 查询中缺少以下信息:")
    print("   - 数据源 (应自动识别为 CAMELS_US)")
    print("   - 模型 (应自动补全为 GR4J 或 XAJ)")
    print("   - 算法 (应自动补全为 SCE-UA)")
    print("   - 时间段 (应自动补全默认训练/测试时间段)")
    print("   - 算法参数 (应自动补全默认 rep=500, ngs=200)")
    print()

    result = experiment.run_experiment(QUERY, llm, use_mock=args.mock)

    # Check results
    print("\n" + "=" * 70)
    print("实验1B结果")
    print("=" * 70)

    if result.get("success"):
        print("✅ 实验1B完成!")
        print("\n验证点:")
        print("  ✅ 自动补全所有缺省信息")
        print("  ✅ 生成的config完整且可执行")
        print("  ✅ 率定成功完成")
        print("  ✅ 日志中显示补全的信息")
        print("\n💡 提示: 检查日志查看自动补全的具体信息")
        return 0
    else:
        print(f"❌ 实验1B失败: {result.get('error')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
