"""
Author: zhuanglaihong
Date: 2025-09-29 16:00:00
LastEditTime: 2025-09-29 16:00:00
LastEditors: zhuanglaihong
Description: 测试WorkflowBuilder能否生成与示例工作流类似的可执行工作流
FilePath: \HydroAgent\test\test_workflow_builder.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import sys
import os
import json
import time
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 确保logs和workflow/generated目录存在
logs_dir = project_root / "logs"
generated_dir = project_root / "workflow" / "generated"
logs_dir.mkdir(exist_ok=True)
generated_dir.mkdir(exist_ok=True)

# 设置详细日志
timestamp = int(time.time())
log_file = logs_dir / f"test_workflow_builder_{timestamp}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

def test_workflow_builder():
    """测试WorkflowBuilder生成工作流功能"""
    try:
        # 导入所需模块
        from builder.workflow_builder import WorkflowBuilder
        from hydrorag import RAGSystem, Config

        logger.info("=" * 60)
        logger.info("开始测试WorkflowBuilder工作流生成功能")
        logger.info(f"日志文件: {log_file}")
        logger.info("=" * 60)

        # 解析命令行参数
        parser = argparse.ArgumentParser(description='测试WorkflowBuilder')
        parser.add_argument('--api', action='store_true', help='使用API模式（默认使用本地模式）')
        parser.add_argument('--disable-rag', action='store_true', help='禁用RAG系统')
        args = parser.parse_args()

        use_api = args.api
        enable_rag = not args.disable_rag

        logger.info(f"测试配置: API模式={use_api}, RAG启用={enable_rag}")

        # 1. 初始化RAG系统（如果启用）
        rag_system = None
        if enable_rag:
            try:
                logger.info("初始化RAG系统...")
                config = Config()
                rag_system = RAGSystem(config)

                if rag_system.is_initialized:
                    logger.info("✓ RAG系统初始化成功")
                else:
                    logger.warning(f"RAG系统初始化部分失败: {rag_system.initialization_errors}")
            except Exception as e:
                logger.error(f"RAG系统初始化失败: {e}")
                logger.info("继续测试（不使用RAG）...")
        else:
            logger.info("RAG系统已禁用")

        # 2. 创建WorkflowBuilder实例
        logger.info("创建WorkflowBuilder实例...")
        try:
            builder = WorkflowBuilder(
                rag_system=rag_system,
                enable_rag=enable_rag,
                use_api_llm=use_api
            )
            logger.info("✓ WorkflowBuilder创建成功")
        except Exception as e:
            logger.error(f"WorkflowBuilder创建失败: {e}")
            return False

        # 3. 检查Builder就绪状态
        logger.info("检查Builder组件状态...")
        status = builder.is_ready()
        for component, ready in status.items():
            status_symbol = "✓" if ready else "✗"
            logger.info(f"  {component}: {status_symbol}")

        if not status.get("overall_ready", False):
            logger.warning("Builder系统未完全就绪，但继续测试...")

        # 4. 定义测试查询
        test_queries = [
            {
                "query": "生成完整的GR4J模型率定和评估工作流",
                "expected_mode": "linear",
                "expected_tasks": ["prepare_data", "calibrate_model", "evaluate_model"],
                "description": "类似complete_hydro_workflow.json的线性工作流"
            },
            {
                "query": "创建带有性能目标监控的GR4J模型自动优化流程，如果NSE低于0.7需要自动重新率定",
                "expected_mode": "react",
                "expected_tasks": ["prepare_data", "calibrate_model", "evaluate_model"],
                "description": "类似react_hydro_optimization.json的反应式工作流"
            },
            {
                "query": "率定GR4J模型并进行多轮优化直到达到NSE>0.6的目标",
                "expected_mode": "react",
                "expected_tasks": ["prepare_data", "calibrate_model", "evaluate_model"],
                "description": "另一个反应式优化工作流"
            },
            {
                "query": "准备数据然后训练XAJ模型",
                "expected_mode": "linear",
                "expected_tasks": ["prepare_data", "calibrate_model"],
                "description": "简单的XAJ模型工作流"
            }
        ]

        # 5. 执行测试
        test_results = []
        for i, test_case in enumerate(test_queries):
            logger.info(f"\n测试案例 {i+1}/4: {test_case['description']}")
            logger.info(f"查询: {test_case['query']}")
            logger.info(f"期望模式: {test_case['expected_mode']}")

            try:
                # 构建工作流
                start_time = time.time()
                result = builder.build_workflow(test_case['query'])
                build_time = time.time() - start_time

                if result.success:
                    workflow = result.workflow

                    # 分析结果
                    actual_mode = result.execution_mode.value
                    actual_tasks = [task.get('tool_name', task.get('action', 'unknown'))
                                  for task in workflow.get('tasks', [])]

                    logger.info(f"✓ 工作流生成成功")
                    logger.info(f"  工作流名称: {workflow.get('name', 'unknown')}")
                    logger.info(f"  执行模式: {actual_mode}")
                    logger.info(f"  任务数量: {len(workflow.get('tasks', []))}")
                    logger.info(f"  任务工具: {actual_tasks}")
                    logger.info(f"  构建时间: {build_time:.2f}秒")
                    logger.info(f"  意图类型: {result.intent_result.intent_type.value}")
                    logger.info(f"  意图置信度: {result.intent_result.confidence:.2f}")
                    logger.info(f"  复杂度评分: {result.mode_analysis.complexity_score:.2f}")

                    # 保存生成的工作流
                    date_str = datetime.now().strftime("%Y%m%d")
                    filename = f"generated_workflow_{i+1}_{date_str}.json"
                    output_path = generated_dir / filename

                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(workflow, f, ensure_ascii=False, indent=2)
                    logger.info(f"  工作流已保存: {output_path}")

                    # 验证工作流格式
                    validation_result = validate_workflow_format(workflow)
                    if validation_result['valid']:
                        logger.info("✓ 工作流格式验证通过")
                    else:
                        logger.warning(f"工作流格式问题: {validation_result['errors']}")

                    # 记录测试结果
                    test_results.append({
                        "case": i + 1,
                        "query": test_case['query'],
                        "success": True,
                        "expected_mode": test_case['expected_mode'],
                        "actual_mode": actual_mode,
                        "mode_match": actual_mode == test_case['expected_mode'],
                        "task_count": len(workflow.get('tasks', [])),
                        "build_time": build_time,
                        "workflow_file": str(output_path),
                        "validation": validation_result
                    })

                else:
                    logger.error(f"✗ 工作流生成失败: {result.error_message}")
                    test_results.append({
                        "case": i + 1,
                        "query": test_case['query'],
                        "success": False,
                        "error": result.error_message,
                        "build_time": build_time
                    })

            except Exception as e:
                logger.error(f"✗ 测试案例执行异常: {e}")
                test_results.append({
                    "case": i + 1,
                    "query": test_case['query'],
                    "success": False,
                    "error": str(e),
                    "build_time": 0
                })

        # 6. 输出测试摘要
        logger.info("\n" + "=" * 60)
        logger.info("测试摘要报告")
        logger.info("=" * 60)

        successful_tests = sum(1 for result in test_results if result['success'])
        total_tests = len(test_results)
        success_rate = successful_tests / total_tests if total_tests > 0 else 0

        logger.info(f"总测试数: {total_tests}")
        logger.info(f"成功测试: {successful_tests}")
        logger.info(f"失败测试: {total_tests - successful_tests}")
        logger.info(f"成功率: {success_rate:.1%}")

        # 详细结果
        for result in test_results:
            case_num = result['case']
            status = "✓" if result['success'] else "✗"
            logger.info(f"\n案例 {case_num}: {status}")
            if result['success']:
                mode_match = "✓" if result.get('mode_match', False) else "✗"
                logger.info(f"  执行模式: {result['actual_mode']} (期望: {result['expected_mode']}) {mode_match}")
                logger.info(f"  任务数量: {result['task_count']}")
                logger.info(f"  构建时间: {result['build_time']:.2f}秒")
                logger.info(f"  工作流文件: {result['workflow_file']}")
                validation = result['validation']
                val_status = "✓" if validation['valid'] else "✗"
                logger.info(f"  格式验证: {val_status}")
            else:
                logger.info(f"  错误: {result.get('error', 'unknown')}")

        # 7. 性能统计
        if successful_tests > 0:
            avg_build_time = sum(r['build_time'] for r in test_results if r['success']) / successful_tests
            logger.info(f"\n平均构建时间: {avg_build_time:.2f}秒")

        # 8. Builder统计信息
        try:
            builder_stats = builder.get_stats()
            logger.info(f"\nBuilder统计信息:")
            logger.info(f"  总构建次数: {builder_stats.get('total_builds', 0)}")
            logger.info(f"  成功次数: {builder_stats.get('successful_builds', 0)}")
            logger.info(f"  系统健康状态: {builder_stats.get('system_health', 'unknown')}")
        except Exception as e:
            logger.warning(f"无法获取Builder统计信息: {e}")

        logger.info(f"\n测试完成！详细日志: {log_file}")
        return success_rate >= 0.75  # 75%以上成功率认为测试通过

    except Exception as e:
        logger.error(f"测试执行异常: {e}")
        return False

def validate_workflow_format(workflow: Dict[str, Any]) -> Dict[str, Any]:
    """验证工作流格式是否符合标准"""
    errors = []

    # 检查必需字段
    required_fields = ['workflow_id', 'name', 'description', 'execution_mode', 'tasks']
    for field in required_fields:
        if field not in workflow:
            errors.append(f"缺少必需字段: {field}")

    # 检查任务格式
    tasks = workflow.get('tasks', [])
    if not tasks:
        errors.append("工作流必须包含至少一个任务")

    for i, task in enumerate(tasks):
        task_errors = validate_task_format(task, i)
        errors.extend(task_errors)

    # 检查执行模式
    valid_modes = ['linear', 'react', 'hybrid', 'sequential']
    execution_mode = workflow.get('execution_mode', '')
    if execution_mode not in valid_modes:
        errors.append(f"无效的执行模式: {execution_mode}")

    return {
        'valid': len(errors) == 0,
        'errors': errors
    }

def validate_task_format(task: Dict[str, Any], task_index: int) -> List[str]:
    """验证单个任务格式"""
    errors = []

    # 检查任务必需字段
    required_fields = ['task_id', 'name', 'description', 'tool_name', 'type', 'parameters']
    for field in required_fields:
        if field not in task:
            errors.append(f"任务 {task_index} 缺少必需字段: {field}")

    # 检查工具名称
    valid_tools = ['prepare_data', 'calibrate_model', 'evaluate_model', 'get_model_params']
    tool_name = task.get('tool_name', task.get('action', ''))
    if tool_name not in valid_tools:
        errors.append(f"任务 {task_index} 使用了无效的工具: {tool_name}")

    # 检查任务类型
    valid_types = ['simple', 'complex']
    task_type = task.get('type', task.get('task_type', ''))
    if task_type not in valid_types:
        errors.append(f"任务 {task_index} 使用了无效的任务类型: {task_type}")

    return errors


if __name__ == "__main__":
    print(f"开始WorkflowBuilder测试，详细输出保存到: {log_file}")

    # 运行测试
#   本地模式（推荐，稳定）
#   python test/test_workflow_builder.py

#   API模式（功能强大）
#   python test/test_workflow_builder.py --api

#   禁用RAG模式
#   python test/test_workflow_builder.py --disable-rag

    success = test_workflow_builder()

    if success:
        print("✓ 测试通过！")
        exit(0)
    else:
        print("✗ 测试失败！")
        exit(1)
