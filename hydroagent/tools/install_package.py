"""
Author: HydroAgent Team
Date: 2026-03-15
Description: Install a Python package into the current virtual environment.
             SAFETY: Agent must NEVER call this without explicit user approval.
"""

import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Known error patterns -> human-readable diagnosis
_ERROR_PATTERNS = [
    ("No matching distribution found", "package_not_found",
     "Package not found on PyPI. Check the spelling or try a different package name."),
    ("Could not find a version that satisfies", "version_not_found",
     "No version satisfies the constraint. Try relaxing the version requirement."),
    ("already satisfied", "already_installed",
     None),  # handled specially — not an error
    ("PermissionError", "permission_denied",
     "Permission denied. The current environment may be read-only. "
     "Ask the user to run as administrator or use a writable virtual environment."),
    ("ResolutionImpossible", "dependency_conflict",
     "Dependency conflict. The package cannot be installed due to incompatible "
     "requirements with existing packages. Report the full error to the user."),
    ("ConnectionError", "network_error",
     "Network error. Check internet connection or proxy settings."),
    ("TimeoutError", "network_timeout",
     "Connection timed out. Check network/proxy or try again."),
    ("SSL", "ssl_error",
     "SSL certificate error. Try --trusted-host pypi.org --trusted-host files.pythonhosted.org."),
]


def install_package(
    package_name: str,
    version_constraint: str | None = None,
    upgrade: bool = False,
    _workspace: Path | None = None,
    _cfg: dict | None = None,
) -> dict:
    """Install a Python package into the current virtual environment.

    CRITICAL SAFETY RULE: ONLY call this tool when the user has EXPLICITLY and
    unambiguously requested the installation (e.g. "install X", "yes, go ahead",
    "please install it"). Do NOT call autonomously because you think a package
    is needed. If uncertain, use ask_user to request explicit permission first.

    Args:
        package_name: Package name, e.g. "spotpy" or "hydroeval"
        version_constraint: Optional version spec, e.g. ">=1.5,<2.0" or "==1.5.3"
        upgrade: If True, pass --upgrade flag (reinstall even if already present)

    Returns:
        {"installed": str, "version": str, "already_installed": bool, "success": bool}
    """
    package_name = package_name.strip()
    if not package_name:
        return {"error": "package_name must not be empty.", "success": False}

    # Build the install spec
    spec = package_name
    if version_constraint:
        vc = version_constraint.strip()
        # Ensure the constraint starts with an operator
        if vc and vc[0].isdigit():
            vc = "==" + vc
        spec = f"{package_name}{vc}"

    python = sys.executable
    logger.info("Installing %s with %s", spec, python)

    # Check current install state first (avoids redundant install when not upgrading)
    if not upgrade:
        show = subprocess.run(
            [python, "-m", "pip", "show", package_name],
            capture_output=True, text=True,
        )
        if show.returncode == 0:
            version = _parse_version_from_show(show.stdout)
            logger.info("Package %s already installed (%s)", package_name, version)
            return {
                "installed": spec,
                "version": version,
                "already_installed": True,
                "success": True,
                "message": f"{package_name} {version} is already installed.",
            }

    # Run pip install
    cmd = [python, "-m", "pip", "install", spec]
    if upgrade:
        cmd.append("--upgrade")

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return {
            "error": "pip install timed out after 120s.",
            "error_type": "network_timeout",
            "diagnosis": "Check internet connection or proxy settings.",
            "success": False,
        }

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    combined = stdout + "\n" + stderr

    if proc.returncode == 0:
        # Determine installed version from pip show
        show = subprocess.run(
            [python, "-m", "pip", "show", package_name],
            capture_output=True, text=True,
        )
        version = _parse_version_from_show(show.stdout) if show.returncode == 0 else "unknown"
        logger.info("Successfully installed %s %s", package_name, version)
        return {
            "installed": spec,
            "version": version,
            "already_installed": False,
            "success": True,
            "message": f"Successfully installed {package_name} {version}.",
        }

    # pip returned non-zero — classify the error
    error_type, diagnosis = _classify_error(combined)
    logger.warning("pip install failed for %s: %s", spec, combined[:200])
    return {
        "error": f"pip install failed for '{spec}'.",
        "error_type": error_type,
        "diagnosis": diagnosis,
        "pip_output": combined[:600],
        "success": False,
        "hint": (
            "Report this error to the user. Do NOT retry automatically. "
            "If it is a network error, ask the user to check their connection. "
            "If it is a dependency conflict, let the user decide how to resolve it."
        ),
    }


# ── helpers ──────────────────────────────────────────────────────────

def _parse_version_from_show(pip_show_output: str) -> str:
    for line in pip_show_output.splitlines():
        if line.lower().startswith("version:"):
            return line.split(":", 1)[1].strip()
    return "unknown"


def _classify_error(output: str) -> tuple[str, str]:
    for pattern, error_type, diagnosis in _ERROR_PATTERNS:
        if pattern.lower() in output.lower():
            if error_type == "already_installed":
                # This shouldn't reach here (caught above), but be safe
                return "already_installed", "Package is already installed."
            return error_type, diagnosis or output[:200]
    return "unknown", (
        "Unknown pip error. See pip_output for details. "
        "Report to the user and ask for guidance."
    )


install_package.__agent_hint__ = (
    "SAFETY: ONLY call when the user has EXPLICITLY approved installation. "
    "If you are not sure, call ask_user first. Never install autonomously. "
    "Uses the current Python executable so the package lands in the active venv. "
    "On success, call register_package to make the new package usable as an adapter."
)
