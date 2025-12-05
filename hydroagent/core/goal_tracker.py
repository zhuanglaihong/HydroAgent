"""
Author: Claude
Date: 2025-12-03 15:45:00
LastEditTime: 2025-12-03 15:45:00
LastEditors: Claude
Description: Goal tracker for monitoring task progress and convergence trends
             目标追踪器 - 监控任务进度、性能趋势、终止条件
FilePath: /HydroAgent/hydroagent/core/goal_tracker.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

核心功能:
1. 追踪任务目标 (target metric, target value)
2. 分析性能趋势 (improving, stable, degrading)
3. 判断终止条件 (目标达成、最大迭代、无改善、性能退化)
4. 建议下一步动作 (continue, adjust_strategy, rollback)
"""

from typing import Dict, Any, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class GoalTracker:
    """
    任务目标追踪器

    职责:
    - 持续监控任务执行的性能指标
    - 分析性能变化趋势
    - 判断是否应该终止任务
    - 建议下一步优化策略
    """

    def __init__(self, goal_definition: Dict[str, Any]):
        """
        初始化目标追踪器

        Args:
            goal_definition: 任务目标定义字典
                {
                    "type": "calibration",           # 任务类型
                    "target_metric": "NSE",          # 目标指标名称
                    "target_value": 0.75,            # 目标阈值
                    "max_iterations": 10,            # 最大迭代次数
                    "convergence_tolerance": 0.01    # 收敛容差
                }
        """
        self.goal = goal_definition
        self.current_iteration = 0
        self.metric_history: List[Tuple[int, float]] = []  # [(iteration, value), ...]
        self.trend: Optional[str] = None  # "improving" | "stable" | "degrading"
        self.best_value = float('-inf')
        self.best_iteration = 0

        logger.info(
            f"[GoalTracker] Initialized with target: {goal_definition.get('target_metric')} "
            f">= {goal_definition.get('target_value')}, max_iterations={goal_definition.get('max_iterations')}"
        )

    def update(self, result: Dict[str, Any]):
        """
        更新当前执行结果

        Args:
            result: 执行结果字典,必须包含metrics字段
                {
                    "success": True,
                    "metrics": {"NSE": 0.72, "RMSE": 1.5, ...},
                    "parameters": {...}
                }
        """
        if not result.get("success", False):
            logger.warning("[GoalTracker] Received failed result, skipping update")
            return

        # 提取目标指标值
        metrics = result.get("metrics", {})
        target_metric = self.goal.get("target_metric", "NSE")
        metric_value = metrics.get(target_metric)

        if metric_value is None:
            logger.warning(f"[GoalTracker] Target metric '{target_metric}' not found in results")
            return

        # 更新迭代计数和历史
        self.current_iteration += 1
        self.metric_history.append((self.current_iteration, metric_value))

        # 更新最佳值
        if metric_value > self.best_value:
            self.best_value = metric_value
            self.best_iteration = self.current_iteration
            logger.info(
                f"[GoalTracker] New best {target_metric}: {metric_value:.4f} "
                f"(iteration {self.current_iteration})"
            )

        # 分析趋势
        self._analyze_trend()

        logger.info(
            f"[GoalTracker] Iteration {self.current_iteration}: {target_metric}={metric_value:.4f}, "
            f"trend={self.trend}, best={self.best_value:.4f}"
        )

    def _analyze_trend(self):
        """
        分析性能变化趋势

        策略:
        - 使用最近3次结果的平均变化率
        - 如果平均增长 > convergence_tolerance → "improving"
        - 如果平均下降 < -convergence_tolerance → "degrading"
        - 否则 → "stable"
        """
        if len(self.metric_history) < 3:
            self.trend = None
            return

        # 取最近3次结果
        recent_values = [v for _, v in self.metric_history[-3:]]

        # 计算连续变化率
        diffs = [recent_values[i+1] - recent_values[i] for i in range(len(recent_values)-1)]
        avg_diff = sum(diffs) / len(diffs)

        # 判断趋势
        tolerance = self.goal.get("convergence_tolerance", 0.01)
        if avg_diff > tolerance:
            self.trend = "improving"
        elif avg_diff < -tolerance:
            self.trend = "degrading"
        else:
            self.trend = "stable"

    def should_terminate(self) -> Tuple[bool, str]:
        """
        判断是否应该终止任务

        终止条件:
        1. 达到目标阈值
        2. 达到最大迭代次数
        3. 连续5次无显著改善
        4. 性能持续退化

        Returns:
            (should_terminate, reason)
        """
        if not self.metric_history:
            return False, ""

        # 条件1: 达到目标
        current_value = self.metric_history[-1][1]
        target_value = self.goal.get("target_value", 0.7)
        if current_value >= target_value:
            return True, "goal_achieved"

        # 条件2: 达到最大迭代次数
        max_iterations = self.goal.get("max_iterations", 10)
        if self.current_iteration >= max_iterations:
            return True, "max_iterations_reached"

        # 条件3: 连续5次无改善
        if len(self.metric_history) >= 5:
            recent_5 = [v for _, v in self.metric_history[-5:]]
            improvement = max(recent_5) - min(recent_5)
            tolerance = self.goal.get("convergence_tolerance", 0.01)
            if improvement < tolerance:
                return True, "no_improvement"

        # 条件4: 性能退化
        if self.trend == "degrading" and len(self.metric_history) >= 3:
            # 检查是否持续退化(最近3次都在下降)
            recent_3 = [v for _, v in self.metric_history[-3:]]
            if all(recent_3[i+1] < recent_3[i] for i in range(len(recent_3)-1)):
                return True, "performance_degrading"

        return False, ""

    def get_next_action(self) -> str:
        """
        基于当前趋势建议下一步行动

        策略:
        - improving: 继续当前策略
        - stable: 调整参数范围或算法
        - degrading: 回滚到最佳配置

        Returns:
            "continue" | "adjust_strategy" | "rollback"
        """
        if self.trend == "improving":
            return "continue"
        elif self.trend == "stable":
            return "adjust_strategy"
        elif self.trend == "degrading":
            return "rollback"
        else:
            return "continue"

    def get_progress_summary(self) -> Dict[str, Any]:
        """
        获取进度摘要 (用于日志和报告)

        Returns:
            进度摘要字典
        """
        target_metric = self.goal.get("target_metric", "NSE")
        target_value = self.goal.get("target_value", 0.7)

        current_value = self.metric_history[-1][1] if self.metric_history else None
        progress_pct = (current_value / target_value * 100) if current_value else 0

        return {
            "current_iteration": self.current_iteration,
            "max_iterations": self.goal.get("max_iterations", 10),
            "target_metric": target_metric,
            "target_value": target_value,
            "current_value": current_value,
            "best_value": self.best_value,
            "best_iteration": self.best_iteration,
            "trend": self.trend,
            "progress_percentage": min(progress_pct, 100),
            "history_length": len(self.metric_history)
        }

    def get_improvement_rate(self) -> Optional[float]:
        """
        计算改善率 (最近5次迭代的平均增长)

        Returns:
            改善率 (正数表示改善,负数表示退化)
        """
        if len(self.metric_history) < 2:
            return None

        # 使用最多5次历史
        recent = self.metric_history[-5:]
        values = [v for _, v in recent]

        # 计算平均变化率
        diffs = [values[i+1] - values[i] for i in range(len(values)-1)]
        avg_improvement = sum(diffs) / len(diffs)

        return avg_improvement

    def reset(self):
        """重置追踪器 (用于新任务)"""
        logger.info("[GoalTracker] Resetting tracker")
        self.current_iteration = 0
        self.metric_history.clear()
        self.trend = None
        self.best_value = float('-inf')
        self.best_iteration = 0


# ============================================================================
# 工厂函数
# ============================================================================

def create_calibration_goal_tracker(
    target_nse: float = 0.75,
    max_iterations: int = 10,
    convergence_tolerance: float = 0.01
) -> GoalTracker:
    """
    创建率定任务的目标追踪器 (快捷工厂函数)

    Args:
        target_nse: 目标NSE阈值
        max_iterations: 最大迭代次数
        convergence_tolerance: 收敛容差

    Returns:
        GoalTracker实例
    """
    goal_definition = {
        "type": "calibration",
        "target_metric": "NSE",
        "target_value": target_nse,
        "max_iterations": max_iterations,
        "convergence_tolerance": convergence_tolerance
    }
    return GoalTracker(goal_definition)


def create_evaluation_goal_tracker(
    target_metric: str = "NSE",
    target_value: float = 0.7
) -> GoalTracker:
    """
    创建验证任务的目标追踪器 (快捷工厂函数)

    Args:
        target_metric: 目标指标名称
        target_value: 目标阈值

    Returns:
        GoalTracker实例
    """
    goal_definition = {
        "type": "evaluation",
        "target_metric": target_metric,
        "target_value": target_value,
        "max_iterations": 1,  # 验证通常只有1次
        "convergence_tolerance": 0.0
    }
    return GoalTracker(goal_definition)
