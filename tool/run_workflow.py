"""
Author: zhuanglaihong
Date: 2025-09-13
Description: 独立的工作流执行脚本 - 读取工作流计划并执行
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, Any

# 添加项目根路径
repo_path = Path(os.path.abspath(__file__)).parent.parent
sys.path.append(str(repo_path))

from workflow.workflow_types import WorkflowPlan, WorkflowStep, StepType
from tool.workflow_executor import WorkflowExecutor
from tool.langchain_tool import get_hydromodel_tools

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
    force=True,
)
logger = logging.getLogger(__name__)


def load_workflow_from_json(file_path: str) -> WorkflowPlan:
    """
    从JSON文件加载工作流计划

    Args:
        file_path: JSON文件路径

    Returns:
        WorkflowPlan: 工作流计划对象
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 构建WorkflowStep对象
        steps = []
        for step_data in data.get("steps", []):
            step = WorkflowStep(
                step_id=step_data.get("step_id"),
                name=step_data.get("name"),
                description=step_data.get("description"),
                step_type=StepType(step_data.get("step_type", "tool_call")),
                tool_name=step_data.get("tool_name"),
                parameters=step_data.get("parameters", {}),
                dependencies=step_data.get("dependencies", []),
                conditions=step_data.get("conditions", {}),
                retry_count=step_data.get("retry_count", 0),
                timeout=step_data.get("timeout", 300),
            )
            steps.append(step)

        # 构建WorkflowPlan对象
        workflow_plan = WorkflowPlan(
            plan_id=data.get("plan_id"),
            name=data.get("name"),
            description=data.get("description"),
            steps=steps,
            user_query=data.get("user_query", ""),
            expanded_query=data.get("expanded_query", ""),
            context=data.get("context", ""),
            metadata=data.get("metadata", {}),
        )

        logger.info(f"成功加载工作流: {workflow_plan.name}")
        return workflow_plan

    except Exception as e:
        logger.error(f"加载工作流失败: {e}")
        raise


def save_workflow_to_json(workflow_plan: WorkflowPlan, file_path: str):
    """
    将工作流计划保存为JSON文件

    Args:
        workflow_plan: 工作流计划对象
        file_path: 保存路径
    """
    try:
        # 转换为字典
        data = workflow_plan.to_dict()

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"工作流已保存到: {file_path}")

    except Exception as e:
        logger.error(f"保存工作流失败: {e}")
        raise


def save_execution_result(execution_result: Dict[str, Any], file_path: str):
    """
    保存执行结果到JSON文件

    Args:
        execution_result: 执行结果
        file_path: 保存路径
    """
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(execution_result, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"执行结果已保存到: {file_path}")

    except Exception as e:
        logger.error(f"保存执行结果失败: {e}")
        raise


def create_sample_workflow() -> WorkflowPlan:
    """创建示例工作流"""
    from datetime import datetime

    steps = [
        WorkflowStep(
            step_id="step_1",
            name="数据准备",
            description="准备和预处理水文数据",
            step_type=StepType.TOOL_CALL,
            tool_name="prepare_data",
            parameters={"data_dir": "data/camels_11532500", "target_data_scale": "D"},
            dependencies=[],
            conditions={},
            retry_count=1,
            timeout=120,
        ),
        WorkflowStep(
            step_id="step_2",
            name="模型率定",
            description="率定GR4J模型参数",
            step_type=StepType.TOOL_CALL,
            tool_name="calibrate_model",
            parameters={
                "model_name": "gr4j",
                "data_dir": "data/camels_11532500",
                "exp_name": "sample_calibration",
            },
            dependencies=["step_1"],
            conditions={},
            retry_count=1,
            timeout=600,
        ),
        WorkflowStep(
            step_id="step_3",
            name="模型评估",
            description="评估模型性能",
            step_type=StepType.TOOL_CALL,
            tool_name="evaluate_model",
            parameters={
                "model_name": "gr4j",
                "result_dir": "result",
                "exp_name": "sample_calibration",
            },
            dependencies=["step_2"],
            conditions={},
            retry_count=1,
            timeout=180,
        ),
    ]

    workflow_plan = WorkflowPlan(
        plan_id="sample_workflow_001",
        name="GR4J模型完整建模流程",
        description="包含数据准备、模型率定和性能评估的完整工作流",
        steps=steps,
        user_query="率定并评估GR4J模型",
        expanded_query="执行GR4J模型的完整建模流程，包括数据预处理、参数率定和性能评估",
        context="水文模型建模标准流程",
        metadata={
            "created_by": "sample_generator",
            "created_time": datetime.now().isoformat(),
        },
    )

    return workflow_plan


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="工作流执行器")
    parser.add_argument("--workflow", type=str, help="工作流JSON文件路径")
    parser.add_argument("--create-sample", action="store_true", help="创建示例工作流")
    parser.add_argument(
        "--output", type=str, default="workflow_result.json", help="执行结果保存路径"
    )
    parser.add_argument(
        "--validate-only", action="store_true", help="仅验证工作流，不执行"
    )
    parser.add_argument("--debug", action="store_true", help="启用调试模式")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        # 确保工作目录是项目根目录
        project_root = Path(__file__).parent.parent
        os.chdir(project_root)
        logger.info(f"设置工作目录为: {project_root}")
        # 初始化执行器
        executor = WorkflowExecutor(
            tools=get_hydromodel_tools(), enable_debug=args.debug
        )

        workflow_plan = None

        # 创建示例工作流
        if args.create_sample:
            logger.info("创建示例工作流...")
            workflow_plan = create_sample_workflow()
            sample_path = "sample_workflow.json"
            save_workflow_to_json(workflow_plan, sample_path)
            logger.info(f"示例工作流已保存到: {sample_path}")

            if not args.workflow:
                args.workflow = sample_path

        # 加载工作流
        if args.workflow:
            logger.info(f"加载工作流: {args.workflow}")
            workflow_plan = load_workflow_from_json(args.workflow)
        else:
            logger.error("请指定工作流文件路径或使用 --create-sample 创建示例")
            return

        if not workflow_plan:
            logger.error("无法加载工作流")
            return

        # 显示工作流信息
        logger.info(f"\n工作流信息:")
        logger.info(f"  ID: {workflow_plan.plan_id}")
        logger.info(f"  名称: {workflow_plan.name}")
        logger.info(f"  描述: {workflow_plan.description}")
        logger.info(f"  步骤数量: {len(workflow_plan.steps)}")

        # 验证工作流
        logger.info("\n验证工作流...")
        validation_result = executor.validate_workflow(workflow_plan)

        if not validation_result["is_valid"]:
            logger.error("工作流验证失败:")
            for error in validation_result["errors"]:
                logger.error(f"  - {error}")
            return

        logger.info("工作流验证通过")

        if args.validate_only:
            logger.info("仅验证模式，跳过执行")
            return

        # 执行工作流
        logger.info("\n开始执行工作流...")
        execution_result = executor.execute_workflow(workflow_plan)

        # 显示执行结果
        logger.info(f"\n工作流执行完成:")
        logger.info(f"  状态: {execution_result['status']}")
        logger.info(f"  总耗时: {execution_result['total_time']:.2f}秒")
        logger.info(f"  成功步骤: {execution_result['success_count']}")
        logger.info(f"  失败步骤: {execution_result['failed_count']}")

        # 详细显示每个步骤的结果
        logger.info("\n步骤执行详情:")
        for step_id, step_result in execution_result["steps"].items():
            logger.info(f"\n步骤 {step_id} ({step_result.get('step_name', '')}):")
            logger.info(f"  状态: {step_result['status']}")
            logger.info(f"  耗时: {step_result['execution_time']:.2f}秒")
            if "result" in step_result:
                logger.info(f"  结果: {step_result['result']}")
            if "error" in step_result:
                logger.error(f"  错误: {step_result['error']}")

        # 保存执行结果
        save_execution_result(execution_result, args.output)

    except Exception as e:
        logger.error(f"执行失败: {e}")
        raise


if __name__ == "__main__":
    main()
