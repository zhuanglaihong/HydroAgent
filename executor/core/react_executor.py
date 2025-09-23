"""
React执行器 - 目标导向的迭代执行逻辑
"""

import logging
import copy
from typing import Dict, Any, Optional, List
from datetime import datetime

from ..models.workflow import Workflow, WorkflowMode
from ..models.result import WorkflowResult, ReactIteration, ExecutionStatus
from .task_dispatcher import TaskDispatcher
from .simple_executor import SimpleTaskExecutor
from .complex_solver import ComplexTaskSolver
from .llm_client import LLMClientFactory, LLMMessage, BaseLLMClient


class ReactExecutor:
    """React模式执行器 - 目标导向迭代执行"""

    def __init__(
        self,
        task_dispatcher: TaskDispatcher,
        simple_executor: SimpleTaskExecutor,
        complex_solver: ComplexTaskSolver = None,
        llm_client: BaseLLMClient = None,
        enable_debug: bool = False
    ):
        """
        初始化React执行器

        Args:
            task_dispatcher: 任务分发器
            simple_executor: 简单任务执行器
            complex_solver: 复杂任务解决器
            llm_client: LLM客户端
            enable_debug: 是否启用调试模式
        """
        self.task_dispatcher = task_dispatcher
        self.simple_executor = simple_executor
        self.complex_solver = complex_solver
        self.llm_client = llm_client or LLMClientFactory.create_default_client()
        self.enable_debug = enable_debug
        self.logger = logging.getLogger(__name__)

        self.logger.info("React执行器初始化完成")

    def execute_with_target(self, workflow: Workflow) -> WorkflowResult:
        """
        按目标执行工作流

        Args:
            workflow: 工作流定义

        Returns:
            WorkflowResult: 执行结果
        """
        if workflow.mode != WorkflowMode.REACT:
            raise ValueError("React执行器只能处理React模式的工作流")

        if not workflow.target:
            raise ValueError("React模式工作流必须设置目标")

        # 创建执行结果
        result = WorkflowResult(
            execution_id=f"react_{workflow.workflow_id}_{int(datetime.now().timestamp())}",
            workflow_id=workflow.workflow_id,
            status=ExecutionStatus.RUNNING
        )

        target = workflow.target
        max_iterations = target.max_iterations
        current_iteration = 0
        target_achieved = False

        self.logger.info(f"开始React执行: 目标={target.metric} {target.comparison} {target.threshold}")

        while current_iteration < max_iterations and not target_achieved:
            current_iteration += 1
            self.logger.info(f"React迭代 {current_iteration}/{max_iterations}")

            # 记录迭代开始
            iteration = ReactIteration(
                iteration=current_iteration,
                start_time=datetime.now(),
                target_achieved=False,
                current_metric=None,
                target_metric=target.threshold
            )

            try:
                # 执行一轮工作流
                iteration_result = self._execute_workflow_iteration(workflow, result)

                # 评估目标达成情况
                current_metric = self._extract_target_metric(iteration_result, target.metric)
                target_achieved = target.is_achieved(current_metric) if current_metric is not None else False

                # 更新迭代记录
                iteration.end_time = datetime.now()
                iteration.target_achieved = target_achieved
                iteration.current_metric = current_metric
                iteration.task_results = iteration_result.task_results

                if target_achieved:
                    iteration.reason = f"目标已达成: {target.metric}={current_metric} {target.comparison} {target.threshold}"
                    self.logger.info(f"React执行成功: {iteration.reason}")
                else:
                    iteration.reason = f"目标未达成: {target.metric}={current_metric} 未满足 {target.comparison} {target.threshold}"

                    # 如果还有迭代机会，调整参数
                    if current_iteration < max_iterations:
                        adjustments = self._generate_adjustments(workflow, iteration_result, target, current_metric)
                        iteration.adjustments_made = adjustments
                        workflow = self._apply_adjustments(workflow, adjustments)
                        self.logger.info(f"应用调整策略: {adjustments}")

                # 添加到结果中
                result.react_iterations.append(iteration)

                # 更新整体结果
                result.task_results.update(iteration_result.task_results)

            except Exception as e:
                iteration.end_time = datetime.now()
                iteration.reason = f"迭代执行失败: {str(e)}"
                result.react_iterations.append(iteration)
                self.logger.error(f"React迭代 {current_iteration} 失败: {e}")
                break

        # 完成执行
        result.target_achieved = target_achieved
        result.status = ExecutionStatus.COMPLETED if target_achieved else ExecutionStatus.FAILED
        result.end_time = datetime.now()
        result.calculate_total_duration()

        # 生成最终报告
        result.final_report = self._generate_final_report(workflow, result)

        self.logger.info(f"React执行完成: 迭代{len(result.react_iterations)}次, 目标达成={target_achieved}")

        return result

    def _execute_workflow_iteration(self, workflow: Workflow, overall_result: WorkflowResult) -> WorkflowResult:
        """执行一次工作流迭代"""
        # 创建本次迭代的结果对象
        iteration_result = WorkflowResult(
            execution_id=f"{overall_result.execution_id}_iter",
            workflow_id=workflow.workflow_id,
            status=ExecutionStatus.RUNNING
        )

        # 构建依赖图
        self.task_dispatcher.build_dependency_graph(workflow.tasks)

        # 获取执行顺序
        execution_order = workflow.get_execution_order()

        # 按层级执行任务
        for level, task_ids in enumerate(execution_order):
            self.logger.info(f"执行第 {level + 1} 层任务: {task_ids}")

            for task_id in task_ids:
                task = workflow.get_task_by_id(task_id)
                if task:
                    task_result = self._execute_single_task(task, iteration_result)
                    iteration_result.add_task_result(task_result)

                    # 检查是否失败且设置了遇错停止
                    if (not task_result.is_successful() and
                        workflow.global_settings.error_handling.value == "stop_on_error"):
                        self.logger.error(f"任务 {task_id} 失败，停止执行")
                        iteration_result.status = ExecutionStatus.FAILED
                        return iteration_result

        iteration_result.status = ExecutionStatus.COMPLETED
        return iteration_result

    def _execute_single_task(self, task, result: WorkflowResult):
        """执行单个任务"""
        try:
            # 分发任务
            from .task_dispatcher import ExecutorType
            executor_type, execution_params = self.task_dispatcher.dispatch_task(task, result.task_results)

            # 根据executor_type调用相应的执行器
            if executor_type == ExecutorType.SIMPLE_EXECUTOR:
                task_result = self.simple_executor.execute_task(task, result.task_results)
            elif executor_type == ExecutorType.COMPLEX_SOLVER:
                if self.complex_solver:
                    task_result = self.complex_solver.solve_complex_task(task, result.task_results)
                else:
                    task_result = self._create_placeholder_result(task, "复杂任务解决器未初始化")
            else:
                task_result = self._create_placeholder_result(task, f"未知执行器类型: {executor_type}")

            self.logger.info(f"任务 {task.task_id} 执行完成，状态: {task_result.status}")

        except Exception as e:
            from datetime import datetime
            from ..models.result import TaskResult, ExecutionStatus

            task_result = TaskResult(
                task_id=task.task_id,
                status=ExecutionStatus.FAILED,
                start_time=datetime.now(),
                end_time=datetime.now(),
                error=str(e)
            )
            self.logger.error(f"任务 {task.task_id} 执行失败: {e}")

        finally:
            # 更新分发器状态
            self.task_dispatcher.update_task_status(task.task_id, task_result.status, task_result)

        return task_result

    def _extract_target_metric(self, result: WorkflowResult, metric_name: str) -> Optional[float]:
        """从执行结果中提取目标指标"""
        try:
            # 在所有任务结果中查找指标
            for task_result in result.task_results.values():
                if metric_name in task_result.outputs:
                    value = task_result.outputs[metric_name]
                    if isinstance(value, (int, float)):
                        return float(value)

                # 检查metrics字段
                if metric_name in task_result.metrics:
                    value = task_result.metrics[metric_name]
                    if isinstance(value, (int, float)):
                        return float(value)

            self.logger.warning(f"未找到目标指标: {metric_name}")
            return None

        except Exception as e:
            self.logger.error(f"提取目标指标失败: {e}")
            return None

    def _generate_adjustments(
        self,
        workflow: Workflow,
        result: WorkflowResult,
        target,
        current_metric: Optional[float]
    ) -> List[str]:
        """生成参数调整策略"""
        adjustments = []

        try:
            # 分析当前结果与目标的差距
            if current_metric is not None and target.threshold is not None:
                gap = abs(current_metric - target.threshold)
                gap_ratio = gap / target.threshold if target.threshold != 0 else 1

                # 根据差距大小决定调整策略
                if gap_ratio > 0.3:  # 差距较大
                    adjustments.append("大幅度参数调整")
                    if target.metric.upper() == "NSE" and current_metric < target.threshold:
                        adjustments.append("增加率定迭代次数")
                        adjustments.append("调整参数搜索范围")
                elif gap_ratio > 0.1:  # 差距中等
                    adjustments.append("中等幅度参数调整")
                    adjustments.append("微调率定算法参数")
                else:  # 差距较小
                    adjustments.append("细微参数调整")

            # 基于失败的任务生成调整策略
            failed_tasks = [
                task_result for task_result in result.task_results.values()
                if not task_result.is_successful()
            ]

            if failed_tasks:
                adjustments.append("修复失败任务的参数配置")

            # 如果没有特定调整，使用默认策略
            if not adjustments:
                adjustments.append("应用默认优化策略")

        except Exception as e:
            self.logger.warning(f"生成调整策略失败: {e}")
            adjustments.append("应用保守调整策略")

        return adjustments

    def _apply_adjustments(self, workflow: Workflow, adjustments: List[str]) -> Workflow:
        """应用调整策略到工作流"""
        # 创建工作流的深拷贝
        adjusted_workflow = copy.deepcopy(workflow)

        try:
            # 根据调整策略修改工作流参数
            for adjustment in adjustments:
                if "增加率定迭代次数" in adjustment:
                    self._adjust_calibration_iterations(adjusted_workflow)
                elif "调整参数搜索范围" in adjustment:
                    self._adjust_parameter_ranges(adjusted_workflow)
                elif "微调率定算法参数" in adjustment:
                    self._adjust_algorithm_parameters(adjusted_workflow)

            self.logger.info(f"应用了 {len(adjustments)} 个调整策略")

        except Exception as e:
            self.logger.error(f"应用调整策略失败: {e}")
            # 返回原始工作流
            return workflow

        return adjusted_workflow

    def _adjust_calibration_iterations(self, workflow: Workflow):
        """调整率定迭代次数"""
        for task in workflow.tasks:
            if task.tool_name == "calibrate_model" and "max_iterations" in task.parameters:
                current_iterations = task.parameters.get("max_iterations", 1000)
                task.parameters["max_iterations"] = min(current_iterations * 1.5, 2000)

    def _adjust_parameter_ranges(self, workflow: Workflow):
        """调整参数搜索范围"""
        for task in workflow.tasks:
            if task.tool_name == "calibrate_model":
                # 这里可以实现参数范围调整逻辑
                pass

    def _adjust_algorithm_parameters(self, workflow: Workflow):
        """微调算法参数"""
        for task in workflow.tasks:
            if task.tool_name == "calibrate_model":
                # 调整优化算法的参数
                task.parameters.setdefault("algorithm_params", {})

    def _generate_final_report(self, workflow: Workflow, result: WorkflowResult):
        """生成最终执行报告"""
        from ..models.result import FinalReport

        # 分析执行结果
        total_iterations = len(result.react_iterations)
        successful_iterations = sum(1 for it in result.react_iterations if it.target_achieved)

        key_achievements = []
        encountered_issues = []
        recommendations = []

        if result.target_achieved:
            key_achievements.append(f"成功达成目标: {workflow.target.metric} >= {workflow.target.threshold}")
            final_metric = result.react_iterations[-1].current_metric
            key_achievements.append(f"最终指标值: {final_metric}")
            key_achievements.append(f"总共迭代: {total_iterations} 次")
        else:
            encountered_issues.append(f"未能达成目标: {workflow.target.metric} >= {workflow.target.threshold}")
            encountered_issues.append(f"达到最大迭代次数: {total_iterations}")

            # 建议
            recommendations.append("考虑调整目标阈值或增加最大迭代次数")
            recommendations.append("检查输入数据质量和模型配置")

        return FinalReport(
            overall_success=result.target_achieved,
            target_achieved=result.target_achieved,
            final_metric_value=result.react_iterations[-1].current_metric if result.react_iterations else None,
            key_achievements=key_achievements,
            encountered_issues=encountered_issues,
            recommendations=recommendations
        )

    def _create_placeholder_result(self, task, message: str):
        """创建占位符结果"""
        from datetime import datetime
        from ..models.result import TaskResult, ExecutionStatus

        return TaskResult(
            task_id=task.task_id,
            status=ExecutionStatus.FAILED,
            start_time=datetime.now(),
            end_time=datetime.now(),
            error=message
        )