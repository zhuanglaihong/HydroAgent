"""
Author: zhuanglaihong
Date: 2025-07-28
Description: 查询扩展器 - 第2步：对原始意图进行改写、扩展，以便获得更丰富的上下文
"""

import logging
from typing import List, Dict, Any, Optional
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser

from .workflow_types import IntentAnalysis

logger = logging.getLogger(__name__)


class ExpandedQuery(BaseModel):
    """扩展后的查询结构"""

    expanded_queries: List[str] = Field(default_factory=list, description="扩展后的查询列表")
    keywords: List[str] = Field(default_factory=list, description="关键词列表")
    synonyms: List[str] = Field(default_factory=list, description="同义词列表")
    related_concepts: List[str] = Field(default_factory=list, description="相关概念列表")
    search_strategies: List[str] = Field(default_factory=list, description="搜索策略列表")


class QueryExpander:
    """查询扩展器 - 负责扩展和丰富查询以提升检索效果"""

    def __init__(self, llm):
        """
        初始化查询扩展器

        Args:
            llm: 语言模型实例
        """
        self.llm = llm
        self.parser = PydanticOutputParser(pydantic_object=ExpandedQuery)
        self._setup_prompts()
        self._load_domain_knowledge()

    def _setup_prompts(self):
        """设置提示模板"""
        self.expansion_prompt = PromptTemplate(
            template="""你是一个专业的水文模型知识库检索专家，需要将用户的查询意图扩展为更丰富的搜索词，以便在知识库中检索到更全面、准确的信息。

水文模型领域知识背景：
- 水文模型：GR4J、XAJ、HYMOD、GR5J、GR6J等
- 模型参数：X1(土壤湿度容量)、X2(地下水交换)、X3(单位线时间常数)、X4(慢速径流)等
- 率定方法：SCE-UA、遗传算法、粒子群算法等
- 评估指标：NSE、R²、RMSE、KGE等
- 数据类型：CAMELS、降水、蒸发、流量、气象数据等

用户原始意图：{clarified_intent}
任务类型：{task_type}
识别实体：{entities}

请为此查询生成扩展的搜索词和策略。你必须严格按照以下JSON格式返回结果：

{{
    "expanded_queries": ["查询1", "查询2", "查询3"],  // 3-5个扩展查询表述
    "keywords": ["关键词1", "关键词2", ...],  // 5-10个关键词
    "synonyms": ["同义词1", "同义词2", ...],  // 相关同义词和别名
    "related_concepts": ["概念1", "概念2", ...],  // 相关概念和主题
    "search_strategies": ["策略1", "策略2", ...]  // 具体搜索策略
}}

示例输出：
{{
    "expanded_queries": ["GR4J模型参数配置", "GR4J四参数水文模型", "GR4J参数率定范围", "GR4J模型结构参数"],
    "keywords": ["GR4J", "参数", "X1", "X2", "X3", "X4", "土壤湿度", "地下水交换"],
    "synonyms": ["四参数模型", "GR4J水文模型", "日径流模型"],
    "related_concepts": ["模型结构", "参数物理意义", "参数敏感性", "率定优化"],
    "search_strategies": ["精确匹配模型名称", "参数名称联合搜索", "模型文档检索"]
}}

{format_instructions}
""",
            input_variables=["clarified_intent", "task_type", "entities"],
            partial_variables={
                "format_instructions": self.parser.get_format_instructions()
            },
        )

    def _load_domain_knowledge(self):
        """加载领域知识库"""
        self.model_knowledge = {
            "gr4j": {
                "full_name": "GR4J四参数日径流模型",
                "parameters": ["X1", "X2", "X3", "X4"],
                "synonyms": ["四参数模型", "GR4J水文模型", "日径流模型"],
                "related_terms": ["土壤湿度容量", "地下水交换", "单位线", "慢速径流"],
            },
            "xaj": {
                "full_name": "新安江模型",
                "parameters": [
                    "SM",
                    "EX",
                    "UH",
                    "LM",
                    "DM",
                    "IM",
                    "KG",
                    "KI",
                    "CS",
                    "CI",
                    "CG",
                ],
                "synonyms": ["新安江流域水文模型", "Xinanjiang模型"],
                "related_terms": ["产流", "汇流", "蒸散发", "流域水文"],
            },
            "hymod": {
                "full_name": "HYMOD概念性水文模型",
                "parameters": ["C_max", "BEXP", "ALPHA", "RS", "RQ"],
                "synonyms": ["HYMOD模型", "概念性模型"],
                "related_terms": ["土壤水分", "径流生成", "线性水库"],
            },
        }

        self.task_knowledge = {
            "parameter_query": {
                "keywords": ["参数", "配置", "范围", "物理意义", "敏感性"],
                "related_terms": ["率定", "优化", "初值", "约束条件"],
            },
            "data_preparation": {
                "keywords": ["数据", "预处理", "格式", "时间序列", "质量控制"],
                "related_terms": ["降水", "蒸发", "流量", "气象数据", "CAMELS"],
            },
            "model_calibration": {
                "keywords": ["率定", "优化", "训练", "参数估计", "目标函数"],
                "related_terms": ["SCE-UA", "遗传算法", "NSE", "收敛", "交叉验证"],
            },
            "model_evaluation": {
                "keywords": ["评估", "验证", "性能", "指标", "精度"],
                "related_terms": ["NSE", "R²", "RMSE", "KGE", "水量平衡", "峰值"],
            },
        }

    def expand_query(self, intent_analysis: IntentAnalysis) -> str:
        """
        扩展查询意图

        Args:
            intent_analysis: 意图分析结果

        Returns:
            str: 扩展后的查询字符串
        """
        try:
            logger.info(f"开始扩展查询: {intent_analysis.clarified_intent}")

            # 使用LLM进行智能扩展
            llm_expanded = self._llm_expand_query(intent_analysis)

            # 基于领域知识进行规则扩展
            rule_expanded = self._rule_based_expand(intent_analysis)

            # 合并扩展结果
            final_expanded = self._merge_expansions(
                llm_expanded, rule_expanded, intent_analysis
            )

            logger.info(f"查询扩展完成，生成{len(final_expanded.split())}个词汇")
            return final_expanded

        except Exception as e:
            logger.error(f"查询扩展失败: {e}")
            # 返回基础扩展
            return self._create_fallback_expansion(intent_analysis)

    def _llm_expand_query(self, intent_analysis: IntentAnalysis) -> ExpandedQuery:
        """使用LLM进行智能查询扩展"""
        try:
            chain = self.expansion_prompt | self.llm | self.parser
            
            # 记录输入参数
            logger.debug("LLM查询扩展输入参数: %s", {
                "clarified_intent": intent_analysis.clarified_intent,
                "task_type": intent_analysis.task_type,
                "entities": str(intent_analysis.entities),
            })
            
            # 获取LLM原始响应
            llm_response = chain.invoke(
                {
                    "clarified_intent": intent_analysis.clarified_intent,
                    "task_type": intent_analysis.task_type,
                    "entities": str(intent_analysis.entities),
                }
            )
            logger.debug("LLM原始响应: %s", llm_response)
            
            # 解析响应
            try:
                result = self.parser.parse(llm_response)
                logger.debug("解析后的结果: %s", result)
                return result
            except Exception as parse_error:
                logger.error("LLM响应解析失败: %s\n原始响应: %s", parse_error, llm_response)
                return self._create_basic_expansion(intent_analysis)
                
        except Exception as e:
            logger.error("LLM查询扩展失败: %s", e, exc_info=True)
            return self._create_basic_expansion(intent_analysis)

    def _rule_based_expand(
        self, intent_analysis: IntentAnalysis
    ) -> Dict[str, List[str]]:
        """基于规则的查询扩展"""
        expansion = {
            "keywords": [],
            "synonyms": [],
            "related_concepts": [],
            "model_specific": [],
        }

        # 提取模型相关扩展
        model_name = intent_analysis.entities.get("model_name", "").lower()
        if model_name in self.model_knowledge:
            model_info = self.model_knowledge[model_name]
            expansion["keywords"].extend(model_info["parameters"])
            expansion["synonyms"].extend(model_info["synonyms"])
            expansion["related_concepts"].extend(model_info["related_terms"])
            expansion["model_specific"] = [model_info["full_name"]]

        # 提取任务相关扩展
        if intent_analysis.task_type in self.task_knowledge:
            task_info = self.task_knowledge[intent_analysis.task_type]
            expansion["keywords"].extend(task_info["keywords"])
            expansion["related_concepts"].extend(task_info["related_terms"])

        # 通用水文术语扩展
        expansion["related_concepts"].extend(
            ["水文建模", "流域建模", "径流模拟", "水文预报"]
        )

        return expansion

    def _merge_expansions(
        self,
        llm_result: ExpandedQuery,
        rule_result: Dict[str, List[str]],
        intent_analysis: IntentAnalysis,
    ) -> str:
        """合并不同方式的扩展结果"""
        all_terms = []

        # 添加原始意图
        all_terms.append(intent_analysis.clarified_intent)

        # 添加LLM扩展结果
        if llm_result.expanded_queries:
            all_terms.extend(llm_result.expanded_queries)

        if llm_result.keywords:
            all_terms.extend(llm_result.keywords)

        if llm_result.synonyms:
            all_terms.extend(llm_result.synonyms)

        if llm_result.related_concepts:
            all_terms.extend(llm_result.related_concepts)

        # 添加规则扩展结果
        for category, terms in rule_result.items():
            all_terms.extend(terms)

        # 去重并按重要性排序
        unique_terms = list(dict.fromkeys(all_terms))  # 保持顺序的去重

        # 构建最终查询字符串
        final_query = self._build_final_query(unique_terms, intent_analysis)

        return final_query

    def _build_final_query(
        self, terms: List[str], intent_analysis: IntentAnalysis
    ) -> str:
        """构建最终的扩展查询字符串"""
        # 按重要性分组
        core_terms = []  # 核心术语
        related_terms = []  # 相关术语
        context_terms = []  # 上下文术语

        original_words = set(intent_analysis.clarified_intent.lower().split())

        for term in terms:
            term_words = set(term.lower().split())

            # 如果与原始查询重叠度高，认为是核心术语
            overlap = len(original_words.intersection(term_words)) / max(
                len(term_words), 1
            )

            if overlap > 0.5 or any(
                word in term.lower() for word in ["gr4j", "xaj", "hymod"]
            ):
                core_terms.append(term)
            elif overlap > 0.2:
                related_terms.append(term)
            else:
                context_terms.append(term)

        # 构建分层查询
        query_parts = []

        # 核心查询（权重最高）
        if core_terms:
            query_parts.append(" ".join(core_terms[:3]))  # 取前3个核心术语

        # 相关查询（中等权重）
        if related_terms:
            query_parts.append(" ".join(related_terms[:5]))  # 取前5个相关术语

        # 上下文查询（较低权重）
        if context_terms:
            query_parts.append(" ".join(context_terms[:3]))  # 取前3个上下文术语

        return " | ".join(query_parts)  # 使用分隔符区分不同权重的查询

    def _create_basic_expansion(self, intent_analysis: IntentAnalysis) -> ExpandedQuery:
        """创建基础的查询扩展"""
        model_name = intent_analysis.entities.get("model_name", "").lower()

        basic_keywords = ["水文模型", "参数", "率定", "评估"]
        basic_synonyms = []
        basic_concepts = ["水文建模", "流域建模"]
        basic_queries = [intent_analysis.clarified_intent]

        if model_name and model_name in self.model_knowledge:
            model_info = self.model_knowledge[model_name]
            basic_keywords.extend(model_info["parameters"][:3])
            basic_synonyms.extend(model_info["synonyms"][:2])
            basic_concepts.extend(model_info["related_terms"][:3])
            basic_queries.append(model_info["full_name"])

        return ExpandedQuery(
            expanded_queries=basic_queries,
            keywords=basic_keywords,
            synonyms=basic_synonyms,
            related_concepts=basic_concepts,
            search_strategies=["关键词匹配", "语义相似性搜索"],
        )

    def _create_fallback_expansion(self, intent_analysis: IntentAnalysis) -> str:
        """创建回退的查询扩展"""
        base_terms = [
            intent_analysis.clarified_intent,
            intent_analysis.task_type.replace("_", " "),
        ]

        # 添加实体信息
        for key, value in intent_analysis.entities.items():
            if isinstance(value, str):
                base_terms.append(value)

        # 添加通用水文术语
        base_terms.extend(["水文模型", "建模", "参数"])

        return " ".join(base_terms)

    def get_expansion_suggestions(self, query: str) -> List[str]:
        """为查询提供扩展建议"""
        suggestions = []

        query_lower = query.lower()

        # 模型相关建议
        for model_name, model_info in self.model_knowledge.items():
            if model_name in query_lower:
                suggestions.extend(
                    [
                        f"{model_info['full_name']}",
                        f"{model_name.upper()}模型参数",
                        f"{model_name.upper()}率定方法",
                    ]
                )

        # 任务相关建议
        if "参数" in query_lower:
            suggestions.extend(["参数敏感性分析", "参数率定范围", "参数物理意义"])

        if "数据" in query_lower:
            suggestions.extend(["数据预处理", "数据质量控制", "时间序列数据"])

        if "率定" in query_lower:
            suggestions.extend(["模型率定算法", "率定目标函数", "率定结果评估"])

        return suggestions[:10]  # 返回前10个建议
