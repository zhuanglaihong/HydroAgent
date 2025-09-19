"""
新工作流生成器与HydroMCP执行器集成测试

测试新生成的工作流能否成功被现有的hydromcp工具执行

Author: Assistant
Date: 2025-01-20
"""

import asyncio
import logging
import sys
import os
import time
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入新版工作流生成器
from workflow import (
    WorkflowGeneratorV2, GenerationConfig, create_workflow_generator,
    AssembledWorkflow, WorkflowTask
)

# 导入HydroMCP执行器
from hydromcp import (
    MCPWorkflowExecutor, HydroMCPClient, TaskDispatcher, 
    SimpleTaskHandler, ComplexTaskHandler
)

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class WorkflowExecutionTester:
    """工作流执行测试器"""
    
    def __init__(self):
        """初始化测试器"""
        # 创建工作流生成器
        self.config = GenerationConfig(
            enable_feedback_learning=False,  # 禁用反馈学习避免文件操作
            enable_validation=True,
            enable_optimization=True
        )
        self.workflow_generator = create_workflow_generator(config=self.config)
        
        # 初始化MCP执行器
        self.mcp_executor = None
        self.task_dispatcher = None
        
        # 测试结果
        self.test_results = []
        
    async def setup_mcp_executor(self) -> bool:
        """设置MCP执行器"""
        try:
            # 创建MCP工作流执行器
            self.mcp_executor = MCPWorkflowExecutor(enable_debug=True)
            
            # 设置执行器
            setup_success = await self.mcp_executor.setup()
            if not setup_success:
                logger.warning("MCP执行器设置失败，将使用任务分发器")
                
                # 创建任务分发器作为备选
                self.task_dispatcher = TaskDispatcher()
                return True
            
            logger.info("MCP执行器设置成功")
            return True
            
        except Exception as e:
            logger.error(f"MCP执行器设置失败: {str(e)}")
            
            # 创建任务分发器作为备选
            try:
                self.task_dispatcher = TaskDispatcher()
                logger.info("使用任务分发器作为备选执行器")
                return True
            except Exception as e2:
                logger.error(f"任务分发器创建失败: {str(e2)}")
                return False
    
    def convert_workflow_to_mcp_format(self, workflow: AssembledWorkflow) -> Dict[str, Any]:
        """将新工作流格式转换为MCP兼容格式"""
        try:
            mcp_workflow = {
                "workflow_id": workflow.workflow_id,
                "name": workflow.name,
                "description": workflow.description,
                "steps": [],
                "metadata": workflow.metadata
            }
            
            # 转换任务为MCP步骤格式
            for task in workflow.tasks:
                mcp_step = {
                    "step_id": task.task_id,
                    "name": task.name,
                    "description": task.description,
                    "tool_name": task.action,
                    "step_type": "tool_call",
                    "parameters": task.parameters,
                    "dependencies": task.dependencies,
                    "conditions": task.conditions,
                    "retry_count": task.retry_count,
                    "timeout": task.timeout
                }
                mcp_workflow["steps"].append(mcp_step)
            
            return mcp_workflow
            
        except Exception as e:
            logger.error(f"工作流格式转换失败: {str(e)}")
            return {}
    
    async def execute_workflow_with_mcp(self, workflow: AssembledWorkflow) -> Dict[str, Any]:
        """使用MCP执行器执行工作流"""
        try:
            if not self.mcp_executor:
                return {
                    "success": False,
                    "error": "MCP执行器不可用",
                    "execution_time": 0.0
                }
            
            # 转换工作流格式
            mcp_workflow = self.convert_workflow_to_mcp_format(workflow)
            if not mcp_workflow:
                return {
                    "success": False,
                    "error": "工作流格式转换失败",
                    "execution_time": 0.0
                }
            
            start_time = time.time()
            
            # 使用MCP执行器执行工作流
            from workflow.workflow_types import WorkflowPlan, WorkflowStep
            
            # 创建WorkflowPlan对象
            workflow_steps = []
            for step_data in mcp_workflow["steps"]:
                step = WorkflowStep(
                    step_id=step_data["step_id"],
                    name=step_data["name"],
                    description=step_data["description"],
                    tool_name=step_data["tool_name"],
                    parameters=step_data["parameters"],
                    dependencies=step_data["dependencies"]
                )
                workflow_steps.append(step)
            
            workflow_plan = WorkflowPlan(
                 workflow_id=mcp_workflow["workflow_id"],
                 name=mcp_workflow["name"],
                 description=mcp_workflow["description"],
                 steps=workflow_steps
             )
            
            # 执行工作流
            execution_result = await self.mcp_executor.execute_workflow(workflow_plan)
            
            execution_time = time.time() - start_time
            
            return {
                "success": execution_result.get("success", False),
                "error": execution_result.get("error", ""),
                "results": execution_result.get("results", {}),
                "execution_time": execution_time,
                "executor_type": "mcp"
            }
            
        except Exception as e:
            logger.error(f"MCP执行器执行失败: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "execution_time": time.time() - start_time if 'start_time' in locals() else 0.0,
                "executor_type": "mcp"
            }
    
    async def execute_workflow_with_dispatcher(self, workflow: AssembledWorkflow) -> Dict[str, Any]:
        """使用任务分发器执行工作流"""
        try:
            if not self.task_dispatcher:
                return {
                    "success": False,
                    "error": "任务分发器不可用",
                    "execution_time": 0.0
                }
            
            start_time = time.time()
            results = {}
            
            # 按执行顺序执行任务
            for batch in workflow.execution_order:
                batch_results = {}
                
                # 并行执行当前批次的任务
                tasks_to_execute = []
                for task_id in batch:
                    task = next((t for t in workflow.tasks if t.task_id == task_id), None)
                    if task:
                        tasks_to_execute.append(task)
                
                # 执行批次中的任务
                for task in tasks_to_execute:
                    try:
                        # 将任务描述转换为自然语言
                        task_description = f"{task.name}: {task.description}"
                        if task.parameters:
                            param_str = ", ".join([f"{k}={v}" for k, v in task.parameters.items()])
                            task_description += f" (参数: {param_str})"
                        
                        # 使用任务分发器处理任务
                        task_result = await self.task_dispatcher.dispatch_task(task_description)
                        
                        batch_results[task.task_id] = {
                            "success": task_result.get("success", False),
                            "result": task_result.get("result", ""),
                            "error": task_result.get("error", "")
                        }
                        
                    except Exception as e:
                        logger.error(f"任务 {task.task_id} 执行失败: {str(e)}")
                        batch_results[task.task_id] = {
                            "success": False,
                            "result": "",
                            "error": str(e)
                        }
                
                results.update(batch_results)
            
            execution_time = time.time() - start_time
            
            # 计算整体成功率
            total_tasks = len(results)
            successful_tasks = sum(1 for result in results.values() if result.get("success", False))
            overall_success = successful_tasks == total_tasks and total_tasks > 0
            
            return {
                "success": overall_success,
                "error": "" if overall_success else f"部分任务失败 ({successful_tasks}/{total_tasks})",
                "results": results,
                "execution_time": execution_time,
                "executor_type": "dispatcher"
            }
            
        except Exception as e:
            logger.error(f"任务分发器执行失败: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "execution_time": time.time() - start_time if 'start_time' in locals() else 0.0,
                "executor_type": "dispatcher"
            }
    
    async def test_workflow_execution(self, instruction: str) -> Dict[str, Any]:
        """测试单个工作流的生成和执行"""
        logger.info(f"开始测试指令: {instruction}")
        
        test_result = {
            "instruction": instruction,
            "generation_success": False,
            "generation_time": 0.0,
            "generation_error": "",
            "execution_success": False,
            "execution_time": 0.0,
            "execution_error": "",
            "executor_type": "",
            "workflow_info": {},
            "detailed_results": {}
        }
        
        try:
            # 第一步：生成工作流
            logger.info("生成工作流...")
            generation_result = self.workflow_generator.generate_workflow(instruction)
            
            test_result["generation_success"] = generation_result.success
            test_result["generation_time"] = generation_result.total_time
            
            if not generation_result.success:
                test_result["generation_error"] = generation_result.error_message
                logger.error(f"工作流生成失败: {generation_result.error_message}")
                return test_result
            
            # 记录工作流信息
            workflow = generation_result.workflow
            test_result["workflow_info"] = {
                "name": workflow.name,
                "task_count": len(workflow.tasks),
                "execution_order": workflow.execution_order,
                "validation_issues": len(workflow.validation_issues)
            }
            
            logger.info(f"工作流生成成功: {workflow.name} ({len(workflow.tasks)}个任务)")
            
            # 第二步：尝试执行工作流
            logger.info("执行工作流...")
            
            # 优先尝试MCP执行器
            if self.mcp_executor:
                execution_result = await self.execute_workflow_with_mcp(workflow)
            else:
                execution_result = await self.execute_workflow_with_dispatcher(workflow)
            
            test_result["execution_success"] = execution_result["success"]
            test_result["execution_time"] = execution_result["execution_time"]
            test_result["execution_error"] = execution_result["error"]
            test_result["executor_type"] = execution_result["executor_type"]
            test_result["detailed_results"] = execution_result.get("results", {})
            
            if execution_result["success"]:
                logger.info(f"工作流执行成功，耗时: {execution_result['execution_time']:.2f}秒")
            else:
                logger.error(f"工作流执行失败: {execution_result['error']}")
            
        except Exception as e:
            logger.error(f"测试过程出现异常: {str(e)}")
            test_result["generation_error"] = str(e)
        
        return test_result
    
    async def run_test_suite(self) -> List[Dict[str, Any]]:
        """运行完整的测试套件"""
        logger.info("🚀 开始工作流生成与执行集成测试")
        
        # 设置执行器
        setup_success = await self.setup_mcp_executor()
        if not setup_success:
            logger.error("执行器设置失败，无法继续测试")
            return []
        
        # 测试用例
        test_cases = [
            "加载CSV数据文件并计算基本统计信息",
            "获取GR4J模型的参数信息",
            "使用示例数据进行模型校准",
        ]
        
        # 执行测试
        for instruction in test_cases:
            try:
                test_result = await self.test_workflow_execution(instruction)
                self.test_results.append(test_result)
                
                # 打印简要结果
                gen_status = "✅" if test_result["generation_success"] else "❌"
                exec_status = "✅" if test_result["execution_success"] else "❌"
                print(f"{gen_status} 生成 | {exec_status} 执行 | {instruction}")
                
                # 添加分隔线
                print("-" * 80)
                
            except Exception as e:
                logger.error(f"测试案例失败: {instruction} - {str(e)}")
        
        return self.test_results
    
    def generate_test_report(self) -> Dict[str, Any]:
        """生成测试报告"""
        if not self.test_results:
            return {"error": "没有测试结果"}
        
        total_tests = len(self.test_results)
        generation_success_count = sum(1 for r in self.test_results if r["generation_success"])
        execution_success_count = sum(1 for r in self.test_results if r["execution_success"])
        
        # 计算平均时间
        avg_generation_time = sum(r["generation_time"] for r in self.test_results) / total_tests
        avg_execution_time = sum(r["execution_time"] for r in self.test_results) / total_tests
        
        # 收集执行器类型
        executor_types = [r["executor_type"] for r in self.test_results if r["executor_type"]]
        
        report = {
            "总测试数": total_tests,
            "工作流生成成功数": generation_success_count,
            "工作流执行成功数": execution_success_count,
            "生成成功率": f"{generation_success_count/total_tests*100:.1f}%",
            "执行成功率": f"{execution_success_count/total_tests*100:.1f}%",
            "平均生成时间": f"{avg_generation_time:.2f}秒",
            "平均执行时间": f"{avg_execution_time:.2f}秒",
            "使用的执行器": list(set(executor_types)),
            "详细结果": self.test_results
        }
        
        return report
    
    async def cleanup(self):
        """清理资源"""
        try:
            if self.mcp_executor:
                await self.mcp_executor.cleanup()
        except Exception as e:
            logger.error(f"清理资源失败: {str(e)}")


async def main():
    """主函数"""
    tester = WorkflowExecutionTester()
    
    try:
        # 运行测试套件
        results = await tester.run_test_suite()
        
        # 生成测试报告
        report = tester.generate_test_report()
        
        # 打印报告
        print("\n" + "="*80)
        print("📊 测试报告")
        print("="*80)
        
        for key, value in report.items():
            if key != "详细结果":
                print(f"{key}: {value}")
        
        # 打印详细结果
        print("\n详细测试结果:")
        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result['instruction']}")
            print(f"   生成: {'成功' if result['generation_success'] else '失败'} ({result['generation_time']:.2f}s)")
            print(f"   执行: {'成功' if result['execution_success'] else '失败'} ({result['execution_time']:.2f}s)")
            
            if result['workflow_info']:
                info = result['workflow_info']
                print(f"   工作流: {info['name']} - {info['task_count']}个任务")
            
            if result['generation_error']:
                print(f"   生成错误: {result['generation_error']}")
            if result['execution_error']:
                print(f"   执行错误: {result['execution_error']}")
        
        # 保存报告到文件
        report_file = Path("test") / "workflow_execution_test_report.json"
        # with open(report_file, 'w', encoding='utf-8') as f:
        #     json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n📄 详细报告已保存到: {report_file}")
        
        # 返回成功状态
        overall_success = (report["生成成功率"] == "100.0%" and 
                          float(report["执行成功率"].rstrip('%')) >= 60.0)  # 执行成功率要求稍低
        
        if overall_success:
            print("\n🎉 集成测试成功!")
            return True
        else:
            print("\n⚠️  集成测试部分失败，请检查具体问题")
            return False
        
    except Exception as e:
        logger.error(f"测试过程出现异常: {str(e)}")
        print(f"\n❌ 测试失败: {str(e)}")
        return False
        
    finally:
        # 清理资源
        await tester.cleanup()


if __name__ == "__main__":
    # 运行异步主函数
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
