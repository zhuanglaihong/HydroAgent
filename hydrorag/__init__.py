"""
HydroRAG - 水文模型RAG知识库系统
基于Chroma构建的本地向量数据库系统，用于水文模型相关知识检索
"""

from .config import Config
from .document_processor import DocumentProcessor
from .vector_store import VectorStore
from .embeddings_manager import EmbeddingsManager
from .rag_system import RAGSystem

__version__ = "1.0.0"
__author__ = "HydroAgent Team"

__all__ = [
    "Config",
    "DocumentProcessor", 
    "VectorStore",
    "EmbeddingsManager",
    "RAGSystem"
]
