"""
Author: zhuanglaihong
Date: 2025-07-28
LastEditTime: 2025-07-28
Description: Workflow 模块 - 智能工作流编排系统
FilePath: workflow/__init__.py
Copyright: Copyright (c) 2021-2024 zhuanglaihong. All rights reserved.

智能工作流编排系统 - 基于LLM和RAG的任务规划与执行

工作流程：
1. 意图理解：LLM将模糊查询重构为明确指令
2. 查询扩展：改写和扩展原始意图以获得更丰富的上下文
3. 知识检索：在向量数据库中检索相关文档和知识片段
4. 上下文构建：拼接用户输入和检索到的知识片段
5. 工作流生成：基于上下文调用LLM生成详细的执行工作流
6. 任务执行：LangChain调用下游工具逐步执行并监控状态
"""

from .orchestrator import WorkflowOrchestrator
from .intent_processor import IntentProcessor
from .query_expander import QueryExpander
from .knowledge_retriever import KnowledgeRetriever
from .context_builder import ContextBuilder
from .workflow_generator import WorkflowGenerator
from .workflow_types import (
    WorkflowStep,
    WorkflowPlan,
    ExecutionResult,
    ExecutionStatus,
    KnowledgeFragment,
    IntentAnalysis,
)

__all__ = [
    "WorkflowOrchestrator",
    "IntentProcessor",
    "QueryExpander",
    "KnowledgeRetriever",
    "ContextBuilder",
    "WorkflowGenerator",
    "WorkflowStep",
    "WorkflowPlan",
    "ExecutionResult",
    "ExecutionStatus",
    "KnowledgeFragment",
    "IntentAnalysis",
]
