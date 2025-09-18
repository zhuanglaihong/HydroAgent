"""
Author: zhuanglaihong
Date: 2025-09-18
Description: 智能体主程序 - 基于工作流的水文模型智能助手
"""

import sys
import os
import logging
import asyncio
import signal
from pathlib import Path
from typing import Dict, Any, Optional, List
import argparse
import time
from datetime import datetime
import json

# 添加项目根路径
repo_path = Path(os.path.abspath(__file__)).parent
sys.path.append(str(repo_path))


# 配置日志
def setup_logging(debug_mode: bool = False):
    """配置日志系统"""
    # 创建日志格式
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # 创建文件处理器
    file_handler = logging.FileHandler("agent.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG if debug_mode else logging.INFO)

    # 创建控制台处理器（仅在调试模式显示）
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.DEBUG if debug_mode else logging.WARNING)

    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    root_logger.handlers = []  # 清除现有处理器
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # 禁用第三方库的调试日志
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


logger = logging.getLogger(__name__)


class GracefulKiller:
    """退出处理器"""

    def __init__(self):
        self.kill_now = False
        self.cleanup_in_progress = False
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame):
        """处理信号"""
        signal_names = {signal.SIGINT: "SIGINT (Ctrl+C)", signal.SIGTERM: "SIGTERM"}
        signal_name = signal_names.get(signum, f"信号{signum}")

        if not self.cleanup_in_progress:
            print(f"\n🛑 接收到 {signal_name} 信号")
            print("⌛ 正在退出，请稍候...")
            logger.info(f"接收到 {signal_name} 信号，开始退出")
            self.kill_now = True
        else:
            print(f"\n⚠️  清理进行中，请稍候...")

    def start_cleanup(self):
        """开始清理过程"""
        self.cleanup_in_progress = True


class HydroIntelligentAgent:
    """水文智能体主接口"""

    def __init__(
        self,
        model_name: str = "qwen3:8b",
        enable_debug: bool = False,
        rebuild_vector_db: bool = False,
    ):
        """
        初始化水文智能体

        Args:
            model_name: LLM模型名称
            enable_debug: 是否启用调试模式
            rebuild_vector_db: 是否重建向量数据库
        """
        self.model_name = model_name
        self.enable_debug = enable_debug
        self.rebuild_vector_db = rebuild_vector_db
        self.start_time = datetime.now()

        # 系统组件
        self.llm = None
        self.rag_workflow_manager = None
        self.mcp_agent = None
        self.tools = []

        # 系统状态
        self.system_ready = False
        self.system_checks = {
            "ollama_service": False,
            "model_available": False,
            "rag_system": False,
            "workflow_system": False,
            "mcp_system": False,
            "tools_loaded": False,
        }

        # 会话状态
        self.session_history = []
        self.current_session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        logger.info(f"=== 水文智能体启动 (会话ID: {self.current_session_id}) ===")

    async def initialize(self) -> bool:
        """
        异步初始化所有系统组件

        Returns:
            bool: 初始化是否成功
        """
        try:
            logger.info("开始系统初始化检查...")
            print("🚀 水文智能体启动中...")
            print("=" * 60)

            # 1. 检查Ollama服务
            print("🔍 检查系统组件...")
            if not await self._check_ollama_service():
                return False

            # 2. 初始化LLM
            if not await self._initialize_llm():
                return False

            # 3. 加载工具
            if not await self._load_tools():
                return False

            # 4. 初始化RAG系统
            if not await self._initialize_rag_system():
                logger.warning("RAG系统初始化失败，将使用基础模式")

            # 5. 初始化工作流系统
            if not await self._initialize_workflow_system():
                return False

            # 6. 初始化MCP系统
            if not await self._initialize_mcp_system():
                return False

            # 7. 最终系统检查
            self.system_ready = self._validate_system_readiness()

            if self.system_ready:
                initialization_time = (datetime.now() - self.start_time).total_seconds()
                logger.info(f"系统初始化完成，耗时 {initialization_time:.2f} 秒")
                print(f"✅ 系统初始化完成 (耗时: {initialization_time:.2f}s)")
                self._print_system_status()
                return True
            else:
                logger.error("系统初始化失败")
                print("❌ 系统初始化失败")
                self._print_system_status()
                return False

        except Exception as e:
            logger.error(f"系统初始化异常: {e}")
            print(f"❌ 系统初始化异常: {e}")
            return False

    async def _check_ollama_service(self) -> bool:
        """检查Ollama服务"""
        try:
            logger.info("检查Ollama服务状态...")
            print("   🔧 检查Ollama服务...")

            from tool.ollama_config import ollama_config

            # 检查服务状态
            if not ollama_config.check_service():
                logger.error("Ollama服务未运行")
                print("   ❌ Ollama服务未运行")
                print("   💡 请运行: ollama serve")
                return False

            self.system_checks["ollama_service"] = True
            print("   ✅ Ollama服务正常")

            # 检查可用模型
            available_models = ollama_config.get_available_models()
            if not available_models:
                logger.error("没有可用的模型")
                print("   ❌ 没有可用的模型")
                return False

            # 检查指定模型
            if self.model_name not in available_models:
                logger.warning(f"指定模型 {self.model_name} 不可用")
                print(f"   ⚠️  指定模型 {self.model_name} 不可用")

                # 尝试选择最佳模型
                best_model = ollama_config.select_best_model()
                if best_model:
                    logger.info(f"自动选择模型: {best_model}")
                    print(f"   🔄 自动选择模型: {best_model}")
                    self.model_name = best_model
                else:
                    logger.error("无法找到合适的模型")
                    print("   ❌ 无法找到合适的模型")
                    return False

            self.system_checks["model_available"] = True
            print(f"   ✅ 模型可用: {self.model_name}")

            # 测试模型连接
            if ollama_config.test_model(self.model_name):
                print(f"   ✅ 模型连接测试通过")
            else:
                print(f"   ⚠️  模型连接测试失败，但继续初始化")

            return True

        except Exception as e:
            logger.error(f"Ollama服务检查失败: {e}")
            print(f"   ❌ Ollama服务检查失败: {e}")
            return False

    async def _initialize_llm(self) -> bool:
        """初始化语言模型"""
        try:
            logger.info("初始化语言模型...")
            print("   🧠 初始化语言模型...")

            from langchain_ollama import ChatOllama
            from tool.ollama_config import ollama_config

            # 获取模型配置
            model_config = ollama_config.get_model_config(self.model_name)

            # 优化配置
            model_config.update(
                {
                    "temperature": 0.1,
                    "top_p": 0.9,
                    "num_ctx": 8192,
                    "num_predict": 2048,
                    "stop": ["</think>", "Human:", "Assistant:"],
                }
            )

            self.llm = ChatOllama(model=self.model_name, **model_config)

            # 测试LLM
            test_response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.llm.invoke("测试连接，请回复'连接成功'")
            )

            if test_response and "成功" in str(test_response.content):
                print("   ✅ 语言模型初始化成功")
                logger.info("语言模型初始化成功")
                return True
            else:
                print("   ⚠️  语言模型响应异常，但继续初始化")
                logger.warning("语言模型响应异常")
                return True  # 仍然允许继续

        except Exception as e:
            logger.error(f"语言模型初始化失败: {e}")
            print(f"   ❌ 语言模型初始化失败: {e}")
            return False

    async def _load_tools(self) -> bool:
        """加载水文模型工具"""
        try:
            logger.info("加载水文模型工具...")
            print("   🔧 加载水文模型工具...")

            from tool.langchain_tool import get_hydromodel_tools

            self.tools = get_hydromodel_tools()

            if not self.tools:
                logger.error("工具加载失败")
                print("   ❌ 工具加载失败")
                return False

            self.system_checks["tools_loaded"] = True
            print(f"   ✅ 成功加载 {len(self.tools)} 个工具")

            if self.enable_debug:
                for tool in self.tools:
                    logger.debug(f"工具: {tool.name} - {tool.description}")

            return True

        except Exception as e:
            logger.error(f"工具加载失败: {e}")
            print(f"   ❌ 工具加载失败: {e}")
            return False

    async def _initialize_rag_system(self) -> bool:
        """初始化RAG系统"""
        try:
            logger.info("初始化RAG系统...")
            print("   📚 初始化RAG系统...")

            from workflow.rag_enhanced_agent import RAGEnhancedWorkflowManager

            # 创建RAG增强工作流管理器
            self.rag_workflow_manager = RAGEnhancedWorkflowManager(
                llm=self.llm, enable_rag=True, rebuild_vector_db=self.rebuild_vector_db
            )

            # 异步初始化
            await self.rag_workflow_manager.initialize()

            if self.rag_workflow_manager.is_initialized:
                self.system_checks["rag_system"] = True
                print("   ✅ RAG系统初始化成功")
                logger.info("RAG系统初始化成功")
                return True
            else:
                errors = self.rag_workflow_manager.initialization_errors
                logger.warning(f"RAG系统初始化部分失败: {errors}")
                print(f"   ⚠️  RAG系统初始化部分失败，将使用基础模式")
                return False

        except Exception as e:
            logger.error(f"RAG系统初始化失败: {e}")
            print(f"   ❌ RAG系统初始化失败: {e}")
            return False

    async def _initialize_workflow_system(self) -> bool:
        """初始化工作流系统"""
        try:
            logger.info("初始化工作流系统...")
            print("   ⚙️  初始化工作流系统...")

            # 检查RAG增强工作流管理器
            if self.rag_workflow_manager and self.rag_workflow_manager.is_initialized:
                self.system_checks["workflow_system"] = True
                print("   ✅ 工作流系统 (RAG增强模式)")
                return True

            # 如果RAG系统失败，尝试初始化基础工作流组件
            from workflow import (
                IntentProcessor,
                QueryExpander,
                ContextBuilder,
                WorkflowGenerator,
                WorkflowOrchestrator,
            )

            self.workflow_components = {
                "intent_processor": IntentProcessor(self.llm),
                "query_expander": QueryExpander(self.llm),
                "context_builder": ContextBuilder(),
                "workflow_generator": WorkflowGenerator(self.llm),
                "orchestrator": WorkflowOrchestrator(
                    llm=self.llm, tools=self.tools, enable_debug=self.enable_debug
                ),
            }

            self.system_checks["workflow_system"] = True
            print("   ✅ 工作流系统 (基础模式)")
            logger.info("工作流系统初始化成功 (基础模式)")
            return True

        except Exception as e:
            logger.error(f"工作流系统初始化失败: {e}")
            print(f"   ❌ 工作流系统初始化失败: {e}")
            return False

    async def _initialize_mcp_system(self) -> bool:
        """初始化MCP系统"""
        try:
            logger.info("初始化MCP系统...")
            print("   🔌 初始化MCP系统...")

            from hydromcp.agent_integration import MCPAgent

            self.mcp_agent = MCPAgent(
                llm_model=self.model_name,
                enable_workflow=True,
                enable_debug=self.enable_debug,
            )

            # 设置MCP Agent
            setup_success = await self.mcp_agent.setup()

            if setup_success:
                self.system_checks["mcp_system"] = True
                print("   ✅ MCP系统初始化成功")
                logger.info("MCP系统初始化成功")
                return True
            else:
                logger.error("MCP系统设置失败")
                print("   ❌ MCP系统设置失败")
                return False

        except Exception as e:
            logger.error(f"MCP系统初始化失败: {e}")
            print(f"   ❌ MCP系统初始化失败: {e}")
            return False

    def _validate_system_readiness(self) -> bool:
        """验证系统就绪状态"""
        required_components = [
            "ollama_service",
            "model_available",
            "workflow_system",
            "mcp_system",
            "tools_loaded",
        ]

        missing_components = [
            comp
            for comp in required_components
            if not self.system_checks.get(comp, False)
        ]

        if missing_components:
            logger.error(f"缺少必需组件: {missing_components}")
            return False

        return True

    def _print_system_status(self):
        """打印系统状态"""
        print("\n📊 系统组件状态:")
        status_items = [
            ("Ollama服务", self.system_checks["ollama_service"]),
            ("模型可用", self.system_checks["model_available"]),
            ("RAG系统", self.system_checks["rag_system"]),
            ("工作流系统", self.system_checks["workflow_system"]),
            ("MCP系统", self.system_checks["mcp_system"]),
            ("工具加载", self.system_checks["tools_loaded"]),
        ]

        for name, status in status_items:
            icon = "✅" if status else "❌"
            print(f"   {icon} {name}")

        # 显示RAG文档监控信息
        if self.rag_workflow_manager and self.system_checks["rag_system"]:
            if hasattr(self.rag_workflow_manager, "document_hashes"):
                doc_count = len(self.rag_workflow_manager.document_hashes)
                print(f"   📚 监控文档: {doc_count} 个文件")

                if self.rag_workflow_manager.last_document_check:
                    check_time = self.rag_workflow_manager.last_document_check.strftime(
                        "%H:%M:%S"
                    )
                    print(f"   🕐 最后检查: {check_time}")

                # 显示向量库模式
                rebuild_mode = "重建模式" if self.rebuild_vector_db else "保留模式"
                auto_update = (
                    "开启"
                    if self.rag_workflow_manager.rag_config.get(
                        "auto_update_vectordb", False
                    )
                    else "关闭"
                )
                print(f"   🔄 向量库: {rebuild_mode} (自动更新: {auto_update})")

        print(f"\n🎯 系统状态: {'🟢 就绪' if self.system_ready else '🔴 未就绪'}")
        print("=" * 60)

    async def process_query(self, user_query: str) -> Dict[str, Any]:
        """
        处理用户查询的完整流程

        Args:
            user_query: 用户输入的查询

        Returns:
            处理结果字典
        """
        if not self.system_ready:
            error_msg = "系统未就绪，无法处理查询"
            logger.error(error_msg)
            return {"status": "error", "error": error_msg}

        start_time = time.time()
        query_id = (
            f"query_{datetime.now().strftime('%H%M%S')}_{len(self.session_history)+1}"
        )

        logger.info(f"开始处理查询 [{query_id}]: {user_query}")
        print(f"\n👤 用户查询 [{query_id}]: {user_query}")
        print("=" * 80)

        try:
            # 1. 生成工作流
            print("🧠 正在生成智能工作流...")
            workflow_result = await self._generate_workflow(user_query)

            if workflow_result["status"] != "success":
                return workflow_result

            workflow_plan = workflow_result["workflow_plan"]

            # 2. 执行工作流
            print("\n⚡ 开始执行工作流...")
            execution_result = await self._execute_workflow(workflow_plan, user_query)

            # 3. 生成回答
            print("\n📝 生成完整回答...")
            final_answer = await self._generate_final_answer(
                user_query, workflow_plan, execution_result
            )

            # 4. 记录会话历史
            processing_time = time.time() - start_time
            session_record = {
                "query_id": query_id,
                "user_query": user_query,
                "workflow_plan": workflow_plan,
                "execution_result": execution_result,
                "final_answer": final_answer,
                "processing_time": processing_time,
                "timestamp": datetime.now().isoformat(),
            }

            self.session_history.append(session_record)

            logger.info(f"查询处理完成 [{query_id}]，耗时 {processing_time:.2f} 秒")

            # 5. 显示最终结果
            print(f"\n🎯 处理完成 (耗时: {processing_time:.2f}s)")
            print("=" * 80)
            print("🤖 智能体回答:")
            print(final_answer)
            print("=" * 80)

            return {
                "status": "success",
                "query_id": query_id,
                "workflow_plan": workflow_plan,
                "execution_result": execution_result,
                "final_answer": final_answer,
                "processing_time": processing_time,
            }

        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"查询处理失败: {str(e)}"

            logger.error(f"查询处理异常 [{query_id}]: {e}")
            print(f"\n❌ 处理失败 (耗时: {processing_time:.2f}s): {error_msg}")

            return {
                "status": "error",
                "query_id": query_id,
                "error": error_msg,
                "processing_time": processing_time,
            }

    async def _generate_workflow(self, user_query: str) -> Dict[str, Any]:
        """生成工作流"""
        try:
            # 优先使用RAG增强工作流管理器
            if (
                self.rag_workflow_manager
                and self.rag_workflow_manager.is_initialized
                and self.system_checks["rag_system"]
            ):
                logger.info("使用RAG增强工作流生成")
                print("   📚 使用知识库增强工作流生成...")

                result = await self.rag_workflow_manager.generate_enhanced_workflow(
                    user_query=user_query,
                    use_knowledge=None,  
                    knowledge_config=None,
                )

                if result.get("status") == "success":
                    workflow_plan = result["workflow_plan"]

                    # 确保兼容性
                    self._ensure_workflow_compatibility(workflow_plan)

                    # 显示增强信息
                    if result.get("knowledge_enhanced"):
                        fragments_count = len(result.get("knowledge_fragments", []))
                        print(f"   ✅ 检索到 {fragments_count} 个相关知识片段")
                        if result.get("knowledge_stats", {}).get("avg_score"):
                            avg_score = result["knowledge_stats"]["avg_score"]
                            print(f"   📊 平均相关性得分: {avg_score:.3f}")
                    else:
                        print("   💡 使用基础工作流模式")

                    print(
                        f"   ✅ 生成工作流: {workflow_plan.name} ({len(workflow_plan.steps)} 个步骤)"
                    )
                    return {"status": "success", "workflow_plan": workflow_plan}
                else:
                    logger.warning(f"RAG增强工作流生成失败: {result.get('error')}")
                    print("   ⚠️  RAG增强失败，尝试基础模式...")

            # 回退到传统工作流生成
            if hasattr(self, "workflow_components"):
                logger.info("使用传统工作流生成")
                print("   ⚙️  使用传统工作流生成...")

                # 意图处理
                intent = self.workflow_components["intent_processor"].process_intent(
                    user_query
                )

                # 查询扩展
                expanded_query = self.workflow_components["query_expander"].expand_query(
                    intent
                )

                # 构建上下文
                context = self.workflow_components["context_builder"].build_context(
                    user_query=user_query, intent_analysis=intent, knowledge_fragments=[]
                )

                # 生成工作流
                workflow_plan = self.workflow_components[
                    "workflow_generator"
                ].generate_workflow(
                    context=context,
                    user_query=user_query,
                    expanded_query=expanded_query,
                    intent_analysis=intent,
                )

                # 确保兼容性
                self._ensure_workflow_compatibility(workflow_plan)

            print(f"   ✅ 生成工作流: {workflow_plan.name} ({len(workflow_plan.steps)} 个步骤)")
            return {"status": "success", "workflow_plan": workflow_plan}

        except Exception as e:
            logger.error(f"工作流生成失败: {e}")
            return {"status": "error", "error": str(e)}

    def _ensure_workflow_compatibility(self, workflow_plan):
        """确保工作流对象兼容性"""
        if not hasattr(workflow_plan, "plan_id") and hasattr(
            workflow_plan, "workflow_id"
        ):
            workflow_plan.plan_id = workflow_plan.workflow_id
        elif not hasattr(workflow_plan, "workflow_id") and hasattr(
            workflow_plan, "plan_id"
        ):
            workflow_plan.workflow_id = workflow_plan.plan_id

    async def _execute_workflow(self, workflow_plan, user_query: str) -> Dict[str, Any]:
        """执行工作流"""
        try:
            logger.info(f"开始执行工作流: {workflow_plan.name}")

            # 显示执行计划
            print(f"📋 工作流: {workflow_plan.name}")
            print(f"📝 描述: {workflow_plan.description}")
            print("🔄 执行步骤:")
            for i, step in enumerate(workflow_plan.steps, 1):
                print(f"   {i}. {step.name}")
            print()

            # 使用MCP Agent执行
            execution_result = await self.mcp_agent._execute_workflow_intelligently(
                workflow_plan, user_query
            )

            # 显示执行结果
            self._display_execution_summary(execution_result)

            return execution_result

        except Exception as e:
            logger.error(f"工作流执行失败: {e}")
            print(f"   ❌ 工作流执行失败: {e}")
            return {
                "overall_success": False,
                "error": str(e),
                "total_steps": len(workflow_plan.steps) if workflow_plan else 0,
                "success_steps": 0,
                "failed_steps": 1,
            }

    def _display_execution_summary(self, execution_result: Dict[str, Any]):
        """显示执行摘要"""
        overall_success = execution_result.get("overall_success", False)
        total_steps = execution_result.get("total_steps", 0)
        success_steps = execution_result.get("success_steps", 0)
        failed_steps = execution_result.get("failed_steps", 0)

        print("📊 执行结果:")
        status_icon = "✅" if overall_success else "❌"
        print(f"   {status_icon} 状态: {'成功' if overall_success else '失败'}")
        print(f"   📈 步骤统计: {success_steps}/{total_steps} 成功")

        if failed_steps > 0:
            print(f"   ⚠️  失败步骤: {failed_steps}")

        # 显示详细步骤结果
        step_results = execution_result.get("step_results", [])
        if step_results:
            print("   📋 详细结果:")
            for step_result in step_results[:3]:  # 只显示前3个步骤
                step_name = step_result.get("step_name", "未知步骤")
                success = step_result.get("success", False)
                icon = "✅" if success else "❌"
                print(f"      {icon} {step_name}")

    async def _generate_final_answer(
        self, user_query: str, workflow_plan, execution_result: Dict[str, Any]
    ) -> str:
        """生成最终回答"""
        try:
            logger.info("生成最终回答")

            # 构建详细的执行报告
            answer_parts = []

            # 1. 问题理解和工作流概述
            answer_parts.append(f"📋 **执行报告**")
            answer_parts.append(f"")
            answer_parts.append(f"根据您的查询「{user_query}」，我执行了以下水文模型工作流：")
            answer_parts.append(f"")
            answer_parts.append(f"🔧 **工作流名称**: {workflow_plan.name}")
            answer_parts.append(f"📝 **工作流描述**: {workflow_plan.description}")
            answer_parts.append(f"")

            # 2. 执行计划详情
            answer_parts.append(f"📋 **执行计划** ({len(workflow_plan.steps)} 个步骤):")
            for i, step in enumerate(workflow_plan.steps, 1):
                step_tool = f" (工具: {step.tool_name})" if step.tool_name else ""
                answer_parts.append(f"   {i}. {step.name}{step_tool}")
                if step.description and step.description != step.name:
                    answer_parts.append(f"      描述: {step.description}")
            answer_parts.append(f"")

            # 3. 执行结果总览
            overall_success = execution_result.get("overall_success", False)
            total_steps = execution_result.get("total_steps", 0)
            success_steps = execution_result.get("success_steps", 0)
            failed_steps = execution_result.get("failed_steps", 0)

            status_icon = "✅" if overall_success else "❌"
            answer_parts.append(f"📊 **执行结果总览**:")
            answer_parts.append(
                f"   {status_icon} 整体状态: {'成功' if overall_success else '部分失败'}"
            )
            answer_parts.append(f"   📈 成功步骤: {success_steps}/{total_steps}")
            if failed_steps > 0:
                answer_parts.append(f"   ⚠️  失败步骤: {failed_steps}")
            answer_parts.append(f"")

            # 4. 详细步骤执行结果
            step_results = execution_result.get("step_results", [])
            if step_results:
                answer_parts.append(f"🔍 **详细执行结果**:")

            for step_result in step_results:
                step_name = step_result.get("step_name", "未知步骤")
                success = step_result.get("success", False)
                result_data = step_result.get("result", {})

                step_icon = "✅" if success else "❌"
                answer_parts.append(f"")
                answer_parts.append(f"   {step_icon} **{step_name}**")

                if success and result_data:
                    # 提取和展示具体结果
                    self._extract_step_details(result_data, answer_parts, step_name)
                else:
                    # 处理失败情况
                    error_msg = step_result.get("result", {}).get("error", "未知错误")
                    answer_parts.append(f"      ❌ 执行失败: {error_msg}")

                answer_parts.append(f"")

            # 5. 关键发现和结论
            answer_parts.append(f"🎯 **关键发现**:")

            # 分析执行结果并提供专业见解
            if overall_success:
                if success_steps == total_steps:
                    answer_parts.append(f"   ✅ 所有{total_steps}个步骤均成功执行，工作流完整完成")

                    # 查找具体的模型结果
                    model_results = self._extract_model_results(step_results)
                    if model_results:
                        answer_parts.extend(model_results)
                    else:
                        answer_parts.append(f"   📊 数据处理和模型执行均正常，系统运行稳定")
                else:
                    answer_parts.append(
                        f"   ⚠️  {success_steps}个步骤成功，{failed_steps}个步骤失败，部分完成"
                    )
                    answer_parts.append(f"   💡 建议检查失败步骤的具体原因并重新执行")
            else:
                answer_parts.append(f"   ❌ 工作流执行遇到问题，已完成{success_steps}个步骤")
                answer_parts.append(f"   🔧 建议检查数据输入、模型配置或系统环境")

            # 6. 用户建议
            answer_parts.append(f"")
            answer_parts.append(f"💡 **建议**:")
            if overall_success and success_steps == total_steps:
                answer_parts.append(f"   - 工作流执行成功，您可以查看生成的结果文件")
                answer_parts.append(f"   - 如需进一步分析，可以尝试其他相关查询")
            elif success_steps > 0:
                answer_parts.append(f"   - 部分步骤已成功，可以在此基础上继续操作")
                answer_parts.append(f"   - 检查失败步骤的错误信息，调整参数后重试")
            else:
                answer_parts.append(f"   - 检查系统配置和数据路径是否正确")
                answer_parts.append(f"   - 确认所需的数据文件是否存在")
                answer_parts.append(f"   - 查看详细日志以获取更多错误信息")

            final_answer = "\n".join(answer_parts)

            return final_answer

        except Exception as e:
            logger.error(f"生成最终回答失败: {e}")
            # 返回基础的结构化总结
            return self._generate_fallback_answer(
                user_query, workflow_plan, execution_result
            )

    def _extract_step_details(
        self, result_data: Dict, answer_parts: List[str], step_name: str
    ):
        """提取步骤执行的详细信息"""
        if isinstance(result_data, dict):
            # 处理MCP工具的直接返回结果
            if "success" in result_data:
                success = result_data.get("success", False)
                if success:
                    # 成功的MCP工具调用
                    message = result_data.get("message", "执行成功")
                    answer_parts.append(f"      ✅ 执行状态: 成功")
                    answer_parts.append(f"      📝 执行信息: {message}")

                    # 提取具体结果信息
                    if "率定" in step_name or "calibrat" in step_name.lower():
                        # 率定任务的特殊处理
                        self._extract_calibration_details(result_data, answer_parts)
                    elif "评估" in step_name or "evaluat" in step_name.lower():
                        # 评估任务的特殊处理
                        self._extract_evaluation_details(result_data, answer_parts)
                    elif "准备" in step_name or "prepar" in step_name.lower():
                        # 数据准备任务的特殊处理
                        self._extract_preparation_details(result_data, answer_parts)
                    elif "参数" in step_name or "param" in step_name.lower():
                        # 参数查询任务的特殊处理
                        self._extract_parameter_details(result_data, answer_parts)
                    else:
                        # 通用信息提取
                        self._extract_general_details(result_data, answer_parts)
                else:
                    # 失败的MCP工具调用
                    error = result_data.get("error", "未知错误")
                    answer_parts.append(f"      ❌ 执行失败: {error}")

                    # 如果有错误堆栈，显示简要信息
                    if "error_stack" in result_data:
                        answer_parts.append(f"      🔍 详细错误信息已记录到日志")

            # 处理嵌套结果（兼容旧格式）
            elif "result" in result_data:
                inner_result = result_data["result"]

            # 模型评估结果
            if isinstance(inner_result, dict) and "evl_info" in inner_result:
                evl_info = inner_result["evl_info"]
                answer_parts.append(f"      📊 模型评估指标:")
                for metric, value in evl_info.items():
                    if isinstance(value, (int, float)):
                        answer_parts.append(f"         - {metric}: {value:.4f}")
                    else:
                        answer_parts.append(f"         - {metric}: {value}")

            # 参数信息
            elif isinstance(inner_result, dict) and "param_names" in inner_result:
                param_count = len(inner_result["param_names"])
                answer_parts.append(f"      🔧 获取到 {param_count} 个模型参数:")
                for i, param in enumerate(inner_result["param_names"][:5], 1):  # 只显示前5个
                    answer_parts.append(f"         {i}. {param}")
                if param_count > 5:
                    answer_parts.append(f"         ... 还有 {param_count-5} 个参数")

                # 状态信息
                elif isinstance(inner_result, dict) and "status" in inner_result:
                    status = inner_result["status"]
                    message = inner_result.get("message", "执行完成")
                    answer_parts.append(f"      ✅ 状态: {status}")
                    answer_parts.append(f"      📝 信息: {message}")

                else:
                    answer_parts.append(f"      ✅ 执行成功，结果已生成")

            # Demo输出
            elif "demo_output" in result_data:
                demo_output = result_data["demo_output"]
                answer_parts.append(f"      📋 输出: {demo_output}")

            # 其他结果
            else:
                answer_parts.append(f"      ✅ 步骤执行成功")
        else:
            answer_parts.append(f"      ✅ 执行完成: {str(result_data)[:100]}...")

    def _extract_calibration_details(self, result_data: Dict, answer_parts: List[str]):
        """提取率定任务的详细信息"""
        # 率定结果目录
        if "result_dir" in result_data:
            result_dir = result_data["result_dir"]
            answer_parts.append(f"      📁 率定结果目录: {result_dir}")

        # 实验名称
        if "exp_name" in result_data:
            exp_name = result_data["exp_name"]
            answer_parts.append(f"      🔬 实验名称: {exp_name}")

        # 模型名称
        if "model_name" in result_data:
            model_name = result_data["model_name"]
            answer_parts.append(f"      🤖 模型类型: {model_name.upper()}")

        # 率定结果文件位置
        answer_parts.append(f"      💾 率定参数保存位置:")
        if "result_dir" in result_data:
            result_dir = result_data["result_dir"]
            answer_parts.append(f"         - 主结果目录: {result_dir}")
            answer_parts.append(f"         - 参数文件: {result_dir}/sceua_gr_model/")
            answer_parts.append(f"         - 配置文件: {result_dir}/config.yaml")

    def _extract_evaluation_details(self, result_data: Dict, answer_parts: List[str]):
        """提取评估任务的详细信息"""
        # 评估指标
        if "metrics" in result_data:
            metrics = result_data["metrics"]
            answer_parts.append(f"      📊 评估指标:")
            for metric_name, metric_value in metrics.items():
                try:
                    # 尝试转换为数值并格式化
                    value = float(metric_value)
                    answer_parts.append(f"         - {metric_name}: {value:.4f}")
                except (ValueError, TypeError):
                    answer_parts.append(f"         - {metric_name}: {metric_value}")

        # 模型和实验信息
        if "model_name" in result_data:
            model_name = result_data["model_name"]
            answer_parts.append(f"      🤖 评估模型: {model_name.upper()}")

        if "exp_name" in result_data:
            exp_name = result_data["exp_name"]
            answer_parts.append(f"      🔬 评估实验: {exp_name}")

        # 评估结果文件位置
        answer_parts.append(f"      💾 评估结果保存位置:")
        answer_parts.append(f"         - 指标文件: basins_metrics.csv")
        answer_parts.append(f"         - 模拟结果: *_evaluation_results.nc")

    def _extract_preparation_details(self, result_data: Dict, answer_parts: List[str]):
        """提取数据准备任务的详细信息"""
        # 数据目录
        if "data_dir" in result_data:
            data_dir = result_data["data_dir"]
            answer_parts.append(f"      📁 数据目录: {data_dir}")

        # 数据时间尺度
        if "data_scale" in result_data:
            data_scale = result_data["data_scale"]
            answer_parts.append(f"      ⏰ 时间尺度: {data_scale} (日尺度)")

        # 数据格式转换信息
        answer_parts.append(f"      🔄 数据处理:")
        answer_parts.append(f"         - 原始CSV数据已转换为NetCDF格式")
        answer_parts.append(f"         - 生成文件: attributes.nc, timeseries.nc")
        answer_parts.append(f"         - 数据已准备好用于模型训练和测试")

    def _extract_parameter_details(self, result_data: Dict, answer_parts: List[str]):
        """提取参数查询任务的详细信息"""
        # 参数名称和数量
        if "param_names" in result_data:
            param_names = result_data["param_names"]
            param_count = len(param_names)
            answer_parts.append(f"      🔧 模型参数详情:")
            answer_parts.append(f"         - 参数数量: {param_count}")
            answer_parts.append(f"         - 参数列表:")
            for i, param in enumerate(param_names, 1):
                answer_parts.append(f"           {i}. {param}")

        # 参数范围
        if "param_ranges" in result_data:
            param_ranges = result_data["param_ranges"]
            answer_parts.append(f"      📏 参数取值范围:")
            param_names = result_data.get("param_names", [])
            for i, (param_name, param_range) in enumerate(
                zip(param_names, param_ranges)
            ):
                if len(param_range) == 2:
                    answer_parts.append(
                        f"         - {param_name}: [{param_range[0]}, {param_range[1]}]"
                    )

        # 模型信息
        if "model_name" in result_data:
            model_name = result_data["model_name"]
            answer_parts.append(f"      🤖 模型类型: {model_name.upper()}")

    def _extract_general_details(self, result_data: Dict, answer_parts: List[str]):
        """提取通用任务信息"""
        # 提取其他有用的字段
        useful_fields = [
            ("model_name", "模型名称", "🤖"),
            ("exp_name", "实验名称", "🔬"),
            ("result_dir", "结果目录", "📁"),
            ("data_dir", "数据目录", "📁"),
            ("basin_id", "流域ID", "🏞️"),
            ("start_date", "开始日期", "📅"),
            ("end_date", "结束日期", "📅"),
        ]

        details_found = False
        for field, display_name, icon in useful_fields:
            if field in result_data:
                value = result_data[field]
                answer_parts.append(f"      {icon} {display_name}: {value}")
                details_found = True

        if not details_found:
            # 如果没有找到特殊字段，显示一般信息
            answer_parts.append(f"      ℹ️  任务执行完成，结果已保存")

    def _extract_model_results(self, step_results: List[Dict]) -> List[str]:
        """提取模型相关的关键结果"""
        insights = []

        calibration_completed = False
        evaluation_completed = False

        for step_result in step_results:
            if not step_result.get("success", False):
                continue

            result_data = step_result.get("result", {})
            step_name = step_result.get("step_name", "")

            # 处理MCP工具的直接返回结果
            if isinstance(result_data, dict):
                # 检查率定任务
                if (
                    "率定" in step_name or "calibrat" in step_name.lower()
                ) and result_data.get("success"):
                    calibration_completed = True
                    model_name = result_data.get("model_name", "模型")
                    result_dir = result_data.get("result_dir", "")
                    exp_name = result_data.get("exp_name", "")

                    insights.append(f"   🎯 {model_name.upper()}模型参数率定成功完成")
                    if result_dir:
                        insights.append(f"   📁 率定结果已保存至: {result_dir}")
                    if exp_name:
                        insights.append(f"   🔬 实验标识: {exp_name}")

                # 检查评估任务
                elif (
                    "评估" in step_name or "evaluat" in step_name.lower()
                ) and result_data.get("success"):
                    evaluation_completed = True

                    # 提取评估指标
                    if "metrics" in result_data:
                        metrics = result_data["metrics"]
                        for metric_name, metric_value in metrics.items():
                            value = float(metric_value)

                            # 分析R²指标
                            if "R2" in metric_name or "R²" in metric_name:
                                if value > 0.8:
                                    insights.append(
                                        f"   🌟 {metric_name}: {value:.4f} - 模型拟合度优秀"
                                    )
                                elif value > 0.6:
                                    insights.append(
                                        f"   📈 {metric_name}: {value:.4f} - 模型拟合度良好"
                                    )
                                elif value > 0.4:
                                    insights.append(
                                        f"   📊 {metric_name}: {value:.4f} - 模型拟合度一般"
                                    )
                                else:
                                    insights.append(
                                        f"   ⚠️ {metric_name}: {value:.4f} - 模型拟合度较差"
                                    )
                            else:
                                insights.append(f"   - {metric_name}: {value:.4f}")

        # 添加工作流总结
        if calibration_completed and evaluation_completed:
            insights.append(f"   ✅ 完整建模流程：参数率定 → 模型评估 已全部完成")
        elif calibration_completed:
            insights.append(f"   ✅ 参数率定完成，可进行后续模型评估")
        elif evaluation_completed:
            insights.append(f"   ✅ 模型评估完成，性能指标已计算")

        return insights

    def _generate_fallback_answer(
        self, user_query: str, workflow_plan, execution_result: Dict[str, Any]
    ) -> str:
        """生成备用回答"""
        overall_success = execution_result.get("overall_success", False)
        success_steps = execution_result.get("success_steps", 0)
        total_steps = execution_result.get("total_steps", 0)

        if overall_success:
            return f"""📋 执行报告

根据您的查询「{user_query}」，我成功执行了 {workflow_plan.name} 工作流。

✅ 执行状态: 成功
📊 完成步骤: {success_steps}/{total_steps}

🎯 关键结果:
- 所有{total_steps}个工作流步骤均已成功执行
- 数据处理和模型计算正常完成
- 系统运行稳定，结果已生成

💡 建议:
- 您可以查看生成的结果文件
- 如需进一步分析，可以继续提出相关问题"""
        else:
            return f"""📋 执行报告

根据您的查询「{user_query}」，我执行了 {workflow_plan.name} 工作流。

⚠️  执行状态: 部分完成
📊 完成步骤: {success_steps}/{total_steps}

🔧 问题分析:
- 已成功完成 {success_steps} 个步骤
- {total_steps - success_steps} 个步骤执行失败

💡 建议:
- 检查系统配置和数据路径
- 确认所需数据文件是否存在
- 查看详细日志获取错误信息
- 调整参数后重新尝试"""

    def get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        return {
            "session_id": self.current_session_id,
            "model_name": self.model_name,
            "system_ready": self.system_ready,
            "system_checks": self.system_checks,
            "tools_count": len(self.tools),
            "session_count": len(self.session_history),
            "uptime": (datetime.now() - self.start_time).total_seconds(),
        }

    def get_session_history(self) -> List[Dict[str, Any]]:
        """获取会话历史"""
        return self.session_history

    async def cleanup(self):
        """清理系统资源"""
        try:
            logger.info("开始清理系统资源...")

            # 清理MCP Agent
            if self.mcp_agent:
                await self.mcp_agent.cleanup()

            # 清理RAG工作流管理器
            if self.rag_workflow_manager:
                await self.rag_workflow_manager.cleanup()

            # 清理其他组件
            if hasattr(self, "workflow_components"):
                for component in self.workflow_components.values():
                    if hasattr(component, "cleanup"):
                        try:
                            if asyncio.iscoroutinefunction(component.cleanup):
                                await component.cleanup()
                            else:
                                component.cleanup()
                        except Exception as e:
                            logger.warning(f"清理组件时出错: {e}")

            logger.info("系统资源清理完成")
            return True

        except Exception as e:
            logger.error(f"清理系统资源时发生错误: {e}")
            return False


def print_banner():
    """打印欢迎横幅"""
    print(
        """
╔══════════════════════════════════════════════════════════════╗
║                    智能水文模型助手                           ║
║                 Intelligent Hydro Model Agent                ║
║                                                              ║
║  🤖 基于RAG增强的智能工作流                                   ║
║  🔧 专业水文模型工具集成                                       ║
║  ⚡ 自动模型率定与评估                                         ║
║  📊 智能结果分析与回答                                         ║
╚══════════════════════════════════════════════════════════════╝
    """
    )


async def interactive_mode(agent: HydroIntelligentAgent, killer: GracefulKiller):
    """交互模式"""
    print("\n🎯 进入对话模式 (输入 'quit'、'exit' 或按 Ctrl+C 退出)")
    print("💡 支持的任务类型:")
    print("   - 'gr4j模型率定' - 自动率定GR4J模型")
    print("   - 'xaj模型评估' - 评估XAJ模型性能")
    print("   - '准备数据' - 数据预处理")
    print("   - '查看gr4j参数' - 查看模型参数信息")
    print("   - 'info' - 查看系统信息")
    print("   - 'history' - 查看会话历史")
    print("   - 'check_docs' - 检查文档变更")
    print("   - 'reload_docs' - 强制重建向量库")
    print()

    try:
        while not killer.kill_now:
            try:
                # 使用非阻塞方式获取用户输入
                print("👤 您: ", end="", flush=True)

                # 检查是否需要退出
                if killer.kill_now:
                    print("\n")
                    break

                try:
                    # 使用异步方式处理输入
                    user_input = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: input().strip()
                    )
                except (EOFError, KeyboardInterrupt):
                    print("\n")
                    break

                # 再次检查退出信号
                if killer.kill_now:
                    break

                if user_input.lower() in ["quit", "exit", "q"]:
                    print("👋 正在保存会话状态...")
                    break
                elif user_input.lower() == "info":
                    info = agent.get_system_info()
                    print(f"\n📊 系统信息:")
                    print(f"   会话ID: {info['session_id']}")
                    print(f"   模型: {info['model_name']}")
                    print(f"   系统状态: {'🟢 就绪' if info['system_ready'] else '🔴 未就绪'}")
                    print(f"   工具数量: {info['tools_count']}")
                    print(f"   会话数量: {info['session_count']}")
                    print(f"   运行时间: {info['uptime']:.1f}秒")
                elif user_input.lower() == "history":
                    history = agent.get_session_history()
                    print(f"\n📚 会话历史 (共{len(history)}条):")
                    for i, record in enumerate(history[-5:], 1):  # 显示最近5条
                        print(
                            f"   {i}. [{record['query_id']}] {record['user_query'][:50]}..."
                        )
                elif user_input.lower() == "check_docs":
                    # 手动触发文档检查
                    if agent.rag_workflow_manager and agent.system_checks["rag_system"]:
                        print("\n🔍 手动检查文档变更...")
                        try:
                            await agent.rag_workflow_manager.check_documents_periodically()
                            print("✅ 文档检查完成")
                        except Exception as e:
                            print(f"❌ 文档检查失败: {e}")
                    else:
                        print("❌ RAG系统未初始化，无法检查文档")
                elif user_input.lower() == "reload_docs":
                    # 强制重建向量库
                    if agent.rag_workflow_manager and agent.system_checks["rag_system"]:
                        print("\n🔄 强制重建向量库...")
                        try:
                            # 先处理raw文档
                            await agent.rag_workflow_manager._process_raw_documents()
                            # 再重建向量库
                            await agent.rag_workflow_manager._rebuild_vector_database()
                            # 更新文档哈希
                            current_hashes = (
                                agent.rag_workflow_manager._calculate_document_hashes()
                            )
                            agent.rag_workflow_manager.document_hashes = current_hashes
                            agent.rag_workflow_manager._save_document_hashes()
                            print("✅ 向量库重建完成")
                        except Exception as e:
                            print(f"❌ 向量库重建失败: {e}")
                    else:
                        print("❌ RAG系统未初始化，无法重建向量库")
                elif user_input:
                    # 检查是否在处理过程中收到退出信号
                    if killer.kill_now:
                        print("⌛ 收到退出信号，跳过当前查询")
                        break

                    # 处理用户查询
                    await agent.process_query(user_input)

                    # 处理完成后再次检查退出信号
                    if killer.kill_now:
                        break
                else:
                    print("请输入有效的查询内容")

            except KeyboardInterrupt:
                # 这里不应该到达，因为信号处理器会设置kill_now
                print("\n👋 收到中断信号...")
                break
            except Exception as e:
                logger.error(f"交互模式错误: {e}")
                print(f"❌ 错误: {e}")

                # 如果是严重错误或收到退出信号，退出循环
                if killer.kill_now or "系统" in str(e):
                    break

                continue

    except Exception as e:
        logger.error(f"交互模式异常: {e}")
        print(f"❌ 交互模式异常: {e}")

    finally:
        # 开始清理过程
        killer.start_cleanup()
        print("🔄 正在清理资源...")

        try:
            await agent.cleanup()
            print("✅ 资源清理完成")
        except Exception as e:
            logger.error(f"资源清理异常: {e}")
            print(f"⚠️  资源清理时出现问题: {e}")

        print("👋 再见！")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="智能水文模型助手")
    parser.add_argument("--model", "-m", type=str, default="qwen3:8b", help="指定LLM模型名称")
    parser.add_argument("--debug", "-d", action="store_true", help="启用调试模式")
    parser.add_argument("--query", "-q", type=str, help="直接执行查询")
    parser.add_argument(
        "--rebuild-vector-db", "-r", action="store_true", help="强制重建向量数据库"
    )

    args = parser.parse_args()
    agent = None
    killer = GracefulKiller()  # 创建信号处理器

    try:
        # 配置日志系统
        setup_logging(args.debug)
        logger.info("=== 智能水文模型助手启动 ===")

        print_banner()

        # 设置工作目录
        project_root = Path(__file__).parent
        os.chdir(project_root)

        # 创建并初始化智能体
        agent = HydroIntelligentAgent(
            model_name=args.model,
            enable_debug=args.debug,
            rebuild_vector_db=args.rebuild_vector_db,
        )

        # 检查是否在初始化期间收到退出信号
        if killer.kill_now:
            print("⌛ 收到退出信号，取消初始化")
            return 130

        # 系统初始化
        if not await agent.initialize():
            print("\n❌ 系统初始化失败，无法启动")
            return 1

        # 再次检查退出信号
        if killer.kill_now:
            print("⌛ 收到退出信号，系统将退出")
            return 130

        # 执行模式
        if args.query:
            # 单次查询模式
            if killer.kill_now:
                print("⌛ 收到退出信号，跳过查询执行")
                return 130

            result = await agent.process_query(args.query)
            return 0 if result["status"] == "success" else 1
        else:
            # 交互模式
            await interactive_mode(agent, killer)
            return 130 if killer.kill_now else 0

    except KeyboardInterrupt:
        # 这里不应该到达，因为信号处理器会处理
        logger.info("接收到KeyboardInterrupt，正在退出...")
        print("\n⌛ 正在保存状态并退出...")
        return 130

    except Exception as e:
        logger.error(f"启动失败: {e}")
        print(f"❌ 启动失败: {e}")

        # 提供解决建议
        error_str = str(e).lower()
        print("\n💡 解决建议:")

        if "ollama" in error_str or "服务" in error_str:
            print("🔧 Ollama 服务问题:")
            print("   1. 启动 Ollama 服务: ollama serve")
            print("   2. 检查 Ollama 是否正确安装")
            print("   3. 确认端口 11434 未被占用")
        elif "模型" in error_str or "model" in error_str:
            print("📦 模型问题:")
            print("   1. 下载推荐模型: ollama pull qwen3:8b")
            print("   2. 查看已安装模型: ollama list")
            print("   3. 指定现有模型: python Agent.py -m <模型名>")
        else:
            print("🔧 通用解决方案:")
            print("   1. 检查 Ollama 服务: ollama serve")
            print("   2. 下载模型: ollama pull qwen3:8b")
            print("   3. 安装依赖: pip install -r requirements.txt")
            print("   4. 查看详细错误: python Agent.py --debug")
            print("   5. 重建向量库: python Agent.py --rebuild-vector-db")

        print("\n📚 更多帮助:")
        print("   - 使用帮助: python Agent.py --help")
        print("   - 查看日志: cat agent.log")

        return 1

    finally:
        # 确保清理资源
        if agent:
            try:
                killer.start_cleanup()
                await agent.cleanup()
                if killer.kill_now:
                    print("✅ 退出完成")
            except Exception as e:
                logger.error(f"清理资源时发生错误: {e}")
                if killer.kill_now:
                    print("⚠️  清理过程中出现问题，但已安全退出")


if __name__ == "__main__":
    exit(asyncio.run(main()))
