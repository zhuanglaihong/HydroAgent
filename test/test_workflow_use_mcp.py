"""
Author: zhuanglaihong
Date: 2025-09-13
Description: 工作流生成器测试脚本 - 测试GR4J模型的率定和评估工作流生成
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any

# 添加项目根路径
repo_path = Path(os.path.abspath(__file__)).parent.parent
sys.path.append(str(repo_path))

from langchain_ollama import ChatOllama
from workflow import (
    WorkflowOrchestrator,
    IntentProcessor,
    QueryExpander,
    ContextBuilder,
    WorkflowGenerator,
)
from workflow.workflow_types import WorkflowPlan
from tool.langchain_tool import get_hydromodel_tools
from hydromcp.agent_integration import MCPAgent
from hydromcp.client import HydroMCPClient
from hydromcp.task_dispatcher import TaskDispatcher

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),  # 添加控制台处理器
    ],
    force=True,  # 强制重新配置日志
)

# 获取logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # 确保logger级别正确设置

# 确保所有相关模块的日志也能显示
logging.getLogger("workflow").setLevel(logging.INFO)
logging.getLogger("tool").setLevel(logging.INFO)


def init_components():
    """初始化所需组件"""
    try:
        # 初始化模型
        llm = ChatOllama(
            model="qwen3:8b",  # 工作流选择推理大模型
            temperature=0.1,  # 保持较低的温度以获得更确定性的输出
            top_p=0.7,  # 适当降低以减少随机性
            num_ctx=8192,  # 保持较大的上下文窗口
            num_predict=2048,  # 增加输出长度限制
            stop=["</think>", "Human:", "Assistant:"],  # 添加停止标记防止思考过程输出
            format="json",  # 强制JSON输出
        )

        # 初始化工作流组件
        intent_processor = IntentProcessor(llm)
        query_expander = QueryExpander(llm)
        context_builder = ContextBuilder()
        workflow_generator = WorkflowGenerator(llm)

        # 初始化编排器
        orchestrator = WorkflowOrchestrator(
            llm=llm,
            tools=get_hydromodel_tools(),
            enable_debug=True,
        )

        logger.info("组件初始化完成")
        return {
            "llm": llm,
            "intent_processor": intent_processor,
            "query_expander": query_expander,
            "context_builder": context_builder,
            "workflow_generator": workflow_generator,
            "orchestrator": orchestrator,
        }

    except Exception as e:
        logger.error(f"组件初始化失败: {e}")
        raise


def process_step_by_step(components: Dict[str, Any], query: str) -> WorkflowPlan:
    """逐步处理工作流生成"""
    try:
        logger.info(f"开始处理查询: {query}")

        # 1. 意图处理
        logger.info("Step 1: 意图处理")
        intent = components["intent_processor"].process_intent(query)
        logger.info(f"识别到的任务类型: {intent.task_type}")
        logger.info(f"建议使用的工具: {intent.suggested_tools}")
        logger.info(f"识别到的实体: {intent.entities}")

        # 2. 查询扩展
        logger.info("Step 2: 查询扩展")
        expanded_query = components["query_expander"].expand_query(intent)
        logger.info(f"扩展后的查询: {expanded_query}")

        # 3. 构建上下文
        logger.info("Step 3: 构建上下文")
        context = components["context_builder"].build_context(
            user_query=query,
            intent_analysis=intent,
            knowledge_fragments=[],  # 不使用知识片段
        )
        logger.info("上下文构建完成")

        # 4. 生成工作流
        logger.info("Step 4: 生成工作流")
        workflow_plan = components["workflow_generator"].generate_workflow(
            context=context,
            user_query=query,
            expanded_query=expanded_query,
            intent_analysis=intent,
        )

        # 打印工作流详情
        logger.info(f"生成的工作流 ID: {workflow_plan.plan_id}")
        logger.info(f"工作流名称: {workflow_plan.name}")
        logger.info(f"工作流描述: {workflow_plan.description}")
        logger.info(f"步骤数量: {len(workflow_plan.steps)}")

        # 打印每个步骤的详情
        for i, step in enumerate(workflow_plan.steps, 1):
            logger.info(f"\n步骤 {i}:")
            logger.info(f"  ID: {step.step_id}")
            logger.info(f"  名称: {step.name}")
            logger.info(f"  描述: {step.description}")
            logger.info(f"  工具: {step.tool_name}")
            logger.info(f"  参数: {step.parameters}")
            logger.info(f"  依赖: {step.dependencies}")
            logger.info(f"  超时: {step.timeout}秒")
            logger.info(f"  重试次数: {step.retry_count}")

        return workflow_plan

    except Exception as e:
        logger.error(f"工作流生成失败: {e}")
        raise


def validate_workflow(workflow_plan: WorkflowPlan):
    """验证生成的工作流"""
    try:
        logger.info("\n开始验证工作流")

        # 1. 基本属性验证
        assert workflow_plan.plan_id, "工作流ID不能为空"
        assert workflow_plan.name, "工作流名称不能为空"
        assert workflow_plan.description, "工作流描述不能为空"
        assert len(workflow_plan.steps) > 0, "工作流步骤不能为空"

        # 2. 步骤验证
        step_ids = set()
        for step in workflow_plan.steps:
            # 步骤ID唯一性
            assert step.step_id not in step_ids, f"步骤ID重复: {step.step_id}"
            step_ids.add(step.step_id)

            # 工具名称验证
            assert step.tool_name in [
                "get_model_params",
                "prepare_data",
                "calibrate_model",
                "evaluate_model",
            ], f"无效的工具名称: {step.tool_name}"

            # 参数验证
            assert isinstance(step.parameters, dict), "参数必须是字典类型"
            if step.tool_name in ["calibrate_model", "evaluate_model"]:
                assert "model_name" in step.parameters, "缺少model_name参数"

            # 依赖验证
            for dep in step.dependencies:
                assert dep in step_ids, f"依赖的步骤不存在: {dep}"

        logger.info("工作流验证通过")

    except AssertionError as e:
        logger.error(f"工作流验证失败: {e}")
        raise


async def main():
    """主函数"""
    try:
        # 确保工作目录是项目根目录
        import os
        from pathlib import Path

        project_root = Path(__file__).parent.parent
        os.chdir(project_root)
        logger.info(f"设置工作目录为: {project_root}")

        # 检查和设置路径
        try:
            from tool.setup_paths import setup_project_paths

            setup_result = setup_project_paths()
            if not setup_result["all_files_present"]:
                logger.warning("数据文件不完整，但继续执行测试...")
        except Exception as e:
            logger.warning(f"路径检查失败: {e}，继续执行...")

        # 1. 初始化组件
        components = init_components()

        # 2. 设置测试查询
        query = "率定并评估GR4J模型"

        # 3. 生成工作流
        workflow_plan = process_step_by_step(components, query)

        # 4. 验证工作流
        validate_workflow(workflow_plan)

        logger.info("\n最终工作流计划:")
        logger.info(f"工作流ID: {workflow_plan.plan_id}")
        logger.info(f"工作流名称: {workflow_plan.name}")
        logger.info(f"步骤数量: {len(workflow_plan.steps)}")

        # 5. 使用MCP Agent执行工作流
        logger.info("\n开始使用MCP Agent执行工作流")
        
        # 初始化MCP Agent
        mcp_agent = MCPAgent(
            llm_model="qwen3:8b",
            server_command=None,  # 使用直接模式
            enable_workflow=True,
            enable_debug=True
        )
        
        # 设置Agent
        setup_success = await mcp_agent.setup()
        if not setup_success:
            raise RuntimeError("MCP Agent设置失败")
        
        try:
            # 执行工作流
            logger.info("开始智能执行工作流...")
            execution_result = await mcp_agent._execute_workflow_intelligently(workflow_plan, query)
            
            # 打印执行结果
            logger.info("\n执行结果:")
            logger.info(f"整体状态: {'成功' if execution_result['overall_success'] else '失败'}")
            logger.info(f"总步骤数: {execution_result['total_steps']}")
            logger.info(f"成功步骤: {execution_result['success_steps']}")
            logger.info(f"失败步骤: {execution_result['failed_steps']}")
            logger.info("\n执行摘要:")
            logger.info(execution_result['execution_summary'])
            
            # 详细步骤结果
            logger.info("\n各步骤执行详情:")
            for step_result in execution_result['step_results']:
                logger.info(f"\n步骤: {step_result['step_name']}")
                logger.info(f"复杂度: {step_result['classification']['complexity']}")
                logger.info(f"执行策略: {step_result['strategy']}")
                logger.info(f"执行状态: {'成功' if step_result['success'] else '失败'}")
                if not step_result['success']:
                    logger.info(f"失败原因: {step_result['result'].get('error', '未知错误')}")
            
            # 验证执行结果
            assert execution_result['overall_success'], "工作流执行失败"
            assert execution_result['success_steps'] > 0, "没有成功执行的步骤"
            logger.info("\n工作流执行测试通过!")
            
        finally:
            # 清理资源
            await mcp_agent.cleanup()
            logger.info("已清理MCP Agent资源")

    except Exception as e:
        logger.error(f"测试失败: {e}")
        raise


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
