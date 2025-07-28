"""
Author: zhuanglaihong
Date: 2025-07-28
Description: 工作流数据类型定义
"""

from typing import List, Dict, Any, Optional, Union
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import json


class ExecutionStatus(Enum):
    """执行状态枚举"""

    PENDING = "pending"  # 待执行
    RUNNING = "running"  # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 执行失败
    SKIPPED = "skipped"  # 已跳过
    CANCELLED = "cancelled"  # 已取消


class StepType(Enum):
    """步骤类型枚举"""

    TOOL_CALL = "tool_call"  # 工具调用
    CONDITION = "condition"  # 条件判断
    LOOP = "loop"  # 循环执行
    PARALLEL = "parallel"  # 并行执行
    WAIT = "wait"  # 等待操作
    VALIDATION = "validation"  # 结果验证


@dataclass
class WorkflowStep:
    """工作流步骤定义"""

    step_id: str  # 步骤ID
    name: str  # 步骤名称
    description: str  # 步骤描述
    step_type: StepType  # 步骤类型
    tool_name: Optional[str] = None  # 工具名称
    parameters: Dict[str, Any] = field(default_factory=dict)  # 参数
    dependencies: List[str] = field(default_factory=list)  # 依赖的步骤ID
    conditions: Dict[str, Any] = field(default_factory=dict)  # 执行条件
    retry_count: int = 0  # 重试次数
    timeout: Optional[int] = None  # 超时时间(秒)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "step_id": self.step_id,
            "name": self.name,
            "description": self.description,
            "step_type": self.step_type.value,
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "dependencies": self.dependencies,
            "conditions": self.conditions,
            "retry_count": self.retry_count,
            "timeout": self.timeout,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowStep":
        """从字典创建"""
        return cls(
            step_id=data["step_id"],
            name=data["name"],
            description=data["description"],
            step_type=StepType(data["step_type"]),
            tool_name=data.get("tool_name"),
            parameters=data.get("parameters", {}),
            dependencies=data.get("dependencies", []),
            conditions=data.get("conditions", {}),
            retry_count=data.get("retry_count", 0),
            timeout=data.get("timeout"),
        )


@dataclass
class ExecutionResult:
    """执行结果"""

    step_id: str  # 步骤ID
    status: ExecutionStatus  # 执行状态
    result: Optional[Any] = None  # 执行结果
    error: Optional[str] = None  # 错误信息
    start_time: Optional[datetime] = None  # 开始时间
    end_time: Optional[datetime] = None  # 结束时间
    execution_time: Optional[float] = None  # 执行时长(秒)
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "step_id": self.step_id,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "execution_time": self.execution_time,
            "metadata": self.metadata,
        }


@dataclass
class WorkflowPlan:
    """工作流计划"""

    plan_id: str  # 计划ID
    name: str  # 计划名称
    description: str  # 计划描述
    steps: List[WorkflowStep]  # 执行步骤
    user_query: str  # 原始用户查询
    expanded_query: str  # 扩展后的查询
    context: str  # 检索到的上下文
    created_time: datetime = field(default_factory=datetime.now)  # 创建时间
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "plan_id": self.plan_id,
            "name": self.name,
            "description": self.description,
            "steps": [step.to_dict() for step in self.steps],
            "user_query": self.user_query,
            "expanded_query": self.expanded_query,
            "context": self.context,
            "created_time": self.created_time.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowPlan":
        """从字典创建"""
        return cls(
            plan_id=data["plan_id"],
            name=data["name"],
            description=data["description"],
            steps=[WorkflowStep.from_dict(step_data) for step_data in data["steps"]],
            user_query=data["user_query"],
            expanded_query=data["expanded_query"],
            context=data["context"],
            created_time=datetime.fromisoformat(data["created_time"]),
            metadata=data.get("metadata", {}),
        )

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "WorkflowPlan":
        """从JSON字符串创建"""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class WorkflowExecution:
    """工作流执行状态"""

    execution_id: str  # 执行ID
    plan: WorkflowPlan  # 工作流计划
    status: ExecutionStatus  # 整体执行状态
    current_step: Optional[str] = None  # 当前执行步骤ID
    step_results: Dict[str, ExecutionResult] = field(
        default_factory=dict
    )  # 步骤执行结果
    start_time: Optional[datetime] = None  # 开始时间
    end_time: Optional[datetime] = None  # 结束时间
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据

    def get_step_result(self, step_id: str) -> Optional[ExecutionResult]:
        """获取步骤执行结果"""
        return self.step_results.get(step_id)

    def add_step_result(self, result: ExecutionResult):
        """添加步骤执行结果"""
        self.step_results[result.step_id] = result

    def get_completed_steps(self) -> List[str]:
        """获取已完成的步骤ID列表"""
        return [
            step_id
            for step_id, result in self.step_results.items()
            if result.status == ExecutionStatus.COMPLETED
        ]

    def get_failed_steps(self) -> List[str]:
        """获取失败的步骤ID列表"""
        return [
            step_id
            for step_id, result in self.step_results.items()
            if result.status == ExecutionStatus.FAILED
        ]

    def is_completed(self) -> bool:
        """检查是否完全执行完成"""
        if not self.step_results:
            return False

        total_steps = len(self.plan.steps)
        completed_steps = len(self.get_completed_steps())
        return completed_steps == total_steps

    def has_failures(self) -> bool:
        """检查是否有失败的步骤"""
        return len(self.get_failed_steps()) > 0


@dataclass
class KnowledgeFragment:
    """知识片段"""

    content: str  # 内容
    source: str  # 来源
    score: float  # 相似度得分
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "content": self.content,
            "source": self.source,
            "score": self.score,
            "metadata": self.metadata,
        }


@dataclass
class IntentAnalysis:
    """意图分析结果"""

    original_query: str  # 原始查询
    clarified_intent: str  # 明确化的意图
    task_type: str  # 任务类型
    entities: Dict[str, Any] = field(default_factory=dict)  # 识别的实体
    confidence: float = 0.0  # 置信度
    suggested_tools: List[str] = field(default_factory=list)  # 建议的工具

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "original_query": self.original_query,
            "clarified_intent": self.clarified_intent,
            "task_type": self.task_type,
            "entities": self.entities,
            "confidence": self.confidence,
            "suggested_tools": self.suggested_tools,
        }
