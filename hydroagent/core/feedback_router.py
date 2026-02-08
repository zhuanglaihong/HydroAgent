"""
Author: Claude
Date: 2025-12-03 16:00:00
LastEditTime: 2026-01-13 20:45:00
LastEditors: Claude Code (v6.1 Fix)
Description: Feedback router for routing agent errors and feedback to appropriate handlers
             反馈路由器 - 将Agent的错误和反馈路由到合适的处理器
    v6.1 Fix (2026-01-13): Unknown source agents return 'continue' instead of 'abort'
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

        # 🔧 循环检测：记录最近的配置生成失败历史
        # 格式: [(config_hash, error_message), ...]
        self.config_failure_history = []
        self.max_history_size = 5  # 只保留最近5次失败
        self.loop_detection_threshold = 2  # 连续2次相同配置失败 = 循环

        logger.info("[FeedbackRouter] Initialized with error classification rules and loop detection")

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
            # 🔧 v6.1 Fix: Unknown source agents should not abort the task
            # This handles cases where Orchestrator's internal flow control
            # accidentally triggers FeedbackRouter (which should not happen)
            logger.warning(f"[FeedbackRouter] Unknown source agent: {source_agent}")
            logger.info("[FeedbackRouter] Returning 'continue' action to proceed with state machine")
            return {
                "target_agent": None,
                "action": "continue",  # 🔧 Changed from "abort" to "continue"
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
        - 🆕 复合任务 + 还有下一个子任务 → 继续执行下一个子任务
        """
        # 🆕 Check for compound task continuation
        should_continue = context.get("should_continue_compound_task", False)
        if should_continue:
            logger.info("[FeedbackRouter] Compound task: continuing to next subtask")
            return {
                "target_agent": "TaskPlanner",
                "action": "plan_tasks",
                "parameters": {},
                "retryable": False
            }

        # Check if all compound tasks are completed
        compound_completed = context.get("compound_task_completed", False)
        if compound_completed:
            compound_results = context.get("compound_task_results", [])
            logger.info(f"[FeedbackRouter] Compound task completed with {len(compound_results)} subtasks")
            return {
                "target_agent": None,
                "action": "complete_success",
                "parameters": {
                    "compound_results": compound_results
                },
                "retryable": False
            }

        analysis = feedback.get("analysis", {})
        metrics = analysis.get("metrics", {})
        nse = metrics.get("NSE", 0)
        recommendations = analysis.get("recommendations", [])

        # 获取NSE目标
        nse_target = context.get("nse_target", 0.7)

        # NSE达标,检查是否还有剩余子任务
        if nse >= nse_target:
            logger.info(f"[FeedbackRouter] NSE {nse:.4f} meets target {nse_target:.4f}")

            # ⭐ 检查是否还有pending的子任务需要执行
            task_plan = context.get("task_plan", {})
            subtasks = task_plan.get("subtasks", [])
            execution_results = context.get("execution_results", [])

            completed_ids = {r.get("task_id") for r in execution_results if r.get("success")}
            pending_subtasks = [st for st in subtasks if st.get("task_id") not in completed_ids]

            if pending_subtasks:
                # 还有剩余子任务，继续执行
                logger.info(f"[FeedbackRouter] NSE达标，但还有 {len(pending_subtasks)} 个子任务待执行，继续流程...")
                return {
                    "target_agent": None,
                    "action": "complete_success",  # 完成当前子任务
                    "parameters": {
                        "final_nse": nse,
                        "metrics": metrics,
                        "continue_subtasks": True  # 标记继续执行剩余子任务
                    },
                    "retryable": False
                }
            else:
                # 所有子任务都已完成，正常结束
                logger.info(f"[FeedbackRouter] NSE达标且所有子任务已完成，结束流程")
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

        # ⭐ 重要：检查用户原始任务类型
        # 只有当用户明确要求iterative_optimization时才触发迭代优化
        # 对于extended_analysis等其他任务类型，应该完成当前子任务后继续执行后续子任务
        # task_type从intent_result中获取
        intent_result = context.get("intent_result", {})
        if isinstance(intent_result, dict) and "intent_result" in intent_result:
            # v5.0格式: {"success": True, "intent_result": {"task_type": "...", ...}}
            task_type = intent_result.get("intent_result", {}).get("task_type")
        else:
            # 旧格式: 直接在顶层
            task_type = intent_result.get("task_type")

        if task_type != "iterative_optimization":
            logger.info(
                f"[FeedbackRouter] Task type is '{task_type}', not 'iterative_optimization'. "
                f"Completing current subtask (NSE={nse:.4f})."
            )
            # 对于非迭代优化任务，即使NSE未达标或有优化建议，也应该正常结束当前子任务
            # 让系统继续执行后续子任务（如extended_analysis的代码生成任务）
            return {
                "target_agent": None,
                "action": "complete_success",
                "parameters": {
                    "final_nse": nse,
                    "metrics": metrics
                },
                "retryable": False
            }

        # 只有明确的iterative_optimization任务才检查建议并触发优化
        logger.info("[FeedbackRouter] Task type is 'iterative_optimization', checking recommendations...")
        has_actionable_recommendation = False

        for rec in recommendations:
            if "参数范围" in rec or "parameter range" in rec.lower():
                # 建议调整参数范围 → 触发迭代优化
                logger.info("[FeedbackRouter] Triggering iterative optimization - parameter range adjustment needed")
                has_actionable_recommendation = True
                return {
                    "target_agent": "TaskPlanner",
                    "action": "trigger_iterative_optimization",
                    "parameters": {
                        "current_nse": nse,
                        "best_params": analysis.get("parameters", {}),
                        "iteration_count": iteration_count + 1,
                        "should_continue_iterating": True  # ⭐ 明确标志：应该继续迭代
                    },
                    "retryable": True
                }

            if "增加迭代" in rec or "increase.*iteration" in rec.lower():
                # 建议增加迭代次数
                logger.info("[FeedbackRouter] Increasing algorithm iterations")
                has_actionable_recommendation = True
                current_rep = context.get("rep", 500)
                return {
                    "target_agent": "InterpreterAgent",
                    "action": "increase_iterations",
                    "parameters": {
                        "current_rep": current_rep,
                        "new_rep": int(current_rep * 1.5),
                        "iteration_count": iteration_count + 1,
                        "should_continue_iterating": True  # ⭐ 明确标志：应该继续迭代
                    },
                    "retryable": True
                }

        # ⭐ CRITICAL FIX: 无明确建议时，不应该继续迭代
        # 设置should_continue_iterating=False，让State Machine知道不要继续迭代
        logger.info("[FeedbackRouter] No actionable recommendations, completing (should NOT continue iterating)")
        return {
            "target_agent": None,
            "action": "complete_partial",
            "parameters": {
                "final_nse": nse,
                "should_continue_iterating": False  # ⭐ 明确标志：不应该继续迭代
            },
            "retryable": False
        }

    def _compute_config_hash(self, config: Dict[str, Any]) -> str:
        """
        计算配置的简单哈希（用于循环检测）

        Args:
            config: 配置字典

        Returns:
            配置的哈希字符串
        """
        import hashlib
        import json

        # 提取关键字段用于哈希
        key_fields = {
            "model_name": config.get("model_cfgs", {}).get("model_name", ""),
            "basin_ids": str(config.get("data_cfgs", {}).get("basin_ids", [])),
            "algorithm": config.get("training_cfgs", {}).get("algorithm_name", "")
        }

        # 计算哈希
        config_str = json.dumps(key_fields, sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()[:8]

    def _detect_config_loop(self, config_hash: str, error_msg: str) -> bool:
        """
        检测是否出现配置生成循环

        Args:
            config_hash: 当前配置的哈希
            error_msg: 错误消息

        Returns:
            True if loop detected, False otherwise
        """
        # 添加到历史记录
        self.config_failure_history.append((config_hash, error_msg))

        # 保持历史记录大小
        if len(self.config_failure_history) > self.max_history_size:
            self.config_failure_history.pop(0)

        # 检测循环：最近N次失败中，有threshold次是相同配置
        if len(self.config_failure_history) < self.loop_detection_threshold:
            return False

        # 统计最近的配置哈希
        recent_hashes = [h for h, _ in self.config_failure_history[-self.loop_detection_threshold:]]
        same_config_count = recent_hashes.count(config_hash)

        if same_config_count >= self.loop_detection_threshold:
            logger.warning(
                f"[FeedbackRouter] 🔁 Loop detected! Same config failed {same_config_count} times. "
                f"Hash: {config_hash}"
            )
            return True

        return False

    def _route_interpreter_feedback(
        self,
        feedback: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        处理InterpreterAgent的反馈

        修复策略 (避免无限循环) v2.0:
        1. 第一次失败: 记录配置哈希
        2. 检测循环: 如果相同配置连续失败N次 → 跳过审查直接执行
        3. 否则: 终止流程

        核心问题: LLM审查器可能误判合理的配置，导致配置被反复拒绝。
        解决方案: 检测循环后，跳过审查直接执行（fallback机制）。
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
        config = feedback.get("config", {})  # 可能部分生成了配置
        retry_count = context.get("config_retry_count", 0)

        logger.warning(f"[FeedbackRouter] InterpreterAgent failed (attempt {retry_count + 1}): {error_msg[:200]}")

        # 🔧 新增：循环检测
        if config:
            config_hash = self._compute_config_hash(config)
            is_loop = self._detect_config_loop(config_hash, error_msg)

            if is_loop:
                logger.warning(
                    f"[FeedbackRouter] 🚨 Configuration validation loop detected! "
                    f"Same config rejected multiple times."
                )
                logger.warning(
                    f"[FeedbackRouter] 🔧 Applying fallback: Skip review and execute with generated config"
                )
                logger.warning(f"[FeedbackRouter] Config hash: {config_hash}")
                logger.warning(f"[FeedbackRouter] Error was: {error_msg[:150]}")

                # Fallback: 跳过审查，直接使用生成的配置执行
                return {
                    "target_agent": "RunnerAgent",
                    "action": "skip_review_and_execute",
                    "parameters": {
                        "config": config,
                        "skip_reason": "validation_loop_detected",
                        "original_error": error_msg[:200]
                    },
                    "retryable": False
                }

        # 🔧 原有逻辑: 直接终止，避免无限循环
        logger.error(f"[FeedbackRouter] Aborting after config validation failure (anti-loop protection)")
        return {
            "target_agent": None,
            "action": "abort",
            "parameters": {
                "reason": f"Configuration validation failed: {error_msg[:300]}",
                "error_type": "configuration_validation_error",
                "llm_feedback": error_msg,
                "suggestion": "Check LLMConfigReviewer prompt or disable strict validation"
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
