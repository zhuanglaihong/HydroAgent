"""
Author: zhuanglaihong
Date: 2024-09-24 16:45:00
LastEditTime: 2024-09-24 16:45:00
LastEditors: zhuanglaihong
Description: LLM client with API priority and local fallback
FilePath: \HydroAgent\builder\llm_client.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import logging
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

try:
    from .api_client import get_api_response

    API_CLIENT_AVAILABLE = True
except (ImportError, Exception) as e:
    API_CLIENT_AVAILABLE = False
    get_api_response = None

try:
    import ollama

    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

from config import (
    LLM_USE_API_FIRST,
    LLM_API_MODEL_NAME,
    LLM_API_TIMEOUT,
    LLM_FALLBACK_MODEL,
    LLM_FALLBACK_TIMEOUT,
    LLM_TEMPERATURE,
)
import signal
import threading

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """LLM响应结果"""

    content: str
    model_used: str
    response_time: float
    success: bool
    error_message: str = ""
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class LLMClient:
    """
    LLM客户端，支持API优先调用和本地Ollama降级
    """

    def __init__(self, use_api_first: bool = True, force_local: bool = False):
        """
        初始化LLM客户端

        Args:
            use_api_first: 是否优先使用API
            force_local: 是否强制使用本地模式（忽略API）
        """
        self.force_local = force_local
        self.use_api_first = (use_api_first and LLM_USE_API_FIRST) and not force_local
        self.api_available = API_CLIENT_AVAILABLE
        self.ollama_available = OLLAMA_AVAILABLE

        # 初始化统计信息
        self.stats = {
            "api_calls": 0,
            "api_successes": 0,
            "ollama_calls": 0,
            "ollama_successes": 0,
            "total_response_time": 0.0,
            "avg_response_time": 0.0,
        }

        # 初始化Ollama客户端
        self.ollama_client = None
        if self.ollama_available:
            try:
                self.ollama_client = ollama.Client()
                # 检查模型是否可用
                try:
                    models = self.ollama_client.list()
                    available_models = []
                    if models and "models" in models:
                        for model in models["models"]:
                            # 兼容不同的键名格式
                            model_name = (
                                model.get("name")
                                or model.get("model")
                                or model.get("id", "")
                            )
                            if model_name:
                                available_models.append(model_name)

                    if available_models:
                        logger.info(f"可用的Ollama模型: {available_models}")
                        if LLM_FALLBACK_MODEL not in available_models:
                            logger.warning(
                                f"Ollama模型 {LLM_FALLBACK_MODEL} 不可用，可用模型: {available_models}"
                            )
                            # 不直接设为不可用，让后续调用时再处理
                    else:
                        logger.warning("未找到任何可用的Ollama模型")
                except Exception as e:
                    logger.warning(f"无法连接到Ollama服务: {e}")
                    self.ollama_available = False
            except Exception as e:
                logger.warning(f"Ollama客户端初始化失败: {e}")
                self.ollama_available = False

        logger.info(
            f"LLM客户端初始化完成 - API可用: {self.api_available}, Ollama可用: {self.ollama_available}"
        )

    def generate(
        self,
        prompt: str,
        model: str = None,
        temperature: float = None,
        max_tokens: int = 4000,
    ) -> LLMResponse:
        """
        生成文本响应

        Args:
            prompt: 输入提示词
            model: 指定模型（可选）
            temperature: 温度参数（可选）
            max_tokens: 最大token数

        Returns:
            LLMResponse: 响应结果
        """
        start_time = time.time()

        if temperature is None:
            temperature = LLM_TEMPERATURE

        # 决定使用哪个客户端
        if self.use_api_first and self.api_available:
            # 首先尝试API
            response = self._call_api(
                prompt, model or LLM_API_MODEL_NAME, temperature, max_tokens
            )
            if response.success:
                self._update_stats("api", True, response.response_time)
                return response
            else:
                logger.warning(
                    f"API调用失败，尝试降级到Ollama: {response.error_message}"
                )

        # 降级到Ollama
        if self.ollama_available:
            response = self._call_ollama(
                prompt, model or LLM_FALLBACK_MODEL, temperature, max_tokens
            )
            self._update_stats("ollama", response.success, response.response_time)
            return response

        # 如果都不可用，返回错误
        response_time = time.time() - start_time
        return LLMResponse(
            content="",
            model_used="none",
            response_time=response_time,
            success=False,
            error_message="没有可用的LLM客户端",
        )

    def _call_api(
        self, prompt: str, model: str, temperature: float, max_tokens: int
    ) -> LLMResponse:
        """调用API客户端（带30秒超时）"""
        start_time = time.time()
        self.stats["api_calls"] += 1

        try:
            # 检查API函数是否可用
            if get_api_response is None:
                raise Exception("API客户端函数不可用")

            # 使用线程和超时机制调用API
            response_container = [None]
            exception_container = [None]

            def api_call():
                try:
                    content = get_api_response(
                        prompt, model=model, temperature=temperature
                    )
                    response_container[0] = content
                except Exception as e:
                    exception_container[0] = e

            # 启动调用线程
            thread = threading.Thread(target=api_call)
            thread.daemon = True
            thread.start()

            # 等待完成或超时
            thread.join(timeout=LLM_API_TIMEOUT)

            if thread.is_alive():
                # 超时了
                response_time = time.time() - start_time
                logger.warning(f"API调用超时({LLM_API_TIMEOUT}秒) - 模型: {model}")
                return LLMResponse(
                    content="",
                    model_used=f"api_{model}",
                    response_time=response_time,
                    success=False,
                    error_message=f"API调用超时({LLM_API_TIMEOUT}秒)",
                )

            # 检查是否有异常
            if exception_container[0]:
                raise exception_container[0]

            # 获取响应
            content = response_container[0]
            response_time = time.time() - start_time

            if content:
                logger.info(
                    f"API调用成功 - 模型: {model}, 响应时间: {response_time:.2f}s"
                )
                return LLMResponse(
                    content=content,
                    model_used=f"api_{model}",
                    response_time=response_time,
                    success=True,
                    metadata={
                        "api_model": model,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                )
            else:
                return LLMResponse(
                    content="",
                    model_used=f"api_{model}",
                    response_time=response_time,
                    success=False,
                    error_message="API返回空响应",
                )

        except Exception as e:
            response_time = time.time() - start_time
            logger.error(f"API调用异常: {str(e)}")
            return LLMResponse(
                content="",
                model_used=f"api_{model}",
                response_time=response_time,
                success=False,
                error_message=f"API调用异常: {str(e)}",
            )

    def _call_ollama(
        self, prompt: str, model: str, temperature: float, max_tokens: int
    ) -> LLMResponse:
        """调用Ollama客户端（带60秒超时）"""
        start_time = time.time()
        self.stats["ollama_calls"] += 1

        # 增加详细日志
        logger.info(
            f"开始Ollama调用 - 模型: {model}, 温度: {temperature}, 最大tokens: {max_tokens}"
        )
        logger.info(f"提示词长度: {len(prompt)} 字符")
        logger.info(f"当前超时设置: {LLM_FALLBACK_TIMEOUT}秒")

        try:
            # 使用线程和超时机制调用Ollama
            response_container = [None]
            exception_container = [None]

            def ollama_call():
                try:
                    logger.info(f"Ollama线程开始执行 - 模型: {model}")
                    response = self.ollama_client.generate(
                        model=model,
                        prompt=prompt,
                        options={"temperature": temperature, "num_predict": max_tokens},
                    )
                    logger.info(f"Ollama生成完成 - 响应大小: {len(str(response))} 字符")
                    response_container[0] = response
                except Exception as e:
                    logger.error(f"Ollama线程异常: {str(e)}")
                    exception_container[0] = e

            # 启动调用线程
            thread = threading.Thread(target=ollama_call)
            thread.daemon = True
            thread.start()
            logger.info("Ollama调用线程已启动")

            # 等待完成或超时
            thread.join(timeout=LLM_FALLBACK_TIMEOUT)

            if thread.is_alive():
                # 超时了
                response_time = time.time() - start_time
                logger.warning(
                    f"Ollama调用超时({LLM_FALLBACK_TIMEOUT}秒) - 模型: {model}"
                )
                logger.warning(f"提示词长度: {len(prompt)} 字符可能过长导致超时")
                logger.warning(
                    f"建议: 1) 减少提示词长度 2) 增加超时设置 3) 检查模型性能"
                )
                return LLMResponse(
                    content="",
                    model_used=f"ollama_{model}",
                    response_time=response_time,
                    success=False,
                    error_message=f"Ollama调用超时({LLM_FALLBACK_TIMEOUT}秒)",
                )

            # 检查是否有异常
            if exception_container[0]:
                raise exception_container[0]

            # 获取响应
            response = response_container[0]
            response_time = time.time() - start_time

            content = response.get("response", "")
            if content:
                logger.info(
                    f"Ollama调用成功 - 模型: {model}, 响应时间: {response_time:.2f}s"
                )
                return LLMResponse(
                    content=content,
                    model_used=f"ollama_{model}",
                    response_time=response_time,
                    success=True,
                    metadata={
                        "ollama_model": model,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                )
            else:
                return LLMResponse(
                    content="",
                    model_used=f"ollama_{model}",
                    response_time=response_time,
                    success=False,
                    error_message="Ollama返回空响应",
                )

        except Exception as e:
            response_time = time.time() - start_time
            logger.error(f"Ollama调用异常: {str(e)}")
            return LLMResponse(
                content="",
                model_used=f"ollama_{model}",
                response_time=response_time,
                success=False,
                error_message=f"Ollama调用异常: {str(e)}",
            )

    def _update_stats(self, client_type: str, success: bool, response_time: float):
        """更新统计信息"""
        if success:
            self.stats[f"{client_type}_successes"] += 1

        self.stats["total_response_time"] += response_time
        total_calls = self.stats["api_calls"] + self.stats["ollama_calls"]
        if total_calls > 0:
            self.stats["avg_response_time"] = (
                self.stats["total_response_time"] / total_calls
            )

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_calls = self.stats["api_calls"] + self.stats["ollama_calls"]
        total_successes = self.stats["api_successes"] + self.stats["ollama_successes"]

        return {
            **self.stats,
            "total_calls": total_calls,
            "total_successes": total_successes,
            "success_rate": total_successes / total_calls if total_calls > 0 else 0.0,
            "api_success_rate": (
                self.stats["api_successes"] / self.stats["api_calls"]
                if self.stats["api_calls"] > 0
                else 0.0
            ),
            "ollama_success_rate": (
                self.stats["ollama_successes"] / self.stats["ollama_calls"]
                if self.stats["ollama_calls"] > 0
                else 0.0
            ),
            "api_available": self.api_available,
            "ollama_available": self.ollama_available,
            "timeout_settings": {
                "api_timeout": LLM_API_TIMEOUT,
                "ollama_timeout": LLM_FALLBACK_TIMEOUT,
            },
        }

    def test_timeout_mechanism(self) -> Dict[str, Any]:
        """
        测试超时机制是否工作
        """
        results = {
            "api_timeout": LLM_API_TIMEOUT,
            "ollama_timeout": LLM_FALLBACK_TIMEOUT,
            "tests": {},
        }

        # 测试API超时（如果可用）
        if self.api_available:
            logger.info(f"测试API超时机制（{LLM_API_TIMEOUT}秒）")
            start = time.time()
            try:
                # 使用一个可能较慢的提示来测试
                response = self.generate(
                    "请详细描述水文建模的完整流程，包括所有步骤和细节，至少2000字",
                    temperature=0.1,
                    max_tokens=3000,
                )
                test_time = time.time() - start
                results["tests"]["api"] = {
                    "completed": response.success,
                    "response_time": test_time,
                    "within_timeout": test_time <= LLM_API_TIMEOUT + 5,  # 允许5秒误差
                    "error": response.error_message if not response.success else None,
                }
            except Exception as e:
                results["tests"]["api"] = {
                    "completed": False,
                    "error": str(e),
                    "response_time": time.time() - start,
                }

        return results

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        temperature: float = None,
    ) -> LLMResponse:
        """
        对话式生成（兼容性方法）

        Args:
            messages: 对话消息列表
            model: 模型名称
            temperature: 温度参数

        Returns:
            LLMResponse: 响应结果
        """
        # 将messages转换为单个prompt
        prompt_parts = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            if role == "system":
                prompt_parts.append(f"系统: {content}")
            elif role == "user":
                prompt_parts.append(f"用户: {content}")
            elif role == "assistant":
                prompt_parts.append(f"助手: {content}")

        prompt = "\n".join(prompt_parts)
        return self.generate(prompt, model=model, temperature=temperature)

    def is_available(self) -> bool:
        """检查是否有可用的LLM客户端"""
        return self.api_available or self.ollama_available

    def test_connection(self) -> Dict[str, bool]:
        """测试连接状态"""
        results = {"api": False, "ollama": False}

        # 测试API连接
        if self.api_available:
            try:
                response = self._call_api("测试", LLM_API_MODEL_NAME, 0.1, 50)
                results["api"] = response.success
            except Exception:
                results["api"] = False

        # 测试Ollama连接
        if self.ollama_available:
            try:
                response = self._call_ollama("测试", LLM_FALLBACK_MODEL, 0.1, 50)
                results["ollama"] = response.success
            except Exception:
                results["ollama"] = False

        return results


# 全局实例
_llm_client = None


def get_llm_client(use_api_first: bool = True, force_local: bool = False) -> LLMClient:
    """
    获取全局LLM客户端实例

    Args:
        use_api_first: 是否优先使用API
        force_local: 是否强制使用本地模式
    """
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient(use_api_first=use_api_first, force_local=force_local)
    return _llm_client
