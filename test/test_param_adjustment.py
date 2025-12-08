"""
Author: Claude
Date: 2025-12-07 15:45:00
LastEditTime: 2025-12-07 15:45:00
LastEditors: Claude
Description: 参数调整任务测试 - 验证IntentAgent提取自定义参数的能力
FilePath: /HydroAgent/test/test_param_adjustment.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import logging
from pathlib import Path
from datetime import datetime

# Setup logging
logs_dir = Path(__file__).parent.parent / "logs"
logs_dir.mkdir(exist_ok=True)

log_file = logs_dir / f"test_param_adjustment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


def test_parameter_extraction():
    """测试参数提取能力"""
    from hydroagent.core.llm_interface import create_llm_interface
    from hydroagent.agents.orchestrator import Orchestrator

    logger.info("=" * 80)
    logger.info("测试: 参数调整任务")
    logger.info("=" * 80)
    logger.info("目标: 验证IntentAgent能否正确提取自定义参数")
    logger.info("")

    # 测试用例
    test_cases = [
        {
            "query": "率定GR4J模型，流域01539000，使用SCE-UA算法，迭代300轮",
            "expected": {
                "intent": "calibration",
                "model_name": "gr4j",
                "basin_id": "01539000",
                "algorithm": "SCE_UA",
                "extra_params": {"rep": 300}
            }
        },
        {
            "query": "用XAJ率定流域02070000，算法用scipy，最大规模200",
            "expected": {
                "intent": "calibration",
                "model_name": "xaj",
                "basin_id": "02070000",
                "algorithm": "SCIPY",
                "extra_params": {"max_iterations": 200}
            }
        },
        {
            "query": "率定流域02177000的GR4J，GA算法，代数100，种群100",
            "expected": {
                "intent": "calibration",
                "model_name": "gr4j",
                "basin_id": "02177000",
                "algorithm": "GA",
                "extra_params": {"generations": 100, "population_size": 100}
            }
        },
        {
            "query": "率定XAJ，流域03346000，SCE-UA算法，复合体数量150",
            "expected": {
                "intent": "calibration",
                "model_name": "xaj",
                "basin_id": "03346000",
                "algorithm": "SCE_UA",
                "extra_params": {"ngs": 150}
            }
        },
    ]

    # 初始化LLM
    try:
        from configs import definitions_private
        api_key = definitions_private.OPENAI_API_KEY
        base_url = definitions_private.OPENAI_BASE_URL
    except ImportError:
        from configs import definitions
        api_key = definitions.OPENAI_API_KEY
        base_url = definitions.OPENAI_BASE_URL

    llm = create_llm_interface(model_name="qwen-flash", api_key=api_key, base_url=base_url)
    logger.info(f"✓ LLM initialized: {llm.model_name}")

    # 初始化Orchestrator
    orchestrator = Orchestrator(
        llm_interface=llm,
        code_llm_interface=None,
        workspace_root=Path(__file__).parent.parent / "results" / "test_param_adjustment"
    )

    logger.info("")
    logger.info("开始测试...")

    passed = 0
    failed = 0

    for i, test_case in enumerate(test_cases, 1):
        query = test_case["query"]
        expected = test_case["expected"]

        logger.info("")
        logger.info(f"[测试 {i}/{len(test_cases)}]")
        logger.info(f"查询: {query}")

        try:
            # 只运行到IntentAgent阶段
            from hydroagent.agents.intent_agent import IntentAgent
            from hydroagent.utils.prompt_manager import PromptManager

            pm = PromptManager()
            intent_agent = IntentAgent(llm, pm)
            result = intent_agent.process({"query": query})

            # ✅ FIX: Extract nested intent_result
            intent_result = result.get("intent_result", {})

            # 验证结果
            checks = []

            # 检查intent
            if intent_result.get("intent") == expected["intent"]:
                checks.append(f"✓ intent: {intent_result.get('intent')}")
            else:
                checks.append(f"✗ intent: {intent_result.get('intent')} (expected: {expected['intent']})")

            # 检查model_name
            if intent_result.get("model_name") == expected["model_name"]:
                checks.append(f"✓ model_name: {intent_result.get('model_name')}")
            else:
                checks.append(f"✗ model_name: {intent_result.get('model_name')} (expected: {expected['model_name']})")

            # 检查basin_id
            if intent_result.get("basin_id") == expected["basin_id"]:
                checks.append(f"✓ basin_id: {intent_result.get('basin_id')}")
            else:
                checks.append(f"✗ basin_id: {intent_result.get('basin_id')} (expected: {expected['basin_id']})")

            # 检查algorithm
            if intent_result.get("algorithm") == expected["algorithm"]:
                checks.append(f"✓ algorithm: {intent_result.get('algorithm')}")
            else:
                checks.append(f"✗ algorithm: {intent_result.get('algorithm')} (expected: {expected['algorithm']})")

            # 检查extra_params
            extra_params = intent_result.get("extra_params", {})
            expected_params = expected.get("extra_params", {})

            params_match = True
            for key, value in expected_params.items():
                if extra_params.get(key) == value:
                    checks.append(f"✓ extra_params.{key}: {extra_params.get(key)}")
                else:
                    checks.append(f"✗ extra_params.{key}: {extra_params.get(key)} (expected: {value})")
                    params_match = False

            # 打印结果
            for check in checks:
                logger.info(f"  {check}")

            if all("✓" in check for check in checks):
                logger.info(f"✅ 测试 {i} 通过")
                passed += 1
            else:
                logger.info(f"❌ 测试 {i} 失败")
                failed += 1

        except Exception as e:
            logger.error(f"❌ 测试 {i} 异常: {str(e)}", exc_info=True)
            failed += 1

    # 总结
    logger.info("")
    logger.info("=" * 80)
    logger.info("测试总结:")
    logger.info("=" * 80)
    logger.info(f"总计: {len(test_cases)} 个测试")
    logger.info(f"通过: {passed} 个 ({passed/len(test_cases)*100:.1f}%)")
    logger.info(f"失败: {failed} 个 ({failed/len(test_cases)*100:.1f}%)")
    logger.info("=" * 80)

    if failed == 0:
        logger.info("✅ 所有测试通过!")
        return True
    else:
        logger.warning(f"⚠️  {failed} 个测试失败")
        return False


if __name__ == "__main__":
    success = test_parameter_extraction()
    exit(0 if success else 1)
