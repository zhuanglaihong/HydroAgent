"""
Author: zhuanglaihong & Claude
Date: 2025-11-20 22:30:00
LastEditTime: 2025-11-20 22:30:00
LastEditors: Claude
Description: Unit tests for ConfigAgent - 配置生成智能体单元测试
FilePath: \\HydroAgent\\test\\test_config_agent.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import sys
import logging
import json
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 确保logs目录存在
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

# 设置详细日志
log_file = logs_dir / f"test_config_agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
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
# 测试用例 - 模拟IntentAgent的输出
# ============================================================================

# 测试用例1: 完整的率定查询
INTENT_RESULT_1 = {
    "success": True,
    "intent_result": {
        "intent": "calibration",
        "model_name": "gr4j",
        "basin_id": "01013500",
        "time_period": {
            "train": ["2000-01-01", "2010-12-31"],
            "test": ["2011-01-01", "2015-12-31"]
        },
        "algorithm": "SCE_UA",
        "missing_info": [],
        "clarifications_needed": [],
        "confidence": 0.95
    }
}

# 测试用例2: XAJ模型（复杂模型）
INTENT_RESULT_2 = {
    "success": True,
    "intent_result": {
        "intent": "calibration",
        "model_name": "xaj",
        "basin_id": "camels_11532500",
        "time_period": {
            "train": ["2005-01-01", "2010-12-31"],
            "test": ["2011-01-01", "2015-12-31"]
        },
        "algorithm": "SCE_UA",
        "missing_info": [],
        "clarifications_needed": [],
        "confidence": 0.9
    }
}

# 测试用例3: 缺少时间段
INTENT_RESULT_3 = {
    "success": True,
    "intent_result": {
        "intent": "calibration",
        "model_name": "gr5j",
        "basin_id": "01022500",
        "time_period": None,
        "algorithm": "SCE_UA",
        "missing_info": ["time_period"],
        "clarifications_needed": ["Please specify time period"],
        "confidence": 0.7
    }
}

# 测试用例4: 评估任务
INTENT_RESULT_4 = {
    "success": True,
    "intent_result": {
        "intent": "evaluation",
        "model_name": "gr6j",
        "basin_id": "01030500",
        "time_period": {
            "test": ["2015-01-01", "2020-12-31"]
        },
        "algorithm": "SCE_UA",
        "missing_info": [],
        "clarifications_needed": [],
        "confidence": 0.85
    }
}

# 测试用例5: 最小配置（只有模型名）
INTENT_RESULT_5 = {
    "success": True,
    "intent_result": {
        "intent": "calibration",
        "model_name": "gr1y",
        "basin_id": None,
        "time_period": None,
        "algorithm": "SCE_UA",
        "missing_info": ["basin_id", "time_period"],
        "clarifications_needed": [],
        "confidence": 0.6
    }
}


def print_test_header(test_num: int, description: str):
    """打印测试标题"""
    print("\n" + "=" * 70)
    print(f"Test Case {test_num}: {description}")
    print("=" * 70)


def print_config_summary(config: dict):
    """打印配置摘要"""
    print("\n配置摘要:")
    print(f"  模型: {config['model_cfgs']['model_name']}")
    print(f"  流域: {config['data_cfgs']['basin_ids']}")
    print(f"  训练期: {config['data_cfgs']['train_period']}")
    print(f"  测试期: {config['data_cfgs']['test_period']}")
    print(f"  算法: {config['training_cfgs']['algorithm_name']}")
    print(f"  算法参数: ngs={config['training_cfgs']['algorithm_params'].get('ngs', 'N/A')}, "
          f"rep={config['training_cfgs']['algorithm_params'].get('rep', 'N/A')}")
    print(f"  输出目录: {config['training_cfgs']['output_dir']}")
    print(f"  实验名称: {config['training_cfgs']['experiment_name']}")


def validate_config_structure(config: dict) -> tuple[bool, list]:
    """
    验证配置结构完整性

    Returns:
        (is_valid, errors)
    """
    errors = []

    # 检查顶层结构
    required_sections = ["data_cfgs", "model_cfgs", "training_cfgs"]
    for section in required_sections:
        if section not in config:
            errors.append(f"缺少必需部分: {section}")

    # 检查data_cfgs
    if "data_cfgs" in config:
        data_cfgs = config["data_cfgs"]
        if not data_cfgs.get("basin_ids"):
            errors.append("data_cfgs.basin_ids不能为空")
        if not data_cfgs.get("train_period"):
            errors.append("data_cfgs.train_period不能为空")

    # 检查model_cfgs
    if "model_cfgs" in config:
        model_cfgs = config["model_cfgs"]
        if not model_cfgs.get("model_name"):
            errors.append("model_cfgs.model_name不能为空")

    # 检查training_cfgs
    if "training_cfgs" in config:
        training_cfgs = config["training_cfgs"]
        if not training_cfgs.get("algorithm_name"):
            errors.append("training_cfgs.algorithm_name不能为空")
        if not training_cfgs.get("output_dir"):
            errors.append("training_cfgs.output_dir不能为空")

    is_valid = len(errors) == 0
    return is_valid, errors


def test_config_agent_basic():
    """测试1: 基础功能测试"""
    print_test_header(1, "基础功能测试 - GR4J模型率定")

    from hydroagent.agents.config_agent import ConfigAgent
    from hydroagent.core.llm_interface import create_llm_interface

    # 创建ConfigAgent（不需要LLM，因为是纯逻辑处理）
    workspace_dir = project_root / "results" / "test_config_agent"
    workspace_dir.mkdir(parents=True, exist_ok=True)

    # 使用dummy LLM（ConfigAgent当前不需要LLM调用）
    llm = create_llm_interface('ollama', 'qwen3:8b')
    config_agent = ConfigAgent(llm_interface=llm, workspace_dir=workspace_dir)

    # 处理IntentAgent的输出
    result = config_agent.process(INTENT_RESULT_1)

    # 验证结果
    assert result["success"], f"配置生成失败: {result.get('error')}"
    assert "config" in result, "结果中缺少config字段"
    assert "config_summary" in result, "结果中缺少config_summary字段"

    config = result["config"]

    # 验证关键字段
    assert config["model_cfgs"]["model_name"] == "gr4j", "模型名称不匹配"
    assert config["data_cfgs"]["basin_ids"] == ["01013500"], "流域ID不匹配"
    assert config["data_cfgs"]["train_period"] == ["2000-01-01", "2010-12-31"], "训练期不匹配"
    assert config["data_cfgs"]["test_period"] == ["2011-01-01", "2015-12-31"], "测试期不匹配"
    assert config["training_cfgs"]["algorithm_name"] == "SCE_UA", "算法名称不匹配"

    # 验证算法参数（GR4J是简单模型，应该用较少的迭代）
    assert config["training_cfgs"]["algorithm_params"]["ngs"] == 500, "ngs参数不符合预期"
    assert config["training_cfgs"]["algorithm_params"]["rep"] == 3000, "rep参数不符合预期"

    print("✅ 基础功能测试通过")
    print_config_summary(config)

    return result


def test_config_agent_complex_model():
    """测试2: 复杂模型测试（XAJ）"""
    print_test_header(2, "复杂模型测试 - XAJ模型率定")

    from hydroagent.agents.config_agent import ConfigAgent
    from hydroagent.core.llm_interface import create_llm_interface

    workspace_dir = project_root / "results" / "test_config_agent"
    llm = create_llm_interface('ollama', 'qwen3:8b')
    config_agent = ConfigAgent(llm_interface=llm, workspace_dir=workspace_dir)

    result = config_agent.process(INTENT_RESULT_2)

    assert result["success"], f"配置生成失败: {result.get('error')}"

    config = result["config"]

    # 验证XAJ模型配置
    assert config["model_cfgs"]["model_name"] == "xaj", "模型名称不匹配"
    assert config["data_cfgs"]["basin_ids"] == ["camels_11532500"], "流域ID不匹配"

    # 验证算法参数（XAJ是复杂模型，应该用更多迭代）
    assert config["training_cfgs"]["algorithm_params"]["ngs"] == 1500, "ngs参数不符合预期（复杂模型）"
    assert config["training_cfgs"]["algorithm_params"]["rep"] == 8000, "rep参数不符合预期（复杂模型）"

    print("✅ 复杂模型测试通过")
    print_config_summary(config)

    return result


def test_config_agent_missing_info():
    """测试3: 缺失信息处理"""
    print_test_header(3, "缺失信息处理 - 缺少时间段")

    from hydroagent.agents.config_agent import ConfigAgent
    from hydroagent.core.llm_interface import create_llm_interface

    workspace_dir = project_root / "results" / "test_config_agent"
    llm = create_llm_interface('ollama', 'qwen3:8b')
    config_agent = ConfigAgent(llm_interface=llm, workspace_dir=workspace_dir)

    result = config_agent.process(INTENT_RESULT_3)

    # 应该成功，但使用默认时间段
    assert result["success"], f"配置生成失败: {result.get('error')}"

    config = result["config"]

    # 验证使用了默认时间段
    assert config["data_cfgs"]["train_period"] is not None, "应该有默认训练期"
    assert config["data_cfgs"]["test_period"] is not None, "应该有默认测试期"

    print("✅ 缺失信息处理测试通过（使用默认值）")
    print_config_summary(config)

    return result


def test_config_agent_evaluation():
    """测试4: 评估任务配置"""
    print_test_header(4, "评估任务配置 - GR6J模型评估")

    from hydroagent.agents.config_agent import ConfigAgent
    from hydroagent.core.llm_interface import create_llm_interface

    workspace_dir = project_root / "results" / "test_config_agent"
    llm = create_llm_interface('ollama', 'qwen3:8b')
    config_agent = ConfigAgent(llm_interface=llm, workspace_dir=workspace_dir)

    result = config_agent.process(INTENT_RESULT_4)

    assert result["success"], f"配置生成失败: {result.get('error')}"

    config = result["config"]

    # 评估任务也应该生成有效配置
    assert config["model_cfgs"]["model_name"] == "gr6j", "模型名称不匹配"
    assert config["data_cfgs"]["basin_ids"] == ["01030500"], "流域ID不匹配"

    print("✅ 评估任务配置测试通过")
    print_config_summary(config)

    return result


def test_config_agent_validation():
    """测试5: 配置验证功能"""
    print_test_header(5, "配置验证功能测试")

    from hydroagent.agents.config_agent import ConfigAgent
    from hydroagent.core.llm_interface import create_llm_interface

    workspace_dir = project_root / "results" / "test_config_agent"
    llm = create_llm_interface('ollama', 'qwen3:8b')
    config_agent = ConfigAgent(llm_interface=llm, workspace_dir=workspace_dir)

    # 测试最小配置
    result = config_agent.process(INTENT_RESULT_5)

    # 应该成功，但使用默认值
    assert result["success"], f"配置生成失败: {result.get('error')}"

    config = result["config"]

    # 验证配置结构
    is_valid, errors = validate_config_structure(config)
    assert is_valid, f"配置结构验证失败: {errors}"

    # 验证GR1Y模型（最简单模型）的参数
    assert config["model_cfgs"]["model_name"] == "gr1y", "模型名称不匹配"
    assert config["training_cfgs"]["algorithm_params"]["ngs"] == 500, "简单模型参数不正确"

    print("✅ 配置验证测试通过")
    print_config_summary(config)

    return result


def test_config_agent_experiment_name():
    """测试6: 实验名称生成"""
    print_test_header(6, "实验名称生成测试")

    from hydroagent.agents.config_agent import ConfigAgent
    from hydroagent.core.llm_interface import create_llm_interface

    workspace_dir = project_root / "results" / "test_config_agent"
    llm = create_llm_interface('ollama', 'qwen3:8b')
    config_agent = ConfigAgent(llm_interface=llm, workspace_dir=workspace_dir)

    result = config_agent.process(INTENT_RESULT_1)
    config = result["config"]

    # 验证实验名称格式: {model}_{algorithm}_{timestamp}
    exp_name = config["training_cfgs"]["experiment_name"]
    assert exp_name is not None, "实验名称不能为空"
    assert "gr4j" in exp_name.lower(), "实验名称应包含模型名"
    assert "sce_ua" in exp_name.lower(), "实验名称应包含算法名"

    print(f"✅ 实验名称生成测试通过: {exp_name}")

    return result


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("ConfigAgent 单元测试套件")
    print("=" * 70)
    print(f"日志文件: {log_file}")
    print()

    results = []

    try:
        # 测试1: 基础功能
        result = test_config_agent_basic()
        results.append(("基础功能测试", True, None))
    except AssertionError as e:
        results.append(("基础功能测试", False, str(e)))
        logger.error(f"测试1失败: {str(e)}", exc_info=True)
    except Exception as e:
        results.append(("基础功能测试", False, str(e)))
        logger.error(f"测试1异常: {str(e)}", exc_info=True)

    try:
        # 测试2: 复杂模型
        result = test_config_agent_complex_model()
        results.append(("复杂模型测试", True, None))
    except AssertionError as e:
        results.append(("复杂模型测试", False, str(e)))
        logger.error(f"测试2失败: {str(e)}", exc_info=True)
    except Exception as e:
        results.append(("复杂模型测试", False, str(e)))
        logger.error(f"测试2异常: {str(e)}", exc_info=True)

    try:
        # 测试3: 缺失信息
        result = test_config_agent_missing_info()
        results.append(("缺失信息处理", True, None))
    except AssertionError as e:
        results.append(("缺失信息处理", False, str(e)))
        logger.error(f"测试3失败: {str(e)}", exc_info=True)
    except Exception as e:
        results.append(("缺失信息处理", False, str(e)))
        logger.error(f"测试3异常: {str(e)}", exc_info=True)

    try:
        # 测试4: 评估任务
        result = test_config_agent_evaluation()
        results.append(("评估任务配置", True, None))
    except AssertionError as e:
        results.append(("评估任务配置", False, str(e)))
        logger.error(f"测试4失败: {str(e)}", exc_info=True)
    except Exception as e:
        results.append(("评估任务配置", False, str(e)))
        logger.error(f"测试4异常: {str(e)}", exc_info=True)

    try:
        # 测试5: 配置验证
        result = test_config_agent_validation()
        results.append(("配置验证功能", True, None))
    except AssertionError as e:
        results.append(("配置验证功能", False, str(e)))
        logger.error(f"测试5失败: {str(e)}", exc_info=True)
    except Exception as e:
        results.append(("配置验证功能", False, str(e)))
        logger.error(f"测试5异常: {str(e)}", exc_info=True)

    try:
        # 测试6: 实验名称
        result = test_config_agent_experiment_name()
        results.append(("实验名称生成", True, None))
    except AssertionError as e:
        results.append(("实验名称生成", False, str(e)))
        logger.error(f"测试6失败: {str(e)}", exc_info=True)
    except Exception as e:
        results.append(("实验名称生成", False, str(e)))
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
