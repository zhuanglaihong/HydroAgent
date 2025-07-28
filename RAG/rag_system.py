"""
Author: zhuanglaihong
Date: 2025-07-24 15:03:46
LastEditTime: 2025-07-24 15:03:46
LastEditors: zhuanglaihong
Description: RAG系统主模块 - 整合文档加载、向量存储、检索和生成功能
FilePath: RAG/rag_system.py
Copyright: Copyright (c) 2021-2024 zhuanglaihong. All rights reserved.
"""

import os
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from langchain.schema import Document
from langchain.embeddings.base import Embeddings
from langchain.llms.base import LLM

from .document_loader import DocumentLoader
from .vector_store import VectorStore
from .retriever import Retriever
from .generator import Generator

logger = logging.getLogger(__name__)


class RAGSystem:
    """RAG系统主类"""

    def __init__(
        self,
        embeddings: Embeddings,
        llm: LLM,
        index_path: Optional[str] = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ):
        """
        初始化RAG系统

        Args:
            embeddings: 嵌入模型
            llm: 语言模型
            index_path: 向量索引路径
            chunk_size: 文档分块大小
            chunk_overlap: 分块重叠大小
        """
        self.embeddings = embeddings
        self.llm = llm
        self.index_path = index_path
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # 初始化组件
        self.document_loader = DocumentLoader(chunk_size, chunk_overlap)
        self.vector_store = VectorStore(embeddings, index_path)
        self.retriever = None
        self.generator = Generator(llm)

        # 文档缓存
        self.documents = []

        logger.info("RAG系统初始化完成")

    def load_documents(
        self,
        source: str,
        file_extensions: Optional[List[str]] = None,
        add_metadata: Optional[Dict[str, Any]] = None,
        filter_min_length: int = 50,
        filter_max_length: int = 10000,
    ) -> int:
        """
        加载文档

        Args:
            source: 文档源（文件路径或目录路径）
            file_extensions: 支持的文件扩展名
            add_metadata: 要添加的元数据
            filter_min_length: 最小文档长度
            filter_max_length: 最大文档长度

        Returns:
            加载的文档数量
        """
        try:
            source_path = Path(source)

            if source_path.is_file():
                # 加载单个文件
                documents = self.document_loader.load_document(str(source_path))
            elif source_path.is_dir():
                # 加载目录中的所有文件
                documents = self.document_loader.load_directory(
                    str(source_path), file_extensions
                )
            else:
                raise FileNotFoundError(f"源路径不存在: {source}")

            # 添加元数据
            if add_metadata:
                documents = self.document_loader.add_metadata(documents, add_metadata)

            # 过滤文档
            documents = self.document_loader.filter_documents(
                documents, filter_min_length, filter_max_length
            )

            # 分割文档
            split_documents = self.document_loader.split_documents(documents)

            # 更新文档缓存
            self.documents.extend(split_documents)

            logger.info(f"成功加载 {len(split_documents)} 个文档块")
            return len(split_documents)

        except Exception as e:
            logger.error(f"加载文档失败: {str(e)}")
            raise

    def create_index(self, index_name: str = "faiss_index") -> bool:
        """
        创建向量索引

        Args:
            index_name: 索引名称

        Returns:
            是否成功创建
        """
        try:
            if not self.documents:
                logger.warning("没有文档可以创建索引")
                return False

            self.vector_store.create_index(self.documents, index_name)

            # 初始化检索器
            self.retriever = Retriever(
                vector_store=self.vector_store, documents=self.documents
            )

            # 添加集成检索器
            self.retriever.add_ensemble_retriever(
                "ensemble", ["vector", "bm25"], weights=[0.7, 0.3]
            )

            logger.info("向量索引创建成功")
            return True

        except Exception as e:
            logger.error(f"创建索引失败: {str(e)}")
            return False

    def add_documents_to_index(self, documents: List[Document]) -> bool:
        """
        向现有索引添加文档

        Args:
            documents: 要添加的文档列表

        Returns:
            是否成功添加
        """
        try:
            # 分割文档
            split_documents = self.document_loader.split_documents(documents)

            # 添加到向量存储
            self.vector_store.add_documents(split_documents)

            # 更新文档缓存
            self.documents.extend(split_documents)

            # 重新初始化检索器
            self.retriever = Retriever(
                vector_store=self.vector_store, documents=self.documents
            )

            logger.info(f"成功添加 {len(split_documents)} 个文档到索引")
            return True

        except Exception as e:
            logger.error(f"添加文档失败: {str(e)}")
            return False

    def query(
        self,
        query: str,
        retriever_name: str = "vector",
        generator_name: str = "qa",
        k: int = 4,
        score_threshold: Optional[float] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        执行查询

        Args:
            query: 查询文本
            retriever_name: 检索器名称
            generator_name: 生成器名称
            k: 检索结果数量
            score_threshold: 相似度阈值
            **kwargs: 其他参数

        Returns:
            查询结果字典
        """
        try:
            if not self.retriever:
                return {
                    "success": False,
                    "error": "检索器未初始化，请先创建索引",
                    "answer": "请先加载文档并创建索引。",
                }

            # 检索相关文档
            retrieved_docs = self.retriever.retrieve(
                query=query,
                retriever_name=retriever_name,
                k=k,
                score_threshold=score_threshold,
            )

            # 提取文档和分数
            documents = [doc for doc, score in retrieved_docs]
            scores = [score for doc, score in retrieved_docs]

            # 生成答案
            answer = self.generator.generate(
                query=query, context=documents, generator_name=generator_name, **kwargs
            )

            # 准备结果
            result = {
                "success": True,
                "query": query,
                "answer": answer,
                "retrieved_documents": len(documents),
                "scores": scores,
                "retriever_used": retriever_name,
                "generator_used": generator_name,
                "documents": [
                    {
                        "content": (
                            doc.page_content[:200] + "..."
                            if len(doc.page_content) > 200
                            else doc.page_content
                        ),
                        "metadata": doc.metadata,
                        "score": score,
                    }
                    for doc, score in retrieved_docs
                ],
            }

            logger.info(f"查询完成: {query[:50]}...")
            return result

        except Exception as e:
            logger.error(f"查询失败: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "answer": f"查询时出现错误: {str(e)}",
            }

    def batch_query(
        self,
        queries: List[str],
        retriever_name: str = "vector",
        generator_name: str = "qa",
        k: int = 4,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        批量查询

        Args:
            queries: 查询列表
            retriever_name: 检索器名称
            generator_name: 生成器名称
            k: 检索结果数量
            **kwargs: 其他参数

        Returns:
            查询结果列表
        """
        results = []

        for i, query in enumerate(queries):
            logger.info(f"处理查询 {i+1}/{len(queries)}: {query[:50]}...")

            result = self.query(
                query=query,
                retriever_name=retriever_name,
                generator_name=generator_name,
                k=k,
                **kwargs,
            )

            results.append(result)

        return results

    def get_system_info(self) -> Dict[str, Any]:
        """
        获取系统信息

        Returns:
            系统信息字典
        """
        info = {
            "documents_loaded": len(self.documents),
            "index_created": self.vector_store.vector_store is not None,
            "index_path": self.index_path,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
        }

        # 添加索引信息
        if self.vector_store.vector_store:
            index_info = self.vector_store.get_index_info()
            info["index_info"] = index_info

        # 添加检索器信息
        if self.retriever:
            info["available_retrievers"] = self.retriever.get_available_retrievers()

        # 添加生成器信息
        info["available_generators"] = self.generator.get_available_generators()

        return info

    def save_system(self, save_path: str) -> bool:
        """
        保存系统状态

        Args:
            save_path: 保存路径

        Returns:
            是否成功保存
        """
        try:
            # 保存向量索引
            if self.vector_store.vector_store:
                self.vector_store.save_index(save_path)

            logger.info(f"系统状态已保存到: {save_path}")
            return True

        except Exception as e:
            logger.error(f"保存系统失败: {str(e)}")
            return False

    def load_system(self, load_path: str) -> bool:
        """
        加载系统状态

        Args:
            load_path: 加载路径

        Returns:
            是否成功加载
        """
        try:
            # 加载向量索引
            self.vector_store.load_index(load_path)

            # 重新初始化检索器
            if self.vector_store.vector_store:
                self.retriever = Retriever(
                    vector_store=self.vector_store, documents=self.documents
                )

            logger.info(f"系统状态已从 {load_path} 加载")
            return True

        except Exception as e:
            logger.error(f"加载系统失败: {str(e)}")
            return False

    def clear_system(self):
        """清除系统状态"""
        self.documents = []
        self.vector_store.delete_index()
        self.retriever = None
        self.generator.clear_conversation_memory()

        logger.info("系统状态已清除")

    def get_available_retrievers(self) -> List[str]:
        """
        获取可用的检索器列表

        Returns:
            检索器名称列表
        """
        if self.retriever:
            return self.retriever.get_available_retrievers()
        return []

    def get_available_generators(self) -> List[str]:
        """
        获取可用的生成器列表

        Returns:
            生成器名称列表
        """
        return self.generator.get_available_generators()
