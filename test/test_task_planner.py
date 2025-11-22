"""
Author: Claude
Date: 2025-01-22 17:00:00
LastEditTime: 2025-01-22 17:00:00
LastEditors: Claude
Description: Test for TaskPlanner - task decomposition and prompt generation
FilePath: \HydroAgent\test\test_task_planner.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set console encoding (Windows compatible)
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from hydroagent.agents.task_planner import TaskPlanner
from hydroagent.core.llm_interface import create_llm_interface
from hydroagent.core.prompt_pool import PromptPool
import logging
from datetime import datetime


def setup_logging():
    """Setup logging for test."""
    logs_dir = Path(__file__).parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)

    log_file = logs_dir / f"test_task_planner_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding='utf-8')
        ]
    )

    return log_file


def test_decomposition(planner, intent_result, test_name, expected_subtasks):
    """Test a single task decomposition."""
    print("\n" + "="*70)
    print(f"【{test_name}】")
    print("="*70)

    # Print intent info
    task_type = intent_result.get('task_type', 'N/A')
    print(f"Task Type: {task_type}")
    print(f"Expected Subtasks: {expected_subtasks}")
    print()

    # Process
    result = planner.process({"intent_result": intent_result})

    if result.get("success"):
        task_plan = result["task_plan"]
        subtasks = task_plan["subtasks"]
        total = task_plan["total_subtasks"]

        print(f"✅ SUCCESS - {total} subtasks created")
        print()

        # Display each subtask
        for i, subtask in enumerate(subtasks, 1):
            task_id = subtask["task_id"]
            task_type = subtask["task_type"]
            description = subtask["description"]
            dependencies = subtask["dependencies"]

            print(f"  Subtask {i}: {task_id}")
            print(f"    Type:        {task_type}")
            print(f"    Description: {description}")
            if dependencies:
                print(f"    Dependencies: {', '.join(dependencies)}")
            print(f"    Prompt length: {len(subtask['prompt'])} chars")
            print()

        # Validation
        if total == expected_subtasks:
            print(f"  ✅ Subtask count matches expected ({expected_subtasks})")
        else:
            print(f"  ⚠️  Expected {expected_subtasks} subtasks, got {total}")

    else:
        print(f"❌ FAILED: {result.get('error', 'Unknown error')}")


def main():
    """Main test function."""
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║           TaskPlanner Test - 任务拆解测试                 ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    # Setup logging
    log_file = setup_logging()
    print(f"\n📝 Logs: {log_file}")

    # Initialize components (no real LLM needed for decomposition test)
    print("\n正在初始化TaskPlanner...")

    # Use a mock LLM interface (we only test decomposition, not prompt quality)
    try:
        from configs import definitions_private as config
    except ImportError:
        from configs import definitions as config

    # Create LLM interface (won't be used for decomposition logic)
    llm = create_llm_interface('ollama', 'qwen3:8b')

    # Create PromptPool
    workspace_dir = Path(__file__).parent.parent / "test_workspace"
    workspace_dir.mkdir(exist_ok=True)
    prompt_pool = PromptPool(pool_dir=workspace_dir / "prompt_pool")

    # Create TaskPlanner
    planner = TaskPlanner(llm_interface=llm, prompt_pool=prompt_pool, workspace_dir=workspace_dir)
    print("✅ TaskPlanner初始化完成\n")

    # ========================================================================
    # Test Cases
    # ========================================================================

    # Test 1: Standard Calibration (实验1)
    test_decomposition(
        planner,
        intent_result={
            "task_type": "standard_calibration",
            "model_name": "xaj",
            "basin_id": "01013500",
            "algorithm": "SCE_UA",
            "time_period": {
                "train": ["1985-10-01", "1995-09-30"],
                "test": ["2005-10-01", "2014-09-30"]
            },
            "extra_params": {}
        },
        test_name="实验1 - 标准流域验证 (standard_calibration)",
        expected_subtasks=1
    )

    # Test 2: Info Completion (实验2B)
    test_decomposition(
        planner,
        intent_result={
            "task_type": "info_completion",
            "model_name": "xaj",
            "basin_id": "01013500",
            "algorithm": "SCE_UA",
            "time_period": {
                "train": ["1985-10-01", "1995-09-30"],
                "test": ["2005-10-01", "2014-09-30"]
            },
            "extra_params": {}
        },
        test_name="实验2B - 缺省信息补全 (info_completion)",
        expected_subtasks=1
    )

    # Test 3: Iterative Optimization (实验3)
    test_decomposition(
        planner,
        intent_result={
            "task_type": "iterative_optimization",
            "model_name": "gr4j",
            "basin_id": "01013500",
            "algorithm": "SCE_UA",
            "strategy": {
                "phases": ["initial", "boundary_aware"],
                "boundary_threshold": 0.05
            },
            "time_period": {
                "train": ["1985-10-01", "1995-09-30"],
                "test": ["2005-10-01", "2014-09-30"]
            },
            "extra_params": {}
        },
        test_name="实验3 - 两阶段迭代优化 (iterative_optimization)",
        expected_subtasks=2
    )

    # Test 4: Repeated Experiment (实验5)
    test_decomposition(
        planner,
        intent_result={
            "task_type": "repeated_experiment",
            "model_name": "gr4j",
            "basin_id": "01013500",
            "algorithm": "SCE_UA",
            "n_repeats": 10,
            "time_period": {
                "train": ["1985-10-01", "1995-09-30"],
                "test": ["2005-10-01", "2014-09-30"]
            },
            "extra_params": {}
        },
        test_name="实验5 - 稳定性验证 (repeated_experiment)",
        expected_subtasks=11  # 10 repetitions + 1 statistical analysis
    )

    # Test 5: Extended Analysis (实验4)
    test_decomposition(
        planner,
        intent_result={
            "task_type": "extended_analysis",
            "model_name": "gr4j",
            "basin_id": "01013500",
            "algorithm": "SCE_UA",
            "needs": ["runoff_coefficient", "FDC"],
            "time_period": {
                "train": ["1985-10-01", "1995-09-30"],
                "test": ["2005-10-01", "2014-09-30"]
            },
            "extra_params": {}
        },
        test_name="实验4 - 扩展分析 (extended_analysis)",
        expected_subtasks=3  # 1 calibration + 2 analyses
    )

    # Test 6: Batch Processing
    test_decomposition(
        planner,
        intent_result={
            "task_type": "batch_processing",
            "model_name": "gr4j",
            "basin_ids": ["01013500", "01022500"],
            "algorithms": ["SCE_UA", "GA"],
            "time_period": {
                "train": ["1985-10-01", "1995-09-30"],
                "test": ["2005-10-01", "2014-09-30"]
            },
            "extra_params": {}
        },
        test_name="批量处理 - 多流域多算法 (batch_processing)",
        expected_subtasks=4  # 2 basins × 2 algorithms
    )

    # Test 7: Custom Data (实验2C)
    test_decomposition(
        planner,
        intent_result={
            "task_type": "custom_data",
            "model_name": "xaj",
            "basin_id": "custom_basin",
            "algorithm": "SCE_UA",
            "data_source": "D:/my_data",
            "time_period": {
                "train": ["1985-10-01", "1995-09-30"],
                "test": ["2005-10-01", "2014-09-30"]
            },
            "extra_params": {}
        },
        test_name="实验2C - 自定义数据路径 (custom_data)",
        expected_subtasks=1
    )

    print("\n" + "="*70)
    print("✅ 所有测试完成!")
    print("="*70)
    print(f"\n📝 完整日志: {log_file}")


if __name__ == "__main__":
    main()
