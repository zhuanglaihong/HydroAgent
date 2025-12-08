"""
Integration test for basin ID validation with config_validator
测试config_validator的流域ID验证集成
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
from datetime import datetime

# Setup logging
logs_dir = Path(__file__).parent.parent / "logs"
logs_dir.mkdir(exist_ok=True)

log_file = logs_dir / f"test_basin_validation_integration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


def test_config_validator():
    """Test ConfigValidator with new basin validation."""
    logger.info("=== Testing ConfigValidator with New Basin Validation ===")

    from hydroagent.utils.config_validator import ConfigValidator

    validator = ConfigValidator()

    # Test 1: Valid basin IDs (from the failed multi-basin experiment)
    logger.info("\n--- Test 1: Valid Basin IDs (Multi-basin experiment IDs) ---")
    test_configs = [
        {
            "description": "Single valid basin",
            "config": {
                "data_cfgs": {
                    "basin_ids": ["01013500"],
                    "train_period": ["1985-10-01", "1995-09-30"],
                    "test_period": ["2005-10-01", "2014-09-30"],
                },
                "model_cfgs": {"model_name": "xaj"},
                "training_cfgs": {"algorithm_name": "SCE_UA"},
            }
        },
        {
            "description": "Multi-basin with IDs > 14500000 (previously failed)",
            "config": {
                "data_cfgs": {
                    "basin_ids": ["11532500", "12025000", "14301000", "14306500", "14325000"],
                    "train_period": ["1985-10-01", "1995-09-30"],
                    "test_period": ["2005-10-01", "2014-09-30"],
                },
                "model_cfgs": {"model_name": "xaj"},
                "training_cfgs": {"algorithm_name": "SCE_UA"},
            }
        }
    ]

    for test in test_configs:
        logger.info(f"\n  Testing: {test['description']}")
        is_valid, errors = validator.validate_config(test['config'])

        if is_valid:
            logger.info(f"    ✓ Configuration VALID")
        else:
            logger.error(f"    ✗ Configuration INVALID")
            for error in errors:
                logger.error(f"      - {error}")

    # Test 2: Invalid basin IDs
    logger.info("\n--- Test 2: Invalid Basin IDs ---")
    invalid_configs = [
        {
            "description": "Non-existent basin ID 99999999",
            "config": {
                "data_cfgs": {
                    "basin_ids": ["99999999"],
                    "train_period": ["1985-10-01", "1995-09-30"],
                    "test_period": ["2005-10-01", "2014-09-30"],
                },
                "model_cfgs": {"model_name": "xaj"},
                "training_cfgs": {"algorithm_name": "SCE_UA"},
            }
        },
        {
            "description": "Invalid format basin ID",
            "config": {
                "data_cfgs": {
                    "basin_ids": ["123"],
                    "train_period": ["1985-10-01", "1995-09-30"],
                    "test_period": ["2005-10-01", "2014-09-30"],
                },
                "model_cfgs": {"model_name": "xaj"},
                "training_cfgs": {"algorithm_name": "SCE_UA"},
            }
        }
    ]

    for test in invalid_configs:
        logger.info(f"\n  Testing: {test['description']}")
        is_valid, errors = validator.validate_config(test['config'])

        if not is_valid:
            logger.info(f"    ✓ Correctly rejected")
            for error in errors:
                logger.info(f"      - {error}")
        else:
            logger.error(f"    ✗ Should have been rejected but was accepted")


def test_llm_config_reviewer():
    """Test LLMConfigReviewer with basin validation (if API available)."""
    logger.info("\n=== Testing LLMConfigReviewer (Optional - requires API) ===")

    try:
        from hydroagent.core.llm_interface import LLMInterface
        from hydroagent.utils.llm_config_reviewer import LLMConfigReviewer

        # Try to create LLM interface
        try:
            llm = LLMInterface(backend="api")
            reviewer = LLMConfigReviewer(llm)

            # Test with a valid config
            logger.info("\n  Testing valid basin ID with LLM reviewer...")
            config = {
                "data_cfgs": {
                    "basin_ids": ["11532500"],
                    "train_period": ["1985-10-01", "1995-09-30"],
                    "test_period": ["2005-10-01", "2014-09-30"],
                },
                "model_cfgs": {"model_name": "xaj"},
                "training_cfgs": {
                    "algorithm_name": "SCE_UA",
                    "algorithm_params": {"rep": 500, "ngs": 200}
                },
            }

            user_query = "用XAJ模型率定流域11532500"
            is_valid, error_msg = reviewer.review_config(config, user_query)

            if is_valid:
                logger.info("    ✓ LLM reviewer: Configuration VALID")
            else:
                logger.warning(f"    ✗ LLM reviewer: Configuration INVALID - {error_msg}")

        except Exception as e:
            logger.warning(f"  Skipping LLM reviewer test (API not available): {str(e)}")

    except ImportError:
        logger.warning("  Skipping LLM reviewer test (module not available)")


def main():
    logger.info("=" * 80)
    logger.info("Basin ID Validation Integration Test")
    logger.info("=" * 80)

    # Test ConfigValidator
    test_config_validator()

    # Test LLMConfigReviewer (optional, requires API)
    test_llm_config_reviewer()

    logger.info("\n" + "=" * 80)
    logger.info("Test Complete")
    logger.info("=" * 80)
    logger.info(f"\nLog saved to: {log_file}")


if __name__ == "__main__":
    main()
