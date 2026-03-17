"""
Author: HydroClaw Team
Date: 2026-03-15
Description: Fetch package metadata from PyPI + inspect its API, then use LLM to
             generate a HydromodelAdapter-style implementation. Calls create_adapter
             internally but goes further: attempts to generate working method bodies,
             not just NotImplementedError stubs.
"""

import importlib
import inspect
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ── LLM prompt ────────────────────────────────────────────────────────────────

_ADAPTER_IMPL_PROMPT = """\
You are implementing a HydroClaw PackageAdapter for the Python package `{package_name}`.

## PackageAdapter interface (4 methods to implement):

```python
def calibrate(self, workspace: Path, **kw) -> dict:
    # kw keys: basin_ids, model_name, algorithm, train_period, test_period,
    #          algorithm_params, output_dir, _cfg, _ui
    # Must return: {"success": bool, "calibration_dir": str, "best_params": dict, ...}

def evaluate(self, workspace: Path, **kw) -> dict:
    # kw keys: calibration_dir, eval_period, output_subdir, _workspace, _cfg
    # Must return: {"success": bool, "metrics": dict, "metrics_dir": str, ...}

def visualize(self, workspace: Path, **kw) -> dict:
    # kw keys: calibration_dir, plot_types, basin_ids, _workspace
    # Must return: {"plot_files": list, "plot_count": int}

def simulate(self, workspace: Path, **kw) -> dict:
    # kw keys: calibration_dir, sim_period, params
    # Must return: {"success": bool, "simulation_dir": str, ...}
```

## Package information:

**Package:** {package_name} {version}
**Description:** {description}

## Discovered public API (function signatures and docstrings):

{api_summary}

## Instructions:

1. Implement ONLY the methods that have a clear mapping to the package API above.
2. For methods with no clear mapping, use this pattern:
   ```python
   return {{"success": False, "message": "Not implemented for {package_name} -- use generate_code instead."}}
   ```
3. Import the package INSIDE the method body (lazy import), guarded by try/except ImportError.
4. NEVER hallucinate import paths. Only use APIs shown in the "Discovered public API" section.
5. Return dicts match the interface above (success, relevant fields).
6. Add `# AUTO-GENERATED` comment on lines that rely on the discovered API.
7. Handle exceptions: return {{"success": False, "error": str(e)}} on failure.

Output ONLY the Python code for the 4 method bodies (starting from `def calibrate`).
No class definition, no imports at module level — those are added automatically.
Wrap each method in ```python ... ```.
"""


def register_package(
    package_name: str,
    priority: int = 5,
    _workspace: Path | None = None,
    _cfg: dict | None = None,
    _llm=None,
) -> dict:
    """Inspect an installed package and generate a PackageAdapter for it.

    Fetches PyPI metadata, inspects the package's public API via importlib,
    then uses LLM to generate adapter method implementations (not just stubs).
    Calls create_adapter internally and reloads the adapter registry.

    Requires the package to already be installed. Call install_package first if needed.

    Args:
        package_name: Name of the installed Python package, e.g. "spotpy"
        priority: Adapter priority (default 5, lower than hydromodel's 10)

    Returns:
        {"adapter_file": str, "auto_implemented": list, "stubs_remaining": list,
         "skill_doc": str, "success": bool}
    """
    if _llm is None:
        return {"error": "LLM client required for register_package.", "success": False}

    package_name = package_name.strip().lower()

    # ── 1. Try to import the package ──────────────────────────────────────────
    try:
        pkg = importlib.import_module(package_name)
    except ImportError:
        return {
            "error": (
                f"Cannot import '{package_name}'. "
                "Make sure the package is installed. "
                "Call install_package first if needed."
            ),
            "success": False,
        }

    # ── 2. Inspect public API ─────────────────────────────────────────────────
    api_summary = _inspect_package_api(pkg, package_name)
    logger.info("[register_package] %s: found %d public symbols",
                package_name, api_summary.count("def "))

    # ── 3. Fetch PyPI metadata ────────────────────────────────────────────────
    pypi_meta = _fetch_pypi_metadata(package_name)
    version = pypi_meta.get("version", "unknown")
    description = pypi_meta.get("description", f"Python package: {package_name}")

    # ── 4. Ask LLM to generate adapter method implementations ─────────────────
    prompt = _ADAPTER_IMPL_PROMPT.format(
        package_name=package_name,
        version=version,
        description=description,
        api_summary=api_summary[:3000],  # cap to avoid huge prompts
    )

    logger.info("[register_package] asking LLM to generate adapter for %s", package_name)
    response = _llm.chat([
        {"role": "system", "content": "You are an expert Python developer writing HydroClaw adapter code."},
        {"role": "user", "content": prompt},
    ])

    method_bodies = _extract_method_bodies(response.text)

    # ── 5. Build the adapter.py content ──────────────────────────────────────
    adapter_name = package_name.replace("-", "_")
    adapter_content = _build_adapter_file(
        adapter_name=adapter_name,
        description=description,
        version=version,
        priority=priority,
        method_bodies=method_bodies,
    )

    # ── 6. Write files ────────────────────────────────────────────────────────
    adapters_dir = Path(__file__).parent.parent / "adapters"
    target_dir = adapters_dir / adapter_name
    skills_dir = target_dir / "skills"

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        skills_dir.mkdir(parents=True, exist_ok=True)

        init_file = target_dir / "__init__.py"
        if not init_file.exists():
            init_file.write_text("", encoding="utf-8")

        adapter_file = target_dir / "adapter.py"
        adapter_file.write_text(adapter_content, encoding="utf-8")

        # Skill doc
        skill_doc = _build_skill_doc(package_name, description, version, api_summary)
        skill_doc_file = skills_dir / "skill.md"
        skill_doc_file.write_text(skill_doc, encoding="utf-8")

        logger.info("[register_package] wrote adapter: %s", adapter_file)

    except Exception as e:
        return {"error": f"Failed to write adapter files: {e}", "success": False}

    # ── 7. Reload adapters ────────────────────────────────────────────────────
    reload_note = ""
    try:
        from hydroclaw.adapters import reload_adapters
        reload_adapters()
        reload_note = "Adapter registry reloaded -- new adapter is active."
    except Exception as e:
        reload_note = f"Warning: could not reload adapters automatically: {e}"

    implemented = [m for m in ("calibrate", "evaluate", "visualize", "simulate")
                   if m in method_bodies and "NotImplementedError" not in method_bodies.get(m, "")]
    stubs = [m for m in ("calibrate", "evaluate", "visualize", "simulate")
             if m not in implemented]

    return {
        "adapter_file": str(adapter_file),
        "skill_doc": str(skill_doc_file),
        "auto_implemented": implemented,
        "stubs_remaining": stubs,
        "package_version": version,
        "reload_note": reload_note,
        "success": True,
        "next_step": (
            f"Adapter for '{package_name}' is registered. "
            + (f"Methods still needing manual implementation: {stubs}. " if stubs else "")
            + "Test with a small calibration task."
        ),
    }


# ── helpers ───────────────────────────────────────────────────────────────────

def _inspect_package_api(pkg, package_name: str, max_symbols: int = 40) -> str:
    """Extract public function/class signatures from a package."""
    lines = []
    seen = 0

    def _add_fn(fn, prefix=""):
        nonlocal seen
        if seen >= max_symbols:
            return
        try:
            sig = inspect.signature(fn)
            doc = (inspect.getdoc(fn) or "").strip().split("\n")[0][:120]
            lines.append(f"{prefix}def {fn.__name__}{sig}")
            if doc:
                lines.append(f"    # {doc}")
            seen += 1
        except (ValueError, TypeError):
            pass

    # Top-level functions
    for name, obj in inspect.getmembers(pkg, inspect.isfunction):
        if not name.startswith("_") and obj.__module__.startswith(package_name):
            _add_fn(obj)

    # Public classes and their methods
    for cls_name, cls in inspect.getmembers(pkg, inspect.isclass):
        if cls_name.startswith("_") or not cls.__module__.startswith(package_name):
            continue
        lines.append(f"\nclass {cls_name}:")
        for meth_name, meth in inspect.getmembers(cls, predicate=inspect.isfunction):
            if not meth_name.startswith("_"):
                _add_fn(meth, prefix="    ")
        if seen >= max_symbols:
            lines.append("    # ... (truncated)")
            break

    return "\n".join(lines) if lines else f"# Could not inspect {package_name} API"


def _fetch_pypi_metadata(package_name: str) -> dict:
    """Fetch package metadata from PyPI JSON API."""
    try:
        import urllib.request
        url = f"https://pypi.org/pypi/{package_name}/json"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        info = data.get("info", {})
        return {
            "version": info.get("version", "unknown"),
            "description": (info.get("summary") or "")[:300],
            "home_page": info.get("home_page", ""),
        }
    except Exception as e:
        logger.warning("[register_package] PyPI fetch failed for %s: %s", package_name, e)
        return {"version": "unknown", "description": f"Python package: {package_name}"}


def _extract_method_bodies(llm_response: str) -> dict[str, str]:
    """Extract calibrate/evaluate/visualize/simulate method bodies from LLM output."""
    import re
    bodies = {}
    # Find ```python ... ``` blocks
    blocks = re.findall(r"```python\s*\n(.*?)\n```", llm_response, re.DOTALL)
    if not blocks:
        blocks = re.findall(r"```\s*\n(.*?)\n```", llm_response, re.DOTALL)

    for block in blocks:
        for method in ("calibrate", "evaluate", "visualize", "simulate"):
            if f"def {method}" in block and method not in bodies:
                bodies[method] = block.strip()

    return bodies


def _build_adapter_file(
    adapter_name: str,
    description: str,
    version: str,
    priority: int,
    method_bodies: dict[str, str],
) -> str:
    """Assemble the full adapter.py content."""

    _NOT_IMPL = (
        '        return {{\n'
        '            "success": False,\n'
        '            "message": "Not implemented for {name} -- use generate_code instead.",\n'
        '        }}'
    ).format(name=adapter_name)

    def _method(name: str) -> str:
        if name in method_bodies:
            # Indent each line of the LLM-generated body by 8 spaces
            body = method_bodies[name]
            # Strip the def line if LLM included it (we add our own)
            lines = body.splitlines()
            # Remove leading def line
            if lines and lines[0].strip().startswith(f"def {name}"):
                lines = lines[1:]
            # Ensure 8-space indent (strip existing indent, re-apply)
            indented = "\n".join(
                "        " + line.lstrip() if line.strip() else ""
                for line in lines
            )
            return f"    def {name}(self, workspace, **kw):\n{indented}"
        else:
            return (
                f"    def {name}(self, workspace, **kw):\n"
                f"{_NOT_IMPL}"
            )

    return f'''\
"""
{adapter_name} adapter for HydroClaw.
Auto-generated by register_package on 2026-03-15.
Package version: {version}

{description}
"""

from pathlib import Path
from hydroclaw.adapters.base import PackageAdapter


class Adapter(PackageAdapter):
    name = "{adapter_name}"
    priority = {priority}

    def can_handle(self, data_source: str, model_name: str) -> bool:
        return True  # handles all inputs; raise priority if this should be selective

{_method("calibrate")}

{_method("evaluate")}

{_method("visualize")}

{_method("simulate")}
'''


def _build_skill_doc(
    package_name: str, description: str, version: str, api_summary: str
) -> str:
    return f"""\
# {package_name} Adapter

**Version:** {version}
**Description:** {description}

Auto-registered via `register_package`. Edit
`hydroclaw/adapters/{package_name}/adapter.py` to refine the implementations.

## Discovered API (top-level)

```python
{api_summary[:1500]}
```

## Usage

After registration the standard tool calls route through this adapter:

```
calibrate_model(basin_ids=[...], model_name="...", data_source="{package_name}")
evaluate_model(calibration_dir="...")
```

If a method returns `"Not implemented"`, use `generate_code` + `run_code`
to call the package directly, or edit the adapter to fill in the method body.
"""


register_package.__agent_hint__ = (
    "Requires the package to be already installed (call install_package first). "
    "Uses LLM to generate adapter method bodies from the real API -- not just stubs. "
    "Implemented methods are immediately usable via calibrate_model/evaluate_model. "
    "Stubs_remaining methods need manual editing of the adapter.py file."
)
