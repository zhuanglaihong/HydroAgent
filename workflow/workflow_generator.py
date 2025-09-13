"""
Author: zhuanglaihong
Date: 2025-07-28
Description: 工作流生成器 - 第5步：基于检索上下文调用大模型，编排生成详细的工作流
"""

import logging
import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from .workflow_types import WorkflowPlan, WorkflowStep, StepType, IntentAnalysis

logger = logging.getLogger(__name__)


class WorkflowPlanOutput(BaseModel):
    """工作流计划输出结构"""

    workflow_plan: Dict[str, Any] = Field(description="完整的工作流计划")


class WorkflowGenerator:
    """工作流生成器 - 负责基于上下文生成可执行的工作流"""

    def __init__(
        self,
        llm,
        max_steps: int = 10,
        allow_parallel: bool = False,
        include_validation: bool = True,
    ):
        """
        初始化工作流生成器

        Args:
            llm: 语言模型实例
            max_steps: 最大步骤数
            allow_parallel: 是否允许并行执行
            include_validation: 是否包含验证步骤
        """
        self.llm = llm
        self.max_steps = max_steps
        self.allow_parallel = allow_parallel
        self.include_validation = include_validation
        self.parser = PydanticOutputParser(pydantic_object=WorkflowPlanOutput)
        self._setup_prompts()
        self._load_workflow_templates()

    def _setup_prompts(self):
        """设置提示模板"""
        self.workflow_generation_prompt = PromptTemplate(
            template="""你是一个专业的水文模型工作流规划专家。请根据提供的上下文生成详细的、可执行的工作流计划。

上下文信息：
{context}

请严格按照以下要求生成工作流：

1. 输出格式：必须是完整的JSON格式，符合WorkflowPlan结构
2. 步骤设计：每个步骤必须包含明确的工具调用和完整参数
3. 依赖关系：正确设置步骤间的依赖关系，确保逻辑执行顺序
4. 参数配置：使用合理的默认参数，确保工具能够正常执行
5. LangChain兼容：生成的工作流必须能被LangChain AgentExecutor直接执行

工作流生成规则：
- 为每个步骤生成唯一的step_id（如step_1, step_2等）
- 设置合理的超时时间（参数查询：30s，数据准备：120s，模型率定：600s，模型评估：180s）
- 对于可能失败的步骤设置重试次数（通常为1）
- 使用项目的默认配置（data_dir: "data/camels_11532500", result_dir: "result"）
- 为工作流生成有意义的plan_id、name和description

{format_instructions}

请现在生成工作流：
""",
            input_variables=["context"],
            partial_variables={
                "format_instructions": self.parser.get_format_instructions()
            },
        )

    def _load_workflow_templates(self):
        """加载工作流模板"""
        self.workflow_templates = {
            "parameter_query": {
                "name": "模型参数查询",
                "description": "查询指定模型的参数信息",
                "steps": [
                    {
                        "tool_name": "get_model_params",
                        "parameters": {"model_name": "gr4j"},
                        "timeout": 30,
                        "retry_count": 0,
                    }
                ],
            },
            "data_preparation": {
                "name": "数据准备",
                "description": "准备和预处理水文数据",
                "steps": [
                    {
                        "tool_name": "prepare_data",
                        "parameters": {
                            "data_dir": "data/camels_11532500",
                            "target_data_scale": "D",
                        },
                        "timeout": 120,
                        "retry_count": 1,
                    }
                ],
            },
            "model_calibration": {
                "name": "模型率定",
                "description": "率定水文模型参数",
                "steps": [
                    {
                        "tool_name": "calibrate_model",
                        "parameters": {
                            "model_name": "gr4j",
                            "data_dir": "data/camels_11532500",
                            "exp_name": "model_calibration",
                        },
                        "timeout": 600,
                        "retry_count": 1,
                    }
                ],
            },
            "model_evaluation": {
                "name": "模型评估",
                "description": "评估模型性能",
                "steps": [
                    {
                        "tool_name": "evaluate_model",
                        "parameters": {
                            "result_dir": "result",
                            "exp_name": "model_calibration",
                        },
                        "timeout": 180,
                        "retry_count": 1,
                    }
                ],
            },
            "complex_workflow": {
                "name": "完整建模流程",
                "description": "数据准备 -> 模型率定 -> 性能评估",
                "steps": [
                    {
                        "tool_name": "prepare_data",
                        "parameters": {
                            "data_dir": "data/camels_11532500",
                            "target_data_scale": "D",
                        },
                        "dependencies": [],
                        "timeout": 120,
                        "retry_count": 1,
                    },
                    {
                        "tool_name": "calibrate_model",
                        "parameters": {
                            "model_name": "gr4j",
                            "data_dir": "data/camels_11532500",
                            "exp_name": "auto_calibration",
                        },
                        "dependencies": ["step_1"],
                        "timeout": 600,
                        "retry_count": 1,
                    },
                    {
                        "tool_name": "evaluate_model",
                        "parameters": {
                            "result_dir": "result",
                            "exp_name": "auto_calibration",
                        },
                        "dependencies": ["step_2"],
                        "timeout": 180,
                        "retry_count": 1,
                    },
                ],
            },
        }

    def generate_workflow(
        self,
        context: str,
        user_query: str = "",
        expanded_query: str = "",
        intent_analysis: Optional[IntentAnalysis] = None,
    ) -> WorkflowPlan:
        """
        生成工作流计划

        Args:
            context: 构建好的上下文
            user_query: 原始用户查询
            expanded_query: 扩展后的查询
            intent_analysis: 意图分析结果

        Returns:
            WorkflowPlan: 生成的工作流计划
        """
        try:
            logger.info("开始生成工作流...")

            # 1. 尝试使用LLM生成工作流
            workflow_data = self._generate_with_llm(context)

            # 2. 验证和修正工作流
            validated_workflow = self._validate_and_fix_workflow(
                workflow_data, intent_analysis
            )

            # 3. 构建WorkflowPlan对象
            workflow_plan = self._build_workflow_plan(
                validated_workflow, user_query, expanded_query, context
            )

            logger.info(f"工作流生成完成，包含{len(workflow_plan.steps)}个步骤")
            return workflow_plan

        except Exception as e:
            logger.error(f"工作流生成失败: {e}")
            # 返回模板工作流
            return self._create_template_workflow(user_query, intent_analysis)

    def _generate_with_llm(self, context: str) -> Dict[str, Any]:
        """使用LLM生成工作流"""
        try:
            chain = self.workflow_generation_prompt | self.llm | self.parser
            result = chain.invoke({"context": context})

            # 提取workflow_plan部分
            if hasattr(result, "workflow_plan"):
                return result.workflow_plan
            elif isinstance(result, dict) and "workflow_plan" in result:
                return result["workflow_plan"]
            else:
                logger.warning("LLM输出格式不符合预期，尝试直接解析")
                return self._parse_llm_output(str(result))

        except Exception as e:
            logger.error(f"LLM工作流生成失败: {e}")
            raise

    def _parse_llm_output(self, output: str) -> Dict[str, Any]:
        """解析LLM输出"""
        try:
            # 尝试直接JSON解析
            if output.strip().startswith("{"):
                parsed = json.loads(output)
                if "workflow_plan" in parsed:
                    return parsed["workflow_plan"]
                return parsed

            # 尝试提取JSON部分
            import re

            json_match = re.search(r"\{.*\}", output, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                parsed = json.loads(json_str)
                if "workflow_plan" in parsed:
                    return parsed["workflow_plan"]
                return parsed

            raise ValueError("无法从LLM输出中提取有效的JSON")

        except Exception as e:
            logger.error(f"解析LLM输出失败: {e}")
            raise

    def _validate_and_fix_workflow(
        self, workflow_data: Dict[str, Any], intent_analysis: Optional[IntentAnalysis]
    ) -> Dict[str, Any]:
        """验证和修正工作流"""
        try:
            # 1. 基本字段验证
            if "plan_id" not in workflow_data:
                workflow_data["plan_id"] = f"workflow_{uuid.uuid4().hex[:8]}"

            if "name" not in workflow_data:
                workflow_data["name"] = "自动生成工作流"

            if "description" not in workflow_data:
                workflow_data["description"] = "基于用户需求自动生成的工作流"

            if "steps" not in workflow_data:
                workflow_data["steps"] = []

            # 2. 步骤验证和修正
            validated_steps = []
            for i, step in enumerate(workflow_data["steps"]):
                validated_step = self._validate_step(step, i + 1)
                if validated_step:
                    validated_steps.append(validated_step)

            workflow_data["steps"] = validated_steps

            # 3. 依赖关系验证
            workflow_data["steps"] = self._validate_dependencies(workflow_data["steps"])

            # 4. 根据意图分析补充缺失步骤
            if intent_analysis:
                workflow_data["steps"] = self._supplement_missing_steps(
                    workflow_data["steps"], intent_analysis
                )

            return workflow_data

        except Exception as e:
            logger.error(f"工作流验证失败: {e}")
            raise

    def _validate_step(
        self, step: Dict[str, Any], step_number: int
    ) -> Optional[Dict[str, Any]]:
        """验证单个步骤"""
        try:
            # 必需字段检查
            if "step_id" not in step:
                step["step_id"] = f"step_{step_number}"

            if "name" not in step:
                step["name"] = f"步骤{step_number}"

            if "description" not in step:
                step["description"] = f"执行{step.get('tool_name', '未知工具')}"

            if "step_type" not in step:
                step["step_type"] = "tool_call"

            # 工具名称验证
            valid_tools = [
                "get_model_params",
                "prepare_data",
                "calibrate_model",
                "evaluate_model",
            ]
            if "tool_name" not in step or step["tool_name"] not in valid_tools:
                logger.warning(
                    f"步骤{step_number}的工具名称无效: {step.get('tool_name')}"
                )
                return None

            # 参数验证
            if "parameters" not in step:
                step["parameters"] = {}

            # 补充默认参数
            step["parameters"] = self._supplement_default_parameters(
                step["tool_name"], step["parameters"]
            )

            # 其他字段默认值
            if "dependencies" not in step:
                step["dependencies"] = []

            if "conditions" not in step:
                step["conditions"] = {}

            if "retry_count" not in step:
                step["retry_count"] = (
                    1 if step["tool_name"] != "get_model_params" else 0
                )

            if "timeout" not in step:
                step["timeout"] = self._get_default_timeout(step["tool_name"])

            return step

        except Exception as e:
            logger.error(f"步骤验证失败: {e}")
            return None

    def _supplement_default_parameters(
        self, tool_name: str, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """补充默认参数"""
        import os
        from pathlib import Path
        
        # 获取项目根目录
        project_root = Path(__file__).parent.parent
        
        defaults = {
            "get_model_params": {"model_name": "gr4j"},
            "prepare_data": {
                "data_dir": str(project_root / "data" / "camels_11532500"),
                "target_data_scale": "D",
            },
            "calibrate_model": {
                "model_name": "gr4j",
                "data_dir": str(project_root / "data" / "camels_11532500"),
                "data_type": "owndata",
                "exp_name": "auto_calibration",
                "result_dir": str(project_root / "result"),
            },
            "evaluate_model": {
                "model_name": "gr4j",  # 添加默认的model_name
                "result_dir": str(project_root / "result"),
                "exp_name": "auto_calibration",
                "cv_fold": 1,
            },
        }

        if tool_name in defaults:
            for key, value in defaults[tool_name].items():
                if key not in parameters:
                    parameters[key] = value

        return parameters

    def _get_default_timeout(self, tool_name: str) -> int:
        """获取默认超时时间"""
        timeouts = {
            "get_model_params": 30,
            "prepare_data": 120,
            "calibrate_model": 600,
            "evaluate_model": 180,
        }
        return timeouts.get(tool_name, 300)

    def _validate_dependencies(
        self, steps: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """验证依赖关系"""
        step_ids = {step["step_id"] for step in steps}

        for step in steps:
            # 移除无效的依赖
            valid_dependencies = []
            for dep in step.get("dependencies", []):
                if dep in step_ids and dep != step["step_id"]:
                    valid_dependencies.append(dep)
            step["dependencies"] = valid_dependencies

        return steps

    def _supplement_missing_steps(
        self, steps: List[Dict[str, Any]], intent_analysis: IntentAnalysis
    ) -> List[Dict[str, Any]]:
        """根据意图分析补充缺失步骤"""
        existing_tools = {step["tool_name"] for step in steps}
        suggested_tools = set(intent_analysis.suggested_tools)

        # 检查是否需要补充步骤
        missing_tools = suggested_tools - existing_tools

        if not missing_tools:
            return steps

        logger.info(f"补充缺失的工具: {missing_tools}")

        # 根据任务类型补充步骤
        if intent_analysis.task_type == "complex_workflow":
            return self._build_complete_workflow_steps(intent_analysis)
        else:
            # 补充单个缺失工具
            for tool in missing_tools:
                if tool in self.workflow_templates:
                    template_step = self.workflow_templates[tool]["steps"][0]
                    new_step = self._create_step_from_template(
                        template_step, len(steps) + 1, tool
                    )
                    steps.append(new_step)

        return steps

    def _build_complete_workflow_steps(
        self, intent_analysis: IntentAnalysis
    ) -> List[Dict[str, Any]]:
        """构建完整工作流步骤"""
        template = self.workflow_templates["complex_workflow"]
        steps = []

        for i, step_template in enumerate(template["steps"]):
            step = self._create_step_from_template(step_template, i + 1)

            # 根据实体信息调整参数
            if intent_analysis.entities:
                if "model_name" in intent_analysis.entities:
                    if "model_name" in step["parameters"]:
                        step["parameters"]["model_name"] = intent_analysis.entities[
                            "model_name"
                        ]

                if "data_path" in intent_analysis.entities:
                    if "data_dir" in step["parameters"]:
                        step["parameters"]["data_dir"] = intent_analysis.entities[
                            "data_path"
                        ]

            steps.append(step)

        return steps

    def _create_step_from_template(
        self,
        template: Dict[str, Any],
        step_number: int,
        override_tool: Optional[str] = None,
    ) -> Dict[str, Any]:
        """从模板创建步骤"""
        return {
            "step_id": f"step_{step_number}",
            "name": f"执行{override_tool or template['tool_name']}",
            "description": f"调用{override_tool or template['tool_name']}工具",
            "step_type": "tool_call",
            "tool_name": override_tool or template["tool_name"],
            "parameters": template.get("parameters", {}).copy(),
            "dependencies": template.get("dependencies", []),
            "conditions": {},
            "retry_count": template.get("retry_count", 1),
            "timeout": template.get("timeout", 300),
        }

    def _build_workflow_plan(
        self,
        workflow_data: Dict[str, Any],
        user_query: str,
        expanded_query: str,
        context: str,
    ) -> WorkflowPlan:
        """构建WorkflowPlan对象"""
        try:
            # 构建步骤对象
            workflow_steps = []
            for step_data in workflow_data["steps"]:
                step = WorkflowStep(
                    step_id=step_data["step_id"],
                    name=step_data["name"],
                    description=step_data["description"],
                    step_type=StepType(step_data["step_type"]),
                    tool_name=step_data.get("tool_name"),
                    parameters=step_data.get("parameters", {}),
                    dependencies=step_data.get("dependencies", []),
                    conditions=step_data.get("conditions", {}),
                    retry_count=step_data.get("retry_count", 0),
                    timeout=step_data.get("timeout"),
                )
                workflow_steps.append(step)

            # 构建工作流计划
            workflow_plan = WorkflowPlan(
                plan_id=workflow_data["plan_id"],
                name=workflow_data["name"],
                description=workflow_data["description"],
                steps=workflow_steps,
                user_query=user_query,
                expanded_query=expanded_query,
                context=(
                    context[:500] + "..." if len(context) > 500 else context
                ),  # 截断长上下文
                metadata={
                    "generated_by": "WorkflowGenerator",
                    "llm_model": getattr(self.llm, "model", "unknown"),
                    "generation_time": datetime.now().isoformat(),
                    "steps_count": len(workflow_steps),
                },
            )

            return workflow_plan

        except Exception as e:
            logger.error(f"构建WorkflowPlan失败: {e}")
            raise

    def _create_template_workflow(
        self, user_query: str, intent_analysis: Optional[IntentAnalysis]
    ) -> WorkflowPlan:
        """创建模板工作流（回退方案）"""
        logger.info("使用模板工作流作为回退方案")

        # 选择合适的模板
        if intent_analysis and intent_analysis.task_type in self.workflow_templates:
            template_name = intent_analysis.task_type
        else:
            template_name = "parameter_query"  # 默认模板

        template = self.workflow_templates[template_name]

        # 构建步骤
        steps = []
        for i, step_template in enumerate(template["steps"]):
            step = WorkflowStep(
                step_id=f"step_{i+1}",
                name=step_template.get("name", f"执行{step_template['tool_name']}"),
                description=step_template.get(
                    "description", f"调用{step_template['tool_name']}工具"
                ),
                step_type=StepType.TOOL_CALL,
                tool_name=step_template["tool_name"],
                parameters=step_template.get("parameters", {}),
                dependencies=step_template.get("dependencies", []),
                conditions={},
                retry_count=step_template.get("retry_count", 0),
                timeout=step_template.get("timeout", 300),
            )
            steps.append(step)

        # 构建工作流计划
        workflow_plan = WorkflowPlan(
            plan_id=f"template_{template_name}_{uuid.uuid4().hex[:8]}",
            name=template["name"],
            description=template["description"],
            steps=steps,
            user_query=user_query,
            expanded_query="",
            context="使用模板生成的工作流",
            metadata={
                "generated_by": "TemplateWorkflow",
                "template_name": template_name,
                "generation_time": datetime.now().isoformat(),
                "is_fallback": True,
            },
        )

        return workflow_plan

    def validate_workflow_for_langchain(self, workflow_plan: WorkflowPlan) -> bool:
        """验证工作流是否符合LangChain执行要求"""
        try:
            # 检查必需字段
            if not workflow_plan.plan_id or not workflow_plan.steps:
                return False

            # 检查每个步骤
            for step in workflow_plan.steps:
                # 检查工具名称
                if not step.tool_name:
                    return False

                # 检查step_type
                if step.step_type != StepType.TOOL_CALL:
                    logger.warning(f"步骤{step.step_id}的类型不是tool_call")

                # 检查参数
                if not isinstance(step.parameters, dict):
                    return False

            # 检查依赖关系
            step_ids = {step.step_id for step in workflow_plan.steps}
            for step in workflow_plan.steps:
                for dep in step.dependencies:
                    if dep not in step_ids:
                        logger.warning(f"步骤{step.step_id}的依赖{dep}不存在")
                        return False

            return True

        except Exception as e:
            logger.error(f"工作流验证失败: {e}")
            return False
