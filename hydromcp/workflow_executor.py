"""
MCP工作流执行器
基于MCP工具的工作流执行器，用于执行生成的工作流计划
"""

import asyncio
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
from .client import MCPToolExecutor

logger = logging.getLogger(__name__)


class MCPWorkflowExecutor:
    """基于MCP的工作流执行器"""
    
    def __init__(self, server_command: Optional[List[str]] = None, enable_debug: bool = False):
        """
        初始化MCP工作流执行器
        
        Args:
            server_command: MCP服务器启动命令，如果为None则使用直接模式
            enable_debug: 是否启用调试模式
        """
        self.mcp_executor = MCPToolExecutor(server_command)
        self.enable_debug = enable_debug
        self.execution_history: List[Dict[str, Any]] = []
        
    async def setup(self) -> bool:
        """
        设置执行器
        
        Returns:
            是否设置成功
        """
        success = await self.mcp_executor.setup()
        if success:
            available_tools = self.mcp_executor.get_available_tools()
            logger.info(f"MCP工作流执行器设置成功，可用工具: {available_tools}")
        return success
    
    async def cleanup(self):
        """清理资源"""
        await self.mcp_executor.cleanup()
    
    async def execute_workflow(self, workflow_plan: WorkflowPlan) -> Dict[str, Any]:
        """
        执行工作流计划
        
        Args:
            workflow_plan: 工作流计划
            
        Returns:
            执行结果
        """
        start_time = time.time()
        
        logger.info(f"开始执行工作流: {workflow_plan.name} (ID: {workflow_plan.plan_id})")
        logger.info(f"工作流包含 {len(workflow_plan.steps)} 个步骤")
        
        execution_results = []
        step_outputs = {}  # 存储每个步骤的输出，供后续步骤使用
        
        try:
            # 按依赖关系排序步骤
            ordered_steps = self._sort_steps_by_dependencies(workflow_plan.steps)
            
            for step in ordered_steps:
                logger.info(f"执行步骤: {step.step_id} - {step.name}")
                
                # 检查依赖是否满足
                if not self._check_dependencies(step, execution_results):
                    error_msg = f"步骤 {step.step_id} 的依赖未满足"
                    logger.error(error_msg)
                    
                    result = ExecutionResult(
                        step_id=step.step_id,
                        status=ExecutionStatus.FAILED,
                        result={"error": error_msg},
                        execution_time=0,
                        timestamp=datetime.now()
                    )
                    execution_results.append(result)
                    continue
                
                # 执行步骤
                step_result = await self._execute_step(step, step_outputs)
                execution_results.append(step_result)
                
                # 如果启用调试模式，记录详细信息
                if self.enable_debug:
                    self._log_step_debug_info(step, step_result)
                
                # 如果步骤失败，根据配置决定是否继续
                if step_result.status == ExecutionStatus.FAILED:
                    logger.error(f"步骤 {step.step_id} 执行失败: {step_result.output}")
                    # 可以根据工作流配置决定是否继续执行
                    # 这里先继续执行剩余步骤
                
                # 保存步骤输出
                step_outputs[step.step_id] = step_result.output
            
            # 计算总体执行结果
            total_time = time.time() - start_time
            success_count = sum(1 for r in execution_results if r.status == ExecutionStatus.SUCCESS)
            failed_count = len(execution_results) - success_count
            
            overall_status = ExecutionStatus.SUCCESS if failed_count == 0 else ExecutionStatus.FAILED
            
            result = {
                "workflow_id": workflow_plan.plan_id,
                "workflow_name": workflow_plan.name,
                "overall_status": overall_status.value,
                "total_execution_time": round(total_time, 2),
                "steps_executed": len(execution_results),
                "steps_successful": success_count,
                "steps_failed": failed_count,
                "step_results": [self._serialize_execution_result(r) for r in execution_results],
                "final_outputs": step_outputs
            }
            
            # 记录执行历史
            self.execution_history.append(result)
            
            logger.info(f"工作流执行完成: {overall_status.value}, 总时间: {total_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"工作流执行失败: {e}")
            import traceback
            error_trace = traceback.format_exc()
            
            return {
                "workflow_id": workflow_plan.plan_id,
                "workflow_name": workflow_plan.name,
                "overall_status": ExecutionStatus.FAILED.value,
                "total_execution_time": round(time.time() - start_time, 2),
                "error": str(e),
                "error_stack": error_trace,
                "steps_executed": len(execution_results),
                "steps_successful": sum(1 for r in execution_results if r.status == ExecutionStatus.SUCCESS),
                "steps_failed": sum(1 for r in execution_results if r.status == ExecutionStatus.FAILED),
                "step_results": [self._serialize_execution_result(r) for r in execution_results]
            }
    
    async def _execute_step(self, step: WorkflowStep, step_outputs: Dict[str, Any]) -> ExecutionResult:
        """
        执行单个步骤
        
        Args:
            step: 工作流步骤
            step_outputs: 之前步骤的输出
            
        Returns:
            执行结果
        """
        start_time = time.time()
        
        try:
            # 检查工具是否可用
            if not self.mcp_executor.is_tool_available(step.tool_name):
                return ExecutionResult(
                    step_id=step.step_id,
                    status=ExecutionStatus.FAILED,
                    output={"error": f"工具 {step.tool_name} 不可用"},
                    execution_time=0,
                    timestamp=datetime.now()
                )
            
            # 处理参数（可能需要从之前步骤的输出中获取）
            processed_parameters = self._process_step_parameters(step.parameters, step_outputs)
            
            # 执行工具
            logger.info(f"调用MCP工具: {step.tool_name}, 参数: {processed_parameters}")
            
            tool_output = await self.mcp_executor.execute_tool(step.tool_name, processed_parameters)
            
            execution_time = time.time() - start_time
            
            # 判断执行状态
            if isinstance(tool_output, dict) and tool_output.get("success", True):
                status = ExecutionStatus.SUCCESS
            else:
                status = ExecutionStatus.FAILED
            
            return ExecutionResult(
                step_id=step.step_id,
                status=status,
                result=tool_output,
                execution_time=round(execution_time, 2),
                timestamp=datetime.now()
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"步骤执行失败: {e}")
            
            import traceback
            error_trace = traceback.format_exc()
            
            return ExecutionResult(
                step_id=step.step_id,
                status=ExecutionStatus.FAILED,
                result={
                    "error": str(e),
                    "error_stack": error_trace
                },
                execution_time=round(execution_time, 2),
                timestamp=datetime.now()
            )
    
    def _sort_steps_by_dependencies(self, steps: List[WorkflowStep]) -> List[WorkflowStep]:
        """
        根据依赖关系排序步骤
        
        Args:
            steps: 工作流步骤列表
            
        Returns:
            排序后的步骤列表
        """
        # 简单的拓扑排序实现
        step_dict = {step.step_id: step for step in steps}
        visited = set()
        result = []
        
        def visit(step_id: str):
            if step_id in visited:
                return
            
            step = step_dict.get(step_id)
            if not step:
                return
            
            # 先访问依赖
            for dep in step.dependencies:
                visit(dep)
            
            visited.add(step_id)
            result.append(step)
        
        # 访问所有步骤
        for step in steps:
            visit(step.step_id)
        
        return result
    
    def _check_dependencies(self, step: WorkflowStep, execution_results: List[ExecutionResult]) -> bool:
        """
        检查步骤依赖是否满足
        
        Args:
            step: 工作流步骤
            execution_results: 已执行的结果列表
            
        Returns:
            依赖是否满足
        """
        executed_step_ids = {result.step_id for result in execution_results}
        
        for dep in step.dependencies:
            if dep not in executed_step_ids:
                return False
            
            # 检查依赖步骤是否成功执行
            dep_result = next((r for r in execution_results if r.step_id == dep), None)
            if not dep_result or dep_result.status != ExecutionStatus.SUCCESS:
                return False
        
        return True
    
    def _process_step_parameters(self, parameters: Dict[str, Any], step_outputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理步骤参数，可能需要从之前步骤的输出中获取值
        
        Args:
            parameters: 原始参数
            step_outputs: 之前步骤的输出
            
        Returns:
            处理后的参数
        """
        processed = parameters.copy()
        
        # 这里可以实现参数引用逻辑，比如 ${step_1.output.result_dir}
        # 暂时返回原始参数
        return processed
    
    def _log_step_debug_info(self, step: WorkflowStep, result: ExecutionResult):
        """记录步骤调试信息"""
        logger.debug(f"步骤调试信息:")
        logger.debug(f"  步骤ID: {step.step_id}")
        logger.debug(f"  工具名称: {step.tool_name}")
        logger.debug(f"  参数: {step.parameters}")
        logger.debug(f"  执行状态: {result.status}")
        logger.debug(f"  执行时间: {result.execution_time}s")
        logger.debug(f"  输出: {result.output}")
    
    def _serialize_execution_result(self, result: ExecutionResult) -> Dict[str, Any]:
        """序列化执行结果"""
        return {
            "step_id": result.step_id,
            "status": result.status.value,
            "output": result.output,
            "execution_time": result.execution_time,
            "timestamp": result.timestamp.isoformat()
        }
    
    def get_execution_history(self) -> List[Dict[str, Any]]:
        """获取执行历史"""
        return self.execution_history.copy()
    
    def get_last_execution_result(self) -> Optional[Dict[str, Any]]:
        """获取最后一次执行结果"""
        return self.execution_history[-1] if self.execution_history else None


# 便利函数
async def execute_workflow_with_mcp(
    workflow_plan: WorkflowPlan,
    server_command: Optional[List[str]] = None,
    enable_debug: bool = False
) -> Dict[str, Any]:
    """
    使用MCP执行工作流
    
    Args:
        workflow_plan: 工作流计划
        server_command: MCP服务器启动命令
        enable_debug: 是否启用调试模式
        
    Returns:
        执行结果
    """
    executor = MCPWorkflowExecutor(server_command, enable_debug)
    
    try:
        # 设置执行器
        if not await executor.setup():
            return {
                "workflow_id": workflow_plan.plan_id,
                "workflow_name": workflow_plan.name,
                "overall_status": ExecutionStatus.FAILED.value,
                "error": "无法设置MCP工作流执行器",
                "step_results": []
            }
        
        # 执行工作流
        return await executor.execute_workflow(workflow_plan)
        
    finally:
        await executor.cleanup()


# 示例使用
async def main():
    """示例：如何使用MCP工作流执行器"""
    import sys
    from pathlib import Path
    
    # 添加项目路径
    repo_path = Path(__file__).parent.parent
    sys.path.append(str(repo_path))
    
    from workflow.workflow_types import WorkflowPlan, WorkflowStep, StepType
    
    logging.basicConfig(level=logging.INFO)
    
    # 创建示例工作流
    steps = [
        WorkflowStep(
            step_id="step_1",
            name="获取模型参数",
            description="获取GR4J模型参数信息",
            step_type=StepType.TOOL_CALL,
            tool_name="get_model_params",
            parameters={"model_name": "gr4j"},
            dependencies=[],
            conditions={},
            retry_count=0,
            timeout=30
        )
    ]
    
    workflow = WorkflowPlan(
        plan_id="test_workflow_001",
        name="测试工作流",
        description="MCP工作流执行器测试",
        steps=steps,
        user_query="获取GR4J模型参数",
        expanded_query="",
        context="测试用例"
    )
    
    # 执行工作流
    result = await execute_workflow_with_mcp(workflow, enable_debug=True)
    print(f"执行结果: {result}")


if __name__ == "__main__":
    asyncio.run(main())
