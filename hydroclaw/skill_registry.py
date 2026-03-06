"""
Author: HydroClaw Team
Date: 2026-03-06
Description: Skill registry - discovers and matches Skill packages (skills/*/skill.md).
             Each Skill = skill.md (usage guide) + tool .py (executable code).
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


class SkillRegistry:
    """Discovers skills from skills/*/skill.md and matches them to queries.

    Each skill directory must contain a skill.md with YAML frontmatter:
      ---
      name: Skill Name
      description: One-line description
      keywords: [kw1, kw2, ...]
      tools: [tool1, tool2, ...]
      when_to_use: Short hint for LLM
      ---
      ## Skill content...
    """

    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self.skills: dict[str, dict] = {}  # dir_name → {name, description, keywords, content}
        self._scan()

    def _scan(self):
        """Scan skills/*/skill.md and parse frontmatter."""
        if not self.skills_dir.exists():
            return

        for skill_md in sorted(self.skills_dir.glob("*/skill.md")):
            dir_name = skill_md.parent.name
            try:
                text = skill_md.read_text(encoding="utf-8")
                meta, content = _parse_frontmatter(text)
                self.skills[dir_name] = {
                    "name": meta.get("name", dir_name),
                    "description": meta.get("description", ""),
                    "keywords": meta.get("keywords", []),
                    "tools": meta.get("tools", []),
                    "when_to_use": meta.get("when_to_use", ""),
                    "content": content,
                }
                logger.debug(f"Loaded skill: {dir_name} ({meta.get('name', dir_name)})")
            except Exception as e:
                logger.warning(f"Failed to load skill {dir_name}: {e}")

        logger.info(f"Loaded {len(self.skills)} skills: {list(self.skills.keys())}")

    def match(self, query: str) -> list[str]:
        """Return matched skill content list for the given query.

        Falls back to 'calibration' skill if nothing matches.
        """
        query_lower = query.lower()
        matched = []

        for skill in self.skills.values():
            keywords = skill.get("keywords", [])
            if any(str(kw).lower() in query_lower for kw in keywords):
                matched.append(skill["content"])

        if not matched:
            # Default fallback: calibration skill
            default = self.skills.get("calibration")
            if default:
                matched.append(default["content"])

        return matched

    def list_all(self) -> list[dict]:
        """Return [{name, description, when_to_use}, ...] for all skills."""
        return [
            {
                "name": s["name"],
                "description": s["description"],
                "when_to_use": s["when_to_use"],
            }
            for s in self.skills.values()
        ]

    def available_skills_prompt(self) -> str:
        """Return a compact skill list for injecting into the system prompt."""
        if not self.skills:
            return ""
        lines = ["## Available Skills\n"]
        for s in self.skills.values():
            lines.append(f"- **{s['name']}**: {s['description']}")
            if s.get("when_to_use"):
                lines.append(f"  - 何时使用: {s['when_to_use']}")
        lines.append(
            "\n当用户需求超出以上 Skill 时，使用 `create_skill` 自动生成新的 Skill 包。"
        )
        return "\n".join(lines)


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from a markdown file.

    Returns (meta_dict, body_text).
    """
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not match:
        return {}, content

    try:
        import yaml
        meta = yaml.safe_load(match.group(1)) or {}
    except Exception:
        meta = {}

    body = content[match.end():]
    return meta, body
