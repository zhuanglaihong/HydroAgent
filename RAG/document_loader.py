"""
Author: zhuanglaihong
Date: 2025-07-24 15:03:46
LastEditTime: 2025-07-24 15:03:46
LastEditors: zhuanglaihong
Description: 文档加载器模块 - 支持多种文档格式的加载和预处理
FilePath: RAG/document_loader.py
Copyright: Copyright (c) 2021-2024 zhuanglaihong. All rights reserved.
"""

import os
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging

from langchain_community.document_loaders import (
    TextLoader,
    CSVLoader,
    PyPDFLoader,
    UnstructuredWordDocumentLoader,
    UnstructuredExcelLoader,
    JSONLoader,
)
from langchain.text_splitter import (
    RecursiveCharacterTextSplitter,
    CharacterTextSplitter,
)
from langchain.schema import Document

logger = logging.getLogger(__name__)


class DocumentLoader:
    """文档加载器类"""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        """
        初始化文档加载器

        Args:
            chunk_size: 文档分块大小
            chunk_overlap: 分块重叠大小
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""],
        )

    def load_document(self, file_path: str) -> List[Document]:
        """
        加载单个文档

        Args:
            file_path: 文档路径

        Returns:
            文档列表
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        file_extension = file_path.suffix.lower()

        try:
            if file_extension == ".txt":
                loader = TextLoader(str(file_path), encoding="utf-8")
            elif file_extension == ".csv":
                loader = CSVLoader(str(file_path), encoding="utf-8")
            elif file_extension == ".pdf":
                loader = PyPDFLoader(str(file_path))
            elif file_extension in [".doc", ".docx"]:
                loader = UnstructuredWordDocumentLoader(str(file_path))
            elif file_extension in [".xls", ".xlsx"]:
                loader = UnstructuredExcelLoader(str(file_path))
            elif file_extension == ".json":
                loader = JSONLoader(
                    file_path=str(file_path), jq_schema=".", text_content=False
                )
            else:
                # 默认使用文本加载器
                loader = TextLoader(str(file_path), encoding="utf-8")

            documents = loader.load()
            logger.info(f"成功加载文档: {file_path}, 文档数量: {len(documents)}")
            return documents

        except Exception as e:
            logger.error(f"加载文档失败: {file_path}, 错误: {str(e)}")
            raise

    def load_directory(
        self, directory_path: str, file_extensions: Optional[List[str]] = None
    ) -> List[Document]:
        """
        加载目录中的所有文档

        Args:
            directory_path: 目录路径
            file_extensions: 支持的文件扩展名列表，如果为None则支持所有常见格式

        Returns:
            文档列表
        """
        if file_extensions is None:
            file_extensions = [
                ".txt",
                ".csv",
                ".pdf",
                ".doc",
                ".docx",
                ".xls",
                ".xlsx",
                ".json",
            ]

        directory_path = Path(directory_path)
        if not directory_path.exists():
            raise FileNotFoundError(f"目录不存在: {directory_path}")

        all_documents = []

        for file_path in directory_path.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in file_extensions:
                try:
                    documents = self.load_document(str(file_path))
                    all_documents.extend(documents)
                except Exception as e:
                    logger.warning(f"跳过文件 {file_path}: {str(e)}")
                    continue

        logger.info(f"从目录 {directory_path} 加载了 {len(all_documents)} 个文档")
        return all_documents

    def split_documents(self, documents: List[Document]) -> List[Document]:
        """
        将文档分割成小块

        Args:
            documents: 原始文档列表

        Returns:
            分割后的文档列表
        """
        if not documents:
            return []

        split_docs = self.text_splitter.split_documents(documents)
        logger.info(f"将 {len(documents)} 个文档分割成 {len(split_docs)} 个块")
        return split_docs

    def add_metadata(
        self, documents: List[Document], metadata: Dict[str, Any]
    ) -> List[Document]:
        """
        为文档添加元数据

        Args:
            documents: 文档列表
            metadata: 要添加的元数据

        Returns:
            添加了元数据的文档列表
        """
        for doc in documents:
            doc.metadata.update(metadata)
        return documents

    def filter_documents(
        self, documents: List[Document], min_length: int = 50, max_length: int = 10000
    ) -> List[Document]:
        """
        过滤文档（按长度）

        Args:
            documents: 文档列表
            min_length: 最小长度
            max_length: 最大长度

        Returns:
            过滤后的文档列表
        """
        filtered_docs = []
        for doc in documents:
            if min_length <= len(doc.page_content) <= max_length:
                filtered_docs.append(doc)

        logger.info(
            f"过滤后保留 {len(filtered_docs)} 个文档（原始 {len(documents)} 个）"
        )
        return filtered_docs
