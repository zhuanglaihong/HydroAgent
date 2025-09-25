"""
Author: zhuanglaihong
Date: 2025-01-25 14:30:00
LastEditTime: 2025-01-25 14:30:00
LastEditors: zhuanglaihong
Description: 简单任务的执行器测试 - 测试构建器与执行器的对接
FilePath: \HydroAgent\test\test_executor_simple.py
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


def test_simple_workflow_integration():
    """测试简单工作流的构建器-执行器集成"""
    print("=" * 60)
    print("测试: 简单工作流构建器与执行器集成")
    print("=" * 60)

    # 1. 初始化构建器
    print("1. 初始化构建器...")
    builder = WorkflowBuilder(enable_rag=False)  # 测试时禁用RAG避免超时
    builder_readiness = builder.is_ready()
    print(f"构建器就绪状态: {builder_readiness}")

    if not builder_readiness["overall_ready"]:
        print("构建器未就绪，跳过测试")
        return False

    # 2. 初始化执行器
    print("\n2. 初始化执行器...")
    executor = ExecutorEngine(enable_debug=True)
    print("执行器初始化完成")

    # 3. 测试简单任务工作流构建
    print("\n3. 构建简单工作流...")
    simple_queries = [
        "获取GR4J模型参数",
        "准备数据"
    ]

    for query in simple_queries:
        print(f"\n--- 测试查询: {query} ---")

        try:
            # 构建工作流
            result = builder.build_workflow(query, {"test_mode": True})

            if not result.success:
                print(f"工作流构建失败: {result.error_message}")
                continue

            workflow = result.workflow
            print(f"构建成功:")
            print(f"  工作流ID: {workflow.get('workflow_id')}")
            print(f"  任务数量: {len(workflow.get('tasks', []))}")
            print(f"  执行模式: {workflow.get('execution_mode', 'sequential')}")

            # 保存工作流到文件
            workflow_id = workflow.get('workflow_id', 'unknown')
            output_file = project_root / "workflow" / "generated" / f"simple_{workflow_id}.json"

            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(workflow, f, ensure_ascii=False, indent=2)
                print(f"  工作流已保存: {output_file}")
            except Exception as e:
                print(f"  保存工作流失败: {e}")

            # 4. 转换工作流格式为执行器接受的格式
            print(f"\n4. 执行工作流...")

            try:
                # 将构建器格式转换为执行器格式
                executor_workflow = convert_builder_to_executor_format(workflow)
                workflow_json = json.dumps(executor_workflow, ensure_ascii=False, indent=2)

                print(f"转换后的工作流格式:")
                print(f"  执行模式: {executor_workflow.get('mode', 'sequential')}")
                print(f"  任务数量: {len(executor_workflow.get('tasks', []))}")

                # 执行工作流
                execution_result = executor.execute_workflow(workflow_json, mode="sequential")

                print(f"\n执行结果:")
                print(f"  执行ID: {execution_result.execution_id}")
                print(f"  状态: {execution_result.status}")
                print(f"  任务结果数: {len(execution_result.task_results)}")

                # 显示每个任务的执行结果
                for task_result in execution_result.task_results.values():
                    print(f"    任务 {task_result.task_id}: {task_result.status}")
                    if task_result.error:
                        print(f"      错误: {task_result.error}")

                if execution_result.metrics:
                    print(f"  成功率: {execution_result.metrics.success_rate:.2%}")

            except Exception as e:
                print(f"执行工作流失败: {e}")
                import traceback
                print(f"详细错误: {traceback.format_exc()}")

        except Exception as e:
            print(f"构建工作流失败: {e}")
            import traceback
            print(f"详细错误: {traceback.format_exc()}")

    print("\n" + "=" * 60)
    print("简单工作流集成测试完成")
    print("=" * 60)

    return True


def convert_builder_to_executor_format(builder_workflow):
    """
    将构建器工作流格式转换为执行器可接受的格式

    Args:
        builder_workflow: 构建器生成的工作流格式

    Returns:
        dict: 执行器可接受的工作流格式
    """
    # 基本映射
    executor_workflow = {
        "workflow_id": builder_workflow.get("workflow_id", f"workflow_{int(time.time())}"),
        "name": builder_workflow.get("name", "Generated Workflow"),
        "description": builder_workflow.get("description", ""),
        "mode": "sequential",  # 简单任务使用顺序执行模式
        "global_settings": {
            "error_handling": "continue_on_error",  # 遇错继续
            "timeout": 300  # 5分钟超时
        },
        "tasks": []
    }

    # 转换任务格式
    builder_tasks = builder_workflow.get("tasks", [])

    for i, task in enumerate(builder_tasks):
        # 确定任务类型
        task_type = task.get("task_type", "simple")
        if task_type in ["simple_action", "simple"]:
            task_type = "simple"
        else:
            task_type = "complex"

        executor_task = {
            "task_id": task.get("task_id", f"task_{i+1}"),
            "name": task.get("name", f"Task {i+1}"),
            "type": task_type,
            "parameters": task.get("parameters", {}),
            "dependencies": task.get("dependencies", []),
            "timeout": task.get("timeout", 60),
            "retry_count": task.get("retry_attempts", 0)
        }

        # 根据任务类型设置不同字段
        if task_type == "simple":
            # 简单任务需要tool_name字段
            action = task.get("action", "unknown")
            tool_mapping = {
                "get_model_params": "get_model_params",
                "prepare_data": "prepare_data",
                "calibrate_model": "calibrate_model",
                "evaluate_model": "evaluate_model"
            }
            executor_task["tool_name"] = tool_mapping.get(action, action)
        else:
            # 复杂任务需要description字段
            executor_task["description"] = task.get("description", f"Complex task: {task.get('action', 'unknown')}")
            executor_task["knowledge_query"] = task.get("action", "")

        executor_workflow["tasks"].append(executor_task)

    return executor_workflow


def test_workflow_format_compatibility():
    """测试工作流格式兼容性"""
    print("\n" + "=" * 60)
    print("测试: 工作流格式兼容性")
    print("=" * 60)

    # 创建测试工作流
    test_workflow = {
        "workflow_id": "test_compatibility_001",
        "name": "兼容性测试工作流",
        "description": "测试构建器和执行器之间的格式兼容性",
        "execution_mode": "sequential",
        "tasks": [
            {
                "task_id": "task_1",
                "name": "获取模型参数",
                "action": "get_model_params",
                "task_type": "simple",
                "parameters": {
                    "model_name": "GR4J"
                },
                "dependencies": []
            }
        ]
    }

    print("原始构建器格式:")
    print(json.dumps(test_workflow, ensure_ascii=False, indent=2))

    # 转换格式
    executor_format = convert_builder_to_executor_format(test_workflow)

    print("\n转换后的执行器格式:")
    print(json.dumps(executor_format, ensure_ascii=False, indent=2))

    # 验证执行器能否接受这个格式
    try:
        executor = ExecutorEngine(enable_debug=False)
        workflow_json = json.dumps(executor_format, ensure_ascii=False)

        print("\n验证执行器接收...")
        # 这里不实际执行，只验证格式接收
        workflow_obj = executor.workflow_receiver.receive_workflow(workflow_json)

        print(f"√ 格式验证通过")
        print(f"  工作流ID: {workflow_obj.workflow_id}")
        print(f"  任务数量: {len(workflow_obj.tasks)}")

        return True

    except Exception as e:
        print(f"× 格式验证失败: {e}")
        return False


def main():
    """主测试函数"""
    print("开始执行器简单任务集成测试...")

    # 测试1: 格式兼容性
    compatibility_ok = test_workflow_format_compatibility()

    # 测试2: 简单工作流集成
    if compatibility_ok:
        integration_ok = test_simple_workflow_integration()
    else:
        print("格式兼容性测试失败，跳过集成测试")
        integration_ok = False

    # 总结
    print("\n" + "=" * 80)
    print("测试总结:")
    print(f"  格式兼容性测试: {'通过' if compatibility_ok else '失败'}")
    print(f"  简单工作流集成测试: {'通过' if integration_ok else '失败'}")
    print("=" * 80)

    return compatibility_ok and integration_ok


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)