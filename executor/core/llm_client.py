"""
Author: zhuanglaihong
Date: 2024-09-26 16:40:00
LastEditTime: 2024-09-26 16:40:00
LastEditors: zhuanglaihong
Description: LLM客户端 - 统一的大语言模型调用接口
FilePath: \HydroAgent\executor\core\llm_client.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import logging
import json
import time
from typing import Dict, List, Any, Optional, Union
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logging.warning("requests模块不可用，LLM调用功能将受限")

# 导入配置文件
try:
    from config import (
        LLM_USE_API_FIRST,
        LLM_API_MODEL_NAME,
        LLM_API_TIMEOUT,
        LLM_API_MAX_RETRIES,
        LLM_FALLBACK_MODEL,
        LLM_FALLBACK_TIMEOUT,
    )

    CONFIG_AVAILABLE = True
except ImportError:
    # 默认配置
    LLM_USE_API_FIRST = True
    LLM_API_MODEL_NAME = "qwen3-coder-plus"
    LLM_API_TIMEOUT = 30
    LLM_API_MAX_RETRIES = 2
    LLM_FALLBACK_MODEL = "deepseek-coder:6.7b"
    LLM_FALLBACK_TIMEOUT = 60
    CONFIG_AVAILABLE = False
    logging.warning("config.py不可用，使用默认LLM配置")

# 导入API配置
try:
    from definitions import OPENAI_API_KEY

    API_KEY_AVAILABLE = bool(OPENAI_API_KEY)
except ImportError:
    API_KEY_AVAILABLE = False
    OPENAI_API_KEY = None
    logging.warning("API密钥不可用")


class LLMMessage(BaseModel):
    """LLM消息模型"""

    role: str = Field(..., description="消息角色: system/user/assistant")
    content: str = Field(..., description="消息内容")


class LLMResponse(BaseModel):
    """LLM响应模型"""

    success: bool = Field(..., description="是否成功")
    content: str = Field(default="", description="响应内容")
    error: Optional[str] = Field(None, description="错误信息")
    usage: Dict[str, Any] = Field(default_factory=dict, description="使用统计")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")


class BaseLLMClient(ABC):
    """LLM客户端基类"""

    def __init__(self, model_name: str, api_key: str = None, base_url: str = None):
        """
        初始化LLM客户端

        Args:
            model_name: 模型名称
            api_key: API密钥
            base_url: API基础URL
        """
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url
        self.logger = logging.getLogger(f"llm_client.{self.__class__.__name__}")

    @abstractmethod
    def chat(self, messages: List[LLMMessage], **kwargs) -> LLMResponse:
        """
        聊天对话

        Args:
            messages: 消息列表
            **kwargs: 额外参数

        Returns:
            LLMResponse: 响应结果
        """
        pass

    @abstractmethod
    def complete(self, prompt: str, **kwargs) -> LLMResponse:
        """
        文本补全

        Args:
            prompt: 提示文本
            **kwargs: 额外参数

        Returns:
            LLMResponse: 响应结果
        """
        pass


class OllamaClient(BaseLLMClient):
    """Ollama本地LLM客户端"""

    def __init__(
        self, model_name: str = "qwen2.5:7b", base_url: str = "http://localhost:11434"
    ):
        super().__init__(model_name=model_name, base_url=base_url)
        self.api_url = f"{base_url}/api"

    def chat(self, messages: List[LLMMessage], **kwargs) -> LLMResponse:
        """Ollama聊天接口"""
        if not REQUESTS_AVAILABLE:
            return LLMResponse(success=False, error="requests模块不可用")

        try:
            # 转换消息格式
            ollama_messages = [
                {"role": msg.role, "content": msg.content} for msg in messages
            ]

            # 构建请求数据
            data = {
                "model": self.model_name,
                "messages": ollama_messages,
                "stream": False,
                **kwargs,
            }

            # 发送请求
            start_time = time.time()
            response = requests.post(
                f"{self.api_url}/chat", json=data, timeout=300  # 5分钟超时
            )
            end_time = time.time()

            if response.status_code == 200:
                result = response.json()
                content = result.get("message", {}).get("content", "")

                return LLMResponse(
                    success=True,
                    content=content,
                    usage={
                        "prompt_tokens": result.get("prompt_eval_count", 0),
                        "completion_tokens": result.get("eval_count", 0),
                        "total_tokens": result.get("prompt_eval_count", 0)
                        + result.get("eval_count", 0),
                    },
                    metadata={
                        "model": self.model_name,
                        "response_time": end_time - start_time,
                        "load_duration": result.get("load_duration", 0),
                        "prompt_eval_duration": result.get("prompt_eval_duration", 0),
                        "eval_duration": result.get("eval_duration", 0),
                    },
                )
            else:
                return LLMResponse(
                    success=False,
                    error=f"Ollama API错误: {response.status_code} - {response.text}",
                )

        except Exception as e:
            self.logger.error(f"Ollama聊天请求失败: {e}")
            return LLMResponse(success=False, error=f"请求失败: {str(e)}")

    def complete(self, prompt: str, **kwargs) -> LLMResponse:
        """Ollama文本补全接口"""
        if not REQUESTS_AVAILABLE:
            return LLMResponse(success=False, error="requests模块不可用")

        try:
            data = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                **kwargs,
            }

            start_time = time.time()
            response = requests.post(f"{self.api_url}/generate", json=data, timeout=300)
            end_time = time.time()

            if response.status_code == 200:
                result = response.json()
                content = result.get("response", "")

                return LLMResponse(
                    success=True,
                    content=content,
                    usage={
                        "prompt_tokens": result.get("prompt_eval_count", 0),
                        "completion_tokens": result.get("eval_count", 0),
                        "total_tokens": result.get("prompt_eval_count", 0)
                        + result.get("eval_count", 0),
                    },
                    metadata={
                        "model": self.model_name,
                        "response_time": end_time - start_time,
                        "load_duration": result.get("load_duration", 0),
                        "prompt_eval_duration": result.get("prompt_eval_duration", 0),
                        "eval_duration": result.get("eval_duration", 0),
                    },
                )
            else:
                return LLMResponse(
                    success=False,
                    error=f"Ollama API错误: {response.status_code} - {response.text}",
                )

        except Exception as e:
            self.logger.error(f"Ollama补全请求失败: {e}")
            return LLMResponse(success=False, error=f"请求失败: {str(e)}")

    def is_available(self) -> bool:
        """检查Ollama服务是否可用"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False

    def list_models(self) -> List[str]:
        """获取可用模型列表"""
        try:
            response = requests.get(f"{self.api_url}/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                return [model["name"] for model in models]
            return []
        except:
            return []


class OpenAIClient(BaseLLMClient):
    """OpenAI API客户端"""

    def __init__(
        self,
        model_name: str = "gpt-3.5-turbo",
        api_key: str = None,
        base_url: str = None,
    ):
        super().__init__(model_name=model_name, api_key=api_key, base_url=base_url)
        self.api_url = base_url or "https://api.openai.com/v1"

    def chat(self, messages: List[LLMMessage], **kwargs) -> LLMResponse:
        """OpenAI聊天接口"""
        if not REQUESTS_AVAILABLE:
            return LLMResponse(success=False, error="requests模块不可用")

        if not self.api_key:
            return LLMResponse(success=False, error="缺少OpenAI API密钥")

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            openai_messages = [
                {"role": msg.role, "content": msg.content} for msg in messages
            ]

            data = {"model": self.model_name, "messages": openai_messages, **kwargs}

            start_time = time.time()
            response = requests.post(
                f"{self.api_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=300,
            )
            end_time = time.time()

            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                usage = result.get("usage", {})

                return LLMResponse(
                    success=True,
                    content=content,
                    usage=usage,
                    metadata={
                        "model": self.model_name,
                        "response_time": end_time - start_time,
                    },
                )
            else:
                return LLMResponse(
                    success=False,
                    error=f"OpenAI API错误: {response.status_code} - {response.text}",
                )

        except Exception as e:
            self.logger.error(f"OpenAI聊天请求失败: {e}")
            return LLMResponse(success=False, error=f"请求失败: {str(e)}")

    def complete(self, prompt: str, **kwargs) -> LLMResponse:
        """OpenAI文本补全接口"""
        # 将补全转换为聊天格式
        messages = [LLMMessage(role="user", content=prompt)]
        return self.chat(messages, **kwargs)


class QwenAPIClient(BaseLLMClient):
    """千问API客户端（阿里云DashScope）"""

    def __init__(self, model_name: str = None, api_key: str = None):
        super().__init__(
            model_name=model_name or LLM_API_MODEL_NAME,
            api_key=api_key or OPENAI_API_KEY,
        )
        self.base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    def chat(self, messages: List[LLMMessage], **kwargs) -> LLMResponse:
        """千问API聊天接口"""
        if not REQUESTS_AVAILABLE:
            return LLMResponse(success=False, error="requests模块不可用")

        if not self.api_key:
            return LLMResponse(success=False, error="缺少千问API密钥")

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            qwen_messages = [
                {"role": msg.role, "content": msg.content} for msg in messages
            ]

            data = {"model": self.model_name, "messages": qwen_messages, **kwargs}

            start_time = time.time()
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=LLM_API_TIMEOUT,
            )
            end_time = time.time()

            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                usage = result.get("usage", {})

                return LLMResponse(
                    success=True,
                    content=content,
                    usage=usage,
                    metadata={
                        "model": self.model_name,
                        "response_time": end_time - start_time,
                        "provider": "qwen_api",
                    },
                )
            else:
                error_msg = f"千问API错误: {response.status_code}"
                try:
                    error_detail = (
                        response.json().get("error", {}).get("message", response.text)
                    )
                    error_msg += f" - {error_detail}"
                except:
                    error_msg += f" - {response.text}"

                return LLMResponse(success=False, error=error_msg)

        except requests.exceptions.Timeout:
            return LLMResponse(
                success=False, error=f"千问API调用超时 (>{LLM_API_TIMEOUT}s)"
            )
        except Exception as e:
            self.logger.error(f"千问API聊天请求失败: {e}")
            return LLMResponse(success=False, error=f"请求失败: {str(e)}")

    def complete(self, prompt: str, **kwargs) -> LLMResponse:
        """千问API文本补全接口"""
        messages = [LLMMessage(role="user", content=prompt)]
        return self.chat(messages, **kwargs)


class IntelligentLLMClient(BaseLLMClient):
    """智能LLM客户端 - 支持推理和代码生成分离，API优先，Ollama降级"""

    def __init__(self, enable_debug: bool = False):
        super().__init__(model_name="intelligent_client")
        self.enable_debug = enable_debug

        # 初始化推理客户端（用于任务分析和知识推理）
        self.reasoning_client = None
        if API_KEY_AVAILABLE and LLM_USE_API_FIRST:
            try:
                self.reasoning_client = QwenAPIClient()
                self.logger.info("初始化推理客户端（千问API）成功")
            except Exception as e:
                self.logger.warning(f"初始化推理API客户端失败: {e}")

        # 初始化代码生成客户端（专门用于代码生成）
        self.coding_client = OllamaClient(
            model_name="deepseek-coder:6.7b",  # 使用专门的代码模型
            base_url="http://localhost:11434",
        )

        # 初始化通用降级客户端
        self.fallback_client = OllamaClient(
            model_name=LLM_FALLBACK_MODEL, base_url="http://localhost:11434"
        )

        self.logger.info(
            f"智能LLM客户端初始化完成 - 推理API可用: {self.reasoning_client is not None}"
        )

    def chat(
        self, messages: List[LLMMessage], task_type: str = "reasoning", **kwargs
    ) -> LLMResponse:
        """智能聊天接口 - 根据任务类型选择合适的模型

        Args:
            messages: 消息列表
            task_type: 任务类型 ('reasoning' 推理任务, 'coding' 代码生成任务, 'general' 通用任务)
            **kwargs: 额外参数
        """

        if task_type == "coding":
            return self._handle_coding_task(messages, **kwargs)
        elif task_type == "reasoning":
            return self._handle_reasoning_task(messages, **kwargs)
        else:
            return self._handle_general_task(messages, **kwargs)

    def _handle_reasoning_task(
        self, messages: List[LLMMessage], **kwargs
    ) -> LLMResponse:
        """处理推理任务 - 优先使用API模型进行复杂推理"""

        # 第一选择：使用推理API客户端
        if self.reasoning_client:
            self.logger.info("使用推理客户端（千问API）处理推理任务")

            for attempt in range(LLM_API_MAX_RETRIES + 1):
                if attempt > 0:
                    self.logger.info(f"推理API重试第 {attempt} 次")

                api_response = self.reasoning_client.chat(messages, **kwargs)

                if api_response.success:
                    self.logger.info("推理API调用成功")
                    api_response.metadata["task_type"] = "reasoning"
                    api_response.metadata["client_used"] = "reasoning_api"
                    return api_response
                else:
                    self.logger.warning(f"推理API调用失败: {api_response.error}")
                    if attempt < LLM_API_MAX_RETRIES:
                        time.sleep(1)

        # 降级到本地模型
        return self._fallback_to_local(messages, "reasoning", **kwargs)

    def _handle_coding_task(self, messages: List[LLMMessage], **kwargs) -> LLMResponse:
        """处理代码生成任务 - 优先使用专门的代码模型"""

        self.logger.info("使用专用代码模型处理代码生成任务")

        # 检查代码模型是否可用
        if not self.coding_client.is_available():
            self.logger.warning("代码生成客户端不可用，降级到通用模型")
            return self._fallback_to_local(messages, "coding", **kwargs)

        # 检查代码模型是否存在
        available_models = self.coding_client.list_models()
        if "deepseek-coder:6.7b" not in available_models:
            self.logger.warning("deepseek-coder:6.7b 模型不存在，降级到通用模型")
            return self._fallback_to_local(messages, "coding", **kwargs)

        # 调用代码生成模型
        coding_response = self.coding_client.chat(messages, **kwargs)

        if coding_response.success:
            self.logger.info("代码生成模型调用成功")
            coding_response.metadata["task_type"] = "coding"
            coding_response.metadata["client_used"] = "coding_local"
            coding_response.metadata["model_used"] = "deepseek-coder:6.7b"
        else:
            self.logger.warning(f"代码生成模型调用失败: {coding_response.error}")
            return self._fallback_to_local(messages, "coding", **kwargs)

        return coding_response

    def _handle_general_task(self, messages: List[LLMMessage], **kwargs) -> LLMResponse:
        """处理通用任务 - 使用原有逻辑"""

        # 第一选择：尝试推理API调用
        if self.reasoning_client:
            self.logger.info("尝试使用推理API处理通用任务")

            for attempt in range(LLM_API_MAX_RETRIES + 1):
                if attempt > 0:
                    self.logger.info(f"通用任务API重试第 {attempt} 次")

                api_response = self.reasoning_client.chat(messages, **kwargs)

                if api_response.success:
                    self.logger.info("通用任务API调用成功")
                    api_response.metadata["task_type"] = "general"
                    api_response.metadata["client_used"] = "reasoning_api"
                    return api_response
                else:
                    self.logger.warning(f"通用任务API调用失败: {api_response.error}")
                    if attempt < LLM_API_MAX_RETRIES:
                        time.sleep(1)

        # 降级到本地模型
        return self._fallback_to_local(messages, "general", **kwargs)

    def _fallback_to_local(
        self, messages: List[LLMMessage], task_type: str, **kwargs
    ) -> LLMResponse:
        """降级到本地模型"""

        self.logger.info(f"降级到本地模型处理{task_type}任务: {LLM_FALLBACK_MODEL}")

        # 检查Ollama是否可用
        if not self.fallback_client.is_available():
            return LLMResponse(
                success=False, error="API调用失败且本地Ollama服务不可用，无法处理任务"
            )

        # 检查模型是否存在
        available_models = self.fallback_client.list_models()
        if LLM_FALLBACK_MODEL not in available_models:
            return LLMResponse(
                success=False,
                error=f"本地模型 {LLM_FALLBACK_MODEL} 不存在，无法处理任务。可用模型: {available_models}",
            )

        # 调用本地模型
        fallback_response = self.fallback_client.chat(messages, **kwargs)

        if fallback_response.success:
            self.logger.info("本地Ollama调用成功")
            # 在元数据中标记这是降级调用
            fallback_response.metadata["fallback_used"] = True
            fallback_response.metadata["fallback_model"] = LLM_FALLBACK_MODEL
            fallback_response.metadata["task_type"] = task_type
            fallback_response.metadata["client_used"] = "fallback_local"
        else:
            self.logger.error(f"本地Ollama调用也失败: {fallback_response.error}")

        return fallback_response

    def complete(self, prompt: str, **kwargs) -> LLMResponse:
        """智能补全接口"""
        messages = [LLMMessage(role="user", content=prompt)]
        return self.chat(messages, **kwargs)


class LLMClientFactory:
    """LLM客户端工厂"""

    @staticmethod
    def create_client(
        client_type: str,
        model_name: str = None,
        api_key: str = None,
        base_url: str = None,
        **kwargs,
    ) -> BaseLLMClient:
        """
        创建LLM客户端

        Args:
            client_type: 客户端类型 (intelligent/ollama/openai/qwen)
            model_name: 模型名称
            api_key: API密钥
            base_url: API基础URL
            **kwargs: 额外参数

        Returns:
            BaseLLMClient: LLM客户端实例
        """
        client_type = client_type.lower()

        if client_type == "intelligent":
            return IntelligentLLMClient(**kwargs)
        elif client_type == "ollama":
            return OllamaClient(
                model_name=model_name or "qwen2.5:7b",
                base_url=base_url or "http://localhost:11434",
            )
        elif client_type == "openai":
            return OpenAIClient(
                model_name=model_name or "gpt-3.5-turbo",
                api_key=api_key,
                base_url=base_url,
            )
        elif client_type == "qwen":
            return QwenAPIClient(model_name=model_name, api_key=api_key)
        else:
            raise ValueError(f"不支持的客户端类型: {client_type}")

    @staticmethod
    def create_default_client() -> BaseLLMClient:
        """创建默认客户端（智能客户端用于复杂任务）"""
        return LLMClientFactory.create_client("intelligent")

    @staticmethod
    def create_complex_task_client() -> BaseLLMClient:
        """创建复杂任务专用客户端（推理优先）"""
        return LLMClientFactory.create_client("intelligent")

    @staticmethod
    def create_reasoning_client() -> BaseLLMClient:
        """创建推理任务专用客户端"""
        return LLMClientFactory.create_client("intelligent")

    @staticmethod
    def create_coding_client() -> BaseLLMClient:
        """创建代码生成专用客户端"""
        return LLMClientFactory.create_client("intelligent")

    @staticmethod
    def create_simple_task_client() -> BaseLLMClient:
        """创建简单任务客户端（仅使用本地模型）"""
        return LLMClientFactory.create_client("ollama")
