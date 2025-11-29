"""
测试IntentAgent中的算法/模型列表提取逻辑

验证点:
1. 正确处理字符串形式的列表（如"['SCE_UA', 'GA']"）
2. 正确处理真实的Python列表
3. 正确处理单个字符串
4. 去重并保持顺序
"""

import sys
import io
from pathlib import Path

# Set console encoding for Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# Add project root
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from hydroagent.agents.intent_agent import IntentAgent


# Create a mock LLM interface
class MockLLM:
    def call(self, *args, **kwargs):
        return ""


def test_extract_algorithms():
    """测试算法列表提取"""
    print("\n" + "=" * 70)
    print("测试1: 算法列表提取")
    print("=" * 70)

    # 创建IntentAgent实例（使用模拟LLM）
    agent = IntentAgent(llm_interface=MockLLM())

    test_cases = [
        {
            "name": "字符串形式的列表",
            "intent_result": {"algorithm": "['SCE_UA', 'GA', 'SCIPY']"},
            "query": "使用 SCE-UA、GA、scipy 算法",
            "expected": ["SCE_UA", "GA", "SCIPY"]
        },
        {
            "name": "真实的Python列表",
            "intent_result": {"algorithm": ["SCE_UA", "GA"]},
            "query": "使用 SCE-UA、GA 算法",
            "expected": ["SCE_UA", "GA"]
        },
        {
            "name": "单个字符串",
            "intent_result": {"algorithm": "SCE_UA"},
            "query": "使用 SCE-UA 算法",
            "expected": ["SCE_UA"]
        },
        {
            "name": "列表+查询重复",
            "intent_result": {"algorithm": ["SCE_UA"]},
            "query": "使用 SCE-UA、GA 算法",
            "expected": ["SCE_UA", "GA"]
        },
        {
            "name": "空intent_result",
            "intent_result": {},
            "query": "使用 SCE-UA、GA、scipy 算法",
            "expected": ["SCE_UA", "GA", "SCIPY"]
        }
    ]

    all_passed = True

    for i, test_case in enumerate(test_cases, 1):
        result = agent._extract_multiple_algorithms(
            test_case["query"],
            test_case["intent_result"]
        )

        passed = result == test_case["expected"]
        status = "✅ PASS" if passed else "❌ FAIL"

        print(f"\n测试 {i}: {test_case['name']}")
        print(f"  Intent: {test_case['intent_result'].get('algorithm', 'None')}")
        print(f"  查询: {test_case['query']}")
        print(f"  期望: {test_case['expected']}")
        print(f"  实际: {result}")
        print(f"  {status}")

        if not passed:
            all_passed = False

    return all_passed


def test_extract_models():
    """测试模型列表提取"""
    print("\n" + "=" * 70)
    print("测试2: 模型列表提取")
    print("=" * 70)

    agent = IntentAgent(llm_interface=MockLLM())

    test_cases = [
        {
            "name": "字符串形式的列表",
            "intent_result": {"model_name": "['xaj', 'gr4j', 'gr5j']"},
            "query": "使用 XAJ、GR4J、GR5J 模型",
            "expected": ["xaj", "gr4j", "gr5j"]
        },
        {
            "name": "真实的Python列表",
            "intent_result": {"model_name": ["xaj", "gr4j"]},
            "query": "使用 XAJ、GR4J 模型",
            "expected": ["xaj", "gr4j"]
        },
        {
            "name": "单个字符串",
            "intent_result": {"model_name": "gr4j"},
            "query": "使用 GR4J 模型",
            "expected": ["gr4j"]
        },
        {
            "name": "列表+查询重复",
            "intent_result": {"model_name": ["xaj"]},
            "query": "使用 XAJ、GR4J 模型",
            "expected": ["xaj", "gr4j"]
        }
    ]

    all_passed = True

    for i, test_case in enumerate(test_cases, 1):
        result = agent._extract_multiple_models(
            test_case["query"],
            test_case["intent_result"]
        )

        passed = result == test_case["expected"]
        status = "✅ PASS" if passed else "❌ FAIL"

        print(f"\n测试 {i}: {test_case['name']}")
        print(f"  Intent: {test_case['intent_result'].get('model_name', 'None')}")
        print(f"  查询: {test_case['query']}")
        print(f"  期望: {test_case['expected']}")
        print(f"  实际: {result}")
        print(f"  {status}")

        if not passed:
            all_passed = False

    return all_passed


def test_task_generation():
    """测试实验2c场景：3算法 × 4模型 = 12任务"""
    print("\n" + "=" * 70)
    print("测试3: 实验2c任务生成（3算法 × 4模型）")
    print("=" * 70)

    agent = IntentAgent(llm_interface=MockLLM())

    # 模拟LLM返回的intent_result（算法是字符串列表）
    intent_result = {
        "algorithm": "['SCE_UA', 'GA', 'SCIPY']",  # 字符串形式的列表
        "model_name": "xaj"
    }

    query = "对流域 12025000 分别使用 SCE-UA、GA、scipy 三种算法，结合 XAJ、GR4J、GR5J、GR6J 四种模型进行率定"

    algorithms = agent._extract_multiple_algorithms(query, intent_result)
    models = agent._extract_multiple_models(query, intent_result)

    print(f"\n提取结果:")
    print(f"  算法: {algorithms} (共{len(algorithms)}个)")
    print(f"  模型: {models} (共{len(models)}个)")

    expected_task_count = len(algorithms) * len(models)
    print(f"\n预期生成任务数: {expected_task_count} = {len(algorithms)} × {len(models)}")

    # 验证算法列表不包含字符串形式的列表
    has_string_list = any(
        isinstance(algo, str) and algo.startswith("[") and algo.endswith("]")
        for algo in algorithms
    )

    if has_string_list:
        print("❌ FAIL: 算法列表中包含字符串形式的列表！")
        return False

    if algorithms == ["SCE_UA", "GA", "SCIPY"] and models == ["xaj", "gr4j", "gr5j", "gr6j"]:
        print("✅ PASS: 算法和模型列表提取正确")
        return True
    else:
        print("❌ FAIL: 算法或模型列表不正确")
        return False


def main():
    """运行所有测试"""
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║     测试IntentAgent算法/模型列表提取逻辑                      ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    results = []

    results.append(("算法列表提取", test_extract_algorithms()))
    results.append(("模型列表提取", test_extract_models()))
    results.append(("实验2c任务生成", test_task_generation()))

    print("\n" + "=" * 70)
    print("测试结果汇总")
    print("=" * 70)

    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")

    all_passed = all(r[1] for r in results)

    print("\n" + "=" * 70)
    if all_passed:
        print("🎉 所有测试通过！")
    else:
        print("⚠️  部分测试失败，请检查修复")
    print("=" * 70)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
