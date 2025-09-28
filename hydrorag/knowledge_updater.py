"""
Author: zhuanglaihong
Date: 2025-09-27 15:10:00
LastEditTime: 2025-09-27 15:10:00
LastEditors: zhuanglaihong
Description: 知识库更新接口，提供增量更新、全量重建和维护功能
FilePath: \HydroAgent\hydrorag\knowledge_updater.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import logging
import os
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import json

from .rag_system import RAGSystem
from .config import Config, default_config
from .document_processor import DocumentProcessor
from .vector_store import VectorStore


class KnowledgeUpdater:
    """知识库更新器

    提供知识库的增量更新、全量重建、备份恢复等功能
    支持上下文管理器，确保资源正确释放
    """

    def __init__(self, config: Optional[Config] = None, lazy_init: bool = True):
        """初始化知识库更新器

        Args:
            config: RAG系统配置，如果为None则使用默认配置
            lazy_init: 是否延迟初始化嵌入组件，True时仅在需要时初始化向量存储
        """
        self.config = config or default_config
        self.logger = logging.getLogger(__name__)
        self.lazy_init = lazy_init

        # 初始化核心组件
        self.doc_processor = DocumentProcessor(self.config)

        # 延迟初始化的组件
        self.embeddings_manager = None
        self.vector_store = None

        # 路径配置
        self.raw_dir = Path(self.config.raw_documents_dir)
        self.processed_dir = Path(self.config.processed_documents_dir)
        self.vector_db_dir = Path(self.config.vector_db_dir)
        self.backup_dir = Path(self.config.documents_dir) / "backup"

        # 确保目录存在
        self._ensure_directories()

        # 如果不是延迟初始化，立即初始化嵌入组件
        if not lazy_init:
            self._init_embedding_components()

    def _ensure_directories(self):
        """确保必要的目录存在"""
        for directory in [self.raw_dir, self.processed_dir, self.vector_db_dir, self.backup_dir]:
            directory.mkdir(parents=True, exist_ok=True)

    def _init_embedding_components(self):
        """初始化嵌入管理器和向量存储"""
        if self.embeddings_manager is None:
            try:
                from .embeddings_manager import EmbeddingsManager
                self.embeddings_manager = EmbeddingsManager(self.config)
                self.logger.info("嵌入管理器初始化成功")
            except Exception as e:
                self.logger.error(f"嵌入管理器初始化失败: {e}")
                self.logger.warning("将使用空嵌入管理器继续运行")
                # 创建一个虚拟的嵌入管理器
                self.embeddings_manager = None

        # 无论嵌入管理器是否成功，都尝试初始化向量存储
        try:
            self.vector_store = VectorStore(self.config, self.embeddings_manager)
            if self.vector_store.is_available():
                self.logger.info("向量存储初始化成功")
            else:
                self.logger.warning("向量存储初始化不完整，但可继续运行")
        except Exception as e:
            self.logger.error(f"向量存储初始化失败: {e}")
            self.vector_store = None

    def _ensure_vector_store(self):
        """确保向量存储已初始化"""
        if self.vector_store is None:
            self._init_embedding_components()

    def full_rebuild(self, backup_existing: bool = True) -> Dict[str, Any]:
        """完全重建知识库

        Args:
            backup_existing: 是否备份现有知识库

        Returns:
            Dict: 重建结果统计
        """
        self.logger.info("开始完全重建知识库")

        result = {
            "status": "success",
            "start_time": datetime.now().isoformat(),
            "backup_created": False,
            "processed_files": 0,
            "indexed_documents": 0,
            "errors": []
        }

        try:
            # 0. 确保向量存储已初始化
            self._ensure_vector_store()
            self.logger.info("向量存储初始化完成")

            # 1. 备份现有知识库
            if backup_existing:
                backup_path = self._create_backup()
                result["backup_created"] = True
                result["backup_path"] = str(backup_path)
                self.logger.info(f"已创建备份: {backup_path}")

            # 2. 清理现有数据
            self._cleanup_existing_data()
            self.logger.info("已清理现有数据")

            # 3. 处理原始文档
            processed_files = self._process_all_documents()
            result["processed_files"] = len(processed_files)
            self.logger.info(f"已处理 {len(processed_files)} 个文档")

            # 4. 重建向量索引
            indexed_count = self._rebuild_vector_index()
            result["indexed_documents"] = indexed_count
            self.logger.info(f"已索引 {indexed_count} 个文档块")

            # 5. 验证重建结果
            validation_result = self._validate_knowledge_base()
            result.update(validation_result)

            result["end_time"] = datetime.now().isoformat()
            self.logger.info("知识库重建完成")

        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            result["errors"].append(str(e))
            self.logger.error(f"知识库重建失败: {e}")

        return result

    def incremental_update(self, file_paths: Optional[List[Union[str, Path]]] = None) -> Dict[str, Any]:
        """增量更新知识库

        Args:
            file_paths: 要更新的文件路径列表，如果为None则自动检测变更

        Returns:
            Dict: 更新结果统计
        """
        self.logger.info("开始增量更新知识库")

        result = {
            "status": "success",
            "start_time": datetime.now().isoformat(),
            "updated_files": [],
            "added_documents": 0,
            "updated_documents": 0,
            "removed_documents": 0,
            "errors": []
        }

        try:
            # 0. 确保向量存储已初始化
            self._ensure_vector_store()
            self.logger.info("向量存储初始化完成")

            # 1. 确定需要更新的文件
            if file_paths:
                files_to_update = [Path(f) for f in file_paths]
            else:
                files_to_update = self._detect_changed_files()

            self.logger.info(f"检测到 {len(files_to_update)} 个文件需要更新")

            # 2. 处理每个变更的文件
            for file_path in files_to_update:
                try:
                    if file_path.exists():
                        # 文件存在，处理更新
                        self._update_single_file(file_path)
                        result["updated_files"].append(str(file_path))
                        self.logger.info(f"已更新文件: {file_path}")
                    else:
                        # 文件不存在，删除相关索引
                        self._remove_file_from_index(file_path)
                        result["removed_documents"] += 1
                        self.logger.info(f"已从索引中删除: {file_path}")

                except Exception as e:
                    error_msg = f"处理文件 {file_path} 时出错: {e}"
                    result["errors"].append(error_msg)
                    self.logger.error(error_msg)

            # 3. 更新统计信息
            self._update_statistics(result)

            result["end_time"] = datetime.now().isoformat()
            self.logger.info("增量更新完成")

        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            result["errors"].append(str(e))
            self.logger.error(f"增量更新失败: {e}")

        return result

    def add_documents(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """添加新文档到知识库

        Args:
            documents: 文档列表，每个文档包含content, metadata等字段

        Returns:
            Dict: 添加结果
        """
        self.logger.info(f"开始添加 {len(documents)} 个文档到知识库")

        result = {
            "status": "success",
            "added_count": 0,
            "failed_count": 0,
            "errors": []
        }

        try:
            # 确保向量存储已初始化
            self._ensure_vector_store()

            for i, doc in enumerate(documents):
                try:
                    # 添加到向量数据库
                    self.vector_store.add_document(
                        content=doc["content"],
                        metadata=doc.get("metadata", {}),
                        doc_id=doc.get("id", f"manual_doc_{i}")
                    )
                    result["added_count"] += 1

                except Exception as e:
                    result["failed_count"] += 1
                    error_msg = f"添加文档 {i} 失败: {e}"
                    result["errors"].append(error_msg)
                    self.logger.error(error_msg)

            self.logger.info(f"文档添加完成: 成功 {result['added_count']}, 失败 {result['failed_count']}")

        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            self.logger.error(f"添加文档失败: {e}")

        return result

    def remove_documents(self, doc_ids: List[str]) -> Dict[str, Any]:
        """从知识库中删除指定文档

        Args:
            doc_ids: 要删除的文档ID列表

        Returns:
            Dict: 删除结果
        """
        self.logger.info(f"开始删除 {len(doc_ids)} 个文档")

        result = {
            "status": "success",
            "removed_count": 0,
            "failed_count": 0,
            "errors": []
        }

        try:
            # 确保向量存储已初始化
            self._ensure_vector_store()

            for doc_id in doc_ids:
                try:
                    success = self.vector_store.delete_document(doc_id)
                    if success:
                        result["removed_count"] += 1
                    else:
                        result["failed_count"] += 1
                        result["errors"].append(f"文档 {doc_id} 不存在")

                except Exception as e:
                    result["failed_count"] += 1
                    error_msg = f"删除文档 {doc_id} 失败: {e}"
                    result["errors"].append(error_msg)
                    self.logger.error(error_msg)

            self.logger.info(f"文档删除完成: 成功 {result['removed_count']}, 失败 {result['failed_count']}")

        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            self.logger.error(f"删除文档失败: {e}")

        return result

    def get_knowledge_base_stats(self) -> Dict[str, Any]:
        """获取知识库统计信息

        Returns:
            Dict: 统计信息
        """
        try:
            # 获取文件系统统计（不需要向量存储）
            raw_files = list(self.raw_dir.rglob("*.*")) if self.raw_dir.exists() else []
            processed_files = list(self.processed_dir.rglob("*.json")) if self.processed_dir.exists() else []

            stats = {
                "file_system": {
                    "raw_files_count": len(raw_files),
                    "processed_files_count": len(processed_files),
                    "raw_files": [str(f.relative_to(self.raw_dir)) for f in raw_files],
                    "processed_files": [str(f.relative_to(self.processed_dir)) for f in processed_files]
                },
                "last_updated": datetime.now().isoformat()
            }

            # 尝试获取向量数据库统计（如果向量存储可用）
            try:
                if self.vector_store is not None:
                    vector_stats = self.vector_store.get_stats()
                    stats["vector_database"] = vector_stats
                else:
                    # 如果是延迟初始化且还未初始化，提供基本信息
                    stats["vector_database"] = {
                        "document_count": "未初始化",
                        "collection_count": "未初始化",
                        "status": "向量存储未初始化"
                    }
            except Exception as e:
                self.logger.warning(f"无法获取向量数据库统计: {e}")
                stats["vector_database"] = {
                    "document_count": "错误",
                    "collection_count": "错误",
                    "error": str(e)
                }

            return stats

        except Exception as e:
            self.logger.error(f"获取统计信息失败: {e}")
            return {"error": str(e)}

    def create_backup(self, backup_name: Optional[str] = None) -> Path:
        """创建知识库备份

        Args:
            backup_name: 备份名称，如果为None则使用时间戳

        Returns:
            Path: 备份路径
        """
        if backup_name is None:
            backup_name = f"knowledge_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        return self._create_backup(backup_name)

    def restore_backup(self, backup_path: Union[str, Path]) -> Dict[str, Any]:
        """恢复知识库备份

        Args:
            backup_path: 备份路径

        Returns:
            Dict: 恢复结果
        """
        backup_path = Path(backup_path)

        if not backup_path.exists():
            return {"status": "failed", "error": f"备份路径不存在: {backup_path}"}

        try:
            self.logger.info(f"开始恢复备份: {backup_path}")

            # 备份当前状态
            current_backup = self._create_backup("pre_restore_backup")

            # 恢复数据
            if self.processed_dir.exists():
                shutil.rmtree(self.processed_dir)
            if self.vector_db_dir.exists():
                shutil.rmtree(self.vector_db_dir)

            # 从备份恢复
            shutil.copytree(backup_path / "processed", self.processed_dir)
            shutil.copytree(backup_path / "vector_db", self.vector_db_dir)

            self.logger.info("备份恢复完成")

            return {
                "status": "success",
                "restored_from": str(backup_path),
                "current_backup": str(current_backup)
            }

        except Exception as e:
            self.logger.error(f"恢复备份失败: {e}")
            return {"status": "failed", "error": str(e)}

    def _create_backup(self, backup_name: Optional[str] = None) -> Path:
        """创建备份（内部方法）"""
        if backup_name is None:
            backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        backup_path = self.backup_dir / backup_name
        backup_path.mkdir(parents=True, exist_ok=True)

        # 备份processed目录
        if self.processed_dir.exists():
            shutil.copytree(self.processed_dir, backup_path / "processed")

        # 备份vector_db目录（跳过可能被占用的文件）
        if self.vector_db_dir.exists():
            try:
                shutil.copytree(self.vector_db_dir, backup_path / "vector_db")
            except Exception as e:
                self.logger.warning(f"无法备份向量数据库目录（可能被占用）: {e}")
                # 创建空目录标记
                (backup_path / "vector_db_backup_failed.txt").write_text(
                    f"向量数据库备份失败: {e}\n时间: {datetime.now().isoformat()}",
                    encoding="utf-8"
                )

        # 创建备份元数据（不获取向量存储统计以避免初始化连接）
        metadata = {
            "created_at": datetime.now().isoformat(),
            "config": str(self.config),
            "backup_note": "备份创建时未获取向量存储统计以避免连接冲突"
        }

        with open(backup_path / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        return backup_path

    def _cleanup_existing_data(self):
        """清理现有数据"""
        # 先尝试清空集合数据（如果向量存储可用）
        if self.vector_store is not None:
            try:
                self.logger.info("尝试清空向量数据库集合...")

                # 确保向量存储已正确初始化
                if hasattr(self.vector_store, 'collection') and self.vector_store.collection is not None:
                    clear_result = self.vector_store.clear_collection()
                    if clear_result.get("status") == "success":
                        self.logger.info(f"成功清空集合，删除了 {clear_result.get('deleted', 0)} 个文档")
                    elif clear_result.get("status") == "already_empty":
                        self.logger.info("集合已经为空")
                    else:
                        self.logger.warning(f"清空集合失败: {clear_result.get('error', '未知错误')}")
                else:
                    self.logger.info("向量存储未完全初始化，跳过集合清空")

            except Exception as e:
                self.logger.warning(f"清空集合时出错: {e}")

            # 然后强制关闭连接
            self.logger.info("强制关闭向量数据库连接...")
            try:
                self.vector_store.force_close()
            except Exception as e:
                self.logger.warning(f"强制关闭连接失败: {e}")
            finally:
                self.vector_store = None

        # 同时清理嵌入管理器
        if self.embeddings_manager is not None:
            self.embeddings_manager = None

        # 强制垃圾回收
        import gc
        gc.collect()

        # 额外等待时间，确保所有资源释放
        import time
        time.sleep(3)
        self.logger.info("等待资源释放完成")

        # 额外检查并终止可能占用ChromaDB文件的进程
        self._terminate_chromadb_processes()

        # 清理处理后的文档目录
        if self.processed_dir.exists():
            self.logger.info(f"删除处理后文档目录: {self.processed_dir}")
            try:
                shutil.rmtree(self.processed_dir)
            except OSError as e:
                self.logger.warning(f"删除处理后文档目录失败: {e}")

        # 清理向量数据库目录
        if self.vector_db_dir.exists():
            self.logger.info(f"删除向量数据库目录: {self.vector_db_dir}")
            success = False

            # 方法1: 直接删除
            try:
                import time
                time.sleep(2)  # 增加等待时间
                shutil.rmtree(self.vector_db_dir)
                success = True
                self.logger.info("成功删除向量数据库目录")
            except OSError as e:
                self.logger.warning(f"直接删除失败: {e}")

            # 方法2: 逐个删除文件
            if not success:
                try:
                    self._force_delete_directory(self.vector_db_dir)
                    success = True
                    self.logger.info("逐个删除文件成功")
                except Exception as e:
                    self.logger.warning(f"逐个删除失败: {e}")

            # 方法3: 使用系统命令
            if not success:
                try:
                    import subprocess
                    result = subprocess.run(
                        ['rmdir', '/s', '/q', str(self.vector_db_dir)],
                        shell=True, capture_output=True, text=True
                    )
                    if result.returncode == 0:
                        success = True
                        self.logger.info("使用系统命令成功删除向量数据库目录")
                    else:
                        self.logger.warning(f"系统命令失败: {result.stderr}")
                except Exception as e:
                    self.logger.warning(f"系统命令执行失败: {e}")

            # 如果仍然失败，重命名旧目录并创建新目录
            if not success and self.vector_db_dir.exists():
                self.logger.warning("无法删除现有向量数据库目录，将重命名并创建新目录")
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

                # 尝试多种方法处理旧目录
                renamed_success = False

                # 方法1: 直接重命名
                old_backup_dir = self.vector_db_dir.parent / f"vector_db_old_{timestamp}"
                try:
                    self.vector_db_dir.rename(old_backup_dir)
                    self.logger.info(f"旧向量数据库已重命名为: {old_backup_dir}")
                    renamed_success = True
                except Exception as e:
                    self.logger.debug(f"直接重命名失败: {e}")

                # 方法2: 使用系统命令重命名
                if not renamed_success:
                    try:
                        import subprocess
                        result = subprocess.run(
                            ['move', str(self.vector_db_dir), str(old_backup_dir)],
                            shell=True, capture_output=True, text=True
                        )
                        if result.returncode == 0:
                            self.logger.info(f"使用系统命令重命名成功: {old_backup_dir}")
                            renamed_success = True
                        else:
                            self.logger.debug(f"系统命令重命名失败: {result.stderr}")
                    except Exception as e:
                        self.logger.debug(f"系统命令重命名异常: {e}")

                # 方法3: 创建新路径
                if renamed_success:
                    # 重新创建目录
                    self.vector_db_dir.mkdir(parents=True, exist_ok=True)
                    self.logger.info(f"重新创建向量数据库目录: {self.vector_db_dir}")
                else:
                    # 如果重命名失败，使用新路径
                    self.logger.warning("重命名失败，使用新的数据库路径")
                    new_db_dir = self.vector_db_dir.parent / f"vector_db_{timestamp}"
                    self.vector_db_dir = new_db_dir
                    self.config.vector_db_dir = str(new_db_dir)
                    self.logger.info(f"使用新的向量数据库路径: {new_db_dir}")

        self._ensure_directories()

    def _force_delete_directory(self, directory):
        """强制删除目录中的所有文件"""
        import stat
        import time

        for root, dirs, files in os.walk(directory, topdown=False):
            # 删除文件
            for file in files:
                file_path = Path(root) / file
                try:
                    # 移除只读属性
                    file_path.chmod(stat.S_IWRITE)
                    time.sleep(0.1)
                    file_path.unlink()
                except Exception as e:
                    self.logger.debug(f"删除文件 {file_path} 失败: {e}")

            # 删除目录
            for dir_name in dirs:
                dir_path = Path(root) / dir_name
                try:
                    dir_path.rmdir()
                except Exception as e:
                    self.logger.debug(f"删除目录 {dir_path} 失败: {e}")

        # 删除根目录
        try:
            directory.rmdir()
        except Exception:
            # 如果还是删不掉，重命名为备份目录
            backup_name = f"{directory.name}_old_{int(time.time())}"
            backup_path = directory.parent / backup_name
            directory.rename(backup_path)
            self.logger.info(f"无法删除目录，已重命名为: {backup_path}")

    def _process_all_documents(self) -> List[Path]:
        """处理所有原始文档"""
        if not self.raw_dir.exists():
            return []

        # 获取所有支持的文件
        supported_extensions = [".txt", ".md", ".json", ".csv"]
        raw_files = []

        for ext in supported_extensions:
            raw_files.extend(self.raw_dir.rglob(f"*{ext}"))

        processed_files = []
        for file_path in raw_files:
            try:
                self.doc_processor.process_document(file_path)
                processed_files.append(file_path)
            except Exception as e:
                self.logger.error(f"处理文档 {file_path} 失败: {e}")

        return processed_files

    def _rebuild_vector_index(self) -> int:
        """重建向量索引"""
        if not self.processed_dir.exists():
            return 0

        # 确保向量存储已重新初始化
        self._ensure_vector_store()

        if self.vector_store is None:
            self.logger.error("向量存储初始化失败，无法索引文档")
            return 0

        # 获取所有处理后的文档
        processed_files = list(self.processed_dir.rglob("*.json"))

        if not processed_files:
            self.logger.warning("没有找到处理后的文档文件")
            return 0

        self.logger.info(f"找到 {len(processed_files)} 个处理后的文档，开始索引...")

        # 收集所有文档块
        all_chunks = []
        indexed_count = 0

        for file_path in processed_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    doc_data = json.load(f)

                # 准备文档块
                for chunk in doc_data.get("chunks", []):
                    chunk_data = {
                        "content": chunk["content"],
                        "metadata": {
                            "source_file": doc_data.get("source_file", ""),
                            "chunk_index": chunk.get("index", 0),
                            "processed_time": doc_data.get("processed_time", ""),
                            "chunk_id": f"{file_path.stem}_{chunk.get('index', 0)}",
                            **chunk.get("metadata", {})
                        },
                        "chunk_id": f"{file_path.stem}_{chunk.get('index', 0)}"
                    }
                    all_chunks.append(chunk_data)
                    indexed_count += 1

            except Exception as e:
                self.logger.error(f"读取文档 {file_path} 失败: {e}")

        # 批量添加到向量数据库
        if all_chunks:
            self.logger.info(f"开始批量索引 {len(all_chunks)} 个文档块...")
            try:
                result = self.vector_store.add_documents(all_chunks)
                if result.get("status") == "success":
                    actual_added = result.get("added", 0)
                    self.logger.info(f"成功索引 {actual_added} 个文档块")
                    return actual_added
                else:
                    self.logger.error(f"批量索引失败: {result.get('error', '未知错误')}")
                    return 0
            except Exception as e:
                self.logger.error(f"批量索引过程失败: {e}")
                return 0
        else:
            self.logger.warning("没有有效的文档块可以索引")
            return 0

    def _detect_changed_files(self) -> List[Path]:
        """检测变更的文件"""
        # 简单实现：检查raw目录中的所有文件
        if not self.raw_dir.exists():
            return []

        # 获取所有支持的文件
        supported_extensions = [".txt", ".md", ".json", ".csv"]
        changed_files = []

        for ext in supported_extensions:
            changed_files.extend(self.raw_dir.rglob(f"*{ext}"))

        return changed_files

    def _update_single_file(self, file_path: Path):
        """更新单个文件"""
        # 重新处理文档
        self.doc_processor.process_document(file_path)

        # 更新向量索引
        processed_file = self.processed_dir / f"{file_path.stem}_processed.json"
        if processed_file.exists():
            with open(processed_file, "r", encoding="utf-8") as f:
                doc_data = json.load(f)

            # 删除旧的索引
            old_doc_ids = [f"{file_path.stem}_{i}" for i in range(100)]  # 假设最多100个块
            for doc_id in old_doc_ids:
                self.vector_store.delete_document(doc_id)

            # 添加新的索引
            for chunk in doc_data.get("chunks", []):
                self.vector_store.add_document(
                    content=chunk["content"],
                    metadata={
                        "source_file": str(file_path),
                        "chunk_index": chunk.get("index", 0),
                        "processed_time": doc_data.get("processed_time", ""),
                        **chunk.get("metadata", {})
                    },
                    doc_id=f"{file_path.stem}_{chunk.get('index', 0)}"
                )

    def _remove_file_from_index(self, file_path: Path):
        """从索引中删除文件"""
        # 删除处理后的文件
        processed_file = self.processed_dir / f"{file_path.stem}_processed.json"
        if processed_file.exists():
            processed_file.unlink()

        # 删除向量索引
        doc_ids = [f"{file_path.stem}_{i}" for i in range(100)]  # 假设最多100个块
        for doc_id in doc_ids:
            self.vector_store.delete_document(doc_id)

    def _update_statistics(self, result: Dict[str, Any]):
        """更新统计信息"""
        # 这里可以添加更详细的统计逻辑
        pass

    def _validate_knowledge_base(self) -> Dict[str, Any]:
        """验证知识库完整性"""
        try:
            stats = self.get_knowledge_base_stats()

            validation = {
                "validation_passed": True,
                "issues": []
            }

            # 检查基本完整性
            if stats.get("vector_database", {}).get("document_count", 0) == 0:
                validation["issues"].append("向量数据库为空")

            if stats.get("file_system", {}).get("processed_files_count", 0) == 0:
                validation["issues"].append("没有处理后的文档")

            validation["validation_passed"] = len(validation["issues"]) == 0

            return validation

        except Exception as e:
            return {
                "validation_passed": False,
                "issues": [f"验证过程出错: {e}"]
            }

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口，确保资源清理"""
        try:
            self.logger.info("KnowledgeUpdater上下文管理器清理资源...")

            # 强制关闭向量存储连接
            if self.vector_store is not None:
                self.vector_store.force_close()
                self.vector_store = None

            # 清理嵌入管理器
            if self.embeddings_manager is not None:
                self.embeddings_manager = None

            # 执行垃圾回收
            import gc
            gc.collect()

            self.logger.info("KnowledgeUpdater资源清理完成")

        except Exception as e:
            self.logger.error(f"KnowledgeUpdater资源清理失败: {e}")

    def cleanup(self):
        """手动清理资源"""
        self.__exit__(None, None, None)

    def _terminate_chromadb_processes(self):
        """终止可能占用ChromaDB文件的进程"""
        try:
            import psutil
            import os
            import signal
            from pathlib import Path

            self.logger.info("检查占用ChromaDB文件的进程...")

            # 获取ChromaDB相关文件路径
            chroma_db_path = Path(self.vector_db_dir)

            if not chroma_db_path.exists():
                self.logger.debug("ChromaDB目录不存在，跳过进程检查")
                return

            # 查找所有可能的SQLite文件
            sqlite_files = list(chroma_db_path.glob("*.sqlite*"))
            if not sqlite_files:
                self.logger.debug("未找到SQLite文件，跳过进程检查")
                return

            self.logger.info(f"找到 {len(sqlite_files)} 个SQLite文件，检查占用进程...")

            terminated_processes = []

            # 遍历所有运行的进程
            for proc in psutil.process_iter(['pid', 'name', 'open_files']):
                try:
                    # 检查进程是否打开了我们的SQLite文件
                    if proc.info['open_files']:
                        for file_info in proc.info['open_files']:
                            file_path = Path(file_info.path)

                            # 检查是否是我们的ChromaDB文件
                            if any(sqlite_file.resolve() == file_path.resolve() for sqlite_file in sqlite_files):
                                self.logger.warning(f"发现占用文件的进程: PID={proc.info['pid']}, Name={proc.info['name']}, File={file_path}")

                                # 尝试友好地终止进程
                                try:
                                    process = psutil.Process(proc.info['pid'])
                                    process.terminate()
                                    self.logger.info(f"已发送终止信号给进程 {proc.info['pid']}")
                                    terminated_processes.append(proc.info['pid'])
                                except (psutil.NoSuchProcess, psutil.AccessDenied):
                                    self.logger.debug(f"无法终止进程 {proc.info['pid']}")

                except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                    # 进程可能已经结束或无权限访问
                    continue

            # 等待进程终止
            if terminated_processes:
                self.logger.info(f"等待 {len(terminated_processes)} 个进程终止...")
                import time
                time.sleep(2)

                # 检查是否还有未终止的进程，强制杀死
                for pid in terminated_processes:
                    try:
                        process = psutil.Process(pid)
                        if process.is_running():
                            self.logger.warning(f"强制杀死进程 {pid}")
                            process.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

                time.sleep(1)
                self.logger.info("进程清理完成")

        except ImportError:
            self.logger.warning("psutil未安装，无法检查占用进程，使用简单的进程终止方法")
            self._simple_process_termination()
        except Exception as e:
            self.logger.warning(f"进程检查失败: {e}")

    def _simple_process_termination(self):
        """简单的进程终止方法（不依赖psutil）"""
        try:
            import subprocess
            import platform

            if platform.system() == "Windows":
                # Windows下使用taskkill强制终止可能的Python进程
                try:
                    # 查找占用文件的句柄
                    result = subprocess.run(
                        ['wmic', 'process', 'where', 'name="python.exe"', 'get', 'ProcessId'],
                        capture_output=True, text=True, timeout=10
                    )

                    if result.returncode == 0:
                        # 解析输出，获取PID
                        lines = result.stdout.strip().split('\n')[1:]  # 跳过标题行
                        for line in lines:
                            line = line.strip()
                            if line and line.isdigit():
                                pid = int(line)
                                try:
                                    # 检查是否是当前进程
                                    import os
                                    if pid != os.getpid():
                                        subprocess.run(['taskkill', '/F', '/PID', str(pid)],
                                                     capture_output=True, timeout=5)
                                        self.logger.info(f"终止了Python进程 {pid}")
                                except Exception:
                                    pass

                except Exception as e:
                    self.logger.debug(f"简单进程终止失败: {e}")

        except Exception as e:
            self.logger.debug(f"简单进程终止方法失败: {e}")