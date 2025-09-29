#!/usr/bin/env python3
"""
Author: zhuanglaihong
Date: 2025-07-28 16:24:08
LastEditTime: 2025-07-28 16:24:08
Description: 智能体主界面 - 用户调用本地Ollama模型配合水文工具进行自动率定
FilePath: script/Agent.py
Copyright: Copyright (c) 2021-2024 zhuanglaihong. All rights reserved.
--- IGNORE ---
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


class HydroAgent:
    """水文智能体主接口 - 基于Builder+HydroRAG+Executor三层架构"""

    def __init__(
        self,
        reasoning_model: str = "qwen-turbo",
        enable_debug: bool = False,
        enable_rag: bool = True,
        mode: str = "auto",
    ):
        """
        初始化水文智能体

        Args:
            reasoning_model: 推理模型名称 (用于Builder阶段)
            enable_debug: 是否启用调试模式
            enable_rag: 是否启用RAG系统
            mode: 执行模式 ('auto'|'sequential'|'react')
        """
        self.reasoning_model = reasoning_model
        self.enable_debug = enable_debug
        self.enable_rag = enable_rag
        self.mode = mode
        self.start_time = datetime.now()

        # 三层系统组件
        self.builder = None  # Builder系统
        self.hydrorag = None  # HydroRAG系统
        self.executor = None  # Executor系统

        # 系统状态
        self.system_ready = False
        self.system_checks = {
            "api_models": False,
            "builder_system": False,
            "rag_system": False,
            "executor_system": False,
        }

        # 会话状态
        self.session_history = []
        self.current_session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        logger.info(f"=== HydroAgent启动 (会话ID: {self.current_session_id}) ===")
        logger.info(
            f"配置: 推理模型={reasoning_model}, RAG={enable_rag}, 模式={mode}, 调试={enable_debug}"
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
                f"🔧 配置: HydroRAG系统={'启用' if self.enable_rag else '禁用'}, "
                f"执行模式={self.mode}"
            )
            print()

            # 1. 检查API模型可用性
            print("🔍 检查系统组件...")
            if not await self._check_api_models():
                return False

            # 2. 初始化HydroRAG系统（可选）
            if self.enable_rag:
                rag_success = await self._initialize_hydrorag_system()
                if not rag_success:
                    logger.warning("HydroRAG系统初始化失败，将禁用RAG功能")
                    self.enable_rag = False
            else:
                print("   📚 HydroRAG系统已禁用")

            # 3. 初始化Builder系统
            if not await self._initialize_builder_system():
                return False

            # 4. 初始化Executor系统
            if not await self._initialize_executor_system():
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

    async def _check_api_models(self) -> bool:
        """检查API模型可用性"""
        try:
            logger.info("检查API模型配置...")
            print("   🤖 检查API模型配置...")

            # 导入配置
            import config

            # 检查API Key配置
            try:
                import definitions_private
                api_key = getattr(definitions_private, 'OPENAI_API_KEY', None)
                base_url = getattr(definitions_private, 'OPENAI_BASE_URL', None)
            except ImportError:
                logger.warning("未找到definitions_private.py，将使用环境变量")
                api_key = os.getenv('OPENAI_API_KEY')
                base_url = os.getenv('OPENAI_BASE_URL')

            if api_key and api_key != 'your-api-key':
                print(f"   ✅ API密钥已配置")
                print(f"   🌐 API地址: {base_url or 'default'}")
                print(f"   🧠 推理模型: {config.REASONING_API_MODEL}")
                print(f"   💻 代码模型: {config.CODER_API_MODEL}")
                print(f"   📝 嵌入模型: {config.EMBEDDING_API_MODEL}")
                self.system_checks["api_models"] = True
                return True
            else:
                print("   ⚠️  API密钥未正确配置，将使用本地模型降级")
                logger.warning("API密钥未配置，将使用本地模型")
                # 可以选择继续使用本地模型
                self.system_checks["api_models"] = True
                return True

        except Exception as e:
            logger.error(f"API模型检查失败: {e}")
            print(f"   ❌ API模型检查失败: {e}")
            print("   💡 请检查:")
            print("      1. definitions_private.py是否正确配置")
            print("      2. API密钥是否有效")
            print("      3. 网络连接是否正常")
            return False

    async def _initialize_hydrorag_system(self) -> bool:
        """初始化HydroRAG系统"""
        try:
            logger.info("初始化HydroRAG系统...")
            print("   📚 初始化HydroRAG系统...")

            from hydrorag import HydroRAG

            self.hydrorag = HydroRAG()

            # 检查HydroRAG系统核心组件是否初始化成功
            if not self.hydrorag.is_ready():
                error_msgs = self.hydrorag.get_errors()
                logger.error(f"HydroRAG系统核心组件初始化失败: {error_msgs}")
                print(f"   ❌ HydroRAG系统核心组件初始化失败")
                for error in error_msgs:
                    print(f"      - {error}")
                return False

            # 设置知识库
            doc_path = repo_path / "documents"
            if doc_path.exists():
                logger.info("正在设置知识库...")
                setup_result = await self.hydrorag.initialize_knowledge_base()

                if setup_result.get("success", False):
                    self.system_checks["rag_system"] = True
                    print("   ✅ HydroRAG系统初始化成功")
                    logger.info("HydroRAG系统初始化成功")
                    return True
                else:
                    logger.error(f"知识库设置失败: {setup_result}")
                    print(f"   ❌ 知识库设置失败")
                    return False
            else:
                logger.warning("未找到documents文件夹")
                print("   ⚠️  未找到documents文件夹，HydroRAG系统将无法使用")
                return False

        except Exception as e:
            logger.error(f"HydroRAG系统初始化失败: {e}")
            print(f"   ❌ HydroRAG系统初始化失败: {e}")
            return False

    async def _initialize_builder_system(self) -> bool:
        """初始化Builder系统"""
        try:
            logger.info("初始化Builder系统...")
            print("   🏗️  初始化Builder系统...")

            from builder import WorkflowBuilder

            self.builder = WorkflowBuilder(
                rag_system=self.hydrorag if self.enable_rag else None,
                enable_rag=self.enable_rag,
                use_api_llm=True  # 使用API优先模式
            )

            # 检查Builder就绪状态
            readiness = self.builder.check_readiness()
            if readiness["ready"]:
                self.system_checks["builder_system"] = True
                print("   ✅ Builder系统初始化成功")
                logger.info("Builder系统初始化成功")
                return True
            else:
                logger.error(f"Builder系统未就绪: {readiness['errors']}")
                print(f"   ❌ Builder系统未就绪")
                for error in readiness["errors"]:
                    print(f"      - {error}")
                return False

        except Exception as e:
            logger.error(f"Builder系统初始化失败: {e}")
            print(f"   ❌ Builder系统初始化失败: {e}")
            return False

    async def _initialize_executor_system(self) -> bool:
        """初始化Executor系统"""
        try:
            logger.info("初始化Executor系统...")
            print("   ⚡ 初始化Executor系统...")

            from executor.main import ExecutorEngine

            self.executor = ExecutorEngine(
                enable_debug=self.enable_debug
            )

            if self.executor:
                self.system_checks["executor_system"] = True
                print("   ✅ Executor系统初始化成功")
                logger.info("Executor系统初始化成功")
                return True
            else:
                logger.error("Executor系统创建失败")
                print("   ❌ Executor系统创建失败")
                return False

        except Exception as e:
            logger.error(f"Executor系统初始化失败: {e}")
            print(f"   ❌ Executor系统初始化失败: {e}")
            return False

    async def _validate_system_readiness(self) -> bool:
        """验证系统就绪状态"""
        try:
            # 1. 检查必需组件是否已初始化
            required_components = [
                "api_models",
                "builder_system",
                "executor_system",
            ]

            missing_components = [
                comp
                for comp in required_components
                if not self.system_checks.get(comp, False)
            ]

            if missing_components:
                logger.error(f"缺少必需组件: {missing_components}")
                return False

            # 2. 检查Builder系统是否已初始化
            if self.builder:
                print("   ✅ Builder系统就绪")
                logger.info("Builder系统就绪")
            else:
                logger.error("Builder系统未初始化")
                print("   ❌ Builder系统未初始化")
                return False

            # 3. 检查Executor系统是否已初始化
            if self.executor:
                print("   ✅ Executor系统就绪")
                logger.info("Executor系统就绪")
            else:
                logger.error("Executor系统未初始化")
                print("   ❌ Executor系统未初始化")
                return False

            # 4. 检查HydroRAG系统（如果启用）
            if self.enable_rag:
                if self.hydrorag and self.system_checks.get("rag_system", False):
                    print("   ✅ HydroRAG系统就绪")
                    logger.info("HydroRAG系统就绪")
                else:
                    logger.warning("HydroRAG系统未就绪，将以基础模式运行")
                    print("   ⚠️  HydroRAG系统未就绪，将以基础模式运行")

            return True

        except Exception as e:
            logger.error(f"系统就绪性验证失败: {e}")
            print(f"   ❌ 系统就绪性验证失败: {e}")
            return False

    def _print_system_status(self):
        """打印系统状态"""
        print("\n📊 系统组件状态:")
        status_items = [
            ("API模型", self.system_checks["api_models"]),
            ("Builder系统", self.system_checks["builder_system"]),
            (
                "HydroRAG系统",
                self.system_checks["rag_system"] if self.enable_rag else "已禁用",
            ),
            ("Executor系统", self.system_checks["executor_system"]),
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
        print(f"   🧠 推理模型: {self.reasoning_model}")
        print(f"   📚 HydroRAG系统: {'启用' if self.enable_rag else '禁用'}")
        print(f"   🔄 执行模式: {self.mode}")
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
            # 1. 使用Builder系统生成工作流
            print("🏗️  正在使用Builder系统生成工作流...")
            workflow_result = await self._build_workflow(user_query)

            if workflow_result["status"] != "success":
                return workflow_result

            workflow = workflow_result["workflow"]

            # 2. 使用Executor系统执行工作流
            print("\n⚡ 使用Executor系统执行工作流...")
            execution_result = await self._execute_workflow_with_executor(workflow, user_query)

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

    async def _build_workflow(self, user_query: str) -> Dict[str, Any]:
        """使用Builder系统生成工作流"""
        try:
            logger.info("开始Builder工作流生成...")

            # 显示生成策略
            if self.enable_rag:
                print("   📚 使用HydroRAG增强工作流生成...")
            else:
                print("   🔧 使用基础工作流生成...")

            # 使用Builder系统生成工作流
            build_result = self.builder.build_workflow(
                user_query,
                {"enable_rag": self.enable_rag, "mode": self.mode}
            )

            if build_result.success and build_result.workflow:
                workflow = build_result.workflow

                print(f"   ✅ 工作流构建成功")
                print(f"      工作流ID: {workflow.get('workflow_id', 'unknown')}")
                print(f"      名称: {workflow.get('name', 'Unknown Workflow')}")
                print(f"      任务数量: {len(workflow.get('tasks', []))}")
                print(f"      构建时间: {build_result.build_time:.2f}秒")

                # 显示任务详情
                print("   📋 任务列表:")
                tasks = workflow.get("tasks", [])
                for i, task in enumerate(tasks, 1):
                    task_name = task.get("name", f"Task {i}")
                    action = task.get("action", "unknown")
                    print(f"      {i}. {task_name} (动作: {action})")

                return {"status": "success", "workflow": workflow}
            else:
                error_msg = build_result.error_message or "工作流构建失败"
                logger.error(f"工作流构建失败: {error_msg}")
                print(f"   ❌ 工作流构建失败: {error_msg}")
                return {"status": "error", "error": error_msg}

        except Exception as e:
            logger.error(f"Builder工作流生成异常: {e}")
            print(f"   ❌ Builder工作流生成异常: {e}")
            return {"status": "error", "error": str(e)}

    async def _execute_workflow_with_executor(self, workflow, user_query: str) -> Dict[str, Any]:
        """使用Executor系统执行工作流"""
        try:
            workflow_name = workflow.get("name", "Unknown Workflow")
            logger.info(f"开始使用Executor系统执行工作流: {workflow_name}")

            # 显示执行计划
            print(f"📋 工作流: {workflow_name}")
            print(f"📝 描述: {workflow.get('description', '无描述')}")
            tasks = workflow.get("tasks", [])
            print("🔄 执行步骤:")
            for i, task in enumerate(tasks, 1):
                task_name = task.get("name", f"Task {i}")
                print(f"   {i}. {task_name}")
            print()

            # 将workflow转换为JSON格式供Executor使用
            import json
            workflow_json = json.dumps(workflow, ensure_ascii=False, indent=2)

            # 根据模式选择执行方式
            execution_mode = self.mode if self.mode != "auto" else "sequential"
            print(f"🎯 执行模式: {execution_mode}")

            # 使用Executor系统执行
            execution_result = self.executor.execute_workflow(
                workflow_json,
                mode=execution_mode
            )

            # 处理执行结果
            if execution_result:
                print(f"\n📊 Executor执行摘要:")
                print(f"   执行ID: {execution_result.execution_id}")
                print(f"   状态: {execution_result.status}")
                print(f"   任务结果数: {len(execution_result.task_results)}")

                # 统计成功失败
                successful_tasks = sum(1 for tr in execution_result.task_results
                                     if tr.status.value == "completed")
                total_tasks = len(execution_result.task_results)
                failed_tasks = total_tasks - successful_tasks
                overall_success = successful_tasks > 0
                success_rate = successful_tasks / total_tasks if total_tasks > 0 else 0

                print(f"   成功率: {success_rate:.1%} ({successful_tasks}/{total_tasks})")

                # 转换为统一的执行摘要格式
                execution_summary = {
                    "overall_success": overall_success,
                    "total_tasks": total_tasks,
                    "successful_tasks": successful_tasks,
                    "failed_tasks": failed_tasks,
                    "success_rate": success_rate,
                    "execution_result": execution_result,
                    "task_results": [{
                        "task_id": tr.task_id,
                        "task_name": tr.task_id,  # Executor中的任务结构
                        "success": tr.status.value == "completed",
                        "result": tr.output if hasattr(tr, 'output') else None,
                        "error": tr.error if tr.error else None,
                        "time_taken": tr.execution_time if hasattr(tr, 'execution_time') else 0
                    } for tr in execution_result.task_results]
                }

                return execution_summary
            else:
                logger.error("Executor返回空结果")
                print(f"   ❌ Executor执行失败: 返回空结果")
                return {
                    "overall_success": False,
                    "error": "Executor返回空结果",
                    "total_tasks": len(tasks),
                    "successful_tasks": 0,
                    "failed_tasks": 1,
                    "task_results": [],
                }

        except Exception as e:
            logger.error(f"Executor工作流执行失败: {e}")
            print(f"   ❌ Executor工作流执行失败: {e}")
            return {
                "overall_success": False,
                "error": str(e),
                "total_tasks": len(workflow.get("tasks", [])) if workflow else 0,
                "successful_tasks": 0,
                "failed_tasks": 1,
                "task_results": [],
            }


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
            workflow_name = workflow.get("name", "Unknown Workflow")
            workflow_description = workflow.get("description", "无描述")
            tasks = workflow.get("tasks", [])

            answer_parts.append(f"🔧 **工作流名称**: {workflow_name}")
            answer_parts.append(f"📝 **工作流描述**: {workflow_description}")
            answer_parts.append(f"")

            # 2. 执行计划详情
            answer_parts.append(f"📋 **执行计划** ({len(tasks)} 个步骤):")
            for i, task in enumerate(tasks, 1):
                task_name = task.get("name", f"Task {i}")
                task_action = task.get("action", "unknown")
                answer_parts.append(f"   {i}. {task_name} (动作: {task_action})")
                task_description = task.get("description", "")
                if task_description and task_description != task_name:
                    answer_parts.append(f"      描述: {task_description}")
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
        workflow_name = workflow.get("name", "Unknown Workflow")

        if overall_success:
            return f"""📋 执行报告

根据您的查询「{user_query}」，我成功执行了 {workflow_name} 工作流。

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

根据您的查询「{user_query}」，我执行了 {workflow_name} 工作流。

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
            "reasoning_model": self.reasoning_model,
            "system_ready": self.system_ready,
            "system_checks": self.system_checks,
            "enable_rag": self.enable_rag,
            "execution_mode": self.mode,
            "builder_ready": self.builder is not None,
            "hydrorag_ready": self.hydrorag is not None,
            "executor_ready": self.executor is not None,
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

            # 清理三层架构组件
            components_to_cleanup = [
                self.builder,
                self.hydrorag,
                self.executor,
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


async def interactive_mode(agent: HydroAgent, killer: GracefulKiller):
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
                    print(f"   推理模型: {info['reasoning_model']}")
                    print(
                        f"   系统状态: {'🟢 就绪' if info['system_ready'] else '🔴 未就绪'}"
                    )
                    print(
                        f"   HydroRAG系统: {'✅ 启用' if info['enable_rag'] else '❌ 禁用'}"
                    )
                    print(f"   执行模式: {info['execution_mode']}")
                    print(f"   Builder系统: {'✅ 就绪' if info['builder_ready'] else '❌ 未就绪'}")
                    print(f"   HydroRAG: {'✅ 就绪' if info['hydrorag_ready'] else '❌ 未就绪'}")
                    print(f"   Executor系统: {'✅ 就绪' if info['executor_ready'] else '❌ 未就绪'}")
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
        "--model", "-m", type=str, default="qwen-turbo", help="指定推理模型名称"
    )
    parser.add_argument("--debug", "-d", action="store_true", help="启用调试模式")
    parser.add_argument("--query", "-q", type=str, help="直接执行查询")
    parser.add_argument("--no-rag", action="store_true", help="禁用HydroRAG系统")
    parser.add_argument(
        "--mode", type=str, choices=["auto", "sequential", "react"],
        default="auto", help="执行模式选择"
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
        agent = HydroAgent(
            reasoning_model=args.model,
            enable_debug=args.debug,
            enable_rag=not args.no_rag,  # 默认启用RAG，除非指定--no-rag
            mode=args.mode,  # 使用命令行指定的执行模式
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
