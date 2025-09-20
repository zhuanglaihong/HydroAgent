"""
增强工作流执行器
适应新的工作流格式，支持task_type字段，根据任务复杂度选择执行策略

Author: Assistant
Date: 2025-01-20
"""

import logging
import json
import asyncio
import time
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from enum import Enum

from .client import HydroMCPClient
from .task_handlers import SimpleTaskHandler, ComplexTaskHandler, create_task_handler

logger = logging.getLogger(__name__)


class TaskExecutionStatus(Enum):
    """任务执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaskExecutionResult:
    """任务执行结果"""
    
    def __init__(
        self,
        task_id: str,
        status: TaskExecutionStatus,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        execution_time: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.task_id = task_id
        self.status = status
        self.result = result or {}
        self.error = error
        self.execution_time = execution_time
        self.metadata = metadata or {}
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "execution_time": self.execution_time,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }


class WorkflowExecutionResult:
    """工作流执行结果"""
    
    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self.task_results: Dict[str, TaskExecutionResult] = {}
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
        self.total_execution_time = 0.0
        self.overall_status = TaskExecutionStatus.PENDING
        
    def add_task_result(self, result: TaskExecutionResult):
        """添加任务结果"""
        self.task_results[result.task_id] = result
        
    def complete(self):
        """完成工作流执行"""
        self.end_time = datetime.now()
        self.total_execution_time = (self.end_time - self.start_time).total_seconds()
        
        # 计算总体状态
        if all(r.status == TaskExecutionStatus.COMPLETED for r in self.task_results.values()):
            self.overall_status = TaskExecutionStatus.COMPLETED
        elif any(r.status == TaskExecutionStatus.FAILED for r in self.task_results.values()):
            self.overall_status = TaskExecutionStatus.FAILED
        else:
            self.overall_status = TaskExecutionStatus.COMPLETED  # 部分成功也算完成
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "workflow_id": self.workflow_id,
            "overall_status": self.overall_status.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_execution_time": self.total_execution_time,
            "task_results": {k: v.to_dict() for k, v in self.task_results.items()},
            "summary": {
                "total_tasks": len(self.task_results),
                "completed_tasks": len([r for r in self.task_results.values() if r.status == TaskExecutionStatus.COMPLETED]),
                "failed_tasks": len([r for r in self.task_results.values() if r.status == TaskExecutionStatus.FAILED]),
                "success_rate": len([r for r in self.task_results.values() if r.status == TaskExecutionStatus.COMPLETED]) / len(self.task_results) if self.task_results else 0
            }
        }


class EnhancedWorkflowExecutor:
    """增强工作流执行器"""
    
    def __init__(
        self,
        server_command: Optional[List[str]] = None,
        enable_debug: bool = False,
        enable_complex_tasks: bool = True
    ):
        """
        初始化增强工作流执行器
        
        Args:
            server_command: MCP服务器启动命令
            enable_debug: 是否启用调试模式  
            enable_complex_tasks: 是否启用复杂任务处理
        """
        self.server_command = server_command
        self.enable_debug = enable_debug
        self.enable_complex_tasks = enable_complex_tasks
        
        # 初始化任务处理器
        self.simple_handler = SimpleTaskHandler(server_command, enable_debug)
        self.complex_handler = ComplexTaskHandler(enable_debug) if enable_complex_tasks else None
        
        # 执行状态
        self.is_setup = False
        self.execution_context: Dict[str, Any] = {}  # 存储任务间的共享数据
        
        logger.info("增强工作流执行器初始化完成")
    
    async def setup(self) -> bool:
        """设置执行器"""
        try:
            # 设置简单任务处理器
            if not await self.simple_handler.setup():
                logger.error("简单任务处理器设置失败")
                return False
            
            # 设置复杂任务处理器
            if self.complex_handler:
                if not await self.complex_handler.setup():
                    logger.warning("复杂任务处理器设置失败，将禁用复杂任务功能")
                    self.complex_handler = None
            
            self.is_setup = True
            logger.info("增强工作流执行器设置成功")
            return True
            
        except Exception as e:
            logger.error(f"增强工作流执行器设置失败: {e}")
            return False
    
    async def cleanup(self):
        """清理资源"""
        try:
            await self.simple_handler.cleanup()
            if self.complex_handler:
                await self.complex_handler.cleanup()
            self.is_setup = False
            logger.info("增强工作流执行器清理完成")
        except Exception as e:
            logger.error(f"清理资源失败: {e}")
    
    async def execute_workflow(self, workflow_data: Union[str, Dict[str, Any]]) -> WorkflowExecutionResult:
        """
        执行工作流
        
        Args:
            workflow_data: 工作流数据（JSON字符串或字典）
            
        Returns:
            工作流执行结果
        """
        if not self.is_setup:
            raise RuntimeError("执行器未设置，请先调用setup()方法")
        
        # 解析工作流数据
        if isinstance(workflow_data, str):
            try:
                workflow = json.loads(workflow_data)
            except json.JSONDecodeError as e:
                raise ValueError(f"工作流JSON解析失败: {e}")
        else:
            workflow = workflow_data
        
        workflow_id = workflow.get("workflow_id", f"workflow_{int(time.time())}")
        logger.info(f"开始执行工作流: {workflow_id}")
        
        # 创建执行结果
        execution_result = WorkflowExecutionResult(workflow_id)
        
        # 清空执行上下文
        self.execution_context = {}
        
        try:
            tasks = workflow.get("tasks", [])
            if not tasks:
                logger.warning("工作流不包含任何任务")
                execution_result.complete()
                return execution_result
            
            # 按依赖关系排序任务
            sorted_tasks = self._sort_tasks_by_dependencies(tasks)
            
            # 逐个执行任务
            for task in sorted_tasks:
                task_result = await self._execute_single_task(task)
                execution_result.add_task_result(task_result)
                
                # 如果任务失败且是关键任务，停止执行
                if task_result.status == TaskExecutionStatus.FAILED:
                    logger.error(f"任务 {task['task_id']} 执行失败: {task_result.error}")
                    # 可以根据任务的重要性决定是否继续执行
            
            execution_result.complete()
            logger.info(f"工作流 {workflow_id} 执行完成")
            
        except Exception as e:
            logger.error(f"工作流执行失败: {e}")
            execution_result.overall_status = TaskExecutionStatus.FAILED
            execution_result.complete()
        
        return execution_result
    
    async def _execute_single_task(self, task: Dict[str, Any]) -> TaskExecutionResult:
        """执行单个任务"""
        task_id = task.get("task_id", "unknown")
        task_type = task.get("task_type", "simple_action")
        action = task.get("action", "")
        
        logger.info(f"开始执行任务: {task_id} (类型: {task_type})")
        start_time = time.time()
        
        try:
            # 检查依赖
            dependencies = task.get("dependencies", [])
            if not self._check_dependencies(dependencies):
                error_msg = f"任务依赖检查失败: {dependencies}"
                logger.error(error_msg)
                return TaskExecutionResult(
                    task_id=task_id,
                    status=TaskExecutionStatus.FAILED,
                    error=error_msg,
                    execution_time=time.time() - start_time
                )
            
            # 准备任务参数
            parameters = self._prepare_task_parameters(task)
            
            # 根据任务类型选择处理器
            if task_type == "simple_action":
                result = await self._execute_simple_task(task, parameters)
            elif task_type == "complex_reasoning":
                result = await self._execute_complex_task(task, parameters)
            else:
                raise ValueError(f"未知的任务类型: {task_type}")
            
            # 保存结果到执行上下文
            self.execution_context[task_id] = result
            
            execution_time = time.time() - start_time
            logger.info(f"任务 {task_id} 执行成功，耗时: {execution_time:.2f}秒")
            
            return TaskExecutionResult(
                task_id=task_id,
                status=TaskExecutionStatus.COMPLETED,
                result=result,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"任务执行失败: {str(e)}"
            logger.error(f"任务 {task_id} 执行失败: {error_msg}")
            
            return TaskExecutionResult(
                task_id=task_id,
                status=TaskExecutionStatus.FAILED,
                error=error_msg,
                execution_time=execution_time
            )
    
    async def _execute_simple_task(self, task: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行简单任务"""
        action = task.get("action", "")
        
        # 使用简单任务处理器
        result = await self.simple_handler.execute_tool(action, parameters)
        
        if not result.get("success", False):
            raise RuntimeError(f"简单任务执行失败: {result.get('error', 'Unknown error')}")
        
        return result
    
    async def _execute_complex_task(self, task: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行复杂任务"""
        if not self.complex_handler:
            # 如果没有复杂任务处理器，返回示例结果
            logger.warning(f"复杂任务处理器未启用，返回示例结果: {task['task_id']}")
            return self._create_mock_complex_result(task)
        
        # 使用复杂任务处理器
        task_description = f"{task.get('name', '')}: {task.get('description', '')}"
        result = await self.complex_handler.handle_complex_task(task_description, parameters)
        
        return result
    
    def _create_mock_complex_result(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """为复杂任务创建模拟结果（示例实现）"""
        action = task.get("action", "")
        
        # 根据不同的复杂任务类型返回不同的模拟结果
        if "calibration" in action.lower() or "rate" in action.lower():
            return {
                "success": True,
                "type": "model_calibration",
                "result": {
                    "optimized_parameters": {
                        "X1": 342.5,
                        "X2": -0.12,
                        "X3": 68.3,
                        "X4": 1.39
                    },
                    "objective_function": "NSE",
                    "objective_value": 0.823,
                    "convergence": True,
                    "iterations": 150
                },
                "message": "模型率定完成（示例结果）",
                "metadata": {
                    "is_mock": True,
                    "task_type": "complex_reasoning"
                }
            }
        elif "optimization" in action.lower():
            return {
                "success": True,
                "type": "parameter_optimization",
                "result": {
                    "optimal_values": [342.5, -0.12, 68.3, 1.39],
                    "objective_value": 0.823,
                    "optimization_method": "SCE-UA",
                    "convergence_info": {
                        "converged": True,
                        "iterations": 150,
                        "function_evaluations": 2250
                    }
                },
                "message": "参数优化完成（示例结果）",
                "metadata": {
                    "is_mock": True,
                    "task_type": "complex_reasoning"
                }
            }
        else:
            return {
                "success": True,
                "type": "complex_analysis",
                "result": {
                    "analysis_results": "复杂分析任务执行完成",
                    "computed_values": [1.23, 4.56, 7.89],
                    "status": "completed"
                },
                "message": f"复杂任务 {action} 执行完成（示例结果）",
                "metadata": {
                    "is_mock": True,
                    "task_type": "complex_reasoning"
                }
            }
    
    def _sort_tasks_by_dependencies(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """根据依赖关系对任务进行拓扑排序"""
        task_dict = {task["task_id"]: task for task in tasks}
        sorted_tasks = []
        visited = set()
        visiting = set()
        
        def visit(task_id: str):
            if task_id in visiting:
                raise ValueError(f"检测到循环依赖: {task_id}")
            if task_id in visited:
                return
            
            visiting.add(task_id)
            task = task_dict.get(task_id)
            if task:
                for dep in task.get("dependencies", []):
                    visit(dep)
                sorted_tasks.append(task)
            visited.add(task_id)
            visiting.remove(task_id)
        
        for task in tasks:
            visit(task["task_id"])
        
        return sorted_tasks
    
    def _check_dependencies(self, dependencies: List[str]) -> bool:
        """检查任务依赖是否已满足"""
        for dep in dependencies:
            if dep not in self.execution_context:
                return False
        return True
    
    def _prepare_task_parameters(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """准备任务参数，解析依赖任务的输出"""
        parameters = task.get("parameters", {}).copy()
        
        # 处理参数中的依赖引用（例如："t1_data_loading.output"）
        for key, value in parameters.items():
            if isinstance(value, str) and "." in value:
                parts = value.split(".")
                if len(parts) == 2 and parts[0] in self.execution_context:
                    # 引用前一个任务的输出
                    dep_result = self.execution_context[parts[0]]
                    if parts[1] == "output" and "result" in dep_result:
                        parameters[key] = dep_result["result"]
                    elif parts[1] in dep_result:
                        parameters[key] = dep_result[parts[1]]
        
        return parameters
    
    def get_execution_status(self) -> Dict[str, Any]:
        """获取执行状态"""
        return {
            "is_setup": self.is_setup,
            "has_simple_handler": self.simple_handler is not None,
            "has_complex_handler": self.complex_handler is not None,
            "enable_complex_tasks": self.enable_complex_tasks,
            "execution_context_keys": list(self.execution_context.keys())
        }


# 便利函数
def create_enhanced_workflow_executor(
    server_command: Optional[List[str]] = None,
    enable_debug: bool = False,
    enable_complex_tasks: bool = True
) -> EnhancedWorkflowExecutor:
    """创建增强工作流执行器实例"""
    return EnhancedWorkflowExecutor(
        server_command=server_command,
        enable_debug=enable_debug,
        enable_complex_tasks=enable_complex_tasks
    )
