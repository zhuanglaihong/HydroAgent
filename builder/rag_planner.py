"""
Author: zhuanglaihong
Date: 2024-09-24 16:47:00
LastEditTime: 2024-09-24 16:47:00
LastEditors: zhuanglaihong
Description: RAG-based planner with Chain-of-Thought reasoning
FilePath: \HydroAgent\builder\rag_planner.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import logging
import json
import re
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from .llm_client import LLMClient, LLMResponse, get_llm_client
from config import COT_MAX_ITERATIONS, COT_TEMPERATURE, COT_KNOWLEDGE_CHUNKS

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeFragment:
    """知识片段"""

    content: str
    source: str
    score: float
    fragment_type: str = "general"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "source": self.source,
            "score": self.score,
            "fragment_type": self.fragment_type,
            "metadata": self.metadata,
        }


@dataclass
class RAGContext:
    """RAG上下文"""

    query: str
    fragments: List[KnowledgeFragment]
    total_fragments: int
    retrieval_time: float
    context_summary: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CoTStep:
    """思维链步骤"""

    step_number: int
    question: str
    reasoning: str
    conclusion: str
    confidence: float = 0.8


@dataclass
class PlanningResult:
    """规划结果"""

    workflow: Dict[str, Any]
    rag_context: RAGContext
    cot_steps: List[CoTStep]
    planning_time: float
    success: bool
    error_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class RAGPlanner:
    """
    基于RAG的工作流规划器，结合思维链推理
    """

    def __init__(self, rag_system=None, llm_client: LLMClient = None):
        """
        初始化RAG规划器

        Args:
            rag_system: RAG系统实例
            llm_client: LLM客户端实例
        """
        self.rag_system = rag_system
        self.llm_client = llm_client or get_llm_client()

        # 提示词模板
        self._init_templates()

        logger.info("RAG规划器初始化完成")

    def _init_templates(self):
        """初始化提示词模板"""

        self.system_prompt = """你是一个专业的水文工作流规划专家，负责将用户需求转化为可执行的工作流计划。

你的核心能力：
1. 理解用户的水文建模需求
2. 结合相关知识进行逐步推理
3. 生成结构化的工作流计划

可用工具（必须严格使用以下工具）：
- get_model_params: 获取模型参数信息
- prepare_data: 准备和处理数据
- calibrate_model: 模型率定
- evaluate_model: 模型评估

你必须：
1. 使用逐步思考的方法分析问题
2. 仅使用上述4个可用工具
3. 为每个任务标记类型：simple 或 complex
4. 生成标准的JSON格式工作流"""

        self.cot_template = """基于以下信息，请逐步思考并生成工作流计划：

用户需求: {query}

相关知识:
{knowledge_context}

请按以下步骤思考：

1. **需求分析**
   - 用户的具体目标是什么？
   - 涉及哪些水文模型和数据？
   - 期望的输出结果是什么？

2. **任务分解**
   - 需要哪些主要步骤？
   - 每个步骤的具体操作是什么？
   - 步骤间的依赖关系如何？

3. **工具选择**
   - 每个步骤应该使用哪个工具？
   - 工具的参数如何设置？
   - 是否需要条件判断或循环？

4. **复杂度评估**
   - 哪些是简单操作（simple）？
   - 哪些是复杂推理（complex）？
   - 如何保证执行效率？

5. **工作流设计**
   请生成以下格式的JSON工作流：

```json
{{
  "workflow_id": "唯一标识",
  "name": "工作流名称",
  "description": "工作流描述",
  "mode": "sequential/react",
  "tasks": [
    {{
      "task_id": "任务ID",
      "name": "任务名称",
      "description": "任务描述",
      "tool_name": "工具名称",
      "type": "simple/complex",
      "parameters": {{
        "参数名": "参数值"
      }},
      "dependencies": ["依赖的任务ID"],
      "conditions": {{
        "retry_count": "重试次数（可选）",
        "timeout": "超时时间（可选）"
      }},
      "expected_output": "期望输出"
    }}
  ],
  "metadata": {{
    "created_time": "{timestamp}",
    "estimated_duration": "预估时间",
    "complexity": "复杂度评级"
  }}
}}
```

请先进行逐步分析，然后输出最终的JSON工作流。"""

    def plan_workflow(
        self, query: str, context: Dict[str, Any] = None
    ) -> PlanningResult:
        """
        规划工作流

        Args:
            query: 用户查询
            context: 额外上下文信息

        Returns:
            PlanningResult: 规划结果
        """
        start_time = time.time()

        try:
            # 第一步：RAG检索相关知识
            logger.info("开始RAG知识检索")
            rag_context = self._retrieve_knowledge(query)

            # 第二步：构建CoT提示词
            logger.info("构建思维链提示词")
            prompt = self._build_cot_prompt(query, rag_context)

            # 打印提示词调试信息
            prompt_length = len(prompt)
            prompt_tokens_estimate = prompt_length // 4  # 粗略估算token数
            logger.info(
                f"提示词长度: {prompt_length} 字符, 估算 {prompt_tokens_estimate} tokens"
            )
            logger.info(f"使用的知识片段数量: {len(rag_context.fragments)}")

            # 第三步：LLM推理生成工作流
            logger.info(f"执行LLM推理 - 温度: {COT_TEMPERATURE}, 最大tokens: 4000")
            # logger.info(f"完整提示词内容:\n{'='*80}\n{prompt}\n{'='*80}")

            llm_start_time = time.time()
            response = self.llm_client.generate(
                prompt=prompt, temperature=COT_TEMPERATURE, max_tokens=4000
            )
            llm_time = time.time() - llm_start_time

            logger.info(
                f"LLM调用完成 - 耗时: {llm_time:.2f}秒, 成功: {response.success}"
            )

            if response.success:
                logger.info(f"LLM响应长度: {len(response.content)} 字符")
                logger.info(
                    f"LLM响应内容预览 (前1000字符):\n{response.content[:1000]}..."
                )
            else:
                logger.error(f"LLM调用失败详情: {response.error_message}")
                logger.error(f"使用的模型: {response.model_used}")
                raise Exception(f"LLM调用失败: {response.error_message}")

            # 第四步：解析响应
            logger.info("解析LLM响应")
            cot_steps, workflow = self._parse_llm_response(response.content)

            planning_time = time.time() - start_time

            return PlanningResult(
                workflow=workflow,
                rag_context=rag_context,
                cot_steps=cot_steps,
                planning_time=planning_time,
                success=True,
                metadata={
                    "model_used": response.model_used,
                    "response_time": response.response_time,
                    "query_length": len(query),
                    "knowledge_fragments": len(rag_context.fragments),
                },
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(f"工作流规划失败: {error_msg}")

            planning_time = time.time() - start_time

            return PlanningResult(
                workflow=self._create_fallback_workflow(query),
                rag_context=RAGContext("", [], 0, 0.0),
                cot_steps=[],
                planning_time=planning_time,
                success=False,
                error_message=error_msg,
            )

    def _retrieve_knowledge(self, query: str) -> RAGContext:
        """检索相关知识"""
        start_time = time.time()

        try:
            fragments = []

            if self.rag_system:
                # 使用RAG系统检索
                results = self.rag_system.query(
                    query_text=query, top_k=COT_KNOWLEDGE_CHUNKS
                )

                if isinstance(results, dict) and "results" in results:
                    for result in results["results"]:
                        fragment = KnowledgeFragment(
                            content=result.get("content", ""),
                            source=result.get("metadata", {}).get(
                                "source_file", "rag_system"
                            ),
                            score=result.get("score", 0.0),
                            fragment_type="rag_retrieved",
                            metadata=result.get("metadata", {}),
                        )
                        fragments.append(fragment)
            else:
                # 使用备用知识
                fragments = self._get_fallback_knowledge(query)

            retrieval_time = time.time() - start_time

            # 生成上下文摘要
            context_summary = self._generate_context_summary(fragments)

            return RAGContext(
                query=query,
                fragments=fragments,
                total_fragments=len(fragments),
                retrieval_time=retrieval_time,
                context_summary=context_summary,
            )

        except Exception as e:
            logger.error(f"知识检索失败: {str(e)}")
            return RAGContext(
                query=query,
                fragments=self._get_fallback_knowledge(query),
                total_fragments=0,
                retrieval_time=time.time() - start_time,
            )

    def _get_fallback_knowledge(self, query: str) -> List[KnowledgeFragment]:
        """获取备用知识"""
        fallback_knowledge = [
            KnowledgeFragment(
                content="水文模型率定是确定模型参数的过程，通常包括数据准备、参数优化和结果评估三个步骤",
                source="fallback_system",
                score=0.7,
                fragment_type="background",
            ),
            KnowledgeFragment(
                content="可用工具：get_model_params(获取参数), prepare_data(数据处理), calibrate_model(模型率定), evaluate_model(模型评估)",
                source="fallback_system",
                score=0.9,
                fragment_type="tool_info",
            ),
            KnowledgeFragment(
                content="工作流任务类型：simple用于直接操作，complex用于需要复杂推理的任务",
                source="fallback_system",
                score=0.8,
                fragment_type="system_info",
            ),
        ]

        return fallback_knowledge

    def _generate_context_summary(self, fragments: List[KnowledgeFragment]) -> str:
        """生成上下文摘要"""
        if not fragments:
            return "无可用知识背景"

        summary_parts = []
        for i, fragment in enumerate(fragments[:5], 1):
            summary_parts.append(f"{i}. {fragment.content[:200]}...")

        return "\n".join(summary_parts)

    def _build_cot_prompt(self, query: str, rag_context: RAGContext) -> str:
        """构建CoT提示词"""
        knowledge_context = ""
        if rag_context.fragments:
            knowledge_parts = []
            for i, fragment in enumerate(rag_context.fragments, 1):
                knowledge_parts.append(
                    f"{i}. {fragment.content} (来源: {fragment.source})"
                )
            knowledge_context = "\n".join(knowledge_parts)
        else:
            knowledge_context = "暂无相关背景知识"

        timestamp = datetime.now().isoformat()

        prompt = f"{self.system_prompt}\n\n"
        prompt += self.cot_template.format(
            query=query, knowledge_context=knowledge_context, timestamp=timestamp
        )

        return prompt

    def _parse_llm_response(
        self, response: str
    ) -> Tuple[List[CoTStep], Dict[str, Any]]:
        """解析LLM响应"""
        cot_steps = []
        workflow = {}

        try:
            # 提取思维链步骤
            cot_steps = self._extract_cot_steps(response)

            # 提取JSON工作流
            workflow = self._extract_json_workflow(response)

            if not workflow or "tasks" not in workflow:
                logger.warning("未能提取有效工作流，使用默认结构")
                workflow = self._create_default_workflow()

        except Exception as e:
            logger.error(f"响应解析失败: {str(e)}")
            workflow = self._create_default_workflow()

        return cot_steps, workflow

    def _extract_cot_steps(self, response: str) -> List[CoTStep]:
        """提取思维链步骤"""
        steps = []

        # 匹配编号的步骤
        pattern = r"(\d+)\.\s*\*\*([^*]+)\*\*\s*\n(.*?)(?=\n\d+\.\s*\*\*|\n```|\n\n|$)"
        matches = re.findall(pattern, response, re.DOTALL)

        for i, (step_num, question, reasoning) in enumerate(matches):
            step = CoTStep(
                step_number=int(step_num),
                question=question.strip(),
                reasoning=reasoning.strip(),
                conclusion="",
                confidence=0.8,
            )
            steps.append(step)

        return steps

    def _extract_json_workflow(self, response: str) -> Dict[str, Any]:
        """提取JSON工作流"""
        # 寻找JSON代码块
        json_pattern = r"```json\s*([\s\S]*?)\s*```"
        json_matches = re.findall(json_pattern, response, re.MULTILINE)

        if json_matches:
            for json_text in json_matches:
                try:
                    workflow = json.loads(json_text)
                    if isinstance(workflow, dict) and "tasks" in workflow:
                        logger.info(
                            f"成功提取JSON工作流，包含 {len(workflow.get('tasks', []))} 个任务"
                        )
                        return workflow
                except json.JSONDecodeError:
                    continue

        # 备用方法：寻找JSON对象
        json_start = response.find("{")
        if json_start != -1:
            brace_count = 0
            json_end = -1
            for i in range(json_start, len(response)):
                if response[i] == "{":
                    brace_count += 1
                elif response[i] == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        json_end = i + 1
                        break

            if json_end != -1:
                json_text = response[json_start:json_end]
                try:
                    workflow = json.loads(json_text)
                    if isinstance(workflow, dict) and "tasks" in workflow:
                        logger.info("备用方法成功提取JSON工作流")
                        return workflow
                except json.JSONDecodeError:
                    pass

        logger.warning("未能从响应中提取有效的JSON工作流")
        return {}

    def _create_default_workflow(self) -> Dict[str, Any]:
        """创建默认工作流"""
        return {
            "workflow_id": f"default_{int(time.time())}",
            "name": "默认工作流",
            "description": "由于解析失败生成的默认工作流",
            "mode": "sequential",
            "tasks": [
                {
                    "task_id": "task_1",
                    "name": "获取模型参数",
                    "description": "获取模型参数信息",
                    "tool_name": "get_model_params",
                    "type": "simple",
                    "parameters": {},
                    "dependencies": [],
                    "conditions": {},
                    "expected_output": "模型参数信息",
                }
            ],
            "metadata": {
                "created_time": datetime.now().isoformat(),
                "estimated_duration": "1分钟",
                "complexity": "低",
            },
        }

    def _create_fallback_workflow(self, query: str) -> Dict[str, Any]:
        """创建回退工作流"""
        return {
            "workflow_id": f"fallback_{int(time.time())}",
            "name": "回退工作流",
            "description": f"针对查询 '{query[:50]}...' 的回退工作流",
            "mode": "sequential",
            "tasks": [
                {
                    "task_id": "fallback_task",
                    "name": "手动处理",
                    "description": "需要手动处理的任务",
                    "tool_name": "manual_processing",
                    "type": "simple",
                    "parameters": {"query": query},
                    "dependencies": [],
                    "conditions": {},
                    "expected_output": "手动处理结果",
                }
            ],
            "metadata": {
                "created_time": datetime.now().isoformat(),
                "estimated_duration": "未知",
                "complexity": "未知",
                "is_fallback": True,
            },
        }

    def validate_workflow(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """验证工作流"""
        validation_result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "suggestions": [],
        }

        try:
            # 检查基本结构
            required_fields = ["workflow_id", "name", "tasks"]
            for field in required_fields:
                if field not in workflow:
                    validation_result["errors"].append(f"缺少必需字段: {field}")
                    validation_result["is_valid"] = False

            # 检查任务
            tasks = workflow.get("tasks", [])
            if not tasks:
                validation_result["errors"].append("工作流没有任务")
                validation_result["is_valid"] = False
            else:
                task_ids = set()
                valid_actions = {
                    "get_model_params",
                    "prepare_data",
                    "calibrate_model",
                    "evaluate_model",
                }

                for task in tasks:
                    task_id = task.get("task_id", "")
                    if not task_id:
                        validation_result["errors"].append("任务缺少task_id")
                        validation_result["is_valid"] = False
                        continue

                    if task_id in task_ids:
                        validation_result["errors"].append(f"重复的task_id: {task_id}")
                        validation_result["is_valid"] = False
                    else:
                        task_ids.add(task_id)

                    # 检查动作
                    tool_name = task.get("tool_name", "")
                    if tool_name not in valid_actions:
                        validation_result["warnings"].append(f"未知的工具: {tool_name}")

                    # 检查任务类型
                    task_type = task.get("type", "")
                    if task_type not in ["simple", "complex"]:
                        validation_result["warnings"].append(
                            f"未知的任务类型: {task_type}"
                        )

                    # 检查依赖
                    dependencies = task.get("dependencies", [])
                    for dep_id in dependencies:
                        if dep_id not in task_ids and dep_id != task_id:
                            # 这里可能是前向依赖，暂时只给警告
                            validation_result["warnings"].append(
                                f"任务 {task_id} 依赖未定义的任务: {dep_id}"
                            )

        except Exception as e:
            validation_result["errors"].append(f"验证过程异常: {str(e)}")
            validation_result["is_valid"] = False

        return validation_result


# 全局实例
_rag_planner = None


def get_rag_planner(rag_system=None, llm_client: LLMClient = None) -> RAGPlanner:
    """获取全局RAG规划器实例"""
    global _rag_planner
    if _rag_planner is None:
        _rag_planner = RAGPlanner(rag_system=rag_system, llm_client=llm_client)
    return _rag_planner
