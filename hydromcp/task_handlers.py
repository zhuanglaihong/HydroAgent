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
        self.available_tools = {}
    
    async def setup(self) -> bool:
        """设置处理器"""
        try:
            self.connected = await self.mcp_client.connect()
            if self.connected:
                # 获取并缓存可用工具信息
                tools = self.mcp_client.get_available_tools()  # 移除await，这是同步方法
                if tools:
                    self.available_tools = {
                        tool.get("name", f"tool_{i}"): tool for i, tool in enumerate(tools)
                    }
                    logger.info(f"简单任务处理器设置成功，可用工具: {list(self.available_tools.keys())}")
                else:
                    logger.warning("未获取到可用工具")
                    self.available_tools = {}
            return self.connected
        except Exception as e:
            logger.error(f"简单任务处理器设置失败: {e}")
            return False
    
    async def cleanup(self):
        """清理资源"""
        await self.mcp_client.disconnect()
        self.connected = False
        self.available_tools = {}
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行指定的工具
        
        Args:
            tool_name: 工具名称
            parameters: 工具参数
            
        Returns:
            执行结果
        """
        if not self.connected:
            raise RuntimeError("MCP客户端未连接")
        
        if tool_name not in self.available_tools:
            raise ValueError(f"未知的工具: {tool_name}")
        
        try:
            # 验证参数
            tool_info = self.available_tools[tool_name]
            validated_params = self._validate_parameters(tool_info, parameters)
            
            # 调用工具
            result = await self.mcp_client.call_tool(tool_name, validated_params)  # call_tool是异步方法
            
            if isinstance(result, dict):
                result["tool_name"] = tool_name
                result["parameters_used"] = validated_params
            else:
                result = {
                    "success": True,
                    "tool_name": tool_name,
                    "parameters_used": validated_params,
                    "result": result
                }
            
            return result
            
        except Exception as e:
            logger.error(f"工具 {tool_name} 执行失败: {e}")
            return {
                "success": False,
                "tool_name": tool_name,
                "error": str(e),
                "parameters_used": parameters
            }
    
    def _validate_parameters(self, tool_info: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """验证并处理工具参数"""
        validated = parameters.copy()  # 先复制所有参数
        
        # 获取工具的输入模式
        input_schema = tool_info.get("inputSchema", {})
        if isinstance(input_schema, dict):
            required_params = input_schema.get("required", [])
            properties = input_schema.get("properties", {})
            
            # 检查必需参数
            for param in required_params:
                if param not in parameters:
                    raise ValueError(f"缺少必需参数: {param}")
            
            # 验证参数类型（如果定义了properties）
            for param, value in parameters.items():
                if param in properties:
                    prop_info = properties[param]
                    # 这里可以添加更详细的类型验证
                    # 目前只是简单的存在性检查
        
        return validated
    
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
            tool_parameters = kwargs.get('tool_parameters', {})
            
            # 依次执行需要的工具
            for tool_name in classification.required_tools:
                logger.info(f"执行工具: {tool_name}")
                
                # 获取工具特定参数
                params = tool_parameters.get(tool_name, {})
                if not params:
                    # 使用默认参数
                    params = self._get_tool_parameters(tool_name, task_description, {})
                
                # 执行工具
                tool_result = await self.execute_tool(tool_name, params)
                results.append(tool_result)
                
                if self.enable_debug:
                    logger.debug(f"工具 {tool_name} 执行结果: {tool_result}")
                
                # 如果工具执行失败，记录错误并继续
                if not tool_result.get("success", True):
                    logger.warning(f"工具 {tool_name} 执行失败: {tool_result.get('error')}")
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # 检查是否所有工具都执行成功
            all_success = all(r.get("success", True) for r in results)
            
            result = {
                "success": all_success,
                "handler": "SimpleTaskHandler",
                "task_description": task_description,
                "execution_time": execution_time,
                "tools_executed": len(results),
                "results": results,
                "summary": self._generate_summary(results)
            }
            
            self._log_execution(task_description, result)
            
            if all_success:
                logger.info(f"简单任务处理完成，执行时间: {execution_time:.2f}s")
            else:
                logger.warning(f"简单任务部分失败，执行时间: {execution_time:.2f}s")
            
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
                "results": results if 'results' in locals() else []
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
            # 数据读取工具
            "read_camels_data": {
                "basin_id": "11532500",
                "data_type": "daily"
            },
            "read_netcdf": {
                "file_path": "data/camels_11532500/attributes.nc"
            },
            "read_csv": {
                "file_path": "data/camels_11532500/basin_11532500.csv"
            },
            
            # 数据处理工具
            "process_and_save_data_as_nc": {
                "input_dir": "data/camels_11532500",
                "output_dir": "data/processed",
                "basin_id": "11532500"
            },
            "calculate_statistics": {
                "data_file": "data/camels_11532500/basin_11532500.csv",
                "variables": ["prcp", "pet", "flow"]
            },
            
            # 模型工具
            "gr4j_calibration": {
                "data_dir": "data/camels_11532500",
                "output_dir": "result/model_calibration",
                "algorithm": "sceua",
                "objective": "nse",
                "max_iterations": 1000
            },
            "gr4j_simulation": {
                "parameters": None,  # 需要从率定结果获取
                "data_file": "data/camels_11532500/basin_11532500.csv"
            },
            "model_evaluation": {
                "obs_data": None,  # 需要从数据文件获取
                "sim_data": None,  # 需要从模拟结果获取
                "metrics": ["nse", "rmse", "kge", "bias"]
            },
            
            # 可视化工具
            "plot_hydrograph": {
                "data_file": "data/camels_11532500/basin_11532500.csv",
                "output_dir": "result/figures",
                "show_statistics": True
            },
            "plot_evaluation_results": {
                "evaluation_file": "result/model_calibration/evaluation_metrics.json",
                "output_dir": "result/figures"
            }
        }
        
        # 获取工具默认参数
        params = default_parameters.get(tool_name, {}).copy()
        
        # 如果工具信息可用，添加必需参数的默认值
        if tool_name in self.available_tools:
            tool_info = self.available_tools[tool_name]
            input_schema = tool_info.get("inputSchema", {})
            required_params = input_schema.get("required", [])
            
            # 确保所有必需参数都有值
            for param in required_params:
                if param not in params:
                    # 使用一些启发式规则设置默认值
                    if "file" in param or "path" in param:
                        params[param] = f"data/camels_11532500/basin_11532500.csv"
                    elif "dir" in param:
                        params[param] = "data/camels_11532500"
                    elif "name" in param:
                        params[param] = "gr4j"
                    elif "id" in param:
                        params[param] = "11532500"
                    else:
                        # 对于其他参数，设置None或空字符串
                        params[param] = None
        
        return params
    
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
    
    def __init__(self, llm=None, knowledge_base=None, enable_debug: bool = False):
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
        self.is_setup = False
    
    async def setup(self) -> bool:
        """设置复杂任务处理器"""
        try:
            # 这里可以添加LLM连接检查等初始化逻辑
            self.is_setup = True
            logger.info("复杂任务处理器设置成功")
            return True
        except Exception as e:
            logger.error(f"复杂任务处理器设置失败: {e}")
            return False
    
    async def cleanup(self):
        """清理资源"""
        self.is_setup = False
        logger.info("复杂任务处理器清理完成")
    
    async def handle_complex_task(self, task_description: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理复杂任务的新接口（适配新工作流格式）
        
        Args:
            task_description: 任务描述
            parameters: 任务参数
            
        Returns:
            处理结果
        """
        if not self.is_setup:
            raise RuntimeError("复杂任务处理器未设置")
        
        return await self._demo_complex_task_processing_v2(task_description, parameters)
    
    async def _demo_complex_task_processing_v2(self, task_description: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        新版本的复杂任务处理demo（适配新工作流格式）
        
        Args:
            task_description: 任务描述
            parameters: 任务参数
            
        Returns:
            处理结果
        """
        logger.info(f"开始处理复杂任务V2: {task_description}")
        
        # 模拟复杂任务处理过程
        start_time = datetime.now()
        
        # 根据任务描述判断复杂任务类型
        if any(keyword in task_description.lower() for keyword in ["率定", "calibration", "parameter", "optimization"]):
            return await self._simulate_model_calibration(parameters)
        elif any(keyword in task_description.lower() for keyword in ["评估", "evaluation", "assess"]):
            return await self._simulate_model_evaluation(parameters)
        elif any(keyword in task_description.lower() for keyword in ["分析", "analysis", "compute"]):
            return await self._simulate_complex_analysis(parameters)
        else:
            return await self._simulate_generic_complex_task(task_description, parameters)
    
    async def _simulate_model_calibration(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """模拟模型率定复杂任务"""
        logger.info("执行模型率定复杂任务（示例）")
        
        # 模拟率定过程
        await asyncio.sleep(1)  # 模拟计算时间
        
        return {
            "success": True,
            "task_type": "model_calibration",
            "result": {
                "calibrated_parameters": {
                    "X1": 342.5,  # 产流系数
                    "X2": -0.12,  # 地下水交换系数
                    "X3": 68.3,   # 汇流水库容量
                    "X4": 1.39    # 单位线时间常数
                },
                "objective_function": "NSE",
                "objective_value": 0.823,
                "optimization_info": {
                    "algorithm": "SCE-UA",
                    "iterations": 150,
                    "convergence": True,
                    "function_evaluations": 2250
                },
                "calibration_period": "2010-2015",
                "performance_metrics": {
                    "NSE": 0.823,
                    "RMSE": 12.45,
                    "BIAS": 0.08,
                    "R2": 0.851
                }
            },
            "message": "GR4J模型率定完成（示例结果）",
            "generated_code": "# 示例：生成的模型率定代码\ndef calibrate_gr4j_model(data, bounds):\n    # 使用SCE-UA算法进行参数优化\n    pass",
            "execution_time": 1.0,
            "metadata": {
                "is_mock": True,
                "complex_task_type": "calibration",
                "generated_tool": "gr4j_calibration_enhanced"
            }
        }
    
    async def _simulate_model_evaluation(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """模拟模型评估复杂任务"""
        logger.info("执行模型评估复杂任务（示例）")
        
        await asyncio.sleep(0.8)  # 模拟计算时间
        
        return {
            "success": True,
            "task_type": "model_evaluation",
            "result": {
                "evaluation_metrics": {
                    "NSE": 0.789,
                    "KGE": 0.812,
                    "RMSE": 15.32,
                    "MAE": 11.67,
                    "BIAS": -0.05,
                    "R2": 0.834,
                    "PBIAS": -4.8
                },
                "time_series_analysis": {
                    "peak_flow_accuracy": 0.85,
                    "low_flow_accuracy": 0.78,
                    "seasonal_performance": {
                        "spring": 0.82,
                        "summer": 0.75,
                        "autumn": 0.81,
                        "winter": 0.79
                    }
                },
                "validation_period": "2016-2020",
                "model_reliability": "Good"
            },
            "message": "模型评估分析完成（示例结果）",
            "generated_code": "# 示例：生成的模型评估代码\ndef evaluate_model_performance(obs, sim):\n    # 计算多种评估指标\n    pass",
            "execution_time": 0.8,
            "metadata": {
                "is_mock": True,
                "complex_task_type": "evaluation",
                "generated_tool": "model_evaluation_enhanced"
            }
        }
    
    async def _simulate_complex_analysis(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """模拟复杂分析任务"""
        logger.info("执行复杂分析任务（示例）")
        
        await asyncio.sleep(0.6)  # 模拟计算时间
        
        return {
            "success": True,
            "task_type": "complex_analysis",
            "result": {
                "analysis_results": {
                    "statistical_summary": {
                        "mean": 45.67,
                        "std": 23.45,
                        "skewness": 1.23,
                        "kurtosis": 0.87
                    },
                    "trend_analysis": {
                        "trend": "increasing",
                        "slope": 0.12,
                        "p_value": 0.03,
                        "significance": "significant"
                    },
                    "correlation_matrix": [
                        [1.0, 0.78, -0.45],
                        [0.78, 1.0, -0.32],
                        [-0.45, -0.32, 1.0]
                    ]
                },
                "computed_indices": [
                    {"name": "Aridity Index", "value": 1.25},
                    {"name": "Seasonality Index", "value": 0.67},
                    {"name": "Flow Variability", "value": 0.89}
                ]
            },
            "message": "复杂数据分析完成（示例结果）",
            "generated_code": "# 示例：生成的复杂分析代码\ndef perform_advanced_analysis(data):\n    # 执行高级统计分析\n    pass",
            "execution_time": 0.6,
            "metadata": {
                "is_mock": True,
                "complex_task_type": "analysis",
                "generated_tool": "advanced_analysis_tool"
            }
        }
    
    async def _simulate_generic_complex_task(self, task_description: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """模拟通用复杂任务"""
        logger.info(f"执行通用复杂任务（示例）: {task_description}")
        
        await asyncio.sleep(0.5)  # 模拟计算时间
        
        return {
            "success": True,
            "task_type": "generic_complex",
            "result": {
                "task_description": task_description,
                "processing_status": "completed",
                "output_data": {
                    "processed_parameters": parameters,
                    "computation_results": [1.23, 4.56, 7.89],
                    "status_code": 200
                }
            },
            "message": f"复杂任务处理完成: {task_description}（示例结果）",
            "generated_code": f"# 示例：为任务生成的代码\ndef handle_{task_description.replace(' ', '_').lower()}():\n    # 自动生成的处理逻辑\n    pass",
            "execution_time": 0.5,
            "metadata": {
                "is_mock": True,
                "complex_task_type": "generic",
                "generated_tool": f"auto_generated_tool_{int(datetime.now().timestamp())}"
            }
        }
    
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
