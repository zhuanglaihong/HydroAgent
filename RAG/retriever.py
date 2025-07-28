"""
Author: zhuanglaihong
Date: 2025-07-24 15:03:46
LastEditTime: 2025-07-24 15:03:46
LastEditors: zhuanglaihong
Description: 检索器模块 - 提供多种检索策略和结果处理
FilePath: RAG/retriever.py
Copyright: Copyright (c) 2021-2024 zhuanglaihong. All rights reserved.
"""

from typing import List, Dict, Any, Optional, Tuple
import logging
from abc import ABC, abstractmethod

from langchain.schema import Document
from langchain.retrievers import BM25Retriever, TFIDFRetriever, EnsembleRetriever
from langchain.retrievers.document_compressors import LLMChainExtractor
from langchain.retrievers.contextual_compression import ContextualCompressionRetriever

logger = logging.getLogger(__name__)


class BaseRetriever(ABC):
    """检索器基类"""

    @abstractmethod
    def retrieve(self, query: str, k: int = 4) -> List[Tuple[Document, float]]:
        """
        检索文档

        Args:
            query: 查询文本
            k: 返回结果数量

        Returns:
            文档和分数的元组列表
        """
        pass


class VectorRetriever(BaseRetriever):
    """向量检索器"""

    def __init__(self, vector_store):
        """
        初始化向量检索器

        Args:
            vector_store: 向量存储对象
        """
        self.vector_store = vector_store

    def retrieve(
        self, query: str, k: int = 4, score_threshold: Optional[float] = None
    ) -> List[Tuple[Document, float]]:
        """
        向量相似性检索

        Args:
            query: 查询文本
            k: 返回结果数量
            score_threshold: 相似度阈值

        Returns:
            文档和分数的元组列表
        """
        return self.vector_store.similarity_search(
            query=query, k=k, score_threshold=score_threshold
        )


class BM25RetrieverWrapper(BaseRetriever):
    """BM25检索器包装器"""

    def __init__(self, documents: List[Document]):
        """
        初始化BM25检索器

        Args:
            documents: 文档列表
        """
        self.retriever = BM25Retriever.from_documents(documents)

    def retrieve(self, query: str, k: int = 4) -> List[Tuple[Document, float]]:
        """
        BM25检索

        Args:
            query: 查询文本
            k: 返回结果数量

        Returns:
            文档和分数的元组列表
        """
        docs = self.retriever.get_relevant_documents(query)
        # BM25不提供分数，所以给每个文档分配默认分数1.0
        return [(doc, 1.0) for doc in docs[:k]]


class TFIDFRetrieverWrapper(BaseRetriever):
    """TF-IDF检索器包装器"""

    def __init__(self, documents: List[Document]):
        """
        初始化TF-IDF检索器

        Args:
            documents: 文档列表
        """
        self.retriever = TFIDFRetriever.from_documents(documents)

    def retrieve(self, query: str, k: int = 4) -> List[Tuple[Document, float]]:
        """
        TF-IDF检索

        Args:
            query: 查询文本
            k: 返回结果数量

        Returns:
            文档和分数的元组列表
        """
        docs = self.retriever.get_relevant_documents(query)
        # TF-IDF不提供分数，所以给每个文档分配默认分数1.0
        return [(doc, 1.0) for doc in docs[:k]]


class EnsembleRetrieverWrapper(BaseRetriever):
    """集成检索器包装器"""

    def __init__(
        self, retrievers: List[BaseRetriever], weights: Optional[List[float]] = None
    ):
        """
        初始化集成检索器

        Args:
            retrievers: 检索器列表
            weights: 权重列表
        """
        self.retrievers = retrievers
        self.weights = weights or [1.0] * len(retrievers)

        if len(self.weights) != len(self.retrievers):
            raise ValueError("权重数量必须与检索器数量相同")

    def retrieve(self, query: str, k: int = 4) -> List[Tuple[Document, float]]:
        """
        集成检索

        Args:
            query: 查询文本
            k: 返回结果数量

        Returns:
            文档和分数的元组列表
        """
        all_results = []

        for retriever, weight in zip(self.retrievers, self.weights):
            try:
                results = retriever.retrieve(query, k)
                # 应用权重
                weighted_results = [(doc, score * weight) for doc, score in results]
                all_results.extend(weighted_results)
            except Exception as e:
                logger.warning(f"检索器 {type(retriever).__name__} 失败: {str(e)}")
                continue

        # 按分数排序并去重
        unique_results = {}
        for doc, score in all_results:
            doc_id = id(doc)
            if doc_id not in unique_results or score > unique_results[doc_id][1]:
                unique_results[doc_id] = (doc, score)

        # 按分数降序排序
        sorted_results = sorted(
            unique_results.values(), key=lambda x: x[1], reverse=True
        )

        return sorted_results[:k]


class ContextualCompressionRetrieverWrapper(BaseRetriever):
    """上下文压缩检索器包装器"""

    def __init__(self, base_retriever: BaseRetriever, llm):
        """
        初始化上下文压缩检索器

        Args:
            base_retriever: 基础检索器
            llm: 语言模型
        """
        self.base_retriever = base_retriever
        self.llm = llm

        # 创建文档压缩器
        self.compressor = LLMChainExtractor.from_llm(llm)

        # 创建上下文压缩检索器
        self.compression_retriever = ContextualCompressionRetriever(
            base_compressor=self.compressor,
            base_retriever=self._create_langchain_retriever(base_retriever),
        )

    def _create_langchain_retriever(self, base_retriever):
        """创建LangChain兼容的检索器"""

        class LangChainRetriever:
            def __init__(self, retriever):
                self.retriever = retriever

            def get_relevant_documents(self, query):
                results = self.retriever.retrieve(query, k=10)
                return [doc for doc, _ in results]

        return LangChainRetriever(base_retriever)

    def retrieve(self, query: str, k: int = 4) -> List[Tuple[Document, float]]:
        """
        上下文压缩检索

        Args:
            query: 查询文本
            k: 返回结果数量

        Returns:
            文档和分数的元组列表
        """
        try:
            docs = self.compression_retriever.get_relevant_documents(query)
            # 压缩检索器不提供分数，给每个文档分配默认分数1.0
            return [(doc, 1.0) for doc in docs[:k]]
        except Exception as e:
            logger.error(f"上下文压缩检索失败: {str(e)}")
            # 回退到基础检索器
            return self.base_retriever.retrieve(query, k)


class Retriever:
    """检索器主类"""

    def __init__(self, vector_store=None, documents: List[Document] = None):
        """
        初始化检索器

        Args:
            vector_store: 向量存储对象
            documents: 文档列表（用于BM25和TF-IDF）
        """
        self.vector_store = vector_store
        self.documents = documents
        self.retrievers = {}

        # 初始化各种检索器
        self._initialize_retrievers()

    def _initialize_retrievers(self):
        """初始化各种检索器"""
        if self.vector_store:
            self.retrievers["vector"] = VectorRetriever(self.vector_store)

        if self.documents:
            try:
                self.retrievers["bm25"] = BM25RetrieverWrapper(self.documents)
                self.retrievers["tfidf"] = TFIDFRetrieverWrapper(self.documents)
            except Exception as e:
                logger.warning(f"初始化BM25/TF-IDF检索器失败: {str(e)}")

    def add_ensemble_retriever(
        self, name: str, retrievers: List[str], weights: Optional[List[float]] = None
    ):
        """
        添加集成检索器

        Args:
            name: 检索器名称
            retrievers: 要集成的检索器名称列表
            weights: 权重列表
        """
        available_retrievers = []
        for retriever_name in retrievers:
            if retriever_name in self.retrievers:
                available_retrievers.append(self.retrievers[retriever_name])
            else:
                logger.warning(f"检索器 {retriever_name} 不可用")

        if available_retrievers:
            self.retrievers[name] = EnsembleRetrieverWrapper(
                available_retrievers, weights
            )

    def add_contextual_compression_retriever(
        self, name: str, base_retriever_name: str, llm
    ):
        """
        添加上下文压缩检索器

        Args:
            name: 检索器名称
            base_retriever_name: 基础检索器名称
            llm: 语言模型
        """
        if base_retriever_name in self.retrievers:
            self.retrievers[name] = ContextualCompressionRetrieverWrapper(
                self.retrievers[base_retriever_name], llm
            )
        else:
            logger.warning(f"基础检索器 {base_retriever_name} 不可用")

    def retrieve(
        self,
        query: str,
        retriever_name: str = "vector",
        k: int = 4,
        score_threshold: Optional[float] = None,
    ) -> List[Tuple[Document, float]]:
        """
        执行检索

        Args:
            query: 查询文本
            retriever_name: 检索器名称
            k: 返回结果数量
            score_threshold: 相似度阈值

        Returns:
            文档和分数的元组列表
        """
        if retriever_name not in self.retrievers:
            logger.warning(f"检索器 {retriever_name} 不可用，使用默认检索器")
            retriever_name = (
                list(self.retrievers.keys())[0] if self.retrievers else None
            )

        if not retriever_name:
            logger.error("没有可用的检索器")
            return []

        try:
            retriever = self.retrievers[retriever_name]

            # 对于向量检索器，传递score_threshold参数
            if isinstance(retriever, VectorRetriever):
                return retriever.retrieve(query, k, score_threshold)
            else:
                return retriever.retrieve(query, k)

        except Exception as e:
            logger.error(f"检索失败: {str(e)}")
            return []

    def get_available_retrievers(self) -> List[str]:
        """
        获取可用的检索器列表

        Returns:
            检索器名称列表
        """
        return list(self.retrievers.keys())

    def get_retriever_info(self, retriever_name: str) -> Dict[str, Any]:
        """
        获取检索器信息

        Args:
            retriever_name: 检索器名称

        Returns:
            检索器信息字典
        """
        if retriever_name not in self.retrievers:
            return {"error": f"检索器 {retriever_name} 不存在"}

        retriever = self.retrievers[retriever_name]
        info = {
            "name": retriever_name,
            "type": type(retriever).__name__,
            "available": True,
        }

        return info
