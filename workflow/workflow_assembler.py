"""
工作流组装与优化模块

功能：将LLM输出的可能不规范的JSON进行结构化解析、验证和优化

处理步骤：
1. 解析与清洗： 解析LLM的回复，提取出符合规范的JSON部分
2. 可行性验证： 检查所有action字段是否在系统预定义的工具/函数列表中
3. 优化： 识别可并行执行的任务（dependencies为空或已满足）

Author: Assistant
Date: 2025-01-20
"""

import logging
import json
import re
import uuid
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# 导入路径处理工具
sys.path.append(str(Path(__file__).parent.parent))
from utils.filepath import correct_path, normalize_path, path_exists

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """任务类型枚举"""
    SIMPLE_ACTION = "simple_action"         # 简单操作
    COMPLEX_REASONING = "complex_reasoning" # 复杂推理


class ValidationStatus(Enum):
    """验证状态枚举"""
    VALID = "valid"                 # 有效
    WARNING = "warning"             # 警告
    ERROR = "error"                 # 错误
    MISSING = "missing"             # 缺失


@dataclass
class ValidationIssue:
    """验证问题"""
    issue_type: ValidationStatus    # 问题类型
    field: str                      # 问题字段
    message: str                    # 问题描述
    suggestion: Optional[str] = None # 修复建议
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据


@dataclass
class WorkflowTask:
    """工作流任务"""
    task_id: str                            # 任务ID
    name: str                               # 任务名称
    description: str                        # 任务描述
    action: str                             # 操作/函数名
    task_type: TaskType                     # 任务类型
    parameters: Dict[str, Any] = field(default_factory=dict)    # 参数
    dependencies: List[str] = field(default_factory=list)       # 依赖任务ID
    conditions: Dict[str, Any] = field(default_factory=dict)    # 执行条件
    expected_output: str = ""               # 期望输出
    priority: int = 1                       # 优先级（1-10）
    timeout: Optional[int] = None           # 超时时间（秒）
    retry_count: int = 0                    # 重试次数
    metadata: Dict[str, Any] = field(default_factory=dict)      # 元数据

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "action": self.action,
            "task_type": self.task_type.value,
            "parameters": self.parameters,
            "dependencies": self.dependencies,
            "conditions": self.conditions,
            "expected_output": self.expected_output,
            "priority": self.priority,
            "timeout": self.timeout,
            "retry_count": self.retry_count,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowTask":
        """从字典创建"""
        return cls(
            task_id=data.get("task_id", str(uuid.uuid4())),
            name=data.get("name", "未命名任务"),
            description=data.get("description", ""),
            action=data.get("action", "unknown"),
            task_type=TaskType(data.get("task_type", "simple_action")),
            parameters=data.get("parameters", {}),
            dependencies=data.get("dependencies", []),
            conditions=data.get("conditions", {}),
            expected_output=data.get("expected_output", ""),
            priority=data.get("priority", 1),
            timeout=data.get("timeout"),
            retry_count=data.get("retry_count", 0),
            metadata=data.get("metadata", {})
        )


@dataclass
class AssembledWorkflow:
    """组装后的工作流"""
    workflow_id: str                        # 工作流ID
    name: str                               # 工作流名称
    description: str                        # 工作流描述
    tasks: List[WorkflowTask]               # 任务列表
    execution_order: List[List[str]]        # 执行顺序（支持并行）
    validation_issues: List[ValidationIssue] = field(default_factory=list)  # 验证问题
    metadata: Dict[str, Any] = field(default_factory=dict)                  # 元数据
    created_time: datetime = field(default_factory=datetime.now)            # 创建时间
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "tasks": [task.to_dict() for task in self.tasks],
            "execution_order": self.execution_order,
            "validation_issues": [
                {
                    "issue_type": issue.issue_type.value,
                    "field": issue.field,
                    "message": issue.message,
                    "suggestion": issue.suggestion,
                    "metadata": issue.metadata
                } for issue in self.validation_issues
            ],
            "metadata": self.metadata,
            "created_time": self.created_time.isoformat()
        }

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class ToolRegistry:
    """工具注册表"""
    
    def __init__(self):
        """初始化工具注册表"""
        self.available_tools = self._init_available_tools()
        self.tool_categories = self._init_tool_categories()
        # 导入工具字典
        self._load_hydro_tools()
    
    def _load_hydro_tools(self):
        """加载HydroMCP工具字典"""
        try:
            import sys
            from pathlib import Path
            # 添加hydromcp路径
            hydromcp_path = Path(__file__).parent.parent / "hydromcp"
            sys.path.append(str(hydromcp_path))
            
            from tools_dict import (
                HYDRO_TOOLS, get_all_tool_names, 
                map_workflow_action_to_tool, get_unsupported_actions
            )
            
            self.hydro_tools = HYDRO_TOOLS
            self.get_all_tool_names = get_all_tool_names
            self.map_workflow_action_to_tool = map_workflow_action_to_tool
            self.get_unsupported_actions = get_unsupported_actions
            
            # 添加实际可用的HydroMCP工具
            self.actual_available_tools = set(get_all_tool_names())
            logger.info(f"加载了 {len(self.actual_available_tools)} 个HydroMCP工具: {', '.join(self.actual_available_tools)}")
            
        except ImportError as e:
            logger.warning(f"无法加载HydroMCP工具字典: {e}")
            self.hydro_tools = {}
            self.actual_available_tools = set()
    
    def _init_available_tools(self) -> Set[str]:
        """初始化可用工具列表（保持兼容性的通用工具）"""
        return {
            # 数据操作 - 通用概念
            "load_data", "save_data", "read_csv", "write_csv", "read_netcdf", "write_netcdf",
            "load_camels_data", "fetch_data", "download_data", "export_data",
            
            # 数据分析
            "analyze_data", "calculate_stats", "correlation_analysis", "time_series_analysis",
            "data_summary", "data_quality_check", "missing_value_analysis",
            
            # 模型相关 - 通用概念
            "calibrate_model", "run_model", "simulate", "predict", "forecast",
            "gr4j_calibration", "gr4j_simulation", "xaj_calibration", "xaj_simulation",
            "lstm_training", "lstm_prediction", "optimize_parameters",
            
            # 评估指标
            "calculate_nse", "calculate_rmse", "calculate_mae", "calculate_r2",
            "evaluate_model", "performance_metrics", "model_assessment",
            
            # 可视化
            "plot_data", "create_chart", "visualize_results", "plot_time_series",
            "plot_correlation", "plot_scatter", "plot_histogram", "create_dashboard",
            
            # 文件操作
            "create_directory", "copy_file", "move_file", "delete_file",
            "compress_files", "extract_files", "list_files",
            
            # 系统操作
            "execute_command", "set_environment", "check_dependencies",
            "install_package", "configure_system", "manage_resources",
            
            # 报告生成
            "generate_report", "create_summary", "export_results",
            "write_documentation", "create_presentation",
            
            # 控制流
            "conditional_execute", "loop_execute", "parallel_execute",
            "wait_for_condition", "retry_on_failure", "validate_result"
        }
    
    def _init_tool_categories(self) -> Dict[str, List[str]]:
        """初始化工具分类"""
        return {
            "data_operations": [
                "load_data", "save_data", "read_csv", "write_csv", "read_netcdf", "write_netcdf",
                "load_camels_data", "fetch_data", "download_data", "export_data"
            ],
            "data_analysis": [
                "analyze_data", "calculate_stats", "correlation_analysis", "time_series_analysis",
                "data_summary", "data_quality_check", "missing_value_analysis"
            ],
            "modeling": [
                "calibrate_model", "run_model", "simulate", "predict", "forecast",
                "gr4j_calibration", "gr4j_simulation", "xaj_calibration", "xaj_simulation",
                "lstm_training", "lstm_prediction", "optimize_parameters"
            ],
            "evaluation": [
                "calculate_nse", "calculate_rmse", "calculate_mae", "calculate_r2",
                "evaluate_model", "performance_metrics", "model_assessment"
            ],
            "visualization": [
                "plot_data", "create_chart", "visualize_results", "plot_time_series",
                "plot_correlation", "plot_scatter", "plot_histogram", "create_dashboard"
            ],
            "file_operations": [
                "create_directory", "copy_file", "move_file", "delete_file",
                "compress_files", "extract_files", "list_files"
            ],
            "system_operations": [
                "execute_command", "set_environment", "check_dependencies",
                "install_package", "configure_system", "manage_resources"
            ],
            "reporting": [
                "generate_report", "create_summary", "export_results",
                "write_documentation", "create_presentation"
            ],
            "control_flow": [
                "conditional_execute", "loop_execute", "parallel_execute",
                "wait_for_condition", "retry_on_failure", "validate_result"
            ]
        }
    
    def is_tool_available(self, tool_name: str) -> bool:
        """检查工具是否可用"""
        # 首先检查实际可用的HydroMCP工具
        if hasattr(self, 'actual_available_tools') and tool_name in self.actual_available_tools:
            return True
        # 然后检查通用工具列表（向后兼容）
        return tool_name in self.available_tools
    
    def get_tool_category(self, tool_name: str) -> Optional[str]:
        """获取工具分类"""
        for category, tools in self.tool_categories.items():
            if tool_name in tools:
                return category
        return None
    
    def suggest_alternative_tools(self, tool_name: str) -> List[str]:
        """建议替代工具"""
        suggestions = []
        
        # 首先尝试使用HydroMCP工具映射
        if hasattr(self, 'map_workflow_action_to_tool'):
            mapped_tool = self.map_workflow_action_to_tool(tool_name)
            if mapped_tool and mapped_tool in self.actual_available_tools:
                suggestions.append(mapped_tool)
                logger.info(f"为动作 '{tool_name}' 找到映射工具: {mapped_tool}")
        
        # 如果没有直接映射，进行相似性匹配
        if not suggestions:
            # 在实际可用的HydroMCP工具中查找
            if hasattr(self, 'actual_available_tools'):
                for available_tool in self.actual_available_tools:
                    if self._calculate_similarity(tool_name, available_tool) > 0.6:
                        suggestions.append(available_tool)
            
            # 如果仍然没有找到，在通用工具中查找
            if not suggestions:
                for available_tool in self.available_tools:
                    if self._calculate_similarity(tool_name, available_tool) > 0.6:
                        suggestions.append(available_tool)
        
        return suggestions[:3]  # 返回前3个建议
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """计算字符串相似度"""
        # 简单的Levenshtein距离计算
        if len(str1) == 0:
            return len(str2)
        if len(str2) == 0:
            return len(str1)
        
        matrix = [[0] * (len(str2) + 1) for _ in range(len(str1) + 1)]
        
        for i in range(len(str1) + 1):
            matrix[i][0] = i
        for j in range(len(str2) + 1):
            matrix[0][j] = j
        
        for i in range(1, len(str1) + 1):
            for j in range(1, len(str2) + 1):
                if str1[i-1] == str2[j-1]:
                    cost = 0
                else:
                    cost = 1
                matrix[i][j] = min(
                    matrix[i-1][j] + 1,      # deletion
                    matrix[i][j-1] + 1,      # insertion
                    matrix[i-1][j-1] + cost  # substitution
                )
        
        max_len = max(len(str1), len(str2))
        return 1.0 - (matrix[len(str1)][len(str2)] / max_len)


class WorkflowAssembler:
    """工作流组装器"""
    
    def __init__(self, tool_registry: Optional[ToolRegistry] = None):
        """
        初始化工作流组装器
        
        Args:
            tool_registry: 工具注册表，如果为None则创建默认注册表
        """
        self.tool_registry = tool_registry or ToolRegistry()
        
        logger.info("工作流组装器初始化完成")
    
    def assemble_workflow(self, raw_plan: str, metadata: Optional[Dict[str, Any]] = None) -> AssembledWorkflow:
        """
        组装工作流
        
        Args:
            raw_plan: LLM生成的原始JSON计划
            metadata: 元数据
            
        Returns:
            AssembledWorkflow: 组装后的工作流
        """
        try:
            # 第一步：解析与清洗
            logger.info("开始解析和清洗工作流计划...")
            parsed_plan = self._parse_and_clean_plan(raw_plan)
            
            # 第二步：创建工作流任务
            logger.info("创建工作流任务...")
            tasks = self._create_workflow_tasks(parsed_plan)
            
            # 第三步：验证工作流
            logger.info("验证工作流可行性...")
            validation_issues = self._validate_workflow(tasks)
            
            # 第四步：修复常见问题
            logger.info("修复常见问题...")
            tasks = self._fix_common_issues(tasks, validation_issues)
            
            # 第五步：优化工作流
            logger.info("优化工作流...")
            execution_order = self._optimize_execution_order(tasks)
            
            # 第六步：创建最终工作流
            workflow = AssembledWorkflow(
                workflow_id=parsed_plan.get("workflow_id", str(uuid.uuid4())),
                name=parsed_plan.get("name", "未命名工作流"),
                description=parsed_plan.get("description", ""),
                tasks=tasks,
                execution_order=execution_order,
                validation_issues=validation_issues,
                metadata={
                    **(metadata or {}),
                    **(parsed_plan.get("metadata", {})),
                    "assembly_time": datetime.now().isoformat(),
                    "total_tasks": len(tasks),
                    "validation_errors": len([i for i in validation_issues if i.issue_type == ValidationStatus.ERROR]),
                    "validation_warnings": len([i for i in validation_issues if i.issue_type == ValidationStatus.WARNING])
                }
            )
            
            logger.info(f"工作流组装完成: {workflow.name} ({len(tasks)}个任务)")
            return workflow
            
        except Exception as e:
            logger.error(f"工作流组装失败: {str(e)}")
            # 返回空工作流
            return self._create_empty_workflow(raw_plan, str(e))
    
    def _parse_and_clean_plan(self, raw_plan: str) -> Dict[str, Any]:
        """解析和清洗原始计划"""
        try:
            logger.info(f"开始解析原始计划，长度: {len(raw_plan)}")
            logger.info(f"原始计划内容: {raw_plan}...")  
            
            # 尝试直接解析JSON
            if raw_plan.strip().startswith('{'):
                parsed = json.loads(raw_plan)
                logger.info(f"直接JSON解析成功，包含 {len(parsed.get('tasks', []))} 个任务")
                return parsed
            
            # 尝试提取JSON部分 - 使用更强大的正则表达式匹配嵌套JSON
            # 先尝试找到完整的JSON对象（从第一个{到最后一个}）
            json_start = raw_plan.find('{')
            if json_start != -1:
                # 从第一个{开始，尝试找到匹配的}
                brace_count = 0
                json_end = -1
                for i in range(json_start, len(raw_plan)):
                    if raw_plan[i] == '{':
                        brace_count += 1
                    elif raw_plan[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break
                
                if json_end != -1:
                    json_candidate = raw_plan[json_start:json_end]
                    try:
                        parsed = json.loads(json_candidate)
                        if isinstance(parsed, dict) and "tasks" in parsed:
                            logger.info(f"完整JSON解析成功，包含 {len(parsed.get('tasks', []))} 个任务")
                            return parsed
                        else:
                            logger.debug("完整JSON不包含tasks字段")
                    except json.JSONDecodeError as e:
                        logger.debug(f"完整JSON解析失败: {str(e)}")
            
            # 如果完整JSON解析失败，回退到原来的正则表达式方法
            json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
            json_matches = re.findall(json_pattern, raw_plan, re.DOTALL)
            logger.info(f"找到 {len(json_matches)} 个JSON候选片段")
            
            for i, json_match in enumerate(json_matches):
                try:
                    parsed = json.loads(json_match)
                    if isinstance(parsed, dict) and "tasks" in parsed:
                        logger.info(f"第{i+1}个JSON片段解析成功，包含 {len(parsed.get('tasks', []))} 个任务")
                        return parsed
                    else:
                        logger.debug(f"第{i+1}个JSON片段不包含tasks字段")
                except json.JSONDecodeError as e:
                    logger.debug(f"第{i+1}个JSON片段解析失败: {str(e)}")
                    continue
            
            # 如果都失败了，尝试修复常见的JSON错误
            return self._fix_json_errors(raw_plan)
            
        except Exception as e:
            logger.error(f"JSON解析失败: {str(e)}")
            logger.warning("将使用回退计划")
            return self._create_fallback_plan()
    
    def _fix_json_errors(self, raw_plan: str) -> Dict[str, Any]:
        """修复常见的JSON错误"""
        try:
            # 移除注释
            cleaned = re.sub(r'//.*?\n', '\n', raw_plan)
            cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL)
            
            # 修复单引号
            cleaned = cleaned.replace("'", '"')
            
            # 修复多余的逗号
            cleaned = re.sub(r',\s*}', '}', cleaned)
            cleaned = re.sub(r',\s*]', ']', cleaned)
            
            # 尝试解析
            return json.loads(cleaned)
            
        except Exception:
            return self._create_fallback_plan()
    
    def _create_fallback_plan(self) -> Dict[str, Any]:
        """创建回退计划"""
        return {
            "workflow_id": str(uuid.uuid4()),
            "name": "回退工作流",
            "description": "由于解析失败而创建的回退工作流",
            "tasks": [
                {
                    "task_id": "fallback_task",
                    "name": "回退任务",
                    "description": "需要手动配置的回退任务",
                    "action": "manual_configuration",
                    "task_type": "simple_action",
                    "parameters": {},
                    "dependencies": [],
                    "conditions": {},
                    "expected_output": "手动配置结果"
                }
            ],
            "metadata": {
                "created_time": datetime.now().isoformat(),
                "is_fallback": True
            }
        }
    
    def _create_workflow_tasks(self, parsed_plan: Dict[str, Any]) -> List[WorkflowTask]:
        """创建工作流任务"""
        tasks = []
        task_data_list = parsed_plan.get("tasks", [])
        
        for i, task_data in enumerate(task_data_list):
            try:
                # 确保task_id唯一
                if not task_data.get("task_id"):
                    task_data["task_id"] = f"task_{i+1}_{int(datetime.now().timestamp())}"
                
                # 标准化task_type
                task_type_str = task_data.get("task_type", "simple_action")
                if task_type_str not in ["simple_action", "complex_reasoning"]:
                    task_type_str = "simple_action"
                
                # 规范化任务参数中的路径
                task_data = self._normalize_task_paths(task_data)
                
                task = WorkflowTask.from_dict(task_data)
                tasks.append(task)
                
            except Exception as e:
                logger.warning(f"任务创建失败 (第{i+1}个): {str(e)}")
                # 创建默认任务
                fallback_task = WorkflowTask(
                    task_id=f"fallback_task_{i+1}",
                    name=f"任务{i+1}",
                    description="解析失败的任务",
                    action="manual_configuration",
                    task_type=TaskType.SIMPLE_ACTION
                )
                tasks.append(fallback_task)
        
        return tasks
    
    def _normalize_task_paths(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        规范化任务参数中的路径
        
        Args:
            task_data: 任务数据
            
        Returns:
            路径规范化后的任务数据
        """
        try:
            action = task_data.get("action", "")
            parameters = task_data.get("parameters", {}).copy()
            
            # 根据不同的工具类型处理路径参数
            if action == "prepare_data":
                # 处理数据目录路径
                if "data_dir" in parameters:
                    original_path = parameters["data_dir"]
                    normalized_path = self._normalize_data_path(original_path)
                    parameters["data_dir"] = normalized_path
                    logger.info(f"路径规范化: {original_path} -> {normalized_path}")
                    
            elif action == "calibrate_model":
                # 处理数据目录路径
                if "data_dir" in parameters:
                    original_path = parameters["data_dir"]
                    normalized_path = self._normalize_data_path(original_path)
                    parameters["data_dir"] = normalized_path
                    logger.info(f"路径规范化: {original_path} -> {normalized_path}")
                
                # 处理结果目录路径
                if "result_dir" in parameters:
                    original_path = parameters["result_dir"]
                    normalized_path = self._normalize_result_path(original_path)
                    parameters["result_dir"] = normalized_path
                    logger.info(f"路径规范化: {original_path} -> {normalized_path}")
                    
            elif action == "evaluate_model":
                # 处理结果目录路径
                if "result_dir" in parameters:
                    original_path = parameters["result_dir"]
                    normalized_path = self._normalize_result_path(original_path)
                    parameters["result_dir"] = normalized_path
                    logger.info(f"路径规范化: {original_path} -> {normalized_path}")
            
            # 更新任务数据
            task_data = task_data.copy()
            task_data["parameters"] = parameters
            
            return task_data
            
        except Exception as e:
            logger.warning(f"路径规范化失败: {e}")
            return task_data
    

    def _normalize_data_path(self, path: str) -> str:
        """
        规范化数据路径
        
        Args:
            path: 原始路径
                
        Returns:
            规范化后的绝对路径
        """
        try:
            # 项目根目录
            project_root = Path(__file__).parent.parent
            
            # 1. 清理路径：移除多余空格和引号
            clean_path = path.strip().strip('"').strip("'")
            
            # 2. 处理特殊标识符（如CAMELS站点ID）
            if re.search(r'\b11532500\b', clean_path) or re.search(r'\bcamels_dataset\b', clean_path, re.IGNORECASE):
                return str(project_root / "data" / "camels_11532500")
            
            # 3. 处理Windows风格的路径分隔符
            if '\\' in clean_path:
                clean_path = clean_path.replace('\\', '/')
            
            # 4. 处理相对路径
            if not os.path.isabs(clean_path):
                # 移除开头的./或.\\
                clean_path = re.sub(r'^\./|^\.\\', '', clean_path)
                
                # 如果路径以data开头，基于项目根目录
                if clean_path.startswith("data/"):
                    return str(project_root / clean_path)
                else:
                    # 默认在项目的data目录下
                    return str(project_root / "data" / clean_path)
            
            # 5. 处理绝对路径
            # 尝试将路径转换为相对于项目根目录的路径
            try:
                # 检查路径是否在项目目录下
                abs_path = Path(clean_path).resolve()
                project_path = project_root.resolve()
                
                # 如果路径在项目目录下，直接返回
                if abs_path.is_relative_to(project_path):
                    return str(abs_path)
                
                # 如果路径在系统数据目录下，尝试映射到项目数据目录
                common_data_dirs = [
                    '/data', '/var/data', '/usr/share/data',
                    'C:/data', 'D:/data', 'E:/data'
                ]
                
                for data_dir in common_data_dirs:
                    if clean_path.startswith(data_dir):
                        # 提取数据目录后的部分
                        rel_path = clean_path[len(data_dir):].lstrip('/\\')
                        # 映射到项目数据目录
                        return str(project_root / "data" / rel_path)
                
                # 无法映射，直接返回绝对路径
                return str(abs_path)
            except Exception:
                # 如果路径解析失败，使用原始路径
                return clean_path
            
        except Exception as e:
            logger.error(f"数据路径规范化失败 [{path}]: {str(e)}")
            # 回退到项目默认数据目录
            return str(project_root / "data" / "camels_11532500")
    
    def _normalize_result_path(self, path: str) -> str:
        """
        规范化结果路径
        
        Args:
            path: 原始路径
            
        Returns:
            规范化后的绝对路径
        """
        try:
            # 项目根目录
            project_root = Path(__file__).parent.parent
            
            # 处理相对路径
            if not os.path.isabs(path):
                # 默认在项目的result目录下
                return str(project_root / "result" / path)
            
            # 使用工具进行路径规范化
            return correct_path(path, project_root)
            
        except Exception as e:
            logger.warning(f"结果路径规范化失败 {path}: {e}")
            # 回退到项目默认结果目录
            return str(Path(__file__).parent.parent / "result")
    
    def _validate_workflow(self, tasks: List[WorkflowTask]) -> List[ValidationIssue]:
        """验证工作流"""
        issues = []
        
        # 验证任务ID唯一性
        task_ids = [task.task_id for task in tasks]
        if len(task_ids) != len(set(task_ids)):
            issues.append(ValidationIssue(
                issue_type=ValidationStatus.ERROR,
                field="task_id",
                message="任务ID不唯一",
                suggestion="为重复的任务ID生成新的唯一标识符"
            ))
        
        # 验证依赖关系
        for task in tasks:
            for dep_id in task.dependencies:
                if dep_id not in task_ids:
                    issues.append(ValidationIssue(
                        issue_type=ValidationStatus.ERROR,
                        field="dependencies",
                        message=f"任务 {task.task_id} 依赖的任务 {dep_id} 不存在",
                        suggestion=f"移除不存在的依赖 {dep_id} 或创建对应的任务"
                    ))
        
        # 验证工具可用性并自动映射
        for task in tasks:
            if not self.tool_registry.is_tool_available(task.action):
                # 尝试自动映射工具
                if hasattr(self.tool_registry, 'map_workflow_action_to_tool'):
                    mapped_tool = self.tool_registry.map_workflow_action_to_tool(task.action)
                    if mapped_tool and self.tool_registry.is_tool_available(mapped_tool):
                        # 自动更新任务的工具名称
                        old_action = task.action
                        task.action = mapped_tool
                        logger.info(f"自动将任务 {task.task_id} 的工具从 '{old_action}' 映射为 '{mapped_tool}'")
                        continue
                
                # 如果无法自动映射，添加警告
                alternatives = self.tool_registry.suggest_alternative_tools(task.action)
                issues.append(ValidationIssue(
                    issue_type=ValidationStatus.WARNING,
                    field="action",
                    message=f"任务 {task.task_id} 使用的工具 {task.action} 不可用",
                    suggestion=f"建议使用替代工具: {', '.join(alternatives) if alternatives else '无可用替代工具'}",
                    metadata={"alternatives": alternatives}
                ))
        
        # 验证循环依赖
        cycle_issues = self._detect_dependency_cycles(tasks)
        issues.extend(cycle_issues)
        
        return issues
    
    def _detect_dependency_cycles(self, tasks: List[WorkflowTask]) -> List[ValidationIssue]:
        """检测循环依赖"""
        issues = []
        task_dict = {task.task_id: task for task in tasks}
        
        def has_cycle(start_id: str, current_id: str, visited: Set[str], path: List[str]) -> bool:
            if current_id in path:
                cycle_path = path[path.index(current_id):] + [current_id]
                issues.append(ValidationIssue(
                    issue_type=ValidationStatus.ERROR,
                    field="dependencies",
                    message=f"检测到循环依赖: {' -> '.join(cycle_path)}",
                    suggestion="重新设计任务依赖关系以消除循环"
                ))
                return True
            
            if current_id in visited:
                return False
            
            visited.add(current_id)
            path.append(current_id)
            
            current_task = task_dict.get(current_id)
            if current_task:
                for dep_id in current_task.dependencies:
                    if has_cycle(start_id, dep_id, visited, path[:]):
                        return True
            
            return False
        
        visited_global = set()
        for task in tasks:
            if task.task_id not in visited_global:
                has_cycle(task.task_id, task.task_id, set(), [])
                visited_global.add(task.task_id)
        
        return issues
    
    def _fix_common_issues(self, tasks: List[WorkflowTask], issues: List[ValidationIssue]) -> List[WorkflowTask]:
        """修复常见问题"""
        fixed_tasks = tasks.copy()
        
        # 修复重复的任务ID
        task_ids = set()
        for task in fixed_tasks:
            original_id = task.task_id
            counter = 1
            while task.task_id in task_ids:
                task.task_id = f"{original_id}_{counter}"
                counter += 1
            task_ids.add(task.task_id)
        
        # 修复不存在的依赖
        valid_task_ids = {task.task_id for task in fixed_tasks}
        for task in fixed_tasks:
            task.dependencies = [dep for dep in task.dependencies if dep in valid_task_ids]
        
        return fixed_tasks
    
    def _optimize_execution_order(self, tasks: List[WorkflowTask]) -> List[List[str]]:
        """优化执行顺序，识别可并行执行的任务"""
        if not tasks:
            return []
        
        # 构建依赖图
        task_dict = {task.task_id: task for task in tasks}
        in_degree = {task.task_id: 0 for task in tasks}
        
        # 计算入度
        for task in tasks:
            for dep_id in task.dependencies:
                if dep_id in in_degree:
                    in_degree[task.task_id] += 1
        
        # 拓扑排序并识别并行任务
        execution_order = []
        remaining_tasks = set(task_dict.keys())
        
        while remaining_tasks:
            # 找到所有入度为0的任务（可以并行执行）
            ready_tasks = [task_id for task_id in remaining_tasks if in_degree[task_id] == 0]
            
            if not ready_tasks:
                # 如果没有入度为0的任务，说明有循环依赖，选择一个任务强制执行
                ready_tasks = [next(iter(remaining_tasks))]
                logger.warning(f"检测到可能的循环依赖，强制执行任务: {ready_tasks[0]}")
            
            # 添加到执行顺序
            execution_order.append(ready_tasks)
            
            # 更新图
            for task_id in ready_tasks:
                remaining_tasks.remove(task_id)
                # 更新依赖这些任务的其他任务的入度
                for other_task in tasks:
                    if task_id in other_task.dependencies:
                        in_degree[other_task.task_id] -= 1
        
        return execution_order
    
    def _create_empty_workflow(self, raw_plan: str, error_message: str) -> AssembledWorkflow:
        """创建空工作流"""
        return AssembledWorkflow(
            workflow_id=str(uuid.uuid4()),
            name="错误工作流",
            description=f"由于错误而创建的空工作流: {error_message}",
            tasks=[],
            execution_order=[],
            validation_issues=[ValidationIssue(
                issue_type=ValidationStatus.ERROR,
                field="global",
                message=f"工作流组装失败: {error_message}",
                suggestion="检查原始计划格式和内容"
            )],
            metadata={
                "raw_plan": raw_plan[:500],  # 只保存前500个字符
                "error_message": error_message,
                "is_error_workflow": True
            }
        )


def create_workflow_assembler(tool_registry: Optional[ToolRegistry] = None) -> WorkflowAssembler:
    """创建工作流组装器实例"""
    return WorkflowAssembler(tool_registry=tool_registry)
