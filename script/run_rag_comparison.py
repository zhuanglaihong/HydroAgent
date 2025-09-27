"""
Author: zhuanglaihong
Date: 2024-09-26 17:15:00
LastEditTime: 2024-09-26 17:15:00
LastEditors: zhuanglaihong
Description: RAG效果对比测试快速运行脚本
FilePath: \HydroAgent\script\run_rag_comparison.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from test.test_rag_effectiveness_comparison import RAGEffectivenessComparison


def quick_demo():
    """快速演示单个测试用例"""
    print("="*80)
    print("RAG效果对比测试 - 快速演示")
    print("="*80)

    tester = RAGEffectivenessComparison(enable_logging=False)

    # 运行一个中等复杂度的测试用例
    test_cases = tester.get_complex_test_cases()
    demo_case = test_cases[0]  # 多流域模型比较

    print(f"演示用例: {demo_case['name']}")
    print(f"复杂度: {demo_case['complexity_level']}")
    print(f"查询: {demo_case['query'][:100]}...")
    print()

    try:
        result = tester.run_comparison_test(demo_case)

        print("测试完成！")
        print(f"RAG成功: {result.get('with_rag', {}).get('success', False)}")
        print(f"非RAG成功: {result.get('without_rag', {}).get('success', False)}")

        comparison = result.get('comparison', {})
        if comparison:
            print(f"质量提升: {comparison.get('quality_improvement', 0):.3f}")
            print(f"建议: {comparison.get('recommendation', '无')}")

        return True

    except Exception as e:
        print(f"测试失败: {e}")
        return False


def list_test_cases():
    """列出所有测试用例"""
    tester = RAGEffectivenessComparison()
    test_cases = tester.get_complex_test_cases()

    print("="*80)
    print("可用的RAG对比测试用例")
    print("="*80)

    for i, case in enumerate(test_cases, 1):
        print(f"\n{i}. ID: {case['case_id']}")
        print(f"   名称: {case['name']}")
        print(f"   复杂度: {case['complexity_level']}")
        print(f"   描述: {case['description']}")
        print(f"   查询示例: {case['query'][:80]}...")


def run_full_suite():
    """运行完整测试套件"""
    print("="*80)
    print("运行完整RAG效果对比测试套件")
    print("="*80)
    print("注意: 完整测试可能需要30-60分钟")

    confirm = input("确认运行完整测试套件? (y/N): ").strip().lower()
    if confirm != 'y':
        print("测试取消")
        return

    tester = RAGEffectivenessComparison(enable_logging=True)

    try:
        results = tester.run_full_comparison_suite(save_results=True)

        print("\n完整测试套件执行完成!")
        summary = results.get('summary', {})

        print("="*60)
        print("测试结果总结:")
        print(f"- 总测试用例: {summary.get('total_test_cases', 0)}")
        print(f"- RAG成功率: {summary.get('rag_success_rate', 0):.2%}")
        print(f"- 非RAG成功率: {summary.get('no_rag_success_rate', 0):.2%}")
        print(f"- RAG独有成功: {summary.get('rag_only_successes', 0)} 个")
        print(f"- 平均质量提升: {summary.get('average_quality_improvement', 0):.3f}")
        print(f"- RAG效果评分: {summary.get('rag_effectiveness_score', 0):.3f}")
        print(f"\n总体建议: {summary.get('recommendation', '无')}")
        print("="*60)

        return True

    except Exception as e:
        print(f"测试套件执行失败: {e}")
        return False


def main():
    """主菜单"""
    while True:
        print("\n" + "="*60)
        print("RAG效果对比测试工具")
        print("="*60)
        print("1. 快速演示 (运行单个测试用例)")
        print("2. 列出所有测试用例")
        print("3. 运行完整测试套件")
        print("4. 退出")
        print("="*60)

        try:
            choice = input("请选择操作 (1-4): ").strip()

            if choice == '1':
                quick_demo()
            elif choice == '2':
                list_test_cases()
            elif choice == '3':
                success = run_full_suite()
                if success:
                    break
            elif choice == '4':
                print("退出测试工具")
                break
            else:
                print("无效选择，请输入1-4")

        except KeyboardInterrupt:
            print("\n测试中断")
            break
        except Exception as e:
            print(f"操作失败: {e}")


if __name__ == "__main__":
    main()