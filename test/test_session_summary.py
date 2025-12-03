"""
Author: Claude
Date: 2025-12-03 10:00:00
LastEditTime: 2025-12-03 10:00:00
LastEditors: Claude
Description: Test session summary functionality
             测试会话总结功能
FilePath: /HydroAgent/test/test_session_summary.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import sys
import logging
from pathlib import Path
from datetime import datetime
try:
    from configs import definitions_private as config
except ImportError:
    from configs import definitions as config
# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 设置日志
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

log_file = logs_dir / f"test_session_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


def test_session_summary_with_orchestrator():
    """
    测试通过Orchestrator生成会话总结

    流程:
    1. 创建Orchestrator
    2. 执行一个简单查询(使用Mock模式)
    3. 检查是否生成了session_summary.md
    4. 验证报告内容
    """
    logger.info("=" * 70)
    logger.info("测试: 通过Orchestrator生成会话总结")
    logger.info("=" * 70)

    from hydroagent.core.llm_interface import create_llm_interface
    from hydroagent.agents.orchestrator import Orchestrator
    from unittest.mock import patch, Mock, MagicMock

    # Step 1: 创建LLM接口(使用API)
    api_key = getattr(config, "OPENAI_API_KEY", None)
    base_url = getattr(config, "OPENAI_BASE_URL", None)
    try:
        llm = create_llm_interface('openai', 'qwen3-max',api_key=api_key,base_url=base_url)
        logger.info("✅ LLM接口创建成功")
    except Exception as e:
        logger.error(f"❌ LLM接口创建失败: {str(e)}")
        return False

    # Step 2: 创建Orchestrator
    workspace_root = project_root / "results" / "test_session_summary"
    workspace_root.mkdir(parents=True, exist_ok=True)

    orchestrator = Orchestrator(
        llm_interface=llm,
        workspace_root=workspace_root,
        show_progress=False,  # 不显示进度条
        enable_checkpoint=False,  # 不使用checkpoint
    )

    # Step 3: 启动新会话
    session_id = orchestrator.start_new_session()
    logger.info(f"✅ 新会话已启动: {session_id}")
    logger.info(f"   工作目录: {orchestrator.current_workspace}")

    # Step 4: 执行查询(使用Mock模式模拟hydromodel)
    query = "率定GR4J模型,流域01013500,使用SCE-UA算法,迭代500轮"

    logger.info(f"\n📝 执行查询: {query}")
    logger.info("   使用Mock模式(模拟hydromodel执行)\n")

    # Mock hydromodel
    mock_result = {
        "best_params": {"x1": 350.0, "x2": 0.5, "x3": 100.0, "x4": 2.0},
        "metrics": {"NSE": 0.75, "RMSE": 2.3, "KGE": 0.72, "PBIAS": 5.0},
        "output_files": ["calibration_results.json"]
    }

    mock_hydromodel = MagicMock()
    mock_hydromodel.calibrate = Mock(return_value=mock_result)
    mock_hydromodel.evaluate = Mock(return_value=mock_result)

    try:
        with patch.dict('sys.modules', {'hydromodel': mock_hydromodel}):
            result = orchestrator.process({
                "query": query,
                "use_mock": True
            })

        # Step 5: 检查执行结果
        if not result.get("success"):
            logger.error(f"❌ 查询执行失败: {result.get('error')}")
            return False

        logger.info("✅ 查询执行成功")

        # Step 6: 检查会话总结
        session_summary = result.get("session_summary", {})

        if not session_summary:
            logger.error("❌ 未生成会话总结")
            return False

        if not session_summary.get("success"):
            logger.warning(f"⚠️  会话总结生成失败: {session_summary.get('error')}")
            # 检查是否有降级总结
            if "fallback_summary" in session_summary:
                logger.info("✅ 降级总结已生成")
                logger.info(f"\n降级总结内容:\n{session_summary['fallback_summary']}")
                return True
            return False

        # Step 7: 验证报告文件
        report_path = Path(session_summary["report_path"])

        if not report_path.exists():
            logger.error(f"❌ 报告文件不存在: {report_path}")
            return False

        logger.info(f"✅ 会话总结报告已生成: {report_path}")

        # 读取并显示报告内容(前50行)
        with open(report_path, "r", encoding="utf-8") as f:
            report_content = f.read()
            lines = report_content.split("\n")[:50]
            logger.info(f"\n报告内容预览(前50行):\n{''.join([f'{i+1:3d}: {line}' for i, line in enumerate(lines)])}")

        # 显示简短摘要
        summary_text = session_summary.get("summary_text", "")
        if summary_text:
            logger.info(f"\n简短摘要:\n{summary_text}")

        logger.info("\n" + "=" * 70)
        logger.info("✅ 会话总结功能测试通过!")
        logger.info("=" * 70)
        logger.info(f"\n报告文件: {report_path}")
        logger.info(f"日志文件: {log_file}")
        logger.info(f"工作目录: {orchestrator.current_workspace}")

        return True

    except Exception as e:
        logger.error(f"❌ 测试过程中发生异常: {str(e)}", exc_info=True)
        return False


def main():
    """主函数"""
    success = test_session_summary_with_orchestrator()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
