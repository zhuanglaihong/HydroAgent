"""
Author: Claude
Date: 2025-01-22 21:30:00
LastEditTime: 2025-01-23 00:00:00
LastEditors: Claude
Description: 实验2B - 缺省信息补全
             Experiment 2B - Information Completion
FilePath: /HydroAgent/experiment/exp_2b_missing_info.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

实验目标:
- 验证系统能够自动补全缺省的信息
- 查询: "帮我率定流域 01013500"
- 验证: 自动补全model_name, algorithm, time_period
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

QUERY = "帮我率定流域 01013500"


def main():
    parser = argparse.ArgumentParser(description="实验2B：缺省信息补全")
    parser.add_argument("--backend", type=str, default="api", choices=["ollama", "api"])
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()

    experiment = BaseExperiment(
        exp_name="exp_2b_missing_info",
        exp_description="实验2B：缺省信息补全"
    )

    log_file = experiment.setup_logging()

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║             实验2B：缺省信息补全                             ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"\n📝 日志文件: {log_file}\n")

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
        print("\n🎉 实验2B完成!")
        return 0
    else:
        print(f"\n❌ 实验2B失败: {result.get('error')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
