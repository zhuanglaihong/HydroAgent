"""
Author: HydroClaw Team
Date: 2026-02-08
Description: Agentic Loop core - the heart of HydroClaw.
             LLM decides what to do, code only executes.
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from hydroclaw.config import load_config
from hydroclaw.llm import LLMClient, LLMResponse
from hydroclaw.memory import Memory
from hydroclaw.skill_registry import SkillRegistry
from hydroclaw.tools import discover_tools, get_tool_schemas
from hydroclaw.ui import ConsoleUI

logger = logging.getLogger(__name__)


class HydroClaw:
    """LLM-driven hydrological model calibration agent.

    Core loop: Query → LLM reasons → calls tools → LLM reasons → ... → final answer.
    No state machine, no if-else routing, no multi-agent orchestration.
    """

    def __init__(
        self,
        config_path: str | Path | None = None,
        workspace: Path | None = None,
        ui: ConsoleUI | None = None,
    ):
        self.cfg = load_config(config_path)
        self.llm = LLMClient(self.cfg["llm"])
        self.memory = Memory(workspace or Path("."))
        self.tools = discover_tools()
        self.tool_schemas = get_tool_schemas()
        self.max_turns = self.cfg.get("max_turns", 30)
        self.workspace = workspace or Path(".")
        self.ui = ui or ConsoleUI(mode="user")

        skills_dir = Path(__file__).parent / "skills"
        self.skill_registry = SkillRegistry(skills_dir)

        logger.info(
            f"HydroClaw initialized: {len(self.tools)} tools, "
            f"{len(self.skill_registry.skills)} skills, "
            f"model={self.cfg['llm']['model']}, max_turns={self.max_turns}"
        )

    def run(self, query: str) -> str:
        """Run the agentic loop for a user query.

        Args:
            query: Natural language query (Chinese or English).

        Returns:
            Final text response from the LLM.
        """
        messages = self._build_context(query)

        logger.info(f"Starting agentic loop for: {query[:80]}...")
        self.ui.on_query(query)

        for turn in range(self.max_turns):
            logger.debug(f"Turn {turn + 1}/{self.max_turns}")

            messages = self._maybe_compress_history(messages)

            with self.ui.thinking(turn + 1):
                response = self.llm.chat(messages, tools=self.tool_schemas)

            if response.is_text():
                logger.info(f"Completed in {turn + 1} turns")
                self.memory.save_session(query, response.text)
                self.ui.on_answer(response.text, turn + 1)
                return response.text

            # LLM wants to call tools
            if self.llm.supports_function_calling:
                assistant_msg = {
                    "role": "assistant",
                    "content": response.text,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                            },
                        }
                        for tc in response.tool_calls
                    ],
                }
                messages.append(assistant_msg)

                for tc in response.tool_calls:
                    self.ui.on_tool_start(tc.name, tc.arguments)
                    t0 = time.time()
                    result = {"error": "execution failed", "success": False}
                    try:
                        with self.ui.suppress_tool_output(tc.name):
                            result = self._execute_tool(tc.name, tc.arguments)
                    finally:
                        self.ui.on_tool_end(tc.name, result, time.time() - t0)

                    self.memory.log_tool_call(tc.name, tc.arguments, result)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    })
            else:
                # Prompt-based fallback
                if response.text:
                    messages.append({"role": "assistant", "content": response.text})

                for tc in response.tool_calls:
                    self.ui.on_tool_start(tc.name, tc.arguments)
                    t0 = time.time()
                    result = {"error": "execution failed", "success": False}
                    try:
                        with self.ui.suppress_tool_output(tc.name):
                            result = self._execute_tool(tc.name, tc.arguments)
                    finally:
                        self.ui.on_tool_end(tc.name, result, time.time() - t0)

                    self.memory.log_tool_call(tc.name, tc.arguments, result)

                    result_text = json.dumps(result, ensure_ascii=False, default=str)
                    messages.append({
                        "role": "user",
                        "content": f"Tool `{tc.name}` returned:\n```json\n{result_text}\n```\nContinue with the next step.",
                    })

        logger.warning(f"Reached max turns ({self.max_turns})")
        self.ui.on_max_turns()
        final = "已达到最大步骤数，请检查已有结果。"
        self.memory.save_session(query, final)
        return final

    def _build_context(self, query: str) -> list[dict]:
        """Build initial message context: system prompt + domain knowledge + skills + memory."""
        system = self._load_system_prompt()
        domain_knowledge = self._load_domain_knowledge(query)
        skill_contents = self.skill_registry.match(query)
        available_skills = self.skill_registry.available_skills_prompt()
        memory = self.memory.load_knowledge()

        # Load basin profiles for any 8-digit basin IDs mentioned in the query
        basin_ids_in_query = re.findall(r'\b\d{8}\b', query)
        basin_profiles = self.memory.format_basin_profiles_for_context(basin_ids_in_query)

        system_content = system
        if available_skills:
            system_content += "\n\n" + available_skills
        if domain_knowledge:
            system_content += "\n\n## Domain Knowledge\n" + domain_knowledge
        for skill_content in skill_contents:
            system_content += "\n\n" + skill_content
        if basin_profiles:
            system_content += "\n\n" + basin_profiles
        if memory:
            system_content += "\n\n## Memory (from previous sessions)\n" + memory

        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": query},
        ]

    def _load_domain_knowledge(self, query: str) -> str:
        """Load relevant domain knowledge files based on query keywords."""
        knowledge_dir = Path(__file__).parent / "knowledge"
        if not knowledge_dir.exists():
            return ""

        query_lower = query.lower()
        loaded = []

        calib_keywords = ["率定", "calibrat", "优化", "参数", "nse", "算法", "边界"]
        if any(kw in query_lower for kw in calib_keywords):
            guide = knowledge_dir / "calibration_guide.md"
            if guide.exists():
                loaded.append(guide.read_text(encoding="utf-8"))

        model_keywords = ["gr4j", "gr5j", "gr6j", "xaj", "参数含义", "模型选择"]
        if any(kw in query_lower for kw in model_keywords):
            params = knowledge_dir / "model_parameters.md"
            if params.exists():
                loaded.append(params.read_text(encoding="utf-8"))

        if not loaded:
            return ""

        result = []
        for text in loaded:
            if len(text) > 2000:
                text = text[:2000] + "\n...(truncated)"
            result.append(text)

        return "\n\n---\n\n".join(result)

    def _load_system_prompt(self) -> str:
        """Load the system skill file."""
        skill_path = Path(__file__).parent / "skills" / "system.md"
        if skill_path.exists():
            return skill_path.read_text(encoding="utf-8")
        return _DEFAULT_SYSTEM_PROMPT

    # ── Context compression (P0) ─────────────────────────────────────

    def _estimate_tokens(self, messages: list[dict]) -> int:
        """Rough token estimate: ~3 chars per token."""
        total = sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)
        return total // 3

    def _maybe_compress_history(self, messages: list[dict]) -> list[dict]:
        """Compress conversation history when approaching context limit.

        Keeps: system message, original user query, last 4 messages.
        Summarizes everything in between into a single assistant message.
        Triggered when estimated tokens exceed context_compress_threshold
        (default 60,000 tokens, ~180k chars).
        """
        threshold = self.cfg.get("context_compress_threshold", 60_000)
        if self._estimate_tokens(messages) < threshold:
            return messages

        # Need at least system + user + some history to compress
        # Structure: [system(0), user_query(1), ...history..., tail(-4):]
        keep_tail = 4
        if len(messages) <= 2 + keep_tail:
            return messages

        system_msg    = messages[0]
        user_query    = messages[1]
        middle        = messages[2: -keep_tail]
        tail          = messages[-keep_tail:]

        if not middle:
            return messages

        logger.info(
            "Context approaching limit (%d est. tokens), compressing %d messages...",
            self._estimate_tokens(messages), len(middle),
        )

        middle_text = json.dumps(middle, ensure_ascii=False)
        summary_response = self.llm.chat([
            {
                "role": "system",
                "content": (
                    "You are a concise summarizer. "
                    "Summarize the following conversation history in a few bullet points. "
                    "Focus on: which tools were called, what results were obtained, "
                    "what decisions were made. Keep it under 300 words."
                ),
            },
            {"role": "user", "content": middle_text},
        ])

        summary_msg = {
            "role": "assistant",
            "content": "[Earlier conversation summary]\n" + summary_response.text,
        }

        compressed = [system_msg, user_query, summary_msg] + tail
        logger.info(
            "History compressed: %d -> %d est. tokens",
            self._estimate_tokens(messages),
            self._estimate_tokens(compressed),
        )
        self.ui.dev_log(
            f"Context compressed: ~{self._estimate_tokens(messages):,} tokens "
            f"-> ~{self._estimate_tokens(compressed):,} tokens"
        )
        return compressed

    def _execute_tool(self, name: str, arguments: dict) -> Any:
        """Execute a tool function by name."""
        fn = self.tools.get(name)
        if fn is None:
            return {"error": f"Unknown tool: {name}"}

        import inspect
        sig = inspect.signature(fn)
        if "_workspace" in sig.parameters:
            arguments["_workspace"] = self.workspace
        if "_cfg" in sig.parameters:
            arguments["_cfg"] = self.cfg
        if "_llm" in sig.parameters:
            arguments["_llm"] = self.llm

        try:
            result = fn(**arguments)

            # Auto-save basin profile after successful calibration
            if (
                name in ("calibrate_model", "llm_calibrate")
                and isinstance(result, dict)
                and result.get("success")
            ):
                basin_ids = arguments.get("basin_ids", [])
                model_name = arguments.get("model_name", "")
                algorithm = arguments.get("algorithm", "SCE_UA")
                best_params = result.get("best_params", {})
                if name == "calibrate_model":
                    metrics = result.get("metrics", {})
                else:
                    nse = result.get("best_nse")
                    metrics = {"NSE": nse} if nse is not None else {}
                for basin_id in basin_ids:
                    self.memory.save_basin_profile(
                        basin_id, model_name, best_params, metrics, algorithm
                    )

            # If a new skill was created, refresh all registries
            if name == "create_skill" and isinstance(result, dict) and result.get("success"):
                self.tools = discover_tools()
                self.tool_schemas = get_tool_schemas()
                self.skill_registry = SkillRegistry(Path(__file__).parent / "skills")
                logger.info(
                    f"Registries refreshed: {len(self.tools)} tools, "
                    f"{len(self.skill_registry.skills)} skills"
                )
                self.ui.dev_log(
                    f"Registry refreshed: {len(self.tools)} tools, "
                    f"{len(self.skill_registry.skills)} skills"
                )

            return result
        except TypeError as e:
            logger.warning(f"Tool {name} argument error: {e}")
            return {"error": f"Invalid arguments for {name}: {e}"}
        except Exception as e:
            logger.error(f"Tool {name} failed: {e}", exc_info=True)
            return {"error": f"Tool {name} failed: {e}"}


# ── Default system prompt ────────────────────────────────────────────

_DEFAULT_SYSTEM_PROMPT = """You are HydroClaw, an expert hydrological model calibration assistant.

You help users calibrate, evaluate, and analyze hydrological models using the CAMELS dataset.
You can understand both Chinese and English queries.

Choose tools flexibly based on the user's intent. Do NOT apply a fixed workflow to every task:
- Calibration tasks: validate_basin → calibrate_model → evaluate_model → visualize
- Evaluation only: evaluate_model
- Custom analysis: generate_code → run_code
- New capability needed: create_skill

Only call validate_basin when the task involves basin data. Skip it for pure analysis or skill creation.
Always provide professional analysis in the user's language.
"""
