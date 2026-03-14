"""
Author: HydroClaw Team
Date: 2026-03-09
Description: Tool for recording error solutions into the Error Knowledge Base.
             Agent calls this after successfully fixing an error to persist the solution.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def record_error_solution(
    error_message: str,
    solution: str,
    resolved: bool = True,
    pattern: str | None = None,
    category: str | None = None,
    example_fix: str | None = None,
) -> dict:
    """Record an error solution into the Error Knowledge Base for future reuse.

    Call this after successfully fixing a tool error. If the error matches a
    known pattern, the solution is added to that entry. If it is a new error
    type, a new entry is created automatically.

    Args:
        error_message: The exact error message that was encountered
        solution: Description of how the error was fixed
        resolved: True if the error was successfully resolved, False if still open
        pattern: Optional regex pattern for matching this error (auto-derived if omitted)
        category: Optional category label, e.g. "missing_import", "api_error"
        example_fix: Optional code snippet showing the fix

    Returns:
        {"entry_id": str, "action": str, "success": bool}
    """
    from hydroclaw.utils.error_kb import ErrorKnowledgeBase

    kb = ErrorKnowledgeBase()

    if pattern and category:
        # User/agent providing explicit pattern -> add as new full entry
        entry_id = kb.add_entry(
            pattern=pattern,
            description=error_message[:120],
            solutions=[solution] if solution else [],
            category=category,
            example_fix=example_fix or "",
        )
        action = "new_entry_added"
    else:
        # Auto-match and record
        kb.record_fix(error_message, solution=solution, resolved=resolved)
        matches = [e for e in kb.entries
                   if error_message and __import__("re").search(
                       e["pattern"], error_message, __import__("re").IGNORECASE
                   )]
        entry_id = matches[0]["id"] if matches else kb.entries[-1]["id"]
        action = "existing_entry_updated" if matches else "new_stub_added"

    status = "resolved" if resolved else "unresolved"
    logger.info(f"ErrorKB: {action} for {entry_id} ({status})")

    return {
        "entry_id": entry_id,
        "action": action,
        "resolved": resolved,
        "message": (
            f"Solution recorded in ErrorKB ({action}). "
            f"Future occurrences of this error will receive this hint automatically."
        ),
        "success": True,
    }
