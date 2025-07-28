"""
Author: zhuanglaihong
Date: 2025-07-28
Description: 工作流系统使用示例
"""

import sys
import os
from pathlib import Path

# 添加项目根路径
repo_path = Path(os.path.abspath(__file__)).parent.parent
sys.path.append(str(repo_path))

import logging
from langchain_ollama import ChatOllama
from langchain_community.embeddings import HuggingFaceEmbeddings

# 设置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def basic_example():
    """基本使用示例"""
    print("=" * 60)
    print("🌟 工作流系统基本使用示例")
    print("=" * 60)

    try:
        # 1. 初始化模型
        print("🔧 初始化模型...")
        llm = ChatOllama(model="granite3-dense:8b", temperature=0.1)

        # 2. 初始化嵌入模型（可选，用于RAG）
        print("🔧 初始化嵌入模型...")
        try:
            embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )
        except Exception as e:
            print(f"⚠️ 嵌入模型初始化失败: {e}")
            embeddings = None

        # 3. 获取水文工具
        print("🔧 加载水文工具...")
        from tool.langchain_tool import get_hydromodel_tools

        tools = get_hydromodel_tools()
        print(f"✅ 加载了 {len(tools)} 个工具")

        # 4. 创建工作流编排器
        print("🔧 创建工作流编排器...")
        from workflow import WorkflowOrchestrator

        orchestrator = WorkflowOrchestrator(
            llm=llm,
            embeddings=embeddings,
            rag_system=None,  # 可以传入RAG系统
            tools=tools,
            enable_debug=True,
        )

        # 5. 处理用户查询
        test_queries = [
            "What are the parameters of gr4j model?",
            "I need to prepare hydrological data",
            "Help me calibrate a gr4j model",
            "我想做一个完整的模型率定流程",
        ]

        for i, query in enumerate(test_queries, 1):
            print(f"\n📝 测试查询 {i}: {query}")
            print("-" * 40)

            try:
                workflow_plan = orchestrator.process_query(query)

                print(f"✅ 生成工作流: {workflow_plan.name}")
                print(f"📋 步骤数量: {len(workflow_plan.steps)}")
                print(f"🔗 计划ID: {workflow_plan.plan_id}")

                # 显示步骤详情
                for step in workflow_plan.steps:
                    print(f"   - {step.step_id}: {step.name} ({step.tool_name})")

                # 导出LangChain格式
                langchain_format = orchestrator.export_workflow_to_langchain_format(
                    workflow_plan
                )
                print(
                    f"🔧 LangChain格式导出成功，包含 {len(langchain_format['execution_plan'])} 个执行步骤"
                )

            except Exception as e:
                print(f"❌ 查询处理失败: {e}")

        # 6. 显示统计信息
        print(f"\n📊 执行统计:")
        stats = orchestrator.get_execution_stats()
        for key, value in stats.items():
            print(f"   {key}: {value}")

    except Exception as e:
        print(f"❌ 示例执行失败: {e}")
        import traceback

        traceback.print_exc()


def step_by_step_example():
    """分步执行示例"""
    print("\n" + "=" * 60)
    print("🔍 工作流系统分步执行示例")
    print("=" * 60)

    try:
        # 初始化
        llm = ChatOllama(model="granite3-dense:8b", temperature=0.1)
        from tool.langchain_tool import get_hydromodel_tools
        from workflow import WorkflowOrchestrator

        orchestrator = WorkflowOrchestrator(llm=llm, tools=get_hydromodel_tools())

        # 分步执行
        query = "我想率定一个GR4J模型"
        print(f"🔍 分步处理查询: {query}")

        results = orchestrator.process_query_step_by_step(query)

        print(f"\n📋 执行结果:")
        print(f"整体状态: {results['overall_status']}")

        for step_name, step_result in results["steps"].items():
            print(f"\n{step_name}:")
            print(f"  状态: {step_result['status']}")
            print(f"  耗时: {step_result['execution_time']:.2f}秒")

            if step_name == "step1_intent":
                intent = step_result["result"]
                print(f"  意图类型: {intent['task_type']}")
                print(f"  置信度: {intent['confidence']}")
            elif step_name == "step2_expansion":
                print(f"  扩展查询长度: {len(step_result['result'])}")
            elif step_name == "step3_retrieval":
                print(f"  检索片段数: {len(step_result['result'])}")
            elif step_name == "step4_context":
                print(f"  上下文长度: {step_result['result']['context_length']}")
            elif step_name == "step5_generation":
                workflow = step_result["result"]
                print(f"  工作流名称: {workflow['name']}")
                print(f"  步骤数量: {len(workflow['steps'])}")

    except Exception as e:
        print(f"❌ 分步示例失败: {e}")


def component_testing_example():
    """组件测试示例"""
    print("\n" + "=" * 60)
    print("🧪 工作流组件单独测试示例")
    print("=" * 60)

    try:
        llm = ChatOllama(model="granite3-dense:8b", temperature=0.1)

        # 测试意图处理器
        print("🧪 测试意图处理器...")
        from workflow import IntentProcessor

        intent_processor = IntentProcessor(llm)

        test_query = "我想了解GR4J模型的参数"
        intent_result = intent_processor.process_intent(test_query)

        print(f"  原始查询: {test_query}")
        print(f"  明确意图: {intent_result.clarified_intent}")
        print(f"  任务类型: {intent_result.task_type}")
        print(f"  建议工具: {intent_result.suggested_tools}")

        # 测试查询扩展器
        print("\n🧪 测试查询扩展器...")
        from workflow import QueryExpander

        query_expander = QueryExpander(llm)

        expanded_query = query_expander.expand_query(intent_result)
        print(f"  扩展查询: {expanded_query[:200]}...")

        # 测试知识检索器
        print("\n🧪 测试知识检索器...")
        from workflow import KnowledgeRetriever

        knowledge_retriever = KnowledgeRetriever()

        knowledge_fragments = knowledge_retriever.retrieve_knowledge(expanded_query)
        print(f"  检索到 {len(knowledge_fragments)} 个知识片段")
        for i, fragment in enumerate(knowledge_fragments[:2]):
            print(
                f"    片段{i+1}: {fragment.content[:100]}... (相关性: {fragment.score:.2f})"
            )

        # 测试上下文构建器
        print("\n🧪 测试上下文构建器...")
        from workflow import ContextBuilder

        context_builder = ContextBuilder()

        context = context_builder.build_context(
            user_query=test_query,
            intent_analysis=intent_result,
            knowledge_fragments=knowledge_fragments,
        )
        print(f"  上下文长度: {len(context)}")

        # 测试工作流生成器
        print("\n🧪 测试工作流生成器...")
        from workflow import WorkflowGenerator

        workflow_generator = WorkflowGenerator(llm)

        workflow_plan = workflow_generator.generate_workflow(
            context=context,
            user_query=test_query,
            expanded_query=expanded_query,
            intent_analysis=intent_result,
        )

        print(f"  生成工作流: {workflow_plan.name}")
        print(f"  包含步骤:")
        for step in workflow_plan.steps:
            print(f"    - {step.name}: {step.tool_name}")

        # 验证LangChain兼容性
        is_valid = workflow_generator.validate_workflow_for_langchain(workflow_plan)
        print(f"  LangChain兼容性: {'✅ 通过' if is_valid else '❌ 失败'}")

    except Exception as e:
        print(f"❌ 组件测试失败: {e}")
        import traceback

        traceback.print_exc()


def main():
    """主函数"""
    print("🌟 水文模型智能工作流系统示例")

    # 检查前置条件
    try:
        from tool.langchain_tool import get_hydromodel_tools

        tools = get_hydromodel_tools()
        if not tools:
            print("❌ 无法加载水文工具，请检查tool模块")
            return
    except ImportError:
        print("❌ 无法导入water工具模块，请检查安装")
        return

    try:
        llm = ChatOllama(model="granite3-dense:8b")
        # 简单测试LLM
        test_response = llm.invoke("Hello")
        print("✅ LLM连接正常")
    except Exception as e:
        print(f"❌ LLM连接失败: {e}")
        print("请检查Ollama服务是否运行，以及模型是否已下载")
        return

    # 运行示例
    try:
        basic_example()
        step_by_step_example()
        component_testing_example()

        print("\n🎉 所有示例执行完成！")
        print("\n💡 提示：")
        print("1. 你可以使用 WorkflowOrchestrator 来处理用户查询")
        print("2. 生成的工作流可以直接用于LangChain AgentExecutor")
        print("3. 支持分步执行和调试模式")
        print("4. 可以批量处理多个查询")

    except KeyboardInterrupt:
        print("\n👋 示例执行已取消")
    except Exception as e:
        print(f"\n❌ 示例执行出错: {e}")


if __name__ == "__main__":
    main()
