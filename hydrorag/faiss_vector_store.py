"""
Author: zhuanglaihong
Date: 2025-09-29 16:00:00
LastEditTime: 2025-09-29 16:00:00
LastEditors: zhuanglaihong
Description: FAISS向量数据库管理器，提供高效的向量存储和检索功能，支持多级检索和重排序优化
FilePath: \HydroAgent\hydrorag\faiss_vector_store.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import logging
import os
import json
import pickle
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime
import uuid
import time

logger = logging.getLogger(__name__)


class FaissVectorStore:
    """FAISS向量数据库管理器 - 基于FAISS的向量存储和检索，支持多级检索和重排序"""

    def __init__(self, config, embeddings_manager):
        """
        初始化FAISS向量数据库管理器

        Args:
            config: 配置对象
            embeddings_manager: 嵌入模型管理器
        """
        self.config = config
        self.embeddings_manager = embeddings_manager

        # 从配置中读取参数
        self.db_path = Path(getattr(config, "vector_db_dir", "./vector_db"))
        self.index_file = self.db_path / getattr(
            config, "VECTOR_INDEX_FILE", "faiss_index.index"
        )
        self.metadata_file = self.db_path / getattr(
            config, "VECTOR_METADATA_FILE", "metadata.json"
        )

        # FAISS配置
        self.index_type = getattr(config, "FAISS_INDEX_TYPE", "Flat")
        self.distance_function = getattr(
            config, "VECTOR_DB_DISTANCE_FUNCTION", "cosine"
        )
        self.ivf_nlist = getattr(config, "FAISS_IVF_NLIST", 100)
        self.hnsw_m = getattr(config, "FAISS_HNSW_M", 16)
        self.hnsw_ef_search = getattr(config, "FAISS_HNSW_EF_SEARCH", 64)
        self.enable_gpu = getattr(config, "FAISS_ENABLE_GPU", False)

        # 重排序配置
        self.rerank_enabled = getattr(config, "RERANK_ENABLED", True)
        self.rerank_top_k = getattr(config, "RERANK_TOP_K_CANDIDATES", 20)

        # 初始化
        self.index = None
        self.documents = []  # 存储文档内容
        self.metadata = []  # 存储元数据
        self.dimension = None

        # 确保目录存在
        self.db_path.mkdir(parents=True, exist_ok=True)

        # 尝试加载现有索引
        self._initialize_index()

        logger.info(f"FAISS向量数据库管理器初始化完成")
        logger.info(f"数据库路径: {self.db_path}")
        logger.info(f"索引类型: {self.index_type}")
        logger.info(f"距离函数: {self.distance_function}")
        logger.info(f"文档数量: {len(self.documents)}")

    def _initialize_index(self):
        """初始化或加载FAISS索引"""
        try:
            # 尝试加载现有索引
            if self.index_file.exists() and self.metadata_file.exists():
                logger.info("发现现有索引，尝试加载...")
                if self._load_index():
                    logger.info(f"成功加载现有索引，包含 {len(self.documents)} 个文档")
                    return
                else:
                    logger.warning("加载现有索引失败，将创建新索引")

            # 创建新索引（延迟初始化，等待第一个文档确定维度）
            logger.info("将在添加第一个文档时创建新索引")

        except Exception as e:
            logger.error(f"初始化FAISS索引失败: {e}")
            self.index = None

    def _create_index(self, dimension: int):
        """创建FAISS索引"""
        try:
            import faiss

            logger.info(f"创建FAISS索引，维度: {dimension}, 类型: {self.index_type}")

            if self.index_type == "Flat":
                # 精确搜索索引
                if self.distance_function == "cosine":
                    # 余弦相似度使用内积+归一化
                    self.index = faiss.IndexFlatIP(dimension)
                elif self.distance_function == "l2":
                    self.index = faiss.IndexFlatL2(dimension)
                else:
                    # 默认使用内积
                    self.index = faiss.IndexFlatIP(dimension)

            elif self.index_type == "IVF":
                # 倒排文件索引
                nlist = min(self.ivf_nlist, max(1, len(self.documents) // 10))

                if self.distance_function == "cosine":
                    quantizer = faiss.IndexFlatIP(dimension)
                    self.index = faiss.IndexIVFFlat(quantizer, dimension, nlist)
                elif self.distance_function == "l2":
                    quantizer = faiss.IndexFlatL2(dimension)
                    self.index = faiss.IndexIVFFlat(quantizer, dimension, nlist)
                else:
                    quantizer = faiss.IndexFlatIP(dimension)
                    self.index = faiss.IndexIVFFlat(quantizer, dimension, nlist)

            elif self.index_type == "HNSW":
                # 分层导航小世界图索引
                self.index = faiss.IndexHNSWFlat(dimension, self.hnsw_m)
                self.index.hnsw.efSearch = self.hnsw_ef_search

            else:
                logger.warning(f"不支持的索引类型 {self.index_type}，使用Flat索引")
                self.index = faiss.IndexFlatIP(dimension)

            # GPU加速（如果启用且可用）
            if self.enable_gpu:
                try:
                    import faiss

                    if faiss.get_num_gpus() > 0:
                        logger.info("启用GPU加速")
                        self.index = faiss.index_cpu_to_gpu(
                            faiss.StandardGpuResources(), 0, self.index
                        )
                    else:
                        logger.warning("未找到GPU，使用CPU索引")
                except Exception as e:
                    logger.warning(f"GPU加速初始化失败: {e}")

            self.dimension = dimension
            logger.info(f"FAISS索引创建成功，类型: {type(self.index).__name__}")

        except ImportError:
            logger.error(
                "FAISS库未安装，请安装: pip install faiss-cpu 或 pip install faiss-gpu"
            )
            raise
        except Exception as e:
            logger.error(f"创建FAISS索引失败: {e}")
            raise

    def add_documents(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        添加文档块到向量数据库

        Args:
            chunks: 文档块列表

        Returns:
            Dict[str, Any]: 添加结果
        """
        try:
            if not chunks:
                logger.warning("没有文档块需要添加")
                return {"status": "no_documents", "added": 0}

            logger.info(f"开始添加 {len(chunks)} 个文档块到FAISS向量数据库")

            # 确保文档块有嵌入向量
            chunks_with_embeddings = self._ensure_embeddings(chunks)

            # 过滤有效的文档块
            valid_chunks = []
            embeddings_list = []

            for chunk in chunks_with_embeddings:
                if (
                    chunk.get("content")
                    and chunk.get("content").strip()
                    and chunk.get("has_embedding", False)
                    and chunk.get("embedding")
                ):

                    valid_chunks.append(chunk)
                    embeddings_list.append(chunk["embedding"])

            if not valid_chunks:
                logger.error("没有有效的文档块（缺少内容或嵌入向量）")
                return {"status": "error", "error": "没有有效的文档内容或嵌入向量"}

            logger.info(f"有效文档块: {len(valid_chunks)}")

            # 转换嵌入向量为numpy数组
            embeddings_array = np.array(embeddings_list, dtype=np.float32)

            # 检查嵌入向量维度
            if self.dimension is None:
                self.dimension = embeddings_array.shape[1]
                self._create_index(self.dimension)
            elif embeddings_array.shape[1] != self.dimension:
                logger.error(
                    f"嵌入向量维度不匹配: 期望 {self.dimension}, 实际 {embeddings_array.shape[1]}"
                )
                return {"status": "error", "error": "嵌入向量维度不匹配"}

            # 归一化向量（用于余弦相似度）
            if self.distance_function == "cosine":
                embeddings_array = self._normalize_vectors(embeddings_array)

            # 训练索引（如果需要）
            if hasattr(self.index, "is_trained") and not self.index.is_trained:
                logger.info("训练FAISS索引...")
                self.index.train(embeddings_array)

            # 添加向量到索引
            start_id = len(self.documents)
            self.index.add(embeddings_array)

            # 更新文档和元数据存储
            for i, chunk in enumerate(valid_chunks):
                # 生成唯一ID
                doc_id = f"{start_id + i:08d}_{uuid.uuid4().hex[:8]}"

                # 准备元数据
                metadata = {
                    "id": doc_id,
                    "chunk_id": chunk.get("chunk_id", ""),
                    "source_file": chunk.get("source_file", ""),
                    "chunk_index": chunk.get("chunk_index", 0),
                    "chunk_size": chunk.get("chunk_size", 0),
                    "embedding_model": chunk.get("embedding_model", ""),
                    "added_time": datetime.now().isoformat(),
                    "original_metadata": chunk.get("metadata", {}),
                }

                self.documents.append(chunk["content"])
                self.metadata.append(metadata)

            # 保存索引
            self._save_index()

            logger.info(f"成功添加 {len(valid_chunks)} 个文档块到FAISS向量数据库")

            return {
                "status": "success",
                "added": len(valid_chunks),
                "skipped": len(chunks) - len(valid_chunks),
                "total_count": len(self.documents),
            }

        except Exception as e:
            logger.error(f"添加文档块失败: {e}")
            return {"status": "error", "error": str(e)}

    def _ensure_embeddings(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """确保文档块有嵌入向量"""
        try:
            if self.embeddings_manager is None:
                logger.warning("嵌入管理器不可用，跳过嵌入向量生成")
                for chunk in chunks:
                    chunk["has_embedding"] = False
                    chunk["embedding"] = None
                return chunks

            # 检查哪些块缺少嵌入向量
            chunks_need_embedding = []
            for chunk in chunks:
                if not chunk.get("has_embedding", False) or not chunk.get("embedding"):
                    chunks_need_embedding.append(chunk)

            if chunks_need_embedding:
                logger.info(f"{len(chunks_need_embedding)} 个文档块需要生成嵌入向量")
                # 使用嵌入管理器生成嵌入向量
                chunks_with_embeddings = self.embeddings_manager.embed_documents_chunks(
                    chunks_need_embedding
                )

                # 更新原始列表
                chunk_map = {
                    chunk.get("chunk_id", ""): chunk for chunk in chunks_with_embeddings
                }
                for i, chunk in enumerate(chunks):
                    chunk_id = chunk.get("chunk_id", "")
                    if chunk_id in chunk_map:
                        chunks[i] = chunk_map[chunk_id]

            return chunks

        except Exception as e:
            logger.error(f"生成嵌入向量失败: {e}")
            return chunks

    def _normalize_vectors(self, vectors: np.ndarray) -> np.ndarray:
        """归一化向量"""
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1  # 避免除零
        return vectors / norms

    def query(
        self,
        query_text: str,
        n_results: int = 5,
        score_threshold: float = 0.0,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        查询相似文档（支持多级检索和重排序）

        Args:
            query_text: 查询文本
            n_results: 返回结果数量
            score_threshold: 分数阈值
            where: 元数据过滤条件（暂未实现）

        Returns:
            Dict[str, Any]: 查询结果
        """
        try:
            if not self.index or len(self.documents) == 0:
                logger.warning("索引为空或未初始化")
                return {"status": "error", "error": "索引为空或未初始化"}

            if not query_text or not query_text.strip():
                logger.warning("查询文本为空")
                return {"status": "error", "error": "查询文本为空"}

            logger.info(f"查询FAISS向量数据库: {query_text[:100]}...")

            # 生成查询向量
            query_embedding = self.embeddings_manager.embed_text(query_text.strip())
            if not query_embedding:
                logger.error("无法生成查询向量")
                return {"status": "error", "error": "查询向量生成失败"}

            # 转换为numpy数组并归一化
            query_vector = np.array([query_embedding], dtype=np.float32)
            if self.distance_function == "cosine":
                query_vector = self._normalize_vectors(query_vector)

            # 第一阶段：粗排（获取更多候选）
            search_k = (
                min(n_results * 3, len(self.documents))
                if self.rerank_enabled
                else n_results
            )
            distances, indices = self.index.search(query_vector, search_k)

            # 处理搜索结果
            candidates = []
            for i, (distance, idx) in enumerate(zip(distances[0], indices[0])):
                if idx < 0 or idx >= len(self.documents):
                    continue

                # 转换距离为相似度分数
                if self.distance_function == "cosine":
                    score = float(distance)  # FAISS IP已经是相似度
                elif self.distance_function == "l2":
                    score = 1.0 / (1.0 + float(distance))
                else:
                    score = float(distance)

                if score >= score_threshold:
                    candidates.append(
                        {
                            "content": self.documents[idx],
                            "score": score,
                            "distance": float(distance),
                            "metadata": self.metadata[idx],
                            "index": idx,
                            "rank": i + 1,
                        }
                    )

            if not candidates:
                return {
                    "status": "success",
                    "query": query_text,
                    "documents": [],
                    "scores": [],
                    "metadatas": [],
                    "distances": [],
                    "total_found": 0,
                }

            # 第二阶段：重排序（如果启用）
            if self.rerank_enabled and len(candidates) > n_results:
                logger.debug(f"开始重排序，候选数量: {len(candidates)}")
                candidates = self._rerank_results(query_text, candidates)

            # 限制结果数量
            final_results = candidates[:n_results]

            # 构建返回结果
            result = {
                "status": "success",
                "query": query_text,
                "documents": [item["content"] for item in final_results],
                "scores": [item["score"] for item in final_results],
                "metadatas": [item["metadata"] for item in final_results],
                "distances": [item["distance"] for item in final_results],
                "total_found": len(final_results),
            }

            logger.info(f"查询完成，返回 {len(final_results)} 个结果")
            return result

        except Exception as e:
            logger.error(f"查询失败: {e}")
            return {"status": "error", "error": str(e)}

    def _rerank_results(
        self, query: str, candidates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """重排序结果（基于文本相似度和多样性）"""
        try:
            # 计算文本相似度分数
            query_lower = query.lower()
            query_words = set(query_lower.split())

            for candidate in candidates:
                content_lower = candidate["content"].lower()
                content_words = set(content_lower.split())

                # 词汇重叠分数
                if query_words and content_words:
                    word_overlap = len(query_words & content_words) / len(
                        query_words | content_words
                    )
                else:
                    word_overlap = 0.0

                # 子串匹配分数
                substring_score = 0.0
                for word in query_words:
                    if len(word) > 2 and word in content_lower:
                        substring_score += 1.0
                substring_score = (
                    substring_score / len(query_words) if query_words else 0.0
                )

                # 长度惩罚（过短或过长的文本）
                content_len = len(candidate["content"])
                length_penalty = 1.0
                if content_len < 100:
                    length_penalty = content_len / 100.0
                elif content_len > 2000:
                    length_penalty = 2000.0 / content_len

                # 组合分数
                text_score = (
                    word_overlap * 0.4 + substring_score * 0.6
                ) * length_penalty

                # 结合向量相似度和文本相似度
                candidate["rerank_score"] = candidate["score"] * 0.7 + text_score * 0.3

            # 按重排序分数排序
            candidates.sort(key=lambda x: x["rerank_score"], reverse=True)

            # 多样性过滤（避免过于相似的结果）
            diverse_results = []
            used_sources = set()

            for candidate in candidates:
                source_file = candidate["metadata"].get("source_file", "")
                chunk_id = candidate["metadata"].get("chunk_id", "")

                # 检查源文件多样性（每个文件最多选择一定数量的块）
                source_count = sum(
                    1
                    for r in diverse_results
                    if r["metadata"].get("source_file") == source_file
                )

                if source_count < 2:  # 每个源文件最多2个结果
                    diverse_results.append(candidate)

                if len(diverse_results) >= len(candidates):
                    break

            logger.debug(f"重排序完成，从 {len(candidates)} 个候选中优化选择")
            return diverse_results

        except Exception as e:
            logger.error(f"重排序失败: {e}")
            return candidates  # 返回原始结果

    def _save_index(self):
        """保存FAISS索引和元数据"""
        try:
            if self.index is None:
                return

            import faiss

            # 保存FAISS索引
            # 如果是GPU索引，先转换为CPU
            index_to_save = self.index
            if hasattr(self.index, "index"):  # GPU索引
                index_to_save = faiss.index_gpu_to_cpu(self.index)

            faiss.write_index(index_to_save, str(self.index_file))

            # 保存元数据
            metadata_info = {
                "documents": self.documents,
                "metadata": self.metadata,
                "dimension": self.dimension,
                "index_type": self.index_type,
                "distance_function": self.distance_function,
                "total_documents": len(self.documents),
                "last_updated": datetime.now().isoformat(),
                "config": {
                    "ivf_nlist": self.ivf_nlist,
                    "hnsw_m": self.hnsw_m,
                    "hnsw_ef_search": self.hnsw_ef_search,
                    "enable_gpu": self.enable_gpu,
                },
            }

            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump(metadata_info, f, ensure_ascii=False, indent=2)

            logger.debug(f"索引已保存: {self.index_file}")

        except Exception as e:
            logger.error(f"保存索引失败: {e}")

    def _load_index(self) -> bool:
        """加载FAISS索引和元数据"""
        try:
            import faiss

            # 加载元数据
            with open(self.metadata_file, "r", encoding="utf-8") as f:
                metadata_info = json.load(f)

            self.documents = metadata_info.get("documents", [])
            self.metadata = metadata_info.get("metadata", [])
            self.dimension = metadata_info.get("dimension")

            # 验证数据一致性
            if len(self.documents) != len(self.metadata):
                logger.error("文档和元数据数量不匹配")
                return False

            # 加载FAISS索引
            self.index = faiss.read_index(str(self.index_file))

            # 检查索引文档数量
            if self.index.ntotal != len(self.documents):
                logger.error(
                    f"索引中的文档数量({self.index.ntotal})与元数据不匹配({len(self.documents)})"
                )
                return False

            # GPU加速（如果启用）
            if self.enable_gpu:
                try:
                    if faiss.get_num_gpus() > 0:
                        self.index = faiss.index_cpu_to_gpu(
                            faiss.StandardGpuResources(), 0, self.index
                        )
                        logger.info("索引已转移到GPU")
                except Exception as e:
                    logger.warning(f"GPU转换失败: {e}")

            logger.info(
                f"成功加载索引: {len(self.documents)} 个文档, 维度: {self.dimension}"
            )
            return True

        except Exception as e:
            logger.error(f"加载索引失败: {e}")
            return False

    def clear_collection(self) -> Dict[str, Any]:
        """清空集合"""
        try:
            current_count = len(self.documents)

            # 清空内存数据
            self.documents = []
            self.metadata = []
            self.index = None
            self.dimension = None

            # 删除文件
            if self.index_file.exists():
                self.index_file.unlink()
            if self.metadata_file.exists():
                self.metadata_file.unlink()

            logger.info(f"集合已清空，删除了 {current_count} 个文档")

            return {"status": "success", "deleted": current_count, "remaining_count": 0}

        except Exception as e:
            logger.error(f"清空集合失败: {e}")
            return {"status": "error", "error": str(e)}

    def get_statistics(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        try:
            # 分析元数据
            source_files = set()
            embedding_models = set()

            for metadata in self.metadata:
                if metadata.get("source_file"):
                    source_files.add(metadata["source_file"])
                if metadata.get("embedding_model"):
                    embedding_models.add(metadata["embedding_model"])

            return {
                "index_type": self.index_type,
                "total_documents": len(self.documents),
                "dimension": self.dimension,
                "distance_function": self.distance_function,
                "database_path": str(self.db_path),
                "index_file": str(self.index_file),
                "unique_source_files": len(source_files),
                "embedding_models": list(embedding_models),
                "sample_source_files": list(source_files)[:5],
                "config": {
                    "ivf_nlist": self.ivf_nlist,
                    "hnsw_m": self.hnsw_m,
                    "hnsw_ef_search": self.hnsw_ef_search,
                    "enable_gpu": self.enable_gpu,
                    "rerank_enabled": self.rerank_enabled,
                },
            }

        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {"error": str(e)}

    def backup_collection(self, backup_path: str) -> Dict[str, Any]:
        """备份集合数据"""
        try:
            logger.info(f"开始备份集合到: {backup_path}")

            backup_data = {
                "documents": self.documents,
                "metadata": self.metadata,
                "dimension": self.dimension,
                "index_type": self.index_type,
                "distance_function": self.distance_function,
                "backup_time": datetime.now().isoformat(),
                "total_documents": len(self.documents),
            }

            # 保存备份数据
            backup_file = Path(backup_path)
            backup_file.parent.mkdir(parents=True, exist_ok=True)

            with open(backup_file, "w", encoding="utf-8") as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)

            # 备份索引文件
            if self.index_file.exists():
                index_backup = backup_file.with_suffix(".index")
                import shutil

                shutil.copy2(self.index_file, index_backup)

            logger.info(f"备份完成，包含 {len(self.documents)} 个文档")

            return {
                "status": "success",
                "backup_file": str(backup_file),
                "document_count": len(self.documents),
            }

        except Exception as e:
            logger.error(f"备份失败: {e}")
            return {"status": "error", "error": str(e)}

    def is_available(self) -> bool:
        """检查向量数据库是否可用"""
        try:
            import faiss

            return True
        except ImportError:
            return False

    def get_document_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取文档"""
        try:
            for i, metadata in enumerate(self.metadata):
                if metadata.get("id") == doc_id:
                    return {
                        "id": doc_id,
                        "document": self.documents[i],
                        "metadata": metadata,
                    }
            return None

        except Exception as e:
            logger.error(f"获取文档失败: {e}")
            return None

    def delete_documents(self, where: Dict[str, Any]) -> Dict[str, Any]:
        """删除文档（暂未实现）"""
        logger.warning("FAISS不支持直接删除文档，需要重建索引")
        return {"status": "not_supported", "error": "FAISS不支持直接删除文档"}

    def restore_collection(self, backup_path: str) -> Dict[str, Any]:
        """从备份恢复集合数据"""
        try:
            logger.info(f"从备份恢复集合: {backup_path}")

            # 读取备份文件
            with open(backup_path, "r", encoding="utf-8") as f:
                backup_data = json.load(f)

            # 清空当前数据
            self.clear_collection()

            # 恢复数据
            self.documents = backup_data.get("documents", [])
            self.metadata = backup_data.get("metadata", [])
            self.dimension = backup_data.get("dimension")
            self.index_type = backup_data.get("index_type", self.index_type)
            self.distance_function = backup_data.get(
                "distance_function", self.distance_function
            )

            # 恢复索引文件
            backup_file = Path(backup_path)
            index_backup = backup_file.with_suffix(".index")
            if index_backup.exists():
                import shutil

                shutil.copy2(index_backup, self.index_file)
                self._load_index()

            restored_count = len(self.documents)
            logger.info(f"恢复完成，恢复了 {restored_count} 个文档")

            return {
                "status": "success",
                "restored_count": restored_count,
                "backup_time": backup_data.get("backup_time", ""),
                "current_count": len(self.documents),
            }

        except Exception as e:
            logger.error(f"恢复失败: {e}")
            return {"status": "error", "error": str(e)}
