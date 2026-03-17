"""
Author: HydroClaw Team
Date: 2026-03-15
Description: Meta-tool: generate a new PackageAdapter skeleton for a water model package.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_ADAPTER_TEMPLATE = '''\
"""
{adapter_name} adapter for HydroClaw.

{description}
"""

from pathlib import Path
from hydroclaw.adapters.base import PackageAdapter


class Adapter(PackageAdapter):
    name = "{adapter_name}"
    priority = 5

    def can_handle(self, data_source: str, model_name: str) -> bool:
{can_handle_body}

    def calibrate(self, workspace: Path, **kw) -> dict:
        """Run calibration using {adapter_name}.

        Expected kw keys: basin_ids, model_name, algorithm, train_period,
        test_period, algorithm_params, output_dir, _cfg, _ui.
        """
        raise NotImplementedError(
            "Fill in {adapter_name} calibrate() logic here. "
            "Return dict with success=True/False, calibration_dir, best_params."
        )

    def evaluate(self, workspace: Path, **kw) -> dict:
        """Evaluate a calibrated {adapter_name} model.

        Expected kw keys: calibration_dir, eval_period, output_subdir.
        """
        raise NotImplementedError(
            "Fill in {adapter_name} evaluate() logic here. "
            "Return dict with success=True/False, metrics (NSE/KGE/RMSE), metrics_dir."
        )

    def visualize(self, workspace: Path, **kw) -> dict:
        """Generate plots from {adapter_name} calibration results.

        Expected kw keys: calibration_dir, plot_types, basin_ids.
        """
        raise NotImplementedError(
            "Fill in {adapter_name} visualize() logic here. "
            "Return dict with plot_files (list), plot_count."
        )

    def simulate(self, workspace: Path, **kw) -> dict:
        """Run {adapter_name} simulation.

        Expected kw keys: calibration_dir, sim_period, params.
        """
        raise NotImplementedError(
            "Fill in {adapter_name} simulate() logic here. "
            "Return dict with success=True/False, simulation_dir."
        )
'''

_SKILL_DOC_TEMPLATE = """\
# {adapter_name} Package Adapter

{description}

## Usage

After filling in the adapter methods, use the standard tool calls:

```
calibrate_model(basin_ids=[...], model_name="...", data_source="...")
evaluate_model(calibration_dir="...")
visualize(calibration_dir="...")
```

## Implementation notes

- Edit `hydroclaw/adapters/{adapter_name}/adapter.py` to fill in the method bodies.
- Supported models: {supported_models}
- After editing, call `reload_adapters()` or restart the agent to pick up changes.
"""


def create_adapter(
    adapter_name: str,
    description: str,
    supported_models: list[str] | None = None,
    _workspace: Path | None = None,
    _cfg: dict | None = None,
) -> dict:
    """Generate a new PackageAdapter skeleton for a water model package.

    Args:
        adapter_name: Adapter name in lowercase, e.g. "xaj_model"
        description: Brief description of the package (used in skill doc comments)
        supported_models: List of model names this adapter supports (optional, informational)

    Returns:
        {"created_files": [...], "next_step": "...", "success": bool}
    """
    adapter_name = adapter_name.strip().lower().replace("-", "_").replace(" ", "_")
    if not adapter_name:
        return {"error": "adapter_name must not be empty.", "success": False}

    adapters_dir = Path(__file__).parent.parent / "adapters"
    target_dir = adapters_dir / adapter_name
    skills_dir = target_dir / "skills"

    created_files = []

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        skills_dir.mkdir(parents=True, exist_ok=True)

        # __init__.py
        init_file = target_dir / "__init__.py"
        if not init_file.exists():
            init_file.write_text("", encoding="utf-8")
            created_files.append(str(init_file))

        # adapter.py skeleton
        adapter_file = target_dir / "adapter.py"
        if adapter_file.exists():
            return {
                "error": f"adapter.py already exists at {adapter_file}. "
                "Delete it first or edit it directly.",
                "success": False,
            }

        models_list = supported_models or []
        if models_list:
            can_handle_body = (
                "        supported = " + repr(models_list) + "\n"
                "        return model_name in supported or not model_name"
            )
        else:
            can_handle_body = "        return True  # handles all model names"

        adapter_content = _ADAPTER_TEMPLATE.format(
            adapter_name=adapter_name,
            description=description,
            can_handle_body=can_handle_body,
        )
        adapter_file.write_text(adapter_content, encoding="utf-8")
        created_files.append(str(adapter_file))

        # skill doc
        skill_doc_file = skills_dir / "skill.md"
        models_str = ", ".join(f"`{m}`" for m in models_list) if models_list else "all"
        skill_doc_content = _SKILL_DOC_TEMPLATE.format(
            adapter_name=adapter_name,
            description=description,
            supported_models=models_str,
        )
        skill_doc_file.write_text(skill_doc_content, encoding="utf-8")
        created_files.append(str(skill_doc_file))

        logger.info("Created adapter skeleton: %s", adapter_name)

        # Hot-reload adapters so the new skeleton is registered immediately
        try:
            from hydroclaw.adapters import reload_adapters

            reload_adapters()
            reload_note = "Adapters reloaded -- new adapter is registered (but NotImplementedError until you fill in the methods)."
        except Exception as e:
            reload_note = f"Note: could not auto-reload adapters: {e}. Restart the agent to pick up changes."

        return {
            "created_files": created_files,
            "next_step": (
                f"Edit {adapter_file} to implement calibrate/evaluate/visualize/simulate methods. "
                + reload_note
            ),
            "success": True,
        }

    except Exception as e:
        logger.error("create_adapter failed: %s", e, exc_info=True)
        return {"error": f"create_adapter failed: {e}", "success": False}
