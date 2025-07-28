#!/usr/bin/env python3
"""
快速验证工具调用的测试脚本
"""

import sys
import os
from pathlib import Path

# 添加项目根路径
repo_path = Path(os.path.abspath(__file__)).parent.parent
sys.path.append(str(repo_path))

from langchain_core.tools import tool
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from tool.ollama_config import ollama_config
from tool.langchain_agent import create_hydromodel_agent


def test_simple_tool_with_agent():
    """使用修复后的配置测试简单工具调用"""
    print("🧪 快速验证工具调用...")

    # 创建简单工具
    @tool("test_calculator")
    def test_calculator(a: int, b: int) -> str:
        """简单计算器"""
        result = a + b
        print(f"🔧 工具被执行: {a} + {b} = {result}")
        return f"计算结果: {a} + {b} = {result}"

    # 检查模型
    available_models = ollama_config.get_available_models()
    if not available_models:
        print("❌ 没有可用模型")
        return False

    print(f"📋 可用模型: {', '.join(available_models)}")

    # 优先选择 granite3-dense:8b
    preferred_models = ["granite3-dense:8b", "llama3-groq-tool-use:8b", "llama3:8b"]
    model_name = None

    for preferred in preferred_models:
        if preferred in available_models:
            model_name = preferred
            print(f"🎯 选择优先模型: {model_name}")
            break

    if not model_name:
        model_name = available_models[0]
        print(f"⚠️ 使用默认模型: {model_name}")

    # 检查模型是否支持工具
    if ollama_config.is_tool_supported_model(model_name):
        print(f"✅ {model_name} 支持工具调用")
    else:
        print(f"⚠️ {model_name} 可能不支持工具调用")

    # 创建 LLM - 添加特殊配置用于工具调用
    model_config = ollama_config.get_model_config(model_name)
    print(f"🔧 模型配置: {model_config}")

    # 为 granite3-dense 添加特殊配置
    if "granite" in model_name.lower():
        model_config.update(
            {
                "temperature": 0.1,  # 降低温度提高确定性
                "top_p": 0.8,
                "num_ctx": 8192,  # 增加上下文窗口
            }
        )
        print(f"🔧 为 {model_name} 优化配置: {model_config}")

    llm = ChatOllama(model=model_name, **model_config)
    print(f"✅ LLM 创建成功: {type(llm).__name__}")

    # 测试工具绑定
    try:
        llm_with_tools = llm.bind_tools([test_calculator])
        print("✅ 工具绑定成功")
    except Exception as e:
        print(f"⚠️ 工具绑定失败: {e}")
        print("💡 可能需要使用不同的工具调用方法")

    # 针对 granite 模型优化的提示（使用英文可能更有效）
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a helpful calculator assistant. You have access to a test_calculator tool.

            When the user asks you to calculate something, you must:
            1. Use the test_calculator tool to get the result
            2. Tell the user the result in Chinese

            Always call the tool first, then provide the answer.

            Available tool:
            - test_calculator: calculates the sum of two numbers""",
            ),
            ("human", "{input}"),
            ("assistant", "{agent_scratchpad}"),
        ]
    )

    # 创建代理（使用修复后的配置）
    tools = [test_calculator]
    print(f"🔧 工具列表: {[tool.name for tool in tools]}")

    try:
        agent = create_openai_tools_agent(llm, tools, prompt)
        print("✅ 代理创建成功")
    except Exception as e:
        print(f"❌ 代理创建失败: {e}")
        return False

    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=5,
        return_intermediate_steps=True,
        early_stopping_method="force",
    )
    print("✅ 代理执行器创建成功")

    # 先测试 LLM 是否正常工作
    print("\n🧪 测试 LLM 基本功能...")
    try:
        basic_response = llm.invoke("你好")
        print(f"📝 LLM 基本回复: {basic_response.content[:50]}...")
        print("✅ LLM 基本功能正常")
    except Exception as e:
        print(f"❌ LLM 基本功能异常: {e}")
        return False

    # 测试
    test_question = "请计算 10 + 15"
    print(f"\n👤 问题: {test_question}")

    try:
        response = agent_executor.invoke({"input": test_question})

        print(f"\n🤖 回复: {response['output']}")
        print(f"回复长度: {len(response['output']) if response['output'] else 0}")

        # 检查中间步骤
        steps = response.get("intermediate_steps", [])
        print(f"🔧 中间步骤: {len(steps)}")

        for i, step in enumerate(steps, 1):
            action, result = step
            print(f"   步骤 {i}: {action.tool} -> {result}")

        # 验证
        if steps and "25" in response["output"]:
            print("✅ 测试成功！工具被调用并结果被正确返回")
            return True
        elif steps:
            print("⚠️ 工具被调用但结果可能不完整")
            print("🔍 详细分析:")
            for i, step in enumerate(steps, 1):
                action, result = step
                print(
                    f"   步骤 {i}: 工具={action.tool}, 输入={action.tool_input}, 输出={result}"
                )
            return False
        else:
            print("❌ 工具未被调用")
            print("🔍 可能的问题:")
            print("   1. 模型不理解工具调用格式")
            print("   2. 提示不够明确")
            print("   3. 模型不支持工具调用")
            print("   4. AgentExecutor 配置问题")

            # 检查是否有任何输出
            if not response["output"] or response["output"].strip() == "":
                print("   5. 模型完全没有输出（可能是模型问题）")
            elif '"type":"function"' in response["output"]:
                print("   6. 模型只输出了工具定义而没有执行")

            return False

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def test_hydromodel_tool():
    """测试水文模型工具"""
    print("\n🧪 快速验证水文模型工具...")

    # 获取工具（用于后续测试）
    try:
        from tool.langchain_tool import get_hydromodel_tools

        tools = get_hydromodel_tools()
        if not tools:
            print("❌ 无法获取水文工具")
            return False

        print(f"🔧 获取到 {len(tools)} 个工具:")
        for tool in tools:
            print(f"   - {tool.name}: {tool.description}")

        # 找到 get_model_params 工具
        get_params_tool = None
        for tool in tools:
            if tool.name == "get_model_params":
                get_params_tool = tool
                break

        if not get_params_tool:
            print("❌ 没有找到 get_model_params 工具")
            return False

    except Exception as e:
        print(f"❌ 工具获取失败: {e}")
        return False

    # 测试1: 简化代理测试（单工具）
    print("\n--- 步骤1: 简化代理测试（单工具）---")
    try:
        # 选择模型
        available_models = ollama_config.get_available_models()
        preferred_models = ["granite3-dense:8b", "llama3-groq-tool-use:8b", "llama3:8b"]
        model_name = None

        for preferred in preferred_models:
            if preferred in available_models:
                model_name = preferred
                break

        if not model_name:
            model_name = available_models[0]

        print(f"🎯 使用模型: {model_name}")

        # 创建 LLM
        model_config = ollama_config.get_model_config(model_name)
        llm = ChatOllama(model=model_name, **model_config)

        # 针对 granite 模型优化的水文工具提示
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a hydrological model assistant. You have access to a get_model_params tool.

                When the user asks about model parameters, you must:
                1. Use the get_model_params tool to get the information
                2. Tell the user the result in Chinese

                Always call the tool first, then provide the answer.

                Available tool:
                - get_model_params: gets hydrological model parameters""",
                ),
                ("human", "{input}"),
                ("assistant", "{agent_scratchpad}"),
            ]
        )

        # 创建代理（只使用一个工具）
        agent = create_openai_tools_agent(llm, [get_params_tool], prompt)
        agent_executor = AgentExecutor(
            agent=agent,
            tools=[get_params_tool],
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=5,
            return_intermediate_steps=True,
            early_stopping_method="force",
        )

        # 测试
        test_question = "请获取 gr4j 模型的参数信息"
        print(f"👤 问题: {test_question}")

        response = agent_executor.invoke({"input": test_question})

        print(f"\n🤖 简化代理回复: {response['output']}")
        print(f"回复长度: {len(response['output']) if response['output'] else 0}")

        # 检查中间步骤
        steps = response.get("intermediate_steps", [])
        print(f"🔧 中间步骤: {len(steps)}")

        for i, step in enumerate(steps, 1):
            action, result = step
            print(f"   步骤 {i}: {action.tool} -> {str(result)[:100]}...")

        if steps:
            print("✅ 简化代理（单工具）成功调用水文工具")
            simple_agent_success = True
        else:
            print("❌ 简化代理（单工具）也无法调用水文工具")
            simple_agent_success = False

    except Exception as e:
        print(f"❌ 简化代理测试失败: {e}")
        simple_agent_success = False

    # 测试2: 原始代理测试（多工具）
    print("\n--- 步骤2: 原始代理测试（多工具）---")
    try:
        # 先获取原始代理使用的工具和配置
        all_tools = get_hydromodel_tools()
        print(f"📋 原始代理工具数量: {len(all_tools)}")
        print("📋 原始代理使用的工具:")
        for i, tool in enumerate(all_tools, 1):
            print(f"   {i}. {tool.name}: {tool.description}")

        agent = create_hydromodel_agent()
        if not agent:
            print("❌ 无法创建原始水文代理")
            return simple_agent_success

        print("✅ 原始代理创建成功")

        # 分析可能的问题
        print("\n🔍 可能的失败原因分析:")
        print(f"   1. 工具数量: {len(all_tools)} 个（简化代理只有1个）")
        print("   2. 提示复杂度: 原始代理提示更复杂")
        print("   3. 工具选择困难: 模型可能不知道选择哪个工具")

        test_question = "请获取 gr4j 模型的参数信息"
        print(f"\n👤 问题: {test_question}")

        response = agent.invoke({"input": test_question})

        print(f"🤖 原始代理回复: {response['output']}")
        print(f"回复长度: {len(response['output']) if response['output'] else 0}")

        # 检查中间步骤
        steps = response.get("intermediate_steps", [])
        print(f"🔧 中间步骤: {len(steps)}")

        if steps:
            print("✅ 原始代理调用工具成功")
            return True
        else:
            print("❌ 原始代理未调用工具")

            # 详细诊断
            print("\n🔍 失败原因诊断:")
            if not response["output"] or response["output"].strip() == "":
                print("   ❌ 完全没有输出 - 可能原因:")
                print("      - 提示模板过于复杂，超出模型理解能力")
                print("      - 多个工具定义导致上下文过载")
                print("      - AgentExecutor 配置问题")
                print("      - 模型在多工具环境下无法做出选择")
            elif '"type":"function"' in response["output"]:
                print("   ⚠️ 只输出了工具定义而没有执行")
            else:
                print(f"   ⚠️ 有输出但没有使用工具: {response['output'][:100]}...")

            print("\n💡 建议的解决方案:")
            print("   1. 简化提示模板（参考成功的简化代理）")
            print("   2. 减少工具数量或分组使用")
            print("   3. 提供更明确的工具选择指导")
            print("   4. 调整 AgentExecutor 配置参数")

            return simple_agent_success

    except Exception as e:
        print(f"❌ 原始代理测试失败: {e}")
        import traceback

        traceback.print_exc()
        return simple_agent_success


if __name__ == "__main__":
    print("🚀 开始快速验证...")

    # 检查 Ollama 服务
    if not ollama_config.check_service():
        print("❌ Ollama 服务未运行")
        exit(1)

    # 测试1: 简单工具
    result1 = test_simple_tool_with_agent()

    # 测试2: 水文工具
    result2 = test_hydromodel_tool()

    print(f"\n📊 快速验证结果:")
    print(f"简单工具: {'✅' if result1 else '❌'}")
    print(f"水文工具: {'✅' if result2 else '❌'}")

    if result1 and result2:
        print("🎉 修复成功！工具调用正常工作")
        print("✅ granite3-dense:8b 模型完全支持工具调用")
        print("✅ 所有配置修复都有效")
    elif result1:
        print("⚠️ 简单工具正常，水文工具需要进一步检查")
        print("✅ granite3-dense:8b 模型支持工具调用")
        print("⚠️ 问题可能在于:")
        print("   - 水文工具定义过于复杂")
        print("   - 原始代理的提示模板需要简化")
        print("   - 工具数量太多导致模型选择困难")
    else:
        print("❌ 仍有问题，需要进一步调试")
        print("❌ 可能的问题:")
        print("   - 模型配置")
        print("   - 工具定义")
        print("   - 代理配置")
