"""
Author: HydroClaw Team
Date: 2026-02-08
Description: Code generation tool - generates Python scripts for custom analysis.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_code(
    task_description: str,
    output_filename: str = "analysis.py",
    calibration_dir: str | None = None,
    _workspace: Path | None = None,
    _llm: object | None = None,
) -> dict:
    """Generate a Python analysis script based on the task description.

    The LLM generates complete, runnable Python code for custom hydrology analysis
    tasks like flow duration curves, runoff coefficient calculation, etc.

    Args:
        task_description: Natural language description of what the code should do
        output_filename: Name of the output Python file
        calibration_dir: Path to calibration results for context

    Returns:
        {"code": str, "file_path": str, "success": bool}
    """
    if _llm is None:
        return {"error": "LLM client required for code generation", "success": False}

    system_prompt = """You are a Python code generation expert for hydrology analysis.
Generate complete, runnable Python scripts with:
- Proper imports
- Type hints
- Error handling
- Clear comments
- matplotlib for visualization (use Agg backend)

The script should be self-contained and ready to run.
Always use `matplotlib.use('Agg')` before importing pyplot.
Output only the Python code, wrapped in ```python ... ``` blocks."""

    context = f"Task: {task_description}"
    if calibration_dir:
        context += f"\nCalibration results are in: {calibration_dir}"

    response = _llm.chat([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": context},
    ])

    # Extract code from response
    code = _extract_code(response.text)

    if not code:
        return {"error": "Failed to generate code", "success": False}

    # Save to file
    workspace = _workspace or Path(".")
    code_dir = workspace / "generated_code"
    code_dir.mkdir(parents=True, exist_ok=True)
    file_path = code_dir / output_filename

    file_path.write_text(code, encoding="utf-8")
    logger.info(f"Generated code saved to: {file_path}")

    return {
        "code": code,
        "file_path": str(file_path),
        "success": True,
    }


def _extract_code(text: str) -> str | None:
    """Extract Python code from LLM response."""
    import re
    matches = re.findall(r'```python\s*\n(.*?)\n```', text, re.DOTALL)
    if matches:
        return matches[0].strip()
    # Fallback: try generic code block
    matches = re.findall(r'```\s*\n(.*?)\n```', text, re.DOTALL)
    if matches:
        return matches[0].strip()
    return None
