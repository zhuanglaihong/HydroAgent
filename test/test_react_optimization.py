"""
Author: zhuanglaihong
Date: 2025-09-27 13:35:00
LastEditTime: 2025-09-27 13:35:00
LastEditors: zhuanglaihong
Description: 测试React模式的自动优化工作流
FilePath: \HydroAgent\test\test_react_optimization.py
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


def test_react_optimization_workflow(logger_config: LoggerConfig = None):
    """测试React模式自动优化工作流"""
    if logger_config:
        logger_config.log_step("测试React模式自动优化工作流")
    else:
        print("\n=== 测试React模式自动优化工作流 ===")

    # 初始化执行器
    executor = ExecutorEngine(enable_debug=False)

    workflow_path = project_root / "workflow" / "example" / "react_hydro_optimization.json"

    if not workflow_path.exists():
        if logger_config:
            logger_config.log_result("React工作流文件不存在", {"status": "error"})
        else:
            print(f"React工作流文件不存在: {workflow_path}")
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
            print(f"任务数量: {len(workflow.get('tasks', []))}")
            print(f"执行模式: {workflow.get('execution_mode', 'react')}")
            print(f"目标NSE: {workflow.get('targets', [{}])[0].get('threshold', 0.7)}")
            print(f"最大迭代次数: {workflow.get('targets', [{}])[0].get('max_iterations', 5)}")
            print(f"超时时间: {workflow.get('react_config', {}).get('timeout_minutes', 5)}分钟")

        start_time = time.time()

        # 执行React工作流
        execution_result = executor.execute_workflow(workflow_json, mode="react")

        end_time = time.time()
        total_duration = end_time - start_time

        if logger_config:
            logger_config.log_execution_result(execution_result)
        else:
            print(f"\n执行结果:")
            print(f"  执行ID: {execution_result.execution_id}")
            print(f"  状态: {execution_result.status}")
            print(f"  总执行时长: {total_duration:.2f}秒")
            print(f"  React迭代次数: {len(execution_result.react_iterations) if execution_result.react_iterations else 0}")

        # 分析React迭代过程
        if execution_result.react_iterations:
            print(f"\n=== React迭代详情 ===")
            for i, iteration in enumerate(execution_result.react_iterations, 1):
                print(f"\n迭代 {i}:")
                print(f"  开始时间: {iteration.start_time.strftime('%H:%M:%S')}")
                print(f"  结束时间: {iteration.end_time.strftime('%H:%M:%S')}")
                print(f"  持续时间: {(iteration.end_time - iteration.start_time).total_seconds():.2f}秒")
                print(f"  目标达成: {'是' if iteration.target_achieved else '否'}")
                print(f"  当前指标: {iteration.current_metric}")
                print(f"  目标指标: {iteration.target_metric}")
                print(f"  原因: {iteration.reason}")

                if iteration.adjustments_made:
                    print(f"  调整策略: {iteration.adjustments_made}")

                # 显示该迭代中的任务结果
                if iteration.task_results:
                    for task_id, task_result in iteration.task_results.items():
                        print(f"    任务 {task_id}: {task_result.status}")
                        if task_id == 'task_evaluate':
                            # 提取NSE值
                            nse_value = extract_nse_from_task_result(task_result)
                            if nse_value is not None:
                                print(f"      NSE: {nse_value:.4f}")
                            else:
                                print(f"      NSE: 未能提取")

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
        final_nse_str = f"{final_nse:.4f}" if final_nse is not None else "未知"
        print(f"最终NSE: {final_nse_str}")
        print(f"迭代次数: {len(execution_result.react_iterations) if execution_result.react_iterations else 0}")
        print(f"总执行时间: {total_duration:.2f}秒")

        success_indicator = "[成功]" if final_success else "[未达标]"
        target_indicator = "[达标]" if final_nse and final_nse >= 0.7 else "[未达标]"

        print(f"\n{success_indicator} React优化{'成功' if final_success else '未达标'}")
        if final_nse is not None:
            nse_status = "达标" if final_nse >= 0.7 else "未达标"
            print(f"{target_indicator} NSE结果: {final_nse:.4f} ({nse_status})")

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

        return execution_result.status in ["completed", "success"]

    except Exception as e:
        if logger_config:
            logger_config.log_result("执行React工作流失败", {"error": str(e), "status": "error"})
        else:
            print(f"执行React工作流失败: {e}")
            import traceback
            print(f"详细错误: {traceback.format_exc()}")
        return False


def main():
    """主测试函数"""
    parser = argparse.ArgumentParser(description="测试React模式的自动优化工作流")
    parser.add_argument("--no-log-file", action="store_true", help="不使用日志文件，直接输出到控制台")
    args = parser.parse_args()

    test_name = "react_optimization"
    test_description = "React模式自动优化工作流测试"

    if args.no_log_file:
        # 不使用日志文件的模式
        print("开始React模式自动优化工作流测试...")
        print("=" * 80)

        success = test_react_optimization_workflow()

        print("\n" + "=" * 80)
        print("测试总结:")
        print(f"  React优化工作流: {'[成功]' if success else '[失败]'}")
        print("=" * 80)

        return success
    else:
        # 使用日志系统
        with TestLoggerContext(test_name, test_description) as logger_config:
            logger_config.log_step("开始React优化测试")
            success = test_react_optimization_workflow(logger_config)
            logger_config.log_step("React优化测试", "完成" if success else "失败")

            # 总结
            logger_config.log_result("测试总结", {
                "status": "completed",
                "React优化工作流": "成功" if success else "失败",
                "overall_success": success
            })

            return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)