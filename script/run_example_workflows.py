"""
Author: zhuanglaihong
Date: 2025-09-27 13:30:00
LastEditTime: 2025-09-27 13:30:00
LastEditors: zhuanglaihong
Description: 运行基于script代码的可运行工作流示例
FilePath: \HydroAgent\script\run_example_workflows.py
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


def run_individual_workflows():
    """运行各个独立的工作流"""
    print("\n=== 运行各个独立工作流 ===")

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
            print(f"工作流文件不存在: {workflow_path}")
            continue

        try:
            with open(workflow_path, 'r', encoding='utf-8') as f:
                workflow_json = f.read()
                workflow = json.loads(workflow_json)

            print(f"\n--- 运行工作流: {workflow['name']} ---")
            print(f"文件: {workflow_file}")
            print(f"任务数量: {len(workflow.get('tasks', []))}")

            start_time = time.time()

            # 执行工作流
            execution_result = executor.execute_workflow(workflow_json, mode="sequential")

            end_time = time.time()
            duration = end_time - start_time

            print(f"\n执行结果:")
            print(f"  执行ID: {execution_result.execution_id}")
            print(f"  状态: {execution_result.status}")
            print(f"  执行时长: {duration:.2f}秒")
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
                print("  ✅ 执行成功")
            else:
                print("  ❌ 执行失败")

        except Exception as e:
            print(f"执行工作流失败 {workflow_file}: {e}")
            import traceback
            print(f"详细错误: {traceback.format_exc()}")

    success_rate = success_count / total_count if total_count > 0 else 0
    print(f"\n独立工作流运行完成: {success_count}/{total_count} 成功 ({success_rate:.2%})")
    return success_count > 0


def run_complete_workflow():
    """运行完整的串联工作流"""
    print("\n=== 运行完整串联工作流 ===")

    # 初始化执行器
    executor = ExecutorEngine(enable_debug=False)

    workflow_path = project_root / "workflow" / "example" / "complete_hydro_workflow.json"

    if not workflow_path.exists():
        print(f"完整工作流文件不存在: {workflow_path}")
        return False

    try:
        with open(workflow_path, 'r', encoding='utf-8') as f:
            workflow_json = f.read()
            workflow = json.loads(workflow_json)

        print(f"\n--- 运行完整工作流: {workflow['name']} ---")
        print(f"任务数量: {len(workflow.get('tasks', []))}")
        print(f"执行模式: {workflow.get('execution_mode', 'sequential')}")

        start_time = time.time()

        # 执行工作流
        execution_result = executor.execute_workflow(workflow_json, mode="sequential")

        end_time = time.time()
        duration = end_time - start_time

        print(f"\n执行结果:")
        print(f"  执行ID: {execution_result.execution_id}")
        print(f"  状态: {execution_result.status}")
        print(f"  总执行时长: {duration:.2f}秒")
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

        success = execution_result.status in ["completed", "success"]
        if success:
            print("  ✅ 完整工作流执行成功")
        else:
            print("  ❌ 完整工作流执行失败")

        return success

    except Exception as e:
        print(f"执行完整工作流失败: {e}")
        import traceback
        print(f"详细错误: {traceback.format_exc()}")
        return False


def main():
    """主运行函数"""
    parser = argparse.ArgumentParser(description="运行基于script代码的可运行工作流示例")
    parser.add_argument("--individual", action="store_true", help="只运行独立工作流")
    parser.add_argument("--complete", action="store_true", help="只运行完整工作流")
    args = parser.parse_args()

    print("开始运行基于script代码的可运行工作流...")
    print("=" * 60)

    individual_success = True
    complete_success = True

    if not args.complete:
        # 运行独立工作流
        individual_success = run_individual_workflows()

    if not args.individual:
        # 运行完整工作流
        complete_success = run_complete_workflow()

    # 总结
    print("\n" + "=" * 80)
    print("运行总结:")
    if not args.complete:
        print(f"  独立工作流: {'✅ 成功' if individual_success else '❌ 失败'}")
    if not args.individual:
        print(f"  完整工作流: {'✅ 成功' if complete_success else '❌ 失败'}")
    print("=" * 80)

    overall_success = individual_success and complete_success
    return overall_success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)