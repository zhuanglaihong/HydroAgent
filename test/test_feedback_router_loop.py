"""
Unit test for FeedbackRouter loop detection mechanism
"""
import sys
from pathlib import Path
import logging

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from hydroagent.core.feedback_router import FeedbackRouter

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_loop_detection():
    """Test that loop detection triggers after 2 identical config failures."""

    logger.info("=" * 80)
    logger.info("Testing FeedbackRouter Loop Detection")
    logger.info("=" * 80)

    router = FeedbackRouter()

    # Simulate a config that fails validation repeatedly
    test_config = {
        "model_cfgs": {"model_name": "gr4j"},
        "data_cfgs": {"basin_ids": ["01013500"]},
        "training_cfgs": {"algorithm_name": "SCE_UA"}
    }

    # Context (simulating Orchestrator's execution_context)
    context = {
        "config_retry_count": 0,
        "query": "对GR4J模型率定流域01013500"
    }

    # Test 1: First failure - should abort (no loop detected yet)
    logger.info("\n--- Test 1: First config failure ---")
    feedback1 = {
        "success": False,
        "error": "配置中obj_func设置为'RMSE'，但用户查询明确要求以NSE作为优化目标",
        "config": test_config
    }

    decision1 = router._route_interpreter_feedback(feedback1, context)
    logger.info(f"Action: {decision1.get('action')}")

    assert decision1.get('action') == 'abort', "First failure should abort (no loop yet)"
    logger.info("✅ Test 1 passed: First failure correctly returns 'abort'")

    # Test 2: Second failure with SAME config - should detect loop and skip review
    logger.info("\n--- Test 2: Second config failure (same config) ---")
    context["config_retry_count"] = 1
    feedback2 = {
        "success": False,
        "error": "配置中obj_func设置为'RMSE'，但用户查询明确要求以NSE作为优化目标",
        "config": test_config  # Same config
    }

    decision2 = router._route_interpreter_feedback(feedback2, context)
    logger.info(f"Action: {decision2.get('action')}")

    assert decision2.get('action') == 'skip_review_and_execute', \
        "Second identical failure should trigger skip_review_and_execute"

    assert decision2.get('parameters', {}).get('skip_reason') == 'validation_loop_detected', \
        "Should indicate loop was detected"

    logger.info("✅ Test 2 passed: Loop detected, action is 'skip_review_and_execute'")

    # Test 3: Different config - should not detect loop
    logger.info("\n--- Test 3: Failure with different config ---")
    router.config_failure_history.clear()  # Reset
    context["config_retry_count"] = 0

    different_config = {
        "model_cfgs": {"model_name": "xaj"},  # Different model
        "data_cfgs": {"basin_ids": ["01013500"]},
        "training_cfgs": {"algorithm_name": "SCE_UA"}
    }

    feedback3 = {
        "success": False,
        "error": "Some error",
        "config": different_config
    }

    decision3 = router._route_interpreter_feedback(feedback3, context)
    logger.info(f"Action: {decision3.get('action')}")

    assert decision3.get('action') == 'abort', "Different config should not trigger loop"
    logger.info("✅ Test 3 passed: Different config does not trigger loop")

    # Test 4: Check hash computation is consistent
    logger.info("\n--- Test 4: Hash computation consistency ---")
    hash1 = router._compute_config_hash(test_config)
    hash2 = router._compute_config_hash(test_config)
    assert hash1 == hash2, "Same config should produce same hash"
    logger.info(f"Config hash: {hash1}")
    logger.info("✅ Test 4 passed: Hash computation is consistent")

    logger.info("\n" + "=" * 80)
    logger.info("All tests passed! ✅")
    logger.info("=" * 80)


if __name__ == "__main__":
    test_loop_detection()
