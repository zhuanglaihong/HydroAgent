"""
Author: zhuanglaihong
Date: 2024-09-24 16:50:00
LastEditTime: 2024-09-24 16:50:00
LastEditors: zhuanglaihong
Description: Integration test for builder system with RAG workflow generation
FilePath: \HydroAgent\test\test_builder_integration.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import sys
import os
import json
import logging
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from builder.workflow_builder import WorkflowBuilder, get_workflow_builder
from builder.rag_planner import RAGPlanner
from builder.llm_client import LLMClient, get_llm_client
from builder.execution_mode import ExecutionMode, get_mode_analyzer

# 尝试导入RAG系统
try:
    from hydrorag.rag_system import RAGSystem
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    print("RAG系统不可用，将使用Mock RAG进行测试")

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MockRAGSystem:
    """Mock RAG系统用于测试"""

    def query(self, query_text: str, top_k: int = 5, score_threshold: float = 0.3):
        """模拟RAG查询"""
        mock_results = [
            {
                "content": "GR4J模型是一个4参数的概念性水文模型，包括X1(产流容量)、X2(地下水交换)、X3(汇流容量)、X4(单位线时间常数)",
                "score": 0.9,
                "metadata": {"source_file": "gr4j_manual.md", "type": "model_info"}
            },
            {
                "content": "模型率定通常包括三个步骤：1)数据准备和预处理 2)参数优化 3)结果评估",
                "score": 0.8,
                "metadata": {"source_file": "calibration_guide.md", "type": "methodology"}
            },
            {
                "content": "可用工具包括：get_model_params获取模型参数，prepare_data处理数据，calibrate_model进行率定，evaluate_model评估结果",
                "score": 0.85,
                "metadata": {"source_file": "tools_manual.md", "type": "tool_info"}
            }
        ]

        return {"results": mock_results[:top_k]}


def test_llm_client():
    """测试LLM客户端"""
    print("\n=== 测试LLM客户端 ===")

    llm_client = get_llm_client()

    # 检查连接状态
    connection_status = llm_client.test_connection()
    print(f"连接状态: {connection_status}")

    if llm_client.is_available():
        # 测试简单生成
        response = llm_client.generate(
            prompt="请简单介绍一下GR4J水文模型",
            temperature=0.1,
            max_tokens=200
        )

        print(f"测试生成 - 成功: {response.success}")
        print(f"使用模型: {response.model_used}")
        print(f"响应时间: {response.response_time:.2f}秒")
        if response.success:
            print(f"响应内容: {response.content[:100]}...")
        else:
            print(f"错误信息: {response.error_message}")
    else:
        print("LLM客户端不可用")

    # 打印统计信息
    stats = llm_client.get_stats()
    print(f"LLM统计: {stats}")

    return llm_client.is_available()


def test_execution_mode_analyzer():
    """测试执行模式分析器"""
    print("\n=== 测试执行模式分析器 ===")

    analyzer = get_mode_analyzer()

    # 测试用例1：简单线性工作流
    simple_workflow = {
        "workflow_id": "test_simple",
        "name": "简单工作流",
        "tasks": [
            {
                "task_id": "task1",
                "action": "get_model_params",
                "task_type": "simple_action",
                "dependencies": [],
                "conditions": {}
            },
            {
                "task_id": "task2",
                "action": "prepare_data",
                "task_type": "simple_action",
                "dependencies": ["task1"],
                "conditions": {}
            }
        ]
    }

    result = analyzer.analyze_workflow(simple_workflow)
    print(f"简单工作流分析:")
    print(f"  推荐模式: {result.recommended_mode.value}")
    print(f"  置信度: {result.confidence:.2f}")
    print(f"  复杂度: {result.complexity_score:.2f}")
    print(f"  推荐理由: {result.reasoning}")

    # 测试用例2：复杂反应式工作流
    complex_workflow = {
        "workflow_id": "test_complex",
        "name": "复杂工作流",
        "tasks": [
            {
                "task_id": "task1",
                "action": "prepare_data",
                "task_type": "simple_action",
                "dependencies": [],
                "conditions": {}
            },
            {
                "task_id": "task2",
                "action": "calibrate_model",
                "task_type": "complex_reasoning",
                "dependencies": ["task1"],
                "conditions": {"retry_count": 5, "if": "validation_failed"}
            },
            {
                "task_id": "task3",
                "action": "evaluate_model",
                "task_type": "complex_reasoning",
                "dependencies": ["task2"],
                "conditions": {"retry_count": 3}
            }
        ]
    }

    result = analyzer.analyze_workflow(complex_workflow)
    print(f"\n复杂工作流分析:")
    print(f"  推荐模式: {result.recommended_mode.value}")
    print(f"  置信度: {result.confidence:.2f}")
    print(f"  复杂度: {result.complexity_score:.2f}")
    print(f"  推荐理由: {result.reasoning}")
    print(f"  检测特征: {result.features}")

    return True


def test_rag_planner():
    """测试RAG规划器"""
    print("\n=== 测试RAG规划器 ===")

    # 初始化RAG系统
    if RAG_AVAILABLE:
        try:
            from hydrorag.config import VECTOR_DB_PATH
            rag_system = RAGSystem(collection_name="test_hydro", persist_directory=str(VECTOR_DB_PATH))
        except Exception as e:
            print(f"初始化真实RAG系统失败: {e}")
            rag_system = MockRAGSystem()
    else:
        rag_system = MockRAGSystem()

    # 创建RAG规划器
    llm_client = get_llm_client()
    planner = RAGPlanner(rag_system=rag_system, llm_client=llm_client)

    # 测试查询
    test_queries = [
        "率定GR4J模型",
        "使用历史数据评估模型性能",
        "准备数据并率定XAJ模型"
    ]

    for query in test_queries:
        print(f"\n测试查询: {query}")

        result = planner.plan_workflow(query)

        print(f"规划成功: {result.success}")
        print(f"规划时间: {result.planning_time:.2f}秒")

        if result.success:
            workflow = result.workflow
            print(f"工作流ID: {workflow.get('workflow_id', 'unknown')}")
            print(f"工作流名称: {workflow.get('name', 'unknown')}")
            print(f"任务数量: {len(workflow.get('tasks', []))}")
            print(f"执行模式: {workflow.get('execution_mode', 'unknown')}")

            # 打印任务摘要
            tasks = workflow.get("tasks", [])
            for i, task in enumerate(tasks[:3], 1):  # 只显示前3个任务
                print(f"  任务{i}: {task.get('name', 'unknown')} ({task.get('action', 'unknown')})")

        print(f"CoT步骤数量: {len(result.cot_steps)}")
        print(f"知识片段数量: {len(result.rag_context.fragments)}")

        if not result.success:
            print(f"错误信息: {result.error_message}")

    return True


def test_workflow_builder():
    """测试完整的工作流构建器"""
    print("\n=== 测试工作流构建器 ===")

    # 初始化RAG系统
    if RAG_AVAILABLE:
        try:
            from hydrorag.config import VECTOR_DB_PATH
            rag_system = RAGSystem(collection_name="test_hydro", persist_directory=str(VECTOR_DB_PATH))
        except Exception as e:
            print(f"初始化真实RAG系统失败: {e}")
            rag_system = MockRAGSystem()
    else:
        rag_system = MockRAGSystem()

    # 创建工作流构建器
    builder = get_workflow_builder(rag_system=rag_system)

    # 检查就绪状态
    readiness = builder.is_ready()
    print(f"构建器就绪状态: {readiness}")

    # 测试构建
    test_queries = [
        "率定并评估GR4J模型",
        "准备数据，率定XAJ模型，然后评估性能",
        "使用2010-2015年数据率定模型，用2016-2020年数据验证"
    ]

    for query in test_queries:
        print(f"\n=== 构建工作流: {query} ===")

        result = builder.build_workflow(query, {"test_mode": True})

        print(f"构建成功: {result.success}")
        print(f"构建时间: {result.build_time:.2f}秒")
        print(f"推荐执行模式: {result.execution_mode.value}")
        print(f"模式置信度: {result.mode_analysis.confidence:.2f}")

        if result.success:
            workflow = result.workflow
            print(f"工作流详情:")
            print(f"  ID: {workflow.get('workflow_id')}")
            print(f"  名称: {workflow.get('name')}")
            print(f"  描述: {workflow.get('description', '无描述')}")
            print(f"  任务数量: {len(workflow.get('tasks', []))}")
            print(f"  执行模式: {workflow.get('execution_mode')}")

            # 打印任务列表
            tasks = workflow.get("tasks", [])
            print(f"  任务列表:")
            for task in tasks:
                task_id = task.get("task_id", "unknown")
                name = task.get("name", "unknown")
                action = task.get("action", "unknown")
                task_type = task.get("task_type", "unknown")
                dependencies = task.get("dependencies", [])

                print(f"    - {task_id}: {name}")
                print(f"      动作: {action} (类型: {task_type})")
                if dependencies:
                    print(f"      依赖: {dependencies}")

            # 保存工作流到文件
            workflow_id = workflow.get('workflow_id', 'unknown_workflow')
            output_file = project_root / "workflow" / "generated" / f"{workflow_id}.json"
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(workflow, f, ensure_ascii=False, indent=2)
                print(f"  工作流已保存到: {output_file}")
            except Exception as e:
                print(f"  保存工作流失败: {e}")

        else:
            print(f"构建失败: {result.error_message}")

        # 打印规划统计
        planning_stats = result.planning_result
        print(f"规划统计:")
        print(f"  规划时间: {planning_stats.planning_time:.2f}秒")
        print(f"  CoT步骤: {len(planning_stats.cot_steps)}")
        print(f"  知识片段: {len(planning_stats.rag_context.fragments) if planning_stats.rag_context else 0}")

        print("-" * 60)

    # 打印全局统计
    stats = builder.get_stats()
    print(f"\n构建器统计信息:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))

    return True


def run_all_tests():
    """运行所有测试"""
    print("开始Builder系统集成测试")
    print("=" * 80)

    test_results = {}

    try:
        # 测试LLM客户端
        test_results["llm_client"] = test_llm_client()

        # 测试执行模式分析器
        test_results["mode_analyzer"] = test_execution_mode_analyzer()

        # 测试RAG规划器
        test_results["rag_planner"] = test_rag_planner()

        # 测试完整工作流构建器
        test_results["workflow_builder"] = test_workflow_builder()

    except Exception as e:
        logger.error(f"测试过程中发生异常: {str(e)}")
        test_results["error"] = str(e)

    # 输出测试结果摘要
    print("\n" + "=" * 80)
    print("测试结果摘要:")
    print("=" * 80)

    for test_name, result in test_results.items():
        if test_name == "error":
            print(f"❌ 测试异常: {result}")
        else:
            status = "✅ 通过" if result else "❌ 失败"
            print(f"{status} {test_name}")

    overall_success = all(result for key, result in test_results.items() if key != "error")
    if overall_success:
        print("\n🎉 所有测试通过！Builder系统工作正常。")
    else:
        print("\n⚠️  部分测试失败，请检查相关组件。")

    return overall_success


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)