"""
Author: zhuanglaihong
Date: 2025-09-29 16:00:00
LastEditTime: 2025-09-29 16:00:00
LastEditors: zhuanglaihong
Description: 知识库更新模块，负责知识库的增量更新、版本管理和自动维护
FilePath: \HydroAgent\hydrorag\knowledge_updater.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import logging
import json
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta
import hashlib
import time

logger = logging.getLogger(__name__)


class KnowledgeUpdater:
    """知识库更新器 - 负责知识库的增量更新、版本管理和自动维护"""

    def __init__(self, config, rag_system=None):
        """
        初始化知识库更新器

        Args:
            config: 配置对象
            rag_system: RAG系统实例（可选，用于更新操作）
        """
        self.config = config
        self.rag_system = rag_system

        # 路径配置
        self.raw_dir = Path(getattr(config, 'raw_documents_dir', './documents/raw'))
        self.processed_dir = Path(getattr(config, 'processed_documents_dir', './documents/processed'))
        self.backup_dir = Path(getattr(config, 'backup_dir', './documents/backups'))
        self.update_log_file = self.backup_dir / 'update_log.json'

        # 更新配置
        self.check_interval = getattr(config, 'UPDATE_CHECK_INTERVAL', 3600)  # 检查间隔（秒）
        self.auto_backup = getattr(config, 'AUTO_BACKUP', True)
        self.max_backups = getattr(config, 'MAX_BACKUPS', 10)
        self.incremental_update = getattr(config, 'INCREMENTAL_UPDATE', True)

        # 确保目录存在
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # 状态跟踪
        self.last_check_time = None
        self.update_history = []

        # 加载更新历史
        self._load_update_history()

        logger.info(f"知识库更新器初始化完成")
        logger.info(f"原始文档目录: {self.raw_dir}")
        logger.info(f"处理文档目录: {self.processed_dir}")
        logger.info(f"备份目录: {self.backup_dir}")

    def _load_update_history(self):
        """加载更新历史"""
        try:
            if self.update_log_file.exists():
                with open(self.update_log_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.update_history = data.get('history', [])
                    self.last_check_time = data.get('last_check_time')
                    if self.last_check_time:
                        self.last_check_time = datetime.fromisoformat(self.last_check_time)

                logger.info(f"加载了 {len(self.update_history)} 条更新历史记录")
            else:
                logger.info("未找到更新历史，从头开始")

        except Exception as e:
            logger.error(f"加载更新历史失败: {e}")
            self.update_history = []
            self.last_check_time = None

    def _save_update_history(self):
        """保存更新历史"""
        try:
            data = {
                'history': self.update_history[-100:],  # 只保留最近100条记录
                'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None,
                'last_updated': datetime.now().isoformat()
            }

            with open(self.update_log_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"保存更新历史失败: {e}")

    def check_for_updates(self) -> Dict[str, Any]:
        """
        检查是否有文档需要更新

        Returns:
            Dict[str, Any]: 检查结果
        """
        try:
            logger.info("开始检查文档更新...")

            # 扫描原始文档
            current_files = self._scan_raw_documents()
            if not current_files:
                return {
                    "status": "no_documents",
                    "message": "未找到原始文档",
                    "changes": {}
                }

            # 获取上次处理的文档状态
            last_state = self._get_last_document_state()

            # 检测变更
            changes = self._detect_changes(current_files, last_state)

            # 更新检查时间
            self.last_check_time = datetime.now()

            # 记录检查结果
            check_result = {
                "status": "completed",
                "check_time": self.last_check_time.isoformat(),
                "total_files": len(current_files),
                "changes": changes,
                "summary": {
                    "new_files": len(changes.get("new", [])),
                    "modified_files": len(changes.get("modified", [])),
                    "deleted_files": len(changes.get("deleted", [])),
                    "unchanged_files": len(changes.get("unchanged", []))
                }
            }

            logger.info(f"检查完成: 新增 {check_result['summary']['new_files']}, "
                       f"修改 {check_result['summary']['modified_files']}, "
                       f"删除 {check_result['summary']['deleted_files']}")

            return check_result

        except Exception as e:
            logger.error(f"检查更新失败: {e}")
            return {"status": "error", "error": str(e)}

    def _scan_raw_documents(self) -> Dict[str, Dict[str, Any]]:
        """扫描原始文档目录"""
        try:
            files_info = {}

            if not self.raw_dir.exists():
                logger.warning(f"原始文档目录不存在: {self.raw_dir}")
                return files_info

            supported_extensions = getattr(self.config, 'RAG_SUPPORTED_EXTENSIONS',
                                         ['.txt', '.md', '.markdown', '.rst', '.pdf', '.docx', '.doc', '.py', '.yaml', '.yml', '.json'])

            for file_path in self.raw_dir.rglob('*'):
                if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                    try:
                        stat = file_path.stat()
                        file_hash = self._get_file_hash(file_path)

                        files_info[str(file_path)] = {
                            "path": str(file_path),
                            "size": stat.st_size,
                            "mtime": stat.st_mtime,
                            "hash": file_hash,
                            "relative_path": str(file_path.relative_to(self.raw_dir))
                        }

                    except Exception as e:
                        logger.error(f"处理文件信息失败 {file_path}: {e}")

            logger.debug(f"扫描到 {len(files_info)} 个文档文件")
            return files_info

        except Exception as e:
            logger.error(f"扫描原始文档失败: {e}")
            return {}

    def _get_file_hash(self, file_path: Path) -> str:
        """计算文件哈希值"""
        try:
            hasher = hashlib.md5()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            logger.error(f"计算文件哈希失败 {file_path}: {e}")
            return ""

    def _get_last_document_state(self) -> Dict[str, Dict[str, Any]]:
        """获取上次处理的文档状态"""
        try:
            if not self.update_history:
                return {}

            # 找到最近一次成功的更新记录
            for record in reversed(self.update_history):
                if record.get("status") == "success" and "document_state" in record:
                    return record["document_state"]

            return {}

        except Exception as e:
            logger.error(f"获取文档状态失败: {e}")
            return {}

    def _detect_changes(self, current_files: Dict[str, Dict[str, Any]],
                       last_state: Dict[str, Dict[str, Any]]) -> Dict[str, List[str]]:
        """检测文档变更"""
        try:
            changes = {
                "new": [],
                "modified": [],
                "deleted": [],
                "unchanged": []
            }

            # 检查新增和修改的文件
            for file_path, file_info in current_files.items():
                if file_path not in last_state:
                    changes["new"].append(file_path)
                else:
                    last_info = last_state[file_path]
                    if (file_info["hash"] != last_info.get("hash") or
                        file_info["mtime"] != last_info.get("mtime")):
                        changes["modified"].append(file_path)
                    else:
                        changes["unchanged"].append(file_path)

            # 检查删除的文件
            for file_path in last_state:
                if file_path not in current_files:
                    changes["deleted"].append(file_path)

            return changes

        except Exception as e:
            logger.error(f"检测变更失败: {e}")
            return {"new": [], "modified": [], "deleted": [], "unchanged": []}

    def update_knowledge_base(self, force_full_update: bool = False) -> Dict[str, Any]:
        """
        更新知识库

        Args:
            force_full_update: 是否强制全量更新

        Returns:
            Dict[str, Any]: 更新结果
        """
        try:
            logger.info("开始更新知识库...")
            start_time = datetime.now()

            # 检查更新
            check_result = self.check_for_updates()
            if check_result["status"] != "completed":
                return check_result

            changes = check_result["changes"]
            has_changes = (len(changes["new"]) > 0 or
                         len(changes["modified"]) > 0 or
                         len(changes["deleted"]) > 0)

            if not has_changes and not force_full_update:
                logger.info("没有检测到变更，跳过更新")
                return {
                    "status": "no_changes",
                    "message": "没有检测到文档变更",
                    "check_result": check_result
                }

            # 备份（如果启用）
            backup_result = None
            if self.auto_backup:
                backup_result = self.create_backup()
                if backup_result["status"] != "success":
                    logger.warning(f"备份失败: {backup_result}")

            update_result = {
                "status": "success",
                "start_time": start_time.isoformat(),
                "changes": changes,
                "backup": backup_result,
                "steps": {}
            }

            try:
                # 执行更新步骤
                if force_full_update:
                    # 全量更新
                    logger.info("执行全量更新...")
                    full_update_result = self._perform_full_update()
                    update_result["steps"]["full_update"] = full_update_result
                else:
                    # 增量更新
                    logger.info("执行增量更新...")
                    incremental_result = self._perform_incremental_update(changes)
                    update_result["steps"]["incremental_update"] = incremental_result

                # 记录成功的文档状态
                current_files = self._scan_raw_documents()
                update_result["document_state"] = current_files

                # 计算更新时间
                end_time = datetime.now()
                update_result["end_time"] = end_time.isoformat()
                update_result["duration"] = (end_time - start_time).total_seconds()

                logger.info(f"知识库更新完成，耗时 {update_result['duration']:.2f} 秒")

            except Exception as e:
                update_result["status"] = "error"
                update_result["error"] = str(e)
                logger.error(f"更新过程中出错: {e}")

            # 记录更新历史
            self.update_history.append(update_result)
            self._save_update_history()

            # 清理旧备份
            if self.auto_backup:
                self._cleanup_old_backups()

            return update_result

        except Exception as e:
            logger.error(f"更新知识库失败: {e}")
            return {"status": "error", "error": str(e)}

    def _perform_full_update(self) -> Dict[str, Any]:
        """执行全量更新"""
        try:
            if not self.rag_system:
                return {"status": "error", "error": "RAG系统未初始化"}

            # 清理现有数据
            logger.info("清理现有处理数据...")
            if hasattr(self.rag_system.document_processor, 'clean_processed_documents'):
                self.rag_system.document_processor.clean_processed_documents()

            if hasattr(self.rag_system.vector_store, 'clear_collection'):
                clear_result = self.rag_system.vector_store.clear_collection()
                logger.info(f"清理向量库: {clear_result}")

            # 重新设置系统
            logger.info("重新构建知识库...")
            setup_result = self.rag_system.setup_from_raw_documents()

            return {
                "status": "success",
                "type": "full_update",
                "setup_result": setup_result
            }

        except Exception as e:
            logger.error(f"全量更新失败: {e}")
            return {"status": "error", "error": str(e)}

    def _perform_incremental_update(self, changes: Dict[str, List[str]]) -> Dict[str, Any]:
        """执行增量更新"""
        try:
            if not self.rag_system:
                return {"status": "error", "error": "RAG系统未初始化"}

            result = {
                "status": "success",
                "type": "incremental_update",
                "processed": {
                    "new": 0,
                    "modified": 0,
                    "deleted": 0
                },
                "details": []
            }

            # 处理新增和修改的文件
            files_to_process = changes["new"] + changes["modified"]

            if files_to_process:
                logger.info(f"处理 {len(files_to_process)} 个新增/修改的文件...")

                for file_path in files_to_process:
                    try:
                        path_obj = Path(file_path)
                        if not path_obj.exists():
                            continue

                        # 处理单个文档
                        process_result = self.rag_system.document_processor.process_document(path_obj)

                        if process_result["status"] == "success":
                            # 获取处理后的文档块
                            processed_file = process_result.get("processed_file")
                            if processed_file and Path(processed_file).exists():
                                with open(processed_file, 'r', encoding='utf-8') as f:
                                    doc_data = json.load(f)

                                chunks = doc_data.get("chunks", [])
                                if chunks:
                                    # 添加到向量数据库
                                    add_result = self.rag_system.vector_store.add_documents(chunks)
                                    if add_result.get("status") == "success":
                                        if file_path in changes["new"]:
                                            result["processed"]["new"] += 1
                                        else:
                                            result["processed"]["modified"] += 1

                                        result["details"].append({
                                            "file": file_path,
                                            "action": "processed",
                                            "chunks": len(chunks)
                                        })
                                    else:
                                        logger.error(f"添加向量失败: {add_result}")
                                        result["details"].append({
                                            "file": file_path,
                                            "action": "vector_add_failed",
                                            "error": add_result.get("error")
                                        })

                    except Exception as e:
                        logger.error(f"处理文件失败 {file_path}: {e}")
                        result["details"].append({
                            "file": file_path,
                            "action": "failed",
                            "error": str(e)
                        })

            # 处理删除的文件（FAISS不支持直接删除，记录但不处理）
            if changes["deleted"]:
                logger.warning(f"检测到 {len(changes['deleted'])} 个删除的文件，FAISS不支持直接删除")
                for file_path in changes["deleted"]:
                    result["details"].append({
                        "file": file_path,
                        "action": "deleted_detected",
                        "note": "FAISS不支持直接删除，需要全量重建"
                    })

            logger.info(f"增量更新完成: 新增 {result['processed']['new']}, "
                       f"修改 {result['processed']['modified']}")

            return result

        except Exception as e:
            logger.error(f"增量更新失败: {e}")
            return {"status": "error", "error": str(e)}

    def create_backup(self, backup_name: Optional[str] = None) -> Dict[str, Any]:
        """
        创建知识库备份

        Args:
            backup_name: 备份名称（可选）

        Returns:
            Dict[str, Any]: 备份结果
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if not backup_name:
                backup_name = f"knowledge_backup_{timestamp}"

            backup_path = self.backup_dir / backup_name
            backup_path.mkdir(parents=True, exist_ok=True)

            logger.info(f"创建知识库备份: {backup_path}")

            backup_info = {
                "backup_name": backup_name,
                "backup_time": datetime.now().isoformat(),
                "backup_path": str(backup_path),
                "components": {}
            }

            # 备份处理后的文档
            if self.processed_dir.exists():
                processed_backup = backup_path / "processed_documents"
                shutil.copytree(self.processed_dir, processed_backup, dirs_exist_ok=True)
                backup_info["components"]["processed_documents"] = str(processed_backup)
                logger.info("备份处理后的文档完成")

            # 备份向量数据库
            if self.rag_system and hasattr(self.rag_system.vector_store, 'backup_collection'):
                vector_backup_file = backup_path / "vector_store.json"
                vector_result = self.rag_system.vector_store.backup_collection(str(vector_backup_file))
                if vector_result.get("status") == "success":
                    backup_info["components"]["vector_store"] = str(vector_backup_file)
                    logger.info("备份向量数据库完成")

            # 保存备份信息
            backup_info_file = backup_path / "backup_info.json"
            with open(backup_info_file, 'w', encoding='utf-8') as f:
                json.dump(backup_info, f, ensure_ascii=False, indent=2)

            logger.info(f"知识库备份创建完成: {backup_path}")

            return {
                "status": "success",
                "backup_name": backup_name,
                "backup_path": str(backup_path),
                "backup_info": backup_info
            }

        except Exception as e:
            logger.error(f"创建备份失败: {e}")
            return {"status": "error", "error": str(e)}

    def restore_backup(self, backup_name: str) -> Dict[str, Any]:
        """
        从备份恢复知识库

        Args:
            backup_name: 备份名称

        Returns:
            Dict[str, Any]: 恢复结果
        """
        try:
            backup_path = self.backup_dir / backup_name
            backup_info_file = backup_path / "backup_info.json"

            if not backup_path.exists() or not backup_info_file.exists():
                return {"status": "error", "error": f"备份不存在: {backup_name}"}

            logger.info(f"从备份恢复知识库: {backup_path}")

            # 读取备份信息
            with open(backup_info_file, 'r', encoding='utf-8') as f:
                backup_info = json.load(f)

            restore_result = {
                "status": "success",
                "backup_name": backup_name,
                "backup_time": backup_info.get("backup_time"),
                "restored_components": {}
            }

            # 恢复处理后的文档
            processed_backup = backup_path / "processed_documents"
            if processed_backup.exists():
                if self.processed_dir.exists():
                    shutil.rmtree(self.processed_dir)
                shutil.copytree(processed_backup, self.processed_dir)
                restore_result["restored_components"]["processed_documents"] = True
                logger.info("恢复处理后的文档完成")

            # 恢复向量数据库
            vector_backup_file = backup_path / "vector_store.json"
            if vector_backup_file.exists() and self.rag_system:
                if hasattr(self.rag_system.vector_store, 'restore_collection'):
                    vector_result = self.rag_system.vector_store.restore_collection(str(vector_backup_file))
                    restore_result["restored_components"]["vector_store"] = vector_result
                    logger.info("恢复向量数据库完成")

            logger.info(f"知识库恢复完成: {backup_name}")

            # 记录恢复操作
            restore_record = {
                "action": "restore",
                "backup_name": backup_name,
                "restore_time": datetime.now().isoformat(),
                "status": "success"
            }
            self.update_history.append(restore_record)
            self._save_update_history()

            return restore_result

        except Exception as e:
            logger.error(f"恢复备份失败: {e}")
            return {"status": "error", "error": str(e)}

    def _cleanup_old_backups(self):
        """清理旧备份"""
        try:
            if not self.backup_dir.exists():
                return

            # 获取所有备份目录
            backup_dirs = [d for d in self.backup_dir.iterdir()
                          if d.is_dir() and d.name.startswith('knowledge_backup_')]

            # 按创建时间排序
            backup_dirs.sort(key=lambda x: x.stat().st_ctime, reverse=True)

            # 删除超出限制的备份
            if len(backup_dirs) > self.max_backups:
                for backup_dir in backup_dirs[self.max_backups:]:
                    try:
                        shutil.rmtree(backup_dir)
                        logger.info(f"删除旧备份: {backup_dir.name}")
                    except Exception as e:
                        logger.error(f"删除备份失败 {backup_dir}: {e}")

        except Exception as e:
            logger.error(f"清理旧备份失败: {e}")

    def list_backups(self) -> List[Dict[str, Any]]:
        """列出所有备份"""
        try:
            backups = []

            if not self.backup_dir.exists():
                return backups

            for backup_dir in self.backup_dir.iterdir():
                if backup_dir.is_dir():
                    info_file = backup_dir / "backup_info.json"
                    if info_file.exists():
                        try:
                            with open(info_file, 'r', encoding='utf-8') as f:
                                backup_info = json.load(f)
                            backups.append(backup_info)
                        except Exception as e:
                            logger.error(f"读取备份信息失败 {backup_dir}: {e}")

            # 按时间排序
            backups.sort(key=lambda x: x.get("backup_time", ""), reverse=True)
            return backups

        except Exception as e:
            logger.error(f"列出备份失败: {e}")
            return []

    def get_update_history(self) -> List[Dict[str, Any]]:
        """获取更新历史"""
        return self.update_history.copy()

    def get_status(self) -> Dict[str, Any]:
        """获取更新器状态"""
        try:
            recent_updates = self.update_history[-5:] if self.update_history else []

            return {
                "last_check_time": self.last_check_time.isoformat() if self.last_check_time else None,
                "total_updates": len(self.update_history),
                "recent_updates": recent_updates,
                "config": {
                    "check_interval": self.check_interval,
                    "auto_backup": self.auto_backup,
                    "max_backups": self.max_backups,
                    "incremental_update": self.incremental_update
                },
                "directories": {
                    "raw_dir": str(self.raw_dir),
                    "processed_dir": str(self.processed_dir),
                    "backup_dir": str(self.backup_dir)
                }
            }

        except Exception as e:
            logger.error(f"获取状态失败: {e}")
            return {"error": str(e)}