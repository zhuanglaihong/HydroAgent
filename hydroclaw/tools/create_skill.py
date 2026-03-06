"""
Author: HydroClaw Team
Date: 2026-03-06
Description: Meta-tool - LLM generates a new Skill package (skill.md + tool .py)
             that is auto-discovered and immediately available.
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_SKILL_TOOL_PROMPT = '''You are writing a HydroClaw tool module for a new Skill package.
A tool is a single Python file containing one public function that gets auto-discovered as an LLM-callable tool.

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

Output ONLY the complete Python file content wrapped in ```python ... ``` blocks.'''

_SKILL_MD_PROMPT = '''You are writing a skill.md guide for a new HydroClaw Skill.

The skill.md must start with YAML frontmatter followed by markdown content.

Format:
```
---
name: <Human-readable skill name>
description: <One-line description in Chinese or English>
keywords: [kw1, kw2, kw3, ...]
tools: [tool_function_name]
when_to_use: <Short hint for when to use this skill>
---

## <Skill Name> 工作流

<Detailed usage guide: when to use, step-by-step workflow, parameters, notes>
```

Output ONLY the complete skill.md content (including the --- frontmatter delimiters).'''


def create_skill(
    skill_name: str,
    description: str,
    package_name: str | None = None,
    example_usage: str | None = None,
    _workspace: Path | None = None,
    _llm: object | None = None,
) -> dict:
    """Create a new Skill package (skill.md + tool .py) that is immediately available.

    Generates a complete Skill directory under hydroclaw/skills/<skill_name>/ with:
    - skill.md: Usage guide and workflow documentation with YAML frontmatter
    - <skill_name>.py: The executable tool function

    The new skill and its tool are auto-discovered and available immediately.

    Args:
        skill_name: Snake_case name for the skill and tool function, e.g. "spotpy_mcmc"
        description: What the skill should do, what package it wraps, expected inputs/outputs
        package_name: Python package to wrap, e.g. "spotpy", "hydroeval". LLM generates proper import code
        example_usage: Optional example of how the underlying package API works

    Returns:
        {"skill_name": str, "skill_dir": str, "tool_name": str, "success": bool}
    """
    if _llm is None:
        return {"error": "LLM client required for skill creation", "success": False}

    # Validate skill_name
    if not skill_name.replace("_", "").isalnum() or skill_name.startswith("_"):
        return {
            "error": f"Invalid skill name '{skill_name}': must be alphanumeric with underscores, not starting with '_'",
            "success": False,
        }

    # Check if skill already exists
    skills_dir = Path(__file__).parent.parent / "skills"
    skill_dir = skills_dir / skill_name
    if skill_dir.exists():
        return {
            "error": f"Skill '{skill_name}' already exists at {skill_dir}. Delete it first or choose a different name.",
            "success": False,
        }

    # Build user message
    user_msg = f"Create a skill named `{skill_name}`.\n\nDescription: {description}\n"
    if package_name:
        user_msg += f"Package to wrap: {package_name}\n"
    if example_usage:
        user_msg += f"\nExample API usage:\n```python\n{example_usage}\n```\n"

    # Generate tool .py
    tool_response = _llm.chat([
        {"role": "system", "content": _SKILL_TOOL_PROMPT},
        {"role": "user", "content": user_msg},
    ])
    tool_code = _extract_code(tool_response.text)
    if not tool_code:
        return {"error": "LLM failed to generate valid Python code for the tool", "success": False}

    if f"def {skill_name}(" not in tool_code:
        return {
            "error": f"Generated code does not contain function `{skill_name}()`. LLM may have used a different name.",
            "generated_code": tool_code,
            "success": False,
        }

    # Generate skill.md
    md_response = _llm.chat([
        {"role": "system", "content": _SKILL_MD_PROMPT},
        {"role": "user", "content": user_msg},
    ])
    skill_md_content = _extract_markdown(md_response.text)
    if not skill_md_content:
        skill_md_content = _default_skill_md(skill_name, description)

    # Write files
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "__init__.py").write_text("", encoding="utf-8")
    (skill_dir / f"{skill_name}.py").write_text(tool_code, encoding="utf-8")
    (skill_dir / "skill.md").write_text(skill_md_content, encoding="utf-8")

    logger.info(f"Created skill package: {skill_dir}")

    # Hot-reload tools and skill registry
    from hydroclaw.tools import reload_tools
    tools = reload_tools()

    if skill_name not in tools:
        return {
            "error": f"Skill files written but `{skill_name}` was not discovered. Check the file for syntax errors.",
            "skill_dir": str(skill_dir),
            "success": False,
        }

    logger.info(f"Skill `{skill_name}` created and registered successfully")
    return {
        "skill_name": skill_name,
        "skill_dir": str(skill_dir),
        "tool_name": skill_name,
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


def _extract_markdown(text: str) -> str | None:
    """Extract skill.md content from LLM response.

    Looks for content starting with --- frontmatter or a markdown block.
    """
    # If response directly starts with frontmatter
    text = text.strip()
    if text.startswith("---"):
        return text

    # Try markdown code block
    matches = re.findall(r'```(?:markdown|md)?\s*\n(.*?)\n```', text, re.DOTALL)
    if matches:
        content = matches[0].strip()
        if content.startswith("---"):
            return content

    return None


def _default_skill_md(skill_name: str, description: str) -> str:
    """Generate a minimal skill.md if LLM fails to produce one."""
    return f"""---
name: {skill_name.replace('_', ' ').title()}
description: {description}
keywords: [{skill_name}]
tools: [{skill_name}]
when_to_use: {description}
---

## {skill_name.replace('_', ' ').title()} 工作流

{description}

### 执行步骤

1. 调用 `{skill_name}` 工具
2. 分析返回结果
3. 生成报告
"""
