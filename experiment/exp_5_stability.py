"""
Author: Claude
Date: 2025-01-22 21:30:00
LastEditTime: 2025-01-23 00:00:00
LastEditors: Claude
Description: 实验5 - 稳定性验证（重复实验）
             Experiment 5 - Stability Verification (Repeated Experiments)
FilePath: /HydroAgent/experiment/exp_5_stability.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

实验目标:
- 验证系统能够执行重复实验
- 使用不同随机种子多次率定
- 进行统计分析评估稳定性

测试查询:
"重复率定流域 01013500 五次，使用不同随机种子"
"""

import sys
from pathlib import Path
import io
import argparse

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from base_experiment import BaseExperiment

QUERY = "重复率定流域 01013500 五次，使用不同随机种子"


def main():
    parser = argparse.ArgumentParser(description="实验5：稳定性验证")
    parser.add_argument("--backend", type=str, default="api", choices=["ollama", "api"])
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()

    experiment = BaseExperiment(
        exp_name="exp_5_stability",
        exp_description="实验5：稳定性验证（重复实验）"
    )

    log_file = experiment.setup_logging()

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║             实验5：稳定性验证（重复实验）                     ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"\n📝 日志文件: {log_file}\n")
    print("⚠️  注意: 此实验需要运行5次率定，耗时较长（约10-30分钟）\n")

    try:
        from configs import definitions_private as config
    except ImportError:
        from configs import definitions as config

    from hydroagent.core.llm_interface import create_llm_interface

    if args.backend == "ollama":
        model = args.model or "qwen3:8b"
        llm = create_llm_interface("ollama", model)
    else:
        api_key = getattr(config, "OPENAI_API_KEY", None)
        base_url = getattr(config, "OPENAI_BASE_URL", None)
        if not api_key:
            print("❌ API key未配置")
            return 1
        model = args.model or "qwen3-max"
        llm = create_llm_interface("openai", model, api_key=api_key, base_url=base_url)

    result = experiment.run_experiment(QUERY, llm, use_mock=args.mock)

    if result.get("success"):
        print("\n🎉 实验5完成!")
        return 0
    else:
        print(f"\n❌ 实验5失败: {result.get('error')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
