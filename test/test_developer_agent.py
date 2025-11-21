"""
Author: zhuanglaihong & Claude
Date: 2025-11-21 11:00:00
LastEditTime: 2025-11-21 11:00:00
LastEditors: Claude
Description: Unit tests for DeveloperAgent - 结果分析智能体单元测试
FilePath: \\HydroAgent\\test\\test_developer_agent.py
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

# 设置控制台编码（Windows兼容）
import io
import codecs
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 设置详细日志
log_file = logs_dir / f"test_developer_agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
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
# 测试配置 - 模拟RunnerAgent的输出
# ============================================================================

MOCK_RUNNER_CALIBRATION_OUTPUT = {
    "success": True,
    "mode": "calibrate",
    "result": {
        "status": "success",
        "metrics": {
            "NSE": 0.85,
            "RMSE": 2.5,
            "KGE": 0.82,
            "PBIAS": 5.2
        },
        "best_params": {
            "x1": 350.0,
            "x2": 0.5,
            "x3": 100.0,
            "x4": 2.0
        },
        "output_files": [
            "results/calibrated_params.json",
            "results/performance_plot.png"
        ]
    },
    "execution_log": {
        "stdout": "Calibration started...\nIteration 1/100...\nCalibration completed.",
        "stderr": ""
    }
}

MOCK_RUNNER_EVALUATION_OUTPUT = {
    "success": True,
    "mode": "evaluate",
    "result": {
        "status": "success",
        "metrics": {
            "NSE": 0.78,
            "RMSE": 3.2,
            "KGE": 0.75,
            "PBIAS": 8.5
        },
        "output_files": [
            "results/evaluation_report.csv",
            "results/timeseries_plot.png"
        ]
    },
    "execution_log": {
        "stdout": "Evaluation started...\nEvaluation completed.",
        "stderr": ""
    }
}

MOCK_RUNNER_FAILURE_OUTPUT = {
    "success": False,
    "mode": "calibrate",
    "error": "Configuration error: invalid parameter range",
    "traceback": "Traceback...",
    "execution_log": {
        "stdout": "",
        "stderr": "Error: invalid parameter range"
    }
}


def print_test_header(test_num: int, description: str):
    """打印测试标题"""
    print("\n" + "=" * 70)
    print(f"Test Case {test_num}: {description}")
    print("=" * 70)


def test_developer_agent_initialization():
    """测试1: DeveloperAgent初始化"""
    print_test_header(1, "DeveloperAgent 初始化测试")

    from hydroagent.agents.developer_agent import DeveloperAgent
    from hydroagent.core.llm_interface import create_llm_interface

    # 创建DeveloperAgent
    llm = create_llm_interface('ollama', 'qwen3:8b')
    workspace_dir = project_root / "results" / "test_developer"
    workspace_dir.mkdir(parents=True, exist_ok=True)

    developer_agent = DeveloperAgent(
        llm_interface=llm,
        workspace_dir=workspace_dir,
        enable_code_gen=True
    )

    # 验证初始化
    assert developer_agent.name == "DeveloperAgent", "Agent名称不匹配"
    assert developer_agent.workspace_dir == workspace_dir, "工作目录不匹配"
    assert developer_agent.enable_code_gen == True, "代码生成功能未启用"

    print("✅ DeveloperAgent 初始化测试通过")

    return developer_agent


def test_developer_agent_analyze_calibration():
    """测试2: 分析率定结果"""
    print_test_header(2, "分析率定结果测试")

    from hydroagent.agents.developer_agent import DeveloperAgent
    from hydroagent.core.llm_interface import create_llm_interface

    llm = create_llm_interface('ollama', 'qwen3:8b')
    workspace_dir = project_root / "results" / "test_developer"
    developer_agent = DeveloperAgent(llm_interface=llm, workspace_dir=workspace_dir)

    # 使用模拟的RunnerAgent输出
    result = developer_agent.process(MOCK_RUNNER_CALIBRATION_OUTPUT)

    # 验证结果
    assert result["success"], f"分析失败: {result.get('error')}"
    assert result["mode"] == "calibrate", "模式不匹配"
    assert "analysis" in result, "结果中缺少analysis字段"

    analysis = result["analysis"]
    assert "metrics" in analysis, "分析中缺少metrics"
    assert "quality" in analysis, "分析中缺少quality评估"
    assert analysis["metrics"]["NSE"] == 0.85, "NSE值不匹配"
    assert analysis["quality"] == "优秀 (Excellent)", "质量评估不正确"

    print("✅ 率定结果分析测试通过")
    print(f"   质量评估: {analysis['quality']}")
    print(f"   NSE: {analysis['metrics']['NSE']}")
    print(f"   参数数量: {analysis['summary'].get('param_count', 0)}")

    return result


def test_developer_agent_analyze_evaluation():
    """测试3: 分析评估结果"""
    print_test_header(3, "分析评估结果测试")

    from hydroagent.agents.developer_agent import DeveloperAgent
    from hydroagent.core.llm_interface import create_llm_interface

    llm = create_llm_interface('ollama', 'qwen3:8b')
    workspace_dir = project_root / "results" / "test_developer"
    developer_agent = DeveloperAgent(llm_interface=llm, workspace_dir=workspace_dir)

    # 使用模拟的RunnerAgent评估输出
    result = developer_agent.process(MOCK_RUNNER_EVALUATION_OUTPUT)

    # 验证结果
    assert result["success"], f"分析失败: {result.get('error')}"
    assert result["mode"] == "evaluate", "模式不匹配"

    analysis = result["analysis"]
    assert "performance" in analysis, "分析中缺少performance"
    assert analysis["metrics"]["NSE"] == 0.78, "NSE值不匹配"
    assert analysis["quality"] == "优秀 (Excellent)", "质量评估不正确"

    print("✅ 评估结果分析测试通过")
    print(f"   质量评估: {analysis['quality']}")
    print(f"   NSE: {analysis['metrics']['NSE']}")

    return result


def test_developer_agent_handle_failure():
    """测试4: 处理RunnerAgent失败"""
    print_test_header(4, "处理执行失败测试")

    from hydroagent.agents.developer_agent import DeveloperAgent
    from hydroagent.core.llm_interface import create_llm_interface

    llm = create_llm_interface('ollama', 'qwen3:8b')
    workspace_dir = project_root / "results" / "test_developer"
    developer_agent = DeveloperAgent(llm_interface=llm, workspace_dir=workspace_dir)

    # 使用失败的RunnerAgent输出
    result = developer_agent.process(MOCK_RUNNER_FAILURE_OUTPUT)

    # 验证错误处理
    assert not result["success"], "应该返回失败状态"
    assert "error" in result, "结果中应包含error字段"
    assert "runner_error" in result, "结果中应包含runner_error字段"
    assert "Configuration error" in result["runner_error"], "错误信息不匹配"

    print("✅ 失败处理测试通过")
    print(f"   错误信息: {result['error']}")

    return result


def test_developer_agent_recommendations():
    """测试5: 生成改进建议"""
    print_test_header(5, "生成改进建议测试")

    from hydroagent.agents.developer_agent import DeveloperAgent
    from hydroagent.core.llm_interface import create_llm_interface

    llm = create_llm_interface('ollama', 'qwen3:8b')
    workspace_dir = project_root / "results" / "test_developer"
    developer_agent = DeveloperAgent(llm_interface=llm, workspace_dir=workspace_dir)

    # 使用NSE较低的结果
    low_nse_output = copy.deepcopy(MOCK_RUNNER_CALIBRATION_OUTPUT)
    low_nse_output["result"]["metrics"]["NSE"] = 0.55
    low_nse_output["result"]["metrics"]["PBIAS"] = 30.0

    result = developer_agent.process(low_nse_output)

    # 验证结果
    assert result["success"], f"分析失败: {result.get('error')}"

    analysis = result["analysis"]
    assert "recommendations" in analysis, "分析中缺少recommendations"
    assert len(analysis["recommendations"]) > 0, "应该生成改进建议"

    print("✅ 改进建议生成测试通过")
    print(f"   建议数量: {len(analysis['recommendations'])}")
    for i, rec in enumerate(analysis["recommendations"], 1):
        print(f"   {i}. {rec}")

    return result


def test_developer_agent_execution_log_summary():
    """测试6: 执行日志摘要"""
    print_test_header(6, "执行日志摘要测试")

    from hydroagent.agents.developer_agent import DeveloperAgent
    from hydroagent.core.llm_interface import create_llm_interface

    llm = create_llm_interface('ollama', 'qwen3:8b')
    workspace_dir = project_root / "results" / "test_developer"
    developer_agent = DeveloperAgent(llm_interface=llm, workspace_dir=workspace_dir)

    # 使用包含执行日志的输出
    result = developer_agent.process(MOCK_RUNNER_CALIBRATION_OUTPUT)

    # 验证结果
    assert result["success"], f"分析失败: {result.get('error')}"

    analysis = result["analysis"]
    assert "execution_summary" in analysis, "分析中缺少execution_summary"

    exec_summary = analysis["execution_summary"]
    assert "stdout_lines" in exec_summary, "摘要中缺少stdout_lines"
    assert "stderr_lines" in exec_summary, "摘要中缺少stderr_lines"
    assert "has_errors" in exec_summary, "摘要中缺少has_errors"

    print("✅ 执行日志摘要测试通过")
    print(f"   stdout行数: {exec_summary['stdout_lines']}")
    print(f"   stderr行数: {exec_summary['stderr_lines']}")
    print(f"   有错误: {exec_summary['has_errors']}")

    return result


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("DeveloperAgent 单元测试套件")
    print("=" * 70)
    print(f"日志文件: {log_file}")
    print()

    results = []

    try:
        # 测试1: 初始化
        test_developer_agent_initialization()
        results.append(("DeveloperAgent初始化", True, None))
    except AssertionError as e:
        results.append(("DeveloperAgent初始化", False, str(e)))
        logger.error(f"测试1失败: {str(e)}", exc_info=True)
    except Exception as e:
        results.append(("DeveloperAgent初始化", False, str(e)))
        logger.error(f"测试1异常: {str(e)}", exc_info=True)

    try:
        # 测试2: 分析率定结果
        test_developer_agent_analyze_calibration()
        results.append(("分析率定结果", True, None))
    except AssertionError as e:
        results.append(("分析率定结果", False, str(e)))
        logger.error(f"测试2失败: {str(e)}", exc_info=True)
    except Exception as e:
        results.append(("分析率定结果", False, str(e)))
        logger.error(f"测试2异常: {str(e)}", exc_info=True)

    try:
        # 测试3: 分析评估结果
        test_developer_agent_analyze_evaluation()
        results.append(("分析评估结果", True, None))
    except AssertionError as e:
        results.append(("分析评估结果", False, str(e)))
        logger.error(f"测试3失败: {str(e)}", exc_info=True)
    except Exception as e:
        results.append(("分析评估结果", False, str(e)))
        logger.error(f"测试3异常: {str(e)}", exc_info=True)

    try:
        # 测试4: 处理失败
        test_developer_agent_handle_failure()
        results.append(("处理执行失败", True, None))
    except AssertionError as e:
        results.append(("处理执行失败", False, str(e)))
        logger.error(f"测试4失败: {str(e)}", exc_info=True)
    except Exception as e:
        results.append(("处理执行失败", False, str(e)))
        logger.error(f"测试4异常: {str(e)}", exc_info=True)

    try:
        # 测试5: 生成建议
        test_developer_agent_recommendations()
        results.append(("生成改进建议", True, None))
    except AssertionError as e:
        results.append(("生成改进建议", False, str(e)))
        logger.error(f"测试5失败: {str(e)}", exc_info=True)
    except Exception as e:
        results.append(("生成改进建议", False, str(e)))
        logger.error(f"测试5异常: {str(e)}", exc_info=True)

    try:
        # 测试6: 执行日志摘要
        test_developer_agent_execution_log_summary()
        results.append(("执行日志摘要", True, None))
    except AssertionError as e:
        results.append(("执行日志摘要", False, str(e)))
        logger.error(f"测试6失败: {str(e)}", exc_info=True)
    except Exception as e:
        results.append(("执行日志摘要", False, str(e)))
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
