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
from tool.langchain_tool import get_hydromodel_tools
from tool.workflow_executor import WorkflowExecutor
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
    """基于工作流的水文模型智能体"""

    def __init__(self, model_name: str = "qwen3:8b", enable_debug: bool = False):
        """
        初始化智能体

        Args:
            model_name: LLM模型名称
            enable_debug: 是否启用调试模式
        """
        self.model_name = model_name
        self.enable_debug = enable_debug
        self.llm = None
        self.tools = []
        self.workflow_components = {}
        self.workflow_executor = None
        self.session_history = []

        # 初始化组件
        self._initialize_components()

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
            logger.info("推荐使用支持工具的模型: qwen2.5:7b, llama3:8b, granite3-dense:8b")
            
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

    def _initialize_components(self):
        """初始化所有组件"""
        try:
            logger.info("开始初始化水文模型智能体")
            
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

            # 2. 初始化工具
            logger.debug("加载水文模型工具")
            self.tools = get_hydromodel_tools()
            
            logger.debug(f"成功加载 {len(self.tools)} 个工具")
            for tool in self.tools:
                logger.debug(f"工具: {tool.name} - {tool.description}")

            # 3. 初始化工作流组件
            logger.debug("初始化工作流组件")
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

            # 4. 初始化工作流执行器
            logger.debug("初始化工作流执行器")
            self.workflow_executor = WorkflowExecutor(
                tools=self.tools, 
                enable_debug=self.enable_debug
            )

            logger.info("智能体初始化完成")

        except Exception as e:
            logger.error(f"智能体初始化失败: {e}")
            raise

    def _generate_workflow(self, query: str) -> WorkflowPlan:
        """生成工作流"""
        try:
            logger.debug("开始生成工作流")
            
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

            logger.info(f"工作流生成完成: {workflow_plan.name} ({len(workflow_plan.steps)} 个步骤)")
            print("⚙️ 工作流生成完成")
            
            return workflow_plan

        except Exception as e:
            logger.error(f"工作流生成失败: {e}")
            raise

    def _execute_workflow(self, workflow_plan: WorkflowPlan) -> Dict[str, Any]:
        """执行工作流"""
        try:
            logger.debug("开始执行工作流")
            
            # 验证工作流
            validation_result = self.workflow_executor.validate_workflow(workflow_plan)
            if not validation_result["is_valid"]:
                error_msg = "工作流验证失败:\n" + "\n".join(validation_result["errors"])
                logger.error(error_msg)
                raise ValueError(error_msg)

            logger.debug("工作流验证通过")
            
            # 显示执行步骤
            print("\n执行步骤:")
            for i, step in enumerate(workflow_plan.steps, 1):
                print(f"  {i}. {step.name}")
            print()
            
            # 执行工作流
            logger.debug("开始执行工作流步骤")
            execution_result = self.workflow_executor.execute_workflow(workflow_plan)
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

    def _display_execution_results(self, execution_result: Dict[str, Any]):
        """显示执行结果"""
        print(f"\n🎯 执行完成:")
        print(f"   状态: {'✅ 成功' if execution_result['status'] == 'completed' else '❌ 失败'}")
        print(f"   总耗时: {execution_result['total_time']:.2f}秒")
        print(f"   成功步骤: {execution_result['success_count']}")
        print(f"   失败步骤: {execution_result['failed_count']}")

        # 显示详细的执行结果
        if execution_result['success_count'] > 0:
            print("\n📊 执行结果:")
            
            # 收集所有成功步骤的结果
            step_results = []
            evaluation_results = {}
            
            for step_id, step_result in execution_result["steps"].items():
                if step_result['status'] == 'completed' and 'result' in step_result:
                    result = step_result['result']
                    step_name = step_result.get('step_name', step_id)
                    
                    if isinstance(result, dict):
                        # 评估结果
                        if 'evl_info' in result:
                            evaluation_results.update(result['evl_info'])
                            step_results.append(f"✅ {step_name}: 模型评估完成")
                        # 其他成功结果
                        elif 'status' in result and result['status'] == 'success':
                            message = result.get('message', '执行成功')
                            step_results.append(f"✅ {step_name}: {message}")
                        # 参数查询结果
                        elif 'param_names' in result:
                            param_count = len(result['param_names'])
                            step_results.append(f"✅ {step_name}: 获取到{param_count}个模型参数")
                        else:
                            step_results.append(f"✅ {step_name}: 执行完成")
                    elif isinstance(result, str):
                        step_results.append(f"✅ {step_name}: {result}")
                    else:
                        step_results.append(f"✅ {step_name}: 执行完成")
            
            # 显示步骤结果
            for result_msg in step_results:
                print(f"   {result_msg}")
            
            # 显示评估指标
            if evaluation_results:
                print(f"\n📈 模型性能指标:")
                for metric_name, metric_value in evaluation_results.items():
                    print(f"   {metric_name}: {metric_value}")
                    
        # 显示错误信息
        if execution_result['failed_count'] > 0:
            print("\n❌ 错误信息:")
            for step_id, step_result in execution_result["steps"].items():
                if step_result['status'] == 'failed':
                    step_name = step_result.get('step_name', step_id)
                    error_msg = step_result.get('error', '未知错误')
                    print(f"   ❌ {step_name}: {error_msg}")
        
        # 添加总结
        if execution_result['status'] == 'completed':
            if execution_result['failed_count'] == 0:
                print(f"\n🎉 任务执行成功！所有{execution_result['success_count']}个步骤均已完成。")
            else:
                print(f"\n⚠️ 任务部分完成。{execution_result['success_count']}个步骤成功，{execution_result['failed_count']}个步骤失败。")
        else:
            print(f"\n❌ 任务执行失败。")
            
        print("=" * 60)

    def chat(self, query: str) -> Dict[str, Any]:
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
            workflow_plan = self._generate_workflow(query)
            
            # 显示执行计划
            self._display_execution_progress(workflow_plan)
            
            # 执行工作流
            execution_result = self._execute_workflow(workflow_plan)
            
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
            print(f"\n❌ {error_msg}")
            return {
                "status": "error",
                "error": error_msg,
            }

    def get_session_info(self) -> Dict[str, Any]:
        """获取会话信息"""
        return {
            "model_name": self.model_name,
            "tools_count": len(self.tools),
            "session_count": len(self.session_history),
            "tools": [
                {"name": tool.name, "description": tool.description}
                for tool in self.tools
            ],
        }


def print_banner():
    """打印欢迎横幅"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                    智能水文模型助手                            ║
║                 Intelligent Hydro Model Agent                ║
║                                                              ║
║  🤖 基于工作流的智能任务规划                                   ║
║  🔧 专业水文模型工具集成                                       ║
║  ⚡ 自动模型率定与评估                                         ║
║  📊 智能结果分析与可视化                                       ║
╚══════════════════════════════════════════════════════════════╝
    """)


def interactive_mode(agent: HydroAgent):
    """交互模式"""
    print("\n🎯 进入对话模式 (输入 'quit' 或 'exit' 退出)")
    print("💡 支持的任务类型:")
    print("   - 'gr4j模型率定' - 自动率定GR4J模型")
    print("   - 'xaj模型评估' - 评估XAJ模型性能")
    print("   - '准备数据' - 数据预处理")
    print("   - '查看gr4j参数' - 查看模型参数信息")
    print("   - 'info' - 查看系统信息")

    while True:
        try:
            user_input = input("\n👤 您: ").strip()

            if user_input.lower() in ["quit", "exit", "q"]:
                print("👋 再见！")
                break
            elif user_input.lower() == "info":
                info = agent.get_session_info()
                print(f"\n📊 系统信息:")
                print(f"   模型: {info['model_name']}")
                print(f"   工具数量: {info['tools_count']}")
                print(f"   会话数量: {info['session_count']}")
            elif user_input:
                agent.chat(user_input)
            else:
                print("请输入有效的查询内容")

        except KeyboardInterrupt:
            print("\n👋 再见！")
            break
        except Exception as e:
            print(f"❌ 错误: {e}")


def main():
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
        "--query", "-q", 
        type=str, 
        help="直接执行查询"
    )

    args = parser.parse_args()

    # 配置日志系统
    setup_logging(args.debug)
    logger.debug("启动智能水文模型助手")

    print_banner()

    try:
        # 设置工作目录
        project_root = Path(__file__).parent
        os.chdir(project_root)
        logger.debug(f"工作目录: {project_root}")

        # 创建智能体
        agent = HydroAgent(
            model_name=args.model,
            enable_debug=args.debug
        )

        # 显示系统信息
        info = agent.get_session_info()
        logger.info(f"系统就绪 - 模型: {info['model_name']}, 工具数量: {info['tools_count']}")
        print("✨ 智能水文模型助手已就绪")

        # 执行模式
        if args.query:
            # 单次查询模式
            agent.chat(args.query)
        else:
            # 交互模式
            interactive_mode(agent)

    except Exception as e:
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

    return 0


if __name__ == "__main__":
    exit(main())
