"""
Author: zhuanglaihong
Date: 2025-02-21 14:54:24
LastEditTime: 2025-02-26 16:24:08
LastEditors: zhuanglaihong
Description: 基本工具功能测试
FilePath: test/test_basic_tools.py
Copyright: Copyright (c) 2021-2024 zhuanglaihong. All rights reserved.
"""

import sys
import os
from pathlib import Path

repo_path = Path(os.path.abspath(__file__)).parent.parent
sys.path.append(str(repo_path))

# 导入自定义路径
from definitions import DATASET_DIR, RESULT_DIR, PARAM_RANGE_FILE


def test_basic_imports():
    """测试基本导入"""
    print("=== 测试基本导入 ===")

    try:
        # 测试基本模块
        import sys
        import os
        import yaml
        from pathlib import Path
        from typing import Dict, List, Any, Optional

        print("✅ 基本模块导入成功")

        # 测试 Pydantic
        from pydantic import BaseModel, Field

        print("✅ Pydantic 导入成功")

        return True

    except Exception as e:
        print(f"❌ 基本导入失败: {e}")
        return False


def test_pydantic_models():
    """测试 Pydantic 模型"""
    print("\n=== 测试 Pydantic 模型 ===")

    try:
        from pydantic import BaseModel, Field

        # 创建测试模型
        class TestModelParams(BaseModel):
            model_name: str = Field(description="模型名称")

        class TestPrepareData(BaseModel):
            data_dir: str = Field(default=DATASET_DIR, description="数据目录")
            target_data_scale: str = Field(default="D", description="时间尺度")

        # 测试模型创建
        model_params = TestModelParams(model_name="gr4j")
        print(f"✅ 模型参数模型: {model_params}")

        prepare_data = TestPrepareData(data_dir=DATASET_DIR, target_data_scale="D")
        print(f"✅ 数据准备模型: {prepare_data}")

        return True

    except Exception as e:
        print(f"❌ Pydantic 模型测试失败: {e}")
        return False


def test_tool_structure():
    """测试工具结构"""
    print("\n=== 测试工具结构 ===")

    try:
        # 模拟工具结构
        class MockTool:
            def __init__(self, name: str, description: str):
                self.name = name
                self.description = description

            def invoke(self, args: dict):
                return {"status": "success", "result": f"Mock result for {self.name}"}

        # 创建模拟工具
        tools = [
            MockTool("get_model_params", "获取模型参数信息"),
            MockTool("prepare_data", "准备水文数据"),
            MockTool("calibrate_model", "率定水文模型"),
            MockTool("evaluate_model", "评估模型性能"),
        ]

        print(f"✅ 创建了 {len(tools)} 个模拟工具")

        for i, tool in enumerate(tools, 1):
            print(f"  {i}. {tool.name}: {tool.description}")

            # 测试 invoke 方法
            result = tool.invoke({"test": "value"})
            print(f"    调用结果: {result}")

        return True

    except Exception as e:
        print(f"❌ 工具结构测试失败: {e}")
        return False


def test_file_structure():
    """测试文件结构"""
    print("\n=== 测试文件结构 ===")

    try:
        # 检查必要的文件是否存在
        tool_dir = Path(repo_path) / "tool"
        test_dir = Path(repo_path) / "test"

        required_files = [
            tool_dir / "langchain_tool.py",
            tool_dir / "langchain_agent.py",
            tool_dir / "ollama_config.py",
            tool_dir / "README.md",
            test_dir / "test_tools.py",
        ]

        existing_files = []
        missing_files = []

        for file_path in required_files:
            if file_path.exists():
                existing_files.append(file_path.name)
            else:
                missing_files.append(file_path.name)

        print(f"✅ 存在的文件: {existing_files}")
        if missing_files:
            print(f"❌ 缺失的文件: {missing_files}")
        else:
            print("✅ 所有必要文件都存在")

        return len(missing_files) == 0

    except Exception as e:
        print(f"❌ 文件结构测试失败: {e}")
        return False


def test_simple_function():
    """测试简单函数"""
    print("\n=== 测试简单函数 ===")

    try:
        # 模拟水文模型工具函数
        def get_model_params(model_name: str):
            """获取模型参数"""
            if model_name == "gr4j":
                return {
                    "model_name": "gr4j",
                    "param_names": ["X1", "X2", "X3", "X4"],
                    "param_ranges": [[100, 1200], [0, 5], [20, 300], [0.5, 2]],
                }
            else:
                return {"error": f"不支持的模型 {model_name}"}

        def prepare_data(data_dir: str, target_data_scale: str = "D"):
            """准备数据"""
            return {
                "status": "success",
                "message": f"数据准备完成: {data_dir}, 尺度: {target_data_scale}",
            }

        # 测试函数调用
        result1 = get_model_params("gr4j")
        print(f"✅ get_model_params 结果: {result1}")

        result2 = prepare_data(DATASET_DIR, "D")
        print(f"✅ prepare_data 结果: {result2}")

        return True

    except Exception as e:
        print(f"❌ 简单函数测试失败: {e}")
        return False


def main():
    """主测试函数"""
    print("开始基本工具功能测试...")

    tests = [
        test_basic_imports,
        test_pydantic_models,
        test_tool_structure,
        test_file_structure,
        test_simple_function,
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
        print("🎉 所有基本测试通过！")
        print("\n下一步：")
        print("运行完整测试: python test/test_tools.py")
    else:
        print("⚠️ 部分测试失败，请检查环境")


if __name__ == "__main__":
    main()
