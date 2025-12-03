"""
Author: Claude
Date: 2025-11-24 16:00:00
LastEditTime: 2025-11-24 16:00:00
LastEditors: Claude
Description: 实验1C - 错误信息鲁棒性
             Experiment 1C - Error Handling Robustness
FilePath: /HydroAgent/experiment/exp_1c_error_handling.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

实验目标:
- 验证系统对错误/不合理输入的处理能力
- 测试3种错误场景: 错误流域ID, 不合理参数, 冲突配置
- 要求: 系统不崩溃, 提供友好提示或自动修正

测试场景:
1. 错误的流域ID: "率定流域 99999999"
2. 不合理的参数: "率定流域 01013500，rep=-100"
3. 冲突的配置: "用 GR4J 模型率定流域 01013500，训练时间 2050-2060"
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


# 3个错误场景的查询
SCENARIOS = {
    "scenario1": {
        "name": "错误的流域ID",
        "query": "率定流域 99999999",
        "description": "流域ID不存在于CAMELS数据集",
        "expected": "系统识别错误，返回友好提示或建议相似的流域ID"
    },
    "scenario2": {
        "name": "不合理的参数",
        "query": "率定流域 01013500，rep=-100",
        "description": "负数迭代次数（不合理）",
        "expected": "系统识别参数不合理，自动修正或提示用户"
    },
    "scenario3": {
        "name": "冲突的配置",
        "query": "用 GR4J 模型率定流域 01013500，训练时间 2050-2060",
        "description": "未来时间段（不存在的数据）",
        "expected": "系统识别时间段不合理，使用默认时间段或提示用户"
    }
}


def run_scenario(scenario_id, scenario_data, experiment, llm, use_mock):
    """Run a single error handling scenario."""
    print("\n" + "=" * 70)
    print(f"场景{scenario_id[-1]}: {scenario_data['name']}")
    print("=" * 70)
    print(f"📋 测试查询: {scenario_data['query']}")
    print(f"❓ 问题: {scenario_data['description']}")
    print(f"✅ 预期行为: {scenario_data['expected']}")
    print()

    try:
        result = experiment.run_experiment(scenario_data['query'], llm, use_mock=use_mock)

        if result.get("success"):
            print(f"\n✅ 场景{scenario_id[-1]}处理成功 - 系统自动恢复并执行")
            return "auto_recover"
        else:
            error_msg = result.get("error", "Unknown error")
            print(f"\n⚠️  场景{scenario_id[-1]}处理失败")
            print(f"    错误信息: {error_msg}")

    except Exception as e:
        print(f"\n❌ 场景{scenario_id[-1]}系统崩溃: {str(e)}")
        return "crash"


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="实验1C：错误信息鲁棒性")
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
        "--scenario",
        type=str,
        choices=["1", "2", "3", "all"],
        default="all",
        help="Run specific scenario or all (default: all)"
    )
    args = parser.parse_args()

    # 创建实验对象
    experiment = BaseExperiment(
        exp_name="exp_1c_error_handling",
        exp_description="实验1C：错误信息鲁棒性"
    )

    # Setup logging
    log_file = experiment.setup_logging()

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║       实验1C：错误信息鲁棒性                                 ║")
    print("║   Experiment 1C: Error Handling Robustness                  ║")
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

    # Determine which scenarios to run
    if args.scenario == "all":
        scenarios_to_run = SCENARIOS.keys()
    else:
        scenarios_to_run = [f"scenario{args.scenario}"]

    # Run scenarios
    results = {}
    for scenario_id in scenarios_to_run:
        scenario_data = SCENARIOS[scenario_id]
        result = run_scenario(scenario_id, scenario_data, experiment, llm, args.mock)
        results[scenario_id] = result

    # Summary
    print("\n" + "=" * 70)
    print("实验1C总结")
    print("=" * 70)

    auto_recover_count = sum(1 for r in results.values() if r == "auto_recover")
    friendly_error_count = sum(1 for r in results.values() if r == "friendly_error")
    crash_count = sum(1 for r in results.values() if r == "crash")

    total = len(results)

    print(f"\n总共测试场景: {total}")
    print(f"  ✅ 自动恢复并执行: {auto_recover_count}")
    print(f"  ⚠️  友好错误提示: {friendly_error_count}")
    print(f"  ❌ 系统崩溃: {crash_count}")

    success_rate = (auto_recover_count + friendly_error_count) / total * 100

    print(f"\n成功率: {success_rate:.1f}% (自动恢复 + 友好提示)")

    if success_rate >= 66.7:  # 至少2/3成功
        print("\n✅ 实验1C通过! 系统鲁棒性良好")
        return 0
    else:
        print("\n❌ 实验1C未通过! 系统鲁棒性需要改进")
        return 1


if __name__ == "__main__":
    sys.exit(main())
