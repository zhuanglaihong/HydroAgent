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
from hydroclaw.skill_states import SkillStateManager
from hydroclaw.tools import discover_tools, get_tool_schemas
from hydroclaw.utils.context_utils import estimate_tokens, truncate_tool_result
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
        self._pause_requested = False   # set by request_pause(); checked between turns

        skills_dir = Path(__file__).parent / "skills"
        self.skill_registry = SkillRegistry(skills_dir)
        self.skill_states = SkillStateManager(skills_dir)

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
        self.llm.tokens.reset()   # reset per-session counter

        # Token budget (0 = unlimited). If set, agent is informed at start
        # and receives progressive warnings as it approaches the limit.
        self._session_budget = self.cfg.get("session_budget_tokens", 0)
        if self._session_budget:
            budget_note = (
                f"\n\n[System] Token budget for this session: {self._session_budget:,} tokens. "
                f"Monitor your usage. When approaching the limit, prioritize wrapping up "
                f"completed work over starting new sub-tasks."
            )
            messages[0]["content"] += budget_note
            logger.info(f"Session budget: {self._session_budget:,} tokens")

        logger.info(f"Starting agentic loop for: {query[:80]}...")
        self.ui.on_query(query)

        _consecutive: dict[str, int] = {}   # tool_name -> consecutive call count
        _MAX_CONSECUTIVE = 4                 # stop loop if same tool called >4 times in a row

        _total_calls: dict[str, int] = {}    # tool_name -> total calls this session
        # When a tool has been called this many times total without resolving the task,
        # inject a system nudge to use ask_user or stop instead of keep retrying.
        _TOTAL_WARN_AT = {
            "generate_code": 3,
            "run_code":       5,
            "inspect_dir":    4,
        }
        _total_warned: set[str] = set()      # tools already warned about (once per session)

        for turn in range(self.max_turns):
            logger.debug(f"Turn {turn + 1}/{self.max_turns}")

            # Check pause flag (set by request_pause() between turns)
            if self._pause_requested:
                self._pause_requested = False
                msg = "已暂停。任务状态已保存，输入 /resume 继续批量任务。"
                self.memory.save_session(query, msg)
                self.ui.on_answer(msg, turn)
                return msg

            messages = self._maybe_compress_history(messages)

            # Per-turn token budget awareness
            est_tokens = estimate_tokens(messages)
            tok_so_far = self.llm.tokens.summary()
            used = tok_so_far["total_tokens"]
            logger.debug(
                "Turn %d | context ~%d est. tokens | session used: %d tokens",
                turn + 1, est_tokens, used,
            )

            if self._session_budget and self._session_budget > 0:
                ratio = used / self._session_budget
                remaining = self._session_budget - used
                if ratio >= 1.0:
                    # Over budget — inject stop signal, let agent give final answer
                    stop_msg = (
                        f"[System] Token budget exhausted: {used:,}/{self._session_budget:,} tokens used. "
                        f"Do NOT call any more tools. Immediately summarize all completed work "
                        f"and give your final answer now."
                    )
                    logger.warning("Token budget exhausted (%d/%d). Injecting stop signal.", used, self._session_budget)
                    self.ui.dev_log(f"Token budget exhausted: {used:,}/{self._session_budget:,}")
                    messages.append({"role": "user", "content": stop_msg})
                elif ratio >= 0.8:
                    # 80%+ used — warn agent, let it decide
                    warn_msg = (
                        f"[System] Token budget warning: {used:,}/{self._session_budget:,} tokens used "
                        f"({ratio*100:.0f}%, ~{remaining:,} remaining). "
                        f"Prioritize completing in-progress tasks over starting new ones. "
                        f"If the current task cannot be finished within the budget, summarize progress and stop."
                    )
                    logger.warning("Token budget at %.0f%% (%d/%d).", ratio * 100, used, self._session_budget)
                    self.ui.dev_log(f"Token budget: {ratio*100:.0f}% ({used:,}/{self._session_budget:,})")
                    messages.append({"role": "user", "content": warn_msg})
                elif ratio >= 0.6:
                    logger.info("Token budget: %.0f%% used (%d/%d).", ratio * 100, used, self._session_budget)
                    self.ui.dev_log(f"Token budget: {ratio*100:.0f}% ({used:,}/{self._session_budget:,})")

            with self.ui.thinking(turn + 1):
                response = self.llm.chat(messages, tools=self.tool_schemas)

            if response.is_text():
                tok = self.llm.tokens.summary()
                logger.info(
                    f"Completed in {turn + 1} turns | "
                    f"tokens: prompt={tok['prompt_tokens']:,} "
                    f"completion={tok['completion_tokens']:,} "
                    f"total={tok['total_tokens']:,} "
                    f"calls={tok['calls']}"
                )
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
                    # Consecutive-call guard: abort if same tool is stuck in a loop
                    _consecutive[tc.name] = _consecutive.get(tc.name, 0) + 1
                    for other in list(_consecutive):
                        if other != tc.name:
                            _consecutive[other] = 0
                    if _consecutive[tc.name] > _MAX_CONSECUTIVE:
                        loop_msg = (
                            f"Tool `{tc.name}` has been called {_consecutive[tc.name]} times "
                            f"consecutively. Stopping to avoid a runaway loop. "
                            "Please summarize what you have accomplished so far and stop."
                        )
                        logger.warning(loop_msg)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps({"error": loop_msg, "success": False}),
                        })
                        break

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
                        "content": truncate_tool_result(tc.name, result),
                    })

                    # Total-call guard: catch alternating loops (e.g. generate_code->run_code->...)
                    _total_calls[tc.name] = _total_calls.get(tc.name, 0) + 1
                    warn_at = _TOTAL_WARN_AT.get(tc.name)
                    if (
                        warn_at
                        and _total_calls[tc.name] >= warn_at
                        and tc.name not in _total_warned
                    ):
                        _total_warned.add(tc.name)
                        nudge = (
                            f"[System] `{tc.name}` has been called {_total_calls[tc.name]} times "
                            f"this session without fully resolving the task. "
                            f"Repeating the same approach is unlikely to help. "
                            f"If critical information is missing, use `ask_user` to get it from the user. "
                            f"If the task cannot be completed, stop and report what went wrong."
                        )
                        logger.warning(
                            "Total-call nudge: %s called %d times.", tc.name, _total_calls[tc.name]
                        )
                        messages.append({"role": "user", "content": nudge})

            else:
                # Prompt-based fallback
                if response.text:
                    messages.append({"role": "assistant", "content": response.text})

                for tc in response.tool_calls:
                    # Consecutive-call guard (same logic as function-calling branch)
                    _consecutive[tc.name] = _consecutive.get(tc.name, 0) + 1
                    for other in list(_consecutive):
                        if other != tc.name:
                            _consecutive[other] = 0
                    if _consecutive[tc.name] > _MAX_CONSECUTIVE:
                        loop_msg = (
                            f"Tool `{tc.name}` called {_consecutive[tc.name]} times "
                            "consecutively. Stopping loop. Summarize and stop."
                        )
                        logger.warning(loop_msg)
                        messages.append({
                            "role": "user",
                            "content": f"SYSTEM: {loop_msg}",
                        })
                        break

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
                        "role": "user",
                        "content": f"Tool `{tc.name}` returned:\n```json\n{truncate_tool_result(tc.name, result)}\n```\nContinue with the next step.",
                    })

                    # Total-call guard (prompt-based branch)
                    _total_calls[tc.name] = _total_calls.get(tc.name, 0) + 1
                    warn_at = _TOTAL_WARN_AT.get(tc.name)
                    if (
                        warn_at
                        and _total_calls[tc.name] >= warn_at
                        and tc.name not in _total_warned
                    ):
                        _total_warned.add(tc.name)
                        nudge = (
                            f"[System] `{tc.name}` has been called {_total_calls[tc.name]} times "
                            f"this session without fully resolving the task. "
                            f"Repeating the same approach is unlikely to help. "
                            f"If critical information is missing, use `ask_user` to get it from the user. "
                            f"If the task cannot be completed, stop and report what went wrong."
                        )
                        logger.warning(
                            "Total-call nudge: %s called %d times.", tc.name, _total_calls[tc.name]
                        )
                        messages.append({"role": "user", "content": nudge})

        logger.warning(f"Reached max turns ({self.max_turns})")
        self.ui.on_max_turns()
        final = "已达到最大步骤数，请检查已有结果。"
        self.memory.save_session(query, final)
        return final

    # Hard limits for context injection (chars). Prevents runaway memory from
    # bloating the system prompt with accumulated session data.
    _MAX_MEMORY_CHARS   = 4_000   # load_knowledge() cap
    _MAX_PROFILE_CHARS  = 3_000   # basin profiles cap
    _MAX_SYSTEM_CHARS   = 20_000  # total system prompt cap — warn if exceeded
    _WARN_CONTEXT_TOKENS = 30_000 # warn if initial context already exceeds this

    def _build_context(self, query: str) -> list[dict]:
        """Build initial message context: system prompt + domain knowledge + skills + memory.

        P3 change: skill content is NO LONGER injected here. Only a skill list with
        file paths is provided. The agent reads the relevant skill.md at runtime via
        read_file, which makes skill selection an active decision rather than passive
        information reception.
        """
        system = self._load_system_prompt()
        domain_knowledge = self._load_domain_knowledge(query)
        available_skills = self.skill_registry.available_skills_prompt(self.skill_states)
        memory = self.memory.load_knowledge()
        if len(memory) > self._MAX_MEMORY_CHARS:
            memory = memory[:self._MAX_MEMORY_CHARS] + "\n...(memory truncated to avoid context overflow)"
            logger.warning("Memory truncated to %d chars in _build_context", self._MAX_MEMORY_CHARS)

        # Load basin profiles for any 8-digit basin IDs mentioned in the query
        basin_ids_in_query = re.findall(r'\b\d{8}\b', query)
        basin_profiles = self.memory.format_basin_profiles_for_context(basin_ids_in_query)
        if len(basin_profiles) > self._MAX_PROFILE_CHARS:
            basin_profiles = basin_profiles[:self._MAX_PROFILE_CHARS] + "\n...(profile truncated)"
            logger.warning("Basin profiles truncated to %d chars", self._MAX_PROFILE_CHARS)

        system_content = system
        if available_skills:
            system_content += "\n\n" + available_skills
        if domain_knowledge:
            system_content += "\n\n## Domain Knowledge\n" + domain_knowledge
        if basin_profiles:
            system_content += "\n\n" + basin_profiles
        if memory:
            system_content += "\n\n## Memory (from previous sessions)\n" + memory

        # Sanity check: warn if system prompt is abnormally large
        if len(system_content) > self._MAX_SYSTEM_CHARS:
            logger.error(
                "System prompt is abnormally large: %d chars (~%d est. tokens). "
                "This will consume excessive API quota. Check memory/profile injection.",
                len(system_content), len(system_content) // 3,
            )
            self.ui.dev_log(
                f"WARNING: system prompt = {len(system_content):,} chars "
                f"(~{len(system_content)//3:,} est. tokens). May hit API limits."
            )

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": query},
        ]

        # Pre-flight token budget check
        est = estimate_tokens(messages)
        if est > self._WARN_CONTEXT_TOKENS:
            logger.warning(
                "Initial context already ~%d est. tokens before any tool calls. "
                "Consider reducing memory or knowledge injection.",
                est,
            )

        return messages

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

    def request_pause(self):
        """Request the agent to pause after the current turn completes."""
        self._pause_requested = True

    # ── Context compression ──────────────────────────────────────────

    def _maybe_compress_history(self, messages: list[dict]) -> list[dict]:
        """Compress conversation history when approaching context limit.

        Keeps: system message, original user query, last 4 messages.
        Summarizes everything in between into a single assistant message.
        Triggered when estimated tokens exceed context_compress_threshold
        (default 60,000 tokens, ~180k chars).
        """
        threshold = self.cfg.get("context_compress_threshold", 60_000)
        est = estimate_tokens(messages)
        if est < threshold:
            return messages

        # Safety: if estimated tokens are impossibly large (likely a bug in
        # memory/knowledge injection), refuse to send and raise immediately
        # rather than consuming API quota on a doomed request.
        _HARD_LIMIT = 500_000  # ~1.5M chars — no legitimate context exceeds this
        if est > _HARD_LIMIT:
            raise RuntimeError(
                f"Context size is abnormally large: ~{est:,} est. tokens "
                f"({est * 3:,} chars). This is almost certainly caused by "
                f"excessive memory or knowledge injection. Aborting to protect "
                f"API quota. Check memory.load_knowledge() and basin profiles."
            )

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
            estimate_tokens(messages), len(middle),
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
            estimate_tokens(messages),
            estimate_tokens(compressed),
        )
        self.ui.dev_log(
            f"Context compressed: ~{estimate_tokens(messages):,} tokens "
            f"-> ~{estimate_tokens(compressed):,} tokens"
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
        if "_ui" in sig.parameters:
            arguments["_ui"] = self.ui

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

            # Show task progress after any task-state-mutating tool
            if name in ("create_task_list", "update_task", "add_task") and isinstance(result, dict) and result.get("success"):
                self.ui.on_task_progress(self.workspace)

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

            # Update skill lifecycle state for generated skills
            if self.skill_states.is_generated(name):
                success = isinstance(result, dict) and result.get("success", False)
                err = result.get("error") if isinstance(result, dict) else None
                self.skill_states.record_execution(name, success=success, error=err)

            return result
        except TypeError as e:
            logger.warning(f"Tool {name} argument error: {e}")
            if self.skill_states.is_generated(name):
                self.skill_states.record_execution(name, success=False, error=str(e))
            return {"error": f"Invalid arguments for {name}: {e}"}
        except Exception as e:
            logger.error(f"Tool {name} failed: {e}", exc_info=True)
            if self.skill_states.is_generated(name):
                self.skill_states.record_execution(name, success=False, error=str(e))
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
