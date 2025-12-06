"""
Author: Claude
Date: 2025-12-06 21:30:00
LastEditTime: 2025-12-06 21:30:00
LastEditors: Claude
Description: 测试FDC曲线生成功能
FilePath: /HydroAgent/test/test_fdc_generation.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
from datetime import datetime

# Setup logging
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

log_file = logs_dir / f"test_fdc_generation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


def test_fdc_generation():
    """
    测试FDC曲线生成功能。

    测试查询："率定GR4J模型，流域14325000，完成后画FDC曲线"

    预期：
    1. 系统识别为extended_analysis
    2. task_3应该生成FDC曲线绘制代码
    3. 在session目录中应该能找到FDC相关的png文件
    """
    logger.info("=" * 80)
    logger.info("测试: FDC曲线生成功能")
    logger.info("=" * 80)

    query = "率定GR4J模型，流域14325000，完成后画FDC曲线"

    logger.info(f"查询: {query}")
    logger.info("预期: 系统应该生成FDC曲线的Python代码并执行")
    logger.info("")

    try:
        from hydroagent.core.llm_interface import create_llm_interface
        from hydroagent.agents.orchestrator import Orchestrator
        from configs.definitions import OPENAI_API_KEY, OPENAI_BASE_URL
        from configs.config import DEFAULT_MODEL, DEFAULT_CODE_MODEL

        # 创建LLM接口（包括code_llm）
        llm = create_llm_interface(
            backend='openai',
            model_name=DEFAULT_MODEL,
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL
        )

        code_llm = create_llm_interface(
            backend='openai',
            model_name=DEFAULT_CODE_MODEL,  # qwen-coder-turbo
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL
        )

        logger.info(f"✓ 通用LLM: {DEFAULT_MODEL}")
        logger.info(f"✓ 代码LLM: {DEFAULT_CODE_MODEL}")

        workspace_root = project_root / "results" / "test_fdc_generation"

        # 创建Orchestrator（传入code_llm）
        orchestrator = Orchestrator(
            llm_interface=llm,
            code_llm_interface=code_llm,  # ⭐ 关键：传入代码生成LLM
            workspace_root=workspace_root,
            enable_faiss=False,
            show_progress=True,
            enable_code_gen=True
        )

        # 执行查询
        logger.info("\n开始执行查询...")
        result = orchestrator.process({
            "query": query,
            "use_mock": True,  # 使用mock加快测试
            "use_v5": True
        })

        # 检查结果
        logger.info("\n" + "=" * 80)
        logger.info("结果分析:")
        logger.info("=" * 80)

        success = result.get("success", False)
        logger.info(f"✓ 执行状态: {'成功' if success else '失败'}")

        # 检查是否生成了FDC相关文件
        session_workspace = orchestrator.current_workspace
        logger.info(f"\n📁 Session目录: {session_workspace}")

        # 查找所有生成的文件
        import os
        fdc_files = []
        code_files = []

        for root, dirs, files in os.walk(session_workspace):
            for file in files:
                file_lower = file.lower()
                if 'fdc' in file_lower and file_lower.endswith('.png'):
                    fdc_files.append(os.path.join(root, file))
                elif file_lower.endswith('.py'):
                    code_files.append(os.path.join(root, file))

        logger.info(f"\n📊 生成的FDC图表: {len(fdc_files)} 个")
        for fdc_file in fdc_files:
            logger.info(f"   ✓ {Path(fdc_file).relative_to(session_workspace)}")

        logger.info(f"\n💻 生成的Python代码: {len(code_files)} 个")
        for code_file in code_files:
            logger.info(f"   ✓ {Path(code_file).relative_to(session_workspace)}")

        # 验证
        if not fdc_files:
            logger.warning("⚠️  没有找到FDC曲线图！")
            logger.info("\n建议检查:")
            logger.info("  1. task_3是否正确执行了custom_analysis")
            logger.info("  2. DeveloperAgent是否成功生成了FDC绘图代码")
            logger.info("  3. 生成的代码是否成功执行")
            return False
        else:
            logger.info("\n✅ FDC曲线生成成功!")
            return True

    except Exception as e:
        logger.error(f"❌ 测试失败: {str(e)}", exc_info=True)
        return False


if __name__ == "__main__":
    success = test_fdc_generation()
    sys.exit(0 if success else 1)
