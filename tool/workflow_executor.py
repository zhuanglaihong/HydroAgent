"""
Author: zhuanglaihong
Date: 2025-09-13
Description: 工作流执行器 - 负责执行生成的工作流计划，调用实际的工具
"""

import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

from workflow.workflow_types import (
    WorkflowPlan,
    WorkflowStep,
    ExecutionResult,
    ExecutionStatus,
)
from .langchain_tool import get_hydromodel_tools

logger = logging.getLogger(__name__)


class WorkflowExecutor:
    """工作流执行器 - 负责执行工作流中的每个步骤"""

    def __init__(self, tools=None, enable_debug: bool = False):
        """
        初始化工作流执行器

        Args:
            tools: 可用工具列表，如果为None则自动获取
            enable_debug: 是否启用调试模式
        """
        self.tools = tools if tools is not None else get_hydromodel_tools()
        self.enable_debug = enable_debug

        # 构建工具映射表
        self.tool_map = {}
        if self.tools:
            for tool in self.tools:
                tool_name = getattr(tool, "name", str(tool))
                self.tool_map[tool_name] = tool

        logger.info(f"工作流执行器初始化完成，可用工具: {list(self.tool_map.keys())}")

    def execute_workflow(self, workflow_plan: WorkflowPlan) -> Dict[str, Any]:
        """
        执行完整的工作流

        Args:
            workflow_plan: 要执行的工作流计划

        Returns:
            Dict: 执行结果，包含每个步骤的结果和总体状态
        """
        logger.info(f"开始执行工作流: {workflow_plan.name}")

        execution_results = {
            "workflow_id": workflow_plan.plan_id,
            "workflow_name": workflow_plan.name,
            "start_time": datetime.now().isoformat(),
            "status": "running",
            "steps": {},
            "step_results": {},  # 存储每个步骤的实际输出
            "total_time": 0,
            "success_count": 0,
            "failed_count": 0,
        }

        start_time = time.time()

        try:
            # 按依赖关系排序步骤
            ordered_steps = self._sort_steps_by_dependencies(workflow_plan.steps)

            for step in ordered_steps:
                logger.info(f"执行步骤: {step.step_id} - {step.name}")

                # 检查依赖是否完成
                if not self._check_dependencies_completed(step, execution_results):
                    logger.error(f"步骤 {step.step_id} 的依赖未完成，跳过执行")
                    execution_results["steps"][step.step_id] = {
                        "status": "skipped",
                        "error": "依赖步骤未完成",
                        "start_time": datetime.now().isoformat(),
                        "execution_time": 0,
                    }
                    execution_results["failed_count"] += 1
                    continue

                # 执行步骤
                step_result = self._execute_step(step, execution_results)
                execution_results["steps"][step.step_id] = step_result

                # 保存步骤的实际输出
                if "result" in step_result:
                    execution_results["step_results"][step.step_id] = step_result[
                        "result"
                    ]

                if step_result["status"] == "success":
                    execution_results["success_count"] += 1
                    logger.info(f"步骤 {step.step_id} 执行成功")
                else:
                    execution_results["failed_count"] += 1
                    logger.error(
                        f"步骤 {step.step_id} 执行失败: {step_result.get('error', '未知错误')}"
                    )

                    # 如果是关键步骤失败，可以选择停止整个工作流
                    # 这里我们继续执行其他步骤

            # 计算总执行时间和最终状态
            execution_results["total_time"] = time.time() - start_time
            execution_results["end_time"] = datetime.now().isoformat()

            if execution_results["failed_count"] == 0:
                execution_results["status"] = "completed"
                logger.info(
                    f"工作流执行完成，所有 {execution_results['success_count']} 个步骤成功"
                )
            else:
                execution_results["status"] = "partial_success"
                logger.warning(
                    f"工作流部分完成，成功: {execution_results['success_count']}，失败: {execution_results['failed_count']}"
                )

        except Exception as e:
            execution_results["status"] = "failed"
            execution_results["error"] = str(e)
            execution_results["total_time"] = time.time() - start_time
            execution_results["end_time"] = datetime.now().isoformat()
            logger.error(f"工作流执行失败: {e}")

        return execution_results

    def _execute_step(
        self, step: WorkflowStep, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行单个步骤

        Args:
            step: 要执行的步骤
            context: 执行上下文，包含之前步骤的结果

        Returns:
            Dict: 步骤执行结果
        """
        step_result = {
            "step_id": step.step_id,
            "step_name": step.name,
            "tool_name": step.tool_name,
            "start_time": datetime.now().isoformat(),
            "status": "running",
            "execution_time": 0,
        }

        start_time = time.time()

        try:
            # 检查工具是否可用
            if step.tool_name not in self.tool_map:
                raise ValueError(f"工具 {step.tool_name} 不可用")

            tool = self.tool_map[step.tool_name]

            # 准备工具参数
            tool_params = self._prepare_tool_parameters(step, context)

            logger.info(f"调用工具 {step.tool_name}，参数: {tool_params}")

            # 执行工具
            if hasattr(tool, "invoke"):
                # LangChain 工具
                result = tool.invoke(tool_params)
            elif callable(tool):
                # 普通函数工具
                result = tool(**tool_params)
            else:
                raise ValueError(f"不支持的工具类型: {type(tool)}")

            step_result["status"] = "success"
            step_result["result"] = result
            logger.info(f"工具 {step.tool_name} 执行成功")

        except Exception as e:
            step_result["status"] = "failed"
            step_result["error"] = str(e)
            logger.error(f"工具 {step.tool_name} 执行失败: {e}")

            # 如果允许重试
            if step.retry_count > 0:
                logger.info(f"尝试重试，剩余重试次数: {step.retry_count}")
                # 这里可以实现重试逻辑
                # 为了简单起见，这里不实现重试

        finally:
            step_result["execution_time"] = time.time() - start_time
            step_result["end_time"] = datetime.now().isoformat()

        return step_result

    def _prepare_tool_parameters(
        self, step: WorkflowStep, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        准备工具参数，可能需要从之前的步骤结果中获取参数

        Args:
            step: 当前步骤
            context: 执行上下文

        Returns:
            Dict: 准备好的工具参数
        """
        import os
        from pathlib import Path

        params = step.parameters.copy()

        # 处理参数中的引用，例如 ${step_1.result.data_path}
        for key, value in params.items():
            if (
                isinstance(value, str)
                and value.startswith("${")
                and value.endswith("}")
            ):
                # 简单的参数引用解析
                reference = value[2:-1]  # 移除 ${ 和 }
                resolved_value = self._resolve_parameter_reference(reference, context)
                if resolved_value is not None:
                    params[key] = resolved_value
                    logger.debug(
                        f"参数 {key} 从引用 {reference} 解析为: {resolved_value}"
                    )

        # 特殊处理：如果是 evaluate_model 工具，尝试从前面的 calibrate_model 步骤获取参数
        if step.tool_name == "evaluate_model":
            # 寻找之前的 calibrate_model 步骤结果
            for dep_step_id in step.dependencies:
                if dep_step_id in context.get("step_results", {}):
                    dep_result = context["step_results"][dep_step_id]
                    if isinstance(dep_result, dict):
                        # 如果率定步骤返回了 result_dir，使用它作为评估的基础目录
                        if "result_dir" in dep_result:
                            result_dir = dep_result["result_dir"]
                            # 获取父目录作为 result_dir，实验名称从路径中提取
                            result_path = Path(result_dir)
                            if result_path.name == params.get("exp_name", ""):
                                # 如果路径末尾已经是实验名称，使用父目录
                                params["result_dir"] = str(result_path.parent)
                                logger.info(
                                    f"从依赖步骤 {dep_step_id} 获取 result_dir: {params['result_dir']}"
                                )
                            else:
                                # 否则使用完整路径作为基础目录
                                params["result_dir"] = str(result_path.parent)
                                params["exp_name"] = result_path.name
                                logger.info(
                                    f"从依赖步骤 {dep_step_id} 更新参数: result_dir={params['result_dir']}, exp_name={params['exp_name']}"
                                )
                        break

        # 处理路径参数，将相对路径转换为绝对路径
        # 获取项目根目录
        project_root = Path(__file__).parent.parent

        path_params = ["data_dir", "result_dir", "file_path", "output_dir", "input_dir"]

        for param_name in path_params:
            if param_name in params:
                path_value = params[param_name]
                if isinstance(path_value, str) and not os.path.isabs(path_value):
                    # 将相对路径转换为基于项目根目录的绝对路径
                    absolute_path = project_root / path_value
                    params[param_name] = str(absolute_path)
                    logger.info(
                        f"路径参数 {param_name} 从相对路径 '{path_value}' 转换为绝对路径 '{absolute_path}'"
                    )

        return params

    def _resolve_parameter_reference(
        self, reference: str, context: Dict[str, Any]
    ) -> Any:
        """
        解析参数引用

        Args:
            reference: 参数引用字符串，例如 "step_1.result.data_path"
            context: 执行上下文

        Returns:
            Any: 解析后的值
        """
        try:
            parts = reference.split(".")
            if len(parts) >= 2:
                step_id = parts[0]
                if step_id in context.get("step_results", {}):
                    result = context["step_results"][step_id]

                    # 导航到指定的属性
                    for part in parts[1:]:
                        if isinstance(result, dict) and part in result:
                            result = result[part]
                        else:
                            return None

                    return result
        except Exception as e:
            logger.warning(f"无法解析参数引用 {reference}: {e}")

        return None

    def _sort_steps_by_dependencies(
        self, steps: List[WorkflowStep]
    ) -> List[WorkflowStep]:
        """
        根据依赖关系对步骤进行拓扑排序

        Args:
            steps: 步骤列表

        Returns:
            List[WorkflowStep]: 排序后的步骤列表
        """
        # 简单的拓扑排序实现
        step_map = {step.step_id: step for step in steps}
        visited = set()
        result = []

        def visit(step_id: str):
            if step_id in visited:
                return

            visited.add(step_id)
            step = step_map.get(step_id)

            if step:
                # 先访问所有依赖
                for dep in step.dependencies:
                    if dep in step_map:
                        visit(dep)

                result.append(step)

        # 访问所有步骤
        for step in steps:
            visit(step.step_id)

        return result

    def _check_dependencies_completed(
        self, step: WorkflowStep, context: Dict[str, Any]
    ) -> bool:
        """
        检查步骤的所有依赖是否已完成

        Args:
            step: 要检查的步骤
            context: 执行上下文

        Returns:
            bool: 如果所有依赖都已完成则返回True
        """
        for dep_id in step.dependencies:
            if dep_id not in context.get("steps", {}):
                return False

            dep_status = context["steps"][dep_id].get("status")
            if dep_status != "success":
                return False

        return True

    def get_available_tools(self) -> List[str]:
        """获取可用工具列表"""
        return list(self.tool_map.keys())

    def validate_workflow(self, workflow_plan: WorkflowPlan) -> Dict[str, Any]:
        """
        验证工作流是否可以执行

        Args:
            workflow_plan: 要验证的工作流

        Returns:
            Dict: 验证结果
        """
        validation_result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
        }

        # 检查工具可用性
        available_tools = set(self.tool_map.keys())
        for step in workflow_plan.steps:
            if step.tool_name not in available_tools:
                validation_result["is_valid"] = False
                validation_result["errors"].append(
                    f"步骤 {step.step_id} 使用的工具 {step.tool_name} 不可用"
                )

        # 检查依赖关系
        step_ids = {step.step_id for step in workflow_plan.steps}
        for step in workflow_plan.steps:
            for dep in step.dependencies:
                if dep not in step_ids:
                    validation_result["is_valid"] = False
                    validation_result["errors"].append(
                        f"步骤 {step.step_id} 依赖的步骤 {dep} 不存在"
                    )

        # 检查循环依赖
        if self._has_circular_dependencies(workflow_plan.steps):
            validation_result["is_valid"] = False
            validation_result["errors"].append("工作流存在循环依赖")

        return validation_result

    def _has_circular_dependencies(self, steps: List[WorkflowStep]) -> bool:
        """检查是否存在循环依赖"""
        step_map = {step.step_id: step for step in steps}
        visited = set()
        rec_stack = set()

        def has_cycle(step_id: str) -> bool:
            if step_id in rec_stack:
                return True
            if step_id in visited:
                return False

            visited.add(step_id)
            rec_stack.add(step_id)

            step = step_map.get(step_id)
            if step:
                for dep in step.dependencies:
                    if dep in step_map and has_cycle(dep):
                        return True

            rec_stack.remove(step_id)
            return False

        for step in steps:
            if step.step_id not in visited:
                if has_cycle(step.step_id):
                    return True

        return False
