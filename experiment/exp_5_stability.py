"""
Author: Claude
Date: 2025-01-22 21:30:00
LastEditTime: 2025-01-22 21:30:00
LastEditors: Claude
Description: 实验5 - 稳定性验证（重复实验）
             Experiment 5 - Stability Verification (Repeated Experiments)
FilePath: /HydroAgent/experiment/exp_5_stability.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

实验目标:
- 验证系统能够执行重复实验
- 使用不同随机种子多次率定
- 进行统计分析评估稳定性

测试查询:
"重复率定流域 01013500 五次，使用不同随机种子"
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from exp_1_standard_calibration import run_experiment, setup_logging, main as base_main
import argparse

QUERY = "重复率定流域 01013500 五次，使用不同随机种子"

def main():
    parser = argparse.ArgumentParser(description='实验5：稳定性验证')
    parser.add_argument('--backend', type=str, default='api', choices=['ollama', 'api'])
    parser.add_argument('--model', type=str, default=None)
    parser.add_argument('--mock', action='store_true')
    args = parser.parse_args()

    log_file = setup_logging("exp_5_stability")

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║             实验5：稳定性验证（重复实验）                     ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"\n📝 日志文件: {log_file}\n")
    print(f"查询: {QUERY}\n")
    print("⚠️  注意: 此实验需要运行5次率定，耗时较长（约10-30分钟）\n")

    # 临时修改查询
    import exp_1_standard_calibration
    original_run = exp_1_standard_calibration.run_experiment

    def modified_run(llm, use_mock):
        # 修改查询
        import hydroagent.agents.intent_agent
        original_process = hydroagent.agents.intent_agent.IntentAgent.process

        def custom_process(self, input_data):
            # 替换查询
            if "query" in input_data:
                input_data["query"] = QUERY
            return original_process(self, input_data)

        hydroagent.agents.intent_agent.IntentAgent.process = custom_process
        result = original_run(llm, use_mock)
        hydroagent.agents.intent_agent.IntentAgent.process = original_process
        return result

    exp_1_standard_calibration.run_experiment = modified_run
    return base_main()

if __name__ == "__main__":
    sys.exit(main())
