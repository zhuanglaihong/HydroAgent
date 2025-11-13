"""
Author: zhuanglaihong
Date: 2024-09-26 16:40:00
LastEditTime: 2025-10-11 19:30:00
LastEditors: zhuanglaihong
Description: 复杂任务执行器 - 使用LLM+RAG生成解决方案
FilePath: \HydroAgent\executor\core\complex_executor.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import logging
import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field

from ..models.task import Task, TaskType
from ..models.result import TaskResult, ExecutionStatus
from .llm_client import LLMClientFactory, LLMMessage, BaseLLMClient
from .simple_executor import SimpleTaskExecutor

# 尝试导入配置
try:
    from definitions import DATASET_DIR
except ImportError:
    DATASET_DIR = "data"


class ToolCall(BaseModel):
    """工具调用定义"""

    step_id: int = Field(..., description="步骤ID")
    tool_name: str = Field(..., description="工具名称")
    parameters: Dict[str, Any] = Field(..., description="工具参数")
    condition: Optional[str] = Field(None, description="执行条件")
    description: str = Field(default="", description="步骤描述")


class SolutionPlan(BaseModel):
    """解决方案计划"""

    task_id: str = Field(..., description="任务ID")
    solution_type: str = Field(..., description="解决方案类型")
    description: str = Field(..., description="解决方案描述")
    steps: List[ToolCall] = Field(..., description="执行步骤")
    estimated_duration: Optional[float] = Field(None, description="预估执行时间")
    confidence: float = Field(default=0.8, description="解决方案置信度")


class ComplexTaskExecutor:
    """复杂任务执行器"""

    def __init__(
        self,
        simple_executor: SimpleTaskExecutor,
        llm_client: BaseLLMClient = None,
        rag_system=None,
        enable_debug: bool = False,
    ):
        """
        初始化复杂任务执行器

        Args:
            simple_executor: 简单任务执行器实例
            llm_client: LLM客户端
            rag_system: RAG知识库系统
            enable_debug: 是否启用调试模式
        """
        self.simple_executor = simple_executor
        self.llm_client = llm_client or LLMClientFactory.create_complex_task_client()
        self.rag_system = rag_system
        self.enable_debug = enable_debug
        self.logger = logging.getLogger(__name__)

        # 获取可用工具列表
        self.available_tools = self._get_available_tools()

        self.logger.info("复杂任务执行器初始化完成")

    def solve_complex_task(
        self, task: Task, context: Dict[str, Any] = None
    ) -> TaskResult:
        """
        解决复杂任务

        Args:
            task: 要解决的复杂任务
            context: 执行上下文

        Returns:
            TaskResult: 执行结果
        """
        if context is None:
            context = {}

        # 验证任务类型
        if task.type != TaskType.COMPLEX:
            return self._create_error_result(
                task.task_id, f"任务类型错误，期望 {TaskType.COMPLEX}，实际 {task.type}"
            )

        try:
            # 创建任务结果
            task_result = TaskResult(
                task_id=task.task_id,
                status=ExecutionStatus.RUNNING,
                start_time=datetime.now(),
            )

            self.logger.info(f"开始解决复杂任务: {task.task_id} - {task.name}")

            # 步骤1: 查询知识库
            knowledge_chunks = self._query_knowledge_base(task)

            # 步骤2: 使用推理模型生成解决方案
            solution_plan = self._generate_solution_plan(task, knowledge_chunks)

            if not solution_plan:
                return self._create_error_result(task.task_id, "无法生成有效的解决方案")

            # 步骤3: 执行解决方案
            execution_result = self._execute_solution_plan(solution_plan, context)

            # 更新任务结果
            task_result.status = execution_result["status"]
            task_result.outputs = execution_result["outputs"]
            task_result.error = execution_result.get("error")

            # 添加解决方案信息到元数据
            task_result.metadata.update(
                {
                    "solution_type": solution_plan.solution_type,
                    "steps_count": len(solution_plan.steps),
                    "confidence": solution_plan.confidence,
                    "knowledge_chunks_used": len(knowledge_chunks),
                }
            )

            task_result.end_time = datetime.now()
            task_result.calculate_duration()

            if task_result.status == ExecutionStatus.COMPLETED:
                self.logger.info(f"复杂任务 {task.task_id} 解决成功")
            else:
                self.logger.error(
                    f"复杂任务 {task.task_id} 解决失败: {task_result.error}"
                )

            return task_result

        except Exception as e:
            error_msg = f"复杂任务 {task.task_id} 解决异常: {str(e)}"
            self.logger.error(error_msg)
            return self._create_error_result(task.task_id, error_msg)

    def _query_knowledge_base(self, task: Task) -> List[Dict[str, Any]]:
        """从知识库检索相关知识"""
        knowledge_chunks = []

        try:
            if self.rag_system:
                # 使用HydroRAG系统检索知识
                query = task.knowledge_query or task.description
                if query:
                    self.logger.info(f"使用RAG系统检索知识: {query}")
                    try:
                        # 调用RAG系统的query方法
                        rag_response = self.rag_system.query(query, top_k=5)

                        # 检查响应状态
                        if rag_response.get("status") == "success":
                            results = rag_response.get("results", [])
                            # 转换RAG结果为标准格式
                            for result in results:
                                knowledge_chunks.append({
                                    "content": result.get("content", ""),
                                    "source": result.get("metadata", {}).get("source", "rag_system"),
                                    "relevance": result.get("score", 0.8),
                                    "metadata": result.get("metadata", {})
                                })
                            self.logger.info(f"RAG系统返回 {len(knowledge_chunks)} 个知识片段")
                        else:
                            self.logger.warning(f"RAG查询无结果: {rag_response.get('status')}")
                    except Exception as rag_error:
                        self.logger.warning(f"RAG系统调用失败: {rag_error}")

            # 如果没有RAG系统或检索失败，使用预设知识
            if not knowledge_chunks:
                self.logger.info("使用默认知识库")
                knowledge_chunks = self._get_default_knowledge(task)

            self.logger.info(f"最终检索到 {len(knowledge_chunks)} 个知识片段")
            return knowledge_chunks

        except Exception as e:
            self.logger.warning(f"知识库检索失败: {e}")
            return self._get_default_knowledge(task)

    def _generate_solution_plan(
        self, task: Task, knowledge_chunks: List[Dict[str, Any]]
    ) -> Optional[SolutionPlan]:
        """生成解决方案计划"""
        try:
            # 构建提示词
            prompt = self._build_solution_prompt(task, knowledge_chunks)

            # 调用LLM生成解决方案
            messages = [
                LLMMessage(role="system", content=self._get_system_prompt()),
                LLMMessage(role="user", content=prompt),
            ]

            # 使用推理模式生成解决方案
            response = self.llm_client.chat(
                messages, task_type="reasoning", temperature=0.3, max_tokens=2000
            )

            if not response.success:
                self.logger.error(f"LLM调用失败: {response.error}")
                return None

            # 解析响应
            solution_plan = self._parse_solution_response(
                task.task_id, response.content
            )

            if solution_plan:
                self.logger.info(
                    f"生成解决方案成功，包含 {len(solution_plan.steps)} 个步骤"
                )
            else:
                self.logger.error("解决方案解析失败")

            return solution_plan

        except Exception as e:
            self.logger.error(f"生成解决方案失败: {e}")
            return None

    def _execute_solution_plan(
        self, solution_plan: SolutionPlan, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行解决方案计划"""
        try:
            outputs = {}
            step_results = []
            current_context = context.copy()

            for step in solution_plan.steps:
                self.logger.info(f"执行步骤 {step.step_id}: {step.description}")

                # 检查执行条件
                if step.condition and not self._evaluate_condition(
                    step.condition, current_context
                ):
                    self.logger.info(f"步骤 {step.step_id} 条件不满足，跳过执行")
                    continue

                # 解析参数中的引用
                self.logger.debug(
                    f"当前步骤 {step.step_id} 上下文: {list(current_context.keys())}"
                )
                for key, value in current_context.items():
                    if isinstance(value, dict) and "output" in value:
                        self.logger.debug(
                            f"  {key}.output: {list(value['output'].keys())}"
                        )
                resolved_params = self._resolve_step_parameters(
                    step.parameters, current_context
                )

                # 判断是否需要代码生成
                if self._is_code_generation_step(step):
                    # 使用代码生成模式
                    tool_result = self._execute_code_generation_step(
                        step, resolved_params, current_context
                    )
                else:
                    # 调用简单任务执行器执行工具
                    tool_result = self.simple_executor.tool_registry.call_tool(
                        step.tool_name, resolved_params
                    )

                step_result = {
                    "step_id": step.step_id,
                    "tool_name": step.tool_name,
                    "success": tool_result.success,
                    "output": tool_result.output,
                    "error": tool_result.error,
                }

                step_results.append(step_result)

                if tool_result.success:
                    # 更新上下文，供后续步骤使用
                    current_context[f"step_{step.step_id}"] = {
                        "success": True,
                        "output": tool_result.output,
                    }
                    outputs.update(tool_result.output)
                else:
                    self.logger.error(
                        f"步骤 {step.step_id} 执行失败: {tool_result.error}"
                    )
                    return {
                        "status": ExecutionStatus.FAILED,
                        "outputs": outputs,
                        "error": f"步骤 {step.step_id} 执行失败: {tool_result.error}",
                        "step_results": step_results,
                    }

            return {
                "status": ExecutionStatus.COMPLETED,
                "outputs": outputs,
                "step_results": step_results,
            }

        except Exception as e:
            self.logger.error(f"执行解决方案失败: {e}")
            return {
                "status": ExecutionStatus.FAILED,
                "outputs": {},
                "error": f"执行解决方案失败: {str(e)}",
            }

    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """你是一个水文建模专家，擅长分析复杂的水文建模任务并决定最佳解决方案。

**重要原则**:
1. 如果任务描述中明确要求"生成代码"、"编写脚本"或"生成Python代码"，你必须使用"generate_code"工具来生成代码，而不是调用现有工具
2. 如果任务要求自定义分析、特殊计算或没有对应的现有工具，应该生成代码来实现
3. 只有在任务可以直接通过现有工具完成时，才调用现有工具

可用工具:
{tools}

**代码生成工具**:
- generate_code: 用于生成Python代码来完成自定义任务
  当任务描述包含以下关键词时，优先使用此工具：
  * "生成代码"、"编写脚本"、"生成Python代码"
  * "自定义分析"、"特殊处理"、"自适应"
  * "创建函数"、"实现算法"

输出格式要求:
- 必须是有效的JSON格式
- 包含solution_type、description、steps字段
- steps是工具调用列表，每个包含step_id、tool_name、parameters、description字段
- 参数可以使用引用格式 ${{step_X.output.field_name}} 来引用前面步骤的输出

**代码生成任务示例**:
{{
  "solution_type": "code_generation",
  "description": "生成Python代码实现自定义数据分析",
  "steps": [
    {{
      "step_id": 1,
      "tool_name": "generate_code",
      "parameters": {{"task_type": "data_analysis", "requirements": "读取和分析水文数据"}},
      "description": "生成数据分析Python代码"
    }}
  ]
}}

**工具调用任务示例**:
{{
  "solution_type": "tool_sequence",
  "description": "使用现有工具序列",
  "steps": [
    {{
      "step_id": 1,
      "tool_name": "prepare_data",
      "parameters": {{"data_dir": "data/custom"}},
      "description": "准备数据"
    }},
    {{
      "step_id": 2,
      "tool_name": "calibrate_model",
      "parameters": {{"data_dir": "${{step_1.output.data_dir}}"}},
      "description": "率定模型"
    }}
  ]
}}""".format(
            tools=self._format_available_tools()
        )

    def _build_solution_prompt(
        self, task: Task, knowledge_chunks: List[Dict[str, Any]]
    ) -> str:
        """构建解决方案提示词"""
        # 检查可用的数据目录
        available_data_dirs = self._get_available_data_directories()

        prompt = f"""
任务描述: {task.description}

可用数据目录: {', '.join(available_data_dirs)}
注意: 在调用prepare_data工具时，请使用上述实际存在的数据目录，不要使用不存在的虚假路径。

相关知识:
{self._format_knowledge_chunks(knowledge_chunks)}

请分析这个复杂任务，并生成一个使用可用工具的解决方案。
重点考虑:
1. 任务的具体需求和目标
2. 工具之间的依赖关系和数据流
3. 参数的正确设置和引用（特别是数据目录路径）
4. 步骤的逻辑顺序
5. 使用实际存在的数据目录

请生成JSON格式的解决方案:
"""
        return prompt

    def _parse_solution_response(
        self, task_id: str, response_content: str
    ) -> Optional[SolutionPlan]:
        """解析LLM响应为解决方案计划"""
        try:
            # 尝试提取JSON部分
            content = response_content.strip()

            # 查找JSON代码块
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                if end > start:
                    content = content[start:end].strip()
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                if end > start:
                    content = content[start:end].strip()

            # 解析JSON
            solution_data = json.loads(content)

            # 构建ToolCall对象
            tool_calls = []
            for step_data in solution_data.get("steps", []):
                tool_call = ToolCall(
                    step_id=step_data["step_id"],
                    tool_name=step_data["tool_name"],
                    parameters=step_data["parameters"],
                    description=step_data.get("description", ""),
                    condition=step_data.get("condition"),
                )
                tool_calls.append(tool_call)

            # 创建解决方案计划
            solution_plan = SolutionPlan(
                task_id=task_id,
                solution_type=solution_data.get("solution_type", "tool_sequence"),
                description=solution_data.get("description", ""),
                steps=tool_calls,
            )

            return solution_plan

        except Exception as e:
            self.logger.error(f"解析解决方案响应失败: {e}")
            self.logger.debug(f"响应内容: {response_content}")
            return None

    def _get_available_tools(self) -> Dict[str, Any]:
        """获取可用工具信息"""
        if hasattr(self.simple_executor, "tool_registry"):
            return self.simple_executor.tool_registry.export_tool_definitions()
        return {}

    def _format_available_tools(self) -> str:
        """格式化可用工具信息"""
        tools_info = []
        for tool_name, tool_info in self.available_tools.items():
            info = tool_info.get("info", {})
            schema = tool_info.get("schema", {})

            tools_info.append(f"- {tool_name}: {info.get('description', '')}")

            # 添加参数信息
            properties = schema.get("properties", {})
            if properties:
                params = []
                for param_name, param_info in properties.items():
                    param_desc = param_info.get("description", "")
                    params.append(f"  {param_name}: {param_desc}")
                tools_info.append("\n".join(params))

        return "\n".join(tools_info)

    def _get_default_knowledge(self, task: Task) -> List[Dict[str, Any]]:
        """获取默认知识（当RAG不可用时）"""
        return [
            {
                "content": "水文模型率定通常包括数据准备、模型配置、参数优化和结果评估等步骤",
                "source": "default_knowledge",
                "relevance": 0.8,
            },
            {
                "content": "GR4J模型需要日尺度的降雨和蒸发数据，以及径流观测数据",
                "source": "default_knowledge",
                "relevance": 0.7,
            },
        ]

    def _format_knowledge_chunks(self, knowledge_chunks: List[Dict[str, Any]]) -> str:
        """格式化知识片段"""
        if not knowledge_chunks:
            return "暂无相关知识"

        formatted = []
        for i, chunk in enumerate(knowledge_chunks[:5], 1):  # 只使用前5个
            content = chunk.get("content", "")
            source = chunk.get("source", "unknown")
            formatted.append(f"{i}. {content} (来源: {source})")

        return "\n".join(formatted)

    def _resolve_step_parameters(
        self, parameters: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """解析步骤参数中的引用"""
        resolved = {}

        for key, value in parameters.items():
            if (
                isinstance(value, str)
                and value.startswith("${")
                and value.endswith("}")
            ):
                # 解析引用
                ref_path = value[2:-1]  # 移除 ${ 和 }
                resolved_value = self._resolve_reference(ref_path, context)
                resolved[key] = resolved_value
            else:
                resolved[key] = value

        return resolved

    def _resolve_reference(self, ref_path: str, context: Dict[str, Any]) -> Any:
        """解析参数引用"""
        parts = ref_path.split(".")
        value = context
        current_path = []

        for part in parts:
            current_path.append(part)
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                # 提供更详细的错误信息
                available_keys = (
                    list(value.keys()) if isinstance(value, dict) else "不是字典类型"
                )
                current_path_str = ".".join(current_path)
                self.logger.error(f"引用解析失败: {ref_path}")
                self.logger.error(f"  - 失败位置: {current_path_str}")
                self.logger.error(f"  - 当前值类型: {type(value)}")
                if isinstance(value, dict):
                    self.logger.error(f"  - 可用键: {list(value.keys())}")
                raise ValueError(f"无法解析引用: {ref_path}")

        return value

    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """评估执行条件"""
        try:
            # 这里可以实现更复杂的条件评估
            # 目前简化处理，只支持基本的布尔表达式
            return True
        except:
            return False

    def _is_code_generation_step(self, step: ToolCall) -> bool:
        """判断是否为代码生成步骤"""
        # 根据工具名称或描述判断是否需要代码生成
        code_generation_tools = [
            "generate_code",
            "write_script",
            "create_function",
            "modify_code",
            "code_optimization",
        ]

        code_keywords = [
            "生成代码",
            "编写脚本",
            "创建函数",
            "修改代码",
            "代码优化",
            "code",
            "script",
        ]

        return step.tool_name in code_generation_tools or any(
            keyword in step.description.lower() for keyword in code_keywords
        )

    def _execute_code_generation_step(
        self, step: ToolCall, resolved_params: Dict[str, Any], context: Dict[str, Any]
    ) -> Any:
        """执行代码生成步骤"""
        try:
            # 如果有RAG系统，检索相关代码示例和知识
            code_knowledge = []
            if self.rag_system:
                try:
                    self.logger.info(f"为代码生成步骤检索知识: {step.description}")
                    rag_response = self.rag_system.query(step.description, top_k=3)
                    if rag_response.get("status") == "success":
                        results = rag_response.get("results", [])
                        for result in results:
                            code_knowledge.append({
                                "content": result.get("content", ""),
                                "source": result.get("metadata", {}).get("source", "rag_system")
                            })
                except Exception as e:
                    self.logger.warning(f"代码知识检索失败: {e}")

            # 构建代码生成提示
            code_prompt = self._build_code_generation_prompt(
                step, resolved_params, context, code_knowledge
            )

            # 使用代码生成模式调用LLM
            system_prompt = """你是一个专业的Python代码生成助手，擅长水文数据分析和建模。
请生成符合要求的高质量代码，遵循以下原则：
1. 代码清晰、可读、高效
2. 包含完整的错误处理
3. 添加必要的文档字符串和注释
4. 使用合适的数据结构和算法
5. 遵循水文建模领域的最佳实践
6. 返回标准格式的结果（dict/JSON）
"""
            messages = [
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=code_prompt),
            ]

            response = self.llm_client.chat(
                messages, task_type="coding", temperature=0.1, max_tokens=3000
            )

            if response.success:
                # 保存生成的代码到tmp目录
                generated_code = response.content
                code_file_path = self._save_generated_code(
                    generated_code,
                    step.tool_name,
                    step.description
                )

                # 模拟工具调用结果格式
                return type(
                    "ToolResult",
                    (),
                    {
                        "success": True,
                        "output": {
                            "generated_code": generated_code,
                            "code_file_path": code_file_path,
                            "step_description": step.description,
                            "model_used": response.metadata.get(
                                "model_used", "unknown"
                            ),
                        },
                        "error": None,
                    },
                )()
            else:
                return type(
                    "ToolResult",
                    (),
                    {
                        "success": False,
                        "output": {},
                        "error": f"代码生成失败: {response.error}",
                    },
                )()

        except Exception as e:
            return type(
                "ToolResult",
                (),
                {"success": False, "output": {}, "error": f"代码生成异常: {str(e)}"},
            )()

    def _build_code_generation_prompt(
        self, step: ToolCall, resolved_params: Dict[str, Any], context: Dict[str, Any],
        code_knowledge: List[Dict[str, Any]] = None
    ) -> str:
        """构建代码生成提示词"""

        # 格式化代码知识
        knowledge_section = ""
        if code_knowledge:
            knowledge_section = "\n相关代码示例和知识:\n"
            for i, knowledge in enumerate(code_knowledge[:3], 1):
                content = knowledge.get("content", "")
                source = knowledge.get("source", "unknown")
                knowledge_section += f"\n示例{i} (来源: {source}):\n{content}\n"

        prompt = f"""任务描述: {step.description}

参数信息:
{self._format_parameters(resolved_params)}

上下文信息:
{self._format_context(context)}
{knowledge_section}

请根据以上信息生成相应的Python代码。要求:
1. 代码要清晰、可读、高效
2. 包含完整的文档字符串和注释
3. 包含完善的错误处理 (try-except)
4. 遵循水文建模领域的最佳实践
5. 使用提供的参数信息
6. 返回dict格式的结果，包含success字段和结果数据
7. 如果提供了代码示例，请参考其风格和模式

请生成完整的可执行代码:"""
        return prompt

    def _format_parameters(self, params: Dict[str, Any]) -> str:
        """格式化参数信息"""
        if not params:
            return "无参数"

        formatted = []
        for key, value in params.items():
            formatted.append(f"- {key}: {value}")

        return "\n".join(formatted)

    def _format_context(self, context: Dict[str, Any]) -> str:
        """格式化上下文信息"""
        if not context:
            return "无上下文信息"

        formatted = []
        for key, value in context.items():
            if isinstance(value, dict) and "output" in value:
                formatted.append(f"- {key}: {value['output']}")
            else:
                formatted.append(f"- {key}: {value}")

        return "\n".join(formatted)

    def _get_available_data_directories(self) -> List[str]:
        """获取可用的数据目录列表"""
        available_dirs = []

        # 检查默认数据目录
        if os.path.exists(DATASET_DIR):
            available_dirs.append(DATASET_DIR)

        # 检查通用的data目录
        if os.path.exists("data"):
            available_dirs.append("data")
            # 检查data目录下的子目录
            try:
                for item in os.listdir("data"):
                    item_path = os.path.join("data", item)
                    if os.path.isdir(item_path):
                        available_dirs.append(item_path)
            except (OSError, PermissionError):
                pass

        # 去重并排序
        available_dirs = sorted(list(set(available_dirs)))

        # 如果没有找到任何目录，至少返回默认值
        if not available_dirs:
            available_dirs = [DATASET_DIR]

        return available_dirs

    def _save_generated_code(
        self, code: str, tool_name: str, description: str
    ) -> str:
        """
        保存生成的代码到tmp目录

        Args:
            code: 生成的代码
            tool_name: 工具名称
            description: 步骤描述

        Returns:
            str: 保存的文件路径
        """
        try:
            # 创建tmp目录
            tmp_dir = Path("tmp")
            tmp_dir.mkdir(exist_ok=True)

            # 生成文件名（使用时间戳确保唯一性）
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # 从tool_name中提取有意义的名称
            safe_tool_name = tool_name.replace("_", "").replace(" ", "")
            filename = f"{safe_tool_name}_{timestamp}.py"

            file_path = tmp_dir / filename

            # 添加文件头注释
            header = f'''"""
生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
任务描述: {description[:100]}...
工具名称: {tool_name}
"""

'''

            # 写入文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(header + code)

            self.logger.info(f"生成的代码已保存到: {file_path}")
            return str(file_path)

        except Exception as e:
            self.logger.error(f"保存生成的代码失败: {e}")
            return ""

    def _create_error_result(self, task_id: str, error_msg: str) -> TaskResult:
        """创建错误结果"""
        return TaskResult(
            task_id=task_id,
            status=ExecutionStatus.FAILED,
            start_time=datetime.now(),
            end_time=datetime.now(),
            error=error_msg,
        )
