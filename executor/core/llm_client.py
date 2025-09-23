"""
LLM客户端 - 统一的大语言模型调用接口
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

    def __init__(self, model_name: str = "qwen2.5:7b", base_url: str = "http://localhost:11434"):
        super().__init__(model_name=model_name, base_url=base_url)
        self.api_url = f"{base_url}/api"

    def chat(self, messages: List[LLMMessage], **kwargs) -> LLMResponse:
        """Ollama聊天接口"""
        if not REQUESTS_AVAILABLE:
            return LLMResponse(
                success=False,
                error="requests模块不可用"
            )

        try:
            # 转换消息格式
            ollama_messages = [
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ]

            # 构建请求数据
            data = {
                "model": self.model_name,
                "messages": ollama_messages,
                "stream": False,
                **kwargs
            }

            # 发送请求
            start_time = time.time()
            response = requests.post(
                f"{self.api_url}/chat",
                json=data,
                timeout=300  # 5分钟超时
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
                        "total_tokens": result.get("prompt_eval_count", 0) + result.get("eval_count", 0)
                    },
                    metadata={
                        "model": self.model_name,
                        "response_time": end_time - start_time,
                        "load_duration": result.get("load_duration", 0),
                        "prompt_eval_duration": result.get("prompt_eval_duration", 0),
                        "eval_duration": result.get("eval_duration", 0)
                    }
                )
            else:
                return LLMResponse(
                    success=False,
                    error=f"Ollama API错误: {response.status_code} - {response.text}"
                )

        except Exception as e:
            self.logger.error(f"Ollama聊天请求失败: {e}")
            return LLMResponse(
                success=False,
                error=f"请求失败: {str(e)}"
            )

    def complete(self, prompt: str, **kwargs) -> LLMResponse:
        """Ollama文本补全接口"""
        if not REQUESTS_AVAILABLE:
            return LLMResponse(
                success=False,
                error="requests模块不可用"
            )

        try:
            data = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                **kwargs
            }

            start_time = time.time()
            response = requests.post(
                f"{self.api_url}/generate",
                json=data,
                timeout=300
            )
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
                        "total_tokens": result.get("prompt_eval_count", 0) + result.get("eval_count", 0)
                    },
                    metadata={
                        "model": self.model_name,
                        "response_time": end_time - start_time,
                        "load_duration": result.get("load_duration", 0),
                        "prompt_eval_duration": result.get("prompt_eval_duration", 0),
                        "eval_duration": result.get("eval_duration", 0)
                    }
                )
            else:
                return LLMResponse(
                    success=False,
                    error=f"Ollama API错误: {response.status_code} - {response.text}"
                )

        except Exception as e:
            self.logger.error(f"Ollama补全请求失败: {e}")
            return LLMResponse(
                success=False,
                error=f"请求失败: {str(e)}"
            )

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

    def __init__(self, model_name: str = "gpt-3.5-turbo", api_key: str = None, base_url: str = None):
        super().__init__(model_name=model_name, api_key=api_key, base_url=base_url)
        self.api_url = base_url or "https://api.openai.com/v1"

    def chat(self, messages: List[LLMMessage], **kwargs) -> LLMResponse:
        """OpenAI聊天接口"""
        if not REQUESTS_AVAILABLE:
            return LLMResponse(
                success=False,
                error="requests模块不可用"
            )

        if not self.api_key:
            return LLMResponse(
                success=False,
                error="缺少OpenAI API密钥"
            )

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            openai_messages = [
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ]

            data = {
                "model": self.model_name,
                "messages": openai_messages,
                **kwargs
            }

            start_time = time.time()
            response = requests.post(
                f"{self.api_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=300
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
                        "response_time": end_time - start_time
                    }
                )
            else:
                return LLMResponse(
                    success=False,
                    error=f"OpenAI API错误: {response.status_code} - {response.text}"
                )

        except Exception as e:
            self.logger.error(f"OpenAI聊天请求失败: {e}")
            return LLMResponse(
                success=False,
                error=f"请求失败: {str(e)}"
            )

    def complete(self, prompt: str, **kwargs) -> LLMResponse:
        """OpenAI文本补全接口"""
        # 将补全转换为聊天格式
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
        **kwargs
    ) -> BaseLLMClient:
        """
        创建LLM客户端

        Args:
            client_type: 客户端类型 (ollama/openai)
            model_name: 模型名称
            api_key: API密钥
            base_url: API基础URL
            **kwargs: 额外参数

        Returns:
            BaseLLMClient: LLM客户端实例
        """
        if client_type.lower() == "ollama":
            return OllamaClient(
                model_name=model_name or "qwen2.5:7b",
                base_url=base_url or "http://localhost:11434"
            )
        elif client_type.lower() == "openai":
            return OpenAIClient(
                model_name=model_name or "gpt-3.5-turbo",
                api_key=api_key,
                base_url=base_url
            )
        else:
            raise ValueError(f"不支持的客户端类型: {client_type}")

    @staticmethod
    def create_default_client() -> BaseLLMClient:
        """创建默认客户端（Ollama）"""
        return LLMClientFactory.create_client("ollama")