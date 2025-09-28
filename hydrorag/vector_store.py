"""
Author: zhuanglaihong
Date: 2024-09-24 15:30:00
LastEditTime: 2025-09-27 15:00:00
LastEditors: zhuanglaihong
Description: 向量数据库管理器，基于ChromaDB提供高效的向量存储和检索功能
FilePath: \HydroAgent\hydrorag\vector_store.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import logging
import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class VectorStore:
    """向量数据库管理器 - 基于Chroma的向量存储和检索"""
    
    def __init__(self, config, embeddings_manager):
        """
        初始化向量数据库管理器

        Args:
            config: 配置对象
            embeddings_manager: 嵌入模型管理器，可以为None
        """
        self.config = config
        self.embeddings_manager = embeddings_manager
        self.db_path = Path(config.vector_db_dir)
        self.collection_name = config.chroma_collection_name

        # Chroma客户端和集合
        self.client = None
        self.collection = None

        # 确保数据库目录存在
        self.db_path.mkdir(parents=True, exist_ok=True)

        # 初始化Chroma（即使嵌入管理器为None也尝试初始化）
        self._initialize_chroma()

        if self.embeddings_manager is None:
            logger.warning("嵌入管理器为None，向量功能将受限")

        logger.info(f"向量数据库管理器初始化完成")
        logger.info(f"数据库路径: {self.db_path}")
        logger.info(f"集合名称: {self.collection_name}")
    
    def _initialize_chroma(self):
        """初始化Chroma向量数据库"""
        try:
            logger.info("正在初始化Chroma向量数据库")
            
            # 导入Chroma
            import chromadb
            from chromadb.config import Settings
            
            # 创建Chroma客户端
            self.client = chromadb.PersistentClient(
                path=str(self.db_path),
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # 创建或获取集合
            try:
                self.collection = self.client.get_collection(
                    name=self.collection_name
                )
                logger.info(f"找到现有集合: {self.collection_name}")
                
            except Exception:
                # 集合不存在，创建新集合
                logger.info(f"创建新集合: {self.collection_name}")
                
                # 定义距离函数
                distance_function = self.config.chroma_distance_function
                if distance_function not in ["cosine", "l2", "ip"]:
                    logger.warning(f"不支持的距离函数: {distance_function}，使用默认的cosine")
                    distance_function = "cosine"
                
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": distance_function}
                )
                
                logger.info(f"集合创建成功，距离函数: {distance_function}")
            
            # 获取集合信息
            collection_info = self._get_collection_info()
            logger.info(f"集合信息: {collection_info}")
            
        except ImportError as e:
            logger.error(f"无法导入Chroma: {e}")
            logger.error("请安装chromadb: pip install chromadb")
            self.client = None
            self.collection = None
            
        except Exception as e:
            logger.error(f"初始化Chroma失败: {e}")
            self.client = None
            self.collection = None
    
    def _get_collection_info(self) -> Dict[str, Any]:
        """获取集合信息"""
        try:
            if not self.collection:
                return {"error": "集合未初始化"}
            
            count = self.collection.count()
            metadata = self.collection.metadata
            
            return {
                "name": self.collection_name,
                "count": count,
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"获取集合信息失败: {e}")
            return {"error": str(e)}
    
    def add_documents(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        添加文档块到向量数据库
        
        Args:
            chunks: 文档块列表
            
        Returns:
            Dict[str, Any]: 添加结果
        """
        try:
            if not self.collection:
                logger.error("向量数据库未初始化")
                return {"status": "error", "error": "数据库未初始化"}
            
            if not chunks:
                logger.warning("没有文档块需要添加")
                return {"status": "no_documents", "added": 0}
            
            logger.info(f"开始添加 {len(chunks)} 个文档块到向量数据库")
            
            # 确保文档块有嵌入向量
            chunks_with_embeddings = self._ensure_embeddings(chunks)
            
            # 过滤有效的文档块
            valid_chunks = []
            chunks_with_embeddings_count = 0

            for chunk in chunks_with_embeddings:
                # 检查块是否有内容
                if chunk.get("content") and chunk.get("content").strip():
                    valid_chunks.append(chunk)
                    if chunk.get("has_embedding", False):
                        chunks_with_embeddings_count += 1

            if not valid_chunks:
                logger.error("没有有效的文档块（缺少内容）")
                return {"status": "error", "error": "没有有效的文档内容"}

            if chunks_with_embeddings_count == 0 and self.embeddings_manager is not None:
                logger.warning("所有文档块都缺少嵌入向量，将仅存储文本和元数据")

            logger.info(f"有效文档块: {len(valid_chunks)}，其中 {chunks_with_embeddings_count} 个有嵌入向量")
            
            # 准备数据
            ids = []
            embeddings = []
            documents = []
            metadatas = []

            # 获取现有的所有ID（避免冲突）
            existing_ids = set()
            try:
                existing_data = self.collection.get()
                if existing_data and existing_data.get('ids'):
                    existing_ids = set(existing_data['ids'])
                    logger.debug(f"检测到现有文档ID数量: {len(existing_ids)}")
            except Exception as e:
                logger.debug(f"获取现有ID失败，假设数据库为空: {e}")

            for i, chunk in enumerate(valid_chunks):
                # 生成唯一ID
                base_chunk_id = chunk.get("chunk_id") or f"chunk_{uuid.uuid4().hex[:8]}"

                # 使用微秒级时间戳和递增索引确保唯一性
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]  # 毫秒精度
                full_id = f"{base_chunk_id}_{timestamp}_{i:03d}"

                # 如果ID仍然冲突，添加随机后缀
                while full_id in existing_ids:
                    random_suffix = uuid.uuid4().hex[:4]
                    full_id = f"{base_chunk_id}_{timestamp}_{i:03d}_{random_suffix}"

                existing_ids.add(full_id)  # 防止本批次内的重复
                ids.append(full_id)
                documents.append(chunk["content"])

                # 只有在有嵌入向量时才添加
                if chunk.get("has_embedding", False) and chunk.get("embedding"):
                    embeddings.append(chunk["embedding"])
                else:
                    # 没有嵌入向量时，添加None或不添加embeddings参数
                    embeddings.append(None)

                # 准备元数据
                metadata = {
                    "chunk_id": chunk.get("chunk_id", ""),
                    "source_file": chunk.get("source_file", ""),
                    "chunk_index": chunk.get("chunk_index", 0),
                    "chunk_size": chunk.get("chunk_size", 0),
                    "embedding_model": chunk.get("embedding_model", ""),
                    "added_time": datetime.now().isoformat(),
                    "has_embedding": chunk.get("has_embedding", False)
                }

                # 添加原始元数据
                if "metadata" in chunk:
                    metadata.update(chunk["metadata"])

                metadatas.append(metadata)

            # 批量添加到Chroma
            try:
                # 如果所有嵌入都是None，就不传递embeddings参数
                add_params = {
                    "ids": ids,
                    "documents": documents,
                    "metadatas": metadatas
                }

                # 只有当有有效嵌入时才添加embeddings参数
                valid_embeddings = [emb for emb in embeddings if emb is not None]
                if valid_embeddings and len(valid_embeddings) == len(embeddings):
                    add_params["embeddings"] = embeddings

                self.collection.add(**add_params)
            except Exception as e:
                # 如果添加失败，尝试仅添加文档和元数据
                logger.warning(f"带嵌入向量添加失败，尝试仅添加文档: {e}")
                self.collection.add(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas
                )
            
            logger.info(f"成功添加 {len(valid_chunks)} 个文档块到向量数据库")
            
            return {
                "status": "success",
                "added": len(valid_chunks),
                "skipped": len(chunks) - len(valid_chunks),
                "total_count": self.collection.count()
            }
            
        except Exception as e:
            logger.error(f"添加文档块失败: {e}")
            return {"status": "error", "error": str(e)}
    
    def _ensure_embeddings(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """确保文档块有嵌入向量"""
        try:
            # 如果没有嵌入管理器，跳过嵌入生成
            if self.embeddings_manager is None:
                logger.warning("嵌入管理器不可用，跳过嵌入向量生成")
                # 为所有块标记为没有嵌入
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

                # 生成嵌入向量
                chunks_with_embeddings = self.embeddings_manager.embed_documents_chunks(
                    chunks_need_embedding
                )

                # 更新原始列表
                chunk_map = {chunk.get("chunk_id", ""): chunk for chunk in chunks_with_embeddings}

                for i, chunk in enumerate(chunks):
                    chunk_id = chunk.get("chunk_id", "")
                    if chunk_id in chunk_map:
                        chunks[i] = chunk_map[chunk_id]

            return chunks

        except Exception as e:
            logger.error(f"生成嵌入向量失败: {e}")
            return chunks
    
    def query(
        self, 
        query_text: str, 
        n_results: int = 5, 
        score_threshold: float = 0.0,
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        查询相似文档
        
        Args:
            query_text: 查询文本
            n_results: 返回结果数量
            score_threshold: 分数阈值
            where: 元数据过滤条件
            
        Returns:
            Dict[str, Any]: 查询结果
        """
        try:
            if not self.collection:
                logger.error("向量数据库未初始化")
                return {"status": "error", "error": "数据库未初始化"}
            
            if not query_text or not query_text.strip():
                logger.warning("查询文本为空")
                return {"status": "error", "error": "查询文本为空"}
            
            logger.info(f"查询向量数据库: {query_text[:100]}...")
            
            # 生成查询向量
            query_embedding = self.embeddings_manager.embed_text(query_text.strip())
            
            if not query_embedding:
                logger.error("无法生成查询向量")
                return {"status": "error", "error": "查询向量生成失败"}
            
            # 执行查询
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where,
                include=["documents", "metadatas", "distances"]
            )
            
            # 处理结果
            processed_results = self._process_query_results(
                results, score_threshold, query_text
            )
            
            logger.info(f"查询完成，返回 {len(processed_results.get('documents', []))} 个结果")
            
            return processed_results
            
        except Exception as e:
            logger.error(f"查询失败: {e}")
            return {"status": "error", "error": str(e)}
    
    def _process_query_results(
        self, 
        raw_results: Dict[str, Any], 
        score_threshold: float,
        query_text: str
    ) -> Dict[str, Any]:
        """处理查询结果"""
        try:
            processed_results = {
                "status": "success",
                "query": query_text,
                "documents": [],
                "scores": [],
                "metadatas": [],
                "total_found": 0
            }
            
            if not raw_results or not raw_results.get("documents"):
                return processed_results
            
            # 提取结果
            documents = raw_results["documents"][0] if raw_results["documents"] else []
            metadatas = raw_results["metadatas"][0] if raw_results["metadatas"] else []
            distances = raw_results["distances"][0] if raw_results["distances"] else []
            
            # 转换距离为相似度分数
            for i, (doc, metadata, distance) in enumerate(zip(documents, metadatas, distances)):
                # 将距离转换为相似度（距离越小，相似度越高）
                if self.config.chroma_distance_function == "cosine":
                    # 余弦距离转换为相似度
                    score = 1 - distance
                elif self.config.chroma_distance_function == "l2":
                    # L2距离转换为相似度（简单的反向映射）
                    score = 1 / (1 + distance)
                else:
                    # 默认处理
                    score = 1 - distance
                
                # 应用分数阈值
                if score >= score_threshold:
                    processed_results["documents"].append(doc)
                    processed_results["scores"].append(float(score))
                    processed_results["metadatas"].append(metadata)
            
            processed_results["total_found"] = len(processed_results["documents"])
            
            return processed_results
            
        except Exception as e:
            logger.error(f"处理查询结果失败: {e}")
            return {"status": "error", "error": str(e)}
    
    def delete_documents(self, where: Dict[str, Any]) -> Dict[str, Any]:
        """
        删除文档
        
        Args:
            where: 删除条件
            
        Returns:
            Dict[str, Any]: 删除结果
        """
        try:
            if not self.collection:
                logger.error("向量数据库未初始化")
                return {"status": "error", "error": "数据库未初始化"}
            
            # 先查询要删除的文档
            query_result = self.collection.get(where=where)
            delete_count = len(query_result.get("ids", []))
            
            if delete_count == 0:
                logger.info("没有找到符合条件的文档")
                return {"status": "no_match", "deleted": 0}
            
            # 执行删除
            self.collection.delete(where=where)
            
            logger.info(f"删除了 {delete_count} 个文档")
            
            return {
                "status": "success",
                "deleted": delete_count,
                "remaining_count": self.collection.count()
            }
            
        except Exception as e:
            logger.error(f"删除文档失败: {e}")
            return {"status": "error", "error": str(e)}
    
    def clear_collection(self) -> Dict[str, Any]:
        """清空集合"""
        try:
            if not self.collection:
                logger.error("向量数据库未初始化")
                return {"status": "error", "error": "数据库未初始化"}
            
            # 获取当前文档数量
            current_count = self.collection.count()
            
            if current_count == 0:
                logger.info("集合已经为空")
                return {"status": "already_empty", "deleted": 0}
            
            # 删除所有文档
            self.client.delete_collection(self.collection_name)
            
            # 重新创建集合
            distance_function = self.config.chroma_distance_function
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": distance_function}
            )
            
            logger.info(f"集合已清空，删除了 {current_count} 个文档")
            
            return {
                "status": "success",
                "deleted": current_count,
                "remaining_count": 0
            }
            
        except Exception as e:
            logger.error(f"清空集合失败: {e}")
            return {"status": "error", "error": str(e)}
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        try:
            if not self.collection:
                return {"error": "数据库未初始化"}
            
            count = self.collection.count()
            collection_info = self._get_collection_info()
            
            # 获取一些示例文档来分析
            sample_result = self.collection.get(limit=10)
            
            # 分析元数据
            source_files = set()
            embedding_models = set()
            
            if sample_result.get("metadatas"):
                for metadata in sample_result["metadatas"]:
                    if metadata.get("source_file"):
                        source_files.add(metadata["source_file"])
                    if metadata.get("embedding_model"):
                        embedding_models.add(metadata["embedding_model"])
            
            return {
                "collection_name": self.collection_name,
                "total_documents": count,
                "database_path": str(self.db_path),
                "distance_function": self.config.chroma_distance_function,
                "unique_source_files": len(source_files),
                "embedding_models": list(embedding_models),
                "collection_metadata": collection_info.get("metadata", {}),
                "sample_source_files": list(source_files)[:5]  # 显示前5个
            }
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {"error": str(e)}
    
    def backup_collection(self, backup_path: str) -> Dict[str, Any]:
        """备份集合数据"""
        try:
            if not self.collection:
                return {"status": "error", "error": "数据库未初始化"}
            
            logger.info(f"开始备份集合到: {backup_path}")
            
            # 获取所有数据
            all_data = self.collection.get(
                include=["documents", "metadatas", "embeddings"]
            )
            
            # 准备备份数据
            backup_data = {
                "collection_name": self.collection_name,
                "backup_time": datetime.now().isoformat(),
                "count": len(all_data.get("ids", [])),
                "config": self.config.to_dict(),
                "data": all_data
            }
            
            # 保存到文件
            backup_file = Path(backup_path)
            backup_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"备份完成，包含 {backup_data['count']} 个文档")
            
            return {
                "status": "success",
                "backup_file": str(backup_file),
                "document_count": backup_data["count"]
            }
            
        except Exception as e:
            logger.error(f"备份失败: {e}")
            return {"status": "error", "error": str(e)}
    
    def restore_collection(self, backup_path: str) -> Dict[str, Any]:
        """从备份恢复集合数据"""
        try:
            if not self.collection:
                return {"status": "error", "error": "数据库未初始化"}
            
            logger.info(f"从备份恢复集合: {backup_path}")
            
            # 读取备份文件
            with open(backup_path, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            # 清空当前集合
            self.clear_collection()
            
            # 恢复数据
            data = backup_data["data"]
            
            if data.get("ids"):
                self.collection.add(
                    ids=data["ids"],
                    embeddings=data.get("embeddings", []),
                    documents=data.get("documents", []),
                    metadatas=data.get("metadatas", [])
                )
            
            restored_count = len(data.get("ids", []))
            logger.info(f"恢复完成，恢复了 {restored_count} 个文档")
            
            return {
                "status": "success",
                "restored_count": restored_count,
                "backup_time": backup_data.get("backup_time", ""),
                "current_count": self.collection.count()
            }
            
        except Exception as e:
            logger.error(f"恢复失败: {e}")
            return {"status": "error", "error": str(e)}
    
    def is_available(self) -> bool:
        """检查向量数据库是否可用"""
        return self.client is not None and self.collection is not None
    
    def get_stats(self) -> Dict[str, Any]:
        """获取数据库统计信息（兼容性方法）"""
        return self.get_statistics()

    def close(self):
        """关闭数据库连接"""
        try:
            if self.collection:
                self.collection = None
                logger.info("向量集合连接已关闭")

            if self.client:
                # 尝试调用reset来清理连接
                try:
                    self.client.reset()
                    logger.info("ChromaDB客户端已reset")
                except Exception as e:
                    logger.debug(f"无法reset ChromaDB客户端: {e}")

                # 设置为None让GC处理
                self.client = None
                logger.info("向量数据库客户端连接已关闭")

                # 强制垃圾回收
                import gc
                gc.collect()
                logger.debug("已执行垃圾回收")

        except Exception as e:
            logger.error(f"关闭数据库连接失败: {e}")

    def force_close(self):
        """强制关闭连接，用于处理顽固的连接问题"""
        try:
            logger.info("开始强制关闭向量数据库连接...")

            # 第一步：清除客户端引用
            if hasattr(self, 'client') and self.client is not None:
                try:
                    # 尝试关闭客户端连接
                    if hasattr(self.client, 'reset'):
                        self.client.reset()
                    logger.debug("客户端连接已重置")
                except Exception as e:
                    logger.debug(f"客户端重置失败: {e}")
                finally:
                    self.client = None

            # 第二步：清除集合引用
            if hasattr(self, 'collection') and self.collection is not None:
                self.collection = None
                logger.debug("集合引用已清除")

            # 第三步：尝试正常关闭
            try:
                self.close()
            except Exception as e:
                logger.debug(f"正常关闭失败: {e}")

            # 第四步：强制清理资源
            import threading
            import time
            import sqlite3
            import gc

            logger.info("强制清理系统资源...")

            # 强制关闭所有SQLite连接
            closed_connections = 0
            try:
                for obj in gc.get_objects():
                    if isinstance(obj, sqlite3.Connection):
                        try:
                            if not obj.in_transaction:
                                obj.close()
                                closed_connections += 1
                        except Exception:
                            pass
                if closed_connections > 0:
                    logger.info(f"强制关闭了 {closed_connections} 个SQLite连接")
            except Exception as e:
                logger.debug(f"强制关闭SQLite连接时出错: {e}")

            # 清理ChromaDB模块级别的状态
            try:
                import sys
                modules_to_clear = []
                for module_name in sys.modules:
                    if 'chroma' in module_name.lower():
                        modules_to_clear.append(module_name)

                for module_name in modules_to_clear:
                    try:
                        module = sys.modules[module_name]
                        if hasattr(module, '_clients'):
                            module._clients = {}
                        if hasattr(module, '_collections'):
                            module._collections = {}
                        if hasattr(module, '_client_cache'):
                            module._client_cache = {}
                    except Exception:
                        pass

                logger.debug(f"清理了 {len(modules_to_clear)} 个ChromaDB模块")
            except Exception as e:
                logger.debug(f"清理ChromaDB模块状态时出错: {e}")

            # 多轮垃圾回收，增加等待时间
            for i in range(3):
                gc.collect()
                time.sleep(2)
                logger.debug(f"执行第 {i+1} 轮垃圾回收")

            # 最后等待，确保所有资源释放
            time.sleep(5)
            logger.info("强制关闭完成，等待资源释放...")

        except Exception as e:
            logger.error(f"强制关闭失败: {e}")
        finally:
            # 确保所有引用都被清除
            for attr in ['client', 'collection', 'embeddings_manager']:
                if hasattr(self, attr):
                    setattr(self, attr, None)

    def __del__(self):
        """析构函数，确保资源释放"""
        try:
            self.close()
        except Exception:
            pass

    def get_document_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取文档"""
        try:
            if not self.collection:
                return None

            result = self.collection.get(ids=[doc_id])

            if result.get("documents"):
                return {
                    "id": doc_id,
                    "document": result["documents"][0],
                    "metadata": result["metadatas"][0] if result.get("metadatas") else {}
                }

            return None

        except Exception as e:
            logger.error(f"获取文档失败: {e}")
            return None
