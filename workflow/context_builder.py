"""
Author: zhuanglaihong
Date: 2025-07-28
Description: 上下文构建器 - 第4步：将用户原始输入 + 检索到的核心知识片段拼接成给LLM的Prompt
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from .workflow_types import IntentAnalysis, KnowledgeFragment

logger = logging.getLogger(__name__)


class ContextBuilder:
    """上下文构建器 - 负责构建结构化的LLM提示上下文"""

    def __init__(
        self,
        max_context_length: int = 4000,
        knowledge_weight: float = 0.7,
        user_intent_weight: float = 0.3,
    ):
        """
        初始化上下文构建器

        Args:
            max_context_length: 最大上下文长度
            knowledge_weight: 知识片段权重
            user_intent_weight: 用户意图权重
        """
        self.max_context_length = max_context_length
        self.knowledge_weight = knowledge_weight
        self.user_intent_weight = user_intent_weight

    def build_context(
        self,
        user_query: str,
        intent_analysis: IntentAnalysis,
        knowledge_fragments: List[KnowledgeFragment],
        include_examples: bool = True,
    ) -> str:
        """
        构建完整的上下文

        Args:
            user_query: 用户原始查询
            intent_analysis: 意图分析结果
            knowledge_fragments: 知识片段列表
            include_examples: 是否包含示例

        Returns:
            str: 构建好的上下文字符串
        """
        try:
            logger.info(f"开始构建上下文，知识片段数量: {len(knowledge_fragments)}")

            # 1. 构建基础上下文结构
            context_sections = {
                "system_role": self._build_system_role(),
                "available_tools": self._build_tools_description(),
                "domain_knowledge": self._build_knowledge_context(knowledge_fragments),
                "user_intent": self._build_user_intent_context(
                    user_query, intent_analysis
                ),
                "workflow_requirements": self._build_workflow_requirements(),
                "output_format": self._build_output_format_specification(),
                "examples": self._build_examples() if include_examples else "",
            }

            # 2. 组装完整上下文
            full_context = self._assemble_context(context_sections)

            # 3. 长度控制和优化
            optimized_context = self._optimize_context_length(full_context)

            logger.info(f"上下文构建完成，长度: {len(optimized_context)}")
            return optimized_context

        except Exception as e:
            logger.error(f"上下文构建失败: {e}")
            return self._build_fallback_context(user_query, intent_analysis)

    def _build_system_role(self) -> str:
        """构建系统角色描述"""
        return """你是一个专业的水文模型工作流规划专家。你的任务是根据用户需求和相关知识，生成详细的、可执行的工作流计划。

你具备以下能力：
1. 理解水文建模的完整流程
2. 根据用户意图选择合适的工具组合
3. 设计逻辑清晰、步骤明确的执行计划
4. 考虑工具间的依赖关系和执行顺序
5. 提供合理的参数配置和错误处理"""

    def _build_tools_description(self) -> str:
        """构建可用工具描述"""
        return """可用的水文建模工具：

1. get_model_params
   - 功能：获取模型参数信息
   - 输入：model_name (模型名称)
   - 输出：参数名称、取值范围、物理意义
   - 使用场景：查询模型配置信息

2. prepare_data
   - 功能：准备和预处理水文数据
   - 输入：data_dir (数据目录), target_data_scale (时间尺度)
   - 输出：处理后的数据文件路径
   - 使用场景：数据格式转换、质量控制

3. calibrate_model
   - 功能：率定水文模型参数
   - 输入：模型名称、数据路径、率定参数等
   - 输出：率定结果和最优参数
   - 使用场景：模型参数优化

4. evaluate_model
   - 功能：评估模型性能
   - 输入：结果目录、实验名称等
   - 输出：评估指标和性能分析
   - 使用场景：模型验证和性能分析"""

    def _build_knowledge_context(
        self, knowledge_fragments: List[KnowledgeFragment]
    ) -> str:
        """构建知识上下文"""
        if not knowledge_fragments:
            return "当前没有相关的领域知识片段。"

        # 按相关性排序
        sorted_fragments = sorted(
            knowledge_fragments, key=lambda x: x.score, reverse=True
        )

        # 选择最相关的知识片段
        selected_fragments = self._select_relevant_fragments(sorted_fragments)

        knowledge_context = "相关领域知识：\n\n"

        for i, fragment in enumerate(selected_fragments, 1):
            # 添加知识片段
            knowledge_context += f"{i}. {fragment.content}\n"

            # 添加来源信息（如果重要）
            if fragment.score > 0.7:
                knowledge_context += (
                    f"   来源：{fragment.source} (相关性：{fragment.score:.2f})\n"
                )

            knowledge_context += "\n"

        return knowledge_context.strip()

    def _select_relevant_fragments(
        self,
        fragments: List[KnowledgeFragment],
        max_fragments: int = 5,
        min_score: float = 0.3,
    ) -> List[KnowledgeFragment]:
        """选择最相关的知识片段"""
        selected = []
        total_length = 0
        max_length = int(self.max_context_length * 0.4)  # 知识片段占总长度的40%

        for fragment in fragments:
            # 检查相关性阈值
            if fragment.score < min_score:
                continue

            # 检查长度限制
            if total_length + len(fragment.content) > max_length:
                break

            # 检查数量限制
            if len(selected) >= max_fragments:
                break

            selected.append(fragment)
            total_length += len(fragment.content)

        return selected

    def _build_user_intent_context(
        self, user_query: str, intent_analysis: IntentAnalysis
    ) -> str:
        """构建用户意图上下文"""
        context = f"""用户需求分析：

原始查询：{user_query}

意图分析：
- 明确意图：{intent_analysis.clarified_intent}
- 任务类型：{intent_analysis.task_type}
- 置信度：{intent_analysis.confidence:.2f}
- 建议工具：{', '.join(intent_analysis.suggested_tools)}

识别实体："""

        if intent_analysis.entities:
            for key, value in intent_analysis.entities.items():
                context += f"\n- {key}: {value}"
        else:
            context += "\n- 无特定实体识别"

        return context

    def _build_workflow_requirements(self) -> str:
        """构建工作流要求"""
        return """工作流生成要求：

1. 结构化输出：必须输出严格的JSON格式，包含完整的工作流定义
2. 步骤设计：每个步骤必须包含明确的工具调用和参数
3. 依赖关系：正确设置步骤间的依赖关系，确保执行顺序
4. 参数配置：使用合理的默认参数，参考领域知识进行配置
5. 错误处理：考虑可能的错误情况和重试机制
6. LangChain兼容：确保生成的工作流可以被LangChain AgentExecutor执行

特别注意：
- 数据准备通常是第一步
- 模型率定依赖于数据准备的结果
- 模型评估依赖于率定的结果
- 参数查询可以独立执行或作为其他步骤的前置条件"""

    def _build_output_format_specification(self) -> str:
        """构建输出格式规范"""
        return """严格按照以下JSON格式输出工作流：

{
  "workflow_plan": {
    "plan_id": "生成唯一ID",
    "name": "工作流名称",
    "description": "工作流描述",
    "steps": [
      {
        "step_id": "step_1",
        "name": "步骤名称",
        "description": "步骤描述",
        "step_type": "tool_call",
        "tool_name": "工具名称",
        "parameters": {
          "参数名": "参数值"
        },
        "dependencies": [],
        "conditions": {},
        "retry_count": 0,
        "timeout": 300
      }
    ],
    "user_query": "原始用户查询",
    "expanded_query": "扩展后的查询",
    "context": "上下文摘要"
  }
}

参数配置指南：
- data_dir: 使用"data/camels_11532500"作为默认数据目录
- model_name: 根据用户需求选择，默认使用"gr4j"
- target_data_scale: 默认使用"D"（日尺度）
- result_dir: 使用"result"作为结果目录
- exp_name: 根据任务生成有意义的实验名称"""

    def _build_examples(self) -> str:
        """构建示例"""
        return """示例工作流：

示例1 - 单个工具调用（参数查询）：
{
  "workflow_plan": {
    "plan_id": "param_query_001",
    "name": "GR4J参数查询",
    "description": "获取GR4J模型的参数信息",
    "steps": [
      {
        "step_id": "step_1",
        "name": "查询GR4J参数",
        "description": "获取GR4J模型的参数名称和取值范围",
        "step_type": "tool_call",
        "tool_name": "get_model_params",
        "parameters": {
          "model_name": "gr4j"
        },
        "dependencies": [],
        "conditions": {},
        "retry_count": 0,
        "timeout": 30
      }
    ]
  }
}

示例2 - 完整率定流程：
{
  "workflow_plan": {
    "plan_id": "calibration_workflow_001",
    "name": "GR4J模型完整率定流程",
    "description": "数据准备 -> 模型率定 -> 性能评估",
    "steps": [
      {
        "step_id": "step_1",
        "name": "准备数据",
        "description": "预处理水文数据",
        "step_type": "tool_call",
        "tool_name": "prepare_data",
        "parameters": {
          "data_dir": "data/camels_11532500",
          "target_data_scale": "D"
        },
        "dependencies": [],
        "conditions": {},
        "retry_count": 1,
        "timeout": 120
      },
      {
        "step_id": "step_2", 
        "name": "率定模型",
        "description": "率定GR4J模型参数",
        "step_type": "tool_call",
        "tool_name": "calibrate_model",
        "parameters": {
          "model_name": "gr4j",
          "data_dir": "data/camels_11532500",
          "exp_name": "gr4j_auto_calibration"
        },
        "dependencies": ["step_1"],
        "conditions": {},
        "retry_count": 1,
        "timeout": 600
      },
      {
        "step_id": "step_3",
        "name": "评估模型",
        "description": "评估率定结果",
        "step_type": "tool_call", 
        "tool_name": "evaluate_model",
        "parameters": {
          "exp_name": "gr4j_auto_calibration",
          "result_dir": "result"
        },
        "dependencies": ["step_2"],
        "conditions": {},
        "retry_count": 1,
        "timeout": 180
      }
    ]
  }
}"""

    def _assemble_context(self, sections: Dict[str, str]) -> str:
        """组装完整上下文"""
        context_parts = []

        # 按重要性排序添加各部分
        if sections["system_role"]:
            context_parts.append(sections["system_role"])

        if sections["available_tools"]:
            context_parts.append(sections["available_tools"])

        if sections["domain_knowledge"]:
            context_parts.append(sections["domain_knowledge"])

        if sections["user_intent"]:
            context_parts.append(sections["user_intent"])

        if sections["workflow_requirements"]:
            context_parts.append(sections["workflow_requirements"])

        if sections["output_format"]:
            context_parts.append(sections["output_format"])

        if sections["examples"]:
            context_parts.append(sections["examples"])

        return "\n\n" + "=" * 80 + "\n\n".join(context_parts)

    def _optimize_context_length(self, context: str) -> str:
        """优化上下文长度"""
        if len(context) <= self.max_context_length:
            return context

        logger.warning(f"上下文过长({len(context)})，进行截断优化")

        # 策略：保留系统角色、工具描述、用户意图和输出格式，压缩知识片段和示例
        essential_parts = []
        optional_parts = []

        parts = context.split("\n\n" + "=" * 80 + "\n\n")

        for i, part in enumerate(parts):
            if i < 4:  # 前4部分是必要的
                essential_parts.append(part)
            else:  # 后面的可以压缩
                optional_parts.append(part)

        # 计算必要部分长度
        essential_length = sum(len(part) for part in essential_parts)
        remaining_length = self.max_context_length - essential_length

        # 压缩可选部分
        compressed_optional = ""
        for part in optional_parts:
            if len(compressed_optional) + len(part) <= remaining_length:
                compressed_optional += "\n\n" + "=" * 80 + "\n\n" + part
            else:
                # 部分截断
                available_space = remaining_length - len(compressed_optional) - 100
                if available_space > 200:  # 至少保留200字符
                    compressed_optional += (
                        "\n\n"
                        + "=" * 80
                        + "\n\n"
                        + part[:available_space]
                        + "...\n[内容已截断]"
                    )
                break

        return "\n\n" + "=" * 80 + "\n\n".join(essential_parts) + compressed_optional

    def _build_fallback_context(
        self, user_query: str, intent_analysis: IntentAnalysis
    ) -> str:
        """构建回退上下文"""
        return f"""你是一个水文模型工作流规划专家，请根据用户需求生成工作流。

用户查询：{user_query}
任务类型：{intent_analysis.task_type}
建议工具：{', '.join(intent_analysis.suggested_tools)}

请生成JSON格式的工作流计划，包含必要的步骤和参数配置。

输出格式：
{{
  "workflow_plan": {{
    "plan_id": "workflow_001",
    "name": "工作流名称", 
    "description": "工作流描述",
    "steps": [...]
  }}
}}"""

    def get_context_statistics(self, context: str) -> Dict[str, Any]:
        """获取上下文统计信息"""
        return {
            "total_length": len(context),
            "word_count": len(context.split()),
            "sections_count": len(context.split("\n\n" + "=" * 80 + "\n\n")),
            "max_length": self.max_context_length,
            "utilization": len(context) / self.max_context_length,
            "timestamp": datetime.now().isoformat(),
        }
