#!/usr/bin/env python3
"""
Author: zhuanglaihong
Date: 2025-01-20
Description: 智能体主程序 - 基于新版工作流的水文模型智能助手

新版特性：
- 集成新版工作流生成器 (CoT + RAG)
- 支持RAG系统开关控制
- 支持MCP工具和本地工具切换
- 路径规范化和参数验证
- 改进的错误处理和用户体验
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

    # 创建控制台处理器
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
    """水文智能体主接口 - 新版架构"""

    def __init__(
        self,
        model_name: str = "qwen3:8b",
        enable_debug: bool = False,
        enable_rag: bool = True,
        use_mcp_tools: bool = True,
    ):
        """
        初始化水文智能体

        Args:
            model_name: LLM模型名称
            enable_debug: 是否启用调试模式
            enable_rag: 是否启用RAG系统
            use_mcp_tools: 是否使用MCP工具（False则使用本地工具）
        """
        self.model_name = model_name
        self.enable_debug = enable_debug
        self.enable_rag = enable_rag
        self.use_mcp_tools = use_mcp_tools
        self.start_time = datetime.now()

        # 系统组件
        self.ollama_client = None
        self.rag_system = None
        self.workflow_generator = None
        self.mcp_tools = None
        self.local_tools = []

        # 系统状态
        self.system_ready = False
        self.system_checks = {
            "ollama_service": False,
            "model_available": False,
            "rag_system": False,
            "workflow_system": False,
            "tools_system": False,
        }

        # 会话状态
        self.session_history = []
        self.current_session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        logger.info(f"=== 水文智能体启动 (会话ID: {self.current_session_id}) ===")
        logger.info(
            f"配置: RAG={enable_rag}, MCP工具={use_mcp_tools}, 调试={enable_debug}"
        )

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
            print(
                f"🔧 配置: RAG系统={'启用' if self.enable_rag else '禁用'}, "
                f"工具类型={'MCP工具' if self.use_mcp_tools else '本地工具'}"
            )
            print()

            # 1. 检查Ollama服务
            print("🔍 检查系统组件...")
            if not await self._check_ollama_service():
                return False

            # 2. 初始化RAG系统（可选）
            if self.enable_rag:
                rag_success = await self._initialize_rag_system()
                if not rag_success:
                    logger.warning("RAG系统初始化失败，将禁用RAG功能")
                    self.enable_rag = False
            else:
                print("   📚 RAG系统已禁用")

            # 3. 初始化工作流生成器
            if not await self._initialize_workflow_generator():
                return False

            # 4. 初始化工具系统
            if not await self._initialize_tools():
                return False

            # 5. 最终系统检查
            print("\n🔍 执行系统就绪性检查...")
            self.system_ready = await self._validate_system_readiness()

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

            import ollama

            self.ollama_client = ollama.Client()

            # 测试qwen3:8b模型
            response = self.ollama_client.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": "test connection"}],
            )

            if response and response.get("message"):
                print(f"   ✅ Ollama服务正常，模型 {self.model_name} 可用")
                self.system_checks["ollama_service"] = True
                self.system_checks["model_available"] = True
                return True
            else:
                logger.error(f"模型 {self.model_name} 响应异常")
                print(f"   ❌ 模型 {self.model_name} 响应异常")
                return False

        except ImportError:
            logger.error("ollama库未安装")
            print("   ❌ ollama库未安装")
            print("   💡 请安装: pip install ollama")
            return False
        except Exception as e:
            logger.error(f"Ollama服务检查失败: {e}")
            print(f"   ❌ Ollama服务检查失败: {e}")
            print("   💡 请检查:")
            print("      1. Ollama服务是否启动: ollama serve")
            print(f"      2. 模型是否已下载: ollama pull {self.model_name}")
            return False

    async def _initialize_rag_system(self) -> bool:
        """初始化RAG系统"""
        try:
            logger.info("初始化RAG系统...")
            print("   📚 初始化RAG系统...")

            from hydrorag import RAGSystem

            self.rag_system = RAGSystem()

            # 首先检查RAG系统核心组件是否初始化成功
            if not self.rag_system.is_initialized:
                error_msgs = self.rag_system.initialization_errors
                logger.error(f"RAG系统核心组件初始化失败: {error_msgs}")
                print(f"   ❌ RAG系统核心组件初始化失败")
                for error in error_msgs:
                    print(f"      - {error}")
                return False

            # 设置知识库
            doc_path = repo_path / "documents"
            if doc_path.exists():
                logger.info("正在设置知识库...")
                setup_result = self.rag_system.setup_from_raw_documents()

                if setup_result.get("status") == "success":
                    self.system_checks["rag_system"] = True
                    print("   ✅ RAG系统初始化成功")
                    logger.info("RAG系统初始化成功")
                    return True
                else:
                    logger.error(f"知识库设置失败: {setup_result}")
                    print(f"   ❌ 知识库设置失败")
                    return False
            else:
                logger.warning("未找到documents文件夹")
                print("   ⚠️  未找到documents文件夹，RAG系统将无法使用")
                return False

        except Exception as e:
            logger.error(f"RAG系统初始化失败: {e}")
            print(f"   ❌ RAG系统初始化失败: {e}")
            return False

    async def _initialize_workflow_generator(self) -> bool:
        """初始化工作流生成器"""
        try:
            logger.info("初始化工作流生成器...")
            print("   ⚙️  初始化工作流生成器...")

            from workflow import create_workflow_generator, GenerationConfig

            config = GenerationConfig(
                llm_model=self.model_name,
                enable_validation=True,
                enable_feedback_learning=False,
                rag_retrieval_k=8,  # 增加检索数量
                rag_score_threshold=0.2,  # 降低阈值以获取更多相关知识
            )

            self.workflow_generator = create_workflow_generator(
                rag_system=self.rag_system if self.enable_rag else None,
                ollama_client=self.ollama_client,
                config=config,
            )

            if self.workflow_generator:
                print("   ✅ 工作流生成器初始化成功")
                logger.info("工作流生成器初始化成功")
                return True
            else:
                logger.error("工作流生成器创建失败")
                print("   ❌ 工作流生成器创建失败")
                return False

        except Exception as e:
            logger.error(f"工作流生成器初始化失败: {e}")
            print(f"   ❌ 工作流生成器初始化失败: {e}")
            return False

    async def _initialize_tools(self) -> bool:
        """初始化工具系统"""
        try:
            if self.use_mcp_tools:
                logger.info("初始化MCP工具...")
                print("   🔌 初始化MCP工具...")

                from hydromcp.tools import HydroModelMCPTools

                self.mcp_tools = HydroModelMCPTools()

                if self.mcp_tools:
                    print("   ✅ MCP工具实例创建成功")
                    logger.info("MCP工具实例创建成功")
                    return True
                else:
                    logger.error("MCP工具实例创建失败")
                    print("   ❌ MCP工具实例创建失败")
                    return False
            else:
                logger.info("加载本地工具...")
                print("   🔧 加载本地工具...")

                from tool.langchain_tool import get_hydromodel_tools

                self.local_tools = get_hydromodel_tools()

                if self.local_tools and len(self.local_tools) > 0:
                    print(f"   ✅ 本地工具加载成功 (共{len(self.local_tools)}个工具)")
                    logger.info(f"本地工具加载成功: {len(self.local_tools)}个")
                    return True
                else:
                    logger.error("本地工具加载失败")
                    print("   ❌ 本地工具加载失败")
                    return False

        except Exception as e:
            logger.error(f"工具系统初始化失败: {e}")
            print(f"   ❌ 工具系统初始化失败: {e}")
            return False

    async def _validate_system_readiness(self) -> bool:
        """验证系统就绪状态"""
        try:
            # 1. 检查必需组件是否已初始化
            required_components = [
                "ollama_service",
                "model_available",
            ]

            missing_components = [
                comp
                for comp in required_components
                if not self.system_checks.get(comp, False)
            ]

            if missing_components:
                logger.error(f"缺少必需组件: {missing_components}")
                return False

            # 2. 检查工作流生成器是否已初始化
            if self.workflow_generator:
                self.system_checks["workflow_system"] = True
                print("   ✅ 工作流生成器就绪")
                logger.info("工作流生成器就绪")
            else:
                logger.error("工作流生成器未初始化")
                print("   ❌ 工作流生成器未初始化")
                return False

            # 3. 检查工具系统是否已初始化
            if self.use_mcp_tools and self.mcp_tools:
                self.system_checks["tools_system"] = True
                print("   ✅ MCP工具系统就绪")
                logger.info("MCP工具系统就绪")
            elif not self.use_mcp_tools and self.local_tools:
                if len(self.local_tools) > 0:
                    self.system_checks["tools_system"] = True
                    print(f"   ✅ 本地工具系统就绪 (共{len(self.local_tools)}个工具)")
                    logger.info(f"本地工具系统就绪: {len(self.local_tools)}个工具")
                else:
                    logger.error("本地工具列表为空")
                    print("   ❌ 本地工具列表为空")
                    return False
            else:
                logger.error("工具系统未初始化")
                print("   ❌ 工具系统未初始化")
                return False

            # 4. 检查RAG系统（如果启用）
            if self.enable_rag:
                if not self.system_checks.get("rag_system", False):
                    logger.warning("RAG系统未就绪，将以基础模式运行")
                    print("   ⚠️  RAG系统未就绪，将以基础模式运行")

            return True

        except Exception as e:
            logger.error(f"系统就绪性验证失败: {e}")
            print(f"   ❌ 系统就绪性验证失败: {e}")
            return False

    def _print_system_status(self):
        """打印系统状态"""
        print("\n📊 系统组件状态:")
        status_items = [
            ("Ollama服务", self.system_checks["ollama_service"]),
            ("模型可用", self.system_checks["model_available"]),
            (
                "RAG系统",
                self.system_checks["rag_system"] if self.enable_rag else "已禁用",
            ),
            ("工作流系统", self.system_checks["workflow_system"]),
            ("工具系统", self.system_checks["tools_system"]),
        ]

        for name, status in status_items:
            if status == "已禁用":
                icon = "⚪"
                print(f"   {icon} {name}: {status}")
            elif status:
                icon = "✅"
                print(f"   {icon} {name}")
            else:
                icon = "❌"
                print(f"   {icon} {name}")

        # 显示配置信息
        print(f"\n⚙️  系统配置:")
        print(f"   🤖 LLM模型: {self.model_name}")
        print(f"   📚 RAG系统: {'启用' if self.enable_rag else '禁用'}")
        print(f"   🔧 工具类型: {'MCP工具' if self.use_mcp_tools else '本地工具'}")
        print(f"   🐛 调试模式: {'启用' if self.enable_debug else '禁用'}")

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

            workflow = workflow_result["workflow"]

            # 2. 执行工作流
            print("\n⚡ 开始执行工作流...")
            execution_result = await self._execute_workflow(workflow, user_query)

            # 3. 生成回答
            print("\n📝 生成完整回答...")
            final_answer = await self._generate_final_answer(
                user_query, workflow, execution_result
            )

            # 4. 记录会话历史
            processing_time = time.time() - start_time
            session_record = {
                "query_id": query_id,
                "user_query": user_query,
                "workflow": (
                    workflow.to_dict()
                    if hasattr(workflow, "to_dict")
                    else str(workflow)
                ),
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
                "workflow": workflow,
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
            logger.info("开始工作流生成...")

            # 显示生成策略
            if self.enable_rag:
                print("   📚 使用RAG增强工作流生成...")
            else:
                print("   🔧 使用基础工作流生成...")

            # 生成工作流
            generation_result = self.workflow_generator.generate_workflow(user_query)

            if generation_result.success and generation_result.workflow:
                workflow = generation_result.workflow

                print(f"   ✅ 工作流生成成功")
                print(f"      工作流ID: {workflow.workflow_id}")
                print(f"      任务数量: {len(workflow.tasks)}")
                print(f"      生成时间: {generation_result.total_time:.2f}秒")

                # 显示任务详情
                print("   📋 任务列表:")
                for i, task in enumerate(workflow.tasks, 1):
                    print(f"      {i}. {task.name} (工具: {task.action})")

                return {"status": "success", "workflow": workflow}
            else:
                error_msg = generation_result.error_message or "工作流生成失败"
                logger.error(f"工作流生成失败: {error_msg}")
                print(f"   ❌ 工作流生成失败: {error_msg}")
                return {"status": "error", "error": error_msg}

        except Exception as e:
            logger.error(f"工作流生成异常: {e}")
            print(f"   ❌ 工作流生成异常: {e}")
            return {"status": "error", "error": str(e)}

    async def _execute_workflow(self, workflow, user_query: str) -> Dict[str, Any]:
        """执行工作流"""
        try:
            logger.info(f"开始执行工作流: {workflow.name}")

            # 显示执行计划
            print(f"📋 工作流: {workflow.name}")
            print(f"📝 描述: {workflow.description}")
            print("🔄 执行步骤:")
            for i, task in enumerate(workflow.tasks, 1):
                print(f"   {i}. {task.name}")
            print()

            execution_results = []
            successful_tasks = 0
            total_tasks = len(workflow.tasks)

            # 按执行顺序处理任务
            for order_group in workflow.execution_order:
                for task_id in order_group:
                    task = next(
                        (t for t in workflow.tasks if t.task_id == task_id), None
                    )
                    if not task:
                        continue

                    print(f"执行任务: {task.name} (工具: {task.action})")
                    task_start = time.time()

                    try:
                        # 根据工具类型执行任务
                        if self.use_mcp_tools:
                            result = await self._execute_mcp_task(task)
                        else:
                            result = await self._execute_local_task(task)

                        task_time = time.time() - task_start

                        task_result = {
                            "task_id": task.task_id,
                            "task_name": task.name,
                            "tool": task.action,
                            "success": result.get("success", False),
                            "time_taken": task_time,
                            "result": result,
                        }

                        if result.get("success"):
                            successful_tasks += 1
                            print(f"   ✅ 任务成功，耗时{task_time:.2f}秒")
                        else:
                            print(f"   ❌ 任务失败: {result.get('error', '未知错误')}")

                        execution_results.append(task_result)

                    except Exception as e:
                        task_time = time.time() - task_start
                        task_result = {
                            "task_id": task.task_id,
                            "task_name": task.name,
                            "tool": task.action,
                            "success": False,
                            "time_taken": task_time,
                            "error": str(e),
                        }
                        execution_results.append(task_result)
                        print(f"   ❌ 任务执行异常: {e}")

            # 生成执行摘要
            overall_success = successful_tasks > 0
            success_rate = successful_tasks / total_tasks if total_tasks > 0 else 0

            execution_summary = {
                "overall_success": overall_success,
                "total_tasks": total_tasks,
                "successful_tasks": successful_tasks,
                "failed_tasks": total_tasks - successful_tasks,
                "success_rate": success_rate,
                "task_results": execution_results,
            }

            print(f"\n📊 执行摘要:")
            print(f"   状态: {'✅ 成功' if overall_success else '❌ 失败'}")
            print(f"   成功率: {success_rate:.1%} ({successful_tasks}/{total_tasks})")

            return execution_summary

        except Exception as e:
            logger.error(f"工作流执行失败: {e}")
            print(f"   ❌ 工作流执行失败: {e}")
            return {
                "overall_success": False,
                "error": str(e),
                "total_tasks": len(workflow.tasks) if workflow else 0,
                "successful_tasks": 0,
                "failed_tasks": 1,
                "task_results": [],
            }

    async def _execute_mcp_task(self, task) -> Dict[str, Any]:
        """执行MCP任务"""
        try:
            # 调用对应的MCP工具
            if task.action == "get_model_params":
                result = self.mcp_tools.get_model_params(**task.parameters)
            elif task.action == "prepare_data":
                result = self.mcp_tools.prepare_data(**task.parameters)
            elif task.action == "calibrate_model":
                result = self.mcp_tools.calibrate_model(**task.parameters)
            elif task.action == "evaluate_model":
                result = self.mcp_tools.evaluate_model(**task.parameters)
            else:
                result = {"success": False, "error": f"不支持的MCP工具: {task.action}"}

            return result

        except Exception as e:
            logger.error(f"MCP任务执行失败: {e}")
            return {"success": False, "error": f"MCP任务执行异常: {str(e)}"}

    async def _execute_local_task(self, task) -> Dict[str, Any]:
        """执行本地任务"""
        try:
            # 查找对应的本地工具
            tool = next((t for t in self.local_tools if t.name == task.action), None)

            if not tool:
                return {"success": False, "error": f"未找到本地工具: {task.action}"}

            # 执行本地工具
            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: tool.run(task.parameters)
            )

            return {
                "success": True,
                "result": result,
                "message": f"本地工具 {task.action} 执行成功",
            }

        except Exception as e:
            logger.error(f"本地任务执行失败: {e}")
            return {"success": False, "error": f"本地任务执行异常: {str(e)}"}

    async def _generate_final_answer(
        self, user_query: str, workflow, execution_result: Dict[str, Any]
    ) -> str:
        """生成最终回答"""
        try:
            logger.info("生成最终回答")

            # 构建详细的执行报告
            answer_parts = []

            # 1. 问题理解和工作流概述
            answer_parts.append(f"📋 **执行报告**")
            answer_parts.append(f"")
            answer_parts.append(
                f"根据您的查询「{user_query}」，我执行了以下水文模型工作流："
            )
            answer_parts.append(f"")
            answer_parts.append(f"🔧 **工作流名称**: {workflow.name}")
            answer_parts.append(f"📝 **工作流描述**: {workflow.description}")
            answer_parts.append(f"")

            # 2. 执行计划详情
            answer_parts.append(f"📋 **执行计划** ({len(workflow.tasks)} 个步骤):")
            for i, task in enumerate(workflow.tasks, 1):
                answer_parts.append(f"   {i}. {task.name} (工具: {task.action})")
                if task.description and task.description != task.name:
                    answer_parts.append(f"      描述: {task.description}")
            answer_parts.append(f"")

            # 3. 执行结果总览
            overall_success = execution_result.get("overall_success", False)
            total_tasks = execution_result.get("total_tasks", 0)
            successful_tasks = execution_result.get("successful_tasks", 0)
            failed_tasks = execution_result.get("failed_tasks", 0)

            status_icon = "✅" if overall_success else "❌"
            answer_parts.append(f"📊 **执行结果总览**:")
            answer_parts.append(
                f"   {status_icon} 整体状态: {'成功' if overall_success else '部分失败'}"
            )
            answer_parts.append(f"   📈 成功步骤: {successful_tasks}/{total_tasks}")
            if failed_tasks > 0:
                answer_parts.append(f"   ⚠️  失败步骤: {failed_tasks}")
            answer_parts.append(f"")

            # 4. 详细步骤执行结果
            task_results = execution_result.get("task_results", [])
            if task_results:
                answer_parts.append(f"🔍 **详细执行结果**:")
                answer_parts.append(f"")

                for task_result in task_results:
                    task_name = task_result.get("task_name", "未知步骤")
                    success = task_result.get("success", False)
                    result_data = task_result.get("result", {})
                    error_msg = task_result.get(
                        "error", "未知错误"
                    )  # 提前定义error_msg

                    step_icon = "✅" if success else "❌"
                    answer_parts.append(f"   {step_icon} **{task_name}**")

                    if success:
                        # 处理成功情况
                        if isinstance(result_data, dict):
                            message = result_data.get("message", "执行成功")
                            answer_parts.append(f"      ✅ 执行状态: 成功")
                            answer_parts.append(f"      📝 执行信息: {message}")
                        else:
                            answer_parts.append(f"      ✅ 步骤执行成功")
                    else:
                        # 处理失败情况
                        answer_parts.append(f"      ❌ 执行失败: {error_msg}")

                    answer_parts.append(f"")

            # 5. 关键发现和结论
            answer_parts.append(f"🎯 **关键发现**:")
            answer_parts.append(f"")

            if overall_success:
                if successful_tasks == total_tasks:
                    answer_parts.append(
                        f"   ✅ 所有{total_tasks}个步骤均成功执行，工作流完整完成"
                    )
                    answer_parts.append(f"   📊 数据处理和模型执行均正常，系统运行稳定")
                else:
                    answer_parts.append(
                        f"   ⚠️  {successful_tasks}个步骤成功，{failed_tasks}个步骤失败，部分完成"
                    )
                    answer_parts.append(f"   💡 建议检查失败步骤的具体原因并重新执行")
            else:
                answer_parts.append(
                    f"   ❌ 工作流执行遇到问题，已完成{successful_tasks}个步骤"
                )
                answer_parts.append(f"   🔧 建议检查数据输入、模型配置或系统环境")

            # 6. 用户建议
            answer_parts.append(f"")
            answer_parts.append(f"💡 **建议**:")
            if overall_success and successful_tasks == total_tasks:
                answer_parts.append(f"   - 工作流执行成功，您可以查看生成的结果文件")
                answer_parts.append(f"   - 如需进一步分析，可以尝试其他相关查询")
            elif successful_tasks > 0:
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
                user_query, workflow, execution_result
            )

    def _generate_fallback_answer(
        self, user_query: str, workflow, execution_result: Dict[str, Any]
    ) -> str:
        """生成备用回答"""
        overall_success = execution_result.get("overall_success", False)
        successful_tasks = execution_result.get("successful_tasks", 0)
        total_tasks = execution_result.get("total_tasks", 0)

        if overall_success:
            return f"""📋 执行报告

根据您的查询「{user_query}」，我成功执行了 {workflow.name} 工作流。

✅ 执行状态: 成功
📊 完成步骤: {successful_tasks}/{total_tasks}

🎯 关键结果:
- 所有{total_tasks}个工作流步骤均已成功执行
- 数据处理和模型计算正常完成
- 系统运行稳定，结果已生成

💡 建议:
- 您可以查看生成的结果文件
- 如需进一步分析，可以继续提出相关问题"""
        else:
            return f"""📋 执行报告

根据您的查询「{user_query}」，我执行了 {workflow.name} 工作流。

⚠️  执行状态: 部分完成
📊 完成步骤: {successful_tasks}/{total_tasks}

🔧 问题分析:
- 已成功完成 {successful_tasks} 个步骤
- {total_tasks - successful_tasks} 个步骤执行失败

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
            "enable_rag": self.enable_rag,
            "use_mcp_tools": self.use_mcp_tools,
            "tools_count": (
                len(self.local_tools) if not self.use_mcp_tools else "MCP工具"
            ),
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

            # 清理各种资源
            components_to_cleanup = [
                self.rag_system,
                self.workflow_generator,
                self.mcp_tools,
            ]

            for component in components_to_cleanup:
                if component and hasattr(component, "cleanup"):
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
║                          新版架构                            ║
║                                                              ║
║  🤖 基于CoT+RAG增强的智能工作流                               ║
║  🔧 专业水文模型工具集成                                       ║
║  ⚡ 自动模型率定与评估                                         ║
║  📊 智能结果分析与回答                                         ║
║  🎛️  灵活的系统配置选项                                        ║
╚══════════════════════════════════════════════════════════════╝
    """
    )


async def interactive_mode(agent: HydroIntelligentAgent, killer: GracefulKiller):
    """交互模式"""
    print("\n🎯 进入对话模式 (输入 'quit'、'exit' 或按 Ctrl+C 退出)")
    print("💡 支持的任务类型:")
    print("   - '整理camels_11532500流域数据，用其率定GR4J模型，并评估模型'")
    print("   - 'gr4j模型率定' - 自动率定GR4J模型")
    print("   - 'xaj模型评估' - 评估XAJ模型性能")
    print("   - '准备数据' - 数据预处理")
    print("   - '查看gr4j参数' - 查看模型参数信息")
    print("   - 'info' - 查看系统信息")
    print("   - 'history' - 查看会话历史")
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
                    print(
                        f"   系统状态: {'🟢 就绪' if info['system_ready'] else '🔴 未就绪'}"
                    )
                    print(
                        f"   RAG系统: {'✅ 启用' if info['enable_rag'] else '❌ 禁用'}"
                    )
                    print(
                        f"   工具类型: {'MCP工具' if info['use_mcp_tools'] else '本地工具'}"
                    )
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
    parser = argparse.ArgumentParser(description="智能水文模型助手 - 新版架构")
    parser.add_argument(
        "--model", "-m", type=str, default="qwen3:8b", help="指定LLM模型名称"
    )
    parser.add_argument("--debug", "-d", action="store_true", help="启用调试模式")
    parser.add_argument("--query", "-q", type=str, help="直接执行查询")
    parser.add_argument("--no-rag", action="store_true", help="禁用RAG系统")
    parser.add_argument(
        "--local-tools", action="store_true", help="使用本地工具而非MCP工具"
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
            enable_rag=not args.no_rag,  # 默认启用RAG，除非指定--no-rag
            use_mcp_tools=not args.local_tools,  # 默认使用MCP工具，除非指定--local-tools
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

        print("\n📚 更多帮助:")
        print("   - 使用帮助: python Agent.py --help")
        print("   - 查看日志: cat agent.log")
        print("   - 禁用RAG: python Agent.py --no-rag")
        print("   - 使用本地工具: python Agent.py --local-tools")

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
