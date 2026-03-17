"""
GenericAdapter: fallback when no specific package adapter matches.

Returns structured guidance instead of raising exceptions, so the LLM
can read the message and take corrective action (e.g. generate custom code).
"""

from pathlib import Path

from hydroclaw.adapters.base import PackageAdapter


class Adapter(PackageAdapter):
    name = "generic"
    priority = 0

    def can_handle(self, data_source: str, model_name: str) -> bool:
        return True  # always falls back here

    def supported_operations(self) -> list[str]:
        return []  # generic adapter has no real implementations

    def execute(self, operation: str, workspace: Path, **kw) -> dict:
        """Return structured guidance for any unmatched operation."""
        return {
            "success": False,
            "adapter": "generic",
            "operation": operation,
            "message": (
                f"No specific package adapter matched for '{operation}'. "
                "Use generate_code to write a script for your package, "
                "then use run_code to execute it. "
                "Check skill docs for code examples."
            ),
        }
