"""
Author: zhuanglaihong
Date: 2024-09-26 16:40:00
LastEditTime: 2024-09-26 16:40:00
LastEditors: zhuanglaihong
Description: 工作流接收器 - 接收和解析工作流定义
FilePath: \HydroAgent\executor\core\workflow_receiver.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import json
import logging
import time
import sys
from typing import Dict, Any, Union, List
from pathlib import Path

from ..models.workflow import Workflow
from ..models.task import Task

# 添加项目根目录到路径以便导入utils模块
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.filepath import process_workflow_paths


class ValidationError(Exception):
    """工作流验证错误"""
    pass


class WorkflowReceiver:
    """工作流接收和解析器"""

    def __init__(self, enable_debug: bool = False):
        """
        初始化工作流接收器

        Args:
            enable_debug: 是否启用调试模式
        """
        self.enable_debug = enable_debug
        self.logger = logging.getLogger(__name__)

        self.logger.info("工作流接收器初始化完成")

    def receive_workflow(self, workflow_data: Union[str, Dict, Path]) -> Workflow:
        """
        接收并解析工作流

        Args:
            workflow_data: 工作流数据，可以是JSON字符串、字典或文件路径

        Returns:
            Workflow: 解析后的工作流对象

        Raises:
            ValidationError: 工作流验证失败
        """
        try:
            # 解析输入数据
            if isinstance(workflow_data, (str, Path)):
                if Path(workflow_data).exists():
                    # 从文件读取
                    with open(workflow_data, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    self.logger.info(f"从文件加载工作流: {workflow_data}")
                else:
                    # 解析JSON字符串
                    data = json.loads(workflow_data)
                    self.logger.info("从JSON字符串解析工作流")
            elif isinstance(workflow_data, dict):
                data = workflow_data
                self.logger.info("从字典解析工作流")
            else:
                raise ValidationError(f"不支持的工作流数据类型: {type(workflow_data)}")

            # 处理工作流中的路径参数（暂时禁用以避免正则表达式问题）
            # data = process_workflow_paths(data)

            # 处理字段映射：execution_mode -> mode
            if 'execution_mode' in data and 'mode' not in data:
                data['mode'] = data.pop('execution_mode')

            # 处理字段映射：targets -> target (取第一个目标)
            if 'targets' in data and 'target' not in data:
                targets = data.pop('targets')
                if targets and len(targets) > 0:
                    data['target'] = targets[0]

            # 创建工作流对象
            workflow = Workflow(**data)

            # 验证工作流
            self.validate_workflow(workflow)

            # 预处理工作流
            workflow = self.preprocess_workflow(workflow)

            if self.enable_debug:
                self.logger.debug(f"成功解析工作流: {workflow.workflow_id}")

            return workflow

        except json.JSONDecodeError as e:
            raise ValidationError(f"JSON解析错误: {e}")
        except Exception as e:
            raise ValidationError(f"工作流解析失败: {e}")

    def validate_workflow(self, workflow: Workflow) -> bool:
        """
        验证工作流的完整性和正确性

        Args:
            workflow: 待验证的工作流

        Returns:
            bool: 验证是否通过

        Raises:
            ValidationError: 验证失败
        """
        try:
            # 1. 基础验证（Pydantic已处理）

            # 2. 验证任务依赖关系
            workflow.validate_dependencies()

            # 3. 验证React模式配置
            if workflow.mode.value == "react":
                if not workflow.target:
                    raise ValidationError("React模式必须设置目标")

                if workflow.target.type.value == "performance_goal":
                    if not workflow.target.metric or workflow.target.threshold is None:
                        raise ValidationError("性能目标必须指定指标和阈值")

            # 4. 验证任务工具引用
            self._validate_task_tools(workflow.tasks)

            # 5. 验证参数引用
            self._validate_parameter_references(workflow.tasks)

            self.logger.info(f"工作流验证通过: {workflow.workflow_id}")
            return True

        except Exception as e:
            raise ValidationError(f"工作流验证失败: {e}")

    def preprocess_workflow(self, workflow: Workflow) -> Workflow:
        """
        预处理工作流，优化执行计划

        Args:
            workflow: 原始工作流

        Returns:
            Workflow: 预处理后的工作流
        """
        # 1. 生成执行顺序
        execution_order = workflow.get_execution_order()
        if self.enable_debug:
            self.logger.debug(f"执行顺序: {execution_order}")

        # 2. 为任务添加执行层级信息
        for level, task_ids in enumerate(execution_order):
            for task_id in task_ids:
                task = workflow.get_task_by_id(task_id)
                if task:
                    # 可以在这里添加执行层级信息到任务的debug_info中
                    pass

        # 3. 验证资源需求
        self._validate_resource_requirements(workflow)

        # 4. 优化任务参数
        self._optimize_task_parameters(workflow)

        return workflow

    def convert_builder_to_executor_format(self, builder_workflow: Union[str, Dict]) -> Dict[str, Any]:
        """
        将构建器工作流格式转换为执行器可接受的格式

        Args:
            builder_workflow: 构建器生成的工作流格式（字符串或字典）

        Returns:
            dict: 执行器可接受的工作流格式
        """
        # 如果输入是字符串，解析为字典
        if isinstance(builder_workflow, str):
            builder_workflow = json.loads(builder_workflow)

        # 检查工作流特征以确定执行模式和任务类型
        builder_tasks = builder_workflow.get("tasks", [])

        # 检查是否有复杂任务或模型率定
        has_complex_tasks = any(
            task.get("task_type") in ["complex_reasoning", "complex"] or
            task.get("action") == "calibrate_model"
            for task in builder_tasks
        )

        has_calibration = any(
            task.get("action") == "calibrate_model"
            for task in builder_tasks
        )

        # 检查构建器推荐的执行模式
        builder_execution_mode = builder_workflow.get("execution_mode", "sequential")

        # 确定执行模式
        if builder_execution_mode == "react" or (has_complex_tasks and has_calibration):
            execution_mode = "react"
            error_handling = "stop_on_error"
            timeout = 600
        else:
            execution_mode = "sequential"
            error_handling = "continue_on_error"
            timeout = 300

        # 基本映射
        executor_workflow = {
            "workflow_id": builder_workflow.get("workflow_id", f"workflow_{int(time.time())}"),
            "name": builder_workflow.get("name", "Generated Workflow"),
            "description": builder_workflow.get("description", ""),
            "mode": execution_mode,
            "global_settings": {
                "error_handling": error_handling,
                "timeout": timeout
            },
            "tasks": []
        }

        # 如果是React模式且有模型率定，添加目标配置
        if execution_mode == "react" and has_calibration:
            executor_workflow["target"] = {
                "type": "performance_goal",
                "metric": "nse",
                "threshold": 0.6,
                "comparison": ">=",
                "max_iterations": 3,
                "description": "模型率定目标NSE >= 0.6"
            }

        # 转换任务格式
        builder_tasks = builder_workflow.get("tasks", [])

        for i, task in enumerate(builder_tasks):
            # 确定任务类型 - 根据构建器的task_type或action来判断
            task_type_raw = task.get("task_type", "simple")
            action = task.get("action", "")

            # 如果是复杂推理类型或明确标记为复杂任务，设为complex
            if (task_type_raw in ["complex_reasoning", "complex"] or
                (has_complex_tasks and action == "calibrate_model")):
                task_type = "complex"
            else:
                task_type = "simple"

            # 获取基本参数
            base_parameters = task.get("parameters", {}).copy()

            executor_task = {
                "task_id": task.get("task_id", f"task_{i+1}"),
                "name": task.get("name", f"Task {i+1}"),
                "type": task_type,
                "parameters": base_parameters,
                "dependencies": task.get("dependencies", []),
                "timeout": task.get("timeout", 60),
                "retry_count": task.get("retry_attempts", 0)
            }

            # 根据任务类型设置不同字段
            if task_type == "simple":
                # 简单任务需要tool_name字段
                action = task.get("action", "unknown")
                tool_mapping = {
                    "get_model_params": "get_model_params",
                    "prepare_data": "prepare_data",
                    "calibrate_model": "calibrate_model",
                    "evaluate_model": "evaluate_model",
                    "率定水文模型": "calibrate_model",
                    "评估水文模型": "evaluate_model"
                }
                executor_task["tool_name"] = tool_mapping.get(action, action)

                # 根据工具类型设置特定的参数依赖关系
                task_id = task.get("task_id")
                dependencies = task.get("dependencies", [])

                # 为依赖任务设置参数引用
                if action == "calibrate_model" and dependencies:
                    # calibrate_model需要从prepare_data任务获取data_dir
                    prep_task_id = dependencies[0] if dependencies else None
                    if prep_task_id:
                        # 添加必需的参数引用
                        executor_task["parameters"]["data_dir"] = f"${{{prep_task_id}.outputs.data_dir}}"
                        # 添加默认的basin_ids（从数据目录推断）
                        if "basin_ids" not in executor_task["parameters"]:
                            executor_task["parameters"]["basin_ids"] = ["11532500"]  # 默认使用CAMELS basin ID
                elif action == "evaluate_model" and dependencies:
                    # evaluate_model需要从calibrate_model获取结果目录
                    calib_task_id = dependencies[0] if dependencies else None
                    if calib_task_id:
                        executor_task["parameters"]["result_dir"] = f"${{{calib_task_id}.outputs.result_dir}}"
                elif action == "get_model_params":
                    # get_model_params工具只需要model_name参数，使用基础参数即可
                    # 确保有model_name参数
                    if "model_name" not in executor_task["parameters"]:
                        # 从原始参数的model字段提取
                        model_info = base_parameters.get("model", "GR4J")
                        if isinstance(model_info, dict):
                            executor_task["parameters"]["model_name"] = model_info.get("name", "GR4J")
                        else:
                            executor_task["parameters"]["model_name"] = str(model_info)

            else:
                # 复杂任务需要description和knowledge_query字段
                executor_task["description"] = task.get("description", f"复杂任务: {action}")
                executor_task["knowledge_query"] = action

                # 为复杂任务添加额外的超时时间和重试配置
                executor_task["timeout"] = max(executor_task["timeout"], 120)
                executor_task["retry_count"] = max(executor_task["retry_count"], 2)

            executor_workflow["tasks"].append(executor_task)

        # 处理工作流中的路径参数
        executor_workflow = process_workflow_paths(executor_workflow)

        if self.enable_debug:
            self.logger.debug(f"构建器工作流已转换为执行器格式: {executor_workflow['workflow_id']}")

        return executor_workflow

    def receive_builder_workflow(self, builder_workflow: Union[str, Dict]) -> Workflow:
        """
        接收构建器格式的工作流并转换为执行器工作流对象

        Args:
            builder_workflow: 构建器生成的工作流格式

        Returns:
            Workflow: 转换后的工作流对象

        Raises:
            ValidationError: 工作流转换或验证失败
        """
        try:
            # 转换格式
            executor_format = self.convert_builder_to_executor_format(builder_workflow)

            # 接收转换后的工作流
            return self.receive_workflow(executor_format)

        except Exception as e:
            raise ValidationError(f"构建器工作流转换失败: {e}")

    def save_workflow(self, workflow: Workflow, file_path: Union[str, Path]) -> bool:
        """
        保存工作流到文件

        Args:
            workflow: 要保存的工作流
            file_path: 文件路径

        Returns:
            bool: 是否成功保存
        """
        try:
            # 转换为字典
            workflow_dict = workflow.dict()

            # 保存到文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(workflow_dict, f, ensure_ascii=False, indent=2, default=str)

            self.logger.info(f"工作流已保存到: {file_path}")
            return True

        except Exception as e:
            self.logger.error(f"保存工作流失败: {e}")
            return False

    def create_example_workflow(self) -> Workflow:
        """
        创建示例工作流

        Returns:
            Workflow: 示例工作流
        """
        example_data = {
            "workflow_id": "example_gr4j_workflow",
            "name": "GR4J模型率定示例",
            "description": "完整的GR4J模型率定和评估工作流示例",
            "mode": "react",
            "tasks": [
                {
                    "task_id": "task_001",
                    "name": "数据准备",
                    "type": "simple",
                    "priority": 2,
                    "tool_name": "prepare_data",
                    "parameters": {
                        "data_dir": "data/camels_11532500",
                        "target_data_scale": "D"
                    },
                    "dependencies": [],
                    "success_criteria": {
                        "expected_outputs": ["processed_data_path"],
                        "validation_rules": ["file_exists", "data_format_valid"]
                    }
                },
                {
                    "task_id": "task_002",
                    "name": "模型率定",
                    "type": "simple",
                    "priority": 3,
                    "tool_name": "calibrate_model",
                    "parameters": {
                        "model_name": "gr4j",
                        "data_dir": "${task_001.outputs.processed_data_path}",
                        "calibrate_period": ["2013-01-01", "2018-12-31"]
                    },
                    "dependencies": ["task_001"],
                    "success_criteria": {
                        "expected_outputs": ["calibration_results", "model_parameters"],
                        "validation_rules": ["nse_above_threshold"]
                    }
                },
                {
                    "task_id": "task_003",
                    "name": "模型评估",
                    "type": "simple",
                    "priority": 2,
                    "tool_name": "evaluate_model",
                    "parameters": {
                        "result_dir": "${task_002.outputs.calibration_results}"
                    },
                    "dependencies": ["task_002"],
                    "success_criteria": {
                        "expected_outputs": ["evaluation_metrics"],
                        "validation_rules": ["metrics_calculated"]
                    }
                }
            ],
            "target": {
                "type": "performance_goal",
                "metric": "NSE",
                "threshold": 0.7,
                "comparison": ">=",
                "max_iterations": 3,
                "description": "NSE指标需要达到0.7以上"
            },
            "global_settings": {
                "error_handling": "continue_on_error",
                "logging_level": "INFO",
                "timeout": 3600,
                "checkpoint_enabled": True
            }
        }

        return Workflow(**example_data)

    def _validate_task_tools(self, tasks: List[Task]):
        """验证任务工具引用"""
        # 这里可以添加工具存在性验证
        # 例如检查tool_name是否在注册的工具列表中
        known_tools = {
            "prepare_data", "calibrate_model", "evaluate_model", "get_model_params"
        }

        for task in tasks:
            if task.type.value == "simple" and task.tool_name:
                if task.tool_name not in known_tools:
                    self.logger.warning(f"未知工具: {task.tool_name} in task {task.task_id}")

    def _validate_parameter_references(self, tasks: List[Task]):
        """验证参数引用的正确性"""
        task_ids = {task.task_id for task in tasks}

        for task in tasks:
            for key, value in task.parameters.items():
                if isinstance(value, str) and value.startswith("${"):
                    # 解析引用路径
                    ref_path = value[2:-1]  # 移除 ${ 和 }
                    parts = ref_path.split('.')

                    if len(parts) >= 1:
                        referenced_task = parts[0]
                        if referenced_task not in task_ids:
                            raise ValidationError(f"任务 {task.task_id} 引用了不存在的任务: {referenced_task}")

    def _validate_resource_requirements(self, workflow: Workflow):
        """验证资源需求"""
        # 这里可以添加资源需求验证逻辑
        # 例如检查系统是否有足够的资源来执行工作流
        pass

    def _optimize_task_parameters(self, workflow: Workflow):
        """优化任务参数"""
        # 这里可以添加参数优化逻辑
        # 例如根据系统配置调整默认参数
        pass