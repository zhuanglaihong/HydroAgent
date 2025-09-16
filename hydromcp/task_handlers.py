"""
任务处理器
包含简单任务处理器和复杂任务处理器
"""

import logging
import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from abc import ABC, abstractmethod

from .client import HydroMCPClient
from .task_dispatcher import TaskClassification, TaskComplexity

logger = logging.getLogger(__name__)


class BaseTaskHandler(ABC):
    """任务处理器基类"""
    
    def __init__(self, enable_debug: bool = False):
        self.enable_debug = enable_debug
        self.execution_history = []
    
    @abstractmethod
    async def handle_task(
        self, 
        task_description: str, 
        classification: TaskClassification,
        **kwargs
    ) -> Dict[str, Any]:
        """
        处理任务
        
        Args:
            task_description: 任务描述
            classification: 任务分类结果
            **kwargs: 额外参数
            
        Returns:
            处理结果
        """
        pass
    
    def _log_execution(self, task_description: str, result: Dict[str, Any]):
        """记录执行历史"""
        execution_record = {
            "task_description": task_description,
            "timestamp": datetime.now().isoformat(),
            "result": result,
            "handler": self.__class__.__name__
        }
        self.execution_history.append(execution_record)
        
        if self.enable_debug:
            logger.debug(f"任务执行记录: {execution_record}")
    
    def get_execution_history(self) -> List[Dict[str, Any]]:
        """获取执行历史"""
        return self.execution_history.copy()


class SimpleTaskHandler(BaseTaskHandler):
    """简单任务处理器 - 使用现有MCP工具执行"""
    
    def __init__(self, server_command: Optional[List[str]] = None, enable_debug: bool = False):
        """
        初始化简单任务处理器
        
        Args:
            server_command: MCP服务器启动命令
            enable_debug: 是否启用调试模式
        """
        super().__init__(enable_debug)
        self.mcp_client = HydroMCPClient(server_command)
        self.connected = False
    
    async def setup(self) -> bool:
        """设置处理器"""
        try:
            self.connected = await self.mcp_client.connect()
            if self.connected:
                tools = self.mcp_client.get_available_tools()
                logger.info(f"简单任务处理器设置成功，可用工具: {[t['name'] for t in tools]}")
            return self.connected
        except Exception as e:
            logger.error(f"简单任务处理器设置失败: {e}")
            return False
    
    async def cleanup(self):
        """清理资源"""
        await self.mcp_client.disconnect()
        self.connected = False
    
    async def handle_task(
        self, 
        task_description: str, 
        classification: TaskClassification,
        **kwargs
    ) -> Dict[str, Any]:
        """
        处理简单任务
        
        Args:
            task_description: 任务描述
            classification: 任务分类结果
            **kwargs: 额外参数，可能包含tool_parameters
            
        Returns:
            处理结果
        """
        start_time = datetime.now()
        
        try:
            if not self.connected:
                raise RuntimeError("MCP客户端未连接")
            
            logger.info(f"开始处理简单任务: {task_description}")
            
            results = []
            
            # 依次执行需要的工具
            for tool_name in classification.required_tools:
                logger.info(f"执行工具: {tool_name}")
                
                # 获取工具参数
                tool_parameters = self._get_tool_parameters(
                    tool_name, 
                    task_description, 
                    kwargs.get('tool_parameters', {})
                )
                
                # 调用工具
                tool_result = await self.mcp_client.call_tool(tool_name, tool_parameters)
                results.append({
                    "tool_name": tool_name,
                    "parameters": tool_parameters,
                    "result": tool_result
                })
                
                if self.enable_debug:
                    logger.debug(f"工具 {tool_name} 执行结果: {tool_result}")
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            result = {
                "success": True,
                "handler": "SimpleTaskHandler",
                "task_description": task_description,
                "execution_time": execution_time,
                "tools_executed": len(results),
                "results": results,
                "summary": self._generate_summary(results)
            }
            
            self._log_execution(task_description, result)
            logger.info(f"简单任务处理完成，执行时间: {execution_time:.2f}s")
            
            return result
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"简单任务处理失败: {e}")
            
            result = {
                "success": False,
                "handler": "SimpleTaskHandler",
                "task_description": task_description,
                "execution_time": execution_time,
                "error": str(e),
                "results": []
            }
            
            self._log_execution(task_description, result)
            return result
    
    def _get_tool_parameters(
        self, 
        tool_name: str, 
        task_description: str, 
        provided_parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        获取工具参数
        
        Args:
            tool_name: 工具名称
            task_description: 任务描述
            provided_parameters: 提供的参数
            
        Returns:
            工具参数
        """
        # 如果已提供特定工具的参数，使用提供的参数
        if tool_name in provided_parameters:
            return provided_parameters[tool_name]
        
        # 否则使用默认参数
        default_parameters = {
            "get_model_params": {"model_name": "gr4j"},
            "prepare_data": {
                "data_dir": "data/camels_11532500",
                "target_data_scale": "D"
            },
            "calibrate_model": {
                "model_name": "gr4j",
                "data_dir": "data/camels_11532500",
                "exp_name": "simple_task_calibration"
            },
            "evaluate_model": {
                "result_dir": "result",
                "exp_name": "simple_task_calibration"
            }
        }
        
        return default_parameters.get(tool_name, {})
    
    def _generate_summary(self, results: List[Dict[str, Any]]) -> str:
        """生成执行结果摘要"""
        if not results:
            return "没有执行任何工具"
        
        successful_tools = []
        failed_tools = []
        
        for result in results:
            tool_name = result["tool_name"]
            tool_result = result["result"]
            
            if isinstance(tool_result, dict) and tool_result.get("success", True):
                successful_tools.append(tool_name)
            else:
                failed_tools.append(tool_name)
        
        summary_parts = []
        if successful_tools:
            summary_parts.append(f"成功执行工具: {', '.join(successful_tools)}")
        if failed_tools:
            summary_parts.append(f"执行失败工具: {', '.join(failed_tools)}")
        
        return "; ".join(summary_parts)


class ComplexTaskHandler(BaseTaskHandler):
    """复杂任务处理器 - 结合知识库和LLM生成新工具（Demo版本）"""
    
    def __init__(self, llm, knowledge_base=None, enable_debug: bool = False):
        """
        初始化复杂任务处理器
        
        Args:
            llm: 语言模型实例
            knowledge_base: 知识库（可选）
            enable_debug: 是否启用调试模式
        """
        super().__init__(enable_debug)
        self.llm = llm
        self.knowledge_base = knowledge_base
        self.code_generation_count = 0
    
    async def handle_task(
        self, 
        task_description: str, 
        classification: TaskClassification,
        **kwargs
    ) -> Dict[str, Any]:
        """
        处理复杂任务（Demo版本）
        
        Args:
            task_description: 任务描述
            classification: 任务分类结果
            **kwargs: 额外参数
            
        Returns:
            处理结果
        """
        start_time = datetime.now()
        
        try:
            logger.info(f"开始处理复杂任务: {task_description}")
            
            # Demo: 模拟复杂任务处理流程
            result = await self._demo_complex_task_processing(
                task_description, 
                classification,
                **kwargs
            )
            
            execution_time = (datetime.now() - start_time).total_seconds()
            result["execution_time"] = execution_time
            
            self._log_execution(task_description, result)
            logger.info(f"复杂任务处理完成，执行时间: {execution_time:.2f}s")
            
            return result
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"复杂任务处理失败: {e}")
            
            result = {
                "success": False,
                "handler": "ComplexTaskHandler",
                "task_description": task_description,
                "execution_time": execution_time,
                "error": str(e),
                "stage": "error"
            }
            
            self._log_execution(task_description, result)
            return result
    
    async def _demo_complex_task_processing(
        self,
        task_description: str,
        classification: TaskClassification,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Demo版本的复杂任务处理
        
        这里展示复杂任务处理的基本流程，具体实现后续可以扩展
        """
        logger.info("执行复杂任务处理Demo")
        
        # 阶段1: 需求分析
        analysis_result = await self._analyze_requirements(task_description, classification)
        
        # 阶段2: 知识检索
        knowledge_result = await self._retrieve_knowledge(task_description)
        
        # 阶段3: 代码生成
        code_result = await self._generate_code(task_description, analysis_result, knowledge_result)
        
        # 阶段4: 代码执行（模拟）
        execution_result = await self._execute_generated_code(code_result)
        
        return {
            "success": True,
            "handler": "ComplexTaskHandler",
            "task_description": task_description,
            "stages": {
                "analysis": analysis_result,
                "knowledge_retrieval": knowledge_result,
                "code_generation": code_result,
                "code_execution": execution_result
            },
            "final_output": execution_result.get("output", "任务执行完成"),
            "generated_tools": code_result.get("generated_tools", [])
        }
    
    async def _analyze_requirements(
        self, 
        task_description: str, 
        classification: TaskClassification
    ) -> Dict[str, Any]:
        """
        分析任务需求
        
        Args:
            task_description: 任务描述
            classification: 任务分类
            
        Returns:
            需求分析结果
        """
        logger.info("执行需求分析")
        
        # Demo: 简化的需求分析
        return {
            "stage": "requirements_analysis",
            "task_type": classification.category.value,
            "missing_capabilities": classification.missing_capabilities,
            "estimated_complexity": "medium",
            "required_libraries": ["numpy", "pandas", "matplotlib"],  # Demo数据
            "estimated_execution_time": "5-10 minutes"
        }
    
    async def _retrieve_knowledge(self, task_description: str) -> Dict[str, Any]:
        """
        从知识库检索相关知识
        
        Args:
            task_description: 任务描述
            
        Returns:
            知识检索结果
        """
        logger.info("执行知识检索")
        
        # Demo: 模拟知识检索
        if self.knowledge_base:
            # 这里可以集成实际的知识库检索
            relevant_docs = ["demo_doc_1", "demo_doc_2"]
        else:
            relevant_docs = []
        
        return {
            "stage": "knowledge_retrieval",
            "relevant_documents": relevant_docs,
            "knowledge_sources": ["水文建模手册", "Python数据分析指南"],  # Demo数据
            "retrieved_examples": [
                "流量计算示例",
                "数据可视化模板"
            ]
        }
    
    async def _generate_code(
        self,
        task_description: str,
        analysis_result: Dict[str, Any],
        knowledge_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        生成代码工具
        
        Args:
            task_description: 任务描述
            analysis_result: 需求分析结果
            knowledge_result: 知识检索结果
            
        Returns:
            代码生成结果
        """
        logger.info("执行代码生成")
        
        self.code_generation_count += 1
        
        # Demo: 模拟代码生成
        if "可视化" in task_description or "绘图" in task_description:
            generated_code = self._demo_visualization_code()
            tool_type = "visualization"
        elif "分析" in task_description:
            generated_code = self._demo_analysis_code()
            tool_type = "analysis"
        else:
            generated_code = self._demo_generic_code()
            tool_type = "generic"
        
        return {
            "stage": "code_generation",
            "generated_code": generated_code,
            "tool_type": tool_type,
            "generated_tools": [f"custom_tool_{self.code_generation_count}"],
            "code_language": "python",
            "estimated_lines": len(generated_code.split('\n'))
        }
    
    def _demo_visualization_code(self) -> str:
        """Demo可视化代码"""
        return """
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

def create_hydrograph(data_file, output_file='hydrograph.png'):
    \"\"\"创建流量过程线图\"\"\"
    # 读取数据
    data = pd.read_csv(data_file)
    
    # 创建图形
    plt.figure(figsize=(12, 6))
    plt.plot(data['date'], data['flow'], label='观测流量', color='blue')
    if 'simulated_flow' in data.columns:
        plt.plot(data['date'], data['simulated_flow'], label='模拟流量', color='red', linestyle='--')
    
    plt.xlabel('时间')
    plt.ylabel('流量 (m³/s)')
    plt.title('流量过程线')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    # 保存图形
    plt.savefig(output_file, dpi=300)
    plt.close()
    
    return f"流量过程线图已保存至: {output_file}"

# 使用示例
# result = create_hydrograph('flow_data.csv')
# print(result)
"""
    
    def _demo_analysis_code(self) -> str:
        """Demo分析代码"""
        return """
import numpy as np
import pandas as pd
from scipy import stats

def analyze_flow_statistics(data_file):
    \"\"\"分析流量统计特征\"\"\"
    # 读取数据
    data = pd.read_csv(data_file)
    flow = data['flow'].dropna()
    
    # 计算统计指标
    statistics = {
        'mean': np.mean(flow),
        'median': np.median(flow),
        'std': np.std(flow),
        'min': np.min(flow),
        'max': np.max(flow),
        'skewness': stats.skew(flow),
        'kurtosis': stats.kurtosis(flow)
    }
    
    # 计算百分位数
    percentiles = [10, 25, 50, 75, 90, 95, 99]
    for p in percentiles:
        statistics[f'p{p}'] = np.percentile(flow, p)
    
    return statistics

def calculate_flow_correlation(obs_data, sim_data):
    \"\"\"计算观测和模拟流量的相关性\"\"\"
    # 移除缺失值
    valid_mask = ~(np.isnan(obs_data) | np.isnan(sim_data))
    obs_clean = obs_data[valid_mask]
    sim_clean = sim_data[valid_mask]
    
    # 计算各种相关指标
    correlation = {
        'pearson_r': stats.pearsonr(obs_clean, sim_clean)[0],
        'spearman_r': stats.spearmanr(obs_clean, sim_clean)[0],
        'nash_sutcliffe': 1 - np.sum((obs_clean - sim_clean)**2) / np.sum((obs_clean - np.mean(obs_clean))**2),
        'rmse': np.sqrt(np.mean((obs_clean - sim_clean)**2)),
        'mae': np.mean(np.abs(obs_clean - sim_clean))
    }
    
    return correlation

# 使用示例
# stats = analyze_flow_statistics('flow_data.csv')
# print("流量统计特征:", stats)
"""
    
    def _demo_generic_code(self) -> str:
        """Demo通用代码"""
        return """
import numpy as np
import pandas as pd

def process_hydrological_data(input_file, output_file=None):
    \"\"\"处理水文数据的通用函数\"\"\"
    # 读取数据
    data = pd.read_csv(input_file)
    
    # 数据预处理
    # 移除异常值
    for col in data.select_dtypes(include=[np.number]).columns:
        Q1 = data[col].quantile(0.25)
        Q3 = data[col].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        data[col] = data[col].clip(lower_bound, upper_bound)
    
    # 填充缺失值
    data = data.fillna(method='interpolate')
    
    # 添加时间相关特征
    if 'date' in data.columns:
        data['date'] = pd.to_datetime(data['date'])
        data['year'] = data['date'].dt.year
        data['month'] = data['date'].dt.month
        data['day_of_year'] = data['date'].dt.dayofyear
    
    # 保存处理后的数据
    if output_file:
        data.to_csv(output_file, index=False)
        return f"处理后的数据已保存至: {output_file}"
    else:
        return data

# 使用示例
# result = process_hydrological_data('raw_data.csv', 'processed_data.csv')
# print(result)
"""
    
    async def _execute_generated_code(self, code_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行生成的代码（Demo版本 - 不实际执行）
        
        Args:
            code_result: 代码生成结果
            
        Returns:
            执行结果
        """
        logger.info("模拟执行生成的代码")
        
        # Demo: 模拟代码执行
        await asyncio.sleep(1)  # 模拟执行时间
        
        tool_type = code_result.get("tool_type", "generic")
        
        if tool_type == "visualization":
            output = "成功生成流量过程线图，图片已保存至 hydrograph.png"
        elif tool_type == "analysis":
            output = {
                "统计分析": "完成流量统计特征计算",
                "相关性分析": "完成观测与模拟流量相关性分析",
                "主要指标": {"平均流量": 125.3, "Nash系数": 0.78, "RMSE": 15.2}
            }
        else:
            output = "成功处理水文数据，结果已保存"
        
        return {
            "stage": "code_execution",
            "status": "success",
            "output": output,
            "execution_time": 1.0,
            "generated_files": ["result_output.csv", "analysis_report.txt"]
        }


class ManualReviewHandler(BaseTaskHandler):
    """人工审查处理器 - 处理无法自动分类的任务"""
    
    async def handle_task(
        self, 
        task_description: str, 
        classification: TaskClassification,
        **kwargs
    ) -> Dict[str, Any]:
        """
        处理需要人工审查的任务
        
        Args:
            task_description: 任务描述
            classification: 任务分类结果
            **kwargs: 额外参数
            
        Returns:
            处理结果
        """
        logger.info(f"任务需要人工审查: {task_description}")
        
        result = {
            "success": False,
            "handler": "ManualReviewHandler",
            "task_description": task_description,
            "message": "此任务需要人工审查以确定适当的处理方式",
            "suggestions": [
                "请提供更详细的任务描述",
                "明确指定需要使用的工具或方法",
                "联系系统管理员进行任务分类"
            ],
            "classification_info": {
                "complexity": classification.complexity.value,
                "category": classification.category.value,
                "confidence": classification.confidence,
                "reasoning": classification.reasoning
            }
        }
        
        self._log_execution(task_description, result)
        return result


# 工厂函数
def create_task_handler(
    handler_type: str,
    **kwargs
) -> BaseTaskHandler:
    """
    创建任务处理器
    
    Args:
        handler_type: 处理器类型 ("simple", "complex", "manual")
        **kwargs: 处理器特定参数
        
    Returns:
        任务处理器实例
    """
    if handler_type == "simple":
        return SimpleTaskHandler(
            server_command=kwargs.get("server_command"),
            enable_debug=kwargs.get("enable_debug", False)
        )
    elif handler_type == "complex":
        return ComplexTaskHandler(
            llm=kwargs.get("llm"),
            knowledge_base=kwargs.get("knowledge_base"),
            enable_debug=kwargs.get("enable_debug", False)
        )
    elif handler_type == "manual":
        return ManualReviewHandler(
            enable_debug=kwargs.get("enable_debug", False)
        )
    else:
        raise ValueError(f"未知的处理器类型: {handler_type}")


# 示例使用
async def main():
    """示例：如何使用任务处理器"""
    import sys
    from pathlib import Path
    
    # 添加项目路径
    repo_path = Path(__file__).parent.parent
    sys.path.append(str(repo_path))
    
    from langchain_ollama import ChatOllama
    from .task_dispatcher import TaskClassification, TaskComplexity, TaskCategory
    
    logging.basicConfig(level=logging.INFO)
    
    # 创建测试分类结果
    simple_classification = TaskClassification(
        complexity=TaskComplexity.SIMPLE,
        category=TaskCategory.PARAMETER_QUERY,
        confidence=0.9,
        reasoning="获取模型参数是简单任务",
        required_tools=["get_model_params"]
    )
    
    complex_classification = TaskClassification(
        complexity=TaskComplexity.COMPLEX,
        category=TaskCategory.VISUALIZATION,
        confidence=0.8,
        reasoning="可视化需要生成代码",
        required_tools=[],
        missing_capabilities=["绘图功能"]
    )
    
    # 测试简单任务处理器
    print("测试简单任务处理器...")
    simple_handler = SimpleTaskHandler(enable_debug=True)
    await simple_handler.setup()
    
    simple_result = await simple_handler.handle_task(
        "获取GR4J模型参数",
        simple_classification
    )
    print(f"简单任务结果: {simple_result['success']}")
    
    await simple_handler.cleanup()
    
    # 测试复杂任务处理器
    print("\n测试复杂任务处理器...")
    llm = ChatOllama(model="granite3-dense:8b", temperature=0.1)
    complex_handler = ComplexTaskHandler(llm, enable_debug=True)
    
    complex_result = await complex_handler.handle_task(
        "绘制流量过程线图",
        complex_classification
    )
    print(f"复杂任务结果: {complex_result['success']}")


if __name__ == "__main__":
    asyncio.run(main())
