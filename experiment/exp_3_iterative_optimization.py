"""
Author: Claude
Date: 2025-01-22 21:30:00
LastEditTime: 2025-01-23 00:00:00
LastEditors: Claude
Description: 实验3 - 参数自适应优化（两阶段迭代）
             Experiment 3 - Iterative Optimization with Boundary Checking
FilePath: /HydroAgent/experiment/exp_3_iterative_optimization.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

实验目标:
- 验证系统能够执行两阶段迭代优化
- 检查参数是否收敛到边界
- 如果收敛到边界，自动调整参数范围重新率定

测试查询:
"率定流域 14301000，如果参数收敛到边界，自动调整范围重新率定"
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

QUERY = "用xaj模型率定流域14301000,如果参数收敛到边界,自动调整范围重新率定" # basin_id：12025000,01013500,14301000


def main():
    parser = argparse.ArgumentParser(description="实验3：参数自适应优化")
    parser.add_argument("--backend", type=str, default="api", choices=["ollama", "api"])
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()

    experiment = BaseExperiment(
        exp_name="exp_3_iterative_optimization",
        exp_description="实验3：参数自适应优化（两阶段）"
    )

    log_file = experiment.setup_logging()

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║             实验3：参数自适应优化（两阶段）                   ║")
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
        print("\n🎉 实验3完成!")
        return 0
    else:
        print(f"\n❌ 实验3失败: {result.get('error')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
