"""
Adapter registry: auto-discovery, hot-reload, and routing.

Usage:
    from hydroclaw.adapters import get_adapter, get_all_skill_docs, reload_adapters

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


def reload_adapters():
    """Re-scan adapters/ and load all adapter.py files.

    Called once at module import. Also call this after create_adapter generates
    a new adapter skeleton so it takes effect without restarting the process.
    """
    global _adapters
    _adapters.clear()

    adapters_dir = Path(__file__).parent
    for adapter_py in sorted(adapters_dir.glob("*/adapter.py")):
        pkg_name = adapter_py.parent.name
        if pkg_name == "generic":
            continue
        mod_name = f"hydroclaw.adapters.{pkg_name}.adapter"
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

    _adapters.sort(key=lambda a: (-a.priority, a.name))
    logger.info("[adapters] total loaded: %d", len(_adapters))


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
