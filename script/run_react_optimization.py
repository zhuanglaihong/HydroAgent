"""
Author: zhuanglaihong
Date: 2025-09-27 14:50:00
LastEditTime: 2025-09-27 14:50:00
LastEditors: zhuanglaihong
Description: React模式水文模型自动优化工作流运行脚本
FilePath: \HydroAgent\script\run_react_optimization.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import json
import sys
import time
from pathlib import Path
import argparse
import re

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from executor.main import ExecutorEngine
from utils.logger_config import TestLoggerContext, LoggerConfig


def extract_nse_from_task_result(task_result):
    """从任务结果中提取NSE值"""
    if not task_result or not task_result.outputs:
        return None

    # 查找NSE相关的输出
    outputs = task_result.outputs

    # 方法1: 直接查找nse字段
    if 'nse' in outputs:
        return outputs['nse']

    # 方法2: 查找评估结果中的NSE
    if 'evaluation_results' in outputs:
        eval_results = outputs['evaluation_results']
        if isinstance(eval_results, dict):
            # 检查test_metrics (优先使用测试期指标)
            if 'test_metrics' in eval_results:
                test_metrics = eval_results['test_metrics']
                if isinstance(test_metrics, dict):
                    # 尝试不同的大小写组合
                    metric_variations = ['NSE', 'nse', 'Nse']
                    for variant in metric_variations:
                        if variant in test_metrics:
                            value = test_metrics[variant]
                            if isinstance(value, (int, float)):
                                return float(value)

            # 检查train_metrics (备选)
            if 'train_metrics' in eval_results:
                train_metrics = eval_results['train_metrics']
                if isinstance(train_metrics, dict):
                    metric_variations = ['NSE', 'nse', 'Nse']
                    for variant in metric_variations:
                        if variant in train_metrics:
                            value = train_metrics[variant]
                            if isinstance(value, (int, float)):
                                return float(value)

            # 原有逻辑保留作为备用
            if 'test_period' in eval_results:
                test_results = eval_results['test_period']
                if isinstance(test_results, dict) and 'nse' in test_results:
                    return test_results['nse']
            if 'nse' in eval_results:
                return eval_results['nse']

    # 方法3: 查找metrics中的NSE
    if 'metrics' in outputs:
        metrics = outputs['metrics']
        if isinstance(metrics, dict) and 'nse' in metrics:
            return metrics['nse']

    # 方法4: 从message中解析NSE值
    if 'message' in outputs:
        message = str(outputs['message'])
        # 使用正则表达式查找NSE值
        nse_pattern = r'NSE[:\s]*([0-9]*\.?[0-9]+)'
        match = re.search(nse_pattern, message, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass

    return None


def run_react_optimization_workflow(logger_config: LoggerConfig = None, workflow_file: str = None):
    """运行React模式自动优化工作流"""
    if logger_config:
        logger_config.log_step("运行React模式自动优化工作流")
    else:
        print("\n=== 运行React模式自动优化工作流 ===")

    # 初始化执行器
    executor = ExecutorEngine(enable_debug=False)

    # 确定工作流文件路径
    if workflow_file:
        workflow_path = Path(workflow_file)
    else:
        workflow_path = project_root / "workflow" / "example" / "react_hydro_optimization.json"

    if not workflow_path.exists():
        error_msg = f"工作流文件不存在: {workflow_path}"
        if logger_config:
            logger_config.log_result("工作流文件检查", {"status": "error", "message": error_msg})
        else:
            print(f"错误: {error_msg}")
        return False

    try:
        with open(workflow_path, 'r', encoding='utf-8') as f:
            workflow_json = f.read()
            workflow = json.loads(workflow_json)

        if logger_config:
            logger_config.log_step(f"执行React工作流: {workflow['name']}")
            logger_config.log_workflow_info(workflow)
        else:
            print(f"\n--- 执行React工作流: {workflow['name']} ---")
            print(f"工作流ID: {workflow.get('workflow_id', 'N/A')}")
            print(f"执行模式: {workflow.get('mode', workflow.get('execution_mode', 'react'))}")
            print(f"任务数量: {len(workflow.get('tasks', []))}")

            # 显示目标配置
            targets = workflow.get('targets', workflow.get('target'))
            if targets:
                target = targets[0] if isinstance(targets, list) else targets
                print(f"目标指标: {target.get('metric', 'N/A')} {target.get('comparison', '>=')} {target.get('threshold', 'N/A')}")
                print(f"最大迭代: {target.get('max_iterations', 'N/A')}次")

            react_config = workflow.get('react_config', {})
            if react_config:
                print(f"超时设置: {react_config.get('timeout_minutes', 'N/A')}分钟")

        start_time = time.time()

        # 执行React工作流
        execution_result = executor.execute_workflow(workflow_json, mode="react")

        end_time = time.time()
        total_duration = end_time - start_time

        if logger_config:
            logger_config.log_execution_result(execution_result)
        else:
            print(f"\n=== 执行结果 ===")
            print(f"执行ID: {execution_result.execution_id}")
            print(f"状态: {execution_result.status}")
            print(f"总执行时长: {total_duration:.2f}秒")

        # 分析React迭代过程
        if execution_result.react_iterations:
            print(f"\n=== React迭代详情 ===")
            print(f"总迭代次数: {len(execution_result.react_iterations)}")

            for i, iteration in enumerate(execution_result.react_iterations, 1):
                duration = (iteration.end_time - iteration.start_time).total_seconds()
                print(f"\n[迭代 {i}]")
                print(f"  时间: {iteration.start_time.strftime('%H:%M:%S')} - {iteration.end_time.strftime('%H:%M:%S')} ({duration:.1f}s)")
                print(f"  目标达成: {'是' if iteration.target_achieved else '否'}")
                print(f"  目标指标: {iteration.target_metric}")

                if iteration.current_metric is not None:
                    print(f"  当前指标: {iteration.current_metric:.4f}")
                else:
                    print(f"  当前指标: 未获取")

                # 显示该迭代中的任务结果
                if iteration.task_results:
                    completed_tasks = sum(1 for result in iteration.task_results.values()
                                        if result.status.value == "completed")
                    print(f"  任务完成: {completed_tasks}/{len(iteration.task_results)}")

                    # 特别显示评估任务的NSE结果
                    if 'task_evaluate' in iteration.task_results:
                        nse_value = extract_nse_from_task_result(iteration.task_results['task_evaluate'])
                        if nse_value is not None:
                            nse_status = "达标" if nse_value >= 0.7 else "未达标"
                            print(f"  NSE结果: {nse_value:.4f} ({nse_status})")

                if iteration.adjustments_made:
                    print(f"  调整策略: {', '.join(iteration.adjustments_made)}")

        # 最终结果分析
        final_success = execution_result.target_achieved if hasattr(execution_result, 'target_achieved') else False
        final_nse = None

        # 从最后一次迭代中获取最终NSE
        if execution_result.react_iterations:
            last_iteration = execution_result.react_iterations[-1]
            if 'task_evaluate' in last_iteration.task_results:
                final_nse = extract_nse_from_task_result(last_iteration.task_results['task_evaluate'])

        print(f"\n=== 最终结果摘要 ===")
        print(f"工作流状态: {execution_result.status}")
        print(f"目标达成: {'是' if final_success else '否'}")

        if final_nse is not None:
            nse_status = "达标" if final_nse >= 0.7 else "未达标"
            print(f"最终NSE: {final_nse:.4f} ({nse_status})")
        else:
            print(f"最终NSE: 无法获取")

        print(f"迭代次数: {len(execution_result.react_iterations) if execution_result.react_iterations else 0}")
        print(f"总耗时: {total_duration:.1f}秒")

        # 成功判断
        success = execution_result.status.value in ["completed", "success"] and final_nse is not None

        success_symbol = "🎉" if success else "⚠️"
        print(f"\n{success_symbol} React优化工作流{'完成' if success else '结束'}")

        # 记录到日志
        if logger_config:
            logger_config.log_result("React优化工作流完成", {
                "status": "completed",
                "target_achieved": final_success,
                "final_nse": final_nse,
                "iterations": len(execution_result.react_iterations) if execution_result.react_iterations else 0,
                "duration": total_duration,
                "execution_status": str(execution_result.status)
            })

        return success

    except Exception as e:
        error_msg = f"执行React工作流失败: {e}"
        if logger_config:
            logger_config.log_result("工作流执行失败", {"error": str(e), "status": "error"})
        else:
            print(f"错误: {error_msg}")
            import traceback
            print(f"详细错误信息:\n{traceback.format_exc()}")
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="运行React模式水文模型自动优化工作流",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python run_react_optimization.py                    # 使用默认工作流和日志
  python run_react_optimization.py --no-log-file      # 不使用日志文件
  python run_react_optimization.py --workflow custom.json  # 使用自定义工作流
  python run_react_optimization.py --quiet            # 简化输出
        """
    )
    parser.add_argument("--no-log-file", action="store_true",
                       help="不使用日志文件，直接输出到控制台")
    parser.add_argument("--workflow", type=str,
                       help="指定工作流JSON文件路径")
    parser.add_argument("--quiet", action="store_true",
                       help="简化输出，只显示关键信息")
    args = parser.parse_args()

    script_name = "react_optimization"
    script_description = "React模式水文模型自动优化工作流"

    if args.no_log_file:
        # 不使用日志文件的模式
        if not args.quiet:
            print("启动React模式水文模型自动优化工作流...")
            print("=" * 80)

        success = run_react_optimization_workflow(workflow_file=args.workflow)

        if not args.quiet:
            print("\n" + "=" * 80)
            print("执行总结:")
            print(f"  React优化工作流: {'[成功]' if success else '[失败]'}")
            print("=" * 80)

        return success
    else:
        # 使用日志系统
        with TestLoggerContext(script_name, script_description) as logger_config:
            logger_config.log_step("开始React优化工作流")
            success = run_react_optimization_workflow(logger_config, workflow_file=args.workflow)
            logger_config.log_step("React优化工作流", "完成" if success else "失败")

            # 总结
            logger_config.log_result("执行总结", {
                "status": "completed",
                "React优化工作流": "成功" if success else "失败",
                "overall_success": success
            })

            return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)