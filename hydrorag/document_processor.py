"""
文档处理器
负责将raw目录中的原始文档转换为processed目录中的处理后文档
支持多种文件格式的文本提取和分块处理
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import hashlib
import json
from datetime import datetime

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """文档处理器 - 处理原始文档并转换为可嵌入的文本格式"""
    
    def __init__(self, config):
        """
        初始化文档处理器
        
        Args:
            config: 配置对象
        """
        self.config = config
        self.raw_dir = Path(config.raw_documents_dir)
        self.processed_dir = Path(config.processed_documents_dir)
        
        # 确保目录存在
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化文档加载器
        self._init_loaders()
        
        logger.info(f"文档处理器初始化完成")
        logger.info(f"原始文档目录: {self.raw_dir}")
        logger.info(f"处理后文档目录: {self.processed_dir}")
    
    def _init_loaders(self):
        """初始化各种文档加载器"""
        self.loaders = {}
        
        try:
            # PDF加载器
            try:
                from langchain_community.document_loaders import PyPDFLoader
                self.loaders['.pdf'] = PyPDFLoader
                logger.info("PDF加载器已初始化")
            except ImportError:
                logger.warning("PyPDFLoader不可用，将跳过PDF文件")
            
            # Word文档加载器
            try:
                from langchain_community.document_loaders import Docx2txtLoader
                self.loaders['.docx'] = Docx2txtLoader
                self.loaders['.doc'] = Docx2txtLoader
                logger.info("Word文档加载器已初始化")
            except ImportError:
                logger.warning("Docx2txtLoader不可用，将跳过Word文件")
            
            # 文本文件加载器
            from langchain_community.document_loaders import TextLoader
            self.loaders['.txt'] = TextLoader
            self.loaders['.md'] = TextLoader
            self.loaders['.markdown'] = TextLoader
            self.loaders['.rst'] = TextLoader
            self.loaders['.py'] = TextLoader
            self.loaders['.yaml'] = TextLoader
            self.loaders['.yml'] = TextLoader
            self.loaders['.json'] = TextLoader
            logger.info("文本文件加载器已初始化")
            
        except Exception as e:
            logger.error(f"初始化文档加载器失败: {e}")
    
    def scan_raw_documents(self) -> List[Path]:
        """扫描原始文档目录，返回支持的文件列表"""
        supported_files = []
        
        try:
            for file_path in self.raw_dir.rglob('*'):
                if file_path.is_file():
                    suffix = file_path.suffix.lower()
                    if suffix in self.config.supported_file_extensions:
                        supported_files.append(file_path)
                        logger.debug(f"发现支持的文件: {file_path}")
                    else:
                        logger.debug(f"跳过不支持的文件: {file_path}")
            
            logger.info(f"扫描完成，发现 {len(supported_files)} 个支持的文件")
            return supported_files
            
        except Exception as e:
            logger.error(f"扫描原始文档失败: {e}")
            return []
    
    def process_document(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        处理单个文档
        
        Args:
            file_path: 文档路径
            
        Returns:
            Dict: 处理结果信息
        """
        try:
            logger.info(f"开始处理文档: {file_path}")
            
            # 检查文件是否已经处理过且未修改
            if self._is_document_processed(file_path):
                logger.info(f"文档已处理且未修改，跳过: {file_path}")
                return {"status": "skipped", "reason": "already_processed"}
            
            # 加载文档内容
            content = self._load_document_content(file_path)
            if not content:
                logger.warning(f"无法加载文档内容: {file_path}")
                return {"status": "failed", "reason": "content_loading_failed"}
            
            # 分块处理
            chunks = self._split_document(content, file_path)
            if not chunks:
                logger.warning(f"文档分块失败: {file_path}")
                return {"status": "failed", "reason": "chunking_failed"}
            
            # 保存处理后的文档
            processed_info = self._save_processed_document(file_path, chunks)
            
            logger.info(f"文档处理完成: {file_path}, 生成 {len(chunks)} 个文本块")
            
            return {
                "status": "success",
                "source_file": str(file_path),
                "chunks_count": len(chunks),
                "processed_file": processed_info["processed_file"],
                "metadata_file": processed_info["metadata_file"]
            }
            
        except Exception as e:
            logger.error(f"处理文档失败 {file_path}: {e}")
            return {"status": "failed", "reason": str(e)}
    
    def _load_document_content(self, file_path: Path) -> Optional[str]:
        """加载文档内容"""
        try:
            suffix = file_path.suffix.lower()
            
            # 对于文本文件，直接读取，不使用LangChain加载器
            text_extensions = ['.txt', '.md', '.markdown', '.rst', '.py', '.yaml', '.yml', '.json']
            
            if suffix in text_extensions:
                # 直接读取文本文件
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    return content
            elif suffix in self.loaders:
                # 使用对应的加载器（PDF、Word等）
                loader_class = self.loaders[suffix]
                try:
                    loader = loader_class(str(file_path))
                    documents = loader.load()
                    
                    # 合并所有页面/部分的内容
                    content = "\n\n".join([doc.page_content for doc in documents])
                    return content
                except Exception as loader_error:
                    logger.warning(f"LangChain加载器失败，尝试直接读取: {loader_error}")
                    # 如果加载器失败，尝试直接读取
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        return f.read()
            else:
                # 默认作为文本文件处理
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()
                    
        except Exception as e:
            logger.error(f"加载文档内容失败 {file_path}: {e}")
            return None
    
    def _split_document(self, content: str, file_path: Path) -> List[Dict[str, Any]]:
        """将文档内容分块"""
        try:
            # 简单的文本分块实现，不依赖LangChain
            chunk_size = self.config.chunk_size
            chunk_overlap = self.config.chunk_overlap
            
            # 首先按段落分割
            paragraphs = content.split('\n\n')
            
            chunks = []
            current_chunk = ""
            chunk_index = 0
            
            for paragraph in paragraphs:
                paragraph = paragraph.strip()
                if not paragraph:
                    continue
                
                # 如果当前块加上新段落超过了chunk_size
                if len(current_chunk) + len(paragraph) + 2 > chunk_size and current_chunk:
                    # 保存当前块
                    chunk = {
                        "chunk_id": f"{file_path.stem}_{chunk_index:04d}",
                        "content": current_chunk.strip(),
                        "source_file": str(file_path),
                        "chunk_index": chunk_index,
                        "chunk_size": len(current_chunk),
                        "metadata": {
                            "file_name": file_path.name,
                            "file_extension": file_path.suffix,
                            "file_size": file_path.stat().st_size
                        }
                    }
                    chunks.append(chunk)
                    chunk_index += 1
                    
                    # 开始新块，包含重叠部分
                    if chunk_overlap > 0 and len(current_chunk) > chunk_overlap:
                        current_chunk = current_chunk[-chunk_overlap:] + "\n\n" + paragraph
                    else:
                        current_chunk = paragraph
                else:
                    # 添加到当前块
                    if current_chunk:
                        current_chunk += "\n\n" + paragraph
                    else:
                        current_chunk = paragraph
            
            # 保存最后一个块
            if current_chunk.strip():
                chunk = {
                    "chunk_id": f"{file_path.stem}_{chunk_index:04d}",
                    "content": current_chunk.strip(),
                    "source_file": str(file_path),
                    "chunk_index": chunk_index,
                    "chunk_size": len(current_chunk),
                    "metadata": {
                        "file_name": file_path.name,
                        "file_extension": file_path.suffix,
                        "file_size": file_path.stat().st_size
                    }
                }
                chunks.append(chunk)
            
            # 更新总块数
            for chunk in chunks:
                chunk["metadata"]["total_chunks"] = len(chunks)
            
            return chunks
            
        except Exception as e:
            logger.error(f"文档分块失败 {file_path}: {e}")
            return []
    
    def _save_processed_document(self, source_file: Path, chunks: List[Dict[str, Any]]) -> Dict[str, str]:
        """保存处理后的文档"""
        try:
            # 生成处理后文件的路径
            relative_path = source_file.relative_to(self.raw_dir)
            processed_name = f"{relative_path.stem}_processed.json"
            processed_file = self.processed_dir / processed_name
            
            # 确保子目录存在
            processed_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 准备保存的数据
            processed_data = {
                "source_file": str(source_file),
                "processed_time": datetime.now().isoformat(),
                "source_file_hash": self._get_file_hash(source_file),
                "config": {
                    "chunk_size": self.config.chunk_size,
                    "chunk_overlap": self.config.chunk_overlap
                },
                "chunks": chunks
            }
            
            # 保存处理后的数据
            with open(processed_file, 'w', encoding='utf-8') as f:
                json.dump(processed_data, f, ensure_ascii=False, indent=2)
            
            # 保存元数据
            metadata_file = processed_file.with_suffix('.meta.json')
            metadata = {
                "source_file": str(source_file),
                "processed_file": str(processed_file),
                "source_file_hash": processed_data["source_file_hash"],
                "processed_time": processed_data["processed_time"],
                "chunks_count": len(chunks),
                "total_chars": sum(len(chunk["content"]) for chunk in chunks)
            }
            
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            return {
                "processed_file": str(processed_file),
                "metadata_file": str(metadata_file)
            }
            
        except Exception as e:
            logger.error(f"保存处理后文档失败: {e}")
            raise
    
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
    
    def _is_document_processed(self, file_path: Path) -> bool:
        """检查文档是否已经处理过且未修改"""
        try:
            # 生成对应的元数据文件路径
            relative_path = file_path.relative_to(self.raw_dir)
            metadata_name = f"{relative_path.stem}_processed.meta.json"
            metadata_file = self.processed_dir / metadata_name
            
            if not metadata_file.exists():
                return False
            
            # 读取元数据
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            # 比较文件哈希
            current_hash = self._get_file_hash(file_path)
            stored_hash = metadata.get("source_file_hash", "")
            
            return current_hash == stored_hash
            
        except Exception as e:
            logger.error(f"检查文档处理状态失败 {file_path}: {e}")
            return False
    
    def process_all_documents(self) -> Dict[str, Any]:
        """处理所有原始文档"""
        try:
            logger.info("开始处理所有原始文档")
            
            # 扫描文档
            files = self.scan_raw_documents()
            if not files:
                logger.warning("未找到需要处理的文档")
                return {"status": "no_documents", "processed": 0, "failed": 0, "skipped": 0}
            
            # 处理统计
            results = {
                "processed": 0,
                "failed": 0,
                "skipped": 0,
                "details": []
            }
            
            # 逐个处理文档
            for file_path in files:
                result = self.process_document(file_path)
                results["details"].append(result)
                
                if result["status"] == "success":
                    results["processed"] += 1
                elif result["status"] == "failed":
                    results["failed"] += 1
                elif result["status"] == "skipped":
                    results["skipped"] += 1
            
            logger.info(f"文档处理完成: 成功 {results['processed']}, 失败 {results['failed']}, 跳过 {results['skipped']}")
            
            return {
                "status": "completed",
                **results
            }
            
        except Exception as e:
            logger.error(f"批量处理文档失败: {e}")
            return {"status": "error", "error": str(e)}
    
    def get_processed_documents(self) -> List[Dict[str, Any]]:
        """获取所有已处理的文档信息"""
        try:
            processed_docs = []
            
            for meta_file in self.processed_dir.glob("*.meta.json"):
                try:
                    with open(meta_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    processed_docs.append(metadata)
                except Exception as e:
                    logger.error(f"读取元数据文件失败 {meta_file}: {e}")
            
            logger.info(f"找到 {len(processed_docs)} 个已处理的文档")
            return processed_docs
            
        except Exception as e:
            logger.error(f"获取已处理文档失败: {e}")
            return []
    
    def clean_processed_documents(self):
        """清理所有已处理的文档"""
        try:
            logger.info("开始清理已处理的文档")
            
            count = 0
            for file_path in self.processed_dir.rglob("*"):
                if file_path.is_file():
                    file_path.unlink()
                    count += 1
            
            logger.info(f"清理完成，删除了 {count} 个文件")
            
        except Exception as e:
            logger.error(f"清理已处理文档失败: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取处理统计信息"""
        try:
            raw_files = self.scan_raw_documents()
            processed_docs = self.get_processed_documents()
            
            total_chunks = 0
            total_chars = 0
            
            for doc in processed_docs:
                total_chunks += doc.get("chunks_count", 0)
                total_chars += doc.get("total_chars", 0)
            
            return {
                "raw_documents_count": len(raw_files),
                "processed_documents_count": len(processed_docs),
                "total_chunks": total_chunks,
                "total_characters": total_chars,
                "average_chunk_size": total_chars / total_chunks if total_chunks > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}
