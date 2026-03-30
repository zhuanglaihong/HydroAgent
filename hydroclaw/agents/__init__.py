"""
AgentRegistry — discovers and manages named subagent definitions.

Scans two layers (lower priority first, higher overrides):
  1. Built-in:      hydroclaw/agents/*.md
  2. Project-level: <workspace>/.hydroclaw/agents/*.md

Each agent definition is a Markdown file with YAML frontmatter:
  ---
  name: basin-explorer
  description: When to delegate to this agent (used by LLM to decide)
  tools: [validate_basin, list_basins]   # allowlist; omit = all tools
  prompt_mode: minimal                   # full | minimal
  max_turns: 8
  ---
  <system prompt body for the subagent>
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TypedDict

logger = logging.getLogger(__name__)


class AgentDef(TypedDict):
    name: str
    description: str
    tools: list[str] | None      # None = inherit all
    prompt_mode: str             # "full" | "minimal"
    max_turns: int
    system_prompt: str           # body of the markdown file


class AgentRegistry:
    """Discovers subagent definitions from built-in and project-level directories."""

    def __init__(self, workspace: Path | None = None):
        self._agents: dict[str, AgentDef] = {}
        # Layer 1: built-in agents shipped with hydroclaw
        self._scan(Path(__file__).parent)
        # Layer 2: project-level overrides (higher priority)
        if workspace:
            self._scan(Path(workspace) / ".hydroclaw" / "agents")

    def _scan(self, directory: Path) -> None:
        if not directory.exists():
            return
        for md_file in sorted(directory.glob("*.md")):
            try:
                text = md_file.read_text(encoding="utf-8")
                meta, body = _parse_frontmatter(text)
                name = meta.get("name") or md_file.stem.replace("_", "-")
                tools_raw = meta.get("tools")
                entry: AgentDef = {
                    "name": name,
                    "description": meta.get("description", ""),
                    "tools": list(tools_raw) if tools_raw else None,
                    "prompt_mode": meta.get("prompt_mode", "minimal"),
                    "max_turns": int(meta.get("max_turns", 15)),
                    "system_prompt": body.strip(),
                }
                self._agents[name] = entry
                logger.debug("AgentRegistry: loaded '%s' from %s", name, md_file)
            except Exception as e:
                logger.warning("AgentRegistry: failed to load %s: %s", md_file, e)
        logger.info("AgentRegistry: %d agents from %s", len(self._agents), directory)

    # ── Public API ────────────────────────────────────────────────────────────

    def get(self, name: str) -> AgentDef | None:
        return self._agents.get(name)

    def list_all(self) -> list[AgentDef]:
        return list(self._agents.values())

    def list_names(self) -> list[str]:
        return list(self._agents.keys())

    def available_agents_prompt(self) -> str:
        """Return a compact listing for the system prompt.

        Only shows agents that have a non-empty description, formatted so
        the LLM knows when to call spawn_agent(name, task).
        """
        agents = [a for a in self._agents.values() if a["description"]]
        if not agents:
            return ""
        lines = [
            "## Available Subagents",
            "",
            "When a task is clearly scoped and matches a subagent, delegate via "
            "`spawn_agent(name, task)`. The subagent runs in an isolated context "
            "with restricted tools and returns a summary.",
            "",
        ]
        for a in agents:
            tool_hint = f" (tools: {', '.join(a['tools'])})" if a["tools"] else ""
            lines.append(f"- **{a['name']}**{tool_hint}: {a['description']}")
        return "\n".join(lines)


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not match:
        return {}, content
    try:
        import yaml
        meta = yaml.safe_load(match.group(1)) or {}
    except Exception:
        meta = {}
    return meta, content[match.end():]
