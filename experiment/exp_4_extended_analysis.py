"""
Author: Claude
Date: 2025-01-22 21:30:00
LastEditTime: 2025-01-23 00:00:00
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
import io
import argparse

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from base_experiment import BaseExperiment

QUERY = "率定完成后，请帮我计算流域的径流系数，并画一张流路历时曲线 FDC"


def main():
    parser = argparse.ArgumentParser(description="实验4：扩展分析")
    parser.add_argument("--backend", type=str, default="api", choices=["ollama", "api"])
    parser.add_argument("--model", type=str, default=None, help="通用模型名称")
    parser.add_argument("--code-model", type=str, default=None, help="代码专用模型名称")
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()

    experiment = BaseExperiment(
        exp_name="exp_4_extended_analysis",
        exp_description="实验4：扩展分析"
    )

    log_file = experiment.setup_logging()

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║             实验4：扩展分析                                  ║")
    print("║   （测试代码生成能力 - 径流系数 + FDC曲线）                  ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"\n📝 日志文件: {log_file}\n")

    try:
        from configs import definitions_private as config
    except ImportError:
        from configs import definitions as config

    from hydroagent.core.llm_interface import create_llm_interface

    # 创建通用LLM
    if args.backend == "ollama":
        model = args.model or "qwen3:8b"
        llm = create_llm_interface("ollama", model)
        print(f"✅ 通用LLM初始化完成: {model}")

        # 创建代码专用LLM
        code_model = args.code_model or "deepseek-coder:6.7b"
        code_llm = create_llm_interface("ollama", code_model)
        print(f"✅ 代码专用LLM初始化完成: {code_model}\n")

    else:
        api_key = getattr(config, "OPENAI_API_KEY", None)
        base_url = getattr(config, "OPENAI_BASE_URL", None)
        if not api_key:
            print("❌ API key未配置")
            return 1

        model = args.model or "qwen-turbo"
        llm = create_llm_interface("openai", model, api_key=api_key, base_url=base_url)
        print(f"✅ 通用LLM初始化完成: {model}")

        # 创建代码专用LLM
        code_model = args.code_model or "qwen-coder-turbo"
        code_llm = create_llm_interface("openai", code_model, api_key=api_key, base_url=base_url)
        print(f"✅ 代码专用LLM初始化完成: {code_model}\n")

    # 运行实验，传入code_llm
    result = experiment.run_experiment(QUERY, llm, use_mock=args.mock, code_llm=code_llm)

    if result.get("success"):
        print("\n🎉 实验4完成!")
        return 0
    else:
        print(f"\n❌ 实验4失败: {result.get('error')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
