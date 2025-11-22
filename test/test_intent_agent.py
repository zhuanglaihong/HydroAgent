"""
Author: Claude
Date: 2025-01-22 14:30:00
LastEditTime: 2025-01-22 14:30:00
LastEditors: Claude
Description: Test for IntentAgent Phase 1 enhancements (task decision & info completion)
FilePath: \HydroAgent\test\test_intent_agent.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set console encoding (Windows compatible)
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from hydroagent.agents.intent_agent import IntentAgent
from hydroagent.core.llm_interface import create_llm_interface

def test_query(agent, query: str, description: str):
    """Test a single query."""
    print("\n" + "="*70)
    print(f"【{description}】")
    print("="*70)
    print(f"Query: {query}")
    print()

    result = agent.process({"query": query})

    if result.get("success"):
        intent_result = result["intent_result"]
        print(f"✅ SUCCESS")

        # 🆕 Task Type (Phase 1 enhancement)
        task_type = intent_result.get('task_type', 'N/A')
        print(f"  🎯 Task Type:  {task_type}")

        print(f"  Intent:        {intent_result.get('intent', 'N/A').upper()}")
        print(f"  Model:         {intent_result.get('model_name', 'N/A')}")
        print(f"  Basin:         {intent_result.get('basin_id', 'N/A')}")
        print(f"  Algorithm:     {intent_result.get('algorithm', 'N/A')}")
        print(f"  Confidence:    {intent_result.get('confidence', 0.0):.2f}")

        # Extra parameters
        extra_params = intent_result.get('extra_params', {})
        if extra_params:
            print(f"  Extra Params:  {extra_params}")

        # 🆕 Strategy (for iterative_optimization)
        strategy = intent_result.get('strategy', {})
        if strategy:
            print(f"  🔄 Strategy:   {strategy}")

        # 🆕 Extended analysis needs (for extended_analysis)
        needs = intent_result.get('needs', [])
        if needs:
            print(f"  🔬 Needs:      {needs}")

        # 🆕 Number of repetitions (for repeated_experiment)
        n_repeats = intent_result.get('n_repeats')
        if n_repeats:
            print(f"  🔁 Repeats:    {n_repeats}")

        # Data source (if inferred)
        data_source = intent_result.get('data_source')
        if data_source:
            print(f"  📊 Data Source: {data_source}")

        # Missing info
        missing = intent_result.get('missing_info', [])
        if missing:
            print(f"  ⚠️  Missing:    {', '.join(missing)}")
    else:
        print(f"❌ FAILED: {result.get('error', 'Unknown error')}")
        print()
        print("⚠️ 这是一个真正的测试失败！")
        print("   可能原因:")
        print("   1. API key配置错误")
        print("   2. API服务连接失败")
        print("   3. LLM返回格式错误")
        print()

        # If there's partial intent_result, show it for debugging
        if "intent_result" in result:
            intent_result = result["intent_result"]
            if "error" in intent_result:
                print(f"   详细错误: {intent_result['error']}")
                if "raw_response" in intent_result:
                    print(f"   原始响应: {intent_result['raw_response'][:200]}...")
        print()
        print("   ❌ 测试未通过 - 需要修复上述问题")


def main():
    """Main test function."""
    import argparse

    parser = argparse.ArgumentParser(description='IntentAgent Quick Test')
    parser.add_argument('--backend', type=str, default='ollama',
                       choices=['ollama', 'api'],
                       help='LLM backend (default: ollama)')
    parser.add_argument('--model', type=str, default=None,
                       help='Model name')
    args = parser.parse_args()

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║           IntentAgent Quick Test - 快速测试               ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    # Load config
    try:
        from configs import definitions_private as config
    except ImportError:
        from configs import definitions as config

    # Create LLM interface
    print(f"\n正在初始化LLM接口 (backend: {args.backend})...")

    if args.backend == 'ollama':
        model = args.model or 'qwen3:8b'
        llm = create_llm_interface('ollama', model)
        print(f"✅ LLM接口初始化完成 (Ollama: {model})")
    else:
        api_key = getattr(config, 'OPENAI_API_KEY', None)
        base_url = getattr(config, 'OPENAI_BASE_URL', None)

        if not api_key:
            print("❌ API key未配置，请设置configs/definitions_private.py")
            return

        model = args.model or 'qwen-turbo'
        llm = create_llm_interface('openai', model,
                                  api_key=api_key,
                                  base_url=base_url)
        print(f"✅ LLM接口初始化完成 (API: {model})")

    # Create IntentAgent
    agent = IntentAgent(llm_interface=llm)
    print("✅ IntentAgent初始化完成")

    # Test cases (覆盖实验1-5的场景)
    test_cases = [
        # 实验1：标准流域验证
        ("率定流域 01013500，使用标准 XAJ 模型",
         "实验1 - 标准流域验证 (standard_calibration)"),

        # 实验2A：全信息
        ("使用 SCE-UA 算法，设置 rep=5000, ngs=1000，率定 CAMELS_US 的 01013500 流域，时间 1990-2000",
         "实验2A - 全信息 (standard_calibration)"),

        # 实验2B：缺省信息
        ("帮我率定流域 01013500",
         "实验2B - 缺省信息 (info_completion)"),

        # 实验2C：自定义数据
        ("用我 D 盘 my_data 文件夹里的数据跑一下模型",
         "实验2C - 自定义数据 (custom_data)"),

        # 实验3：参数自适应优化
        ("率定流域 01013500，如果参数收敛到边界，自动调整范围重新率定",
         "实验3 - 参数自适应优化 (iterative_optimization)"),

        # 实验4：代码生成与工具扩展
        ("率定完成后，请帮我计算流域的径流系数，并画一张流路历时曲线 FDC",
         "实验4 - 扩展分析 (extended_analysis)"),

        # 实验5：稳定性验证
        ("重复率定流域 01013500 十次，使用不同随机种子",
         "实验5 - 稳定性验证 (repeated_experiment)"),

        # 批量处理
        ("率定GR4J模型，流域01013500和01022500，分别用SCE-UA和GA算法",
         "批量处理 - 多流域多算法 (batch_processing)"),

        # 英文查询
        ("Calibrate GR5J for basin camels_01013500",
         "英文查询 (standard_calibration)"),
    ]

    for query, desc in test_cases:
        test_query(agent, query, desc)

    print("\n" + "="*70)
    print("✅ 测试完成!")
    print("="*70)


if __name__ == "__main__":
    main()
