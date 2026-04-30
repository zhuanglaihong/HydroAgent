"""
Author: HydroAgent Team
Date: 2026-02-08
Description: Code generation tool - generates Python scripts for custom analysis.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


_CAMELS_DATA_SNIPPET = """
## CAMELS Data Access (IMPORTANT - use this exact pattern)

CAMELS data is stored as NetCDF files, accessed via the `hydrodataset` library.
**Do NOT try to read CSV files.**

Available standard variable names:
  streamflow, precipitation, temperature_max, temperature_min,
  daylight_duration, solar_radiation, snow_water_equivalent,
  vapor_pressure, potential_evapotranspiration, evapotranspiration

Correct API (t_range is REQUIRED — omitting it causes a cache validation error):

```python
from hydrodataset.camels_us import CamelsUs

ds = CamelsUs(data_path=DATA_PATH)  # DATA_PATH will be provided

# Read streamflow — always pass t_range and var_lst as keyword arguments
streamflow_ds = ds.read_ts_xrdataset(
    gage_id_lst=[BASIN_ID],
    t_range=["2000-01-01", "2014-12-31"],   # REQUIRED
    var_lst=["streamflow"],                  # use exact names from the list above
)
df = streamflow_ds.to_dataframe().reset_index()
# df columns: 'basin' (str), 'time' (datetime64), 'streamflow' (float, mm/day)

# Read precipitation + temperature together
forcing_ds = ds.read_ts_xrdataset(
    gage_id_lst=[BASIN_ID],
    t_range=["2000-01-01", "2014-12-31"],
    var_lst=["precipitation", "temperature_max"],
)
```

If DATA_PATH is None or loading fails, raise FileNotFoundError immediately.
Never fall back to simulated / random data.
"""


def generate_code(
    task_description: str,
    output_filename: str = "analysis.py",
    data_path: str | None = None,
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
        data_path: CAMELS dataset root directory (from validate_basin result)
        calibration_dir: Path to calibration results for context

    Returns:
        {"code": str, "file_path": str, "success": bool}
    """
    if _llm is None:
        return {"error": "LLM client required for code generation", "success": False}

    system_prompt = (
        "You are a Python code generation expert for hydrology analysis.\n"
        "Generate complete, runnable Python scripts with:\n"
        "- Proper imports\n"
        "- Error handling (raise FileNotFoundError if data missing, never use simulated data)\n"
        "- Clear comments\n"
        "- matplotlib for visualization (use Agg backend, save to file, no plt.show())\n\n"
        "The script should be self-contained and ready to run.\n"
        "Always use `matplotlib.use('Agg')` before importing pyplot.\n"
        "Output only the Python code, wrapped in ```python ... ``` blocks.\n"
        + _CAMELS_DATA_SNIPPET
    )

    context = f"Task: {task_description}"
    if data_path:
        context += f"\nCAMELS data_path = r\"{data_path}\""
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


generate_code.__agent_hint__ = (
    "Pass data_path, available_variables, full_time_range from validate_basin result. "
    "For CAMELS: t_range is REQUIRED in read_ts_xrdataset — omitting it causes cache rebuild failure. "
    "Never generate code that falls back to simulated data; raise FileNotFoundError instead."
)


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
