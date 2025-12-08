# -*- coding: utf-8 -*-
"""
Author: Claude
Date: 2025-12-07 02:50:00
LastEditTime: 2025-12-07 02:50:00
LastEditors: Claude
Description: Test code generation fixes (field name mismatch + Unicode encoding)
FilePath: /HydroAgent/test/test_code_gen_fix.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import logging
from datetime import datetime
from pathlib import Path

# Setup logging
logs_dir = Path(__file__).parent.parent / "logs"
logs_dir.mkdir(exist_ok=True)

log_file = logs_dir / f"test_code_gen_fix_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


def test_field_name_fix():
    """测试字段名修复"""
    from hydroagent.utils.prompt_manager import _build_fdc_prompt

    # 模拟 previous_results（使用 calibration_dir 字段）
    params = {
        "basin_id": "01013500",
        "previous_results": [
            {
                "success": True,
                "calibration_dir": r"D:\project\Agent\HydroAgent\results\test_session\task_1",
                "metrics": {"NSE": 0.75}
            }
        ]
    }

    # 创建临时测试目录和nc文件
    test_dir = Path(params["previous_results"][0]["calibration_dir"])
    test_dir.mkdir(parents=True, exist_ok=True)
    test_nc_file = test_dir / "gr4j_evaluation_results.nc"
    test_nc_file.touch()  # 创建空文件

    logger.info("=" * 80)
    logger.info("测试1: 字段名修复（calibration_dir）")
    logger.info("=" * 80)

    # 生成提示词
    prompt = _build_fdc_prompt(params["basin_id"], params)

    # 验证提示词包含正确的路径
    logger.info(f"生成的提示词长度: {len(prompt)} 字符")

    expected_dir = str(test_dir)
    expected_file = "gr4j_evaluation_results.nc"

    if expected_dir in prompt:
        logger.info(f"✓ 提示词包含正确的目录路径: {expected_dir}")
    else:
        logger.error(f"✗ 提示词不包含目录路径: {expected_dir}")
        return False

    if expected_file in prompt:
        logger.info(f"✓ 提示词包含正确的文件名: {expected_file}")
    else:
        logger.error(f"✗ 提示词不包含文件名: {expected_file}")
        return False

    # 清理测试文件
    test_nc_file.unlink()
    test_dir.rmdir()

    return True


def test_unicode_encoding_requirement():
    """测试Unicode编码要求"""
    from hydroagent.utils.prompt_manager import build_code_generation_prompt

    logger.info("\n" + "=" * 80)
    logger.info("测试2: Unicode编码要求")
    logger.info("=" * 80)

    params = {"basin_id": "01013500", "model_name": "gr4j"}

    for analysis_type in ["FDC", "runoff_coefficient", "water_balance", "seasonal_analysis"]:
        prompt = build_code_generation_prompt(analysis_type, params)

        if "Windows编码兼容性" in prompt or "避免使用emoji" in prompt:
            logger.info(f"✓ {analysis_type} 提示词包含编码要求")
        else:
            logger.error(f"✗ {analysis_type} 提示词缺少编码要求")
            return False

    return True


def main():
    """主测试函数"""
    logger.info("开始测试代码生成修复...")
    logger.info(f"日志文件: {log_file}")

    # 测试1: 字段名修复
    test1_passed = test_field_name_fix()

    # 测试2: Unicode编码要求
    test2_passed = test_unicode_encoding_requirement()

    # 总结
    logger.info("\n" + "=" * 80)
    logger.info("测试结果总结")
    logger.info("=" * 80)
    logger.info(f"测试1 (字段名修复): {'通过' if test1_passed else '失败'}")
    logger.info(f"测试2 (Unicode编码要求): {'通过' if test2_passed else '失败'}")

    if test1_passed and test2_passed:
        logger.info("\n✅ 所有测试通过!")
        return 0
    else:
        logger.error("\n❌ 部分测试失败")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
