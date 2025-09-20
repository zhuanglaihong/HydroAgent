"""
MCP (Model Context Protocol) 工具包
用于将水文模型工具暴露为MCP服务，供Ollama等LLM使用

目录结构:
- server.py: MCP服务端，暴露水文模型工具
- client.py: MCP客户端，供Agent使用
- schemas.py: 工具参数模式定义
- tools.py: 水文模型工具实现
"""

__version__ = "1.0.0"
__author__ = "zhuanglaihong"

from .server import HydroMCPServer
from .client import HydroMCPClient  
from .tools import HydroModelMCPTools
from .task_dispatcher import TaskDispatcher, TaskClassification, TaskComplexity, TaskCategory
from .task_handlers import SimpleTaskHandler, ComplexTaskHandler, ManualReviewHandler, create_task_handler
# from .agent_integration import MCPAgent, create_mcp_agent
# from .workflow_executor import MCPWorkflowExecutor, execute_workflow_with_mcp
from .enhanced_workflow_executor import EnhancedWorkflowExecutor, create_enhanced_workflow_executor
from .agent_interface import (
    HydroAgentInterface, 
    SyncHydroAgentInterface,
    create_hydro_agent_interface,
    create_sync_hydro_agent_interface
)

__all__ = [
    "HydroMCPServer",
    "HydroMCPClient", 
    "HydroModelMCPTools",
    "TaskDispatcher",
    "TaskClassification", 
    "TaskComplexity",
    "TaskCategory",
    "SimpleTaskHandler",
    "ComplexTaskHandler",
    "ManualReviewHandler",
    "create_task_handler",
    "MCPAgent",
    "create_mcp_agent",
    "MCPWorkflowExecutor",
    "execute_workflow_with_mcp",
    # 新增的增强功能
    "EnhancedWorkflowExecutor",
    "create_enhanced_workflow_executor",
    "HydroAgentInterface",
    "SyncHydroAgentInterface", 
    "create_hydro_agent_interface",
    "create_sync_hydro_agent_interface",
]
