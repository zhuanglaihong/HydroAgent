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
import signal
from threading import Thread, Event
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

logger = logging.getLogger(__name__)


class QwenAPIEmbeddings:
    """
    Qwen API嵌入模型包装器
    兼容LangChain嵌入接口
    """

    def __init__(
        self,
        client,
        model: str = "text-embedding-v1",
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
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
                response = self.client.embeddings.create(input=text, model=self.model)
                return response.data[0].embedding

            except Exception as e:
                if attempt < self.max_retries:
                    logger.warning(
                        f"API调用失败 (尝试 {attempt + 1}/{self.max_retries + 1}): {e}"
                    )
                    time.sleep(self.retry_delay * (2**attempt))  # 指数退避
                else:
                    logger.error(f"API调用最终失败: {e}")
                    raise


class EmbeddingsManager:
    """嵌入模型管理器 - 管理文本嵌入模型和向量化功能，支持API优先和自动降级"""

    def __init__(self, config):
        """
        初始化嵌入模型管理器

        Args:
            config: 配置对象
        """
        self.config = config
        self.api_model = None
        self.ollama_model = None
        self.current_model = None
        self.current_model_type = None  # 'api' or 'ollama'

        # 从config中读取参数
        self.use_api_first = getattr(config, "EMBEDDING_USE_API_FIRST", True)
        self.api_timeout = getattr(config, "EMBEDDING_API_TIMEOUT", 30)
        self.ollama_timeout = getattr(config, "EMBEDDING_FALLBACK_TIMEOUT", 60)
        self.auto_fallback = getattr(config, "EMBEDDING_AUTO_FALLBACK", True)

        # API配置
        self.api_key = getattr(config, "openai_api_key", None)
        self.api_base_url = getattr(
            config,
            "openai_base_url",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        self.api_model_name = getattr(
            config, "EMBEDDING_API_MODEL", "text-embedding-v1"
        )

        # Ollama配置
        self.ollama_model_name = getattr(
            config, "EMBEDDING_FALLBACK_MODEL", "bge-large:335m"
        )
        self.ollama_base_url = getattr(
            config, "ollama_base_url", "http://localhost:11434"
        )
        self.device = getattr(config, "EMBEDDING_DEVICE", "cpu")

        # 状态跟踪
        self.api_available = False
        self.ollama_available = False
        self.last_api_failure_time = 0
        self.api_retry_interval = 300  # 5分钟后重试API

        # 初始化模型
        self._initialize_models()

        logger.info(f"嵌入模型管理器初始化完成")
        logger.info(f"API模型可用: {self.api_available}")
        logger.info(f"Ollama模型可用: {self.ollama_available}")
        logger.info(f"当前使用: {self.current_model_type}")

    def _initialize_models(self):
        """初始化嵌入模型 - 同时尝试初始化API和Ollama模型"""
        try:
            logger.info("正在初始化嵌入模型...")

            # 并行初始化API和Ollama模型
            with ThreadPoolExecutor(max_workers=2) as executor:
                api_future = (
                    executor.submit(self._try_qwen_api_embeddings)
                    if self.use_api_first
                    else None
                )
                ollama_future = executor.submit(self._try_ollama_embeddings)

                # 等待API模型初始化（如果启用）
                if api_future:
                    try:
                        self.api_available = api_future.result(timeout=10)
                    except Exception as e:
                        logger.warning(f"API模型初始化失败: {e}")
                        self.api_available = False

                # 等待Ollama模型初始化
                try:
                    self.ollama_available = ollama_future.result(timeout=10)
                except Exception as e:
                    logger.warning(f"Ollama模型初始化失败: {e}")
                    self.ollama_available = False

            # 设置当前模型
            self._set_current_model()

            if not self.api_available and not self.ollama_available:
                logger.error("所有嵌入模型都不可用")

        except Exception as e:
            logger.error(f"嵌入模型初始化失败: {e}")
            self.api_available = False
            self.ollama_available = False

    def _set_current_model(self):
        """设置当前使用的模型"""
        if self.use_api_first and self.api_available:
            self.current_model = self.api_model
            self.current_model_type = "api"
            logger.info("当前使用API嵌入模型")
        elif self.ollama_available:
            self.current_model = self.ollama_model
            self.current_model_type = "ollama"
            logger.info("当前使用Ollama嵌入模型")
        else:
            self.current_model = None
            self.current_model_type = None
            logger.warning("没有可用的嵌入模型")

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
            client = OpenAI(api_key=self.api_key, base_url=self.api_base_url)

            # 创建API嵌入包装器
            self.api_model = QwenAPIEmbeddings(
                client=client,
                model=self.api_model_name,
                max_retries=1,  # 降低重试次数以快速失败
                retry_delay=0.5,
            )

            logger.info("Qwen API嵌入模型初始化成功")

            # 测试模型
            test_result = self._test_model_with_timeout(self.api_model, timeout=5)
            if test_result:
                logger.info("Qwen API嵌入模型测试通过")
                return True
            else:
                logger.error("Qwen API嵌入模型测试失败")
                self.api_model = None
                return False

        except Exception as e:
            logger.warning(f"Qwen API嵌入模型初始化失败: {e}")
            self.api_model = None
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
                self.ollama_model_name,  # 首先尝试配置中指定的模型
                "nomic-embed-text",
                "mxbai-embed-large",
                "bge-large:335m",
                "bge-large",
                "all-minilm",
            ]

            for preferred in preferred_models:
                matching_models = [
                    model
                    for model in available_models
                    if preferred.lower() in model.lower()
                ]
                if matching_models:
                    embedding_model = matching_models[0]
                    logger.info(f"找到嵌入模型: {embedding_model}")
                    break

            if not embedding_model:
                # 查找其他可用的嵌入模型
                embedding_models = [
                    model
                    for model in available_models
                    if any(
                        name in model.lower()
                        for name in ["embed", "bge", "sentence", "gte", "nomic"]
                    )
                ]
                if embedding_models:
                    embedding_model = embedding_models[0]
                    logger.info(f"找到其他嵌入模型: {embedding_model}")
                else:
                    logger.warning("未找到可用的Ollama嵌入模型")
                    return False

            # 初始化Ollama嵌入模型
            self.ollama_model = OllamaEmbeddings(
                model=embedding_model, base_url=self.ollama_base_url
            )

            logger.info(f"Ollama嵌入模型初始化成功: {embedding_model}")

            # 测试模型
            test_result = self._test_model_with_timeout(self.ollama_model, timeout=5)
            if test_result:
                logger.info("Ollama嵌入模型测试通过")
                return True
            else:
                logger.error("Ollama嵌入模型测试失败")
                self.ollama_model = None
                return False

        except Exception as e:
            logger.warning(f"Ollama嵌入模型初始化失败: {e}")
            self.ollama_model = None
            return False

    def _check_ollama_models(self) -> list:
        """检查可用的Ollama模型"""
        try:
            import requests

            # 请求Ollama API获取模型列表
            response = requests.get(f"{self.ollama_base_url}/api/tags", timeout=5)

            if response.status_code == 200:
                data = response.json()
                models = [model["name"] for model in data.get("models", [])]
                logger.info(f"发现Ollama模型: {models}")
                return models
            else:
                logger.warning(f"获取Ollama模型列表失败: HTTP {response.status_code}")
                return []

        except requests.exceptions.ConnectionError:
            logger.warning(f"无法连接到Ollama服务（{self.ollama_base_url}）")
            return []
        except Exception as e:
            logger.warning(f"检查Ollama模型时出错: {e}")
            return []

    def _test_model_with_timeout(self, model, timeout: int = 5) -> bool:
        """带超时的测试嵌入模型"""
        try:
            if not model:
                return False

            # 测试文本
            test_text = "这是一个测试文本"

            # 使用线程池执行测试，避免阻塞
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(model.embed_query, test_text)
                try:
                    embedding = future.result(timeout=timeout)

                    # 检查向量格式
                    if isinstance(embedding, list) and len(embedding) > 0:
                        logger.info(f"嵌入向量维度: {len(embedding)}")
                        return True
                    else:
                        logger.error("嵌入向量格式不正确")
                        return False

                except FutureTimeoutError:
                    logger.error(f"模型测试超时（{timeout}秒）")
                    return False

        except Exception as e:
            logger.error(f"测试嵌入模型失败: {e}")
            return False

    def embed_text(self, text: str) -> Optional[List[float]]:
        """
        对单个文本进行嵌入（支持超时和自动降级）

        Args:
            text: 输入文本

        Returns:
            List[float]: 嵌入向量，失败时返回None
        """
        try:
            if not text or not text.strip():
                logger.warning("输入文本为空")
                return None

            text = text.strip()

            # 检查是否需要切换模型
            self._check_and_switch_model()

            if not self.current_model:
                logger.error("没有可用的嵌入模型")
                return None

            # 尝试使用当前模型
            if self.current_model_type == "api":
                return self._embed_with_timeout(
                    self.current_model, text, self.api_timeout
                )
            elif self.current_model_type == "ollama":
                return self._embed_with_timeout(
                    self.current_model, text, self.ollama_timeout
                )
            else:
                logger.error("未知的模型类型")
                return None

        except Exception as e:
            logger.error(f"文本嵌入失败: {e}")
            # 尝试切换到备用模型
            if self.auto_fallback:
                return self._try_fallback_embedding(text)
            return None

    def _embed_with_timeout(
        self, model, text: str, timeout: int
    ) -> Optional[List[float]]:
        """带超时的嵌入处理"""
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(model.embed_query, text)
                try:
                    embedding = future.result(timeout=timeout)

                    if isinstance(embedding, list) and len(embedding) > 0:
                        return embedding
                    else:
                        logger.error(f"嵌入向量格式不正确: {type(embedding)}")
                        return None

                except FutureTimeoutError:
                    logger.error(f"嵌入请求超时（{timeout}秒）")
                    # 记录API失败时间
                    if self.current_model_type == "api":
                        self.last_api_failure_time = time.time()
                    return None

        except Exception as e:
            logger.error(f"嵌入处理失败: {e}")
            if self.current_model_type == "api":
                self.last_api_failure_time = time.time()
            return None

    def _try_fallback_embedding(self, text: str) -> Optional[List[float]]:
        """尝试使用备用模型"""
        try:
            if self.current_model_type == "api" and self.ollama_available:
                logger.info("API失败，切换到Ollama模型")
                self.current_model = self.ollama_model
                self.current_model_type = "ollama"
                return self._embed_with_timeout(
                    self.current_model, text, self.ollama_timeout
                )
            elif self.current_model_type == "ollama" and self.api_available:
                # 检查API是否已经冷却
                if time.time() - self.last_api_failure_time > self.api_retry_interval:
                    logger.info("Ollama失败，重试API模型")
                    self.current_model = self.api_model
                    self.current_model_type = "api"
                    return self._embed_with_timeout(
                        self.current_model, text, self.api_timeout
                    )

            logger.error("所有嵌入模型都不可用")
            return None

        except Exception as e:
            logger.error(f"备用模型嵌入失败: {e}")
            return None

    def _check_and_switch_model(self):
        """检查并切换模型（如果需要）"""
        try:
            # 如果当前没有模型，尝试重新初始化
            if not self.current_model:
                self._set_current_model()

            # 如果使用API优先策略，检查是否需要重试API
            if (
                self.use_api_first
                and self.current_model_type == "ollama"
                and self.api_available
                and time.time() - self.last_api_failure_time > self.api_retry_interval
            ):
                logger.info("尝试重新使用API模型")
                self.current_model = self.api_model
                self.current_model_type = "api"

        except Exception as e:
            logger.error(f"模型切换检查失败: {e}")

    def embed_texts(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        对多个文本进行批量嵌入（支持超时和自动降级）

        Args:
            texts: 文本列表

        Returns:
            List[Optional[List[float]]]: 嵌入向量列表
        """
        try:
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

            # 检查并设置当前模型
            self._check_and_switch_model()

            if not self.current_model:
                logger.error("没有可用的嵌入模型")
                return [None] * len(texts)

            # 批量生成嵌入向量
            embeddings = self._embed_documents_with_timeout(valid_texts)

            # 构建结果列表
            results = [None] * len(texts)
            for i, embedding in enumerate(embeddings):
                original_index = text_indices[i]
                if isinstance(embedding, list) and len(embedding) > 0:
                    results[original_index] = embedding
                else:
                    results[original_index] = None

            success_count = sum(1 for r in results if r is not None)
            logger.info(f"批量嵌入完成，成功 {success_count}/{len(texts)} 个")

            return results

        except Exception as e:
            logger.error(f"批量文本嵌入失败: {e}")
            return [None] * len(texts)

    def _embed_documents_with_timeout(
        self, texts: List[str]
    ) -> List[Optional[List[float]]]:
        """带超时的批量文档嵌入"""
        try:
            if self.current_model_type == "api":
                timeout = self.api_timeout
            elif self.current_model_type == "ollama":
                timeout = self.ollama_timeout
            else:
                timeout = 30  # 默认超时

            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self.current_model.embed_documents, texts)
                try:
                    embeddings = future.result(timeout=timeout)

                    # 验证结果
                    if isinstance(embeddings, list) and len(embeddings) == len(texts):
                        return embeddings
                    else:
                        logger.error(
                            f"批量嵌入结果格式错误: {type(embeddings)}, 长度: {len(embeddings) if isinstance(embeddings, list) else 'N/A'}"
                        )
                        return [None] * len(texts)

                except FutureTimeoutError:
                    logger.error(f"批量嵌入请求超时（{timeout}秒）")
                    # 记录API失败时间
                    if self.current_model_type == "api":
                        self.last_api_failure_time = time.time()

                    # 尝试使用备用模型
                    if self.auto_fallback:
                        return self._try_fallback_batch_embedding(texts)
                    return [None] * len(texts)

        except Exception as e:
            logger.error(f"批量嵌入处理失败: {e}")
            if self.current_model_type == "api":
                self.last_api_failure_time = time.time()

            # 尝试使用备用模型
            if self.auto_fallback:
                return self._try_fallback_batch_embedding(texts)
            return [None] * len(texts)

    def _try_fallback_batch_embedding(
        self, texts: List[str]
    ) -> List[Optional[List[float]]]:
        """尝试使用备用模型进行批量嵌入"""
        try:
            if self.current_model_type == "api" and self.ollama_available:
                logger.info("API批量嵌入失败，切换到Ollama模型")
                self.current_model = self.ollama_model
                self.current_model_type = "ollama"
                return self._embed_documents_with_timeout(texts)
            elif self.current_model_type == "ollama" and self.api_available:
                # 检查API是否已经冷却
                if time.time() - self.last_api_failure_time > self.api_retry_interval:
                    logger.info("Ollama批量嵌入失败，重试API模型")
                    self.current_model = self.api_model
                    self.current_model_type = "api"
                    return self._embed_documents_with_timeout(texts)

            logger.error("所有模型都不可用于批量嵌入")
            return [None] * len(texts)

        except Exception as e:
            logger.error(f"备用批量嵌入失败: {e}")
            return [None] * len(texts)

    def embed_documents_chunks(
        self, chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        对文档块进行嵌入处理（支持超时和自动降级）

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
                    processed_chunk["embedding_model"] = self._get_current_model_name()
                    processed_chunk["has_embedding"] = True
                else:
                    processed_chunk["embedding"] = None
                    processed_chunk["embedding_model"] = None
                    processed_chunk["has_embedding"] = False
                    logger.warning(f"文档块 {i} 嵌入失败")

                processed_chunks.append(processed_chunk)

            success_count = sum(
                1 for chunk in processed_chunks if chunk.get("has_embedding", False)
            )
            logger.info(f"文档块嵌入完成，成功 {success_count}/{len(chunks)} 个")

            return processed_chunks

        except Exception as e:
            logger.error(f"文档块嵌入处理失败: {e}")
            # 返回原始块，但标记嵌入失败
            return [
                {**chunk, "embedding": None, "has_embedding": False} for chunk in chunks
            ]

    def _get_current_model_name(self) -> str:
        """获取当前使用的模型名称"""
        if self.current_model_type == "api":
            return f"api-{self.api_model_name}"
        elif self.current_model_type == "ollama":
            return f"ollama-{self.ollama_model_name}"
        else:
            return "unknown"

    def calculate_similarity(
        self, embedding1: List[float], embedding2: List[float]
    ) -> float:
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
        top_k: int = 5,
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
                similarities.append({"index": i, "similarity": similarity})

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
                "count": len(embeddings),
            }

            with open(file_path, "wb") as f:
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

            with open(file_path, "rb") as f:
                data = pickle.load(f)

            embeddings = data.get("embeddings", [])
            model_name = data.get("model_name", "")

            if model_name != self.model_name:
                logger.warning(
                    f"加载的嵌入向量使用的模型({model_name})与当前模型({self.model_name})不同"
                )

            logger.info(f"从文件加载了 {len(embeddings)} 个嵌入向量")
            return embeddings

        except Exception as e:
            logger.error(f"加载嵌入向量失败: {e}")
            return None

    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            "current_model_type": self.current_model_type,
            "api_available": self.api_available,
            "ollama_available": self.ollama_available,
            "api_model_name": self.api_model_name,
            "ollama_model_name": self.ollama_model_name,
            "device": self.device,
            "use_api_first": self.use_api_first,
            "auto_fallback": self.auto_fallback,
            "api_timeout": self.api_timeout,
            "ollama_timeout": self.ollama_timeout,
        }

    def is_available(self) -> bool:
        """检查嵌入模型是否可用"""
        return self.api_available or self.ollama_available

    def get_embedding_dimension(self) -> int:
        """获取嵌入向量维度"""
        try:
            if not self.current_model:
                return 0

            # 用简单文本测试获取维度
            test_embedding = self.embed_text("test")
            return len(test_embedding) if test_embedding else 0

        except Exception as e:
            logger.error(f"获取嵌入维度失败: {e}")
            return 0
