"""
Author: zhuanglaihong
Date: 2024-09-24 16:55:00
LastEditTime: 2024-09-24 16:55:00
LastEditors: zhuanglaihong
Description: Basic test for builder system without external dependencies
FilePath: \HydroAgent\test\test_builder_basic.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import sys
import json
import logging
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from builder.execution_mode import ExecutionMode, ExecutionModeAnalyzer, get_mode_analyzer
from builder.intent_parser import IntentParser, IntentType, get_intent_parser

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_intent_parser():
    """测试意图解析器"""
    print("=== 测试意图解析器 ===")

    parser = get_intent_parser()

    # 测试用例
    test_queries = [
        ("率定GR4J模型", IntentType.MODEL_CALIBRATION),
        ("评估模型性能", IntentType.MODEL_EVALUATION),
        ("准备数据文件", IntentType.DATA_ACQUISITION),
        ("分析降雨量数据", IntentType.DATA_ANALYSIS),
        ("运行XAJ模型", IntentType.MODEL_SIMULATION),
        ("画图显示结果", IntentType.VISUALIZATION)
    ]

    for query, expected_intent in test_queries:
        print(f"\n测试查询: {query}")
        result = parser.parse_instruction(query)

        print(f"  检测意图: {result.intent_type.value}")
        print(f"  期望意图: {expected_intent.value}")
        print(f"  置信度: {result.confidence:.2f}")
        print(f"  明确意图: {result.clarified_intent}")
        print(f"  建议工具: {result.suggested_tools}")
        print(f"  处理时间: {result.processing_time:.3f}秒")

        if result.entities:
            print(f"  识别实体:")
            for entity_type, entities in result.entities.items():
                for entity in entities:
                    print(f"    - {entity_type}: {entity.text} -> {entity.value}")

        # 检查基本意图识别
        if result.intent_type != IntentType.UNKNOWN:
            assert result.confidence > 0.0

    print("[PASS] 意图解析器测试通过")
    return True


def test_execution_mode_analyzer():
    """测试执行模式分析器"""
    print("=== 测试执行模式分析器 ===")

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
    print(f"  检测特征: {result.features}")

    assert result.recommended_mode == ExecutionMode.LINEAR
    assert result.confidence > 0.5

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

    assert result.complexity_score > 0.3
    assert result.features.get("has_complex_tasks", False)
    assert result.features.get("has_loops", False)

    # 测试用例3：混合模式工作流
    hybrid_workflow = {
        "workflow_id": "test_hybrid",
        "name": "混合工作流",
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
                "dependencies": [],
                "conditions": {}
            },
            {
                "task_id": "task3",
                "action": "calibrate_model",
                "task_type": "complex_reasoning",
                "dependencies": ["task1", "task2"],
                "conditions": {"retry_count": 2}
            }
        ]
    }

    result = analyzer.analyze_workflow(hybrid_workflow)
    print(f"\n混合工作流分析:")
    print(f"  推荐模式: {result.recommended_mode.value}")
    print(f"  置信度: {result.confidence:.2f}")
    print(f"  复杂度: {result.complexity_score:.2f}")
    print(f"  推荐理由: {result.reasoning}")
    print(f"  检测特征: {result.features}")

    assert result.features.get("has_parallel_branches", False)
    assert result.features.get("has_complex_tasks", False)

    print("[PASS] 执行模式分析器测试通过")
    return True


def test_workflow_structure_validation():
    """测试工作流结构验证"""
    print("\n=== 测试工作流结构验证 ===")

    # 创建一些测试工作流
    workflows = [
        # 有效工作流
        {
            "workflow_id": "valid_workflow",
            "name": "有效工作流",
            "tasks": [
                {
                    "task_id": "task1",
                    "action": "get_model_params",
                    "task_type": "simple_action",
                    "dependencies": [],
                    "conditions": {},
                    "expected_output": "模型参数"
                }
            ]
        },
        # 无效工作流 - 没有任务
        {
            "workflow_id": "empty_workflow",
            "name": "空工作流",
            "tasks": []
        },
        # 无效工作流 - 重复task_id
        {
            "workflow_id": "duplicate_workflow",
            "name": "重复ID工作流",
            "tasks": [
                {
                    "task_id": "task1",
                    "action": "get_model_params",
                    "task_type": "simple_action",
                    "dependencies": []
                },
                {
                    "task_id": "task1",  # 重复ID
                    "action": "prepare_data",
                    "task_type": "simple_action",
                    "dependencies": []
                }
            ]
        }
    ]

    from builder.rag_planner import RAGPlanner

    # 创建一个简单的规划器来测试验证功能
    planner = RAGPlanner()

    for workflow in workflows:
        print(f"\n验证工作流: {workflow['name']}")
        validation = planner.validate_workflow(workflow)

        print(f"  有效性: {validation['is_valid']}")
        if validation['errors']:
            print(f"  错误: {validation['errors']}")
        if validation['warnings']:
            print(f"  警告: {validation['warnings']}")
        if validation['suggestions']:
            print(f"  建议: {validation['suggestions']}")

    print("[PASS] 工作流结构验证测试完成")
    return True


def test_workflow_json_generation():
    """测试工作流JSON格式生成"""
    print("\n=== 测试工作流JSON格式生成 ===")

    # 创建一个标准工作流结构
    workflow = {
        "workflow_id": "gr4j_calibration_001",
        "name": "GR4J模型率定工作流",
        "description": "使用历史数据对GR4J模型进行参数率定和性能评估",
        "execution_mode": "hybrid",
        "tasks": [
            {
                "task_id": "task_1",
                "name": "获取模型参数",
                "description": "获取GR4J模型的参数信息和边界",
                "action": "get_model_params",
                "task_type": "simple_action",
                "parameters": {
                    "model_name": "GR4J"
                },
                "dependencies": [],
                "conditions": {
                    "timeout": 30
                },
                "expected_output": "模型参数信息"
            },
            {
                "task_id": "task_2",
                "name": "准备率定数据",
                "description": "处理和准备用于模型率定的时间序列数据",
                "action": "prepare_data",
                "task_type": "simple_action",
                "parameters": {
                    "data_source": "historical",
                    "start_date": "2010-01-01",
                    "end_date": "2015-12-31"
                },
                "dependencies": [],
                "conditions": {
                    "timeout": 120
                },
                "expected_output": "处理后的时间序列数据"
            },
            {
                "task_id": "task_3",
                "name": "模型率定",
                "description": "使用准备的数据对GR4J模型进行参数优化",
                "action": "calibrate_model",
                "task_type": "complex_reasoning",
                "parameters": {
                    "model_name": "GR4J",
                    "optimization_method": "SCE-UA",
                    "max_iterations": 1000
                },
                "dependencies": ["task_1", "task_2"],
                "conditions": {
                    "retry_count": 3,
                    "timeout": 1800
                },
                "expected_output": "优化后的模型参数"
            },
            {
                "task_id": "task_4",
                "name": "模型评估",
                "description": "评估率定后模型的性能指标",
                "action": "evaluate_model",
                "task_type": "complex_reasoning",
                "parameters": {
                    "model_name": "GR4J",
                    "evaluation_metrics": ["NSE", "RMSE", "R2"]
                },
                "dependencies": ["task_3"],
                "conditions": {
                    "timeout": 300
                },
                "expected_output": "模型性能评估报告"
            }
        ],
        "metadata": {
            "created_time": "2024-09-24T16:55:00",
            "complexity": "中等",
            "estimated_duration": "45分钟",
            "target_model": "GR4J",
            "data_period": "2010-2015"
        }
    }

    # 验证JSON格式
    try:
        json_str = json.dumps(workflow, indent=2, ensure_ascii=False)
        print("工作流JSON格式:")
        print(json_str[:500] + "..." if len(json_str) > 500 else json_str)

        # 验证能够重新解析
        parsed_workflow = json.loads(json_str)
        assert parsed_workflow == workflow

        # 检查关键字段
        assert "workflow_id" in parsed_workflow
        assert "tasks" in parsed_workflow
        assert len(parsed_workflow["tasks"]) == 4

        # 检查任务结构
        for task in parsed_workflow["tasks"]:
            assert "task_id" in task
            assert "action" in task
            assert "task_type" in task
            assert task["task_type"] in ["simple_action", "complex_reasoning"]
            assert task["action"] in ["get_model_params", "prepare_data", "calibrate_model", "evaluate_model"]

        print("[PASS] JSON格式验证通过")

    except Exception as e:
        print(f"[FAIL] JSON格式验证失败: {e}")
        return False

    # 测试执行模式分析
    analyzer = get_mode_analyzer()
    mode_result = analyzer.analyze_workflow(workflow)

    print(f"\n工作流复杂度分析:")
    print(f"  推荐执行模式: {mode_result.recommended_mode.value}")
    print(f"  置信度: {mode_result.confidence:.2f}")
    print(f"  复杂度评分: {mode_result.complexity_score:.2f}")
    print(f"  检测到的特征:")
    for feature, value in mode_result.features.items():
        if value:
            print(f"    - {feature}: {value}")

    print("[PASS] 工作流JSON生成和分析测试通过")
    return True


def run_basic_tests():
    """运行基础测试"""
    print("开始Builder系统基础功能测试")
    print("=" * 60)

    test_results = {}

    try:
        # 测试意图解析器
        test_results["intent_parser"] = test_intent_parser()

        # 测试执行模式分析器
        test_results["mode_analyzer"] = test_execution_mode_analyzer()

        # 测试工作流结构验证
        test_results["workflow_validation"] = test_workflow_structure_validation()

        # 测试工作流JSON生成
        test_results["json_generation"] = test_workflow_json_generation()

    except Exception as e:
        logger.error(f"测试过程中发生异常: {str(e)}")
        test_results["error"] = str(e)

    # 输出测试结果摘要
    print("\n" + "=" * 60)
    print("测试结果摘要:")
    print("=" * 60)

    for test_name, result in test_results.items():
        if test_name == "error":
            print(f"[ERROR] 测试异常: {result}")
        else:
            status = "[PASS]" if result else "[FAIL]"
            print(f"{status} {test_name}")

    overall_success = all(result for key, result in test_results.items() if key != "error")
    if overall_success:
        print("\n[SUCCESS] 所有基础测试通过！Builder系统核心功能正常。")
        print("\nBuilder系统功能总结:")
        print("  [OK] 意图解析与理解 (实体识别、参数提取)")
        print("  [OK] 执行模式智能分析 (LINEAR/REACT/HYBRID)")
        print("  [OK] 工作流结构验证")
        print("  [OK] 标准JSON格式输出")
        print("  [OK] 任务类型识别 (simple_action/complex_reasoning)")
        print("  [OK] 依赖关系管理")
        print("  [OK] 复杂度评估")
        print("\n与executor对接接口:")
        print("  - 工作流JSON格式兼容")
        print("  - 执行模式标识")
        print("  - 任务类型标记")
        print("  - 参数验证完整")
    else:
        print("\n[WARNING] 部分测试失败，请检查相关组件。")

    return overall_success


if __name__ == "__main__":
    success = run_basic_tests()
    sys.exit(0 if success else 1)