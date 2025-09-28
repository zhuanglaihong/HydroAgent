"""
Author: zhuanglaihong
Date: 2024-09-24 15:30:00
LastEditTime: 2025-09-27 15:00:00
LastEditors: zhuanglaihong
Description: HydroRAG - 智能水文知识检索增强生成系统，支持Qwen API和本地Ollama嵌入模型的混合RAG系统，为水文智能体提供高质量的知识检索和增强生成服务
FilePath: \HydroAgent\hydrorag\__init__.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.

主要特性:
- 混合嵌入模型支持（Qwen API + 本地Ollama）
- 智能查询处理和重排序
- 高性能向量检索（ChromaDB）
- 水文领域专用优化
"""

from .config import Config, create_default_config, default_config
from .document_processor import DocumentProcessor
from .vector_store import VectorStore
from .embeddings_manager import EmbeddingsManager
from .query_processor import QueryProcessor
from .rag_system import RAGSystem, create_rag_system, quick_setup

__version__ = "2.0.0"
__author__ = "HydroAgent Team"
__title__ = "HydroRAG"
__description__ = "智能水文知识检索增强生成系统"
__url__ = "https://github.com/hydroagent/hydrorag"
__license__ = "MIT"
__copyright__ = "Copyright 2024 HydroAgent Team"

__all__ = [
    # 核心类
    "Config",
    "DocumentProcessor",
    "VectorStore",
    "EmbeddingsManager",
    "QueryProcessor",
    "RAGSystem",

    # 配置函数
    "create_default_config",
    "default_config",

    # 便利函数
    "create_rag_system",
    "quick_setup"
]