"""
Author: HydroClaw Team
Date: 2026-03-08
Description: Task state persistence for batch experiments.
             Tracks pending/running/done/failed sub-tasks so a batch run
             can be safely interrupted and resumed without re-running
             completed tasks.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Task status constants
PENDING = "pending"
RUNNING = "running"
DONE    = "done"
FAILED  = "failed"


class TaskState:
    """JSON-backed task state for multi-step batch experiments.

    Usage (new batch run):
        state = TaskState(workspace / "task_state.json")
        state.create("比较GR4J和XAJ在5个流域的表现", tasks=[
            {"id": "12025000_gr4j", "description": "率定GR4J，流域12025000"},
            {"id": "12025000_xaj",  "description": "率定XAJ，流域12025000"},
        ])
        for task in state.pending():
            state.mark_running(task["id"])
            result = run(task)
            state.mark_done(task["id"], result)

    Usage (resume interrupted run):
        state = TaskState(workspace / "task_state.json")
        if state.exists():
            state.load()   # picks up from where it left off
        for task in state.pending():
            ...
    """

    def __init__(self, state_file: Path):
        self.path = Path(state_file)
        self._data: dict = {}

    # ── Lifecycle ────────────────────────────────────────────────────

    def exists(self) -> bool:
        return self.path.exists()

    def create(self, goal: str, tasks: list[dict[str, Any]]) -> None:
        """Initialize a new task state (overwrites any existing file)."""
        now = datetime.now().isoformat(timespec="seconds")
        normalized = []
        for t in tasks:
            normalized.append({
                "id":          t["id"],
                "description": t.get("description", t["id"]),
                "status":      PENDING,
                "result":      None,
                "error":       None,
                "started_at":  None,
                "finished_at": None,
            })
        self._data = {
            "goal":       goal,
            "created_at": now,
            "updated_at": now,
            "tasks":      normalized,
        }
        self._save()
        logger.info("TaskState created: %d tasks for goal: %s", len(tasks), goal[:60])

    def load(self) -> "TaskState":
        """Load state from disk. Call before iterating on resume."""
        with open(self.path, encoding="utf-8") as f:
            self._data = json.load(f)
        pending_n = len(self.pending())
        done_n    = len(self.done())
        logger.info(
            "TaskState loaded: %d pending, %d done (goal: %s)",
            pending_n, done_n, self._data.get("goal", "")[:60],
        )
        # Reset any tasks stuck in 'running' (from a previous interrupted run)
        for t in self._data["tasks"]:
            if t["status"] == RUNNING:
                t["status"] = PENDING
                logger.warning("Task %s was stuck in RUNNING, reset to PENDING", t["id"])
        self._save()
        return self

    # ── Query ────────────────────────────────────────────────────────

    def pending(self) -> list[dict]:
        return [t for t in self._data.get("tasks", []) if t["status"] == PENDING]

    def done(self) -> list[dict]:
        return [t for t in self._data.get("tasks", []) if t["status"] == DONE]

    def failed(self) -> list[dict]:
        return [t for t in self._data.get("tasks", []) if t["status"] == FAILED]

    def all_tasks(self) -> list[dict]:
        return list(self._data.get("tasks", []))

    def is_complete(self) -> bool:
        return len(self.pending()) == 0 and len(self._running()) == 0

    def get(self, task_id: str) -> dict | None:
        for t in self._data.get("tasks", []):
            if t["id"] == task_id:
                return t
        return None

    @property
    def goal(self) -> str:
        return self._data.get("goal", "")

    # ── Mutations ────────────────────────────────────────────────────

    def mark_running(self, task_id: str) -> None:
        t = self._get_or_raise(task_id)
        t["status"]     = RUNNING
        t["started_at"] = datetime.now().isoformat(timespec="seconds")
        self._save()

    def mark_done(self, task_id: str, result: dict | None = None) -> None:
        t = self._get_or_raise(task_id)
        t["status"]      = DONE
        t["result"]      = result or {}
        t["finished_at"] = datetime.now().isoformat(timespec="seconds")
        self._save()
        logger.info("Task done: %s", task_id)

    def mark_failed(self, task_id: str, error: str = "") -> None:
        t = self._get_or_raise(task_id)
        t["status"]      = FAILED
        t["error"]       = error
        t["finished_at"] = datetime.now().isoformat(timespec="seconds")
        self._save()
        logger.warning("Task failed: %s — %s", task_id, error[:120])

    def retry_failed(self) -> int:
        """Reset all failed tasks back to pending. Returns number reset."""
        count = 0
        for t in self._data.get("tasks", []):
            if t["status"] == FAILED:
                t["status"] = PENDING
                t["error"]  = None
                count += 1
        if count:
            self._save()
        return count

    # ── Summary ──────────────────────────────────────────────────────

    def summary(self) -> str:
        """Return a human-readable progress summary."""
        tasks = self._data.get("tasks", [])
        total   = len(tasks)
        done    = sum(1 for t in tasks if t["status"] == DONE)
        failed  = sum(1 for t in tasks if t["status"] == FAILED)
        pending = sum(1 for t in tasks if t["status"] == PENDING)
        running = sum(1 for t in tasks if t["status"] == RUNNING)
        lines = [
            f"Goal: {self.goal}",
            f"Progress: {done}/{total} done, {failed} failed, {pending} pending, {running} running",
        ]
        for t in tasks:
            icon = {"done": "[+]", "failed": "[x]", "pending": "[ ]", "running": "[~]"}.get(t["status"], "?")
            line = f"  {icon} {t['id']}: {t['status']}"
            if t["status"] == DONE and t.get("result"):
                r = t["result"]
                nse = r.get("nse") or r.get("NSE") or r.get("metrics", {}).get("NSE")
                if nse is not None and isinstance(nse, (int, float)):
                    line += f"  NSE={nse:.3f}"
            elif t["status"] == FAILED and t.get("error"):
                line += f"  ({t['error'][:60]})"
            lines.append(line)
        return "\n".join(lines)

    def results_by_id(self) -> dict[str, dict]:
        """Return {task_id: result} for all completed tasks."""
        return {t["id"]: t["result"] for t in self.done() if t.get("result")}

    # ── Internal ─────────────────────────────────────────────────────

    def _running(self) -> list[dict]:
        return [t for t in self._data.get("tasks", []) if t["status"] == RUNNING]

    def _get_or_raise(self, task_id: str) -> dict:
        t = self.get(task_id)
        if t is None:
            raise KeyError(f"Task not found: {task_id}")
        return t

    def _save(self) -> None:
        self._data["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
