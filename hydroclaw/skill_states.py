"""
Author: HydroClaw Team
Date: 2026-03-09
Description: Skill lifecycle state manager.
             Tracks generated skills through: unverified -> good | bad
             Builtin skills are never tracked (always treated as stable).
"""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Thresholds for state transitions
_GOOD_THRESHOLD = 2   # success_count >= N -> good
_BAD_THRESHOLD  = 2   # fail_count   >= N -> bad

_STATE_FILE = ".skill_states.json"


class SkillStateManager:
    """Manages lifecycle states for dynamically generated skills.

    State file: hydroclaw/skills/.skill_states.json
    Only generated skills are tracked; builtin skills are never in this file.

    States:
        unverified  Created but not yet verified by successful execution.
        good        Executed successfully >= _GOOD_THRESHOLD times.
        bad         Load test failed OR execution failed >= _BAD_THRESHOLD times.
    """

    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self.state_file = skills_dir / _STATE_FILE
        self._states: dict = self._load()

    # ── Persistence ──────────────────────────────────────────────────────────

    def _load(self) -> dict:
        if self.state_file.exists():
            try:
                text = self.state_file.read_text(encoding="utf-8").strip()
                if not text:
                    return {}
                return json.loads(text)
            except Exception as e:
                logger.warning(f"Failed to load skill states: {e}")
        return {}

    def _save(self):
        try:
            self.state_file.write_text(
                json.dumps(self._states, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"Failed to save skill states: {e}")

    # ── Public API ────────────────────────────────────────────────────────────

    def is_generated(self, skill_name: str) -> bool:
        return skill_name in self._states

    def get_status(self, skill_name: str) -> str:
        """Return status string or 'builtin' if not tracked."""
        return self._states.get(skill_name, {}).get("status", "builtin")

    def get_last_error(self, skill_name: str) -> str | None:
        return self._states.get(skill_name, {}).get("last_error")

    def mark_created(self, skill_name: str):
        """Called immediately after create_skill writes files successfully."""
        self._states[skill_name] = {
            "status": "unverified",
            "source": "generated",
            "use_count": 0,
            "success_count": 0,
            "fail_count": 0,
            "created_at": datetime.now().isoformat(),
            "last_used": None,
            "last_error": None,
        }
        self._save()
        logger.info(f"Skill '{skill_name}' registered as unverified")

    def mark_bad(self, skill_name: str, error: str | None = None):
        """Called when module load test fails. Immediately marks as bad."""
        if skill_name not in self._states:
            return
        self._states[skill_name]["status"] = "bad"
        if error:
            self._states[skill_name]["last_error"] = error[:400]
        self._save()
        logger.warning(f"Skill '{skill_name}' marked as bad: {error}")

    def record_execution(self, skill_name: str, success: bool, error: str | None = None):
        """Update state after a tool call. Transitions unverified->good or ->bad."""
        if skill_name not in self._states:
            return  # builtin or untracked, skip
        s = self._states[skill_name]
        s["use_count"] = s.get("use_count", 0) + 1
        s["last_used"] = datetime.now().isoformat()

        if success:
            s["success_count"] = s.get("success_count", 0) + 1
            s["last_error"] = None
            if s.get("status") != "good" and s["success_count"] >= _GOOD_THRESHOLD:
                s["status"] = "good"
                logger.info(f"Skill '{skill_name}' promoted to good "
                            f"({s['success_count']} successful executions)")
        else:
            s["fail_count"] = s.get("fail_count", 0) + 1
            if error:
                s["last_error"] = error[:400]
            if s.get("status") not in ("bad",) and s["fail_count"] >= _BAD_THRESHOLD:
                s["status"] = "bad"
                logger.warning(f"Skill '{skill_name}' marked as bad "
                               f"({s['fail_count']} failures)")

        self._save()

    def status_badge(self, skill_name: str) -> str:
        """Short badge for UI display: [good] / [unverified] / [bad] / ''"""
        status = self.get_status(skill_name)
        return {"good": "[good]", "unverified": "[unverified]", "bad": "[bad]"}.get(status, "")

    def summary(self) -> dict:
        """Return counts by status for logging/reporting."""
        counts: dict[str, int] = {}
        for s in self._states.values():
            st = s.get("status", "unknown")
            counts[st] = counts.get(st, 0) + 1
        return counts
