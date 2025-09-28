"""
Author: zhuanglaihong
Date: 2024-09-24 16:48:00
LastEditTime: 2024-09-24 16:48:00
LastEditors: zhuanglaihong
Description: Main workflow builder - orchestrates planning and execution mode determination
FilePath: \HydroAgent\builder\workflow_builder.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import logging
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from .rag_planner import RAGPlanner, PlanningResult, get_rag_planner
from .execution_mode import ExecutionModeAnalyzer, ExecutionMode, ModeAnalysisResult, get_mode_analyzer
from .llm_client import LLMClient, get_llm_client
from .intent_parser import IntentParser, IntentResult, IntentType, get_intent_parser

logger = logging.getLogger(__name__)


@dataclass
class WorkflowBuildResult:
    """工作流构建结果"""
    success: bool
    workflow: Dict[str, Any]
    execution_mode: ExecutionMode
    intent_result: IntentResult
    mode_analysis: ModeAnalysisResult
    planning_result: PlanningResult
    build_time: float
    error_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "success": self.success,
            "workflow": self.workflow,
            "execution_mode": self.execution_mode.value,
            "intent_analysis": {
                "intent_type": self.intent_result.intent_type.value,
                "confidence": self.intent_result.confidence,
                "clarified_intent": self.intent_result.clarified_intent,
                "entities_count": sum(len(entities) for entities in self.intent_result.entities.values()),
                "suggested_tools": self.intent_result.suggested_tools
            },
            "mode_analysis": {
                "recommended_mode": self.mode_analysis.recommended_mode.value,
                "confidence": self.mode_analysis.confidence,
                "reasoning": self.mode_analysis.reasoning,
                "complexity_score": self.mode_analysis.complexity_score,
                "features": self.mode_analysis.features
            },
            "planning_stats": {
                "planning_time": self.planning_result.planning_time,
                "cot_steps_count": len(self.planning_result.cot_steps),
                "knowledge_fragments": len(self.planning_result.rag_context.fragments) if self.planning_result.rag_context else 0
            },
            "build_time": self.build_time,
            "error_message": self.error_message,
            "metadata": self.metadata
        }


class WorkflowBuilder:
    """
    工作流构建器 - 整个Agent的规划层
    结合RAG知识库和思维链推理，生成可执行的工作流
    """

    def __init__(self, rag_system=None, llm_client: LLMClient = None, enable_rag: bool = True,
                 use_api_llm: bool = True):
        """
        初始化工作流构建器

        Args:
            rag_system: RAG系统实例
            llm_client: LLM客户端实例
            enable_rag: 是否启用RAG系统，测试时可设为False
            use_api_llm: LLM推理模式 - True使用API优先，False强制使用本地Ollama
        """
        self.use_api_llm = use_api_llm
        # RAG和工作流生成需要LLM推理，根据参数选择模式
        self.llm_client = llm_client or get_llm_client(use_api_first=use_api_llm, force_local=not use_api_llm)

        # 初始化RAG系统
        if rag_system is None and enable_rag:
            try:
                from hydrorag import RAGSystem, Config
                # 创建本地优先的配置，避免网络依赖
                local_config = Config(
                    # 禁用API嵌入，优先使用本地Ollama
                    openai_api_key=None,
                    embedding_model_name="bge-large:335m",  # 使用本地模型
                    local_embedding_model="bge-large:335m"
                )
                self.rag_system = RAGSystem(local_config)
                # 检查RAG系统是否初始化成功
                if self.rag_system.is_initialized:
                    logger.info("自动初始化RAG系统成功")
                else:
                    logger.warning(f"RAG系统初始化部分失败: {self.rag_system.initialization_errors}")
                    # 仍然保留实例，但功能可能受限
            except Exception as e:
                logger.warning(f"自动初始化RAG系统失败: {e}，将以None模式运行")
                self.rag_system = None
        elif rag_system is not None:
            self.rag_system = rag_system
        else:
            # enable_rag=False 或者测试模式
            self.rag_system = None
            if not enable_rag:
                logger.info("RAG系统被禁用，运行在简化模式")

        # 初始化子组件
        # 意图解析器默认不使用LLM增强，主要依靠规则匹配以提升性能
        self.intent_parser = get_intent_parser(llm_client=None, enable_llm_enhancement=False)
        self.rag_planner = get_rag_planner(rag_system=self.rag_system, llm_client=self.llm_client)
        self.mode_analyzer = get_mode_analyzer()

        # 统计信息
        self.stats = {
            "total_builds": 0,
            "successful_builds": 0,
            "failed_builds": 0,
            "avg_build_time": 0.0,
            "execution_mode_distribution": {
                "linear": 0,
                "react": 0,
                "hybrid": 0
            }
        }

        logger.info("工作流构建器初始化完成")

    def enable_intent_llm_enhancement(self, enable: bool = True):
        """
        动态启用或禁用意图解析器的LLM增强功能
        注意：正常情况下意图解析器不需要LLM，这个方法仅用于特殊场景

        Args:
            enable: 是否启用LLM增强
        """
        if enable and not self.intent_parser.enable_llm_enhancement:
            # 重新创建意图解析器并启用LLM增强
            self.intent_parser = get_intent_parser(llm_client=self.llm_client, enable_llm_enhancement=True)
            logger.info("已启用意图解析器LLM增强功能（通常不推荐）")
        elif not enable and self.intent_parser.enable_llm_enhancement:
            # 重新创建意图解析器并禁用LLM增强
            self.intent_parser = get_intent_parser(llm_client=None, enable_llm_enhancement=False)
            logger.info("已禁用意图解析器LLM增强功能")

    def build_workflow(self, query: str, context: Dict[str, Any] = None) -> WorkflowBuildResult:
        """
        构建工作流

        Args:
            query: 用户查询
            context: 额外上下文信息

        Returns:
            WorkflowBuildResult: 构建结果
        """
        start_time = time.time()
        self.stats["total_builds"] += 1

        try:
            logger.info(f"开始构建工作流: {query[:100]}...")

            # 第一步：意图解析与理解
            logger.info("第一步：意图解析与理解")
            intent_result = self.intent_parser.parse_instruction(query)

            if intent_result.intent_type.value == "unknown":
                logger.warning(f"无法识别用户意图，将使用原始查询继续")

            # 第二步：使用RAG规划器生成工作流
            logger.info("第二步：RAG规划生成工作流")
            # 将意图结果传递给规划器以增强规划效果
            enhanced_context = context or {}
            enhanced_context.update({
                "intent_result": intent_result.to_dict(),
                "suggested_tools": intent_result.suggested_tools,
                "clarified_intent": intent_result.clarified_intent
            })

            planning_result = self.rag_planner.plan_workflow(query, enhanced_context)

            if not planning_result.success:
                logger.warning(f"RAG规划失败: {planning_result.error_message}")
                # 继续使用fallback工作流

            workflow = planning_result.workflow

            # 第三步：分析执行模式
            logger.info("第三步：分析执行模式")
            mode_analysis = self.mode_analyzer.analyze_workflow(workflow)

            # 第四步：应用执行模式到工作流
            logger.info(f"第四步：应用执行模式 - {mode_analysis.recommended_mode.value}")
            workflow = self._apply_execution_mode(workflow, mode_analysis.recommended_mode)

            # 第五步：最终验证和优化
            logger.info("第五步：最终验证和优化")
            workflow = self._finalize_workflow(workflow, mode_analysis, intent_result)

            build_time = time.time() - start_time

            # 更新统计信息
            self.stats["successful_builds"] += 1
            self._update_stats(build_time, mode_analysis.recommended_mode)

            logger.info(f"工作流构建成功: {workflow.get('name', 'unknown')} "
                       f"({len(workflow.get('tasks', []))}个任务, "
                       f"{mode_analysis.recommended_mode.value}模式, "
                       f"耗时{build_time:.2f}秒)")

            return WorkflowBuildResult(
                success=True,
                workflow=workflow,
                execution_mode=mode_analysis.recommended_mode,
                intent_result=intent_result,
                mode_analysis=mode_analysis,
                planning_result=planning_result,
                build_time=build_time,
                metadata={
                    "query": query,
                    "context": context,
                    "build_timestamp": datetime.now().isoformat()
                }
            )

        except Exception as e:
            error_msg = str(e)
            build_time = time.time() - start_time

            # 更新失败统计
            self.stats["failed_builds"] += 1
            self._update_stats(build_time, ExecutionMode.LINEAR)

            logger.error(f"工作流构建失败: {error_msg}")

            # 返回最小可用工作流
            fallback_workflow = self._create_emergency_workflow(query)
            fallback_mode_analysis = ModeAnalysisResult(
                recommended_mode=ExecutionMode.LINEAR,
                confidence=0.5,
                reasoning="构建失败，使用应急线性模式",
                complexity_score=0.0,
                features={}
            )
            fallback_intent = IntentResult(
                original_query=query,
                intent_type=IntentType.UNKNOWN,
                entities={},
                parameters={},
                constraints={},
                confidence=0.0,
                processing_time=0.0
            )

            return WorkflowBuildResult(
                success=False,
                workflow=fallback_workflow,
                execution_mode=ExecutionMode.LINEAR,
                intent_result=fallback_intent,
                mode_analysis=fallback_mode_analysis,
                planning_result=PlanningResult(
                    workflow=fallback_workflow,
                    rag_context=None,
                    cot_steps=[],
                    planning_time=0.0,
                    success=False,
                    error_message=error_msg
                ),
                build_time=build_time,
                error_message=error_msg,
                metadata={"query": query, "context": context}
            )

    def _apply_execution_mode(self, workflow: Dict[str, Any], mode: ExecutionMode) -> Dict[str, Any]:
        """应用执行模式到工作流"""
        try:
            # 更新工作流的执行模式
            workflow["execution_mode"] = mode.value

            # 根据模式调整任务配置
            tasks = workflow.get("tasks", [])

            if mode == ExecutionMode.LINEAR:
                # 线性模式：确保严格的依赖顺序
                workflow = self._optimize_for_linear_execution(workflow)

            elif mode == ExecutionMode.REACT:
                # 反应式模式：添加错误处理和重试机制
                workflow = self._optimize_for_react_execution(workflow)

            elif mode == ExecutionMode.HYBRID:
                # 混合模式：根据任务类型选择执行方式
                workflow = self._optimize_for_hybrid_execution(workflow)

            return workflow

        except Exception as e:
            logger.error(f"应用执行模式失败: {str(e)}")
            workflow["execution_mode"] = ExecutionMode.LINEAR.value
            return workflow

    def _optimize_for_linear_execution(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """为线性执行优化工作流"""
        tasks = workflow.get("tasks", [])

        # 简化依赖关系，确保线性顺序
        for i, task in enumerate(tasks):
            if i == 0:
                task["dependencies"] = []
            else:
                task["dependencies"] = [tasks[i-1]["task_id"]]

            # 移除复杂的条件判断
            task["conditions"] = task.get("conditions", {})
            if "retry_count" in task["conditions"]:
                task["conditions"]["retry_count"] = min(task["conditions"]["retry_count"], 2)

        workflow["metadata"]["optimization"] = "linear_optimized"
        return workflow

    def _optimize_for_react_execution(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """为反应式执行优化工作流"""
        tasks = workflow.get("tasks", [])

        for task in tasks:
            # 为复杂任务添加重试和超时机制
            if task.get("task_type") == "complex_reasoning":
                conditions = task.get("conditions", {})
                conditions["retry_count"] = conditions.get("retry_count", 3)
                conditions["timeout"] = conditions.get("timeout", 300)
                conditions["on_error"] = "retry_or_skip"
                task["conditions"] = conditions

            # 为率定任务添加反馈机制
            if "calibrate" in task.get("action", "").lower():
                task["feedback_enabled"] = True

        workflow["metadata"]["optimization"] = "react_optimized"
        return workflow

    def _optimize_for_hybrid_execution(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """为混合执行优化工作流"""
        tasks = workflow.get("tasks", [])

        for task in tasks:
            task_type = task.get("task_type", "simple_action")

            if task_type == "simple_action":
                # 简单任务使用线性执行
                task["execution_style"] = "linear"
                # 限制重试次数
                conditions = task.get("conditions", {})
                conditions["retry_count"] = min(conditions.get("retry_count", 1), 2)
                task["conditions"] = conditions

            elif task_type == "complex_reasoning":
                # 复杂任务使用反应式执行
                task["execution_style"] = "reactive"
                conditions = task.get("conditions", {})
                conditions["retry_count"] = conditions.get("retry_count", 3)
                conditions["timeout"] = conditions.get("timeout", 300)
                task["conditions"] = conditions

        workflow["metadata"]["optimization"] = "hybrid_optimized"
        return workflow

    def _finalize_workflow(self, workflow: Dict[str, Any], mode_analysis: ModeAnalysisResult, intent_result: IntentResult) -> Dict[str, Any]:
        """最终化工作流"""
        try:
            # 添加构建元数据
            metadata = workflow.get("metadata", {})
            metadata.update({
                "build_timestamp": datetime.now().isoformat(),
                "complexity_score": mode_analysis.complexity_score,
                "execution_mode": mode_analysis.recommended_mode.value,
                "mode_confidence": mode_analysis.confidence,
                "features_detected": mode_analysis.features,
                "intent_type": intent_result.intent_type.value,
                "intent_confidence": intent_result.confidence,
                "clarified_intent": intent_result.clarified_intent,
                "entities_detected": len(intent_result.entities),
                "builder_version": "1.1"
            })
            workflow["metadata"] = metadata

            # 验证工作流
            validation = self.rag_planner.validate_workflow(workflow)
            if not validation["is_valid"]:
                logger.warning(f"工作流验证发现问题: {validation['errors']}")
                metadata["validation_warnings"] = validation["errors"]

            # 确保必需字段
            if "workflow_id" not in workflow:
                workflow["workflow_id"] = f"workflow_{int(time.time())}"

            if "name" not in workflow:
                workflow["name"] = f"自动生成工作流_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            return workflow

        except Exception as e:
            logger.error(f"工作流最终化失败: {str(e)}")
            return workflow

    def _create_emergency_workflow(self, query: str) -> Dict[str, Any]:
        """创建应急工作流"""
        return {
            "workflow_id": f"emergency_{int(time.time())}",
            "name": "应急工作流",
            "description": f"针对查询 '{query[:50]}...' 的应急工作流",
            "execution_mode": "linear",
            "tasks": [
                {
                    "task_id": "emergency_task",
                    "name": "应急处理",
                    "description": "系统异常时的应急处理任务",
                    "action": "get_model_params",
                    "task_type": "simple_action",
                    "parameters": {},
                    "dependencies": [],
                    "conditions": {},
                    "expected_output": "基本系统信息"
                }
            ],
            "metadata": {
                "created_time": datetime.now().isoformat(),
                "is_emergency": True,
                "original_query": query
            }
        }

    def _update_stats(self, build_time: float, mode: ExecutionMode):
        """更新统计信息"""
        total_builds = self.stats["total_builds"]
        if total_builds > 0:
            current_avg = self.stats["avg_build_time"]
            self.stats["avg_build_time"] = (current_avg * (total_builds - 1) + build_time) / total_builds

        self.stats["execution_mode_distribution"][mode.value] += 1

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_builds = self.stats["total_builds"]
        success_rate = self.stats["successful_builds"] / total_builds if total_builds > 0 else 0.0

        return {
            **self.stats,
            "success_rate": success_rate,
            "system_health": "优秀" if success_rate >= 0.9 else "良好" if success_rate >= 0.7 else "需要关注",
            "llm_client_stats": self.llm_client.get_stats() if self.llm_client else {}
        }

    def test_build(self, test_query: str = "率定GR4J模型") -> WorkflowBuildResult:
        """
        测试构建功能

        Args:
            test_query: 测试查询

        Returns:
            WorkflowBuildResult: 测试结果
        """
        logger.info(f"开始测试构建: {test_query}")
        result = self.build_workflow(test_query, {"test_mode": True})

        if result.success:
            logger.info("测试构建成功")
        else:
            logger.error(f"测试构建失败: {result.error_message}")

        return result

    def is_ready(self) -> Dict[str, bool]:
        """检查构建器就绪状态"""
        status = {
            "llm_client_ready": self.llm_client.is_available() if self.llm_client else False,
            "rag_system_ready": self.rag_system is not None,
            "intent_parser_ready": self.intent_parser is not None,
            "mode_analyzer_ready": self.mode_analyzer is not None,
            "rag_planner_ready": self.rag_planner is not None
        }

        # RAG系统虽然重要，但在某些情况下可以不依赖RAG系统运行
        # 因此overall_ready不强制要求rag_system_ready，但会记录状态
        status["overall_ready"] = all([
            status["llm_client_ready"],
            status["intent_parser_ready"],
            status["mode_analyzer_ready"],
            status["rag_planner_ready"]
        ])

        # 如果RAG系统就绪，记录为非降级模式（OK）
        status["degraded_mode"] = status["rag_system_ready"]

        return status


# 全局实例
_workflow_builder = None


def get_workflow_builder(rag_system=None, llm_client: LLMClient = None) -> WorkflowBuilder:
    """获取全局工作流构建器实例"""
    global _workflow_builder
    if _workflow_builder is None:
        _workflow_builder = WorkflowBuilder(rag_system=rag_system, llm_client=llm_client)
    return _workflow_builder