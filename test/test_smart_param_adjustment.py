"""
Author: Claude
Date: 2025-12-05 00:00:00
LastEditTime: 2025-12-05 00:00:00
LastEditors: Claude
Description: 测试智能边界自适应参数调整功能
             Test smart boundary-adaptive parameter range adjustment
FilePath: /HydroAgent/test/test_smart_param_adjustment.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import sys
from pathlib import Path
import logging
from datetime import datetime
import io

# Set console encoding (Windows compatible)
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup logging
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

log_file = logs_dir / f"test_smart_param_adjustment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)


def create_mock_calibration_result_with_boundary_params():
    """
    创建一个模拟的率定结果，包含不同边界情况的参数。

    场景：
    - x1: 接近下边界（需要向下扩展）
    - x2: 接近上边界（需要向上扩展）
    - x3: 在中间区域（保持不变）
    - x4: 在中间区域（保持不变）
    """
    from pathlib import Path
    import yaml
    import pandas as pd

    # 创建临时目录
    test_dir = project_root / "test" / "temp_smart_adjustment_result"
    test_dir.mkdir(parents=True, exist_ok=True)

    # 1. 创建 param_range.yaml（GR4J参数范围）
    param_range = {
        "x1": [100.0, 1500.0],  # 产流土壤蓄水容量 (mm)
        "x2": [-5.0, 3.0],       # 地下水交换系数 (mm)
        "x3": [20.0, 500.0],     # 汇流土壤蓄水容量 (mm)
        "x4": [1.0, 5.0],        # 单位线汇流时间 (day)
    }

    with open(test_dir / "param_range.yaml", "w", encoding="utf-8") as f:
        yaml.dump(param_range, f, default_flow_style=False)

    logger.info(f"✅ 创建 param_range.yaml: {param_range}")

    # 2. 创建 basins_denorm_params.csv（模拟不同边界情况的最佳参数）
    best_params_df = pd.DataFrame({
        "basin_id": ["01013500"],
        "x1": [120.0],   # 接近下边界 (100-1500, 距离下边界仅20)
        "x2": [2.8],     # 接近上边界 (-5 to 3, 距离上边界仅0.2)
        "x3": [250.0],   # 中间区域 (20-500)
        "x4": [3.0],     # 中间区域 (1-5)
    })

    best_params_df.to_csv(test_dir / "basins_denorm_params.csv", index=False)

    logger.info(f"✅ 创建 basins_denorm_params.csv")
    logger.info(f"   最佳参数（边界情况）:")
    logger.info(f"   - x1=120.0 (接近下边界 100, 距离仅20)")
    logger.info(f"   - x2=2.8 (接近上边界 3, 距离仅0.2)")
    logger.info(f"   - x3=250.0 (中间区域)")
    logger.info(f"   - x4=3.0 (中间区域)")

    return test_dir


def test_smart_adjustment():
    """测试智能边界自适应调整功能。"""
    from hydroagent.utils.param_range_adjuster import adjust_from_previous_calibration

    print("\n" + "=" * 80)
    print("测试智能边界自适应参数调整功能")
    print("=" * 80 + "\n")

    # 1. 创建模拟数据（包含边界情况）
    print("📂 步骤1: 创建模拟率定结果（包含边界参数）...")
    mock_calib_dir = create_mock_calibration_result_with_boundary_params()
    print(f"   模拟目录: {mock_calib_dir}\n")

    # 2. 测试智能调整（默认启用）
    print("=" * 80)
    print("🧠 场景1: 智能边界自适应调整（smart_adjustment=True）")
    print("=" * 80 + "\n")
    print("📋 策略说明:")
    print("   - x1 (接近下边界) → 向下扩展下边界")
    print("   - x2 (接近上边界) → 向上扩展上边界")
    print("   - x3, x4 (中间区域) → 保持范围不变\n")

    result_smart = adjust_from_previous_calibration(
        prev_calibration_dir=str(mock_calib_dir),
        range_scale=0.6,  # 这个参数在智能模式下不会对所有参数生效
        boundary_threshold=0.1,  # 10% 阈值
        boundary_expand_factor=1.5,  # 扩展50%
        smart_adjustment=True,
        output_yaml_path=str(mock_calib_dir / "smart_adjusted_param_range.yaml")
    )

    # 3. 显示智能调整结果
    print("\n" + "=" * 80)
    print("📊 智能调整结果:")
    print("=" * 80 + "\n")

    if result_smart["success"]:
        print("✅ 参数范围调整成功!\n")

        # 显示每个参数的调整策略
        for param_name, log in result_smart["adjustment_log"].items():
            strategy = log["strategy"]
            prev_range = log["prev_range"]
            best_value = log["best_value"]
            new_range = log["new_range"]

            # 策略中文说明
            strategy_map = {
                "expand_lower_boundary": "🔽 向下扩展下边界",
                "expand_upper_boundary": "🔼 向上扩展上边界",
                "keep_unchanged": "✅ 保持不变（收敛良好）",
                "uniform_shrink": "🔄 统一缩小（旧版本）"
            }

            print(f"参数 {param_name}:")
            print(f"  调整策略: {strategy_map.get(strategy, strategy)}")
            print(f"  最佳值: {best_value}")
            print(f"  原范围: [{prev_range[0]}, {prev_range[1]}] (长度: {prev_range[1] - prev_range[0]})")
            print(f"  新范围: [{new_range[0]:.2f}, {new_range[1]:.2f}] (长度: {new_range[1] - new_range[0]:.2f})")
            print(f"  范围变化: {log['range_change']}\n")

        print(f"💾 输出文件: {result_smart['output_file']}\n")

    else:
        print(f"❌ 调整失败: {result_smart.get('error')}")
        return False

    # 4. 对比：旧版本行为（统一缩小）
    print("=" * 80)
    print("🔄 场景2: 旧版本行为（smart_adjustment=False）")
    print("=" * 80 + "\n")
    print("📋 策略说明: 所有参数统一缩小至60%范围\n")

    result_old = adjust_from_previous_calibration(
        prev_calibration_dir=str(mock_calib_dir),
        range_scale=0.6,
        smart_adjustment=False,  # 禁用智能调整
        output_yaml_path=str(mock_calib_dir / "old_adjusted_param_range.yaml")
    )

    print("\n" + "=" * 80)
    print("📊 旧版本调整结果:")
    print("=" * 80 + "\n")

    if result_old["success"]:
        print("✅ 参数范围调整成功!\n")

        for param_name, log in result_old["adjustment_log"].items():
            prev_range = log["prev_range"]
            best_value = log["best_value"]
            new_range = log["new_range"]

            print(f"参数 {param_name}:")
            print(f"  调整策略: 统一缩小（60%）")
            print(f"  最佳值: {best_value}")
            print(f"  原范围: [{prev_range[0]}, {prev_range[1]}]")
            print(f"  新范围: [{new_range[0]:.2f}, {new_range[1]:.2f}]")
            print(f"  范围变化: {log['range_change']}\n")

        print(f"💾 输出文件: {result_old['output_file']}\n")

    # 5. 对比分析
    print("=" * 80)
    print("📈 对比分析：智能调整 vs 旧版本")
    print("=" * 80 + "\n")

    for param_name in result_smart["adjustment_log"].keys():
        smart_log = result_smart["adjustment_log"][param_name]
        old_log = result_old["adjustment_log"][param_name]

        smart_length = smart_log["new_range"][1] - smart_log["new_range"][0]
        old_length = old_log["new_range"][1] - old_log["new_range"][0]

        print(f"参数 {param_name}:")
        print(f"  智能调整: {smart_log['strategy']}, 新范围长度={smart_length:.2f}")
        print(f"  旧版本: uniform_shrink, 新范围长度={old_length:.2f}")
        print(f"  差异: {smart_length - old_length:+.2f}\n")

    print("=" * 80)
    print("✅ 测试完成!")
    print("=" * 80)
    return True


def main():
    """主函数。"""
    print("\n╔════════════════════════════════════════════════════════════════════════╗")
    print("║          测试智能边界自适应参数调整功能                                ║")
    print("╚════════════════════════════════════════════════════════════════════════╝")
    print(f"\n📝 日志文件: {log_file}\n")

    success = test_smart_adjustment()

    if success:
        print("\n🎉 测试通过!")
        return 0
    else:
        print("\n❌ 测试失败!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
