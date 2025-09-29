"""
Author: zhuanglaihong
Date: 2024-09-24 16:46:00
LastEditTime: 2024-09-24 16:46:00
LastEditors: zhuanglaihong
Description: Execution mode determination for workflows
FilePath: \HydroAgent\builder\execution_mode.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

from enum import Enum
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """执行模式枚举"""

    LINEAR = "linear"  # 线性执行：严格按依赖顺序执行
    REACT = "react"  # 反应式执行：支持动态决策和循环
    HYBRID = "hybrid"  # 混合模式：结合线性和反应式


@dataclass
class ModeAnalysisResult:
    """模式分析结果"""

    recommended_mode: ExecutionMode
    confidence: float  # 推荐置信度 (0.0 - 1.0)
    reasoning: str  # 推荐理由
    complexity_score: float  # 复杂度评分 (0.0 - 1.0)
    features: Dict[str, bool]  # 检测到的特征
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ExecutionModeAnalyzer:
    """
    执行模式分析器 - 分析工作流特征并推荐执行模式
    """

    def __init__(self):
        """初始化分析器"""
        self.complexity_weights = {
            "task_count": 0.1,  # 任务数量权重
            "dependency_depth": 0.2,  # 依赖深度权重
            "branch_count": 0.15,  # 分支数量权重
            "loop_count": 0.25,  # 循环数量权重
            "condition_count": 0.15,  # 条件数量权重
            "complex_task_ratio": 0.15,  # 复杂任务比例权重
        }

    def analyze_workflow(self, workflow: Dict[str, Any]) -> ModeAnalysisResult:
        """
        分析工作流并推荐执行模式

        Args:
            workflow: 工作流定义

        Returns:
            ModeAnalysisResult: 分析结果
        """
        try:
            tasks = workflow.get("tasks", [])
            if not tasks:
                return ModeAnalysisResult(
                    recommended_mode=ExecutionMode.LINEAR,
                    confidence=1.0,
                    reasoning="空工作流，使用线性模式",
                    complexity_score=0.0,
                    features={},
                )

            # 特征检测
            features = self._detect_features(tasks)

            # 复杂度评分
            complexity_score = self._calculate_complexity(tasks, features)

            # 模式推荐
            mode, confidence, reasoning = self._recommend_mode(
                features, complexity_score
            )

            return ModeAnalysisResult(
                recommended_mode=mode,
                confidence=confidence,
                reasoning=reasoning,
                complexity_score=complexity_score,
                features=features,
                metadata={
                    "task_count": len(tasks),
                    "workflow_id": workflow.get("workflow_id", "unknown"),
                },
            )

        except Exception as e:
            logger.error(f"工作流模式分析失败: {str(e)}")
            return ModeAnalysisResult(
                recommended_mode=ExecutionMode.LINEAR,
                confidence=0.5,
                reasoning=f"分析失败，使用默认线性模式: {str(e)}",
                complexity_score=0.0,
                features={},
            )

    def _detect_features(self, tasks: List[Dict[str, Any]]) -> Dict[str, bool]:
        """检测工作流特征"""
        features = {
            "has_loops": False,
            "has_conditions": False,
            "has_complex_tasks": False,
            "has_parallel_branches": False,
            "has_error_handling": False,
            "has_dynamic_params": False,
            "requires_feedback": False,
            "has_model_calibration": False,
        }

        # 分析每个任务
        for task in tasks:
            task_type = task.get("task_type", "simple_action")
            action = task.get("action", "")
            conditions = task.get("conditions", {})
            dependencies = task.get("dependencies", [])

            # 检测复杂任务
            if task_type == "complex_reasoning":
                features["has_complex_tasks"] = True

            # 检测循环
            if conditions.get("retry_count", 0) > 1:
                features["has_loops"] = True

            # 检测条件判断
            if conditions.get("if") or conditions.get("while"):
                features["has_conditions"] = True

            # 检测错误处理
            if conditions.get("on_error") or conditions.get("timeout"):
                features["has_error_handling"] = True

            # 检测模型率定
            if "calibrate" in action.lower():
                features["has_model_calibration"] = True
                features["requires_feedback"] = True

            # 检测动态参数
            parameters = task.get("parameters", {})
            for param_value in parameters.values():
                if isinstance(param_value, str) and "${" in param_value:
                    features["has_dynamic_params"] = True

        # 检测并行分支
        dependency_graph = self._build_dependency_graph(tasks)
        features["has_parallel_branches"] = self._has_parallel_execution(
            dependency_graph
        )

        return features

    def _calculate_complexity(
        self, tasks: List[Dict[str, Any]], features: Dict[str, bool]
    ) -> float:
        """计算复杂度评分"""
        scores = {}

        # 任务数量评分
        task_count = len(tasks)
        scores["task_count"] = min(task_count / 10.0, 1.0)

        # 依赖深度评分
        dependency_graph = self._build_dependency_graph(tasks)
        max_depth = self._calculate_max_dependency_depth(dependency_graph)
        scores["dependency_depth"] = min(max_depth / 5.0, 1.0)

        # 分支数量评分
        branch_count = self._count_parallel_branches(dependency_graph)
        scores["branch_count"] = min(branch_count / 3.0, 1.0)

        # 循环数量评分
        loop_count = sum(
            1 for task in tasks if task.get("conditions", {}).get("retry_count", 0) > 1
        )
        scores["loop_count"] = min(loop_count / 2.0, 1.0)

        # 条件数量评分
        condition_count = sum(
            1 for task in tasks if task.get("conditions", {}).get("if")
        )
        scores["condition_count"] = min(condition_count / 3.0, 1.0)

        # 复杂任务比例评分
        complex_tasks = sum(
            1 for task in tasks if task.get("task_type") == "complex_reasoning"
        )
        complex_ratio = complex_tasks / len(tasks) if tasks else 0
        scores["complex_task_ratio"] = complex_ratio

        # 加权求和
        weighted_score = sum(
            scores[key] * self.complexity_weights[key] for key in scores
        )

        return min(weighted_score, 1.0)

    def _recommend_mode(
        self, features: Dict[str, bool], complexity_score: float
    ) -> tuple:
        """推荐执行模式"""

        # 高复杂度特征检查
        high_complexity_features = [
            "has_loops",
            "has_conditions",
            "requires_feedback",
            "has_model_calibration",
            "has_dynamic_params",
        ]

        high_complexity_count = sum(
            1 for feature in high_complexity_features if features.get(feature, False)
        )

        # 决策逻辑
        if complexity_score >= 0.7 or high_complexity_count >= 3:
            return (
                ExecutionMode.REACT,
                0.9,
                f"高复杂度工作流(评分: {complexity_score:.2f})，包含{high_complexity_count}个高复杂度特征，推荐REACT模式",
            )

        elif features.get("has_model_calibration") or features.get("requires_feedback"):
            return (
                ExecutionMode.REACT,
                0.8,
                "包含模型率定或需要反馈循环，推荐REACT模式",
            )

        elif complexity_score >= 0.4 or features.get("has_parallel_branches"):
            return (
                ExecutionMode.HYBRID,
                0.7,
                f"中等复杂度工作流(评分: {complexity_score:.2f})，推荐HYBRID模式",
            )

        else:
            return (
                ExecutionMode.LINEAR,
                0.8,
                f"低复杂度工作流(评分: {complexity_score:.2f})，推荐LINEAR模式",
            )

    def _build_dependency_graph(
        self, tasks: List[Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        """构建依赖图"""
        graph = {}
        for task in tasks:
            task_id = task.get("task_id", "")
            dependencies = task.get("dependencies", [])
            graph[task_id] = dependencies
        return graph

    def _has_parallel_execution(self, dependency_graph: Dict[str, List[str]]) -> bool:
        """检测是否有并行执行"""
        # 找到没有依赖的任务
        independent_tasks = [
            task_id for task_id, deps in dependency_graph.items() if not deps
        ]

        # 如果有多个独立任务，说明可以并行执行
        return len(independent_tasks) > 1

    def _calculate_max_dependency_depth(
        self, dependency_graph: Dict[str, List[str]]
    ) -> int:
        """计算最大依赖深度"""

        def get_depth(task_id: str, visited: set = None) -> int:
            if visited is None:
                visited = set()

            if task_id in visited:
                return 0  # 避免循环依赖

            visited.add(task_id)
            deps = dependency_graph.get(task_id, [])

            if not deps:
                return 1

            max_dep_depth = max(get_depth(dep, visited.copy()) for dep in deps)
            return max_dep_depth + 1

        if not dependency_graph:
            return 0

        return max(get_depth(task_id) for task_id in dependency_graph.keys())

    def _count_parallel_branches(self, dependency_graph: Dict[str, List[str]]) -> int:
        """计算并行分支数量"""
        # 简化计算：统计同一层级的任务数量
        levels = {}

        def assign_level(task_id: str, level: int = 0, visited: set = None):
            if visited is None:
                visited = set()

            if task_id in visited:
                return

            visited.add(task_id)

            if level not in levels:
                levels[level] = []
            levels[level].append(task_id)

            # 处理依赖这个任务的其他任务
            for other_task, deps in dependency_graph.items():
                if task_id in deps:
                    assign_level(other_task, level + 1, visited.copy())

        # 从没有依赖的任务开始
        independent_tasks = [
            task_id for task_id, deps in dependency_graph.items() if not deps
        ]

        for task_id in independent_tasks:
            assign_level(task_id, 0)

        # 返回最大层级的任务数量
        if not levels:
            return 0

        return max(len(tasks) for tasks in levels.values())

    def get_mode_recommendations(self) -> Dict[str, str]:
        """获取执行模式建议说明"""
        return {
            ExecutionMode.LINEAR.value: (
                "线性执行模式：适用于简单的顺序任务，严格按依赖关系执行，"
                "执行效率高，调试简单，但缺乏灵活性"
            ),
            ExecutionMode.REACT.value: (
                "反应式执行模式：适用于复杂的动态任务，支持条件判断、循环重试、"
                "错误恢复等高级功能，灵活性高但执行开销较大"
            ),
            ExecutionMode.HYBRID.value: (
                "混合执行模式：结合线性和反应式的优点，对简单任务使用线性执行，"
                "对复杂任务使用反应式执行，平衡效率和灵活性"
            ),
        }


# 全局实例
_mode_analyzer = None


def get_mode_analyzer() -> ExecutionModeAnalyzer:
    """获取全局执行模式分析器实例"""
    global _mode_analyzer
    if _mode_analyzer is None:
        _mode_analyzer = ExecutionModeAnalyzer()
    return _mode_analyzer
