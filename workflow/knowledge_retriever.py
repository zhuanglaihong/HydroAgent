"""
Author: zhuanglaihong
Date: 2025-07-28
Description: 知识检索器 - 第3步：在向量数据库（FAISS/Elasticsearch）中检索 Top‑k 文档，保留核心段落或要点
"""

import logging
import os
from typing import List, Dict, Any, Optional
from pathlib import Path
import sys

# 添加项目根路径
repo_path = Path(os.path.abspath(__file__)).parent.parent
sys.path.append(str(repo_path))

from RAG import RAGSystem
from .workflow_types import KnowledgeFragment

logger = logging.getLogger(__name__)


class KnowledgeRetriever:
    """知识检索器 - 负责从本地知识库检索相关文档片段"""

    def __init__(
        self,
        rag_system=None,
        faiss_index_path: str = "./faiss_db",
        embeddings=None,
        llm=None,
        enable_fallback: bool = True,
    ):
        """
        初始化知识检索器

        Args:
            rag_system: RAG系统实例
            faiss_index_path: FAISS索引路径
            embeddings: 嵌入模型实例
            llm: 语言模型实例
            enable_fallback: 是否启用回退机制
        """
        self.rag_system = rag_system
        self.faiss_index_path = faiss_index_path
        self.embeddings = embeddings
        self.llm = llm
        self.enable_fallback = enable_fallback

        # 初始化RAG系统（如果未提供）
        if self.rag_system is None:
            self._initialize_rag_system()

        # 默认知识库（回退用）
        self._setup_default_knowledge()

        logger.info("知识检索器初始化完成")

    def _initialize_rag_system(self):
        """初始化RAG系统"""
        try:
            if self.embeddings is None:
                logger.warning("未提供嵌入模型，尝试使用默认模型")
                try:
                    from langchain_community.embeddings import HuggingFaceEmbeddings

                    self.embeddings = HuggingFaceEmbeddings(
                        model_name="sentence-transformers/all-MiniLM-L6-v2"
                    )
                except Exception as e:
                    logger.error(f"无法初始化嵌入模型: {e}")
                    self.embeddings = None

            if self.llm is None:
                logger.warning("未提供语言模型，尝试使用默认模型")
                try:
                    from langchain_ollama import ChatOllama

                    self.llm = ChatOllama(model="granite3-dense:8b", temperature=0.1)
                except Exception as e:
                    logger.error(f"无法初始化语言模型: {e}")
                    self.llm = None

            # 导入RAG系统
            try:
                from RAG import RAGSystem

                self.rag_system = RAGSystem(
                    embeddings=self.embeddings,
                    llm=self.llm,
                    index_path=self.faiss_index_path,
                )
                logger.info("RAG系统初始化成功")

                # 检查是否有现有索引
                if self._check_existing_index():
                    logger.info("发现现有知识库索引")
                else:
                    logger.info("未发现现有索引，将使用默认知识库")

            except ImportError as e:
                logger.error(f"无法导入RAG系统: {e}")
                self.rag_system = None
            except Exception as e:
                logger.error(f"RAG系统初始化失败: {e}")
                self.rag_system = None

        except Exception as e:
            logger.error(f"RAG系统初始化过程中发生错误: {e}")
            self.rag_system = None

    def _check_existing_index(self) -> bool:
        """检查是否存在现有索引"""
        if not self.rag_system:
            return False

        try:
            # 检查索引文件是否存在
            index_path = Path(self.faiss_index_path)
            if index_path.exists():
                # 检查是否有索引文件
                index_files = list(index_path.glob("*.pkl")) + list(
                    index_path.glob("*.faiss")
                )
                return len(index_files) > 0
            return False
        except Exception as e:
            logger.error(f"检查索引时发生错误: {e}")
            return False

    def _setup_default_knowledge(self):
        """设置默认知识库"""
        self.default_knowledge = [
            KnowledgeFragment(
                content="GR4J模型是一个概念性水文模型，包含4个参数：X1（土壤蓄水容量）、X2（地下水交换系数）、X3（最大地下水蓄水容量）、X4（单位线时间参数）。",
                source="水文模型基础知识",
                score=0.9,
                metadata={"category": "model_parameters", "model": "gr4j"},
            ),
            KnowledgeFragment(
                content="水文模型率定是通过优化算法调整模型参数，使模型输出与观测数据匹配的过程。常用的优化算法包括SCE-UA、遗传算法等。",
                source="模型率定理论",
                score=0.85,
                metadata={"category": "calibration", "method": "optimization"},
            ),
            KnowledgeFragment(
                content="模型评估指标包括NSE（Nash-Sutcliffe效率系数）、RMSE（均方根误差）、MAE（平均绝对误差）等。NSE值越接近1表示模型性能越好。",
                source="模型评估标准",
                score=0.8,
                metadata={"category": "evaluation", "metrics": ["nse", "rmse", "mae"]},
            ),
            KnowledgeFragment(
                content="数据预处理包括缺失值处理、异常值检测、数据格式转换、时间序列对齐等步骤，是建模前的重要准备工作。",
                source="数据预处理指南",
                score=0.75,
                metadata={
                    "category": "data_preprocessing",
                    "steps": ["cleaning", "formatting"],
                },
            ),
            KnowledgeFragment(
                content="CAMELS数据集包含美国671个流域的水文气象数据，包括日尺度的降水、温度、流量等数据，是水文建模的重要数据集。",
                source="数据集介绍",
                score=0.7,
                metadata={"category": "dataset", "name": "camels", "scale": "daily"},
            ),
        ]
        logger.info(f"设置默认知识库，包含 {len(self.default_knowledge)} 个片段")

    def retrieve_knowledge(
        self,
        expanded_query: str,
        k: int = 5,
        score_threshold: float = 0.3,
        retriever_type: str = "vector",
        use_rag_system: bool = True,
    ) -> List[KnowledgeFragment]:
        """
        检索相关知识片段

        Args:
            expanded_query: 扩展后的查询
            k: 检索数量
            score_threshold: 相关性阈值
            retriever_type: 检索器类型 ("vector", "bm25", "ensemble")
            use_rag_system: 是否使用RAG系统

        Returns:
            List[KnowledgeFragment]: 知识片段列表
        """
        try:
            logger.info(f"开始知识检索，查询: {expanded_query[:100]}...")

            # 优先使用RAG系统
            if use_rag_system and self.rag_system:
                fragments = self._retrieve_from_rag_system(
                    expanded_query, k, score_threshold, retriever_type
                )
                if fragments:
                    logger.info(f"从RAG系统检索到 {len(fragments)} 个知识片段")
                    return fragments

            # 回退到默认知识库
            if self.enable_fallback:
                logger.info("使用默认知识库进行检索")
                fragments = self._retrieve_from_default_knowledge(
                    expanded_query, k, score_threshold
                )
                logger.info(f"从默认知识库检索到 {len(fragments)} 个知识片段")
                return fragments

            logger.warning("未找到相关知识片段")
            return []

        except Exception as e:
            logger.error(f"知识检索失败: {e}")
            if self.enable_fallback:
                return self._retrieve_from_default_knowledge(
                    expanded_query, k, score_threshold
                )
            return []

    def _retrieve_from_rag_system(
        self, query: str, k: int, score_threshold: float, retriever_type: str
    ) -> List[KnowledgeFragment]:
        """从RAG系统检索知识"""
        try:
            # 使用RAG系统进行检索
            result = self.rag_system.query(
                query=query,
                retriever_name=retriever_type,
                generator_name="qa",  # 使用问答生成器
                k=k,
                score_threshold=score_threshold,
            )

            # 解析RAG结果
            fragments = self._parse_rag_result(result, query)
            return fragments

        except Exception as e:
            logger.error(f"RAG系统检索失败: {e}")
            return []

    def _parse_rag_result(
        self, rag_result: Dict[str, Any], query: str
    ) -> List[KnowledgeFragment]:
        """解析RAG系统返回的结果"""
        fragments = []

        try:
            # 提取检索到的文档
            if "documents" in rag_result:
                for i, doc in enumerate(rag_result["documents"]):
                    fragment = KnowledgeFragment(
                        content=doc.page_content,
                        source=doc.metadata.get("source", "RAG系统"),
                        score=(
                            rag_result.get("scores", [1.0])[i]
                            if "scores" in rag_result
                            else 0.8
                        ),
                        metadata={
                            "retrieved_from": "rag_system",
                            "original_metadata": doc.metadata,
                            "query": query,
                        },
                    )
                    fragments.append(fragment)

            # 如果没有文档但有答案，创建一个包含答案的片段
            elif "answer" in rag_result and rag_result["answer"]:
                fragment = KnowledgeFragment(
                    content=f"基于检索结果生成的答案: {rag_result['answer']}",
                    source="RAG系统生成",
                    score=0.9,
                    metadata={
                        "retrieved_from": "rag_generated",
                        "query": query,
                        "has_answer": True,
                    },
                )
                fragments.append(fragment)

        except Exception as e:
            logger.error(f"解析RAG结果失败: {e}")

        return fragments

    def _retrieve_from_default_knowledge(
        self, query: str, k: int, score_threshold: float
    ) -> List[KnowledgeFragment]:
        """从默认知识库检索知识"""
        try:
            # 简单的关键词匹配
            query_lower = query.lower()
            relevant_fragments = []

            for fragment in self.default_knowledge:
                # 计算简单的相关性分数
                score = self._calculate_simple_relevance(fragment.content, query_lower)

                if score >= score_threshold:
                    # 创建新的片段，更新分数
                    new_fragment = KnowledgeFragment(
                        content=fragment.content,
                        source=fragment.source,
                        score=score,
                        metadata={
                            **fragment.metadata,
                            "retrieved_from": "default_knowledge",
                            "query": query,
                        },
                    )
                    relevant_fragments.append(new_fragment)

            # 按分数排序并返回前k个
            relevant_fragments.sort(key=lambda x: x.score, reverse=True)
            return relevant_fragments[:k]

        except Exception as e:
            logger.error(f"默认知识库检索失败: {e}")
            return []

    def _calculate_simple_relevance(self, content: str, query: str) -> float:
        """计算简单的相关性分数"""
        try:
            content_lower = content.lower()

            # 关键词匹配
            keywords = query.split()
            matches = sum(1 for keyword in keywords if keyword in content_lower)

            # 计算匹配率
            if keywords:
                match_rate = matches / len(keywords)
            else:
                match_rate = 0.0

            # 考虑内容长度（较长的内容可能包含更多信息）
            length_factor = min(len(content) / 500, 1.0)  # 标准化到0-1

            # 综合分数
            score = (match_rate * 0.7) + (length_factor * 0.3)

            return min(score, 1.0)  # 确保不超过1.0

        except Exception as e:
            logger.error(f"计算相关性分数失败: {e}")
            return 0.5  # 默认分数

    def post_process_fragments(
        self, fragments: List[KnowledgeFragment]
    ) -> List[KnowledgeFragment]:
        """后处理知识片段"""
        try:
            processed_fragments = []

            for fragment in fragments:
                # 1. 清理内容
                cleaned_content = self._clean_content(fragment.content)

                # 2. 重新评分
                adjusted_score = self._adjust_score(fragment.score, cleaned_content)

                # 3. 创建处理后的片段
                processed_fragment = KnowledgeFragment(
                    content=cleaned_content,
                    source=fragment.source,
                    score=adjusted_score,
                    metadata={
                        **fragment.metadata,
                        "post_processed": True,
                        "original_score": fragment.score,
                    },
                )
                processed_fragments.append(processed_fragment)

            # 4. 去重
            deduplicated = self._deduplicate_fragments(processed_fragments)

            # 5. 排序
            deduplicated.sort(key=lambda x: x.score, reverse=True)

            logger.info(
                f"后处理完成，从 {len(fragments)} 个片段处理为 {len(deduplicated)} 个"
            )
            return deduplicated

        except Exception as e:
            logger.error(f"后处理失败: {e}")
            return fragments

    def _clean_content(self, content: str) -> str:
        """清理内容"""
        try:
            # 移除多余的空白字符
            cleaned = " ".join(content.split())

            # 移除特殊字符（保留中文、英文、数字、标点）
            import re

            cleaned = re.sub(r'[^\w\s\u4e00-\u9fff.,!?;:()\[\]{}"\'-]', "", cleaned)

            # 限制长度
            if len(cleaned) > 1000:
                cleaned = cleaned[:1000] + "..."

            return cleaned

        except Exception as e:
            logger.error(f"内容清理失败: {e}")
            return content

    def _adjust_score(self, original_score: float, content: str) -> float:
        """调整分数"""
        try:
            # 基于内容质量调整分数
            quality_factors = []

            # 长度因子
            length_factor = min(len(content) / 200, 1.0)
            quality_factors.append(length_factor)

            # 信息密度因子（关键词密度）
            keywords = [
                "模型",
                "参数",
                "率定",
                "评估",
                "数据",
                "水文",
                "GR4J",
                "calibration",
                "model",
            ]
            keyword_count = sum(
                1 for keyword in keywords if keyword.lower() in content.lower()
            )
            density_factor = min(keyword_count / 5, 1.0)
            quality_factors.append(density_factor)

            # 计算平均质量因子
            avg_quality = sum(quality_factors) / len(quality_factors)

            # 调整分数
            adjusted_score = (original_score * 0.7) + (avg_quality * 0.3)

            return min(adjusted_score, 1.0)

        except Exception as e:
            logger.error(f"分数调整失败: {e}")
            return original_score

    def _deduplicate_fragments(
        self, fragments: List[KnowledgeFragment]
    ) -> List[KnowledgeFragment]:
        """去重知识片段"""
        try:
            seen_contents = set()
            deduplicated = []

            for fragment in fragments:
                # 使用内容的前100个字符作为去重标识
                content_key = fragment.content[:100].lower().strip()

                if content_key not in seen_contents:
                    seen_contents.add(content_key)
                    deduplicated.append(fragment)

            return deduplicated

        except Exception as e:
            logger.error(f"去重失败: {e}")
            return fragments

    def summarize_fragments(self, fragments: List[KnowledgeFragment]) -> str:
        """总结知识片段"""
        try:
            if not fragments:
                return "未找到相关知识片段。"

            # 提取关键信息
            summary_parts = []

            for i, fragment in enumerate(fragments[:3], 1):  # 只总结前3个
                summary_parts.append(f"{i}. {fragment.content[:200]}...")

            summary = "检索到的相关知识：\n" + "\n".join(summary_parts)

            if len(fragments) > 3:
                summary += f"\n\n... 还有 {len(fragments) - 3} 个相关片段"

            return summary

        except Exception as e:
            logger.error(f"总结失败: {e}")
            return "知识片段总结失败。"

    def get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        info = {
            "rag_system_available": self.rag_system is not None,
            "embeddings_available": self.embeddings is not None,
            "llm_available": self.llm is not None,
            "fallback_enabled": self.enable_fallback,
            "default_knowledge_count": len(self.default_knowledge),
            "faiss_index_path": self.faiss_index_path,
        }

        # 添加RAG系统信息
        if self.rag_system:
            try:
                rag_info = self.rag_system.get_system_info()
                info["rag_system_info"] = rag_info
            except:
                info["rag_system_info"] = "无法获取RAG系统信息"

        return info

    def load_documents_to_rag(
        self, document_path: str, file_extensions: Optional[List[str]] = None
    ) -> bool:
        """
        加载文档到RAG系统

        Args:
            document_path: 文档路径
            file_extensions: 文件扩展名列表

        Returns:
            bool: 是否成功
        """
        try:
            if not self.rag_system:
                logger.error("RAG系统未初始化")
                return False

            # 加载文档
            doc_count = self.rag_system.load_documents(
                source=document_path, file_extensions=file_extensions
            )

            if doc_count > 0:
                # 创建索引
                success = self.rag_system.create_index()
                if success:
                    logger.info(f"成功加载 {doc_count} 个文档并创建索引")
                    return True
                else:
                    logger.error("创建索引失败")
                    return False
            else:
                logger.warning("未加载到任何文档")
                return False

        except Exception as e:
            logger.error(f"加载文档失败: {e}")
            return False

    def test_retrieval(self, test_query: str = "GR4J模型参数") -> Dict[str, Any]:
        """测试检索功能"""
        try:
            logger.info(f"测试检索功能，查询: {test_query}")

            # 执行检索
            fragments = self.retrieve_knowledge(test_query, k=3)

            # 后处理
            processed_fragments = self.post_process_fragments(fragments)

            # 总结
            summary = self.summarize_fragments(processed_fragments)

            return {
                "test_query": test_query,
                "raw_fragments_count": len(fragments),
                "processed_fragments_count": len(processed_fragments),
                "summary": summary,
                "fragments": [frag.to_dict() for frag in processed_fragments],
                "system_info": self.get_system_info(),
            }

        except Exception as e:
            logger.error(f"测试检索失败: {e}")
            return {
                "test_query": test_query,
                "error": str(e),
                "system_info": self.get_system_info(),
            }
