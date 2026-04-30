"""
Author: HydroAgent Team
Date: 2026-03-08
Description: Observation tools - give the Agent eyes to inspect real-world state.

These tools let the Agent actively look at files and directories,
just like a researcher checking their lab bench after an experiment.
They are intentionally simple: return raw content without interpretation,
so the LLM can reason about what it actually sees.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def read_file(path: str, limit: int = 200) -> dict:
    """Read a file and return its raw contents for inspection.

    Use this to observe actual experiment outputs: calibration results,
    metrics CSVs, parameter files, config YAMLs, log excerpts, etc.
    Like a researcher opening a file to check what's inside before deciding
    what to do next.

    Args:
        path: Absolute or relative path to the file.
        limit: Max lines to return for text/CSV files (default 200). Use 0 for no limit.

    Returns:
        For JSON: {"content": <parsed dict/list>, "format": "json", "path": ..., "success": True}
        For CSV:  {"content": [{"col": val, ...}, ...], "format": "csv", "rows": N, "path": ..., "success": True}
        For YAML: {"content": <parsed dict>, "format": "yaml", "path": ..., "success": True}
        For text: {"content": "<text>", "format": "text", "path": ..., "success": True}
        On error: {"error": "...", "path": ..., "success": False}
    """
    import csv
    import json

    p = Path(path)
    if not p.exists():
        return {
            "error": f"File not found: {path}",
            "path": str(p.absolute()),
            "success": False,
            "hint": "Use inspect_dir(parent_directory) to see what files exist.",
        }
    if not p.is_file():
        return {
            "error": f"Path is a directory, not a file: {path}",
            "path": path,
            "success": False,
            "hint": "Use inspect_dir(path) to list directory contents.",
        }

    suffix = p.suffix.lower()
    try:
        if suffix == ".json":
            data = json.loads(p.read_text(encoding="utf-8"))
            return {
                "content": data,
                "format": "json",
                "path": str(p),
                "success": True,
            }

        elif suffix == ".csv":
            rows = []
            with open(p, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows.append({k: _try_numeric(v) for k, v in row.items() if k})
            total = len(rows)
            if limit and limit > 0:
                rows = rows[:limit]
            return {
                "content": rows,
                "format": "csv",
                "rows": total,
                "returned_rows": len(rows),
                "truncated": total > len(rows),
                "columns": list(rows[0].keys()) if rows else [],
                "path": str(p),
                "success": True,
            }

        elif suffix in (".yaml", ".yml"):
            import yaml
            data = yaml.safe_load(p.read_text(encoding="utf-8"))
            return {
                "content": data,
                "format": "yaml",
                "path": str(p),
                "success": True,
            }

        else:
            # Plain text — apply line limit to prevent context overflow
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            total = len(lines)
            if limit and limit > 0:
                lines = lines[:limit]
            text = "\n".join(lines)
            return {
                "content": text,
                "format": "text",
                "total_lines": total,
                "returned_lines": len(lines),
                "truncated": total > len(lines),
                "path": str(p),
                "success": True,
            }

    except Exception as e:
        return {
            "error": f"Failed to read file: {e}",
            "path": str(p),
            "success": False,
        }


def inspect_dir(path: str) -> dict:
    """List the contents of a directory: files with sizes, subdirectories with file counts.

    Use this to check what hydromodel produced after calibration, verify that
    expected output files exist, or explore an unfamiliar results folder.
    Like a researcher looking at their lab bench to understand the current state
    before deciding what measurement to take next.

    Args:
        path: Directory path to inspect.

    Returns:
        {
          "path": str,
          "files": [{"name": str, "size_kb": float, "modified": str}, ...],
          "subdirs": [{"name": str, "n_files": int}, ...],
          "total_files": int,
          "key_files": [str, ...],   # files likely worth reading (json/csv/yaml)
          "success": True
        }
        On missing directory:
        {
          "error": "Directory not found",
          "exists": False,
          "success": False
        }
    """
    from datetime import datetime

    p = Path(path)
    if not p.exists():
        return {
            "error": f"Directory not found: {path}",
            "exists": False,
            "success": False,
            "hint": "Check if calibration completed successfully and the path is correct.",
        }
    if not p.is_dir():
        return {
            "error": f"Path is a file, not a directory: {path}",
            "success": False,
            "hint": f"Use read_file('{path}') to read this file directly.",
        }

    files = []
    subdirs = []
    key_extensions = {".json", ".csv", ".yaml", ".yml"}

    try:
        for item in sorted(p.iterdir()):
            if item.is_file():
                stat = item.stat()
                files.append({
                    "name": item.name,
                    "size_kb": round(stat.st_size / 1024, 1),
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                })
            elif item.is_dir():
                n_files = sum(1 for f in item.iterdir() if f.is_file())
                subdirs.append({"name": item.name, "n_files": n_files})
    except PermissionError as e:
        return {"error": f"Permission denied: {e}", "path": path, "success": False}

    key_files = [
        f["name"] for f in files
        if Path(f["name"]).suffix.lower() in key_extensions
    ]

    result = {
        "path": str(p),
        "files": files,
        "subdirs": subdirs,
        "total_files": len(files),
        "key_files": key_files,
        "success": True,
    }

    # Add a hint when the directory looks like a calibration output
    if "calibration_results.json" in key_files:
        result["hint"] = (
            "This looks like a calibration output directory. "
            "Read 'calibration_results.json' to inspect best_params and objective_value. "
            "Subdirs 'train_metrics/' and 'test_metrics/' contain evaluation CSVs if evaluate_model was run."
        )
    elif not files and not subdirs:
        result["hint"] = "Directory is empty. The producing step may not have completed successfully."

    logger.debug(f"inspect_dir: {path} -> {len(files)} files, {len(subdirs)} subdirs")
    return result


def _try_numeric(value: str):
    """Convert string to int or float if possible, else keep as string."""
    if not isinstance(value, str):
        return value
    v = value.strip()
    if not v:
        return None
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        return v
