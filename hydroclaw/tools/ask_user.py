"""
Author: HydroClaw Team
Date: 2026-03-10
Description: ask_user tool - let the agent ask the user a clarifying question
             when critical information is missing and cannot be resolved by tools.
"""

import logging

logger = logging.getLogger(__name__)


def ask_user(
    question: str,
    context: str | None = None,
    _ui=None,
) -> dict:
    """Ask the user a clarifying question when critical information is missing.

    Use this whenever you would otherwise have to guess, use a placeholder,
    or fall back to simulated data. Any tool or step can trigger ask_user
    if a required input is unknown and cannot be resolved by other tools.

    Args:
        question: Specific, concise question stating exactly what is needed
        context: One-sentence explanation of why this information is required

    Returns:
        {"answer": str, "success": bool}
    """
    if _ui is not None:
        answer = _ui.ask_user(question, context)
    else:
        # Bare fallback: no UI injected (e.g. unit tests)
        import sys
        if context:
            print(f"[Context] {context}", file=sys.__stdout__)
        print(f"[Question] {question}", file=sys.__stdout__)
        print("> ", end="", flush=True, file=sys.__stdout__)
        try:
            answer = sys.__stdin__.readline().strip()
        except (AttributeError, EOFError):
            answer = ""

    logger.info("ask_user: Q=%r  A=%r", question, answer)

    if not answer:
        return {
            "answer": "",
            "success": False,
            "note": "User provided no answer; try a sensible default or stop.",
        }

    return {"answer": answer, "success": True}
