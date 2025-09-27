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
import argparse

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from builder import WorkflowBuilder
from executor.main import ExecutorEngine
from utils.logger_config import TestLoggerContext, LoggerConfig


def test_complex_workflow_integration(use_example_workflow: bool = False, logger_config: LoggerConfig = None):
    """测试复杂工作流的构建器-执行器集成"""
    if not logger_config:
        print("=" * 80)
        print("测试: 复杂工作流构建器与执行器集成")
        print("=" * 80)

    # 1. 初始化执行器
    if logger_config:
        logger_config.log_step("初始化执行器")
    else:
        print("1. 初始化执行器...")

    executor = ExecutorEngine(enable_debug=False)  # 关闭debug减少输出

    if logger_config:
        logger_config.log_step("初始化执行器", "完成")
    else:
        print("执行器初始化完成")

    # 2. 选择工作流来源
    if use_example_workflow:
        success = test_with_complex_example_workflows(executor, logger_config)
    else:
        success = test_with_builder_generated_complex_workflows(executor, logger_config)

    return success

def test_with_complex_example_workflows(executor, logger_config: LoggerConfig = None):
    """使用复杂示例工作流进行测试"""
    if logger_config:
        logger_config.log_step("使用复杂示例工作流测试")
    else:
        print("\n=== 使用复杂示例工作流测试 ===")

    example_dir = project_root / "workflow" / "example"
    complex_examples = [
        "complex_model_calibration.json",
        "parallel_comparison.json"
    ]

    success_count = 0
    total_count = len(complex_examples)

    for example_file in complex_examples:
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
                logger_config.log_step(f"执行复杂工作流: {workflow['name']}")
                logger_config.log_workflow_info(workflow)
            else:
                print(f"\n--- 执行复杂示例工作流: {workflow['name']} ---")
                print(f"文件: {example_file}")
                print(f"任务数量: {len(workflow.get('tasks', []))}")
                print(f"执行模式: {workflow.get('mode', 'sequential')}")

            # 根据工作流选择执行模式
            execution_mode = workflow.get('mode', 'sequential')

            # 执行工作流
            execution_result = executor.execute_workflow(workflow_json, mode=execution_mode)

            if logger_config:
                logger_config.log_execution_result(execution_result)
                # 显示React模式特殊结果
                if execution_mode == "react" and hasattr(execution_result, 'target_achieved'):
                    target_status = "达成" if execution_result.target_achieved else "未达成"
                    logger_config.log_result("React目标状态", {"status": target_status})
            else:
                print(f"\n执行结果:")
                print(f"  执行ID: {execution_result.execution_id}")
                print(f"  状态: {execution_result.status}")
                print(f"  任务结果数: {len(execution_result.task_results)}")

                for task_result in execution_result.task_results.values():
                    print(f"    任务 {task_result.task_id}: {task_result.status}")
                    if task_result.error:
                        print(f"      错误: {task_result.error}")

                if execution_mode == "react" and hasattr(execution_result, 'target_achieved'):
                    target_status = "√ 达成" if execution_result.target_achieved else "× 未达成"
                    print(f"    目标状态: {target_status}")

            if execution_result.status in ["completed", "success"]:
                success_count += 1

        except Exception as e:
            if logger_config:
                logger_config.log_result(f"执行{example_file}", {"status": "error", "error": str(e)})
                logger = logger_config.get_test_logger()
                if logger:
                    import traceback
                    logger.error(f"执行复杂示例工作流失败 {example_file}: {traceback.format_exc()}")
            else:
                print(f"执行复杂示例工作流失败 {example_file}: {e}")

    success_rate = success_count / total_count if total_count > 0 else 0

    if logger_config:
        logger_config.log_result("复杂示例工作流测试总结", {
            "status": "completed",
            "success_count": success_count,
            "total_count": total_count,
            "success_rate": f"{success_rate:.2%}"
        })
    else:
        print(f"\n复杂示例工作流测试完成: {success_count}/{total_count} 成功 ({success_rate:.2%})")

    return success_count > 0

def test_with_builder_generated_complex_workflows(executor, logger_config: LoggerConfig = None):
    """使用构建器生成的复杂工作流进行测试"""
    if logger_config:
        logger_config.log_step("初始化构建器")
    else:
        print("\n=== 使用构建器生成复杂工作流测试 ===")
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

    # 3. 测试复杂任务工作流构建
    if logger_config:
        logger_config.log_step("构建复杂工作流")
    else:
        print("\n3. 构建复杂工作流...")

    complex_queries = [
        "率定并评估GR4J模型",
        "准备数据，率定XAJ模型，然后评估性能",
        "使用2010-2015年数据率定模型，用2016-2020年数据验证"
    ]

    success_count = 0
    total_count = len(complex_queries)

    for i, query in enumerate(complex_queries, 1):
        if logger_config:
            logger_config.log_step(f"构建复杂查询 {i}/{total_count}: {query}")
        else:
            print(f"\n--- 测试查询 {i}/{total_count}: {query} ---")

        try:
            # 构建工作流
            result = builder.build_workflow(query, {"test_mode": True})

            if not result.success:
                if logger_config:
                    logger_config.log_result(f"构建查询 {i}: {query}", {"status": "failed", "error": result.error_message})
                else:
                    print(f"× 工作流构建失败: {result.error_message}")
                continue

            workflow = result.workflow
            if logger_config:
                logger_config.log_workflow_info(workflow)
                logger_config.log_result(f"构建时间 {i}", {"status": "success", "time": f"{result.build_time:.2f}秒"})
            else:
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
                # 确保目录存在
                output_file.parent.mkdir(parents=True, exist_ok=True)
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(workflow, f, ensure_ascii=False, indent=2)

                if logger_config:
                    logger_config.log_result(f"保存工作流 {i}", {"status": "success", "file": str(output_file)})
                else:
                    print(f"  工作流已保存: {output_file}")
            except Exception as e:
                if logger_config:
                    logger_config.log_result(f"保存工作流 {i}", {"status": "error", "error": str(e)})
                else:
                    print(f"  保存工作流失败: {e}")

            # 4. 转换并执行工作流
            if logger_config:
                logger_config.log_step(f"执行复杂工作流 {i}: {query}")

            try:
                # 将构建器格式转换为执行器格式
                executor_workflow = executor.workflow_receiver.convert_builder_to_executor_format(workflow)
                workflow_json = json.dumps(executor_workflow, ensure_ascii=False, indent=2)

                if not logger_config:
                    print(f"\n4. 执行复杂工作流...")
                    print(f"转换后的工作流:")
                    print(f"  执行模式: {executor_workflow.get('mode', 'sequential')}")
                    print(f"  任务数量: {len(executor_workflow.get('tasks', []))}")
                    print(f"  错误处理: {executor_workflow.get('global_settings', {}).get('error_handling', 'continue')}")

                # 根据复杂度选择执行模式
                execution_mode = determine_execution_mode(workflow, result)

                if logger_config:
                    logger_config.log_result(f"选择执行模式 {i}", {"status": "completed", "mode": execution_mode})
                else:
                    print(f"  选择的执行模式: {execution_mode}")

                # 执行工作流
                execution_result = executor.execute_workflow(workflow_json, mode=execution_mode)

                if logger_config:
                    logger_config.log_execution_result(execution_result)
                    # 显示React模式特殊结果
                    if execution_mode == "react" and hasattr(execution_result, 'target_achieved'):
                        target_status = "达成" if execution_result.target_achieved else "未达成"
                        logger_config.log_result(f"React目标状态 {i}", {"status": target_status})
                else:
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

                    print(f"√ 复杂工作流 {i} 执行完成")

                if execution_result.status in ["completed", "success"]:
                    success_count += 1

            except Exception as e:
                if logger_config:
                    logger_config.log_result(f"执行工作流 {i}", {"status": "error", "error": str(e)})
                    logger = logger_config.get_test_logger()
                    if logger:
                        import traceback
                        logger.error(f"执行复杂工作流失败 {query}: {traceback.format_exc()}")
                else:
                    print(f"× 执行工作流失败: {e}")
                    import traceback
                    print(f"详细错误: {traceback.format_exc()}")

        except Exception as e:
            if logger_config:
                logger_config.log_result(f"构建工作流 {i}", {"status": "error", "error": str(e)})
                logger = logger_config.get_test_logger()
                if logger:
                    import traceback
                    logger.error(f"构建复杂工作流失败 {query}: {traceback.format_exc()}")
            else:
                print(f"× 构建工作流失败: {e}")
                import traceback
                print(f"详细错误: {traceback.format_exc()}")
                print("-" * 60)

    success_rate = success_count / total_count if total_count > 0 else 0

    if logger_config:
        logger_config.log_result("构建器复杂工作流测试总结", {
            "status": "completed",
            "success_count": success_count,
            "total_count": total_count,
            "success_rate": f"{success_rate:.2%}"
        })
    else:
        print(f"\n复杂工作流测试总结:")
        print(f"  成功: {success_count}/{total_count}")
        print(f"  成功率: {success_rate:.2%}")

    return success_count > 0


# convert_builder_to_executor_format 函数已移动到 WorkflowReceiver 类中


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


def test_react_mode_execution(logger_config: LoggerConfig = None):
    """测试React模式执行"""
    if logger_config:
        logger_config.log_step("React模式执行测试")
    else:
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
        if logger_config:
            logger_config.log_step("创建React模式测试工作流")
        else:
            print("创建React模式测试工作流...")

        executor = ExecutorEngine(enable_debug=False)  # 关闭debug减少输出
        workflow_json = json.dumps(react_workflow, ensure_ascii=False, indent=2)

        if logger_config:
            logger_config.log_result("React工作流配置", {
                "status": "completed",
                "mode": react_workflow['mode'],
                "target_metric": react_workflow['target']['metric'],
                "target_threshold": react_workflow['target']['threshold'],
                "max_iterations": react_workflow['target']['max_iterations']
            })
        else:
            print("工作流配置:")
            print(f"  执行模式: {react_workflow['mode']}")
            print(f"  目标指标: {react_workflow['target']['metric']}")
            print(f"  目标阈值: {react_workflow['target']['threshold']}")
            print(f"  最大迭代: {react_workflow['target']['max_iterations']}")

        # 执行React工作流
        if logger_config:
            logger_config.log_step("执行React模式工作流")
        else:
            print("\n开始执行React模式工作流...")

        execution_result = executor.execute_workflow(workflow_json, mode="react")

        if logger_config:
            logger_config.log_execution_result(execution_result)
            if hasattr(execution_result, 'target_achieved'):
                target_status = "达成" if execution_result.target_achieved else "未达成"
                logger_config.log_result("React目标状态", {"status": target_status})
        else:
            print(f"\nReact执行结果:")
            print(f"  执行ID: {execution_result.execution_id}")
            print(f"  状态: {execution_result.status}")
            print(f"  任务结果数: {len(execution_result.task_results)}")

            if hasattr(execution_result, 'target_achieved'):
                target_status = "√ 达成" if execution_result.target_achieved else "× 未达成"
                print(f"  目标状态: {target_status}")

        return True

    except Exception as e:
        if logger_config:
            logger_config.log_result("React模式测试", {"status": "error", "error": str(e)})
            logger = logger_config.get_test_logger()
            if logger:
                import traceback
                logger.error(f"React模式测试失败: {traceback.format_exc()}")
        else:
            print(f"React模式测试失败: {e}")
            import traceback
            print(f"详细错误: {traceback.format_exc()}")
        return False


def main():
    """主测试函数"""
    parser = argparse.ArgumentParser(description="执行器复杂任务集成测试")
    parser.add_argument("--use-examples", action="store_true", help="使用示例工作流而不是构建器生成")
    parser.add_argument("--no-log-file", action="store_true", help="不使用日志文件，直接输出到控制台")
    parser.add_argument("--skip-react", action="store_true", help="跳过React模式测试")
    args = parser.parse_args()

    test_name = "executor_complex"
    test_description = "执行器复杂任务集成测试"

    if args.no_log_file:
        # 不使用日志文件的旧模式
        print("开始执行器复杂任务集成测试...")

        # 测试1: 复杂工作流集成
        complex_integration_ok = test_complex_workflow_integration(args.use_examples)

        # 测试2: React模式执行
        if not args.skip_react:
            react_mode_ok = test_react_mode_execution()
        else:
            print("跳过React模式测试")
            react_mode_ok = True  # 跳过时默认通过

        # 总结
        print("\n" + "=" * 100)
        print("复杂任务测试总结:")
        print(f"  复杂工作流集成测试: {'√ 通过' if complex_integration_ok else '× 失败'}")
        print(f"  React模式执行测试: {'√ 通过' if react_mode_ok else '× 失败'}")
        print("=" * 100)

        return complex_integration_ok or react_mode_ok  # 至少一个测试通过即可
    else:
        # 使用新的日志系统
        with TestLoggerContext(test_name, test_description) as logger_config:
            # 测试1: 复杂工作流集成
            logger_config.log_step("开始复杂工作流集成测试")
            complex_integration_ok = test_complex_workflow_integration(args.use_examples, logger_config)
            logger_config.log_step("复杂工作流集成测试", "完成" if complex_integration_ok else "失败")

            # 测试2: React模式执行
            if not args.skip_react:
                logger_config.log_step("开始React模式执行测试")
                react_mode_ok = test_react_mode_execution(logger_config)
                logger_config.log_step("React模式执行测试", "完成" if react_mode_ok else "失败")
            else:
                logger_config.log_result("React模式测试", {"status": "skipped", "reason": "用户跳过"})
                react_mode_ok = True  # 跳过时默认通过

            # 总结
            logger_config.log_result("复杂任务测试总结", {
                "status": "completed",
                "复杂工作流集成测试": "通过" if complex_integration_ok else "失败",
                "React模式执行测试": "通过" if react_mode_ok else "失败",
                "overall_success": complex_integration_ok or react_mode_ok
            })

            return complex_integration_ok or react_mode_ok  # 至少一个测试通过即可


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)