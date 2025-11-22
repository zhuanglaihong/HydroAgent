"""
实验2B - 缺省信息补全
查询: "帮我率定流域 01013500"
验证: 自动补全model_name, algorithm, time_period
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from exp_1_standard_calibration import run_experiment, setup_logging, main as base_main
import argparse

QUERY = "帮我率定流域 01013500"

def main():
    parser = argparse.ArgumentParser(description='实验2B：缺省信息补全')
    parser.add_argument('--backend', type=str, default='api', choices=['ollama', 'api'])
    parser.add_argument('--model', type=str, default=None)
    parser.add_argument('--mock', action='store_true')
    args = parser.parse_args()

    log_file = setup_logging("exp_2b_missing_info")

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║             实验2B：缺省信息补全                             ║")
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
