"""
Author: Claude
Date: 2025-01-22 21:30:00
LastEditTime: 2025-11-30 00:00:00
LastEditors: Claude
Description: 通用实验运行器 - 运行所有8个实验
             Universal Experiment Runner - Run all 8 experiments
FilePath: /HydroAgent/experiment/run_experiments.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import sys
from pathlib import Path
import json
import time
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set console encoding (Windows compatible)
import io

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

import logging
import argparse


# 实验配置 - 对应8个独立的实验脚本
EXPERIMENTS = {
    "1a": {
        "name": "标准流程验证",
        "query": "率定流域 14301000，使用 XAJ 模型，SCE-UA 算法，rep=500",
        "description": "完整信息下的标准率定流程",
    },
    "1b": {
        "name": "缺省信息补全",
        "query": "帮我率定流域 14301000",
        "description": "自动补全模型、算法等缺省信息",
    },
    "1c": {
        "name": "错误处理验证",
        "query": "率定流域 99999999",  # 错误的流域ID
        "description": "测试系统错误处理和鲁棒性",
    },
    "2a": {
        "name": "重复率定验证",
        "query": "重复执行20次率定，流域 14301000，XAJ 模型",
        "description": "单流域稳定性验证（20次重复）",
        "default_repetitions": 20,
    },
    "2b": {
        "name": "多流域批量率定",
        "query": "批量率定10个流域，使用 XAJ  模型",
        "description": "多流域性能对比",
        "default_basins": ["14301000", "01013500", "01022500"],
    },
    "2c": {
        "name": "多算法对比",
        "query": "分别使用 SCE-UA、SCIPY、GA 率定流域 14301000",
        "description": "多算法性能对比",
        "default_algorithms": ["SCE_UA", "scipy", "GA"],
    },
    "3": {
        "name": "参数自适应优化",
        "query": "率定流域 14301000，如果参数收敛到边界，自动调整范围重新率定",
        "description": "两阶段迭代优化（参数范围自适应调整）",
    },
    "4": {
        "name": "扩展分析（代码生成）",
        "query": "率定完成后，请帮我计算流域的径流系数，并画一张流量历时曲线 FDC",
        "description": "代码生成与扩展分析（双LLM模式）",
    },
}


def setup_logging(exp_id):
    """Setup logging for experiment."""
    logs_dir = project_root / "logs"
    logs_dir.mkdir(exist_ok=True)

    log_file = logs_dir / f"exp_{exp_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )

    return log_file


def run_experiment(exp_id, llm, code_llm=None, use_mock=True, **kwargs):
    """
    运行指定实验（使用Orchestrator统一接口）

    Args:
        exp_id: 实验ID (1a, 1b, 1c, 2a, 2b, 2c, 3, 4)
        llm: LLM接口（通用模型）
        code_llm: 代码专用LLM接口（可选，仅实验4需要）
        use_mock: 是否使用Mock模式
        **kwargs: 实验特定参数（如repetitions, basins等）

    Returns:
        实验结果字典
    """
    from base_experiment import BaseExperiment

    if exp_id not in EXPERIMENTS:
        return {"success": False, "error": f"Unknown experiment: {exp_id}"}

    exp_config = EXPERIMENTS[exp_id]
    query = exp_config["query"]

    print("\n" + "=" * 70)
    print(f"【实验{exp_id.upper()}：{exp_config['name']}】")
    print("=" * 70)
    print(f"查询: {query}")
    print(f"描述: {exp_config['description']}")
    print(f"模式: {'Mock (模拟)' if use_mock else 'Real (真实hydromodel)'}")
    print()

    total_start = time.time()

    # ========================================================================
    # 使用 BaseExperiment + Orchestrator 执行
    # ========================================================================
    exp_name = f"exp_{exp_id}"
    experiment = BaseExperiment(
        exp_name=exp_name,
        exp_description=exp_config["name"]
    )

    # 执行实验
    result = experiment.run_experiment(
        query=query,
        llm=llm,
        use_mock=use_mock,
        code_llm=code_llm
    )

    total_elapsed = time.time() - total_start

    # ========================================================================
    # 总结
    # ========================================================================
    print("\n" + "=" * 70)
    if result.get("success"):
        print(f"✅ 实验{exp_id.upper()}通过!")
    else:
        print(f"❌ 实验{exp_id.upper()}失败")
        if "error" in result:
            print(f"   错误: {result['error']}")

    print("=" * 70)
    print(f"总耗时: {total_elapsed:.1f}s")

    if "workspace" in result:
        print(f"工作目录: {result['workspace']}")

    print("=" * 70)

    return result


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="运行HydroAgent实验",
        epilog=f"可用实验: {', '.join(EXPERIMENTS.keys())}, all"
    )
    parser.add_argument(
        "experiment",
        type=str,
        nargs="?",
        default="all",
        help="实验ID: 1a, 1b, 1c, 2a, 2b, 2c, 3, 4, all (default: all)",
    )
    parser.add_argument(
        "--backend",
        type=str,
        default="api",
        choices=["ollama", "api"],
        help="LLM backend (default: api)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="通用LLM模型名称（default: API=qwen-turbo, Ollama=qwen3:8b）"
    )
    parser.add_argument(
        "--code-model",
        type=str,
        default=None,
        help="代码专用LLM模型（实验4使用，default: API=qwen-coder-turbo, Ollama=deepseek-coder:6.7b）"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Mock模式（不运行真实hydromodel）"
    )
    args = parser.parse_args()

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║           HydroAgent 实验运行器 v2.0                        ║")
    print("║           Experiment Runner (8 Experiments)                  ║")
    print("╚══════════════════════════════════════════════════════════════╝\n")

    # Load config
    try:
        from configs import definitions_private as config
    except ImportError:
        from configs import definitions as config

    # Create LLM interface
    from hydroagent.core.llm_interface import create_llm_interface

    # ========================================================================
    # 初始化通用LLM
    # ========================================================================
    print(f"正在初始化通用LLM接口 (backend: {args.backend})...")

    if args.backend == "ollama":
        model = args.model or "qwen3:8b"
        llm = create_llm_interface("ollama", model)
        print(f"✅ 通用LLM初始化完成 (Ollama: {model})")
    else:
        api_key = getattr(config, "OPENAI_API_KEY", None)
        base_url = getattr(config, "OPENAI_BASE_URL", None)

        if not api_key:
            print("❌ API key未配置，请设置configs/definitions_private.py")
            return 1

        model = args.model or "qwen-turbo"
        llm = create_llm_interface("openai", model, api_key=api_key, base_url=base_url)
        print(f"✅ 通用LLM初始化完成 (API: {model})")

    # ========================================================================
    # 初始化代码专用LLM（实验4需要）
    # ========================================================================
    code_llm = None
    if args.code_model or args.experiment in ["4", "all"]:
        print(f"正在初始化代码专用LLM接口...")

        if args.backend == "ollama":
            code_model = args.code_model or "deepseek-coder:6.7b"
            code_llm = create_llm_interface("ollama", code_model)
            print(f"✅ 代码LLM初始化完成 (Ollama: {code_model})")
        else:
            code_model = args.code_model or "qwen-coder-turbo"
            code_llm = create_llm_interface(
                "openai", code_model, api_key=api_key, base_url=base_url
            )
            print(f"✅ 代码LLM初始化完成 (API: {code_model})")

    print()

    # ========================================================================
    # 确定要运行的实验
    # ========================================================================
    if args.experiment == "all":
        exp_ids = list(EXPERIMENTS.keys())
        print(f"📋 运行所有{len(exp_ids)}个实验\n")
    else:
        if args.experiment not in EXPERIMENTS:
            print(f"❌ 未知实验: {args.experiment}")
            print(f"可用实验: {', '.join(EXPERIMENTS.keys())}, all")
            return 1
        exp_ids = [args.experiment]
        print(f"📋 运行单个实验: {args.experiment}\n")

    # ========================================================================
    # 运行实验
    # ========================================================================
    results = {}
    for i, exp_id in enumerate(exp_ids, 1):
        print(f"\n{'='*70}")
        print(f"进度: [{i}/{len(exp_ids)}]")
        print(f"{'='*70}")

        log_file = setup_logging(exp_id)
        print(f"📝 日志: {log_file}\n")

        result = run_experiment(
            exp_id,
            llm,
            code_llm=code_llm,
            use_mock=args.mock
        )
        results[exp_id] = result

        # 短暂停顿（避免API限流）
        if i < len(exp_ids):
            time.sleep(2)

    # ========================================================================
    # 总结报告
    # ========================================================================
    print("\n" + "=" * 70)
    print("📊 实验总结报告")
    print("=" * 70)

    passed = 0
    failed = 0

    for exp_id, result in results.items():
        success = result.get("success", False)
        status = "✅ 通过" if success else "❌ 失败"
        exp_name = EXPERIMENTS[exp_id]["name"]

        print(f"实验{exp_id.upper():<4} - {exp_name:<20} {status}")

        if success:
            passed += 1
        else:
            failed += 1

    print("=" * 70)
    print(f"通过: {passed}/{len(results)} | 失败: {failed}/{len(results)}")

    all_passed = all(r.get("success") for r in results.values())

    if all_passed:
        print("\n🎉 所有实验通过!")
        return 0
    else:
        print(f"\n⚠️  有 {failed} 个实验失败，请查看日志")
        return 1


if __name__ == "__main__":
    sys.exit(main())
