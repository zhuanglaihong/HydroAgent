"""
Author: zhuanglaihong
Date: 2025-09-27 11:15:00
LastEditTime: 2025-09-27 11:15:00
LastEditors: zhuanglaihong
Description: 测试基于script代码的可运行工作流
FilePath: \HydroAgent\test\test_working_workflows.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import json
import sys
import time
from pathlib import Path
import argparse

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from executor.main import ExecutorEngine
from utils.logger_config import TestLoggerContext, LoggerConfig


def test_individual_workflows(logger_config: LoggerConfig = None):
    """测试各个独立的工作流"""
    if logger_config:
        logger_config.log_step("测试各个独立工作流")
    else:
        print("\n=== 测试各个独立工作流 ===")

    # 初始化执行器
    executor = ExecutorEngine(enable_debug=False)

    working_workflows = [
        "working_prepare_data.json",
        "working_calibrate_model.json",
        "working_evaluate_model.json"
    ]

    success_count = 0
    total_count = len(working_workflows)

    for workflow_file in working_workflows:
        workflow_path = project_root / "workflow" / "example" / workflow_file

        if not workflow_path.exists():
            if logger_config:
                logger_config.log_result(f"工作流文件不存在", {"file": workflow_file, "status": "error"})
            else:
                print(f"工作流文件不存在: {workflow_path}")
            continue

        try:
            with open(workflow_path, 'r', encoding='utf-8') as f:
                workflow_json = f.read()
                workflow = json.loads(workflow_json)

            if logger_config:
                logger_config.log_step(f"执行工作流: {workflow['name']}")
                logger_config.log_workflow_info(workflow)
            else:
                print(f"\n--- 执行工作流: {workflow['name']} ---")
                print(f"文件: {workflow_file}")
                print(f"任务数量: {len(workflow.get('tasks', []))}")
                print(f"基于脚本: {workflow.get('metadata', {}).get('based_on_script', 'unknown')}")

            # 执行工作流
            execution_result = executor.execute_workflow(workflow_json, mode="sequential")

            if logger_config:
                logger_config.log_execution_result(execution_result)
            else:
                print(f"\n执行结果:")
                print(f"  执行ID: {execution_result.execution_id}")
                print(f"  状态: {execution_result.status}")
                print(f"  任务结果数: {len(execution_result.task_results)}")

                for task_result in execution_result.task_results.values():
                    print(f"    任务 {task_result.task_id}: {task_result.status}")
                    if task_result.error:
                        print(f"      错误: {task_result.error}")
                    elif task_result.outputs:
                        # 显示关键输出信息
                        if 'status' in task_result.outputs:
                            print(f"      状态: {task_result.outputs['status']}")
                        if 'message' in task_result.outputs:
                            print(f"      消息: {task_result.outputs['message']}")

            if execution_result.status in ["completed", "success"]:
                success_count += 1

        except Exception as e:
            if logger_config:
                logger_config.log_result(f"执行工作流失败", {"file": workflow_file, "error": str(e), "status": "error"})
            else:
                print(f"执行工作流失败 {workflow_file}: {e}")
                import traceback
                print(f"详细错误: {traceback.format_exc()}")

    success_rate = success_count / total_count if total_count > 0 else 0

    if logger_config:
        logger_config.log_result("独立工作流测试总结", {
            "status": "completed",
            "success_count": success_count,
            "total_count": total_count,
            "success_rate": f"{success_rate:.2%}"
        })
    else:
        print(f"\n独立工作流测试完成: {success_count}/{total_count} 成功 ({success_rate:.2%})")

    return success_count > 0


def test_complete_workflow(logger_config: LoggerConfig = None):
    """测试完整的串联工作流"""
    if logger_config:
        logger_config.log_step("测试完整串联工作流")
    else:
        print("\n=== 测试完整串联工作流 ===")

    # 初始化执行器
    executor = ExecutorEngine(enable_debug=False)

    workflow_path = project_root / "workflow" / "example" / "complete_hydro_workflow.json"

    if not workflow_path.exists():
        if logger_config:
            logger_config.log_result("完整工作流文件不存在", {"status": "error"})
        else:
            print(f"完整工作流文件不存在: {workflow_path}")
        return False

    try:
        with open(workflow_path, 'r', encoding='utf-8') as f:
            workflow_json = f.read()
            workflow = json.loads(workflow_json)

        if logger_config:
            logger_config.log_step(f"执行完整工作流: {workflow['name']}")
            logger_config.log_workflow_info(workflow)
        else:
            print(f"\n--- 执行完整工作流: {workflow['name']} ---")
            print(f"任务数量: {len(workflow.get('tasks', []))}")
            print(f"执行模式: {workflow.get('execution_mode', 'sequential')}")
            print(f"是否有依赖关系: {workflow.get('metadata', {}).get('features', {}).get('has_dependencies', False)}")

        # 执行工作流
        execution_result = executor.execute_workflow(workflow_json, mode="sequential")

        if logger_config:
            logger_config.log_execution_result(execution_result)
        else:
            print(f"\n执行结果:")
            print(f"  执行ID: {execution_result.execution_id}")
            print(f"  状态: {execution_result.status}")
            print(f"  任务结果数: {len(execution_result.task_results)}")

            # 详细显示每个任务的执行结果
            for task_result in execution_result.task_results.values():
                print(f"\n    任务 {task_result.task_id}: {task_result.status}")
                if task_result.error:
                    print(f"      错误: {task_result.error}")
                elif task_result.outputs:
                    # 显示关键输出信息
                    if 'status' in task_result.outputs:
                        print(f"      状态: {task_result.outputs['status']}")
                    if 'message' in task_result.outputs:
                        print(f"      消息: {task_result.outputs['message']}")
                    if 'data_dir' in task_result.outputs:
                        print(f"      数据目录: {task_result.outputs['data_dir']}")
                print(f"      持续时间: {task_result.duration:.2f}秒" if task_result.duration else "      持续时间: 未知")

            if execution_result.metrics:
                print(f"\n  整体成功率: {execution_result.metrics.success_rate:.2%}")
                print(f"  平均任务时长: {execution_result.metrics.average_task_duration:.2f}秒")

        return execution_result.status in ["completed", "success"]

    except Exception as e:
        if logger_config:
            logger_config.log_result("执行完整工作流失败", {"error": str(e), "status": "error"})
        else:
            print(f"执行完整工作流失败: {e}")
            import traceback
            print(f"详细错误: {traceback.format_exc()}")
        return False


def main():
    """主测试函数"""
    parser = argparse.ArgumentParser(description="测试基于script代码的可运行工作流")
    parser.add_argument("--test-individual", action="store_true", help="只测试独立工作流")
    parser.add_argument("--test-complete", action="store_true", help="只测试完整工作流")
    parser.add_argument("--no-log-file", action="store_true", help="不使用日志文件，直接输出到控制台")
    args = parser.parse_args()

    test_name = "working_workflows"
    test_description = "基于script代码的可运行工作流测试"

    if args.no_log_file:
        # 不使用日志文件的旧模式
        print("开始测试基于script代码的可运行工作流...")

        individual_success = True
        complete_success = True

        if not args.test_complete:
            # 测试独立工作流
            individual_success = test_individual_workflows()

        if not args.test_individual:
            # 测试完整工作流
            complete_success = test_complete_workflow()

        # 总结
        print("\n" + "=" * 80)
        print("测试总结:")
        if not args.test_complete:
            print(f"  独立工作流测试: {'通过' if individual_success else '失败'}")
        if not args.test_individual:
            print(f"  完整工作流测试: {'通过' if complete_success else '失败'}")
        print("=" * 80)

        overall_success = individual_success and complete_success
        return overall_success
    else:
        # 使用新的日志系统
        with TestLoggerContext(test_name, test_description) as logger_config:
            individual_success = True
            complete_success = True

            if not args.test_complete:
                # 测试独立工作流
                logger_config.log_step("开始独立工作流测试")
                individual_success = test_individual_workflows(logger_config)
                logger_config.log_step("独立工作流测试", "完成" if individual_success else "失败")

            if not args.test_individual:
                # 测试完整工作流
                logger_config.log_step("开始完整工作流测试")
                complete_success = test_complete_workflow(logger_config)
                logger_config.log_step("完整工作流测试", "完成" if complete_success else "失败")

            # 总结
            overall_success = individual_success and complete_success
            logger_config.log_result("测试总结", {
                "status": "completed",
                "独立工作流测试": "通过" if individual_success else "失败",
                "完整工作流测试": "通过" if complete_success else "失败",
                "overall_success": overall_success
            })

            return overall_success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)