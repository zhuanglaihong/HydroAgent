"""
Adapter registry: auto-discovery, hot-reload, and routing.

Usage:
    from hydroagent.adapters import get_adapter, get_all_skill_docs, reload_adapters

    adapter = get_adapter(data_source="camels_us", model_name="gr4j")
    result  = adapter.calibrate(workspace=Path("."), ...)
"""

import importlib
import logging
import sys
from pathlib import Path

from .base import PackageAdapter

logger = logging.getLogger(__name__)
_adapters: list[PackageAdapter] = []


def reload_adapters(workspace: "Path | None" = None):
    """Re-scan adapters/ and load all adapter.py files, then load external plugins.

    Called once at module import. Also call this after create_adapter or
    add_local_package generates new adapters so they take effect without restart.

    Args:
        workspace: Optional path to the current workspace.  Used to locate the
                   local plugin registry (<workspace>/.hydroagent/plugins.json).
    """
    global _adapters
    _adapters.clear()

    # ── 1. Built-in adapters (hydroagent/adapters/*/adapter.py) ───────────────
    adapters_dir = Path(__file__).parent
    for adapter_py in sorted(adapters_dir.glob("*/adapter.py")):
        pkg_name = adapter_py.parent.name
        if pkg_name == "generic":
            continue
        mod_name = f"hydroagent.adapters.{pkg_name}.adapter"
        try:
            if mod_name in sys.modules:
                mod = importlib.reload(sys.modules[mod_name])
            else:
                mod = importlib.import_module(mod_name)
            cls = getattr(mod, "Adapter", None)
            if cls and issubclass(cls, PackageAdapter) and cls is not PackageAdapter:
                _adapters.append(cls())
                logger.info(
                    "[adapters] discovered: %s (priority=%d)", pkg_name, cls.priority
                )
        except Exception as e:
            logger.warning("[adapters] load failed: %s -- %s", pkg_name, e)

    # ── 2. External plugins from plugin registry ──────────────────────────────
    try:
        from hydroagent.utils.plugin_registry import PluginRegistry
        registry = PluginRegistry(workspace)
        for plugin in registry.list_plugins():
            if not plugin.get("enabled", True):
                continue
            if plugin.get("type") in ("local_dir", "single_file"):
                _load_external_adapter(plugin)
    except Exception as exc:
        logger.debug("[adapters] plugin registry scan skipped: %s", exc)

    _adapters.sort(key=lambda a: (-a.priority, a.name))
    logger.info("[adapters] total loaded: %d", len(_adapters))


def _load_external_adapter(plugin: dict) -> None:
    """Load a PackageAdapter from an external plugin entry.

    Adds the plugin's directory to sys.path so the underlying package can be
    imported, then loads the Adapter class from the declared adapter_path.
    """
    import importlib.util

    name = plugin.get("name", "<unknown>")
    adapter_path_str = plugin.get("adapter_path", "")
    if not adapter_path_str:
        logger.debug("[adapters] external plugin '%s' has no adapter_path, skipping", name)
        return

    adapter_path = Path(adapter_path_str)
    if not adapter_path.exists():
        logger.warning("[adapters] external adapter not found: %s", adapter_path)
        return

    # Add the plugin's root directory to sys.path (idempotent)
    pkg_dir = str(adapter_path.parent)
    if pkg_dir not in sys.path:
        sys.path.insert(0, pkg_dir)

    # Also add the declared package path for packages in a sub-directory
    pkg_path_str = plugin.get("path", "")
    if pkg_path_str:
        pkg_root = str(Path(pkg_path_str))
        if pkg_root not in sys.path:
            sys.path.insert(0, pkg_root)

    mod_key = f"_hydroagent_plugin_{name}_adapter"
    try:
        spec = importlib.util.spec_from_file_location(mod_key, adapter_path)
        if spec is None or spec.loader is None:
            logger.warning("[adapters] cannot load spec for external plugin: %s", adapter_path)
            return
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_key] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        cls = getattr(mod, "Adapter", None)
        if cls and issubclass(cls, PackageAdapter) and cls is not PackageAdapter:
            _adapters.append(cls())
            logger.info(
                "[adapters] external plugin loaded: %s (priority=%d)", name, cls.priority
            )
        else:
            logger.warning("[adapters] no valid Adapter class in external plugin: %s", adapter_path)
    except Exception as exc:
        logger.warning("[adapters] failed to load external plugin '%s': %s", name, exc)


def get_adapter(data_source: str, model_name: str) -> PackageAdapter:
    """Return the highest-priority adapter that can handle this data_source/model_name.

    Falls back to GenericAdapter if no specific adapter matches.
    """
    for a in _adapters:
        if a.can_handle(data_source, model_name):
            return a
    from .generic.adapter import Adapter as GenericAdapter

    return GenericAdapter()


def get_all_skill_docs() -> list[str]:
    """Collect skill docs from all loaded adapters (for system prompt injection)."""
    docs: list[str] = []
    for a in _adapters:
        docs.extend(a.get_skill_docs())
    return docs


reload_adapters()
