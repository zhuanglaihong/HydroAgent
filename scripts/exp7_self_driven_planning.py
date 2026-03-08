"""
Experiment 7 - Agent 自驱动任务规划与自适应策略
================================================
目的：验证 HydroClaw 的第5个核心创新点：
      Agent 在同一 Agentic Loop 中自主制定计划、追踪进度、根据中间结果调整策略，
      无需外部 Orchestrator，无需人工介入。

三阶段实验：

  Phase A (计划执行): 给定批量目标，验证 Agent 自主创建任务列表并完整执行
    - 验证：create_task_list / get_pending_tasks / update_task 是否被调用
    - 验证：所有任务执行完毕后 task_state.json 状态正确
    - 对比基线：普通 SCE-UA 脚本（硬编码 for 循环，无规划工具）

  Phase B (自适应调整): 给定含困难流域的批量任务，测试 Agent 是否主动追加补救任务
    - 设计：部分流域（半干旱）NSE 预期较低
    - 验证：add_task 是否被调用（体现 LLM 推理驱动的自适应）
    - 注意：P3 自适应是涌现行为，非强制要求，在统计上汇报触发率即可

  Phase C (断点恢复): 模拟中断后恢复，验证已完成任务不被重复执行
    - 操作：预写 task_state.json（部分任务标 done）→ 运行 agent → 检查跳过行为
    - 验证：agent 调用 create_task_list 时识别到已有状态并 resume

论文对应：Section 4.8
对比点：
  - 旧 HydroAgent Orchestrator+5子Agent（架构复杂度对比）
  - 普通批量脚本（硬编码 for 循环，无规划、无恢复、无自适应）
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import logging
import time
from datetime import datetime

import matplotlib
matplotlib.use("Agg")

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("results/paper/exp7")

# ── 实验配置 ──────────────────────────────────────────────────────────────

# Phase A：基础批量执行验证（2流域×2模型=4个任务）
PHASE_A_QUERY = (
    "请帮我比较GR4J和XAJ模型在流域12025000和03439000上的率定性能。"
    "列出任务计划，依次执行，最后给出综合对比报告。"
)

# Phase B：含困难流域的批量任务，测试自适应追加行为
PHASE_B_QUERY = (
    "批量率定以下3个流域的GR4J模型：12025000（湿润）、06043500（半干旱山区）、08101000（半干旱闪洪）。"
    "如果某个流域的NSE低于0.3，请分析原因并考虑是否需要追加LLM智能率定或换用XAJ模型。"
    "全部完成后给出分析报告。"
)

# Phase B 期望工具（子集匹配）
PHASE_B_EXPECTED_TOOLS = [
    "create_task_list", "get_pending_tasks", "calibrate_model", "update_task",
]
PHASE_B_ADAPTIVE_TOOL = "add_task"  # 自适应触发的标志

# Phase C：预写部分完成的 task_state.json，测试断点恢复
PHASE_C_QUERY = (
    "继续批量率定任务：比较GR4J和XAJ在流域12025000和03439000上的性能。"
)
PHASE_C_PRESET_STATE = {
    "goal": "比较GR4J和XAJ在流域12025000和03439000上的性能",
    "created_at": "2026-03-08T00:00:00",
    "updated_at": "2026-03-08T00:00:00",
    "tasks": [
        {
            "id": "task_001",
            "description": "率定GR4J，流域12025000",
            "status": "done",
            "result": {"NSE": 0.72, "notes": "pre-completed for resume test"},
            "error": None,
            "started_at": "2026-03-08T00:00:00",
            "finished_at": "2026-03-08T00:10:00",
        },
        {
            "id": "task_002",
            "description": "率定XAJ，流域12025000",
            "status": "pending",
            "result": None,
            "error": None,
            "started_at": None,
            "finished_at": None,
        },
        {
            "id": "task_003",
            "description": "率定GR4J，流域03439000",
            "status": "pending",
            "result": None,
            "error": None,
            "started_at": None,
            "finished_at": None,
        },
        {
            "id": "task_004",
            "description": "率定XAJ，流域03439000",
            "status": "pending",
            "result": None,
            "error": None,
            "started_at": None,
            "finished_at": None,
        },
    ],
}


def setup_logging():
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(logs_dir / f"exp7_{ts}.log", encoding="utf-8"),
        ],
    )


# ── 工具追踪 patch ────────────────────────────────────────────────────────

def _patch_tool_tracker(agent):
    """Patch agent._execute_tool to record which tools were called in order."""
    called = []
    orig = agent._execute_tool

    def tracked(name, arguments):
        called.append(name)
        return orig(name, arguments)

    agent._execute_tool = tracked
    return called


# ── Phase A ───────────────────────────────────────────────────────────────

def run_phase_a(agent, workspace: Path) -> dict:
    """Verify Agent autonomously creates and executes a task list."""
    logger.info("Phase A: Basic task planning execution")
    state_file = workspace / "task_state.json"
    if state_file.exists():
        state_file.unlink()

    called = _patch_tool_tracker(agent)
    t0 = time.time()
    response = agent.run(PHASE_A_QUERY)
    elapsed = time.time() - t0

    # Check task state file
    state_ok = state_file.exists()
    final_state = {}
    if state_ok:
        final_state = json.loads(state_file.read_text(encoding="utf-8"))

    tasks_total   = len(final_state.get("tasks", []))
    tasks_done    = sum(1 for t in final_state.get("tasks", []) if t["status"] == "done")
    tasks_failed  = sum(1 for t in final_state.get("tasks", []) if t["status"] == "failed")

    planning_tools_used = [t for t in called if t in (
        "create_task_list", "get_pending_tasks", "update_task", "add_task"
    )]

    result = {
        "phase": "A",
        "description": "Basic task planning execution",
        "success": (
            "create_task_list" in called
            and "get_pending_tasks" in called
            and "update_task" in called
            and tasks_total > 0
        ),
        "tools_called":           called,
        "planning_tools_used":    planning_tools_used,
        "create_task_list_called": "create_task_list" in called,
        "get_pending_called":      "get_pending_tasks" in called,
        "update_task_called":      "update_task" in called,
        "task_state_file_created": state_ok,
        "tasks_total":   tasks_total,
        "tasks_done":    tasks_done,
        "tasks_failed":  tasks_failed,
        "completion_rate": tasks_done / tasks_total if tasks_total else 0,
        "elapsed_s":     round(elapsed, 1),
        "response_preview": response[:300],
    }
    _log_phase(result)
    return result


# ── Phase B ───────────────────────────────────────────────────────────────

def run_phase_b(agent, workspace: Path) -> dict:
    """Verify Agent adds adaptive tasks when intermediate NSE is poor."""
    logger.info("Phase B: Adaptive strategy (add_task on poor NSE)")
    state_file = workspace / "task_state.json"
    if state_file.exists():
        state_file.unlink()

    called = _patch_tool_tracker(agent)
    t0 = time.time()
    response = agent.run(PHASE_B_QUERY)
    elapsed = time.time() - t0

    state_ok = state_file.exists()
    final_state = {}
    if state_ok:
        final_state = json.loads(state_file.read_text(encoding="utf-8"))

    tasks_all    = final_state.get("tasks", [])
    tasks_total  = len(tasks_all)
    tasks_done   = sum(1 for t in tasks_all if t["status"] == "done")
    adaptive_triggered = PHASE_B_ADAPTIVE_TOOL in called
    add_task_count     = called.count(PHASE_B_ADAPTIVE_TOOL)

    # Collect NSE values from completed tasks
    nse_values = {}
    for t in tasks_all:
        if t["status"] == "done" and t.get("result"):
            nse = t["result"].get("NSE")
            if nse is not None:
                nse_values[t["id"]] = nse

    result = {
        "phase": "B",
        "description": "Adaptive planning on difficult basins",
        "success": (
            "create_task_list" in called
            and tasks_done >= 3  # at least the 3 original tasks attempted
        ),
        "tools_called":         called,
        "create_task_list_called": "create_task_list" in called,
        "tasks_total":          tasks_total,
        "tasks_done":           tasks_done,
        "completion_rate":      tasks_done / tasks_total if tasks_total else 0,
        "adaptive_triggered":   adaptive_triggered,
        "add_task_count":       add_task_count,
        "nse_values":           nse_values,
        "elapsed_s":            round(elapsed, 1),
        "response_preview":     response[:300],
    }
    _log_phase(result)
    return result


# ── Phase C ───────────────────────────────────────────────────────────────

def run_phase_c(agent, workspace: Path) -> dict:
    """Verify interrupted task list can be resumed without re-running done tasks."""
    logger.info("Phase C: Interruption recovery")
    state_file = workspace / "task_state.json"

    # Pre-write partial state (task_001 already done)
    state_file.write_text(
        json.dumps(PHASE_C_PRESET_STATE, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    called = _patch_tool_tracker(agent)
    t0 = time.time()
    response = agent.run(PHASE_C_QUERY)
    elapsed = time.time() - t0

    final_state = json.loads(state_file.read_text(encoding="utf-8"))
    tasks_all = final_state.get("tasks", [])

    # task_001 was pre-marked done; check it's still done (not re-run)
    task_001 = next((t for t in tasks_all if t["id"] == "task_001"), {})
    skipped_correctly = (
        task_001.get("status") == "done"
        and task_001.get("result", {}).get("notes") == "pre-completed for resume test"
    )

    tasks_done   = sum(1 for t in tasks_all if t["status"] == "done")
    tasks_total  = len(tasks_all)
    resumed      = "create_task_list" in called  # agent called it and got "resumed" response

    result = {
        "phase": "C",
        "description": "Interruption & resume",
        "success": skipped_correctly and resumed,
        "tools_called":           called,
        "resumed_correctly":      resumed,
        "skipped_done_task":      skipped_correctly,
        "tasks_total":            tasks_total,
        "tasks_done":             tasks_done,
        "completion_rate":        tasks_done / tasks_total if tasks_total else 0,
        "elapsed_s":              round(elapsed, 1),
        "response_preview":       response[:300],
    }
    _log_phase(result)
    return result


# ── Summary ───────────────────────────────────────────────────────────────

def _log_phase(r: dict):
    ok = "[PASS]" if r["success"] else "[FAIL]"
    logger.info(f"  Phase {r['phase']} {ok}: {r['description']}")
    if r["phase"] == "A":
        logger.info(
            f"    planning tools: {r['planning_tools_used']}, "
            f"tasks {r['tasks_done']}/{r['tasks_total']} done, "
            f"time={r['elapsed_s']:.0f}s"
        )
    elif r["phase"] == "B":
        logger.info(
            f"    adaptive triggered={r['adaptive_triggered']} (add_task x{r['add_task_count']}), "
            f"tasks {r['tasks_done']}/{r['tasks_total']} done, "
            f"NSE={r['nse_values']}"
        )
    elif r["phase"] == "C":
        logger.info(
            f"    resumed={r['resumed_correctly']}, "
            f"pre-done task skipped={r['skipped_done_task']}, "
            f"tasks {r['tasks_done']}/{r['tasks_total']} done"
        )


def print_summary(results: dict):
    phases = results["phases"]
    print(f"\n{'='*70}")
    print(f"  Exp7: Self-Driven Task Planning & Adaptive Strategy")
    n_pass = sum(1 for p in phases if p["success"])
    print(f"  {n_pass}/{len(phases)} phases passed")
    print(f"{'='*70}")
    for p in phases:
        ok = "PASS" if p["success"] else "FAIL"
        print(f"  Phase {p['phase']} [{ok}]  {p['description']}")
        if p["phase"] == "A":
            print(f"    - Task planning tools used: {p['planning_tools_used']}")
            print(f"    - Tasks completed: {p['tasks_done']}/{p['tasks_total']} "
                  f"({p['completion_rate']*100:.0f}%)")
        elif p["phase"] == "B":
            print(f"    - Adaptive strategy triggered: {p['adaptive_triggered']} "
                  f"(add_task called {p['add_task_count']} times)")
            print(f"    - Tasks completed: {p['tasks_done']}/{p['tasks_total']} "
                  f"({p['completion_rate']*100:.0f}%)")
            if p["nse_values"]:
                for tid, nse in p["nse_values"].items():
                    print(f"      {tid}: NSE={nse:.3f}")
        elif p["phase"] == "C":
            print(f"    - Resumed without re-running done task: {p['skipped_done_task']}")
            print(f"    - Tasks completed: {p['tasks_done']}/{p['tasks_total']} "
                  f"({p['completion_rate']*100:.0f}%)")
    print()


def run_experiment() -> dict:
    from hydroclaw.agent import HydroClaw

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    workspace = OUTPUT_DIR / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    agent = HydroClaw(workspace=workspace)
    phases = []

    phases.append(run_phase_a(agent, workspace))
    phases.append(run_phase_b(agent, workspace))
    phases.append(run_phase_c(agent, workspace))

    return {
        "experiment":  "exp7_self_driven_planning",
        "timestamp":   datetime.now().isoformat(),
        "phases":      phases,
        "n_phases":    len(phases),
        "n_pass":      sum(1 for p in phases if p["success"]),
    }


def save_results(results: dict):
    f = OUTPUT_DIR / "exp7_results.json"
    f.write_text(
        json.dumps(results, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    logger.info(f"Saved -> {f}")


def main():
    setup_logging()
    logger.info("Starting Exp7: Self-Driven Task Planning & Adaptive Strategy")
    results = run_experiment()
    save_results(results)
    print_summary(results)
    logger.info("Exp7 complete")


if __name__ == "__main__":
    main()
