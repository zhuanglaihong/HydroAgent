"""
Author: HydroClaw Team
Date: 2026-02-08
Description: LLM client with function calling support and prompt-based fallback.
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """A single tool call from the LLM."""
    name: str
    arguments: dict[str, Any]
    id: str = ""


@dataclass
class LLMResponse:
    """Parsed LLM response."""
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)

    def is_text(self) -> bool:
        return len(self.tool_calls) == 0 and self.text is not None

    def is_tool_call(self) -> bool:
        return len(self.tool_calls) > 0


class TokenTracker:
    """Track token usage across API calls."""

    def __init__(self):
        self.total_prompt = 0
        self.total_completion = 0
        self.call_count = 0

    def record(self, prompt: int, completion: int):
        self.total_prompt += prompt
        self.total_completion += completion
        self.call_count += 1

    @property
    def total(self) -> int:
        return self.total_prompt + self.total_completion

    def summary(self) -> dict:
        return {
            "calls": self.call_count,
            "prompt_tokens": self.total_prompt,
            "completion_tokens": self.total_completion,
            "total_tokens": self.total,
        }


class LLMClient:
    """Unified LLM client supporting function calling and prompt-based fallback.

    Mode A: Native function calling (OpenAI, Qwen with tools support)
    Mode B: Prompt-based fallback (Ollama, models without tools support)
    """

    def __init__(self, config: dict):
        self.model = config.get("model", "deepseek-v3.1")
        self.base_url = config.get("base_url")
        self.api_key = config.get("api_key")
        self.temperature = config.get("temperature", 0.1)
        self.max_tokens = config.get("max_tokens", 20000)
        self.timeout = config.get("timeout", 60)
        self.tokens = TokenTracker()

        # Auto-detect or use config
        self._supports_fc = config.get("supports_function_calling")
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI
            kwargs = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = OpenAI(**kwargs)
            logger.info(f"LLM client initialized: model={self.model}, base_url={self.base_url}")
        return self._client

    @property
    def supports_function_calling(self) -> bool:
        if self._supports_fc is None:
            # Auto-detect: try function calling, fallback if it fails
            self._supports_fc = self._detect_function_calling()
        return self._supports_fc

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        """Send messages to LLM and get response.

        Args:
            messages: Chat messages in OpenAI format.
            tools: Tool schemas in OpenAI function calling format.
            temperature: Override default temperature.

        Returns:
            LLMResponse with either text or tool_calls.
        """
        temp = temperature if temperature is not None else self.temperature

        if tools and self.supports_function_calling:
            return self._chat_with_tools(messages, tools, temp)
        elif tools:
            return self._chat_with_prompt_tools(messages, tools, temp)
        else:
            return self._chat_text(messages, temp)

    def _chat_text(self, messages: list[dict], temperature: float) -> LLMResponse:
        """Simple text chat without tools."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=self.max_tokens,
            timeout=self.timeout,
        )
        self._track_tokens(response)
        text = response.choices[0].message.content or ""
        return LLMResponse(text=text)

    def _chat_with_tools(
        self, messages: list[dict], tools: list[dict], temperature: float
    ) -> LLMResponse:
        """Chat using native function calling."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                temperature=temperature,
                max_tokens=self.max_tokens,
                timeout=self.timeout,
            )
            self._track_tokens(response)

            msg = response.choices[0].message

            # Check for tool calls
            if msg.tool_calls:
                calls = []
                for tc in msg.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}
                    calls.append(ToolCall(
                        name=tc.function.name,
                        arguments=args,
                        id=tc.id or "",
                    ))
                return LLMResponse(text=msg.content, tool_calls=calls)

            return LLMResponse(text=msg.content or "")

        except Exception as e:
            error_msg = str(e).lower()
            # If function calling not supported, fall back
            if "tool" in error_msg or "function" in error_msg or "unsupported" in error_msg:
                logger.warning(f"Function calling failed, falling back to prompt mode: {e}")
                self._supports_fc = False
                return self._chat_with_prompt_tools(messages, tools, temperature)
            raise

    def _chat_with_prompt_tools(
        self, messages: list[dict], tools: list[dict], temperature: float
    ) -> LLMResponse:
        """Fallback: inject tool descriptions into prompt, parse JSON response."""
        tool_desc = self._format_tools_for_prompt(tools)

        # Inject tool descriptions into system message
        augmented = list(messages)
        if augmented and augmented[0]["role"] == "system":
            augmented[0] = {
                "role": "system",
                "content": augmented[0]["content"] + "\n\n" + tool_desc,
            }
        else:
            augmented.insert(0, {"role": "system", "content": tool_desc})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=augmented,
            temperature=temperature,
            max_tokens=self.max_tokens,
            timeout=self.timeout,
        )
        self._track_tokens(response)

        text = response.choices[0].message.content or ""
        return self._parse_tool_calls_from_text(text)

    def _format_tools_for_prompt(self, tools: list[dict]) -> str:
        """Format tool schemas as text instructions for prompt-based mode."""
        lines = [
            "## Available Tools",
            "",
            "You can call tools by responding with a JSON block like:",
            '```json',
            '{"tool": "tool_name", "arguments": {"arg1": "value1"}}',
            '```',
            "",
            "If you want to provide a final answer (no more tool calls), respond with plain text WITHOUT any JSON tool block.",
            "",
            "### Tools:",
            "",
        ]
        for tool in tools:
            fn = tool.get("function", tool)
            name = fn.get("name", "unknown")
            desc = fn.get("description", "")
            params = fn.get("parameters", {})
            props = params.get("properties", {})
            required = params.get("required", [])

            lines.append(f"**{name}**: {desc}")
            if props:
                lines.append("  Parameters:")
                for pname, pinfo in props.items():
                    ptype = pinfo.get("type", "any")
                    pdesc = pinfo.get("description", "")
                    req = " (required)" if pname in required else ""
                    lines.append(f"  - {pname} ({ptype}{req}): {pdesc}")
            lines.append("")

        return "\n".join(lines)

    def _parse_tool_calls_from_text(self, text: str) -> LLMResponse:
        """Parse tool calls from text response (prompt-based fallback)."""
        # Look for JSON blocks
        json_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
        matches = re.findall(json_pattern, text, re.DOTALL)

        tool_calls = []
        for match in matches:
            try:
                data = json.loads(match.strip())
                if "tool" in data:
                    tool_calls.append(ToolCall(
                        name=data["tool"],
                        arguments=data.get("arguments", {}),
                        id=f"prompt_{len(tool_calls)}",
                    ))
            except json.JSONDecodeError:
                continue

        if tool_calls:
            # Remove JSON blocks from text for the accompanying message
            clean_text = re.sub(json_pattern, "", text, flags=re.DOTALL).strip()
            return LLMResponse(text=clean_text or None, tool_calls=tool_calls)

        return LLMResponse(text=text)

    def _detect_function_calling(self) -> bool:
        """Try to detect if the model supports function calling."""
        # Known models that support function calling
        fc_models = ["gpt-", "qwen", "deepseek", "glm-"]
        model_lower = self.model.lower()
        for prefix in fc_models:
            if prefix in model_lower:
                return True
        # Ollama models generally don't support FC natively
        if self.base_url and "11434" in self.base_url:
            return False
        # Default: try it
        return True

    def _track_tokens(self, response):
        """Track token usage from API response."""
        if hasattr(response, "usage") and response.usage:
            self.tokens.record(
                prompt=response.usage.prompt_tokens or 0,
                completion=response.usage.completion_tokens or 0,
            )
