"""
Author: HydroClaw Team
Date: 2026-02-09
Description: Meta-tool - LLM generates new tool wrapper scripts that are auto-discovered.
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_TOOL_TEMPLATE_PROMPT = '''You are writing a HydroClaw tool module. A tool is a single Python file in `hydroclaw/tools/` containing one public function that gets auto-discovered as an LLM-callable tool.

## Rules (MUST follow exactly):

1. The file must have ONE public function (the tool entry point). Helper functions must start with `_`.
2. The public function MUST have:
   - Full type hints on ALL parameters and return type
   - A Google-style docstring with `Args:` and `Returns:` sections
   - Return a `dict` with at least a `"success"` key
3. Parameters starting with `_` are injected by the agent at runtime (hidden from LLM):
   - `_workspace: Path | None = None` — working directory
   - `_cfg: dict | None = None` — global config
   - `_llm: object | None = None` — LLM client (only if the tool needs LLM)
4. Import external packages inside the function body (lazy import) to avoid startup errors.
5. Use `logging.getLogger(__name__)` for logging.
6. Include the standard file header comment.
7. Handle errors gracefully — return `{"error": "...", "success": False}` instead of raising.

## Example tool (for reference):

```python
"""
Author: HydroClaw Team
Date: 2026-02-09
Description: Brief description of what this tool does.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def my_tool_name(
    basin_ids: list[str],
    some_param: str = "default",
    optional_param: int | None = None,
    _workspace: Path | None = None,
    _cfg: dict | None = None,
) -> dict:
    """One-line description of what this tool does.

    More detailed explanation if needed.

    Args:
        basin_ids: CAMELS basin ID list
        some_param: Description of this parameter
        optional_param: Description of optional parameter

    Returns:
        {"result_key": ..., "success": bool}
    """
    try:
        # Lazy import external packages
        from some_package import some_function

        result = some_function(basin_ids, some_param)

        return {"result": result, "success": True}

    except Exception as e:
        logger.error(f"my_tool_name failed: {e}", exc_info=True)
        return {"error": str(e), "success": False}
```

Now generate the tool based on the user's requirements below.
Output ONLY the complete Python file content wrapped in ```python ... ``` blocks.'''


def create_tool(
    tool_name: str,
    description: str,
    package_name: str | None = None,
    example_usage: str | None = None,
    _workspace: Path | None = None,
    _llm: object | None = None,
) -> dict:
    """Create a new tool wrapper script that will be auto-discovered by HydroClaw.

    The LLM generates a complete tool module based on your description. The new tool
    becomes immediately available for use in the current session.

    Args:
        tool_name: Snake_case name for the tool function, e.g. "sensitivity_analysis"
        description: What the tool should do, what package it wraps, expected inputs/outputs
        package_name: Python package to wrap, e.g. "hydromodel", "spotpy". The LLM will generate proper import code
        example_usage: Optional example of how the underlying package API works

    Returns:
        {"tool_name": str, "file_path": str, "schema": dict, "success": bool}
    """
    if _llm is None:
        return {"error": "LLM client required for tool creation", "success": False}

    # Validate tool_name
    if not tool_name.isidentifier() or tool_name.startswith("_"):
        return {"error": f"Invalid tool name '{tool_name}': must be a valid Python identifier and not start with '_'", "success": False}

    # Check if tool already exists
    tools_dir = Path(__file__).parent
    target_file = tools_dir / f"{tool_name}.py"
    if target_file.exists():
        return {"error": f"Tool file '{tool_name}.py' already exists. Delete it first or choose a different name.", "success": False}

    # Build prompt for LLM
    user_msg = f"Create a tool named `{tool_name}`.\n\n"
    user_msg += f"Description: {description}\n"
    if package_name:
        user_msg += f"Package to wrap: {package_name}\n"
    if example_usage:
        user_msg += f"\nExample API usage:\n```python\n{example_usage}\n```\n"

    response = _llm.chat([
        {"role": "system", "content": _TOOL_TEMPLATE_PROMPT},
        {"role": "user", "content": user_msg},
    ])

    # Extract code
    code = _extract_code(response.text)
    if not code:
        return {"error": "LLM failed to generate valid Python code", "success": False}

    # Validate: must contain the tool function
    if f"def {tool_name}(" not in code:
        return {
            "error": f"Generated code does not contain function `{tool_name}()`. LLM may have used a different name.",
            "generated_code": code,
            "success": False,
        }

    # Write file
    target_file.write_text(code, encoding="utf-8")
    logger.info(f"Created tool file: {target_file}")

    # Hot-reload tools so the new tool is immediately available
    from hydroclaw.tools import reload_tools, get_tool_schemas
    tools = reload_tools()

    if tool_name not in tools:
        return {
            "error": f"Tool file written but `{tool_name}` was not discovered. Check the file for syntax errors.",
            "file_path": str(target_file),
            "success": False,
        }

    # Get the schema for the new tool
    from hydroclaw.tools import fn_to_schema
    schema = fn_to_schema(tools[tool_name])

    logger.info(f"Tool `{tool_name}` created and registered successfully")
    return {
        "tool_name": tool_name,
        "file_path": str(target_file),
        "schema": schema,
        "total_tools": len(tools),
        "success": True,
    }


def _extract_code(text: str) -> str | None:
    """Extract Python code from LLM response."""
    matches = re.findall(r'```python\s*\n(.*?)\n```', text, re.DOTALL)
    if matches:
        return matches[0].strip()
    matches = re.findall(r'```\s*\n(.*?)\n```', text, re.DOTALL)
    if matches:
        return matches[0].strip()
    return None
