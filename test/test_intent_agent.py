"""
Author: Claude
Date: 2025-11-21 15:00:00
LastEditTime: 2025-11-21 15:00:00
LastEditors: Claude
Description: Quick test for IntentAgent improvements
FilePath: \HydroAgent\scripts\test_intent_quick.py
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
        print(f"  Intent:     {intent_result.get('intent', 'N/A').upper()}")
        print(f"  Model:      {intent_result.get('model_name', 'N/A')}")
        print(f"  Basin:      {intent_result.get('basin_id', 'N/A')}")
        print(f"  Algorithm:  {intent_result.get('algorithm', 'N/A')}")
        print(f"  Confidence: {intent_result.get('confidence', 0.0):.2f}")

        # Extra parameters
        extra_params = intent_result.get('extra_params', {})
        if extra_params:
            print(f"  Extra Params: {extra_params}")

        # Missing info
        missing = intent_result.get('missing_info', [])
        if missing:
            print(f"  Missing:    {', '.join(missing)}")
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

    # Test cases
    test_cases = [
        ("率定GR4J模型，流域01013500, 使用SCE-UA算法，算法迭代只需要500轮就行",
         "完整中文查询 - 包含迭代次数"),

        ("评估XAJ模型在流域11532500的表现",
         "中文评估查询"),

        ("Calibrate GR5J for basin camels_01013500",
         "英文率定查询"),

        ("率定一个水文模型",
         "不完整查询 - 缺失信息"),

        ("使用XAJ_MZ模型，流域camels_01013500，训练期2000-2010，测试期2011-2015，使用DE算法，迭代1000次",
         "复杂中文查询 - 多参数"),
    ]

    for query, desc in test_cases:
        test_query(agent, query, desc)

    print("\n" + "="*70)
    print("✅ 测试完成!")
    print("="*70)


if __name__ == "__main__":
    main()
