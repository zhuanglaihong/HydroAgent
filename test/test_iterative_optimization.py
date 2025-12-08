"""
Author: Claude
Date: 2025-12-07 15:50:00
LastEditTime: 2025-12-07 15:50:00
LastEditors: Claude
Description: 迭代优化任务测试 - 验证系统的条件判断和多轮优化能力
FilePath: /HydroAgent/test/test_iterative_optimization.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import logging
from pathlib import Path
from datetime import datetime

# Setup logging
logs_dir = Path(__file__).parent.parent / "logs"
logs_dir.mkdir(exist_ok=True)

log_file = logs_dir / f"test_iterative_optimization_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


def test_iterative_task_planning():
    """测试迭代优化任务规划"""
    from hydroagent.core.llm_interface import create_llm_interface
    from hydroagent.agents.orchestrator import Orchestrator

    logger.info("=" * 80)
    logger.info("测试: 迭代优化任务")
    logger.info("=" * 80)
    logger.info("目标: 验证系统能否理解条件判断并规划多轮优化")
    logger.info("")

    # 测试用例
    test_cases = [
        {
            "query": "率定GR4J模型，流域02177000，如果参数收敛到边界则调整参数范围重新率定",
            "expected_task_type": "iterative_optimization",
            "expected_subtasks_min": 2,  # 至少包含初始率定和条件检查
            "description": "参数边界检查"
        },
        {
            "query": "用XAJ率定流域03346000，如果NSE低于0.7则增加迭代轮数重新率定",
            "expected_task_type": "iterative_optimization",
            "expected_subtasks_min": 2,
            "description": "NSE阈值检查"
        },
        {
            "query": "率定XAJ模型，流域14325000，不断优化直到NSE达到0.7以上",
            "expected_task_type": "iterative_optimization",
            "expected_subtasks_min": 2,
            "description": "持续优化直到达标"
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
    workspace = Path(__file__).parent.parent / "results" / "test_iterative_optimization"
    orchestrator = Orchestrator(
        llm_interface=llm,
        code_llm_interface=None,
        workspace_root=workspace
    )

    logger.info("")
    logger.info("开始测试...")

    passed = 0
    failed = 0

    for i, test_case in enumerate(test_cases, 1):
        query = test_case["query"]
        expected_task_type = test_case["expected_task_type"]
        expected_subtasks_min = test_case["expected_subtasks_min"]
        description = test_case["description"]

        logger.info("")
        logger.info(f"[测试 {i}/{len(test_cases)}] {description}")
        logger.info(f"查询: {query}")

        try:
            # 运行到TaskPlanner阶段
            from hydroagent.agents.intent_agent import IntentAgent
            from hydroagent.agents.task_planner import TaskPlanner
            from hydroagent.utils.prompt_manager import PromptManager

            pm = PromptManager()
            intent_agent = IntentAgent(llm, pm)
            task_planner = TaskPlanner(llm, prompt_pool=None)

            # Step 1: IntentAgent
            result = intent_agent.process({"query": query})

            # ✅ FIX: Extract nested intent_result
            intent_result = result.get("intent_result", {})

            logger.info(f"  Intent结果:")
            logger.info(f"    - task_type: {intent_result.get('task_type')}")
            logger.info(f"    - intent: {intent_result.get('intent')}")

            # Step 2: TaskPlanner
            task_plan = task_planner.decompose_task(intent_result)
            logger.info(f"  TaskPlanner结果:")
            logger.info(f"    - 子任务数: {len(task_plan)}")
            for j, subtask in enumerate(task_plan, 1):
                logger.info(f"    - 子任务{j}: {subtask.task_id} ({subtask.task_type})")

            # 验证结果
            checks = []

            # 检查task_type
            actual_task_type = intent_result.get("task_type")
            if actual_task_type == expected_task_type:
                checks.append(f"✓ task_type: {actual_task_type}")
            else:
                checks.append(f"✗ task_type: {actual_task_type} (expected: {expected_task_type})")

            # 检查子任务数量
            if len(task_plan) >= expected_subtasks_min:
                checks.append(f"✓ 子任务数: {len(task_plan)} >= {expected_subtasks_min}")
            else:
                checks.append(f"✗ 子任务数: {len(task_plan)} < {expected_subtasks_min}")

            # 检查是否包含calibration任务
            has_calibration = any(t.task_type == "calibration" for t in task_plan)
            if has_calibration:
                checks.append(f"✓ 包含calibration子任务")
            else:
                checks.append(f"✗ 缺少calibration子任务")

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
    logger.info("")
    logger.info("关键观察:")
    logger.info("  - IntentAgent能否识别出iterative_optimization任务类型？")
    logger.info("  - TaskPlanner能否规划出多步骤的优化流程？")
    logger.info("  - 任务依赖关系是否正确？")
    logger.info("=" * 80)

    if failed == 0:
        logger.info("✅ 所有测试通过!")
        return True
    else:
        logger.warning(f"⚠️  {failed} 个测试失败")
        return False


if __name__ == "__main__":
    success = test_iterative_task_planning()
    exit(0 if success else 1)
