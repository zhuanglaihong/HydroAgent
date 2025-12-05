"""
Author: Claude
Date: 2025-12-05 01:30:00
LastEditTime: 2025-12-05 01:30:00
LastEditors: Claude
Description: 结果序列化工具 - 处理不可JSON序列化的对象（numpy数组、Path等）
FilePath: /HydroAgent/hydroagent/utils/result_serializer.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

功能：
- 递归清理字典/列表中的不可序列化对象
- 转换numpy数组为列表
- 转换Path对象为字符串
- 转换pandas对象为原生Python类型
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Union
import numpy as np

logger = logging.getLogger(__name__)


def sanitize_for_json(obj: Any) -> Any:
    """
    递归清理对象，使其可以JSON序列化。

    转换规则：
    - np.ndarray → list
    - np.integer → int
    - np.floating → float
    - np.bool_ → bool
    - Path → str
    - dict → 递归清理所有值
    - list/tuple → 递归清理所有元素
    - 其他不可序列化对象 → str(obj)

    Args:
        obj: 任意Python对象

    Returns:
        可JSON序列化的对象
    """
    # None, bool, int, float, str - 直接返回
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj

    # numpy数组和数值类型
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)

    # Path对象
    elif isinstance(obj, Path):
        return str(obj)

    # 字典 - 递归清理
    elif isinstance(obj, dict):
        return {key: sanitize_for_json(value) for key, value in obj.items()}

    # 列表/元组 - 递归清理
    elif isinstance(obj, (list, tuple)):
        return [sanitize_for_json(item) for item in obj]

    # pandas对象
    elif hasattr(obj, 'to_dict'):
        # DataFrame/Series
        try:
            return sanitize_for_json(obj.to_dict())
        except Exception:
            pass

    elif hasattr(obj, 'isoformat'):
        # Timestamp/datetime
        try:
            return obj.isoformat()
        except Exception:
            pass

    # 其他不可序列化对象 - 转为字符串
    try:
        # 尝试JSON序列化测试
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        # 不可序列化，转为字符串
        logger.debug(f"Converting non-serializable object to string: {type(obj)}")
        return str(obj)


def sanitize_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    清理单个结果字典，确保所有字段可JSON序列化。

    Args:
        result: 结果字典（来自Agent或Orchestrator）

    Returns:
        清理后的结果字典
    """
    return sanitize_for_json(result)


def sanitize_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    清理结果列表，确保所有元素可JSON序列化。

    Args:
        results: 结果字典列表

    Returns:
        清理后的结果列表
    """
    return [sanitize_result(r) for r in results]


def test_serialization(obj: Any) -> bool:
    """
    测试对象是否可JSON序列化。

    Args:
        obj: 待测试对象

    Returns:
        True if serializable, False otherwise
    """
    try:
        json.dumps(obj)
        return True
    except (TypeError, ValueError):
        return False


if __name__ == "__main__":
    # 测试用例
    import numpy as np
    from pathlib import Path

    # 测试数据
    test_data = {
        "success": True,
        "array": np.array([1, 2, 3]),
        "int": np.int64(42),
        "float": np.float64(3.14),
        "bool": np.bool_(True),
        "path": Path("/tmp/test.txt"),
        "nested": {
            "list": [np.array([4, 5]), Path("/tmp")],
            "dict": {"val": np.float32(1.5)}
        }
    }

    print("Before sanitization:")
    print(f"  Serializable: {test_serialization(test_data)}")

    cleaned = sanitize_for_json(test_data)

    print("\nAfter sanitization:")
    print(f"  Serializable: {test_serialization(cleaned)}")
    print(f"  JSON: {json.dumps(cleaned, indent=2)}")
