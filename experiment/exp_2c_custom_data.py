"""
Author: Claude
Date: 2025-01-22 21:30:00
LastEditTime: 2025-01-22 21:30:00
LastEditors: Claude
Description: 实验2C - 自定义数据路径
             Experiment 2C - Custom Data Path
FilePath: /HydroAgent/experiment/exp_2c_custom_data.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

实验目标:
- 验证系统能够识别并使用自定义数据路径
- 测试数据源类型识别(custom vs CAMELS_US)

测试查询:
"用我 D 盘 my_data 文件夹里的数据跑一下模型"
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from exp_1_standard_calibration import run_experiment, setup_logging, main as base_main
import argparse

QUERY = "用我 D 盘 my_data 文件夹里的数据跑一下模型"


def main():
    parser = argparse.ArgumentParser(description="实验2C：自定义数据路径")
    parser.add_argument("--backend", type=str, default="api", choices=["ollama", "api"])
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()

    log_file = setup_logging("exp_2c_custom_data")

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║             实验2C：自定义数据路径                           ║")
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
