"""
Author: zhuanglaihong
Date: 2024-09-24 17:00:00
LastEditTime: 2024-09-24 17:00:00
LastEditors: zhuanglaihong
Description: Intent parser for instruction understanding and entity extraction
FilePath: \HydroAgent\builder\intent_parser.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import logging
import re
import json
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .llm_client import LLMClient, get_llm_client

logger = logging.getLogger(__name__)


class IntentType(Enum):
    """意图类型枚举"""
    DATA_ACQUISITION = "data_acquisition"    # 数据获取
    DATA_ANALYSIS = "data_analysis"          # 数据分析
    MODEL_CALIBRATION = "model_calibration"  # 模型率定
    MODEL_SIMULATION = "model_simulation"    # 模型模拟
    MODEL_EVALUATION = "model_evaluation"    # 模型评估
    VISUALIZATION = "visualization"          # 数据可视化
    CONTENT_GENERATION = "content_generation" # 内容生成
    CONTROL_OPERATION = "control_operation"  # 控制操作
    UNKNOWN = "unknown"                      # 未知意图


class EntityType(Enum):
    """实体类型枚举"""
    TIME_PERIOD = "time_period"      # 时间段
    LOCATION = "location"            # 地点
    MODEL_NAME = "model_name"        # 模型名称
    PARAMETER = "parameter"          # 参数
    DATA_TYPE = "data_type"          # 数据类型
    OPERATION = "operation"          # 操作
    FILE_PATH = "file_path"          # 文件路径
    THRESHOLD = "threshold"          # 阈值


@dataclass
class Entity:
    """实体对象"""
    text: str                    # 原始文本
    entity_type: EntityType      # 实体类型
    value: Any                   # 标准化值
    confidence: float = 0.0      # 置信度
    start_pos: int = -1          # 开始位置
    end_pos: int = -1           # 结束位置
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "text": self.text,
            "entity_type": self.entity_type.value,
            "value": self.value,
            "confidence": self.confidence,
            "start_pos": self.start_pos,
            "end_pos": self.end_pos,
            "metadata": self.metadata
        }


@dataclass
class IntentResult:
    """意图分析结果"""
    original_query: str                      # 原始查询
    intent_type: IntentType                  # 意图类型
    entities: Dict[str, List[Entity]]        # 识别的实体
    parameters: Dict[str, Any]               # 提取的参数
    constraints: Dict[str, Any]              # 约束条件
    confidence: float = 0.0                  # 整体置信度
    suggested_tools: List[str] = field(default_factory=list)  # 建议工具
    clarified_intent: str = ""               # 明确化的意图
    processing_time: float = 0.0             # 处理时间

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "original_query": self.original_query,
            "intent_type": self.intent_type.value,
            "entities": {
                entity_type: [entity.to_dict() for entity in entity_list]
                for entity_type, entity_list in self.entities.items()
            },
            "parameters": self.parameters,
            "constraints": self.constraints,
            "confidence": self.confidence,
            "suggested_tools": self.suggested_tools,
            "clarified_intent": self.clarified_intent,
            "processing_time": self.processing_time
        }


class IntentParser:
    """指令解析器 - 用于指令理解和意图识别"""

    def __init__(self, llm_client: LLMClient = None, enable_llm_enhancement: bool = False):
        """
        初始化指令解析器

        Args:
            llm_client: LLM客户端，用于增强分析
            enable_llm_enhancement: 是否启用LLM增强功能，默认False
        """
        self.enable_llm_enhancement = enable_llm_enhancement
        self.llm_client = llm_client if enable_llm_enhancement else None

        # 初始化意图关键词映射
        self._init_intent_keywords()

        # 初始化实体识别规则
        self._init_entity_patterns()

        # 初始化工具映射 - 仅使用可用的4个工具
        self._init_tool_mapping()

        logger.info("意图解析器初始化完成")

    def _init_intent_keywords(self):
        """初始化意图关键词映射"""
        self.intent_keywords = {
            IntentType.DATA_ACQUISITION: [
                "获取", "下载", "收集", "读取", "加载", "导入", "准备",
                "数据", "文件", "数据集"
            ],
            IntentType.DATA_ANALYSIS: [
                "分析", "统计", "计算", "检查", "查看",
                "趋势", "相关性", "回归", "聚类"
            ],
            IntentType.MODEL_CALIBRATION: [
                "率定", "校准", "优化", "拟合", "参数调整",
                "模型率定", "参数优化", "校正", "训练"
            ],
            IntentType.MODEL_SIMULATION: [
                "模拟", "仿真", "预测", "运行", "执行",
                "模型运行", "计算", "求解", "模型参数"
            ],
            IntentType.MODEL_EVALUATION: [
                "评估", "验证", "测试", "性能", "精度", "指标",
                "R2", "NSE", "RMSE", "效果", "评价", "评价指标"
            ],
            IntentType.VISUALIZATION: [
                "绘制", "画图", "可视化", "图表", "曲线",
                "展示", "显示", "图"
            ],
            IntentType.CONTENT_GENERATION: [
                "生成", "创建", "编写", "制作", "产生",
                "报告", "文档", "总结"
            ],
            IntentType.CONTROL_OPERATION: [
                "控制", "设置", "配置", "调节", "启动",
                "停止", "重启", "管理"
            ]
        }

    def _init_entity_patterns(self):
        """初始化实体识别正则模式"""
        self.entity_patterns = {
            EntityType.TIME_PERIOD: [
                r'\d{4}年?\d{1,2}月?\d{1,2}日?',  # 日期
                r'\d{4}-\d{1,2}-\d{1,2}',        # ISO日期
                r'\d{1,2}月',                    # 月份
                r'\d{4}年',                      # 年份
                r'从.*到.*',                     # 时间范围
                r'最近\d+[天月年]',               # 相对时间
                r'\d{4}-\d{4}',                  # 年份范围
            ],
            EntityType.MODEL_NAME: [
                r'GR4J|gr4j',
                r'GR1Y|gr1y',
                r'GR2M|gr2m',
                r'GR5J|gr5j',
                r'GR6J|gr6j',
                r'XAJ|xaj',
                r'LSTM|lstm',
                r'CNN|cnn',
                r'Transformer|transformer',
                r'Random Forest|random forest',
            ],
            EntityType.PARAMETER: [
                r'参数\w*',
                r'\w*参数',
                r'X[1-6]',                       # GR系列参数
                r'学习率',
                r'批量大小',
                r'epoch',
                r'迭代次数',
                r'优化方法',
            ],
            EntityType.DATA_TYPE: [
                r'降雨量?',
                r'径流量?',
                r'蒸发量?',
                r'温度',
                r'湿度',
                r'流量',
                r'水位',
                r'时间序列',
                r'历史数据',
            ],
            EntityType.FILE_PATH: [
                r'[./\w\-_]+\.(csv|txt|json|xlsx?|nc)',
                r'[A-Za-z]:[/\\][\w/\\.-]+',
            ],
            EntityType.THRESHOLD: [
                r'>\s*[\d.]+',
                r'<\s*[\d.]+',
                r'=\s*[\d.]+',
                r'阈值\s*[\d.]+',
            ],
        }

    def _init_tool_mapping(self):
        """初始化工具映射 - 仅映射到实际可用的4个工具"""
        self.tool_mapping = {
            IntentType.DATA_ACQUISITION: [
                "prepare_data",  # 数据准备工具
            ],
            IntentType.DATA_ANALYSIS: [
                "prepare_data",  # 数据分析也可能需要数据准备
                "evaluate_model",  # 评估工具可以用于数据分析
            ],
            IntentType.MODEL_CALIBRATION: [
                "calibrate_model",  # 模型率定工具
                "prepare_data",     # 率定前需要数据准备
            ],
            IntentType.MODEL_SIMULATION: [
                "get_model_params",  # 获取模型参数
                "prepare_data",      # 模拟需要数据
            ],
            IntentType.MODEL_EVALUATION: [
                "evaluate_model",   # 模型评估工具
                "calibrate_model",  # 评估通常在率定后
            ],
            IntentType.VISUALIZATION: [
                "evaluate_model",   # 评估结果可视化
                "prepare_data",     # 可视化需要数据
            ],
            IntentType.CONTENT_GENERATION: [
                "evaluate_model",   # 生成评估报告
            ],
            IntentType.CONTROL_OPERATION: [
                "get_model_params",  # 控制操作可能需要参数信息
            ]
        }

    def parse_instruction(self, instruction: str) -> IntentResult:
        """
        解析用户指令

        Args:
            instruction: 用户指令文本

        Returns:
            IntentResult: 解析结果
        """
        start_time = time.time()

        try:
            # 1. 预处理指令
            normalized_instruction = self._normalize_instruction(instruction)

            # 2. 基于规则的意图分类
            intent_type = self._classify_intent_by_rules(normalized_instruction)

            # 3. 实体识别
            entities = self._extract_entities(normalized_instruction)

            # 4. 参数提取
            parameters = self._extract_parameters(normalized_instruction, entities)

            # 5. 约束条件提取
            constraints = self._extract_constraints(normalized_instruction, entities)

            # 6. 建议工具
            suggested_tools = self._suggest_tools(intent_type, entities)

            # 7. 使用LLM进行增强分析（如果启用且可用）
            clarified_intent = instruction
            if self.enable_llm_enhancement and self.llm_client and self.llm_client.is_available():
                enhanced_result = self._enhance_with_llm(
                    instruction, intent_type, entities, parameters, constraints
                )
                if enhanced_result:
                    # 处理LLM返回的意图类型
                    llm_intent_type = enhanced_result.get("intent_type", intent_type)
                    if isinstance(llm_intent_type, str):
                        # 尝试将字符串转换为IntentType枚举
                        try:
                            for intent_enum in IntentType:
                                if (intent_enum.value == llm_intent_type or
                                    intent_enum.name.lower() == llm_intent_type.lower()):
                                    intent_type = intent_enum
                                    break
                        except:
                            pass
                    elif isinstance(llm_intent_type, IntentType):
                        intent_type = llm_intent_type

                    clarified_intent = enhanced_result.get("clarified_intent", instruction)

            # 8. 计算置信度
            confidence = self._calculate_confidence(intent_type, entities, parameters)

            # 9. 构建结果
            processing_time = time.time() - start_time

            result = IntentResult(
                original_query=instruction,
                intent_type=intent_type,
                entities=entities,
                parameters=parameters,
                constraints=constraints,
                confidence=confidence,
                suggested_tools=suggested_tools,
                clarified_intent=clarified_intent,
                processing_time=processing_time
            )

            logger.info(f"意图解析完成: {instruction[:50]}... -> {intent_type.value}")
            return result

        except Exception as e:
            logger.error(f"意图解析失败: {str(e)}")
            # 返回默认结果
            return IntentResult(
                original_query=instruction,
                intent_type=IntentType.UNKNOWN,
                entities={},
                parameters={},
                constraints={},
                confidence=0.0,
                processing_time=time.time() - start_time
            )

    def _normalize_instruction(self, instruction: str) -> str:
        """标准化指令文本"""
        # 转换为小写
        normalized = instruction.lower().strip()

        # 去除多余空白字符
        normalized = re.sub(r'\s+', ' ', normalized)

        # 标准化标点符号
        normalized = re.sub(r'[，。！？]', ',', normalized)

        return normalized

    def _classify_intent_by_rules(self, instruction: str) -> IntentType:
        """基于规则的意图分类"""
        intent_scores = {}

        for intent_type, keywords in self.intent_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword in instruction:
                    score += 1
            intent_scores[intent_type] = score

        # 找到得分最高的意图类型
        if intent_scores:
            best_intent = max(intent_scores, key=intent_scores.get)
            if intent_scores[best_intent] > 0:
                return best_intent

        return IntentType.UNKNOWN

    def _extract_entities(self, instruction: str) -> Dict[str, List[Entity]]:
        """提取实体"""
        entities = {}

        for entity_type, patterns in self.entity_patterns.items():
            entity_list = []

            for pattern in patterns:
                matches = re.finditer(pattern, instruction, re.IGNORECASE)
                for match in matches:
                    entity = Entity(
                        text=match.group(),
                        entity_type=entity_type,
                        value=self._normalize_entity_value(match.group(), entity_type),
                        confidence=0.8,  # 基于规则的实体置信度
                        start_pos=match.start(),
                        end_pos=match.end()
                    )
                    entity_list.append(entity)

            if entity_list:
                entities[entity_type.value] = entity_list

        return entities

    def _normalize_entity_value(self, text: str, entity_type: EntityType) -> Any:
        """标准化实体值"""
        if entity_type == EntityType.MODEL_NAME:
            return text.upper()
        elif entity_type == EntityType.TIME_PERIOD:
            return text
        elif entity_type == EntityType.PARAMETER:
            return text.lower()
        else:
            return text

    def _extract_parameters(self, instruction: str, entities: Dict[str, List[Entity]]) -> Dict[str, Any]:
        """提取参数"""
        parameters = {}

        # 从实体中提取参数
        parameter_key = EntityType.PARAMETER.value
        if parameter_key in entities:
            parameters["model_parameters"] = [e.value for e in entities[parameter_key]]

        # 提取数值参数
        number_pattern = r'(\d+(?:\.\d+)?)'
        numbers = re.findall(number_pattern, instruction)
        if numbers:
            parameters["numeric_values"] = [float(n) for n in numbers]

        # 提取布尔参数
        if any(word in instruction for word in ["启用", "开启", "打开"]):
            parameters["enable"] = True
        elif any(word in instruction for word in ["禁用", "关闭", "停止"]):
            parameters["enable"] = False

        return parameters

    def _extract_constraints(self, instruction: str, entities: Dict[str, List[Entity]]) -> Dict[str, Any]:
        """提取约束条件"""
        constraints = {}

        # 时间约束
        time_period_key = EntityType.TIME_PERIOD.value
        if time_period_key in entities:
            constraints["time_constraints"] = [e.value for e in entities[time_period_key]]

        # 阈值约束
        threshold_key = EntityType.THRESHOLD.value
        if threshold_key in entities:
            constraints["threshold_constraints"] = [e.value for e in entities[threshold_key]]

        # 数据类型约束
        data_type_key = EntityType.DATA_TYPE.value
        if data_type_key in entities:
            constraints["data_type_constraints"] = [e.value for e in entities[data_type_key]]

        return constraints

    def _suggest_tools(self, intent_type: IntentType, entities: Dict[str, List[Entity]]) -> List[str]:
        """建议相关工具（仅限4个可用工具）"""
        suggested_tools = self.tool_mapping.get(intent_type, [])

        # 根据实体进一步细化工具建议
        model_name_key = EntityType.MODEL_NAME.value
        if model_name_key in entities:
            model_names = [e.value.lower() for e in entities[model_name_key]]
            # 所有模型都使用相同的4个工具，只是参数不同
            if any(model in model_names for model in ["gr4j", "gr1y", "gr2m", "gr5j", "gr6j", "xaj"]):
                # 确保包含核心工具
                suggested_tools.extend(["get_model_params", "calibrate_model", "evaluate_model"])

        return list(set(suggested_tools))  # 去重

    def _enhance_with_llm(self, instruction: str, intent_type: IntentType,
                         entities: Dict[str, List[Entity]], parameters: Dict[str, Any],
                         constraints: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """使用LLM增强分析结果"""
        try:
            # 构建提示词
            prompt = self._build_enhancement_prompt(
                instruction, intent_type, entities, parameters, constraints
            )

            # 调用LLM
            response = self.llm_client.generate(prompt, temperature=0.3, max_tokens=500)

            if response.success:
                # 解析LLM响应
                return self._parse_llm_response(response.content)

        except Exception as e:
            logger.warning(f"LLM增强分析失败: {str(e)}")

        return None

    def _build_enhancement_prompt(self, instruction: str, intent_type: IntentType,
                                 entities: Dict[str, List[Entity]], parameters: Dict[str, Any],
                                 constraints: Dict[str, Any]) -> str:
        """构建LLM增强分析的提示词"""
        prompt = f"""你是一个水文建模领域的专家助手，请分析以下用户指令并提供改进建议。

原始指令: {instruction}

当前分析结果:
- 意图类型: {intent_type.value}
- 实体: {json.dumps({k: [e.to_dict() for e in v] for k, v in entities.items()}, ensure_ascii=False, indent=2)}
- 参数: {json.dumps(parameters, ensure_ascii=False, indent=2)}
- 约束: {json.dumps(constraints, ensure_ascii=False, indent=2)}

可用意图类型:
- data_acquisition: 数据获取
- data_analysis: 数据分析
- model_calibration: 模型率定
- model_simulation: 模型模拟
- model_evaluation: 模型评估
- visualization: 数据可视化
- content_generation: 内容生成
- control_operation: 控制操作

请分析上述结果是否准确，并提供以下信息：
1. 意图类型是否正确？如果不正确，正确的意图类型是什么？
2. 用户的真实意图是什么？请用一句话清楚地表达。
3. 是否遗漏了重要的实体或参数？

请以JSON格式回复：
{{
    "intent_type": "正确的意图类型",
    "clarified_intent": "明确的意图描述",
    "missing_entities": ["遗漏的实体"],
    "suggestions": "改进建议"
}}"""
        return prompt

    def _parse_llm_response(self, response: str) -> Optional[Dict[str, Any]]:
        """解析LLM响应"""
        try:
            # 尝试提取JSON部分
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                return json.loads(json_str)
        except Exception as e:
            logger.warning(f"LLM响应解析失败: {str(e)}")

        return None

    def _calculate_confidence(self, intent_type: IntentType, entities: Dict[str, List[Entity]],
                            parameters: Dict[str, Any]) -> float:
        """计算整体置信度"""
        confidence = 0.0

        # 基于意图类型的置信度
        if intent_type != IntentType.UNKNOWN:
            confidence += 0.4

        # 基于实体数量的置信度
        entity_count = sum(len(entity_list) for entity_list in entities.values())
        confidence += min(entity_count * 0.1, 0.3)

        # 基于参数数量的置信度
        param_count = len(parameters)
        confidence += min(param_count * 0.05, 0.3)

        return min(confidence, 1.0)


# 全局实例
_intent_parser = None


def get_intent_parser(llm_client: LLMClient = None, enable_llm_enhancement: bool = False) -> IntentParser:
    """获取全局意图解析器实例"""
    global _intent_parser
    if _intent_parser is None:
        _intent_parser = IntentParser(llm_client=llm_client, enable_llm_enhancement=enable_llm_enhancement)
    return _intent_parser