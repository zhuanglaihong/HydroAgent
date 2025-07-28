"""
Author: zhuanglaihong
Date: 2025-07-28
Description: 意图处理器 - 第1步：将模糊查询重构为明确指令
"""

import re
import logging
from typing import Dict, Any, List, Optional
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from .workflow_types import IntentAnalysis


logger = logging.getLogger(__name__)


class ParsedIntent(BaseModel):
    """解析后的意图结构"""

    clarified_intent: str = Field(description="明确化的意图描述")
    task_type: str = Field(
        description="任务类型：parameter_query, data_preparation, model_calibration, model_evaluation, complex_workflow"
    )
    entities: Dict[str, Any] = Field(description="识别的实体信息", default_factory=dict)
    confidence: float = Field(description="置信度 0-1", default=0.0)
    suggested_tools: List[str] = Field(
        description="建议使用的工具列表", default_factory=list
    )


class IntentProcessor:
    """意图处理器 - 负责理解和重构用户输入"""

    def __init__(self, llm):
        """
        初始化意图处理器

        Args:
            llm: 语言模型实例
        """
        self.llm = llm
        self.parser = PydanticOutputParser(pydantic_object=ParsedIntent)
        self._setup_prompts()

    def _setup_prompts(self):
        """设置提示模板"""
        self.intent_analysis_prompt = PromptTemplate(
            template="""你是一个专业的水文模型助手，负责理解用户的模糊查询并将其重构为明确的指令。

可用的水文工具：
1. get_model_params - 获取模型参数信息
2. prepare_data - 准备水文数据
3. calibrate_model - 率定水文模型  
4. evaluate_model - 评估模型性能

任务类型定义：
- parameter_query: 查询模型参数、配置信息
- data_preparation: 数据准备、处理、格式转换
- model_calibration: 模型训练、参数优化、率定
- model_evaluation: 模型评估、性能分析、结果验证
- complex_workflow: 需要多个步骤的复杂工作流

用户原始查询: {user_query}

请分析用户意图并提供以下信息：

1. 将模糊的查询重构为明确、具体的指令
2. 识别任务类型
3. 提取关键实体信息（如模型名称、数据路径、时间范围等）
4. 评估分析的置信度
5. 建议使用的工具

示例：
用户查询: "我想了解GR4J"
明确意图: "获取GR4J模型的参数信息，包括参数名称、取值范围和物理意义"
任务类型: parameter_query
实体: {{"model_name": "gr4j"}}
建议工具: ["get_model_params"]

用户查询: "帮我做个模型率定"
明确意图: "使用默认参数对GR4J模型进行率定，包括数据准备、模型训练和结果评估"
任务类型: complex_workflow
实体: {{"model_name": "gr4j", "workflow_type": "calibration"}}
建议工具: ["prepare_data", "calibrate_model", "evaluate_model"]

{format_instructions}
""",
            input_variables=["user_query"],
            partial_variables={
                "format_instructions": self.parser.get_format_instructions()
            },
        )

    def process_intent(self, user_query: str) -> IntentAnalysis:
        """
        处理用户意图

        Args:
            user_query: 用户原始查询

        Returns:
            IntentAnalysis: 意图分析结果
        """
        try:
            logger.info(f"开始处理用户意图: {user_query}")

            # 预处理查询
            cleaned_query = self._preprocess_query(user_query)

            # 使用LLM分析意图
            chain = self.intent_analysis_prompt | self.llm | self.parser
            parsed_result = chain.invoke({"user_query": cleaned_query})

            # 后处理和验证
            validated_result = self._post_process_intent(parsed_result, cleaned_query)

            # 构建返回结果
            intent_analysis = IntentAnalysis(
                original_query=user_query,
                clarified_intent=validated_result.clarified_intent,
                task_type=validated_result.task_type,
                entities=validated_result.entities,
                confidence=validated_result.confidence,
                suggested_tools=validated_result.suggested_tools,
            )

            logger.info(
                f"意图分析完成: {intent_analysis.task_type}, 置信度: {intent_analysis.confidence}"
            )
            return intent_analysis

        except Exception as e:
            logger.error(f"意图处理失败: {e}")
            # 返回基础的意图分析
            return self._create_fallback_intent(user_query)

    def _preprocess_query(self, query: str) -> str:
        """预处理查询文本"""
        # 移除多余空格
        query = re.sub(r"\s+", " ", query.strip())

        # 统一模型名称格式
        model_mappings = {
            "gr4j": "GR4J",
            "gr5j": "GR5J",
            "gr6j": "GR6J",
            "xaj": "XAJ",
            "hymod": "HYMOD",
        }

        for old_name, new_name in model_mappings.items():
            query = re.sub(f"\\b{old_name}\\b", new_name, query, flags=re.IGNORECASE)

        return query

    def _post_process_intent(
        self, parsed_result: ParsedIntent, original_query: str
    ) -> ParsedIntent:
        """后处理和验证意图分析结果"""

        # 验证任务类型
        valid_task_types = [
            "parameter_query",
            "data_preparation",
            "model_calibration",
            "model_evaluation",
            "complex_workflow",
        ]
        if parsed_result.task_type not in valid_task_types:
            parsed_result.task_type = "complex_workflow"

        # 验证建议工具
        valid_tools = [
            "get_model_params",
            "prepare_data",
            "calibrate_model",
            "evaluate_model",
        ]
        parsed_result.suggested_tools = [
            tool for tool in parsed_result.suggested_tools if tool in valid_tools
        ]

        # 如果没有建议工具，根据任务类型推断
        if not parsed_result.suggested_tools:
            parsed_result.suggested_tools = self._infer_tools_from_task_type(
                parsed_result.task_type
            )

        # 调整置信度
        if parsed_result.confidence < 0.1:
            parsed_result.confidence = 0.5  # 设置合理的默认置信度

        # 验证实体信息
        parsed_result.entities = self._validate_entities(parsed_result.entities)

        return parsed_result

    def _infer_tools_from_task_type(self, task_type: str) -> List[str]:
        """根据任务类型推断需要的工具"""
        task_tool_mapping = {
            "parameter_query": ["get_model_params"],
            "data_preparation": ["prepare_data"],
            "model_calibration": ["calibrate_model"],
            "model_evaluation": ["evaluate_model"],
            "complex_workflow": ["prepare_data", "calibrate_model", "evaluate_model"],
        }
        return task_tool_mapping.get(task_type, ["get_model_params"])

    def _validate_entities(self, entities: Dict[str, Any]) -> Dict[str, Any]:
        """验证和标准化实体信息"""
        validated = {}

        # 标准化模型名称
        if "model_name" in entities:
            model_name = str(entities["model_name"]).lower()
            valid_models = ["gr4j", "gr5j", "gr6j", "xaj", "hymod", "gr2m", "gr1a"]
            if model_name in valid_models:
                validated["model_name"] = model_name
            else:
                validated["model_name"] = "gr4j"  # 默认模型

        # 验证数据路径
        if "data_path" in entities:
            validated["data_path"] = str(entities["data_path"])

        # 验证时间范围
        if "time_range" in entities:
            validated["time_range"] = entities["time_range"]

        # 验证工作流类型
        if "workflow_type" in entities:
            workflow_type = str(entities["workflow_type"]).lower()
            valid_workflows = [
                "calibration",
                "evaluation",
                "data_processing",
                "parameter_analysis",
            ]
            if workflow_type in valid_workflows:
                validated["workflow_type"] = workflow_type

        return validated

    def _create_fallback_intent(self, user_query: str) -> IntentAnalysis:
        """创建回退的意图分析结果"""
        # 简单的关键词匹配
        query_lower = user_query.lower()

        if any(
            keyword in query_lower
            for keyword in ["参数", "parameter", "配置", "config"]
        ):
            task_type = "parameter_query"
            suggested_tools = ["get_model_params"]
        elif any(
            keyword in query_lower for keyword in ["数据", "data", "准备", "prepare"]
        ):
            task_type = "data_preparation"
            suggested_tools = ["prepare_data"]
        elif any(
            keyword in query_lower for keyword in ["率定", "calibrate", "训练", "train"]
        ):
            task_type = "model_calibration"
            suggested_tools = ["calibrate_model"]
        elif any(
            keyword in query_lower
            for keyword in ["评估", "evaluate", "性能", "performance"]
        ):
            task_type = "model_evaluation"
            suggested_tools = ["evaluate_model"]
        else:
            task_type = "complex_workflow"
            suggested_tools = ["get_model_params"]

        return IntentAnalysis(
            original_query=user_query,
            clarified_intent=f"根据用户查询 '{user_query}' 执行{task_type}任务",
            task_type=task_type,
            entities={"model_name": "gr4j"},  # 默认模型
            confidence=0.3,  # 低置信度
            suggested_tools=suggested_tools,
        )

    def get_intent_suggestions(self, partial_query: str) -> List[str]:
        """为部分查询提供意图建议"""
        suggestions = []

        query_lower = partial_query.lower()

        if "gr4j" in query_lower or "模型" in query_lower:
            suggestions.extend(
                ["获取GR4J模型的参数信息", "率定GR4J模型", "评估GR4J模型性能"]
            )

        if "数据" in query_lower or "data" in query_lower:
            suggestions.extend(
                ["准备水文数据进行建模", "处理CAMELS数据集", "转换数据格式"]
            )

        if "率定" in query_lower or "calibrate" in query_lower:
            suggestions.extend(
                ["执行完整的模型率定流程", "优化模型参数", "自动率定并评估结果"]
            )

        return suggestions[:5]  # 返回前5个建议
