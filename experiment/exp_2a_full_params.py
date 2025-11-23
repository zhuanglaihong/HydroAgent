"""
Author: Claude
Date: 2025-01-22 21:30:00
LastEditTime: 2025-01-23 00:00:00
LastEditors: Claude
Description: 实验2A - 全信息率定
             Experiment 2A - Full Parameter Specification
FilePath: /HydroAgent/experiment/exp_2a_full_params.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

实验目标:
- 验证系统能够正确提取用户指定的所有参数
- 包括算法参数(rep=500, ngs=100)、流域ID、时间段等

测试查询:
"使用 SCE-UA 算法，设置 rep=500, ngs=100，率定 CAMELS_US 的 01013500 流域，时间 1990-2000"
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

QUERY = "使用 SCE-UA 算法，设置 rep=500, ngs=100，率定 CAMELS_US 的 01013500 流域，时间 1990-2000"


def main():
    parser = argparse.ArgumentParser(description="实验2A：全信息率定")
    parser.add_argument("--backend", type=str, default="api", choices=["ollama", "api"])
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()

    experiment = BaseExperiment(
        exp_name="exp_2a_full_params",
        exp_description="实验2A：全信息率定"
    )

    log_file = experiment.setup_logging()

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║             实验2A：全信息率定                               ║")
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
        print("\n🎉 实验2A完成!")
        return 0
    else:
        print(f"\n❌ 实验2A失败: {result.get('error')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
