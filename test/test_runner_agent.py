"""
Author: zhuanglaihong & Claude
Date: 2025-11-20 23:00:00
LastEditTime: 2025-11-20 23:00:00
LastEditors: Claude
Description: Unit tests for RunnerAgent - 执行监控智能体单元测试
FilePath: \\HydroAgent\\test\\test_runner_agent.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import sys
import logging
import json
import copy
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 确保logs目录存在
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

# 设置详细日志
log_file = logs_dir / f"test_runner_agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

# ============================================================================
# 测试配置 - 模拟ConfigAgent的输出
# ============================================================================

CONFIG_AGENT_OUTPUT_1 = {
    "success": True,
    "config": {
        "data_cfgs": {
            "data_source_type": "camels_us",
            "data_source_path": None,
            "basin_ids": ["01013500"],
            "warmup_length": 365,
            "variables": [
                "precipitation",
                "potential_evapotranspiration",
                "streamflow",
            ],
            "train_period": ["2005-01-01", "2010-12-31"],
            "test_period": ["2011-01-01", "2015-12-31"],
        },
        "model_cfgs": {
            "model_name": "gr4j",
            "model_params": {
                "source_type": "sources",
                "source_book": "HF",
                "kernel_size": 15,
            },
        },
        "training_cfgs": {
            "algorithm_name": "SCE_UA",
            "algorithm_params": {
                "rep": 300,
                "ngs": 500,
            },
            "loss_config": {
                "type": "time_series",
                "obj_func": "RMSE",
            },
            "output_dir": str(project_root / "results" / "test_runner"),
            "experiment_name": "gr4j_SCE_UA_test",
            "random_seed": 1234,
            "save_config": True,
        },
        "evaluation_cfgs": {
            "metrics": ["NSE", "RMSE", "KGE", "PBIAS"],
            "save_results": True,
            "plot_results": True,
        },
    },
    "config_summary": "Test config for GR4J calibration",
    "intent_result": {
        "intent": "calibration",
        "model_name": "gr4j",
        "basin_id": "01013500",
    }
}


def print_test_header(test_num: int, description: str):
    """打印测试标题"""
    print("\n" + "=" * 70)
    print(f"Test Case {test_num}: {description}")
    print("=" * 70)


def test_runner_agent_initialization():
    """测试1: RunnerAgent初始化"""
    print_test_header(1, "RunnerAgent 初始化测试")

    from hydroagent.agents.runner_agent import RunnerAgent
    from hydroagent.core.llm_interface import create_llm_interface

    # 创建RunnerAgent
    llm = create_llm_interface('ollama', 'qwen3:8b')
    workspace_dir = project_root / "results" / "test_runner"
    workspace_dir.mkdir(parents=True, exist_ok=True)

    runner_agent = RunnerAgent(
        llm_interface=llm,
        workspace_dir=workspace_dir,
        timeout=3600
    )

    # 验证初始化
    assert runner_agent.name == "RunnerAgent", "Agent名称不匹配"
    assert runner_agent.workspace_dir == workspace_dir, "工作目录不匹配"
    assert runner_agent.timeout == 3600, "超时设置不匹配"

    print("✅ RunnerAgent 初始化测试通过")

    return runner_agent


def test_runner_agent_mock_calibration():
    """测试2: Mock率定测试（不调用真实hydromodel）"""
    print_test_header(2, "Mock 率定测试")

    from hydroagent.agents.runner_agent import RunnerAgent
    from hydroagent.core.llm_interface import create_llm_interface

    llm = create_llm_interface('ollama', 'qwen3:8b')
    workspace_dir = project_root / "results" / "test_runner"
    runner_agent = RunnerAgent(llm_interface=llm, workspace_dir=workspace_dir)

    # Mock hydromodel的calibrate函数
    mock_calibrate_result = {
        "best_params": {
            "x1": 350.0,
            "x2": 0.5,
            "x3": 100.0,
            "x4": 2.0
        },
        "metrics": {
            "NSE": 0.85,
            "RMSE": 2.5,
            "KGE": 0.82
        },
        "output_files": [
            "results/calibrated_params.json",
            "results/performance_plot.png"
        ]
    }

    # Mock hydromodel的calibrate函数
    # 由于虚拟环境中hydromodel可能缺少依赖导致导入失败
    # 我们创建一个模拟的hydromodel模块
    mock_hydromodel = MagicMock()
    mock_hydromodel.calibrate = Mock(return_value=mock_calibrate_result)
    mock_hydromodel.evaluate = Mock(return_value={})  # 提供evaluate函数

    with patch.dict('sys.modules', {'hydromodel': mock_hydromodel}):
        # 调用RunnerAgent
        result = runner_agent.process(CONFIG_AGENT_OUTPUT_1)

        # 验证结果
        assert result["success"], f"执行失败: {result.get('error')}"
        assert result["mode"] == "calibrate", "执行模式不匹配"
        assert "result" in result, "结果中缺少result字段"

        inner_result = result["result"]
        assert inner_result["status"] == "success", "内部状态不是success"
        assert "metrics" in inner_result, "结果中缺少metrics"
        assert "best_params" in inner_result, "结果中缺少best_params"

        # 验证指标
        metrics = inner_result["metrics"]
        assert "NSE" in metrics, "缺少NSE指标"
        assert metrics["NSE"] == 0.85, "NSE值不匹配"

        print("✅ Mock 率定测试通过")
        print(f"   最佳参数: {inner_result['best_params']}")
        print(f"   性能指标: {inner_result['metrics']}")

    return result


def test_runner_agent_mock_evaluation():
    """测试3: Mock评估测试"""
    print_test_header(3, "Mock 评估测试")

    from hydroagent.agents.runner_agent import RunnerAgent
    from hydroagent.core.llm_interface import create_llm_interface

    llm = create_llm_interface('ollama', 'qwen3:8b')
    workspace_dir = project_root / "results" / "test_runner"
    runner_agent = RunnerAgent(llm_interface=llm, workspace_dir=workspace_dir)

    # 准备评估配置（使用深拷贝避免修改原始配置）
    eval_config = copy.deepcopy(CONFIG_AGENT_OUTPUT_1)
    eval_config["intent_result"]["intent"] = "evaluation"

    # Mock hydromodel的evaluate函数
    mock_evaluate_result = {
        "performance": {
            "NSE": 0.82,
            "RMSE": 2.8,
            "KGE": 0.79,
            "PBIAS": 5.2
        },
        "output_files": [
            "results/evaluation_report.csv",
            "results/timeseries_plot.png"
        ]
    }

    # Mock hydromodel的evaluate函数
    # 创建模拟的hydromodel模块
    mock_hydromodel = MagicMock()
    mock_hydromodel.evaluate = Mock(return_value=mock_evaluate_result)
    mock_hydromodel.calibrate = Mock(return_value={})  # 提供calibrate函数

    with patch.dict('sys.modules', {'hydromodel': mock_hydromodel}):
        # 调用RunnerAgent
        result = runner_agent.process(eval_config)

        # 验证结果
        assert result["success"], f"执行失败: {result.get('error')}"
        assert result["mode"] == "evaluate", "执行模式不匹配"

        inner_result = result["result"]
        assert inner_result["status"] == "success", "内部状态不是success"
        assert "metrics" in inner_result or "performance" in inner_result, "结果中缺少性能指标"

        print("✅ Mock 评估测试通过")
        print(f"   性能指标: {inner_result.get('metrics') or inner_result.get('performance')}")

    return result


def test_runner_agent_error_handling():
    """测试4: 错误处理测试"""
    print_test_header(4, "错误处理测试")

    from hydroagent.agents.runner_agent import RunnerAgent
    from hydroagent.core.llm_interface import create_llm_interface

    llm = create_llm_interface('ollama', 'qwen3:8b')
    workspace_dir = project_root / "results" / "test_runner"
    runner_agent = RunnerAgent(llm_interface=llm, workspace_dir=workspace_dir)

    # Mock一个抛出异常的calibrate函数
    def mock_calibrate_error(config):
        raise ValueError("模拟的率定错误：参数超出范围")

    # 创建模拟的hydromodel模块，其calibrate函数会抛出异常
    mock_hydromodel = MagicMock()
    mock_hydromodel.calibrate = Mock(side_effect=mock_calibrate_error)
    # 同时提供evaluate函数（即使不会被调用）
    mock_hydromodel.evaluate = Mock(return_value={})

    # 确保使用calibration配置（使用深拷贝）
    calibration_config = copy.deepcopy(CONFIG_AGENT_OUTPUT_1)
    calibration_config["intent_result"]["intent"] = "calibration"  # 明确设置为calibration

    with patch.dict('sys.modules', {'hydromodel': mock_hydromodel}):
        # 调用RunnerAgent
        result = runner_agent.process(calibration_config)

        # 验证错误被正确捕获
        assert not result["success"], "应该返回失败状态"
        assert "error" in result, "结果中应包含error字段"
        assert "traceback" in result, "结果中应包含traceback字段"
        assert "参数超出范围" in result["error"], "错误信息不匹配"

        print("✅ 错误处理测试通过")
        print(f"   错误信息: {result['error']}")

    return result


def test_runner_agent_missing_config():
    """测试5: 缺少配置的错误处理"""
    print_test_header(5, "缺少配置测试")

    from hydroagent.agents.runner_agent import RunnerAgent
    from hydroagent.core.llm_interface import create_llm_interface

    llm = create_llm_interface('ollama', 'qwen3:8b')
    workspace_dir = project_root / "results" / "test_runner"
    runner_agent = RunnerAgent(llm_interface=llm, workspace_dir=workspace_dir)

    # 传入没有config的输入
    invalid_input = {
        "success": True,
        "message": "没有config字段"
    }

    result = runner_agent.process(invalid_input)

    # 验证错误
    assert not result["success"], "应该返回失败状态"
    assert "error" in result, "结果中应包含error字段"
    assert "Missing 'config'" in result["error"], "错误信息不正确"

    print("✅ 缺少配置测试通过")
    print(f"   错误信息: {result['error']}")

    return result


def test_runner_agent_check_hydromodel():
    """测试6: hydromodel可用性检查"""
    print_test_header(6, "hydromodel 可用性检查")

    from hydroagent.agents.runner_agent import RunnerAgent
    from hydroagent.core.llm_interface import create_llm_interface

    llm = create_llm_interface('ollama', 'qwen3:8b')
    workspace_dir = project_root / "results" / "test_runner"
    runner_agent = RunnerAgent(llm_interface=llm, workspace_dir=workspace_dir)

    # 检查hydromodel是否可用
    is_available = runner_agent.check_hydromodel_available()

    print(f"   hydromodel 可用: {is_available}")

    if is_available:
        print("✅ hydromodel 已安装且可访问")
    else:
        print("⚠️  hydromodel 未安装（这在测试环境中是正常的）")

    return is_available


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("RunnerAgent 单元测试套件")
    print("=" * 70)
    print(f"日志文件: {log_file}")
    print()

    results = []

    try:
        # 测试1: 初始化
        test_runner_agent_initialization()
        results.append(("RunnerAgent初始化", True, None))
    except AssertionError as e:
        results.append(("RunnerAgent初始化", False, str(e)))
        logger.error(f"测试1失败: {str(e)}", exc_info=True)
    except Exception as e:
        results.append(("RunnerAgent初始化", False, str(e)))
        logger.error(f"测试1异常: {str(e)}", exc_info=True)

    try:
        # 测试2: Mock率定
        test_runner_agent_mock_calibration()
        results.append(("Mock率定测试", True, None))
    except AssertionError as e:
        results.append(("Mock率定测试", False, str(e)))
        logger.error(f"测试2失败: {str(e)}", exc_info=True)
    except Exception as e:
        results.append(("Mock率定测试", False, str(e)))
        logger.error(f"测试2异常: {str(e)}", exc_info=True)

    try:
        # 测试3: Mock评估
        test_runner_agent_mock_evaluation()
        results.append(("Mock评估测试", True, None))
    except AssertionError as e:
        results.append(("Mock评估测试", False, str(e)))
        logger.error(f"测试3失败: {str(e)}", exc_info=True)
    except Exception as e:
        results.append(("Mock评估测试", False, str(e)))
        logger.error(f"测试3异常: {str(e)}", exc_info=True)

    try:
        # 测试4: 错误处理
        test_runner_agent_error_handling()
        results.append(("错误处理测试", True, None))
    except AssertionError as e:
        results.append(("错误处理测试", False, str(e)))
        logger.error(f"测试4失败: {str(e)}", exc_info=True)
    except Exception as e:
        results.append(("错误处理测试", False, str(e)))
        logger.error(f"测试4异常: {str(e)}", exc_info=True)

    try:
        # 测试5: 缺少配置
        test_runner_agent_missing_config()
        results.append(("缺少配置测试", True, None))
    except AssertionError as e:
        results.append(("缺少配置测试", False, str(e)))
        logger.error(f"测试5失败: {str(e)}", exc_info=True)
    except Exception as e:
        results.append(("缺少配置测试", False, str(e)))
        logger.error(f"测试5异常: {str(e)}", exc_info=True)

    try:
        # 测试6: hydromodel检查
        test_runner_agent_check_hydromodel()
        results.append(("hydromodel检查", True, None))
    except Exception as e:
        results.append(("hydromodel检查", False, str(e)))
        logger.error(f"测试6异常: {str(e)}", exc_info=True)

    # 打印测试总结
    print("\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)

    passed = sum(1 for _, success, _ in results if success)
    total = len(results)

    for i, (name, success, error) in enumerate(results, 1):
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{i}. {status} - {name}")
        if error:
            print(f"   错误: {error}")

    print()
    print(f"总计: {passed}/{total} 通过")
    print(f"成功率: {passed/total*100:.1f}%")
    print("=" * 70)
    print(f"\n详细日志: {log_file}")

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
