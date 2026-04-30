"""
Meta-tool: register a single .py file's public functions as HydroAgent tools.

The file does not need to contain an Adapter class — any public function
(not starting with _) will be discovered and registered at PRIORITY_DYNAMIC.
Registration survives process restarts via the plugin registry.
"""

from __future__ import annotations

import inspect
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def add_local_tool(
    path: str,
    name: str | None = None,
    description: str = "",
    _workspace=None,
    _cfg=None,
) -> dict:
    """Register all public functions in a .py file as HydroAgent tools.

    The functions become immediately callable by the Agent.  Registration is
    persisted in the plugin registry so they survive restarts.

    Args:
        path: Absolute or relative path to a .py file.
        name: Plugin name used in the registry (default: filename stem).
        description: What the file / its functions do.

    Returns:
        {"success": True, "plugin_name": ..., "registered_tools": [...]}
    """
    resolved = Path(path).expanduser().resolve()

    if not resolved.exists():
        return {"success": False, "error": f"File not found: {resolved}"}
    if not resolved.is_file() or resolved.suffix != ".py":
        return {"success": False, "error": f"Expected a .py file, got: {resolved}"}

    plugin_name = name or resolved.stem

    # Persist in registry
    from hydroagent.utils.plugin_registry import PluginRegistry
    registry = PluginRegistry(Path(_workspace) if _workspace else None)
    entry = registry.make_entry(
        name=plugin_name,
        path=str(resolved),
        plugin_type="single_file",
        adapter_path="",
        description=description,
    )
    registry.add(entry)

    # Dynamically load the file and register its functions right now
    import importlib.util
    import sys

    pkg_dir = str(resolved.parent)
    if pkg_dir not in sys.path:
        sys.path.insert(0, pkg_dir)

    mod_key = f"_hydroagent_plugin_{plugin_name}_tool"
    registered: list[str] = []
    errors: list[str] = []

    try:
        spec = importlib.util.spec_from_file_location(mod_key, resolved)
        if spec is None or spec.loader is None:
            return {"success": False, "error": f"Cannot load spec for {resolved}"}
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_key] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]

        from hydroagent.tools import _register_tool, PRIORITY_DYNAMIC, reload_tools
        # Force reload so the new functions appear in schema
        from hydroagent.tools import _TOOLS, _TOOL_META
        for fn_name, obj in inspect.getmembers(mod, inspect.isfunction):
            if fn_name.startswith("_"):
                continue
            if obj.__module__ != mod.__name__:
                continue
            _register_tool(fn_name, obj, source=str(resolved), priority=PRIORITY_DYNAMIC)
            registered.append(fn_name)
    except Exception as exc:
        errors.append(str(exc))
        logger.warning("[add_local_tool] failed to load %s: %s", resolved, exc)

    if not registered and errors:
        return {"success": False, "error": errors[0], "plugin_name": plugin_name}

    logger.info("[add_local_tool] registered %d function(s) from %s", len(registered), resolved)

    return {
        "success": True,
        "plugin_name": plugin_name,
        "plugin_type": "single_file",
        "path": str(resolved),
        "registered_tools": registered,
        "errors": errors,
        "next_steps": [
            f"Tools {registered} are now available to the Agent.",
            "They persist across restarts (registered in plugins.json).",
        ],
    }
