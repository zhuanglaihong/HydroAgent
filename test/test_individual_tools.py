#!/usr/bin/env python3
"""
水文模型智能助手 - 通用工具调用系统
Author: zhuanglaihong
Date: 2025-07-26 16:24:08
LastEditTime: 2025-07-28 16:24:08
Description: 基于通用提示词的智能水文建模助手，支持自动工具选择和调用

功能：
1. 智能理解用户问题
2. 自动选择合适的工具
3. 执行工具调用获取结果
4. 整理结果回答用户

前置条件：
1. Ollama 服务正常运行
2. granite3-dense:8b 模型可用
3. 水文模型工具模块正常
"""

import sys
import os
from pathlib import Path

# 添加项目根路径
repo_path = Path(os.path.abspath(__file__)).parent.parent
sys.path.append(str(repo_path))

from langchain_ollama import ChatOllama
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate
from tool.ollama_config import ollama_config
from tool.langchain_tool import get_hydromodel_tools
import traceback


def create_intelligent_assistant(model_name="granite3-dense:8b", verbose=False):
    """
    创建智能水文建模助手

    Args:
        model_name: 使用的模型名称，默认为 granite3-dense:8b
        verbose: 是否显示详细执行过程，默认为 False（生产环境）

    Returns:
        AgentExecutor: 配置好的智能助手，如果创建失败返回 None
    """
    try:
        # 检查前置条件
        if not ollama_config.check_service():
            print("❌ Ollama 服务未运行")
            return None

        available_models = ollama_config.get_available_models()
        if model_name not in available_models:
            print(f"❌ 模型 {model_name} 不可用")
            print(f"📋 可用模型: {', '.join(available_models)}")
            return None

        # 获取水文模型工具
        tools = get_hydromodel_tools()
        if not tools:
            print("❌ 无法获取水文模型工具")
            return None

        if verbose:
            print(f"✅ 加载了 {len(tools)} 个水文工具:")
            for tool in tools:
                print(f"   - {tool.name}: {tool.description}")

        # 创建 LLM
        model_config = ollama_config.get_model_config(model_name)
        if "granite" in model_name.lower():
            model_config.update(
                {
                    "temperature": 0.1,
                    "top_p": 0.8,
                    "num_ctx": 8192,
                }
            )
            if verbose:
                print(f"🔧 为 {model_name} 应用优化配置")

        llm = ChatOllama(model=model_name, **model_config)

        # 通用提示模板 - 经过验证的成功配置
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """IMPORTANT: You are an assistant that can ONLY get information by calling tools. You have NO knowledge of your own.

You have these tools available:
1. get_model_params - for questions about model parameters, configurations, or "what is" questions
2. prepare_data - for questions about data preparation, processing, or data-related tasks  
3. calibrate_model - for questions about model training, calibration, or optimization
4. evaluate_model - for questions about model evaluation, performance, or metrics

CRITICAL RULES:
1. ALWAYS call a tool first before answering
2. NEVER provide information from your own knowledge
3. ONLY respond with information from the tool's response
4. Choose the RIGHT tool based on the user's question

TOOL SELECTION GUIDE:
- "parameters", "what is", "model info" → get_model_params
- "prepare", "data", "process" → prepare_data
- "calibrate", "train", "optimize" → calibrate_model  
- "evaluate", "performance", "metrics" → evaluate_model

When you need to call a tool, you MUST use this format:
<|tool_call|>{{"type":"function","function":{{"name":"TOOL_NAME","arguments":{{"param":"value"}}}}}}

If you try to answer without calling a tool first, you are making a mistake.

Remember: ALWAYS call the appropriate tool first, then explain the results.""",
                ),
                ("human", "{input}"),
                ("assistant", "{agent_scratchpad}"),
            ]
        )

        # 创建智能助手
        agent = create_openai_tools_agent(llm, tools, prompt)
        assistant = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=verbose,
            handle_parsing_errors=True,
            max_iterations=5,
            return_intermediate_steps=True,
            early_stopping_method="force",
        )

        if verbose:
            print("✅ 智能水文助手创建成功")

        return assistant

    except Exception as e:
        print(f"❌ 智能助手创建失败: {e}")
        if verbose:
            traceback.print_exc()
        return None


def test_assistant():
    """测试智能助手的基本功能"""
    print("🧪 测试智能水文助手...")

    # 创建助手
    assistant = create_intelligent_assistant(verbose=True)
    if not assistant:
        print("❌ 助手创建失败")
        return False

    # 测试用例
    test_cases = [
        "What are the parameters of gr4j model?",
        "I need to prepare hydrological data",
        "How to calibrate a model?",
        "Check model performance",
    ]

    success_count = 0
    for i, question in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"🧪 测试 {i}: {question}")
        print("=" * 60)

        try:
            response = assistant.invoke({"input": question})
            steps = response.get("intermediate_steps", [])

            if steps:
                print(f"✅ 成功调用工具: {steps[0][0].tool}")
                print(f"📝 助手回复: {response['output'][:150]}...")
                success_count += 1
            else:
                print("❌ 没有调用工具")

        except Exception as e:
            print(f"❌ 测试失败: {e}")

    print(f"\n📊 测试结果: {success_count}/{len(test_cases)} 成功")
    return success_count == len(test_cases)


def interactive_demo():
    """交互式演示"""
    print("🤖 智能水文助手交互演示")
    print("=" * 50)
    print("输入 'quit' 退出演示")

    assistant = create_intelligent_assistant()
    if not assistant:
        print("❌ 无法创建助手")
        return

    while True:
        try:
            question = input("\n您的问题: ").strip()

            if question.lower() in ["quit", "exit", "退出"]:
                print("再见！")
                break

            if not question:
                continue

            print("🤖 助手正在处理...")
            response = assistant.invoke({"input": question})
            print(f"\n助手回复:\n{response['output']}")

        except KeyboardInterrupt:
            print("\n再见！")
            break
        except Exception as e:
            print(f"❌ 处理失败: {e}")


def main():
    """主函数"""
    print("🌟 智能水文建模助手")
    print("=" * 50)
    print("基于通用提示词的多工具智能助手")
    print("支持: 参数查询、数据准备、模型率定、性能评估")
    print("=" * 50)

    import argparse

    parser = argparse.ArgumentParser(description="智能水文建模助手")
    parser.add_argument(
        "--mode",
        choices=["test", "demo"],
        default="test",
        help="运行模式: test(测试) 或 demo(交互演示)",
    )

    args = parser.parse_args()

    if args.mode == "test":
        success = test_assistant()
        if success:
            print("\n🎉 所有测试通过！智能助手运行正常")
            print("💡 可以使用 --mode demo 进行交互演示")
        else:
            print("\n❌ 测试失败，请检查配置")
        return success

    elif args.mode == "demo":
        interactive_demo()
        return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
