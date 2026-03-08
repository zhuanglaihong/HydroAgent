"""
Author: HydroClaw Team
Date: 2026-03-08
Description: Self-driven task planning tools. Let the agent create and track
             its own multi-step work plan without an external orchestrator.
             The agent calls these tools just like any other tool, so planning
             and execution stay in the same Agentic Loop.
"""

from pathlib import Path

from hydroclaw.task_state import TaskState


def _state(workspace: Path | None) -> TaskState:
    ws = workspace or Path(".")
    return TaskState(ws / "task_state.json")


def create_task_list(
    goal: str,
    tasks: list[str],
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
        tasks: List of task descriptions in execution order, e.g. ["Calibrate GR4J on basin 12025000", "Calibrate XAJ on basin 12025000"]

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

    task_dicts = [
        {"id": f"task_{i+1:03d}", "description": desc}
        for i, desc in enumerate(tasks)
    ]
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
    pending = s.pending()
    progress = s.summary()

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

    next_task = pending[0]
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
