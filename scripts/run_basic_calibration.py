"""
Author: Claude
Date: 2025-12-04 20:45:00
LastEditTime: 2025-12-04 20:45:00
LastEditors: Claude
Description: 最小标准率定测试脚本 - 测试 HydroAgent v5.0 基本功能
FilePath: /HydroAgent/scripts/run_basic_calibration.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import sys
from pathlib import Path
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from hydroagent.system import HydroAgent


def test_basic_calibration(backend="api", use_mock=True):
    """
    测试基础率定功能

    Args:
        backend: LLM后端 ("api" 或 "ollama")
        use_mock: 是否使用mock模式
    """
    print("=" * 80)
    print("HydroAgent v5.0 - Basic Calibration Test")
    print("=" * 80)
    print(f"Backend: {backend}")
    print(f"Mode: {'Mock' if use_mock else 'Real'}")
    print("=" * 80)

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(
                Path(__file__).parent.parent / "logs" / "test_basic_calibration.log",
                encoding='utf-8'
            )
        ]
    )

    # 创建 HydroAgent 实例
    print("\nTest Query: Calibrate GR4J model for basin 01013500\n")

    agent = HydroAgent(
        backend=backend,
        workspace_dir=Path(__file__).parent.parent / "test_results",
        enable_checkpoint=True
    )

    # 初始化
    if not agent.initialize():
        print("Failed to initialize")
        return None

    # 执行查询
    input_data = {
        "query": "率定流域01434000的XAJ模型",
        "use_mock": use_mock,
        "use_v5": True
    }

    print("\nStarting execution...\n")
    result = agent.orchestrator.process(input_data)

    # 打印结果
    print("\n" + "=" * 80)
    print("Execution Results")
    print("=" * 80)
    print(f"Success: {result.get('success')}")
    print(f"Final State: {result.get('final_state')}")
    print(f"Session ID: {result.get('session_id')}")
    print(f"Workspace: {result.get('workspace')}")

    if not result.get('success'):
        print(f"\nFailed:")
        print(f"  Error: {result.get('error', 'Unknown error')}")
        print(f"  Phase: {result.get('error_phase', 'unknown')}")
    else:
        print(f"\nExecution Successful!")

        # 打印意图识别结果
        if result.get('intent'):
            intent = result['intent']
            print(f"\nIntent Analysis:")
            print(f"  Task Type: {intent.get('task_type')}")
            print(f"  Model: {intent.get('model_name')}")
            print(f"  Basin: {intent.get('basin_id')}")
            print(f"  Algorithm: {intent.get('algorithm')}")

        # 打印任务规划
        if result.get('task_plan'):
            task_plan = result['task_plan']
            subtasks = task_plan.get('subtasks', [])
            print(f"\nTask Plan: {len(subtasks)} subtasks")
            for i, task in enumerate(subtasks, 1):
                print(f"  {i}. {task.get('task_type')}")

        # 打印执行结果
        exec_results = result.get('execution_results', [])
        if exec_results:
            print(f"\nExecution Results: {len(exec_results)} tasks")
            for i, res in enumerate(exec_results, 1):
                success = res.get('success', False)
                status = "[OK]" if success else "[FAIL]"
                print(f"  {status} Task {i}: {res.get('task_type', 'unknown')}")
                if success and 'calibration_metrics' in res:
                    metrics = res['calibration_metrics']
                    if metrics:
                        print(f"      NSE_train: {metrics.get('NSE_train', 'N/A')}")
                        print(f"      NSE_test: {metrics.get('NSE_test', 'N/A')}")

    # 打印状态转换历史
    print(f"\nState Transitions: {result.get('total_transitions', 0)} times")
    state_history = result.get('state_history', [])
    if state_history:
        print("  State Flow:")
        for i, transition in enumerate(state_history[:10], 1):  # 只显示前10个
            print(f"    {i}. {transition['from_state']} -> {transition['to_state']}")
        if len(state_history) > 10:
            print(f"    ... ({len(state_history)} total transitions)")

    print("\n" + "=" * 80)

    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="HydroAgent v5.0 基础率定测试")
    parser.add_argument(
        "--backend",
        type=str,
        default="api",
        choices=["api", "ollama"],
        help="LLM后端 (默认: api)"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        default=False,
        help="使用mock模式"
    )
    parser.add_argument(
        "--real",
        action="store_true",
        default=False,
        help="使用真实hydromodel执行"
    )

    args = parser.parse_args()

    # 确定是否使用mock
    use_mock = args.mock or not args.real  # 默认使用mock，除非明确指定--real

    result = test_basic_calibration(backend=args.backend, use_mock=use_mock)

    # 返回退出码
    sys.exit(0 if result and result.get('success') else 1)
