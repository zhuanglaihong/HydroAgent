"""
快速测试流域ID验证功能
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from hydroagent.utils.config_validator import validate_basin_id

# 测试用例
test_cases = [
    ("01013500", "正常流域ID"),
    ("99999999", "超出范围的流域ID"),
    ("123", "格式错误（长度不足）"),
    ("abcd1234", "格式错误（包含字母）"),
]

print("=" * 70)
print("流域ID验证测试")
print("=" * 70)

for basin_id, description in test_cases:
    print(f"\n测试: {description}")
    print(f"  输入: {basin_id}")

    error = validate_basin_id(basin_id)

    if error:
        print(f"  ❌ 验证失败")
        print(f"  错误信息:\n{error}")
    else:
        print(f"  ✅ 验证通过")

print("\n" + "=" * 70)
