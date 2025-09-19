"""
Author: zhuanglaihong
Date: 2025-07-28
LastEditTime: 2025-01-20
Description: Workflow 模块 - 智能工作流编排系统 (重构版本)
FilePath: workflow/__init__.py
Copyright: Copyright (c) 2021-2024 zhuanglaihong. All rights reserved.

智能工作流编排系统 - 基于LLM和RAG的任务规划与执行

重构后的工作流程：
1. 指令解析与意图理解：对用户指令进行NLP处理，提取关键信息
2. 增强推理引擎（CoT + RAG）：利用RAG检索知识，引导LLM逐步推理
3. 工作流组装与优化：解析、验证和优化LLM输出的工作流
4. 验证与反馈闭环：自动处理错误并学习优化
"""

# 新版模块
from .instruction_parser import (
    InstructionParser, IntentResult, IntentType, EntityType, Entity,
    create_instruction_parser
)
from .cot_rag_engine import (
    CoTRAGEngine, KnowledgeFragment, RAGRetrievalResult, CoTReasoningResult,
    create_cot_rag_engine
)
from .workflow_assembler import (
    WorkflowAssembler, AssembledWorkflow, WorkflowTask, ToolRegistry,
    ValidationIssue, ValidationStatus, TaskType, create_workflow_assembler
)
from .validation_feedback import (
    ValidationFeedbackSystem, ExecutionFeedback, LearningCase, 
    FeedbackCollector, LearningEngine, ErrorType, FeedbackType,
    create_validation_feedback_system
)
from .workflow_generator_v2 import (
    WorkflowGeneratorV2, GenerationConfig, GenerationResult,
    create_workflow_generator
)


# 新版模块优先
__all__ = [
    # 新版核心模块
    "WorkflowGeneratorV2",
    "GenerationConfig", 
    "GenerationResult",
    "create_workflow_generator",
    
    # 子模块
    "InstructionParser",
    "IntentResult",
    "IntentType", 
    "EntityType",
    "Entity",
    "create_instruction_parser",
    
    "CoTRAGEngine",
    "KnowledgeFragment",
    "RAGRetrievalResult", 
    "CoTReasoningResult",
    "create_cot_rag_engine",
    
    "WorkflowAssembler",
    "AssembledWorkflow",
    "WorkflowTask",
    "ToolRegistry",
    "ValidationIssue",
    "ValidationStatus",
    "TaskType",
    "create_workflow_assembler",
    
    "ValidationFeedbackSystem",
    "ExecutionFeedback",
    "LearningCase",
    "FeedbackCollector",
    "LearningEngine", 
    "ErrorType",
    "FeedbackType",
    "create_validation_feedback_system",
    
]
