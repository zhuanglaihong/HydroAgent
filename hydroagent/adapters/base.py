"""
PackageAdapter abstract base class.

Each water model package (hydromodel, etc.) implements this interface.
The adapter encapsulates all package-specific logic so the core agent
remains package-agnostic.

Design:
  - can_handle()           : routing selector (required)
  - supported_operations() : capability declaration (required)
  - execute()              : single dispatch entry point (optional override)
  - calibrate / evaluate / visualize / simulate / read_data / list_basins
                           : optional operation methods; default returns
                             {"success": False, "supported": False}

Adding a new operation type never requires changing this base class:
just implement a new method in the adapter and declare it in
supported_operations().
"""

from abc import ABC, abstractmethod
from pathlib import Path


class PackageAdapter(ABC):
    name: str = ""
    priority: int = 0  # higher wins; equal priority sorted by name
    description: str = ""          # one-line description shown in Web UI
    zh_label: str = ""             # Chinese display name for Web UI (falls back to name)
    zh_operations: dict = {}       # operation -> Chinese label, e.g. {"derive_formula": "推导产流公式"}

    # ── Required: routing ─────────────────────────────────────────────────────

    @abstractmethod
    def can_handle(self, data_source: str, model_name: str) -> bool:
        """Return True if this adapter can process the given data_source/model_name."""
        ...

    @abstractmethod
    def supported_operations(self) -> list[str]:
        """Declare which operation names this adapter implements.

        Examples: ["calibrate", "evaluate", "visualize", "simulate"]
                  ["read_data", "list_basins", "convert_to_nc"]

        The agent uses this list to decide whether to route here or fall
        through to a lower-priority adapter / GenericAdapter.
        """
        ...

    # ── Dispatch entry point ──────────────────────────────────────────────────

    def execute(self, operation: str, workspace: Path, **kw) -> dict:
        """Dispatch an operation to the corresponding method.

        Looks up self.<operation>(workspace, **kw). If the method exists and
        is callable, calls it. Otherwise returns a structured 'not supported'
        dict so the LLM can take corrective action.

        Subclasses rarely need to override this — just implement the operation
        methods and declare them in supported_operations().
        """
        fn = getattr(self, operation, None)
        if callable(fn):
            return fn(workspace, **kw)
        return {
            "success": False,
            "supported": False,
            "adapter": self.name,
            "error": (
                f"Operation '{operation}' is not implemented by adapter "
                f"'{self.name}'. Supported: {self.supported_operations()}. "
                "Use generate_code + run_code to handle this manually."
            ),
        }

    # ── Optional operation methods (default: not supported) ───────────────────
    # Subclasses override only the ones they support.

    def calibrate(self, workspace: Path, **kw) -> dict:
        return self._not_supported("calibrate")

    def evaluate(self, workspace: Path, **kw) -> dict:
        return self._not_supported("evaluate")

    def visualize(self, workspace: Path, **kw) -> dict:
        return self._not_supported("visualize")

    def simulate(self, workspace: Path, **kw) -> dict:
        return self._not_supported("simulate")

    def read_data(self, workspace: Path, **kw) -> dict:
        return self._not_supported("read_data")

    def list_basins(self, workspace: Path, **kw) -> dict:
        return self._not_supported("list_basins")

    # ── Skill docs ────────────────────────────────────────────────────────────

    def get_skill_docs(self) -> list[str]:
        """Read adapters/<name>/skills/*.md and return text list."""
        skills_dir = Path(__file__).parent / self.name / "skills"
        if not skills_dir.exists():
            return []
        return [
            p.read_text(encoding="utf-8")
            for p in sorted(skills_dir.glob("*.md"))
        ]

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _not_supported(self, operation: str) -> dict:
        return {
            "success": False,
            "supported": False,
            "adapter": self.name,
            "error": (
                f"Adapter '{self.name}' does not support '{operation}'. "
                f"Supported operations: {self.supported_operations()}. "
                "Use generate_code + run_code to handle this manually."
            ),
        }
