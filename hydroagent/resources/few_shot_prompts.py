"""
Author: Claude & zhuanglaihong
Date: 2025-011-20 20:00:00
LastEditTime: 2025-11-20 20:00:00
LastEditors: Claude
Description: Few-shot prompt templates for agent guidance (Tech 4.6)
             少样本提示词模板 - 用于智能体指导
FilePath: \HydroAgent\hydroagent\resources\few_shot_prompts.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from typing import Dict, List

# Few-shot examples for intent recognition
INTENT_EXAMPLES: List[Dict[str, str]] = [
    {
        "user_query": "率定GR4J模型，流域01013500",
        "intent": "calibration",
        "model": "gr4j",
        "basin_id": "01013500",
        "reasoning": "User explicitly mentions '率定' (calibration) and specifies model and basin"
    },
    {
        "user_query": "Calibrate XAJ model for basin camels_11532500 from 2000 to 2010",
        "intent": "calibration",
        "model": "xaj",
        "basin_id": "camels_11532500",
        "time_period": {
            "train": ["2000-01-01", "2010-12-31"]
        },
        "reasoning": "Clear calibration intent with explicit model, basin, and time period"
    },
    {
        "user_query": "评估模型在测试集上的表现",
        "intent": "evaluation",
        "model": "unknown",
        "basin_id": "unknown",
        "reasoning": "User wants evaluation but didn't specify model or basin - need clarification"
    },
    {
        "user_query": "帮我画一下流域的降雨径流过程线",
        "intent": "extension",
        "task_type": "visualization",
        "reasoning": "Custom visualization task not directly supported by hydromodel API"
    }
]

# Few-shot examples for configuration generation
CONFIG_EXAMPLES: List[Dict[str, str]] = [
    {
        "scenario": "Basic GR4J calibration",
        "intent": {
            "model": "gr4j",
            "basin_id": "01013500",
            "train_period": ["2000-01-01", "2005-12-31"]
        },
        "config": """
exp_name: "gr4j_calibration_01013500"
model_name: "gr4j"
basin_id: "01013500"

data:
  datasets-origin: "/path/to/camels/data"
  warmup: 365

training_cfgs:
  algorithm: "SCE_UA"
  ngs: 7
  npg: 9  # 2*4+1 for GR4J (4 parameters)
  npt: 5  # 4+1
  rep: 5
  maxn: 10000

train_period: ["2000-01-01", "2005-12-31"]
test_period: ["2006-01-01", "2010-12-31"]
""",
        "explanation": "Standard SCE-UA configuration for GR4J with 4 parameters"
    },
    {
        "scenario": "XAJ calibration with high complexity",
        "intent": {
            "model": "xaj",
            "basin_id": "camels_11532500",
            "train_period": ["1995-01-01", "2005-12-31"]
        },
        "config": """
exp_name: "xaj_calibration_11532500"
model_name: "xaj"
basin_id: "camels_11532500"

data:
  datasets-origin: "/path/to/camels/data"
  warmup: 730  # 2 years for XAJ

training_cfgs:
  algorithm: "SCE_UA"
  ngs: 10  # More complexes for 15 parameters
  npg: 31  # 2*15+1
  npt: 16  # 15+1
  rep: 10  # More evolution steps
  maxn: 50000  # More evaluations for complex model

train_period: ["1995-01-01", "2005-12-31"]
test_period: ["2006-01-01", "2010-12-31"]
""",
        "explanation": "XAJ has 15 parameters, needs more complexes and iterations"
    }
]

# Few-shot examples for multi-round optimization (Experiment 2)
ADAPTIVE_OPTIMIZATION_EXAMPLES: List[Dict[str, str]] = [
    {
        "round": 1,
        "situation": "Initial calibration, parameter K hit upper bound",
        "analysis": {
            "nse": 0.75,
            "boundary_warnings": [
                "Parameter 'K' = 0.98 is at upper bound (1.0)"
            ]
        },
        "action": "Expand K range",
        "new_param_range": {
            "K": [0.0, 1.5]  # Expanded from [0, 1.0]
        },
        "config_change": """
# In param_range.yaml
K: [0.0, 1.5]  # Expanded by 50%

# In config.yaml
exp_name: "gr4j_calibration_01013500_round2"  # Increment round number
training_cfgs:
  rep: 10  # Increase from 5 for better convergence
"""
    },
    {
        "round": 2,
        "situation": "After range expansion, NSE improved",
        "analysis": {
            "nse": 0.82,
            "nse_improvement": "+9.3%",
            "boundary_warnings": [],
            "convergence": "good"
        },
        "action": "Calibration complete",
        "recommendation": "Parameters converged well within bounds, no further refinement needed"
    }
]

# Few-shot examples for error handling
ERROR_HANDLING_EXAMPLES: List[Dict[str, str]] = [
    {
        "error": "KeyError: 'prec'",
        "traceback": "File 'data_loader.py', line 45, in load_forcing\n  prec = data['prec']",
        "diagnosis": "Variable name mismatch",
        "fix": "Change 'prec' to 'prcp' in configuration or code",
        "agent_action": "Regenerate config with correct variable name 'prcp'"
    },
    {
        "error": "FileNotFoundError: /wrong/path/to/data",
        "traceback": "No such file or directory: '/wrong/path/to/data'",
        "diagnosis": "Data path configuration error",
        "fix": "Update datasets-origin path in config.yaml",
        "agent_action": "Ask user for correct data directory path"
    },
    {
        "error": "ValueError: time data '2000/01/01' does not match format '%Y-%m-%d'",
        "traceback": "File 'time_parser.py', line 23",
        "diagnosis": "Incorrect date format",
        "fix": "Use YYYY-MM-DD format: '2000-01-01'",
        "agent_action": "Regenerate config with correct date format"
    }
]

# System prompts for different scenarios
SYSTEM_PROMPTS: Dict[str, str] = {
    "orchestrator": """You are the Orchestrator of HydroAgent, coordinating multiple specialized agents.

Your role:
1. Analyze user queries and determine which agents to invoke
2. Maintain conversation context and state
3. Handle errors and implement retry logic
4. Aggregate results and present to user

Think step-by-step and explain your reasoning clearly.""",

    "intent_agent": """You are the Intent Agent, responsible for understanding user queries.

Your tasks:
1. Classify intent: calibration / evaluation / simulation / extension
2. Extract basin ID, model name, time periods
3. Validate data availability
4. Fill missing information with reasonable defaults

Be precise and ask for clarification if needed.""",

    "config_agent": """You are the Config Agent, generating hydromodel configurations.

Your tasks:
1. Create valid YAML configuration files
2. Choose appropriate algorithm parameters
3. Implement adaptive parameter range adjustment
4. Validate against hydromodel schema

Follow best practices and explain your parameter choices.""",

    "runner_agent": """You are the Runner Agent, executing hydromodel tasks.

Your tasks:
1. Call hydromodel API (calibrate/evaluate)
2. Monitor execution and capture output
3. Report errors with detailed diagnostics
4. Collect results and logs

Provide clear execution status updates.""",

    "developer_agent": """You are the Developer Agent with advanced analytical capabilities.

Your tasks:
1. Analyze calibration results for insights
2. Detect boundary effects in optimization
3. Generate custom Python code for unsupported features
4. Create visualizations and reports

Provide actionable recommendations based on data."""
}

# Conversation examples (multi-turn)
CONVERSATION_EXAMPLES: List[Dict[str, List[Dict[str, str]]]] = [
    {
        "scenario": "Complete calibration workflow",
        "turns": [
            {
                "role": "user",
                "content": "帮我率定一下GR4J模型"
            },
            {
                "role": "orchestrator",
                "content": "我来帮你率定GR4J模型。首先，我需要了解几个信息..."
            },
            {
                "role": "intent_agent",
                "content": "Intent: calibration, Model: GR4J. 缺少流域ID和时间段。"
            },
            {
                "role": "orchestrator",
                "content": "请问你想用哪个流域的数据？建议使用 CAMELS 数据集中的流域ID。"
            },
            {
                "role": "user",
                "content": "用01013500这个流域，2000年到2010年的数据"
            },
            {
                "role": "config_agent",
                "content": "生成配置文件：训练期2000-2005，测试期2006-2010，使用SCE-UA算法..."
            },
            {
                "role": "runner_agent",
                "content": "开始率定... 进度: 50%... 完成！NSE=0.78"
            },
            {
                "role": "developer_agent",
                "content": "率定结果分析：NSE=0.78表现良好。参数X1触碰上界，建议扩大范围。"
            },
            {
                "role": "orchestrator",
                "content": "率定完成！NSE=0.78。结果已保存到workspace/。是否需要进一步优化？"
            }
        ]
    },
    {
        "scenario": "Adaptive optimization (Experiment 2)",
        "turns": [
            {
                "role": "user",
                "content": "上次率定的NSE不太理想，能不能再优化一下？"
            },
            {
                "role": "developer_agent",
                "content": "分析上次结果：参数K触碰上界(1.0)，这可能限制了优化空间。"
            },
            {
                "role": "config_agent",
                "content": "建议扩大K的范围到[0, 1.5]，同时增加rep到10以提高收敛性。"
            },
            {
                "role": "orchestrator",
                "content": "启动第2轮自适应优化..."
            },
            {
                "role": "runner_agent",
                "content": "第2轮率定完成！NSE=0.85，提升了9.3%"
            },
            {
                "role": "developer_agent",
                "content": "所有参数收敛良好，未触碰边界。建议使用此结果。"
            }
        ]
    }
]

# Code generation examples (Experiment 3)
CODE_GENERATION_EXAMPLES: List[Dict[str, str]] = [
    {
        "user_request": "生成降雨径流过程线图",
        "task_description": "Plot precipitation and streamflow time series for visual analysis",
        "generated_code": """
import matplotlib.pyplot as plt
import pandas as pd
from hydrodataset import Camels

# Load data
basin_id = "01013500"
camels = Camels()
data = camels.read_target_cols(
    basin_id=basin_id,
    time_range=["2000-01-01", "2005-12-31"],
    target_cols=["prcp", "streamflow"]
)

# Create figure
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

# Plot precipitation
ax1.bar(data.index, data['prcp'], color='steelblue', alpha=0.7)
ax1.set_ylabel('Precipitation (mm)', fontsize=12)
ax1.set_title(f'Basin {basin_id}: Precipitation and Streamflow', fontsize=14)
ax1.invert_yaxis()  # Precipitation from top

# Plot streamflow
ax2.plot(data.index, data['streamflow'], color='darkred', linewidth=1.5)
ax2.set_ylabel('Streamflow (mm/day)', fontsize=12)
ax2.set_xlabel('Date', fontsize=12)

plt.tight_layout()
plt.savefig('rainfall_runoff_hydrograph.png', dpi=300)
print("Plot saved: rainfall_runoff_hydrograph.png")
""",
        "explanation": "This code loads data using hydrodataset and creates a dual-axis plot"
    },
    {
        "user_request": "计算多个流域的平均NSE",
        "task_description": "Calculate average NSE across multiple basins from calibration results",
        "generated_code": """
import json
from pathlib import Path
import numpy as np

# Directory containing results
results_dir = Path("workspace/multi_basin_calibration/results")

nse_values = []
basin_results = {}

# Iterate through result files
for json_file in results_dir.glob("**/calibration_results.json"):
    with open(json_file, 'r') as f:
        data = json.load(f)

    basin_id = data.get('basin_id', 'unknown')
    nse = data.get('nse', None)

    if nse is not None:
        nse_values.append(nse)
        basin_results[basin_id] = nse
        print(f"Basin {basin_id}: NSE = {nse:.4f}")

# Calculate statistics
if nse_values:
    avg_nse = np.mean(nse_values)
    std_nse = np.std(nse_values)

    print(f"\\nSummary Statistics:")
    print(f"Average NSE: {avg_nse:.4f}")
    print(f"Std Dev: {std_nse:.4f}")
    print(f"Min NSE: {np.min(nse_values):.4f}")
    print(f"Max NSE: {np.max(nse_values):.4f}")

    # Save summary
    summary = {
        "average_nse": float(avg_nse),
        "std_nse": float(std_nse),
        "basin_results": basin_results
    }

    with open("nse_summary.json", 'w') as f:
        json.dump(summary, f, indent=2)
    print("\\nSummary saved: nse_summary.json")
""",
        "explanation": "This code aggregates NSE values from multiple calibration results"
    }
]


def get_few_shot_prompt(agent_type: str, scenario: str = "default") -> str:
    """
    Get few-shot prompt for specific agent and scenario.
    获取特定智能体和场景的少样本提示词。

    Args:
        agent_type: Agent identifier (orchestrator, intent, config, etc.)
        scenario: Scenario name (default, adaptive, error_handling, etc.)

    Returns:
        Formatted few-shot prompt string
    """
    if agent_type == "intent" and scenario == "default":
        examples_text = "\n\n".join([
            f"Example {i+1}:\nUser: {ex['user_query']}\nIntent: {ex['intent']}\n"
            f"Model: {ex.get('model', 'N/A')}\nBasin: {ex.get('basin_id', 'N/A')}\n"
            f"Reasoning: {ex['reasoning']}"
            for i, ex in enumerate(INTENT_EXAMPLES)
        ])
        return f"{SYSTEM_PROMPTS['intent_agent']}\n\nHere are some examples:\n\n{examples_text}"

    elif agent_type == "config" and scenario == "default":
        examples_text = "\n\n".join([
            f"Example {i+1}: {ex['scenario']}\n{ex['config']}\n"
            f"Explanation: {ex['explanation']}"
            for i, ex in enumerate(CONFIG_EXAMPLES)
        ])
        return f"{SYSTEM_PROMPTS['config_agent']}\n\nExamples:\n\n{examples_text}"

    elif agent_type == "developer" and scenario == "adaptive":
        examples_text = "\n\n".join([
            f"Round {ex['round']}:\nSituation: {ex['situation']}\n"
            f"Analysis: {ex['analysis']}\nAction: {ex['action']}"
            for ex in ADAPTIVE_OPTIMIZATION_EXAMPLES
        ])
        return f"{SYSTEM_PROMPTS['developer_agent']}\n\nAdaptive optimization examples:\n\n{examples_text}"

    else:
        # Return default system prompt
        return SYSTEM_PROMPTS.get(agent_type, "")


def get_error_handling_guidance(error_type: str) -> str:
    """
    Get error handling guidance for specific error type.
    获取特定错误类型的处理指导。

    Args:
        error_type: Error type (KeyError, FileNotFoundError, etc.)

    Returns:
        Error handling guidance string
    """
    for ex in ERROR_HANDLING_EXAMPLES:
        if error_type in ex["error"]:
            return f"""
Error: {ex['error']}
Diagnosis: {ex['diagnosis']}
Fix: {ex['fix']}
Agent Action: {ex['agent_action']}
"""
    return "No specific guidance available for this error type."
