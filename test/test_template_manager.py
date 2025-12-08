"""
Author: Claude
Date: 2025-12-07 19:55:00
LastEditTime: 2025-12-07 19:55:00
LastEditors: Claude
Description: 测试模板化代码生成系统
FilePath: /HydroAgent/test/test_template_manager.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)


def test_template_manager():
    """测试TemplateManager基本功能"""
    from hydroagent.utils.template_manager import TemplateManager, extract_placeholders

    logger.info("=" * 80)
    logger.info("测试: TemplateManager基本功能")
    logger.info("=" * 80)

    # 1. 初始化
    tm = TemplateManager()
    logger.info(f"✓ TemplateManager initialized: {tm.templates_dir}")

    # 2. 检查可用模板
    available = tm.list_available_templates()
    logger.info(f"✓ Available templates: {available}")

    if len(available) == 0:
        logger.error("❌ No templates found!")
        return False

    # 3. 测试 runoff_coefficient 模板
    if tm.has_template('runoff_coefficient'):
        logger.info("✓ runoff_coefficient template exists")

        # 获取模板
        template = tm.get_template('runoff_coefficient')
        if template:
            logger.info(f"✓ Template loaded: {len(template)} characters")

            # 检查占位符
            if '{{NC_FILE_PATH}}' in template:
                logger.info("✓ Template contains {{NC_FILE_PATH}} placeholder")
            if '{{BASIN_ID}}' in template:
                logger.info("✓ Template contains {{BASIN_ID}} placeholder")
            if '{{OUTPUT_DIR}}' in template:
                logger.info("✓ Template contains {{OUTPUT_DIR}} placeholder")

            # 填充占位符
            placeholders = extract_placeholders(
                nc_file_path=r"D:\data\test.nc",
                basin_id="01539000",
                output_dir=r"D:\results"
            )

            filled_code = tm.fill_template(template, placeholders)

            # 检查是否正确替换
            if 'D:\\data\\test.nc' in filled_code:
                logger.info("✓ NC_FILE_PATH correctly replaced")
            if '01539000' in filled_code:
                logger.info("✓ BASIN_ID correctly replaced")
            if 'D:\\results' in filled_code:
                logger.info("✓ OUTPUT_DIR correctly replaced")

            # 检查是否还有未填充的占位符
            import re
            remaining = re.findall(r'\{\{(\w+)\}\}', filled_code)
            if remaining:
                logger.warning(f"⚠ Unfilled placeholders: {remaining}")
            else:
                logger.info("✓ All placeholders filled")

            logger.info("✅ runoff_coefficient template test passed!")
            return True
        else:
            logger.error("❌ Failed to load template")
            return False
    else:
        logger.error("❌ runoff_coefficient template not found")
        return False


def test_code_generation():
    """测试完整的代码生成流程"""
    from hydroagent.utils.template_manager import TemplateManager

    logger.info("\n" + "=" * 80)
    logger.info("测试: 完整代码生成")
    logger.info("=" * 80)

    tm = TemplateManager()

    # 测试参数
    placeholders = {
        'NC_FILE_PATH': r'D:\project\Agent\HydroAgent\results\test\calibration_results.nc',
        'BASIN_ID': '01539000',
        'OUTPUT_DIR': r'D:\project\Agent\HydroAgent\results\test\analysis'
    }

    # 生成代码
    code = tm.generate_code('runoff_coefficient', placeholders)

    if code:
        logger.info(f"✓ Code generated successfully ({len(code)} characters)")

        # 保存到临时文件进行语法检查
        test_file = project_root / "generated_code" / "test_template_output.py"
        test_file.parent.mkdir(exist_ok=True)
        test_file.write_text(code, encoding='utf-8')

        logger.info(f"✓ Code saved to: {test_file}")

        # 语法检查
        import py_compile
        try:
            py_compile.compile(str(test_file), doraise=True)
            logger.info("✓ Syntax check passed")
            logger.info("✅ Code generation test passed!")
            return True
        except py_compile.PyCompileError as e:
            logger.error(f"❌ Syntax error: {e}")
            return False
    else:
        logger.error("❌ Code generation failed")
        return False


if __name__ == "__main__":
    success1 = test_template_manager()
    success2 = test_code_generation()

    logger.info("\n" + "=" * 80)
    logger.info("测试总结:")
    logger.info("=" * 80)
    logger.info(f"TemplateManager: {'✅ PASS' if success1 else '❌ FAIL'}")
    logger.info(f"Code Generation: {'✅ PASS' if success2 else '❌ FAIL'}")
    logger.info("=" * 80)

    sys.exit(0 if (success1 and success2) else 1)
