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


def semantic_truncate(text: str, max_chars: int, label: str = "content") -> str:
    """Truncate *text* to *max_chars* by cutting at paragraph (double-newline) boundaries.

    Prefer complete paragraphs over a hard character-count cut.
    Falls back to sentence-boundary ('. ') if no paragraph break is found near the limit.
    Always appends a note showing how much was dropped.
    """
    if len(text) <= max_chars:
        return text

    # Try to cut at last paragraph boundary before limit
    cut = text.rfind("\n\n", 0, max_chars)
    if cut == -1 or cut < max_chars // 2:
        # No good paragraph break — fall back to sentence boundary
        cut = text.rfind(". ", 0, max_chars)
    if cut == -1 or cut < max_chars // 4:
        # Still nothing — hard cut
        cut = max_chars

    kept = text[:cut].rstrip()
    dropped = len(text) - cut
    return kept + f"\n\n...({label} truncated, {dropped} chars omitted)"


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
