"""
Author: Claude
Date: 2025-01-25 10:00:00
LastEditTime: 2025-01-25 10:00:00
LastEditors: Claude
Description: Checkpoint manager for task interruption and recovery
             任务中断和恢复的检查点管理器
FilePath: /HydroAgent/hydroagent/core/checkpoint_manager.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

功能:
- 保存任务执行状态到检查点文件
- 从检查点文件恢复执行状态
- 跟踪已完成的子任务
- 支持任务暂停和继续
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class CheckpointManager:
    """
    管理任务执行的检查点，支持中断和恢复。

    检查点文件结构:
    {
        "version": "1.0",
        "experiment_name": "exp_2a_repeated_calibration",
        "query": "用户查询...",
        "created_at": "2025-01-25T10:00:00",
        "last_updated": "2025-01-25T10:15:00",
        "status": "in_progress",  # pending, in_progress, completed, failed
        "total_tasks": 20,
        "completed_tasks": 5,
        "failed_tasks": 0,
        "current_phase": "runner",  # intent, planner, interpreter, runner, developer
        "intent_result": {...},
        "task_plan": {...},
        "subtasks_status": {
            "task_1_phase1_rep1": {
                "status": "completed",
                "config": {...},
                "result": {...},
                "completed_at": "2025-01-25T10:05:00"
            },
            "task_2_phase1_rep2": {
                "status": "in_progress",
                "config": {...},
                "started_at": "2025-01-25T10:14:00"
            },
            "task_3_phase1_rep3": {
                "status": "pending"
            }
        }
    }
    """

    CHECKPOINT_VERSION = "1.0"
    CHECKPOINT_FILENAME = "checkpoint.json"

    def __init__(self, workspace_dir: Path):
        """
        初始化检查点管理器。

        Args:
            workspace_dir: 实验工作目录
        """
        self.workspace_dir = Path(workspace_dir)
        self.checkpoint_file = self.workspace_dir / self.CHECKPOINT_FILENAME
        self.checkpoint_data: Optional[Dict[str, Any]] = None

        # 如果checkpoint文件存在，自动加载
        if self.checkpoint_file.exists():
            self.load()

    def initialize(
        self,
        experiment_name: str,
        query: str,
        total_tasks: int = 0
    ) -> None:
        """
        初始化一个新的检查点。

        Args:
            experiment_name: 实验名称
            query: 用户查询
            total_tasks: 总任务数（可能在task planning后更新）
        """
        self.checkpoint_data = {
            "version": self.CHECKPOINT_VERSION,
            "experiment_name": experiment_name,
            "query": query,
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "status": "pending",
            "total_tasks": total_tasks,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "current_phase": "intent",
            "intent_result": None,
            "task_plan": None,
            "subtasks_status": {}
        }

        self.save()
        logger.info(f"Checkpoint initialized: {self.checkpoint_file}")

    def update_phase(self, phase: str) -> None:
        """
        更新当前执行阶段。

        Args:
            phase: 阶段名称 (intent, planner, interpreter, runner, developer)
        """
        if self.checkpoint_data is None:
            raise RuntimeError("Checkpoint not initialized")

        self.checkpoint_data["current_phase"] = phase
        self.checkpoint_data["last_updated"] = datetime.now().isoformat()
        self.save()
        logger.debug(f"Checkpoint phase updated: {phase}")

    def save_intent_result(self, intent_result: Dict[str, Any]) -> None:
        """
        保存Intent阶段的结果。

        Args:
            intent_result: IntentAgent返回的结果
        """
        if self.checkpoint_data is None:
            raise RuntimeError("Checkpoint not initialized")

        self.checkpoint_data["intent_result"] = intent_result
        self.checkpoint_data["last_updated"] = datetime.now().isoformat()
        self.save()
        logger.debug("Intent result saved to checkpoint")

    def save_task_plan(self, task_plan: Dict[str, Any]) -> None:
        """
        保存TaskPlanner的结果，并初始化所有subtask状态。

        Args:
            task_plan: TaskPlanner返回的任务计划
        """
        if self.checkpoint_data is None:
            raise RuntimeError("Checkpoint not initialized")

        self.checkpoint_data["task_plan"] = task_plan

        # 初始化所有subtask的状态
        subtasks = task_plan.get("subtasks", [])
        self.checkpoint_data["total_tasks"] = len(subtasks)

        for subtask in subtasks:
            task_id = subtask["task_id"]
            if task_id not in self.checkpoint_data["subtasks_status"]:
                self.checkpoint_data["subtasks_status"][task_id] = {
                    "status": "pending",
                    "subtask_info": subtask
                }

        self.checkpoint_data["last_updated"] = datetime.now().isoformat()
        self.save()
        logger.debug(f"Task plan saved: {len(subtasks)} subtasks initialized")

    def mark_subtask_started(self, task_id: str, config: Dict[str, Any]) -> None:
        """
        标记一个子任务开始执行。

        Args:
            task_id: 子任务ID
            config: 子任务的配置
        """
        if self.checkpoint_data is None:
            raise RuntimeError("Checkpoint not initialized")

        if task_id not in self.checkpoint_data["subtasks_status"]:
            self.checkpoint_data["subtasks_status"][task_id] = {}

        self.checkpoint_data["subtasks_status"][task_id].update({
            "status": "in_progress",
            "config": config,
            "started_at": datetime.now().isoformat()
        })

        self.checkpoint_data["last_updated"] = datetime.now().isoformat()
        self.save()
        logger.info(f"Subtask started: {task_id}")

    def mark_subtask_completed(
        self,
        task_id: str,
        result: Dict[str, Any]
    ) -> None:
        """
        标记一个子任务完成。

        Args:
            task_id: 子任务ID
            result: 子任务的执行结果
        """
        if self.checkpoint_data is None:
            raise RuntimeError("Checkpoint not initialized")

        if task_id not in self.checkpoint_data["subtasks_status"]:
            logger.warning(f"Task {task_id} not found in checkpoint")
            return

        self.checkpoint_data["subtasks_status"][task_id].update({
            "status": "completed",
            "result": result,
            "completed_at": datetime.now().isoformat()
        })

        self.checkpoint_data["completed_tasks"] += 1
        self.checkpoint_data["last_updated"] = datetime.now().isoformat()
        self.save()
        logger.info(f"Subtask completed: {task_id} ({self.checkpoint_data['completed_tasks']}/{self.checkpoint_data['total_tasks']})")

    def mark_subtask_failed(
        self,
        task_id: str,
        error: str
    ) -> None:
        """
        标记一个子任务失败。

        Args:
            task_id: 子任务ID
            error: 错误信息
        """
        if self.checkpoint_data is None:
            raise RuntimeError("Checkpoint not initialized")

        if task_id not in self.checkpoint_data["subtasks_status"]:
            logger.warning(f"Task {task_id} not found in checkpoint")
            return

        self.checkpoint_data["subtasks_status"][task_id].update({
            "status": "failed",
            "error": error,
            "failed_at": datetime.now().isoformat()
        })

        self.checkpoint_data["failed_tasks"] += 1
        self.checkpoint_data["last_updated"] = datetime.now().isoformat()
        self.save()
        logger.warning(f"Subtask failed: {task_id} - {error}")

    def mark_experiment_completed(self, analysis_result: Dict[str, Any]) -> None:
        """
        标记整个实验完成。

        Args:
            analysis_result: DeveloperAgent的分析结果
        """
        if self.checkpoint_data is None:
            raise RuntimeError("Checkpoint not initialized")

        self.checkpoint_data["status"] = "completed"
        self.checkpoint_data["analysis_result"] = analysis_result
        self.checkpoint_data["last_updated"] = datetime.now().isoformat()
        self.save()
        logger.info("Experiment marked as completed")

    def mark_experiment_failed(self, error: str) -> None:
        """
        标记整个实验失败。

        Args:
            error: 错误信息
        """
        if self.checkpoint_data is None:
            raise RuntimeError("Checkpoint not initialized")

        self.checkpoint_data["status"] = "failed"
        self.checkpoint_data["error"] = error
        self.checkpoint_data["last_updated"] = datetime.now().isoformat()
        self.save()
        logger.error(f"Experiment marked as failed: {error}")

    def get_pending_subtasks(self) -> List[Dict[str, Any]]:
        """
        获取所有待执行的子任务。

        Returns:
            待执行的子任务列表
        """
        if self.checkpoint_data is None:
            return []

        pending_tasks = []
        for task_id, task_status in self.checkpoint_data["subtasks_status"].items():
            if task_status["status"] == "pending":
                pending_tasks.append({
                    "task_id": task_id,
                    **task_status.get("subtask_info", {})
                })

        return pending_tasks

    def get_completed_subtasks(self) -> List[str]:
        """
        获取所有已完成的子任务ID。

        Returns:
            已完成的子任务ID列表
        """
        if self.checkpoint_data is None:
            return []

        return [
            task_id
            for task_id, task_status in self.checkpoint_data["subtasks_status"].items()
            if task_status["status"] == "completed"
        ]

    def get_failed_subtasks(self) -> List[str]:
        """
        获取所有失败的子任务ID。

        Returns:
            失败的子任务ID列表
        """
        if self.checkpoint_data is None:
            return []

        return [
            task_id
            for task_id, task_status in self.checkpoint_data["subtasks_status"].items()
            if task_status["status"] == "failed"
        ]

    def can_resume(self) -> bool:
        """
        检查是否可以恢复执行。

        Returns:
            如果有待执行的任务，返回True
        """
        if self.checkpoint_data is None:
            return False

        # 如果实验已完成或失败，不能恢复
        if self.checkpoint_data["status"] in ["completed", "failed"]:
            return False

        # 如果有pending或failed的任务，可以恢复
        pending = len(self.get_pending_subtasks())
        failed = len(self.get_failed_subtasks())

        return (pending + failed) > 0

    def get_progress_summary(self) -> Dict[str, Any]:
        """
        获取进度摘要。

        Returns:
            进度信息字典
        """
        if self.checkpoint_data is None:
            return {}

        total = self.checkpoint_data["total_tasks"]
        completed = self.checkpoint_data["completed_tasks"]
        failed = self.checkpoint_data["failed_tasks"]
        pending = total - completed - failed

        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "progress_percentage": (completed / total * 100) if total > 0 else 0,
            "current_phase": self.checkpoint_data.get("current_phase", "unknown"),
            "status": self.checkpoint_data.get("status", "unknown")
        }

    def save(self) -> None:
        """保存检查点到文件。"""
        if self.checkpoint_data is None:
            raise RuntimeError("No checkpoint data to save")

        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(self.checkpoint_data, f, indent=2, ensure_ascii=False)

        logger.debug(f"Checkpoint saved: {self.checkpoint_file}")

    def load(self) -> Dict[str, Any]:
        """
        从文件加载检查点。

        Returns:
            检查点数据
        """
        if not self.checkpoint_file.exists():
            raise FileNotFoundError(f"Checkpoint file not found: {self.checkpoint_file}")

        with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
            self.checkpoint_data = json.load(f)

        logger.info(f"Checkpoint loaded: {self.checkpoint_file}")
        logger.info(f"Progress: {self.checkpoint_data['completed_tasks']}/{self.checkpoint_data['total_tasks']} tasks completed")

        return self.checkpoint_data

    def exists(self) -> bool:
        """
        检查检查点文件是否存在。

        Returns:
            如果存在返回True
        """
        return self.checkpoint_file.exists()

    def get_data(self) -> Optional[Dict[str, Any]]:
        """
        获取当前的检查点数据。

        Returns:
            检查点数据，如果未初始化返回None
        """
        return self.checkpoint_data
