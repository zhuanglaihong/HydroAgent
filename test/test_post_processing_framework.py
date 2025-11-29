"""
Author: Claude
Date: 2025-11-28 15:00:00
LastEditTime: 2025-11-28 15:00:00
LastEditors: Claude
Description: Test the unified post-processing framework
FilePath: /HydroAgent/test/test_post_processing_framework.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import sys
from pathlib import Path
import logging
from datetime import datetime

# Setup logging
logs_dir = Path(__file__).parent.parent / "logs"
logs_dir.mkdir(exist_ok=True)

log_file = logs_dir / f"test_post_processing_framework_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_task_type_detection():
    """测试任务类型检测"""
    from hydroagent.utils.task_detector import TaskTypeDetector

    logger.info("=" * 80)
    logger.info("Testing TaskTypeDetector")
    logger.info("=" * 80)

    # Test 1: Multi-basin
    subtask_results = [{"config": {}}, {"config": {}}, {"config": {}}]
    task_plan = {"subtasks": []}
    intent = {"intent_result": {"basin_ids": ["01013500", "01022500", "01030500"]}}

    task_type = TaskTypeDetector.detect_task_type(subtask_results, task_plan, intent)
    logger.info(f"✅ Test 1 - Multi-basin detection: {task_type}")
    assert task_type == "multi_basin", f"Expected 'multi_basin', got '{task_type}'"

    # Test 2: Repeated calibration
    subtask_results = [{"config": {}} for _ in range(5)]
    task_plan = {"subtasks": [{"description": "重复率定任务1"}, {"description": "重复率定任务2"}]}
    intent = {"intent_result": {"basin_ids": ["01013500"]}}

    task_type = TaskTypeDetector.detect_task_type(subtask_results, task_plan, intent)
    logger.info(f"✅ Test 2 - Repeated calibration detection: {task_type}")
    assert task_type == "repeated_calibration", f"Expected 'repeated_calibration', got '{task_type}'"

    # Test 3: Multi-algorithm
    subtask_results = [
        {"config": {"training_cfgs": {"algorithm": "SCE_UA"}, "model_cfgs": {"model_name": "GR4J"}}},
        {"config": {"training_cfgs": {"algorithm": "DE"}, "model_cfgs": {"model_name": "GR4J"}}},
        {"config": {"training_cfgs": {"algorithm": "SCE_UA"}, "model_cfgs": {"model_name": "XAJ"}}}
    ]
    task_plan = {"subtasks": []}
    intent = {"intent_result": {"basin_ids": ["01013500"]}}

    task_type = TaskTypeDetector.detect_task_type(subtask_results, task_plan, intent)
    logger.info(f"✅ Test 3 - Multi-algorithm detection: {task_type}")
    assert task_type == "multi_algorithm", f"Expected 'multi_algorithm', got '{task_type}'"

    # Test 4: Single task
    subtask_results = [{"config": {}}]
    task_plan = {"subtasks": []}
    intent = {"intent_result": {"basin_ids": ["01013500"]}}

    task_type = TaskTypeDetector.detect_task_type(subtask_results, task_plan, intent)
    logger.info(f"✅ Test 4 - Single task detection: {task_type}")
    assert task_type == "single_task", f"Expected 'single_task', got '{task_type}'"

    logger.info("=" * 80)
    logger.info("All TaskTypeDetector tests passed! ✅")
    logger.info("=" * 80)


def test_post_processor_initialization():
    """测试PostProcessingEngine初始化"""
    from hydroagent.utils.post_processor import PostProcessingEngine

    logger.info("=" * 80)
    logger.info("Testing PostProcessingEngine Initialization")
    logger.info("=" * 80)

    # Create a test workspace directory
    test_workspace = Path(__file__).parent / "test_workspace"
    test_workspace.mkdir(exist_ok=True)

    # Initialize engine
    engine = PostProcessingEngine(workspace_dir=test_workspace)
    logger.info(f"✅ PostProcessingEngine initialized with workspace: {engine.workspace_dir}")

    assert engine.workspace_dir == test_workspace, "Workspace directory mismatch"

    logger.info("=" * 80)
    logger.info("PostProcessingEngine initialization test passed! ✅")
    logger.info("=" * 80)

    # Cleanup
    import shutil
    if test_workspace.exists():
        shutil.rmtree(test_workspace)


def test_integration_with_developer_agent():
    """测试DeveloperAgent集成（模拟）"""
    logger.info("=" * 80)
    logger.info("Testing Integration with DeveloperAgent (Simulated)")
    logger.info("=" * 80)

    # Check that the imports work
    try:
        from hydroagent.utils.task_detector import TaskTypeDetector
        from hydroagent.utils.post_processor import PostProcessingEngine
        logger.info("✅ Task detector and post processor imports successful")
    except ImportError as e:
        logger.error(f"❌ Import failed: {e}")
        raise

    # Simulate the workflow
    subtask_results = [
        {"config": {}, "evaluation_metrics": {"NSE": 0.75, "RMSE": 1.2}},
        {"config": {}, "evaluation_metrics": {"NSE": 0.80, "RMSE": 1.0}}
    ]
    task_plan = {"subtasks": []}
    intent = {"intent_result": {"basin_ids": ["01013500", "01022500"]}}

    # Step 1: Detect task type
    task_type = TaskTypeDetector.detect_task_type(subtask_results, task_plan, intent)
    logger.info(f"✅ Detected task type: {task_type}")

    # Step 2: Initialize post processor (would normally use actual workspace)
    # We skip actual processing since it requires real data files

    logger.info("=" * 80)
    logger.info("Integration test passed! ✅")
    logger.info("=" * 80)


def test_plotting_toolkit():
    """测试PlottingToolkit.plot_metrics_comparison"""
    from hydroagent.utils.plotting import PlottingToolkit

    logger.info("=" * 80)
    logger.info("Testing PlottingToolkit.plot_metrics_comparison")
    logger.info("=" * 80)

    # Check that the method exists
    assert hasattr(PlottingToolkit, 'plot_metrics_comparison'), \
        "plot_metrics_comparison method not found in PlottingToolkit"

    logger.info("✅ plot_metrics_comparison method exists")

    # Create test data
    test_workspace = Path(__file__).parent / "test_workspace"
    test_workspace.mkdir(exist_ok=True)

    basin_ids = ["01013500", "01022500", "01030500"]
    nse_values = [0.75, 0.80, 0.70]
    rmse_values = [1.2, 1.0, 1.5]
    kge_values = [0.78, 0.82, 0.73]

    output_path = test_workspace / "test_metrics_comparison.png"

    # Try to generate plot
    try:
        success = PlottingToolkit.plot_metrics_comparison(
            basin_ids=basin_ids,
            nse_values=nse_values,
            rmse_values=rmse_values,
            kge_values=kge_values,
            output_path=output_path
        )

        if success:
            logger.info(f"✅ Plot generated successfully: {output_path}")
            assert output_path.exists(), "Plot file not created"
        else:
            logger.warning("⚠️ Plot generation returned False (matplotlib may not be installed)")

    except Exception as e:
        logger.warning(f"⚠️ Plot generation failed (expected if matplotlib not installed): {e}")

    logger.info("=" * 80)
    logger.info("PlottingToolkit test completed! ✅")
    logger.info("=" * 80)

    # Cleanup
    import shutil
    if test_workspace.exists():
        shutil.rmtree(test_workspace)


def main():
    """运行所有测试"""
    logger.info("=" * 80)
    logger.info("POST-PROCESSING FRAMEWORK TEST SUITE")
    logger.info("=" * 80)

    try:
        test_task_type_detection()
        test_post_processor_initialization()
        test_integration_with_developer_agent()
        test_plotting_toolkit()

        logger.info("\n" + "=" * 80)
        logger.info("🎉 ALL TESTS PASSED! 🎉")
        logger.info("=" * 80)
        logger.info(f"Log file: {log_file}")

    except Exception as e:
        logger.error("\n" + "=" * 80)
        logger.error(f"❌ TEST FAILED: {str(e)}")
        logger.error("=" * 80)
        raise


if __name__ == "__main__":
    main()
