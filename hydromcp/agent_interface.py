"""
Agent统一接口
为主界面Agent提供统一的调用接口，整合工作流生成和执行功能

Author: Assistant  
Date: 2025-01-20
"""

import logging
import json
import asyncio
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

from workflow import (
    WorkflowGeneratorV2, 
    GenerationConfig, 
    create_workflow_generator
)
from hydrorag import RAGSystem
from .enhanced_workflow_executor import EnhancedWorkflowExecutor

logger = logging.getLogger(__name__)


class HydroAgentInterface:
    """水文智能Agent统一接口"""
    
    def __init__(
        self,
        llm_model: str = "qwen3:8b",
        enable_rag: bool = True,
        enable_complex_tasks: bool = True,
        server_command: Optional[List[str]] = None,
        enable_debug: bool = False
    ):
        """
        初始化Agent接口
        
        Args:
            llm_model: LLM模型名称
            enable_rag: 是否启用RAG系统
            enable_complex_tasks: 是否启用复杂任务处理
            server_command: MCP服务器启动命令
            enable_debug: 是否启用调试模式
        """
        self.llm_model = llm_model
        self.enable_rag = enable_rag
        self.enable_complex_tasks = enable_complex_tasks
        self.enable_debug = enable_debug
        
        # 组件初始化状态
        self.is_initialized = False
        self.workflow_generator = None
        self.workflow_executor = None
        self.rag_system = None
        self.ollama_client = None
        
        logger.info("HydroAgent接口初始化开始...")
    
    async def initialize(self) -> bool:
        """
        初始化所有组件
        
        Returns:
            是否初始化成功
        """
        try:
            logger.info("开始初始化Agent组件...")
            
            # 1. 初始化Ollama客户端
            await self._initialize_ollama_client()
            
            # 2. 初始化RAG系统
            if self.enable_rag:
                await self._initialize_rag_system()
            
            # 3. 初始化工作流生成器
            await self._initialize_workflow_generator()
            
            # 4. 初始化工作流执行器
            await self._initialize_workflow_executor()
            
            self.is_initialized = True
            logger.info("Agent接口初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"Agent接口初始化失败: {e}")
            return False
    
    async def _initialize_ollama_client(self):
        """初始化Ollama客户端"""
        try:
            import ollama
            self.ollama_client = ollama.Client()
            
            # 测试连接
            response = self.ollama_client.chat(
                model=self.llm_model,
                messages=[{"role": "user", "content": "test"}]
            )
            logger.info(f"Ollama客户端初始化成功，模型: {self.llm_model}")
            
        except Exception as e:
            logger.warning(f"Ollama客户端初始化失败: {e}，将使用回退模式")
            self.ollama_client = None
    
    async def _initialize_rag_system(self):
        """初始化RAG系统"""
        try:
            from hydrorag import RAGSystem
            self.rag_system = RAGSystem()
            
            # 检查是否需要设置知识库
            status = self.rag_system.get_system_status()
            if not status.get("is_initialized", False):
                logger.info("设置RAG知识库...")
                setup_result = self.rag_system.setup_from_raw_documents()
                if setup_result.get("status") != "success":
                    logger.warning(f"RAG系统设置遇到问题: {setup_result}")
            
            logger.info("RAG系统初始化成功")
            
        except Exception as e:
            logger.warning(f"RAG系统初始化失败: {e}，将禁用RAG功能")
            self.rag_system = None
    
    async def _initialize_workflow_generator(self):
        """初始化工作流生成器"""
        try:
            # 创建生成配置
            config = GenerationConfig(
                llm_model=self.llm_model,
                llm_temperature=0.7,
                rag_retrieval_k=8,
                rag_score_threshold=0.2,
                enable_feedback_learning=False
            )
            
            # 创建工作流生成器
            self.workflow_generator = create_workflow_generator(
                rag_system=self.rag_system,
                ollama_client=self.ollama_client,
                config=config
            )
            
            logger.info("工作流生成器初始化成功")
            
        except Exception as e:
            logger.error(f"工作流生成器初始化失败: {e}")
            raise
    
    async def _initialize_workflow_executor(self):
        """初始化工作流执行器"""
        try:
            self.workflow_executor = EnhancedWorkflowExecutor(
                enable_debug=self.enable_debug,
                enable_complex_tasks=self.enable_complex_tasks
            )
            
            if not await self.workflow_executor.setup():
                raise RuntimeError("工作流执行器设置失败")
            
            logger.info("工作流执行器初始化成功")
            
        except Exception as e:
            logger.error(f"工作流执行器初始化失败: {e}")
            raise
    
    async def process_user_request(self, user_input: str) -> Dict[str, Any]:
        """
        处理用户请求（生成并执行工作流）
        
        Args:
            user_input: 用户输入的自然语言指令
            
        Returns:
            处理结果
        """
        if not self.is_initialized:
            return {
                "success": False,
                "error": "Agent接口未初始化，请先调用initialize()方法"
            }
        
        try:
            logger.info(f"开始处理用户请求: {user_input}")
            
            # 第一阶段：生成工作流
            generation_result = self.workflow_generator.generate_workflow(user_input)
            # print('generation_result————', generation_result)
            if not generation_result.success:
                return {
                    "success": False,
                    "stage": "workflow_generation",
                    "error": generation_result.error_message,
                    "details": generation_result.error_details
                }
            
            logger.info(f"工作流生成成功: {generation_result.workflow.name}")
            
            # 第二阶段：执行工作流
            execution_result = await self.workflow_executor.execute_workflow(
                generation_result.workflow.to_dict()
            )
            
            # 组合结果
            return {
                "success": True,
                "user_input": user_input,
                "workflow_generation": {
                    "workflow_name": generation_result.workflow.name,
                    "workflow_description": generation_result.workflow.description,
                    "task_count": len(generation_result.workflow.tasks),
                    "generation_time": generation_result.total_time
                },
                "workflow_execution": execution_result.to_dict(),
                "overall_summary": {
                    "total_time": generation_result.total_time + execution_result.total_execution_time,
                    "success_rate": execution_result.to_dict()["summary"]["success_rate"],
                    "completed_tasks": execution_result.to_dict()["summary"]["completed_tasks"],
                    "total_tasks": execution_result.to_dict()["summary"]["total_tasks"]
                }
            }
            
        except Exception as e:
            logger.error(f"处理用户请求失败: {e}")
            return {
                "success": False,
                "error": f"处理失败: {str(e)}",
                "user_input": user_input
            }
    
    async def generate_workflow_only(self, user_input: str) -> Dict[str, Any]:
        """
        仅生成工作流（不执行）
        
        Args:
            user_input: 用户输入的自然语言指令
            
        Returns:
            工作流生成结果
        """
        if not self.is_initialized:
            return {
                "success": False,
                "error": "Agent接口未初始化"
            }
        
        try:
            generation_result = self.workflow_generator.generate_workflow(user_input)
            
            if not generation_result.success:
                return {
                    "success": False,
                    "error": generation_result.error_message,
                    "details": generation_result.error_details
                }
            
            return {
                "success": True,
                "workflow": generation_result.workflow.to_dict(),
                "generation_info": {
                    "total_time": generation_result.total_time,
                    "rag_fragments": len(generation_result.rag_result.fragments) if generation_result.rag_result else 0,
                    "reasoning_steps": len(generation_result.cot_result.reasoning_steps) if generation_result.cot_result else 0
                }
            }
            
        except Exception as e:
            logger.error(f"工作流生成失败: {e}")
            return {
                "success": False,
                "error": f"生成失败: {str(e)}"
            }
    
    async def execute_workflow_only(self, workflow_data: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        仅执行工作流（不生成）
        
        Args:
            workflow_data: 工作流数据
            
        Returns:
            执行结果
        """
        if not self.is_initialized:
            return {
                "success": False,
                "error": "Agent接口未初始化"
            }
        
        try:
            execution_result = await self.workflow_executor.execute_workflow(workflow_data)
            
            return {
                "success": True,
                "execution_result": execution_result.to_dict()
            }
            
        except Exception as e:
            logger.error(f"工作流执行失败: {e}")
            return {
                "success": False,
                "error": f"执行失败: {str(e)}"
            }
    
    async def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        status = {
            "is_initialized": self.is_initialized,
            "llm_model": self.llm_model,
            "components": {
                "ollama_client": self.ollama_client is not None,
                "rag_system": self.rag_system is not None,
                "workflow_generator": self.workflow_generator is not None,
                "workflow_executor": self.workflow_executor is not None
            }
        }
        
        # 获取详细状态
        if self.rag_system:
            status["rag_system_status"] = self.rag_system.get_system_status()
        
        if self.workflow_generator:
            status["generator_stats"] = self.workflow_generator.get_generation_statistics()
        
        if self.workflow_executor:
            status["executor_status"] = self.workflow_executor.get_execution_status()
        
        return status
    
    async def cleanup(self):
        """清理资源"""
        try:
            if self.workflow_executor:
                await self.workflow_executor.cleanup()
            
            logger.info("Agent接口清理完成")
            
        except Exception as e:
            logger.error(f"清理资源失败: {e}")


# 便利函数
async def create_hydro_agent_interface(
    llm_model: str = "qwen3:8b",
    enable_rag: bool = True,
    enable_complex_tasks: bool = True,
    server_command: Optional[List[str]] = None,
    enable_debug: bool = False
) -> HydroAgentInterface:
    """
    创建并初始化HydroAgent接口
    
    Returns:
        已初始化的Agent接口
    """
    interface = HydroAgentInterface(
        llm_model=llm_model,
        enable_rag=enable_rag,
        enable_complex_tasks=enable_complex_tasks,
        server_command=server_command,
        enable_debug=enable_debug
    )
    
    await interface.initialize()
    return interface


# 同步包装器（用于非异步环境）
class SyncHydroAgentInterface:
    """同步版本的Agent接口"""
    
    def __init__(self, async_interface: HydroAgentInterface):
        self.async_interface = async_interface
    
    def process_user_request(self, user_input: str) -> Dict[str, Any]:
        """同步处理用户请求"""
        return asyncio.run(self.async_interface.process_user_request(user_input))
    
    def generate_workflow_only(self, user_input: str) -> Dict[str, Any]:
        """同步生成工作流"""
        return asyncio.run(self.async_interface.generate_workflow_only(user_input))
    
    def execute_workflow_only(self, workflow_data: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """同步执行工作流"""
        return asyncio.run(self.async_interface.execute_workflow_only(workflow_data))
    
    def get_system_status(self) -> Dict[str, Any]:
        """同步获取系统状态"""
        return asyncio.run(self.async_interface.get_system_status())


def create_sync_hydro_agent_interface(
    llm_model: str = "qwen3:8b",
    enable_rag: bool = True,
    enable_complex_tasks: bool = True,
    server_command: Optional[List[str]] = None,
    enable_debug: bool = False
) -> SyncHydroAgentInterface:
    """创建同步版本的Agent接口"""
    async_interface = asyncio.run(create_hydro_agent_interface(
        llm_model=llm_model,
        enable_rag=enable_rag,
        enable_complex_tasks=enable_complex_tasks,
        server_command=server_command,
        enable_debug=enable_debug
    ))
    
    return SyncHydroAgentInterface(async_interface)
