"""
Author: zhuanglaihong
Date: 2024-09-26 16:35:00
LastEditTime: 2024-09-26 16:35:00
LastEditors: zhuanglaihong
Description: 简单任务的执行器测试 - 测试构建器与执行器的对接
FilePath: \HydroAgent\test\test_executor_simple.py
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

from builder import WorkflowBuilder
from executor.main import ExecutorEngine
from utils.logger_config import TestLoggerContext, LoggerConfig


def test_simple_workflow_integration(use_example_workflow: bool = False, logger_config: LoggerConfig = None):
    """测试简单工作流的构建器-执行器集成"""
    if not logger_config:
        print("=" * 60)
        print("测试: 简单工作流构建器与执行器集成")
        print("=" * 60)

    logger = logger_config.get_test_logger() if logger_config else None

    # 1. 初始化执行器
    if logger_config:
        logger_config.log_step("初始化执行器")
    else:
        print("\n1. 初始化执行器...")

    executor = ExecutorEngine(enable_debug=False)  # 关闭debug减少输出

    if logger_config:
        logger_config.log_step("初始化执行器", "完成")
    else:
        print("执行器初始化完成")

    # 2. 选择工作流来源
    if use_example_workflow:
        success = test_with_example_workflows(executor, logger_config)
    else:
        success = test_with_builder_generated_workflows(executor, logger_config)

    return success

def test_with_example_workflows(executor, logger_config: LoggerConfig = None):
    """使用示例工作流进行测试"""
    if logger_config:
        logger_config.log_step("使用示例工作流测试")
    else:
        print("\n=== 使用示例工作流测试 ===")

    example_dir = project_root / "workflow" / "example"
    simple_examples = [
        "simple_get_model_params.json",
        "simple_prepare_data.json",
        "simple_calibrate_model.json",
        "simple_evaluate_model.json"
    ]

    success_count = 0
    total_count = len(simple_examples)

    for example_file in simple_examples:
        example_path = example_dir / example_file
        if not example_path.exists():
            if logger_config:
                logger_config.log_result(f"加载{example_file}", {"status": "error", "error": "文件不存在"})
            else:
                print(f"示例文件不存在: {example_path}")
            continue

        try:
            with open(example_path, 'r', encoding='utf-8') as f:
                workflow_json = f.read()
                workflow = json.loads(workflow_json)

            if logger_config:
                logger_config.log_step(f"执行工作流: {workflow['name']}")
                logger_config.log_workflow_info(workflow)
            else:
                print(f"\n--- 执行示例工作流: {workflow['name']} ---")
                print(f"文件: {example_file}")
                print(f"任务数量: {len(workflow.get('tasks', []))}")

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

            if execution_result.status in ["completed", "success"]:
                success_count += 1

        except Exception as e:
            if logger_config:
                logger_config.log_result(f"执行{example_file}", {"status": "error", "error": str(e)})
                if logger:
                    import traceback
                    logger.error(f"执行示例工作流失败 {example_file}: {traceback.format_exc()}")
            else:
                print(f"执行示例工作流失败 {example_file}: {e}")

    success_rate = success_count / total_count if total_count > 0 else 0

    if logger_config:
        logger_config.log_result("示例工作流测试总结", {
            "status": "completed",
            "success_count": success_count,
            "total_count": total_count,
            "success_rate": f"{success_rate:.2%}"
        })
    else:
        print(f"\n示例工作流测试完成: {success_count}/{total_count} 成功 ({success_rate:.2%})")

    return success_count > 0

def test_with_builder_generated_workflows(executor, logger_config: LoggerConfig = None):
    """使用构建器生成的工作流进行测试"""
    if logger_config:
        logger_config.log_step("初始化构建器")
    else:
        print("\n=== 使用构建器生成工作流测试 ===")
        print("\n2. 初始化构建器...")

    builder = WorkflowBuilder(enable_rag=False)  # 测试时禁用RAG避免超时
    builder_readiness = builder.is_ready()

    if logger_config:
        logger_config.log_result("构建器就绪检查", {"status": "completed" if builder_readiness["overall_ready"] else "failed", "details": builder_readiness})
    else:
        print(f"构建器就绪状态: {builder_readiness}")

    if not builder_readiness["overall_ready"]:
        if logger_config:
            logger_config.log_result("构建器初始化", {"status": "failed", "error": "构建器未就绪"})
        else:
            print("构建器未就绪，跳过测试")
        return False

    # 3. 测试简单任务工作流构建
    if logger_config:
        logger_config.log_step("构建简单工作流")
    else:
        print("\n3. 构建简单工作流...")

    simple_queries = [
        "获取GR4J模型参数",
        "准备数据",
        "率定水文模型",
        "评估水文模型"
    ]

    success_count = 0
    total_count = len(simple_queries)

    for query in simple_queries:
        if logger_config:
            logger_config.log_step(f"构建查询: {query}")
        else:
            print(f"\n--- 测试查询: {query} ---")

        try:
            # 构建工作流
            result = builder.build_workflow(query, {"test_mode": True})

            if not result.success:
                if logger_config:
                    logger_config.log_result(f"构建查询: {query}", {"status": "failed", "error": result.error_message})
                else:
                    print(f"工作流构建失败: {result.error_message}")
                continue

            workflow = result.workflow
            if logger_config:
                logger_config.log_workflow_info(workflow)
            else:
                print(f"构建成功:")
                print(f"  工作流ID: {workflow.get('workflow_id')}")
                print(f"  任务数量: {len(workflow.get('tasks', []))}")
                print(f"  执行模式: {workflow.get('execution_mode', 'sequential')}")

            # 保存工作流到文件
            workflow_id = workflow.get('workflow_id', 'unknown')
            output_file = project_root / "workflow" / "generated" / f"simple_{workflow_id}.json"

            try:
                # 确保目录存在
                output_file.parent.mkdir(parents=True, exist_ok=True)
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(workflow, f, ensure_ascii=False, indent=2)

                if logger_config:
                    logger_config.log_result(f"保存工作流: {query}", {"status": "success", "file": str(output_file)})
                else:
                    print(f"  工作流已保存: {output_file}")
            except Exception as e:
                if logger_config:
                    logger_config.log_result(f"保存工作流: {query}", {"status": "error", "error": str(e)})
                else:
                    print(f"  保存工作流失败: {e}")

            # 4. 转换工作流格式为执行器接受的格式
            if logger_config:
                logger_config.log_step(f"执行工作流: {query}")

            try:
                # 将构建器格式转换为执行器格式
                executor_workflow = executor.workflow_receiver.convert_builder_to_executor_format(workflow)
                workflow_json = json.dumps(executor_workflow, ensure_ascii=False, indent=2)

                if not logger_config:
                    print(f"\n4. 执行工作流...")
                    print(f"转换后的工作流格式:")
                    print(f"  执行模式: {executor_workflow.get('mode', 'sequential')}")
                    print(f"  任务数量: {len(executor_workflow.get('tasks', []))}")

                # 执行工作流
                execution_result = executor.execute_workflow(workflow_json, mode="sequential")

                if logger_config:
                    logger_config.log_execution_result(execution_result)
                else:
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

                if execution_result.status in ["completed", "success"]:
                    success_count += 1

            except Exception as e:
                if logger_config:
                    logger_config.log_result(f"执行工作流: {query}", {"status": "error", "error": str(e)})
                    if logger:
                        import traceback
                        logger.error(f"执行工作流失败 {query}: {traceback.format_exc()}")
                else:
                    print(f"执行工作流失败: {e}")
                    import traceback
                    print(f"详细错误: {traceback.format_exc()}")

        except Exception as e:
            if logger_config:
                logger_config.log_result(f"构建工作流: {query}", {"status": "error", "error": str(e)})
                if logger:
                    import traceback
                    logger.error(f"构建工作流失败 {query}: {traceback.format_exc()}")
            else:
                print(f"构建工作流失败: {e}")
                import traceback
                print(f"详细错误: {traceback.format_exc()}")

    success_rate = success_count / total_count if total_count > 0 else 0

    if logger_config:
        logger_config.log_result("构建器工作流测试总结", {
            "status": "completed",
            "success_count": success_count,
            "total_count": total_count,
            "success_rate": f"{success_rate:.2%}"
        })
    else:
        print(f"\n构建器工作流测试完成: {success_count}/{total_count} 成功 ({success_rate:.2%})")
        print("\n" + "=" * 60)
        print("简单工作流集成测试完成")
        print("=" * 60)

    return success_count > 0


def test_workflow_format_compatibility(logger_config: LoggerConfig = None):
    """测试工作流格式兼容性"""
    if logger_config:
        logger_config.log_step("工作流格式兼容性测试")
    else:
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

    if not logger_config:
        print("原始构建器格式:")
        print(json.dumps(test_workflow, ensure_ascii=False, indent=2))

    # 转换格式
    executor = ExecutorEngine(enable_debug=False)
    executor_format = executor.workflow_receiver.convert_builder_to_executor_format(test_workflow)

    if not logger_config:
        print("\n转换后的执行器格式:")
        print(json.dumps(executor_format, ensure_ascii=False, indent=2))

    # 验证执行器能否接受这个格式
    try:
        executor = ExecutorEngine(enable_debug=False)
        workflow_json = json.dumps(executor_format, ensure_ascii=False)

        if logger_config:
            logger_config.log_step("验证执行器格式接收")
        else:
            print("\n验证执行器接收...")

        # 这里不实际执行，只验证格式接收
        workflow_obj = executor.workflow_receiver.receive_workflow(workflow_json)

        if logger_config:
            logger_config.log_result("格式兼容性验证", {
                "status": "success",
                "workflow_id": workflow_obj.workflow_id,
                "task_count": len(workflow_obj.tasks)
            })
        else:
            print(f"√ 格式验证通过")
            print(f"  工作流ID: {workflow_obj.workflow_id}")
            print(f"  任务数量: {len(workflow_obj.tasks)}")

        return True

    except Exception as e:
        if logger_config:
            logger_config.log_result("格式兼容性验证", {"status": "error", "error": str(e)})
        else:
            print(f"× 格式验证失败: {e}")
        return False


def main():
    """主测试函数"""
    parser = argparse.ArgumentParser(description="执行器简单任务集成测试")
    parser.add_argument("--use-examples", action="store_true", help="使用示例工作流而不是构建器生成")
    parser.add_argument("--no-log-file", action="store_true", help="不使用日志文件，直接输出到控制台")
    args = parser.parse_args()

    test_name = "executor_simple"
    test_description = "执行器简单任务集成测试"

    if args.no_log_file:
        # 不使用日志文件的旧模式
        print("开始执行器简单任务集成测试...")

        # 测试1: 格式兼容性
        compatibility_ok = test_workflow_format_compatibility()

        # 测试2: 简单工作流集成
        if compatibility_ok:
            integration_ok = test_simple_workflow_integration(args.use_examples)
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
    else:
        # 使用新的日志系统
        with TestLoggerContext(test_name, test_description) as logger_config:
            # 测试1: 格式兼容性
            logger_config.log_step("开始格式兼容性测试")
            compatibility_ok = test_workflow_format_compatibility(logger_config)
            logger_config.log_step("格式兼容性测试", "完成" if compatibility_ok else "失败")

            # 测试2: 简单工作流集成
            if compatibility_ok:
                logger_config.log_step("开始工作流集成测试")
                integration_ok = test_simple_workflow_integration(args.use_examples, logger_config)
                logger_config.log_step("工作流集成测试", "完成" if integration_ok else "失败")
            else:
                logger_config.log_result("集成测试", {"status": "skipped", "reason": "格式兼容性测试失败"})
                integration_ok = False

            # 总结
            logger_config.log_result("测试总结", {
                "status": "completed",
                "格式兼容性测试": "通过" if compatibility_ok else "失败",
                "工作流集成测试": "通过" if integration_ok else "失败",
                "overall_success": compatibility_ok and integration_ok
            })

            return compatibility_ok and integration_ok


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)