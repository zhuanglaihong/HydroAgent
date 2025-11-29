"""
测试TaskTypeDetector的任务类型检测（验证修复）

验证点：
1. 多流域检测（实验2b）- 从intent、task_plan、subtask_results提取basin_ids
2. 多算法×模型检测（实验2c）- 从多个数据源提取
3. 向后兼容性
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

from hydroagent.utils.task_detector import TaskTypeDetector


def test_multi_basin_detection():
    """测试多流域检测（实验2b场景）"""
    print("\n" + "=" * 70)
    print("测试1: 多流域检测（实验2b）")
    print("=" * 70)

    # 场景1: basin_ids在intent中
    intent = {
        "intent_result": {
            "basin_ids": ["01013500", "01022500", "01030500", "01031500", "01047000",
                          "01052500", "01054200", "01055000", "01057000", "01170100"],
            "algorithms": ["SCE_UA"],
            "model_names": ["gr4j"]
        }
    }

    task_plan = {
        "task_type": "batch_processing",
        "subtasks": [
            {"task_id": "task_1", "parameters": {"basin_id": "01013500", "algorithm": "SCE_UA", "model_name": "gr4j"}},
            {"task_id": "task_2", "parameters": {"basin_id": "01022500", "algorithm": "SCE_UA", "model_name": "gr4j"}},
            # ... 其他任务
        ]
    }

    subtask_results = [
        {"success": True, "config": {}},
        {"success": True, "config": {}},
    ]

    task_type = TaskTypeDetector.detect_task_type(subtask_results, task_plan, intent)

    print(f"\n场景1: basin_ids在intent中")
    print(f"  结果: {task_type}")
    if task_type == "multi_basin":
        print("  ✅ PASS: 正确检测到multi_basin")
        return True
    else:
        print(f"  ❌ FAIL: 期望multi_basin，实际{task_type}")
        return False


def test_multi_algorithm_detection():
    """测试多算法×模型检测（实验2c场景）"""
    print("\n" + "=" * 70)
    print("测试2: 多算法×模型检测（实验2c）")
    print("=" * 70)

    # 场景1: algorithms和model_names在intent中
    intent = {
        "intent_result": {
            "basin_ids": ["12025000"],
            "algorithms": ["SCE_UA", "GA", "SCIPY"],
            "model_names": ["xaj", "gr4j", "gr5j", "gr6j"]
        }
    }

    task_plan = {
        "task_type": "batch_processing",
        "subtasks": [
            {"task_id": "task_1", "parameters": {"basin_id": "12025000", "algorithm": "SCE_UA", "model_name": "xaj"}},
            {"task_id": "task_2", "parameters": {"basin_id": "12025000", "algorithm": "SCE_UA", "model_name": "gr4j"}},
            # ... 12个任务
        ] * 12
    }

    subtask_results = [{"success": True, "config": {}} for _ in range(12)]

    task_type = TaskTypeDetector.detect_task_type(subtask_results, task_plan, intent)

    print(f"\n场景1: algorithms和model_names在intent中")
    print(f"  结果: {task_type}")
    if task_type == "multi_algorithm":
        print("  ✅ PASS: 正确检测到multi_algorithm")
        return True
    else:
        print(f"  ❌ FAIL: 期望multi_algorithm，实际{task_type}")
        return False


def test_fallback_from_task_plan():
    """测试从task_plan兜底提取（intent为空的情况）"""
    print("\n" + "=" * 70)
    print("测试3: 从task_plan兜底提取basin_ids")
    print("=" * 70)

    # intent为空，但task_plan中有basin_ids
    intent = {"intent_result": {}}

    task_plan = {
        "task_type": "batch_processing",
        "subtasks": [
            {"task_id": "task_1", "parameters": {"basin_id": "01013500", "algorithm": "SCE_UA", "model_name": "gr4j"}},
            {"task_id": "task_2", "parameters": {"basin_id": "01022500", "algorithm": "SCE_UA", "model_name": "gr4j"}},
            {"task_id": "task_3", "parameters": {"basin_id": "01030500", "algorithm": "SCE_UA", "model_name": "gr4j"}},
        ]
    }

    subtask_results = [{"success": True, "config": {}} for _ in range(3)]

    task_type = TaskTypeDetector.detect_task_type(subtask_results, task_plan, intent)

    print(f"\n场景: intent为空，从task_plan提取")
    print(f"  结果: {task_type}")
    if task_type == "multi_basin":
        print("  ✅ PASS: 成功从task_plan兜底提取")
        return True
    else:
        print(f"  ❌ FAIL: 期望multi_basin，实际{task_type}")
        return False


def test_fallback_from_subtask_results():
    """测试从subtask_results兜底提取（intent和task_plan都为空）"""
    print("\n" + "=" * 70)
    print("测试4: 从subtask_results兜底提取algorithms/models")
    print("=" * 70)

    # intent和task_plan都为空，但subtask_results中有config
    intent = {"intent_result": {}}
    task_plan = {"subtasks": []}

    subtask_results = [
        {
            "success": True,
            "config": {
                "training_cfgs": {"algorithm_name": "SCE_UA"},
                "model_cfgs": {"model_name": "xaj"}
            }
        },
        {
            "success": True,
            "config": {
                "training_cfgs": {"algorithm_name": "GA"},
                "model_cfgs": {"model_name": "xaj"}
            }
        },
        {
            "success": True,
            "config": {
                "training_cfgs": {"algorithm_name": "SCIPY"},
                "model_cfgs": {"model_name": "gr4j"}
            }
        },
    ]

    task_type = TaskTypeDetector.detect_task_type(subtask_results, task_plan, intent)

    print(f"\n场景: intent和task_plan为空，从subtask_results提取")
    print(f"  结果: {task_type}")
    if task_type == "multi_algorithm":
        print("  ✅ PASS: 成功从subtask_results兜底提取")
        return True
    else:
        print(f"  ❌ FAIL: 期望multi_algorithm，实际{task_type}")
        return False


def test_backward_compatibility():
    """测试向后兼容性（旧版数据结构）"""
    print("\n" + "=" * 70)
    print("测试5: 向后兼容性")
    print("=" * 70)

    # 旧版结构：单个basin_id字符串而非列表
    intent = {
        "intent_result": {
            "basin_id": "01013500",  # 单个字符串
            "algorithm": "SCE_UA",
            "model_name": "gr4j"
        }
    }

    task_plan = {"subtasks": []}
    subtask_results = [{"success": True, "config": {}}]

    task_type = TaskTypeDetector.detect_task_type(subtask_results, task_plan, intent)

    print(f"\n场景: 旧版单任务数据结构")
    print(f"  结果: {task_type}")
    if task_type == "single_task":
        print("  ✅ PASS: 向后兼容，正确处理旧版数据")
        return True
    else:
        print(f"  ❌ FAIL: 期望single_task，实际{task_type}")
        return False


def main():
    """运行所有测试"""
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║     测试TaskTypeDetector任务类型检测（验证修复）              ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    results = []

    results.append(("多流域检测", test_multi_basin_detection()))
    results.append(("多算法×模型检测", test_multi_algorithm_detection()))
    results.append(("从task_plan兜底提取", test_fallback_from_task_plan()))
    results.append(("从subtask_results兜底提取", test_fallback_from_subtask_results()))
    results.append(("向后兼容性", test_backward_compatibility()))

    print("\n" + "=" * 70)
    print("测试结果汇总")
    print("=" * 70)

    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")

    all_passed = all(r[1] for r in results)

    print("\n" + "=" * 70)
    if all_passed:
        print("🎉 所有测试通过！TaskTypeDetector修复成功")
        print("\n修复效果：")
        print("  ✅ 支持从intent提取basin_ids/algorithms/models")
        print("  ✅ 支持从task_plan兜底提取")
        print("  ✅ 支持从subtask_results兜底提取")
        print("  ✅ 向后兼容旧版数据结构")
        print("\n现在实验2b和2c应该能正确检测任务类型并生成汇总图了！")
    else:
        print("⚠️  部分测试失败，请检查修复")
    print("=" * 70)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
