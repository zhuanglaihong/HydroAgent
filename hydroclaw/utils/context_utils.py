"""
Author: HydroClaw Team
Date: 2026-03-09
Description: Context management utilities for the agentic loop.
             Keeps agent.py clean by centralizing token estimation,
             tool result serialization, and context size checks.
"""

import json
import logging

logger = logging.getLogger(__name__)

# Max chars for any single tool result stored in messages.
# Prevents run_code stdout or read_file content from bloating the context.
TOOL_RESULT_MAX_CHARS = 8_000


def estimate_tokens(messages: list[dict]) -> int:
    """Rough token estimate: ~3 chars per token."""
    total = sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)
    return total // 3


def truncate_tool_result(tool_name: str, result: object) -> str:
    """Serialize a tool result to JSON, truncating oversized string fields.

    Prevents large stdout (run_code) or file content (read_file) from
    accumulating in the message history and blowing up the context window.
    """
    if isinstance(result, dict):
        truncated = {}
        for k, v in result.items():
            if isinstance(v, str) and len(v) > TOOL_RESULT_MAX_CHARS:
                truncated[k] = (
                    v[:TOOL_RESULT_MAX_CHARS]
                    + f"\n...(truncated, {len(v)} chars total)"
                )
                logger.debug(
                    "Tool '%s' field '%s' truncated: %d -> %d chars",
                    tool_name, k, len(v), TOOL_RESULT_MAX_CHARS,
                )
            else:
                truncated[k] = v
        text = json.dumps(truncated, ensure_ascii=False, default=str)
    else:
        text = json.dumps(result, ensure_ascii=False, default=str)

    # Final safety: catch large nested structures
    if len(text) > TOOL_RESULT_MAX_CHARS * 2:
        text = text[:TOOL_RESULT_MAX_CHARS * 2] + "\n...(result truncated)"
        logger.warning("Tool '%s' result truncated at serialization level.", tool_name)

    return text
