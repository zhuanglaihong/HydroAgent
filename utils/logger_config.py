"""
Author: zhuanglaihong
Date: 2025-01-26 10:30:00
LastEditTime: 2025-01-26 10:30:00
LastEditors: zhuanglaihong
Description: 日志配置工具 - 提供详细日志输出到文件，简化控制台输出
FilePath: /HydroAgent/utils/logger_config.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any


class LoggerConfig:
    """日志配置管理器"""

    def __init__(self, log_dir: str = "./logs", test_name: str = "test"):
        """
        初始化日志配置

        Args:
            log_dir: 日志目录
            test_name: 测试名称，用于日志文件命名
        """
        self.log_dir = Path(log_dir)
        self.test_name = test_name
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 生成日志文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"{test_name}_{timestamp}.log"

        # 保存原始标准输出
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr

    def setup_logging(self, console_level: str = "INFO", file_level: str = "DEBUG"):
        """
        设置日志系统

        Args:
            console_level: 控制台日志级别
            file_level: 文件日志级别
        """
        # 清除已有的handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # 设置根日志级别为最低级别，让handlers自己过滤
        root_logger.setLevel(logging.DEBUG)

        # 创建格式器
        console_formatter = logging.Formatter(
            '[%(levelname)s] %(message)s'
        )

        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s - [%(filename)s:%(lineno)d]'
        )

        # 控制台Handler - 只显示重要信息
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, console_level.upper()))
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

        # 设置控制台编码
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except AttributeError:
            # Python < 3.7
            pass

        # 文件Handler - 详细信息
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(getattr(logging, file_level.upper()))
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

        print(f"日志系统已配置:")
        print(f"  详细日志文件: {self.log_file}")
        print(f"  控制台级别: {console_level}")
        print(f"  文件级别: {file_level}")
        print("-" * 60)

    def get_test_logger(self) -> logging.Logger:
        """获取测试专用logger"""
        logger = logging.getLogger(f"test_{self.test_name}")
        return logger

    def log_test_start(self, test_description: str):
        """记录测试开始"""
        logger = self.get_test_logger()
        print(f"\n{'='*60}")
        print(f"开始测试: {test_description}")
        print(f"{'='*60}")
        logger.info(f"========== 测试开始: {test_description} ==========")

    def log_test_end(self, test_description: str, success: bool):
        """记录测试结束"""
        logger = self.get_test_logger()
        status = "成功" if success else "失败"
        print(f"\n{'='*60}")
        print(f"测试完成: {test_description} - {status}")
        print(f"{'='*60}")
        logger.info(f"========== 测试完成: {test_description} - {status} ==========")

    def log_step(self, step_name: str, status: str = "开始"):
        """记录步骤信息"""
        logger = self.get_test_logger()
        if status == "开始":
            print(f"\n>>> {step_name}...")
        else:
            print(f"    {step_name}: {status}")
        logger.info(f"步骤 [{status}]: {step_name}")

    def log_result(self, task_name: str, result: Dict[str, Any]):
        """记录任务结果"""
        logger = self.get_test_logger()

        # 控制台显示简化结果
        if isinstance(result, dict):
            status = result.get('status', 'unknown')
            if status == 'success' or status == 'completed':
                print(f"    [OK] {task_name}: 成功")
            elif status == 'failed' or status == 'error':
                print(f"    [FAIL] {task_name}: 失败")
                error = result.get('error', result.get('error_message', ''))
                if error:
                    print(f"      错误: {str(error)[:100]}")
            else:
                print(f"    [INFO] {task_name}: {status}")
        else:
            print(f"    [INFO] {task_name}: {result}")

        # 文件记录详细结果
        logger.info(f"任务结果 [{task_name}]: {result}")

    def log_execution_result(self, execution_result):
        """记录执行结果"""
        logger = self.get_test_logger()

        # 终端只显示简要信息
        print(f"\n执行结果:")
        print(f"  执行ID: {execution_result.execution_id}")
        print(f"  状态: {execution_result.status}")
        print(f"  任务数: {len(execution_result.task_results)}")

        # 显示每个任务的执行状态（简化版）
        completed_tasks = sum(1 for task_result in execution_result.task_results.values()
                            if task_result.status == "completed")
        print(f"  成功任务: {completed_tasks}/{len(execution_result.task_results)}")

        # 如果有React迭代信息，显示迭代次数
        if hasattr(execution_result, 'react_iterations') and execution_result.react_iterations:
            print(f"  React迭代: {len(execution_result.react_iterations)}次")

        # 详细结果只记录到文件，不输出到终端
        # logger.info(f"完整执行结果: {execution_result}") TODO
        for task_id, task_result in execution_result.task_results.items():
            logger.info(f"任务详情 [{task_id}]: {task_result}")

    def log_workflow_info(self, workflow: Dict[str, Any]):
        """记录工作流信息"""
        logger = self.get_test_logger()

        print(f"工作流信息:")
        print(f"  ID: {workflow.get('workflow_id', 'unknown')}")
        print(f"  任务数: {len(workflow.get('tasks', []))}")
        print(f"  执行模式: {workflow.get('execution_mode', workflow.get('mode', 'sequential'))}")

        # 详细工作流信息记录到文件
        logger.info(f"完整工作流: {workflow}")

    def cleanup(self):
        """清理资源"""
        # 恢复标准输出
        sys.stdout = self._original_stdout
        sys.stderr = self._original_stderr

        # 关闭文件handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            if isinstance(handler, logging.FileHandler):
                handler.close()
                root_logger.removeHandler(handler)


class TestLoggerContext:
    """测试日志上下文管理器"""

    def __init__(self, test_name: str, test_description: str, log_dir: str = "./logs"):
        self.config = LoggerConfig(log_dir, test_name)
        self.test_description = test_description
        self.success = False

    def __enter__(self):
        self.config.setup_logging()
        self.config.log_test_start(self.test_description)
        return self.config

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.success = exc_type is None
        self.config.log_test_end(self.test_description, self.success)
        self.config.cleanup()
        return False


# 便利函数
def setup_test_logging(test_name: str, log_dir: str = "./logs") -> LoggerConfig:
    """
    快速设置测试日志

    Args:
        test_name: 测试名称
        log_dir: 日志目录

    Returns:
        LoggerConfig: 配置好的日志管理器
    """
    config = LoggerConfig(log_dir, test_name)
    config.setup_logging()
    return config