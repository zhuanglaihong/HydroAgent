"""
Author: Claude & zhuanglaihong
Date: 2025-11-20 19:55:00
LastEditTime: 2025-12-05 21:00:00
LastEditors: Claude
Description: Unified LLM API interface supporting OpenAI, Claude, and local models (Ollama)
             LLM API 统一接口 - 支持 OpenAI、Claude 和本地模型 (Ollama)
             + Token consumption tracking (v2.0)
             + Better timeout handling (v2.0)
FilePath: /HydroAgent/hydroagent/core/llm_interface.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
import logging
import os
import time

logger = logging.getLogger(__name__)


class LLMTimeoutError(Exception):
    """Custom exception for LLM API timeout."""
    pass


class LLMConnectionError(Exception):
    """Custom exception for LLM API connection errors."""
    pass


class TokenUsageTracker:
    """
    Token usage tracker for LLM API calls.
    跟踪 LLM API 调用的 token 消耗。
    """

    def __init__(self):
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self.call_count = 0
        self.call_history = []

    def record_usage(self, prompt_tokens: int, completion_tokens: int, model: str = "unknown"):
        """Record token usage from an API call."""
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_tokens += (prompt_tokens + completion_tokens)
        self.call_count += 1

        self.call_history.append({
            "timestamp": time.time(),
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total": prompt_tokens + completion_tokens
        })

        logger.debug(
            f"[TokenTracker] Call #{self.call_count}: "
            f"{prompt_tokens} prompt + {completion_tokens} completion = {prompt_tokens + completion_tokens} total tokens"
        )

    def get_summary(self) -> Dict[str, Any]:
        """Get token usage summary."""
        return {
            "total_calls": self.call_count,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "average_tokens_per_call": self.total_tokens / self.call_count if self.call_count > 0 else 0,
        }

    def reset(self):
        """Reset token usage statistics."""
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self.call_count = 0
        self.call_history = []

    def __repr__(self):
        summary = self.get_summary()
        return (
            f"TokenUsageTracker(calls={summary['total_calls']}, "
            f"total_tokens={summary['total_tokens']}, "
            f"prompt={summary['total_prompt_tokens']}, "
            f"completion={summary['total_completion_tokens']})"
        )


class LLMInterface(ABC):
    """
    Abstract interface for Large Language Model APIs.
    大语言模型 API 的抽象接口。

    Supports multiple backends:
    - OpenAI (GPT-3.5, GPT-4)
    - Claude (Claude 3 series)
    - Ollama (Local models: Qwen, Llama, etc.)

    v2.0 Features:
    - Token usage tracking
    - Better timeout handling
    """

    def __init__(self, model_name: str, api_key: Optional[str] = None, **kwargs):
        """
        Initialize LLM interface.

        Args:
            model_name: Model identifier (e.g., 'gpt-4', 'claude-3-opus', 'qwen2:7b')
            api_key: API key for cloud services (not needed for Ollama)
            **kwargs: Additional configuration parameters
        """
        self.model_name = model_name
        self.api_key = api_key
        self.config = kwargs
        self.token_tracker = TokenUsageTracker()  # 🆕 Token tracking
        logger.info(f"Initialized LLM interface: {model_name}")

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        Generate text completion from the LLM.
        从 LLM 生成文本补全。

        Args:
            system_prompt: System-level instruction
            user_prompt: User query or task description
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional generation parameters

        Returns:
            Generated text response
        """
        pass

    @abstractmethod
    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate structured JSON output.
        生成结构化的 JSON 输出。

        Args:
            system_prompt: System instruction
            user_prompt: User query
            temperature: Sampling temperature
            **kwargs: Additional parameters

        Returns:
            Parsed JSON dictionary
        """
        pass

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the current model.

        Returns:
            Dictionary containing model metadata
        """
        return {
            "model_name": self.model_name,
            "backend": self.__class__.__name__,
            "config": self.config,
            "token_usage": self.token_tracker.get_summary()  # 🆕 Include token stats
        }

    def get_token_usage(self) -> Dict[str, Any]:
        """
        Get token usage statistics.

        Returns:
            Dictionary with token usage summary
        """
        return self.token_tracker.get_summary()

    def reset_token_usage(self):
        """Reset token usage statistics."""
        self.token_tracker.reset()
        logger.info(f"[{self.model_name}] Token usage statistics reset")


class OpenAIInterface(LLMInterface):
    """OpenAI API interface implementation."""

    def __init__(self, model_name: str , api_key: Optional[str] = None, **kwargs):
        super().__init__(model_name, api_key, **kwargs)

        # Try to get API key from: 1) parameter, 2) env var, 3) config file
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            try:
                from configs import definitions_private
                self.api_key = getattr(definitions_private, "OPENAI_API_KEY", None)
            except ImportError:
                try:
                    from configs import definitions
                    self.api_key = getattr(definitions, "OPENAI_API_KEY", None)
                except ImportError:
                    pass

        # Try to get base_url from: 1) kwargs, 2) env var, 3) config file
        self.base_url = kwargs.get("base_url", None)
        if not self.base_url:
            self.base_url = os.getenv("OPENAI_BASE_URL")
        if not self.base_url:
            try:
                from configs import definitions_private
                self.base_url = getattr(definitions_private, "OPENAI_BASE_URL", None)
            except ImportError:
                try:
                    from configs import definitions
                    self.base_url = getattr(definitions, "OPENAI_BASE_URL", None)
                except ImportError:
                    pass

        if not self.api_key:
            raise ValueError(
                "OpenAI API key not provided. Please set it in:\n"
                "1. configs/definitions_private.py (OPENAI_API_KEY)\n"
                "2. Environment variable (OPENAI_API_KEY)\n"
                "3. Or pass as parameter"
            )

        # Lazy import to avoid dependency if not used
        try:
            from openai import OpenAI
            # Support custom base_url (e.g., for Qwen, Azure OpenAI)
            if self.base_url:
                self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
                logger.info(f"OpenAI client initialized with custom base_url: {self.base_url}")
            else:
                self.client = OpenAI(api_key=self.api_key)
                logger.info("OpenAI client initialized with default base_url")
        except ImportError:
            raise ImportError("openai package not installed. Run: pip install openai")

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """Generate text using OpenAI API with timeout handling and token tracking."""
        try:
            # Set default timeout if not provided
            timeout = kwargs.pop("timeout", 60)  # Default 60 seconds

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                **kwargs
            )

            # 🆕 Track token usage
            if hasattr(response, 'usage') and response.usage:
                self.token_tracker.record_usage(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    model=self.model_name
                )

            return response.choices[0].message.content

        except Exception as e:
            error_str = str(e).lower()

            # Handle specific error types with user-friendly messages
            if "timeout" in error_str or "timed out" in error_str:
                error_msg = (
                    f"⚠️ API Request Timeout\n\n"
                    f"The request to {self.model_name} timed out after {timeout} seconds.\n\n"
                    f"Please check:\n"
                    f"1. Your internet connection\n"
                    f"2. API service status (https://status.openai.com/ or your provider)\n"
                    f"3. Consider increasing the timeout parameter\n\n"
                    f"Original error: {str(e)}"
                )
                logger.error(error_msg)
                raise LLMTimeoutError(error_msg) from e

            elif "connection" in error_str or "network" in error_str:
                error_msg = (
                    f"⚠️ API Connection Error\n\n"
                    f"Failed to connect to {self.base_url or 'OpenAI API'}.\n\n"
                    f"Please check:\n"
                    f"1. Your internet connection\n"
                    f"2. Firewall settings\n"
                    f"3. API base URL: {self.base_url or '(default)'}\n"
                    f"4. API key validity\n\n"
                    f"Original error: {str(e)}"
                )
                logger.error(error_msg)
                raise LLMConnectionError(error_msg) from e

            elif "api" in error_str and "key" in error_str:
                error_msg = (
                    f"⚠️ API Key Error\n\n"
                    f"Invalid or missing API key.\n\n"
                    f"Please check:\n"
                    f"1. API key is correctly set in configs/definitions_private.py\n"
                    f"2. API key is valid and not expired\n"
                    f"3. API key has sufficient quota\n\n"
                    f"Original error: {str(e)}"
                )
                logger.error(error_msg)
                raise ValueError(error_msg) from e

            else:
                logger.error(f"OpenAI API call failed: {str(e)}")
                raise

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate JSON output using OpenAI API."""
        import json
        import re

        response = self.generate(
            system_prompt=system_prompt + "\n\nRespond with valid JSON only.",
            user_prompt=user_prompt,
            temperature=temperature,
            **kwargs
        )

        # Extract JSON from markdown code blocks if present
        json_str = response
        json_match = re.search(r'```json\s*\n(.*?)\n```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            logger.debug("Extracted JSON from markdown code block")
        else:
            # Try to find JSON directly
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                logger.debug("Extracted JSON from response body")

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {str(e)}")
            logger.error(f"Response length: {len(response) if response else 0} characters")
            logger.error(f"Response preview (first 500 chars): {response[:500] if response else '(empty)'}")
            logger.error(f"Response preview (last 200 chars): {response[-200:] if response and len(response) > 200 else '(n/a)'}")
            raise


class ClaudeInterface(LLMInterface):
    """Anthropic Claude API interface implementation."""

    def __init__(self, model_name: str = "claude-3-opus-20240229", api_key: Optional[str] = None, **kwargs):
        super().__init__(model_name, api_key, **kwargs)
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")

        if not self.api_key:
            raise ValueError("Claude API key not provided")

        try:
            from anthropic import Anthropic
            self.client = Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 4096,
        **kwargs
    ) -> str:
        """Generate text using Claude API."""
        try:
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ],
                **kwargs
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Claude API call failed: {str(e)}")
            raise

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate JSON output using Claude API."""
        import json
        import re

        response = self.generate(
            system_prompt=system_prompt + "\n\nRespond with valid JSON only.",
            user_prompt=user_prompt,
            temperature=temperature,
            **kwargs
        )

        # Extract JSON from markdown code blocks if present
        json_str = response
        json_match = re.search(r'```json\s*\n(.*?)\n```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            logger.debug("Extracted JSON from markdown code block")
        else:
            # Try to find JSON directly
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                logger.debug("Extracted JSON from response body")

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {str(e)}")
            logger.error(f"Response length: {len(response) if response else 0} characters")
            logger.error(f"Response preview (first 500 chars): {response[:500] if response else '(empty)'}")
            raise


class OllamaInterface(LLMInterface):
    """Ollama local model interface implementation."""

    def __init__(self, model_name: str = "qwen3:8b", base_url: str = "http://localhost:11434", **kwargs):
        super().__init__(model_name, api_key=None, **kwargs)
        self.base_url = base_url

        try:
            import requests
            self.requests = requests
        except ImportError:
            raise ImportError("requests package not installed. Run: pip install requests")

        # Verify Ollama is running
        try:
            response = self.requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code != 200:
                logger.warning(f"Ollama server returned status {response.status_code}")
        except Exception as e:
            logger.warning(f"Failed to connect to Ollama: {str(e)}")

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """Generate text using Ollama API with retry logic, timeout handling, and token tracking."""
        import time

        # Retry configuration
        max_retries = kwargs.get('max_retries', 2)
        timeout = kwargs.get('timeout', 60)  # Increased to 60 seconds for better stability

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                # Combine system and user prompts for Ollama
                combined_prompt = f"{system_prompt}\n\n{user_prompt}"

                payload = {
                    "model": self.model_name,
                    "prompt": combined_prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                    }
                }

                if max_tokens:
                    payload["options"]["num_predict"] = max_tokens

                if attempt > 0:
                    logger.info(f"Retry attempt {attempt}/{max_retries} for Ollama API call")

                response = self.requests.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=timeout
                )
                response.raise_for_status()

                result = response.json()

                # 🆕 Track token usage (Ollama provides approximate token counts)
                if "prompt_eval_count" in result and "eval_count" in result:
                    self.token_tracker.record_usage(
                        prompt_tokens=result.get("prompt_eval_count", 0),
                        completion_tokens=result.get("eval_count", 0),
                        model=self.model_name
                    )
                else:
                    # Fallback: Estimate tokens (rough approximation)
                    prompt_est = len(combined_prompt) // 4
                    response_est = len(result["response"]) // 4
                    self.token_tracker.record_usage(
                        prompt_tokens=prompt_est,
                        completion_tokens=response_est,
                        model=self.model_name
                    )

                return result["response"]

            except self.requests.exceptions.Timeout as e:
                error_msg = (
                    f"⚠️ Ollama Request Timeout\n\n"
                    f"The request to {self.model_name} @ {self.base_url} timed out after {timeout} seconds.\n\n"
                    f"Please check:\n"
                    f"1. Ollama service is running (run: ollama list)\n"
                    f"2. Model {self.model_name} is downloaded (run: ollama pull {self.model_name})\n"
                    f"3. Consider increasing the timeout parameter\n"
                    f"4. Check if your system has enough resources (RAM/GPU)\n\n"
                    f"Original error: {str(e)}"
                )
                logger.error(error_msg)
                raise LLMTimeoutError(error_msg) from e

            except self.requests.exceptions.ConnectionError as e:
                error_msg = (
                    f"⚠️ Ollama Connection Error\n\n"
                    f"Failed to connect to Ollama at {self.base_url}.\n\n"
                    f"Please check:\n"
                    f"1. Ollama is running (run: ollama serve)\n"
                    f"2. Base URL is correct: {self.base_url}\n"
                    f"3. Firewall settings allow connection\n\n"
                    f"Original error: {str(e)}"
                )
                logger.error(error_msg)
                raise LLMConnectionError(error_msg) from e

            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                logger.warning(f"Ollama API call attempt {attempt + 1} failed: {str(e)}")

                if attempt < max_retries:
                    # Wait before retry (exponential backoff)
                    wait_time = 2 ** attempt
                    logger.info(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    # Final failure - provide detailed error message
                    if "model" in error_str and "not found" in error_str:
                        error_msg = (
                            f"⚠️ Ollama Model Not Found\n\n"
                            f"Model '{self.model_name}' is not available.\n\n"
                            f"Please run: ollama pull {self.model_name}\n\n"
                            f"Original error: {str(last_error)}"
                        )
                        logger.error(error_msg)
                        raise ValueError(error_msg) from last_error
                    else:
                        logger.error(f"Ollama API call failed after {max_retries + 1} attempts")
                        raise last_error

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate JSON output using Ollama API."""
        import json
        import re

        response = self.generate(
            system_prompt=system_prompt + "\n\nRespond with valid JSON only.",
            user_prompt=user_prompt,
            temperature=temperature,
            **kwargs
        )

        # Extract JSON from markdown code blocks if present
        json_str = response
        json_match = re.search(r'```json\s*\n(.*?)\n```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            logger.debug("Extracted JSON from markdown code block")
        else:
            # Try to find JSON directly
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                logger.debug("Extracted JSON from response body")

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {str(e)}")
            logger.error(f"Response length: {len(response) if response else 0} characters")
            logger.error(f"Response preview (first 500 chars): {response[:500] if response else '(empty)'}")
            raise


def create_llm_interface(
    backend: str = "openai",
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs
) -> LLMInterface:
    """
    Factory function to create appropriate LLM interface.
    工厂函数，用于创建合适的 LLM 接口。

    Args:
        backend: LLM backend ('openai', 'claude', 'ollama')
        model_name: Specific model to use
        api_key: API key (for cloud services)
        **kwargs: Additional configuration

    Returns:
        LLMInterface instance

    Examples:
        >>> llm = create_llm_interface('openai', 'gpt-4')
        >>> llm = create_llm_interface('ollama', 'qwen2:7b')
        >>> llm = create_llm_interface('claude', 'claude-3-opus-20240229')
    """
    backend = backend.lower()

    if backend == "openai":
        model_name = model_name or "gpt-4"
        return OpenAIInterface(model_name, api_key, **kwargs)

    elif backend == "claude":
        model_name = model_name or "claude-3-opus-20240229"
        return ClaudeInterface(model_name, api_key, **kwargs)

    elif backend == "ollama":
        model_name = model_name or "qwen2:7b"
        return OllamaInterface(model_name, **kwargs)

    else:
        raise ValueError(f"Unsupported backend: {backend}. Choose from: openai, claude, ollama")
