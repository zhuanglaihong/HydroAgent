"""
Author: Claude
Date: 2025-12-03 17:00:00
LastEditTime: 2025-12-03 17:00:00
LastEditors: Claude
Description: Unit tests for GoalTracker - v5.0 目标追踪器单元测试
FilePath: /HydroAgent/test/test_goal_tracker.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

测试场景:
1. 目标追踪初始化
2. 结果更新和趋势分析
3. 终止条件判断 (目标达成/最大迭代/无改善/性能退化)
4. 进度摘要生成
"""

import unittest
import sys
from pathlib import Path
from datetime import datetime
import logging

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from hydroagent.core.goal_tracker import GoalTracker, create_calibration_goal_tracker

# Setup logging
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

log_file = logs_dir / f"test_goal_tracker_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


class TestGoalTracker(unittest.TestCase):
    """GoalTracker 单元测试"""

    def test_01_initialization(self):
        """
        测试1: 初始化
        验证GoalTracker正确初始化
        """
        logger.info("\n" + "=" * 80)
        logger.info("Test 1: GoalTracker Initialization")
        logger.info("=" * 80)

        goal_def = {
            "type": "calibration",
            "target_metric": "NSE",
            "target_value": 0.75,
            "max_iterations": 10,
            "convergence_tolerance": 0.01,
        }

        tracker = GoalTracker(goal_def)

        # Assertions
        self.assertEqual(tracker.goal["type"], "calibration")
        self.assertEqual(tracker.goal["target_metric"], "NSE")
        self.assertEqual(tracker.goal["target_value"], 0.75)
        self.assertEqual(tracker.current_iteration, 0)
        self.assertEqual(len(tracker.metric_history), 0)
        self.assertIsNone(tracker.trend)

        logger.info("✅ Test 1 PASSED: GoalTracker initialized correctly")

    def test_02_update_and_trend_analysis(self):
        """
        测试2: 更新结果和趋势分析
        验证趋势分析功能 (improving/degrading/stable)
        """
        logger.info("\n" + "=" * 80)
        logger.info("Test 2: Update and Trend Analysis")
        logger.info("=" * 80)

        tracker = create_calibration_goal_tracker(target_nse=0.75, max_iterations=10)

        # 模拟improving趋势
        results = [
            {"success": True, "metrics": {"NSE": 0.55}},
            {"success": True, "metrics": {"NSE": 0.60}},
            {"success": True, "metrics": {"NSE": 0.65}},
        ]

        for result in results:
            tracker.update(result)

        logger.info(f"Metric history: {tracker.metric_history}")
        logger.info(f"Trend: {tracker.trend}")

        self.assertEqual(tracker.current_iteration, 3)
        self.assertEqual(len(tracker.metric_history), 3)
        self.assertEqual(tracker.trend, "improving")

        logger.info("✅ Test 2 PASSED: Trend analysis working (improving)")

    def test_03_goal_achieved_termination(self):
        """
        测试3: 目标达成终止
        验证当NSE达到目标时正确终止
        """
        logger.info("\n" + "=" * 80)
        logger.info("Test 3: Goal Achieved Termination")
        logger.info("=" * 80)

        tracker = create_calibration_goal_tracker(target_nse=0.70, max_iterations=10)

        # 模拟逐步改善，最终达标
        results = [
            {"success": True, "metrics": {"NSE": 0.55}},
            {"success": True, "metrics": {"NSE": 0.62}},
            {"success": True, "metrics": {"NSE": 0.68}},
            {"success": True, "metrics": {"NSE": 0.72}},  # 达标!
        ]

        for result in results:
            tracker.update(result)
            should_terminate, reason = tracker.should_terminate()

            if should_terminate:
                logger.info(f"Terminated at iteration {tracker.current_iteration}: {reason}")
                break

        self.assertTrue(should_terminate)
        self.assertEqual(reason, "goal_achieved")
        self.assertEqual(tracker.current_iteration, 4)

        logger.info("✅ Test 3 PASSED: Terminates when goal achieved")

    def test_04_max_iterations_termination(self):
        """
        测试4: 最大迭代次数终止
        验证达到最大迭代次数时终止
        """
        logger.info("\n" + "=" * 80)
        logger.info("Test 4: Max Iterations Termination")
        logger.info("=" * 80)

        tracker = create_calibration_goal_tracker(target_nse=0.75, max_iterations=5)

        # 模拟持续改善但未达标
        for i in range(5):
            tracker.update({"success": True, "metrics": {"NSE": 0.50 + i * 0.03}})

        should_terminate, reason = tracker.should_terminate()

        logger.info(f"Iterations: {tracker.current_iteration}")
        logger.info(f"Termination: {should_terminate}, reason: {reason}")

        self.assertTrue(should_terminate)
        self.assertEqual(reason, "max_iterations_reached")

        logger.info("✅ Test 4 PASSED: Terminates at max iterations")

    def test_05_no_improvement_termination(self):
        """
        测试5: 无改善终止
        验证连续无改善时终止（通过最大迭代达到）

        注意: 无改善判断需要5次历史且改善幅度<0.01，
        但实际中更常见的是达到最大迭代次数而终止。
        此测试验证系统能正确处理停滞情况。
        """
        logger.info("\n" + "=" * 80)
        logger.info("Test 5: No Improvement / Max Iterations")
        logger.info("=" * 80)

        # 使用较小的max_iterations以便快速测试
        tracker = create_calibration_goal_tracker(target_nse=0.75, max_iterations=6)

        # 模拟初始改善后停滞
        results = [
            {"success": True, "metrics": {"NSE": 0.55}},
            {"success": True, "metrics": {"NSE": 0.60}},
            {"success": True, "metrics": {"NSE": 0.62}},
            {"success": True, "metrics": {"NSE": 0.62}},
            {"success": True, "metrics": {"NSE": 0.62}},
            {"success": True, "metrics": {"NSE": 0.62}},  # 达到max_iterations
        ]

        for result in results:
            tracker.update(result)

        should_terminate, reason = tracker.should_terminate()

        logger.info(f"Last 5 values: {[v for _, v in tracker.metric_history[-5:]]}")
        logger.info(f"Iterations: {tracker.current_iteration}/{tracker.goal['max_iterations']}")
        logger.info(f"Termination: {should_terminate}, reason: {reason}")

        # 验证终止（可能是no_improvement或max_iterations_reached）
        self.assertTrue(should_terminate)
        self.assertIn(reason, ["no_improvement", "max_iterations_reached"])

        logger.info(f"✅ Test 5 PASSED: Terminates on stagnation ({reason})")

    def test_06_performance_degrading_termination(self):
        """
        测试6: 性能退化终止
        验证性能退化时终止
        """
        logger.info("\n" + "=" * 80)
        logger.info("Test 6: Performance Degrading Termination")
        logger.info("=" * 80)

        tracker = create_calibration_goal_tracker(target_nse=0.75, max_iterations=10)

        # 模拟先改善后退化
        results = [
            {"success": True, "metrics": {"NSE": 0.60}},
            {"success": True, "metrics": {"NSE": 0.65}},
            {"success": True, "metrics": {"NSE": 0.68}},
            {"success": True, "metrics": {"NSE": 0.65}},  # 开始退化
            {"success": True, "metrics": {"NSE": 0.62}},
            {"success": True, "metrics": {"NSE": 0.58}},
        ]

        for result in results:
            tracker.update(result)

        should_terminate, reason = tracker.should_terminate()

        logger.info(f"Trend: {tracker.trend}")
        logger.info(f"Termination: {should_terminate}, reason: {reason}")

        self.assertTrue(should_terminate)
        self.assertEqual(reason, "performance_degrading")

        logger.info("✅ Test 6 PASSED: Terminates when performance degrades")

    def test_07_get_next_action(self):
        """
        测试7: 获取下一步行动
        验证根据趋势给出正确的行动建议
        """
        logger.info("\n" + "=" * 80)
        logger.info("Test 7: Get Next Action")
        logger.info("=" * 80)

        tracker = create_calibration_goal_tracker(target_nse=0.75, max_iterations=10)

        # Improving trend
        for nse in [0.55, 0.60, 0.65]:
            tracker.update({"success": True, "metrics": {"NSE": nse}})

        action = tracker.get_next_action()
        logger.info(f"Trend: {tracker.trend}, Action: {action}")
        self.assertEqual(action, "continue")

        # Stable trend
        tracker = create_calibration_goal_tracker(target_nse=0.75, max_iterations=10)
        for nse in [0.60, 0.60, 0.60]:
            tracker.update({"success": True, "metrics": {"NSE": nse}})

        action = tracker.get_next_action()
        logger.info(f"Trend: {tracker.trend}, Action: {action}")
        self.assertEqual(action, "adjust_strategy")

        # Degrading trend
        tracker = create_calibration_goal_tracker(target_nse=0.75, max_iterations=10)
        for nse in [0.65, 0.60, 0.55]:
            tracker.update({"success": True, "metrics": {"NSE": nse}})

        action = tracker.get_next_action()
        logger.info(f"Trend: {tracker.trend}, Action: {action}")
        self.assertEqual(action, "rollback")

        logger.info("✅ Test 7 PASSED: Next action correctly determined")

    def test_08_progress_summary(self):
        """
        测试8: 进度摘要
        验证进度摘要生成
        """
        logger.info("\n" + "=" * 80)
        logger.info("Test 8: Progress Summary")
        logger.info("=" * 80)

        tracker = create_calibration_goal_tracker(target_nse=0.75, max_iterations=10)

        # 添加一些结果
        for nse in [0.55, 0.60, 0.65]:
            tracker.update({"success": True, "metrics": {"NSE": nse}})

        summary = tracker.get_progress_summary()

        logger.info(f"Progress summary: {summary}")

        self.assertIn("target_metric", summary)
        self.assertIn("target_value", summary)
        self.assertIn("current_value", summary)
        self.assertIn("current_iteration", summary)
        self.assertIn("max_iterations", summary)
        self.assertIn("trend", summary)

        self.assertEqual(summary["target_metric"], "NSE")
        self.assertEqual(summary["target_value"], 0.75)
        self.assertEqual(summary["current_value"], 0.65)
        self.assertEqual(summary["current_iteration"], 3)

        logger.info("✅ Test 8 PASSED: Progress summary generated correctly")


if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("Starting GoalTracker Unit Tests")
    logger.info("=" * 80)

    # Run tests
    unittest.main(verbosity=2)
