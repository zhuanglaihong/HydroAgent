"""
Author: HydroClaw Team
Date: 2026-02-08
Description: Memory system - persistent knowledge (MEMORY.md) + session logs (JSONL).
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class Memory:
    """Agent memory: persistent knowledge + session recording.

    - MEMORY.md: Persistent knowledge the agent accumulates (cross-session).
    - sessions/*.jsonl: Per-session tool call logs for resumption.
    """

    def __init__(self, base_dir: Path | str = "."):
        self.base_dir = Path(base_dir)
        self.memory_file = self.base_dir / "MEMORY.md"
        self.sessions_dir = self.base_dir / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

        self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._session_file = self.sessions_dir / f"{self._session_id}.jsonl"
        self._log: list[dict] = []

    @property
    def session_id(self) -> str:
        return self._session_id

    def load_knowledge(self) -> str:
        """Load persistent knowledge from MEMORY.md."""
        if self.memory_file.exists():
            text = self.memory_file.read_text(encoding="utf-8")
            # Truncate to avoid token overflow
            lines = text.split("\n")
            if len(lines) > 200:
                text = "\n".join(lines[:200]) + "\n...(truncated)"
            return text
        return ""

    def save_knowledge(self, content: str):
        """Save persistent knowledge to MEMORY.md."""
        self.memory_file.write_text(content, encoding="utf-8")
        logger.info("Saved knowledge to MEMORY.md")

    def log_tool_call(self, tool_name: str, arguments: dict, result: Any):
        """Log a tool call for session replay."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "tool": tool_name,
            "arguments": _safe_serialize(arguments),
            "result_summary": _summarize_result(result),
        }
        self._log.append(entry)

        # Append to JSONL file
        with open(self._session_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def save_session(self, query: str, final_response: str):
        """Save session summary."""
        summary = {
            "session_id": self._session_id,
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "tool_calls": len(self._log),
            "final_response_preview": final_response[:500] if final_response else "",
        }

        summary_file = self.sessions_dir / f"{self._session_id}_summary.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        logger.info(f"Session saved: {self._session_id} ({len(self._log)} tool calls)")

    def load_session(self, session_id: str) -> list[dict]:
        """Load a previous session's tool calls for resumption."""
        session_file = self.sessions_dir / f"{session_id}.jsonl"
        if not session_file.exists():
            logger.warning(f"Session file not found: {session_file}")
            return []

        entries = []
        with open(session_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))

        logger.info(f"Loaded session {session_id}: {len(entries)} entries")
        return entries

    def get_recent_sessions(self, limit: int = 5) -> list[dict]:
        """Get recent session summaries."""
        summaries = []
        for f in sorted(self.sessions_dir.glob("*_summary.json"), reverse=True)[:limit]:
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    summaries.append(json.load(fh))
            except Exception:
                continue
        return summaries


def _safe_serialize(obj: Any) -> Any:
    """Make an object JSON-serializable."""
    if isinstance(obj, dict):
        return {k: _safe_serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_safe_serialize(v) for v in obj]
    if isinstance(obj, Path):
        return str(obj)
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)


def _summarize_result(result: Any) -> Any:
    """Create a compact summary of a tool result."""
    if isinstance(result, dict):
        # Keep small dicts, summarize large ones
        if len(str(result)) > 2000:
            summary = {}
            for k, v in result.items():
                if k in ("error", "success", "metrics", "best_params", "calibration_dir",
                         "valid", "valid_basins", "plot_count", "file_path"):
                    summary[k] = v
                elif isinstance(v, list):
                    summary[k] = f"[{len(v)} items]"
                elif isinstance(v, str) and len(v) > 200:
                    summary[k] = v[:200] + "..."
                else:
                    summary[k] = v
            return summary
        return result
    if isinstance(result, str) and len(result) > 1000:
        return result[:1000] + "..."
    return result
