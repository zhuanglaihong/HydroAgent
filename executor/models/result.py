"""
Author: zhuanglaihong
Date: 2024-09-26 16:40:00
LastEditTime: 2024-09-26 16:40:00
LastEditors: zhuanglaihong
Description: 执行结果数据模型
FilePath: \HydroAgent\executor\models\result.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

from typing import Dict, List, Any, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime


class ExecutionStatus(str, Enum):
    """执行状态枚举"""
    PENDING = "pending"       # 等待执行
    RUNNING = "running"       # 正在执行
    COMPLETED = "completed"   # 执行完成
    FAILED = "failed"         # 执行失败
    SKIPPED = "skipped"       # 跳过执行
    PAUSED = "paused"         # 暂停执行
    CANCELLED = "cancelled"   # 取消执行


class TaskResult(BaseModel):
    """单个任务执行结果"""
    task_id: str = Field(..., description="任务ID")
    status: ExecutionStatus = Field(..., description="执行状态")
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    duration: Optional[float] = Field(None, description="执行时长(秒)")

    # 执行结果
    outputs: Dict[str, Any] = Field(default_factory=dict, description="任务输出")
    error: Optional[str] = Field(None, description="错误信息")
    error_details: Optional[Dict[str, Any]] = Field(None, description="详细错误信息")
    retry_count: int = Field(default=0, description="重试次数")

    # 性能指标
    metrics: Dict[str, float] = Field(default_factory=dict, description="性能指标")
    resource_usage: Dict[str, Any] = Field(default_factory=dict, description="资源使用情况")

    # 日志和调试信息
    logs: List[str] = Field(default_factory=list, description="执行日志")
    debug_info: Dict[str, Any] = Field(default_factory=dict, description="调试信息")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="任务元数据")

    def calculate_duration(self) -> Optional[float]:
        """计算执行时长"""
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            self.duration = delta.total_seconds()
            return self.duration
        return None

    def is_successful(self) -> bool:
        """判断任务是否成功"""
        return self.status == ExecutionStatus.COMPLETED and self.error is None

    def add_log(self, message: str, level: str = "INFO"):
        """添加日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        self.logs.append(log_entry)

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task_001",
                "status": "completed",
                "start_time": "2025-01-01T10:00:00Z",
                "end_time": "2025-01-01T10:15:00Z",
                "duration": 900,
                "outputs": {
                    "data_dir": "result/processed_data_20250101",
                    "records_count": 4018,
                    "validation_passed": True
                },
                "error": None,
                "retry_count": 0,
                "metrics": {
                    "processing_speed": 4.5,
                    "data_quality_score": 0.95
                }
            }
        }


class ReactIteration(BaseModel):
    """React模式迭代记录"""
    iteration: int = Field(..., description="迭代次数")
    start_time: datetime = Field(default_factory=datetime.now, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")

    # 目标评估
    target_achieved: bool = Field(..., description="是否达到目标")
    current_metric: Optional[float] = Field(None, description="当前指标值")
    target_metric: Optional[float] = Field(None, description="目标指标值")

    # 调整策略
    adjustments_made: List[str] = Field(default_factory=list, description="调整的策略")
    reason: Optional[str] = Field(None, description="未达到目标的原因")

    # 执行结果
    task_results: Dict[str, TaskResult] = Field(default_factory=dict, description="本次迭代的任务结果")

    class Config:
        json_schema_extra = {
            "example": {
                "iteration": 1,
                "target_achieved": False,
                "current_metric": 0.65,
                "target_metric": 0.7,
                "adjustments_made": ["increased_calibration_epochs", "adjusted_parameter_bounds"],
                "reason": "NSE below threshold (0.7), need parameter optimization"
            }
        }


class ExecutionMetrics(BaseModel):
    """执行指标统计"""
    total_tasks: int = Field(default=0, description="总任务数")
    completed_tasks: int = Field(default=0, description="完成任务数")
    failed_tasks: int = Field(default=0, description="失败任务数")
    skipped_tasks: int = Field(default=0, description="跳过任务数")

    # 性能指标
    success_rate: float = Field(default=0.0, description="成功率")
    average_task_duration: float = Field(default=0.0, description="平均任务时长")
    total_duration: float = Field(default=0.0, description="总执行时长")

    # 资源使用
    peak_memory_usage: Optional[float] = Field(None, description="峰值内存使用(MB)")
    total_api_calls: int = Field(default=0, description="API调用总数")
    llm_tokens_used: int = Field(default=0, description="LLM使用的Token数")

    def calculate_success_rate(self):
        """计算成功率"""
        if self.total_tasks > 0:
            self.success_rate = self.completed_tasks / self.total_tasks
        else:
            self.success_rate = 0.0

    def calculate_average_duration(self, task_results: List[TaskResult]):
        """计算平均任务时长"""
        durations = [r.duration for r in task_results if r.duration is not None]
        if durations:
            self.average_task_duration = sum(durations) / len(durations)

    class Config:
        json_schema_extra = {
            "example": {
                "total_tasks": 3,
                "completed_tasks": 2,
                "failed_tasks": 0,
                "skipped_tasks": 1,
                "success_rate": 0.67,
                "average_task_duration": 1200,
                "total_duration": 3600
            }
        }


class FinalReport(BaseModel):
    """最终执行报告"""
    overall_success: bool = Field(..., description="整体是否成功")
    target_achieved: Optional[bool] = Field(None, description="是否达到目标")
    final_metric_value: Optional[float] = Field(None, description="最终指标值")

    # 总结信息
    key_achievements: List[str] = Field(default_factory=list, description="主要成就")
    encountered_issues: List[str] = Field(default_factory=list, description="遇到的问题")
    recommendations: List[str] = Field(default_factory=list, description="建议")

    # 自动生成的总结
    ai_summary: Optional[str] = Field(None, description="AI生成的执行总结")
    generated_at: datetime = Field(default_factory=datetime.now, description="报告生成时间")

    class Config:
        json_schema_extra = {
            "example": {
                "overall_success": True,
                "target_achieved": True,
                "final_metric_value": 0.73,
                "key_achievements": [
                    "成功率定GR4J模型",
                    "NSE达到0.73，超过目标阈值0.7",
                    "优化参数提高了模型性能"
                ],
                "recommendations": [
                    "建议在其他流域验证参数的可移植性",
                    "考虑添加更多验证指标"
                ]
            }
        }


class WorkflowResult(BaseModel):
    """工作流执行结果"""
    execution_id: str = Field(..., description="执行ID")
    workflow_id: str = Field(..., description="工作流ID")
    status: ExecutionStatus = Field(..., description="整体执行状态")

    # 时间信息
    start_time: datetime = Field(default_factory=datetime.now, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    total_duration: Optional[float] = Field(None, description="总执行时长")

    # 任务结果
    task_results: Dict[str, TaskResult] = Field(default_factory=dict, description="任务执行结果")

    # 执行指标
    metrics: ExecutionMetrics = Field(default_factory=ExecutionMetrics, description="执行指标")

    # React模式相关
    react_iterations: List[ReactIteration] = Field(default_factory=list, description="React迭代记录")
    target_achieved: Optional[bool] = Field(None, description="是否达到目标")

    # 最终报告
    final_report: Optional[FinalReport] = Field(None, description="最终执行报告")

    # 检查点和恢复
    checkpoint_data: Dict[str, Any] = Field(default_factory=dict, description="检查点数据")
    can_resume: bool = Field(default=False, description="是否可以恢复")

    def add_task_result(self, task_result: TaskResult):
        """添加任务结果"""
        self.task_results[task_result.task_id] = task_result
        self._update_metrics()

    def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """获取任务结果"""
        return self.task_results.get(task_id)

    def calculate_total_duration(self):
        """计算总执行时长"""
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            self.total_duration = delta.total_seconds()

    def _update_metrics(self):
        """更新执行指标"""
        task_results = list(self.task_results.values())

        # 更新任务统计
        self.metrics.total_tasks = len(task_results)
        self.metrics.completed_tasks = sum(1 for r in task_results if r.status == ExecutionStatus.COMPLETED)
        self.metrics.failed_tasks = sum(1 for r in task_results if r.status == ExecutionStatus.FAILED)
        self.metrics.skipped_tasks = sum(1 for r in task_results if r.status == ExecutionStatus.SKIPPED)

        # 计算成功率
        self.metrics.calculate_success_rate()

        # 计算平均时长
        self.metrics.calculate_average_duration(task_results)

    def is_completed(self) -> bool:
        """判断工作流是否完成"""
        return self.status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED]

    def is_successful(self) -> bool:
        """判断工作流是否成功"""
        return (
            self.status == ExecutionStatus.COMPLETED and
            all(result.is_successful() for result in self.task_results.values())
        )

    class Config:
        json_schema_extra = {
            "example": {
                "execution_id": "exec_20250101_001",
                "workflow_id": "wf_20250101_001",
                "status": "completed",
                "start_time": "2025-01-01T10:00:00Z",
                "end_time": "2025-01-01T11:30:00Z",
                "total_duration": 5400,
                "task_results": {},
                "metrics": {
                    "total_tasks": 3,
                    "completed_tasks": 3,
                    "failed_tasks": 0,
                    "success_rate": 1.0
                }
            }
        }