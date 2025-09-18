"""
配置管理模块
管理RAG系统的各种配置参数
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
    embedding_model_name: str = "bge-large:335m"  # 优先使用本地Ollama模型
    embedding_device: str = "cpu"  # 或 "cuda" 如果有GPU
    
    # Ollama配置
    ollama_base_url: str = "http://localhost:11434"
    prefer_ollama: bool = True  # 是否优先使用Ollama模型
    
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
                ".txt", ".md", ".markdown", ".rst", 
                ".pdf", ".docx", ".doc", ".py", ".yaml", ".yml", ".json"
            ]
        
        # 确保路径存在
        self._ensure_directories()
    
    def _ensure_directories(self):
        """确保必要的目录存在"""
        dirs_to_create = [
            self.documents_dir,
            self.raw_documents_dir,
            self.processed_documents_dir,
            self.vector_db_dir
        ]
        
        for dir_path in dirs_to_create:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
            logger.info(f"确保目录存在: {dir_path}")
    
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
            "ollama_base_url": self.ollama_base_url,
            "prefer_ollama": self.prefer_ollama,
            "chroma_collection_name": self.chroma_collection_name,
            "chroma_distance_function": self.chroma_distance_function,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "supported_file_extensions": self.supported_file_extensions,
            "top_k": self.top_k,
            "score_threshold": self.score_threshold,
            "llm_model": self.llm_model,
            "llm_temperature": self.llm_temperature,
            "llm_base_url": self.llm_base_url
        }
    
    def save_to_file(self, file_path: str):
        """保存配置到文件"""
        import json
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"配置已保存到: {file_path}")
    
    @classmethod
    def load_from_file(cls, file_path: str) -> "Config":
        """从文件加载配置"""
        import json
        with open(file_path, 'r', encoding='utf-8') as f:
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
            for dir_attr in ["documents_dir", "raw_documents_dir", "processed_documents_dir"]:
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


# 默认配置实例
default_config = Config()
