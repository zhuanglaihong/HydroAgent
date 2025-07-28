"""
Author: zhuanglaihong
Date: 2025-02-21 14:54:24
LastEditTime: 2025-02-26 16:24:08
LastEditors: zhuanglaihong
Description: 测试所有水文模型 LangChain 工具
FilePath: test/test_tools.py
Copyright: Copyright (c) 2021-2024 zhuanglaihong. All rights reserved.
"""

import sys
import os
from pathlib import Path

repo_path = Path(os.path.abspath(__file__)).parent.parent  # 获取两次父路径
sys.path.append(str(repo_path))  # 添加项目根路径

# 导入自定义路径
from definitions import DATASET_DIR, RESULT_DIR, PARAM_RANGE_FILE


def test_tool_import():
    """测试工具导入"""
    print("=== 测试工具导入 ===")

    try:
        from tool.langchain_tool import get_hydromodel_tools, HydroModelTools

        print("✅ 工具模块导入成功")

        # 测试获取工具列表
        tools = get_hydromodel_tools()
        print(f"✅ 成功获取到 {len(tools)} 个工具")

        # 检查是否真正获取到工具
        if len(tools) == 0:
            print("❌ 没有获取到任何工具，测试失败")
            return False

        for i, tool in enumerate(tools, 1):
            print(f"  {i}. {tool.name}: {tool.description}")

        return True

    except Exception as e:
        print(f"❌ 工具导入失败: {e}")
        return False


def test_tool_instantiation():
    """测试工具实例化"""
    print("\n=== 测试工具实例化 ===")

    try:
        from tool.langchain_tool import HydroModelTools

        tools_instance = HydroModelTools()
        print("✅ 工具实例化成功")

        # 测试获取模型参数 - 使用 invoke 方法
        print("\n测试获取模型参数...")
        result = tools_instance.get_model_params_raw("gr4j")
        print(f"结果: {result}")

        return True

    except Exception as e:
        print(f"❌ 工具实例化失败: {e}")
        return False


def test_tool_schemas():
    """测试工具参数模式"""
    print("\n=== 测试工具参数模式 ===")

    try:
        from tool.langchain_tool import (
            ModelParamsInput,
            PrepareDataInput,
            CalibrateModelInput,
            EvaluateModelInput,
        )

        # 测试参数模式
        model_params = ModelParamsInput(model_name="gr4j")
        print(f"✅ 模型参数输入模式: {model_params}")

        prepare_data = PrepareDataInput(data_dir=DATASET_DIR, target_data_scale="D")
        print(f"✅ 数据准备输入模式: {prepare_data}")

        calibrate_model = CalibrateModelInput(model_name="gr4j", data_dir=DATASET_DIR)
        print(f"✅ 模型率定输入模式: {calibrate_model}")

        evaluate_model = EvaluateModelInput(result_dir="result")
        print(f"✅ 模型评估输入模式: {evaluate_model}")

        return True

    except Exception as e:
        print(f"❌ 参数模式测试失败: {e}")
        return False


def test_tool_invoke_methods():
    """测试工具调用方法"""
    print("\n=== 测试工具调用方法 ===")

    try:
        from tool.langchain_tool import HydroModelTools

        tools_instance = HydroModelTools()
        print("✅ 工具实例创建成功")

        # 测试各个工具的 invoke 方法
        print("\n1. 测试 get_model_params 工具...")
        result1 = tools_instance.get_model_params.invoke({"model_name": "gr4j"})
        print(f"结果: {result1}")

        print("\n2. 测试 prepare_data 工具...")
        result2 = tools_instance.prepare_data.invoke(
            {"data_dir": DATASET_DIR, "target_data_scale": "D"}
        )
        print(f"结果: {result2}")

        print("\n3. 测试 calibrate_model 工具...")
        result3 = tools_instance.calibrate_model.invoke(
            {"model_name": "gr4j", "data_dir": DATASET_DIR}
        )
        print(f"结果: {result3}")

        print("\n4. 测试 evaluate_model 工具...")
        result4 = tools_instance.evaluate_model.invoke({"result_dir": f"{RESULT_DIR}"})
        print(f"结果: {result4}")

        return True

    except Exception as e:
        print(f"❌ 工具调用测试失败: {e}")
        return False


def test_langchain_tools():
    """测试 LangChain 工具包装器"""
    print("\n=== 测试 LangChain 工具包装器 ===")

    try:
        from tool.langchain_tool import get_hydromodel_tools

        # 获取 LangChain 工具列表
        tools = get_hydromodel_tools()
        print(f"✅ 获取到 {len(tools)} 个 LangChain 工具")

        # 检查是否真正获取到工具
        if len(tools) == 0:
            print("❌ 没有获取到任何 LangChain 工具，测试失败")
            return False

        # 测试第一个工具
        first_tool = tools[0]
        print(f"测试工具: {first_tool.name}")
        print(f"工具描述: {first_tool.description}")

        # 测试工具调用
        try:
            result = first_tool.invoke({"model_name": "gr4j"})
            print(f"工具调用结果: {result}")
        except Exception as e:
            print(f"工具调用失败: {e}")
            return False

        return True

    except Exception as e:
        print(f"❌ LangChain 工具测试失败: {e}")
        return False


def main():
    """主测试函数"""
    print("开始测试水文模型 LangChain 工具...")

    tests = [
        test_tool_import,
        test_tool_instantiation,
        test_tool_schemas,
        test_tool_invoke_methods,
        test_langchain_tools,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        print()

    print(f"=== 测试结果 ===")
    print(f"通过: {passed}/{total}")

    if passed == total:
        print("🎉 所有工具函数测试完成！")
    else:
        print("⚠️ 部分测试失败，请检查依赖和环境")


if __name__ == "__main__":
    main()
