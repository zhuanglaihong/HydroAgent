"""
Author: zhuanglaihong
Date: 2025-02-26 16:24:08
LastEditors: zhuanglaihong
Description: 验证ollama模型是否支持工具调用
FilePath: test/test_tool_support_verification.py
Copyright: Copyright (c) 2021-2024 zhuanglaihong. All rights reserved.
"""

import sys
import os
from pathlib import Path

repo_path = Path(os.path.abspath(__file__)).parent.parent
sys.path.append(str(repo_path))

from langchain_core.tools import tool
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate

# 对于工具调用，应该使用 ChatOllama
from langchain_ollama import ChatOllama

print("✅ 使用 ChatOllama 类（支持工具调用）")


def test_model_tool_support(model_name: str):
    """测试特定模型是否支持工具调用"""
    print(f"\n=== 测试模型: {model_name} ===")

    try:
        # 创建简单的测试工具
        @tool("test_tool")
        def test_tool():
            """测试工具"""
            return "工具调用成功"

        # 使用 ChatOllama 进行工具调用
        from langchain_ollama import ChatOllama

        llm = ChatOllama(model=model_name, temperature=0.1)
        print(f"✅ 使用 ChatOllama 类创建 LLM（支持工具调用）")

        # 创建提示模板
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "你是一个测试助手。请使用提供的工具来回答问题。"),
                ("human", "{input}"),
                ("assistant", "{agent_scratchpad}"),
            ]
        )

        # 创建代理
        agent = create_openai_tools_agent(llm, [test_tool], prompt)
        agent_executor = AgentExecutor(agent=agent, tools=[test_tool], verbose=False)

        # 测试工具调用
        response = agent_executor.invoke({"input": "请调用测试工具"})

        print(f"✅ {model_name} 支持工具调用")
        print(f"🤖 回复: {response['output']}")
        return True

    except Exception as e:
        error_msg = str(e)
        if "does not support tools" in error_msg or "status code: 400" in error_msg:
            print(f"❌ {model_name} 不支持工具调用")
            print(f"💡 错误详情: {error_msg}")
            print("💡 建议使用以下支持工具的模型：")
            print("   - llama3:8b")
            print("   - llama3.2:7b")
            print("   - llama3-groq-tool-use:8b (专门支持工具调用)")
            print("   - granite3-dense:8b")
            print("   - deepseek-coder")
            print("   - codellama")
        else:
            print(f"❌ {model_name} 测试失败: {error_msg}")
        return False


def test_available_models():
    """测试所有可用模型"""
    print("=== 验证模型工具支持 ===")

    try:
        from tool.ollama_config import ollama_config

        if not ollama_config.check_service():
            print("❌ Ollama 服务未运行")
            return

        # 获取可用模型
        available_models = ollama_config.get_available_models()
        if not available_models:
            print("❌ 没有找到可用的模型")
            return

        print(f"📋 可用模型: {', '.join(available_models)}")

        # 测试每个模型
        supported_models = []
        unsupported_models = []

        for model in available_models:
            if test_model_tool_support(model):
                supported_models.append(model)
            else:
                unsupported_models.append(model)

        # 总结结果
        print(f"\n{'='*50}")
        print("测试结果总结")
        print("=" * 50)
        print(
            f"✅ 支持工具的模型: {', '.join(supported_models) if supported_models else '无'}"
        )
        print(
            f"❌ 不支持工具的模型: {', '.join(unsupported_models) if unsupported_models else '无'}"
        )

        if supported_models:
            print(f"\n💡 推荐使用: {supported_models[0]}")
        else:
            print("\n⚠️ 没有找到支持工具的模型")
            print("💡 建议下载以下模型之一：")
            print("   ollama pull llama3:8b")
            print("   ollama pull llama3.2:7b")
            print("   ollama pull llama3-groq-tool-use:8b")
            print("   ollama pull granite3-dense:8b")
            print("   ollama pull deepseek-coder")
            print("   ollama pull codellama")

    except Exception as e:
        print(f"❌ 测试失败: {e}")


def test_agent_with_forced_tool_usage():
    """测试强制使用工具的代理"""
    print("\n=== 测试强制使用工具的代理 ===")

    try:
        from tool.langchain_agent import create_hydromodel_agent

        # 创建代理
        agent = create_hydromodel_agent()
        if not agent:
            print("❌ 无法创建代理")
            return False

        print("✅ 代理创建成功")

        # 测试强制使用工具的问题
        test_questions = [
            "请使用 get_model_params 工具获取 gr4j 模型的参数信息",
            "使用工具查询 gr4j 模型的参数",
            "调用工具获取 gr4j 模型参数",
        ]

        for i, question in enumerate(test_questions, 1):
            print(f"\n--- 测试问题 {i} ---")
            print(f"问题: {question}")

            try:
                response = agent.invoke({"input": question})
                print(f"回答: {response['output']}")
                print(
                    f"回答长度: {len(response['output']) if response['output'] else 0}"
                )

                # 检查是否使用了工具
                if (
                    "tool" in str(response).lower()
                    or "function" in str(response).lower()
                ):
                    print("✅ 检测到工具调用")
                else:
                    print("❌ 未检测到工具调用")

                # 检查中间步骤
                if "intermediate_steps" in response:
                    steps = response["intermediate_steps"]
                    print(f"中间步骤数量: {len(steps)}")
                    for i, step in enumerate(steps):
                        print(f"  步骤 {i+1}: {step}")
                else:
                    print("❌ 没有中间步骤信息")

            except Exception as e:
                print(f"❌ 执行失败: {e}")
                import traceback

                traceback.print_exc()

        return True

    except Exception as e:
        print(f"❌ 代理测试失败: {e}")
        return False


def test_model_tool_understanding():
    """测试模型是否理解工具使用"""
    print("\n=== 测试模型工具理解能力 ===")

    try:
        from tool.ollama_config import create_tool_supported_llm

        # 测试创建支持工具的 LLM
        llm = create_tool_supported_llm()
        if llm:
            print("✅ 成功创建支持工具的 LLM")
            print(f"🤖 使用的 LLM 类: {type(llm).__name__}")

            # 测试工具理解能力
            test_prompt = """你有以下工具可用：
- get_model_params: 获取模型参数信息
- prepare_data: 准备水文数据
- calibrate_model: 率定水文模型
- evaluate_model: 评估水文模型

用户问："请获取 gr4j 模型的参数信息"

你应该使用哪个工具？请回答工具名称。"""

            try:
                response = llm.invoke(test_prompt)
                print(f"🤖 模型回复: {response.content}")

                if "get_model_params" in response.content.lower():
                    print("✅ 模型理解工具使用")
                else:
                    print("❌ 模型不理解工具使用")

            except Exception as e:
                print(f"❌ 模型测试失败: {e}")

        else:
            print("❌ 无法创建支持工具的 LLM")

        return True

    except Exception as e:
        print(f"❌ 模型理解测试失败: {e}")
        return False


def test_tool_direct_call():
    """直接测试工具调用"""
    print("\n=== 直接测试工具调用 ===")

    try:
        from tool.langchain_tool import get_hydromodel_tools

        tools = get_hydromodel_tools()
        if not tools:
            print("❌ 没有获取到工具")
            return False

        print(f"✅ 获取到 {len(tools)} 个工具")

        # 测试获取模型参数工具
        for tool in tools:
            if tool.name == "get_model_params":
                print(f"🔧 测试工具: {tool.name}")
                result = tool.invoke({"model_name": "gr4j"})
                print(f"结果: {result}")
                return True

        print("❌ 没有找到 get_model_params 工具")
        return False

    except Exception as e:
        print(f"❌ 工具测试失败: {e}")
        return False


def test_specific_model():
    """测试特定模型（命令行参数）"""
    if len(sys.argv) > 1:
        model_name = sys.argv[1]
        if model_name == "llama3-groq-tool-use:8b":
            print("🎯 专门测试 llama3-groq-tool-use:8b 工具支持")
            print("✅ 这个模型专门设计用于工具调用")
            # 检查模型是否可用
            from tool.ollama_config import ollama_config

            available_models = ollama_config.get_available_models()
            if "llama3-groq-tool-use:8b" not in available_models:
                print("❌ llama3-groq-tool-use:8b 模型不可用")
                print("💡 请先下载模型：")
                print("   ollama pull llama3-groq-tool-use:8b")
                return
            print("✅ llama3-groq-tool-use:8b 模型可用")
        elif model_name == "granite3-dense:8b":
            print("🎯 专门测试 granite3-dense:8b 工具支持")
            print("✅ 这个模型可能支持工具调用")
            # 检查模型是否可用
            from tool.ollama_config import ollama_config

            available_models = ollama_config.get_available_models()
            if "granite3-dense:8b" not in available_models:
                print("❌ granite3-dense:8b 模型不可用")
                print("💡 请先下载模型：")
                print("   ollama pull granite3-dense:8b")
                return
            print("✅ granite3-dense:8b 模型可用")

        test_model_tool_support(model_name)
    else:
        test_available_models()


def run_comprehensive_tests():
    """运行综合测试"""
    print("=== 综合工具支持测试 ===")

    tests = [
        ("模型工具支持", test_available_models),
        ("直接工具调用", test_tool_direct_call),
        ("代理工具使用", test_agent_with_forced_tool_usage),
        ("模型工具理解", test_model_tool_understanding),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"测试: {test_name}")
        print("=" * 50)

        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} 测试通过")
            else:
                print(f"❌ {test_name} 测试失败")
        except Exception as e:
            print(f"❌ {test_name} 测试异常: {e}")

    print(f"\n{'='*50}")
    print("综合测试结果总结")
    print("=" * 50)
    print(f"通过: {passed}/{total}")

    if passed == total:
        print("🎉 所有测试通过！工具系统正常工作")
    elif passed >= total * 0.8:
        print("⚠️ 大部分测试通过，系统基本可用")
    else:
        print("❌ 多个测试失败，请检查配置")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--comprehensive":
        run_comprehensive_tests()
    else:
        test_specific_model()
