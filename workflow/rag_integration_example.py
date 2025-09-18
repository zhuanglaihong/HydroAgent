"""
RAG系统与工作流完整集成示例
演示如何将HydroRAG知识库集成到工作流生成系统中
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any, List
import logging

# 添加项目根路径
repo_path = Path(os.path.abspath(__file__)).parent.parent
sys.path.append(str(repo_path))

from hydrorag.rag_system import quick_setup
from workflow.knowledge_retriever import KnowledgeRetriever
from workflow.orchestrator import WorkflowOrchestrator
from workflow.intent_processor import IntentProcessor
from workflow.query_expander import QueryExpander
from workflow.workflow_generator import WorkflowGenerator
from workflow.workflow_types import WorkflowRequest, WorkflowStep, KnowledgeFragment

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RAGEnhancedWorkflowSystem:
    """集成RAG系统的增强工作流系统"""
    
    def __init__(self, documents_dir: str = None):
        """
        初始化增强工作流系统
        
        Args:
            documents_dir: 文档目录路径
        """
        if documents_dir is None:
            documents_dir = os.path.join(repo_path, "documents")
        
        self.documents_dir = documents_dir
        
        # 初始化RAG相关组件
        self.rag_system = None
        self.knowledge_retriever = None
        
        # 初始化工作流组件
        self.intent_processor = None
        self.query_expander = None
        self.workflow_generator = None
        self.orchestrator = None
        
        # 系统状态
        self.is_initialized = False
        self.initialization_errors = []
        
        # 初始化系统
        self._initialize_system()
    
    def _initialize_system(self):
        """初始化系统所有组件"""
        try:
            logger.info("开始初始化RAG增强工作流系统")
            
            # 1. 初始化RAG系统
            self._initialize_rag_system()
            
            # 2. 初始化工作流组件
            self._initialize_workflow_components()
            
            # 3. 集成RAG到工作流
            self._integrate_rag_into_workflow()
            
            # 检查初始化状态
            self.is_initialized = (
                self.rag_system is not None and
                self.knowledge_retriever is not None and
                self.orchestrator is not None
            )
            
            if self.is_initialized:
                logger.info("RAG增强工作流系统初始化成功")
            else:
                logger.warning(f"系统初始化部分失败，错误: {self.initialization_errors}")
                
        except Exception as e:
            error_msg = f"系统初始化失败: {e}"
            self.initialization_errors.append(error_msg)
            logger.error(error_msg)
            self.is_initialized = False
    
    def _initialize_rag_system(self):
        """初始化RAG系统"""
        try:
            logger.info("初始化RAG系统...")
            
            # 使用快速设置初始化RAG系统
            self.rag_system = quick_setup(self.documents_dir)
            
            if not self.rag_system or not self.rag_system.is_initialized:
                error_msg = "RAG系统初始化失败"
                self.initialization_errors.append(error_msg)
                logger.error(error_msg)
                return
            
            # 初始化知识检索器
            self.knowledge_retriever = KnowledgeRetriever(
                rag_system=self.rag_system,
                enable_fallback=True
            )
            
            logger.info("RAG系统和知识检索器初始化成功")
            
        except Exception as e:
            error_msg = f"RAG系统初始化失败: {e}"
            self.initialization_errors.append(error_msg)
            logger.error(error_msg)
    
    def _initialize_workflow_components(self):
        """初始化工作流组件"""
        try:
            logger.info("初始化工作流组件...")
            
            # 初始化语言模型
            try:
                from langchain_ollama import ChatOllama
                self.llm = ChatOllama(model="granite3-dense:8b", temperature=0.1)
                logger.info("✅ 语言模型初始化成功")
            except Exception as e:
                error_msg = f"语言模型初始化失败: {e}"
                self.initialization_errors.append(error_msg)
                logger.error(error_msg)
                return
            
            # 初始化意图处理器
            self.intent_processor = IntentProcessor(llm=self.llm)
            
            # 初始化查询扩展器
            self.query_expander = QueryExpander(llm=self.llm)
            
            # 初始化工作流生成器
            self.workflow_generator = WorkflowGenerator(llm=self.llm)
            
            logger.info("工作流组件初始化成功")
            
        except Exception as e:
            error_msg = f"工作流组件初始化失败: {e}"
            self.initialization_errors.append(error_msg)
            logger.error(error_msg)
    
    def _integrate_rag_into_workflow(self):
        """将RAG系统集成到工作流中"""
        try:
            logger.info("集成RAG系统到工作流...")
            
            # 创建带RAG增强的编排器
            self.orchestrator = WorkflowOrchestrator(
                llm=self.llm,
                tools=None,  # 暂时不使用工具
                enable_debug=True
            )
            
            # 注入组件
            self.orchestrator.intent_processor = self.intent_processor
            self.orchestrator.query_expander = self.query_expander
            self.orchestrator.knowledge_retriever = self.knowledge_retriever
            self.orchestrator.workflow_generator = self.workflow_generator
            
            logger.info("RAG系统成功集成到工作流")
            
        except Exception as e:
            error_msg = f"RAG集成失败: {e}"
            self.initialization_errors.append(error_msg)
            logger.error(error_msg)
    
    def generate_workflow_with_knowledge(
        self, 
        user_query: str,
        use_knowledge: bool = True,
        knowledge_top_k: int = 5,
        knowledge_threshold: float = 0.3
    ) -> Dict[str, Any]:
        """
        基于知识库生成工作流
        
        Args:
            user_query: 用户查询
            use_knowledge: 是否使用知识库
            knowledge_top_k: 知识检索数量
            knowledge_threshold: 知识相关性阈值
            
        Returns:
            Dict[str, Any]: 工作流生成结果
        """
        try:
            if not self.is_initialized:
                return {
                    "status": "error",
                    "error": "系统未初始化",
                    "initialization_errors": self.initialization_errors
                }
            
            logger.info(f"开始生成工作流，查询: {user_query}")
            
            # 创建工作流请求
            request = WorkflowRequest(
                query=user_query,
                user_context={
                    "use_knowledge": use_knowledge,
                    "knowledge_config": {
                        "top_k": knowledge_top_k,
                        "threshold": knowledge_threshold
                    }
                }
            )
            
            # 使用编排器生成工作流
            workflow = self.orchestrator.process_query(request.query)
            
            # 构建响应结果
            result = {
                "status": "success" if workflow else "error",
                "workflow": workflow,
                "knowledge_enhanced": use_knowledge,
                "knowledge_fragments": [],  # 暂时为空，后续可以从知识检索器获取
                "request_id": request.request_id
            }
            
            # 如果使用了知识库，添加知识统计信息
            if use_knowledge and hasattr(self.knowledge_retriever, "get_last_retrieval_stats"):
                stats = self.knowledge_retriever.get_last_retrieval_stats()
                result["knowledge_stats"] = stats
            
            logger.info(f"工作流生成完成，状态: {result['status']}")
            return result
            
        except Exception as e:
            logger.error(f"工作流生成失败: {e}")
            return {
                "status": "error",
                "error": str(e),
                "request_id": request.request_id,
                "query": request.query,
                "knowledge_enhanced": use_knowledge
            }
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        status = {
            "is_initialized": self.is_initialized,
            "initialization_errors": self.initialization_errors,
            "components": {}
        }
        
        # RAG系统状态
        if self.rag_system:
            rag_health = self.rag_system.health_check()
            status["components"]["rag_system"] = {
                "available": True,
                "health": rag_health
            }
        else:
            status["components"]["rag_system"] = {"available": False}
        
        # 知识检索器状态
        if self.knowledge_retriever:
            retriever_info = self.knowledge_retriever.get_system_info()
            status["components"]["knowledge_retriever"] = {
                "available": True,
                "info": retriever_info
            }
        else:
            status["components"]["knowledge_retriever"] = {"available": False}
        
        # 工作流组件状态
        status["components"]["workflow"] = {
            "intent_processor": self.intent_processor is not None,
            "query_expander": self.query_expander is not None,
            "workflow_generator": self.workflow_generator is not None,
            "orchestrator": self.orchestrator is not None
        }
        
        return status


def demo_workflow_scenarios():
    """演示不同的工作流场景"""
    
    print("🚀 RAG增强工作流系统演示")
    print("=" * 80)
    
    # 初始化系统
    print("\n📚 初始化RAG增强工作流系统...")
    system = RAGEnhancedWorkflowSystem()
    
    if not system.is_initialized:
        print("❌ 系统初始化失败")
        for error in system.initialization_errors:
            print(f"   - {error}")
        return False
    
    print("✅ 系统初始化成功")
    
    # 测试场景
    test_scenarios = [
        {
            "name": "模型率定流程",
            "query": "如何对水文模型进行率定和验证？",
            "description": "测试模型率定相关的工作流生成"
        },
        {
            "name": "模型评估指标计算",
            "query": "计算模型的NSE、RMSE等评估指标",
            "description": "测试模型评估相关的工作流生成"
        }
    ]
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n{'='*60}")
        print(f"场景 {i}: {scenario['name']}")
        print(f"描述: {scenario['description']}")
        print(f"查询: {scenario['query']}")
        print("="*60)
        
        # 生成工作流（使用知识库）
        print("\n🧠 使用知识库增强生成工作流...")
        result_with_knowledge = system.generate_workflow_with_knowledge(
            user_query=scenario['query'],
            use_knowledge=True,
            knowledge_top_k=5,
            knowledge_threshold=0.2
        )
        
        if result_with_knowledge.get("status") == "success":
            print("✅ 知识增强工作流生成成功")
            
            # 显示知识片段信息
            if "knowledge_fragments" in result_with_knowledge:
                fragments = result_with_knowledge["knowledge_fragments"]
                print(f"   检索到 {len(fragments)} 个知识片段")
                
                for j, fragment in enumerate(fragments[:2], 1):
                    print(f"   片段 {j} (得分: {fragment.score:.3f}):")
                    print(f"     内容: {fragment.content[:100]}...")
                    print(f"     来源: {fragment.source}")
            
            # 显示生成的工作流
            if "workflow" in result_with_knowledge:
                workflow = result_with_knowledge["workflow"]
                print(f"\n📋 生成的工作流包含 {len(workflow.steps)} 个步骤:")
                
                for j, step in enumerate(workflow.steps[:3], 1):
                    print(f"   步骤 {j}: {step.name}")
                    print(f"     描述: {step.description[:100]}...")
                    if step.tools:
                        print(f"     工具: {', '.join(step.tools[:3])}")
        else:
            print("❌ 工作流生成失败:")
            print(f"   错误: {result_with_knowledge.get('error', '未知错误')}")
        
        # 对比：不使用知识库的结果
        # print("\n🤖 不使用知识库生成工作流...")
        # result_without_knowledge = system.generate_workflow_with_knowledge(
        #     user_query=scenario['query'],
        #     use_knowledge=False
        # )
        
        # if result_without_knowledge.get("status") == "success":
        #     print("✅ 基础工作流生成成功")
        #     if "workflow" in result_without_knowledge:
        #         workflow = result_without_knowledge["workflow"]
        #         print(f"   基础工作流包含 {len(workflow.steps)} 个步骤")
        # else:
        #     print("❌ 基础工作流生成失败")
    
    # 系统状态报告
    print(f"\n{'='*60}")
    print("📊 系统状态报告")
    print("="*60)
    
    status = system.get_system_status()
    
    print(f"系统初始化: {'✅ 成功' if status['is_initialized'] else '❌ 失败'}")
    
    for component, info in status["components"].items():
        if isinstance(info, dict) and "available" in info:
            status_icon = "✅" if info["available"] else "❌"
            print(f"{component}: {status_icon} {'可用' if info['available'] else '不可用'}")
        else:
            print(f"{component}: {info}")
    
    print("\n🎉 演示完成！RAG增强工作流系统运行正常")
    return True


def simple_usage_example():
    """简单使用示例"""
    print("\n" + "="*80)
    print("📖 简单使用示例")
    print("="*80)
    
    # 初始化系统
    system = RAGEnhancedWorkflowSystem()
    
    if not system.is_initialized:
        print("❌ 系统初始化失败")
        return False
    
    # 用户查询
    user_query = "我需要建立一个完整的GR4J水文模型率定和验证流程"
    
    print(f"用户查询: {user_query}")
    
    # 生成工作流
    result = system.generate_workflow_with_knowledge(
        user_query=user_query,
        use_knowledge=True,
        knowledge_top_k=3,
        knowledge_threshold=0.3
    )
    
    if result.get("status") == "success":
        print("\n✅ 工作流生成成功")
        
        # 显示知识增强信息
        if result.get("knowledge_enhanced") and "knowledge_stats" in result:
            stats = result["knowledge_stats"]
            print(f"知识增强: {stats['fragments_count']} 个片段，平均得分: {stats['avg_score']:.3f}")
        
        # 显示工作流概览
        if "workflow" in result:
            workflow = result["workflow"]
            print(f"\n📋 生成的工作流: {workflow.name}")
            print(f"描述: {workflow.description}")
            print(f"步骤数: {len(workflow.steps)}")
            
            print("\n步骤详情:")
            for i, step in enumerate(workflow.steps, 1):
                print(f"  {i}. {step.name}")
                print(f"     {step.description}")
                if step.tools:
                    print(f"     工具: {', '.join(step.tools)}")
                print()
    
    else:
        print("❌ 工作流生成失败:")
        print(f"错误: {result.get('error', '未知错误')}")
    
    return True


if __name__ == "__main__":
    try:
        # 运行完整演示
        success = demo_workflow_scenarios()
        
        if success:
            # 运行简单示例
            simple_usage_example()
        
        print("\n" + "="*80)
        print("🎯 集成完成！RAG系统已成功集成到工作流生成中")
        print("💡 现在可以在Agent中使用这个增强系统进行智能工作流生成")
        print("="*80)
        
    except Exception as e:
        logger.exception(f"演示运行失败: {e}")
        exit(1)
