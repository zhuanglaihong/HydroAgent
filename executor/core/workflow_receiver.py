"""
工作流接收器 - 接收和解析工作流定义
"""

import json
import logging
from typing import Dict, Any, Union, List
from pathlib import Path

from ..models.workflow import Workflow
from ..models.task import Task


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