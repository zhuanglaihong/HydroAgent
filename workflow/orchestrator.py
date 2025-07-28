"""
Author: zhuanglaihong
Date: 2025-07-28
Description: 工作流编排器 - 主编排器，整合所有步骤实现完整的工作流系统
"""

import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

from .intent_processor import IntentProcessor
from .query_expander import QueryExpander
from .knowledge_retriever import KnowledgeRetriever
from .context_builder import ContextBuilder
from .workflow_generator import WorkflowGenerator
from .workflow_types import WorkflowPlan, IntentAnalysis, KnowledgeFragment

logger = logging.getLogger(__name__)


class WorkflowOrchestrator:
    """工作流编排器 - 整合6步流程的主要协调器"""

    def __init__(
        self,
        llm,
        embeddings=None,
        rag_system=None,
        tools=None,
        faiss_index_path: str = "./faiss_db",
        enable_debug: bool = False,
    ):
        """
        初始化工作流编排器

        Args:
            llm: 语言模型实例
            embeddings: 嵌入模型实例
            rag_system: RAG系统实例
            tools: 可用工具列表
            faiss_index_path: FAISS索引路径
            enable_debug: 是否启用调试模式
        """
        self.llm = llm
        self.embeddings = embeddings
        self.rag_system = rag_system
        self.tools = tools
        self.enable_debug = enable_debug

        # 统计信息
        self.execution_stats = {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "total_execution_time": 0.0,
            "avg_execution_time": 0.0,
        }

        # 初始化各个组件
        self._initialize_components(faiss_index_path)

    def _initialize_components(self, faiss_index_path: str):
        """初始化各个组件"""
        try:
            logger.info("初始化工作流组件...")

            # 第1步：意图处理器
            self.intent_processor = IntentProcessor(self.llm)
            logger.info("✅ 意图处理器初始化完成")

            # 第2步：查询扩展器
            self.query_expander = QueryExpander(self.llm)
            logger.info("✅ 查询扩展器初始化完成")

            # 第3步：知识检索器
            self.knowledge_retriever = KnowledgeRetriever(
                rag_system=self.rag_system,
                faiss_index_path=faiss_index_path,
                embeddings=self.embeddings,
                llm=self.llm,
            )
            logger.info("✅ 知识检索器初始化完成")

            # 第4步：上下文构建器
            self.context_builder = ContextBuilder(
                max_context_length=4000, knowledge_weight=0.7, user_intent_weight=0.3
            )
            logger.info("✅ 上下文构建器初始化完成")

            # 第5步：工作流生成器
            self.workflow_generator = WorkflowGenerator(
                llm=self.llm,
                max_steps=10,
                allow_parallel=False,
                include_validation=True,
            )
            logger.info("✅ 工作流生成器初始化完成")

            logger.info("🎉 所有工作流组件初始化完成")

        except Exception as e:
            logger.error(f"组件初始化失败: {e}")
            raise

    def process_query(self, user_query: str, debug: bool = False) -> WorkflowPlan:
        """
        处理用户查询，生成完整的工作流

        Args:
            user_query: 用户查询
            debug: 是否启用调试模式

        Returns:
            WorkflowPlan: 生成的工作流计划
        """
        start_time = time.time()
        debug_info = {} if (debug or self.enable_debug) else None

        try:
            logger.info(f"开始处理查询: {user_query}")
            self.execution_stats["total_queries"] += 1

            # 第1步：意图理解
            logger.info("🔍 第1步：意图理解...")
            intent_analysis = self.intent_processor.process_intent(user_query)
            if debug_info is not None:
                debug_info["step1_intent"] = intent_analysis.to_dict()
            logger.info(
                f"   意图类型: {intent_analysis.task_type}, 置信度: {intent_analysis.confidence:.2f}"
            )

            # 第2步：查询扩展
            logger.info("📝 第2步：查询扩展...")
            expanded_query = self.query_expander.expand_query(intent_analysis)
            if debug_info is not None:
                debug_info["step2_expanded_query"] = expanded_query
            logger.info(f"   扩展查询长度: {len(expanded_query)}")

            # 第3步：知识检索
            logger.info("🔎 第3步：知识检索...")
            knowledge_fragments = self.knowledge_retriever.retrieve_knowledge(
                expanded_query=expanded_query,
                k=5,
                score_threshold=0.3,
                retriever_type="vector",
            )
            if debug_info is not None:
                debug_info["step3_knowledge"] = [
                    frag.to_dict() for frag in knowledge_fragments
                ]
            logger.info(f"   检索到 {len(knowledge_fragments)} 个知识片段")

            # 第4步：上下文构建
            logger.info("🔧 第4步：上下文构建...")
            context = self.context_builder.build_context(
                user_query=user_query,
                intent_analysis=intent_analysis,
                knowledge_fragments=knowledge_fragments,
                include_examples=True,
            )
            if debug_info is not None:
                debug_info["step4_context_length"] = len(context)
                debug_info["step4_context_preview"] = (
                    context[:500] + "..." if len(context) > 500 else context
                )
            logger.info(f"   上下文长度: {len(context)}")

            # 第5步：工作流生成
            logger.info("⚙️ 第5步：工作流生成...")
            workflow_plan = self.workflow_generator.generate_workflow(
                context=context,
                user_query=user_query,
                expanded_query=expanded_query,
                intent_analysis=intent_analysis,
            )
            if debug_info is not None:
                debug_info["step5_workflow"] = workflow_plan.to_dict()
            logger.info(
                f"   生成工作流: {workflow_plan.name}, 包含 {len(workflow_plan.steps)} 个步骤"
            )

            # 第6步：工作流验证（确保LangChain兼容性）
            logger.info("✅ 第6步：工作流验证...")
            is_valid = self.workflow_generator.validate_workflow_for_langchain(
                workflow_plan
            )
            if not is_valid:
                logger.warning("工作流验证失败，可能影响执行")
            else:
                logger.info("   工作流验证通过，符合LangChain执行要求")

            # 更新统计信息
            execution_time = time.time() - start_time
            self.execution_stats["successful_queries"] += 1
            self.execution_stats["total_execution_time"] += execution_time
            self.execution_stats["avg_execution_time"] = (
                self.execution_stats["total_execution_time"]
                / self.execution_stats["total_queries"]
            )

            if debug_info is not None:
                debug_info["execution_time"] = execution_time
                debug_info["validation_result"] = is_valid
                workflow_plan.metadata["debug_info"] = debug_info

            logger.info(f"🎉 查询处理完成，耗时: {execution_time:.2f}秒")
            return workflow_plan

        except Exception as e:
            execution_time = time.time() - start_time
            self.execution_stats["failed_queries"] += 1
            logger.error(f"查询处理失败: {e}, 耗时: {execution_time:.2f}秒")

            # 返回错误工作流
            return self._create_error_workflow(user_query, str(e))

    def process_query_step_by_step(self, user_query: str) -> Dict[str, Any]:
        """
        分步执行查询处理，返回每步的详细结果

        Args:
            user_query: 用户查询

        Returns:
            Dict: 包含每步结果的字典
        """
        results = {
            "user_query": user_query,
            "timestamp": datetime.now().isoformat(),
            "steps": {},
        }

        try:
            # 第1步
            start_time = time.time()
            intent_analysis = self.intent_processor.process_intent(user_query)
            results["steps"]["step1_intent"] = {
                "result": intent_analysis.to_dict(),
                "execution_time": time.time() - start_time,
                "status": "success",
            }

            # 第2步
            start_time = time.time()
            expanded_query = self.query_expander.expand_query(intent_analysis)
            results["steps"]["step2_expansion"] = {
                "result": expanded_query,
                "execution_time": time.time() - start_time,
                "status": "success",
            }

            # 第3步
            start_time = time.time()
            knowledge_fragments = self.knowledge_retriever.retrieve_knowledge(
                expanded_query
            )
            results["steps"]["step3_retrieval"] = {
                "result": [frag.to_dict() for frag in knowledge_fragments],
                "execution_time": time.time() - start_time,
                "status": "success",
            }

            # 第4步
            start_time = time.time()
            context = self.context_builder.build_context(
                user_query, intent_analysis, knowledge_fragments
            )
            results["steps"]["step4_context"] = {
                "result": {
                    "context_length": len(context),
                    "context_preview": (
                        context[:200] + "..." if len(context) > 200 else context
                    ),
                },
                "execution_time": time.time() - start_time,
                "status": "success",
            }

            # 第5步
            start_time = time.time()
            workflow_plan = self.workflow_generator.generate_workflow(
                context, user_query, expanded_query, intent_analysis
            )
            results["steps"]["step5_generation"] = {
                "result": workflow_plan.to_dict(),
                "execution_time": time.time() - start_time,
                "status": "success",
            }

            results["overall_status"] = "success"
            results["final_workflow"] = workflow_plan

        except Exception as e:
            results["overall_status"] = "failed"
            results["error"] = str(e)
            logger.error(f"分步执行失败: {e}")

        return results

    def batch_process_queries(self, queries: List[str]) -> List[WorkflowPlan]:
        """
        批量处理查询

        Args:
            queries: 查询列表

        Returns:
            List[WorkflowPlan]: 工作流计划列表
        """
        logger.info(f"开始批量处理 {len(queries)} 个查询")
        results = []

        for i, query in enumerate(queries):
            logger.info(f"处理查询 {i+1}/{len(queries)}: {query}")
            try:
                workflow = self.process_query(query)
                results.append(workflow)
            except Exception as e:
                logger.error(f"查询 {i+1} 处理失败: {e}")
                error_workflow = self._create_error_workflow(query, str(e))
                results.append(error_workflow)

        logger.info(
            f"批量处理完成，成功: {len([r for r in results if not r.metadata.get('is_error')])}"
        )
        return results

    def _create_error_workflow(
        self, user_query: str, error_message: str
    ) -> WorkflowPlan:
        """创建错误工作流"""
        from .workflow_types import WorkflowStep, StepType
        import uuid

        error_step = WorkflowStep(
            step_id="error_step",
            name="错误处理",
            description=f"处理查询时发生错误: {error_message}",
            step_type=StepType.VALIDATION,
            tool_name=None,
            parameters={"error": error_message},
            dependencies=[],
            conditions={},
            retry_count=0,
            timeout=0,
        )

        return WorkflowPlan(
            plan_id=f"error_{uuid.uuid4().hex[:8]}",
            name="错误工作流",
            description="查询处理失败时的错误工作流",
            steps=[error_step],
            user_query=user_query,
            expanded_query="",
            context="",
            metadata={
                "is_error": True,
                "error_message": error_message,
                "timestamp": datetime.now().isoformat(),
            },
        )

    def get_execution_stats(self) -> Dict[str, Any]:
        """获取执行统计信息"""
        return self.execution_stats.copy()

    def get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        info = {
            "orchestrator_status": "initialized",
            "components": {
                "intent_processor": self.intent_processor is not None,
                "query_expander": self.query_expander is not None,
                "knowledge_retriever": self.knowledge_retriever is not None,
                "context_builder": self.context_builder is not None,
                "workflow_generator": self.workflow_generator is not None,
            },
            "llm_model": getattr(self.llm, "model", "unknown"),
            "tools_available": len(self.tools) if self.tools else 0,
            "debug_enabled": self.enable_debug,
            "stats": self.execution_stats,
        }

        # 添加知识检索器信息
        if self.knowledge_retriever:
            try:
                retriever_info = self.knowledge_retriever.get_system_info()
                info["knowledge_retriever_info"] = retriever_info
            except:
                pass

        return info

    def validate_components(self) -> Dict[str, bool]:
        """验证各组件状态"""
        validation = {}

        try:
            validation["intent_processor"] = self.intent_processor is not None
            validation["query_expander"] = self.query_expander is not None
            validation["knowledge_retriever"] = self.knowledge_retriever is not None
            validation["context_builder"] = self.context_builder is not None
            validation["workflow_generator"] = self.workflow_generator is not None
            validation["llm"] = self.llm is not None

            # 检查RAG系统
            if self.knowledge_retriever:
                validation["rag_system"] = (
                    self.knowledge_retriever.rag_system is not None
                )
            else:
                validation["rag_system"] = False

        except Exception as e:
            logger.error(f"组件验证失败: {e}")
            validation["validation_error"] = str(e)

        return validation

    def enable_debug_mode(self):
        """启用调试模式"""
        self.enable_debug = True
        logger.setLevel(logging.DEBUG)
        logger.info("调试模式已启用")

    def disable_debug_mode(self):
        """禁用调试模式"""
        self.enable_debug = False
        logger.setLevel(logging.INFO)
        logger.info("调试模式已禁用")

    def clear_stats(self):
        """清除统计信息"""
        self.execution_stats = {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "total_execution_time": 0.0,
            "avg_execution_time": 0.0,
        }
        logger.info("统计信息已清除")

    def export_workflow_to_langchain_format(
        self, workflow_plan: WorkflowPlan
    ) -> Dict[str, Any]:
        """
        将工作流导出为LangChain兼容格式

        Args:
            workflow_plan: 工作流计划

        Returns:
            Dict: LangChain兼容的工作流定义
        """
        langchain_format = {
            "workflow_id": workflow_plan.plan_id,
            "workflow_name": workflow_plan.name,
            "description": workflow_plan.description,
            "created_time": workflow_plan.created_time.isoformat(),
            "user_query": workflow_plan.user_query,
            "execution_plan": [],
        }

        for step in workflow_plan.steps:
            if step.step_type == StepType.TOOL_CALL and step.tool_name:
                langchain_step = {
                    "step_id": step.step_id,
                    "action": "tool_call",
                    "tool": step.tool_name,
                    "tool_input": step.parameters,
                    "dependencies": step.dependencies,
                    "retry_policy": {
                        "max_retries": step.retry_count,
                        "timeout": step.timeout,
                    },
                }
                langchain_format["execution_plan"].append(langchain_step)

        return langchain_format
