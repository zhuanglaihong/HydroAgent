"""
Author: zhuanglaihong
Date: 2024-09-24 15:30:00
LastEditTime: 2025-09-27 15:00:00
LastEditors: zhuanglaihong
Description: RAG系统主接口，整合文档处理、向量存储和查询功能，提供统一的RAG服务接口
FilePath: \HydroAgent\hydrorag\rag_system.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import logging
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from datetime import datetime

from .config import Config, default_config
from .document_processor import DocumentProcessor
from .embeddings_manager import EmbeddingsManager
from .vector_store import VectorStore
from .query_processor import QueryProcessor

logger = logging.getLogger(__name__)


class RAGSystem:
    """RAG系统主类 - 提供完整的RAG功能"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        初始化RAG系统
        
        Args:
            config: 配置对象，如果为None则使用默认配置
        """
        self.config = config or default_config
        
        # 验证配置
        if not self.config.validate():
            raise ValueError("配置验证失败")
        
        # 初始化各个组件
        self.embeddings_manager = None
        self.vector_store = None
        self.document_processor = None
        self.query_processor = None
        
        # 系统状态
        self.is_initialized = False
        self.initialization_errors = []
        
        # 初始化系统
        self._initialize_system()
        
        logger.info("RAG系统初始化完成")
    
    def _initialize_system(self):
        """初始化系统组件"""
        try:
            logger.info("开始初始化RAG系统组件")
            
            # 1. 初始化嵌入模型管理器
            try:
                self.embeddings_manager = EmbeddingsManager(self.config)
                if not self.embeddings_manager.is_available():
                    error_msg = "嵌入模型初始化失败"
                    self.initialization_errors.append(error_msg)
                    logger.error(error_msg)
                else:
                    logger.info("嵌入模型管理器初始化成功")
            except Exception as e:
                error_msg = f"嵌入模型管理器初始化失败: {e}"
                self.initialization_errors.append(error_msg)
                logger.error(error_msg)
            
            # 2. 初始化向量数据库
            try:
                if self.embeddings_manager:
                    self.vector_store = VectorStore(self.config, self.embeddings_manager)
                    if not self.vector_store.is_available():
                        error_msg = "向量数据库初始化失败"
                        self.initialization_errors.append(error_msg)
                        logger.error(error_msg)
                    else:
                        logger.info("向量数据库初始化成功")
                else:
                    error_msg = "无法初始化向量数据库（嵌入模型不可用）"
                    self.initialization_errors.append(error_msg)
                    logger.error(error_msg)
            except Exception as e:
                error_msg = f"向量数据库初始化失败: {e}"
                self.initialization_errors.append(error_msg)
                logger.error(error_msg)
            
            # 3. 初始化文档处理器
            try:
                self.document_processor = DocumentProcessor(self.config)
                logger.info("文档处理器初始化成功")
            except Exception as e:
                error_msg = f"文档处理器初始化失败: {e}"
                self.initialization_errors.append(error_msg)
                logger.error(error_msg)

            # 4. 初始化查询处理器
            try:
                self.query_processor = QueryProcessor(self.config, self.embeddings_manager)
                logger.info("查询处理器初始化成功")
            except Exception as e:
                error_msg = f"查询处理器初始化失败: {e}"
                self.initialization_errors.append(error_msg)
                logger.error(error_msg)
            
            # 检查初始化状态
            self.is_initialized = (
                self.embeddings_manager is not None and
                self.embeddings_manager.is_available() and
                self.vector_store is not None and
                self.vector_store.is_available() and
                self.document_processor is not None and
                self.query_processor is not None
            )
            
            if self.is_initialized:
                logger.info("RAG系统所有组件初始化成功")
            else:
                logger.warning(f"RAG系统初始化部分失败，错误: {self.initialization_errors}")
            
        except Exception as e:
            error_msg = f"RAG系统初始化失败: {e}"
            self.initialization_errors.append(error_msg)
            logger.error(error_msg)
            self.is_initialized = False
    
    def process_documents(self, force_reprocess: bool = False) -> Dict[str, Any]:
        """
        处理所有原始文档
        
        Args:
            force_reprocess: 是否强制重新处理所有文档
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        try:
            if not self.document_processor:
                return {"status": "error", "error": "文档处理器未初始化"}
            
            logger.info("开始处理原始文档")
            
            # 如果强制重新处理，先清理已处理的文档
            if force_reprocess:
                logger.info("强制重新处理，清理已处理的文档")
                self.document_processor.clean_processed_documents()
            
            # 处理文档
            result = self.document_processor.process_all_documents()
            
            if result.get("status") == "completed":
                logger.info(f"文档处理完成: 成功 {result.get('processed', 0)}, 失败 {result.get('failed', 0)}, 跳过 {result.get('skipped', 0)}")
            else:
                logger.error(f"文档处理失败: {result}")
            
            return result
            
        except Exception as e:
            logger.error(f"处理文档失败: {e}")
            return {"status": "error", "error": str(e)}
    
    def build_vector_index(self, rebuild: bool = False) -> Dict[str, Any]:
        """
        构建向量索引
        
        Args:
            rebuild: 是否重建索引
            
        Returns:
            Dict[str, Any]: 构建结果
        """
        try:
            if not self.vector_store or not self.document_processor:
                return {"status": "error", "error": "系统组件未初始化"}
            
            logger.info("开始构建向量索引")
            
            # 如果需要重建，先清空向量数据库
            if rebuild:
                logger.info("重建索引，清空向量数据库")
                clear_result = self.vector_store.clear_collection()
                if clear_result.get("status") != "success":
                    logger.error(f"清空向量数据库失败: {clear_result}")
            
            # 获取已处理的文档
            processed_docs = self.document_processor.get_processed_documents()
            
            if not processed_docs:
                logger.warning("没有已处理的文档，先处理原始文档")
                process_result = self.process_documents()
                if process_result.get("status") != "completed":
                    return {"status": "error", "error": "文档处理失败"}
                
                processed_docs = self.document_processor.get_processed_documents()
            
            # 加载文档块并添加到向量数据库
            total_added = 0
            total_failed = 0
            
            for doc_info in processed_docs:
                try:
                    # 读取处理后的文档
                    processed_file = doc_info.get("processed_file")
                    if not processed_file or not Path(processed_file).exists():
                        logger.warning(f"处理后的文档文件不存在: {processed_file}")
                        total_failed += 1
                        continue
                    
                    with open(processed_file, 'r', encoding='utf-8') as f:
                        doc_data = json.load(f)
                    
                    chunks = doc_data.get("chunks", [])
                    if not chunks:
                        logger.warning(f"文档没有文本块: {processed_file}")
                        continue
                    
                    # 添加到向量数据库
                    add_result = self.vector_store.add_documents(chunks)
                    
                    if add_result.get("status") == "success":
                        added_count = add_result.get("added", 0)
                        total_added += added_count
                        logger.info(f"成功添加 {added_count} 个文本块来自 {doc_info.get('source_file', '')}")
                    else:
                        total_failed += 1
                        logger.error(f"添加文档块失败: {add_result}")
                
                except Exception as e:
                    total_failed += 1
                    logger.error(f"处理文档失败 {doc_info}: {e}")
            
            # 获取最终统计信息
            stats = self.vector_store.get_statistics()
            
            result = {
                "status": "success",
                "total_documents_processed": len(processed_docs),
                "total_chunks_added": total_added,
                "failed_documents": total_failed,
                "final_document_count": stats.get("total_documents", 0),
                "vector_store_stats": stats
            }
            
            logger.info(f"向量索引构建完成: {result}")
            return result
            
        except Exception as e:
            logger.error(f"构建向量索引失败: {e}")
            return {"status": "error", "error": str(e)}
    
    def query(
        self,
        query_text: str,
        top_k: int = None,
        score_threshold: float = None,
        include_metadata: bool = True,
        enable_rerank: bool = None,
        enable_expansion: bool = True
    ) -> Dict[str, Any]:
        """
        查询相关文档（增强版）

        Args:
            query_text: 查询文本
            top_k: 返回结果数量
            score_threshold: 分数阈值
            include_metadata: 是否包含元数据
            enable_rerank: 是否启用重排序
            enable_expansion: 是否启用查询扩展

        Returns:
            Dict[str, Any]: 查询结果
        """
        try:
            if not self.vector_store:
                return {"status": "error", "error": "向量数据库未初始化"}

            # 使用配置中的默认值
            if top_k is None:
                top_k = self.config.top_k
            if score_threshold is None:
                score_threshold = self.config.score_threshold
            if enable_rerank is None:
                enable_rerank = getattr(self.config, 'rerank_enabled', True)

            logger.info(f"查询: {query_text[:100]}..., top_k={top_k}, threshold={score_threshold}")

            # 查询预处理
            if self.query_processor:
                processed_query = self.query_processor.preprocess_query(query_text)
                logger.debug(f"查询预处理: '{query_text}' -> '{processed_query}'")
            else:
                processed_query = query_text

            # 查询扩展
            queries_to_search = [processed_query]
            if enable_expansion and self.query_processor:
                expanded_queries = self.query_processor.expand_query(processed_query)
                queries_to_search = expanded_queries[:3]  # 限制扩展查询数量

            # 执行多查询检索
            all_results = []
            for query in queries_to_search:
                raw_result = self.vector_store.query(
                    query_text=query,
                    n_results=top_k * 2 if enable_rerank else top_k,  # 重排序时获取更多结果
                    score_threshold=score_threshold * 0.8  # 降低阈值以获取更多候选
                )

                if raw_result.get("status") == "success":
                    results = self._convert_vector_results(raw_result)
                    all_results.extend(results)

            if not all_results:
                return {"status": "no_results", "query": query_text, "results": []}

            # 去重（基于内容相似性）
            unique_results = self._deduplicate_results(all_results)

            # 重排序
            if enable_rerank and self.query_processor:
                reranked_results = self.query_processor.rerank_results(query_text, unique_results)
            else:
                reranked_results = unique_results

            # 结果过滤和限制
            if self.query_processor:
                filtered_results = self.query_processor.filter_results(
                    reranked_results,
                    min_score=score_threshold,
                    max_results=top_k,
                    source_diversity=True
                )
            else:
                filtered_results = reranked_results[:top_k]

            # 结果后处理
            if self.query_processor:
                final_results = self.query_processor.post_process_results(filtered_results)
            else:
                final_results = filtered_results

            # 构建最终结果
            processed_result = {
                "status": "success",
                "query": query_text,
                "processed_query": processed_query,
                "expanded_queries": queries_to_search if enable_expansion else [processed_query],
                "total_found": len(all_results),
                "after_dedup": len(unique_results),
                "final_count": len(final_results),
                "rerank_enabled": enable_rerank,
                "results": final_results
            }

            logger.info(f"查询完成，返回 {len(final_results)} 个结果")

            return processed_result

        except Exception as e:
            logger.error(f"查询失败: {e}")
            return {"status": "error", "error": str(e)}

    def get_query_suggestions(self, query_text: str) -> List[str]:
        """获取查询建议"""
        if self.query_processor:
            return self.query_processor.get_query_suggestions(query_text)
        return []

    def get_knowledge_fragments(self, query_text: str, top_k: int = 5) -> List[str]:
        """
        获取知识片段（为与COT系统集成而设计）

        Args:
            query_text: 查询文本
            top_k: 返回结果数量

        Returns:
            List[str]: 知识片段列表，直接用于提示词构建
        """
        try:
            result = self.query(
                query_text=query_text,
                top_k=top_k,
                include_metadata=False,
                enable_rerank=True,
                enable_expansion=True
            )

            if result.get("status") == "success":
                return [item["content"] for item in result.get("results", [])]
            else:
                logger.warning(f"获取知识片段失败: {result}")
                return []

        except Exception as e:
            logger.error(f"获取知识片段失败: {e}")
            return []
    
    def _convert_vector_results(self, raw_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """转换向量数据库结果为标准格式"""
        try:
            results = []
            documents = raw_result.get("documents", [])
            distances = raw_result.get("distances", [])
            metadatas = raw_result.get("metadatas", [])

            for i, doc in enumerate(documents):
                distance = distances[i] if i < len(distances) else 1.0
                metadata = metadatas[i] if i < len(metadatas) else {}

                result_item = {
                    "content": doc,
                    "distance": distance,
                    "score": 1.0 - distance,  # 转换为相似度分数
                    "metadata": metadata
                }

                results.append(result_item)

            return results

        except Exception as e:
            logger.error(f"转换向量结果失败: {e}")
            return []

    def _deduplicate_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """去除重复结果"""
        try:
            seen_contents = set()
            unique_results = []

            for result in results:
                content = result.get("content", "")
                # 使用内容的前100个字符作为去重标准
                content_key = content[:100] if content else ""

                if content_key not in seen_contents:
                    seen_contents.add(content_key)
                    unique_results.append(result)

            logger.debug(f"去重后保留 {len(unique_results)}/{len(results)} 个结果")
            return unique_results

        except Exception as e:
            logger.error(f"去重处理失败: {e}")
            return results

    def _process_query_result(self, raw_result: Dict[str, Any], include_metadata: bool) -> Dict[str, Any]:
        """处理查询结果"""
        try:
            processed_result = {
                "status": "success",
                "query": raw_result.get("query", ""),
                "total_found": raw_result.get("total_found", 0),
                "results": []
            }
            
            documents = raw_result.get("documents", [])
            scores = raw_result.get("scores", [])
            metadatas = raw_result.get("metadatas", [])
            
            for i, (doc, score) in enumerate(zip(documents, scores)):
                result_item = {
                    "content": doc,
                    "score": score,
                    "rank": i + 1
                }
                
                if include_metadata and i < len(metadatas):
                    metadata = metadatas[i]
                    result_item["metadata"] = {
                        "source_file": metadata.get("source_file", ""),
                        "chunk_index": metadata.get("chunk_index", 0),
                        "chunk_size": metadata.get("chunk_size", 0),
                        "file_name": metadata.get("file_name", ""),
                        "embedding_model": metadata.get("embedding_model", "")
                    }
                
                processed_result["results"].append(result_item)
            
            return processed_result
            
        except Exception as e:
            logger.error(f"处理查询结果失败: {e}")
            return {"status": "error", "error": str(e)}
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        try:
            status = {
                "is_initialized": self.is_initialized,
                "initialization_errors": self.initialization_errors,
                "config": self.config.to_dict(),
                "components": {
                    "embeddings_manager": {
                        "available": self.embeddings_manager is not None and self.embeddings_manager.is_available(),
                        "info": self.embeddings_manager.get_model_info() if self.embeddings_manager else None
                    },
                    "vector_store": {
                        "available": self.vector_store is not None and self.vector_store.is_available(),
                        "stats": self.vector_store.get_statistics() if self.vector_store else None
                    },
                    "document_processor": {
                        "available": self.document_processor is not None,
                        "stats": self.document_processor.get_statistics() if self.document_processor else None
                    }
                }
            }
            
            return status
            
        except Exception as e:
            logger.error(f"获取系统状态失败: {e}")
            return {"error": str(e)}
    
    def backup_system(self, backup_dir: str) -> Dict[str, Any]:
        """备份整个系统"""
        try:
            backup_path = Path(backup_dir)
            backup_path.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            results = {
                "status": "success",
                "backup_time": timestamp,
                "backup_dir": str(backup_path),
                "backups": {}
            }
            
            # 备份配置
            config_backup = backup_path / f"config_{timestamp}.json"
            self.config.save_to_file(str(config_backup))
            results["backups"]["config"] = str(config_backup)
            
            # 备份向量数据库
            if self.vector_store and self.vector_store.is_available():
                vector_backup = backup_path / f"vector_store_{timestamp}.json"
                backup_result = self.vector_store.backup_collection(str(vector_backup))
                if backup_result.get("status") == "success":
                    results["backups"]["vector_store"] = str(vector_backup)
                else:
                    results["backups"]["vector_store_error"] = backup_result.get("error")
            
            # 备份处理后的文档（复制目录）
            if self.document_processor:
                import shutil
                processed_backup = backup_path / f"processed_docs_{timestamp}"
                shutil.copytree(
                    self.config.processed_documents_dir,
                    processed_backup,
                    dirs_exist_ok=True
                )
                results["backups"]["processed_documents"] = str(processed_backup)
            
            logger.info(f"系统备份完成: {backup_path}")
            return results
            
        except Exception as e:
            logger.error(f"系统备份失败: {e}")
            return {"status": "error", "error": str(e)}
    
    def setup_from_raw_documents(self) -> Dict[str, Any]:
        """从原始文档完整设置系统"""
        try:
            logger.info("开始从原始文档完整设置RAG系统")
            
            # 检查是否已经处理过文档和构建了向量库
            processed_docs = self.document_processor.get_processed_documents() if self.document_processor else []
            vector_store_stats = self.vector_store.get_statistics() if self.vector_store else {"error": "向量存储未初始化"}
            
            # 如果向量存储不为空且已有处理后的文档，跳过处理
            if (processed_docs and 
                vector_store_stats.get("total_documents", 0) > 0 and 
                not vector_store_stats.get("error")):
                logger.info("发现已存在的向量库和处理后的文档，跳过处理")
                return {
                    "status": "success",
                    "message": "已存在处理后的文档和向量库",
                    "processed": len(processed_docs),
                    "in_vector_store": vector_store_stats.get("total_documents", 0),
                    "skipped": True
                }
            
            results = {
                "status": "success",
                "steps": {}
            }
            
            # 步骤1: 处理原始文档
            logger.info("步骤1: 处理原始文档")
            process_result = self.process_documents(force_reprocess=False)  # 默认不强制重新处理
            results["steps"]["document_processing"] = process_result
            
            if process_result.get("status") not in ["completed", "success"]:
                return {
                    "status": "error",
                    "error": "文档处理失败",
                    "details": results
                }
            
            # 步骤2: 构建向量索引
            logger.info("步骤2: 构建向量索引")
            index_result = self.build_vector_index(rebuild=False)  # 默认不重建索引
            results["steps"]["index_building"] = index_result
            
            if index_result.get("status") != "success":
                return {
                    "status": "error",
                    "error": "索引构建失败",
                    "details": results
                }
            
            # 步骤3: 测试查询
            logger.info("步骤3: 测试查询")
            test_result = self.query("GR4J模型参数", top_k=3)
            results["steps"]["test_query"] = test_result
            
            # 获取最终状态
            results["final_status"] = self.get_system_status()
            
            logger.info("RAG系统完整设置完成")
            return results
            
        except Exception as e:
            logger.error(f"完整设置失败: {e}")
            return {"status": "error", "error": str(e)}
    
    def health_check(self) -> Dict[str, Any]:
        """系统健康检查"""
        try:
            health = {
                "overall_status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "checks": {}
            }
            
            issues = []
            
            # 检查初始化状态
            if not self.is_initialized:
                health["checks"]["initialization"] = {
                    "status": "failed",
                    "errors": self.initialization_errors
                }
                issues.append("系统未完全初始化")
            else:
                health["checks"]["initialization"] = {"status": "passed"}
            
            # 检查嵌入模型
            if self.embeddings_manager and self.embeddings_manager.is_available():
                health["checks"]["embeddings"] = {"status": "passed"}
            else:
                health["checks"]["embeddings"] = {"status": "failed"}
                issues.append("嵌入模型不可用")
            
            # 检查向量数据库
            if self.vector_store and self.vector_store.is_available():
                stats = self.vector_store.get_statistics()
                health["checks"]["vector_store"] = {
                    "status": "passed",
                    "document_count": stats.get("total_documents", 0)
                }
                
                if stats.get("total_documents", 0) == 0:
                    issues.append("向量数据库为空")
            else:
                health["checks"]["vector_store"] = {"status": "failed"}
                issues.append("向量数据库不可用")
            
            # 检查文档处理器
            if self.document_processor:
                doc_stats = self.document_processor.get_statistics()
                health["checks"]["document_processor"] = {
                    "status": "passed",
                    "processed_docs": doc_stats.get("processed_documents_count", 0)
                }
            else:
                health["checks"]["document_processor"] = {"status": "failed"}
                issues.append("文档处理器不可用")
            
            # 设置总体状态
            if issues:
                health["overall_status"] = "unhealthy"
                health["issues"] = issues
            
            return health
            
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return {
                "overall_status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        # 清理资源（如果需要）
        pass


# 便利函数
def create_rag_system(config_file: Optional[str] = None) -> RAGSystem:
    """
    创建RAG系统实例
    
    Args:
        config_file: 配置文件路径
        
    Returns:
        RAGSystem: RAG系统实例
    """
    if config_file and Path(config_file).exists():
        config = Config.load_from_file(config_file)
    else:
        config = default_config
    
    return RAGSystem(config)


def quick_setup(documents_dir: str = "./documents") -> RAGSystem:
    """
    快速设置RAG系统
    
    Args:
        documents_dir: 文档目录
        
    Returns:
        RAGSystem: 已设置的RAG系统
    """
    config = Config(
        documents_dir=documents_dir,
        raw_documents_dir=f"{documents_dir}/raw",
        processed_documents_dir=f"{documents_dir}/processed",
        vector_db_dir=f"{documents_dir}/vector_db"
    )
    
    rag_system = RAGSystem(config)
    
    # 从原始文档设置系统
    setup_result = rag_system.setup_from_raw_documents()
    
    if setup_result.get("status") != "success":
        logger.warning(f"快速设置遇到问题: {setup_result}")
    
    return rag_system
