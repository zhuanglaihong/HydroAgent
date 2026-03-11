"""
Author: HydroClaw Team
Date: 2026-02-08
Description: Auto-discovery of tool functions and schema generation.
             Scans both tools/*.py (core tools) and skills/*/*.py (skill tools).
"""

import importlib
import inspect
import logging
import pkgutil
from pathlib import Path
from typing import Any, Callable, get_type_hints

logger = logging.getLogger(__name__)

# Registry: {tool_name: function}
_TOOLS: dict[str, Callable] = {}


def discover_tools() -> dict[str, Callable]:
    """Scan tool modules in tools/ and skills/*/ and register public functions.

    Functions with names starting with '_' are skipped.
    Scans two locations:
      1. tools/*.py  — core shared tools (validate, simulate, create_skill, etc.)
      2. skills/*/*.py — skill-specific tools (calibrate_model, evaluate_model, etc.)
    """
    if _TOOLS:
        return _TOOLS

    package_dir = Path(__file__).parent

    # 1. Scan tools/*.py
    _scan_dir(package_dir, "hydroclaw.tools")

    # 2. Scan skills/*/*.py
    skills_dir = package_dir.parent / "skills"
    if skills_dir.exists():
        for skill_dir in sorted(skills_dir.iterdir()):
            if skill_dir.is_dir() and not skill_dir.name.startswith("_"):
                _scan_dir(skill_dir, f"hydroclaw.skills.{skill_dir.name}")

    logger.info(f"Discovered {len(_TOOLS)} tools: {list(_TOOLS.keys())}")
    return _TOOLS


def _scan_dir(dir_path: Path, module_prefix: str):
    """Scan a directory for tool modules and register their public functions."""
    for module_info in pkgutil.iter_modules([str(dir_path)]):
        if module_info.name.startswith("_"):
            continue
        module_name = f"{module_prefix}.{module_info.name}"
        try:
            module = importlib.import_module(module_name)
            for name, obj in inspect.getmembers(module, inspect.isfunction):
                if name.startswith("_"):
                    continue
                # Only register functions defined in this module (not imports)
                if obj.__module__ == module.__name__:
                    _TOOLS[name] = obj
                    logger.debug(f"Registered tool: {name} (from {module_name})")
        except Exception as e:
            logger.warning(f"Failed to load tool module {module_name}: {e}")


def reload_tools() -> dict[str, Callable]:
    """Clear cache and re-discover all tools. Used after creating new skill/tool files."""
    _TOOLS.clear()
    # Clear Python's module cache for tools and skills
    import sys
    to_remove = [
        k for k in sys.modules
        if k.startswith("hydroclaw.tools.") or k.startswith("hydroclaw.skills.")
        if k not in ("hydroclaw.tools", "hydroclaw.skills")
    ]
    for k in to_remove:
        del sys.modules[k]
    return discover_tools()


def get_tool_schemas() -> list[dict[str, Any]]:
    """Generate OpenAI function calling schemas for all registered tools."""
    tools = discover_tools()
    schemas = []
    for name, fn in tools.items():
        schema = fn_to_schema(fn)
        if schema:
            schemas.append(schema)
    return schemas


def fn_to_schema(fn: Callable) -> dict[str, Any] | None:
    """Convert a function's signature + docstring to OpenAI tool schema.

    Parameters starting with '_' are treated as internal (injected at runtime)
    and excluded from the schema.
    """
    try:
        sig = inspect.signature(fn)
        hints = get_type_hints(fn)
        doc = inspect.getdoc(fn) or ""

        # Split docstring into description and args
        description, param_docs = _parse_docstring(doc)

        # Append __agent_hint__ if defined — operational call-site knowledge
        # (parameter gotchas, output→input relationships, common mistakes).
        # Kept separate from docstring so it survives _parse_docstring truncation.
        hint = getattr(fn, "__agent_hint__", None)
        if hint:
            description = description.rstrip(".") + ". " + hint.strip()

        properties = {}
        required = []

        for param_name, param in sig.parameters.items():
            # Skip internal parameters (prefixed with _)
            if param_name.startswith("_"):
                continue

            param_type = hints.get(param_name, Any)
            json_type = _python_type_to_json(param_type)
            param_desc = param_docs.get(param_name, "")

            prop: dict[str, Any] = {"type": json_type}
            if param_desc:
                prop["description"] = param_desc

            # Handle default values
            if param.default is inspect.Parameter.empty:
                required.append(param_name)
            elif param.default is not None:
                prop["default"] = param.default

            # Handle list/array types
            if json_type == "array":
                item_type = _get_list_item_type(param_type)
                if item_type:
                    prop["items"] = {"type": item_type}

            properties[param_name] = prop

        schema = {
            "type": "function",
            "function": {
                "name": fn.__name__,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }
        return schema

    except Exception as e:
        logger.warning(f"Failed to generate schema for {fn.__name__}: {e}")
        return None


_PARAM_DESC_MAX = 100  # max chars for each parameter description in schema

def _parse_docstring(doc: str) -> tuple[str, dict[str, str]]:
    """Parse docstring into description and parameter docs.

    Schema-size policy:
    - Function description: first sentence only (up to first '. ' or 120 chars)
    - Parameter descriptions: truncated to _PARAM_DESC_MAX chars
    Full docstrings remain in source for developer reference.
    """
    lines = doc.strip().split("\n")
    description_lines = []
    param_docs: dict[str, str] = {}
    in_args = False

    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith("args:"):
            in_args = True
            continue
        if stripped.lower().startswith("returns:"):
            in_args = False
            continue
        if in_args:
            import re
            match = re.match(r"(\w+)(?:\s*\([^)]*\))?\s*:\s*(.*)", stripped)
            if match:
                desc = match.group(2).strip()
                # Truncate long param descriptions to keep schema lean
                if len(desc) > _PARAM_DESC_MAX:
                    desc = desc[:_PARAM_DESC_MAX - 3] + "..."
                param_docs[match.group(1)] = desc
        elif not in_args and not stripped.startswith("---"):
            description_lines.append(stripped)

    full_desc = " ".join(description_lines).strip()
    # Keep only the first sentence for the schema; full text stays in source
    dot_idx = full_desc.find(". ")
    if 0 < dot_idx < 120:
        description = full_desc[: dot_idx + 1]
    else:
        description = full_desc[:120]
    return description, param_docs


def _python_type_to_json(python_type) -> str:
    """Convert Python type hint to JSON Schema type."""
    import types
    import typing
    origin = getattr(python_type, "__origin__", None)

    if origin is list or origin is typing.List:
        return "array"
    if origin is dict or origin is typing.Dict:
        return "object"
    if origin is typing.Union:
        args = python_type.__args__
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return _python_type_to_json(non_none[0])
    # Handle Python 3.10+ X | Y syntax (types.UnionType)
    if isinstance(python_type, types.UnionType):
        args = python_type.__args__
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return _python_type_to_json(non_none[0])

    if python_type is str:
        return "string"
    if python_type is int:
        return "integer"
    if python_type is float:
        return "number"
    if python_type is bool:
        return "boolean"

    return "string"


def _get_list_item_type(python_type) -> str | None:
    """Get the item type of a list type hint."""
    args = getattr(python_type, "__args__", None)
    if args and len(args) > 0:
        return _python_type_to_json(args[0])
    return "string"
