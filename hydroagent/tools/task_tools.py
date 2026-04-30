"""
Author: HydroAgent Team
Date: 2026-03-08
Description: Self-driven task planning tools. Let the agent create and track
             its own multi-step work plan without an external orchestrator.
             The agent calls these tools just like any other tool, so planning
             and execution stay in the same Agentic Loop.
"""

from pathlib import Path

from hydroagent.utils.task_state import TaskState


_ZH = {
    "create_task_list":  ("创建任务列表",  "为批量实验创建多步骤任务计划，自动跳过已完成任务"),
    "get_pending_tasks": ("获取待办任务",  "获取下一个待执行的任务及整体进度概览"),
    "add_task":          ("动态添加任务",  "根据中间结果动态向任务列表追加新任务"),
    "update_task":       ("更新任务状态",  "将任务标记为已完成或失败，记录 NSE/KGE 等指标"),
    "get_task_result":   ("获取任务结果",  "获取已完成任务的结构化结果，用于下游任务读取上游产出"),
}


def _state(workspace: Path | None) -> TaskState:
    ws = workspace or Path(".")
    return TaskState(ws / "task_state.json")


def create_task_list(
    goal: str,
    tasks: list,
    _workspace: Path | None = None,
) -> dict:
    """Create a task list to plan and track a multi-step batch experiment.

    Call this at the start of any batch job (multiple basins, models, or
    scenarios). Each task in the list will be executed one by one. The plan
    is saved to disk so it survives interruptions — if the run is restarted,
    already-completed tasks are skipped automatically.

    After creating the list, use get_pending_tasks() to retrieve the next
    task and update_task() to mark each one done or failed.

    Args:
        goal: Human-readable description of the overall goal, e.g. "Compare GR4J and XAJ on 5 basins"
        tasks: List of tasks. Each item can be either:
            - A plain string: "Calibrate GR4J on basin 12025000"
            - A dict with optional dependency info:
              {"description": "Evaluate on test set", "depends_on": ["task_001", "task_002"]}
              'depends_on' lists task IDs that must be done before this task is eligible.

    Returns:
        {"success": True, "total": N, "goal": "...", "message": "..."}
    """
    s = _state(_workspace)

    # Resume if same goal already exists and has pending tasks
    if s.exists():
        s.load()
        if s.goal == goal and s.pending():
            return {
                "success": True,
                "resumed": True,
                "total": len(s.all_tasks()),
                "pending": len(s.pending()),
                "done": len(s.done()),
                "goal": goal,
                "message": (
                    f"Resumed existing task list: {len(s.pending())} pending, "
                    f"{len(s.done())} already done. Skipping completed tasks."
                ),
            }

    task_dicts = []
    for i, item in enumerate(tasks):
        task_id = f"task_{i+1:03d}"
        if isinstance(item, str):
            task_dicts.append({"id": task_id, "description": item})
        elif isinstance(item, dict):
            task_dicts.append({
                "id": task_id,
                "description": item.get("description", str(item)),
                "depends_on": item.get("depends_on", []),
            })
        else:
            task_dicts.append({"id": task_id, "description": str(item)})

    s.create(goal, task_dicts)
    return {
        "success": True,
        "resumed": False,
        "total": len(task_dicts),
        "pending": len(task_dicts),
        "done": 0,
        "goal": goal,
        "message": f"Task list created with {len(task_dicts)} tasks. Call get_pending_tasks() to start.",
    }


def get_pending_tasks(
    _workspace: Path | None = None,
) -> dict:
    """Get the next pending task and current overall progress.

    Call this after each completed task to decide what to do next.
    Returns the next pending task (if any) and a progress summary.
    When all tasks are done, 'complete' is True — that is the signal to
    generate the final summary report.

    Returns:
        {"complete": False, "next_task": {"id": "...", "description": "..."}, "progress": "...", "done": N, "total": N}
        or {"complete": True, "progress": "...", "results": {...}} when all done
    """
    s = _state(_workspace)
    if not s.exists():
        return {
            "complete": False,
            "next_task": None,
            "message": "No task list found. Call create_task_list() first.",
        }

    s.load()
    progress = s.summary()
    done_ids = {t["id"] for t in s.done()}
    failed_ids = {t["id"] for t in s.failed()}

    # Filter pending tasks whose dependencies are all satisfied
    pending = s.pending()
    ready = [
        t for t in pending
        if all(dep in done_ids for dep in t.get("depends_on", []))
    ]
    # Tasks blocked only by failures (not by pending deps) are effectively stuck
    blocked_by_failure = [
        t for t in pending
        if t not in ready and any(dep in failed_ids for dep in t.get("depends_on", []))
    ]

    if not pending:
        return {
            "complete": True,
            "progress": progress,
            "done": len(s.done()),
            "failed": len(s.failed()),
            "total": len(s.all_tasks()),
            "results": s.results_by_id(),
            "message": "All tasks complete. Generate the final report now.",
        }

    if not ready:
        # All pending tasks are waiting on unfinished dependencies
        waiting_on = [
            dep
            for t in pending
            for dep in t.get("depends_on", [])
            if dep not in done_ids and dep not in failed_ids
        ]
        return {
            "complete": False,
            "next_task": None,
            "progress": progress,
            "done": len(s.done()),
            "failed": len(s.failed()),
            "pending": len(pending),
            "blocked_by_failure": [t["id"] for t in blocked_by_failure],
            "total": len(s.all_tasks()),
            "message": (
                f"No tasks ready yet. Waiting on: {list(set(waiting_on))}. "
                "Check if dependent tasks failed."
            ),
        }

    next_task = ready[0]
    return {
        "complete": False,
        "next_task": {
            "id":          next_task["id"],
            "description": next_task["description"],
        },
        "progress":  progress,
        "done":      len(s.done()),
        "failed":    len(s.failed()),
        "pending":   len(pending),
        "ready":     len(ready),
        "total":     len(s.all_tasks()),
        "message": f"Next: {next_task['description']}. Call update_task() after finishing it.",
    }


def add_task(
    description: str,
    _workspace: Path | None = None,
) -> dict:
    """Dynamically add a new task to the current task list mid-execution.

    Call this when analysis of intermediate results reveals a new hypothesis
    worth testing — for example, if semiarid basins consistently underperform
    with GR4J, add a task to test GR5J on those basins. This enables the agent
    to adapt its plan based on domain reasoning rather than pre-coded rules.

    The new task is appended with 'pending' status and will be returned by
    the next get_pending_tasks() call.

    Args:
        description: What this new task should do, e.g. "Test GR5J on basin 06043500 — GR4J underperformed in semiarid regime"

    Returns:
        {"success": True, "task_id": "task_NNN", "total": N, "message": "..."}
    """
    s = _state(_workspace)
    if not s.exists():
        return {"success": False, "error": "No task list found. Call create_task_list() first."}

    s.load()
    existing_ids = {t["id"] for t in s.all_tasks()}
    # Generate next sequential ID
    n = len(s.all_tasks()) + 1
    while f"task_{n:03d}" in existing_ids:
        n += 1
    task_id = f"task_{n:03d}"

    s._data["tasks"].append({
        "id":          task_id,
        "description": description,
        "status":      "pending",
        "result":      None,
        "error":       None,
        "started_at":  None,
        "finished_at": None,
    })
    s._save()

    return {
        "success":  True,
        "task_id":  task_id,
        "total":    len(s.all_tasks()),
        "pending":  len(s.pending()),
        "message":  f"Task {task_id} added. It will appear in the next get_pending_tasks() call.",
    }


def update_task(
    task_id: str,
    status: str,
    nse: float | None = None,
    kge: float | None = None,
    notes: str = "",
    _workspace: Path | None = None,
) -> dict:
    """Mark a task as done or failed after executing it.

    Call this immediately after completing (or failing) each task returned by
    get_pending_tasks(). Then call get_pending_tasks() again to get the next one.

    Args:
        task_id: The task ID returned by get_pending_tasks(), e.g. "task_001"
        status: "done" if the task succeeded, "failed" if it failed
        nse: NSE metric from the completed calibration/evaluation (optional)
        kge: KGE metric from the completed calibration/evaluation (optional)
        notes: Brief notes about the result or failure reason (optional)

    Returns:
        {"success": True, "task_id": "...", "status": "...", "progress": "..."}
    """
    s = _state(_workspace)
    if not s.exists():
        return {"success": False, "error": "No task list found. Call create_task_list() first."}

    s.load()
    task = s.get(task_id)
    if task is None:
        return {"success": False, "error": f"Task not found: {task_id}"}

    result = {}
    if nse is not None:
        result["NSE"] = nse
    if kge is not None:
        result["KGE"] = kge
    if notes:
        result["notes"] = notes

    if status == "done":
        s.mark_done(task_id, result or None)
    else:
        s.mark_failed(task_id, notes or "unspecified error")

    return {
        "success":  True,
        "task_id":  task_id,
        "status":   status,
        "progress": s.summary(),
        "message":  "Task updated. Call get_pending_tasks() for the next task.",
    }


def get_task_result(
    task_id: str,
    _workspace: Path | None = None,
) -> dict:
    """Retrieve the stored result of a completed task.

    Call this when a downstream task needs to read the output of an upstream
    task, for example: after calibration (task_001) is done, the evaluation
    task (task_002) calls get_task_result("task_001") to get the NSE and
    calibration directory from the previous step.

    For file-based results (e.g. model output netCDF), check the directory
    workflow_output/{task_id}/ in the workspace.

    Args:
        task_id: ID of the completed task, e.g. "task_001"

    Returns:
        {"found": True, "task_id": "...", "status": "done", "result": {...}}
        or {"found": False, "error": "..."} if task not found or not done
    """
    s = _state(_workspace)
    if not s.exists():
        return {"found": False, "error": "No task list found. Call create_task_list() first."}

    s.load()
    task = s.get(task_id)
    if task is None:
        return {"found": False, "error": f"Task not found: {task_id}"}

    status = task.get("status", "unknown")
    result = task.get("result") or {}

    # Also report workflow_output dir if it exists
    ws = _workspace or Path(".")
    output_dir = ws / "workflow_output" / task_id
    file_hints = []
    if output_dir.exists():
        file_hints = [str(p.name) for p in sorted(output_dir.iterdir())[:10]]

    return {
        "found": True,
        "task_id": task_id,
        "status": status,
        "description": task.get("description", ""),
        "result": result,
        "finished_at": task.get("finished_at", ""),
        "workflow_output_dir": str(output_dir) if output_dir.exists() else None,
        "output_files": file_hints,
    }


# ── Chinese UI metadata ────────────────────────────────────────────────────────
for _fn in (create_task_list, get_pending_tasks, add_task, update_task, get_task_result):
    _n, _d = _ZH[_fn.__name__]
    _fn.__zh_name__ = _n
    _fn.__zh_desc__ = _d
