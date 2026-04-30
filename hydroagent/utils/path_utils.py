"""
Path resolution utility shared by the web server and agent tools.

Resolution priority (given a raw path string and a workspace root):
  1. Raw path as-is (absolute and exists) -> use directly
  2. Relative path -> resolve under workspace
  3. Absolute path missing, workspace name found in parts
     -> re-root the suffix after the workspace folder under current workspace
     (handles project relocated to a different drive / parent directory)
  4. Strip root anchor, try whole suffix under workspace (last resort)

Usage:
    from hydroagent.utils.path_utils import resolve_path

    p = resolve_path("D:/old/HydroAgent/results/gr4j/file.png", workspace)
    # -> workspace / "results/gr4j/file.png"  (if workspace name is "HydroAgent")
"""

from pathlib import Path


def resolve_path(raw: str | Path, workspace: str | Path | None = None) -> Path | None:
    """Resolve *raw* to an existing file/directory, using *workspace* as fallback root.

    Returns the resolved Path if it exists, or None if not found.
    Works for both files and directories.
    """
    p = Path(raw)
    ws = Path(workspace).resolve() if workspace else None

    # 1. Direct hit (absolute or relative to cwd)
    if p.exists():
        return p.resolve()

    if ws is None:
        return None

    # 2. Relative path -> resolve under workspace
    if not p.is_absolute():
        candidate = ws / p
        return candidate.resolve() if candidate.exists() else None

    # --- absolute path that does not exist on disk ---

    # 3. Match workspace folder name in path parts, re-root the suffix
    ws_name = ws.name
    parts = p.parts
    for i, part in enumerate(parts):
        if part == ws_name and i + 1 < len(parts):
            candidate = ws.joinpath(*parts[i + 1:])
            if candidate.exists():
                return candidate.resolve()

    # 4. Strip drive/root anchor, try the whole suffix under workspace
    try:
        without_root = p.relative_to(p.anchor)
        candidate = ws / without_root
        if candidate.exists():
            return candidate.resolve()
    except Exception:
        pass

    return None


def resolve_path_str(raw: str | Path, workspace: str | Path | None = None,
                     fallback: str = "") -> str:
    """Like resolve_path but returns a string; returns *fallback* if not found."""
    result = resolve_path(raw, workspace)
    return str(result) if result is not None else (fallback or str(raw))


def is_relative(raw: str | Path) -> bool:
    """Return True if *raw* is a relative path (not anchored to a drive/root)."""
    return not Path(raw).is_absolute()
