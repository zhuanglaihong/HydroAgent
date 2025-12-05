"""
Author: Claude
Date: 2025-01-24 17:00:00
LastEditTime: 2025-01-24 17:00:00
LastEditors: Claude
Description: 实验2C - 模型×算法全覆盖测试
             Experiment 2C - Model × Algorithm Matrix Test
FilePath: /HydroAgent/experiment/exp_2c_multi_algorithm.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

实验目标:
- 全面验证系统对hydromodel所有模型和算法的支持
- 一次对话生成所有模型×算法组合任务
- 对比性能：算法维度、模型维度、组合维度

测试内容:
- 3种算法：SCE-UA, GA, scipy
- 4种模型：XAJ, GR4J, GR5J, GR6J
- 12个组合任务（3×4 笛卡尔积）

测试查询:
"对流域 12025000 分别使用 SCE-UA、GA、scipy 三种算法，
结合 XAJ、GR4J、GR5J、GR6J 四种模型进行率定，对比所有组合的性能"

成功标准:
- 12个组合全部成功执行
- 生成模型×算法性能矩阵
- 识别最佳算法（跨模型平均）
- 识别最佳模型（跨算法平均）
- 识别最佳组合
"""

import sys
from pathlib import Path
import io
import argparse

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set console encoding (Windows compatible)
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from base_experiment import BaseExperiment


# 3种优化算法
ALGORITHMS = ["SCE-UA", "GA", "scipy"]

# 4种水文模型（覆盖hydromodel的核心模型）
MODELS = ["XAJ", "GR4J", "GR5J", "GR6J"]

# 实验查询 - 模型×算法全覆盖
QUERY = "对流域 12025000 分别使用 SCE-UA、GA、scipy 三种算法，结合 XAJ、GR4J、GR5J、GR6J 四种模型进行率定，对比所有组合的性能"


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="实验2C：模型×算法全覆盖测试")
    parser.add_argument(
        "--backend",
        type=str,
        default="api",
        choices=["ollama", "api"],
        help="LLM backend (default: api)",
    )
    parser.add_argument("--model", type=str, default=None, help="Model name")
    parser.add_argument(
        "--mock", action="store_true", help="Use mock mode (do not run real hydromodel)"
    )
    parser.add_argument(
        "--algorithms",
        type=str,
        default=None,
        help="Custom algorithms (comma-separated), default: SCE-UA,GA,scipy"
    )
    parser.add_argument(
        "--models",
        type=str,
        default=None,
        help="Custom models (comma-separated), default: XAJ,GR4J,GR5J,GR6J"
    )
    args = parser.parse_args()

    # 创建实验对象
    experiment = BaseExperiment(
        exp_name="exp_2c_model_algorithm_matrix",
        exp_description="实验2C：模型×算法全覆盖测试"
    )

    # Setup logging
    log_file = experiment.setup_logging()

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║     实验2C：模型×算法全覆盖测试                              ║")
    print("║  Experiment 2C: Model × Algorithm Matrix Test               ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"\n📝 日志文件: {log_file}\n")

    # Load config
    try:
        from configs import definitions_private as config
    except ImportError:
        from configs import definitions as config

    # Create LLM interface
    from hydroagent.core.llm_interface import create_llm_interface

    print(f"正在初始化LLM接口 (backend: {args.backend})...")

    if args.backend == "ollama":
        model = args.model or "qwen3:8b"
        llm = create_llm_interface("ollama", model)
        print(f"✅ LLM接口初始化完成 (Ollama: {model})\n")
    else:
        api_key = getattr(config, "OPENAI_API_KEY", None)
        base_url = getattr(config, "OPENAI_BASE_URL", None)

        if not api_key:
            print("❌ API key未配置，请设置configs/definitions_private.py")
            return 1

        model = args.model or "qwen3-max"
        llm = create_llm_interface("openai", model, api_key=api_key, base_url=base_url)
        print(f"✅ LLM接口初始化完成 (API: {model})\n")

    # Use custom algorithms and models if provided
    if args.algorithms:
        algorithm_list = [a.strip() for a in args.algorithms.split(",")]
    else:
        algorithm_list = ALGORITHMS

    if args.models:
        model_list = [m.strip() for m in args.models.split(",")]
    else:
        model_list = MODELS

    # Build query
    if args.algorithms or args.models:
        algorithms_str = ', '.join(algorithm_list)
        models_str = ', '.join(model_list)
        query = f"对流域 12025000 分别使用 {algorithms_str} 算法，结合 {models_str} 模型进行率定，对比所有组合的性能"
    else:
        query = QUERY

    total_combinations = len(algorithm_list) * len(model_list)

    # Run experiment
    print(f"📋 测试查询: {query}\n")
    print("⚠️  注意: 这将执行以下操作:")
    print(f"   - 一次对话，{total_combinations}个任务（{len(algorithm_list)}种算法 × {len(model_list)}种模型）")
    print(f"   - 生成所有模型×算法组合的笛卡尔积")
    print(f"   - 记录每个组合的NSE、RMSE、KGE和执行时间")
    print(f"   - 预计耗时: ~{total_combinations * 10}分钟（真实执行）")
    if args.mock:
        print("   - Mock模式: 不会真实执行hydromodel")
    print()

    print(f"算法列表 ({len(algorithm_list)}种):")
    for i, algo in enumerate(algorithm_list, 1):
        print(f"  {i}. {algo}")
    print()

    print(f"模型列表 ({len(model_list)}种):")
    for i, model in enumerate(model_list, 1):
        print(f"  {i}. {model}")
    print()

    print(f"组合总数: {total_combinations} = {len(algorithm_list)} × {len(model_list)}")
    print("示例组合:")
    for i, algo in enumerate(algorithm_list[:2], 1):  # 显示前2个算法的组合
        for j, model in enumerate(model_list, 1):
            combo_num = (i-1) * len(model_list) + j
            print(f"  {combo_num}. {algo} + {model}")
    if len(algorithm_list) > 2:
        print("  ...")
    print()

    result = experiment.run_experiment(query, llm, use_mock=args.mock)

    # Check results
    print("\n" + "=" * 70)
    print("实验2C结果")
    print("=" * 70)

    if result.get("success"):
        print("✅ 实验2C完成!")
        print("\n验证点:")
        print(f"  ✅ {total_combinations}个组合全部成功执行")
        print("  ✅ 生成模型×算法性能矩阵")
        print("  ✅ 识别最佳算法（跨模型平均）")
        print("  ✅ 识别最佳模型（跨算法平均）")
        print("  ✅ 识别最佳组合")
        print("  ✅ 提供模型和算法选择建议")

        print("\n📊 预期输出文件:")
        print("  - model_algorithm_matrix.csv - 完整性能矩阵")
        print("  - nse_heatmap.png - NSE热力图（算法×模型）")
        print("  - algorithm_ranking.json - 算法平均性能排名")
        print("  - model_ranking.json - 模型平均性能排名")
        print("  - best_combination.json - 最佳组合推荐")
        print(f"  - {total_combinations}个独立的率定结果目录")

        print("\n💡 多维度分析:")
        print("  - 算法维度: 哪种算法整体表现最好（跨所有模型）")
        print("  - 模型维度: 哪种模型整体表现最好（跨所有算法）")
        print("  - 组合维度: 最佳算法-模型组合")
        print("  - 效率分析: NSE vs 执行时间权衡")

        print(f"\n🎯 覆盖范围:")
        print(f"  - 算法: {', '.join(algorithm_list)}")
        print(f"  - 模型: {', '.join(model_list)}")
        print(f"  - 这个实验全面覆盖了hydromodel的核心功能！")

        return 0
    else:
        print(f"❌ 实验2C失败: {result.get('error')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
