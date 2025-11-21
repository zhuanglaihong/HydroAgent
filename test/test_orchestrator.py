"""
Author: Claude & zhuanglaihong
Date: 2025-11-21 15:30:00
LastEditTime: 2025-11-21 15:30:00
LastEditors: Claude
Description: Unit tests for Orchestrator and HydroAgent system
             Orchestrator和HydroAgent系统的单元测试
FilePath: \HydroAgent\test\test_orchestrator.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import sys
import logging
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import copy

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set console encoding (Windows compatible)
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Ensure logs directory exists
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

# Setup logging
log_file = logs_dir / f"test_orchestrator_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

# ============================================================================
# Test Data - Mock agent responses
# ============================================================================

MOCK_INTENT_RESULT = {
    "success": True,
    "intent_result": {
        "intent": "calibration",
        "model_name": "gr4j",
        "basin_id": "01013500",
        "algorithm": "SCE_UA",
        "confidence": 0.95
    }
}

MOCK_CONFIG_RESULT = {
    "success": True,
    "config": {
        "model": "gr4j",
        "basin_id": "01013500",
        "algorithm": "SCE_UA"
    },
    "config_summary": "GR4J model configuration for basin 01013500",
    "intent_result": MOCK_INTENT_RESULT["intent_result"]
}

MOCK_RUNNER_SUCCESS_RESULT = {
    "success": True,
    "mode": "calibrate",
    "result": {
        "metrics": {"NSE": 0.85, "RMSE": 2.5},
        "best_params": {"x1": 350.0, "x2": 0.5, "x3": 100.0, "x4": 2.0}
    },
    "execution_log": {"stdout": "Calibration completed", "stderr": ""}
}

MOCK_DEVELOPER_RESULT = {
    "success": True,
    "mode": "calibrate",
    "analysis": {
        "quality": "优秀 (Excellent)",
        "metrics": {"NSE": 0.85, "RMSE": 2.5},
        "recommendations": []
    }
}


def print_test_header(test_num: int, description: str):
    """Print test header."""
    print("\n" + "="*70)
    print(f"Test Case {test_num}: {description}")
    print("="*70)


def test_orchestrator_initialization():
    """测试1: Orchestrator初始化"""
    print_test_header(1, "Orchestrator 初始化测试")

    from hydroagent.agents.orchestrator import Orchestrator
    from hydroagent.core.llm_interface import create_llm_interface

    llm = create_llm_interface('ollama', 'qwen3:8b')
    workspace_root = project_root / "results" / "test_orchestrator"

    orchestrator = Orchestrator(
        llm_interface=llm,
        workspace_root=workspace_root,
        show_progress=False
    )

    # Verify initialization
    assert orchestrator.name == "Orchestrator", "Orchestrator name mismatch"
    assert orchestrator.workspace_root == workspace_root, "Workspace root mismatch"
    assert orchestrator.current_session_id is None, "Session should be None initially"

    print("✅ Orchestrator 初始化测试通过")
    return orchestrator


def test_session_management():
    """测试2: 会话管理"""
    print_test_header(2, "会话管理测试")

    from hydroagent.agents.orchestrator import Orchestrator
    from hydroagent.core.llm_interface import create_llm_interface

    llm = create_llm_interface('ollama', 'qwen3:8b')
    workspace_root = project_root / "results" / "test_orchestrator"

    orchestrator = Orchestrator(llm_interface=llm, workspace_root=workspace_root)

    # Start session
    session_id = orchestrator.start_new_session()

    # Verify session
    assert session_id is not None, "Session ID should not be None"
    assert orchestrator.current_session_id == session_id, "Session ID mismatch"
    assert orchestrator.current_workspace is not None, "Workspace should be created"
    assert orchestrator.current_workspace.exists(), "Workspace should exist"

    # Verify sub-agents initialized
    assert orchestrator.intent_agent is not None, "IntentAgent not initialized"
    assert orchestrator.config_agent is not None, "ConfigAgent not initialized"
    assert orchestrator.runner_agent is not None, "RunnerAgent not initialized"
    assert orchestrator.developer_agent is not None, "DeveloperAgent not initialized"

    print("✅ 会话管理测试通过")
    print(f"   Session ID: {session_id}")
    print(f"   Workspace: {orchestrator.current_workspace}")
    return orchestrator


def test_orchestrator_mock_pipeline():
    """测试3: Orchestrator完整管道 (Mock)"""
    print_test_header(3, "完整管道测试 (Mock所有Agent)")

    from hydroagent.agents.orchestrator import Orchestrator
    from hydroagent.core.llm_interface import create_llm_interface

    llm = create_llm_interface('ollama', 'qwen3:8b')
    workspace_root = project_root / "results" / "test_orchestrator"

    orchestrator = Orchestrator(llm_interface=llm, workspace_root=workspace_root)
    session_id = orchestrator.start_new_session()

    # Mock all sub-agents
    orchestrator.intent_agent.process = Mock(return_value=MOCK_INTENT_RESULT)
    orchestrator.config_agent.process = Mock(return_value=MOCK_CONFIG_RESULT)
    orchestrator.runner_agent.process = Mock(return_value=MOCK_RUNNER_SUCCESS_RESULT)
    orchestrator.developer_agent.process = Mock(return_value=MOCK_DEVELOPER_RESULT)

    # Run pipeline
    result = orchestrator.process({"query": "率定GR4J模型，流域01013500"})

    # Verify result
    assert result["success"], f"Pipeline should succeed: {result.get('error')}"
    assert result["session_id"] == session_id, "Session ID mismatch"
    assert "intent" in result, "Intent result missing"
    assert "config" in result, "Config result missing"
    assert "execution" in result, "Execution result missing"
    assert "analysis" in result, "Analysis result missing"
    assert "summary" in result, "Summary missing"

    print("✅ 完整管道测试通过 (Mock)")
    print(f"   Summary:\n{result['summary']}")
    return result


def test_hydro_agent_api():
    """测试4: HydroAgent API"""
    print_test_header(4, "HydroAgent API测试")

    from hydroagent import HydroAgent

    # Create HydroAgent
    agent = HydroAgent(backend='ollama', model='qwen3:8b', show_progress=False)

    # Verify initialization
    assert agent.llm is not None, "LLM not initialized"
    assert agent.orchestrator is not None, "Orchestrator not initialized"

    # Mock all sub-agents
    agent.start_session()
    agent.orchestrator.intent_agent.process = Mock(return_value=MOCK_INTENT_RESULT)
    agent.orchestrator.config_agent.process = Mock(return_value=MOCK_CONFIG_RESULT)
    agent.orchestrator.runner_agent.process = Mock(return_value=MOCK_RUNNER_SUCCESS_RESULT)
    agent.orchestrator.developer_agent.process = Mock(return_value=MOCK_DEVELOPER_RESULT)

    # Run query
    result = agent.run("率定GR4J模型，流域01013500")

    # Verify result
    assert result["success"], f"Query should succeed: {result.get('error')}"
    assert "summary" in result, "Summary missing"

    print("✅ HydroAgent API测试通过")
    print(f"   Workspace: {agent.get_workspace()}")
    return result


def test_conversation_history():
    """测试5: 对话历史记录"""
    print_test_header(5, "对话历史记录测试")

    from hydroagent import HydroAgent

    agent = HydroAgent(backend='ollama', model='qwen3:8b', show_progress=False)
    agent.start_session()

    # Mock agents
    agent.orchestrator.intent_agent.process = Mock(return_value=MOCK_INTENT_RESULT)
    agent.orchestrator.config_agent.process = Mock(return_value=MOCK_CONFIG_RESULT)
    agent.orchestrator.runner_agent.process = Mock(return_value=MOCK_RUNNER_SUCCESS_RESULT)
    agent.orchestrator.developer_agent.process = Mock(return_value=MOCK_DEVELOPER_RESULT)

    # Run multiple queries
    query1 = "率定GR4J模型"
    query2 = "评估模型性能"

    agent.run(query1)
    agent.run(query2)

    # Get history
    history = agent.get_history()

    # Verify history
    assert len(history) >= 4, "History should have at least 4 messages (2 queries + 2 responses)"

    # Check queries in history
    user_messages = [msg for msg in history if msg["role"] == "user"]
    assert len(user_messages) >= 2, "Should have at least 2 user messages"
    assert query1 in user_messages[0]["content"], "First query not in history"
    assert query2 in user_messages[1]["content"], "Second query not in history"

    print("✅ 对话历史记录测试通过")
    print(f"   Messages: {len(history)}")
    return history


def test_error_handling():
    """测试6: 错误处理"""
    print_test_header(6, "错误处理测试")

    from hydroagent import HydroAgent

    agent = HydroAgent(backend='ollama', model='qwen3:8b', show_progress=False)
    agent.start_session()

    # Mock IntentAgent to fail
    agent.orchestrator.intent_agent.process = Mock(return_value={
        "success": False,
        "error": "Intent parsing failed"
    })

    # Run query (should fail)
    result = agent.run("invalid query")

    # Verify error handling
    assert not result["success"], "Query should fail"
    assert "error" in result, "Error message missing"

    print("✅ 错误处理测试通过")
    print(f"   Error: {result['error']}")
    return result


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*70)
    print("Orchestrator & HydroAgent 单元测试套件")
    print("="*70)
    print(f"日志文件: {log_file}")
    print()

    results = []

    try:
        # Test 1: Initialization
        test_orchestrator_initialization()
        results.append(("Orchestrator初始化", True, None))
    except AssertionError as e:
        results.append(("Orchestrator初始化", False, str(e)))
        logger.error(f"Test 1 failed: {str(e)}", exc_info=True)
    except Exception as e:
        results.append(("Orchestrator初始化", False, str(e)))
        logger.error(f"Test 1 error: {str(e)}", exc_info=True)

    try:
        # Test 2: Session management
        test_session_management()
        results.append(("会话管理", True, None))
    except AssertionError as e:
        results.append(("会话管理", False, str(e)))
        logger.error(f"Test 2 failed: {str(e)}", exc_info=True)
    except Exception as e:
        results.append(("会话管理", False, str(e)))
        logger.error(f"Test 2 error: {str(e)}", exc_info=True)

    try:
        # Test 3: Mock pipeline
        test_orchestrator_mock_pipeline()
        results.append(("完整管道 (Mock)", True, None))
    except AssertionError as e:
        results.append(("完整管道 (Mock)", False, str(e)))
        logger.error(f"Test 3 failed: {str(e)}", exc_info=True)
    except Exception as e:
        results.append(("完整管道 (Mock)", False, str(e)))
        logger.error(f"Test 3 error: {str(e)}", exc_info=True)

    try:
        # Test 4: HydroAgent API
        test_hydro_agent_api()
        results.append(("HydroAgent API", True, None))
    except AssertionError as e:
        results.append(("HydroAgent API", False, str(e)))
        logger.error(f"Test 4 failed: {str(e)}", exc_info=True)
    except Exception as e:
        results.append(("HydroAgent API", False, str(e)))
        logger.error(f"Test 4 error: {str(e)}", exc_info=True)

    try:
        # Test 5: Conversation history
        test_conversation_history()
        results.append(("对话历史记录", True, None))
    except AssertionError as e:
        results.append(("对话历史记录", False, str(e)))
        logger.error(f"Test 5 failed: {str(e)}", exc_info=True)
    except Exception as e:
        results.append(("对话历史记录", False, str(e)))
        logger.error(f"Test 5 error: {str(e)}", exc_info=True)

    try:
        # Test 6: Error handling
        test_error_handling()
        results.append(("错误处理", True, None))
    except AssertionError as e:
        results.append(("错误处理", False, str(e)))
        logger.error(f"Test 6 failed: {str(e)}", exc_info=True)
    except Exception as e:
        results.append(("错误处理", False, str(e)))
        logger.error(f"Test 6 error: {str(e)}", exc_info=True)

    # Print test summary
    print("\n" + "="*70)
    print("测试总结")
    print("="*70)

    passed = sum(1 for _, success, _ in results if success)
    total = len(results)

    for i, (name, success, error) in enumerate(results, 1):
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{i}. {status} - {name}")
        if error:
            print(f"   错误: {error}")

    print()
    print(f"总计: {passed}/{total} 通过")
    print(f"成功率: {passed/total*100:.1f}%")
    print("="*70)
    print(f"\n详细日志: {log_file}")

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
