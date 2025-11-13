"""
Author: zhuanglaihong
Date: 2024-09-24 17:00:00
LastEditTime: 2024-09-24 17:00:00
LastEditors: zhuanglaihong
Description: 测试智能LLM客户端的API优先和Ollama降级机制
FilePath: \HydroAgent\test\test_intelligent_llm_client.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import sys
import os
from pathlib import Path

# 添加项目根路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

import logging
from executor.core.llm_client import (
    LLMClientFactory, IntelligentLLMClient, LLMMessage,
    QwenAPIClient, OllamaClient
)

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_intelligent_client():
    """测试智能客户端的完整功能"""
    print("=" * 60)
    print("测试智能LLM客户端")
    print("=" * 60)

    try:
        # 创建智能客户端
        logger.info("创建智能客户端...")
        client = LLMClientFactory.create_complex_task_client()
        print(f"[OK] 智能客户端创建成功: {type(client).__name__}")

        # 准备测试消息
        messages = [
            LLMMessage(role="user", content="简单介绍一下GR4J水文模型的主要参数")
        ]

        # 测试聊天功能
        logger.info("开始测试聊天功能...")
        print("\n测试消息: 简单介绍一下GR4J水文模型的主要参数")
        print("-" * 40)

        response = client.chat(messages)

        if response.success:
            print("[OK] 聊天调用成功!")
            print(f"响应长度: {len(response.content)} 字符")
            print(f"响应预览: {response.content[:200]}...")

            # 检查是否使用了降级
            if response.metadata.get("fallback_used"):
                print(f"[WARN] 使用了降级模型: {response.metadata.get('fallback_model')}")
            elif response.metadata.get("provider") == "qwen_api":
                print("[OK] 使用了千问API")
            else:
                print(f"[INFO] 使用了未知提供者: {response.metadata}")

            # 显示使用统计
            usage = response.usage
            if usage:
                print(f"Token使用: {usage}")

            return True
        else:
            print(f"[ERROR] 聊天调用失败: {response.error}")
            return False

    except Exception as e:
        logger.error(f"智能客户端测试异常: {e}")
        print(f"[ERROR] 测试异常: {e}")
        return False

def test_reasoning_vs_coding_separation():
    """测试推理和代码生成分离功能"""
    print("\n" + "=" * 60)
    print("测试推理和代码生成分离功能")
    print("=" * 60)

    try:
        client = IntelligentLLMClient(enable_debug=True)
        print("[OK] 智能客户端创建成功")

        # 测试推理任务
        print("\n1. 测试推理任务:")
        print("-" * 30)
        reasoning_messages = [
            LLMMessage(role="user", content="请分析GR4J水文模型的参数特性和应用场景，并提出率定策略")
        ]

        reasoning_response = client.chat(reasoning_messages, task_type="reasoning")

        if reasoning_response.success:
            print("[OK] 推理任务成功!")
            print(f"使用客户端: {reasoning_response.metadata.get('client_used', 'unknown')}")
            print(f"任务类型: {reasoning_response.metadata.get('task_type', 'unknown')}")
            print(f"响应预览: {reasoning_response.content[:150]}...")
            reasoning_success = True
        else:
            print(f"[ERROR] 推理任务失败: {reasoning_response.error}")
            reasoning_success = False

        # 测试代码生成任务
        print("\n2. 测试代码生成任务:")
        print("-" * 30)
        coding_messages = [
            LLMMessage(role="user", content="请编写一个Python函数，用于计算GR4J模型的有效性系数NSE")
        ]

        coding_response = client.chat(coding_messages, task_type="coding")

        if coding_response.success:
            print("[OK] 代码生成任务成功!")
            print(f"使用客户端: {coding_response.metadata.get('client_used', 'unknown')}")
            print(f"使用模型: {coding_response.metadata.get('model_used', 'unknown')}")
            print(f"任务类型: {coding_response.metadata.get('task_type', 'unknown')}")
            print(f"响应预览: {coding_response.content[:200]}...")
            coding_success = True
        else:
            print(f"[ERROR] 代码生成任务失败: {coding_response.error}")
            coding_success = False

        # 测试通用任务
        print("\n3. 测试通用任务:")
        print("-" * 30)
        general_messages = [
            LLMMessage(role="user", content="介绍一下水文建模的基本步骤")
        ]

        general_response = client.chat(general_messages, task_type="general")

        if general_response.success:
            print("[OK] 通用任务成功!")
            print(f"使用客户端: {general_response.metadata.get('client_used', 'unknown')}")
            print(f"任务类型: {general_response.metadata.get('task_type', 'unknown')}")
            print(f"响应预览: {general_response.content[:150]}...")
            general_success = True
        else:
            print(f"[ERROR] 通用任务失败: {general_response.error}")
            general_success = False

        # 统计结果
        total_success = reasoning_success and coding_success and general_success
        if total_success:
            print("\n[SUCCESS] 推理和代码分离功能测试全部成功!")
        else:
            print(f"\n[PARTIAL] 部分测试成功 - 推理:{reasoning_success}, 代码:{coding_success}, 通用:{general_success}")

        return total_success

    except Exception as e:
        print(f"[ERROR] 分离功能测试异常: {e}")
        return False

def test_ollama_fallback():
    """测试Ollama降级功能"""
    print("\n" + "=" * 60)
    print("测试Ollama降级客户端")
    print("=" * 60)

    try:
        from config import LLM_FALLBACK_MODEL

        client = OllamaClient(model_name=LLM_FALLBACK_MODEL)
        print(f"[OK] Ollama客户端创建成功，模型: {LLM_FALLBACK_MODEL}")

        # 检查服务可用性
        if client.is_available():
            print("[OK] Ollama服务运行正常")

            # 检查模型可用性
            available_models = client.list_models()
            print(f"可用模型: {available_models}")

            if LLM_FALLBACK_MODEL in available_models:
                print(f"[OK] 降级模型 {LLM_FALLBACK_MODEL} 可用")

                # 测试简单调用
                messages = [
                    LLMMessage(role="user", content="简单回答：什么是水文模型？")
                ]

                response = client.chat(messages)

                if response.success:
                    print("[OK] Ollama降级调用成功!")
                    print(f"响应预览: {response.content[:100]}...")
                    return True
                else:
                    print(f"[ERROR] Ollama调用失败: {response.error}")
                    return False

            else:
                print(f"[WARN] 降级模型 {LLM_FALLBACK_MODEL} 不可用")
                print("请运行: ollama pull deepseek-coder:6.7b")
                return False

        else:
            print("[ERROR] Ollama服务不可用")
            print("请确保Ollama服务正在运行")
            return False

    except Exception as e:
        print(f"[ERROR] Ollama测试异常: {e}")
        return False

def test_complex_task_solver_integration():
    """测试复杂任务解决器集成（包含推理和代码分离）"""
    print("\n" + "=" * 60)
    print("测试复杂任务解决器集成（包含推理和代码分离）")
    print("=" * 60)

    try:
        from executor import ComplexTaskExecutor, SimpleTaskExecutor
        from executor.models import Task, TaskType

        # 创建简单任务执行器
        simple_executor = SimpleTaskExecutor()

        # 创建复杂任务解决器（将自动使用智能客户端）
        complex_executor = ComplexTaskExecutor(
            simple_executor=simple_executor,
            enable_debug=True
        )

        print("[OK] 复杂任务解决器创建成功")
        print(f"LLM客户端类型: {type(complex_executor.llm_client).__name__}")

        # 测试一：推理任务（任务分析和解决方案生成）
        print("\n1. 测试推理任务 - 任务解决方案生成:")
        print("-" * 40)

        reasoning_task = Task(
            task_id="test_reasoning_integration",
            name="测试推理集成",
            type=TaskType.COMPLEX,
            description="分析GR4J模型的率定流程，并生成一个包含数据准备、参数优化和结果评估的工具调用序列"
        )

        # 直接测试解决方案生成（不执行完整流程）
        knowledge_chunks = complex_executor._query_knowledge_base(reasoning_task)
        solution_plan = complex_executor._generate_solution_plan(reasoning_task, knowledge_chunks)

        if solution_plan:
            print("[OK] 推理任务 - 解决方案生成成功!")
            print(f"解决方案类型: {solution_plan.solution_type}")
            print(f"步骤数量: {len(solution_plan.steps)}")
            reasoning_success = True

            # 显示几个步骤作为示例
            for i, step in enumerate(solution_plan.steps[:3], 1):
                print(f"  步骤{i}: {step.tool_name} - {step.description}")
        else:
            print("[ERROR] 推理任务 - 解决方案生成失败")
            reasoning_success = False

        # 测试二：代码生成模拟（模拟代码生成步骤）
        print("\n2. 测试代码生成功能:")
        print("-" * 40)

        from executor.core.complex_executor import ToolCall

        # 创建一个模拟的代码生成步骤
        code_step = ToolCall(
            step_id=1,
            tool_name="generate_code",
            parameters={"function_name": "calculate_nse", "inputs": "observed, simulated"},
            description="生成代码计算NSE指标的函数"
        )

        # 测试是否正确识别为代码生成步骤
        is_code_step = complex_executor._is_code_generation_step(code_step)
        print(f"代码步骤识别: {is_code_step}")

        if is_code_step:
            # 测试代码生成执行
            context = {}
            code_result = complex_executor._execute_code_generation_step(code_step, code_step.parameters, context)

            if code_result.success:
                print("[OK] 代码生成步骤执行成功!")
                print(f"生成的代码预览: {code_result.output.get('generated_code', '')[:200]}...")
                print(f"使用模型: {code_result.output.get('model_used', 'unknown')}")
                coding_success = True
            else:
                print(f"[ERROR] 代码生成步骤执行失败: {code_result.error}")
                coding_success = False
        else:
            print("[ERROR] 代码步骤识别失败")
            coding_success = False

        # 统计结果
        total_success = reasoning_success and coding_success
        if total_success:
            print("\n[SUCCESS] 复杂任务解决器集成测试全部成功!")
        else:
            print(f"\n[PARTIAL] 部分测试成功 - 推理:{reasoning_success}, 代码:{coding_success}")

        return total_success

    except Exception as e:
        print(f"[ERROR] 复杂任务解决器测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("开始测试智能LLM客户端功能")
    print("=" * 80)

    test_results = []

    # 测试1: 智能客户端基本功能
    # test_results.append(("智能客户端基本功能", test_intelligent_client()))

    # 测试2: 推理和代码生成分离功能
    test_results.append(("推理和代码生成分离", test_reasoning_vs_coding_separation()))

    # 测试3: Ollama降级功能
    # test_results.append(("Ollama降级功能", test_ollama_fallback()))

    # 测试4: 复杂任务解决器集成（推理+代码分离）
    test_results.append(("复杂任务解决器集成（推理+代码分离）", test_complex_task_solver_integration()))

    # 显示测试结果摘要
    print("\n" + "=" * 80)
    print("测试结果摘要")
    print("=" * 80)

    passed = 0
    failed = 0

    for test_name, result in test_results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status:<8} {test_name}")
        if result:
            passed += 1
        else:
            failed += 1

    print(f"\n总计: {passed} 通过, {failed} 失败")

    if failed == 0:
        print("\n[SUCCESS] 所有测试都通过了！")
    else:
        print(f"\n[WARNING] 有 {failed} 个测试失败，请检查配置和服务状态")

if __name__ == "__main__":
    main()