"""
Author: zhuanglaihong
Date: 2025-01-26 10:45:00
LastEditTime: 2025-01-26 10:45:00
LastEditors: zhuanglaihong
Description: 测试新的日志系统功能
FilePath: /HydroAgent/test/test_logging_system.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.logger_config import TestLoggerContext, LoggerConfig


def test_logger_functionality():
    """测试日志系统的基本功能"""

    # 测试上下文管理器方式
    with TestLoggerContext("logger_test", "日志系统功能测试") as logger_config:

        # 测试步骤记录
        logger_config.log_step("初始化测试环境")
        logger_config.log_step("初始化测试环境", "完成")

        # 测试结果记录
        logger_config.log_result("测试任务1", {"status": "success", "result": "任务执行成功"})
        logger_config.log_result("测试任务2", {"status": "error", "error": "模拟错误"})

        # 测试工作流信息记录
        test_workflow = {
            "workflow_id": "test_workflow_001",
            "name": "测试工作流",
            "tasks": [{"task_id": "task1", "name": "测试任务"}],
            "mode": "sequential"
        }
        logger_config.log_workflow_info(test_workflow)

        # 模拟执行结果
        class MockTaskResult:
            def __init__(self, task_id, status, error=None):
                self.task_id = task_id
                self.status = status
                self.error = error

        class MockExecutionResult:
            def __init__(self):
                self.execution_id = "exec_001"
                self.status = "completed"
                self.task_results = {
                    "task1": MockTaskResult("task1", "completed"),
                    "task2": MockTaskResult("task2", "failed", "模拟任务失败"),
                }

                class MockMetrics:
                    success_rate = 0.5

                self.metrics = MockMetrics()

        mock_result = MockExecutionResult()
        logger_config.log_execution_result(mock_result)

        print("✓ 日志系统测试完成")
        return True


def test_direct_logger_config():
    """测试直接使用LoggerConfig"""
    print("\n=== 测试直接LoggerConfig使用 ===")

    config = LoggerConfig("./logs", "direct_test")
    config.setup_logging()

    config.log_test_start("直接配置测试")

    config.log_step("执行步骤1")
    config.log_result("步骤1结果", {"status": "success"})

    config.log_step("执行步骤2")
    config.log_result("步骤2结果", {"status": "failed", "error": "模拟失败"})

    config.log_test_end("直接配置测试", True)

    config.cleanup()
    print("✓ 直接LoggerConfig测试完成")


if __name__ == "__main__":
    print("开始测试日志系统...")

    # 测试1: 上下文管理器方式
    success1 = test_logger_functionality()

    # 测试2: 直接使用方式
    test_direct_logger_config()

    print(f"\n日志系统测试{'成功' if success1 else '失败'}")
    print("请检查 ./logs 目录下的日志文件内容")