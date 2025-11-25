"""
Author: Claude & zhuanglaihong
Date: 2025-01-20 19:55:00
LastEditTime: 2025-11-21 19:45:00
LastEditors: Claude
Description: Unified LLM API interface supporting OpenAI, Claude, and local models (Ollama)
             LLM API 统一接口 - 支持 OpenAI、Claude 和本地模型 (Ollama)
FilePath: /HydroAgent/hydroagent/core/llm_interface.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
import logging
import os

logger = logging.getLogger(__name__)


class LLMInterface(ABC):
    """
    Abstract interface for Large Language Model APIs.
    大语言模型 API 的抽象接口。

    Supports multiple backends:
    - OpenAI (GPT-3.5, GPT-4)
    - Claude (Claude 3 series)
    - Ollama (Local models: Qwen, Llama, etc.)
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
            "config": self.config
        }


class OpenAIInterface(LLMInterface):
    """OpenAI API interface implementation."""

    def __init__(self, model_name: str = "gpt-4", api_key: Optional[str] = None, **kwargs):
        super().__init__(model_name, api_key, **kwargs)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = kwargs.get("base_url", None)  # Support custom base_url

        if not self.api_key:
            raise ValueError("OpenAI API key not provided")

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
        """Generate text using OpenAI API."""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
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

    def __init__(self, model_name: str = "qwen2:7b", base_url: str = "http://localhost:11434", **kwargs):
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
        """Generate text using Ollama API with retry logic."""
        import time

        # Retry configuration
        max_retries = kwargs.get('max_retries', 2)
        timeout = kwargs.get('timeout', 30)  # Reduced from 120 to 30 seconds

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

                return response.json()["response"]

            except Exception as e:
                last_error = e
                logger.warning(f"Ollama API call attempt {attempt + 1} failed: {str(e)}")

                if attempt < max_retries:
                    # Wait before retry (exponential backoff)
                    wait_time = 2 ** attempt
                    logger.info(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
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
    backend: str = "ollama",
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
