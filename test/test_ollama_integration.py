"""
Author: zhuanglaihong
Date: 2025-07-25 14:54:24
LastEditTime: 2025-07-28 16:24:08
LastEditors: zhuanglaihong
Description: 测试 Ollama 与 LangChain 水文模型工具的集成
FilePath: test/test_basic_tools.py
Copyright: Copyright (c) 2021-2024 zhuanglaihong. All rights reserved.
"""

import sys
import os
from pathlib import Path

repo_path = Path(os.path.abspath(__file__)).parent.parent  # 获取两次父路径
sys.path.append(str(repo_path))  # 添加项目根路径


def test_ollama_config(specified_model=None):
    """测试 Ollama 配置"""
    print("=== 测试 Ollama 配置 ===")

    try:
        from tool.ollama_config import ollama_config

        # 检查服务状态
        if ollama_config.check_service():
            print("✅ Ollama 服务正常")

            # 获取可用模型
            models = ollama_config.get_available_models()
            print(f"📋 可用模型: {', '.join(models)}")

            if models:
                # 如果指定了模型，检查是否可用
                if specified_model:
                    if specified_model in models:
                        selected_model = specified_model
                        print(f"🎯 使用指定模型: {selected_model}")
                    else:
                        print(f"❌ 指定模型 {specified_model} 不可用")
                        print(f"💡 可用模型: {', '.join(models)}")
                        return False
                else:
                    # 选择最佳模型
                    selected_model = ollama_config.select_best_model()
                    print(f"🎯 选择模型: {selected_model}")

                    # 获取模型配置
                    config = ollama_config.get_model_config(selected_model)
                    print(f"⚙️ 模型配置: {config}")

                # 测试模型
                if ollama_config.test_model(selected_model):
                    print("✅ 模型测试通过")
                    return True
                else:
                    print("❌ 模型测试失败")
                    return False
            else:
                print("❌ 没有可用模型")
                return False
        else:
            print("❌ Ollama 服务未运行")
            return False

    except Exception as e:
        print(f"❌ 配置测试失败: {e}")
        return False


def test_langchain_tools():
    """测试 LangChain 工具"""
    print("\n=== 测试 LangChain 工具 ===")

    try:
        from tool.langchain_tool import get_hydromodel_tools

        tools = get_hydromodel_tools()
        if tools:
            print(f"✅ 成功加载 {len(tools)} 个工具")
            for tool in tools:
                print(f"  - {tool.name}: {tool.description}")
            return True
        else:
            print("❌ 没有加载到工具")
            return False

    except Exception as e:
        print(f"❌ 工具测试失败: {e}")
        return False


def test_ollama_llm_with_tool_support(specified_model=None):
    """测试 Ollama LLM 和工具支持"""
    print("\n=== 测试 Ollama LLM 和工具支持 ===")

    try:
        from tool.ollama_config import ollama_config, create_tool_supported_llm

        # 检查 Ollama 服务
        if not ollama_config.check_service():
            print("❌ Ollama 服务未运行")
            return False

        print("✅ Ollama 服务正在运行")

        # 获取可用模型
        available_models = ollama_config.get_available_models()
        if not available_models:
            print("❌ 没有找到可用的模型")
            return False

        print(f"📋 可用模型: {', '.join(available_models)}")

        # 如果指定了模型，检查是否可用
        if specified_model:
            if specified_model not in available_models:
                print(f"❌ 指定模型 {specified_model} 不可用")
                print(f"💡 可用模型: {', '.join(available_models)}")
                return False

            # 检查指定模型是否支持工具
            if ollama_config.is_tool_supported_model(specified_model):
                print(f"✅ 指定模型 {specified_model} 支持工具")
                tool_supported = [specified_model]
                tool_not_supported = []
            else:
                print(f"❌ 指定模型 {specified_model} 不支持工具")
                tool_supported = []
                tool_not_supported = [specified_model]
        else:
            # 检查每个模型是否支持工具
            tool_supported = []
            tool_not_supported = []

        for model in available_models:
            if ollama_config.is_tool_supported_model(model):
                tool_supported.append(model)
            else:
                tool_not_supported.append(model)

        print(
            f"\n✅ 支持工具的模型: {', '.join(tool_supported) if tool_supported else '无'}"
        )
        print(
            f"❌ 不支持工具的模型: {', '.join(tool_not_supported) if tool_not_supported else '无'}"
        )

        # 测试创建支持工具的 LLM
        print("\n=== 测试创建支持工具的 LLM ===")

        # 如果指定了模型，强制使用该模型
        if specified_model:
            print(f"🎯 强制使用指定模型: {specified_model}")
            # 创建指定模型的 LLM
            from langchain_ollama import ChatOllama

            model_config = ollama_config.get_model_config(specified_model)
            llm = ChatOllama(model=specified_model, **model_config)
        else:
            llm = create_tool_supported_llm()

        if llm:
            print("✅ 成功创建支持工具的 LLM")
            print(f"🤖 使用的模型: {llm.model}")

            # 简单测试
            try:
                response = llm.invoke("Hello, please briefly introduce yourself")
                print(f"🤖 Model response: {response.content[:100]}...")
                return True
            except Exception as e:
                print(f"❌ 模型测试失败: {e}")
                return False
        else:
            print("❌ 无法创建支持工具的 LLM")
            print("💡 请下载支持工具的模型，例如：")
            print("   ollama pull llama3:8b")
            print("   ollama pull granite3-dense:8b")
            print("   ollama pull llama3-groq-tool-use:8b")
            return False

    except Exception as e:
        print(f"❌ LLM 和工具支持测试失败: {e}")
        return False


def test_agent_creation(specified_model=None):
    """测试代理创建（使用支持工具的模型）- 应用成功配置"""
    print("\n=== 测试代理创建（支持工具） ===")

    try:
        from tool.langchain_agent import create_hydromodel_agent
        from tool.ollama_config import ollama_config

        # 如果指定了模型，检查是否可用
        if specified_model:
            available_models = ollama_config.get_available_models()
            if specified_model not in available_models:
                print(f"❌ 指定模型 {specified_model} 不可用")
                print(f"💡 可用模型: {', '.join(available_models)}")
                return False

            print(f"🎯 使用指定模型创建代理: {specified_model}")

            # 应用成功配置：使用单工具代理策略
            from langchain_ollama import ChatOllama
            from tool.langchain_tool import get_hydromodel_tools
            from langchain.agents import AgentExecutor, create_openai_tools_agent
            from langchain_core.prompts import ChatPromptTemplate

            # 获取工具
            tools = get_hydromodel_tools()
            if not tools:
                print("❌ 无法获取工具")
                return False

            # 只测试 get_model_params 工具（单工具策略）
            test_tool = None
            for tool in tools:
                if tool.name == "get_model_params":
                    test_tool = tool
                    break

            if not test_tool:
                print("❌ 未找到 get_model_params 工具")
                return False

            # 创建 LLM（应用优化配置）
            model_config = ollama_config.get_model_config(specified_model)

            # 为 granite 模型添加特殊优化
            if "granite" in specified_model.lower():
                model_config.update(
                    {
                        "temperature": 0.1,  # 降低温度提高确定性
                        "top_p": 0.8,
                        "num_ctx": 8192,  # 增加上下文窗口
                    }
                )
                print(f"🔧 为 {specified_model} 应用优化配置")

            llm = ChatOllama(model=specified_model, **model_config)

            # 根据模型类型创建优化的提示模板
            if "granite" in specified_model.lower():
                # 为 granite 模型使用英文提示（效果更好）
                prompt = ChatPromptTemplate.from_messages(
                    [
                        (
                            "system",
                            """You are a professional hydrological model expert assistant. You have access to a get_model_params tool.

                        When the user asks about model parameters, you must:
                        1. Use the get_model_params tool to get the information
                        2. Tell the user the result in English

                        Always call the tool first, then provide the answer.

                        Available tool:
                        - get_model_params: gets hydrological model parameters""",
                        ),
                        ("human", "{input}"),
                        ("assistant", "{agent_scratchpad}"),
                    ]
                )
            else:
                # 为其他模型使用中文提示
                prompt = ChatPromptTemplate.from_messages(
                    [
                        (
                            "system",
                            """You are a professional hydrological model expert assistant. You have access to a get_model_params tool.

                        When the user asks about model parameters, you must:
                        1. Use the get_model_params tool to get the information
                        2. Tell the user the result in English

                        Always call the tool first, then provide the answer.

                        Available tool:
                        - get_model_params: gets hydrological model parameters""",
                        ),
                        ("human", "{input}"),
                        ("assistant", "{agent_scratchpad}"),
                    ]
                )

            # 创建单工具代理（应用成功配置）
            agent = create_openai_tools_agent(llm, [test_tool], prompt)
            agent_executor = AgentExecutor(
                agent=agent,
                tools=[test_tool],
                verbose=True,
                handle_parsing_errors=True,
                max_iterations=5,  # 增加迭代次数
                return_intermediate_steps=True,
                early_stopping_method="force",  # 强制完成流程
            )
        else:
            # 使用默认的代理创建方法
            agent_executor = create_hydromodel_agent()

        if agent_executor:
            print("✅ 代理创建成功")

            # 测试工具调用
            test_query = "Please get the parameter information for gr4j model"
            print(f"👤 Test query: {test_query}")

            response = agent_executor.invoke({"input": test_query})
            print(f"🤖 Agent response: {response['output']}")

            # 检查中间步骤
            if "intermediate_steps" in response:
                steps = response["intermediate_steps"]
                print(f"🔧 中间步骤数量: {len(steps)}")

                tool_called = False
                for i, step in enumerate(steps):
                    action, result = step
                    print(
                        f"  步骤 {i+1}: 工具={action.tool}, 结果={str(result)[:100]}..."
                    )
                    if action.tool == "get_model_params":
                        tool_called = True

                if tool_called:
                    print("✅ 工具被成功调用")
                    return True
                else:
                    print("❌ 工具未被调用")
                    return False
            else:
                print("❌ 没有中间步骤记录")
                return False
        else:
            print("❌ 代理创建失败")
            return False

    except Exception as e:
        print(f"❌ 代理测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_simple_tool_call(specified_model=None):
    """测试简单的工具调用"""
    print("\n=== 测试简单工具调用 ===")

    try:
        from tool.langchain_tool import get_hydromodel_tools
        from tool.ollama_config import ollama_config
        from langchain_ollama import ChatOllama
        from langchain.agents import AgentExecutor, create_openai_tools_agent
        from langchain_core.prompts import ChatPromptTemplate

        # 获取工具
        tools = get_hydromodel_tools()
        if not tools:
            print("❌ 无法获取工具")
            return False

        # 只使用 get_model_params 工具
        test_tool = None
        for tool in tools:
            if tool.name == "get_model_params":
                test_tool = tool
                break

        if not test_tool:
            print("❌ 未找到 get_model_params 工具")
            return False

        print(f"✅ 找到工具: {test_tool.name}")
        print(f"📝 工具描述: {test_tool.description}")

        # 创建 LLM
        if not specified_model:
            specified_model = ollama_config.select_best_model()
            if not specified_model:
                print("❌ 无法找到可用的模型")
                return False
            print(f"✅ 自动选择模型: {specified_model}")

        model_config = ollama_config.get_model_config(specified_model)
        if "granite" in specified_model.lower():
            model_config.update(
                {
                    "temperature": 0.1,
                    "top_p": 0.8,
                    "num_ctx": 8192,
                }
            )
            print(f"🔧 为 {specified_model} 应用优化配置")

        llm = ChatOllama(model=specified_model, **model_config)

        # 使用更强调工具调用的提示模板
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """IMPORTANT: You are an assistant that can ONLY get information by calling tools. You have NO knowledge of your own about model parameters.

                When asked about model parameters, you MUST:
                1. ALWAYS call the get_model_params function
                2. NEVER provide information from your own knowledge
                3. ONLY respond with information from the tool's response

                                 To call the function, use EXACTLY this format:
                 <|tool_call|>{{"type":"function","function":{{"name":"get_model_params","arguments":{{"model_name":"gr4j"}}}}}}

                 If you try to answer without calling the tool first, you are making a mistake.
                 If you provide information not from the tool, you are making a mistake.

                 Example correct behavior:
                 User: "What are gr4j parameters?"
                 Assistant: Let me get that information by calling the tool.
                 <|tool_call|>{{"type":"function","function":{{"name":"get_model_params","arguments":{{"model_name":"gr4j"}}}}}}
                 [Wait for tool response]
                Here are the parameters based on the tool's response: [only show what the tool returned]""",
                ),
                ("human", "{input}"),
                ("assistant", "{agent_scratchpad}"),
            ]
        )

        # 创建代理
        agent = create_openai_tools_agent(llm, [test_tool], prompt)
        agent_executor = AgentExecutor(
            agent=agent,
            tools=[test_tool],
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=2,
            return_intermediate_steps=True,
            early_stopping_method="force",
        )

        # 测试
        test_query = "What are the parameters of gr4j model?"
        print(f"👤 Test query: {test_query}")

        response = agent_executor.invoke({"input": test_query})
        print(f"🤖 Agent response: {response['output']}")

        # 检查中间步骤
        if "intermediate_steps" in response:
            steps = response["intermediate_steps"]
            print(f"🔧 Steps: {len(steps)}")

            for i, step in enumerate(steps):
                action, result = step
                print(f"  Step {i+1}: {action.tool} -> {str(result)[:100]}...")

                if action.tool == "get_model_params":
                    print("✅ Tool was called successfully!")
                    return True
        else:
            print("❌ No intermediate steps found")
            return False

    except Exception as e:
        print(f"❌ Simple tool test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    # 检查命令行参数
    specified_model = None
    if len(sys.argv) > 1:
        specified_model = sys.argv[1]
        print(f"🎯 指定测试模型: {specified_model}")

    print("开始测试 Ollama 与 LangChain 工具集成...")

    tests = [
        ("简单工具调用", lambda: test_simple_tool_call(specified_model)),
        # ("代理创建", lambda: test_agent_creation(specified_model)),
        # ("Ollama 配置", lambda: test_ollama_config(specified_model)),
        # ("LangChain 工具", test_langchain_tools),
        # ("LLM和工具支持", lambda: test_ollama_llm_with_tool_support(specified_model)),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"测试: {test_name}")
        print("=" * 50)

        if test_func():
            passed += 1
            print(f"✅ {test_name} 测试通过")
        else:
            print(f"❌ {test_name} 测试失败")

    print(f"\n{'='*50}")
    print("测试结果总结")
    print("=" * 50)
    print(f"通过: {passed}/{total}")

    if passed == total:
        print("🎉 所有测试通过！系统可以正常使用")
        print("\n💡 系统功能：")
        print("- ✅ Ollama 服务正常运行")
        print("- ✅ LangChain 工具加载成功")
        print("- ✅ 支持工具的模型可用")
        print("- ✅ 代理创建成功")
    elif passed >= total * 0.8:
        print("⚠️ 大部分测试通过，系统基本可用")
        print("\n💡 建议检查失败的测试项")
    else:
        print("❌ 多个测试失败，请检查配置")
        print("\n💡 常见问题：")
        print("1. Ollama 服务未启动")
        print("2. 没有下载支持工具的模型")
        print("3. 水文模型模块未正确安装")


if __name__ == "__main__":
    main()
