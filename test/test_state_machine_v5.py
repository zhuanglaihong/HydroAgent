"""
Author: Claude
Date: 2025-12-03 18:30:00
LastEditTime: 2025-12-03 18:30:00
LastEditors: Claude
Description: Unit tests for v5.0 State Machine components
             v5.0 状态机组件的单元测试
FilePath: /HydroAgent/test/test_state_machine_v5.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

Test Coverage:
1. StateMachine: State transitions, context updates, history tracking
2. GoalTracker: Trend analysis, termination conditions
3. FeedbackRouter: Error classification, routing decisions
"""

import unittest
from pathlib import Path
import logging
from datetime import datetime

# Setup logging
logs_dir = Path(__file__).parent.parent / "logs"
logs_dir.mkdir(exist_ok=True)

log_file = logs_dir / f"test_state_machine_v5_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

# Import modules to test
from hydroagent.core.state_machine import (
    StateMachine,
    OrchestratorState,
    StateTransition,
    build_default_transitions,
)
from hydroagent.core.goal_tracker import GoalTracker, create_calibration_goal_tracker
from hydroagent.core.feedback_router import FeedbackRouter


class TestStateMachine(unittest.TestCase):
    """Test StateMachine core functionality."""

    def setUp(self):
        """Initialize state machine for each test."""
        self.state_machine = StateMachine(max_transitions=50)

    def test_initialization(self):
        """Test state machine initialization."""
        self.assertEqual(self.state_machine.current_state, OrchestratorState.INIT)
        self.assertEqual(self.state_machine.transition_count, 0)
        self.assertEqual(len(self.state_machine.state_history), 0)

    def test_simple_transition(self):
        """Test a simple state transition."""
        # Add transition: INIT → WAITING_USER_INPUT
        transition = StateTransition(
            from_state=OrchestratorState.INIT,
            to_state=OrchestratorState.WAITING_USER_INPUT,
            condition=lambda ctx: True,
            description="Test transition"
        )
        self.state_machine.add_transition(transition)

        # Execute transition
        next_state = self.state_machine.transition()

        self.assertEqual(next_state, OrchestratorState.WAITING_USER_INPUT)
        self.assertEqual(self.state_machine.transition_count, 1)
        self.assertEqual(len(self.state_machine.state_history), 1)

    def test_conditional_transition(self):
        """Test conditional state transition."""
        # Add two transitions from same state
        self.state_machine.add_transition(StateTransition(
            from_state=OrchestratorState.INIT,
            to_state=OrchestratorState.WAITING_USER_INPUT,
            condition=lambda ctx: ctx.get("has_query", False),
            description="Condition True"
        ))

        self.state_machine.add_transition(StateTransition(
            from_state=OrchestratorState.INIT,
            to_state=OrchestratorState.FAILED_UNRECOVERABLE,
            condition=lambda ctx: not ctx.get("has_query", False),
            description="Condition False"
        ))

        # Test condition=False
        next_state = self.state_machine.transition({"has_query": False})
        self.assertEqual(next_state, OrchestratorState.FAILED_UNRECOVERABLE)

        # Reset and test condition=True
        self.state_machine.reset()
        next_state = self.state_machine.transition({"has_query": True})
        self.assertEqual(next_state, OrchestratorState.WAITING_USER_INPUT)

    def test_context_updates(self):
        """Test context updates during transitions."""
        self.state_machine.update_context({"key1": "value1"})
        self.assertEqual(self.state_machine.get_context("key1"), "value1")

        self.state_machine.update_context({"key2": "value2"})
        self.assertEqual(self.state_machine.get_context("key2"), "value2")
        self.assertEqual(self.state_machine.get_context("key1"), "value1")  # Still exists

    def test_default_transitions(self):
        """Test default transition rules."""
        transitions = build_default_transitions()
        self.assertGreater(len(transitions), 10)  # Should have many transitions

        self.state_machine.add_transitions(transitions)

        # Simulate progression: INIT → WAITING_USER_INPUT → ANALYZING_INTENT
        self.state_machine.transition()  # INIT → WAITING_USER_INPUT
        self.assertEqual(self.state_machine.current_state, OrchestratorState.WAITING_USER_INPUT)

        self.state_machine.transition({"query": "test query"})  # → ANALYZING_INTENT
        self.assertEqual(self.state_machine.current_state, OrchestratorState.ANALYZING_INTENT)

    def test_max_transitions_limit(self):
        """Test max transitions limit protection."""
        small_machine = StateMachine(max_transitions=5)

        # Create a loop transition
        small_machine.add_transition(StateTransition(
            from_state=OrchestratorState.INIT,
            to_state=OrchestratorState.INIT,
            condition=lambda ctx: True
        ))

        # Execute 6 times (should raise error on 6th)
        with self.assertRaises(RuntimeError):
            for _ in range(6):
                small_machine.transition()

    def test_is_terminal_state(self):
        """Test terminal state detection."""
        self.assertFalse(self.state_machine.is_terminal_state())

        # Manually set to terminal state
        self.state_machine.current_state = OrchestratorState.COMPLETED_SUCCESS
        self.assertTrue(self.state_machine.is_terminal_state())

        self.state_machine.current_state = OrchestratorState.FAILED_UNRECOVERABLE
        self.assertTrue(self.state_machine.is_terminal_state())

    def test_history_tracking(self):
        """Test state history tracking."""
        self.state_machine.add_transitions(build_default_transitions())

        # Execute few transitions
        self.state_machine.transition()
        self.state_machine.transition({"query": "test"})

        self.assertEqual(len(self.state_machine.state_history), 2)

        # Check history content
        first_record = self.state_machine.state_history[0]
        self.assertIn("from_state", first_record)
        self.assertIn("to_state", first_record)
        self.assertIn("timestamp", first_record)

    def test_reset(self):
        """Test state machine reset."""
        self.state_machine.update_context({"key": "value"})
        self.state_machine.transition_count = 5
        self.state_machine.state_history.append({"test": "data"})

        self.state_machine.reset()

        self.assertEqual(self.state_machine.current_state, OrchestratorState.INIT)
        self.assertEqual(self.state_machine.transition_count, 0)
        self.assertEqual(len(self.state_machine.state_history), 0)
        self.assertEqual(len(self.state_machine.context), 0)


class TestGoalTracker(unittest.TestCase):
    """Test GoalTracker functionality."""

    def setUp(self):
        """Initialize goal tracker for each test."""
        self.tracker = create_calibration_goal_tracker(
            target_nse=0.75,
            max_iterations=10,
            convergence_tolerance=0.01
        )

    def test_initialization(self):
        """Test goal tracker initialization."""
        self.assertEqual(self.tracker.current_iteration, 0)
        self.assertEqual(len(self.tracker.metric_history), 0)
        self.assertIsNone(self.tracker.trend)

    def test_update_metrics(self):
        """Test updating metrics."""
        result = {
            "success": True,
            "metrics": {"NSE": 0.65, "RMSE": 2.5}
        }

        self.tracker.update(result)

        self.assertEqual(self.tracker.current_iteration, 1)
        self.assertEqual(len(self.tracker.metric_history), 1)
        self.assertEqual(self.tracker.metric_history[0], (1, 0.65))

    def test_trend_analysis(self):
        """Test trend analysis."""
        # Simulate improving trend
        for nse in [0.55, 0.60, 0.65]:
            self.tracker.update({"success": True, "metrics": {"NSE": nse}})

        self.assertEqual(self.tracker.trend, "improving")

        # Simulate degrading trend
        self.tracker.reset()
        for nse in [0.65, 0.60, 0.55]:
            self.tracker.update({"success": True, "metrics": {"NSE": nse}})

        self.assertEqual(self.tracker.trend, "degrading")

        # Simulate stable trend
        self.tracker.reset()
        for nse in [0.60, 0.601, 0.602]:
            self.tracker.update({"success": True, "metrics": {"NSE": nse}})

        self.assertEqual(self.tracker.trend, "stable")

    def test_termination_goal_achieved(self):
        """Test termination condition: goal achieved."""
        self.tracker.update({"success": True, "metrics": {"NSE": 0.76}})

        should_terminate, reason = self.tracker.should_terminate()

        self.assertTrue(should_terminate)
        self.assertEqual(reason, "goal_achieved")

    def test_termination_max_iterations(self):
        """Test termination condition: max iterations."""
        for i in range(11):  # Exceed max_iterations=10
            self.tracker.update({"success": True, "metrics": {"NSE": 0.60}})

        should_terminate, reason = self.tracker.should_terminate()

        self.assertTrue(should_terminate)
        self.assertEqual(reason, "max_iterations_reached")

    def test_termination_no_improvement(self):
        """Test termination condition: no improvement."""
        # Simulate 5 iterations with no improvement
        for _ in range(5):
            self.tracker.update({"success": True, "metrics": {"NSE": 0.600}})

        should_terminate, reason = self.tracker.should_terminate()

        self.assertTrue(should_terminate)
        self.assertEqual(reason, "no_improvement")

    def test_get_next_action(self):
        """Test next action recommendation."""
        # Improving trend → continue
        for nse in [0.55, 0.60, 0.65]:
            self.tracker.update({"success": True, "metrics": {"NSE": nse}})

        self.assertEqual(self.tracker.get_next_action(), "continue")

        # Stable trend → adjust_strategy
        self.tracker.reset()
        for nse in [0.60, 0.601, 0.602]:
            self.tracker.update({"success": True, "metrics": {"NSE": nse}})

        self.assertEqual(self.tracker.get_next_action(), "adjust_strategy")

        # Degrading trend → rollback
        self.tracker.reset()
        for nse in [0.65, 0.60, 0.55]:
            self.tracker.update({"success": True, "metrics": {"NSE": nse}})

        self.assertEqual(self.tracker.get_next_action(), "rollback")

    def test_progress_summary(self):
        """Test progress summary generation."""
        self.tracker.update({"success": True, "metrics": {"NSE": 0.65}})
        self.tracker.update({"success": True, "metrics": {"NSE": 0.70}})

        summary = self.tracker.get_progress_summary()

        self.assertEqual(summary["current_iteration"], 2)
        self.assertEqual(summary["current_value"], 0.70)
        self.assertEqual(summary["best_value"], 0.70)
        self.assertEqual(summary["target_value"], 0.75)

    def test_improvement_rate(self):
        """Test improvement rate calculation."""
        for nse in [0.55, 0.60, 0.65]:
            self.tracker.update({"success": True, "metrics": {"NSE": nse}})

        improvement_rate = self.tracker.get_improvement_rate()

        self.assertIsNotNone(improvement_rate)
        self.assertGreater(improvement_rate, 0)  # Should be positive


class TestFeedbackRouter(unittest.TestCase):
    """Test FeedbackRouter functionality."""

    def setUp(self):
        """Initialize feedback router for each test."""
        self.router = FeedbackRouter()

    def test_error_classification(self):
        """Test error classification."""
        # Configuration error
        error_type = self.router._classify_error("KeyError: 'training_cfgs'")
        self.assertEqual(error_type, "configuration_error")

        # Data not found
        error_type = self.router._classify_error("FileNotFoundError: basin data not found")
        self.assertEqual(error_type, "data_not_found")

        # Timeout
        error_type = self.router._classify_error("TimeoutError: execution took too long")
        self.assertEqual(error_type, "timeout")

        # Dependency error
        error_type = self.router._classify_error("ImportError: No module named hydromodel")
        self.assertEqual(error_type, "dependency_error")

        # Numerical error
        error_type = self.router._classify_error("RuntimeError: NaN detected in results")
        self.assertEqual(error_type, "numerical_error")

        # Unknown
        error_type = self.router._classify_error("Something completely unexpected")
        self.assertEqual(error_type, "unknown")

    def test_runner_feedback_success(self):
        """Test RunnerAgent feedback routing (success case)."""
        feedback = {"success": True, "metrics": {"NSE": 0.75}}
        context = {}

        routing = self.router.route_feedback("RunnerAgent", feedback, context)

        self.assertEqual(routing["target_agent"], "DeveloperAgent")
        self.assertEqual(routing["action"], "analyze_results")

    def test_runner_feedback_config_error(self):
        """Test RunnerAgent feedback routing (config error)."""
        feedback = {"success": False, "error": "KeyError: 'data_cfgs'"}
        context = {"last_config": {}}

        routing = self.router.route_feedback("RunnerAgent", feedback, context)

        self.assertEqual(routing["target_agent"], "InterpreterAgent")
        self.assertEqual(routing["action"], "regenerate_config")
        self.assertTrue(routing["retryable"])

    def test_runner_feedback_timeout(self):
        """Test RunnerAgent feedback routing (timeout)."""
        feedback = {"success": False, "error": "TimeoutError: exceeded 3600s"}
        context = {"rep": 500}

        routing = self.router.route_feedback("RunnerAgent", feedback, context)

        self.assertEqual(routing["target_agent"], "TaskPlanner")
        self.assertEqual(routing["action"], "reduce_complexity")
        self.assertTrue(routing["retryable"])

    def test_runner_feedback_dependency_error(self):
        """Test RunnerAgent feedback routing (dependency error - not retryable)."""
        feedback = {"success": False, "error": "ImportError: hydromodel not found"}
        context = {}

        routing = self.router.route_feedback("RunnerAgent", feedback, context)

        self.assertEqual(routing["target_agent"], None)
        self.assertEqual(routing["action"], "abort")
        self.assertFalse(routing["retryable"])

    def test_developer_feedback_goal_achieved(self):
        """Test DeveloperAgent feedback routing (goal achieved)."""
        feedback = {
            "success": True,
            "analysis": {
                "metrics": {"NSE": 0.76},
                "recommendations": []
            }
        }
        context = {"nse_target": 0.75}

        routing = self.router.route_feedback("DeveloperAgent", feedback, context)

        self.assertEqual(routing["target_agent"], None)
        self.assertEqual(routing["action"], "complete_success")

    def test_developer_feedback_below_threshold(self):
        """Test DeveloperAgent feedback routing (below threshold)."""
        feedback = {
            "success": True,
            "analysis": {
                "metrics": {"NSE": 0.65},
                "recommendations": ["建议调整参数范围"]
            }
        }
        context = {"nse_target": 0.75, "iteration_count": 2, "max_iterations": 10}

        routing = self.router.route_feedback("DeveloperAgent", feedback, context)

        self.assertEqual(routing["target_agent"], "TaskPlanner")
        self.assertEqual(routing["action"], "trigger_iterative_optimization")
        self.assertTrue(routing["retryable"])

    def test_interpreter_feedback_success(self):
        """Test InterpreterAgent feedback routing (success)."""
        feedback = {"success": True, "config": {"data_cfgs": {}}}
        context = {}

        routing = self.router.route_feedback("InterpreterAgent", feedback, context)

        self.assertEqual(routing["target_agent"], "RunnerAgent")
        self.assertEqual(routing["action"], "execute_task")

    def test_interpreter_feedback_failure(self):
        """Test InterpreterAgent feedback routing (failure)."""
        feedback = {"success": False, "error": "Config generation failed"}
        context = {"config_retry_count": 0}

        routing = self.router.route_feedback("InterpreterAgent", feedback, context)

        self.assertEqual(routing["target_agent"], "TaskPlanner")
        self.assertEqual(routing["action"], "adjust_task_plan")
        self.assertTrue(routing["retryable"])

    def test_batch_error_classification(self):
        """Test batch error classification."""
        errors = [
            "KeyError: 'data_cfgs'",
            "FileNotFoundError: basin not found",
            "TimeoutError: execution exceeded",
            "KeyError: 'model_cfgs'"
        ]

        stats = self.router.classify_error_batch(errors)

        self.assertEqual(stats["configuration_error"], 2)
        self.assertEqual(stats["data_not_found"], 1)
        self.assertEqual(stats["timeout"], 1)


if __name__ == "__main__":
    logger.info("=" * 70)
    logger.info("Starting v5.0 State Machine Unit Tests")
    logger.info(f"Log file: {log_file}")
    logger.info("=" * 70)

    unittest.main(verbosity=2)
