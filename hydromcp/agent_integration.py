"""
Agent集成模块
将MCP工具集成到Agent中，让Ollama等LLM能够使用MCP工具
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate

from .client import HydroMCPClient
from .workflow_executor import MCPWorkflowExecutor
from .task_dispatcher import TaskDispatcher, TaskComplexity
from .task_handlers import SimpleTaskHandler, ComplexTaskHandler, ManualReviewHandler, create_task_handler
from workflow.orchestrator import WorkflowOrchestrator
from workflow.workflow_types import WorkflowPlan

logger = logging.getLogger(__name__)


class MCPAgent:
    """集成MCP工具的智能Agent"""
    
    def __init__(
        self, 
        llm_model: str = "granite3-dense:8b",
        server_command: Optional[List[str]] = None,
        enable_workflow: bool = True,
        enable_debug: bool = False
    ):
        """
        初始化MCP Agent
        
        Args:
            llm_model: Ollama模型名称
            server_command: MCP服务器启动命令
            enable_workflow: 是否启用工作流功能
            enable_debug: 是否启用调试模式
        """
        self.llm_model = llm_model
        self.enable_workflow = enable_workflow
        self.enable_debug = enable_debug
        self.server_command = server_command
        
        # 初始化LLM
        self.llm = ChatOllama(
            model=llm_model,
            temperature=0.1,
            format="json"  # 确保输出JSON格式
        )
        
        # 初始化MCP客户端
        self.mcp_client = HydroMCPClient(server_command)
        self.available_tools = []
        
        # 初始化任务分发器
        self.task_dispatcher = TaskDispatcher(self.llm)
        
        # 初始化任务处理器
        self.simple_task_handler = None
        self.complex_task_handler = None
        
        # 初始化工作流组件（如果启用）
        if enable_workflow:
            self.workflow_orchestrator = WorkflowOrchestrator(
                llm=self.llm,
                tools=[],  # MCP工具将通过不同方式管理
                enable_debug=enable_debug
            )
            self.workflow_executor = MCPWorkflowExecutor(server_command, enable_debug)
        else:
            self.workflow_orchestrator = None
            self.workflow_executor = None
        
        self.conversation_history = []
        
    async def setup(self) -> bool:
        """
        设置Agent，连接MCP服务器
        
        Returns:
            是否设置成功
        """
        try:
            # 连接MCP客户端
            if not await self.mcp_client.connect():
                logger.error("无法连接MCP服务器")
                return False
            
            # 获取可用工具
            self.available_tools = self.mcp_client.get_available_tools()
            available_tool_names = [tool['name'] for tool in self.available_tools]
            logger.info(f"MCP Agent设置成功，可用工具: {available_tool_names}")
            
            # 更新任务分发器的可用工具列表
            self.task_dispatcher.available_tools = available_tool_names
            
            # 初始化任务处理器
            self.simple_task_handler = SimpleTaskHandler(self.server_command, self.enable_debug)
            await self.simple_task_handler.setup()
            
            self.complex_task_handler = ComplexTaskHandler(self.llm, enable_debug=self.enable_debug)
            
            # 设置工作流执行器（如果启用）
            if self.workflow_executor:
                if not await self.workflow_executor.setup():
                    logger.warning("工作流执行器设置失败，但Agent仍可使用")
            
            return True
            
        except Exception as e:
            logger.error(f"MCP Agent设置失败: {e}")
            return False
    
    async def cleanup(self):
        """清理资源"""
        await self.mcp_client.disconnect()
        if self.simple_task_handler:
            await self.simple_task_handler.cleanup()
        if self.workflow_executor:
            await self.workflow_executor.cleanup()
    
    async def chat(self, user_message: str, use_workflow: bool = None) -> Dict[str, Any]:
        """
        与Agent聊天
        
        Args:
            user_message: 用户消息
            use_workflow: 是否使用工作流模式，None表示自动判断
            
        Returns:
            Agent响应
        """
        try:
            logger.info(f"收到用户消息: {user_message}")
            
            # 决定是否使用工作流
            if use_workflow is None:
                use_workflow = await self._should_use_workflow(user_message)
            
            if use_workflow and self.enable_workflow:
                return await self._handle_with_workflow(user_message)
            else:
                return await self._handle_with_direct_tools(user_message)
                
        except Exception as e:
            logger.error(f"处理用户消息失败: {e}")
            return {
                "success": False,
                "error": f"处理失败: {str(e)}",
                "response": "抱歉，我遇到了一些问题，无法处理您的请求。"
            }
    
    async def _should_use_workflow(self, user_message: str) -> bool:
        """
        判断是否应该使用工作流模式
        
        Args:
            user_message: 用户消息
            
        Returns:
            是否使用工作流
        """
        # 简单的启发式规则
        workflow_keywords = [
            "率定", "calibrat", "建模", "model", "流程", "workflow", 
            "完整", "complete", "评估", "evaluat", "准备数据", "prepare"
        ]
        
        return any(keyword in user_message.lower() for keyword in workflow_keywords)
    
    async def _handle_with_workflow(self, user_message: str) -> Dict[str, Any]:
        """
        使用工作流模式处理用户消息 - 智能逐步执行
        
        Args:
            user_message: 用户消息
            
        Returns:
            处理结果
        """
        try:
            logger.info("使用智能工作流模式处理用户请求")
            
            # 生成工作流计划
            workflow_plan = await self._generate_workflow(user_message)
            if not workflow_plan:
                return {
                    "success": False,
                    "error": "无法生成工作流计划",
                    "response": "抱歉，我无法为您的请求生成合适的工作流。"
                }
            
            logger.info(f"生成工作流: {workflow_plan.name}, 包含 {len(workflow_plan.steps)} 个步骤")
            
            # 智能逐步执行工作流
            execution_result = await self._execute_workflow_intelligently(workflow_plan, user_message)
            
            # 生成响应
            response = await self._generate_workflow_response(user_message, workflow_plan, execution_result)
            
            return {
                "success": execution_result.get("overall_success", False),
                "workflow_plan": {
                    "plan_id": workflow_plan.plan_id,
                    "name": workflow_plan.name,
                    "description": workflow_plan.description,
                    "steps": [
                        {
                            "step_id": step.step_id,
                            "name": step.name,
                            "tool_name": step.tool_name,
                            "parameters": step.parameters
                        }
                        for step in workflow_plan.steps
                    ]
                },
                "execution_result": execution_result,
                "response": response
            }
            
        except Exception as e:
            logger.error(f"工作流模式处理失败: {e}")
            return {
                "success": False,
                "error": f"工作流处理失败: {str(e)}",
                "response": "抱歉，在处理您的工作流请求时出现了问题。"
            }
    
    async def _handle_with_direct_tools(self, user_message: str) -> Dict[str, Any]:
        """
        使用直接工具调用模式处理用户消息（集成任务分发器）
        
        Args:
            user_message: 用户消息
            
        Returns:
            处理结果
        """
        try:
            logger.info("使用任务分发器处理用户请求")
            
            # 1. 使用任务分发器分析任务
            classification, strategy = await self.task_dispatcher.dispatch_task(user_message)
            
            logger.info(f"任务分类: {classification.complexity.value}, 执行策略: {strategy['execution_type']}")
            
            # 2. 根据分发结果选择处理方式
            if strategy["execution_type"] == "mcp_tools":
                # 简单任务：使用MCP工具
                result = await self.simple_task_handler.handle_task(
                    user_message, 
                    classification
                )
                
                # 生成响应
                response = await self._generate_task_response(user_message, result, "simple")
                
                return {
                    "success": result["success"],
                    "execution_type": "simple_task",
                    "classification": {
                        "complexity": classification.complexity.value,
                        "category": classification.category.value,
                        "confidence": classification.confidence,
                        "reasoning": classification.reasoning
                    },
                    "task_result": result,
                    "response": response
                }
                
            elif strategy["execution_type"] == "code_generation":
                # 复杂任务：生成代码工具
                result = await self.complex_task_handler.handle_task(
                    user_message,
                    classification
                )
                
                # 生成响应
                response = await self._generate_task_response(user_message, result, "complex")
                
                return {
                    "success": result["success"],
                    "execution_type": "complex_task",
                    "classification": {
                        "complexity": classification.complexity.value,
                        "category": classification.category.value,
                        "confidence": classification.confidence,
                        "reasoning": classification.reasoning
                    },
                    "task_result": result,
                    "response": response
                }
                
            else:
                # 需要人工审查
                manual_handler = ManualReviewHandler(self.enable_debug)
                result = await manual_handler.handle_task(user_message, classification)
                
                return {
                    "success": False,
                    "execution_type": "manual_review",
                    "classification": {
                        "complexity": classification.complexity.value,
                        "category": classification.category.value,
                        "confidence": classification.confidence,
                        "reasoning": classification.reasoning
                    },
                    "task_result": result,
                    "response": result["message"]
                }
            
        except Exception as e:
            logger.error(f"任务分发处理失败: {e}")
            return {
                "success": False,
                "error": f"任务处理失败: {str(e)}",
                "response": "抱歉，在处理您的请求时出现了问题。"
            }
    
    async def _execute_workflow_intelligently(self, workflow_plan: WorkflowPlan, original_query: str) -> Dict[str, Any]:
        """
        智能执行工作流 - 逐步分析、动态调整
        
        Args:
            workflow_plan: 工作流计划
            original_query: 原始用户查询
            
        Returns:
            执行结果
        """
        execution_context = {
            "original_query": original_query,
            "workflow_id": workflow_plan.plan_id,
            "step_results": [],
            "accumulated_context": "",
            "failed_steps": [],
            "success_steps": [],
            "current_step_index": 0
        }
        
        logger.info(f"开始智能执行工作流: {workflow_plan.name}")
        
        overall_success = True
        
        for i, step in enumerate(workflow_plan.steps):
            execution_context["current_step_index"] = i
            logger.info(f"处理步骤 {i+1}/{len(workflow_plan.steps)}: {step.name}")
            
            try:
                # 1. 基于当前上下文分析任务
                step_analysis = await self._analyze_step_with_context(step, execution_context)
                
                # 2. 使用任务分发器重新评估任务复杂度
                classification, strategy = await self.task_dispatcher.dispatch_task(
                    f"{step.description}\n\n上下文：{execution_context['accumulated_context']}"
                )
                
                logger.info(f"步骤分类: {classification.complexity.value}, 策略: {strategy['execution_type']}")
                
                # 3. 根据分类和策略执行任务
                step_result = await self._execute_step_intelligently(step, classification, strategy, execution_context)
                
                # 4. 更新执行上下文
                self._update_execution_context(execution_context, step, step_result, classification)
                
                # 5. 记录结果
                execution_context["step_results"].append({
                    "step_id": step.step_id,
                    "step_name": step.name,
                    "classification": {
                        "complexity": classification.complexity.value,
                        "category": classification.category.value,
                        "confidence": classification.confidence
                    },
                    "strategy": strategy["execution_type"],
                    "result": step_result,
                    "success": step_result.get("success", False)
                })
                
                if step_result.get("success", False):
                    execution_context["success_steps"].append(step.step_id)
                    logger.info(f"步骤 {step.step_id} 执行成功")
                else:
                    execution_context["failed_steps"].append(step.step_id)
                    overall_success = False
                    logger.error(f"步骤 {step.step_id} 执行失败: {step_result.get('error', '未知错误')}")
                    
                    # 根据失败处理策略决定是否继续
                    should_continue = await self._should_continue_after_failure(step, step_result, execution_context)
                    if not should_continue:
                        logger.info("由于关键步骤失败，停止工作流执行")
                        break
                
            except Exception as e:
                logger.error(f"步骤 {step.step_id} 执行异常: {e}")
                execution_context["failed_steps"].append(step.step_id)
                execution_context["step_results"].append({
                    "step_id": step.step_id,
                    "step_name": step.name,
                    "error": str(e),
                    "success": False
                })
                overall_success = False
        
        # 汇总执行结果
        final_result = {
            "workflow_id": workflow_plan.plan_id,
            "workflow_name": workflow_plan.name,
            "overall_success": overall_success,
            "total_steps": len(workflow_plan.steps),
            "success_steps": len(execution_context["success_steps"]),
            "failed_steps": len(execution_context["failed_steps"]),
            "step_results": execution_context["step_results"],
            "final_context": execution_context["accumulated_context"],
            "execution_summary": self._generate_execution_summary(execution_context)
        }
        
        logger.info(f"工作流执行完成: 成功 {final_result['success_steps']}/{final_result['total_steps']} 步骤")
        return final_result
    
    async def _analyze_step_with_context(self, step, execution_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        基于上下文分析当前步骤
        
        Args:
            step: 当前步骤
            execution_context: 执行上下文
            
        Returns:
            步骤分析结果
        """
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", """你是一个专业的工作流分析专家。基于之前步骤的执行结果和上下文，分析当前步骤的执行策略。

请考虑：
1. 之前步骤的成功/失败情况
2. 已获得的数据和结果
3. 当前步骤是否需要调整参数
4. 是否存在依赖关系问题

返回JSON格式：
{{
    "adjusted_description": "调整后的步骤描述",
    "parameter_adjustments": {{"需要调整的参数": "调整建议"}},
    "dependencies_satisfied": true/false,
    "risk_level": "low/medium/high",
    "recommendations": ["执行建议列表"]
}}"""),
                ("human", """
原始步骤信息：
- 步骤ID: {step_id}
- 名称: {step_name}
- 描述: {step_description}
- 工具: {step_tool}
- 参数: {step_params}

执行上下文：
- 原始查询: {original_query}
- 当前是第 {current_step} 步
- 已成功步骤: {success_steps}
- 已失败步骤: {failed_steps}
- 累积上下文: {accumulated_context}

请分析这个步骤的执行策略。""")
            ])
            
            chain = prompt | self.llm
            response = await chain.ainvoke({
                "step_id": step.step_id,
                "step_name": step.name,
                "step_description": step.description,
                "step_tool": step.tool_name,
                "step_params": str(step.parameters),  # 转为字符串避免引号问题
                "original_query": execution_context['original_query'],
                "current_step": execution_context['current_step_index'] + 1,
                "success_steps": str(execution_context['success_steps']),
                "failed_steps": str(execution_context['failed_steps']),
                "accumulated_context": execution_context['accumulated_context']
            })
            
            try:
                return json.loads(response.content)
            except json.JSONDecodeError:
                logger.warning(f"无法解析步骤分析结果，使用默认分析")
                return {
                    "adjusted_description": step.description,
                    "parameter_adjustments": {},
                    "dependencies_satisfied": True,
                    "risk_level": "medium",
                    "recommendations": ["按原计划执行"]
                }
                
        except Exception as e:
            logger.error(f"步骤分析失败: {e}")
            return {
                "adjusted_description": step.description,
                "parameter_adjustments": {},
                "dependencies_satisfied": True,
                "risk_level": "high",
                "recommendations": ["存在分析错误，谨慎执行"]
            }
    
    async def _execute_step_intelligently(self, step, classification, strategy, execution_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        智能执行单个步骤
        
        Args:
            step: 工作流步骤
            classification: 任务分类结果
            strategy: 执行策略
            execution_context: 执行上下文
            
        Returns:
            步骤执行结果
        """
        try:
            if strategy["execution_type"] == "mcp_tools":
                # 简单任务：直接使用MCP工具
                logger.info(f"使用MCP工具执行简单任务: {step.tool_name}")
                return await self._execute_simple_step(step, execution_context)
                
            elif strategy["execution_type"] == "code_generation":
                # 复杂任务：生成代码工具 (目前使用Demo)
                logger.info(f"处理复杂任务: {step.name}")
                return await self._execute_complex_step_demo(step, classification, execution_context)
                
            elif strategy["execution_type"] == "manual_review":
                # 未知任务：人工审查
                logger.info(f"需要人工审查的任务: {step.name}")
                return await self._execute_manual_review_step(step, classification, execution_context)
                
            else:
                return {
                    "success": False,
                    "error": f"未知的执行策略: {strategy['execution_type']}",
                    "step_id": step.step_id
                }
                
        except Exception as e:
            logger.error(f"步骤执行失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "step_id": step.step_id
            }
    
    async def _execute_simple_step(self, step, execution_context: Dict[str, Any]) -> Dict[str, Any]:
        """执行简单任务步骤"""
        try:
            # 检查工具是否可用
            if step.tool_name and step.tool_name not in [tool['name'] for tool in self.available_tools]:
                return {
                    "success": False,
                    "error": f"工具 {step.tool_name} 不可用",
                    "step_id": step.step_id
                }
            
            # 调用MCP工具
            if step.tool_name:
                result = await self.mcp_client.call_tool(step.tool_name, step.parameters)
                return {
                    "success": result.get("success", True),
                    "result": result,
                    "tool_used": step.tool_name,
                    "parameters": step.parameters,
                    "step_id": step.step_id
                }
            else:
                # 如果没有指定工具，尝试智能选择
                return await self._smart_tool_selection(step, execution_context)
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "step_id": step.step_id
            }
    
    async def _execute_complex_step_demo(self, step, classification, execution_context: Dict[str, Any]) -> Dict[str, Any]:
        """执行复杂任务步骤 (Demo版本)"""
        logger.info(f"复杂任务Demo执行: {step.name}")
        
        # Demo: 模拟复杂任务处理
        demo_result = {
            "success": True,
            "generated_tool": f"custom_tool_for_{step.step_id}",
            "tool_description": f"为任务 '{step.name}' 生成的自定义工具",
            "execution_notes": "这是一个Demo实现，实际中会调用大模型生成具体工具",
            "demo_output": f"模拟执行 {step.description} 的结果",
            "complexity_handled": classification.complexity.value,
            "step_id": step.step_id
        }
        
        # 模拟执行时间
        await asyncio.sleep(0.5)
        
        return demo_result
    
    async def _execute_manual_review_step(self, step, classification, execution_context: Dict[str, Any]) -> Dict[str, Any]:
        """执行需要人工审查的步骤"""
        logger.warning(f"任务需要人工审查: {step.name}")
        
        return {
            "success": False,
            "needs_manual_review": True,
            "review_reason": f"任务 '{step.name}' 复杂度未知，需要人工判断执行方式",
            "classification": classification.reasoning,
            "suggested_actions": [
                "由专家评估任务需求",
                "确定合适的工具或方法",
                "手动执行或指导Agent执行"
            ],
            "step_id": step.step_id
        }
    
    async def _smart_tool_selection(self, step, execution_context: Dict[str, Any]) -> Dict[str, Any]:
        """智能工具选择"""
        try:
            # 基于步骤描述和上下文选择合适的工具
            tool_decision = await self._analyze_and_select_tool(
                f"{step.description}\n\n上下文: {execution_context['accumulated_context']}"
            )
            
            if tool_decision and tool_decision["tool_name"]:
                # 执行选择的工具
                result = await self.mcp_client.call_tool(
                    tool_decision["tool_name"], 
                    tool_decision["parameters"]
                )
                return {
                    "success": result.get("success", True),
                    "result": result,
                    "tool_used": tool_decision["tool_name"],
                    "parameters": tool_decision["parameters"],
                    "selection_reasoning": tool_decision["reasoning"],
                    "step_id": step.step_id
                }
            else:
                return {
                    "success": False,
                    "error": "无法为该步骤选择合适的工具",
                    "step_id": step.step_id
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"智能工具选择失败: {str(e)}",
                "step_id": step.step_id
            }
    
    def _update_execution_context(self, execution_context: Dict[str, Any], step, step_result: Dict[str, Any], classification):
        """更新执行上下文"""
        # 添加步骤结果到累积上下文
        context_update = f"\n步骤 {step.step_id} ({step.name}):\n"
        
        if step_result.get("success", False):
            context_update += f"  - 执行成功\n"
            if "result" in step_result:
                context_update += f"  - 结果: {step_result['result']}\n"
            if "tool_used" in step_result:
                context_update += f"  - 使用工具: {step_result['tool_used']}\n"
        else:
            context_update += f"  - 执行失败: {step_result.get('error', '未知错误')}\n"
        
        context_update += f"  - 任务复杂度: {classification.complexity.value}\n"
        
        execution_context["accumulated_context"] += context_update
        
        # 限制上下文长度，避免过长
        if len(execution_context["accumulated_context"]) > 2000:
            # 保留最近的上下文
            lines = execution_context["accumulated_context"].split('\n')
            execution_context["accumulated_context"] = '\n'.join(lines[-30:])
    
    async def _should_continue_after_failure(self, step, step_result: Dict[str, Any], execution_context: Dict[str, Any]) -> bool:
        """判断失败后是否应该继续执行"""
        # 简单策略：如果是关键步骤失败，停止执行
        critical_keywords = ["准备", "率定", "calibrat", "train"]
        
        if any(keyword in step.name.lower() or keyword in step.description.lower() for keyword in critical_keywords):
            logger.warning(f"关键步骤 {step.step_id} 失败，建议停止执行")
            return False
        
        # 如果连续失败步骤过多，停止执行
        if len(execution_context["failed_steps"]) >= 2:
            logger.warning("连续失败步骤过多，停止执行")
            return False
        
        return True
    
    def _generate_execution_summary(self, execution_context: Dict[str, Any]) -> str:
        """生成执行摘要"""
        total_steps = len(execution_context["step_results"])
        success_count = len(execution_context["success_steps"])
        failed_count = len(execution_context["failed_steps"])
        
        summary = f"工作流执行完成，共 {total_steps} 个步骤，"
        summary += f"成功 {success_count} 个，失败 {failed_count} 个。"
        
        if failed_count > 0:
            summary += f" 失败的步骤: {', '.join(execution_context['failed_steps'])}"
        
        return summary
    
    async def _generate_workflow(self, user_message: str) -> Optional[WorkflowPlan]:
        """生成工作流计划"""
        if not self.workflow_orchestrator:
            return None
        
        try:
            return await asyncio.to_thread(
                self.workflow_orchestrator.process_query,
                user_message
            )
        except Exception as e:
            logger.error(f"生成工作流失败: {e}")
            return None
    
    async def _analyze_and_select_tool(self, user_message: str) -> Optional[Dict[str, Any]]:
        """
        分析用户消息并选择合适的工具
        
        Args:
            user_message: 用户消息
            
        Returns:
            工具选择结果
        """
        try:
            # 构建工具选择提示
            tools_info = self._format_tools_for_prompt()
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", f"""你是一个专业的水文模型助手。根据用户的问题，分析是否需要调用工具，如果需要则选择合适的工具并提取参数。

可用工具：
{tools_info}

请严格按照以下JSON格式回答：
{{
    "need_tool": true/false,
    "tool_name": "工具名称或null",
    "parameters": {{参数字典}},
    "reasoning": "选择原因"
}}

重要提示：
1. 如果用户只是在问候或询问一般信息，设置need_tool为false
2. 仔细匹配用户需求和工具功能
3. 确保参数符合工具要求"""),
                ("human", "{user_message}")
            ])
            
            # 调用LLM
            chain = prompt | self.llm
            response = await chain.ainvoke({"user_message": user_message})
            
            # 解析响应
            try:
                result = json.loads(response.content)
                if result.get("need_tool", False):
                    return {
                        "tool_name": result.get("tool_name"),
                        "parameters": result.get("parameters", {}),
                        "reasoning": result.get("reasoning", "")
                    }
                else:
                    return None
                    
            except json.JSONDecodeError:
                logger.error(f"无法解析LLM响应为JSON: {response.content}")
                return None
                
        except Exception as e:
            logger.error(f"工具选择分析失败: {e}")
            return None
    
    def _format_tools_for_prompt(self) -> str:
        """格式化工具信息用于提示"""
        tools_desc = []
        for tool in self.available_tools:
            schema = tool["inputSchema"]
            properties = schema.get("properties", {})
            required = schema.get("required", [])
            
            params_desc = []
            for param, param_info in properties.items():
                is_required = param in required
                param_desc = f"  - {param} ({'必需' if is_required else '可选'}): {param_info.get('description', '')}"
                params_desc.append(param_desc)
            
            tool_desc = f"""
工具名称: {tool['name']}
功能描述: {tool['description']}
参数:
{chr(10).join(params_desc)}
"""
            tools_desc.append(tool_desc)
        
        return "\n".join(tools_desc)
    
    async def _generate_direct_response(self, user_message: str) -> str:
        """生成直接响应（无需工具调用）"""
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", """你是一个专业的水文模型助手。用户没有请求特定的工具操作，请直接回答他们的问题。

你可以提供关于水文建模的一般性信息，解释概念，或者引导用户如何使用你的工具功能。

保持回答简洁、友好和有帮助。"""),
                ("human", "{user_message}")
            ])
            
            chain = prompt | self.llm
            response = await chain.ainvoke({"user_message": user_message})
            return response.content
            
        except Exception as e:
            logger.error(f"生成直接响应失败: {e}")
            return "我很乐意帮助您，但是遇到了一些技术问题。请尝试重新表述您的问题。"
    
    async def _generate_tool_response(
        self, 
        user_message: str, 
        tool_decision: Dict[str, Any], 
        tool_result: Dict[str, Any]
    ) -> str:
        """生成基于工具结果的响应"""
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", """你是一个专业的水文模型助手。用户请求了一个工具操作，你已经获得了工具的执行结果。

请根据工具结果生成一个清晰、有用的回答。如果工具执行成功，解释结果的含义；如果失败，解释可能的原因并建议解决方案。

保持回答专业但易懂。"""),
                ("human", f"""
用户问题: {user_message}

使用的工具: {tool_decision['tool_name']}
工具参数: {json.dumps(tool_decision['parameters'], ensure_ascii=False, indent=2)}
工具结果: {json.dumps(tool_result, ensure_ascii=False, indent=2)}

请基于以上信息生成回答。""")
            ])
            
            chain = prompt | self.llm
            response = await chain.ainvoke({})
            return response.content
            
        except Exception as e:
            logger.error(f"生成工具响应失败: {e}")
            return f"工具执行完成，结果：{json.dumps(tool_result, ensure_ascii=False, indent=2)}"
    
    async def _generate_workflow_response(
        self,
        user_message: str,
        workflow_plan: WorkflowPlan,
        execution_result: Dict[str, Any]
    ) -> str:
        """生成基于工作流结果的响应"""
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", """你是一个专业的水文模型助手。用户请求了一个复杂的工作流操作，你已经执行了相应的工作流。

请根据工作流执行结果生成一个详细、清晰的总结报告。包括：
1. 工作流的整体执行情况
2. 每个步骤的执行结果
3. 最终的成果和输出
4. 如果有失败，解释原因和建议

保持回答专业、详细但易懂。"""),
                ("human", f"""
用户请求: {user_message}

工作流计划:
- 名称: {workflow_plan.name}
- 描述: {workflow_plan.description}
- 步骤数量: {len(workflow_plan.steps)}

执行结果: {json.dumps(execution_result, ensure_ascii=False, indent=2)}

请生成详细的工作流执行报告。""")
            ])
            
            chain = prompt | self.llm
            response = await chain.ainvoke({})
            return response.content
            
        except Exception as e:
            logger.error(f"生成工作流响应失败: {e}")
            return f"工作流执行完成。总体状态：{execution_result.get('overall_status', 'unknown')}"
    
    async def _generate_task_response(
        self, 
        user_message: str, 
        task_result: Dict[str, Any], 
        task_type: str
    ) -> str:
        """
        生成基于任务结果的响应
        
        Args:
            user_message: 用户消息
            task_result: 任务执行结果
            task_type: 任务类型 ("simple" 或 "complex")
            
        Returns:
            生成的响应
        """
        try:
            if task_type == "simple":
                prompt = ChatPromptTemplate.from_messages([
                    ("system", """你是一个专业的水文模型助手。用户请求了一个简单任务，你已经使用MCP工具执行完成。

请根据执行结果生成一个清晰、有用的回答。如果任务成功，解释结果的含义；如果失败，解释可能的原因并建议解决方案。

保持回答专业但易懂。"""),
                    ("human", f"""
用户请求: {user_message}

任务执行结果: {json.dumps(task_result, ensure_ascii=False, indent=2)}

请基于以上信息生成回答。""")
                ])
            
            elif task_type == "complex":
                prompt = ChatPromptTemplate.from_messages([
                    ("system", """你是一个专业的水文模型助手。用户请求了一个复杂任务，你已经生成了相应的代码工具并执行完成。

请根据执行结果生成一个详细的报告，包括：
1. 任务的处理过程
2. 生成的工具或代码
3. 执行结果和输出
4. 如果有问题，提供解决建议

保持回答专业、详细但易懂。"""),
                    ("human", f"""
用户请求: {user_message}

复杂任务处理结果: {json.dumps(task_result, ensure_ascii=False, indent=2)}

请生成详细的任务处理报告。""")
                ])
            
            else:
                # 默认响应
                return f"任务处理完成。结果：{json.dumps(task_result, ensure_ascii=False, indent=2)}"
            
            chain = prompt | self.llm
            response = await chain.ainvoke({})
            return response.content
            
        except Exception as e:
            logger.error(f"生成任务响应失败: {e}")
            
            # 回退到简单格式
            if task_result.get("success", False):
                return f"任务执行成功！{task_result.get('summary', '已完成所需操作。')}"
            else:
                return f"任务执行失败：{task_result.get('error', '未知错误')}"


# 便利函数
async def create_mcp_agent(
    llm_model: str = "granite3-dense:8b",
    server_command: Optional[List[str]] = None,
    enable_workflow: bool = True,
    enable_debug: bool = False
) -> MCPAgent:
    """
    创建并设置MCP Agent
    
    Args:
        llm_model: Ollama模型名称
        server_command: MCP服务器启动命令
        enable_workflow: 是否启用工作流功能
        enable_debug: 是否启用调试模式
        
    Returns:
        已设置的MCP Agent
    """
    agent = MCPAgent(llm_model, server_command, enable_workflow, enable_debug)
    
    if not await agent.setup():
        raise RuntimeError("无法设置MCP Agent")
    
    return agent


# 示例使用
async def main():
    """示例：如何使用MCP Agent"""
    logging.basicConfig(level=logging.INFO)
    
    try:
        # 创建Agent
        agent = await create_mcp_agent(enable_debug=True)
        
        # 测试对话
        test_messages = [
            "你好！",
            "GR4J模型有哪些参数？",
            "我想率定一个GR4J模型",
        ]
        
        for message in test_messages:
            print(f"\n用户: {message}")
            result = await agent.chat(message)
            print(f"Agent: {result['response']}")
            
    except Exception as e:
        print(f"示例运行失败: {e}")
    
    finally:
        if 'agent' in locals():
            await agent.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
