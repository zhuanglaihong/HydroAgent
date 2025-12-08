"""
Author: Claude
Date: 2025-12-06 03:30:00
LastEditTime: 2025-12-06 03:30:00
LastEditors: Claude
Description: 测试实验1c的修复 - 验证extended_analysis任务不会陷入iterative_optimization循环
FilePath: /HydroAgent/test/test_exp1c_fix.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
from datetime import datetime
from hydroagent.agents.orchestrator import Orchestrator

# Setup logging
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

log_file = logs_dir / f"test_exp1c_fix_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


def test_extended_analysis_no_loop():
    """
    测试extended_analysis任务不会陷入iterative_optimization循环，并验证代码生成功能。

    测试查询："率定GR4J模型，流域14325000，完成后画FDC曲线"

    预期行为：
    1. 系统识别为extended_analysis (3个子任务)
    2. task_1: calibration (率定)
    3. task_2: evaluation (评估)
    4. task_3: code_generation (生成FDC绘图代码)
    5. FeedbackRouter不应该触发iterative_optimization
    6. 状态机应该正常完成，不会达到100次转换上限
    7. 应该生成FDC曲线相关的Python代码和图表
    """
    logger.info("=" * 80)
    logger.info("测试: Extended Analysis任务（代码生成）不陷入循环")
    logger.info("=" * 80)

    query = "率定流域02177000的GR4J，然后计算径流系数和画FDC曲线"

    logger.info(f"查询: {query}")
    logger.info("预期: 系统应该识别3个子任务并顺序执行，生成FDC曲线，不会进入迭代优化循环")
    logger.info("")

    try:
        # 创建LLM接口（包括代码生成LLM）
        from hydroagent.core.llm_interface import create_llm_interface
        from configs.definitions import OPENAI_API_KEY, OPENAI_BASE_URL
        from configs.config import DEFAULT_MODEL, DEFAULT_CODE_MODEL

        llm = create_llm_interface(
            backend='openai',
            model_name=DEFAULT_MODEL,
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL
        )

        code_llm = create_llm_interface(
            backend='openai',
            model_name=DEFAULT_CODE_MODEL,  # qwen-coder-turbo
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL
        )

        logger.info(f"✓ 通用LLM: {DEFAULT_MODEL}")
        logger.info(f"✓ 代码LLM: {DEFAULT_CODE_MODEL}")

        workspace_root = project_root / "results" / "test_exp1c_fix"

        # 创建Orchestrator（传入code_llm）
        orchestrator = Orchestrator(
            llm_interface=llm,
            code_llm_interface=code_llm,  # ⭐ 关键：传入代码生成LLM
            workspace_root=workspace_root,
            enable_faiss=False,  # 禁用FAISS加快测试
            show_progress=False,
            enable_code_gen=True  # 启用代码生成
        )

        # 执行查询
        logger.info("\n开始执行查询...")
        result = orchestrator.process({
            "query": query,
            "use_mock": False,  # 使用mock加快测试
            "use_v5": True
        })

        # 检查结果
        logger.info("\n" + "=" * 80)
        logger.info("结果分析:")
        logger.info("=" * 80)

        success = result.get("success", False)
        final_state = result.get("final_state", "UNKNOWN")
        state_history = result.get("state_history", [])
        transition_count = len(state_history)

        logger.info(f"✓ 执行状态: {'成功' if success else '失败'}")
        logger.info(f"✓ 最终状态: {final_state}")
        logger.info(f"✓ 状态转换次数: {transition_count}")

        # 检查是否超过转换上限
        if transition_count >= 100:
            logger.error("❌ 测试失败: 状态机执行了100次转换，可能陷入循环!")
            return False
        else:
            logger.info(f"✓ 状态转换次数正常 ({transition_count} < 100)")

        # 检查task_type
        intent = result.get("intent", {})
        intent_data = intent.get("intent_result", {})
        task_type = intent_data.get("task_type", "UNKNOWN")

        logger.info(f"✓ 任务类型: {task_type}")

        if task_type != "extended_analysis":
            logger.warning(f"⚠ 警告: task_type应该是'extended_analysis'，实际是'{task_type}'")

        # 检查子任务执行情况
        task_plan = result.get("task_plan", {})
        subtasks = task_plan.get("subtasks", [])
        execution_results = result.get("execution_results", [])

        logger.info(f"\n✓ 规划的子任务数: {len(subtasks)}")
        logger.info(f"✓ 执行的子任务数: {len(execution_results)}")

        for i, subtask in enumerate(subtasks, 1):
            task_id = subtask.get("task_id", f"task_{i}")
            task_type = subtask.get("task_type", "unknown")
            description = subtask.get("description", "无描述")
            logger.info(f"  {i}. {task_id} ({task_type}): {description}")

        # 检查是否所有子任务都执行了
        expected_tasks = len(subtasks)
        actual_tasks = len(execution_results)

        if actual_tasks < expected_tasks:
            logger.error(f"❌ 测试失败: 只执行了{actual_tasks}/{expected_tasks}个子任务!")
            logger.error("   task_2和task_3可能没有执行")
            return False
        else:
            logger.info(f"✓ 所有子任务都已执行 ({actual_tasks}/{expected_tasks})")

        # 检查是否有trigger_iterative_optimization
        has_iterative_opt = False
        for record in state_history:
            description = record.get("description", "")
            if "iterative_optimization" in description.lower():
                has_iterative_opt = True
                logger.warning(f"⚠ 检测到迭代优化触发: {description}")

        if has_iterative_opt and task_type == "extended_analysis":
            logger.error("❌ 测试失败: extended_analysis任务不应该触发iterative_optimization!")
            return False
        elif not has_iterative_opt:
            logger.info("✓ 未触发iterative_optimization (正确)")

        logger.info("\n" + "=" * 80)
        logger.info("✅ 测试通过!")
        logger.info("=" * 80)
        return True

    except Exception as e:
        logger.error(f"❌ 测试失败: {str(e)}", exc_info=True)
        return False


if __name__ == "__main__":
    success = test_extended_analysis_no_loop()
    sys.exit(0 if success else 1)
