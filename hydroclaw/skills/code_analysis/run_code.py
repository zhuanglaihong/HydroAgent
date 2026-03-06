"""
Author: HydroClaw Team
Date: 2026-02-08
Description: Code execution tool - runs generated Python scripts safely.
"""

import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def run_code(
    file_path: str,
    timeout: int = 300,
    _workspace: Path | None = None,
) -> dict:
    """Execute a Python script and capture its output.

    Args:
        file_path: Path to the Python script to execute
        timeout: Execution timeout in seconds, default 300

    Returns:
        {"stdout": str, "stderr": str, "return_code": int, "success": bool}
    """
    script = Path(file_path)
    if not script.exists():
        return {"error": f"Script not found: {file_path}", "success": False}

    logger.info(f"Executing script: {file_path}")

    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(_workspace or script.parent),
        )

        success = result.returncode == 0

        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode,
            "success": success,
        }

    except subprocess.TimeoutExpired:
        return {"error": f"Script timed out after {timeout}s", "success": False}
    except Exception as e:
        return {"error": f"Execution failed: {e}", "success": False}
