"""
Author: Claude
Date: 2025-12-05 21:00:00
LastEditTime: 2025-12-05 21:00:00
LastEditors: Claude
Description: Example of using token tracking in experiments
             展示如何在实验中使用token统计功能
FilePath: /HydroAgent/examples/example_token_tracking.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from hydroagent.core.llm_interface import create_llm_interface
from hydroagent.utils.token_stats import (
    export_token_stats,
    format_token_stats_report,
)


def example_token_tracking():
    """
    Example: Track token usage during API calls.
    示例：在API调用期间跟踪token使用情况。
    """
    print("\n" + "=" * 70)
    print("Token Tracking Example")
    print("=" * 70 + "\n")

    # 1. Create LLM interface
    print("1. Creating LLM interface...")
    llm = create_llm_interface(
        backend="openai",  # or "ollama"
        model_name="qwen-turbo",
    )
    print(f"   Model: {llm.model_name}")
    print(f"   Backend: {llm.__class__.__name__}\n")

    # 2. Make some API calls
    print("2. Making API calls...")
    try:
        # First call
        response1 = llm.generate(
            system_prompt="You are a helpful assistant.",
            user_prompt="What is machine learning in one sentence?",
            temperature=0.7
        )
        print(f"   Response 1: {response1[:100]}...")

        # Second call
        response2 = llm.generate(
            system_prompt="You are a helpful assistant.",
            user_prompt="What is deep learning in one sentence?",
            temperature=0.7
        )
        print(f"   Response 2: {response2[:100]}...\n")

    except Exception as e:
        print(f"   ❌ API call failed: {str(e)}\n")
        return

    # 3. Get token usage statistics
    print("3. Token usage statistics:")
    token_stats = llm.get_token_usage()
    print(f"   Total calls: {token_stats['total_calls']}")
    print(f"   Total tokens: {token_stats['total_tokens']}")
    print(f"   - Prompt tokens: {token_stats['total_prompt_tokens']}")
    print(f"   - Completion tokens: {token_stats['total_completion_tokens']}")
    print(f"   Average per call: {token_stats['average_tokens_per_call']:.1f}\n")

    # 4. Export to file
    print("4. Exporting token statistics...")
    output_dir = project_root / "results" / "token_tracking_example"
    export_file = export_token_stats(
        llm_interface=llm,
        output_dir=output_dir,
        experiment_name="example_experiment"
    )
    print(f"   ✅ Exported to: {export_file}\n")

    # 5. Format as report
    print("5. Formatted report:")
    report = format_token_stats_report(token_stats)
    print(report)

    # 6. Reset statistics
    print("6. Resetting token statistics...")
    llm.reset_token_usage()
    new_stats = llm.get_token_usage()
    print(f"   After reset: {new_stats['total_calls']} calls, {new_stats['total_tokens']} tokens\n")

    print("=" * 70)
    print("✅ Example completed!")
    print("=" * 70)


if __name__ == "__main__":
    example_token_tracking()
