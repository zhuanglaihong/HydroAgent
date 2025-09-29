"""
Author: zhuanglaihong
Date: 2024-09-24 15:30:00
LastEditTime: 2025-09-27 15:00:00
LastEditors: zhuanglaihong
Description: 查询处理和重排序模块，负责查询预处理、结果重排序和多样性优化
FilePath: \HydroAgent\hydrorag\query_processor.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)


class QueryProcessor:
    """查询处理器 - 处理查询和优化检索结果"""

    def __init__(self, config, embeddings_manager=None):
        """
        初始化查询处理器

        Args:
            config: 配置对象
            embeddings_manager: 嵌入模型管理器（可选）
        """
        self.config = config
        self.embeddings_manager = embeddings_manager

        # 重排序配置
        self.rerank_enabled = getattr(config, "rerank_enabled", True)
        self.diversity_weight = getattr(config, "diversity_weight", 0.3)
        self.recency_weight = getattr(config, "recency_weight", 0.1)
        self.semantic_weight = getattr(config, "semantic_weight", 0.6)

        logger.info("查询处理器初始化完成")
        logger.info(f"重排序启用: {self.rerank_enabled}")

    def preprocess_query(self, query_text: str) -> str:
        """
        查询预处理

        Args:
            query_text: 原始查询文本

        Returns:
            str: 处理后的查询文本
        """
        try:
            if not query_text:
                return ""

            # 基础清理
            processed = query_text.strip()

            # 移除多余的空白字符
            processed = re.sub(r"\s+", " ", processed)

            # 水文术语规范化（可根据需要扩展）
            term_mapping = {
                "GR4J模型": "GR4J 模型",
                "GR4J参数": "GR4J 参数",
                "XAJ模型": "XAJ 模型",
                "径流模拟": "径流 模拟",
                "参数率定": "参数 率定",
                "水文模型": "水文 模型",
            }

            for original, normalized in term_mapping.items():
                processed = processed.replace(original, normalized)

            logger.debug(f"查询预处理: '{query_text}' -> '{processed}'")

            return processed

        except Exception as e:
            logger.error(f"查询预处理失败: {e}")
            return query_text

    def expand_query(self, query_text: str) -> List[str]:
        """
        查询扩展 - 生成相关的查询变体

        Args:
            query_text: 查询文本

        Returns:
            List[str]: 扩展后的查询列表
        """
        try:
            expanded_queries = [query_text]

            # 基于水文领域知识的查询扩展
            if "GR4J" in query_text.upper():
                expanded_queries.extend(
                    [
                        query_text.replace("GR4J", "GR模型"),
                        query_text + " 日径流",
                        query_text + " 四参数",
                    ]
                )

            if "XAJ" in query_text.upper():
                expanded_queries.extend(
                    [
                        query_text.replace("XAJ", "新安江模型"),
                        query_text + " 三水源",
                        query_text + " 蒸散发",
                    ]
                )

            if "参数" in query_text:
                expanded_queries.extend(
                    [
                        query_text.replace("参数", "参数值"),
                        query_text.replace("参数", "参数范围"),
                        query_text + " 敏感性",
                    ]
                )

            if "率定" in query_text:
                expanded_queries.extend(
                    [
                        query_text.replace("率定", "校准"),
                        query_text.replace("率定", "参数估计"),
                        query_text + " 目标函数",
                    ]
                )

            # 去重并保持顺序
            unique_queries = []
            for q in expanded_queries:
                if q not in unique_queries:
                    unique_queries.append(q)

            logger.debug(f"查询扩展: {len(unique_queries)} 个查询变体")

            return unique_queries

        except Exception as e:
            logger.error(f"查询扩展失败: {e}")
            return [query_text]

    def rerank_results(
        self, query_text: str, results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        重排序检索结果

        Args:
            query_text: 原始查询文本
            results: 检索结果列表

        Returns:
            List[Dict[str, Any]]: 重排序后的结果
        """
        try:
            if not self.rerank_enabled or not results:
                return results

            logger.info(f"开始重排序 {len(results)} 个检索结果")

            # 计算各种分数
            reranked_results = []

            for result in results:
                # 原始相似度分数（从ChromaDB distance转换为similarity）
                original_distance = result.get("distance", 1.0)
                semantic_score = 1.0 - original_distance  # 转换为相似度分数

                # 计算多样性分数
                diversity_score = self._calculate_diversity_score(
                    result, reranked_results
                )

                # 计算时效性分数
                recency_score = self._calculate_recency_score(result)

                # 计算内容质量分数
                content_quality_score = self._calculate_content_quality_score(result)

                # 综合分数计算
                final_score = (
                    self.semantic_weight * semantic_score
                    + self.diversity_weight * diversity_score
                    + self.recency_weight * recency_score
                    + 0.2 * content_quality_score  # 内容质量权重
                )

                # 添加重排序信息
                enhanced_result = result.copy()
                enhanced_result.update(
                    {
                        "rerank_score": final_score,
                        "semantic_score": semantic_score,
                        "diversity_score": diversity_score,
                        "recency_score": recency_score,
                        "content_quality_score": content_quality_score,
                        "original_distance": original_distance,
                    }
                )

                reranked_results.append(enhanced_result)

            # 按综合分数排序
            reranked_results.sort(key=lambda x: x["rerank_score"], reverse=True)

            logger.info(
                f"重排序完成，分数范围: {reranked_results[0]['rerank_score']:.3f} - {reranked_results[-1]['rerank_score']:.3f}"
            )

            return reranked_results

        except Exception as e:
            logger.error(f"重排序失败: {e}")
            return results

    def _calculate_diversity_score(
        self, current_result: Dict[str, Any], existing_results: List[Dict[str, Any]]
    ) -> float:
        """计算多样性分数"""
        try:
            if not existing_results:
                return 1.0  # 第一个结果的多样性分数最高

            current_content = current_result.get("content", "")
            current_source = current_result.get("metadata", {}).get("source_file", "")

            # 检查内容相似性
            content_similarities = []
            source_diversity = 1.0

            for existing in existing_results:
                existing_content = existing.get("content", "")
                existing_source = existing.get("metadata", {}).get("source_file", "")

                # 简单的内容相似性计算（基于共同词汇）
                content_sim = self._calculate_text_similarity(
                    current_content, existing_content
                )
                content_similarities.append(content_sim)

                # 检查是否来自同一文件
                if current_source == existing_source and current_source:
                    source_diversity *= 0.8  # 来自同一文件的结果多样性降低

            # 计算平均内容相似性
            avg_content_similarity = (
                np.mean(content_similarities) if content_similarities else 0.0
            )

            # 多样性分数：与现有结果差异越大，分数越高
            diversity_score = (1.0 - avg_content_similarity) * source_diversity

            return max(0.0, min(1.0, diversity_score))

        except Exception as e:
            logger.error(f"计算多样性分数失败: {e}")
            return 0.5

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """计算两个文本的相似性（基于词汇重叠）"""
        try:
            if not text1 or not text2:
                return 0.0

            # 简单的词汇集合相似性
            words1 = set(text1.lower().split())
            words2 = set(text2.lower().split())

            if not words1 or not words2:
                return 0.0

            intersection = words1.intersection(words2)
            union = words1.union(words2)

            return len(intersection) / len(union) if union else 0.0

        except Exception as e:
            logger.error(f"计算文本相似性失败: {e}")
            return 0.0

    def _calculate_recency_score(self, result: Dict[str, Any]) -> float:
        """计算时效性分数"""
        try:
            metadata = result.get("metadata", {})
            added_time_str = metadata.get("added_time", "")

            if not added_time_str:
                return 0.5  # 没有时间信息的结果给中等分数

            # 解析添加时间
            added_time = datetime.fromisoformat(added_time_str)
            current_time = datetime.now()

            # 计算时间差（天数）
            time_diff_days = (current_time - added_time).days

            # 时效性分数：越新的内容分数越高
            if time_diff_days <= 7:
                return 1.0  # 一周内的内容
            elif time_diff_days <= 30:
                return 0.8  # 一个月内的内容
            elif time_diff_days <= 90:
                return 0.6  # 三个月内的内容
            elif time_diff_days <= 365:
                return 0.4  # 一年内的内容
            else:
                return 0.2  # 一年以上的内容

        except Exception as e:
            logger.error(f"计算时效性分数失败: {e}")
            return 0.5

    def _calculate_content_quality_score(self, result: Dict[str, Any]) -> float:
        """计算内容质量分数"""
        try:
            content = result.get("content", "")

            if not content:
                return 0.0

            quality_score = 0.0

            # 长度质量：适中长度的内容质量较高
            content_length = len(content)
            if 100 <= content_length <= 1000:
                quality_score += 0.3
            elif 50 <= content_length < 100 or 1000 < content_length <= 2000:
                quality_score += 0.2
            elif content_length > 2000:
                quality_score += 0.1

            # 信息密度：包含数字、专业术语等
            if re.search(r"\d+", content):  # 包含数字
                quality_score += 0.2

            # 水文专业术语
            hydro_terms = [
                "模型",
                "参数",
                "径流",
                "降水",
                "蒸发",
                "土壤",
                "含水量",
                "流域",
            ]
            term_count = sum(1 for term in hydro_terms if term in content)
            quality_score += min(0.3, term_count * 0.05)

            # 结构化内容：包含公式、列表等
            if re.search(r"[=:]|\d+\.|•|▪", content):  # 包含公式或列表结构
                quality_score += 0.2

            return min(1.0, quality_score)

        except Exception as e:
            logger.error(f"计算内容质量分数失败: {e}")
            return 0.5

    def filter_results(
        self,
        results: List[Dict[str, Any]],
        min_score: float = None,
        max_results: int = None,
        source_diversity: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        过滤和限制结果

        Args:
            results: 结果列表
            min_score: 最小分数阈值
            max_results: 最大结果数量
            source_diversity: 是否确保来源多样性

        Returns:
            List[Dict[str, Any]]: 过滤后的结果
        """
        try:
            filtered_results = results.copy()

            # 分数过滤
            if min_score is not None:
                score_key = (
                    "rerank_score" if "rerank_score" in filtered_results[0] else "score"
                )
                filtered_results = [
                    r for r in filtered_results if r.get(score_key, 0) >= min_score
                ]
                logger.info(f"分数过滤后剩余 {len(filtered_results)} 个结果")

            # 来源多样性过滤
            if source_diversity and filtered_results:
                diverse_results = []
                source_counts = {}
                max_per_source = max(1, len(filtered_results) // 3)  # 每个来源最多占1/3

                for result in filtered_results:
                    source = result.get("metadata", {}).get("source_file", "unknown")
                    current_count = source_counts.get(source, 0)

                    if current_count < max_per_source:
                        diverse_results.append(result)
                        source_counts[source] = current_count + 1

                filtered_results = diverse_results
                logger.info(f"多样性过滤后剩余 {len(filtered_results)} 个结果")

            # 数量限制
            if max_results is not None and len(filtered_results) > max_results:
                filtered_results = filtered_results[:max_results]
                logger.info(f"数量限制后剩余 {len(filtered_results)} 个结果")

            return filtered_results

        except Exception as e:
            logger.error(f"结果过滤失败: {e}")
            return results

    def post_process_results(
        self, results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        后处理结果 - 添加额外信息和格式化

        Args:
            results: 结果列表

        Returns:
            List[Dict[str, Any]]: 后处理的结果
        """
        try:
            processed_results = []

            for i, result in enumerate(results):
                processed_result = result.copy()

                # 添加排名信息
                processed_result["rank"] = i + 1

                # 内容摘要（如果内容太长）
                content = result.get("content", "")
                if len(content) > 500:
                    # 保留前200字符和最后100字符，中间用省略号
                    summary = content[:200] + "..." + content[-100:]
                    processed_result["content_summary"] = summary
                else:
                    processed_result["content_summary"] = content

                # 关键词提取（简单实现）
                keywords = self._extract_keywords(content)
                processed_result["keywords"] = keywords

                # 相关性标签
                relevance_tag = self._get_relevance_tag(processed_result)
                processed_result["relevance_tag"] = relevance_tag

                processed_results.append(processed_result)

            logger.info(f"后处理完成 {len(processed_results)} 个结果")

            return processed_results

        except Exception as e:
            logger.error(f"结果后处理失败: {e}")
            return results

    def _extract_keywords(self, text: str, max_keywords: int = 5) -> List[str]:
        """提取关键词"""
        try:
            if not text:
                return []

            # 水文领域关键词
            hydro_keywords = [
                "GR4J",
                "XAJ",
                "新安江",
                "模型",
                "参数",
                "径流",
                "降水",
                "蒸发",
                "土壤",
                "含水量",
                "流域",
                "率定",
                "校准",
                "敏感性",
                "目标函数",
                "纳什效率",
                "NSE",
                "相关系数",
                "均方根误差",
            ]

            text_lower = text.lower()
            found_keywords = []

            for keyword in hydro_keywords:
                if keyword.lower() in text_lower or keyword in text:
                    found_keywords.append(keyword)

            # 简单的词频统计
            words = re.findall(r"\b\w{2,}\b", text)
            word_freq = {}
            for word in words:
                if len(word) > 2 and word not in [
                    "的",
                    "和",
                    "或",
                    "但",
                    "因为",
                    "所以",
                ]:
                    word_freq[word] = word_freq.get(word, 0) + 1

            # 获取高频词
            high_freq_words = sorted(
                word_freq.items(), key=lambda x: x[1], reverse=True
            )
            for word, freq in high_freq_words:
                if word not in found_keywords and len(found_keywords) < max_keywords:
                    found_keywords.append(word)

            return found_keywords[:max_keywords]

        except Exception as e:
            logger.error(f"关键词提取失败: {e}")
            return []

    def _get_relevance_tag(self, result: Dict[str, Any]) -> str:
        """获取相关性标签"""
        try:
            score = result.get("rerank_score", result.get("score", 0))

            if score >= 0.9:
                return "高度相关"
            elif score >= 0.7:
                return "相关"
            elif score >= 0.5:
                return "部分相关"
            else:
                return "弱相关"

        except Exception as e:
            logger.error(f"获取相关性标签失败: {e}")
            return "未知"

    def get_query_suggestions(self, query_text: str) -> List[str]:
        """生成查询建议"""
        try:
            suggestions = []

            # 基于查询内容生成建议
            if "模型" in query_text:
                suggestions.extend(
                    [
                        query_text + " 参数设置",
                        query_text + " 应用案例",
                        query_text + " 优缺点分析",
                    ]
                )

            if "参数" in query_text:
                suggestions.extend(
                    [
                        query_text + " 敏感性分析",
                        query_text + " 取值范围",
                        query_text + " 率定方法",
                    ]
                )

            # 相关模型建议
            if "GR4J" in query_text.upper():
                suggestions.append(query_text.replace("GR4J", "XAJ"))
                suggestions.append(query_text.replace("GR4J", "SWAT"))

            if "XAJ" in query_text.upper():
                suggestions.append(query_text.replace("XAJ", "GR4J"))
                suggestions.append(query_text.replace("XAJ", "新安江"))

            return list(set(suggestions))  # 去重

        except Exception as e:
            logger.error(f"生成查询建议失败: {e}")
            return []
