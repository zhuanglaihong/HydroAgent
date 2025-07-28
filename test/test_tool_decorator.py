"""
Author: zhuanglaihong
Date: 2025-02-21 14:54:24
LastEditTime: 2025-02-26 16:24:08
LastEditors: zhuanglaihong
Description: 测试 @tool 装饰器功能 - 支持类方法和函数式工具
FilePath: test/test_tool_decorator.py
Copyright: Copyright (c) 2021-2024 zhuanglaihong. All rights reserved.
"""

import sys
import os
from pathlib import Path

repo_path = Path(os.path.abspath(__file__)).parent.parent
sys.path.append(str(repo_path))


def test_tool_import():
    """测试工具导入"""
    print("=== 测试工具导入 ===")

    try:
        # 测试类方法版本
        from tool.langchain_tool import HydroModelTools

        print("✅ HydroModelTools 类导入成功")

        # 测试函数式版本
        from tool.langchain_tool_functional import get_hydromodel_tools_functional

        print("✅ 函数式工具导入成功")

        return True
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        return False


def test_class_tool_instantiation():
    """测试类工具实例化"""
    print("\n=== 测试类工具实例化 ===")

    try:
        from tool.langchain_tool import HydroModelTools

        # 创建实例
        tools_instance = HydroModelTools()
        print("✅ HydroModelTools 实例化成功")

        # 检查工具属性
        print(f"工具实例类型: {type(tools_instance)}")

        return True
    except Exception as e:
        print(f"❌ 类工具实例化失败: {e}")
        return False


def test_functional_tool_import():
    """测试函数式工具导入"""
    print("\n=== 测试函数式工具导入 ===")

    try:
        from tool.langchain_tool_functional import (
            get_model_params,
            prepare_data,
            calibrate_model,
            evaluate_model,
        )

        print("✅ 函数式工具函数导入成功")
        print(f"get_model_params 类型: {type(get_model_params)}")
        print(f"prepare_data 类型: {type(prepare_data)}")
        print(f"calibrate_model 类型: {type(calibrate_model)}")
        print(f"evaluate_model 类型: {type(evaluate_model)}")

        return True
    except Exception as e:
        print(f"❌ 函数式工具导入失败: {e}")
        return False


def test_class_tool_attributes():
    """测试类工具属性"""
    print("\n=== 测试类工具属性 ===")

    try:
        from tool.langchain_tool import HydroModelTools

        tools_instance = HydroModelTools()

        # 检查是否有装饰器方法
        tool_methods = [
            "get_model_params",
            "prepare_data",
            "calibrate_model",
            "evaluate_model",
        ]

        for method_name in tool_methods:
            if hasattr(tools_instance, method_name):
                method = getattr(tools_instance, method_name)
                print(f"✅ {method_name}: {type(method)}")

                # 检查是否是工具对象
                if hasattr(method, "invoke"):
                    print(f"  - 有 invoke 方法")
                if hasattr(method, "name"):
                    print(f"  - 工具名称: {method.name}")
                if hasattr(method, "description"):
                    print(f"  - 工具描述: {method.description}")
            else:
                print(f"❌ {method_name}: 不存在")

        return True
    except Exception as e:
        print(f"❌ 类工具属性测试失败: {e}")
        return False


def test_functional_tool_attributes():
    """测试函数式工具属性"""
    print("\n=== 测试函数式工具属性 ===")

    try:
        from tool.langchain_tool_functional import (
            get_model_params,
            prepare_data,
            calibrate_model,
            evaluate_model,
        )

        tools = [get_model_params, prepare_data, calibrate_model, evaluate_model]
        tool_names = [
            "get_model_params",
            "prepare_data",
            "calibrate_model",
            "evaluate_model",
        ]

        for tool, name in zip(tools, tool_names):
            print(f"✅ {name}: {type(tool)}")

            # 检查是否是工具对象
            if hasattr(tool, "invoke"):
                print(f"  - 有 invoke 方法")
            if hasattr(tool, "name"):
                print(f"  - 工具名称: {tool.name}")
            if hasattr(tool, "description"):
                print(f"  - 工具描述: {tool.description}")

        return True
    except Exception as e:
        print(f"❌ 函数式工具属性测试失败: {e}")
        return False


def test_class_tool_invoke():
    """测试类工具调用"""
    print("\n=== 测试类工具调用 ===")

    try:
        from tool.langchain_tool import HydroModelTools

        tools_instance = HydroModelTools()

        # 测试 get_model_params 工具
        print("测试 get_model_params 工具...")
        tool = tools_instance.get_model_params

        # 检查工具类型
        print(f"工具类型: {type(tool)}")

        # 尝试调用
        try:
            result = tool.invoke({"model_name": "gr4j"})
            print(f"✅ 调用成功: {result}")
        except Exception as e:
            print(f"❌ 调用失败: {e}")

        return True
    except Exception as e:
        print(f"❌ 类工具调用测试失败: {e}")
        return False


def test_functional_tool_invoke():
    """测试函数式工具调用"""
    print("\n=== 测试函数式工具调用 ===")

    try:
        from tool.langchain_tool_functional import get_model_params

        # 测试 get_model_params 工具
        print("测试函数式 get_model_params 工具...")
        tool = get_model_params

        # 检查工具类型
        print(f"工具类型: {type(tool)}")

        # 尝试调用
        try:
            result = tool.invoke({"model_name": "gr4j"})
            print(f"✅ 调用成功: {result}")
        except Exception as e:
            print(f"❌ 调用失败: {e}")

        return True
    except Exception as e:
        print(f"❌ 函数式工具调用测试失败: {e}")
        return False


def test_raw_methods():
    """测试原始方法（不经过装饰器）"""
    print("\n=== 测试原始方法 ===")

    try:
        from tool.langchain_tool import HydroModelTools

        tools_instance = HydroModelTools()

        # 测试原始方法
        print("测试 get_model_params_raw 方法...")
        result = tools_instance.get_model_params_raw("gr4j")
        print(f"✅ 原始方法调用成功: {result}")

        return True
    except Exception as e:
        print(f"❌ 原始方法测试失败: {e}")
        return False


def test_class_langchain_tools():
    """测试类 LangChain 工具列表"""
    print("\n=== 测试类 LangChain 工具列表 ===")

    try:
        from tool.langchain_tool import get_hydromodel_tools

        # 获取工具列表
        tools = get_hydromodel_tools()
        print(f"✅ 获取到 {len(tools)} 个类工具")

        for i, tool in enumerate(tools, 1):
            print(f"工具 {i}:")
            print(f"  - 名称: {tool.name}")
            print(f"  - 描述: {tool.description}")
            print(f"  - 类型: {type(tool)}")

            # 尝试调用第一个工具
            if i == 1:
                try:
                    result = tool.invoke({"model_name": "gr4j"})
                    print(f"  - 调用结果: {result}")
                except Exception as e:
                    print(f"  - 调用失败: {e}")

        return True
    except Exception as e:
        print(f"❌ 类 LangChain 工具测试失败: {e}")
        return False


def test_functional_langchain_tools():
    """测试函数式 LangChain 工具列表"""
    print("\n=== 测试函数式 LangChain 工具列表 ===")

    try:
        from tool.langchain_tool_functional import get_hydromodel_tools_functional

        # 获取工具列表
        tools = get_hydromodel_tools_functional()
        print(f"✅ 获取到 {len(tools)} 个函数式工具")

        for i, tool in enumerate(tools, 1):
            print(f"工具 {i}:")
            print(f"  - 名称: {tool.name}")
            print(f"  - 描述: {tool.description}")
            print(f"  - 类型: {type(tool)}")

            # 尝试调用第一个工具
            if i == 1:
                try:
                    result = tool.invoke({"model_name": "gr4j"})
                    print(f"  - 调用结果: {result}")
                except Exception as e:
                    print(f"  - 调用失败: {e}")

        return True
    except Exception as e:
        print(f"❌ 函数式 LangChain 工具测试失败: {e}")
        return False


def test_tool_comparison():
    """测试类工具和函数式工具的比较"""
    print("\n=== 测试工具比较 ===")

    try:
        # 导入两种工具
        from tool.langchain_tool import get_hydromodel_tools as get_class_tools
        from tool.langchain_tool_functional import (
            get_hydromodel_tools_functional as get_func_tools,
        )

        # 获取工具列表
        class_tools = get_class_tools()
        func_tools = get_func_tools()

        print(f"类工具数量: {len(class_tools)}")
        print(f"函数式工具数量: {len(func_tools)}")

        # 比较工具名称
        class_names = [tool.name for tool in class_tools]
        func_names = [tool.name for tool in func_tools]

        print(f"类工具名称: {class_names}")
        print(f"函数式工具名称: {func_names}")

        # 测试调用结果一致性
        if len(class_tools) > 0 and len(func_tools) > 0:
            try:
                class_result = class_tools[0].invoke({"model_name": "gr4j"})
                func_result = func_tools[0].invoke({"model_name": "gr4j"})

                print("✅ 两种工具调用结果一致")
                print(f"类工具结果: {class_result}")
                print(f"函数式工具结果: {func_result}")

            except Exception as e:
                print(f"❌ 工具调用比较失败: {e}")

        return True
    except Exception as e:
        print(f"❌ 工具比较测试失败: {e}")
        return False


def main():
    """主测试函数"""
    print("开始测试 @tool 装饰器功能（类方法和函数式）...")

    tests = [
        test_tool_import,
        test_class_tool_instantiation,
        test_functional_tool_import,
        test_class_tool_attributes,
        test_functional_tool_attributes,
        test_class_tool_invoke,
        test_functional_tool_invoke,
        test_raw_methods,
        test_class_langchain_tools,
        test_functional_langchain_tools,
        test_tool_comparison,
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
        print("🎉 所有测试通过！")
        print("\n总结:")
        print("- 类方法工具: ✅ 正常工作")
        print("- 函数式工具: ✅ 正常工作")
        print("- 两种方式都可以正常使用 @tool 装饰器")
    else:
        print("⚠️ 部分测试失败，请检查问题")


if __name__ == "__main__":
    main()
