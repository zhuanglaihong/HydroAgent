"""
验证与反馈闭环机制

功能：无需用户确认，自动处理错误并学习

处理步骤：
1. 在执行层面，工作流执行失败时，记录错误信息（任务ID、错误类型、输入上下文）
2. 设计一个离线学习机制，将失败案例和最终解决方案存入知识库，供RAG后续检索，实现自我优化

Author: Assistant
Date: 2025-01-20
"""

import logging
import json
import time
import sqlite3
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """错误类型枚举"""
    SYNTAX_ERROR = "syntax_error"           # 语法错误
    LOGIC_ERROR = "logic_error"             # 逻辑错误
    RESOURCE_ERROR = "resource_error"       # 资源错误
    DEPENDENCY_ERROR = "dependency_error"   # 依赖错误
    TIMEOUT_ERROR = "timeout_error"         # 超时错误
    VALIDATION_ERROR = "validation_error"   # 验证错误
    UNKNOWN_ERROR = "unknown_error"         # 未知错误


class FeedbackType(Enum):
    """反馈类型枚举"""
    SUCCESS = "success"                     # 成功
    FAILURE = "failure"                     # 失败
    WARNING = "warning"                     # 警告
    IMPROVEMENT = "improvement"             # 改进建议


@dataclass
class ExecutionFeedback:
    """执行反馈"""
    feedback_id: str                        # 反馈ID
    workflow_id: str                        # 工作流ID
    task_id: str                            # 任务ID
    feedback_type: FeedbackType             # 反馈类型
    error_type: Optional[ErrorType] = None  # 错误类型
    error_message: str = ""                 # 错误消息
    context: Dict[str, Any] = field(default_factory=dict)      # 执行上下文
    solution: Optional[str] = None          # 解决方案
    input_data: Dict[str, Any] = field(default_factory=dict)   # 输入数据
    output_data: Optional[Any] = None       # 输出数据
    execution_time: float = 0.0             # 执行时间
    timestamp: datetime = field(default_factory=datetime.now)  # 时间戳
    metadata: Dict[str, Any] = field(default_factory=dict)     # 元数据

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "feedback_id": self.feedback_id,
            "workflow_id": self.workflow_id,
            "task_id": self.task_id,
            "feedback_type": self.feedback_type.value,
            "error_type": self.error_type.value if self.error_type else None,
            "error_message": self.error_message,
            "context": self.context,
            "solution": self.solution,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "execution_time": self.execution_time,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class LearningCase:
    """学习案例"""
    case_id: str                            # 案例ID
    problem_description: str                # 问题描述
    error_pattern: str                      # 错误模式
    solution_description: str               # 解决方案描述
    context_pattern: Dict[str, Any]         # 上下文模式
    success_rate: float = 0.0               # 成功率
    usage_count: int = 0                    # 使用次数
    effectiveness_score: float = 0.0        # 有效性评分
    created_time: datetime = field(default_factory=datetime.now)   # 创建时间
    last_used: Optional[datetime] = None    # 最后使用时间
    metadata: Dict[str, Any] = field(default_factory=dict)         # 元数据

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "case_id": self.case_id,
            "problem_description": self.problem_description,
            "error_pattern": self.error_pattern,
            "solution_description": self.solution_description,
            "context_pattern": self.context_pattern,
            "success_rate": self.success_rate,
            "usage_count": self.usage_count,
            "effectiveness_score": self.effectiveness_score,
            "created_time": self.created_time.isoformat(),
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "metadata": self.metadata
        }


class FeedbackCollector:
    """反馈收集器"""
    
    def __init__(self, storage_path: str = "workflow/feedback_data"):
        """
        初始化反馈收集器
        
        Args:
            storage_path: 存储路径
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # 初始化数据库
        self.db_path = self.storage_path / "feedback.db"
        self._init_database()
        
        logger.info(f"反馈收集器初始化完成，存储路径: {self.storage_path}")
    
    def _init_database(self):
        """初始化数据库"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 创建反馈表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS execution_feedback (
                        feedback_id TEXT PRIMARY KEY,
                        workflow_id TEXT,
                        task_id TEXT,
                        feedback_type TEXT,
                        error_type TEXT,
                        error_message TEXT,
                        context TEXT,
                        solution TEXT,
                        input_data TEXT,
                        output_data TEXT,
                        execution_time REAL,
                        timestamp TEXT,
                        metadata TEXT
                    )
                """)
                
                # 创建学习案例表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS learning_cases (
                        case_id TEXT PRIMARY KEY,
                        problem_description TEXT,
                        error_pattern TEXT,
                        solution_description TEXT,
                        context_pattern TEXT,
                        success_rate REAL,
                        usage_count INTEGER,
                        effectiveness_score REAL,
                        created_time TEXT,
                        last_used TEXT,
                        metadata TEXT
                    )
                """)
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"数据库初始化失败: {str(e)}")
    
    def record_execution_feedback(self, feedback: ExecutionFeedback):
        """记录执行反馈"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO execution_feedback (
                        feedback_id, workflow_id, task_id, feedback_type, error_type,
                        error_message, context, solution, input_data, output_data,
                        execution_time, timestamp, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    feedback.feedback_id,
                    feedback.workflow_id,
                    feedback.task_id,
                    feedback.feedback_type.value,
                    feedback.error_type.value if feedback.error_type else None,
                    feedback.error_message,
                    json.dumps(feedback.context, ensure_ascii=False),
                    feedback.solution,
                    json.dumps(feedback.input_data, ensure_ascii=False),
                    json.dumps(feedback.output_data, ensure_ascii=False) if feedback.output_data else None,
                    feedback.execution_time,
                    feedback.timestamp.isoformat(),
                    json.dumps(feedback.metadata, ensure_ascii=False)
                ))
                
                conn.commit()
                logger.info(f"记录执行反馈: {feedback.feedback_id}")
                
        except Exception as e:
            logger.error(f"记录执行反馈失败: {str(e)}")
    
    def get_similar_failures(self, error_type: ErrorType, context: Dict[str, Any], 
                           limit: int = 10) -> List[ExecutionFeedback]:
        """获取相似的失败案例"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM execution_feedback 
                    WHERE feedback_type = 'failure' AND error_type = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (error_type.value, limit))
                
                rows = cursor.fetchall()
                feedbacks = []
                
                for row in rows:
                    feedback = ExecutionFeedback(
                        feedback_id=row[0],
                        workflow_id=row[1],
                        task_id=row[2],
                        feedback_type=FeedbackType(row[3]),
                        error_type=ErrorType(row[4]) if row[4] else None,
                        error_message=row[5],
                        context=json.loads(row[6]) if row[6] else {},
                        solution=row[7],
                        input_data=json.loads(row[8]) if row[8] else {},
                        output_data=json.loads(row[9]) if row[9] else None,
                        execution_time=row[10],
                        timestamp=datetime.fromisoformat(row[11]),
                        metadata=json.loads(row[12]) if row[12] else {}
                    )
                    feedbacks.append(feedback)
                
                return feedbacks
                
        except Exception as e:
            logger.error(f"获取相似失败案例失败: {str(e)}")
            return []
    
    def get_execution_statistics(self, time_range_days: int = 30) -> Dict[str, Any]:
        """获取执行统计信息"""
        try:
            start_time = datetime.now() - timedelta(days=time_range_days)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 总体统计
                cursor.execute("""
                    SELECT feedback_type, COUNT(*) FROM execution_feedback
                    WHERE timestamp >= ?
                    GROUP BY feedback_type
                """, (start_time.isoformat(),))
                
                feedback_stats = dict(cursor.fetchall())
                
                # 错误类型统计
                cursor.execute("""
                    SELECT error_type, COUNT(*) FROM execution_feedback
                    WHERE timestamp >= ? AND feedback_type = 'failure' AND error_type IS NOT NULL
                    GROUP BY error_type
                """, (start_time.isoformat(),))
                
                error_stats = dict(cursor.fetchall())
                
                # 成功率统计
                total_executions = sum(feedback_stats.values())
                success_count = feedback_stats.get('success', 0)
                success_rate = success_count / total_executions if total_executions > 0 else 0.0
                
                return {
                    "time_range_days": time_range_days,
                    "total_executions": total_executions,
                    "feedback_statistics": feedback_stats,
                    "error_statistics": error_stats,
                    "success_rate": success_rate,
                    "generated_time": datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"获取执行统计信息失败: {str(e)}")
            return {}


class LearningEngine:
    """学习引擎"""
    
    def __init__(self, feedback_collector: FeedbackCollector, rag_system=None):
        """
        初始化学习引擎
        
        Args:
            feedback_collector: 反馈收集器
            rag_system: RAG系统，用于知识存储
        """
        self.feedback_collector = feedback_collector
        self.rag_system = rag_system
        
        logger.info("学习引擎初始化完成")
    
    def analyze_failure_patterns(self, min_occurrences: int = 3) -> List[LearningCase]:
        """分析失败模式"""
        try:
            # 获取最近的失败案例
            with sqlite3.connect(self.feedback_collector.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT error_type, error_message, context, COUNT(*) as count
                    FROM execution_feedback
                    WHERE feedback_type = 'failure' AND error_type IS NOT NULL
                    GROUP BY error_type, error_message
                    HAVING count >= ?
                    ORDER BY count DESC
                """, (min_occurrences,))
                
                patterns = cursor.fetchall()
                
            learning_cases = []
            for pattern in patterns:
                error_type, error_message, context_json, count = pattern
                
                # 创建学习案例
                case_id = f"pattern_{hash(f'{error_type}_{error_message}')}"
                
                learning_case = LearningCase(
                    case_id=case_id,
                    problem_description=f"重复出现的错误: {error_type}",
                    error_pattern=error_message,
                    solution_description=self._generate_solution_suggestion(error_type, error_message),
                    context_pattern=json.loads(context_json) if context_json else {},
                    usage_count=count,
                    effectiveness_score=0.0  # 需要通过实际使用来更新
                )
                
                learning_cases.append(learning_case)
            
            logger.info(f"分析出 {len(learning_cases)} 个失败模式")
            return learning_cases
            
        except Exception as e:
            logger.error(f"分析失败模式失败: {str(e)}")
            return []
    
    def _generate_solution_suggestion(self, error_type: str, error_message: str) -> str:
        """生成解决方案建议"""
        solution_templates = {
            "syntax_error": "检查语法格式，确保JSON结构正确",
            "logic_error": "检查任务依赖关系和执行逻辑",
            "resource_error": "检查资源可用性，确保文件路径正确",
            "dependency_error": "检查任务依赖关系，确保依赖任务存在",
            "timeout_error": "增加超时时间或优化任务执行效率",
            "validation_error": "检查输入参数的有效性和完整性",
            "unknown_error": "查看详细错误日志，联系技术支持"
        }
        
        base_solution = solution_templates.get(error_type, "分析具体错误信息并采取相应措施")
        
        # 根据错误消息细化建议
        if "file not found" in error_message.lower():
            return f"{base_solution}。特别检查文件路径是否存在。"
        elif "permission denied" in error_message.lower():
            return f"{base_solution}。检查文件权限设置。"
        elif "timeout" in error_message.lower():
            return f"{base_solution}。考虑增加超时时间。"
        else:
            return base_solution
    
    def store_learning_case(self, learning_case: LearningCase):
        """存储学习案例"""
        try:
            with sqlite3.connect(self.feedback_collector.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO learning_cases (
                        case_id, problem_description, error_pattern, solution_description,
                        context_pattern, success_rate, usage_count, effectiveness_score,
                        created_time, last_used, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    learning_case.case_id,
                    learning_case.problem_description,
                    learning_case.error_pattern,
                    learning_case.solution_description,
                    json.dumps(learning_case.context_pattern, ensure_ascii=False),
                    learning_case.success_rate,
                    learning_case.usage_count,
                    learning_case.effectiveness_score,
                    learning_case.created_time.isoformat(),
                    learning_case.last_used.isoformat() if learning_case.last_used else None,
                    json.dumps(learning_case.metadata, ensure_ascii=False)
                ))
                
                conn.commit()
                logger.info(f"存储学习案例: {learning_case.case_id}")
                
        except Exception as e:
            logger.error(f"存储学习案例失败: {str(e)}")
    
    def update_case_effectiveness(self, case_id: str, was_successful: bool):
        """更新案例有效性"""
        try:
            with sqlite3.connect(self.feedback_collector.db_path) as conn:
                cursor = conn.cursor()
                
                # 获取当前案例
                cursor.execute("""
                    SELECT usage_count, effectiveness_score FROM learning_cases WHERE case_id = ?
                """, (case_id,))
                
                result = cursor.fetchone()
                if not result:
                    logger.warning(f"学习案例不存在: {case_id}")
                    return
                
                usage_count, current_score = result
                
                # 更新有效性评分（简单的移动平均）
                new_usage_count = usage_count + 1
                success_value = 1.0 if was_successful else 0.0
                new_score = (current_score * usage_count + success_value) / new_usage_count
                
                # 更新数据库
                cursor.execute("""
                    UPDATE learning_cases 
                    SET usage_count = ?, effectiveness_score = ?, last_used = ?
                    WHERE case_id = ?
                """, (new_usage_count, new_score, datetime.now().isoformat(), case_id))
                
                conn.commit()
                logger.info(f"更新案例有效性: {case_id}, 新评分: {new_score:.2f}")
                
        except Exception as e:
            logger.error(f"更新案例有效性失败: {str(e)}")
    
    def get_relevant_learning_cases(self, error_type: ErrorType, context: Dict[str, Any], 
                                  limit: int = 5) -> List[LearningCase]:
        """获取相关的学习案例"""
        try:
            with sqlite3.connect(self.feedback_collector.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM learning_cases 
                    WHERE effectiveness_score > 0.3
                    ORDER BY effectiveness_score DESC, usage_count DESC
                    LIMIT ?
                """, (limit,))
                
                rows = cursor.fetchall()
                cases = []
                
                for row in rows:
                    case = LearningCase(
                        case_id=row[0],
                        problem_description=row[1],
                        error_pattern=row[2],
                        solution_description=row[3],
                        context_pattern=json.loads(row[4]) if row[4] else {},
                        success_rate=row[5],
                        usage_count=row[6],
                        effectiveness_score=row[7],
                        created_time=datetime.fromisoformat(row[8]),
                        last_used=datetime.fromisoformat(row[9]) if row[9] else None,
                        metadata=json.loads(row[10]) if row[10] else {}
                    )
                    cases.append(case)
                
                return cases
                
        except Exception as e:
            logger.error(f"获取相关学习案例失败: {str(e)}")
            return []
    
    def integrate_to_rag_system(self, learning_cases: List[LearningCase]):
        """将学习案例集成到RAG系统"""
        if not self.rag_system:
            logger.warning("RAG系统不可用，无法集成学习案例")
            return
        
        try:
            for case in learning_cases:
                # 构建知识文档
                knowledge_doc = f"""
问题类型: {case.problem_description}
错误模式: {case.error_pattern}
解决方案: {case.solution_description}
有效性评分: {case.effectiveness_score:.2f}
使用次数: {case.usage_count}

上下文模式:
{json.dumps(case.context_pattern, ensure_ascii=False, indent=2)}
"""
                
                # 添加到RAG系统
                if hasattr(self.rag_system, 'add_document'):
                    self.rag_system.add_document(
                        content=knowledge_doc,
                        metadata={
                            "type": "learning_case",
                            "case_id": case.case_id,
                            "effectiveness_score": case.effectiveness_score
                        }
                    )
                elif hasattr(self.rag_system, 'insert'):
                    self.rag_system.insert(knowledge_doc)
            
            logger.info(f"成功集成 {len(learning_cases)} 个学习案例到RAG系统")
            
        except Exception as e:
            logger.error(f"集成学习案例到RAG系统失败: {str(e)}")


class ValidationFeedbackSystem:
    """验证反馈系统"""
    
    def __init__(self, storage_path: str = "workflow/feedback_data", rag_system=None):
        """
        初始化验证反馈系统
        
        Args:
            storage_path: 存储路径
            rag_system: RAG系统
        """
        self.feedback_collector = FeedbackCollector(storage_path)
        self.learning_engine = LearningEngine(self.feedback_collector, rag_system)
        
        logger.info("验证反馈系统初始化完成")
    
    def record_execution_result(self, workflow_id: str, task_id: str, 
                              success: bool, error_info: Optional[Dict[str, Any]] = None,
                              context: Optional[Dict[str, Any]] = None,
                              execution_time: float = 0.0) -> str:
        """
        记录执行结果
        
        Args:
            workflow_id: 工作流ID
            task_id: 任务ID
            success: 是否成功
            error_info: 错误信息
            context: 执行上下文
            execution_time: 执行时间
            
        Returns:
            str: 反馈ID
        """
        feedback_id = f"fb_{int(time.time())}_{hash(f'{workflow_id}_{task_id}')}"
        
        if success:
            feedback = ExecutionFeedback(
                feedback_id=feedback_id,
                workflow_id=workflow_id,
                task_id=task_id,
                feedback_type=FeedbackType.SUCCESS,
                context=context or {},
                execution_time=execution_time
            )
        else:
            error_type = self._classify_error_type(error_info)
            error_message = error_info.get("message", "未知错误") if error_info else "未知错误"
            
            feedback = ExecutionFeedback(
                feedback_id=feedback_id,
                workflow_id=workflow_id,
                task_id=task_id,
                feedback_type=FeedbackType.FAILURE,
                error_type=error_type,
                error_message=error_message,
                context=context or {},
                execution_time=execution_time,
                metadata=error_info or {}
            )
        
        self.feedback_collector.record_execution_feedback(feedback)
        return feedback_id
    
    def _classify_error_type(self, error_info: Optional[Dict[str, Any]]) -> ErrorType:
        """分类错误类型"""
        if not error_info:
            return ErrorType.UNKNOWN_ERROR
        
        error_message = error_info.get("message", "").lower()
        
        if "syntax" in error_message or "json" in error_message:
            return ErrorType.SYNTAX_ERROR
        elif "timeout" in error_message:
            return ErrorType.TIMEOUT_ERROR
        elif "file not found" in error_message or "resource" in error_message:
            return ErrorType.RESOURCE_ERROR
        elif "dependency" in error_message:
            return ErrorType.DEPENDENCY_ERROR
        elif "validation" in error_message or "invalid" in error_message:
            return ErrorType.VALIDATION_ERROR
        elif "logic" in error_message:
            return ErrorType.LOGIC_ERROR
        else:
            return ErrorType.UNKNOWN_ERROR
    
    def get_improvement_suggestions(self, error_type: ErrorType, 
                                   context: Dict[str, Any]) -> List[str]:
        """获取改进建议"""
        suggestions = []
        
        # 从学习案例中获取建议
        learning_cases = self.learning_engine.get_relevant_learning_cases(error_type, context)
        for case in learning_cases:
            suggestions.append(case.solution_description)
        
        # 添加通用建议
        general_suggestions = {
            ErrorType.SYNTAX_ERROR: [
                "检查JSON格式是否正确",
                "验证所有括号和引号是否配对",
                "使用JSON验证工具检查语法"
            ],
            ErrorType.LOGIC_ERROR: [
                "检查任务依赖关系",
                "验证条件判断逻辑",
                "确保数据流的一致性"
            ],
            ErrorType.RESOURCE_ERROR: [
                "检查文件路径是否存在",
                "验证资源访问权限",
                "确保网络连接正常"
            ],
            ErrorType.DEPENDENCY_ERROR: [
                "检查依赖任务是否存在",
                "验证依赖关系是否形成循环",
                "确保依赖任务已成功执行"
            ],
            ErrorType.TIMEOUT_ERROR: [
                "增加任务超时时间",
                "优化任务执行效率",
                "检查系统资源使用情况"
            ],
            ErrorType.VALIDATION_ERROR: [
                "检查输入参数的有效性",
                "验证数据格式是否正确",
                "确保必需参数不为空"
            ]
        }
        
        suggestions.extend(general_suggestions.get(error_type, ["联系技术支持获取帮助"]))
        
        return list(set(suggestions))  # 去重
    
    def trigger_learning_update(self):
        """触发学习更新"""
        try:
            # 分析失败模式
            learning_cases = self.learning_engine.analyze_failure_patterns()
            
            # 存储新的学习案例
            for case in learning_cases:
                self.learning_engine.store_learning_case(case)
            
            # 集成到RAG系统
            self.learning_engine.integrate_to_rag_system(learning_cases)
            
            logger.info(f"学习更新完成，处理了 {len(learning_cases)} 个案例")
            
        except Exception as e:
            logger.error(f"学习更新失败: {str(e)}")
    
    def get_system_health_report(self) -> Dict[str, Any]:
        """获取系统健康报告"""
        try:
            stats = self.feedback_collector.get_execution_statistics()
            
            # 添加健康评估
            success_rate = stats.get("success_rate", 0.0)
            health_level = "优秀" if success_rate >= 0.9 else "良好" if success_rate >= 0.7 else "需要改进"
            
            stats["health_assessment"] = {
                "level": health_level,
                "success_rate": success_rate,
                "recommendations": self._generate_health_recommendations(stats)
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"获取系统健康报告失败: {str(e)}")
            return {}
    
    def _generate_health_recommendations(self, stats: Dict[str, Any]) -> List[str]:
        """生成健康建议"""
        recommendations = []
        
        success_rate = stats.get("success_rate", 0.0)
        error_stats = stats.get("error_statistics", {})
        
        if success_rate < 0.7:
            recommendations.append("系统成功率较低，建议全面检查工作流设计")
        
        # 分析主要错误类型
        if error_stats:
            most_common_error = max(error_stats.items(), key=lambda x: x[1])
            recommendations.append(f"主要错误类型是 {most_common_error[0]}，建议重点关注该类问题")
        
        if not recommendations:
            recommendations.append("系统运行良好，继续保持")
        
        return recommendations


def create_validation_feedback_system(storage_path: str = "workflow/feedback_data", 
                                    rag_system=None) -> ValidationFeedbackSystem:
    """创建验证反馈系统实例"""
    return ValidationFeedbackSystem(storage_path=storage_path, rag_system=rag_system)
