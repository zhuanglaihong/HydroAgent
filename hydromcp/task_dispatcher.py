"""
任务分发器
判断任务是简单任务还是复杂任务，并选择相应的执行路径
"""

import logging
import json
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from datetime import datetime

from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)


class TaskComplexity(Enum):
    """任务复杂度枚举"""
    SIMPLE_ACTION = "simple_action"           # 简单操作：现有工具可以直接解决
    COMPLEX_REASONING = "complex_reasoning"   # 复杂推理：需要新的代码工具或复杂逻辑
    UNKNOWN = "unknown"                       # 未知复杂度


class TaskCategory(Enum):
    """任务类别枚举"""
    PARAMETER_QUERY = "parameter_query"        # 参数查询
    DATA_PREPARATION = "data_preparation"      # 数据准备
    MODEL_CALIBRATION = "model_calibration"    # 模型率定
    MODEL_EVALUATION = "model_evaluation"      # 模型评估
    ANALYSIS = "analysis"                      # 分析任务
    VISUALIZATION = "visualization"            # 可视化任务
    CUSTOM_COMPUTATION = "custom_computation"  # 自定义计算
    OTHER = "other"                           # 其他任务


class TaskClassification:
    """任务分类结果"""
    
    def __init__(
        self,
        complexity: TaskComplexity,
        category: TaskCategory,
        confidence: float,
        reasoning: str,
        required_tools: List[str],
        missing_capabilities: List[str] = None
    ):
        self.complexity = complexity
        self.category = category
        self.confidence = confidence
        self.reasoning = reasoning
        self.required_tools = required_tools
        self.missing_capabilities = missing_capabilities or []
        self.timestamp = datetime.now()


class TaskDispatcher:
    """任务分发器 - 判断任务复杂性并选择执行路径"""
    
    def __init__(self, llm, available_tools: List[str] = None):
        """
        初始化任务分发器
        
        Args:
            llm: 语言模型实例
            available_tools: 可用工具列表
        """
        self.llm = llm
        self.available_tools = available_tools or [
            "get_model_params",
            "prepare_data", 
            "calibrate_model",
            "evaluate_model"
        ]
        
        # 工具能力映射
        self.tool_capabilities = {
            "get_model_params": [
                "查询模型参数",
                "获取参数范围",
                "模型信息查询"
            ],
            "prepare_data": [
                "数据格式转换",
                "数据预处理",
                "时间序列处理",
                "数据质量控制"
            ],
            "calibrate_model": [
                "参数率定",
                "模型优化",
                "参数搜索",
                "模型训练"
            ],
            "evaluate_model": [
                "性能评估",
                "指标计算",
                "模型验证",
                "结果分析"
            ]
        }
        
        self._setup_prompts()
    
    def _setup_prompts(self):
        """设置提示模板"""
        available_capabilities = []
        for tool, capabilities in self.tool_capabilities.items():
            available_capabilities.extend([f"{tool}: {cap}" for cap in capabilities])
        
        capabilities_text = "\n".join(available_capabilities)
        
        self.classification_prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个专业的水文建模任务分析专家。你需要分析用户的任务请求，判断任务的复杂度和类别。

当前可用的工具和能力：
{capabilities_text}

请严格按照以下JSON格式回答：
{{
    "complexity": "simple/complex",
    "category": "parameter_query/data_preparation/model_calibration/model_evaluation/analysis/visualization/custom_computation/other",
    "confidence": 0.0-1.0,
    "reasoning": "判断理由",
    "required_tools": ["需要的工具列表"],
    "missing_capabilities": ["当前工具无法提供的能力"]
}}

判断标准：
1. SIMPLE任务：当前工具完全可以解决的任务
2. COMPLEX任务：需要额外的代码开发、算法实现或分析功能的任务

任务类别说明：
- parameter_query: 查询模型参数、配置信息
- data_preparation: 数据预处理、格式转换
- model_calibration: 模型率定、参数优化
- model_evaluation: 模型评估、性能分析
- analysis: 数据分析、统计分析
- visualization: 绘图、可视化
- custom_computation: 自定义计算、算法实现
- other: 其他类型任务"""),
            ("human", "请分析以下任务：{task_description}")
        ])
    
    async def classify_task(self, task_description: str) -> TaskClassification:
        """
        分类任务
        
        Args:
            task_description: 任务描述
            
        Returns:
            任务分类结果
        """
        try:
            logger.info(f"正在分析任务: {task_description}")
            
            # 调用LLM进行分析
            chain = self.classification_prompt | self.llm
            
            # 重新生成capabilities_text以确保最新
            available_capabilities = []
            for tool, capabilities in self.tool_capabilities.items():
                available_capabilities.extend([f"{tool}: {cap}" for cap in capabilities])
            capabilities_text = "\n".join(available_capabilities)
            
            response = await chain.ainvoke({
                "task_description": task_description,
                "capabilities_text": capabilities_text
            })
            
            # 解析响应
            try:
                result = json.loads(response.content)
                
                complexity = TaskComplexity(result.get("complexity", "unknown"))
                category = TaskCategory(result.get("category", "other"))
                confidence = float(result.get("confidence", 0.0))
                reasoning = result.get("reasoning", "")
                required_tools = result.get("required_tools", [])
                missing_capabilities = result.get("missing_capabilities", [])
                
                classification = TaskClassification(
                    complexity=complexity,
                    category=category,
                    confidence=confidence,
                    reasoning=reasoning,
                    required_tools=required_tools,
                    missing_capabilities=missing_capabilities
                )
                
                logger.info(f"任务分类完成: {complexity.value}, 置信度: {confidence}")
                return classification
                
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.error(f"解析LLM响应失败: {e}, 响应内容: {response.content}")
                return self._fallback_classification(task_description)
                
        except Exception as e:
            logger.error(f"任务分类失败: {e}")
            return self._fallback_classification(task_description)
    
    def _fallback_classification(self, task_description: str) -> TaskClassification:
        """
        回退分类方法（基于规则）
        
        Args:
            task_description: 任务描述
            
        Returns:
            回退分类结果
        """
        logger.info("使用规则基础的回退分类方法")
        
        task_lower = task_description.lower()
        
        # 简单的关键词匹配
        if any(keyword in task_lower for keyword in ["参数", "parameter", "查询", "query"]):
            return TaskClassification(
                complexity=TaskComplexity.SIMPLE,
                category=TaskCategory.PARAMETER_QUERY,
                confidence=0.7,
                reasoning="基于关键词匹配的回退分类",
                required_tools=["get_model_params"]
            )
        
        elif any(keyword in task_lower for keyword in ["数据", "data", "准备", "preprocess"]):
            return TaskClassification(
                complexity=TaskComplexity.SIMPLE,
                category=TaskCategory.DATA_PREPARATION,
                confidence=0.7,
                reasoning="基于关键词匹配的回退分类",
                required_tools=["prepare_data"]
            )
        
        elif any(keyword in task_lower for keyword in ["率定", "calibrat", "训练", "train"]):
            return TaskClassification(
                complexity=TaskComplexity.SIMPLE,
                category=TaskCategory.MODEL_CALIBRATION,
                confidence=0.7,
                reasoning="基于关键词匹配的回退分类",
                required_tools=["calibrate_model"]
            )
        
        elif any(keyword in task_lower for keyword in ["评估", "evaluat", "验证", "valid"]):
            return TaskClassification(
                complexity=TaskComplexity.SIMPLE,
                category=TaskCategory.MODEL_EVALUATION,
                confidence=0.7,
                reasoning="基于关键词匹配的回退分类",
                required_tools=["evaluate_model"]
            )
        
        elif any(keyword in task_lower for keyword in ["分析", "analysis", "统计", "statistic"]):
            return TaskClassification(
                complexity=TaskComplexity.COMPLEX,
                category=TaskCategory.ANALYSIS,
                confidence=0.6,
                reasoning="分析任务可能需要自定义代码",
                required_tools=[],
                missing_capabilities=["自定义分析算法"]
            )
        
        elif any(keyword in task_lower for keyword in ["绘图", "plot", "可视化", "visualiz"]):
            return TaskClassification(
                complexity=TaskComplexity.COMPLEX,
                category=TaskCategory.VISUALIZATION,
                confidence=0.6,
                reasoning="可视化任务需要额外的绘图代码",
                required_tools=[],
                missing_capabilities=["绘图和可视化"]
            )
        
        else:
            return TaskClassification(
                complexity=TaskComplexity.UNKNOWN,
                category=TaskCategory.OTHER,
                confidence=0.3,
                reasoning="无法确定任务类型",
                required_tools=[],
                missing_capabilities=["任务类型不明确"]
            )
    
    def get_execution_strategy(self, classification: TaskClassification) -> Dict[str, Any]:
        """
        根据任务分类获取执行策略
        
        Args:
            classification: 任务分类结果
            
        Returns:
            执行策略
        """
        if classification.complexity == TaskComplexity.SIMPLE:
            return {
                "execution_type": "mcp_tools",
                "handler": "SimpleTaskHandler",
                "tools": classification.required_tools,
                "description": "使用现有MCP工具直接执行"
            }
        
        elif classification.complexity == TaskComplexity.COMPLEX:
            return {
                "execution_type": "code_generation",
                "handler": "ComplexTaskHandler", 
                "tools": [],
                "missing_capabilities": classification.missing_capabilities,
                "description": "需要生成新的代码工具来执行"
            }
        
        else:
            return {
                "execution_type": "manual_review",
                "handler": "ManualReviewHandler",
                "tools": [],
                "description": "需要人工审查确定执行方式"
            }
    
    async def dispatch_task(self, task_description: str) -> Tuple[TaskClassification, Dict[str, Any]]:
        """
        分发任务
        
        Args:
            task_description: 任务描述
            
        Returns:
            (任务分类, 执行策略)
        """
        # 1. 分类任务
        classification = await self.classify_task(task_description)
        
        # 2. 获取执行策略
        strategy = self.get_execution_strategy(classification)
        
        logger.info(f"任务分发完成: {classification.complexity.value} -> {strategy['execution_type']}")
        
        return classification, strategy
    
    def can_handle_with_existing_tools(self, required_tools: List[str]) -> bool:
        """
        检查是否可以用现有工具处理
        
        Args:
            required_tools: 需要的工具列表
            
        Returns:
            是否可以处理
        """
        return all(tool in self.available_tools for tool in required_tools)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取分发统计信息"""
        # 这里可以添加统计功能
        return {
            "available_tools": len(self.available_tools),
            "tool_capabilities": len(sum(self.tool_capabilities.values(), [])),
            "dispatch_timestamp": datetime.now().isoformat()
        }


# 便利函数
async def classify_and_dispatch_task(
    task_description: str,
    llm,
    available_tools: List[str] = None
) -> Tuple[TaskClassification, Dict[str, Any]]:
    """
    便利函数：分类并分发任务
    
    Args:
        task_description: 任务描述
        llm: 语言模型
        available_tools: 可用工具列表
        
    Returns:
        (任务分类, 执行策略)
    """
    dispatcher = TaskDispatcher(llm, available_tools)
    return await dispatcher.dispatch_task(task_description)


# 示例使用
async def main():
    """示例：如何使用任务分发器"""
    import sys
    from pathlib import Path
    
    # 添加项目路径
    repo_path = Path(__file__).parent.parent
    sys.path.append(str(repo_path))
    
    from langchain_ollama import ChatOllama
    
    logging.basicConfig(level=logging.INFO)
    
    # 初始化LLM
    llm = ChatOllama(model="granite3-dense:8b", temperature=0.1)
    
    # 创建任务分发器
    dispatcher = TaskDispatcher(llm)
    
    # 测试任务
    test_tasks = [
        "获取GR4J模型的参数信息",
        "率定一个水文模型",
        "绘制流量过程线图", 
        "计算两个时间序列的相关性",
        "分析降雨径流关系",
        "准备CAMELS数据集"
    ]
    
    for task in test_tasks:
        print(f"\n任务: {task}")
        classification, strategy = await dispatcher.dispatch_task(task)
        
        print(f"  复杂度: {classification.complexity.value}")
        print(f"  类别: {classification.category.value}")
        print(f"  置信度: {classification.confidence:.2f}")
        print(f"  执行策略: {strategy['execution_type']}")
        print(f"  处理器: {strategy['handler']}")
        if classification.required_tools:
            print(f"  需要工具: {classification.required_tools}")
        if classification.missing_capabilities:
            print(f"  缺失能力: {classification.missing_capabilities}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
