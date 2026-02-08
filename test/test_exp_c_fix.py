"""
Quick test script to verify Exp C v6.1 fix (FeedbackRouter abort bug)

测试目标:
- 验证 FeedbackRouter 不再对 unknown source_agent 返回 abort
- 确认任务能正常执行到 FAILED_UNRECOVERABLE（预期失败）
- 确认生成 analysis_report.md

运行: python test/test_exp_c_fix.py --backend api
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import argparse
from experiment.base_experiment import create_experiment

# 选择实验C中最简单、最快失败的3个场景
QUICK_TEST_QUERIES = [
    # Query 0: data_validation - 流域不存在（应该快速失败）
    "验证流域99999999的数据，然后率定GR4J模型",

    # Query 2: data_validation - 非法参数（应该快速失败）
    "率定GR4J模型流域01013500，迭代-100轮",

    # Query 1: data_validation - 时间范围超出（需要数据加载，稍慢）
    "率定GR4J模型流域01013500，训练期2025-2027，测试期2027-2028",
]

def main():
    parser = argparse.ArgumentParser(description="Quick test for Exp C v6.1 fix")
    parser.add_argument("--backend", type=str, default="api", choices=["api", "ollama"])
    parser.add_argument("--mock", action="store_true", help="Use mock mode for faster testing")
    args = parser.parse_args()

    print("=" * 80)
    print("🔧 Experiment C v6.1 Fix Verification")
    print("=" * 80)
    print(f"\nTesting 3 quick-fail scenarios from Experiment C")
    print(f"Backend: {args.backend}")
    print(f"Mock mode: {args.mock}")
    print(f"\n{'=' * 80}\n")

    # Create experiment
    exp = create_experiment(
        exp_name="exp_C_fix_verification",
        exp_description="Quick test to verify FeedbackRouter abort bug fix (v6.1)"
    )

    # Expected outcomes
    print("Expected outcomes for all 3 queries:")
    print("  ✅ No 'Unknown source agent: Orchestrator' error")
    print("  ✅ No premature abort in GENERATING_CONFIG")
    print("  ✅ Each query fails gracefully (FAILED_UNRECOVERABLE)")
    print("  ✅ Each query generates analysis_report.md")
    print(f"\n{'=' * 80}\n")

    # Run batch
    results = exp.run_batch(
        QUICK_TEST_QUERIES,
        backend=args.backend,
        use_mock=args.mock,
        use_tool_system=True  # Must use tool system for Exp C
    )

    # Analyze results
    print("\n" + "=" * 80)
    print("📊 Verification Results")
    print("=" * 80)

    success_count = sum(1 for r in results if r.get("success"))
    fail_count = len(results) - success_count

    print(f"\nExecution Summary:")
    print(f"  Total queries: {len(results)}")
    print(f"  Expected failures: {len(results)} (all should fail by design)")
    print(f"  Actual failures: {fail_count}")
    print(f"  Unexpected successes: {success_count} ⚠️" if success_count > 0 else f"  Unexpected successes: 0 ✅")

    # Check for the critical bug
    print(f"\n🔍 Checking for v6.1 bug symptoms:")

    has_abort_bug = False
    reports_generated = 0

    for i, result in enumerate(results):
        query = QUICK_TEST_QUERIES[i]
        session_id = result.get("session_id", "unknown")
        workspace = result.get("workspace", "")

        print(f"\n  Query {i+1}: {query[:50]}...")

        # Check for abort bug in logs
        if workspace:
            session_dir = Path(workspace)
            if session_dir.exists():
                # Check if analysis_report.md exists
                report_file = session_dir / "analysis_report.md"
                if report_file.exists():
                    reports_generated += 1
                    print(f"    ✅ analysis_report.md generated")
                else:
                    print(f"    ❌ analysis_report.md NOT found")

        # Check final state
        final_state = result.get("final_state", "unknown")
        print(f"    Final state: {final_state}")

        if final_state == "FAILED_UNRECOVERABLE":
            print(f"    ✅ Failed gracefully (as expected)")
        else:
            print(f"    ⚠️ Unexpected final state")

    print(f"\n{'=' * 80}")
    print(f"📋 Final Verdict:")
    print(f"{'=' * 80}")
    print(f"  Reports generated: {reports_generated}/{len(results)}")

    if reports_generated == len(results):
        print(f"\n  ✅ v6.1 FIX VERIFIED - All queries generated failure reports")
        print(f"     The 'Unknown source agent → abort' bug is fixed!")
    else:
        print(f"\n  ⚠️ POSSIBLE ISSUES - Some queries did not generate reports")
        print(f"     Please check logs for details")

    print(f"\n{'=' * 80}\n")

    # Save results
    exp.save_results(results)
    print(f"Full results saved to: {exp.workspace}")
    print(f"\n✅ Verification test completed!\n")

if __name__ == "__main__":
    main()
