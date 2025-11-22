"""
Author: Claude
Date: 2025-01-22 21:30:00
LastEditTime: 2025-01-22 21:30:00
LastEditors: Claude
Description: 实验4 - 扩展分析（率定 + 自定义分析）
             Experiment 4 - Extended Analysis (Calibration + Custom Analysis)
FilePath: /HydroAgent/experiment/exp_4_extended_analysis.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

实验目标:
- 验证系统能够识别并计划扩展分析任务
- 执行标准率定后，进行自定义分析（径流系数、FDC）
- 测试DeveloperAgent的代码生成能力

测试查询:
"率定完成后，请帮我计算流域的径流系数，并画一张流路历时曲线 FDC"
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from exp_1_standard_calibration import run_experiment, setup_logging, main as base_main
import argparse

QUERY = "率定完成后，请帮我计算流域的径流系数，并画一张流路历时曲线 FDC"

def main():
    parser = argparse.ArgumentParser(description='实验4：扩展分析')
    parser.add_argument('--backend', type=str, default='api', choices=['ollama', 'api'])
    parser.add_argument('--model', type=str, default=None)
    parser.add_argument('--mock', action='store_true')
    args = parser.parse_args()

    log_file = setup_logging("exp_4_extended_analysis")

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║             实验4：扩展分析                                  ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"\n📝 日志文件: {log_file}\n")
    print(f"查询: {QUERY}\n")

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
