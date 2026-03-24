"""
External plugin registry for HydroClaw.

Manages ~/.hydroclaw/plugins.json (global) and <workspace>/.hydroclaw/plugins.json (local).
Local entries override global entries with the same name.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Literal, TypedDict

logger = logging.getLogger(__name__)

_GLOBAL_DIR = Path.home() / ".hydroclaw"
_PLUGINS_FILENAME = "plugins.json"


class PluginEntry(TypedDict):
    name: str
    type: Literal["pip", "local_dir", "single_file"]
    path: str           # local filesystem path or pip package name
    adapter_path: str   # absolute path to the adapter .py file (may be empty)
    enabled: bool
    description: str
    added_at: str       # ISO 8601


class PluginRegistry:
    """Read/write plugin registry with two-layer override (global < local)."""

    def __init__(self, workspace: Path | None = None):
        self._workspace = workspace

    # ── paths ─────────────────────────────────────────────────────────────────

    @property
    def global_path(self) -> Path:
        return _GLOBAL_DIR / _PLUGINS_FILENAME

    @property
    def local_path(self) -> Path | None:
        if self._workspace is None:
            return None
        return self._workspace / ".hydroclaw" / _PLUGINS_FILENAME

    # ── low-level read/write ──────────────────────────────────────────────────

    def _read(self, path: Path) -> dict[str, PluginEntry]:
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return {e["name"]: e for e in data.get("plugins", []) if "name" in e}
        except Exception as exc:
            logger.warning("[plugin_registry] failed to read %s: %s", path, exc)
            return {}

    def _write(self, path: Path, entries: dict[str, PluginEntry]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"plugins": list(entries.values())}
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

    # ── public API ────────────────────────────────────────────────────────────

    def list_plugins(self) -> list[PluginEntry]:
        """Return merged plugin list (global + local); local overrides global."""
        global_entries = self._read(self.global_path)
        merged = dict(global_entries)
        if self.local_path is not None:
            merged.update(self._read(self.local_path))
        return list(merged.values())

    def get(self, name: str) -> PluginEntry | None:
        for p in self.list_plugins():
            if p["name"] == name:
                return p
        return None

    def add(self, entry: PluginEntry) -> None:
        """Add or update a plugin entry in the local registry."""
        target = self.local_path or self.global_path
        entries = self._read(target)
        entries[entry["name"]] = entry
        self._write(target, entries)
        logger.info("[plugin_registry] registered plugin '%s' -> %s", entry["name"], target)

    def remove(self, name: str) -> bool:
        """Remove a plugin from the local registry. Returns True if found."""
        target = self.local_path or self.global_path
        entries = self._read(target)
        if name not in entries:
            # also try global
            g_entries = self._read(self.global_path)
            if name in g_entries:
                del g_entries[name]
                self._write(self.global_path, g_entries)
                return True
            return False
        del entries[name]
        self._write(target, entries)
        return True

    def _set_enabled(self, name: str, enabled: bool) -> bool:
        target = self.local_path or self.global_path
        entries = self._read(target)
        if name not in entries:
            # copy from global to local before modifying
            g = self._read(self.global_path)
            if name not in g:
                return False
            entries[name] = dict(g[name])
        entries[name]["enabled"] = enabled
        self._write(target, entries)
        return True

    def enable(self, name: str) -> bool:
        return self._set_enabled(name, True)

    def disable(self, name: str) -> bool:
        return self._set_enabled(name, False)

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def make_entry(
        name: str,
        path: str,
        plugin_type: Literal["pip", "local_dir", "single_file"],
        adapter_path: str = "",
        description: str = "",
        enabled: bool = True,
    ) -> PluginEntry:
        return PluginEntry(
            name=name,
            type=plugin_type,
            path=path,
            adapter_path=adapter_path,
            enabled=enabled,
            description=description,
            added_at=datetime.now().isoformat(timespec="seconds"),
        )
