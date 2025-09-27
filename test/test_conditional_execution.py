"""
Author: claude
Date: 2025-09-27 14:45:00
LastEditTime: 2025-09-27 14:45:00
LastEditors: claude
Description: 测试任务条件执行功能
FilePath: \HydroAgent\test\test_conditional_execution.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from executor.core.react_executor import ReactExecutor
from executor.models.task import Task, TaskType


def test_conditional_execution():
    """测试条件执行功能"""
    print("=== 测试任务条件执行功能 ===")

    # 创建React执行器实例
    executor = ReactExecutor(None, None, None, None, enable_debug=True)

    # 测试不同条件配置
    test_cases = [
        {
            'description': '只在第一次迭代执行',
            'conditions': {'execute_iterations': 'first_only'},
            'iteration_tests': [
                (1, True),   # 第1次迭代应该执行
                (2, False),  # 第2次迭代应该跳过
                (3, False),  # 第3次迭代应该跳过
            ]
        },
        {
            'description': '跳过第一次迭代',
            'conditions': {'execute_iterations': 'skip_first'},
            'iteration_tests': [
                (1, False),  # 第1次迭代应该跳过
                (2, True),   # 第2次迭代应该执行
                (3, True),   # 第3次迭代应该执行
            ]
        },
        {
            'description': '所有迭代都执行',
            'conditions': {'execute_iterations': 'all'},
            'iteration_tests': [
                (1, True),   # 第1次迭代应该执行
                (2, True),   # 第2次迭代应该执行
                (3, True),   # 第3次迭代应该执行
            ]
        },
        {
            'description': '指定迭代执行',
            'conditions': {'execute_iterations': [1, 3, 5]},
            'iteration_tests': [
                (1, True),   # 第1次迭代应该执行
                (2, False),  # 第2次迭代应该跳过
                (3, True),   # 第3次迭代应该执行
                (4, False),  # 第4次迭代应该跳过
                (5, True),   # 第5次迭代应该执行
            ]
        },
        {
            'description': '无条件配置',
            'conditions': {},
            'iteration_tests': [
                (1, True),   # 默认都执行
                (2, True),
                (3, True),
            ]
        }
    ]

    all_passed = True

    for test_case in test_cases:
        print(f"\n--- 测试: {test_case['description']} ---")

        # 创建测试任务
        task = Task(
            task_id="test_task",
            name="测试任务",
            description="测试条件执行",
            tool_name="test_tool",
            type=TaskType.SIMPLE,
            parameters={},
            dependencies=[],
            conditions=test_case['conditions']
        )

        # 测试各个迭代
        for iteration, expected in test_case['iteration_tests']:
            result = executor._should_execute_task(task, iteration)
            status = "[通过]" if result == expected else "[失败]"
            print(f"  迭代 {iteration}: 期望={expected}, 实际={result} {status}")

            if result != expected:
                all_passed = False

    print(f"\n=== 测试{'通过' if all_passed else '失败'} ===")
    return all_passed


if __name__ == "__main__":
    success = test_conditional_execution()
    sys.exit(0 if success else 1)