"""
Author: Claude
Date: 2025-01-22 21:00:00
LastEditTime: 2025-01-23 00:00:00
LastEditors: Claude
Description: 实验1 - 标准流域验证
             Experiment 1 - Standard Basin Calibration
FilePath: /HydroAgent/experiment/exp_1_standard_calibration.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

实验目标:
- 验证系统能够正确执行标准的单流域率定任务
- 要求: NSE > 0.5, 完整的5-Agent流程

测试查询:
"率定流域 01013500，使用标准 XAJ 模型"
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


# 实验查询
QUERY = "率定camels_us数据集中的01013500流域,使用 XAJ 模型"


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="实验1：标准流域验证")
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
        exp_name="exp_1_standard_calibration",
        exp_description="实验1：标准流域验证"
    )

    # Setup logging
    log_file = experiment.setup_logging()

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║             实验1：标准流域验证                              ║")
    print("║       Experiment 1: Standard Basin Calibration              ║")
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

    # Run experiment
    result = experiment.run_experiment(QUERY, llm, use_mock=args.mock)

    if result.get("success"):
        print("\n🎉 实验1完成!")
        return 0
    else:
        print(f"\n❌ 实验1失败: {result.get('error')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
