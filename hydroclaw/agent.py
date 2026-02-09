"""
Author: HydroClaw Team
Date: 2026-02-08
Description: Agentic Loop core - the heart of HydroClaw.
             LLM decides what to do, code only executes.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any

from hydroclaw.config import load_config
from hydroclaw.llm import LLMClient, LLMResponse
from hydroclaw.memory import Memory
from hydroclaw.tools import discover_tools, get_tool_schemas

logger = logging.getLogger(__name__)


class HydroClaw:
    """LLM-driven hydrological model calibration agent.

    Core loop: Query → LLM reasons → calls tools → LLM reasons → ... → final answer.
    No state machine, no if-else routing, no multi-agent orchestration.
    """

    def __init__(self, config_path: str | Path | None = None, workspace: Path | None = None):
        self.cfg = load_config(config_path)
        self.llm = LLMClient(self.cfg["llm"])
        self.memory = Memory(workspace or Path("."))
        self.tools = discover_tools()
        self.tool_schemas = get_tool_schemas()
        self.max_turns = self.cfg.get("max_turns", 30)
        self.workspace = workspace or Path(".")

        logger.info(
            f"HydroClaw initialized: {len(self.tools)} tools, "
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
        _print_user(query)

        for turn in range(self.max_turns):
            logger.debug(f"Turn {turn + 1}/{self.max_turns}")

            response = self.llm.chat(messages, tools=self.tool_schemas)

            if response.is_text():
                # LLM produced a final text answer → done
                logger.info(f"Completed in {turn + 1} turns")
                self.memory.save_session(query, response.text)
                _print_assistant(response.text)
                return response.text

            # LLM wants to call tools
            if self.llm.supports_function_calling:
                # Native function calling: use proper tool message format
                # Build assistant message with all tool calls
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
                    _print_tool_call(tc.name, tc.arguments)
                    result = self._execute_tool(tc.name, tc.arguments)
                    self.memory.log_tool_call(tc.name, tc.arguments, result)
                    _print_tool_result(tc.name, result)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    })
            else:
                # Prompt-based fallback: use user/assistant message format
                if response.text:
                    messages.append({"role": "assistant", "content": response.text})

                for tc in response.tool_calls:
                    _print_tool_call(tc.name, tc.arguments)
                    result = self._execute_tool(tc.name, tc.arguments)
                    self.memory.log_tool_call(tc.name, tc.arguments, result)
                    _print_tool_result(tc.name, result)

                    result_text = json.dumps(result, ensure_ascii=False, default=str)
                    messages.append({
                        "role": "user",
                        "content": f"Tool `{tc.name}` returned:\n```json\n{result_text}\n```\nContinue with the next step.",
                    })

        # Exceeded max turns
        logger.warning(f"Reached max turns ({self.max_turns})")
        final = "I've reached the maximum number of steps. Here's what I've done so far - please check the results."
        self.memory.save_session(query, final)
        return final

    def _build_context(self, query: str) -> list[dict]:
        """Build initial message context: system prompt + skills + memory."""
        system = self._load_system_prompt()
        skill = self._match_skill(query)
        knowledge = self.memory.load_knowledge()

        system_content = system
        if skill:
            system_content += "\n\n" + skill
        if knowledge:
            system_content += "\n\n## Memory (from previous sessions)\n" + knowledge

        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": query},
        ]

    def _load_system_prompt(self) -> str:
        """Load the system skill file."""
        skill_path = Path(__file__).parent / "skills" / "system.md"
        if skill_path.exists():
            return skill_path.read_text(encoding="utf-8")
        return _DEFAULT_SYSTEM_PROMPT

    def _match_skill(self, query: str) -> str | None:
        """Match query to the most relevant skill file based on keywords."""
        skills_dir = Path(__file__).parent / "skills"
        if not skills_dir.exists():
            return None

        query_lower = query.lower()

        # Keyword → skill file mapping
        skill_map = {
            "calibration.md": ["率定", "calibrat", "优化参数", "参数优化"],
            "llm_calibration.md": ["ai率定", "智能率定", "专家模式", "llm率定", "ai calibrat"],
            "iterative.md": ["迭代", "iterativ", "边界", "boundary", "反复"],
            "comparison.md": ["对比", "比较", "compar", "多模型", "两个模型"],
            "batch.md": ["批量", "batch", "多个流域", "多流域"],
            "analysis.md": ["分析", "analysis", "fdc", "径流系数", "runoff", "代码", "code", "画图", "绘图"],
        }

        for filename, keywords in skill_map.items():
            if any(kw in query_lower for kw in keywords):
                skill_file = skills_dir / filename
                if skill_file.exists():
                    logger.debug(f"Matched skill: {filename}")
                    return skill_file.read_text(encoding="utf-8")

        # Default: load calibration skill for calibration-related queries
        default_skill = skills_dir / "calibration.md"
        if default_skill.exists():
            return default_skill.read_text(encoding="utf-8")

        return None

    def _execute_tool(self, name: str, arguments: dict) -> Any:
        """Execute a tool function by name."""
        fn = self.tools.get(name)
        if fn is None:
            return {"error": f"Unknown tool: {name}"}

        # Inject internal parameters
        import inspect
        sig = inspect.signature(fn)
        if "_workspace" in sig.parameters:
            arguments["_workspace"] = self.workspace
        if "_cfg" in sig.parameters:
            arguments["_cfg"] = self.cfg
        if "_llm" in sig.parameters:
            arguments["_llm"] = self.llm

        try:
            return fn(**arguments)
        except TypeError as e:
            # Handle argument mismatches gracefully
            logger.warning(f"Tool {name} argument error: {e}")
            return {"error": f"Invalid arguments for {name}: {e}"}
        except Exception as e:
            logger.error(f"Tool {name} failed: {e}", exc_info=True)
            return {"error": f"Tool {name} failed: {e}"}


# ── Console output helpers ──────────────────────────────────────────────

def _print_user(query: str):
    print(f"\n{'='*60}")
    print(f"  User: {query}")
    print(f"{'='*60}\n")


def _print_assistant(text: str):
    print(f"\n{'─'*60}")
    print(text)
    print(f"{'─'*60}\n")


def _print_tool_call(name: str, args: dict):
    args_preview = json.dumps(args, ensure_ascii=False)
    if len(args_preview) > 200:
        args_preview = args_preview[:200] + "..."
    print(f"  >> Calling: {name}({args_preview})")


def _print_tool_result(name: str, result: Any):
    if isinstance(result, dict):
        success = result.get("success", True)
        error = result.get("error")
        if error:
            print(f"  << {name}: ERROR - {error}")
        elif "metrics" in result:
            metrics = result["metrics"]
            print(f"  << {name}: {metrics}")
        elif "valid_basins" in result:
            print(f"  << {name}: valid={result.get('valid_basins')}")
        elif "plot_count" in result:
            print(f"  << {name}: {result['plot_count']} plots generated")
        elif "calibration_dir" in result:
            print(f"  << {name}: dir={result['calibration_dir']}")
        else:
            summary = str(result)
            if len(summary) > 200:
                summary = summary[:200] + "..."
            print(f"  << {name}: {summary}")
    else:
        print(f"  << {name}: done")


# ── Default system prompt (fallback if system.md not found) ─────────

_DEFAULT_SYSTEM_PROMPT = """You are HydroClaw, an expert hydrological model calibration assistant.

You help users calibrate, evaluate, and analyze hydrological models using the CAMELS dataset.
You can understand both Chinese and English queries.

When the user asks you to calibrate a model, follow these steps:
1. Validate the basin data
2. Run calibration
3. Evaluate on test period
4. Generate visualizations
5. Provide analysis in Chinese

Always provide clear, professional analysis of the results.
Use the available tools to accomplish tasks - do NOT try to do everything in one step.
"""
