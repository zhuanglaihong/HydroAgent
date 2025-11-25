"""
Author: Claude
Date: 2025-01-25 10:30:00
LastEditTime: 2025-01-25 10:30:00
LastEditors: Claude
Description: Test checkpoint and resume functionality
             测试checkpoint和恢复功能
FilePath: /HydroAgent/test/test_checkpoint_resume.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

测试场景:
1. 启动一个多任务实验（如重复率定5次）
2. 模拟中断（在第3个任务后）
3. 从checkpoint恢复执行
4. 验证只执行剩余的pending任务
"""

import sys
from pathlib import Path
import io
import json
import logging
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set console encoding (Windows compatible)
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# Setup logging
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)
log_file = logs_dir / f"test_checkpoint_resume_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


def test_checkpoint_creation():
    """
    测试1: 验证checkpoint文件的创建和基本操作
    """
    print("\n" + "=" * 70)
    print("测试1: Checkpoint创建和基本操作")
    print("=" * 70)

    from hydroagent.core.checkpoint_manager import CheckpointManager

    # 创建临时工作目录
    test_workspace = project_root / "test_workspace" / "checkpoint_test_1"
    test_workspace.mkdir(parents=True, exist_ok=True)

    # 初始化checkpoint
    checkpoint = CheckpointManager(test_workspace)
    checkpoint.initialize(
        experiment_name="test_repeated_calibration",
        query="测试查询：重复率定5次",
        total_tasks=0
    )

    print(f"✅ Checkpoint已创建: {checkpoint.checkpoint_file}")

    # 模拟任务计划
    task_plan = {
        "task_type": "repeated_calibration",
        "subtasks": [
            {"task_id": f"task_{i}", "description": f"率定任务 {i}"}
            for i in range(1, 6)
        ]
    }

    checkpoint.save_task_plan(task_plan)
    print(f"✅ 任务计划已保存: {len(task_plan['subtasks'])} 个子任务")

    # 模拟执行前3个任务
    for i in range(1, 4):
        task_id = f"task_{i}"
        config = {"basin_id": "01013500", "model": "gr4j", "task_num": i}
        checkpoint.mark_subtask_started(task_id, config)
        result = {"nse": 0.65 + i * 0.01, "rmse": 2.5}
        checkpoint.mark_subtask_completed(task_id, result)
        print(f"✅ 任务完成: {task_id}")

    # 获取进度摘要
    progress = checkpoint.get_progress_summary()
    print(f"\n当前进度:")
    print(f"  总任务数: {progress['total']}")
    print(f"  已完成: {progress['completed']}")
    print(f"  待执行: {progress['pending']}")
    print(f"  失败: {progress['failed']}")
    print(f"  进度: {progress['progress_percentage']:.1f}%")

    # 验证可以恢复
    can_resume = checkpoint.can_resume()
    print(f"\n可以恢复: {can_resume}")

    assert progress['completed'] == 3, "应该有3个已完成任务"
    assert progress['pending'] == 2, "应该有2个待执行任务"
    assert can_resume, "应该可以恢复执行"

    print("\n✅ 测试1通过!")
    return test_workspace


def test_checkpoint_resume(workspace_path: Path):
    """
    测试2: 验证从checkpoint恢复执行
    """
    print("\n" + "=" * 70)
    print("测试2: 从Checkpoint恢复执行")
    print("=" * 70)

    from hydroagent.core.checkpoint_manager import CheckpointManager

    # 加载checkpoint
    checkpoint = CheckpointManager(workspace_path)
    checkpoint.load()

    print(f"✅ Checkpoint已加载")

    # 获取进度
    progress = checkpoint.get_progress_summary()
    print(f"\n恢复前的进度:")
    print(f"  已完成: {progress['completed']}")
    print(f"  待执行: {progress['pending']}")

    # 获取待执行的任务
    pending_tasks = checkpoint.get_pending_subtasks()
    print(f"\n待执行任务:")
    for task in pending_tasks:
        print(f"  - {task['task_id']}: {task.get('description', 'N/A')}")

    # 继续执行剩余任务
    for task in pending_tasks:
        task_id = task['task_id']
        print(f"\n执行: {task_id}")

        config = {"basin_id": "01013500", "model": "gr4j"}
        checkpoint.mark_subtask_started(task_id, config)

        # 模拟执行
        result = {"nse": 0.70, "rmse": 2.3}
        checkpoint.mark_subtask_completed(task_id, result)
        print(f"✅ 完成: {task_id}")

    # 最终进度
    final_progress = checkpoint.get_progress_summary()
    print(f"\n最终进度:")
    print(f"  已完成: {final_progress['completed']}/{final_progress['total']}")
    print(f"  进度: {final_progress['progress_percentage']:.1f}%")

    # 标记实验完成
    checkpoint.mark_experiment_completed({"analysis": "All tasks completed"})

    assert final_progress['completed'] == 5, "应该有5个已完成任务"
    assert final_progress['pending'] == 0, "不应该有待执行任务"
    assert not checkpoint.can_resume(), "已完成的实验不应该可以恢复"

    print("\n✅ 测试2通过!")


def test_checkpoint_with_failure():
    """
    测试3: 验证任务失败的checkpoint处理
    """
    print("\n" + "=" * 70)
    print("测试3: 任务失败的Checkpoint处理")
    print("=" * 70)

    from hydroagent.core.checkpoint_manager import CheckpointManager

    # 创建新的工作目录
    test_workspace = project_root / "test_workspace" / "checkpoint_test_3"
    test_workspace.mkdir(parents=True, exist_ok=True)

    checkpoint = CheckpointManager(test_workspace)
    checkpoint.initialize(
        experiment_name="test_with_failure",
        query="测试失败处理",
        total_tasks=0
    )

    # 任务计划
    task_plan = {
        "task_type": "test",
        "subtasks": [
            {"task_id": f"task_{i}", "description": f"任务 {i}"}
            for i in range(1, 4)
        ]
    }
    checkpoint.save_task_plan(task_plan)

    # 执行任务1 - 成功
    checkpoint.mark_subtask_started("task_1", {})
    checkpoint.mark_subtask_completed("task_1", {"nse": 0.65})
    print("✅ task_1 完成")

    # 执行任务2 - 失败
    checkpoint.mark_subtask_started("task_2", {})
    checkpoint.mark_subtask_failed("task_2", "模拟错误：数据不可用")
    print("❌ task_2 失败")

    # 获取进度
    progress = checkpoint.get_progress_summary()
    print(f"\n当前进度:")
    print(f"  已完成: {progress['completed']}")
    print(f"  失败: {progress['failed']}")
    print(f"  待执行: {progress['pending']}")

    # 验证失败任务
    failed_tasks = checkpoint.get_failed_subtasks()
    print(f"\n失败任务: {failed_tasks}")

    assert progress['completed'] == 1, "应该有1个已完成任务"
    assert progress['failed'] == 1, "应该有1个失败任务"
    assert checkpoint.can_resume(), "应该可以恢复（重试失败的任务）"

    print("\n✅ 测试3通过!")


def test_checkpoint_data_persistence():
    """
    测试4: 验证checkpoint数据持久化
    """
    print("\n" + "=" * 70)
    print("测试4: Checkpoint数据持久化")
    print("=" * 70)

    from hydroagent.core.checkpoint_manager import CheckpointManager

    # 创建checkpoint
    test_workspace = project_root / "test_workspace" / "checkpoint_test_4"
    test_workspace.mkdir(parents=True, exist_ok=True)

    checkpoint1 = CheckpointManager(test_workspace)
    checkpoint1.initialize(
        experiment_name="test_persistence",
        query="测试持久化",
        total_tasks=0
    )

    task_plan = {
        "task_type": "test",
        "subtasks": [{"task_id": "task_1", "description": "任务1"}]
    }
    checkpoint1.save_task_plan(task_plan)
    checkpoint1.save_intent_result({"intent": "calibration", "model": "gr4j"})

    print("✅ Checkpoint已创建并保存数据")

    # 模拟程序重启 - 创建新的CheckpointManager实例
    checkpoint2 = CheckpointManager(test_workspace)
    loaded_data = checkpoint2.load()

    print("✅ Checkpoint已从文件重新加载")

    # 验证数据完整性
    assert loaded_data['experiment_name'] == "test_persistence"
    assert loaded_data['intent_result']['intent'] == "calibration"
    assert len(loaded_data['subtasks_status']) == 1
    assert 'task_1' in loaded_data['subtasks_status']

    print("\n验证数据完整性:")
    print(f"  实验名称: {loaded_data['experiment_name']}")
    print(f"  Intent: {loaded_data['intent_result']['intent']}")
    print(f"  子任务数: {len(loaded_data['subtasks_status'])}")

    print("\n✅ 测试4通过!")


def main():
    """运行所有测试"""
    print("\n" + "╔" + "=" * 68 + "╗")
    print("║" + "  测试Checkpoint和Resume功能".center(68) + "║")
    print("╚" + "=" * 68 + "╝")

    try:
        # 测试1: Checkpoint创建
        workspace = test_checkpoint_creation()

        # 测试2: 恢复执行
        test_checkpoint_resume(workspace)

        # 测试3: 失败处理
        test_checkpoint_with_failure()

        # 测试4: 数据持久化
        test_checkpoint_data_persistence()

        print("\n" + "=" * 70)
        print("✅ 所有测试通过!")
        print("=" * 70)

        print("\n测试结果目录:")
        print(f"  {project_root / 'test_workspace'}")
        print(f"\n日志文件:")
        print(f"  {log_file}")

        return 0

    except Exception as e:
        logger.error(f"测试失败: {str(e)}", exc_info=True)
        print(f"\n❌ 测试失败: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
