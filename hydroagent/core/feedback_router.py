"""
Author: Claude
Date: 2025-12-03 16:00:00
LastEditTime: 2025-12-03 16:00:00
LastEditors: Claude
Description: Feedback router for routing agent errors and feedback to appropriate handlers
             反馈路由器 - 将Agent的错误和反馈路由到合适的处理器
FilePath: /HydroAgent/hydroagent/core/feedback_router.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

核心功能:
1. 错误分类 (configuration_error, timeout, data_not_found等)
2. 反馈路由 (根据错误类型决定回退到哪个Agent)
3. 决策建议 (retry, adjust_params, regenerate_config等)
"""

from typing import Dict, Any, Optional
import logging
import re

logger = logging.getLogger(__name__)


class FeedbackRouter:
    """
    Agent反馈路由器

    职责:
    - 接收Agent的执行结果和错误信息
    - 分类错误类型
    - 决定反馈目标 (哪个上游Agent需要调整)
    - 提供恢复建议
    """

    def __init__(self):
        """初始化反馈路由器"""
        # 错误模式匹配规则
        self.error_patterns = self._build_error_patterns()
        logger.info("[FeedbackRouter] Initialized with error classification rules")

    def _build_error_patterns(self) -> Dict[str, list]:
        """
        构建错误匹配模式

        Returns:
            错误类型 → 匹配模式列表
        """
        return {
            "configuration_error": [
                r"KeyError",  # 通用 KeyError 匹配
                r"missing.*required.*parameter",
                r"invalid.*configuration",
                r"config.*not.*found"
            ],
            "data_not_found": [
                r"FileNotFoundError",
                r"basin.*not.*found",
                r"data.*not.*available",
                r"No such file or directory",
                r"Dataset.*missing"
            ],
            "timeout": [
                r"TimeoutError",
                r"exceeded.*timeout",
                r"took too long",
                r"execution.*timed out"
            ],
            "dependency_error": [
                r"ImportError",
                r"ModuleNotFoundError",
                r"cannot import",
                r"No module named"
            ],
            "numerical_error": [
                r"NaN",
                r"inf",
                r"overflow",
                r"underflow",
                r"invalid.*value",
                r"math domain error"
            ],
            "memory_error": [
                r"MemoryError",
                r"out of memory",
                r"cannot allocate memory"
            ]
        }

    def route_feedback(
        self,
        source_agent: str,
        feedback: Dict[str, Any],
        orchestrator_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        路由Agent反馈到合适的目标

        Args:
            source_agent: 反馈来源 ("IntentAgent", "RunnerAgent", "DeveloperAgent", "InterpreterAgent"等)
            feedback: 反馈内容字典
            orchestrator_context: Orchestrator全局上下文

        Returns:
            路由决策字典:
            {
                "target_agent": str,        # 目标Agent名称 (None表示无需回退)
                "action": str,              # 建议动作
                "parameters": dict,         # 动作参数
                "retryable": bool          # 是否可重试
            }
        """
        if source_agent == "IntentAgent":
            return self._route_intent_feedback(feedback, orchestrator_context)
        elif source_agent == "TaskPlanner":
            return self._route_planner_feedback(feedback, orchestrator_context)
        elif source_agent == "RunnerAgent":
            return self._route_runner_feedback(feedback, orchestrator_context)
        elif source_agent == "DeveloperAgent":
            return self._route_developer_feedback(feedback, orchestrator_context)
        elif source_agent == "InterpreterAgent":
            return self._route_interpreter_feedback(feedback, orchestrator_context)
        else:
            logger.warning(f"[FeedbackRouter] Unknown source agent: {source_agent}")
            return {
                "target_agent": None,
                "action": "abort",
                "parameters": {},
                "retryable": False
            }

    def _route_intent_feedback(
        self,
        feedback: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        处理IntentAgent的反馈

        IntentAgent成功 → 继续到TaskPlanner
        IntentAgent失败 → 终止流程
        """
        if feedback.get("success", False):
            return {
                "target_agent": "TaskPlanner",
                "action": "plan_tasks",
                "parameters": {},
                "retryable": False
            }
        else:
            # Intent识别失败,终止
            return {
                "target_agent": None,
                "action": "abort",
                "parameters": {
                    "reason": "Intent recognition failed"
                },
                "retryable": False
            }

    def _route_planner_feedback(
        self,
        feedback: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        处理TaskPlanner的反馈

        TaskPlanner成功 → 继续到InterpreterAgent
        TaskPlanner失败 → 终止流程
        """
        if feedback.get("success", False):
            return {
                "target_agent": "InterpreterAgent",
                "action": "generate_config",
                "parameters": {},
                "retryable": False
            }
        else:
            # Task planning失败,终止
            return {
                "target_agent": None,
                "action": "abort",
                "parameters": {
                    "reason": "Task planning failed"
                },
                "retryable": False
            }

    def _route_runner_feedback(
        self,
        feedback: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        处理RunnerAgent的反馈

        错误类型 → 路由目标:
        - configuration_error → InterpreterAgent (重新生成配置)
        - data_not_found → IntentAgent (验证basin_id)
        - timeout → TaskPlanner (减少复杂度)
        - dependency_error → 终止 (不可恢复)
        - numerical_error → InterpreterAgent (调整参数范围)
        """
        # 如果执行成功,路由到DeveloperAgent进行分析
        if feedback.get("success", False):
            return {
                "target_agent": "DeveloperAgent",
                "action": "analyze_results",
                "parameters": {
                    "execution_result": feedback
                },
                "retryable": False
            }

        # 执行失败,分类错误
        error_msg = feedback.get("error", "")
        error_type = self._classify_error(error_msg)

        logger.info(f"[FeedbackRouter] Classified error as: {error_type}")

        # 根据错误类型路由
        if error_type == "configuration_error":
            return {
                "target_agent": "InterpreterAgent",
                "action": "regenerate_config",
                "parameters": {
                    "error_log": error_msg,
                    "previous_config": context.get("last_config"),
                    "retry_count": context.get("config_retry_count", 0) + 1
                },
                "retryable": True
            }

        elif error_type == "data_not_found":
            return {
                "target_agent": "IntentAgent",
                "action": "verify_data_availability",
                "parameters": {
                    "basin_id": context.get("basin_id"),
                    "error_log": error_msg
                },
                "retryable": False  # 数据问题通常不可重试
            }

        elif error_type == "timeout":
            return {
                "target_agent": "TaskPlanner",
                "action": "reduce_complexity",
                "parameters": {
                    "current_rep": context.get("rep", 500),
                    "reduction_factor": 0.7,
                    "retry_count": context.get("execution_retry_count", 0) + 1
                },
                "retryable": True
            }

        elif error_type == "dependency_error":
            return {
                "target_agent": None,
                "action": "abort",
                "parameters": {
                    "reason": "Missing dependencies",
                    "error_log": error_msg
                },
                "retryable": False
            }

        elif error_type == "numerical_error":
            return {
                "target_agent": "InterpreterAgent",
                "action": "adjust_parameter_ranges",
                "parameters": {
                    "error_log": error_msg,
                    "retry_count": context.get("config_retry_count", 0) + 1
                },
                "retryable": True
            }

        elif error_type == "memory_error":
            return {
                "target_agent": "TaskPlanner",
                "action": "reduce_batch_size",
                "parameters": {
                    "error_log": error_msg
                },
                "retryable": True
            }

        else:
            # 未知错误,尝试重试
            retry_count = context.get("execution_retry_count", 0)
            return {
                "target_agent": "InterpreterAgent" if retry_count < 2 else None,
                "action": "retry_with_default_config" if retry_count < 2 else "abort",
                "parameters": {
                    "error_log": error_msg,
                    "retry_count": retry_count + 1
                },
                "retryable": retry_count < 2
            }

    def _route_developer_feedback(
        self,
        feedback: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        处理DeveloperAgent的反馈

        决策逻辑:
        - NSE达标 → 正常结束
        - NSE未达标 + 建议调整参数范围 → TaskPlanner (触发迭代优化)
        - NSE未达标 + 建议增加迭代 → InterpreterAgent (增加rep)
        - NSE未达标 + 达到最大迭代次数 → 结束 (部分成功)
        """
        analysis = feedback.get("analysis", {})
        metrics = analysis.get("metrics", {})
        nse = metrics.get("NSE", 0)
        recommendations = analysis.get("recommendations", [])

        # 获取NSE目标
        nse_target = context.get("nse_target", 0.7)

        # NSE达标,正常结束
        if nse >= nse_target:
            logger.info(f"[FeedbackRouter] NSE {nse:.4f} meets target {nse_target:.4f}")
            return {
                "target_agent": None,
                "action": "complete_success",
                "parameters": {
                    "final_nse": nse,
                    "metrics": metrics
                },
                "retryable": False
            }

        # NSE未达标,检查是否达到最大迭代次数
        iteration_count = context.get("iteration_count", 0)
        max_iterations = context.get("max_iterations", 10)

        if iteration_count >= max_iterations:
            logger.info(f"[FeedbackRouter] Reached max iterations ({max_iterations})")
            return {
                "target_agent": None,
                "action": "complete_partial",
                "parameters": {
                    "final_nse": nse,
                    "iterations": iteration_count
                },
                "retryable": False
            }

        # NSE未达标,检查建议
        for rec in recommendations:
            if "参数范围" in rec or "parameter range" in rec.lower():
                # 建议调整参数范围 → 触发迭代优化
                logger.info("[FeedbackRouter] Triggering iterative optimization")
                return {
                    "target_agent": "TaskPlanner",
                    "action": "trigger_iterative_optimization",
                    "parameters": {
                        "current_nse": nse,
                        "best_params": analysis.get("parameters", {}),
                        "iteration_count": iteration_count + 1
                    },
                    "retryable": True
                }

            if "增加迭代" in rec or "increase.*iteration" in rec.lower():
                # 建议增加迭代次数
                logger.info("[FeedbackRouter] Increasing algorithm iterations")
                current_rep = context.get("rep", 500)
                return {
                    "target_agent": "InterpreterAgent",
                    "action": "increase_iterations",
                    "parameters": {
                        "current_rep": current_rep,
                        "new_rep": int(current_rep * 1.5),
                        "iteration_count": iteration_count + 1
                    },
                    "retryable": True
                }

        # 无明确建议,默认结束
        logger.info("[FeedbackRouter] No actionable recommendations, completing")
        return {
            "target_agent": None,
            "action": "complete_partial",
            "parameters": {
                "final_nse": nse
            },
            "retryable": False
        }

    def _route_interpreter_feedback(
        self,
        feedback: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        处理InterpreterAgent的反馈

        通常InterpreterAgent不需要反馈路由,
        但如果配置生成失败,可以回退到TaskPlanner重新规划
        """
        if feedback.get("success", False):
            return {
                "target_agent": "RunnerAgent",
                "action": "execute_task",
                "parameters": {
                    "config": feedback.get("config")
                },
                "retryable": False
            }

        # 配置生成失败
        error_msg = feedback.get("error", "")
        retry_count = context.get("config_retry_count", 0)

        if retry_count < 3:
            return {
                "target_agent": "TaskPlanner",
                "action": "adjust_task_plan",
                "parameters": {
                    "error_log": error_msg,
                    "retry_count": retry_count + 1
                },
                "retryable": True
            }
        else:
            return {
                "target_agent": None,
                "action": "abort",
                "parameters": {
                    "reason": "Config generation failed after 3 retries"
                },
                "retryable": False
            }

    def _classify_error(self, error_msg: str) -> str:
        """
        分类错误类型

        Args:
            error_msg: 错误消息字符串

        Returns:
            错误类型字符串
        """
        if not error_msg:
            return "unknown"

        # 遍历所有错误模式
        for error_type, patterns in self.error_patterns.items():
            for pattern in patterns:
                if re.search(pattern, error_msg, re.IGNORECASE):
                    return error_type

        return "unknown"

    def classify_error_batch(self, error_msgs: list) -> Dict[str, int]:
        """
        批量分类错误 (用于统计分析)

        Args:
            error_msgs: 错误消息列表

        Returns:
            错误类型统计字典 {error_type: count}
        """
        stats = {}
        for msg in error_msgs:
            error_type = self._classify_error(msg)
            stats[error_type] = stats.get(error_type, 0) + 1

        return stats
