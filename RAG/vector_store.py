"""
Author: zhuanglaihong
Date: 2025-07-24 15:03:46
LastEditTime: 2025-07-24 15:03:46
LastEditors: zhuanglaihong
Description: 向量存储模块 - 支持FAISS向量数据库的创建、存储和检索
FilePath: RAG/vector_store.py
Copyright: Copyright (c) 2021-2024 zhuanglaihong. All rights reserved.
"""

import os
import pickle
from typing import List, Dict, Any, Optional, Tuple
import logging
import numpy as np

import faiss
from langchain_community.vectorstores import FAISS
from langchain.schema import Document
from langchain.embeddings.base import Embeddings

logger = logging.getLogger(__name__)


class VectorStore:
    """向量存储类"""

    def __init__(self, embeddings: Embeddings, index_path: Optional[str] = None):
        """
        初始化向量存储

        Args:
            embeddings: 嵌入模型
            index_path: 索引文件路径
        """
        self.embeddings = embeddings
        self.index_path = index_path
        self.vector_store = None

        # 如果指定了索引路径且文件存在，则加载现有索引
        if index_path and os.path.exists(index_path):
            self.load_index(index_path)

    def create_index(
        self, documents: List[Document], index_name: str = "faiss_index"
    ) -> None:
        """
        创建向量索引

        Args:
            documents: 文档列表
            index_name: 索引名称
        """
        if not documents:
            logger.warning("没有文档可以创建索引")
            return

        try:
            # 创建FAISS向量存储
            self.vector_store = FAISS.from_documents(
                documents=documents, embedding=self.embeddings
            )

            logger.info(f"成功创建向量索引，包含 {len(documents)} 个文档")

            # 如果指定了保存路径，则保存索引
            if self.index_path:
                self.save_index(self.index_path)

        except Exception as e:
            logger.error(f"创建向量索引失败: {str(e)}")
            raise

    def add_documents(self, documents: List[Document]) -> None:
        """
        向现有索引添加文档

        Args:
            documents: 要添加的文档列表
        """
        if not self.vector_store:
            logger.warning("向量存储未初始化，请先创建索引")
            return

        try:
            self.vector_store.add_documents(documents)
            logger.info(f"成功添加 {len(documents)} 个文档到向量存储")

            # 保存更新后的索引
            if self.index_path:
                self.save_index(self.index_path)

        except Exception as e:
            logger.error(f"添加文档失败: {str(e)}")
            raise

    def similarity_search(
        self, query: str, k: int = 4, score_threshold: Optional[float] = None
    ) -> List[Tuple[Document, float]]:
        """
        相似性搜索

        Args:
            query: 查询文本
            k: 返回结果数量
            score_threshold: 相似度阈值

        Returns:
            文档和相似度分数的元组列表
        """
        if not self.vector_store:
            logger.warning("向量存储未初始化")
            return []

        try:
            # 执行相似性搜索
            results = self.vector_store.similarity_search_with_score(query=query, k=k)

            # 如果设置了阈值，过滤结果
            if score_threshold is not None:
                results = [
                    (doc, score) for doc, score in results if score >= score_threshold
                ]

            logger.info(f"相似性搜索完成，返回 {len(results)} 个结果")
            return results

        except Exception as e:
            logger.error(f"相似性搜索失败: {str(e)}")
            return []

    def similarity_search_by_vector(
        self, embedding: List[float], k: int = 4
    ) -> List[Tuple[Document, float]]:
        """
        基于向量进行相似性搜索

        Args:
            embedding: 查询向量
            k: 返回结果数量

        Returns:
            文档和相似度分数的元组列表
        """
        if not self.vector_store:
            logger.warning("向量存储未初始化")
            return []

        try:
            results = self.vector_store.similarity_search_by_vector_with_score(
                embedding=embedding, k=k
            )

            logger.info(f"向量相似性搜索完成，返回 {len(results)} 个结果")
            return results

        except Exception as e:
            logger.error(f"向量相似性搜索失败: {str(e)}")
            return []

    def save_index(self, index_path: Optional[str] = None) -> None:
        """
        保存向量索引

        Args:
            index_path: 保存路径，如果为None则使用初始化时的路径
        """
        if not self.vector_store:
            logger.warning("没有向量存储可以保存")
            return

        save_path = index_path or self.index_path
        if not save_path:
            logger.warning("未指定保存路径")
            return

        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            # 保存FAISS索引
            self.vector_store.save_local(save_path)

            logger.info(f"向量索引已保存到: {save_path}")

        except Exception as e:
            logger.error(f"保存向量索引失败: {str(e)}")
            raise

    def load_index(self, index_path: Optional[str] = None) -> None:
        """
        加载向量索引

        Args:
            index_path: 索引路径，如果为None则使用初始化时的路径
        """
        load_path = index_path or self.index_path
        if not load_path:
            logger.warning("未指定加载路径")
            return

        if not os.path.exists(load_path):
            logger.warning(f"索引文件不存在: {load_path}")
            return

        try:
            # 加载FAISS索引
            self.vector_store = FAISS.load_local(
                folder_path=load_path, embeddings=self.embeddings
            )

            logger.info(f"向量索引已从 {load_path} 加载")

        except Exception as e:
            logger.error(f"加载向量索引失败: {str(e)}")
            raise

    def get_index_info(self) -> Dict[str, Any]:
        """
        获取索引信息

        Returns:
            索引信息字典
        """
        if not self.vector_store:
            return {"status": "未初始化"}

        try:
            # 获取索引统计信息
            index = self.vector_store.index
            info = {
                "status": "已初始化",
                "total_documents": index.ntotal if hasattr(index, "ntotal") else "未知",
                "dimension": index.d if hasattr(index, "d") else "未知",
                "index_type": type(index).__name__,
            }

            return info

        except Exception as e:
            logger.error(f"获取索引信息失败: {str(e)}")
            return {"status": "错误", "error": str(e)}

    def delete_index(self) -> None:
        """删除向量索引"""
        if self.index_path and os.path.exists(self.index_path):
            try:
                import shutil

                shutil.rmtree(self.index_path)
                logger.info(f"索引已删除: {self.index_path}")
            except Exception as e:
                logger.error(f"删除索引失败: {str(e)}")

        self.vector_store = None
