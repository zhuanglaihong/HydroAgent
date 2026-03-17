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
                    "skill_md_path": str(skill_md),  # absolute path for read_file
                }
                logger.debug(f"Loaded skill: {dir_name} ({meta.get('name', dir_name)})")
            except Exception as e:
                logger.warning(f"Failed to load skill {dir_name}: {e}")

        logger.info(f"Loaded {len(self.skills)} skills: {list(self.skills.keys())}")

    # Max chars of a skill's content to inject per request.
    # Full content is ~1500-3000 chars; 800 chars covers the key workflow steps.
    _SKILL_CONTENT_MAX = 800

    def match(self, query: str) -> list[str]:
        """Return matched skill content snippets for the given query.

        Injects up to _SKILL_CONTENT_MAX chars per matched skill to keep
        the system prompt lean. Full skill.md is available on disk if the
        agent needs more detail via read_file / inspect_dir.
        Falls back to 'calibration' skill if nothing matches.
        """
        query_lower = query.lower()
        matched = []

        for skill in self.skills.values():
            keywords = skill.get("keywords", [])
            if any(str(kw).lower() in query_lower for kw in keywords):
                content = skill["content"]
                if len(content) > self._SKILL_CONTENT_MAX:
                    content = content[: self._SKILL_CONTENT_MAX] + "\n...(see skill.md for full workflow)"
                matched.append(content)

        if not matched:
            default = self.skills.get("calibration")
            if default:
                content = default["content"]
                if len(content) > self._SKILL_CONTENT_MAX:
                    content = content[: self._SKILL_CONTENT_MAX] + "\n...(see skill.md for full workflow)"
                matched.append(content)

        return matched

    def list_all(self) -> list[dict]:
        """Return full skill metadata for all skills (used by web UI panel)."""
        return [
            {
                "id": dir_name,
                "name": s["name"],
                "description": s["description"],
                "when_to_use": s["when_to_use"],
                "keywords": s.get("keywords", []),
                "tools": s.get("tools", []),
                "content": s.get("content", "")[:800],
            }
            for dir_name, s in self.skills.items()
        ]

    def available_skills_prompt(self, state_mgr=None) -> str:
        """Return a skill list with file paths for the system prompt.

        Each entry shows the skill name, description, when_to_use, and the
        path to skill.md so the agent can read the full workflow via read_file.

        Args:
            state_mgr: Optional SkillStateManager to show lifecycle badges.
        """
        if not self.skills:
            return ""
        lines = [
            "## Available Skills",
            "",
            "若任务匹配某个 Skill，先用 `read_file` 读取其 `skill_md_path`，",
            "阅读完整工作流后再执行。不要跳过这一步。",
            "",
        ]
        for dir_name, s in self.skills.items():
            badge = state_mgr.status_badge(dir_name) if state_mgr else ""
            badge_str = f" {badge}" if badge else ""
            lines.append(f"- **{s['name']}**{badge_str}")
            lines.append(f"  - 描述: {s['description']}")
            if s.get("when_to_use"):
                lines.append(f"  - 何时使用: {s['when_to_use']}")
            lines.append(f"  - 读取路径: `{s['skill_md_path']}`")
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
