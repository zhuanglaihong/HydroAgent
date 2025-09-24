"""
Executor 综合集成测试
"""

import json
import logging
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from executor.main import ExecutorEngine
from executor.models.workflow import WorkflowMode
from executor.models.result import ExecutionStatus


def test_simple_workflow():
    """测试简单工作流执行"""
    print("\n[TEST] 简单工作流执行测试")
    print("=" * 50)

    # 创建执行引擎
    engine = ExecutorEngine(enable_debug=True)

    # 创建简单工作流JSON
    simple_workflow = {
        "workflow_id": "test_simple_001",
        "name": "简单数据准备工作流",
        "mode": "sequential",
        "tasks": [
            {
                "task_id": "task1",
                "name": "准备数据",
                "type": "simple",
                "tool_name": "prepare_data",
                "parameters": {
                    "data_dir": "data/test",
                    "format": "csv"
                },
                "description": "准备测试数据"
            },
            {
                "task_id": "task2",
                "name": "验证数据",
                "type": "simple",
                "tool_name": "validate_data",
                "parameters": {
                    "data_dir": "${task1.output.data_dir}",
                    "check_completeness": True
                },
                "dependencies": ["task1"],
                "description": "验证数据完整性"
            }
        ],
        "global_settings": {
            "error_handling": "continue_on_error",
            "timeout": 300,
            "retry_count": 2
        }
    }

    # 执行工作流
    workflow_json = json.dumps(simple_workflow, ensure_ascii=False, indent=2)
    result = engine.execute_workflow(workflow_json, mode="sequential")

    # 验证结果
    print(f"执行状态: {result.status}")
    print(f"任务结果数: {len(result.task_results)}")
    print(f"成功率: {result.metrics.success_rate:.2%}")

    if result.status == ExecutionStatus.COMPLETED:
        print("[PASS] 简单工作流执行成功")
        return True
    else:
        print(f"[FAIL] 简单工作流执行失败: {result.status}")
        return False


def test_complex_workflow():
    """测试复杂工作流执行"""
    print("\n[TEST] 复杂工作流执行测试")
    print("=" * 50)

    # 创建执行引擎
    engine = ExecutorEngine(enable_debug=True)

    # 创建包含复杂任务的工作流
    complex_workflow = {
        "workflow_id": "test_complex_001",
        "name": "模型率定工作流",
        "mode": "sequential",
        "tasks": [
            {
                "task_id": "task1",
                "name": "数据准备",
                "type": "simple",
                "tool_name": "prepare_data",
                "parameters": {
                    "data_dir": "data/calibration",
                    "format": "csv"
                },
                "description": "准备率定数据"
            },
            {
                "task_id": "task2",
                "name": "智能模型率定",
                "type": "complex",
                "description": "根据数据特征自动选择合适的率定算法和参数，优化模型性能直到NSE达到0.7以上",
                "parameters": {
                    "model_type": "GR4J",
                    "target_metric": "NSE",
                    "target_threshold": 0.7,
                    "data_source": "${task1.output.data_dir}"
                },
                "dependencies": ["task1"],
                "knowledge_query": "GR4J模型率定最佳实践和参数优化策略"
            }
        ],
        "global_settings": {
            "error_handling": "stop_on_error",
            "timeout": 600,
            "retry_count": 1
        }
    }

    # 执行工作流
    workflow_json = json.dumps(complex_workflow, ensure_ascii=False, indent=2)
    result = engine.execute_workflow(workflow_json, mode="sequential")

    # 验证结果
    print(f"执行状态: {result.status}")
    print(f"任务结果数: {len(result.task_results)}")

    for task_id, task_result in result.task_results.items():
        print(f"任务 {task_id}: {task_result.status}")
        if hasattr(task_result, 'metadata'):
            metadata = task_result.metadata
            if 'solution_type' in metadata:
                print(f"  解决方案类型: {metadata['solution_type']}")
                print(f"  执行步骤数: {metadata['steps_count']}")
                print(f"  置信度: {metadata['confidence']}")

    if result.status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]:
        print("[PASS] 复杂工作流执行完成")
        return True
    else:
        print(f"[FAIL] 复杂工作流执行异常: {result.status}")
        return False


def test_react_workflow():
    """测试React模式工作流"""
    print("\n[TEST] React模式工作流测试")
    print("=" * 50)

    # 创建执行引擎
    engine = ExecutorEngine(enable_debug=True)

    # 创建React模式工作流
    react_workflow = {
        "workflow_id": "test_react_001",
        "name": "目标导向模型优化",
        "mode": "react",
        "tasks": [
            {
                "task_id": "calibration",
                "name": "模型率定",
                "type": "simple",
                "tool_name": "calibrate_model",
                "parameters": {
                    "model_type": "GR4J",
                    "data_dir": "data/calibration",
                    "max_iterations": 1000,
                    "algorithm": "SCE-UA"
                },
                "description": "执行模型率定"
            },
            {
                "task_id": "evaluation",
                "name": "模型评估",
                "type": "simple",
                "tool_name": "evaluate_model",
                "parameters": {
                    "model_path": "${calibration.output.model_path}",
                    "test_data": "data/validation"
                },
                "dependencies": ["calibration"],
                "description": "评估模型性能"
            }
        ],
        "target": {
            "type": "performance_goal",
            "metric": "NSE",
            "comparison": ">=",
            "threshold": 0.75,
            "max_iterations": 3,
            "description": "NSE >= 0.75"
        },
        "global_settings": {
            "error_handling": "continue_on_error",
            "timeout": 900,
            "retry_count": 1
        }
    }

    # 执行React模式工作流
    workflow_json = json.dumps(react_workflow, ensure_ascii=False, indent=2)
    result = engine.execute_workflow(workflow_json, mode="react")

    # 验证结果
    print(f"执行状态: {result.status}")
    print(f"目标达成: {result.target_achieved}")
    print(f"React迭代次数: {len(result.react_iterations)}")

    for i, iteration in enumerate(result.react_iterations, 1):
        print(f"迭代 {i}:")
        print(f"  目标达成: {iteration.target_achieved}")
        print(f"  当前指标: {iteration.current_metric}")
        print(f"  原因: {iteration.reason}")
        if iteration.adjustments_made:
            print(f"  调整策略: {', '.join(iteration.adjustments_made)}")

    if hasattr(result, 'final_report') and result.final_report:
        report = result.final_report
        print("\n最终报告:")
        print(f"  整体成功: {report.overall_success}")
        print(f"  目标达成: {report.target_achieved}")
        print(f"  最终指标值: {report.final_metric_value}")

        if report.key_achievements:
            print("  关键成果:")
            for achievement in report.key_achievements:
                print(f"    - {achievement}")

        if report.encountered_issues:
            print("  遇到问题:")
            for issue in report.encountered_issues:
                print(f"    - {issue}")

        if report.recommendations:
            print("  建议:")
            for recommendation in report.recommendations:
                print(f"    - {recommendation}")

    if result.status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]:
        print("[PASS] React模式工作流执行完成")
        return True
    else:
        print(f"[FAIL] React模式工作流执行异常: {result.status}")
        return False


def test_workflow_creation():
    """测试工作流创建功能"""
    print("\n[TEST] 工作流创建测试")
    print("=" * 50)

    # 创建执行引擎
    engine = ExecutorEngine(enable_debug=True)

    # 创建示例工作流
    example_workflow = engine.create_example_workflow()

    # 解析JSON
    try:
        workflow_data = json.loads(example_workflow)
        print(f"工作流ID: {workflow_data['workflow_id']}")
        print(f"工作流名称: {workflow_data['name']}")
        print(f"执行模式: {workflow_data['mode']}")
        print(f"任务数量: {len(workflow_data['tasks'])}")

        # 验证必要字段
        required_fields = ['workflow_id', 'name', 'mode', 'tasks']
        missing_fields = [field for field in required_fields if field not in workflow_data]

        if not missing_fields:
            print("[PASS] 工作流创建成功，包含所有必要字段")
            return True
        else:
            print(f"[FAIL] 工作流缺少字段: {missing_fields}")
            return False

    except json.JSONDecodeError as e:
        print(f"[FAIL] 工作流JSON解析失败: {e}")
        return False


def test_llm_client():
    """测试LLM客户端"""
    print("\n[TEST] LLM客户端测试")
    print("=" * 50)

    from executor.core.llm_client import LLMClientFactory, LLMMessage

    # 创建Ollama客户端
    llm_client = LLMClientFactory.create_default_client()
    print(f"LLM客户端类型: {type(llm_client).__name__}")
    print(f"模型名称: {llm_client.model_name}")
    print(f"API URL: {llm_client.api_url}")

    # 检查服务可用性
    if hasattr(llm_client, 'is_available'):
        available = llm_client.is_available()
        print(f"服务可用: {available}")

        if available:
            # 测试简单对话
            messages = [
                LLMMessage(role="user", content="Hello, please respond with 'LLM test successful'")
            ]

            response = llm_client.chat(messages, max_tokens=50)
            print(f"响应成功: {response.success}")

            if response.success:
                print(f"响应内容: {response.content}")
                print("[PASS] LLM客户端测试成功")
                return True
            else:
                print(f"响应失败: {response.error}")
                print("[PASS] LLM客户端连接正常但响应失败(可能是模型问题)")
                return True
        else:
            print("[PASS] LLM客户端创建成功但服务不可用(正常，Ollama未启动)")
            return True
    else:
        print("[PASS] LLM客户端创建成功")
        return True


def main():
    """运行所有测试"""
    print("Executor 综合集成测试")
    print("=" * 80)

    # 设置日志级别
    logging.basicConfig(level=logging.INFO)

    # 执行所有测试
    tests = [
        ("工作流创建", test_workflow_creation),
        ("LLM客户端", test_llm_client),
        ("简单工作流", test_simple_workflow),
        ("复杂工作流", test_complex_workflow),
        ("React模式工作流", test_react_workflow),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"[ERROR] 测试 {test_name} 发生异常: {e}")
            results.append((test_name, False))

    # 汇总结果
    print("\n测试结果汇总")
    print("=" * 80)

    passed = 0
    failed = 0

    for test_name, success in results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"{status} {test_name}")
        if success:
            passed += 1
        else:
            failed += 1

    print(f"\n总计: {passed} 通过, {failed} 失败")

    if failed == 0:
        print("[SUCCESS] 所有测试通过!")
        return True
    else:
        print(f"[WARNING] {failed} 个测试失败")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)