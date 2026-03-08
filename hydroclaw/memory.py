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
        self.basin_profiles_dir = self.base_dir / "basin_profiles"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.basin_profiles_dir.mkdir(parents=True, exist_ok=True)

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

    def save_basin_profile(
        self,
        basin_id: str,
        model_name: str,
        best_params: dict,
        metrics: dict,
        algorithm: str = "SCE_UA",
    ):
        """Save a calibration result as a structured basin profile.

        Appends to the basin's history file; each basin can accumulate
        multiple records across sessions (different models / algorithms).
        """
        profile_file = self.basin_profiles_dir / f"{basin_id}.json"

        if profile_file.exists():
            try:
                with open(profile_file, "r", encoding="utf-8") as f:
                    profile = json.load(f)
            except Exception:
                profile = {"basin_id": basin_id, "records": []}
        else:
            profile = {"basin_id": basin_id, "records": []}

        record = {
            "model": model_name,
            "algorithm": algorithm,
            "train_nse": metrics.get("NSE"),
            "train_kge": metrics.get("KGE"),
            "train_rmse": metrics.get("RMSE"),
            "best_params": best_params,
            "calibrated_at": datetime.now().isoformat(),
        }
        profile["records"].append(record)

        with open(profile_file, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2, ensure_ascii=False, default=str)

        logger.info(
            f"Basin profile saved: {basin_id}/{model_name} "
            f"NSE={metrics.get('NSE')}"
        )

    def load_basin_profile(self, basin_id: str) -> dict | None:
        """Load all historical calibrations for a basin."""
        profile_file = self.basin_profiles_dir / f"{basin_id}.json"
        if not profile_file.exists():
            return None
        try:
            with open(profile_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load basin profile {basin_id}: {e}")
            return None

    def format_basin_profiles_for_context(self, basin_ids: list[str]) -> str:
        """Format historical basin calibrations as markdown for LLM context.

        Returns empty string if no profiles exist for any of the given basins.
        """
        lines = []
        for basin_id in basin_ids:
            profile = self.load_basin_profile(basin_id)
            if not profile or not profile.get("records"):
                continue

            lines.append(f"### Basin {basin_id}")
            # Show at most last 3 records to keep context short
            for rec in profile["records"][-3:]:
                nse = rec.get("train_nse")
                nse_str = f"{nse:.3f}" if isinstance(nse, float) else "N/A"
                params = rec.get("best_params", {})
                params_str = ", ".join(
                    f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}"
                    for k, v in params.items()
                )
                lines.append(
                    f"- {rec['model'].upper()} ({rec['algorithm']}, "
                    f"{rec['calibrated_at'][:10]}): train NSE={nse_str}"
                )
                if params_str:
                    lines.append(f"  Best params: {params_str}")
            lines.append("")

        if not lines:
            return ""
        return "## Previous Basin Calibrations\n\n" + "\n".join(lines)

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
