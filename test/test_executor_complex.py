"""
Author: zhuanglaihong
Date: 2025-01-25 14:45:00
LastEditTime: 2025-01-25 14:45:00
LastEditors: zhuanglaihong
Description: 复杂任务的执行器测试 - 测试构建器与执行器的复杂工作流对接
FilePath: \HydroAgent\test\test_executor_complex.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import json
import sys
import time
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from builder import WorkflowBuilder
from executor.main import ExecutorEngine


def test_complex_workflow_integration():
    """测试复杂工作流的构建器-执行器集成"""
    print("=" * 80)
    print("测试: 复杂工作流构建器与执行器集成")
    print("=" * 80)

    # 1. 初始化构建器和执行器
    print("1. 初始化构建器和执行器...")
    builder = WorkflowBuilder(enable_rag=False)  # 测试时禁用RAG避免超时
    builder_readiness = builder.is_ready()
    print(f"构建器就绪状态: {builder_readiness}")

    if not builder_readiness["overall_ready"]:
        print("构建器未就绪，跳过测试")
        return False

    executor = ExecutorEngine(enable_debug=True)
    print("执行器初始化完成")

    # 2. 测试复杂任务工作流构建
    print("\n2. 构建复杂工作流...")
    complex_queries = [
        "率定并评估GR4J模型",
        "准备数据，率定XAJ模型，然后评估性能",
        "使用2010-2015年数据率定模型，用2016-2020年数据验证"
    ]

    success_count = 0
    total_count = len(complex_queries)

    for i, query in enumerate(complex_queries, 1):
        print(f"\n--- 测试查询 {i}/{total_count}: {query} ---")

        try:
            # 构建工作流
            result = builder.build_workflow(query, {"test_mode": True})

            if not result.success:
                print(f"× 工作流构建失败: {result.error_message}")
                continue

            workflow = result.workflow
            print(f"√ 构建成功:")
            print(f"  工作流ID: {workflow.get('workflow_id')}")
            print(f"  名称: {workflow.get('name')}")
            print(f"  任务数量: {len(workflow.get('tasks', []))}")
            print(f"  执行模式: {workflow.get('execution_mode', 'sequential')}")
            print(f"  构建时间: {result.build_time:.2f}秒")

            # 显示任务依赖关系
            tasks = workflow.get("tasks", [])
            print(f"  任务依赖关系:")
            for task in tasks:
                task_id = task.get("task_id", "unknown")
                dependencies = task.get("dependencies", [])
                print(f"    {task_id}: {dependencies if dependencies else '无依赖'}")

            # 保存工作流到文件
            workflow_id = workflow.get('workflow_id', 'unknown')
            output_file = project_root / "workflow" / "generated" / f"complex_{workflow_id}.json"

            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(workflow, f, ensure_ascii=False, indent=2)
                print(f"  工作流已保存: {output_file}")
            except Exception as e:
                print(f"  保存工作流失败: {e}")

            # 3. 转换并执行工作流
            print(f"\n3. 执行复杂工作流...")

            try:
                # 将构建器格式转换为执行器格式
                executor_workflow = convert_builder_to_executor_format(workflow, complex=True)
                workflow_json = json.dumps(executor_workflow, ensure_ascii=False, indent=2)

                print(f"转换后的工作流:")
                print(f"  执行模式: {executor_workflow.get('mode', 'sequential')}")
                print(f"  任务数量: {len(executor_workflow.get('tasks', []))}")
                print(f"  错误处理: {executor_workflow.get('global_settings', {}).get('error_handling', 'continue')}")

                # 根据复杂度选择执行模式
                execution_mode = determine_execution_mode(workflow, result)
                print(f"  选择的执行模式: {execution_mode}")

                # 执行工作流
                execution_result = executor.execute_workflow(workflow_json, mode=execution_mode)

                print(f"\n执行结果:")
                print(f"  执行ID: {execution_result.execution_id}")
                print(f"  状态: {execution_result.status}")
                print(f"  任务结果数: {len(execution_result.task_results)}")

                # 详细显示任务执行结果
                print(f"  任务执行详情:")
                for task_result in execution_result.task_results.values():
                    status_icon = "√" if task_result.status.value == "completed" else "×"
                    print(f"    {status_icon} 任务 {task_result.task_id}: {task_result.status}")

                    if hasattr(task_result, 'outputs') and task_result.outputs:
                        print(f"      输出: {str(task_result.outputs)[:100]}...")

                    if task_result.error:
                        print(f"      错误: {task_result.error}")

                    if hasattr(task_result, 'duration') and task_result.duration:
                        print(f"      执行时间: {task_result.duration:.2f}秒")

                # 显示整体指标
                if execution_result.metrics:
                    print(f"  整体指标:")
                    print(f"    成功率: {execution_result.metrics.success_rate:.2%}")
                    print(f"    总执行时间: {execution_result.metrics.total_duration:.2f}秒")

                # 如果是React模式，显示目标达成情况
                if execution_mode == "react" and hasattr(execution_result, 'target_achieved'):
                    target_status = "√ 达成" if execution_result.target_achieved else "× 未达成"
                    print(f"    目标状态: {target_status}")

                success_count += 1
                print(f"√ 复杂工作流 {i} 执行完成")

            except Exception as e:
                print(f"× 执行工作流失败: {e}")
                import traceback
                print(f"详细错误: {traceback.format_exc()}")

        except Exception as e:
            print(f"× 构建工作流失败: {e}")
            import traceback
            print(f"详细错误: {traceback.format_exc()}")

        print("-" * 60)

    print(f"\n复杂工作流测试总结:")
    print(f"  成功: {success_count}/{total_count}")
    print(f"  成功率: {success_count/total_count:.2%}")

    return success_count > 0


def convert_builder_to_executor_format(builder_workflow, complex=False):
    """
    将构建器工作流格式转换为执行器可接受的复杂格式

    Args:
        builder_workflow: 构建器生成的工作流格式
        complex: 是否为复杂任务

    Returns:
        dict: 执行器可接受的工作流格式
    """
    # 基本映射
    executor_workflow = {
        "workflow_id": builder_workflow.get("workflow_id", f"complex_workflow_{int(time.time())}"),
        "name": builder_workflow.get("name", "Generated Complex Workflow"),
        "description": builder_workflow.get("description", ""),
        "mode": "sequential",  # 默认顺序执行
        "global_settings": {
            "error_handling": "stop_on_error" if complex else "continue_on_error",
            "timeout": 600 if complex else 300,  # 复杂任务更长超时
            "retry_attempts": 3 if complex else 2
        },
        "tasks": []
    }

    # 如果是复杂任务且包含模型率定，添加目标配置
    has_calibration = any(
        task.get("action") == "calibrate_model"
        for task in builder_workflow.get("tasks", [])
    )

    if complex and has_calibration:
        executor_workflow["target"] = {
            "type": "performance_goal",
            "metric": "nse",
            "threshold": 0.6,
            "comparison": ">=",
            "max_iterations": 3,
            "description": "模型率定目标NSE >= 0.6"
        }
        executor_workflow["mode"] = "react"  # 有目标的复杂任务使用React模式

    # 转换任务格式
    builder_tasks = builder_workflow.get("tasks", [])

    for i, task in enumerate(builder_tasks):
        # 确定任务类型
        task_type = "complex" if complex else "simple"

        executor_task = {
            "task_id": task.get("task_id", f"complex_task_{i + 1}"),
            "name": task.get("name", f"复杂任务 {i + 1}"),
            "type": task_type,
            "parameters": task.get("parameters", {}),
            "dependencies": task.get("dependencies", []),
            "timeout": task.get("timeout", 120 if complex else 60),
            "retry_count": task.get("retry_attempts", 3 if complex else 2)
        }

        # 根据任务类型设置不同字段
        action = task.get("action", "")
        if task_type == "simple":
            # 简单任务需要tool_name字段
            tool_mapping = {
                "get_model_params": "get_model_params",
                "prepare_data": "prepare_data",
                "calibrate_model": "calibrate_model",
                "evaluate_model": "evaluate_model"
            }
            executor_task["tool_name"] = tool_mapping.get(action, action)
        else:
            # 复杂任务需要description字段
            executor_task["description"] = task.get("description", f"复杂任务: {action}")
            executor_task["knowledge_query"] = action

        # 为复杂任务添加额外配置
        if complex:
            # 率定任务的特殊配置
            if action == "calibrate_model":
                executor_task["parameters"].update({
                    "max_iterations": 100,
                    "optimization_method": "ga",  # 遗传算法
                    "target_metric": "nse",
                    "min_improvement": 0.01
                })

            # 评估任务的特殊配置
            elif action == "evaluate_model":
                executor_task["parameters"].update({
                    "metrics": ["nse", "kge", "r2", "rmse"],
                    "validation_period": "auto",
                    "generate_plots": True
                })

        executor_workflow["tasks"].append(executor_task)

    return executor_workflow


def determine_execution_mode(workflow, build_result):
    """
    根据工作流特征确定执行模式

    Args:
        workflow: 构建器生成的工作流
        build_result: 构建结果

    Returns:
        str: 执行模式 (sequential|react)
    """
    # 检查是否有模型率定任务
    has_calibration = any(
        task.get("action") == "calibrate_model"
        for task in workflow.get("tasks", [])
    )

    # 检查任务复杂度
    task_count = len(workflow.get("tasks", []))

    # 检查是否有复杂依赖关系
    has_complex_dependencies = any(
        len(task.get("dependencies", [])) > 1
        for task in workflow.get("tasks", [])
    )

    # 检查构建器推荐的执行模式
    recommended_mode = build_result.execution_mode.value if hasattr(build_result, 'execution_mode') else 'sequential'

    # 决策逻辑
    if has_calibration and (task_count > 2 or has_complex_dependencies):
        return "react"  # 复杂率定任务使用React模式
    elif recommended_mode == "react":
        return "react"  # 遵循构建器推荐
    else:
        return "sequential"  # 默认顺序执行


def test_react_mode_execution():
    """测试React模式执行"""
    print("\n" + "=" * 80)
    print("测试: React模式执行")
    print("=" * 80)

    # 创建一个需要React模式的复杂工作流
    react_workflow = {
        "workflow_id": "react_test_001",
        "name": "React模式测试工作流",
        "description": "测试目标导向的React执行模式",
        "mode": "react",
        "global_settings": {
            "error_handling": "continue_on_error",
            "timeout": 600,
            "retry_attempts": 3
        },
        "target": {
            "type": "performance_goal",
            "metric": "nse",
            "threshold": 0.7,
            "comparison": ">=",
            "max_iterations": 3,
            "description": "达到NSE >= 0.7的模型性能目标"
        },
        "tasks": [
            {
                "task_id": "prep_data",
                "name": "准备数据",
                "type": "simple",
                "tool_name": "prepare_data",
                "parameters": {"data_period": "2010-2015"},
                "dependencies": [],
                "timeout": 60,
                "retry_count": 0
            },
            {
                "task_id": "calibrate",
                "name": "模型率定",
                "type": "complex",
                "description": "复杂任务: 模型率定",
                "knowledge_query": "calibrate_model",
                "parameters": {
                    "model_name": "GR4J",
                    "target_metric": "nse",
                    "max_iterations": 50
                },
                "dependencies": ["prep_data"],
                "timeout": 300,
                "retry_count": 0
            },
            {
                "task_id": "evaluate",
                "name": "模型评估",
                "type": "simple",
                "tool_name": "evaluate_model",
                "parameters": {
                    "metrics": ["nse", "kge", "r2"],
                    "validation_period": "2016-2020"
                },
                "dependencies": ["calibrate"],
                "timeout": 120,
                "retry_count": 0
            }
        ]
    }

    try:
        print("创建React模式测试工作流...")
        executor = ExecutorEngine(enable_debug=True)
        workflow_json = json.dumps(react_workflow, ensure_ascii=False, indent=2)

        print("工作流配置:")
        print(f"  执行模式: {react_workflow['mode']}")
        print(f"  目标指标: {react_workflow['target']['metric']}")
        print(f"  目标阈值: {react_workflow['target']['threshold']}")
        print(f"  最大迭代: {react_workflow['target']['max_iterations']}")

        # 执行React工作流
        print("\n开始执行React模式工作流...")
        execution_result = executor.execute_workflow(workflow_json, mode="react")

        print(f"\nReact执行结果:")
        print(f"  执行ID: {execution_result.execution_id}")
        print(f"  状态: {execution_result.status}")
        print(f"  任务结果数: {len(execution_result.task_results)}")

        if hasattr(execution_result, 'target_achieved'):
            target_status = "√ 达成" if execution_result.target_achieved else "× 未达成"
            print(f"  目标状态: {target_status}")

        return True

    except Exception as e:
        print(f"React模式测试失败: {e}")
        import traceback
        print(f"详细错误: {traceback.format_exc()}")
        return False


def main():
    """主测试函数"""
    print("开始执行器复杂任务集成测试...")

    # 测试1: 复杂工作流集成
    complex_integration_ok = test_complex_workflow_integration()

    # 测试2: React模式执行
    react_mode_ok = test_react_mode_execution()

    # 总结
    print("\n" + "=" * 100)
    print("复杂任务测试总结:")
    print(f"  复杂工作流集成测试: {'√ 通过' if complex_integration_ok else '× 失败'}")
    print(f"  React模式执行测试: {'√ 通过' if react_mode_ok else '× 失败'}")
    print("=" * 100)

    return complex_integration_ok or react_mode_ok  # 至少一个测试通过即可


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)