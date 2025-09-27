"""
Author: zhuanglaihong
Date: 2024-09-26 16:35:00
LastEditTime: 2024-09-26 16:35:00
LastEditors: zhuanglaihong
Description: 简单任务执行器 - 处理简单类型的任务
FilePath: \HydroAgent\executor\core\simple_executor.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from ..models.task import Task, TaskType
from ..models.result import TaskResult, ExecutionStatus
from ..tools.registry import HydroToolRegistry
from ..tools import GetModelParamsTool, PrepareDataTool, CalibrateModelTool, EvaluateModelTool


class SimpleTaskExecutor:
    """简单任务执行器"""

    def __init__(self, enable_debug: bool = False):
        """
        初始化简单任务执行器

        Args:
            enable_debug: 是否启用调试模式
        """
        self.enable_debug = enable_debug
        self.logger = logging.getLogger(__name__)

        # 初始化工具注册表
        self.tool_registry = HydroToolRegistry()

        # 注册水文工具
        self._register_hydro_tools()

        self.logger.info("简单任务执行器初始化完成")

    def execute_task(self, task: Task, context: Dict[str, Any] = None) -> TaskResult:
        """
        执行简单任务

        Args:
            task: 要执行的任务
            context: 执行上下文

        Returns:
            TaskResult: 执行结果
        """
        if context is None:
            context = {}

        # 验证任务类型
        if task.type != TaskType.SIMPLE:
            return self._create_error_result(
                task.task_id,
                f"任务类型错误，期望 {TaskType.SIMPLE}，实际 {task.type}"
            )

        # 验证工具名称
        if not task.tool_name:
            return self._create_error_result(
                task.task_id,
                "简单任务必须指定工具名称"
            )

        try:
            # 解析参数
            resolved_params = task.resolve_parameters(context)
            if self.enable_debug:
                self.logger.debug(f"任务 {task.task_id} 解析参数: {resolved_params}")

            # 创建任务结果
            task_result = TaskResult(
                task_id=task.task_id,
                status=ExecutionStatus.RUNNING,
                start_time=datetime.now()
            )

            # 执行工具
            tool_result = self.tool_registry.call_tool(task.tool_name, resolved_params)

            # 更新任务结果
            if tool_result.success:
                task_result.status = ExecutionStatus.COMPLETED
                task_result.outputs = tool_result.output
                task_result.metrics.update(tool_result.metadata)

                # 验证成功标准
                if self._validate_success_criteria(task, tool_result.output):
                    self.logger.info(f"任务 {task.task_id} 执行成功")
                else:
                    task_result.status = ExecutionStatus.FAILED
                    task_result.error = "未满足成功标准"
                    self.logger.warning(f"任务 {task.task_id} 未满足成功标准")
            else:
                task_result.status = ExecutionStatus.FAILED
                task_result.error = tool_result.error
                self.logger.error(f"任务 {task.task_id} 执行失败: {tool_result.error}")

            # 设置结束时间和执行时长
            task_result.end_time = datetime.now()
            task_result.calculate_duration()

            # 添加执行日志
            task_result.add_log(f"使用工具 {task.tool_name} 执行任务")
            if tool_result.execution_time:
                task_result.add_log(f"工具执行时间: {tool_result.execution_time:.2f}秒")

            return task_result

        except Exception as e:
            error_msg = f"任务 {task.task_id} 执行异常: {str(e)}"
            self.logger.error(error_msg)
            return self._create_error_result(task.task_id, error_msg)

    def validate_task(self, task: Task) -> bool:
        """
        验证任务是否可以执行

        Args:
            task: 要验证的任务

        Returns:
            bool: 是否可以执行
        """
        try:
            # 检查任务类型
            if task.type != TaskType.SIMPLE:
                self.logger.error(f"任务类型错误: {task.type}")
                return False

            # 检查工具名称
            if not task.tool_name:
                self.logger.error("缺少工具名称")
                return False

            # 检查工具是否存在
            tool = self.tool_registry.get_tool(task.tool_name)
            if not tool:
                self.logger.error(f"工具不存在: {task.tool_name}")
                return False

            # 验证参数格式
            try:
                # 这里只是基础验证，实际参数解析在执行时进行
                if not isinstance(task.parameters, dict):
                    self.logger.error("任务参数必须是字典格式")
                    return False
            except Exception as e:
                self.logger.error(f"参数验证失败: {e}")
                return False

            return True

        except Exception as e:
            self.logger.error(f"任务验证失败: {e}")
            return False

    def get_available_tools(self) -> Dict[str, Any]:
        """
        获取可用工具列表

        Returns:
            Dict[str, Any]: 工具信息
        """
        return self.tool_registry.get_registry_stats()

    def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        获取工具参数模式

        Args:
            tool_name: 工具名称

        Returns:
            Optional[Dict[str, Any]]: 参数模式，如果工具不存在返回None
        """
        tool_info = self.tool_registry.get_tool_info(tool_name)
        if tool_info:
            return tool_info.parameter_schema
        return None

    def _register_hydro_tools(self):
        """注册水文工具"""
        try:
            # 注册获取模型参数工具
            get_params_tool = GetModelParamsTool()
            self.tool_registry.register_tool(get_params_tool, category="model_info")

            # 注册数据准备工具
            prepare_data_tool = PrepareDataTool()
            self.tool_registry.register_tool(prepare_data_tool, category="data_processing")

            # 注册模型率定工具
            calibrate_tool = CalibrateModelTool()
            self.tool_registry.register_tool(calibrate_tool, category="modeling")

            # 注册模型评估工具
            evaluate_tool = EvaluateModelTool()
            self.tool_registry.register_tool(evaluate_tool, category="evaluation")

            self.logger.info("水文工具注册完成")

        except Exception as e:
            self.logger.error(f"注册水文工具失败: {e}")

    def _validate_success_criteria(self, task: Task, output: Dict[str, Any]) -> bool:
        """
        验证成功标准

        Args:
            task: 任务对象
            output: 工具输出

        Returns:
            bool: 是否满足成功标准
        """
        try:
            criteria = task.success_criteria

            # 检查期望输出
            for expected_output in criteria.expected_outputs:
                if expected_output not in output:
                    self.logger.warning(f"缺少期望输出: {expected_output}")
                    return False

            # 检查性能阈值
            for metric, threshold in criteria.performance_thresholds.items():
                if metric in output:
                    value = output[metric]
                    if isinstance(value, (int, float)) and value < threshold:
                        self.logger.warning(f"性能指标 {metric}={value} 低于阈值 {threshold}")
                        return False

            # TODO: 实现验证规则检查
            # 目前简化处理，只要有期望输出就认为成功

            return True

        except Exception as e:
            self.logger.error(f"验证成功标准失败: {e}")
            return False

    def _create_error_result(self, task_id: str, error_msg: str) -> TaskResult:
        """创建错误结果"""
        task_result = TaskResult(
            task_id=task_id,
            status=ExecutionStatus.FAILED,
            start_time=datetime.now(),
            end_time=datetime.now(),
            error=error_msg
        )
        task_result.calculate_duration()
        return task_result