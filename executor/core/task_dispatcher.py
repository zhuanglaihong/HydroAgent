"""
Author: zhuanglaihong
Date: 2024-09-26 16:40:00
LastEditTime: 2024-09-26 16:40:00
LastEditors: zhuanglaihong
Description: 任务分发器 - 智能任务路由和分发
FilePath: \HydroAgent\executor\core\task_dispatcher.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import logging
from typing import Dict, List, Any, Optional, Union, Tuple
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field

from ..models.task import Task, TaskType, TaskPriority
from ..models.result import TaskResult, ExecutionStatus


class ExecutorType(str, Enum):
    """执行器类型"""
    SIMPLE_EXECUTOR = "simple_executor"      # 简单任务执行器
    COMPLEX_SOLVER = "complex_solver"        # 复杂任务解决器


class DispatchDecision(BaseModel):
    """分发决策"""
    task_id: str = Field(..., description="任务ID")
    executor_type: ExecutorType = Field(..., description="执行器类型")
    priority_score: int = Field(..., description="优先级分数")
    can_execute: bool = Field(..., description="是否可以执行")
    blocked_by: List[str] = Field(default_factory=list, description="被阻塞的依赖")
    estimated_duration: Optional[float] = Field(None, description="预估执行时间")
    resource_requirements: Dict[str, Any] = Field(default_factory=dict, description="资源需求")


class TaskDispatcher:
    """智能任务分发器"""

    def __init__(self, enable_debug: bool = False):
        """
        初始化任务分发器

        Args:
            enable_debug: 是否启用调试模式
        """
        self.enable_debug = enable_debug
        self.logger = logging.getLogger(__name__)

        # 任务状态跟踪
        self.task_status: Dict[str, ExecutionStatus] = {}
        self.task_results: Dict[str, TaskResult] = {}
        self.dependency_graph: Dict[str, List[str]] = {}

        # 执行器负载跟踪
        self.executor_load: Dict[ExecutorType, int] = {
            ExecutorType.SIMPLE_EXECUTOR: 0,
            ExecutorType.COMPLEX_SOLVER: 0
        }

        self.logger.info("任务分发器初始化完成")

    def analyze_task(self, task: Task) -> DispatchDecision:
        """
        分析任务并生成分发决策

        Args:
            task: 待分析的任务

        Returns:
            DispatchDecision: 分发决策
        """
        if self.enable_debug:
            self.logger.debug(f"分析任务: {task.task_id} - {task.name}")

        # 1. 根据任务类型决定执行器
        executor_type = self._determine_executor_type(task)

        # 2. 计算优先级分数
        priority_score = self._calculate_priority_score(task)

        # 3. 检查依赖关系
        can_execute, blocked_by = self._check_dependencies(task)

        # 4. 预估执行时间
        estimated_duration = self._estimate_duration(task)

        # 5. 分析资源需求
        resource_requirements = self._analyze_resource_requirements(task)

        decision = DispatchDecision(
            task_id=task.task_id,
            executor_type=executor_type,
            priority_score=priority_score,
            can_execute=can_execute,
            blocked_by=blocked_by,
            estimated_duration=estimated_duration,
            resource_requirements=resource_requirements
        )

        if self.enable_debug:
            self.logger.debug(f"分发决策: {decision}")

        return decision

    def dispatch_task(self, task: Task, context: Dict[str, Any] = None) -> Tuple[ExecutorType, Dict[str, Any]]:
        """
        分发任务到合适的执行器

        Args:
            task: 待分发的任务
            context: 执行上下文

        Returns:
            Tuple[ExecutorType, Dict[str, Any]]: (执行器类型, 执行参数)
        """
        if context is None:
            context = {}

        # 分析任务
        decision = self.analyze_task(task)

        # 检查是否可以执行
        if not decision.can_execute:
            raise ValueError(f"任务 {task.task_id} 无法执行，被依赖阻塞: {decision.blocked_by}")

        # 解析任务参数
        try:
            resolved_params = task.resolve_parameters(context)
        except ValueError as e:
            self.logger.error(f"参数解析失败: {e}")
            raise

        # 构建执行参数
        execution_params = {
            "task": task,
            "parameters": resolved_params,
            "priority": decision.priority_score,
            "estimated_duration": decision.estimated_duration,
            "resource_requirements": decision.resource_requirements,
            "context": context
        }

        # 更新执行器负载
        self.executor_load[decision.executor_type] += 1

        # 更新任务状态
        self.task_status[task.task_id] = ExecutionStatus.PENDING

        self.logger.info(f"任务 {task.task_id} 分发到 {decision.executor_type}")

        return decision.executor_type, execution_params

    def get_ready_tasks(self, tasks: List[Task]) -> List[Task]:
        """
        获取可以立即执行的任务列表

        Args:
            tasks: 任务列表

        Returns:
            List[Task]: 可执行任务列表
        """
        ready_tasks = []

        for task in tasks:
            decision = self.analyze_task(task)
            if decision.can_execute:
                ready_tasks.append(task)

        # 按优先级排序
        ready_tasks.sort(key=lambda t: self._calculate_priority_score(t), reverse=True)

        return ready_tasks

    def update_task_status(self, task_id: str, status: ExecutionStatus, result: TaskResult = None):
        """
        更新任务状态

        Args:
            task_id: 任务ID
            status: 新状态
            result: 任务结果（可选）
        """
        old_status = self.task_status.get(task_id)
        self.task_status[task_id] = status

        if result:
            self.task_results[task_id] = result

        # 如果任务完成，减少执行器负载
        if status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.SKIPPED]:
            # 从两个执行器中找到并减少负载
            for executor_type in self.executor_load:
                if self.executor_load[executor_type] > 0:
                    self.executor_load[executor_type] -= 1
                    break

        self.logger.info(f"任务 {task_id} 状态更新: {old_status} -> {status}")

    def build_dependency_graph(self, tasks: List[Task]):
        """
        构建任务依赖图

        Args:
            tasks: 任务列表
        """
        self.dependency_graph = {}

        for task in tasks:
            self.dependency_graph[task.task_id] = task.dependencies[:]

        if self.enable_debug:
            self.logger.debug(f"依赖图: {self.dependency_graph}")

    def get_execution_statistics(self) -> Dict[str, Any]:
        """
        获取执行统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        total_tasks = len(self.task_status)
        status_counts = {}

        for status in ExecutionStatus:
            status_counts[status.value] = sum(1 for s in self.task_status.values() if s == status)

        return {
            "total_tasks": total_tasks,
            "status_distribution": status_counts,
            "executor_load": dict(self.executor_load),
            "completed_tasks": len(self.task_results),
            "success_rate": self._calculate_success_rate()
        }

    def _determine_executor_type(self, task: Task) -> ExecutorType:
        """根据任务类型确定执行器"""
        if task.type == TaskType.SIMPLE:
            return ExecutorType.SIMPLE_EXECUTOR
        elif task.type == TaskType.COMPLEX:
            return ExecutorType.COMPLEX_SOLVER
        else:
            raise ValueError(f"未知任务类型: {task.type}")

    def _calculate_priority_score(self, task: Task) -> int:
        """
        计算任务优先级分数

        分数越高，优先级越高
        """
        base_score = task.priority.value * 100

        # 根据依赖数量调整（依赖少的优先）
        dependency_penalty = len(task.dependencies) * 10

        # 根据任务类型调整
        type_bonus = 50 if task.type == TaskType.SIMPLE else 30

        # 根据重试次数调整（重试多的降低优先级）
        retry_penalty = task.retry_count * 20

        final_score = base_score + type_bonus - dependency_penalty - retry_penalty

        return max(final_score, 0)  # 确保分数非负

    def _check_dependencies(self, task: Task) -> Tuple[bool, List[str]]:
        """
        检查任务依赖关系

        Returns:
            Tuple[bool, List[str]]: (是否可执行, 阻塞的依赖列表)
        """
        blocked_by = []

        for dep_id in task.dependencies:
            dep_status = self.task_status.get(dep_id, ExecutionStatus.PENDING)
            if dep_status != ExecutionStatus.COMPLETED:
                blocked_by.append(dep_id)

        can_execute = len(blocked_by) == 0

        return can_execute, blocked_by

    def _estimate_duration(self, task: Task) -> Optional[float]:
        """
        预估任务执行时间

        Returns:
            Optional[float]: 预估时间（秒）
        """
        # 基础时间估算
        base_times = {
            TaskType.SIMPLE: 300,    # 5分钟
            TaskType.COMPLEX: 1800   # 30分钟
        }

        base_time = base_times.get(task.type, 600)

        # 根据工具类型调整
        if task.tool_name:
            tool_factors = {
                "prepare_data": 0.5,
                "calibrate_model": 2.0,
                "evaluate_model": 0.3,
                "get_model_params": 0.1
            }
            factor = tool_factors.get(task.tool_name, 1.0)
            base_time *= factor

        # 根据参数复杂度调整
        param_count = len(task.parameters)
        complexity_factor = 1 + (param_count / 10)

        estimated_time = base_time * complexity_factor

        return estimated_time

    def _analyze_resource_requirements(self, task: Task) -> Dict[str, Any]:
        """
        分析任务资源需求

        Returns:
            Dict[str, Any]: 资源需求
        """
        requirements = {
            "cpu_cores": 1,
            "memory_mb": 512,
            "disk_mb": 100,
            "gpu_required": False,
            "network_required": False
        }

        # 根据任务类型调整
        if task.type == TaskType.COMPLEX:
            requirements.update({
                "cpu_cores": 2,
                "memory_mb": 2048,
                "network_required": True  # 需要调用LLM API
            })

        # 根据具体工具调整
        if task.tool_name == "calibrate_model":
            requirements.update({
                "cpu_cores": 4,
                "memory_mb": 4096,
                "disk_mb": 1024
            })

        return requirements

    def _calculate_success_rate(self) -> float:
        """计算任务成功率"""
        if not self.task_results:
            return 0.0

        successful_tasks = sum(1 for result in self.task_results.values() if result.is_successful())
        total_completed = len(self.task_results)

        return successful_tasks / total_completed if total_completed > 0 else 0.0

    def reset(self):
        """重置分发器状态"""
        self.task_status.clear()
        self.task_results.clear()
        self.dependency_graph.clear()

        for executor_type in self.executor_load:
            self.executor_load[executor_type] = 0

        self.logger.info("任务分发器状态已重置")