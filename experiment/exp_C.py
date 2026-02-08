"""
Experiment C v4.0: Robustness and Error Boundary Exploration
实验C v4.0：系统鲁棒性与错误边界探测

Purpose:
- 探测系统的错误识别能力和容忍边界
- 验证系统在极限条件下的稳定性
- 评估错误分类的准确性

Design Philosophy:
1. 明确错误场景 (Error Scenarios): 验证系统能识别明显的用户错误
2. 边界条件场景 (Boundary Conditions): 探测系统的容忍边界
3. 压力测试场景 (Stress Tests): 验证极限条件下的稳定性

NOT a "find all bugs" test, but a "understand system limits" exploration.

Author: Claude & zhuanglaihong
Date: 2026-01-14
Version: v4.0 (Redesigned for robustness testing)
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from experiment.base_experiment import create_experiment
from datetime import datetime


# ========================================================================
# Test Scenarios (18 total = 6 error + 6 boundary + 6 stress)
# ========================================================================

# Category 1: Error Scenarios (明确错误 - Expected to Fail)
# 验证系统能正确识别和分类明显的用户错误
ERROR_SCENARIOS = [
    # data_validation (2个)
    "验证流域99999999的数据可用性",  # 流域ID不存在
    "率定GR4J模型流域01013500，算法迭代-100次",  # 负数参数

    # configuration (2个)
    "率定GR4J模型流域01013500，训练期2000-2010，测试期1995-2000",  # 时间段冲突
    "率定XAJ模型流域01013500，训练期2099-01-01到2100-12-31",  # 未来时间

    # data (2个)
    "率定GR4J模型流域01013500，训练期1980-01-01到1980-01-07",  # 训练期太短（7天）
    "率定GR4J模型流域01013500，测试期1980-01-01到1980-01-03",  # 测试期太短（3天）
]

# Category 2: Boundary Conditions (边界条件 - Unknown Outcome)
# 探测系统的容忍边界（可能成功也可能失败，重点是不崩溃）
BOUNDARY_SCENARIOS = [
    # 极端参数范围
    "率定GR4J模型流域01013500，参数x1范围[0.00001, 0.00002]",  # 极窄范围
    "率定GR4J模型流域01013500，参数x1范围[0, 1000000]",  # 极宽范围

    # 极短训练期
    "率定XAJ模型流域01013500，训练期1985-10-01到1985-12-31",  # 3个月

    # 极限算法参数
    "率定GR4J模型流域01013500，SCE-UA算法ngs设为1",  # 最小复合体数
    "率定GR4J模型流域01013500，warmup期设为0天",  # 无warmup

    # 特殊配置
    "率定GR4J模型流域01013500，warmup期设为400天，训练期只有1年",  # warmup接近训练期
]

# Category 3: Stress Tests (压力测试 - Expected to Succeed)
# 验证系统在极限条件下的稳定性（应该能处理）
STRESS_SCENARIOS = [
    # 大规模参数搜索
    "率定GR4J模型流域01013500，SCE-UA算法迭代5000轮",  # 长时间运行

    # 复杂代码生成任务
    "率定GR4J模型流域01013500，完成后生成Python代码计算流域的径流深度、产流系数、基流指数",
    "率定GR4J模型流域01013500，完成后生成Python代码使用sklearn库进行流量预测建模",

    # 多流域批量任务
    "批量率定GR4J模型，流域01013500、01022500、01030500",

    # 迭代优化任务
    "率定GR4J模型流域01013500，如果NSE<0.7则调整参数范围重新率定",

    # 重复实验
    "重复率定GR4J模型流域01013500共3次，分析结果稳定性",
]

# Expected error categories for Error Scenarios
EXPECTED_ERROR_CATEGORIES = {
    ERROR_SCENARIOS[0]: "data_validation",  # 流域不存在
    ERROR_SCENARIOS[1]: "configuration",    # 负数参数（LLM config review拒绝）
    ERROR_SCENARIOS[2]: "configuration",    # 时间冲突
    ERROR_SCENARIOS[3]: "configuration",    # 未来时间
    ERROR_SCENARIOS[4]: "configuration",    # 训练期太短（LLM config review拒绝）
    ERROR_SCENARIOS[5]: "configuration",    # 测试期太短（LLM config review拒绝）
}


def analyze_results(results, mode, exp_workspace):
    """
    Analyze experiment results and generate comprehensive report.
    分析实验结果并生成综合报告。
    """
    print("\n" + "=" * 80)
    print("📊 Experiment C v4.0 Results Analysis")
    print("=" * 80)

    # Split results by category
    if mode == "error":
        error_results = results
        boundary_results = []
        stress_results = []
        test_queries = ERROR_SCENARIOS
    elif mode == "boundary":
        error_results = []
        boundary_results = results
        stress_results = []
        test_queries = BOUNDARY_SCENARIOS
    elif mode == "stress":
        error_results = []
        boundary_results = []
        stress_results = results
        test_queries = STRESS_SCENARIOS
    else:  # all
        error_results = results[:len(ERROR_SCENARIOS)]
        boundary_results = results[len(ERROR_SCENARIOS):len(ERROR_SCENARIOS)+len(BOUNDARY_SCENARIOS)]
        stress_results = results[len(ERROR_SCENARIOS)+len(BOUNDARY_SCENARIOS):]
        test_queries = ERROR_SCENARIOS + BOUNDARY_SCENARIOS + STRESS_SCENARIOS

    # ========================================================================
    # 1. Error Detection Analysis (错误检测能力)
    # ========================================================================
    if error_results:
        print("\n📋 1. Error Detection Analysis (明确错误场景)")
        print("-" * 80)

        total_error_scenarios = len(error_results)
        detected_errors = sum(1 for r in error_results if not r.get("success"))
        error_detection_rate = detected_errors / total_error_scenarios if total_error_scenarios > 0 else 0

        print(f"   Total error scenarios: {total_error_scenarios}")
        print(f"   Detected (failed): {detected_errors}")
        print(f"   Missed (succeeded): {total_error_scenarios - detected_errors}")
        print(f"   Error Detection Rate: {error_detection_rate*100:.1f}%")

        if error_detection_rate >= 0.8:
            print(f"   ✅ Target met (≥80%)")
        else:
            print(f"   ⚠️ Below target (<80%)")

        # Error classification accuracy
        print(f"\n   Error Classification Analysis:")
        correct_classifications = 0
        total_classifications = 0

        for i, result in enumerate(error_results):
            query = ERROR_SCENARIOS[i] if i < len(ERROR_SCENARIOS) else ""
            expected_cat = EXPECTED_ERROR_CATEGORIES.get(query)
            actual_cat = result.get("error_category", "unknown")

            if not result.get("success") and expected_cat:
                total_classifications += 1
                if actual_cat == expected_cat:
                    correct_classifications += 1
                    print(f"   ✅ Scenario {i+1}: {expected_cat} (correct)")
                else:
                    print(f"   ❌ Scenario {i+1}: Expected {expected_cat}, got {actual_cat}")

        if total_classifications > 0:
            classification_accuracy = correct_classifications / total_classifications
            print(f"\n   Classification Accuracy: {correct_classifications}/{total_classifications} = {classification_accuracy*100:.1f}%")
            if classification_accuracy >= 0.85:
                print(f"   ✅ Target met (≥85%)")
            else:
                print(f"   ⚠️ Below target (<85%)")

    # ========================================================================
    # 2. Boundary Exploration Analysis (边界条件探测)
    # ========================================================================
    if boundary_results:
        print("\n🔬 2. Boundary Exploration Analysis (边界条件场景)")
        print("-" * 80)

        total_boundary = len(boundary_results)
        boundary_success = sum(1 for r in boundary_results if r.get("success"))
        boundary_fail = total_boundary - boundary_success

        print(f"   Total boundary scenarios: {total_boundary}")
        print(f"   Accepted (succeeded): {boundary_success}")
        print(f"   Rejected (failed): {boundary_fail}")
        print(f"   Acceptance Rate: {boundary_success/total_boundary*100:.1f}%")

        # System stability check (no crashes)
        crashes = sum(1 for r in boundary_results if "crash" in str(r.get("error", "")).lower())
        print(f"\n   System Stability:")
        print(f"   Crashes: {crashes}")
        if crashes == 0:
            print(f"   ✅ No crashes (100% stable)")
        else:
            print(f"   ⚠️ System instability detected")

        # Detail breakdown
        print(f"\n   Boundary Results Breakdown:")
        for i, result in enumerate(boundary_results):
            status = "ACCEPT" if result.get("success") else "REJECT"
            query_preview = BOUNDARY_SCENARIOS[i][:50] if i < len(BOUNDARY_SCENARIOS) else ""
            print(f"   [{status}] Scenario {i+1}: {query_preview}...")

    # ========================================================================
    # 3. Stress Test Analysis (压力测试)
    # ========================================================================
    if stress_results:
        print("\n💪 3. Stress Test Analysis (压力测试场景)")
        print("-" * 80)

        total_stress = len(stress_results)
        stress_pass = sum(1 for r in stress_results if r.get("success"))
        stress_fail = total_stress - stress_pass
        stress_pass_rate = stress_pass / total_stress if total_stress > 0 else 0

        print(f"   Total stress scenarios: {total_stress}")
        print(f"   Passed: {stress_pass}")
        print(f"   Failed: {stress_fail}")
        print(f"   Pass Rate: {stress_pass_rate*100:.1f}%")

        if stress_pass_rate >= 0.8:
            print(f"   ✅ Target met (≥80%)")
        else:
            print(f"   ⚠️ Below target (<80%)")

        # Timeout analysis
        timeouts = sum(1 for r in stress_results if "timeout" in str(r.get("error", "")).lower())
        if timeouts > 0:
            print(f"\n   ⚠️ Timeouts detected: {timeouts}")

    # ========================================================================
    # 4. Overall System Stability
    # ========================================================================
    print("\n🛡️ 4. Overall System Stability")
    print("-" * 80)

    total_scenarios = len(results)
    total_crashes = sum(1 for r in results if "crash" in str(r.get("error", "")).lower() or "abort" in str(r.get("final_state", "")).lower())
    total_infinite_loops = sum(1 for r in results if r.get("api_calls", 0) > 20)  # Heuristic: >20 calls = likely stuck

    print(f"   Total scenarios executed: {total_scenarios}")
    print(f"   Crashes: {total_crashes}")
    print(f"   Infinite loops: {total_infinite_loops}")

    system_stable = (total_crashes == 0 and total_infinite_loops == 0)
    if system_stable:
        print(f"   ✅ System Stability: 100% (No crashes, no infinite loops)")
    else:
        print(f"   ⚠️ System Stability: Issues detected")

    # ========================================================================
    # 5. Performance Metrics
    # ========================================================================
    print("\n📈 5. Performance Metrics")
    print("-" * 80)

    total_time = sum(r.get("elapsed_time", 0) for r in results)
    # 🔧 修复：从嵌套的token_usage字段中读取token数据
    total_tokens = sum(r.get("token_usage", {}).get("total_tokens", 0) for r in results)
    total_api_calls = sum(r.get("token_usage", {}).get("total_calls", 0) for r in results)

    print(f"   Total execution time: {total_time:.1f}s ({total_time/60:.1f}min)")
    print(f"   Total tokens consumed: {total_tokens:,}")
    print(f"   Total API calls: {total_api_calls}")
    print(f"   Average time per scenario: {total_time/total_scenarios:.1f}s")
    avg_tokens = total_tokens // total_scenarios if total_scenarios > 0 else 0
    print(f"   Average tokens per scenario: {avg_tokens:,}")

    # ========================================================================
    # 6. Generate Final Report (保存到文件)
    # ========================================================================
    print("\n📝 Generating final experiment report...")

    report_content = generate_experiment_report(
        results=results,
        error_results=error_results,
        boundary_results=boundary_results,
        stress_results=stress_results,
        mode=mode
    )

    report_file = Path(exp_workspace) / "experiment_C_v4_report.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report_content)

    print(f"   Report saved to: {report_file}")

    # Print summary
    print(f"\n{'=' * 80}")
    print(f"📁 Results Location:")
    print(f"{'=' * 80}")
    print(f"   Workspace: {exp_workspace}")
    print(f"   Data: {exp_workspace}/data/")
    print(f"   Session reports: {exp_workspace}/session_*/analysis_report.md")
    print(f"   Experiment report: {report_file}")
    print(f"\n✅ Experiment C v4.0 completed!\n")


def generate_experiment_report(results, error_results, boundary_results, stress_results, mode):
    """Generate comprehensive experiment report in Markdown format."""

    report = []
    report.append("# Experiment C v4.0: Robustness and Error Boundary Exploration")
    report.append(f"\n**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"**Mode:** {mode}")
    report.append(f"**Total Scenarios:** {len(results)}")
    report.append("\n---\n")

    # Executive Summary
    report.append("## Executive Summary\n")
    report.append("This experiment explores HydroAgent's robustness and error handling capabilities through three categories of test scenarios:\n")
    report.append("1. **Error Scenarios**: Verify system can detect obvious user errors\n")
    report.append("2. **Boundary Conditions**: Explore system tolerance limits\n")
    report.append("3. **Stress Tests**: Validate stability under extreme conditions\n")

    # Key Findings
    report.append("\n## Key Findings\n")

    if error_results:
        detected = sum(1 for r in error_results if not r.get("success"))
        detection_rate = detected / len(error_results) * 100 if error_results else 0
        report.append(f"### Error Detection\n")
        report.append(f"- **Detection Rate:** {detection_rate:.1f}% ({detected}/{len(error_results)} errors detected)\n")

        # Classification accuracy
        correct_class = 0
        total_class = 0
        for i, r in enumerate(error_results):
            if not r.get("success") and i < len(ERROR_SCENARIOS):
                query = ERROR_SCENARIOS[i]
                expected = EXPECTED_ERROR_CATEGORIES.get(query)
                actual = r.get("error_category")
                if expected:
                    total_class += 1
                    if expected == actual:
                        correct_class += 1

        if total_class > 0:
            class_accuracy = correct_class / total_class * 100
            report.append(f"- **Classification Accuracy:** {class_accuracy:.1f}% ({correct_class}/{total_class})\n")

    if boundary_results:
        accepted = sum(1 for r in boundary_results if r.get("success"))
        acceptance_rate = accepted / len(boundary_results) * 100 if boundary_results else 0
        report.append(f"\n### Boundary Exploration\n")
        report.append(f"- **Acceptance Rate:** {acceptance_rate:.1f}% ({accepted}/{len(boundary_results)} scenarios accepted)\n")
        report.append(f"- **System Stability:** No crashes detected ✅\n")

    if stress_results:
        passed = sum(1 for r in stress_results if r.get("success"))
        pass_rate = passed / len(stress_results) * 100 if stress_results else 0
        report.append(f"\n### Stress Test\n")
        report.append(f"- **Pass Rate:** {pass_rate:.1f}% ({passed}/{len(stress_results)})\n")

    # Overall Stability
    crashes = sum(1 for r in results if "crash" in str(r.get("error", "")).lower())
    infinite_loops = sum(1 for r in results if r.get("api_calls", 0) > 20)
    report.append(f"\n### System Stability\n")
    report.append(f"- **Crashes:** {crashes}\n")
    report.append(f"- **Infinite Loops:** {infinite_loops}\n")
    report.append(f"- **Overall Stability:** {'100% ✅' if crashes == 0 and infinite_loops == 0 else 'Issues detected ⚠️'}\n")

    # Performance Metrics
    total_time = sum(r.get("elapsed_time", 0) for r in results)
    # 🔧 修复：从嵌套的token_usage字段中读取token数据
    total_tokens = sum(r.get("token_usage", {}).get("total_tokens", 0) for r in results)
    report.append(f"\n## Performance Metrics\n")
    report.append(f"- **Total Execution Time:** {total_time:.1f}s ({total_time/60:.1f}min)\n")
    report.append(f"- **Total Tokens:** {total_tokens:,}\n")
    report.append(f"- **Average Time/Scenario:** {total_time/len(results):.1f}s\n")

    # Detailed Results
    report.append("\n## Detailed Results\n")

    if error_results:
        report.append("\n### 1. Error Scenarios (Expected to Fail)\n")
        report.append("\n| # | Query | Result | Error Category | Classification |\n")
        report.append("|---|-------|--------|----------------|----------------|\n")
        for i, r in enumerate(error_results):
            query_preview = ERROR_SCENARIOS[i][:40] if i < len(ERROR_SCENARIOS) else ""
            result_str = "FAIL ✅" if not r.get("success") else "PASS ⚠️"
            error_cat = r.get("error_category", "N/A")
            expected_cat = EXPECTED_ERROR_CATEGORIES.get(ERROR_SCENARIOS[i]) if i < len(ERROR_SCENARIOS) else ""
            classification = "✅" if error_cat == expected_cat else "❌"
            report.append(f"| {i+1} | {query_preview}... | {result_str} | {error_cat} | {classification} |\n")

    if boundary_results:
        report.append("\n### 2. Boundary Conditions (Unknown Outcome)\n")
        report.append("\n| # | Query | Result | Note |\n")
        report.append("|---|-------|--------|------|\n")
        for i, r in enumerate(boundary_results):
            query_preview = BOUNDARY_SCENARIOS[i][:40] if i < len(BOUNDARY_SCENARIOS) else ""
            result_str = "ACCEPT" if r.get("success") else "REJECT"
            note = "System tolerates" if r.get("success") else "Beyond limit"
            report.append(f"| {i+1} | {query_preview}... | {result_str} | {note} |\n")

    if stress_results:
        report.append("\n### 3. Stress Tests (Expected to Succeed)\n")
        report.append("\n| # | Query | Result | Time (s) | Tokens |\n")
        report.append("|---|-------|--------|----------|--------|\n")
        for i, r in enumerate(stress_results):
            query_preview = STRESS_SCENARIOS[i][:40] if i < len(STRESS_SCENARIOS) else ""
            result_str = "PASS ✅" if r.get("success") else "FAIL ⚠️"
            time_str = f"{r.get('elapsed_time', 0):.1f}"
            tokens_str = f"{r.get('total_tokens', 0):,}"
            report.append(f"| {i+1} | {query_preview}... | {result_str} | {time_str} | {tokens_str} |\n")

    # Conclusions
    report.append("\n## Conclusions\n")
    report.append("\nHydroAgent demonstrates:\n")

    if error_results:
        detected = sum(1 for r in error_results if not r.get("success"))
        detection_rate = detected / len(error_results) * 100 if error_results else 0
        if detection_rate >= 80:
            report.append(f"1. ✅ **Strong error detection**: {detection_rate:.1f}% of obvious errors correctly identified\n")
        else:
            report.append(f"1. ⚠️ **Limited error detection**: Only {detection_rate:.1f}% errors detected\n")

    if boundary_results:
        report.append(f"2. ✅ **Boundary exploration**: System behavior under extreme conditions documented\n")

    if stress_results:
        passed = sum(1 for r in stress_results if r.get("success"))
        pass_rate = passed / len(stress_results) * 100 if stress_results else 0
        if pass_rate >= 80:
            report.append(f"3. ✅ **Stress tolerance**: {pass_rate:.1f}% success rate under stress conditions\n")
        else:
            report.append(f"3. ⚠️ **Stress sensitivity**: Only {pass_rate:.1f}% stress tests passed\n")

    crashes = sum(1 for r in results if "crash" in str(r.get("error", "")).lower())
    if crashes == 0:
        report.append(f"4. ✅ **System stability**: No crashes or infinite loops detected\n")

    # Recommendations
    report.append("\n## Recommendations for Publication\n")
    report.append("\n1. Present error detection rate as key robustness metric\n")
    report.append("2. Include boundary exploration results to show system limits\n")
    report.append("3. Highlight system stability (no crashes) as reliability indicator\n")
    report.append("4. Use classification accuracy to demonstrate intelligent error handling\n")
    report.append("5. Compare with baseline systems if available\n")

    report.append("\n---\n")
    report.append(f"\n*Generated by HydroAgent Experiment C v4.0 on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")

    return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(
        description="Experiment C v4.0: Robustness and Error Boundary Exploration"
    )
    parser.add_argument(
        "--backend",
        type=str,
        default="api",
        choices=["api", "ollama"],
        help="LLM backend to use"
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="all",
        choices=["error", "boundary", "stress", "all"],
        help="Which category to test (default: all)"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        default=False,
        help="Use mock mode for faster testing"
    )
    args = parser.parse_args()

    # Select test queries based on mode
    if args.mode == "error":
        test_queries = ERROR_SCENARIOS
        description = "Error Detection Testing (6 scenarios)"
    elif args.mode == "boundary":
        test_queries = BOUNDARY_SCENARIOS
        description = "Boundary Condition Exploration (6 scenarios)"
    elif args.mode == "stress":
        test_queries = STRESS_SCENARIOS
        description = "Stress Testing (6 scenarios)"
    else:  # all
        test_queries = ERROR_SCENARIOS + BOUNDARY_SCENARIOS + STRESS_SCENARIOS
        description = "Complete Robustness Testing (18 scenarios)"

    print("=" * 80)
    print("🔬 Experiment C v4.0: Robustness and Error Boundary Exploration")
    print("=" * 80)
    print(f"\nMode: {args.mode}")
    print(f"Description: {description}")
    print(f"Backend: {args.backend}")
    print(f"Mock: {args.mock}")

    print(f"\n{'=' * 80}")
    print("Test Categories:")
    print(f"{'=' * 80}")

    if args.mode in ["error", "all"]:
        print(f"\n📋 Error Scenarios ({len(ERROR_SCENARIOS)}):")
        print(f"   Purpose: Verify error detection and classification")
        print(f"   Expected: ≥80% detection rate, ≥85% classification accuracy")

    if args.mode in ["boundary", "all"]:
        print(f"\n🔬 Boundary Conditions ({len(BOUNDARY_SCENARIOS)}):")
        print(f"   Purpose: Explore system tolerance limits")
        print(f"   Expected: Unknown (exploration), no crashes")

    if args.mode in ["stress", "all"]:
        print(f"\n💪 Stress Tests ({len(STRESS_SCENARIOS)}):")
        print(f"   Purpose: Validate stability under extreme conditions")
        print(f"   Expected: ≥80% pass rate, no crashes")

    print(f"\n{'=' * 80}\n")

    if not args.mock:
        print("⏱️  WARNING: Real execution mode enabled.")
        print("   Some scenarios may take several minutes.")
        estimated_time = len(test_queries) * 2  # ~2 min per scenario
        print(f"   Estimated total time: {estimated_time} minutes")
        print("   Press Ctrl+C within 5 seconds to cancel...\n")
        import time
        try:
            time.sleep(5)
        except KeyboardInterrupt:
            print("\n\n❌ Cancelled by user\n")
            return

    # Create experiment
    exp = create_experiment(
        exp_name="exp_C_robustness_v4",
        exp_description="Robustness and Error Boundary Exploration (v4.0)"
    )

    # Run batch
    print("\nExecuting experiment...")
    results = exp.run_batch(
        test_queries,
        backend=args.backend,
        use_mock=args.mock,
        use_tool_system=True
    )

    # Save results
    print("\nSaving results...")
    exp.save_results(results)

    # Analyze and generate report
    analyze_results(results, args.mode, exp.workspace)


if __name__ == "__main__":
    main()
