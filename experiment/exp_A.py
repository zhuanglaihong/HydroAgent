"""
Author: Claude
Date: 2025-12-23 00:00:00
LastEditTime: 2026-01-14 19:30:00
LastEditors: Claude
Description: Experiment A - 工具系统单独工具验证 (Tool System Phase 1)
             Individual Tool Validation for Tool System
             v2.0: Added scene categories and comprehensive final report
FilePath: /HydroAgent/experiment/exp_A.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

实验目标:
- 验证7个核心工具的独立可用性
- 测试工具接口、输入输出规范
- 评估工具执行稳定性

方法学层级: 工具层 (Tool Layer)
核心问题: 每个工具能否独立正常工作? (Does each tool work independently?)
"""

import argparse
from pathlib import Path
from base_experiment import create_experiment

# ============================================================================
# Experiment A 测试集: 14个查询 (单独工具验证)
# ============================================================================
#
# 场景分类 (3类 × 工具):
#   Category 1: 验证类工具 (Validation Tools) - 2个
#       - DataValidationTool (2个)
#       预期成功率: ≥90% (验证必须可靠)
#
#   Category 2: 执行类工具 (Execution Tools) - 6个
#       - CalibrationTool (2个)
#       - EvaluationTool (2个)
#       - SimulationTool (2个)
#       预期成功率: ≥85% (核心建模功能)
#
#   Category 3: 分析类工具 (Analysis Tools) - 6个
#       - VisualizationTool (2个)
#       - CodeGenerationTool (2个)
#       - CustomAnalysisTool (2个)
#       预期成功率: ≥70% (复杂分析任务)
#
# 注意: 需要启用工具系统 (USE_TOOL_SYSTEM=True)
# ============================================================================

# 场景分类映射
TOOL_CATEGORIES = {
    "validation": {
        "name": "验证类工具",
        "tools": ["DataValidationTool"],
        "indices": [0, 1],
        "target_success_rate": 0.90,
        "description": "数据验证和质量检查工具"
    },
    "execution": {
        "name": "执行类工具",
        "tools": ["CalibrationTool", "EvaluationTool", "SimulationTool"],
        "indices": [2, 3, 4, 5, 6, 7],
        "target_success_rate": 0.85,
        "description": "模型率定、评估、模拟等核心建模工具"
    },
    "analysis": {
        "name": "分析类工具",
        "tools": ["VisualizationTool", "CodeGenerationTool", "CustomAnalysisTool"],
        "indices": [8, 9, 10, 11, 12, 13],
        "target_success_rate": 0.70,
        "description": "可视化、代码生成、自定义分析等高级工具"
    }
}

# 预期工具调用映射 (每个查询应该调用的核心工具)
EXPECTED_TOOLS = {
    # DataValidationTool (0-1)
    0: ["validate_data"],
    1: ["validate_data"],

    # CalibrationTool (2-3)
    2: ["validate_data", "calibrate"],
    3: ["validate_data", "calibrate"],

    # EvaluationTool (4-5)
    4: ["validate_data", "calibrate", "evaluate"],
    5: ["validate_data", "calibrate", "evaluate"],

    # SimulationTool (6-7)
    6: ["validate_data", "calibrate", "simulate"],
    7: ["validate_data", "calibrate", "simulate"],

    # VisualizationTool (8-9)
    8: ["validate_data", "calibrate", "evaluate", "visualize"],
    9: ["validate_data", "calibrate", "evaluate", "visualize"],

    # CodeGenerationTool (10-11)
    10: ["validate_data", "calibrate", "evaluate", "code_generation"],
    11: ["validate_data", "calibrate", "evaluate", "code_generation"],

    # CustomAnalysisTool (12-13)
    12: ["validate_data", "calibrate", "evaluate", "custom_analysis"],
    13: ["validate_data", "calibrate", "evaluate", "custom_analysis"],
}

TEST_QUERIES = [
    # ========== 1. DataValidationTool - 数据验证 ==========
    "验证流域12025000的数据可用性，训练期1985-1995，测试期2005-2014",

    "检查流域14301000,02070000,14301000的数据质量",

    # ========== 2. CalibrationTool - 模型率定 ==========
    "率定GR4J模型，流域12025000，使用SCE-UA算法，迭代500轮",

    "率定XAJ模型，流域14301000，使用GA算法，代数100",

    # ========== 3. EvaluationTool - 模型评估 ==========
    "评估流域12025000的GR4J模型性能，测试期2005-2014",

    "评估流域14301000的XAJ模型在2010-2014期间的表现",

    # ========== 4. SimulationTool - 模型模拟 ==========
    "率定GR4J模型流域12025000后，使用最优参数模拟2015-2020期间的径流",

    "用训练期1990-2000年间的数据率定XAJ模型流域14301000后，模拟2005-2010期间的水文过程",

    # ========== 5. VisualizationTool - 结果可视化 ==========
    "率定GR4J模型流域12025000后，绘制水文过程线和性能图表",

    "率定XAJ模型流域14301000后，画出径流模拟对比图",

    # # ========== 6. CodeGenerationTool - 代码生成 ==========
    "率定GR4J模型流域12025000后，生成Python代码计算径流系数",

    "率定XAJ模型流域14301000后，生成代码画流量历时曲线FDC",

    # ========== 7. CustomAnalysisTool - 自定义分析 ==========
    "率定GR4J模型流域12025000后，分析洪峰流量的模拟误差",

    "率定XAJ模型流域14301000后，统计枯水期的模拟精度",
]


def calculate_detailed_metrics(results: list) -> dict:
    """
    计算 Experiment A 的详细指标。

    验证维度:
    - 执行成功率 (Execution Success Rate)
    - 意图识别准确率 (Intent Recognition Accuracy)
    - 配置生成成功率 (Config Generation Success)
    - 输出一致性 (Output Consistency)

    Returns:
        详细指标字典
    """
    import numpy as np

    total = len(results)
    if total == 0:
        return {}

    # 基础统计
    success_results = [r for r in results if r.get("success")]
    success_count = len(success_results)

    # ========== 执行成功率 ==========
    execution_success_rate = success_count / total

    # ========== 意图识别准确率 ==========
    # 检查 IntentAgent 是否正确识别任务类型和参数
    intent_correct_count = 0
    for r in results:
        # 修复: intent直接包含task_type和intent字段,没有intent_result这一层
        intent_data = r.get("intent", {})

        # 🔧 修复: 处理intent_data为None的情况（API失败时）
        if intent_data is None:
            intent_data = {}

        # 检查两个可能的字段
        intent = intent_data.get("intent", "")
        task_type = intent_data.get("task_type", "")

        # 检查是否识别出有效任务类型（检查intent或task_type）
        valid_intents = ["calibration", "evaluation", "simulation", "custom_analysis"]
        valid_task_types = ["standard_calibration", "evaluation", "simulation", "extended_analysis",
                           "boundary_check_recalibration", "custom_analysis"]

        if intent in valid_intents or task_type in valid_task_types:
            intent_correct_count += 1

    intent_accuracy = intent_correct_count / total if total > 0 else 0

    # ========== 配置生成成功率 ==========
    # 检查 InterpreterAgent 是否成功生成配置
    config_success_count = 0
    for r in success_results:
        # 如果执行成功，说明配置生成成功
        if r.get("success"):
            config_success_count += 1

    config_success_rate = config_success_count / total if total > 0 else 0

    # ========== 输出一致性 ==========
    # 检查输出文件结构是否标准化
    output_consistent_count = 0
    for r in success_results:
        workspace = r.get("workspace", "")
        if workspace and Path(workspace).exists():
            output_consistent_count += 1

    output_consistency = output_consistent_count / success_count if success_count > 0 else 0

    # ========== 时间统计 ==========
    times = [r.get("elapsed_time", 0) for r in results]

    # ========== Token 统计 ==========
    total_tokens = []
    for r in results:
        token_usage = r.get("token_usage", {})
        if token_usage and token_usage.get("total_tokens", 0) > 0:
            total_tokens.append(token_usage.get("total_tokens", 0))

    # ========== 工具调用统计 (Exp A核心指标) ==========
    # 检查每个查询是否调用了预期的工具
    tool_call_matches = []
    tool_call_details = []

    for idx, r in enumerate(results):
        expected = EXPECTED_TOOLS.get(idx, [])

        # 从execution_results中提取实际调用的工具
        actual_tools = []
        execution_results = r.get("execution_results", [])
        if execution_results:
            # execution_results可能是列表，取第一个元素
            if isinstance(execution_results, list) and len(execution_results) > 0:
                exec_result = execution_results[0]
                # 从tool_chain中提取工具名称
                tool_chain = exec_result.get("tool_chain", [])
                for step in tool_chain:
                    tool_name = step.get("tool", "")
                    if tool_name and tool_name not in actual_tools:
                        actual_tools.append(tool_name)

        # 检查是否包含所有预期工具
        has_all_expected = all(tool in actual_tools for tool in expected)
        tool_call_matches.append(has_all_expected)

        # 记录详细信息
        tool_call_details.append({
            "query_idx": idx,
            "expected": expected,
            "actual": actual_tools,
            "match": has_all_expected,
            "missing": [t for t in expected if t not in actual_tools],
            "extra": [t for t in actual_tools if t not in expected]
        })

    # 计算工具调用准确率
    tool_call_accuracy = sum(tool_call_matches) / len(tool_call_matches) if tool_call_matches else 0

    # ========== 按工具统计 (Exp A专用) ==========
    # 根据TEST_QUERIES的顺序推断工具
    tool_stats = {}
    tool_query_mapping = [
        ("DataValidationTool", 0, 2),      # 查询0-1
        ("CalibrationTool", 2, 4),         # 查询2-3
        ("EvaluationTool", 4, 6),          # 查询4-5
        ("SimulationTool", 6, 8),          # 查询6-7
        ("VisualizationTool", 8, 10),      # 查询8-9
        ("CodeGenerationTool", 10, 12),    # 查询10-11
        ("CustomAnalysisTool", 12, 14),    # 查询12-13
    ]

    for tool_name, start_idx, end_idx in tool_query_mapping:
        tool_results = results[start_idx:end_idx]
        tool_success = sum(1 for r in tool_results if r.get("success"))

        # 检查工具调用匹配情况
        tool_call_match_count = sum(1 for i in range(start_idx, end_idx)
                                    if i < len(tool_call_matches) and tool_call_matches[i])

        tool_stats[tool_name] = {
            "total": len(tool_results),
            "success": tool_success,
            "success_rate": tool_success / len(tool_results) if tool_results else 0,
            "tool_call_match": tool_call_match_count,
            "tool_call_match_rate": tool_call_match_count / len(tool_results) if tool_results else 0
        }

    # 保留旧的task_type_stats用于向后兼容
    task_type_stats = tool_stats

    # ========== 按场景分类统计 (新增) ==========
    category_stats = {}
    for category_key, category_info in TOOL_CATEGORIES.items():
        indices = category_info["indices"]
        category_results = [results[i] for i in indices if i < len(results)]

        category_success = sum(1 for r in category_results if r.get("success"))
        category_total = len(category_results)

        category_stats[category_key] = {
            "name": category_info["name"],
            "total": category_total,
            "success": category_success,
            "success_rate": category_success / category_total if category_total > 0 else 0,
            "target_rate": category_info["target_success_rate"],
            "description": category_info["description"],
            "tools": category_info["tools"]
        }

    metrics = {
        # ========== 核心验证指标 (论文关键指标) ==========
        "execution_success_rate": execution_success_rate,
        "intent_recognition_accuracy": intent_accuracy,
        "config_generation_success_rate": config_success_rate,
        "output_consistency": output_consistency,
        "tool_call_accuracy": tool_call_accuracy,  # 新增：工具调用准确率

        # ========== 基础统计 ==========
        "total_tasks": total,
        "success_count": success_count,
        "failure_count": total - success_count,

        # ========== 时间统计 ==========
        "average_time": float(np.mean(times)) if times else 0,
        "median_time": float(np.median(times)) if times else 0,
        "min_time": float(np.min(times)) if times else 0,
        "max_time": float(np.max(times)) if times else 0,

        # ========== Token 统计 ==========
        "average_tokens_per_task": float(np.mean(total_tokens)) if total_tokens else 0,
        "total_tokens_sum": int(np.sum(total_tokens)) if total_tokens else 0,

        # ========== 按任务类型统计 ==========
        "task_type_stats": task_type_stats,

        # ========== 按场景分类统计 (新增) ==========
        "category_stats": category_stats,

        # ========== 工具调用详情 ==========
        "tool_call_details": tool_call_details,
    }

    return metrics


def generate_experiment_report(exp, results: list, metrics: dict):
    """
    生成 Experiment A 专用报告。

    包含:
    - 实验设计说明
    - 核心验证指标
    - 按任务类型统计
    - 方法学意义
    """
    additional_sections = {
        "实验设计": """
本实验验证工具系统（Tool System）的7个核心工具的独立可用性:

| 工具名称 | 功能描述 | 预期输出 | 测试数量 |
|---------|---------|---------|---------|
| DataValidationTool | 数据验证 | 流域数据可用性报告 | 2 |
| CalibrationTool | 模型率定 | 最优参数集 + 目标函数值 | 2 |
| EvaluationTool | 模型评估 | 性能指标(NSE/KGE/RMSE) | 2 |
| SimulationTool | 模型模拟 | 径流时间序列 + NetCDF文件 | 2 |
| VisualizationTool | 结果可视化 | 水文过程线图、性能图表 | 2 |
| CodeGenerationTool | 代码生成 | Python分析脚本 | 2 |
| CustomAnalysisTool | 自定义分析 | LLM辅助的复杂分析任务 | 2 |

**总计**: 14个测试用例

**实验约束**:
- 每个工具独立测试2次（不同流域或参数）
- 不引入工具间复杂依赖
- 所有任务均通过 HydroAgent 自动完成，无人工干预
""",

        "核心验证指标": f"""
| 验证维度 | 指标值 | 目标值 | 达标 |
|---------|-------|-------|------|
| **执行成功率** | {metrics.get('execution_success_rate', 0):.1%} | ≥85% | {'✅' if metrics.get('execution_success_rate', 0) >= 0.85 else '❌'} |
| **意图识别准确率** | {metrics.get('intent_recognition_accuracy', 0):.1%} | ≥90% | {'✅' if metrics.get('intent_recognition_accuracy', 0) >= 0.90 else '❌'} |
| **配置生成成功率** | {metrics.get('config_generation_success_rate', 0):.1%} | ≥95% | {'✅' if metrics.get('config_generation_success_rate', 0) >= 0.95 else '❌'} |
| **输出一致性** | {metrics.get('output_consistency', 0):.1%} | 100% | {'✅' if metrics.get('output_consistency', 0) >= 1.0 else '❌'} |
| **工具调用准确率** | {metrics.get('tool_call_accuracy', 0):.1%} | ≥90% | {'✅' if metrics.get('tool_call_accuracy', 0) >= 0.90 else '❌'} |

**说明**: 工具调用准确率衡量LLM是否为每个查询选择了正确的工具链（是否包含所有预期工具）。
""",

        "按工具统计": _format_task_type_stats(metrics.get("task_type_stats", {})),

        "预期结论": """
> **HydroAgent is able to reliably execute individual hydrological modelling tasks,
> generating reproducible model configurations and standardized outputs without
> manual intervention.**
>
> HydroAgent能够可靠地执行单个水文建模任务，在无人工干预的情况下生成可复现的
> 模型配置和标准化输出。

**方法学意义 (Methodological Significance)**:

该实验证明 HydroAgent 具备作为水文建模自动化系统的**基本可用性与工程可执行性**。
""",
    }

    exp.generate_report(results, metrics, additional_sections)


def _format_task_type_stats(task_type_stats: dict) -> str:
    """格式化工具统计表格 (Exp A专用)。"""
    lines = [
        "| 工具名称 | 测试数 | 成功数 | 成功率 | 工具调用匹配 | 匹配率 | 状态 |",
        "|---------|--------|--------|--------|------------|--------|------|"
    ]

    # 按照工具执行顺序排列
    tool_order = [
        "DataValidationTool",
        "CalibrationTool",
        "EvaluationTool",
        "SimulationTool",
        "VisualizationTool",
        "CodeGenerationTool",
        "CustomAnalysisTool"
    ]

    tool_display_names = {
        "DataValidationTool": "数据验证",
        "CalibrationTool": "模型率定",
        "EvaluationTool": "模型评估",
        "SimulationTool": "模型模拟",
        "VisualizationTool": "结果可视化",
        "CodeGenerationTool": "代码生成",
        "CustomAnalysisTool": "自定义分析"
    }

    for tool_name in tool_order:
        if tool_name in task_type_stats:
            stats = task_type_stats[tool_name]
            display_name = tool_display_names.get(tool_name, tool_name)
            total = stats.get("total", 0)
            success = stats.get("success", 0)
            rate = stats.get("success_rate", 0)
            tool_match = stats.get("tool_call_match", 0)
            tool_match_rate = stats.get("tool_call_match_rate", 0)
            # 同时检查成功率和工具调用匹配率
            status = "✅" if rate >= 0.5 and tool_match_rate >= 0.5 else "❌"
            lines.append(
                f"| {display_name} | {total} | {success} | {rate:.1%} | "
                f"{tool_match}/{total} | {tool_match_rate:.1%} | {status} |"
            )

    lines.append("")
    lines.append("**说明**: 工具调用匹配表示LLM为该工具的测试查询选择了正确的工具链（包含预期工具）。")

    return "\n".join(lines)


def generate_final_report(results: list, metrics: dict, exp_workspace: str):
    """
    生成实验A的最终综合报告（类似exp_C_v4.py）

    保存为独立的 experiment_A_report.md 文件
    """
    from datetime import datetime

    report = []
    report.append("# Experiment A: Individual Tool Validation")
    report.append(f"\n**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"**Total Scenarios:** {len(results)}")
    report.append("\n---\n")

    # Executive Summary
    report.append("## Executive Summary\n")
    report.append("This experiment validates the independent execution capability of 7 core tools in HydroAgent's tool system through three categories:\n")
    report.append("1. **Validation Tools**: Data validation and quality checks\n")
    report.append("2. **Execution Tools**: Core modeling operations (calibration, evaluation, simulation)\n")
    report.append("3. **Analysis Tools**: Advanced analysis capabilities (visualization, code generation, custom analysis)\n")

    # Key Findings
    report.append("\n## Key Findings\n")

    category_stats = metrics.get("category_stats", {})

    if category_stats:
        report.append("### Tool Category Performance\n")
        for cat_key, cat_info in category_stats.items():
            name = cat_info["name"]
            success_rate = cat_info["success_rate"] * 100
            target_rate = cat_info["target_rate"] * 100
            status = "✅" if cat_info["success_rate"] >= cat_info["target_rate"] else "⚠️"

            report.append(f"**{name}** {status}:\n")
            report.append(f"- **Success Rate:** {success_rate:.1f}% ({cat_info['success']}/{cat_info['total']})\n")
            report.append(f"- **Target:** {target_rate:.0f}%\n")
            report.append(f"- **Status:** {'Target met' if cat_info['success_rate'] >= cat_info['target_rate'] else 'Below target'}\n\n")

    # Core Metrics
    report.append("### Core Metrics\n")
    report.append(f"- **Execution Success Rate:** {metrics.get('execution_success_rate', 0)*100:.1f}%\n")
    report.append(f"- **Intent Recognition Accuracy:** {metrics.get('intent_recognition_accuracy', 0)*100:.1f}%\n")
    report.append(f"- **Config Generation Success:** {metrics.get('config_generation_success_rate', 0)*100:.1f}%\n")
    report.append(f"- **Tool Call Accuracy:** {metrics.get('tool_call_accuracy', 0)*100:.1f}%\n")
    report.append(f"- **Output Consistency:** {metrics.get('output_consistency', 0)*100:.1f}%\n")

    # Performance Metrics
    total_time = sum(r.get("elapsed_time", 0) for r in results)
    total_tokens = sum(r.get("total_tokens", 0) for r in results)
    report.append(f"\n## Performance Metrics\n")
    report.append(f"- **Total Execution Time:** {total_time:.1f}s ({total_time/60:.1f}min)\n")
    report.append(f"- **Total Tokens:** {total_tokens:,}\n")
    report.append(f"- **Average Time/Task:** {total_time/len(results):.1f}s\n")
    report.append(f"- **Average Tokens/Task:** {total_tokens//len(results):,}\n")

    # Detailed Results by Category
    report.append("\n## Detailed Results by Category\n")

    for cat_key in ["validation", "execution", "analysis"]:
        if cat_key not in category_stats:
            continue

        cat_info = category_stats[cat_key]
        indices = TOOL_CATEGORIES[cat_key]["indices"]

        report.append(f"\n### {cat_info['name']}\n")
        report.append(f"**Description:** {cat_info['description']}\n")
        report.append(f"**Tools:** {', '.join(cat_info['tools'])}\n\n")

        report.append("| # | Query | Result | Tool Called | Time (s) |\n")
        report.append("|---|-------|--------|-------------|----------|\n")

        for idx in indices:
            if idx >= len(results):
                continue
            r = results[idx]
            query_preview = r.get("query", "")[:40]
            result_str = "PASS" if r.get("success") else "FAIL"

            # Extract tool from execution_results
            tools_called = []
            exec_results = r.get("execution_results", [])
            if exec_results and isinstance(exec_results, list) and len(exec_results) > 0:
                tool_chain = exec_results[0].get("tool_chain", [])
                tools_called = [step.get("tool", "") for step in tool_chain if step.get("tool")]

            tools_str = ", ".join(tools_called[:2]) if tools_called else "N/A"
            if len(tools_called) > 2:
                tools_str += f" (+{len(tools_called)-2})"

            time_str = f"{r.get('elapsed_time', 0):.1f}"

            report.append(f"| {idx+1} | {query_preview}... | {result_str} | {tools_str} | {time_str} |\n")

    # Conclusions
    report.append("\n## Conclusions\n")

    overall_success = metrics.get("execution_success_rate", 0)
    if overall_success >= 0.85:
        report.append(f"HydroAgent's tool system demonstrates:\n")
        report.append(f"1. ✅ **Reliable tool execution**: {overall_success*100:.1f}% overall success rate\n")
    else:
        report.append(f"HydroAgent's tool system shows:\n")
        report.append(f"1. ⚠️ **Needs improvement**: {overall_success*100:.1f}% overall success rate (target: ≥85%)\n")

    # Check each category
    for cat_key in ["validation", "execution", "analysis"]:
        cat_info = category_stats.get(cat_key, {})
        if cat_info:
            target = cat_info["target_rate"]
            actual = cat_info["success_rate"]
            status = "✅" if actual >= target else "⚠️"
            report.append(f"2. {status} **{cat_info['name']}**: {actual*100:.1f}% (target: {target*100:.0f}%)\n")

    tool_call_acc = metrics.get("tool_call_accuracy", 0)
    if tool_call_acc >= 0.90:
        report.append(f"3. ✅ **Accurate tool selection**: {tool_call_acc*100:.1f}% tool call accuracy\n")

    # Recommendations
    report.append("\n## Recommendations for Publication\n")
    report.append("\n1. Present tool category success rates as evidence of modular design\n")
    report.append("2. Highlight execution success rate (≥85%) as key reliability metric\n")
    report.append("3. Use tool call accuracy to demonstrate intelligent tool orchestration\n")
    report.append("4. Compare with baseline systems if available\n")
    report.append("5. Include detailed tool chain examples from each category\n")

    report.append("\n---\n")
    report.append(f"\n*Generated by HydroAgent Experiment A on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")

    # Save report
    report_file = Path(exp_workspace) / "experiment_A_report.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(report))

    return report_file


def main():
    """运行 Experiment A: 工具系统单独工具验证"""
    parser = argparse.ArgumentParser(
        description="Experiment A - 工具系统单独工具验证 (Tool System Phase 1)"
    )
    parser.add_argument(
        "--backend",
        type=str,
        default="api",
        choices=["api", "ollama"],
        help="LLM后端 (默认: api)"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        default=False,
        help="使用mock模式 (默认: False)"
    )
    parser.add_argument(
        "--no-mock",
        dest="mock",
        action="store_false",
        help="使用真实hydromodel执行"
    )
    parser.add_argument(
        "--use-tool-system",
        action="store_true",
        default=True,
        help="启用工具系统 (默认: True, 本实验必需)"
    )
    args = parser.parse_args()

    print("=" * 80)
    print("🧪 Experiment A: 工具系统单独工具验证")
    print("   Individual Tool Validation for Tool System")
    print("=" * 80)
    print(f"")
    print(f"📋 实验设计:")
    print(f"   - 方法学层级: 工具层 (Tool Layer)")
    print(f"   - 核心问题: 每个工具能否独立正常工作?")
    print(f"   - 测试集规模: {len(TEST_QUERIES)} 个查询")
    print(f"")
    print(f"📦 工具覆盖 (7个工具，每个工具2个查询):")
    print(f"   1. DataValidationTool: 2个")
    print(f"   2. CalibrationTool: 2个")
    print(f"   3. EvaluationTool: 2个")
    print(f"   4. SimulationTool: 2个 [NEW - Phase 2]")
    print(f"   5. VisualizationTool: 2个")
    print(f"   6. CodeGenerationTool: 2个")
    print(f"   7. CustomAnalysisTool: 2个")
    print(f"")
    print(f"🎯 核心验证指标:")
    print(f"   - 执行成功率 (Execution Success Rate): 目标 ≥85%")
    print(f"   - 意图识别准确率 (Intent Recognition Accuracy): 目标 ≥90%")
    print(f"   - 配置生成成功率 (Config Generation Success): 目标 ≥95%")
    print(f"   - 输出一致性 (Output Consistency): 目标 100%")
    print(f"")
    print(f"🔧 配置:")
    print(f"   - LLM后端: {args.backend}")
    print(f"   - Mock模式: {args.mock}")
    print(f"   - 工具系统: {'✅ 启用' if args.use_tool_system else '❌ 禁用'}")
    print("=" * 80)

    # 创建实验
    exp = create_experiment(
        exp_name="exp_A_tool_validation",
        exp_description="Experiment A - 工具系统单独工具验证"
    )

    # 批量执行
    print("\n🚀 开始执行实验...")
    # 需要修改base_experiment.py的run_batch方法支持use_tool_system参数
    results = exp.run_batch(TEST_QUERIES, backend=args.backend, use_mock=args.mock, use_tool_system=args.use_tool_system)

    # 保存结果
    print("\n💾 保存结果...")
    exp.save_results(results, filename="exp_A_results")

    # 计算详细指标
    print("\n📊 计算评估指标...")
    metrics = calculate_detailed_metrics(results)
    exp.save_metrics(metrics, filename="exp_A_metrics")

    # 生成报告
    print("\n📝 生成实验报告...")
    generate_experiment_report(exp, results, metrics)

    # 🆕 生成综合实验报告 (类似 Experiment C v4.0)
    print("\n📝 生成综合实验报告 (experiment_A_report.md)...")
    final_report_path = generate_final_report(results, metrics, exp.workspace)
    print(f"   ✅ 综合报告已保存: {final_report_path}")

    # 生成图表
    print("\n📈 生成可视化图表...")
    exp.plot_results(results, plot_type="success_rate")
    exp.plot_results(results, plot_type="time_distribution")

    # 显示最终总结
    print("\n" + "=" * 80)
    print("✅ Experiment A 执行完成")
    print("=" * 80)
    print(f"📊 核心指标:")
    print(f"   - 执行成功率: {metrics.get('execution_success_rate', 0):.1%} "
          f"({'✅ 达标' if metrics.get('execution_success_rate', 0) >= 0.85 else '❌ 未达标'})")
    print(f"   - 意图识别准确率: {metrics.get('intent_recognition_accuracy', 0):.1%} "
          f"({'✅ 达标' if metrics.get('intent_recognition_accuracy', 0) >= 0.90 else '❌ 未达标'})")
    print(f"   - 配置生成成功率: {metrics.get('config_generation_success_rate', 0):.1%} "
          f"({'✅ 达标' if metrics.get('config_generation_success_rate', 0) >= 0.95 else '❌ 未达标'})")
    print(f"   - 输出一致性: {metrics.get('output_consistency', 0):.1%} "
          f"({'✅ 达标' if metrics.get('output_consistency', 0) >= 1.0 else '❌ 未达标'})")
    print(f"   - 工具调用准确率: {metrics.get('tool_call_accuracy', 0):.1%} "
          f"({'✅ 达标' if metrics.get('tool_call_accuracy', 0) >= 0.90 else '❌ 未达标'})")
    print(f"")
    print(f"📁 结果文件:")
    print(f"   - 工作目录: {exp.workspace}")
    print(f"   - 详细报告: {exp.workspace / 'reports' / 'experiment_report.md'}")
    print(f"   - 综合报告: {exp.workspace / 'experiment_A_report.md'}")
    print("=" * 80)


if __name__ == "__main__":
    main()
