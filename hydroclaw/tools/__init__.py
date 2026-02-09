"""
Author: HydroClaw Team
Date: 2026-02-08
Description: Auto-discovery of tool functions and schema generation.
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
    """Scan all modules in tools/ and register public functions as tools.

    Functions with names starting with '_' are skipped.
    Each public function becomes a tool with its function name.
    """
    if _TOOLS:
        return _TOOLS

    package_dir = Path(__file__).parent

    for module_info in pkgutil.iter_modules([str(package_dir)]):
        if module_info.name.startswith("_"):
            continue
        try:
            module = importlib.import_module(f"hydroclaw.tools.{module_info.name}")
            for name, obj in inspect.getmembers(module, inspect.isfunction):
                if name.startswith("_"):
                    continue
                # Only register functions defined in the module (not imports)
                if obj.__module__ == module.__name__:
                    _TOOLS[name] = obj
                    logger.debug(f"Registered tool: {name}")
        except Exception as e:
            logger.warning(f"Failed to load tool module {module_info.name}: {e}")

    logger.info(f"Discovered {len(_TOOLS)} tools: {list(_TOOLS.keys())}")
    return _TOOLS


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


def _parse_docstring(doc: str) -> tuple[str, dict[str, str]]:
    """Parse docstring into description and parameter docs."""
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
            # Parse "param_name: description" or "param_name (type): description"
            import re
            match = re.match(r"(\w+)(?:\s*\([^)]*\))?\s*:\s*(.*)", stripped)
            if match:
                param_docs[match.group(1)] = match.group(2).strip()
        elif not in_args and not stripped.startswith("---"):
            description_lines.append(stripped)

    description = " ".join(description_lines).strip()
    return description, param_docs


def _python_type_to_json(python_type) -> str:
    """Convert Python type hint to JSON Schema type."""
    import typing
    origin = getattr(python_type, "__origin__", None)

    if origin is list or origin is typing.List:
        return "array"
    if origin is dict or origin is typing.Dict:
        return "object"
    if origin is typing.Union:
        # Handle Optional[X] = Union[X, None]
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
