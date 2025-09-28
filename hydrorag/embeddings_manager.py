"""
Author: zhuanglaihong
Date: 2024-09-24 15:30:00
LastEditTime: 2025-09-27 15:00:00
LastEditors: zhuanglaihong
Description: 嵌入模型管理器，负责管理文本嵌入模型，提供文本向量化功能
FilePath: \HydroAgent\hydrorag\embeddings_manager.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import logging
from typing import List, Optional, Dict, Any
import numpy as np
from pathlib import Path
import time

logger = logging.getLogger(__name__)


class QwenAPIEmbeddings:
    """
    Qwen API嵌入模型包装器
    兼容LangChain嵌入接口
    """

    def __init__(self, client, model: str = "text-embedding-v1", max_retries: int = 3, retry_delay: float = 1.0):
        """
        初始化Qwen API嵌入模型

        Args:
            client: OpenAI客户端实例
            model: 嵌入模型名称
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
        """
        self.client = client
        self.model = model
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def embed_query(self, text: str) -> List[float]:
        """
        对查询文本进行嵌入

        Args:
            text: 输入文本

        Returns:
            List[float]: 嵌入向量
        """
        return self._get_embedding(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        对多个文档进行嵌入

        Args:
            texts: 文本列表

        Returns:
            List[List[float]]: 嵌入向量列表
        """
        embeddings = []
        for text in texts:
            embedding = self._get_embedding(text)
            embeddings.append(embedding)
        return embeddings

    def _get_embedding(self, text: str) -> List[float]:
        """
        获取单个文本的嵌入向量，包含重试逻辑

        Args:
            text: 输入文本

        Returns:
            List[float]: 嵌入向量
        """
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.embeddings.create(
                    input=text,
                    model=self.model
                )
                return response.data[0].embedding

            except Exception as e:
                if attempt < self.max_retries:
                    logger.warning(f"API调用失败 (尝试 {attempt + 1}/{self.max_retries + 1}): {e}")
                    time.sleep(self.retry_delay * (2 ** attempt))  # 指数退避
                else:
                    logger.error(f"API调用最终失败: {e}")
                    raise


class EmbeddingsManager:
    """嵌入模型管理器 - 管理文本嵌入模型和向量化功能"""
    
    def __init__(self, config):
        """
        初始化嵌入模型管理器
        
        Args:
            config: 配置对象
        """
        self.config = config
        self.model = None
        self.model_name = config.embedding_model_name
        self.device = getattr(config, 'embedding_device', 'cpu')

        # API配置
        self.api_key = getattr(config, 'openai_api_key', None)
        self.api_base_url = getattr(config, 'openai_base_url', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
        self.api_model = getattr(config, 'api_embedding_model', 'text-embedding-v1')
        
        # 初始化嵌入模型
        self._initialize_model()
        
        logger.info(f"嵌入模型管理器初始化完成")
        logger.info(f"模型: {self.model_name}")
        logger.info(f"设备: {self.device}")
    
    def _initialize_model(self):
        """初始化嵌入模型 - 优先使用Qwen API，失败时切换到本地Ollama"""
        try:
            logger.info(f"正在初始化嵌入模型: {self.model_name}")

            # 优先级1: 尝试使用Qwen API嵌入模型
            if self._try_qwen_api_embeddings():
                logger.info("成功使用Qwen API嵌入模型")
                return

            logger.warning("Qwen API不可用，尝试本地Ollama模型")

            # 优先级2: 尝试使用本地Ollama嵌入模型
            if self._try_ollama_embeddings():
                logger.info("成功使用本地Ollama嵌入模型")
                return

            logger.error("所有嵌入模型都不可用")
            self.model = None

        except Exception as e:
            logger.error(f"嵌入模型初始化失败: {e}")
            self.model = None
    
    def _try_qwen_api_embeddings(self) -> bool:
        """尝试使用Qwen API嵌入模型"""
        try:
            logger.info("尝试连接Qwen API嵌入模型...")

            # 检查是否有必要的配置
            if not self.api_key:
                logger.warning("未配置Qwen API密钥，跳过API模式")
                return False

            # 导入OpenAI客户端
            try:
                from openai import OpenAI
            except ImportError:
                logger.warning("无法导入OpenAI客户端，跳过API模式")
                return False

            # 创建OpenAI客户端（用于Qwen API）
            client = OpenAI(
                api_key=self.api_key,
                base_url=self.api_base_url
            )

            # 创建API嵌入包装器
            self.model = QwenAPIEmbeddings(
                client=client,
                model=self.api_model
            )

            logger.info("Qwen API嵌入模型初始化成功")

            # 测试模型
            test_result = self._test_model()
            if test_result:
                logger.info("Qwen API嵌入模型测试通过")
                self.model_name = f"qwen-api-{self.api_model}"
                return True
            else:
                logger.error("Qwen API嵌入模型测试失败")
                self.model = None
                return False

        except Exception as e:
            logger.warning(f"Qwen API嵌入模型初始化失败: {e}")
            self.model = None
            return False

    def _try_ollama_embeddings(self) -> bool:
        """尝试使用本地Ollama嵌入模型"""
        try:
            logger.info("尝试连接本地Ollama嵌入模型...")
            
            # 尝试导入langchain-ollama
            try:
                from langchain_ollama import OllamaEmbeddings
            except ImportError:
                # 回退到langchain_community
                try:
                    from langchain_community.embeddings import OllamaEmbeddings
                except ImportError:
                    logger.warning("无法导入OllamaEmbeddings，跳过Ollama嵌入模型")
                    return False
            
            # 检查可用的嵌入模型
            available_models = self._check_ollama_models()

            embedding_model = None
            # 按优先级查找嵌入模型
            preferred_models = [
                "nomic-embed-text",  # 优先使用nomic-embed-text
                "mxbai-embed-large",  # 次选mxbai-embed-large
                "bge-large:335m",
                "bge-large",
                "all-minilm",
                "sentence-transformers"
            ]

            for preferred in preferred_models:
                matching_models = [model for model in available_models if preferred.lower() in model.lower()]
                if matching_models:
                    embedding_model = matching_models[0]
                    logger.info(f"找到优选嵌入模型: {embedding_model}")
                    break

            if not embedding_model:
                # 查找其他可用的嵌入模型
                embedding_models = [model for model in available_models if any(name in model.lower() for name in ['embed', 'bge', 'sentence', 'gte', 'nomic'])]
                if embedding_models:
                    embedding_model = embedding_models[0]
                    logger.info(f"找到其他嵌入模型: {embedding_model}")
                else:
                    logger.warning("未找到可用的Ollama嵌入模型")
                    return False
            
            # 初始化Ollama嵌入模型
            self.model = OllamaEmbeddings(
                model=embedding_model,
                base_url=getattr(self.config, 'ollama_base_url', "http://localhost:11434")
            )
            
            logger.info(f"Ollama嵌入模型初始化成功: {embedding_model}")
            
            # 测试模型
            test_result = self._test_model()
            if test_result:
                logger.info("Ollama嵌入模型测试通过")
                self.model_name = f"ollama-{embedding_model}"
                return True
            else:
                logger.error("Ollama嵌入模型测试失败")
                self.model = None
                return False
                
        except Exception as e:
            logger.warning(f"Ollama嵌入模型初始化失败: {e}")
            self.model = None
            return False
    
    def _check_ollama_models(self) -> list:
        """检查可用的Ollama模型"""
        try:
            import requests
            
            # 请求Ollama API获取模型列表
            base_url = getattr(self.config, 'ollama_base_url', "http://localhost:11434")
            response = requests.get(f"{base_url}/api/tags", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                models = [model['name'] for model in data.get('models', [])]
                logger.info(f"发现Ollama模型: {models}")
                return models
            else:
                logger.warning(f"获取Ollama模型列表失败: HTTP {response.status_code}")
                return []
                
        except requests.exceptions.ConnectionError:
            base_url = getattr(self.config, 'ollama_base_url', "http://localhost:11434")
            logger.warning(f"无法连接到Ollama服务（{base_url}）")
            return []
        except Exception as e:
            logger.warning(f"检查Ollama模型时出错: {e}")
            return []
    
    def _test_model(self) -> bool:
        """测试嵌入模型"""
        try:
            if not self.model:
                return False
            
            # 测试文本
            test_text = "这是一个测试文本"
            
            # 生成嵌入向量
            embedding = self.model.embed_query(test_text)
            
            # 检查向量格式
            if isinstance(embedding, list) and len(embedding) > 0:
                logger.info(f"嵌入向量维度: {len(embedding)}")
                return True
            else:
                logger.error("嵌入向量格式不正确")
                return False
                
        except Exception as e:
            logger.error(f"测试嵌入模型失败: {e}")
            return False
    
    def embed_text(self, text: str) -> Optional[List[float]]:
        """
        对单个文本进行嵌入
        
        Args:
            text: 输入文本
            
        Returns:
            List[float]: 嵌入向量，失败时返回None
        """
        try:
            if not self.model:
                logger.error("嵌入模型未初始化")
                return None
            
            if not text or not text.strip():
                logger.warning("输入文本为空")
                return None
            
            # 生成嵌入向量
            embedding = self.model.embed_query(text.strip())
            
            if isinstance(embedding, list):
                return embedding
            else:
                logger.error(f"嵌入向量格式不正确: {type(embedding)}")
                return None
                
        except Exception as e:
            logger.error(f"文本嵌入失败: {e}")
            return None
    
    def embed_texts(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        对多个文本进行批量嵌入
        
        Args:
            texts: 文本列表
            
        Returns:
            List[Optional[List[float]]]: 嵌入向量列表
        """
        try:
            if not self.model:
                logger.error("嵌入模型未初始化")
                return [None] * len(texts)
            
            if not texts:
                logger.warning("输入文本列表为空")
                return []
            
            # 过滤空文本
            valid_texts = []
            text_indices = []
            
            for i, text in enumerate(texts):
                if text and text.strip():
                    valid_texts.append(text.strip())
                    text_indices.append(i)
            
            if not valid_texts:
                logger.warning("没有有效的文本")
                return [None] * len(texts)
            
            logger.info(f"开始批量嵌入 {len(valid_texts)} 个文本")
            
            # 批量生成嵌入向量
            embeddings = self.model.embed_documents(valid_texts)
            
            # 构建结果列表
            results = [None] * len(texts)
            for i, embedding in enumerate(embeddings):
                original_index = text_indices[i]
                if isinstance(embedding, list):
                    results[original_index] = embedding
                else:
                    logger.error(f"嵌入向量格式不正确: {type(embedding)}")
                    results[original_index] = None
            
            success_count = sum(1 for r in results if r is not None)
            logger.info(f"批量嵌入完成，成功 {success_count}/{len(texts)} 个")
            
            return results
            
        except Exception as e:
            logger.error(f"批量文本嵌入失败: {e}")
            return [None] * len(texts)
    
    def embed_documents_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        对文档块进行嵌入处理
        
        Args:
            chunks: 文档块列表，每个块包含content字段
            
        Returns:
            List[Dict[str, Any]]: 包含嵌入向量的文档块列表
        """
        try:
            logger.info(f"开始对 {len(chunks)} 个文档块进行嵌入处理")
            
            # 提取文本内容
            texts = [chunk.get("content", "") for chunk in chunks]
            
            # 批量嵌入
            embeddings = self.embed_texts(texts)
            
            # 将嵌入向量添加到文档块中
            processed_chunks = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                processed_chunk = chunk.copy()
                
                if embedding is not None:
                    processed_chunk["embedding"] = embedding
                    processed_chunk["embedding_model"] = self.model_name
                    processed_chunk["has_embedding"] = True
                else:
                    processed_chunk["embedding"] = None
                    processed_chunk["embedding_model"] = None
                    processed_chunk["has_embedding"] = False
                    logger.warning(f"文档块 {i} 嵌入失败")
                
                processed_chunks.append(processed_chunk)
            
            success_count = sum(1 for chunk in processed_chunks if chunk.get("has_embedding", False))
            logger.info(f"文档块嵌入完成，成功 {success_count}/{len(chunks)} 个")
            
            return processed_chunks
            
        except Exception as e:
            logger.error(f"文档块嵌入处理失败: {e}")
            # 返回原始块，但标记嵌入失败
            return [
                {**chunk, "embedding": None, "has_embedding": False}
                for chunk in chunks
            ]
    
    def calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        计算两个嵌入向量的相似度
        
        Args:
            embedding1: 第一个嵌入向量
            embedding2: 第二个嵌入向量
            
        Returns:
            float: 余弦相似度，范围[-1, 1]
        """
        try:
            if not embedding1 or not embedding2:
                return 0.0
            
            if len(embedding1) != len(embedding2):
                logger.error("嵌入向量维度不匹配")
                return 0.0
            
            # 转换为numpy数组
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)
            
            # 计算余弦相似度
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            return float(similarity)
            
        except Exception as e:
            logger.error(f"计算相似度失败: {e}")
            return 0.0
    
    def find_most_similar(
        self, 
        query_embedding: List[float], 
        candidate_embeddings: List[List[float]], 
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        找到最相似的嵌入向量
        
        Args:
            query_embedding: 查询向量
            candidate_embeddings: 候选向量列表
            top_k: 返回前k个最相似的
            
        Returns:
            List[Dict[str, Any]]: 相似度结果列表
        """
        try:
            if not query_embedding or not candidate_embeddings:
                return []
            
            similarities = []
            
            for i, candidate in enumerate(candidate_embeddings):
                similarity = self.calculate_similarity(query_embedding, candidate)
                similarities.append({
                    "index": i,
                    "similarity": similarity
                })
            
            # 按相似度排序
            similarities.sort(key=lambda x: x["similarity"], reverse=True)
            
            # 返回前k个
            return similarities[:top_k]
            
        except Exception as e:
            logger.error(f"查找相似向量失败: {e}")
            return []
    
    def save_embeddings(self, embeddings: List[List[float]], file_path: str):
        """
        保存嵌入向量到文件
        
        Args:
            embeddings: 嵌入向量列表
            file_path: 保存路径
        """
        try:
            import pickle
            
            data = {
                "embeddings": embeddings,
                "model_name": self.model_name,
                "embedding_dim": len(embeddings[0]) if embeddings else 0,
                "count": len(embeddings)
            }
            
            with open(file_path, 'wb') as f:
                pickle.dump(data, f)
            
            logger.info(f"嵌入向量已保存到: {file_path}")
            
        except Exception as e:
            logger.error(f"保存嵌入向量失败: {e}")
    
    def load_embeddings(self, file_path: str) -> Optional[List[List[float]]]:
        """
        从文件加载嵌入向量
        
        Args:
            file_path: 文件路径
            
        Returns:
            List[List[float]]: 嵌入向量列表
        """
        try:
            import pickle
            
            with open(file_path, 'rb') as f:
                data = pickle.load(f)
            
            embeddings = data.get("embeddings", [])
            model_name = data.get("model_name", "")
            
            if model_name != self.model_name:
                logger.warning(f"加载的嵌入向量使用的模型({model_name})与当前模型({self.model_name})不同")
            
            logger.info(f"从文件加载了 {len(embeddings)} 个嵌入向量")
            return embeddings
            
        except Exception as e:
            logger.error(f"加载嵌入向量失败: {e}")
            return None
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "is_initialized": self.model is not None,
            "model_type": type(self.model).__name__ if self.model else None
        }
    
    def is_available(self) -> bool:
        """检查嵌入模型是否可用"""
        return self.model is not None
    
    def get_embedding_dimension(self) -> int:
        """获取嵌入向量维度"""
        try:
            if not self.model:
                return 0
            
            # 用简单文本测试获取维度
            test_embedding = self.embed_text("test")
            return len(test_embedding) if test_embedding else 0
            
        except Exception as e:
            logger.error(f"获取嵌入维度失败: {e}")
            return 0
