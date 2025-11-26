"""
Author: Claude
Date: 2025-11-26 00:00:00
LastEditTime: 2025-11-26 00:00:00
LastEditors: Claude
Description: Test PromptPool history functionality
            测试提示词池是否启用了历史记录
FilePath: /HydroAgent/test/test_prompt_pool_history.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import logging
from pathlib import Path
from datetime import datetime
import json
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from hydroagent.core.prompt_pool import PromptPool


def setup_logging():
    """Setup logging for test"""
    logs_dir = Path(__file__).parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)

    log_file = logs_dir / f"test_prompt_pool_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding='utf-8')
        ]
    )
    return logging.getLogger(__name__)


def test_prompt_pool_history():
    """Test PromptPool history saving and loading"""
    logger = setup_logging()
    logger.info("=" * 80)
    logger.info("Testing PromptPool History Functionality")
    logger.info("=" * 80)

    # Create test directory
    test_pool_dir = Path(__file__).parent.parent / "test_prompt_pool"
    test_pool_dir.mkdir(exist_ok=True)

    # Initialize PromptPool
    logger.info(f"\n📁 Initializing PromptPool in: {test_pool_dir}")
    pool = PromptPool(pool_dir=test_pool_dir, max_history=10)

    # Add some test history records
    test_cases = [
        {
            "task_type": "calibration",
            "intent": {
                "task_type": "standard_calibration",
                "model_name": "gr4j",
                "basin_id": "01013500",
                "algorithm": "SCE_UA"
            },
            "config": {
                "data_cfgs": {"basin_ids": ["01013500"]},
                "model_cfgs": {"model_name": "gr4j"},
                "training_cfgs": {"algorithm": "SCE_UA", "algorithm_params": {"rep": 500}}
            },
            "result": {
                "success": True,
                "metrics": {"NSE": 0.75, "RMSE": 1.23}
            },
            "success": True
        },
        {
            "task_type": "calibration",
            "intent": {
                "task_type": "standard_calibration",
                "model_name": "gr4j",
                "basin_id": "01022500",
                "algorithm": "DE"
            },
            "config": {
                "data_cfgs": {"basin_ids": ["01022500"]},
                "model_cfgs": {"model_name": "gr4j"},
                "training_cfgs": {"algorithm": "DE", "algorithm_params": {"max_generations": 100}}
            },
            "result": {
                "success": True,
                "metrics": {"NSE": 0.68, "RMSE": 1.45}
            },
            "success": True
        },
        {
            "task_type": "calibration",
            "intent": {
                "task_type": "standard_calibration",
                "model_name": "xaj",
                "basin_id": "01013500",
                "algorithm": "SCE_UA"
            },
            "config": {
                "data_cfgs": {"basin_ids": ["01013500"]},
                "model_cfgs": {"model_name": "xaj"},
                "training_cfgs": {"algorithm": "SCE_UA"}
            },
            "result": {
                "success": False,
                "error": "Calibration failed"
            },
            "success": False
        }
    ]

    logger.info(f"\n📝 Adding {len(test_cases)} test records to history...")
    for i, case in enumerate(test_cases, 1):
        pool.add_history(**case)
        logger.info(f"  ✅ Record {i} added: {case['intent']['model_name']} + {case['intent']['algorithm']}")

    # Check if history file exists
    history_file = test_pool_dir / "history.json"
    logger.info(f"\n🔍 Checking history file: {history_file}")
    if history_file.exists():
        logger.info(f"  ✅ history.json exists ({history_file.stat().st_size} bytes)")

        # Print content
        with open(history_file, 'r', encoding='utf-8') as f:
            history_data = json.load(f)
        logger.info(f"  ✅ Contains {len(history_data)} records")
    else:
        logger.error("  ❌ history.json NOT found!")
        return False

    # Test similar case retrieval
    logger.info("\n🔎 Testing similar case retrieval...")
    test_intent = {
        "task_type": "standard_calibration",
        "model_name": "gr4j",
        "basin_id": "01013500",
        "algorithm": "SCE_UA"
    }
    similar = pool.get_similar_cases(test_intent, limit=3, only_success=True)
    logger.info(f"  Query intent: {test_intent}")
    logger.info(f"  Found {len(similar)} similar cases:")
    for i, case in enumerate(similar, 1):
        logger.info(f"    {i}. {case['intent']['model_name']} + {case['intent']['algorithm']} "
                   f"(NSE={case['result'].get('metrics', {}).get('NSE', 'N/A')})")

    # Test statistics
    logger.info("\n📊 Testing statistics...")
    stats = pool.get_statistics()
    logger.info(f"  Total records: {stats['total_records']}")
    logger.info(f"  Successful: {stats['successful_records']}")
    logger.info(f"  Success rate: {stats['success_rate']:.1%}")
    logger.info(f"  Task types: {stats['task_type_distribution']}")
    logger.info(f"  Models: {stats['model_usage']}")

    # Test context prompt generation
    logger.info("\n📄 Testing context prompt generation...")
    base_prompt = "请根据以下配置执行模型率定："
    context_prompt = pool.generate_context_prompt(
        base_prompt=base_prompt,
        intent=test_intent
    )
    logger.info(f"  Base prompt length: {len(base_prompt)} chars")
    logger.info(f"  Context prompt length: {len(context_prompt)} chars")
    logger.info(f"  Enhancement: +{len(context_prompt) - len(base_prompt)} chars")
    if "历史成功案例参考" in context_prompt:
        logger.info("  ✅ Historical cases added to prompt")

    logger.info("\n" + "=" * 80)
    logger.info("✅ All tests passed!")
    logger.info("=" * 80)

    return True


if __name__ == "__main__":
    try:
        success = test_prompt_pool_history()
        sys.exit(0 if success else 1)
    except Exception as e:
        logging.error(f"Test failed with error: {e}", exc_info=True)
        sys.exit(1)
