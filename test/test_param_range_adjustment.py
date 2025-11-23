"""
Author: Claude
Date: 2025-01-23 00:30:00
LastEditTime: 2025-01-23 00:30:00
LastEditors: Claude
Description: 测试智能参数范围调整功能
             Test smart parameter range adjustment
FilePath: /HydroAgent/test/test_param_range_adjustment.py
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

log_file = logs_dir / f"test_param_range_adjustment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)


def create_mock_calibration_result():
    """
    创建一个模拟的率定结果目录结构，用于测试。
    """
    from pathlib import Path
    import yaml
    import pandas as pd

    # 创建临时目录
    test_dir = project_root / "test" / "temp_calibration_result"
    test_dir.mkdir(parents=True, exist_ok=True)

    # 1. 创建 param_range.yaml（模拟GR4J参数范围）
    param_range = {
        "x1": [100.0, 1500.0],  # 产流土壤蓄水容量 (mm)
        "x2": [-5.0, 3.0],       # 地下水交换系数 (mm)
        "x3": [20.0, 500.0],     # 汇流土壤蓄水容量 (mm)
        "x4": [1.0, 5.0],        # 单位线汇流时间 (day)
    }

    with open(test_dir / "param_range.yaml", "w", encoding="utf-8") as f:
        yaml.dump(param_range, f, default_flow_style=False)

    logger.info(f"✅ 创建 param_range.yaml: {param_range}")

    # 2. 创建 basins_denorm_params.csv（模拟最佳参数，反归一化）
    # 假设第一次率定的最佳参数
    best_params_df = pd.DataFrame({
        "basin_id": ["01013500"],
        "x1": [350.0],   # 接近下边界 (100-1500)
        "x2": [-1.5],    # 中间偏下
        "x3": [120.0],   # 偏下
        "x4": [2.5],     # 中间
    })

    best_params_df.to_csv(test_dir / "basins_denorm_params.csv", index=False)

    logger.info(f"✅ 创建 basins_denorm_params.csv")
    logger.info(f"   最佳参数: x1=350.0, x2=-1.5, x3=120.0, x4=2.5")

    return test_dir


def test_param_range_adjustment():
    """测试参数范围调整功能。"""
    from hydroagent.agents.runner_agent import RunnerAgent
    from hydroagent.core.llm_interface import create_llm_interface

    print("\n" + "=" * 70)
    print("测试智能参数范围调整功能")
    print("=" * 70 + "\n")

    # 1. 创建模拟数据
    print("📂 步骤1: 创建模拟率定结果...")
    mock_calib_dir = create_mock_calibration_result()
    print(f"   模拟目录: {mock_calib_dir}\n")

    # 2. 创建RunnerAgent
    print("🔧 步骤2: 初始化RunnerAgent...")
    llm = create_llm_interface("ollama", "qwen3:8b")  # 占位符，不使用LLM
    runner_agent = RunnerAgent(llm_interface=llm)
    print("   ✅ RunnerAgent初始化完成\n")

    # 3. 测试参数范围调整
    print("🔄 步骤3: 调整参数范围（scale=0.6）...")
    print("   策略: 以最佳参数为中心，缩小搜索范围至原来的60%\n")

    result = runner_agent.adjust_param_range_from_previous_calibration(
        prev_calibration_dir=str(mock_calib_dir),
        range_scale=0.6,
        output_yaml_path=str(mock_calib_dir / "adjusted_param_range.yaml")
    )

    # 4. 显示结果
    print("=" * 70)
    print("调整结果:")
    print("=" * 70 + "\n")

    if result["success"]:
        print("✅ 参数范围调整成功!\n")

        print("📊 原始参数范围:")
        for param, range_val in result["prev_param_range"].items():
            print(f"  {param}: [{range_val[0]}, {range_val[1]}] (长度: {range_val[1] - range_val[0]})")

        print("\n🎯 最佳参数（第一次率定）:")
        for param, value in result["best_params"].items():
            print(f"  {param}: {value}")

        print("\n🔄 新参数范围（缩小至60%）:")
        for param, range_val in result["new_param_range"].items():
            old_range = result["prev_param_range"][param]
            old_length = old_range[1] - old_range[0]
            new_length = range_val[1] - range_val[0]
            print(f"  {param}: [{range_val[0]:.2f}, {range_val[1]:.2f}] (长度: {new_length:.2f}, 原:{old_length:.2f})")

        print(f"\n💾 输出文件: {result['output_file']}")

        # 验证逻辑
        print("\n" + "=" * 70)
        print("验证逻辑正确性:")
        print("=" * 70 + "\n")

        for param in result["best_params"].keys():
            best_val = result["best_params"][param]
            old_range = result["prev_param_range"][param]
            new_range = result["new_param_range"][param]

            old_min, old_max = old_range
            new_min, new_max = new_range

            # 检查：新范围应该包含最佳参数
            if new_min <= best_val <= new_max:
                print(f"✅ {param}: 新范围 [{new_min:.2f}, {new_max:.2f}] 包含最佳值 {best_val:.2f}")
            else:
                print(f"❌ {param}: 新范围 [{new_min:.2f}, {new_max:.2f}] 不包含最佳值 {best_val:.2f}")

            # 检查：新范围不超出原始范围
            if new_min >= old_min and new_max <= old_max:
                print(f"   ✅ 新范围在原始范围 [{old_min}, {old_max}] 内")
            else:
                print(f"   ⚠️  新范围超出原始范围 [{old_min}, {old_max}]")

        print("\n" + "=" * 70)
        print("测试完成!")
        print("=" * 70)
        return True

    else:
        print(f"❌ 参数范围调整失败: {result.get('error')}")
        return False


def main():
    """主函数。"""
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║          测试智能参数范围调整功能                            ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"\n📝 日志文件: {log_file}\n")

    success = test_param_range_adjustment()

    if success:
        print("\n🎉 测试通过!")
        return 0
    else:
        print("\n❌ 测试失败!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
