"""
Author: HydroClaw Team
Date: 2026-03-06
Description: Meta-tool - LLM generates a new Skill package (skill.md + tool .py)
             that is auto-discovered and immediately available.
"""

import ast
import inspect
import logging
import re
import subprocess
import sys
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

## CRITICAL: Only use APIs you are certain exist.
- If `example_usage` is provided, follow it exactly — do NOT invent function names or module paths.
- If no `example_usage` is provided and you are unsure of an API, implement a safe stub that
  returns `{"error": "API not verified — inspect the package first", "success": False}` and
  add a comment `# TODO: verify import path before use`.
- NEVER hallucinate import paths like `from package.submodule import func` unless you are
  100% certain the path exists.

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
        skill_name: Snake_case name, e.g. "spotpy_mcmc". If this call returns an error saying
            the name already exists, you MUST immediately retry with a different name
            (e.g. append a descriptive suffix like "_custom" or "_v2"). Never give up after
            one failure — always retry with a unique name.
        description: What the skill should do, what package it wraps, expected inputs/outputs
        package_name: Python package to wrap, e.g. "spotpy", "hydroeval". LLM generates proper import code
        example_usage: Optional example of how the underlying package API works

    Returns:
        {"skill_name": str, "skill_dir": str, "tool_name": str, "success": bool}
    """
    if _llm is None:
        return {"error": "LLM client required for skill creation", "success": False}

    # Semantic deduplication: warn if a similar tool already exists.
    # Skip check when caller explicitly confirms they want a duplicate.
    _confirmed_duplicate = "confirm_duplicate=True" in description or "confirm_duplicate" in description
    similar = [] if _confirmed_duplicate else _find_similar_tools(skill_name, description)
    if similar:
        names = [s["name"] for s in similar]
        return {
            "warning": "similar_tool_exists",
            "message": (
                f"Found {len(similar)} existing tool(s) with similar functionality: {names}. "
                "Consider using one of these instead of creating a duplicate. "
                "If you truly need a new skill, call create_skill again with "
                "confirm_duplicate=True (add it to description) to proceed anyway."
            ),
            "similar_tools": similar,
            "success": False,
        }

    # Validate skill_name
    if not skill_name.replace("_", "").isalnum() or skill_name.startswith("_"):
        return {
            "error": f"Invalid skill name '{skill_name}': must be alphanumeric with underscores, not starting with '_'",
            "success": False,
        }

    # Check if skill already exists — use state to decide what to do
    from hydroclaw.skill_states import SkillStateManager
    skills_dir = Path(__file__).parent.parent / "skills"
    state_mgr = SkillStateManager(skills_dir)
    skill_dir = skills_dir / skill_name

    if skill_dir.exists():
        existing_py = skill_dir / f"{skill_name}.py"
        if not existing_py.exists():
            return {
                "error": f"Skill directory '{skill_name}' exists but has no tool .py. Choose a different name.",
                "success": False,
            }

        status = state_mgr.get_status(skill_name)

        import shutil

        if status == "good":
            # Verified working skill — refuse overwrite, agent should just call it
            return {
                "error": (
                    f"Skill '{skill_name}' already exists and is verified [good] "
                    f"({state_mgr._states.get(skill_name, {}).get('success_count', 0)} successful uses). "
                    f"Call it directly instead of recreating. "
                    f"If you need different functionality, use a different skill_name."
                ),
                "existing_skill": skill_name,
                "status": "good",
                "success": False,
            }

        # bad or unverified: auto-overwrite and rebuild.
        # - bad: known broken, must rebuild
        # - unverified: never confirmed working, safe to rebuild with fresh code
        if status == "bad":
            last_err = state_mgr.get_last_error(skill_name) or "unknown"
            logger.warning(f"Skill '{skill_name}' is [bad] (last error: {last_err}). Rebuilding.")
        else:
            # Run load test first: if it actually loads fine, keep it and return early
            load_check = subprocess.run(
                [sys.executable, "-c",
                 f"import importlib.util; "
                 f"spec = importlib.util.spec_from_file_location('_chk', {repr(str(existing_py))}); "
                 f"mod = importlib.util.module_from_spec(spec); "
                 f"spec.loader.exec_module(mod)"],
                capture_output=True, text=True, timeout=10,
            )
            if load_check.returncode != 0:
                state_mgr.mark_bad(skill_name, load_check.stderr)
                logger.warning(f"Skill '{skill_name}' [unverified] fails load test. Marking bad and rebuilding.")
            else:
                logger.info(f"Skill '{skill_name}' is [unverified] but loads correctly. Rebuilding with fresh code.")

        shutil.rmtree(skill_dir, ignore_errors=True)

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

    # Validate imports in the generated code before writing to disk
    import_errors = _validate_imports(tool_code)
    if import_errors:
        return {
            "error": (
                f"Generated code contains imports that cannot be resolved: {import_errors}. "
                "The LLM hallucinated an API that does not exist. "
                "To fix: use inspect_dir or read_file to find the correct import path, "
                "then call create_skill again with example_usage showing the real API."
            ),
            "failed_imports": import_errors,
            "success": False,
        }

    # Write files
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "__init__.py").write_text("", encoding="utf-8")
    # Mark as dynamically generated so tool registry assigns PRIORITY_DYNAMIC (5)
    (skill_dir / ".dynamic").write_text("", encoding="utf-8")
    tool_file = skill_dir / f"{skill_name}.py"
    tool_file.write_text(tool_code, encoding="utf-8")
    (skill_dir / "skill.md").write_text(skill_md_content, encoding="utf-8")

    logger.info(f"Created skill package: {skill_dir}")

    # Full module load test: catches NameErrors, AttributeErrors, and other
    # runtime errors that _validate_imports() cannot detect from AST alone.
    load_test = subprocess.run(
        [sys.executable, "-c",
         f"import importlib.util; "
         f"spec = importlib.util.spec_from_file_location('_skill_test', {repr(str(tool_file))}); "
         f"mod = importlib.util.module_from_spec(spec); "
         f"spec.loader.exec_module(mod)"],
        capture_output=True, text=True, timeout=15,
    )
    if load_test.returncode != 0:
        import shutil
        shutil.rmtree(skill_dir, ignore_errors=True)
        err_msg = (load_test.stderr or load_test.stdout or "unknown error").strip()
        logger.warning(f"Skill `{skill_name}` module load test failed: {err_msg}")

        # Search Error KB for known solutions
        from hydroclaw.error_kb import ErrorKnowledgeBase
        kb = ErrorKnowledgeBase()
        kb_hints = kb.format_hints(err_msg)
        kb.record_fix(err_msg, solution="", resolved=False)  # log as unresolved

        return {
            "error": f"Generated module fails to load: {err_msg[:400]}",
            "known_solutions": kb_hints or "No matching pattern in ErrorKB — use your judgment.",
            "instruction": (
                "Fix the error based on known_solutions above, then call create_skill again "
                "with corrected code in example_usage. "
                "After fixing successfully, call record_error_solution to save the fix."
            ),
            "generated_code_snippet": tool_code[:500],
            "success": False,
        }

    # Register skill state: starts as unverified, promoted to good after use
    state_mgr.mark_created(skill_name)

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


def _find_similar_tools(skill_name: str, description: str,
                        threshold: float = 0.5) -> list[dict]:
    """Return existing tools that appear to overlap with the requested functionality.

    Uses *query recall* (|intersection| / |query|) rather than Jaccard, because
    the candidate docstrings are much longer than the query — Jaccard penalises
    length asymmetry too harshly.  Recall answers: "how much of what the user
    asked for is already covered by this tool?"

    Threshold 0.5 means at least half the meaningful query words appear in the
    candidate tool's description.

    Returns list of {"name": str, "similarity": float, "source": str}, sorted
    descending. Empty list means no duplicates found.
    """
    try:
        from hydroclaw.tools import discover_tools, _TOOL_META
    except ImportError:
        return []

    query_words = _word_bag(skill_name + " " + description)
    if not query_words:
        return []

    results = []
    tools = discover_tools()
    for name, fn in tools.items():
        if name == skill_name:
            continue
        doc = inspect.getdoc(fn) or ""
        hint = getattr(fn, "__agent_hint__", "") or ""
        candidate_words = _word_bag(name + " " + doc + " " + hint)
        sim = _query_recall(query_words, candidate_words)
        if sim >= threshold:
            meta = _TOOL_META.get(name, {})
            results.append({
                "name": name,
                "similarity": round(sim, 3),
                "source": meta.get("source", "unknown"),
            })

    results.sort(key=lambda x: -x["similarity"])
    return results[:5]


def _word_bag(text: str) -> set[str]:
    """Tokenise text into a lowercase word set, filtering stop words."""
    import re
    _STOP = {"a", "an", "the", "to", "of", "for", "in", "on", "at", "by",
             "is", "are", "and", "or", "not", "with", "from", "this", "that",
             "be", "do", "use", "used", "using", "call", "calls", "return",
             "returns", "it", "its", "if", "when", "then", "as", "into"}
    tokens = re.findall(r"[a-z][a-z0-9_]{1,}", text.lower())
    return {t for t in tokens if t not in _STOP and len(t) > 2}


def _query_recall(query: set, candidate: set) -> float:
    """Fraction of query words that appear in candidate."""
    if not query:
        return 0.0
    return len(query & candidate) / len(query)


def _validate_imports(code: str) -> list[str]:
    """Extract all import statements from the code and test them in a subprocess.

    Returns a list of import strings that fail to import, empty list if all pass.
    Skips imports of stdlib and the project's own hydroclaw package.
    """
    SKIP_PREFIXES = ("hydroclaw", "pathlib", "logging", "typing", "json", "os",
                     "sys", "re", "math", "datetime", "collections", "itertools",
                     "functools", "io", "abc", "copy", "time", "warnings")
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []  # syntax errors are caught elsewhere

    imports_to_test = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if not any(alias.name.startswith(p) for p in SKIP_PREFIXES):
                    imports_to_test.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module and not any(node.module.startswith(p) for p in SKIP_PREFIXES):
                names = ", ".join(a.name for a in node.names)
                imports_to_test.append(f"from {node.module} import {names}")

    if not imports_to_test:
        return []

    failed = []
    for stmt in imports_to_test:
        result = subprocess.run(
            [sys.executable, "-c", stmt],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            failed.append(stmt)

    return failed


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
