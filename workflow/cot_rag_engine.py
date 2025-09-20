"""
增强推理引擎（CoT + RAG）

功能：这是系统的核心，利用RAG检索相关知识，并引导LLM进行逐步推理（CoT），生成初步计划

处理步骤：
1. RAG检索：根据意图对象，构造查询（Query），从已构建好的向量数据库中检索相关背景知识、工具文档、工作流案例
2. CoT Prompt构建：构建一个强大的Prompt模板
3. 调用LLM：将组装好的Prompt发送给LLM，并获得其生成的原始计划

Author: Assistant
Date: 2025-01-20
"""

import logging
import json
import re
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from .instruction_parser import IntentResult, IntentType, EntityType

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeFragment:
    """知识片段"""

    content: str  # 内容
    source: str  # 来源
    score: float  # 相似度得分
    fragment_type: str = (
        "general"  # 片段类型：general, tool_doc, workflow_case, background
    )
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "content": self.content,
            "source": self.source,
            "score": self.score,
            "fragment_type": self.fragment_type,
            "metadata": self.metadata,
        }


@dataclass
class RAGRetrievalResult:
    """RAG检索结果"""

    query: str  # 查询文本
    fragments: List[KnowledgeFragment]  # 知识片段
    total_fragments: int  # 总片段数
    retrieval_time: float  # 检索用时
    retrieval_strategy: str = "hybrid"  # 检索策略
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据


@dataclass
class CoTReasoningStep:
    """CoT推理步骤"""

    step_number: int  # 步骤序号
    question: str  # 思考问题
    reasoning: str  # 推理过程
    conclusion: str  # 结论
    confidence: float = 0.0  # 置信度


@dataclass
class CoTReasoningResult:
    """CoT推理结果"""

    reasoning_steps: List[CoTReasoningStep]  # 推理步骤
    final_plan: str  # 最终计划（原始JSON）
    reasoning_time: float  # 推理用时
    llm_model: str = "unknown"  # 使用的LLM模型
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据


class CoTRAGEngine:
    """增强推理引擎（CoT + RAG）"""

    def __init__(
        self,
        rag_system=None,
        ollama_client=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        初始化推理引擎

        Args:
            rag_system: RAG系统实例
            ollama_client: Ollama客户端
            config: 配置参数
        """
        self.rag_system = rag_system
        self.ollama_client = ollama_client
        self.config = config or {}

        # 默认配置
        self.default_config = {
            "rag_retrieval_k": 10,  # RAG检索数量
            "rag_score_threshold": 0.3,  # RAG相似度阈值
            "llm_model": "qwen3:8b",  # LLM模型名称
            "max_context_length": 4000,  # 最大上下文长度
            "reasoning_temperature": 0.7,  # 推理温度
            "enable_cot_validation": True,  # 启用CoT验证
        }

        # 合并配置
        self.config = {**self.default_config, **self.config}

        # 初始化提示词模板
        self._init_prompt_templates()

        logger.info("CoT + RAG推理引擎初始化完成")

    def _init_prompt_templates(self):
        """初始化提示词模板"""

        # 系统角色定义
        self.system_role = """你是一个高级工作流规划专家，专门负责将用户的自然语言指令转化为结构化的、可执行的工作流计划。

你的专业领域包括：
- 水文建模和分析
- 数据处理和可视化
- 模型率定和模拟
- 自动化工作流设计

🎯 核心任务：
生成的工作流必须能够在HydroMCP系统中直接执行，这意味着：
1. 只能使用系统提供的4个工具：get_model_params, prepare_data, calibrate_model, evaluate_model
2. 每个工具的参数必须严格遵循工具定义，不能添加不存在的参数
3. 必须包含所有必需参数，可选参数可以省略或使用默认值

你需要运用逐步推理（Chain of Thought）的方法，系统性地分析用户需求，并生成详细的工作流计划。"""

        # CoT推理指引模板
        self.cot_reasoning_guide = """请按照以下步骤逐步思考：

1. **最终目标分析**
   - 用户的真实需求是什么？
   - 期望的最终输出是什么？
   - 有哪些隐含的要求？

2. **任务分解**
   - 需要哪些主要的子任务？
   - 每个子任务的具体内容是什么？
   - 子任务之间的逻辑关系如何？

3. **依赖关系分析**
   - 哪些任务必须串行执行？
   - 哪些任务可以并行执行？
   - 每个任务的输入和输出是什么？

4. **循环和条件判断**
   - 是否需要循环执行某些步骤（如校准、重试）？
   - 需要什么条件判断和分支逻辑？
   - 如何处理错误和异常情况？

5. **任务类型标记**
   - 每个任务是简单操作（simple_action）还是复杂推理（complex_reasoning）？
   - simple_action: 直接的数据操作、文件读写、简单计算
   - complex_reasoning: 模型率定、参数优化、复杂分析、决策制定

6. **工具和资源需求**
   - 每个任务需要使用哪些工具？
   - 需要什么数据和资源？
   - 有什么约束条件？"""

        # 输出格式要求模板
        self.output_format_template = """
请严格按照以下JSON格式输出工作流计划：

{
  "workflow_id": "唯一的工作流ID",
  "name": "工作流名称",
  "description": "工作流描述",
  "tasks": [
    {
      "task_id": "唯一的任务ID",
      "name": "任务名称",
      "description": "任务描述",
      "action": "具体的操作或函数名(必须来自可用工具列表)",
      "task_type": "simple_action 或 complex_reasoning",
      "parameters": {
        "参数名": "参数值"
      },
      "dependencies": ["依赖的任务ID列表"],
      "conditions": {
        "if": "执行条件（可选）",
        "retry_count": "重试次数（可选）",
        "timeout": "超时时间（可选）"
      },
      "expected_output": "期望的输出描述"
    }
  ],
  "metadata": {
    "created_time": "创建时间",
    "complexity": "工作流复杂度评估",
    "estimated_duration": "预估执行时间"
  }
}

🚨 关键约束：
1. action字段只能使用：get_model_params, prepare_data, calibrate_model, evaluate_model
2. parameters字段只能包含对应工具定义中存在的参数
3. 必需参数必须包含，可选参数可以省略
4. 参数值必须符合类型要求(string, integer, array等)
5. 枚举参数必须使用指定的可选值
6. 每个task_id必须唯一
7. dependencies中引用的task_id必须存在
8. task_type必须是 "simple_action" 或 "complex_reasoning" 之一
9. 确保JSON格式完全正确，可以被直接解析
"""

    def generate_reasoning_plan(
        self, intent_result: IntentResult
    ) -> Tuple[RAGRetrievalResult, CoTReasoningResult]:
        """
        生成推理计划

        Args:
            intent_result: 意图分析结果

        Returns:
            Tuple[RAGRetrievalResult, CoTReasoningResult]: RAG检索结果和CoT推理结果
        """
        start_time = time.time()

        try:
            # 第一步：RAG检索
            logger.info("开始RAG知识检索...")
            rag_result = self._perform_rag_retrieval(intent_result)

            # 第二步：构建CoT提示词
            logger.info("构建CoT推理提示词...")
            prompt = self._build_cot_prompt(intent_result, rag_result)

            # 第三步：调用LLM进行CoT推理
            logger.info("执行CoT推理...")
            cot_result = self._perform_cot_reasoning(prompt)

            logger.info(f"推理计划生成完成，总用时: {time.time() - start_time:.2f}秒")
            return rag_result, cot_result

        except Exception as e:
            logger.error(f"推理计划生成失败: {str(e)}")
            # 返回空结果
            return (
                RAGRetrievalResult(
                    query=intent_result.original_query,
                    fragments=[],
                    total_fragments=0,
                    retrieval_time=0.0,
                ),
                CoTReasoningResult(
                    reasoning_steps=[],
                    final_plan="{}",
                    reasoning_time=time.time() - start_time,
                ),
            )

    def _perform_rag_retrieval(self, intent_result: IntentResult) -> RAGRetrievalResult:
        """执行RAG检索"""
        start_time = time.time()

        try:
            # 构建检索查询
            retrieval_queries = self._build_retrieval_queries(intent_result)

            all_fragments = []

            for query in retrieval_queries:
                if self.rag_system:
                    # 使用RAG系统检索
                    fragments = self._retrieve_from_rag_system(query)
                else:
                    # 使用回退检索机制
                    fragments = self._retrieve_fallback_knowledge(query, intent_result)

                all_fragments.extend(fragments)

            # 去重和排序
            unique_fragments = self._deduplicate_and_rank_fragments(all_fragments)

            # 限制片段数量
            max_fragments = self.config.get("rag_retrieval_k", 10)
            top_fragments = unique_fragments[:max_fragments]

            retrieval_time = time.time() - start_time

            logger.info(f"RAG检索完成，检索到 {len(top_fragments)} 个知识片段")

            return RAGRetrievalResult(
                query=" | ".join(retrieval_queries),
                fragments=top_fragments,
                total_fragments=len(unique_fragments),
                retrieval_time=retrieval_time,
                retrieval_strategy="hybrid",
            )

        except Exception as e:
            logger.error(f"RAG检索失败: {str(e)}")
            return RAGRetrievalResult(
                query=intent_result.original_query,
                fragments=[],
                total_fragments=0,
                retrieval_time=time.time() - start_time,
            )

    def _build_retrieval_queries(self, intent_result: IntentResult) -> List[str]:
        """构建检索查询"""
        queries = []

        # 基础查询
        queries.append(intent_result.original_query)

        # 基于意图类型的查询
        intent_type = intent_result.intent_type
        if intent_type == IntentType.MODEL_CALIBRATION:
            queries.append("模型率定 参数优化 校准方法")
        elif intent_type == IntentType.MODEL_SIMULATION:
            queries.append("模型仿真 模拟运行 预测")
        elif intent_type == IntentType.DATA_ANALYSIS:
            queries.append("数据分析 统计 评估指标")
        elif intent_type == IntentType.VISUALIZATION:
            queries.append("数据可视化 绘图 图表")

        # 基于实体的查询
        entities = intent_result.entities
        if "model_name" in entities:
            model_names = [e.value for e in entities["model_name"]]
            for model_name in model_names:
                queries.append(f"{model_name} 模型 使用方法")

        if "data_type" in entities:
            data_types = [e.value for e in entities["data_type"]]
            for data_type in data_types:
                queries.append(f"{data_type} 数据处理")

        # 工具文档查询
        for tool in intent_result.suggested_tools:
            queries.append(f"{tool} 工具 使用说明")

        return queries

    def _retrieve_from_rag_system(self, query: str) -> List[KnowledgeFragment]:
        """从RAG系统检索知识"""
        try:
            # 调用RAG系统的检索方法
            if hasattr(self.rag_system, "query"):
                results = self.rag_system.query(
                    query_text=query,
                    top_k=self.config.get("rag_retrieval_k", 5),
                    score_threshold=self.config.get("rag_score_threshold", 0.3),
                )
            elif hasattr(self.rag_system, "retrieve"):
                results = self.rag_system.retrieve(
                    query, top_k=self.config.get("rag_retrieval_k", 5)
                )
            else:
                logger.warning("RAG系统没有标准的检索方法")
                return []

            fragments = []
            # RAGSystem.query返回的是字典格式，包含results键
            if isinstance(results, dict) and "results" in results:
                query_results = results.get("results", [])
                for result in query_results:
                    if isinstance(result, dict):
                        fragment = KnowledgeFragment(
                            content=result.get("content", str(result)),
                            source=result.get("metadata", {}).get(
                                "source_file", "rag_system"
                            ),
                            score=result.get("score", 0.0),
                            fragment_type="rag_retrieved",
                            metadata=result.get("metadata", {}),
                        )
                        fragments.append(fragment)
            elif isinstance(results, list):
                # 如果是列表格式（向后兼容）
                for result in results:
                    if isinstance(result, dict):
                        fragment = KnowledgeFragment(
                            content=result.get("content", str(result)),
                            source=result.get("source", "rag_system"),
                            score=result.get("score", 0.0),
                            fragment_type="rag_retrieved",
                            metadata=result.get("metadata", {}),
                        )
                    else:
                        # 简单字符串结果
                        fragment = KnowledgeFragment(
                            content=str(result),
                            source="rag_system",
                            score=0.5,
                            fragment_type="rag_retrieved",
                        )
                    fragments.append(fragment)

            return fragments

        except Exception as e:
            logger.error(f"RAG系统检索失败: {str(e)}")
            return []

    def _retrieve_fallback_knowledge(
        self, query: str, intent_result: IntentResult
    ) -> List[KnowledgeFragment]:
        """回退知识检索"""
        # 提供基础的知识片段作为回退
        fallback_knowledge = {
            "model_calibration": [
                "模型率定是确定模型参数的过程，通常使用历史观测数据进行优化",
                "常用的率定算法包括遗传算法（GA）、SCE-UA、粒子群优化等",
                "GR4J模型有4个参数：X1(产流能力)、X2(地下水交换)、X3(汇流时间)、X4(单位线时间常数)",
            ],
            "model_simulation": [
                "模型仿真是使用已率定的模型参数对新时期进行预测",
                "仿真前需要确保输入数据的质量和完整性",
                "仿真结果需要进行评估，常用指标包括NSE、RMSE、MAE等",
            ],
            "data_analysis": [
                "水文数据分析包括数据质量检查、统计分析、趋势分析等",
                "常用的评估指标有纳什效率系数(NSE)、相关系数(R)、均方根误差(RMSE)",
                "时间序列分析可以识别数据的周期性、趋势性和异常值",
            ],
        }

        fragments = []
        intent_key = intent_result.intent_type.value

        if intent_key in fallback_knowledge:
            for i, content in enumerate(fallback_knowledge[intent_key]):
                fragment = KnowledgeFragment(
                    content=content,
                    source="fallback_knowledge",
                    score=0.6,
                    fragment_type="background",
                    metadata={"index": i},
                )
                fragments.append(fragment)

        return fragments

    def _deduplicate_and_rank_fragments(
        self, fragments: List[KnowledgeFragment]
    ) -> List[KnowledgeFragment]:
        """去重和排序知识片段"""
        # 简单的去重：基于内容的前100个字符
        seen_contents = set()
        unique_fragments = []

        for fragment in fragments:
            content_key = fragment.content[:100]
            if content_key not in seen_contents:
                seen_contents.add(content_key)
                unique_fragments.append(fragment)

        # 按相似度得分排序
        unique_fragments.sort(key=lambda x: x.score, reverse=True)

        return unique_fragments

    def _build_cot_prompt(
        self, intent_result: IntentResult, rag_result: RAGRetrievalResult
    ) -> str:
        """构建CoT推理提示词"""
        # 构建知识上下文
        knowledge_context = self._build_knowledge_context(rag_result.fragments)

        # 构建用户指令和解析结果
        user_context = f"""
原始用户指令: {intent_result.original_query}

指令解析结果:
- 意图类型: {intent_result.intent_type.value}
- 明确化意图: {intent_result.clarified_intent}
- 识别的实体: {json.dumps({k: [e.to_dict() for e in v] for k, v in intent_result.entities.items()}, ensure_ascii=False, indent=2)}
- 提取的参数: {json.dumps(intent_result.parameters, ensure_ascii=False, indent=2)}
- 约束条件: {json.dumps(intent_result.constraints, ensure_ascii=False, indent=2)}
- 建议工具: {intent_result.suggested_tools}
"""

        # 构建可用工具和参数约束
        tools_constraints = self._build_tools_constraints()

        # 组装完整提示词
        prompt = f"""{self.system_role}

{user_context}

相关背景知识:
{knowledge_context}

可用工具及参数约束:
{tools_constraints}

{self.cot_reasoning_guide}

{self.output_format_template}

现在，请基于上述信息，运用逐步推理的方法，为用户生成一个详细的工作流计划。

❗️重要提醒：
1. 工作流中的action字段必须是可用工具列表中的工具名称
2. 每个任务的parameters必须严格遵循对应工具的参数定义
3. 不要添加工具定义中不存在的参数
4. 必需参数必须包含，可选参数可以省略或使用默认值

请先进行逐步思考，然后输出最终的JSON格式工作流计划。
"""

        return prompt

    def _build_knowledge_context(self, fragments: List[KnowledgeFragment]) -> str:
        """构建知识上下文"""
        if not fragments:
            return "暂无相关背景知识。"

        context_parts = []
        for i, fragment in enumerate(fragments[:8], 1):  # 限制最多8个片段
            context_parts.append(f"{i}. {fragment.content} (来源: {fragment.source})")

        return "\n".join(context_parts)

    def _build_tools_constraints(self) -> str:
        """构建工具约束信息"""
        try:
            # 导入工具定义
            from hydromcp.tools_dict import HYDRO_TOOLS
            
            constraints_text = "## 可用工具及其参数定义\n\n"
            constraints_text += f"系统提供以下 {len(HYDRO_TOOLS)} 个工具，请严格按照参数定义使用：\n\n"
            
            for tool_name, tool_def in HYDRO_TOOLS.items():
                constraints_text += f"### {tool_name}\n"
                constraints_text += f"**描述**: {tool_def.description}\n"
                constraints_text += f"**类别**: {tool_def.category}\n\n"
                
                if tool_def.parameters:
                    constraints_text += "**参数列表**:\n"
                    for param in tool_def.parameters:
                        status = "必需" if param.required else f"可选(默认: {param.default})"
                        constraints_text += f"- `{param.name}` ({param.type}, {status}): {param.description}\n"
                        
                        if param.enum:
                            constraints_text += f"  - 可选值: {', '.join(param.enum)}\n"
                    constraints_text += "\n"
                
                if tool_def.usage_examples:
                    constraints_text += "**使用场景**:\n"
                    for example in tool_def.usage_examples:
                        constraints_text += f"- {example}\n"
                    constraints_text += "\n"
                
                constraints_text += "---\n\n"
            
            return constraints_text
            
        except ImportError as e:
            logger.warning(f"无法导入工具定义: {e}")
            return "工具约束信息不可用，请参考系统文档。\n"
        except Exception as e:
            logger.error(f"构建工具约束失败: {e}")
            return "工具约束信息构建失败。\n"

    def _perform_cot_reasoning(self, prompt: str) -> CoTReasoningResult:
        """执行CoT推理"""
        start_time = time.time()

        try:
            if not self.ollama_client:
                logger.warning("没有可用的LLM客户端，使用默认计划")
                return self._create_default_reasoning_result(start_time)

            # 调用LLM
            logger.info("正在调用LLM进行CoT推理...")
            response = self._call_llm(prompt)
            
            if not response:
                logger.warning("LLM调用失败，使用默认计划")
                return self._create_default_reasoning_result(start_time)
            
            logger.info(f"LLM响应长度: {len(response)}")
            logger.info(f"LLM响应内容: {response}") 

            # 解析推理步骤和最终计划
            reasoning_steps, final_plan = self._parse_cot_response(response)

            reasoning_time = time.time() - start_time

            return CoTReasoningResult(
                reasoning_steps=reasoning_steps,
                final_plan=final_plan,
                reasoning_time=reasoning_time,
                llm_model=self.config.get("llm_model", "unknown"),
                metadata={
                    "prompt_length": len(prompt),
                    "response_length": len(response),
                },
            )

        except Exception as e:
            logger.error(f"CoT推理失败: {str(e)}")
            return self._create_default_reasoning_result(start_time)

    def _call_llm(self, prompt: str) -> Optional[str]:
        """调用LLM"""
        try:
            model_name = self.config.get("llm_model", "qwen3:8b")

            if hasattr(self.ollama_client, "chat"):
                # 使用chat接口
                response = self.ollama_client.chat(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": self.system_role},
                        {"role": "user", "content": prompt},
                    ],
                    options={
                        "temperature": self.config.get("reasoning_temperature", 0.7),
                        "num_predict": 2000,  # 限制输出长度
                    },
                )
                return response["message"]["content"]
            elif hasattr(self.ollama_client, "generate"):
                # 使用generate接口
                response = self.ollama_client.generate(
                    model=model_name,
                    prompt=prompt,
                    options={
                        "temperature": self.config.get("reasoning_temperature", 0.7),
                        "num_predict": 2000,
                    },
                )
                return response["response"]
            else:
                logger.error("Ollama客户端接口不兼容")
                return None

        except Exception as e:
            logger.error(f"LLM调用失败: {str(e)}")
            return None

    def _parse_cot_response(self, response: str) -> Tuple[List[CoTReasoningStep], str]:
        """解析CoT响应"""
        reasoning_steps = []
        final_plan = "{}"

        try:
            # 尝试提取推理步骤
            reasoning_pattern = (
                r"(\d+)\.\s*\*\*([^*]+)\*\*([^0-9]+?)(?=\d+\.\s*\*\*|\{|$)"
            )
            matches = re.findall(reasoning_pattern, response, re.DOTALL)

            for i, (step_num, question, reasoning) in enumerate(matches):
                step = CoTReasoningStep(
                    step_number=int(step_num),
                    question=question.strip(),
                    reasoning=reasoning.strip(),
                    conclusion="",  # 可以进一步解析
                    confidence=0.8,
                )
                reasoning_steps.append(step)

            # 提取JSON计划 - 使用更强大的括号匹配逻辑
            json_start = response.find('{')
            if json_start != -1:
                # 从第一个{开始，尝试找到匹配的}
                brace_count = 0
                json_end = -1
                for i in range(json_start, len(response)):
                    if response[i] == '{':
                        brace_count += 1
                    elif response[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break
                
                if json_end != -1:
                    json_candidate = response[json_start:json_end]
                    try:
                        parsed_test = json.loads(json_candidate)
                        if isinstance(parsed_test, dict) and "tasks" in parsed_test:
                            final_plan = json_candidate
                            logger.info(f"成功提取JSON计划，包含 {len(parsed_test.get('tasks', []))} 个任务")
                        else:
                            logger.debug("提取的JSON不包含tasks字段")
                    except json.JSONDecodeError as e:
                        logger.debug(f"JSON提取失败: {str(e)}")
            
            # 如果完整JSON提取失败，回退到原来的正则表达式方法
            if final_plan == "{}":
                json_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
                json_matches = re.findall(json_pattern, response, re.DOTALL)
                logger.debug(f"回退到正则表达式，找到 {len(json_matches)} 个候选JSON")

                for json_match in json_matches:
                    try:
                        parsed_test = json.loads(json_match)
                        if isinstance(parsed_test, dict) and "tasks" in parsed_test:
                            final_plan = json_match
                            logger.info(f"正则表达式提取JSON成功，包含 {len(parsed_test.get('tasks', []))} 个任务")
                            break
                    except json.JSONDecodeError:
                        continue

            if final_plan == "{}":
                logger.warning("未能从LLM响应中提取有效的JSON计划")

        except Exception as e:
            logger.error(f"CoT响应解析失败: {str(e)}")

        return reasoning_steps, final_plan

    def _create_default_reasoning_result(self, start_time: float) -> CoTReasoningResult:
        """创建默认推理结果"""
        default_plan = {
            "workflow_id": f"default_{int(time.time())}",
            "name": "默认工作流",
            "description": "由于推理失败生成的默认工作流",
            "tasks": [
                {
                    "task_id": "default_task",
                    "name": "默认任务",
                    "description": "需要手动配置的默认任务",
                    "action": "manual_configuration",
                    "task_type": "simple_action",
                    "parameters": {},
                    "dependencies": [],
                    "conditions": {},
                    "expected_output": "手动配置结果",
                }
            ],
            "metadata": {
                "created_time": datetime.now().isoformat(),
                "complexity": "unknown",
                "estimated_duration": "unknown",
            },
        }

        return CoTReasoningResult(
            reasoning_steps=[],
            final_plan=json.dumps(default_plan, ensure_ascii=False, indent=2),
            reasoning_time=time.time() - start_time,
            llm_model="default",
            metadata={"is_fallback": True},
        )


def create_cot_rag_engine(
    rag_system=None, ollama_client=None, config=None
) -> CoTRAGEngine:
    """创建CoT+RAG推理引擎实例"""
    return CoTRAGEngine(
        rag_system=rag_system, ollama_client=ollama_client, config=config
    )
