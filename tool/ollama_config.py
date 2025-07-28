"""
Author: zhuanglaihong
Date: 2025-02-21 14:54:24
LastEditTime: 2025-02-26 16:24:08
LastEditors: zhuanglaihong
Description: Ollama 本地模型配置
FilePath: tool/ollama_config.py
Copyright: Copyright (c) 2021-2024 zhuanglaihong. All rights reserved.
"""

import requests
from typing import List, Optional, Dict, Any


class OllamaConfig:
    """Ollama 配置管理类"""

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"

    def check_service(self) -> bool:
        """检查 Ollama 服务是否运行"""
        try:
            response = requests.get(f"{self.api_url}/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def get_available_models(self) -> List[str]:
        """获取可用的模型列表"""
        try:
            response = requests.get(f"{self.api_url}/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                return [model["name"] for model in models]
            return []
        except Exception:
            return []

    def get_model_info(self, model_name: str) -> Optional[Dict[str, Any]]:
        """获取模型信息"""
        try:
            response = requests.post(
                f"{self.api_url}/show", json={"name": model_name}, timeout=10
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception:
            return None

    def select_best_model(self, preferred_models: List[str] = None) -> Optional[str]:
        """选择最佳可用模型"""
        if preferred_models is None:
            # 优先选择支持工具的模型
            preferred_models = [
                "llama2:7b",
                "llama2:13b",
                "granite3-dense:8b",
                "llama3-groq-tool-use:8b",
            ]

        available_models = self.get_available_models()
        if not available_models:
            return None

        # 按优先级选择模型
        for model in preferred_models:
            if model in available_models:
                return model

        # 如果没有找到优先模型，返回第一个可用模型
        return available_models[0]

    def is_tool_supported_model(self, model_name: str) -> bool:
        """检查模型是否支持工具调用"""
        # 已知支持工具的模型（基于实际测试）
        tool_supported_models = [
            # Llama3 系列（最新，支持工具）
            "llama3",
            "llama3:8b",
            "llama3:70b",
            "llama3.1:8b",
            "llama3.1:70b",
            "llama3.2:3b",
            "llama3.2:7b",
            "llama3.2:13b",
            "llama3.2:70b",
            # Groq 工具使用模型（专门支持工具调用）
            "llama3-groq-tool-use:8b",
            "llama3-groq-tool-use",
            # Granite 系列模型
            "granite3-dense:8b",
            "granite3-dense",
            # 代码模型（通常支持工具）
            "deepseek-coder",
            "codellama",
            "codellama:7b",
            "codellama:13b",
            "codellama:34b",
            # 其他可能支持的模型
            "mistral:7b",
            "mistral:instruct",
            "mistral:7b-instruct",
            "qwen2.5:7b",
            "qwen2.5:14b",
            "qwen2.5:32b",
            "phi3",
            "phi3:mini",
            "phi3:medium",
            "phi3:small",
        ]

        # 检查基础模型名称
        base_model = model_name.split(":")[0]

        # 检查完整模型名称或基础模型名称
        return (
            model_name in tool_supported_models or base_model in tool_supported_models
        )

    def get_model_config(self, model_name: str) -> Dict[str, Any]:
        """获取模型配置"""
        # 根据模型类型返回不同的配置
        configs = {
            "llama2": {
                "temperature": 0.7,
                "top_p": 0.9,
                "num_ctx": 4096,
                "repeat_penalty": 1.1,
            },
            "llama2:7b": {
                "temperature": 0.7,
                "top_p": 0.9,
                "num_ctx": 4096,
                "repeat_penalty": 1.1,
            },
            "llama2:13b": {
                "temperature": 0.7,
                "top_p": 0.9,
                "num_ctx": 4096,
                "repeat_penalty": 1.1,
            },
            "deepseek-coder": {
                "temperature": 0.3,
                "top_p": 0.95,
                "num_ctx": 8192,
                "repeat_penalty": 1.1,
            },
            "codellama": {
                "temperature": 0.3,
                "top_p": 0.95,
                "num_ctx": 8192,
                "repeat_penalty": 1.1,
            },
            "qwen2.5:7b": {
                "temperature": 0.7,
                "top_p": 0.9,
                "num_ctx": 4096,
                "repeat_penalty": 1.1,
            },
            "qwen2.5:14b": {
                "temperature": 0.7,
                "top_p": 0.9,
                "num_ctx": 8192,
                "repeat_penalty": 1.1,
            },
        }

        # 获取基础模型名称（去掉版本号）
        base_model = model_name.split(":")[0]

        # 为 granite 系列模型添加优化配置
        if "granite" in model_name.lower():
            return {
                "temperature": 0.1,  # 降低温度提高确定性
                "top_p": 0.8,
                "num_ctx": 8192,  # 增加上下文窗口
                "repeat_penalty": 1.1,
            }

        # 返回特定模型配置或默认配置
        return configs.get(
            model_name,
            configs.get(
                base_model,
                {
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "num_ctx": 4096,
                    "repeat_penalty": 1.1,
                },
            ),
        )

    def test_model(self, model_name: str) -> bool:
        """测试模型是否可用"""
        try:
            response = requests.post(
                f"{self.api_url}/generate",
                json={"model": model_name, "prompt": "Hello", "stream": False},
                timeout=30,
            )
            return response.status_code == 200
        except Exception:
            return False


# 全局配置实例
ollama_config = OllamaConfig()


def get_ollama_llm_config():
    """获取 Ollama LLM 配置"""

    if not ollama_config.check_service():
        print("❌ Ollama 服务未运行")
        return None, None

    # 选择最佳模型
    selected_model = ollama_config.select_best_model()
    if not selected_model:
        print("❌ 没有找到可用的模型")
        return None, None

    # 检查模型是否支持工具调用
    if not ollama_config.is_tool_supported_model(selected_model):
        print(f"⚠️ 警告: {selected_model} 可能不支持工具调用")
        print("💡 建议使用支持工具的模型，如 llama2, deepseek-coder 等")

    # 获取模型配置
    model_config = ollama_config.get_model_config(selected_model)

    print(f"✅ 选择模型: {selected_model}")
    print(f"📋 模型配置: {model_config}")

    return selected_model, model_config


def create_ollama_llm_with_config():
    """使用配置创建 Ollama LLM"""
    from langchain_ollama import ChatOllama

    model_name, config = get_ollama_llm_config()
    if not model_name or not config:
        return None

    try:
        llm = ChatOllama(model=model_name, **config)
        print("✅ 本地 Ollama 模型创建成功")
        return llm
    except Exception as e:
        print(f"❌ 模型创建失败: {e}")
        return None


def create_tool_supported_llm():
    """创建支持工具的 Ollama LLM"""
    # 对于工具调用，应该使用 ChatOllama
    from langchain_ollama import ChatOllama

    print("✅ 使用 ChatOllama 类（支持工具调用）")

    if not ollama_config.check_service():
        print("❌ Ollama 服务未运行")
        return None

    # 获取可用模型
    available_models = ollama_config.get_available_models()
    if not available_models:
        print("❌ 没有找到可用的模型")
        return None

    # 优先选择支持工具的模型（基于测试验证，按推荐优先级排序）
    tool_supported_models = [
        # 首选模型（经过验证，工具调用效果最佳）
        "granite3-dense:8b",
        "granite3-dense",
        # Groq 工具使用模型（专门支持工具调用）
        "llama3-groq-tool-use:8b",
        "llama3-groq-tool-use",
        # Llama3 系列（最新，支持工具）
        "llama3:8b",
        "llama3.2:7b",
        "llama3.2:3b",
        "llama3.1:8b",
        "llama3",
        "llama3:70b",
        "llama3.1:70b",
        "llama3.2:13b",
        "llama3.2:70b",
        # 代码模型（通常支持工具）
        "deepseek-coder",
        "codellama",
        "codellama:7b",
        "codellama:13b",
        # 其他可能支持的模型
        "mistral:7b",
        "mistral:instruct",
        "mistral:7b-instruct",
        "qwen2.5:7b",
        "qwen2.5:14b",
        "qwen2.5:32b",
        "phi3:mini",
        "phi3:small",
        "phi3:medium",
        "phi3",
    ]

    selected_model = None
    for model in tool_supported_models:
        if model in available_models:
            selected_model = model
            break

    if not selected_model:
        print("❌ 没有找到支持工具的模型")
        print("💡 请下载支持工具的模型，例如：")
        print("   ollama pull llama3:8b")
        print("   ollama pull llama3.2:7b")
        print("   ollama pull llama3-groq-tool-use:8b")
        print("   ollama pull granite3-dense:8b")
        print("   ollama pull deepseek-coder")
        print("   ollama pull codellama")
        return None

    # 获取模型配置
    model_config = ollama_config.get_model_config(selected_model)

    try:
        # 使用 ChatOllama 进行工具调用
        llm = ChatOllama(model=selected_model, **model_config)
        print(f"✅ 创建支持工具的模型: {selected_model}")
        return llm
    except Exception as e:
        print(f"❌ 模型创建失败: {e}")
        return None


if __name__ == "__main__":
    # 测试配置
    print("=== Ollama 配置测试 ===")

    if ollama_config.check_service():
        print("✅ Ollama 服务正在运行")

        models = ollama_config.get_available_models()
        print(f"📋 可用模型: {', '.join(models)}")

        selected_model = ollama_config.select_best_model()
        if selected_model:
            print(f"🎯 推荐模型: {selected_model}")

            config = ollama_config.get_model_config(selected_model)
            print(f"⚙️ 模型配置: {config}")

            if ollama_config.test_model(selected_model):
                print("✅ 模型测试通过")
            else:
                print("❌ 模型测试失败")
    else:
        print("❌ Ollama 服务未运行")
