"""
Author: zhuanglaihong
Date: 2024-09-24 15:30:00
LastEditTime: 2025-09-27 15:00:00
LastEditors: zhuanglaihong
Description: 文档处理器，负责将raw目录中的原始文档转换为processed目录中的处理后文档，支持多种文件格式的文本提取和分块处理
FilePath: \HydroAgent\hydrorag\document_processor.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import os
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import hashlib
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import math

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """文档处理器 - 处理原始文档并转换为可嵌入的文本格式，支持智能分块和并行处理"""
    
    def __init__(self, config):
        """
        初始化文档处理器
        
        Args:
            config: 配置对象
        """
        self.config = config
        self.raw_dir = Path(config.raw_documents_dir)
        self.processed_dir = Path(config.processed_documents_dir)

        # 从配置中获取参数
        self.chunk_size = getattr(config, 'RAG_CHUNK_SIZE', 1000)
        self.chunk_overlap = getattr(config, 'RAG_CHUNK_OVERLAP', 200)
        self.max_chunk_size = getattr(config, 'RAG_MAX_CHUNK_SIZE', 2000)
        self.supported_extensions = getattr(config, 'RAG_SUPPORTED_EXTENSIONS',
                                          ['.txt', '.md', '.markdown', '.rst', '.pdf', '.docx', '.doc', '.py', '.yaml', '.yml', '.json'])

        # 确保目录存在
        self.processed_dir.mkdir(parents=True, exist_ok=True)

        # 初始化文档加载器
        self._init_loaders()

        # 初始化文本分割器
        self._init_text_splitters()

        logger.info(f"文档处理器初始化完成")
        logger.info(f"原始文档目录: {self.raw_dir}")
        logger.info(f"处理后文档目录: {self.processed_dir}")
        logger.info(f"分块参数: 大小={self.chunk_size}, 重叠={self.chunk_overlap}, 最大={self.max_chunk_size}")
    
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
                    if suffix in self.supported_extensions:
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
            
            # 内容质量检查
            content = self._clean_and_validate_content(content)
            if not content or len(content.strip()) < 50:  # 过短的内容
                logger.warning(f"文档内容过短或为空: {file_path}")
                return {"status": "failed", "reason": "content_too_short"}

            # 智能分块处理
            chunks = self._intelligent_split_document(content, file_path)
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
    
    def _init_text_splitters(self):
        """初始化文本分割器"""
        self.sentence_endings = re.compile(r'[.!?]\s+')
        self.paragraph_splitter = re.compile(r'\n\s*\n')
        self.section_headers = re.compile(r'^#{1,6}\s+.*$|^[A-Z\s]+:?$', re.MULTILINE)

    def _clean_and_validate_content(self, content: str) -> str:
        """清理和验证文档内容"""
        try:
            if not content:
                return ""

            # 移除过多的空白字符
            content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
            content = re.sub(r'[ \t]+', ' ', content)

            # 移除开头和结尾的空白
            content = content.strip()

            # 检查内容质量
            if len(content) < 50:
                return ""

            # 检查是否包含有意义的内容（不仅仅是特殊字符）
            meaningful_chars = len(re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff]', '', content))
            if meaningful_chars / len(content) < 0.1:  # 有意义字符太少
                return ""

            return content

        except Exception as e:
            logger.error(f"内容清理失败: {e}")
            return content

    def _intelligent_split_document(self, content: str, file_path: Path) -> List[Dict[str, Any]]:
        """智能文档分块（保持语义完整性）"""
        try:
            # 首先检测文档类型和结构
            doc_type = self._detect_document_type(content, file_path)

            if doc_type == 'code':
                return self._split_code_document(content, file_path)
            elif doc_type == 'markdown':
                return self._split_markdown_document(content, file_path)
            else:
                return self._split_text_document(content, file_path)

        except Exception as e:
            logger.error(f"智能分块失败 {file_path}: {e}")
            return self._split_text_document(content, file_path)  # 退回到基本分块

    def _detect_document_type(self, content: str, file_path: Path) -> str:
        """检测文档类型"""
        extension = file_path.suffix.lower()

        if extension in ['.py', '.js', '.java', '.cpp', '.c', '.h']:
            return 'code'
        elif extension in ['.md', '.markdown']:
            return 'markdown'
        elif extension in ['.rst']:
            return 'rst'
        else:
            # 通过内容特征判断
            if re.search(r'^```|^#{1,6}\s+', content, re.MULTILINE):
                return 'markdown'
            elif re.search(r'^def |^class |^import |^from ', content, re.MULTILINE):
                return 'code'
            else:
                return 'text'

    def _split_text_document(self, content: str, file_path: Path) -> List[Dict[str, Any]]:
        """分割普通文本文档"""
        chunks = []
        chunk_index = 0

        # 首先按段落分割
        paragraphs = self.paragraph_splitter.split(content)

        current_chunk = ""

        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue

            # 检查段落是否过长
            if len(paragraph) > self.max_chunk_size:
                # 对过长的段落按句子分割
                sentences = self._split_long_paragraph(paragraph)
                for sentence in sentences:
                    if self._should_create_new_chunk(current_chunk, sentence):
                        if current_chunk.strip():
                            chunks.append(self._create_chunk(current_chunk, file_path, chunk_index))
                            chunk_index += 1
                        current_chunk = self._get_overlap_text(current_chunk) + sentence
                    else:
                        current_chunk = self._add_to_chunk(current_chunk, sentence)
            else:
                # 正常段落处理
                if self._should_create_new_chunk(current_chunk, paragraph):
                    if current_chunk.strip():
                        chunks.append(self._create_chunk(current_chunk, file_path, chunk_index))
                        chunk_index += 1
                    current_chunk = self._get_overlap_text(current_chunk) + paragraph
                else:
                    current_chunk = self._add_to_chunk(current_chunk, paragraph)

        # 添加最后一个块
        if current_chunk.strip():
            chunks.append(self._create_chunk(current_chunk, file_path, chunk_index))

        # 更新元数据
        for chunk in chunks:
            chunk["metadata"]["total_chunks"] = len(chunks)

        return chunks

    def _split_markdown_document(self, content: str, file_path: Path) -> List[Dict[str, Any]]:
        """分割Markdown文档（保持结构）"""
        chunks = []
        chunk_index = 0

        # 按标题分割
        sections = re.split(r'^(#{1,6}\s+.*$)', content, flags=re.MULTILINE)

        current_section = ""
        current_header = ""

        for i, section in enumerate(sections):
            if not section.strip():
                continue

            # 检查是否是标题
            if re.match(r'^#{1,6}\s+', section):
                # 保存上一个部分
                if current_section.strip():
                    section_chunks = self._split_text_section(current_header + "\n\n" + current_section, file_path, chunk_index)
                    chunks.extend(section_chunks)
                    chunk_index += len(section_chunks)

                current_header = section
                current_section = ""
            else:
                current_section += section

        # 处理最后一个部分
        if current_section.strip():
            section_chunks = self._split_text_section(current_header + "\n\n" + current_section, file_path, chunk_index)
            chunks.extend(section_chunks)

        # 更新元数据
        for chunk in chunks:
            chunk["metadata"]["total_chunks"] = len(chunks)

        return chunks

    def _split_code_document(self, content: str, file_path: Path) -> List[Dict[str, Any]]:
        """分割代码文档（保持函数/类完整性）"""
        chunks = []
        chunk_index = 0

        # 简单的代码分割（按函数/类）
        lines = content.split('\n')
        current_chunk = ""
        current_indent = 0

        for line in lines:
            # 检测函数或类定义
            if re.match(r'^\s*(def |class |function |public |private )', line):
                # 如果当前块太大，先保存
                if len(current_chunk) > self.chunk_size and current_chunk.strip():
                    chunks.append(self._create_chunk(current_chunk, file_path, chunk_index))
                    chunk_index += 1
                    current_chunk = ""

            current_chunk += line + "\n"

            # 检查块大小
            if len(current_chunk) > self.max_chunk_size:
                chunks.append(self._create_chunk(current_chunk, file_path, chunk_index))
                chunk_index += 1
                current_chunk = ""

        # 添加最后一个块
        if current_chunk.strip():
            chunks.append(self._create_chunk(current_chunk, file_path, chunk_index))

        # 更新元数据
        for chunk in chunks:
            chunk["metadata"]["total_chunks"] = len(chunks)

        return chunks

    def _split_long_paragraph(self, paragraph: str) -> List[str]:
        """分割过长的段落"""
        sentences = self.sentence_endings.split(paragraph)
        result = []
        current = ""

        for sentence in sentences:
            if len(current + sentence) > self.chunk_size and current:
                result.append(current.strip())
                current = sentence
            else:
                current += sentence + " "

        if current.strip():
            result.append(current.strip())

        return result

    def _split_text_section(self, section: str, file_path: Path, start_index: int) -> List[Dict[str, Any]]:
        """分割文本部分"""
        if len(section) <= self.chunk_size:
            return [self._create_chunk(section, file_path, start_index)]

        # 对长部分递归分割
        return self._split_text_document(section, file_path)

    def _should_create_new_chunk(self, current_chunk: str, new_text: str) -> bool:
        """判断是否应该创建新的块"""
        if not current_chunk:
            return False
        return len(current_chunk) + len(new_text) + 2 > self.chunk_size

    def _add_to_chunk(self, current_chunk: str, new_text: str) -> str:
        """将新文本添加到当前块"""
        if current_chunk:
            return current_chunk + "\n\n" + new_text
        else:
            return new_text

    def _get_overlap_text(self, chunk: str) -> str:
        """获取重叠文本"""
        if not chunk or self.chunk_overlap <= 0:
            return ""

        if len(chunk) <= self.chunk_overlap:
            return chunk

        # 尝试在句子边界处切断
        overlap_text = chunk[-self.chunk_overlap:]

        # 查找句子结束
        sentences = self.sentence_endings.split(overlap_text)
        if len(sentences) > 1:
            return sentences[-1] + "\n\n"

        return overlap_text + "\n\n"

    def _create_chunk(self, content: str, file_path: Path, chunk_index: int) -> Dict[str, Any]:
        """创建文档块"""
        content = content.strip()
        return {
            "chunk_id": f"{file_path.stem}_{chunk_index:04d}",
            "content": content,
            "source_file": str(file_path),
            "chunk_index": chunk_index,
            "chunk_size": len(content),
            "metadata": {
                "file_name": file_path.name,
                "file_extension": file_path.suffix,
                "file_size": file_path.stat().st_size,
                "content_hash": hashlib.md5(content.encode()).hexdigest()[:8]
            }
        }
    
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
                    "chunk_size": self.chunk_size,
                    "chunk_overlap": self.chunk_overlap,
                    "max_chunk_size": self.max_chunk_size
                },
                "chunks": chunks,
                "processing_stats": {
                    "total_chunks": len(chunks),
                    "avg_chunk_size": sum(len(chunk["content"]) for chunk in chunks) / len(chunks) if chunks else 0,
                    "min_chunk_size": min(len(chunk["content"]) for chunk in chunks) if chunks else 0,
                    "max_chunk_size": max(len(chunk["content"]) for chunk in chunks) if chunks else 0
                }
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
    
    def process_all_documents(self, parallel: bool = True, max_workers: int = 4) -> Dict[str, Any]:
        """处理所有原始文档（支持并行处理）"""
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

            if parallel and len(files) > 1:
                logger.info(f"使用并行处理，最大工作线程数: {max_workers}")
                # 并行处理
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_to_file = {executor.submit(self.process_document, file_path): file_path
                                    for file_path in files}

                    for future in as_completed(future_to_file):
                        file_path = future_to_file[future]
                        try:
                            result = future.result()
                            results["details"].append(result)

                            if result["status"] == "success":
                                results["processed"] += 1
                            elif result["status"] == "failed":
                                results["failed"] += 1
                            elif result["status"] == "skipped":
                                results["skipped"] += 1

                        except Exception as e:
                            logger.error(f"并行处理文档失败 {file_path}: {e}")
                            results["failed"] += 1
                            results["details"].append({
                                "status": "failed",
                                "source_file": str(file_path),
                                "reason": str(e)
                            })
            else:
                # 顺序处理
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
                "average_chunk_size": total_chars / total_chunks if total_chunks > 0 else 0,
                "supported_extensions": self.supported_extensions,
                "chunk_config": {
                    "chunk_size": self.chunk_size,
                    "chunk_overlap": self.chunk_overlap,
                    "max_chunk_size": self.max_chunk_size
                }
            }
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}
