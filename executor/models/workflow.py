"""
Author: zhuanglaihong
Date: 2024-09-26 16:40:00
LastEditTime: 2024-09-26 16:40:00
LastEditors: zhuanglaihong
Description: 工作流数据模型
FilePath: \HydroAgent\executor\models\workflow.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

from typing import Dict, List, Any, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field, validator
from datetime import datetime

from .task import Task


class WorkflowMode(str, Enum):
    """工作流执行模式"""

    SEQUENTIAL = "sequential"  # 顺序执行
    REACT = "react"  # React模式，目标导向


class ErrorHandling(str, Enum):
    """错误处理策略"""

    CONTINUE_ON_ERROR = "continue_on_error"  # 遇到错误继续执行
    STOP_ON_ERROR = "stop_on_error"  # 遇到错误停止执行


class TargetType(str, Enum):
    """目标类型"""

    PERFORMANCE_GOAL = "performance_goal"  # 性能目标
    COMPLETION_GOAL = "completion_goal"  # 完成目标
    CUSTOM_GOAL = "custom_goal"  # 自定义目标


class WorkflowTarget(BaseModel):
    """工作流目标配置"""

    type: TargetType = Field(..., description="目标类型")
    metric: Optional[str] = Field(None, description="目标指标名称")
    threshold: Optional[float] = Field(None, description="目标阈值")
    comparison: str = Field(default=">=", description="比较运算符")
    max_iterations: int = Field(default=3, description="最大迭代次数")
    description: Optional[str] = Field(None, description="目标描述")

    @validator("metric")
    def validate_performance_goal(cls, v, values):
        """验证性能目标必须有指标"""
        if values.get("type") == TargetType.PERFORMANCE_GOAL and not v:
            raise ValueError("Performance goals must have a metric")
        return v

    def is_achieved(self, current_value: float) -> bool:
        """判断目标是否达成"""
        if self.threshold is None:
            return False

        if self.comparison == ">=":
            return current_value >= self.threshold
        elif self.comparison == "<=":
            return current_value <= self.threshold
        elif self.comparison == ">":
            return current_value > self.threshold
        elif self.comparison == "<":
            return current_value < self.threshold
        elif self.comparison == "==":
            return abs(current_value - self.threshold) < 1e-6
        else:
            return False

    class Config:
        json_schema_extra = {
            "example": {
                "type": "performance_goal",
                "metric": "NSE",
                "threshold": 0.7,
                "comparison": ">=",
                "max_iterations": 5,
                "description": "NSE指标需要达到0.7以上",
            }
        }


class WorkflowSettings(BaseModel):
    """工作流全局设置"""

    error_handling: ErrorHandling = Field(
        default=ErrorHandling.CONTINUE_ON_ERROR, description="错误处理策略"
    )
    logging_level: str = Field(default="INFO", description="日志级别")
    timeout: Optional[int] = Field(None, description="全局超时时间(秒)")
    checkpoint_enabled: bool = Field(default=True, description="是否启用检查点")
    parallel_execution: bool = Field(default=False, description="是否支持并行执行")
    max_parallel_tasks: int = Field(default=3, description="最大并行任务数")

    class Config:
        json_schema_extra = {
            "example": {
                "error_handling": "continue_on_error",
                "logging_level": "INFO",
                "timeout": 3600,
                "checkpoint_enabled": True,
                "parallel_execution": False,
                "max_parallel_tasks": 3,
            }
        }


class Workflow(BaseModel):
    """工作流定义模型"""

    workflow_id: str = Field(..., description="工作流唯一ID")
    name: str = Field(..., description="工作流名称")
    description: Optional[str] = Field(None, description="工作流描述")
    version: str = Field(default="1.0", description="工作流版本")
    mode: WorkflowMode = Field(default=WorkflowMode.SEQUENTIAL, description="执行模式")

    # 核心组件
    tasks: List[Task] = Field(..., description="任务列表")
    target: Optional[WorkflowTarget] = Field(None, description="目标配置")
    global_settings: WorkflowSettings = Field(
        default_factory=WorkflowSettings, description="全局设置"
    )

    # 元数据
    created_at: Optional[datetime] = Field(
        default_factory=datetime.now, description="创建时间"
    )
    created_by: Optional[str] = Field(None, description="创建者")
    tags: List[str] = Field(default_factory=list, description="标签")

    @validator("tasks")
    def validate_tasks(cls, v):
        """验证任务列表"""
        if not v:
            raise ValueError("Workflow must have at least one task")

        # 检查任务ID唯一性
        task_ids = [task.task_id for task in v]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("Task IDs must be unique")

        return v

    @validator("target")
    def validate_react_mode(cls, v, values):
        """验证React模式必须有目标"""
        if values.get("mode") == WorkflowMode.REACT and not v:
            raise ValueError("React mode workflows must have a target")
        return v

    def get_task_by_id(self, task_id: str) -> Optional[Task]:
        """根据ID获取任务"""
        for task in self.tasks:
            if task.task_id == task_id:
                return task
        return None

    def get_execution_order(self) -> List[List[str]]:
        """获取任务执行顺序（考虑依赖关系）"""
        # 拓扑排序算法
        in_degree = {}
        graph = {}

        # 初始化
        for task in self.tasks:
            in_degree[task.task_id] = 0
            graph[task.task_id] = []

        # 构建图
        for task in self.tasks:
            for dep in task.dependencies:
                if dep in graph:
                    graph[dep].append(task.task_id)
                    in_degree[task.task_id] += 1

        # 拓扑排序
        result = []
        current_level = []

        # 找到入度为0的节点
        for task_id, degree in in_degree.items():
            if degree == 0:
                current_level.append(task_id)

        while current_level:
            result.append(current_level[:])  # 当前层级的任务可以并行执行
            next_level = []

            for task_id in current_level:
                for neighbor in graph[task_id]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_level.append(neighbor)

            current_level = next_level

        return result

    def validate_dependencies(self) -> bool:
        """验证依赖关系是否有效"""
        task_ids = set(task.task_id for task in self.tasks)

        for task in self.tasks:
            for dep in task.dependencies:
                if dep not in task_ids:
                    raise ValueError(
                        f"Task {task.task_id} depends on non-existent task {dep}"
                    )

        # 检查循环依赖
        execution_order = self.get_execution_order()
        all_ordered_tasks = [task_id for level in execution_order for task_id in level]

        if len(all_ordered_tasks) != len(self.tasks):
            raise ValueError("Circular dependency detected in workflow")

        return True

    class Config:
        json_schema_extra = {
            "example": {
                "workflow_id": "wf_20250101_001",
                "name": "GR4J模型率定和评估",
                "description": "完整的GR4J模型率定、评估和优化工作流",
                "mode": "react",
                "tasks": [],  # 任务列表示例在Task模型中
                "target": {
                    "type": "performance_goal",
                    "metric": "NSE",
                    "threshold": 0.7,
                    "max_iterations": 5,
                },
                "global_settings": {
                    "error_handling": "continue_on_error",
                    "logging_level": "INFO",
                    "timeout": 3600,
                    "checkpoint_enabled": True,
                },
            }
        }
