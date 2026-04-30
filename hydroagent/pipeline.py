"""
hydroclaw/pipeline.py — Pipeline execution mode (Plan-and-Execute).

Architecture
------------
Instead of calling the LLM on every tool invocation (ReAct), Pipeline mode
makes a SINGLE LLM call to generate a complete JSON execution plan, then
runs that plan locally with no further LLM involvement — unless a tool fails,
in which case it sends a compact error context to the LLM for recovery.

Token cost:
  ReAct:    N tool calls -> N API calls -> cumulative history (~80K/run)
  Pipeline: 1 planning call + 0-1 error call -> (~10K/run)

Step format (returned by LLM):
  {
    "steps": [
      {"id": "s1", "tool": "validate_basin",
       "args": {"basin_id": "12025000"}, "output_var": "val"},
      {"id": "s2", "tool": "calibrate_model",
       "args": {"basin_id": "$val.basin_id", "model_name": "gr4j"},
       "output_var": "cal"},
      {"id": "s3", "tool": "evaluate_model",
       "args": {"calibration_dir": "$cal.calibration_dir"},
       "output_var": "eval"}
    ]
  }

Variable syntax: "$<output_var>.<field>" is resolved at runtime.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Callable

# Skills directory (relative to this file: hydroclaw/pipeline.py -> hydroclaw/skills/)
_SKILLS_DIR = Path(__file__).parent / "skills"

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Plan schema
# ---------------------------------------------------------------------------

class PipelineStep:
    def __init__(self, d: dict):
        self.id: str = d.get("id", "s?")
        self.tool: str = d["tool"]
        self.args: dict = d.get("args", {})
        self.output_var: str | None = d.get("output_var")

    def __repr__(self):
        return f"Step({self.id}: {self.tool}({self.args}) -> {self.output_var})"


class ExecutionPlan:
    def __init__(self, steps: list[PipelineStep]):
        self.steps = steps

    @classmethod
    def from_dict(cls, d: dict) -> "ExecutionPlan":
        return cls([PipelineStep(s) for s in d.get("steps", [])])

    def summary(self) -> str:
        return " -> ".join(f"{s.tool}" for s in self.steps)


# ---------------------------------------------------------------------------
# Variable resolver
# ---------------------------------------------------------------------------

def _resolve_vars(args: dict, ctx: dict[str, Any]) -> dict:
    """Replace $var.field references with runtime values from ctx."""
    resolved = {}
    for k, v in args.items():
        if isinstance(v, str) and v.startswith("$"):
            # $output_var.field  or  $output_var
            parts = v[1:].split(".", 1)
            var_name = parts[0]
            field = parts[1] if len(parts) > 1 else None
            val = ctx.get(var_name)
            if val is None:
                logger.warning("Variable $%s not found in context", var_name)
                resolved[k] = v  # keep as-is, let tool handle the error
            elif field and isinstance(val, dict):
                resolved[k] = val.get(field, v)
            else:
                resolved[k] = val
        else:
            resolved[k] = v
    return resolved


# ---------------------------------------------------------------------------
# Error KB lookup
# ---------------------------------------------------------------------------

def _lookup_error_kb(tool_name: str, error_type: str, error_msg: str) -> str:
    """Look up the error knowledge base for recovery hints."""
    kb_path = Path(__file__).parent / "knowledge" / "tool_error_kb.md"
    if not kb_path.exists():
        return ""
    text = kb_path.read_text(encoding="utf-8")
    # Find the section for this tool
    tool_section = re.search(
        rf"## {re.escape(tool_name)}\n(.*?)(?=\n## |\Z)",
        text, re.DOTALL
    )
    if not tool_section:
        return ""
    section_text = tool_section.group(1)
    # Score each error entry by keyword overlap with error_msg
    entries = re.split(r"\n### ", section_text)
    best_entry, best_score = "", 0
    keywords = set((error_type + " " + error_msg).lower().split())
    for entry in entries:
        score = sum(1 for kw in keywords if kw in entry.lower())
        if score > best_score:
            best_score, best_entry = score, entry
    return best_entry.strip()[:400] if best_entry else ""


# ---------------------------------------------------------------------------
# Compact error context builder
# ---------------------------------------------------------------------------

def _build_error_context(plan: ExecutionPlan, step: PipelineStep,
                          resolved_args: dict, exc: Exception) -> str:
    error_type = type(exc).__name__
    error_msg = str(exc)[:300]
    kb_hint = _lookup_error_kb(step.tool, error_type, error_msg)

    lines = [
        f"Original plan: {plan.summary()}",
        f"Failed at step: {step.id} ({step.tool})",
        f"Input args: {json.dumps(resolved_args, ensure_ascii=False, default=str)[:300]}",
        f"Error type: {error_type}",
        f"Error summary: {error_msg}",
    ]
    if kb_hint:
        lines.append(f"Knowledge base hint: {kb_hint}")
    lines.append(
        "Reply with JSON: {\"action\": \"retry\"|\"skip\"|\"abort\", "
        "\"reason\": \"...\", \"new_args\": {...}}  (new_args only needed for retry)"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Skill Decision Rules extractor
# ---------------------------------------------------------------------------

def _extract_decision_rules(task: str) -> str:
    """Find the best-matching skill.md and extract its Decision Rules section.

    Matches task keywords against skill front-matter keywords.
    Returns the Decision Rules section text, or "" if no match.
    This text is injected into the planning prompt so the LLM generates a plan
    consistent with the skill's defined workflow order (小脑 -> 大脑 bridge).
    """
    if not _SKILLS_DIR.exists():
        return ""

    task_lower = task.lower()
    best_skill_text = ""
    best_score = 0

    for skill_file in _SKILLS_DIR.glob("*/skill.md"):
        try:
            text = skill_file.read_text(encoding="utf-8")
        except OSError:
            continue
        # Extract keywords from YAML front-matter
        kw_match = re.search(r"keywords:\s*\[([^\]]+)\]", text)
        if not kw_match:
            continue
        keywords = [k.strip().strip("'\"") for k in kw_match.group(1).split(",")]
        score = sum(1 for kw in keywords if kw.lower() in task_lower)
        if score > best_score:
            best_score = score
            best_skill_text = text

    if not best_skill_text or best_score == 0:
        return ""

    # Extract the "## Decision Rules" section
    dr_match = re.search(
        r"## Decision Rules\n(.*?)(?=\n## |\Z)",
        best_skill_text, re.DOTALL
    )
    if not dr_match:
        return ""
    rules = dr_match.group(1).strip()
    # Trim to 800 chars to keep planning prompt lean
    if len(rules) > 800:
        rules = rules[:800] + "\n...(truncated)"
    return rules


# ---------------------------------------------------------------------------
# Pipeline Planner — generates the plan via a single LLM call
# ---------------------------------------------------------------------------

PLAN_SYSTEM_PROMPT = """You are a hydrology workflow planner.
Given a task, output ONLY a JSON execution plan with no other text.

Available tools (name: description):
{tool_list}

Step format:
{{"id": "s1", "tool": "<name>", "args": {{...}}, "output_var": "<var>"}}

Use $var.field to reference outputs of previous steps.
{skill_rules_section}
Example for calibration task:
{{"steps": [
  {{"id": "s1", "tool": "validate_basin", "args": {{"basin_id": "12025000"}}, "output_var": "val"}},
  {{"id": "s2", "tool": "calibrate_model", "args": {{"basin_id": "12025000", "model_name": "xaj"}}, "output_var": "cal"}},
  {{"id": "s3", "tool": "evaluate_model", "args": {{"calibration_dir": "$cal.calibration_dir", "eval_period": null}}, "output_var": "eval_test"}},
  {{"id": "s4", "tool": "evaluate_model", "args": {{"calibration_dir": "$cal.calibration_dir", "eval_period": "train"}}, "output_var": "eval_train"}}
]}}
"""

RECOVERY_SYSTEM_PROMPT = """You are a hydrology workflow error handler.
Respond with JSON only: {"action": "retry"|"skip"|"abort", "reason": "...", "new_args": {...}}
new_args is only needed when action is retry and args need to change."""


class PipelinePlanner:
    def __init__(self, llm, tools: dict[str, Callable]):
        self._llm = llm
        self._tools = tools  # name -> callable

    def _tool_list_text(self) -> str:
        lines = []
        for name, fn in self._tools.items():
            hint = getattr(fn, "__agent_hint__", "")
            doc = (fn.__doc__ or "").strip().split("\n")[0]
            desc = hint or doc or name
            lines.append(f"  {name}: {desc[:120]}")
        return "\n".join(lines)

    def plan(self, task: str) -> ExecutionPlan:
        """Single LLM call -> JSON plan.

        The planning system prompt includes:
        - Available tool list (大脑 context)
        - Matched skill's Decision Rules section (小脑 bridge)
        This means the plan is generated in alignment with the skill's
        prescribed workflow order, not inferred from scratch.
        """
        decision_rules = _extract_decision_rules(task)
        skill_rules_section = (
            f"\nWorkflow rules from matched skill (follow these):\n{decision_rules}\n"
            if decision_rules else ""
        )
        system = PLAN_SYSTEM_PROMPT.format(
            tool_list=self._tool_list_text(),
            skill_rules_section=skill_rules_section,
        )
        response = self._llm.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": task},
            ],
            tools=None,  # no function calling, plain text JSON response
        )
        raw = (response.text or "").strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
        plan_dict = json.loads(raw)
        plan = ExecutionPlan.from_dict(plan_dict)
        self._validate(plan)
        logger.info("[pipeline] Plan: %s", plan.summary())
        return plan

    def _validate(self, plan: ExecutionPlan):
        """Check that all tool names exist and required arg types are sane."""
        for step in plan.steps:
            if step.tool not in self._tools:
                raise ValueError(
                    f"Plan references unknown tool '{step.tool}'. "
                    f"Valid tools: {list(self._tools)[:10]}"
                )

    def recover(self, plan: ExecutionPlan, step: PipelineStep,
                resolved_args: dict, exc: Exception) -> dict:
        """Single LLM call -> recovery decision."""
        error_ctx = _build_error_context(plan, step, resolved_args, exc)
        response = self._llm.chat(
            messages=[
                {"role": "system", "content": RECOVERY_SYSTEM_PROMPT},
                {"role": "user", "content": error_ctx},
            ],
            tools=None,
        )
        raw = (response.text or "").strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
        return json.loads(raw)


# ---------------------------------------------------------------------------
# Local Executor — runs plan without LLM
# ---------------------------------------------------------------------------

class PipelineResult:
    def __init__(self):
        self.steps_done: list[str] = []
        self.ctx: dict[str, Any] = {}
        self.success: bool = False
        self.error_step: str | None = None
        self.error: str | None = None
        self.elapsed_s: float = 0.0
        self.token_cost: dict = {}

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "steps_done": self.steps_done,
            "outputs": {k: v for k, v in self.ctx.items()},
            "error_step": self.error_step,
            "error": self.error,
            "elapsed_s": round(self.elapsed_s, 1),
        }


class LocalExecutor:
    """Runs an ExecutionPlan without calling the LLM between steps."""

    def __init__(self, tools: dict[str, Callable],
                 planner: PipelinePlanner | None = None,
                 ui=None):
        self._tools = tools
        self._planner = planner  # optional: if set, errors trigger LLM recovery
        self._ui = ui

    def run(self, plan: ExecutionPlan, extra_ctx: dict | None = None) -> PipelineResult:
        result = PipelineResult()
        ctx: dict[str, Any] = dict(extra_ctx or {})
        t0 = time.time()

        for step in plan.steps:
            resolved_args = _resolve_vars(step.args, ctx)
            logger.info("[pipeline] Running %s(%s)", step.tool, resolved_args)
            if self._ui:
                self._ui.on_tool_call(step.tool, resolved_args)

            fn = self._tools.get(step.tool)
            if fn is None:
                result.error_step = step.id
                result.error = f"Tool '{step.tool}' not found"
                result.elapsed_s = time.time() - t0
                return result

            try:
                tool_result = fn(**resolved_args)
                if step.output_var:
                    ctx[step.output_var] = tool_result
                result.steps_done.append(step.id)
                if self._ui:
                    self._ui.on_tool_result(step.tool, tool_result)

            except Exception as exc:
                logger.warning("[pipeline] Step %s failed: %s", step.id, exc)
                recovery = self._try_recover(plan, step, resolved_args, exc)

                action = recovery.get("action", "abort")
                if action == "skip":
                    logger.info("[pipeline] Skipping step %s: %s", step.id, recovery.get("reason"))
                    result.steps_done.append(step.id + "(skipped)")
                elif action == "retry":
                    new_args = recovery.get("new_args", resolved_args)
                    try:
                        tool_result = fn(**new_args)
                        if step.output_var:
                            ctx[step.output_var] = tool_result
                        result.steps_done.append(step.id + "(retried)")
                    except Exception as exc2:
                        result.error_step = step.id
                        result.error = f"Retry failed: {exc2}"
                        result.elapsed_s = time.time() - t0
                        return result
                else:  # abort
                    result.error_step = step.id
                    result.error = str(exc)
                    result.elapsed_s = time.time() - t0
                    return result

        result.ctx = ctx
        result.success = True
        result.elapsed_s = time.time() - t0
        return result

    def _try_recover(self, plan, step, resolved_args, exc) -> dict:
        if self._planner is None:
            logger.info("[pipeline] No planner set, aborting on error")
            return {"action": "abort"}
        try:
            return self._planner.recover(plan, step, resolved_args, exc)
        except Exception as e:
            logger.warning("[pipeline] Recovery LLM call failed: %s", e)
            return {"action": "abort"}


# ---------------------------------------------------------------------------
# Top-level entry point: run a task in pipeline mode
# ---------------------------------------------------------------------------

def run_pipeline(task: str, llm, tools: dict[str, Callable],
                 ui=None, extra_ctx: dict | None = None) -> PipelineResult:
    """Plan-and-execute a task with minimal LLM calls.

    Args:
        task:      Natural language task description.
        llm:       HydroClaw LLM client (must support .chat(messages, system, tools)).
        tools:     Dict of {name: callable} from discover_tools().
        ui:        Optional UI callback object.
        extra_ctx: Pre-populated variables (e.g., workspace path).

    Returns:
        PipelineResult with .success, .ctx (outputs), .steps_done, .error.
    """
    planner = PipelinePlanner(llm, tools)
    executor = LocalExecutor(tools, planner=planner, ui=ui)

    try:
        plan = planner.plan(task)
    except Exception as exc:
        r = PipelineResult()
        r.error = f"Planning failed: {exc}"
        return r

    return executor.run(plan, extra_ctx=extra_ctx)
