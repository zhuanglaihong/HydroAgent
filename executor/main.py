"""
Author: zhuanglaihong
Date: 2024-09-26 16:40:00
LastEditTime: 2024-09-26 16:40:00
LastEditors: zhuanglaihong
Description: Executor 新架构主入口文件
FilePath: \HydroAgent\executor\main.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import json
import logging
import asyncio
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from .core.workflow_receiver import WorkflowReceiver
from .core.task_dispatcher import TaskDispatcher, ExecutorType
from .core.simple_executor import SimpleTaskExecutor
from .core.complex_executor import ComplexTaskExecutor
from .core.react_executor import ReactExecutor
from .core.llm_client import LLMClientFactory
from .models.workflow import Workflow, WorkflowMode
from .models.result import WorkflowResult, ExecutionStatus
from .visualization.result_visualizer import ResultVisualizer


class ExecutorEngine:
    """Executor 执行引擎"""

    def __init__(self, enable_debug: bool = False):
        """
        初始化执行引擎

        Args:
            enable_debug: 是否启用调试模式
        """
        self.enable_debug = enable_debug
        self.logger = self._setup_logging()

        # 初始化核心组件
        self.workflow_receiver = WorkflowReceiver(enable_debug=enable_debug)
        self.task_dispatcher = TaskDispatcher(enable_debug=enable_debug)

        # 初始化执行器
        self.simple_executor = SimpleTaskExecutor(enable_debug=enable_debug)

        # 初始化LLM客户端
        self.llm_client = LLMClientFactory.create_default_client()

        # 初始化复杂任务解决器
        self.complex_executor = ComplexTaskExecutor(
            simple_executor=self.simple_executor,
            llm_client=self.llm_client,
            enable_debug=enable_debug,
        )

        # 初始化React执行器
        self.react_executor = ReactExecutor(
            task_dispatcher=self.task_dispatcher,
            simple_executor=self.simple_executor,
            complex_executor=self.complex_executor,
            llm_client=self.llm_client,
            enable_debug=enable_debug,
        )

        # 初始化结果可视化器
        self.visualizer = ResultVisualizer(enable_debug=enable_debug)

        self.logger.info("Executor 执行引擎初始化完成")

    def execute_workflow(
        self, workflow_data: str, mode: str = "sequential"
    ) -> WorkflowResult:
        """
        执行工作流的主接口

        Args:
            workflow_data: 工作流JSON数据
            mode: 执行模式 (sequential|react)

        Returns:
            WorkflowResult: 执行结果
        """
        workflow = None
        try:
            # 1. 接收和解析工作流
            self.logger.info("开始执行工作流")
            workflow = self.workflow_receiver.receive_workflow(workflow_data)

            # 2. 创建执行结果对象
            result = WorkflowResult(
                execution_id=f"exec_{workflow.workflow_id}_{int(time.time())}",
                workflow_id=workflow.workflow_id,
                status=ExecutionStatus.RUNNING,
            )

            # 3. 构建依赖图
            self.task_dispatcher.build_dependency_graph(workflow.tasks)

            # 4. 根据模式执行
            if mode == "react" or workflow.mode == WorkflowMode.REACT:
                result = self.react_executor.execute_with_target(workflow)
            else:
                result = self._execute_sequential_mode(workflow, result)

            self.logger.info(f"工作流执行完成: {result.status}")
            return result

        except Exception as e:
            self.logger.error(f"工作流执行失败: {e}")
            # 创建失败结果
            workflow_id = workflow.workflow_id if workflow else "unknown"
            result = WorkflowResult(
                execution_id=f"exec_failed_{int(time.time())}",
                workflow_id=workflow_id,
                status=ExecutionStatus.FAILED,
            )
            return result

    def _execute_sequential_mode(
        self, workflow: Workflow, result: WorkflowResult
    ) -> WorkflowResult:
        """顺序执行模式"""
        self.logger.info("使用顺序执行模式")

        # 获取执行顺序
        execution_order = workflow.get_execution_order()

        for level, task_ids in enumerate(execution_order):
            self.logger.info(f"执行第 {level + 1} 层任务: {task_ids}")

            for task_id in task_ids:
                task = workflow.get_task_by_id(task_id)
                if task:
                    task_result = self._execute_single_task(task, result)
                    result.add_task_result(task_result)

                    # 检查是否失败且设置了遇错停止
                    if (
                        not task_result.is_successful()
                        and workflow.global_settings.error_handling.value
                        == "stop_on_error"
                    ):
                        self.logger.error(f"任务 {task_id} 失败，停止执行")
                        result.status = ExecutionStatus.FAILED
                        return result

        result.status = ExecutionStatus.COMPLETED
        return result

    def _execute_react_mode(
        self, workflow: Workflow, result: WorkflowResult
    ) -> WorkflowResult:
        """React执行模式（目标导向）"""
        self.logger.info("使用React执行模式")

        if not workflow.target:
            raise ValueError("React模式需要设置目标")

        max_iterations = workflow.target.max_iterations
        current_iteration = 0

        while current_iteration < max_iterations:
            self.logger.info(f"React迭代 {current_iteration + 1}/{max_iterations}")

            # 执行一轮工作流
            iteration_result = self._execute_sequential_mode(workflow, result)

            # 评估是否达到目标
            target_achieved = self._evaluate_target(workflow.target, iteration_result)

            # 记录迭代结果
            # TODO: 创建ReactIteration对象并添加到result中

            if target_achieved:
                self.logger.info("达到目标，React执行完成")
                result.target_achieved = True
                break

            current_iteration += 1

        result.status = ExecutionStatus.COMPLETED
        return result

    def _execute_single_task(self, task, result: WorkflowResult):
        """执行单个任务"""
        try:
            # 分发任务
            executor_type, execution_params = self.task_dispatcher.dispatch_task(
                task, result.task_results
            )

            # 根据executor_type调用相应的执行器
            if executor_type == ExecutorType.SIMPLE_EXECUTOR:
                task_result = self.simple_executor.execute_task(
                    task, result.task_results
                )
            elif executor_type == ExecutorType.COMPLEX_SOLVER:
                task_result = self.complex_executor.solve_complex_task(
                    task, result.task_results
                )
            else:
                task_result = self._create_placeholder_result(
                    task, f"未知执行器类型: {executor_type}"
                )

            self.logger.info(
                f"任务 {task.task_id} 执行完成，状态: {task_result.status}"
            )

        except Exception as e:
            from datetime import datetime
            from .models.result import TaskResult, ExecutionStatus

            task_result = TaskResult(
                task_id=task.task_id,
                status=ExecutionStatus.FAILED,
                start_time=datetime.now(),
                end_time=datetime.now(),
                error=str(e),
            )
            self.logger.error(f"任务 {task.task_id} 执行失败: {e}")

        finally:
            # 更新分发器状态
            self.task_dispatcher.update_task_status(
                task.task_id, task_result.status, task_result
            )

        return task_result

    def _create_placeholder_result(self, task, message: str):
        """创建占位符结果"""
        from datetime import datetime
        from .models.result import TaskResult, ExecutionStatus

        return TaskResult(
            task_id=task.task_id,
            status=ExecutionStatus.FAILED,
            start_time=datetime.now(),
            end_time=datetime.now(),
            error=message,
        )

    def _evaluate_target(self, target, result: WorkflowResult) -> bool:
        """评估是否达到目标（占位符实现）"""
        # 这是一个占位符实现
        # 实际需要根据target的配置和result中的指标来判断
        return False

    def create_example_workflow(self) -> str:
        """创建示例工作流JSON"""
        workflow = self.workflow_receiver.create_example_workflow()
        return json.dumps(workflow.dict(), ensure_ascii=False, indent=2, default=str)

    def execute_workflow_with_visualization(
        self,
        workflow_data: str,
        mode: str = "sequential",
        generate_visualization: bool = True,
    ) -> Tuple[WorkflowResult, Optional[str]]:
        """
        执行工作流并生成可视化结果

        Args:
            workflow_data: 工作流JSON数据
            mode: 执行模式 (sequential|react)
            generate_visualization: 是否生成可视化

        Returns:
            Tuple[WorkflowResult, Optional[str]]: (执行结果, 可视化报告文件路径)
        """
        # 执行工作流
        result = self.execute_workflow(workflow_data, mode)

        # 生成可视化报告
        report_path = None
        if generate_visualization:
            try:
                # 解析工作流定义
                workflow = self.workflow_receiver.receive_workflow(workflow_data)

                # 生成可视化报告
                report_path = self.visualizer.generate_summary_report(result, workflow)

                if report_path:
                    self.logger.info(f"可视化报告已生成: {report_path}")
                else:
                    self.logger.warning("可视化报告生成失败")

            except Exception as e:
                self.logger.error(f"生成可视化报告时发生错误: {e}")

        return result, report_path

    def visualize_existing_result(
        self, result: WorkflowResult, workflow_data: Optional[str] = None
    ) -> Optional[str]:
        """
        为现有的执行结果生成可视化

        Args:
            result: 工作流执行结果
            workflow_data: 工作流JSON数据（可选）

        Returns:
            Optional[str]: 可视化报告文件路径
        """
        try:
            workflow = None
            if workflow_data:
                workflow = self.workflow_receiver.receive_workflow(workflow_data)

            report_path = self.visualizer.generate_summary_report(result, workflow)

            if report_path:
                self.logger.info(f"可视化报告已生成: {report_path}")
            else:
                self.logger.warning("可视化报告生成失败")

            return report_path

        except Exception as e:
            self.logger.error(f"生成可视化报告时发生错误: {e}")
            return None

    def _setup_logging(self) -> logging.Logger:
        """设置日志"""
        logger = logging.getLogger("executor")

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        logger.setLevel(logging.DEBUG if self.enable_debug else logging.INFO)
        return logger


def main():
    """主函数示例"""
    import time

    # 创建执行引擎
    engine = ExecutorEngine(enable_debug=True)

    # 创建示例工作流
    workflow_json = engine.create_example_workflow()
    print("示例工作流:")
    print(workflow_json)
    print("\n" + "=" * 50 + "\n")

    # 执行工作流
    result = engine.execute_workflow(workflow_json, mode="sequential")

    # 显示结果
    print("执行结果:")
    print(f"执行ID: {result.execution_id}")
    print(f"状态: {result.status}")
    print(f"任务结果数: {len(result.task_results)}")
    print(f"成功率: {result.metrics.success_rate:.2%}")


if __name__ == "__main__":
    main()
