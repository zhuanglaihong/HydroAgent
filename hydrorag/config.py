"""
Author: zhuanglaihong
Date: 2024-09-24 15:30:00
LastEditTime: 2025-09-27 15:00:00
LastEditors: zhuanglaihong
Description: 配置管理模块，管理RAG系统的各种配置参数
FilePath: \HydroAgent\hydrorag\config.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """RAG系统配置类"""

    # 路径配置
    documents_dir: str = "./documents"
    raw_documents_dir: str = "./documents/raw"
    processed_documents_dir: str = "./documents/processed"
    vector_db_dir: str = "./documents/vector_db"

    # 嵌入模型配置
    embedding_model_name: str = "text-embedding-v1"  # 默认使用API模型
    embedding_device: str = "cpu"  # 或 "cuda" 如果有GPU

    # API嵌入模型配置（优先级1）
    openai_api_key: Optional[str] = None  # Qwen API密钥
    openai_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    api_embedding_model: str = "text-embedding-v1"  # API嵌入模型名称

    # Ollama配置（优先级2，备用）
    ollama_base_url: str = "http://localhost:11434"
    local_embedding_model: str = "bge-large:335m"  # 本地嵌入模型

    # Chroma配置
    chroma_collection_name: str = "hydro_knowledge"
    chroma_distance_function: str = "cosine"  # cosine, l2, ip

    # 文档处理配置
    chunk_size: int = 500
    chunk_overlap: int = 50
    supported_file_extensions: List[str] = None

    # 检索配置
    top_k: int = 5
    score_threshold: float = 0.5

    # LLM配置（用于生成回答）
    llm_model: str = "granite3-dense:8b"
    llm_temperature: float = 0.1
    llm_base_url: str = "http://localhost:11434"

    def __post_init__(self):
        """初始化后处理"""
        if self.supported_file_extensions is None:
            self.supported_file_extensions = [
                ".txt",
                ".md",
                ".markdown",
                ".rst",
                ".pdf",
                ".docx",
                ".doc",
                ".py",
                ".yaml",
                ".yml",
                ".json",
            ]

        # 从环境变量或definitions_private.py获取API密钥
        if not self.openai_api_key:
            self.openai_api_key = os.getenv(
                "OPENAI_API_KEY"
            ) or self._load_from_private_config("OPENAI_API_KEY")

        # 确保路径存在
        self._ensure_directories()

    def _load_from_private_config(self, key: str) -> Optional[str]:
        """从definitions_private.py加载配置"""
        try:
            import definitions_private

            return getattr(definitions_private, key, None)
        except ImportError:
            logger.warning("无法导入definitions_private.py，请确保已正确配置")
            return None
        except AttributeError:
            logger.warning(f"在definitions_private.py中未找到{key}配置")
            return None

    def _ensure_directories(self):
        """确保必要的目录存在"""
        dirs_to_create = [
            self.documents_dir,
            self.raw_documents_dir,
            self.processed_documents_dir,
            self.vector_db_dir,
        ]

        for dir_path in dirs_to_create:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
            logger.debug(f"确保目录存在: {dir_path}")

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "Config":
        """从字典创建配置"""
        return cls(**config_dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "documents_dir": self.documents_dir,
            "raw_documents_dir": self.raw_documents_dir,
            "processed_documents_dir": self.processed_documents_dir,
            "vector_db_dir": self.vector_db_dir,
            "embedding_model_name": self.embedding_model_name,
            "embedding_device": self.embedding_device,
            "openai_api_key": "***" if self.openai_api_key else None,  # 隐藏API密钥
            "openai_base_url": self.openai_base_url,
            "api_embedding_model": self.api_embedding_model,
            "ollama_base_url": self.ollama_base_url,
            "local_embedding_model": self.local_embedding_model,
            "chroma_collection_name": self.chroma_collection_name,
            "chroma_distance_function": self.chroma_distance_function,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "supported_file_extensions": self.supported_file_extensions,
            "top_k": self.top_k,
            "score_threshold": self.score_threshold,
            "llm_model": self.llm_model,
            "llm_temperature": self.llm_temperature,
            "llm_base_url": self.llm_base_url,
        }

    def save_to_file(self, file_path: str):
        """保存配置到文件"""
        import json

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"配置已保存到: {file_path}")

    @classmethod
    def load_from_file(cls, file_path: str) -> "Config":
        """从文件加载配置"""
        import json

        with open(file_path, "r", encoding="utf-8") as f:
            config_dict = json.load(f)
        logger.info(f"配置已从文件加载: {file_path}")
        return cls.from_dict(config_dict)

    def update(self, **kwargs):
        """更新配置"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
                logger.info(f"配置已更新: {key} = {value}")
            else:
                logger.warning(f"未知配置项: {key}")

    def validate(self) -> bool:
        """验证配置有效性"""
        try:
            # 检查路径是否存在
            for dir_attr in [
                "documents_dir",
                "raw_documents_dir",
                "processed_documents_dir",
            ]:
                dir_path = getattr(self, dir_attr)
                if not Path(dir_path).exists():
                    logger.error(f"路径不存在: {dir_path}")
                    return False

            # 检查参数范围
            if self.chunk_size <= 0:
                logger.error("chunk_size 必须大于0")
                return False

            if self.chunk_overlap < 0:
                logger.error("chunk_overlap 不能小于0")
                return False

            if self.chunk_overlap >= self.chunk_size:
                logger.error("chunk_overlap 不能大于等于 chunk_size")
                return False

            if self.top_k <= 0:
                logger.error("top_k 必须大于0")
                return False

            if not 0 <= self.score_threshold <= 1:
                logger.error("score_threshold 必须在0-1之间")
                return False

            logger.info("配置验证通过")
            return True

        except Exception as e:
            logger.error(f"配置验证失败: {e}")
            return False


def create_default_config() -> Config:
    """创建默认配置，从definitions_private.py加载API配置"""
    config = Config()

    # 从definitions_private.py加载配置
    try:
        import definitions_private as dp

        if hasattr(dp, "OPENAI_API_KEY"):
            config.openai_api_key = dp.OPENAI_API_KEY
        if hasattr(dp, "OPENAI_BASE_URL"):
            config.openai_base_url = dp.OPENAI_BASE_URL
        if hasattr(dp, "KNOWLEDGE_BASE_DIR"):
            # 更新文档路径
            base_dir = dp.KNOWLEDGE_BASE_DIR
            config.documents_dir = base_dir
            config.raw_documents_dir = f"{base_dir}/raw"
            config.processed_documents_dir = f"{base_dir}/processed"
            config.vector_db_dir = f"{base_dir}/vector_db"

    except ImportError:
        logger.warning("无法导入definitions_private.py，使用默认配置")

    return config


# 默认配置实例
default_config = create_default_config()
