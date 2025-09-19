"""
新版工作流生成器 - 主入口类

这是重新设计的工作流生成器，将用户的自然语言指令，通过思维链（CoT）推理和RAG系统的增强，
转化为一个结构化的、可执行的工作流计划（DSL）。

核心流程：
1. 指令解析与意图理解 -> 提取关键信息，识别实体和意图
2. 增强推理引擎（CoT + RAG） -> 利用RAG检索知识，引导LLM逐步推理
3. 工作流组装与优化 -> 解析、验证和优化LLM输出的工作流
4. 验证与反馈闭环 -> 自动记录错误并学习优化

Author: Assistant
Date: 2025-01-20
"""

import logging
import time
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from .instruction_parser import (
    InstructionParser, IntentResult, IntentType, create_instruction_parser
)
from .cot_rag_engine import (
    CoTRAGEngine, RAGRetrievalResult, CoTReasoningResult, create_cot_rag_engine
)
from .workflow_assembler import (
    WorkflowAssembler, AssembledWorkflow, ToolRegistry, create_workflow_assembler
)
from .validation_feedback import (
    ValidationFeedbackSystem, create_validation_feedback_system
)

logger = logging.getLogger(__name__)


@dataclass
class GenerationConfig:
    """生成配置"""
    # LLM配置
    llm_model: str = "qwen3:8b"           # LLM模型名称
    llm_temperature: float = 0.7             # LLM温度参数
    max_context_length: int = 4000           # 最大上下文长度
    
    # RAG配置
    rag_retrieval_k: int = 10               # RAG检索数量
    rag_score_threshold: float = 0.3        # RAG相似度阈值
    enable_rag_fallback: bool = True        # 启用RAG回退机制
    
    # 验证配置
    enable_validation: bool = True          # 启用工作流验证
    enable_optimization: bool = True        # 启用工作流优化
    enable_feedback_learning: bool = True   # 启用反馈学习
    
    # 超时配置
    parsing_timeout: int = 30               # 解析超时（秒）
    reasoning_timeout: int = 120            # 推理超时（秒）
    assembly_timeout: int = 60              # 组装超时（秒）
    
    # 存储配置
    feedback_storage_path: str = "workflow/feedback_data"  # 反馈存储路径


@dataclass
class GenerationResult:
    """生成结果"""
    success: bool                           # 是否成功
    workflow: Optional[AssembledWorkflow] = None   # 生成的工作流
    intent_result: Optional[IntentResult] = None   # 意图分析结果
    rag_result: Optional[RAGRetrievalResult] = None # RAG检索结果
    cot_result: Optional[CoTReasoningResult] = None # CoT推理结果
    
    # 时间统计
    total_time: float = 0.0                 # 总耗时
    parsing_time: float = 0.0               # 解析耗时
    reasoning_time: float = 0.0             # 推理耗时
    assembly_time: float = 0.0              # 组装耗时
    
    # 错误信息
    error_message: str = ""                 # 错误信息
    error_details: Dict[str, Any] = field(default_factory=dict)  # 错误详情
    
    # 元数据
    generation_id: str = ""                 # 生成ID
    timestamp: datetime = field(default_factory=datetime.now)  # 时间戳
    metadata: Dict[str, Any] = field(default_factory=dict)     # 元数据

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "workflow": self.workflow.to_dict() if self.workflow else None,
            "intent_result": self.intent_result.to_dict() if self.intent_result else None,
            "rag_result": {
                "query": self.rag_result.query,
                "fragments": [f.to_dict() for f in self.rag_result.fragments],
                "total_fragments": self.rag_result.total_fragments,
                "retrieval_time": self.rag_result.retrieval_time
            } if self.rag_result else None,
            "cot_result": {
                "reasoning_steps": [
                    {
                        "step_number": step.step_number,
                        "question": step.question,
                        "reasoning": step.reasoning,
                        "conclusion": step.conclusion,
                        "confidence": step.confidence
                    } for step in self.cot_result.reasoning_steps
                ],
                "final_plan": self.cot_result.final_plan,
                "reasoning_time": self.cot_result.reasoning_time,
                "llm_model": self.cot_result.llm_model
            } if self.cot_result else None,
            "total_time": self.total_time,
            "parsing_time": self.parsing_time,
            "reasoning_time": self.reasoning_time,
            "assembly_time": self.assembly_time,
            "error_message": self.error_message,
            "error_details": self.error_details,
            "generation_id": self.generation_id,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class WorkflowGeneratorV2:
    """新版工作流生成器"""
    
    def __init__(self, 
                 rag_system=None, 
                 ollama_client=None,
                 config: Optional[GenerationConfig] = None):
        """
        初始化工作流生成器
        
        Args:
            rag_system: RAG系统实例
            ollama_client: Ollama客户端
            config: 生成配置
        """
        self.rag_system = rag_system
        self.ollama_client = ollama_client
        self.config = config or GenerationConfig()
        
        # 初始化各个组件
        self._init_components()
        
        # 统计信息
        self.generation_count = 0
        self.success_count = 0
        self.error_count = 0
        
        logger.info("新版工作流生成器初始化完成")
    
    def _init_components(self):
        """初始化各个组件"""
        try:
            # 1. 指令解析器
            self.instruction_parser = create_instruction_parser(self.ollama_client)
            
            # 2. CoT+RAG推理引擎
            engine_config = {
                "rag_retrieval_k": self.config.rag_retrieval_k,
                "rag_score_threshold": self.config.rag_score_threshold,
                "llm_model": self.config.llm_model,
                "max_context_length": self.config.max_context_length,
                "reasoning_temperature": self.config.llm_temperature,
            }
            self.cot_rag_engine = create_cot_rag_engine(
                rag_system=self.rag_system,
                ollama_client=self.ollama_client,
                config=engine_config
            )
            
            # 3. 工作流组装器
            self.tool_registry = ToolRegistry()
            self.workflow_assembler = create_workflow_assembler(self.tool_registry)
            
            # 4. 验证反馈系统
            if self.config.enable_feedback_learning:
                self.feedback_system = create_validation_feedback_system(
                    storage_path=self.config.feedback_storage_path,
                    rag_system=self.rag_system
                )
            else:
                self.feedback_system = None
            
            logger.info("所有组件初始化完成")
            
        except Exception as e:
            logger.error(f"组件初始化失败: {str(e)}")
            raise
    
    def generate_workflow(self, instruction: str, 
                         metadata: Optional[Dict[str, Any]] = None) -> GenerationResult:
        """
        生成工作流
        
        Args:
            instruction: 用户指令
            metadata: 元数据
            
        Returns:
            GenerationResult: 生成结果
        """
        start_time = time.time()
        generation_id = f"gen_{int(start_time)}_{hash(instruction)}"
        
        # 初始化结果
        result = GenerationResult(
            success=False,
            generation_id=generation_id,
            metadata=metadata or {}
        )
        
        try:
            logger.info(f"开始生成工作流: {instruction[:100]}...")
            
            # 第一步：指令解析与意图理解
            logger.info("第一步：指令解析与意图理解")
            parsing_start = time.time()
            intent_result = self._parse_instruction(instruction)
            result.intent_result = intent_result
            result.parsing_time = time.time() - parsing_start
            
            if intent_result.intent_type == IntentType.UNKNOWN:
                raise ValueError("无法理解用户意图")
            
            # 第二步：增强推理引擎（CoT + RAG）
            logger.info("第二步：增强推理引擎（CoT + RAG）")
            reasoning_start = time.time()
            rag_result, cot_result = self._perform_reasoning(intent_result)
            result.rag_result = rag_result
            result.cot_result = cot_result
            result.reasoning_time = time.time() - reasoning_start
            
            # 第三步：工作流组装与优化
            logger.info("第三步：工作流组装与优化")
            assembly_start = time.time()
            workflow = self._assemble_workflow(cot_result, metadata)
            result.workflow = workflow
            result.assembly_time = time.time() - assembly_start
            
            # 第四步：记录成功结果
            if self.feedback_system and self.config.enable_feedback_learning:
                self.feedback_system.record_execution_result(
                    workflow_id=workflow.workflow_id,
                    task_id="generation",
                    success=True,
                    context={
                        "instruction": instruction,
                        "intent_type": intent_result.intent_type.value,
                        "task_count": len(workflow.tasks)
                    },
                    execution_time=time.time() - start_time
                )
            
            # 更新统计信息
            self.generation_count += 1
            self.success_count += 1
            
            result.success = True
            result.total_time = time.time() - start_time
            
            logger.info(f"工作流生成成功: {workflow.name} ({len(workflow.tasks)}个任务)")
            return result
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"工作流生成失败: {error_message}")
            
            # 记录失败结果
            if self.feedback_system and self.config.enable_feedback_learning:
                self.feedback_system.record_execution_result(
                    workflow_id=generation_id,
                    task_id="generation",
                    success=False,
                    error_info={
                        "message": error_message,
                        "type": type(e).__name__
                    },
                    context={
                        "instruction": instruction,
                        "step": self._get_current_step(result)
                    },
                    execution_time=time.time() - start_time
                )
            
            # 更新统计信息
            self.generation_count += 1
            self.error_count += 1
            
            result.success = False
            result.error_message = error_message
            result.error_details = {
                "type": type(e).__name__,
                "step": self._get_current_step(result)
            }
            result.total_time = time.time() - start_time
            
            return result
    
    def _parse_instruction(self, instruction: str) -> IntentResult:
        """解析指令"""
        try:
            return self.instruction_parser.parse_instruction(instruction)
        except Exception as e:
            logger.error(f"指令解析失败: {str(e)}")
            raise
    
    def _perform_reasoning(self, intent_result: IntentResult) -> Tuple[RAGRetrievalResult, CoTReasoningResult]:
        """执行推理"""
        try:
            return self.cot_rag_engine.generate_reasoning_plan(intent_result)
        except Exception as e:
            logger.error(f"推理失败: {str(e)}")
            raise
    
    def _assemble_workflow(self, cot_result: CoTReasoningResult, 
                          metadata: Optional[Dict[str, Any]]) -> AssembledWorkflow:
        """组装工作流"""
        try:
            return self.workflow_assembler.assemble_workflow(
                raw_plan=cot_result.final_plan,
                metadata=metadata
            )
        except Exception as e:
            logger.error(f"工作流组装失败: {str(e)}")
            raise
    
    def _get_current_step(self, result: GenerationResult) -> str:
        """获取当前执行步骤"""
        if not result.intent_result:
            return "instruction_parsing"
        elif not result.rag_result:
            return "rag_retrieval"
        elif not result.cot_result:
            return "cot_reasoning"
        elif not result.workflow:
            return "workflow_assembly"
        else:
            return "completed"
    
    def generate_workflow_batch(self, instructions: List[str], 
                               metadata_list: Optional[List[Dict[str, Any]]] = None) -> List[GenerationResult]:
        """
        批量生成工作流
        
        Args:
            instructions: 指令列表
            metadata_list: 元数据列表
            
        Returns:
            List[GenerationResult]: 生成结果列表
        """
        if metadata_list and len(metadata_list) != len(instructions):
            raise ValueError("元数据列表长度与指令列表长度不匹配")
        
        results = []
        for i, instruction in enumerate(instructions):
            metadata = metadata_list[i] if metadata_list else None
            result = self.generate_workflow(instruction, metadata)
            results.append(result)
        
        logger.info(f"批量生成完成: {len(instructions)}个指令，成功{sum(1 for r in results if r.success)}个")
        return results
    
    def validate_workflow(self, workflow: AssembledWorkflow) -> Dict[str, Any]:
        """
        验证工作流
        
        Args:
            workflow: 工作流
            
        Returns:
            Dict[str, Any]: 验证结果
        """
        validation_result = {
            "is_valid": True,
            "issues": [],
            "suggestions": []
        }
        
        try:
            # 检查工作流完整性
            if not workflow.tasks:
                validation_result["is_valid"] = False
                validation_result["issues"].append("工作流没有任务")
                validation_result["suggestions"].append("添加至少一个任务")
            
            # 检查任务依赖
            task_ids = {task.task_id for task in workflow.tasks}
            for task in workflow.tasks:
                for dep_id in task.dependencies:
                    if dep_id not in task_ids:
                        validation_result["is_valid"] = False
                        validation_result["issues"].append(f"任务 {task.task_id} 依赖的任务 {dep_id} 不存在")
                        validation_result["suggestions"].append(f"移除依赖 {dep_id} 或添加对应任务")
            
            # 检查工具可用性
            for task in workflow.tasks:
                if not self.tool_registry.is_tool_available(task.action):
                    validation_result["is_valid"] = False
                    validation_result["issues"].append(f"任务 {task.task_id} 使用的工具 {task.action} 不可用")
                    alternatives = self.tool_registry.suggest_alternative_tools(task.action)
                    if alternatives:
                        validation_result["suggestions"].append(f"使用替代工具: {', '.join(alternatives)}")
            
            # 检查循环依赖
            if self._has_circular_dependencies(workflow.tasks):
                validation_result["is_valid"] = False
                validation_result["issues"].append("存在循环依赖")
                validation_result["suggestions"].append("重新设计任务依赖关系")
            
        except Exception as e:
            logger.error(f"工作流验证失败: {str(e)}")
            validation_result["is_valid"] = False
            validation_result["issues"].append(f"验证过程出错: {str(e)}")
        
        return validation_result
    
    def _has_circular_dependencies(self, tasks: List) -> bool:
        """检查是否存在循环依赖"""
        # 简化的循环依赖检测
        task_dict = {task.task_id: task for task in tasks}
        visited = set()
        path = set()
        
        def dfs(task_id: str) -> bool:
            if task_id in path:
                return True  # 发现循环
            if task_id in visited:
                return False
            
            visited.add(task_id)
            path.add(task_id)
            
            task = task_dict.get(task_id)
            if task:
                for dep_id in task.dependencies:
                    if dfs(dep_id):
                        return True
            
            path.remove(task_id)
            return False
        
        for task in tasks:
            if task.task_id not in visited:
                if dfs(task.task_id):
                    return True
        
        return False
    
    def get_generation_statistics(self) -> Dict[str, Any]:
        """获取生成统计信息"""
        success_rate = self.success_count / self.generation_count if self.generation_count > 0 else 0.0
        
        stats = {
            "total_generations": self.generation_count,
            "successful_generations": self.success_count,
            "failed_generations": self.error_count,
            "success_rate": success_rate,
            "system_health": "优秀" if success_rate >= 0.9 else "良好" if success_rate >= 0.7 else "需要改进"
        }
        
        # 如果有反馈系统，添加详细统计
        if self.feedback_system:
            try:
                health_report = self.feedback_system.get_system_health_report()
                stats.update(health_report)
            except Exception as e:
                logger.warning(f"获取反馈系统统计失败: {str(e)}")
        
        return stats
    
    def trigger_learning_update(self):
        """触发学习更新"""
        if self.feedback_system and self.config.enable_feedback_learning:
            try:
                self.feedback_system.trigger_learning_update()
                logger.info("学习更新完成")
            except Exception as e:
                logger.error(f"学习更新失败: {str(e)}")
        else:
            logger.warning("反馈学习未启用")
    
    def export_workflow_dsl(self, workflow: AssembledWorkflow, format: str = "json") -> str:
        """
        导出工作流DSL
        
        Args:
            workflow: 工作流
            format: 导出格式 (json, yaml, xml)
            
        Returns:
            str: DSL字符串
        """
        if format.lower() == "json":
            return workflow.to_json()
        elif format.lower() == "yaml":
            try:
                import yaml
                return yaml.dump(workflow.to_dict(), default_flow_style=False, allow_unicode=True)
            except ImportError:
                logger.warning("PyYAML未安装，使用JSON格式")
                return workflow.to_json()
        elif format.lower() == "xml":
            # 简单的XML转换
            return self._convert_to_xml(workflow.to_dict())
        else:
            raise ValueError(f"不支持的格式: {format}")
    
    def _convert_to_xml(self, data: Dict[str, Any], root_name: str = "workflow") -> str:
        """将字典转换为XML"""
        def dict_to_xml(d, parent_tag):
            xml_parts = [f"<{parent_tag}>"]
            for key, value in d.items():
                if isinstance(value, dict):
                    xml_parts.append(dict_to_xml(value, key))
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            xml_parts.append(dict_to_xml(item, key))
                        else:
                            xml_parts.append(f"<{key}>{item}</{key}>")
                else:
                    xml_parts.append(f"<{key}>{value}</{key}>")
            xml_parts.append(f"</{parent_tag}>")
            return "\n".join(xml_parts)
        
        return dict_to_xml(data, root_name)


def create_workflow_generator(rag_system=None, ollama_client=None, 
                            config: Optional[GenerationConfig] = None) -> WorkflowGeneratorV2:
    """创建工作流生成器实例"""
    return WorkflowGeneratorV2(
        rag_system=rag_system,
        ollama_client=ollama_client,
        config=config
    )
