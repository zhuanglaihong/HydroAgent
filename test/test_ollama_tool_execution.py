#!/usr/bin/env python3
"""
Author: zhuanglaihong
Date: 2025-02-27
LastEditTime: 2025-02-27
Description: 测试本地Ollama是否真正执行工具并返回结果
FilePath: test/test_ollama_tool_execution.py
Copyright: Copyright (c) 2021-2024 zhuanglaihong. All rights reserved.
"""

import sys
import os
from pathlib import Path
import json
import traceback

# 添加项目根路径
repo_path = Path(os.path.abspath(__file__)).parent.parent
sys.path.append(str(repo_path))

from langchain_core.tools import tool
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from tool.ollama_config import ollama_config


class ToolExecutionTester:
    """工具执行测试器"""

    def __init__(self, model_name: str = None):
        self.model_name = model_name or "granite3-dense:8b"
        self.execution_log = []

    def create_test_tools(self):
        """创建测试工具"""

        @tool("simple_calculator")
        def simple_calculator(operation: str, a: float, b: float) -> str:
            """简单计算器工具

            Args:
                operation: 运算类型 (add, subtract, multiply, divide)
                a: 第一个数字
                b: 第二个数字

            Returns:
                计算结果
            """
            self.execution_log.append(
                f"✅ simple_calculator 被调用: {operation}({a}, {b})"
            )
            print(f"🔧 工具被执行: simple_calculator({operation}, {a}, {b})")

            try:
                if operation == "add":
                    result = a + b
                elif operation == "subtract":
                    result = a - b
                elif operation == "multiply":
                    result = a * b
                elif operation == "divide":
                    if b == 0:
                        return "错误：除零"
                    result = a / b
                else:
                    return f"不支持的运算: {operation}"

                return f"计算结果: {a} {operation} {b} = {result}"
            except Exception as e:
                return f"计算错误: {e}"

        @tool("weather_checker")
        def weather_checker(city: str) -> str:
            """天气查询工具

            Args:
                city: 城市名称

            Returns:
                天气信息
            """
            self.execution_log.append(f"✅ weather_checker 被调用: {city}")
            print(f"🔧 工具被执行: weather_checker({city})")

            # 模拟天气数据
            weather_data = {
                "北京": "晴天，25°C，东风2级",
                "上海": "多云，23°C，南风3级",
                "广州": "雨天，20°C，西风1级",
                "深圳": "晴天，28°C，无风",
            }

            result = weather_data.get(city, f"{city}：天气晴朗，温度适宜")
            return f"{city}的天气：{result}"

        @tool("text_processor")
        def text_processor(text: str, action: str) -> str:
            """文本处理工具

            Args:
                text: 要处理的文本
                action: 处理动作 (uppercase, lowercase, reverse, length)

            Returns:
                处理后的结果
            """
            self.execution_log.append(
                f"✅ text_processor 被调用: {action} on '{text[:20]}...'"
            )
            print(f"🔧 工具被执行: text_processor({action}, '{text[:20]}...')")

            try:
                if action == "uppercase":
                    return f"大写结果: {text.upper()}"
                elif action == "lowercase":
                    return f"小写结果: {text.lower()}"
                elif action == "reverse":
                    return f"反转结果: {text[::-1]}"
                elif action == "length":
                    return f"文本长度: {len(text)} 个字符"
                else:
                    return f"不支持的操作: {action}"
            except Exception as e:
                return f"处理错误: {e}"

        return [simple_calculator, weather_checker, text_processor]

    def test_direct_tool_call(self):
        """测试直接工具调用"""
        print("\n" + "=" * 60)
        print("🧪 测试1: 直接工具调用")
        print("=" * 60)

        tools = self.create_test_tools()

        try:
            # 测试计算器工具
            calc_result = tools[0].invoke({"operation": "add", "a": 10, "b": 5})
            print(f"📊 计算器结果: {calc_result}")

            # 测试天气工具
            weather_result = tools[1].invoke({"city": "北京"})
            print(f"🌤️ 天气结果: {weather_result}")

            # 测试文本处理工具
            text_result = tools[2].invoke(
                {"text": "Hello World", "action": "uppercase"}
            )
            print(f"📝 文本处理结果: {text_result}")

            print("✅ 直接工具调用测试通过")
            return True

        except Exception as e:
            print(f"❌ 直接工具调用失败: {e}")
            traceback.print_exc()
            return False

    def test_agent_tool_execution(self):
        """测试代理工具执行"""
        print("\n" + "=" * 60)
        print("🧪 测试2: 代理工具执行")
        print("=" * 60)

        try:
            # 检查模型是否可用
            available_models = ollama_config.get_available_models()
            if self.model_name not in available_models:
                print(f"❌ 模型 {self.model_name} 不可用")
                print(f"💡 可用模型: {', '.join(available_models)}")
                return False

            print(f"🤖 使用模型: {self.model_name}")

            # 创建工具
            tools = self.create_test_tools()

            # 创建 LLM（应用优化配置）
            model_config = ollama_config.get_model_config(self.model_name)

            # 为 granite 模型添加特殊优化
            if "granite" in self.model_name.lower():
                model_config.update(
                    {
                        "temperature": 0.1,  # 降低温度提高确定性
                        "top_p": 0.8,
                        "num_ctx": 8192,  # 增加上下文窗口
                    }
                )
                print(f"🔧 为 {self.model_name} 应用优化配置")

            llm = ChatOllama(model=self.model_name, **model_config)

            # 根据模型类型创建优化的提示模板
            if "granite" in self.model_name.lower():
                # 为 granite 模型使用英文提示（效果更好）- 应用成功配置
                prompt = ChatPromptTemplate.from_messages(
                    [
                        (
                            "system",
                            """You are a helpful calculator assistant. You have access to a simple_calculator tool.

                        When the user asks you to calculate something, you must:
                        1. Use the simple_calculator tool to get the result
                        2. Tell the user the result in Chinese

                        Always call the tool first, then provide the answer.

                        Available tool:
                        - simple_calculator: calculates the sum of two numbers""",
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
                            """你是一个测试助手。你有以下工具可以使用：

                        1. simple_calculator - 执行基本数学运算
                        2. weather_checker - 查询城市天气
                        3. text_processor - 处理文本

                        工作流程：
                        1. 理解用户请求
                        2. 选择合适的工具
                        3. 调用工具获取结果
                        4. 用中文解释和整理结果给用户

                        重要规则：
                        - 当用户要求计算时，必须使用 simple_calculator 工具，然后解释计算过程
                        - 当用户询问天气时，必须使用 weather_checker 工具，然后报告天气情况
                        - 当用户要求处理文本时，必须使用 text_processor 工具，然后说明处理结果
                        - 绝对不要基于自己的知识直接回答，必须先调用工具
                        - 调用工具后，必须对结果进行中文解释和总结

                        记住：每次都要实际调用工具，获取真实结果，然后用自然语言回复用户。""",
                        ),
                        ("human", "{input}"),
                        ("assistant", "{agent_scratchpad}"),
                    ]
                )

            # 创建代理
            agent = create_openai_tools_agent(llm, tools, prompt)
            agent_executor = AgentExecutor(
                agent=agent,
                tools=tools,
                verbose=True,
                handle_parsing_errors=True,
                max_iterations=5,  # 增加迭代次数，确保有足够的步骤
                return_intermediate_steps=True,
                early_stopping_method="force",  # 改为 force，确保完成完整流程
            )

            # 使用成功配置：每个工具单独测试（避免多工具选择困难）
            test_cases = [
                {
                    "name": "数学计算",
                    "query": "请计算 15 加 25 的结果",
                    "tool": tools[0],  # simple_calculator
                    "tool_name": "simple_calculator",
                },
                {
                    "name": "天气查询",
                    "query": "请查询北京的天气",
                    "tool": tools[1],  # weather_checker
                    "tool_name": "weather_checker",
                },
                {
                    "name": "文本处理",
                    "query": "请将文本 'Hello World' 转换为大写",
                    "tool": tools[2],  # text_processor
                    "tool_name": "text_processor",
                },
            ]

            success_count = 0

            for i, test_case in enumerate(test_cases, 1):
                print(f"\n--- 测试案例 {i}: {test_case['name']} ---")
                print(f"👤 用户问题: {test_case['query']}")

                # 清空执行日志
                self.execution_log.clear()

                try:
                    # 应用成功配置：为每个工具创建单独的简化代理
                    single_tool = test_case["tool"]
                    tool_name = test_case["tool_name"]

                    # 创建针对单个工具的简化提示（模仿成功配置）
                    if "granite" in self.model_name.lower():
                        # 为 granite 模型使用英文提示
                        if tool_name == "simple_calculator":
                            simple_prompt = ChatPromptTemplate.from_messages(
                                [
                                    (
                                        "system",
                                        """You are a helpful calculator assistant. You have access to a simple_calculator tool.

                                When the user asks you to calculate something, you must:
                                1. Use the simple_calculator tool to get the result
                                2. Tell the user the result in Chinese

                                Always call the tool first, then provide the answer.

                                Available tool:
                                - simple_calculator: calculates the sum of two numbers""",
                                    ),
                                    ("human", "{input}"),
                                    ("assistant", "{agent_scratchpad}"),
                                ]
                            )
                        elif tool_name == "weather_checker":
                            simple_prompt = ChatPromptTemplate.from_messages(
                                [
                                    (
                                        "system",
                                        """You are a helpful weather assistant. You have access to a weather_checker tool.

                                When the user asks about weather, you must:
                                1. Use the weather_checker tool to get the information
                                2. Tell the user the result in Chinese

                                Always call the tool first, then provide the answer.

                                Available tool:
                                - weather_checker: checks weather for cities""",
                                    ),
                                    ("human", "{input}"),
                                    ("assistant", "{agent_scratchpad}"),
                                ]
                            )
                        else:  # text_processor
                            simple_prompt = ChatPromptTemplate.from_messages(
                                [
                                    (
                                        "system",
                                        """You are a helpful text processing assistant. You have access to a text_processor tool.

                                When the user asks to process text, you must:
                                1. Use the text_processor tool to process the text
                                2. Tell the user the result in Chinese

                                Always call the tool first, then provide the answer.

                                Available tool:
                                - text_processor: processes text in various ways""",
                                    ),
                                    ("human", "{input}"),
                                    ("assistant", "{agent_scratchpad}"),
                                ]
                            )
                    else:
                        # 为其他模型使用中文提示
                        simple_prompt = ChatPromptTemplate.from_messages(
                            [
                                (
                                    "system",
                                    f"""你是一个助手。当用户有需求时，你必须使用 {tool_name} 工具。
                            
                            工作步骤：
                            1. 使用 {tool_name} 工具
                            2. 告诉用户结果
                            
                            可用工具：
                            - {tool_name}""",
                                ),
                                ("human", "{input}"),
                                ("assistant", "{agent_scratchpad}"),
                            ]
                        )

                    # 创建单工具代理（模仿成功配置）
                    single_agent = create_openai_tools_agent(
                        llm, [single_tool], simple_prompt
                    )
                    single_executor = AgentExecutor(
                        agent=single_agent,
                        tools=[single_tool],
                        verbose=True,
                        handle_parsing_errors=True,
                        max_iterations=5,
                        return_intermediate_steps=True,
                        early_stopping_method="force",
                    )

                    # 执行单工具代理
                    response = single_executor.invoke({"input": test_case["query"]})

                    print(f"🤖 代理回复: {response['output']}")
                    print(
                        f"回复长度: {len(response['output']) if response['output'] else 0}"
                    )

                    # 检查中间步骤
                    intermediate_steps = response.get("intermediate_steps", [])
                    print(f"🔧 中间步骤数量: {len(intermediate_steps)}")

                    tool_called = False
                    tool_results = []

                    for j, step in enumerate(intermediate_steps):
                        action, result = step
                        print(f"   步骤 {j+1}: {action.tool} -> {str(result)[:100]}...")
                        tool_results.append(result)

                        if action.tool == tool_name:
                            tool_called = True

                    # 检查执行日志
                    print(f"📋 执行日志: {len(self.execution_log)} 条")
                    for log in self.execution_log:
                        print(f"   {log}")

                    # 验证结果
                    if tool_called and self.execution_log:
                        print(f"✅ 测试案例 {i} 通过 - 工具被正确调用和执行")
                        success_count += 1
                    elif tool_called and not self.execution_log:
                        print(f"⚠️ 测试案例 {i} 部分通过 - 工具被调用但可能没有真正执行")
                    elif not tool_called and self.execution_log:
                        print(f"⚠️ 测试案例 {i} 异常 - 工具被执行但代理没有记录")
                    else:
                        print(f"❌ 测试案例 {i} 失败 - 工具未被调用或执行")

                    # 检查回复是否为空或只是工具定义
                    if not response["output"] or response["output"].strip() == "":
                        print(f"❌ 代理回复为空")
                    elif '"type":"function"' in response["output"]:
                        print(f"❌ 代理只返回了工具定义，没有执行工具")
                    elif any(
                        result in response["output"]
                        for result in tool_results
                        if result
                    ):
                        print(f"✅ 代理回复包含工具执行结果")
                    else:
                        print(f"⚠️ 代理回复可能不包含工具结果")

                except Exception as e:
                    print(f"❌ 测试案例 {i} 执行失败: {e}")
                    traceback.print_exc()

            print(f"\n📊 测试结果总结:")
            print(f"   成功: {success_count}/{len(test_cases)}")
            print(f"   成功率: {success_count/len(test_cases)*100:.1f}%")

            return success_count == len(test_cases)

        except Exception as e:
            print(f"❌ 代理工具执行测试失败: {e}")
            traceback.print_exc()
            return False

    def test_model_understanding(self):
        """测试模型理解能力"""
        print("\n" + "=" * 60)
        print("🧪 测试3: 模型理解能力")
        print("=" * 60)

        try:
            model_config = ollama_config.get_model_config(self.model_name)
            llm = ChatOllama(model=self.model_name, **model_config)

            test_prompt = """你有以下工具可用：
            1. simple_calculator(operation, a, b) - 执行数学运算
            2. weather_checker(city) - 查询天气
            3. text_processor(text, action) - 处理文本

            用户问："请计算 10 + 20 的结果"
            
            你应该：
            1. 使用哪个工具？
            2. 传递什么参数？
            
            请直接回答，不要实际调用工具。"""

            response = llm.invoke(test_prompt)
            print(f"🤖 模型回复: {response.content}")

            # 检查理解能力
            understanding_score = 0
            if "simple_calculator" in response.content.lower():
                understanding_score += 1
                print("✅ 模型正确识别了需要使用的工具")
            else:
                print("❌ 模型没有正确识别工具")

            if (
                "add" in response.content.lower()
                or "10" in response.content
                and "20" in response.content
            ):
                understanding_score += 1
                print("✅ 模型理解了参数需求")
            else:
                print("❌ 模型没有理解参数")

            print(f"📊 理解能力得分: {understanding_score}/2")
            return understanding_score >= 1

        except Exception as e:
            print(f"❌ 模型理解测试失败: {e}")
            return False

    def test_hydromodel_tools(self):
        """测试水文模型工具"""
        print("\n" + "=" * 60)
        print("🧪 测试4: 水文模型工具")
        print("=" * 60)

        try:
            from tool.langchain_tool import get_hydromodel_tools

            # 获取水文工具
            hydro_tools = get_hydromodel_tools()
            if not hydro_tools:
                print("❌ 无法获取水文模型工具")
                return False

            print(f"🔧 获取到 {len(hydro_tools)} 个水文工具:")
            for tool in hydro_tools:
                print(f"   - {tool.name}: {tool.description}")

            # 测试直接调用
            get_params_tool = None
            for tool in hydro_tools:
                if tool.name == "get_model_params":
                    get_params_tool = tool
                    break

            if get_params_tool:
                print(f"\n🧪 测试 get_model_params 工具直接调用...")
                result = get_params_tool.invoke({"model_name": "gr4j"})
                print(f"📊 直接调用结果: {result}")

                if result and "参数" in str(result):
                    print("✅ 水文工具直接调用成功")
                else:
                    print("❌ 水文工具直接调用失败")

            # 测试代理调用水文工具
            print(f"\n🧪 测试代理调用水文工具...")

            # 创建 LLM（应用优化配置）
            model_config = ollama_config.get_model_config(self.model_name)

            # 为 granite 模型添加特殊优化
            if "granite" in self.model_name.lower():
                model_config.update(
                    {
                        "temperature": 0.1,  # 降低温度提高确定性
                        "top_p": 0.8,
                        "num_ctx": 8192,  # 增加上下文窗口
                    }
                )
                print(f"🔧 为水文工具测试应用 {self.model_name} 优化配置")

            llm = ChatOllama(model=self.model_name, **model_config)

            # 根据模型类型创建优化的提示模板
            if "granite" in self.model_name.lower():
                # 为 granite 模型使用英文提示（效果更好）
                prompt = ChatPromptTemplate.from_messages(
                    [
                        (
                            "system",
                            """You are a professional hydrological model expert assistant. You have access to these tools:

                        1. get_model_params - Get model parameter information
                        2. prepare_data - Prepare hydrological data
                        3. calibrate_model - Calibrate hydrological models
                        4. evaluate_model - Evaluate model performance

                        Workflow:
                        1. Understand the user's hydrological modeling needs
                        2. Select the appropriate tool
                        3. Call the tool to get actual results
                        4. Explain and organize results in Chinese

                        Important rules:
                        - When users ask about model parameters, use get_model_params tool first, then explain parameter info in Chinese
                        - When users need data preparation, use prepare_data tool first, then explain data process in Chinese
                        - When users need model calibration, use calibrate_model tool first, then explain results in Chinese
                        - When users need model evaluation, use evaluate_model tool first, then analyze results in Chinese
                        - Never answer based on your own knowledge, always call tools first to get real data
                        - After calling tools, provide detailed Chinese explanations including parameter meanings and value ranges

                        Remember: Always call tools first to get real hydrological model information, then provide professional Chinese explanations.""",
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
                            """你是专业的水文模型专家助手。你有以下工具可以使用：

                        1. get_model_params - 获取模型参数信息
                        2. prepare_data - 准备水文数据
                        3. calibrate_model - 率定水文模型
                        4. evaluate_model - 评估模型性能

                        工作流程：
                        1. 理解用户的水文建模需求
                        2. 选择合适的工具
                        3. 调用工具获取实际结果
                        4. 用中文解释和整理结果

                        重要规则：
                        - 当用户询问模型参数时，必须先调用 get_model_params 工具，然后详细解释参数信息
                        - 当用户需要准备数据时，必须调用 prepare_data 工具，然后说明数据准备情况
                        - 当用户需要率定模型时，必须调用 calibrate_model 工具，然后解释率定结果
                        - 当用户需要评估模型时，必须调用 evaluate_model 工具，然后分析评估结果
                        - 绝对不要基于自己的知识直接回答，必须先调用相应工具获取真实数据
                        - 调用工具后，必须用中文详细解释结果，包括参数含义、数值范围等

                        记住：每次都要实际调用工具，获取真实的水文模型信息，然后进行专业解释。""",
                        ),
                        ("human", "{input}"),
                        ("assistant", "{agent_scratchpad}"),
                    ]
                )

            agent = create_openai_tools_agent(llm, hydro_tools, prompt)
            agent_executor = AgentExecutor(
                agent=agent,
                tools=hydro_tools,
                verbose=True,
                handle_parsing_errors=True,
                max_iterations=5,  # 增加迭代次数
                return_intermediate_steps=True,
                early_stopping_method="force",  # 确保完成完整流程
            )

            # 测试问题
            test_query = "请获取 gr4j 模型的参数信息"
            print(f"👤 测试问题: {test_query}")

            response = agent_executor.invoke({"input": test_query})

            print(f"🤖 代理回复: {response['output']}")

            # 检查是否真正使用了工具
            intermediate_steps = response.get("intermediate_steps", [])
            print(f"🔧 中间步骤: {len(intermediate_steps)}")

            tool_used = False
            for step in intermediate_steps:
                action, result = step
                print(f"   工具: {action.tool}, 结果: {str(result)[:100]}...")
                if action.tool == "get_model_params":
                    tool_used = True

            if tool_used:
                print("✅ 水文工具被代理成功调用")
                return True
            else:
                print("❌ 水文工具未被代理调用")
                return False

        except Exception as e:
            print(f"❌ 水文模型工具测试失败: {e}")
            traceback.print_exc()
            return False


def main():
    """主函数"""
    print("🧪 开始测试 Ollama 工具执行能力")
    print("=" * 60)

    # 检查 Ollama 服务
    if not ollama_config.check_service():
        print("❌ Ollama 服务未运行，请先启动: ollama serve")
        return 1

    # 获取可用模型
    available_models = ollama_config.get_available_models()
    if not available_models:
        print("❌ 没有可用模型")
        return 1

    print(f"📋 可用模型: {', '.join(available_models)}")

    # 选择测试模型
    test_models = ["granite3-dense:8b", "llama3-groq-tool-use:8b", "llama3:8b"]
    selected_model = None

    for model in test_models:
        if model in available_models:
            selected_model = model
            break

    if not selected_model:
        selected_model = available_models[0]
        print(f"⚠️ 未找到推荐模型，使用: {selected_model}")
    else:
        print(f"🎯 选择测试模型: {selected_model}")

    # 创建测试器
    tester = ToolExecutionTester(selected_model)

    # 运行测试
    test_results = []

    # 测试1: 直接工具调用
    test_results.append(("直接工具调用", tester.test_direct_tool_call()))

    # 测试2: 代理工具执行
    test_results.append(("代理工具执行", tester.test_agent_tool_execution()))

    # 测试3: 模型理解能力
    test_results.append(("模型理解能力", tester.test_model_understanding()))

    # 测试4: 水文模型工具
    test_results.append(("水文模型工具", tester.test_hydromodel_tools()))

    # 总结结果
    print("\n" + "=" * 60)
    print("📊 测试结果总结")
    print("=" * 60)

    passed = 0
    total = len(test_results)

    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
        if result:
            passed += 1

    print(f"\n总体结果: {passed}/{total} ({passed/total*100:.1f}%)")

    if passed == total:
        print("🎉 所有测试通过！Ollama 能够正确执行工具")
    elif passed >= total * 0.7:
        print("⚠️ 大部分测试通过，Ollama 基本能够执行工具")
    else:
        print("❌ 多个测试失败，Ollama 可能无法正确执行工具")
        print("\n💡 可能的问题:")
        print("1. 模型不支持工具调用")
        print("2. 模型配置有问题")
        print("3. 提示模板需要优化")
        print("4. 工具定义有问题")

    return 0 if passed >= total * 0.7 else 1


if __name__ == "__main__":
    exit(main())
