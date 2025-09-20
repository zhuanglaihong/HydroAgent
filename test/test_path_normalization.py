#!/usr/bin/env python3
"""
测试路径规范化功能
"""

import sys
from pathlib import Path
import json

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from workflow.workflow_assembler import WorkflowAssembler

def test_path_normalization():
    """测试路径规范化功能"""
    print("=== 路径规范化测试 ===\n")
    
    # 创建工作流组装器
    assembler = WorkflowAssembler()
    
    # 测试用例：AI可能生成的各种路径格式
    test_cases = [
        {
            "name": "准备数据任务 - 相对路径",
            "task_data": {
                "task_id": "test_prepare_1",
                "name": "数据准备",
                "action": "prepare_data",
                "parameters": {
                    "data_dir": "camels_11532500"
                }
            }
        },
        {
            "name": "准备数据任务 - 错误绝对路径",
            "task_data": {
                "task_id": "test_prepare_2", 
                "name": "数据准备",
                "action": "prepare_data",
                "parameters": {
                    "data_dir": "/data/camels/11532500"
                }
            }
        },
        {
            "name": "模型率定任务 - 多个路径参数",
            "task_data": {
                "task_id": "test_calibrate_1",
                "name": "模型率定",
                "action": "calibrate_model", 
                "parameters": {
                    "data_dir": "11532500",
                    "result_dir": "calibration_results"
                }
            }
        },
        {
            "name": "模型评估任务 - 结果路径",
            "task_data": {
                "task_id": "test_evaluate_1",
                "name": "模型评估",
                "action": "evaluate_model",
                "parameters": {
                    "result_dir": "./results/test_exp"
                }
            }
        }
    ]
    
    for case in test_cases:
        print(f"测试: {case['name']}")
        print(f"原始参数: {json.dumps(case['task_data']['parameters'], ensure_ascii=False, indent=2)}")
        
        # 执行路径规范化
        normalized_task = assembler._normalize_task_paths(case['task_data'])
        
        print(f"规范化后: {json.dumps(normalized_task['parameters'], ensure_ascii=False, indent=2)}")
        print("-" * 50)

if __name__ == "__main__":
    test_path_normalization()
