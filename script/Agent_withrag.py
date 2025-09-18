"""
Author: zhuanglaihong
Date: 2025-09-14
Description: 智能体主程序 - 基于工作流的水文模型智能助手
"""

import sys
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import argparse

# 添加项目根路径
repo_path = Path(os.path.abspath(__file__)).parent
sys.path.append(str(repo_path))

from langchain_ollama import ChatOllama
from workflow import (
    WorkflowOrchestrator,
    IntentProcessor,
    QueryExpander,
    ContextBuilder,
    WorkflowGenerator,
)
from workflow.workflow_types import WorkflowPlan
from workflow.rag_enhanced_agent import RAGEnhancedWorkflowManager
from tool.langchain_tool import get_hydromodel_tools
from hydromcp.agent_integration import MCPAgent, create_mcp_agent
from tool.ollama_config import ollama_config

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

logger = logging.getLogger(__name__)


class HydroAgent:
    """基于MCP工具的水文模型智能体"""

    def __init__(self, model_name: str = "qwen3:8b", enable_debug: bool = False, mcp_mode: str = "compatible", enable_rag: bool = True):
        """
        初始化智能体

        Args:
            model_name: LLM模型名称
            enable_debug: 是否启用调试模式
            mcp_mode: MCP工具执行模式，可选值：
                - "compatible": 兼容模式（默认），直接在本地执行工具
                - "service": 服务模式，通过独立的MCP服务器执行工具
            enable_rag: 是否启用RAG知识库功能
        """
        self.model_name = model_name
        self.enable_debug = enable_debug
        self.mcp_mode = mcp_mode
        self.enable_rag = enable_rag
        self.llm = None
        self.tools = []
        self.workflow_components = {}
        self.rag_workflow_manager = None
        self.mcp_agent = None
        self.session_history = []

        # 注意：_initialize_components 现在是异步的，需要在 main() 中调用

    def _check_prerequisites(self):
        """检查系统前置条件"""
        logger.debug("开始检查系统前置条件")
        
        # 1. 检查 Ollama 服务
        logger.debug("检查 Ollama 服务")
        if not ollama_config.check_service():
            logger.error("Ollama 服务未运行")
            raise RuntimeError("Ollama 服务不可用")
        
        logger.debug("Ollama 服务运行正常")
        
        # 2. 检查可用模型
        logger.debug("检查可用模型")
        available_models = ollama_config.get_available_models()
        if not available_models:
            logger.error("没有找到可用的模型")
            raise RuntimeError("没有可用的模型")
        
        logger.debug(f"找到 {len(available_models)} 个可用模型: {available_models}")
        
        # 3. 检查指定模型是否存在
        if self.model_name not in available_models:
            logger.warning(f"指定模型 {self.model_name} 不可用")
            # 尝试自动选择最佳模型
            best_model = ollama_config.select_best_model()
            if best_model:
                logger.info(f"自动选择最佳模型: {best_model}")
                self.model_name = best_model
            else:
                logger.error(f"无法找到合适的模型，可用模型: {available_models}")
                raise RuntimeError(f"模型 {self.model_name} 不可用")
        
        # 4. 检查模型是否支持工具调用
        if not ollama_config.is_tool_supported_model(self.model_name):
            logger.warning(f"模型 {self.model_name} 可能不支持工具调用")
            logger.info("推荐使用支持工具的模型: granite3-dense:8b")
            
        # 5. 检查水文模型工具
        logger.debug("检查水文模型工具")
        try:
            tools = get_hydromodel_tools()
            if not tools:
                logger.error("水文模型工具加载失败")
                raise RuntimeError("水文模型工具不可用")
            logger.debug(f"水文模型工具检查通过，共 {len(tools)} 个工具")
        except Exception as e:
            logger.error(f"水文模型工具检查失败: {e}")
            raise RuntimeError("水文模型工具不可用")
            
        logger.debug("所有前置条件检查通过")

    async def _initialize_components(self):
        """初始化所有组件"""
        try:
            logger.info("开始初始化水文模型智能体（MCP模式）")
            
            # 0. 检查前置条件
            self._check_prerequisites()
            
            # 1. 初始化LLM
            logger.debug("初始化语言模型")
            model_config = ollama_config.get_model_config(self.model_name)
            
            # 为工作流优化配置
            model_config.update({
                "temperature": 0.1,
                "top_p": 0.7,
                "num_ctx": 8192,
                "num_predict": 2048,
                "stop": ["</think>", "Human:", "Assistant:"],
                "format": "json",
            })
            
            self.llm = ChatOllama(
                model=self.model_name,
                **model_config
            )
            
            # 测试模型连接
            logger.debug("测试模型连接")
            if not ollama_config.test_model(self.model_name):
                logger.warning(f"模型 {self.model_name} 连接测试失败，但继续初始化")
            else:
                logger.debug("模型连接测试通过")

            # 2. 初始化传统工具（用于工作流生成）
            logger.debug("加载水文模型工具")
            self.tools = get_hydromodel_tools()
            
            logger.debug(f"成功加载 {len(self.tools)} 个工具")
            for tool in self.tools:
                logger.debug(f"工具: {tool.name} - {tool.description}")

            # 3. 初始化RAG增强工作流管理器
            logger.debug("初始化RAG增强工作流管理器")
            self.rag_workflow_manager = RAGEnhancedWorkflowManager(
                llm=self.llm,
                enable_rag=self.enable_rag
            )
            await self.rag_workflow_manager.initialize()
            
            # 4. 初始化传统工作流组件（备用）
            logger.debug("初始化传统工作流组件")
            self.workflow_components = {
                "intent_processor": IntentProcessor(self.llm),
                "query_expander": QueryExpander(self.llm),
                "context_builder": ContextBuilder(),
                "workflow_generator": WorkflowGenerator(self.llm),
                "orchestrator": WorkflowOrchestrator(
                    llm=self.llm,
                    tools=self.tools,
                    enable_debug=self.enable_debug,
                ),
            }

            # 5. 初始化MCP Agent（用于执行）
            logger.debug(f"初始化MCP Agent (模式: {self.mcp_mode})")
            
            if self.mcp_mode == "service":
                # 服务模式：通过独立的MCP服务器执行工具
                server_command = ["python", "-m", "hydromcp.server"]
                logger.info("使用MCP服务模式，需要先启动服务器: python -m hydromcp.server")
            else:
                # 兼容模式：直接在本地执行工具
                server_command = None
                logger.info("使用MCP兼容模式，直接执行工具")
            
            self.mcp_agent = MCPAgent(
                llm_model=self.model_name,
                enable_workflow=True,
                enable_debug=self.enable_debug
            )
            
            # 设置MCP Agent
            setup_success = await self.mcp_agent.setup()
            if not setup_success:
                raise RuntimeError("MCP Agent设置失败")

            logger.info("智能体初始化完成")

        except Exception as e:
            logger.error(f"智能体初始化失败: {e}")
            raise

    async def _generate_workflow(self, query: str) -> WorkflowPlan:
        """生成工作流（优先使用RAG增强）"""
        try:
            logger.debug("开始生成工作流")
            
            # 优先使用RAG增强工作流管理器
            if self.rag_workflow_manager and self.rag_workflow_manager.is_initialized:
                logger.debug("使用RAG增强工作流生成")
                print("🧠 使用知识库增强工作流生成...")
                
                result = await self.rag_workflow_manager.generate_enhanced_workflow(
                    user_query=query,
                    use_knowledge=None,  # 自动决定是否使用知识库
                    knowledge_config=None
                )
                
                if result.get("status") == "success":
                    workflow_plan = result["workflow_plan"]
                    
                    # 确保工作流有必要的属性用于兼容性
                    if hasattr(workflow_plan, 'workflow_id') and not hasattr(workflow_plan, 'plan_id'):
                        workflow_plan.plan_id = workflow_plan.workflow_id
                    elif hasattr(workflow_plan, 'plan_id') and not hasattr(workflow_plan, 'workflow_id'):
                        workflow_plan.workflow_id = workflow_plan.plan_id
                    
                    # 显示知识增强信息
                    if result.get("knowledge_enhanced"):
                        fragments_count = len(result.get("knowledge_fragments", []))
                        print(f"   📚 检索到 {fragments_count} 个知识片段")
                        if result.get("knowledge_stats"):
                            stats = result["knowledge_stats"]
                            if "avg_score" in stats:
                                print(f"   📊 平均相关性得分: {stats['avg_score']:.3f}")
                    else:
                        print("   💡 使用基础工作流模式")
                    
                    logger.info(f"RAG增强工作流生成完成: {workflow_plan.name} ({len(workflow_plan.steps)} 个步骤)")
                    print("✅ RAG增强工作流生成完成")
                    return workflow_plan
                else:
                    logger.warning(f"RAG增强工作流生成失败: {result.get('error')}")
                    print("⚠️ RAG增强工作流生成失败，使用传统模式")
            
            # 回退到传统工作流生成
            logger.debug("使用传统工作流生成")
            print("⚙️ 使用传统工作流生成...")
            
            # 1. 意图处理
            logger.debug("处理用户意图")
            intent = self.workflow_components["intent_processor"].process_intent(query)
            logger.debug(f"任务类型: {intent.task_type}, 建议工具: {intent.suggested_tools}")

            # 2. 查询扩展
            logger.debug("扩展查询内容")
            expanded_query = self.workflow_components["query_expander"].expand_query(intent)
            logger.debug(f"扩展后的查询: {expanded_query}")

            # 3. 构建上下文
            logger.debug("构建执行上下文")
            context = self.workflow_components["context_builder"].build_context(
                user_query=query,
                intent_analysis=intent,
                knowledge_fragments=[],
            )

            # 4. 生成工作流
            logger.debug("生成执行工作流")
            workflow_plan = self.workflow_components["workflow_generator"].generate_workflow(
                context=context,
                user_query=query,
                expanded_query=expanded_query,
                intent_analysis=intent,
            )

            # 确保工作流有必要的属性用于兼容性
            if hasattr(workflow_plan, 'workflow_id') and not hasattr(workflow_plan, 'plan_id'):
                workflow_plan.plan_id = workflow_plan.workflow_id
            elif hasattr(workflow_plan, 'plan_id') and not hasattr(workflow_plan, 'workflow_id'):
                workflow_plan.workflow_id = workflow_plan.plan_id

            logger.info(f"传统工作流生成完成: {workflow_plan.name} ({len(workflow_plan.steps)} 个步骤)")
            print("✅ 传统工作流生成完成")
            
            return workflow_plan

        except Exception as e:
            logger.error(f"工作流生成失败: {e}")
            raise

    async def _execute_workflow(self, workflow_plan: WorkflowPlan, query: str) -> Dict[str, Any]:
        """执行工作流"""
        try:
            logger.debug("开始执行工作流")
            
            # 显示执行步骤
            print("\n📋 执行计划:")
            for i, step in enumerate(workflow_plan.steps, 1):
                print(f"   {i}. {step.name}")
            print()
            
            # 确保工作流对象有必要的属性用于兼容性
            # 检查是否使用新的workflow_id或旧的plan_id
            if not hasattr(workflow_plan, 'plan_id') and hasattr(workflow_plan, 'workflow_id'):
                # 为向后兼容，添加plan_id属性
                workflow_plan.plan_id = workflow_plan.workflow_id
            elif not hasattr(workflow_plan, 'workflow_id') and hasattr(workflow_plan, 'plan_id'):
                # 为向前兼容，添加workflow_id属性
                workflow_plan.workflow_id = workflow_plan.plan_id
            
            # 使用MCP Agent智能执行工作流
            logger.debug("开始MCP智能执行工作流步骤")
            execution_result = await self.mcp_agent._execute_workflow_intelligently(workflow_plan, query)
            logger.debug("工作流执行完成")
            
            return execution_result

        except Exception as e:
            logger.error(f"工作流执行失败: {e}")
            raise

    def _display_execution_progress(self, workflow_plan: WorkflowPlan):
        """显示执行进度"""
        print("\n📋 执行计划:")
        for i, step in enumerate(workflow_plan.steps, 1):
            print(f"   {i}. {step.name} ({step.tool_name})")

    def _display_execution_progress(self, step_name: str, current: int, total: int):
        """显示执行进度"""
        print(f"🔄 正在执行步骤 {current}/{total}: {step_name}")
    
    def _display_execution_results(self, execution_result: Dict[str, Any]):
        """显示MCP执行结果"""
        print(f"\n🎯 执行完成:")
        overall_success = execution_result.get('overall_success', False)
        print(f"   状态: {'✅ 成功' if overall_success else '❌ 失败'}")
        print(f"   总步骤数: {execution_result.get('total_steps', 0)}")
        print(f"   成功步骤: {execution_result.get('success_steps', 0)}")
        print(f"   失败步骤: {execution_result.get('failed_steps', 0)}")

        # 显示步骤执行详情
        step_results = execution_result.get('step_results', [])
        if step_results:
            print("\n📊 步骤执行详情:")
            
            # 收集成功和失败的步骤
            successful_steps = []
            failed_steps = []
            evaluation_metrics = {}
            
            for step_result in step_results:
                step_name = step_result.get('step_name', '未知步骤')
                success = step_result.get('success', False)
                result_data = step_result.get('result', {})
                
                if success:
                    # 分析结果类型
                    if isinstance(result_data, dict):
                        if 'result' in result_data and isinstance(result_data['result'], dict):
                            # 嵌套结果
                            inner_result = result_data['result']
                            if 'evl_info' in inner_result:
                                evaluation_metrics.update(inner_result['evl_info'])
                                successful_steps.append(f"✅ {step_name}: 模型评估完成")
                            elif 'param_names' in inner_result:
                                param_count = len(inner_result['param_names'])
                                successful_steps.append(f"✅ {step_name}: 获取到{param_count}个模型参数")
                            elif 'status' in inner_result and inner_result['status'] == 'success':
                                message = inner_result.get('message', '执行成功')
                                successful_steps.append(f"✅ {step_name}: {message}")
                            else:
                                successful_steps.append(f"✅ {step_name}: 执行完成")
                        elif 'demo_output' in result_data:
                            # Demo结果
                            successful_steps.append(f"✅ {step_name}: {result_data['demo_output']}")
                        else:
                            successful_steps.append(f"✅ {step_name}: 执行完成")
                    else:
                        successful_steps.append(f"✅ {step_name}: 执行完成")
                else:
                    error_msg = result_data.get('error', '未知错误')
                    failed_steps.append(f"❌ {step_name}: {error_msg}")
            
            # 显示成功步骤
            for step_msg in successful_steps:
                print(f"   {step_msg}")
            
            # 显示失败步骤
            for step_msg in failed_steps:
                print(f"   {step_msg}")
            
            # 显示评估指标
            if evaluation_metrics:
                print(f"\n📈 模型性能指标:")
                for metric_name, metric_value in evaluation_metrics.items():
                    print(f"   {metric_name}: {metric_value}")
        
        # 显示执行摘要
        execution_summary = execution_result.get('execution_summary', '')
        if execution_summary:
            print(f"\n📝 执行摘要:")
            print(f"   {execution_summary}")
        
        # 总结
        if overall_success:
            if execution_result.get('failed_steps', 0) == 0:
                print(f"\n🎉 任务执行成功！所有{execution_result.get('success_steps', 0)}个步骤均已完成。")
            else:
                print(f"\n⚠️ 任务部分完成。{execution_result.get('success_steps', 0)}个步骤成功，{execution_result.get('failed_steps', 0)}个步骤失败。")
        else:
            print(f"\n❌ 任务执行失败。")
            
        print("=" * 60)

    async def chat(self, query: str) -> Dict[str, Any]:
        """
        处理用户查询

        Args:
            query: 用户查询

        Returns:
            处理结果
        """
        try:
            print(f"\n👤 用户: {query}")
            print("=" * 60)

            # 生成工作流
            print("⚙️ 正在生成工作流计划...")
            workflow_plan = await self._generate_workflow(query)
            print("✅ 工作流计划生成完成")
            
            # 执行工作流（包含步骤进度显示）
            execution_result = await self._execute_workflow(workflow_plan, query)
            
            # 显示结果
            self._display_execution_results(execution_result)

            # 记录会话历史
            self.session_history.append({
                "query": query,
                "workflow_plan": workflow_plan,
                "execution_result": execution_result,
            })

            return {
                "status": "success",
                "workflow_plan": workflow_plan,
                "execution_result": execution_result,
            }

        except Exception as e:
            error_msg = f"处理失败: {str(e)}"
            logger.error(error_msg)
            print(f"\n❌ {error_msg}")
            return {
                "status": "error",
                "error": error_msg,
            }

    def get_session_info(self) -> Dict[str, Any]:
        """获取会话信息"""
        info = {
            "model_name": self.model_name,
            "tools_count": len(self.tools),
            "session_count": len(self.session_history),
            "rag_enabled": self.enable_rag,
            "tools": [
                {"name": tool.name, "description": tool.description}
                for tool in self.tools
            ],
        }
        
        # 添加RAG系统状态
        if self.rag_workflow_manager:
            rag_status = self.rag_workflow_manager.get_system_status()
            info["rag_system"] = {
                "initialized": rag_status["is_initialized"],
                "enabled": rag_status["rag_enabled"],
                "components": rag_status["components"],
                "documents_dir": rag_status["documents_directory"]
            }
        
        return info
        
    async def cleanup(self):
        """清理系统资源"""
        try:
            # 保存会话历史
            if self.session_history:
                logger.info(f"本次会话共有 {len(self.session_history)} 条对话记录")
                # TODO: 实现会话历史的持久化存储
                
            # 清理MCP Agent资源
            if self.mcp_agent:
                await self.mcp_agent.cleanup()
            
            # 清理RAG增强工作流管理器
            if self.rag_workflow_manager:
                await self.rag_workflow_manager.cleanup()
                
            # 清理工作流组件
            if self.workflow_components:
                # 清理各个组件
                for component_name, component in self.workflow_components.items():
                    if hasattr(component, 'cleanup') and callable(component.cleanup):
                        try:
                            if asyncio.iscoroutinefunction(component.cleanup):
                                await component.cleanup()
                            else:
                                component.cleanup()
                            logger.debug(f"组件 {component_name} 清理完成")
                        except Exception as e:
                            logger.warning(f"清理组件 {component_name} 时出错: {e}")
                
                self.workflow_components.clear()
            
            # 清理LLM资源
            if self.llm and hasattr(self.llm, 'cleanup'):
                try:
                    if asyncio.iscoroutinefunction(self.llm.cleanup):
                        await self.llm.cleanup()
                    else:
                        self.llm.cleanup()
                except Exception as e:
                    logger.warning(f"清理LLM资源时出错: {e}")
            
            # 清理其他资源
            self.tools.clear()
            self.llm = None
            
            logger.info("系统资源清理完成")
            return True
            
        except Exception as e:
            logger.error(f"清理系统资源时发生错误: {e}")
            return False


def print_banner():
    """打印欢迎横幅"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                    智能水文模型助手                           ║
║                 Intelligent Hydro Model Agent                ║
║                                                              ║
║  🤖 基于工作流的智能任务规划                                   ║
║  🔧 专业水文模型工具集成                                       ║
║  ⚡ 自动模型率定与评估                                         ║
║  📊 智能结果分析与可视化                                       ║
╚══════════════════════════════════════════════════════════════╝
    """)


async def interactive_mode(agent: HydroAgent):
    """交互模式"""
    print("\n🎯 进入对话模式 (输入 'quit' 或 'exit' 退出)")
    print("💡 支持的任务类型:")
    print("   - 'gr4j模型率定' - 自动率定GR4J模型")
    print("   - 'xaj模型评估' - 评估XAJ模型性能")
    print("   - '准备数据' - 数据预处理")
    print("   - '查看gr4j参数' - 查看模型参数信息")
    print("   - 'info' - 查看系统信息")
    print("🧠 RAG增强功能:")
    print("   - 自动从知识库检索相关信息")
    print("   - 基于专业文档生成优化工作流")
    print("   - 提供模型配置和参数建议")

    try:
        while True:
            try:
                user_input = input("\n👤 您: ").strip()

                if user_input.lower() in ["quit", "exit", "q"]:
                    print("👋 正在保存会话状态...")
                    break
                elif user_input.lower() == "info":
                    info = agent.get_session_info()
                    print(f"\n📊 系统信息:")
                    print(f"   模型: {info['model_name']}")
                    print(f"   工具数量: {info['tools_count']}")
                    print(f"   会话数量: {info['session_count']}")
                elif user_input:
                    await agent.chat(user_input)
                else:
                    print("请输入有效的查询内容")

            except KeyboardInterrupt:
                print("\n👋 正在保存会话状态...")
                break
            except Exception as e:
                logger.error(f"交互模式错误: {e}")
                print(f"❌ 错误: {e}")
                # 对于非致命错误，继续运行
                continue
    finally:
        # 在退出前执行清理操作
        print("🔄 正在清理资源...")
        try:
            if agent.mcp_agent:
                await agent.mcp_agent.cleanup()
            # 保存会话历史（如果需要）
            # TODO: 实现会话历史保存功能
            print("✅ 资源清理完成")
            print("👋 再见！")
        except Exception as e:
            logger.error(f"清理资源时发生错误: {e}")
            print("⚠️ 资源清理过程中出现问题")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="智能水文模型助手")
    parser.add_argument(
        "--model", "-m", 
        type=str, 
        default="qwen3:8b", 
        help="指定LLM模型名称"
    )
    parser.add_argument(
        "--debug", "-d", 
        action="store_true", 
        help="启用调试模式"
    )
    parser.add_argument(
        "--mcp-mode",
        type=str,
        choices=["compatible", "service"],
        default="compatible",
        help="MCP工具执行模式：compatible(默认)=兼容模式，service=服务模式"
    )
    parser.add_argument(
        "--enable-rag",
        action="store_true",
        default=True,
        help="启用RAG知识库功能（默认启用）"
    )
    parser.add_argument(
        "--disable-rag",
        action="store_true",
        help="禁用RAG知识库功能"
    )
    parser.add_argument(
        "--query", "-q", 
        type=str, 
        help="直接执行查询"
    )

    args = parser.parse_args()
    agent = None

    try:
        # 配置日志系统
        setup_logging(args.debug)
        logger.debug("启动智能水文模型助手")

        print_banner()

        # 设置工作目录
        project_root = Path(__file__).parent
        os.chdir(project_root)
        logger.debug(f"工作目录: {project_root}")

        # 确定RAG设置
        enable_rag = args.enable_rag and not args.disable_rag
        
        # 创建智能体
        agent = HydroAgent(
            model_name=args.model,
            enable_debug=args.debug,
            mcp_mode=args.mcp_mode,
            enable_rag=enable_rag
        )
        
        # 异步初始化
        await agent._initialize_components()

        # 显示系统信息
        info = agent.get_session_info()
        logger.info(f"系统就绪 - 模型: {info['model_name']}, 工具数量: {info['tools_count']}, RAG: {info['rag_enabled']}")
        print("✨ 智能水文模型助手已就绪")
        
        # 显示RAG状态
        if info.get('rag_enabled'):
            rag_info = info.get('rag_system', {})
            if rag_info.get('initialized'):
                print("📚 RAG知识库系统已启用")
            else:
                print("⚠️ RAG知识库系统启用失败，使用基础模式")
        else:
            print("💡 使用基础工作流模式（RAG未启用）")

        # 执行模式
        if args.query:
            # 单次查询模式
            await agent.chat(args.query)
        else:
            # 交互模式
            await interactive_mode(agent)

        return 0

    except KeyboardInterrupt:
        logger.info("接收到中断信号，正在优雅退出...")
        print("\n⌛ 正在保存状态并退出...")
        return 130  # 标准的SIGINT退出码
        
    except Exception as e:
        logger.error(f"启动失败: {e}")
        print(f"❌ 启动失败: {e}")
        print("\n💡 解决建议:")
        
        error_str = str(e).lower()
        
        if "ollama" in error_str or "服务" in error_str:
            print("🔧 Ollama 服务问题:")
            print("   1. 启动 Ollama 服务: ollama serve")
            print("   2. 检查 Ollama 是否正确安装")
            print("   3. 确认端口 11434 未被占用")
            
        elif "模型" in error_str or "model" in error_str:
            print("📦 模型问题:")
            print("   1. 下载推荐模型:")
            print("      ollama pull qwen2.5:7b")
            print("      ollama pull llama3:8b")
            print("      ollama pull granite3-dense:8b")
            print("   2. 查看已安装模型: ollama list")
            print("   3. 指定现有模型: python Agent.py -m <模型名>")
            
        elif "工具" in error_str or "tool" in error_str:
            print("🔧 水文模型工具问题:")
            print("   1. 检查 hydromodel 包是否安装")
            print("   2. 检查项目依赖: pip install -r requirements.txt")
            print("   3. 确认数据文件路径正确")
            
        else:
            print("🔧 通用解决方案:")
            print("   1. 检查 Ollama 服务: ollama serve")
            print("   2. 下载模型: ollama pull qwen2.5:7b")
            print("   3. 安装依赖: pip install -r requirements.txt")
            print("   4. 查看详细错误: python Agent.py --debug")
            
        print("\n📚 更多帮助:")
        print("   - Ollama 官网: https://ollama.ai/")
        print("   - 使用帮助: python Agent.py --help")
        
        return 1
        
    finally:
        # 确保在任何情况下都清理资源
        if agent:
            try:
                print("🔄 正在清理系统资源...")
                await agent.cleanup()
                print("✅ 资源清理完成")
            except Exception as e:
                logger.error(f"清理资源时发生错误: {e}")
                print("⚠️ 清理资源时出现问题，但程序仍将退出")

if __name__ == "__main__":
    import asyncio
    exit(asyncio.run(main()))
