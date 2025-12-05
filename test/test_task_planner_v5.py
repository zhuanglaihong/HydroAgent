"""
Author: Claude
Date: 2025-12-03 22:30:00
LastEditTime: 2025-12-03 22:30:00
LastEditors: Claude
Description: Unit tests for TaskPlanner v5.0 LLM-based dynamic planning
             TaskPlanner v5.0 LLM动态规划的单元测试
FilePath: /HydroAgent/test/test_task_planner_v5.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

Test Coverage:
1. LLM-based task decomposition
2. FAISS historical case retrieval
3. Fallback to rule-based methods
4. LLM response parsing
"""

import unittest
from pathlib import Path
import logging
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

# Setup logging
logs_dir = Path(__file__).parent.parent / "logs"
logs_dir.mkdir(exist_ok=True)

log_file = logs_dir / f"test_task_planner_v5_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
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
from hydroagent.agents.task_planner import TaskPlanner, SubTask
from hydroagent.core.llm_interface import LLMInterface


class TestTaskPlannerV5LLM(unittest.TestCase):
    """Test TaskPlanner v5.0 LLM-based planning."""

    def setUp(self):
        """Initialize TaskPlanner with mock LLM for each test."""
        self.mock_llm = Mock(spec=LLMInterface)
        self.mock_llm.model_name = "mock-model"
        self.mock_llm.chat = Mock()  # Add chat method to mock

        # Create TaskPlanner with LLM planning enabled
        self.planner = TaskPlanner(
            llm_interface=self.mock_llm,
            workspace_dir=None,
            use_llm_planning=True
        )

    def test_initialization_llm_enabled(self):
        """Test TaskPlanner v5.0 initialization with LLM planning."""
        self.assertTrue(self.planner.use_llm_planning)
        self.assertIsNotNone(self.planner.prompt_pool)
        self.assertEqual(len(self.planner.decomposition_methods), 8)

    def test_initialization_llm_disabled(self):
        """Test TaskPlanner with LLM planning disabled (fallback mode)."""
        planner_no_llm = TaskPlanner(
            llm_interface=self.mock_llm,
            workspace_dir=None,
            use_llm_planning=False
        )

        self.assertFalse(planner_no_llm.use_llm_planning)

    @patch.object(TaskPlanner, '_retrieve_historical_cases')
    def test_llm_decomposition_success(self, mock_retrieve):
        """Test successful LLM-based task decomposition."""
        # Mock historical case retrieval to return empty (avoid FAISS issues)
        mock_retrieve.return_value = []

        # Mock LLM response with valid JSON
        mock_llm_response = """```json
[
  {
    "task_id": "task_1",
    "task_type": "calibration",
    "description": "Calibrate GR4J model for basin 01013500",
    "parameters": {
      "model_name": "gr4j",
      "basin_id": "01013500",
      "algorithm": "SCE_UA"
    },
    "dependencies": []
  },
  {
    "task_id": "task_2",
    "task_type": "evaluation",
    "description": "Evaluate model performance on test period",
    "parameters": {
      "model_name": "gr4j",
      "basin_id": "01013500"
    },
    "dependencies": ["task_1"]
  }
]
```"""

        self.mock_llm.chat.return_value = mock_llm_response

        # Create intent
        intent_result = {
            "task_type": "standard_calibration",
            "model_name": "gr4j",
            "basin_id": "01013500",
            "algorithm": "SCE_UA"
        }

        # Call process
        result = self.planner.process({"intent_result": intent_result})

        # Verify success
        self.assertTrue(result["success"])
        self.assertIn("task_plan", result)

        task_plan = result["task_plan"]
        self.assertEqual(task_plan["total_subtasks"], 2)

        # Check subtasks
        subtasks = task_plan["subtasks"]
        self.assertEqual(len(subtasks), 2)
        self.assertEqual(subtasks[0]["task_id"], "task_1")
        self.assertEqual(subtasks[0]["task_type"], "calibration")
        self.assertEqual(subtasks[1]["dependencies"], ["task_1"])

    def test_llm_decomposition_fallback_on_error(self):
        """Test fallback to rule-based when LLM fails."""
        # Mock LLM to raise exception
        self.mock_llm.chat.side_effect = RuntimeError("LLM API error")

        intent_result = {
            "task_type": "standard_calibration",
            "model_name": "gr4j",
            "basin_id": "01013500"
        }

        # Call process - should fallback to rule-based
        result = self.planner.process({"intent_result": intent_result})

        # Should still succeed with fallback
        self.assertTrue(result["success"])
        self.assertIn("task_plan", result)

    def test_llm_decomposition_invalid_json(self):
        """Test handling of invalid JSON from LLM."""
        # Mock LLM response with invalid JSON
        self.mock_llm.chat.return_value = "This is not valid JSON"

        intent_result = {
            "task_type": "standard_calibration",
            "model_name": "gr4j",
            "basin_id": "01013500"
        }

        # Call process - should fallback to rule-based
        result = self.planner.process({"intent_result": intent_result})

        # Should fallback and succeed
        self.assertTrue(result["success"])

    def test_parse_llm_response_with_markdown(self):
        """Test parsing LLM response wrapped in markdown code block."""
        llm_response = """```json
[
  {"task_id": "task_1", "task_type": "calibration", "description": "Test", "parameters": {}}
]
```"""

        intent_result = {"task_type": "calibration"}

        subtasks = self.planner._parse_llm_decomposition(llm_response, intent_result)

        self.assertEqual(len(subtasks), 1)
        self.assertEqual(subtasks[0].task_id, "task_1")

    def test_parse_llm_response_bare_json(self):
        """Test parsing bare JSON without markdown."""
        llm_response = '[{"task_id": "task_1", "task_type": "calibration", "description": "Test", "parameters": {}}]'

        intent_result = {"task_type": "calibration"}

        subtasks = self.planner._parse_llm_decomposition(llm_response, intent_result)

        self.assertEqual(len(subtasks), 1)

    def test_parse_llm_response_missing_fields(self):
        """Test handling of subtasks with missing required fields."""
        llm_response = """```json
[
  {"task_id": "task_1", "task_type": "calibration"},
  {"task_id": "task_2", "task_type": "evaluation", "description": "Valid task", "parameters": {}}
]
```"""

        intent_result = {"task_type": "calibration"}

        subtasks = self.planner._parse_llm_decomposition(llm_response, intent_result)

        # Only valid subtask should be parsed
        self.assertEqual(len(subtasks), 1)
        self.assertEqual(subtasks[0].task_id, "task_2")

    def test_intent_to_query_text(self):
        """Test conversion of intent to FAISS query text."""
        intent_result = {
            "task_type": "iterative_optimization",
            "model_name": "gr4j",
            "algorithm": "SCE_UA"
        }

        query_text = self.planner._intent_to_query_text(intent_result)

        self.assertIn("iterative_optimization", query_text)
        self.assertIn("gr4j", query_text)
        self.assertIn("SCE_UA", query_text)

    def test_build_decomposition_prompt(self):
        """Test building of LLM decomposition prompt."""
        intent_result = {
            "task_type": "standard_calibration",
            "model_name": "gr4j"
        }

        historical_cases = [
            {"task_id": "old_task_1", "success": True}
        ]

        prompt = self.planner._build_decomposition_prompt(intent_result, historical_cases)

        # Check prompt contains required parts
        self.assertIn("当前任务", prompt)
        self.assertIn("gr4j", prompt)
        self.assertIn("历史参考案例", prompt)
        self.assertIn("任务要求", prompt)

    def test_build_decomposition_prompt_no_history(self):
        """Test prompt building without historical cases."""
        intent_result = {
            "task_type": "standard_calibration",
            "model_name": "gr4j"
        }

        prompt = self.planner._build_decomposition_prompt(intent_result, [])

        # Should not contain historical cases section
        self.assertNotIn("历史参考案例", prompt)
        self.assertIn("当前任务", prompt)

    def test_retrieve_historical_cases_no_faiss(self):
        """Test historical case retrieval when FAISS not available."""
        # Mock prompt_pool to indicate FAISS not available
        self.planner.prompt_pool.faiss_available = False

        intent_result = {"task_type": "calibration"}

        cases = self.planner._retrieve_historical_cases(intent_result)

        # Should return empty list
        self.assertEqual(cases, [])

    @patch.object(TaskPlanner, '_retrieve_historical_cases')
    def test_llm_planning_with_history(self, mock_retrieve):
        """Test LLM planning with historical cases."""
        # Mock historical case retrieval
        mock_retrieve.return_value = [
            {
                "task_id": "historical_task",
                "task_type": "calibration",
                "success": True
            }
        ]

        # Mock LLM response
        self.mock_llm.chat.return_value = '```json\n[{"task_id": "task_1", "task_type": "calibration", "description": "Test", "parameters": {}}]\n```'

        intent_result = {
            "task_type": "standard_calibration",
            "model_name": "gr4j"
        }

        result = self.planner.process({"intent_result": intent_result})

        # Verify retrieve was called
        mock_retrieve.assert_called_once()

        # Verify success
        self.assertTrue(result["success"])

    def test_llm_system_prompt(self):
        """Test LLM planning system prompt."""
        system_prompt = self.planner._get_llm_planning_system_prompt()

        # Check key components
        self.assertIn("任务规划专家", system_prompt)
        self.assertIn("calibration", system_prompt)
        self.assertIn("evaluation", system_prompt)
        self.assertIn("JSON", system_prompt)


class TestTaskPlannerV5Fallback(unittest.TestCase):
    """Test TaskPlanner v5.0 fallback to rule-based methods."""

    def setUp(self):
        """Initialize TaskPlanner for fallback testing."""
        self.mock_llm = Mock(spec=LLMInterface)
        self.mock_llm.model_name = "mock-model"
        self.mock_llm.chat = Mock()  # Add chat method to mock

        # Create planner with LLM disabled
        self.planner = TaskPlanner(
            llm_interface=self.mock_llm,
            workspace_dir=None,
            use_llm_planning=False
        )

    def test_fallback_standard_calibration(self):
        """Test fallback to rule-based standard calibration."""
        intent_result = {
            "task_type": "standard_calibration",
            "model_name": "gr4j",
            "basin_id": "01013500"
        }

        result = self.planner.process({"intent_result": intent_result})

        # Should succeed with rule-based method
        self.assertTrue(result["success"])
        self.assertIn("task_plan", result)

        # LLM should not be called
        self.mock_llm.chat.assert_not_called()

    def test_fallback_unknown_task_type(self):
        """Test fallback with unknown task type."""
        intent_result = {
            "task_type": "unknown_task_type",
            "model_name": "gr4j"
        }

        result = self.planner.process({"intent_result": intent_result})

        # Should fallback to standard calibration
        self.assertTrue(result["success"])


if __name__ == "__main__":
    logger.info("=" * 70)
    logger.info("Starting TaskPlanner v5.0 Unit Tests")
    logger.info(f"Log file: {log_file}")
    logger.info("=" * 70)

    unittest.main(verbosity=2)
