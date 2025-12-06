"""
替换实验2和3中的流域ID为有效流域
"""

import random
from pathlib import Path

# 有效流域列表
VALID_BASINS = [
    "01539000",
    "02070000",
    "02177000",
    "03346000",
    "03500000",
    "11532500",
    "12025000",
    "14301000",
    "14306500",
    "14325000",
]

# 设置随机种子以便复现
random.seed(42)

# 读取实验2
exp2_file = Path("experiment/exp_2_nlp_robustness.py")
exp3_file = Path("experiment/exp_3_config_reliability.py")

def extract_basin_ids(content):
    """提取所有流域ID（8位数字）"""
    import re
    pattern = r'\d{8}'  # 简化正则，不使用\b
    basins = set(re.findall(pattern, content))
    return sorted(basins)

def create_mapping(basins):
    """创建流域映射表（随机分配）"""
    mapping = {}
    valid_pool = VALID_BASINS.copy()

    for basin in basins:
        if basin in VALID_BASINS:
            # 已经是有效流域，保持不变
            mapping[basin] = basin
        else:
            # 随机选择一个有效流域
            if not valid_pool:
                valid_pool = VALID_BASINS.copy()
            new_basin = random.choice(valid_pool)
            mapping[basin] = new_basin
            # 允许重复使用（因为有很多流域需要替换）

    return mapping

def replace_basins(content, mapping):
    """替换内容中的流域ID"""
    for old, new in mapping.items():
        content = content.replace(old, new)
    return content

# 处理exp_2
print("Processing Exp 2...")
exp2_content = exp2_file.read_text(encoding='utf-8')
exp2_basins = extract_basin_ids(exp2_content)
print(f"  Found {len(exp2_basins)} unique basin IDs")

exp2_mapping = create_mapping(exp2_basins)
print(f"  Mapping:")
for old, new in sorted(exp2_mapping.items()):
    if old != new:
        print(f"    {old} -> {new}")

exp2_new_content = replace_basins(exp2_content, exp2_mapping)
exp2_file.write_text(exp2_new_content, encoding='utf-8')
print("  [OK] Exp 2 updated")

# 处理exp_3
print("\nProcessing Exp 3...")
exp3_content = exp3_file.read_text(encoding='utf-8')
exp3_basins = extract_basin_ids(exp3_content)
print(f"  Found {len(exp3_basins)} unique basin IDs")

exp3_mapping = create_mapping(exp3_basins)
print(f"  Mapping:")
for old, new in sorted(exp3_mapping.items()):
    if old != new:
        print(f"    {old} -> {new}")

exp3_new_content = replace_basins(exp3_content, exp3_mapping)
exp3_file.write_text(exp3_new_content, encoding='utf-8')
print("  [OK] Exp 3 updated")

print("\n" + "=" * 60)
print("[SUCCESS] All basin IDs replaced with valid basins")
print("=" * 60)
print(f"\nExp 2 uses: {sorted(set(exp2_mapping.values()))}")
print(f"Exp 3 uses: {sorted(set(exp3_mapping.values()))}")
