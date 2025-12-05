"""
Author: Claude
Date: 2025-12-05 01:45:00
LastEditTime: 2025-12-05 01:45:00
LastEditors: Claude
Description: 测试result_serializer工具 - 验证不可序列化对象的处理
FilePath: /HydroAgent/test/test_result_serializer.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import json
import sys
from pathlib import Path
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from hydroagent.utils.result_serializer import sanitize_for_json, sanitize_result


def test_numpy_arrays():
    """测试numpy数组的转换"""
    print("=" * 70)
    print("测试1: Numpy数组转换")
    print("=" * 70)

    test_data = {
        "array_1d": np.array([1, 2, 3]),
        "array_2d": np.array([[1, 2], [3, 4]]),
        "int64": np.int64(42),
        "float64": np.float64(3.14159),
        "bool": np.bool_(True),
    }

    print("\n原始数据:")
    for key, value in test_data.items():
        print(f"  {key}: {type(value)} = {value}")

    cleaned = sanitize_for_json(test_data)

    print("\n清理后:")
    for key, value in cleaned.items():
        print(f"  {key}: {type(value)} = {value}")

    # 验证可序列化
    try:
        json_str = json.dumps(cleaned, indent=2)
        print("\n[OK] JSON序列化成功:")
        print(json_str[:200] + "...")
        return True
    except Exception as e:
        print(f"\n[ERROR] JSON序列化失败: {e}")
        return False


def test_path_objects():
    """测试Path对象的转换"""
    print("\n" + "=" * 70)
    print("测试2: Path对象转换")
    print("=" * 70)

    test_data = {
        "workspace": Path("/tmp/workspace"),
        "output_dir": Path("D:/results"),
        "nested": {
            "file": Path("/tmp/test.txt"),
            "list": [Path("/a"), Path("/b")]
        }
    }

    print("\n原始数据:")
    print(f"  workspace: {type(test_data['workspace'])} = {test_data['workspace']}")

    cleaned = sanitize_for_json(test_data)

    print("\n清理后:")
    print(f"  workspace: {type(cleaned['workspace'])} = {cleaned['workspace']}")

    # 验证可序列化
    try:
        json_str = json.dumps(cleaned, indent=2)
        print("\n[OK] JSON序列化成功")
        return True
    except Exception as e:
        print(f"\n[ERROR] JSON序列化失败: {e}")
        return False


def test_nested_structures():
    """测试嵌套结构"""
    print("\n" + "=" * 70)
    print("测试3: 嵌套结构转换")
    print("=" * 70)

    test_data = {
        "success": True,
        "result": {
            "params": {"x1": np.float64(0.5), "x2": np.float64(0.3)},
            "metrics": {
                "NSE": np.array([0.68, 0.72, 0.75]),
                "RMSE": np.float32(1.5)
            }
        },
        "workspace": Path("/tmp/session_123"),
        "execution_results": [
            {"basin": "01013500", "nse": np.float64(0.68)},
            {"basin": "01022500", "nse": np.float64(0.72)}
        ]
    }

    print("\n原始数据结构:")
    print(f"  result.metrics.NSE: {type(test_data['result']['metrics']['NSE'])}")
    print(f"  workspace: {type(test_data['workspace'])}")

    cleaned = sanitize_for_json(test_data)

    print("\n清理后:")
    print(f"  result.metrics.NSE: {type(cleaned['result']['metrics']['NSE'])}")
    print(f"  workspace: {type(cleaned['workspace'])}")

    # 验证可序列化
    try:
        json_str = json.dumps(cleaned, indent=2)
        print("\n[OK] JSON序列化成功")
        print(f"  JSON长度: {len(json_str)} 字符")
        return True
    except Exception as e:
        print(f"\n[ERROR] JSON序列化失败: {e}")
        return False


def test_real_world_scenario():
    """模拟真实场景：Runner返回结果"""
    print("\n" + "=" * 70)
    print("测试4: 真实场景 - RunnerAgent结果")
    print("=" * 70)

    # 模拟RunnerAgent可能返回的结果
    runner_result = {
        "success": True,
        "task_id": "task_1",
        "mode": "calibrate",
        "result": {
            "status": "success",
            "best_params": {
                "x1": np.float64(0.970),
                "x2": np.float64(0.053),
                "x3": np.float64(0.294),
                "x4": np.float64(0.878)
            },
            "metrics": {
                "NSE": np.array([0.68]),
                "RMSE": np.float32(2.46),
                "KGE": np.float64(0.65)
            },
            "convergence_history": np.array([3.5, 3.2, 2.9, 2.7, 2.5, 2.46]),
            "calibration_dir": Path("/tmp/task_1"),
        },
        "workspace": Path("/tmp/session_123"),
        "execution_log": "Calibration completed successfully..."
    }

    print("\n原始结果包含:")
    print(f"  - numpy float64: {type(runner_result['result']['best_params']['x1'])}")
    print(f"  - numpy array: {type(runner_result['result']['metrics']['NSE'])}")
    print(f"  - Path object: {type(runner_result['result']['calibration_dir'])}")

    # 清理
    cleaned = sanitize_result(runner_result)

    print("\n清理后:")
    print(f"  - best_params.x1: {type(cleaned['result']['best_params']['x1'])}")
    print(f"  - metrics.NSE: {type(cleaned['result']['metrics']['NSE'])}")
    print(f"  - calibration_dir: {type(cleaned['result']['calibration_dir'])}")

    # 验证可序列化并保存
    try:
        json_str = json.dumps(cleaned, indent=2, ensure_ascii=False)
        print("\n[OK] JSON序列化成功")

        # 尝试保存到文件
        test_file = Path(__file__).parent.parent / "logs" / "test_serialization.json"
        test_file.parent.mkdir(exist_ok=True)

        with open(test_file, "w", encoding="utf-8") as f:
            f.write(json_str)

        print(f"[OK] 成功保存到文件: {test_file}")
        print(f"  文件大小: {test_file.stat().st_size} 字节")

        # 读取验证
        with open(test_file, "r", encoding="utf-8") as f:
            reloaded = json.load(f)

        print(f"[OK] 成功从文件读取: {len(reloaded)} 个键")

        return True
    except Exception as e:
        print(f"\n[ERROR] 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\nResult Serializer 测试套件")
    print("=" * 70)

    results = []

    # 运行测试
    results.append(("Numpy数组", test_numpy_arrays()))
    results.append(("Path对象", test_path_objects()))
    results.append(("嵌套结构", test_nested_structures()))
    results.append(("真实场景", test_real_world_scenario()))

    # 汇总
    print("\n" + "=" * 70)
    print("测试结果汇总")
    print("=" * 70)

    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} {name}")

    all_passed = all(r[1] for r in results)

    print("\n" + "=" * 70)
    if all_passed:
        print("[SUCCESS] 所有测试通过！")
    else:
        print("[WARNING] 部分测试失败")
    print("=" * 70)

    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
