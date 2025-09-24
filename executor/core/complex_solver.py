"""
复杂任务解决器 - 使用LLM+RAG生成解决方案
"""

import logging
import json
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field

from ..models.task import Task, TaskType
from ..models.result import TaskResult, ExecutionStatus
from .llm_client import LLMClientFactory, LLMMessage, BaseLLMClient
from .simple_executor import SimpleTaskExecutor


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


class ComplexTaskSolver:
    """复杂任务智能解决器"""

    def __init__(
        self,
        simple_executor: SimpleTaskExecutor,
        llm_client: BaseLLMClient = None,
        rag_system = None,
        enable_debug: bool = False
    ):
        """
        初始化复杂任务解决器

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

        self.logger.info("复杂任务解决器初始化完成")

    def solve_complex_task(self, task: Task, context: Dict[str, Any] = None) -> TaskResult:
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
                task.task_id,
                f"任务类型错误，期望 {TaskType.COMPLEX}，实际 {task.type}"
            )

        try:
            # 创建任务结果
            task_result = TaskResult(
                task_id=task.task_id,
                status=ExecutionStatus.RUNNING,
                start_time=datetime.now()
            )

            self.logger.info(f"开始解决复杂任务: {task.task_id} - {task.name}")

            # 步骤1: 查询知识库
            knowledge_chunks = self._query_knowledge_base(task)

            # 步骤2: 使用推理模型生成解决方案
            solution_plan = self._generate_solution_plan(task, knowledge_chunks)

            if not solution_plan:
                return self._create_error_result(
                    task.task_id,
                    "无法生成有效的解决方案"
                )

            # 步骤3: 执行解决方案
            execution_result = self._execute_solution_plan(solution_plan, context)

            # 更新任务结果
            task_result.status = execution_result["status"]
            task_result.outputs = execution_result["outputs"]
            task_result.error = execution_result.get("error")

            # 添加解决方案信息到元数据
            task_result.metadata.update({
                "solution_type": solution_plan.solution_type,
                "steps_count": len(solution_plan.steps),
                "confidence": solution_plan.confidence,
                "knowledge_chunks_used": len(knowledge_chunks)
            })

            task_result.end_time = datetime.now()
            task_result.calculate_duration()

            if task_result.status == ExecutionStatus.COMPLETED:
                self.logger.info(f"复杂任务 {task.task_id} 解决成功")
            else:
                self.logger.error(f"复杂任务 {task.task_id} 解决失败: {task_result.error}")

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
                    # TODO: 实际集成HydroRAG
                    # knowledge_chunks = self.rag_system.search(query, top_k=5)
                    pass

            # 如果没有RAG系统或检索失败，使用预设知识
            if not knowledge_chunks:
                knowledge_chunks = self._get_default_knowledge(task)

            self.logger.info(f"检索到 {len(knowledge_chunks)} 个知识片段")
            return knowledge_chunks

        except Exception as e:
            self.logger.warning(f"知识库检索失败: {e}")
            return self._get_default_knowledge(task)

    def _generate_solution_plan(self, task: Task, knowledge_chunks: List[Dict[str, Any]]) -> Optional[SolutionPlan]:
        """生成解决方案计划"""
        try:
            # 构建提示词
            prompt = self._build_solution_prompt(task, knowledge_chunks)

            # 调用LLM生成解决方案
            messages = [
                LLMMessage(role="system", content=self._get_system_prompt()),
                LLMMessage(role="user", content=prompt)
            ]

            # 使用推理模式生成解决方案
            response = self.llm_client.chat(messages, task_type="reasoning", temperature=0.3, max_tokens=2000)

            if not response.success:
                self.logger.error(f"LLM调用失败: {response.error}")
                return None

            # 解析响应
            solution_plan = self._parse_solution_response(task.task_id, response.content)

            if solution_plan:
                self.logger.info(f"生成解决方案成功，包含 {len(solution_plan.steps)} 个步骤")
            else:
                self.logger.error("解决方案解析失败")

            return solution_plan

        except Exception as e:
            self.logger.error(f"生成解决方案失败: {e}")
            return None

    def _execute_solution_plan(self, solution_plan: SolutionPlan, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行解决方案计划"""
        try:
            outputs = {}
            step_results = []
            current_context = context.copy()

            for step in solution_plan.steps:
                self.logger.info(f"执行步骤 {step.step_id}: {step.description}")

                # 检查执行条件
                if step.condition and not self._evaluate_condition(step.condition, current_context):
                    self.logger.info(f"步骤 {step.step_id} 条件不满足，跳过执行")
                    continue

                # 解析参数中的引用
                resolved_params = self._resolve_step_parameters(step.parameters, current_context)

                # 判断是否需要代码生成
                if self._is_code_generation_step(step):
                    # 使用代码生成模式
                    tool_result = self._execute_code_generation_step(step, resolved_params, current_context)
                else:
                    # 调用简单任务执行器执行工具
                    tool_result = self.simple_executor.tool_registry.call_tool(step.tool_name, resolved_params)

                step_result = {
                    "step_id": step.step_id,
                    "tool_name": step.tool_name,
                    "success": tool_result.success,
                    "output": tool_result.output,
                    "error": tool_result.error
                }

                step_results.append(step_result)

                if tool_result.success:
                    # 更新上下文，供后续步骤使用
                    current_context[f"step_{step.step_id}"] = {
                        "success": True,
                        "output": tool_result.output
                    }
                    outputs.update(tool_result.output)
                else:
                    self.logger.error(f"步骤 {step.step_id} 执行失败: {tool_result.error}")
                    return {
                        "status": ExecutionStatus.FAILED,
                        "outputs": outputs,
                        "error": f"步骤 {step.step_id} 执行失败: {tool_result.error}",
                        "step_results": step_results
                    }

            return {
                "status": ExecutionStatus.COMPLETED,
                "outputs": outputs,
                "step_results": step_results
            }

        except Exception as e:
            self.logger.error(f"执行解决方案失败: {e}")
            return {
                "status": ExecutionStatus.FAILED,
                "outputs": {},
                "error": f"执行解决方案失败: {str(e)}"
            }

    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """你是一个水文建模专家，擅长将复杂的水文建模任务分解为简单的工具调用序列。

可用工具:
{tools}

请根据用户的复杂任务描述和相关知识，生成一个工具调用序列来解决问题。

输出格式要求:
- 必须是有效的JSON格式
- 包含solution_type、description、steps字段
- steps是工具调用列表，每个包含step_id、tool_name、parameters、description字段
- 参数可以使用引用格式 ${{step_X.output.field_name}} 来引用前面步骤的输出

示例输出:
{{
  "solution_type": "tool_sequence",
  "description": "使用工具序列解决复杂任务",
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
}}""".format(tools=self._format_available_tools())

    def _build_solution_prompt(self, task: Task, knowledge_chunks: List[Dict[str, Any]]) -> str:
        """构建解决方案提示词"""
        prompt = f"""
任务描述: {task.description}

相关知识:
{self._format_knowledge_chunks(knowledge_chunks)}

请分析这个复杂任务，并生成一个使用可用工具的解决方案。
重点考虑:
1. 任务的具体需求和目标
2. 工具之间的依赖关系和数据流
3. 参数的正确设置和引用
4. 步骤的逻辑顺序

请生成JSON格式的解决方案:
"""
        return prompt

    def _parse_solution_response(self, task_id: str, response_content: str) -> Optional[SolutionPlan]:
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
                    condition=step_data.get("condition")
                )
                tool_calls.append(tool_call)

            # 创建解决方案计划
            solution_plan = SolutionPlan(
                task_id=task_id,
                solution_type=solution_data.get("solution_type", "tool_sequence"),
                description=solution_data.get("description", ""),
                steps=tool_calls
            )

            return solution_plan

        except Exception as e:
            self.logger.error(f"解析解决方案响应失败: {e}")
            self.logger.debug(f"响应内容: {response_content}")
            return None

    def _get_available_tools(self) -> Dict[str, Any]:
        """获取可用工具信息"""
        if hasattr(self.simple_executor, 'tool_registry'):
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
                "relevance": 0.8
            },
            {
                "content": "GR4J模型需要日尺度的降雨和蒸发数据，以及径流观测数据",
                "source": "default_knowledge",
                "relevance": 0.7
            }
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

    def _resolve_step_parameters(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """解析步骤参数中的引用"""
        resolved = {}

        for key, value in parameters.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                # 解析引用
                ref_path = value[2:-1]  # 移除 ${ 和 }
                resolved_value = self._resolve_reference(ref_path, context)
                resolved[key] = resolved_value
            else:
                resolved[key] = value

        return resolved

    def _resolve_reference(self, ref_path: str, context: Dict[str, Any]) -> Any:
        """解析参数引用"""
        parts = ref_path.split('.')
        value = context

        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
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
            "generate_code", "write_script", "create_function",
            "modify_code", "code_optimization"
        ]

        code_keywords = [
            "生成代码", "编写脚本", "创建函数",
            "修改代码", "代码优化", "code", "script"
        ]

        return (
            step.tool_name in code_generation_tools or
            any(keyword in step.description.lower() for keyword in code_keywords)
        )

    def _execute_code_generation_step(self, step: ToolCall, resolved_params: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """执行代码生成步骤"""
        try:
            # 构建代码生成提示
            code_prompt = self._build_code_generation_prompt(step, resolved_params, context)

            # 使用代码生成模式调用LLM
            messages = [
                LLMMessage(role="system", content="你是一个专业的Python代码生成助手。请生成符合要求的高质量代码。"),
                LLMMessage(role="user", content=code_prompt)
            ]

            response = self.llm_client.chat(messages, task_type="coding", temperature=0.1, max_tokens=2000)

            if response.success:
                # 模拟工具调用结果格式
                return type('ToolResult', (), {
                    'success': True,
                    'output': {
                        'generated_code': response.content,
                        'step_description': step.description,
                        'model_used': response.metadata.get('model_used', 'unknown')
                    },
                    'error': None
                })()
            else:
                return type('ToolResult', (), {
                    'success': False,
                    'output': {},
                    'error': f"代码生成失败: {response.error}"
                })()

        except Exception as e:
            return type('ToolResult', (), {
                'success': False,
                'output': {},
                'error': f"代码生成异常: {str(e)}"
            })()

    def _build_code_generation_prompt(self, step: ToolCall, resolved_params: Dict[str, Any], context: Dict[str, Any]) -> str:
        """构建代码生成提示词"""
        prompt = f"""任务描述: {step.description}

参数信息:
{self._format_parameters(resolved_params)}

上下文信息:
{self._format_context(context)}

请根据以上信息生成相应的Python代码。要求:
1. 代码要清晰、可读、高效
2. 包含必要的注释
3. 处理可能的异常情况
4. 遵循水文建模领域的最佳实践

代码:"""
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
            if isinstance(value, dict) and 'output' in value:
                formatted.append(f"- {key}: {value['output']}")
            else:
                formatted.append(f"- {key}: {value}")

        return "\n".join(formatted)

    def _create_error_result(self, task_id: str, error_msg: str) -> TaskResult:
        """创建错误结果"""
        return TaskResult(
            task_id=task_id,
            status=ExecutionStatus.FAILED,
            start_time=datetime.now(),
            end_time=datetime.now(),
            error=error_msg
        )