"""
Author: zhuanglaihong
Date: 2025-10-11 00:00:00
LastEditTime: 2025-10-11 00:00:00
LastEditors: zhuanglaihong
Description: RAG系统对复杂任务执行的影响测试 - 对比加载RAG和不加载RAG的效果
FilePath: \HydroAgent\test\test_rag_complex_workflow_comparison.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import sys
import os
import json
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 确保logs目录存在
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

# 设置详细日志
log_file = logs_dir / f"test_rag_complex_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

print(f"日志将保存到: {log_file}")


class RAGComparisonTest:
    """RAG系统对比测试"""

    def __init__(self):
        """初始化测试"""
        self.logger = logging.getLogger(__name__)
        self.results = {
            'test_time': datetime.now().isoformat(),
            'with_rag': {},
            'without_rag': {},
            'comparison': {}
        }

    def load_workflow_example(self, workflow_path: str) -> Dict[str, Any]:
        """
        加载工作流示例

        Args:
            workflow_path: 工作流JSON文件路径

        Returns:
            工作流配置
        """
        try:
            with open(workflow_path, 'r', encoding='utf-8') as f:
                workflow = json.load(f)
            self.logger.info(f"成功加载工作流: {workflow.get('name')}")
            return workflow
        except Exception as e:
            self.logger.error(f"加载工作流失败: {e}")
            return None

    def initialize_rag_system(self):
        """
        初始化RAG系统（使用上下文管理器确保资源清理）

        Returns:
            RAG系统实例或None
        """
        try:
            from hydrorag.rag_system import RAGSystem

            self.logger.info("正在初始化RAG系统...")

            # 检查documents目录
            docs_dir = project_root / "documents"
            if not docs_dir.exists():
                self.logger.warning(f"文档目录不存在: {docs_dir}")
                return None

            # 统计文档数量
            doc_files = list(docs_dir.glob("**/*.md"))
            self.logger.info(f"找到 {len(doc_files)} 个文档文件")

            # 初始化RAG系统（不使用with语句，因为需要返回实例）
            rag_system = RAGSystem()

            # 设置系统（处理文档和构建向量索引）
            if doc_files:
                self.logger.info("正在设置RAG系统（处理文档和构建索引）...")
                setup_result = rag_system.setup_from_raw_documents()
                if setup_result.get("status") == "success":
                    self.logger.info("RAG系统设置成功")
                else:
                    self.logger.warning(f"RAG系统设置遇到问题: {setup_result}")

            self.logger.info("RAG系统初始化完成")
            return rag_system

        except ImportError as e:
            self.logger.error(f"导入RAG系统失败: {e}")
            return None
        except Exception as e:
            self.logger.error(f"RAG系统初始化失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None

    def initialize_executor(self, with_rag: bool = False):
        """
        初始化执行器

        Args:
            with_rag: 是否启用RAG系统

        Returns:
            执行器实例或None
        """
        try:
            from executor.core.simple_executor import SimpleTaskExecutor
            from executor.core.complex_executor import ComplexTaskExecutor
            from executor.core.react_executor import ReactExecutor
            from executor.core.task_dispatcher import TaskDispatcher
            from executor.core.llm_client import LLMClientFactory

            self.logger.info(f"正在初始化执行器 (RAG: {with_rag})...")

            # 初始化组件
            simple_executor = SimpleTaskExecutor(enable_debug=True)
            task_dispatcher = TaskDispatcher(enable_debug=True)
            llm_client = LLMClientFactory.create_default_client()

            # 初始化RAG系统（如果需要）
            rag_system = None
            if with_rag:
                rag_system = self.initialize_rag_system()
                if rag_system:
                    self.logger.info("RAG系统已集成到执行器")
                else:
                    self.logger.warning("RAG系统初始化失败，将使用默认知识")

            # 创建复杂任务解决器
            complex_executor = ComplexTaskExecutor(
                simple_executor=simple_executor,
                llm_client=llm_client,
                rag_system=rag_system,
                enable_debug=True
            )

            # 创建React执行器
            react_executor = ReactExecutor(
                task_dispatcher=task_dispatcher,
                simple_executor=simple_executor,
                complex_executor=complex_executor,
                llm_client=llm_client,
                enable_debug=True
            )

            self.logger.info("执行器初始化完成")
            return react_executor

        except Exception as e:
            self.logger.error(f"执行器初始化失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None

    def convert_workflow_to_model(self, workflow_dict: Dict[str, Any]):
        """
        将工作流字典转换为模型对象

        Args:
            workflow_dict: 工作流字典

        Returns:
            Workflow模型对象
        """
        try:
            from executor.models.workflow import (
                Workflow, WorkflowMode, WorkflowTarget,
                WorkflowSettings, ErrorHandling
            )
            from executor.models.task import Task

            # 创建任务列表
            tasks = []
            for task_dict in workflow_dict.get('tasks', []):
                task = Task(
                    task_id=task_dict['task_id'],
                    name=task_dict['name'],
                    description=task_dict['description'],
                    tool_name=task_dict.get('tool_name'),
                    type=task_dict.get('type', 'simple'),
                    parameters=task_dict.get('parameters', {}),
                    dependencies=task_dict.get('dependencies', []),
                    conditions=task_dict.get('conditions', {}),
                    knowledge_query=task_dict.get('knowledge_query')
                )
                tasks.append(task)

            # 创建目标（如果有）
            target = None
            if workflow_dict.get('targets'):
                target_dict = workflow_dict['targets'][0]
                target = WorkflowTarget(
                    type=target_dict['type'],
                    metric=target_dict['metric'],
                    threshold=target_dict['threshold'],
                    comparison=target_dict['comparison'],
                    max_iterations=target_dict.get('max_iterations', 1)
                )

            # 创建工作流
            workflow = Workflow(
                workflow_id=workflow_dict['workflow_id'],
                name=workflow_dict['name'],
                description=workflow_dict['description'],
                mode=WorkflowMode.REACT if target else WorkflowMode.SEQUENTIAL,
                tasks=tasks,
                target=target,
                global_settings=WorkflowSettings(
                    error_handling=ErrorHandling.STOP_ON_ERROR
                )
            )

            return workflow

        except Exception as e:
            self.logger.error(f"转换工作流失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None

    def execute_workflow_test(self, workflow_dict: Dict[str, Any], with_rag: bool) -> Dict[str, Any]:
        """
        执行工作流测试（包含资源清理）

        Args:
            workflow_dict: 工作流配置
            with_rag: 是否启用RAG

        Returns:
            测试结果
        """
        test_name = "with_rag" if with_rag else "without_rag"
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"开始测试: {test_name}")
        self.logger.info(f"{'='*60}\n")

        result = {
            'test_name': test_name,
            'with_rag': with_rag,
            'success': False,
            'start_time': None,
            'end_time': None,
            'duration_seconds': 0,
            'error': None,
            'complex_tasks_count': 0,
            'complex_tasks_success': 0,
            'knowledge_chunks_used': 0,
            'llm_calls': 0,
            'workflow_result': None,
            'rag_query_success': 0,
            'rag_query_failed': 0
        }

        executor = None
        rag_system = None

        try:
            # 记录开始时间
            start_time = time.time()
            result['start_time'] = datetime.now().isoformat()

            # 统计复杂任务数量
            complex_tasks = [t for t in workflow_dict['tasks'] if t.get('type') == 'complex']
            result['complex_tasks_count'] = len(complex_tasks)

            # 初始化执行器
            executor = self.initialize_executor(with_rag=with_rag)
            if not executor:
                result['error'] = "执行器初始化失败"
                return result

            # 转换工作流
            workflow = self.convert_workflow_to_model(workflow_dict)
            if not workflow:
                result['error'] = "工作流转换失败"
                return result

            # 执行工作流
            self.logger.info("开始执行工作流...")
            if workflow.mode.value == "react":
                workflow_result = executor.execute_with_target(workflow)
            else:
                self.logger.error("当前只支持React模式工作流")
                result['error'] = "不支持的工作流模式"
                return result

            # 记录结束时间
            end_time = time.time()
            result['end_time'] = datetime.now().isoformat()
            result['duration_seconds'] = end_time - start_time

            # 分析结果
            result['success'] = workflow_result.status.value == 'completed'

            # 统计复杂任务成功数量和知识使用情况
            for task_id, task_result in workflow_result.task_results.items():
                if task_id.startswith('task_') and task_result.metadata:
                    if task_result.metadata.get('solution_type'):
                        # 这是一个复杂任务
                        if task_result.status.value == 'completed':
                            result['complex_tasks_success'] += 1
                        result['knowledge_chunks_used'] += task_result.metadata.get('knowledge_chunks_used', 0)

            result['workflow_result'] = {
                'status': workflow_result.status.value,
                'target_achieved': getattr(workflow_result, 'target_achieved', None),
                'iterations': len(getattr(workflow_result, 'react_iterations', [])),
                'task_count': len(workflow_result.task_results),
                'tasks_status': {
                    task_id: task_result.status.value
                    for task_id, task_result in workflow_result.task_results.items()
                }
            }

            self.logger.info(f"\n测试 {test_name} 完成:")
            self.logger.info(f"  - 状态: {result['success']}")
            self.logger.info(f"  - 耗时: {result['duration_seconds']:.2f}秒")
            self.logger.info(f"  - 复杂任务: {result['complex_tasks_success']}/{result['complex_tasks_count']}")
            self.logger.info(f"  - 知识片段使用: {result['knowledge_chunks_used']}")

        except Exception as e:
            self.logger.error(f"测试 {test_name} 执行失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            result['error'] = str(e)

        finally:
            # 清理资源
            if with_rag and rag_system:
                try:
                    self.logger.info("清理RAG系统资源...")
                    rag_system.cleanup()
                    import gc
                    gc.collect()
                    self.logger.info("RAG系统资源清理完成")
                except Exception as e:
                    self.logger.warning(f"RAG资源清理失败: {e}")

        return result

    def compare_results(self, result_with_rag: Dict, result_without_rag: Dict):
        """
        对比两个测试结果

        Args:
            result_with_rag: 启用RAG的结果
            result_without_rag: 未启用RAG的结果

        Returns:
            对比结果
        """
        self.logger.info(f"\n{'='*60}")
        self.logger.info("对比分析")
        self.logger.info(f"{'='*60}\n")

        comparison = {
            'success_rate': {
                'with_rag': f"{result_with_rag['complex_tasks_success']}/{result_with_rag['complex_tasks_count']}",
                'without_rag': f"{result_without_rag['complex_tasks_success']}/{result_without_rag['complex_tasks_count']}",
                'improvement': 0
            },
            'execution_time': {
                'with_rag': result_with_rag['duration_seconds'],
                'without_rag': result_without_rag['duration_seconds'],
                'difference': 0
            },
            'knowledge_usage': {
                'with_rag': result_with_rag['knowledge_chunks_used'],
                'without_rag': result_without_rag['knowledge_chunks_used']
            },
            'conclusion': []
        }

        # 计算改进
        if result_with_rag['complex_tasks_count'] > 0:
            rate_with = result_with_rag['complex_tasks_success'] / result_with_rag['complex_tasks_count']
            rate_without = result_without_rag['complex_tasks_success'] / result_without_rag['complex_tasks_count']
            comparison['success_rate']['improvement'] = (rate_with - rate_without) * 100

        comparison['execution_time']['difference'] = (
            result_with_rag['duration_seconds'] - result_without_rag['duration_seconds']
        )

        # 生成结论
        if comparison['success_rate']['improvement'] > 0:
            comparison['conclusion'].append(
                f"RAG系统提升了 {comparison['success_rate']['improvement']:.1f}% 的成功率"
            )
        elif comparison['success_rate']['improvement'] < 0:
            comparison['conclusion'].append(
                f"RAG系统降低了 {abs(comparison['success_rate']['improvement']):.1f}% 的成功率"
            )
        else:
            comparison['conclusion'].append("RAG系统对成功率无影响")

        if comparison['execution_time']['difference'] > 0:
            comparison['conclusion'].append(
                f"RAG系统增加了 {comparison['execution_time']['difference']:.2f}秒 的执行时间"
            )
        elif comparison['execution_time']['difference'] < 0:
            comparison['conclusion'].append(
                f"RAG系统减少了 {abs(comparison['execution_time']['difference']):.2f}秒 的执行时间"
            )

        if result_with_rag['knowledge_chunks_used'] > 0:
            comparison['conclusion'].append(
                f"RAG系统成功检索并使用了 {result_with_rag['knowledge_chunks_used']} 个知识片段"
            )

        # 打印对比结果
        self.logger.info("成功率对比:")
        self.logger.info(f"  - 启用RAG: {comparison['success_rate']['with_rag']}")
        self.logger.info(f"  - 未启用RAG: {comparison['success_rate']['without_rag']}")
        self.logger.info(f"  - 改进: {comparison['success_rate']['improvement']:.1f}%")

        self.logger.info("\n执行时间对比:")
        self.logger.info(f"  - 启用RAG: {comparison['execution_time']['with_rag']:.2f}秒")
        self.logger.info(f"  - 未启用RAG: {comparison['execution_time']['without_rag']:.2f}秒")
        self.logger.info(f"  - 差异: {comparison['execution_time']['difference']:.2f}秒")

        self.logger.info("\n知识使用情况:")
        self.logger.info(f"  - 启用RAG: {comparison['knowledge_usage']['with_rag']} 个知识片段")
        self.logger.info(f"  - 未启用RAG: {comparison['knowledge_usage']['without_rag']} 个知识片段")

        self.logger.info("\n结论:")
        for i, conclusion in enumerate(comparison['conclusion'], 1):
            self.logger.info(f"  {i}. {conclusion}")

        return comparison

    def run_comparison_test(self, workflow_path: str):
        """
        运行完整的对比测试

        Args:
            workflow_path: 工作流文件路径

        Returns:
            完整测试结果
        """
        self.logger.info("="*80)
        self.logger.info("RAG系统对复杂任务影响对比测试")
        self.logger.info("="*80)

        # 加载工作流
        workflow_dict = self.load_workflow_example(workflow_path)
        if not workflow_dict:
            self.logger.error("加载工作流失败，测试终止")
            return None

        # 测试1: 不启用RAG
        self.logger.info("\n\n第一轮测试: 不启用RAG系统")
        result_without_rag = self.execute_workflow_test(workflow_dict, with_rag=False)
        self.results['without_rag'] = result_without_rag

        # 等待一会儿
        time.sleep(2)

        # 测试2: 启用RAG
        self.logger.info("\n\n第二轮测试: 启用RAG系统")
        result_with_rag = self.execute_workflow_test(workflow_dict, with_rag=True)
        self.results['with_rag'] = result_with_rag

        # 对比分析
        comparison = self.compare_results(result_with_rag, result_without_rag)
        self.results['comparison'] = comparison

        # 保存结果
        self.save_results()

        return self.results

    def save_results(self):
        """保存测试结果到JSON文件"""
        output_file = logs_dir / f"rag_comparison_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, indent=2, ensure_ascii=False)
            self.logger.info(f"\n测试结果已保存到: {output_file}")
        except Exception as e:
            self.logger.error(f"保存结果失败: {e}")


def main():
    """主函数"""
    print("\n" + "="*80)
    print("RAG系统对复杂任务执行影响对比测试")
    print("="*80 + "\n")

    # 工作流文件路径
    workflow_file = project_root / "workflow" / "example" / "complex_data_analysis.json"

    if not workflow_file.exists():
        logger.error(f"工作流文件不存在: {workflow_file}")
        logger.error("请确保已创建 workflow/example/complex_data_analysis.json")
        return

    # 创建测试实例
    test = RAGComparisonTest()

    # 运行对比测试
    results = test.run_comparison_test(str(workflow_file))

    if results:
        print("\n" + "="*80)
        print("测试完成！")
        print("="*80)
        print(f"\n详细日志: {log_file}")
        
    else:
        print("\n测试失败，请查看日志文件获取详细信息")


if __name__ == '__main__':
    main()
