"""
spawn_agent — delegate a task to a named specialized subagent.

The subagent runs as an isolated HydroAgent instance with:
  - restricted tool allowlist (from agent definition)
  - minimal prompt mode (no domain knowledge / memory by default)
  - independent message context (does not share parent's history)
  - its own system prompt (from the agent's markdown body)

Subagents cannot spawn other subagents (depth limit enforced).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Prevent subagents from recursively spawning further subagents
_SPAWN_DEPTH: int = 0
_MAX_SPAWN_DEPTH: int = 1


def spawn_agent(
    name: str,
    task: str,
    _workspace: Path | None = None,
    _cfg: dict | None = None,
    _ui=None,
) -> dict[str, Any]:
    """Delegate *task* to the named subagent and return its result.

    Args:
        name: Agent name as defined in agents/*.md (e.g. "basin-explorer").
        task: Natural-language task description for the subagent.

    Returns:
        {"success": True, "result": <text>, "agent": name}  on success
        {"success": False, "error": <msg>}                  on failure
    """
    global _SPAWN_DEPTH

    if _SPAWN_DEPTH >= _MAX_SPAWN_DEPTH:
        return {
            "success": False,
            "error": "Subagents cannot spawn further subagents (max depth reached).",
        }

    # ── Load agent definition ─────────────────────────────────────────────
    from hydroagent.agents import AgentRegistry  # local import: avoids circular dep
    registry = AgentRegistry(_workspace)
    agent_def = registry.get(name)
    if agent_def is None:
        available = registry.list_names()
        return {
            "success": False,
            "error": (
                f"Agent '{name}' not found. "
                f"Available agents: {available or '(none)'}"
            ),
        }

    # ── Build restricted HydroAgent instance ──────────────────────────────
    from hydroagent.agent import HydroAgent  # local import: avoids circular dep

    sub = HydroAgent(
        workspace=_workspace,
        config_override=_cfg,
        ui=_ui,
        prompt_mode=agent_def.get("prompt_mode", "minimal"),
    )
    sub.max_turns = agent_def.get("max_turns", 15)

    # Apply tool allowlist
    allowed = agent_def.get("tools")
    if allowed:
        allowed_set = set(allowed)
        # Also always allow spawn_agent so the subagent can report errors cleanly
        # (but depth guard prevents actual recursion)
        sub.tools = {k: v for k, v in sub.tools.items() if k in allowed_set}
        sub.tool_schemas = [
            s for s in sub.tool_schemas
            if s.get("function", {}).get("name") in allowed_set
        ]

    # Apply custom system prompt from agent body (overrides _load_system_prompt)
    custom_prompt = agent_def.get("system_prompt", "").strip()
    if custom_prompt:
        sub._subagent_system_prompt = custom_prompt

    # ── Run subagent ──────────────────────────────────────────────────────
    logger.info("spawn_agent: delegating to '%s' | task: %s", name, task[:80])
    _SPAWN_DEPTH += 1
    try:
        result_text = sub.run(task)
    except Exception as e:
        logger.error("spawn_agent '%s' raised: %s", name, e, exc_info=True)
        return {"success": False, "error": f"Subagent '{name}' failed: {e}"}
    finally:
        _SPAWN_DEPTH -= 1

    logger.info("spawn_agent '%s' finished.", name)
    return {"success": True, "result": result_text, "agent": name}


spawn_agent.__agent_hint__ = (
    "Delegate a self-contained sub-task to a named specialist agent. "
    "Use when the task is clearly scoped (one basin, one check) and you want to isolate "
    "its context from the main conversation. Available agents: 'basin-explorer' (data validation), "
    "'calibrate-worker' (single-basin calibration + evaluation). "
    "Do NOT use for tasks that require the main agent's full context or for tasks that "
    "modify global state (e.g., create_skill, install_package)."
)
