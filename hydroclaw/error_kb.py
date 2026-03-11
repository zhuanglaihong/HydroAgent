"""
Author: HydroClaw Team
Date: 2026-03-09
Description: Self-growing error knowledge base.
             Matches known error patterns, returns solutions, records new fixes.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_KB_FILE = Path(__file__).parent / "knowledge" / "error_solutions.json"

# ── Built-in seed entries ────────────────────────────────────────────────────
# Added on first run if the KB file does not exist.

_SEED_ENTRIES = [
    {
        "id": "err_001",
        "category": "missing_import",
        "pattern": r"NameError: name '(\w+)' is not defined",
        "description": "Variable used at module level without import",
        "solutions": [
            "Move all imports inside the function body (lazy import pattern).",
            "For numpy: add `import numpy as np` at the top of the function.",
            "For pandas: add `import pandas as pd` inside the function.",
            "For matplotlib: add `import matplotlib.pyplot as plt` inside the function.",
            "Check if the variable is a typo of an imported name.",
        ],
        "example_fix": (
            "def my_tool(x: int) -> dict:\n"
            "    import numpy as np          # import inside function body\n"
            "    arr = np.array([x])\n"
            "    return {'result': arr.tolist(), 'success': True}"
        ),
        "times_seen": 0,
        "times_resolved": 0,
        "last_seen": None,
    },
    {
        "id": "err_002",
        "category": "import_error",
        "pattern": r"(ImportError|ModuleNotFoundError): [Nn]o module named '(\S+)'",
        "description": "Package not installed or wrong import path",
        "solutions": [
            "Check if the package is installed: run `pip show <package>` in terminal.",
            "If the package is not installed, add a try/except around the import and return "
            '{"error": "Package X not installed. Run: pip install X", "success": False}.',
            "Verify the exact import path — do not hallucinate submodule paths.",
            "Use inspect_dir or read_file to verify the real import structure before importing.",
        ],
        "example_fix": (
            "def my_tool() -> dict:\n"
            "    try:\n"
            "        import spotpy\n"
            "    except ImportError:\n"
            "        return {'error': 'spotpy not installed. Run: pip install spotpy', 'success': False}\n"
            "    ..."
        ),
        "times_seen": 0,
        "times_resolved": 0,
        "last_seen": None,
    },
    {
        "id": "err_003",
        "category": "attribute_error",
        "pattern": r"AttributeError: .* has no attribute '(\w+)'",
        "description": "Wrong attribute or method name on an object",
        "solutions": [
            "Use inspect_dir or read_file to check the actual API of the package.",
            "Do not guess method names — verify with the package documentation.",
            "Add a stub that returns an error rather than calling an unverified API.",
        ],
        "example_fix": (
            "# Instead of guessing: result = pkg.unknown_method()\n"
            "# Use a safe stub:\n"
            "return {'error': 'API not verified — inspect package first', 'success': False}"
            "  # TODO: verify import path"
        ),
        "times_seen": 0,
        "times_resolved": 0,
        "last_seen": None,
    },
    {
        "id": "err_004",
        "category": "syntax_error",
        "pattern": r"SyntaxError: (.*)",
        "description": "Python syntax error in generated code",
        "solutions": [
            "Check for unclosed parentheses, brackets, or quotes.",
            "Ensure f-strings are properly closed.",
            "Verify indentation is consistent (use 4 spaces, not tabs).",
            "Check for missing colons after def/if/for/with statements.",
        ],
        "example_fix": "",
        "times_seen": 0,
        "times_resolved": 0,
        "last_seen": None,
    },
    {
        "id": "err_005",
        "category": "type_error",
        "pattern": r"TypeError: (.*)",
        "description": "Wrong argument type or count passed to a function",
        "solutions": [
            "Check the function signature and ensure argument types match.",
            "Verify the number of positional arguments.",
            "Add type conversion if needed (e.g. int(), str(), list()).",
        ],
        "example_fix": "",
        "times_seen": 0,
        "times_resolved": 0,
        "last_seen": None,
    },
]


class ErrorKnowledgeBase:
    """Self-growing error pattern knowledge base.

    Stores known error patterns with solutions. Matches incoming error
    messages and returns actionable hints for the agent. Records new
    fixes as they are discovered.
    """

    def __init__(self, kb_file: Path = _KB_FILE):
        self.kb_file = kb_file
        self.entries: list[dict] = []
        self._load()

    # ── Persistence ──────────────────────────────────────────────────────────

    def _load(self):
        if self.kb_file.exists():
            try:
                data = json.loads(self.kb_file.read_text(encoding="utf-8"))
                self.entries = data.get("entries", [])
                logger.debug(f"ErrorKB loaded: {len(self.entries)} entries")
                return
            except Exception as e:
                logger.warning(f"Failed to load ErrorKB: {e}")
        # First run: seed with built-in entries
        self.entries = [dict(e) for e in _SEED_ENTRIES]
        self._save()
        logger.info("ErrorKB initialized with seed entries")

    def _save(self):
        self.kb_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "description": "HydroClaw Error Knowledge Base — auto-updated",
            "updated_at": datetime.now().isoformat(),
            "entries": self.entries,
        }
        self.kb_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ── Search ────────────────────────────────────────────────────────────────

    def search(self, error_msg: str) -> list[dict]:
        """Return matching KB entries for the given error message.

        Returns a list of dicts with {id, description, solutions, example_fix}.
        Updates times_seen for each match.
        """
        if not error_msg:
            return []

        matched = []
        for entry in self.entries:
            try:
                if re.search(entry["pattern"], error_msg, re.IGNORECASE):
                    entry["times_seen"] = entry.get("times_seen", 0) + 1
                    entry["last_seen"] = datetime.now().isoformat()
                    matched.append({
                        "id": entry["id"],
                        "category": entry["category"],
                        "description": entry["description"],
                        "solutions": entry["solutions"],
                        "example_fix": entry.get("example_fix", ""),
                    })
            except re.error:
                pass

        if matched:
            self._save()
        return matched

    def format_hints(self, error_msg: str) -> str:
        """Return a formatted hint string to include in tool error responses."""
        matches = self.search(error_msg)
        if not matches:
            return ""
        lines = ["[ErrorKB] Known solutions for this error type:"]
        for m in matches:
            lines.append(f"  Category: {m['category']} — {m['description']}")
            for i, sol in enumerate(m["solutions"], 1):
                lines.append(f"    {i}. {sol}")
            if m.get("example_fix"):
                lines.append(f"  Example fix:\n{m['example_fix']}")
        return "\n".join(lines)

    # ── Record ────────────────────────────────────────────────────────────────

    def record_fix(self, error_msg: str, solution: str, resolved: bool):
        """Record that a solution was attempted for an error.

        If resolved=True and the error matched an existing entry, increment
        times_resolved. If no match, add a new entry (unresolved goes in as
        a stub; resolved gets recorded with the solution).
        """
        matches = [e for e in self.entries
                   if re.search(e["pattern"], error_msg, re.IGNORECASE | re.DOTALL)]

        if matches and resolved:
            for entry in matches:
                entry["times_resolved"] = entry.get("times_resolved", 0) + 1
                # Add the solution if it's new
                if solution and solution not in entry["solutions"]:
                    entry["solutions"].append(solution)
            self._save()
            logger.info(f"ErrorKB: recorded fix for pattern '{matches[0]['id']}'")
            return

        if not matches:
            # New error pattern — add as a stub
            new_id = f"err_{len(self.entries) + 1:03d}"
            # Use first line of error as pattern (escaped for regex)
            first_line = error_msg.strip().split("\n")[-1][:120]
            pattern = re.escape(first_line[:60])
            new_entry = {
                "id": new_id,
                "category": "unknown",
                "pattern": pattern,
                "description": first_line,
                "solutions": [solution] if solution else [],
                "example_fix": "",
                "times_seen": 1,
                "times_resolved": 1 if resolved else 0,
                "last_seen": datetime.now().isoformat(),
                "auto_added": True,
            }
            self.entries.append(new_entry)
            self._save()
            status = "resolved" if resolved else "unresolved"
            logger.info(f"ErrorKB: new entry {new_id} added ({status})")

    def add_entry(
        self,
        pattern: str,
        description: str,
        solutions: list[str],
        category: str = "custom",
        example_fix: str = "",
    ) -> str:
        """Manually add a new KB entry. Returns the new entry ID."""
        new_id = f"err_{len(self.entries) + 1:03d}"
        self.entries.append({
            "id": new_id,
            "category": category,
            "pattern": pattern,
            "description": description,
            "solutions": solutions,
            "example_fix": example_fix,
            "times_seen": 0,
            "times_resolved": 0,
            "last_seen": None,
            "user_added": True,
        })
        self._save()
        logger.info(f"ErrorKB: user-added entry {new_id}")
        return new_id
