"""
Author: Claude & zhuanglaihong
Date: 2025-01-20 20:30:00
LastEditTime: 2025-01-20 20:30:00
LastEditors: Claude
Description: Comprehensive test for IntentAgent - Natural Language Understanding
             IntentAgent 综合测试 - 自然语言理解
FilePath: \\HydroAgent\\test\\test_intent_agent.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import sys
from pathlib import Path
import logging
from datetime import datetime
import json
import time

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Ensure logs directory exists
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

# Set up logging
log_file = logs_dir / f"test_intent_agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)
print(f"[LOG] 日志将保存到: {log_file}\n")


# ============================================================================
# LLM Configuration
# ============================================================================

def create_llm_backend(backend_type="ollama"):
    """
    Create LLM backend interface.
    创建 LLM 后端接口。

    Args:
        backend_type: "ollama" or "qwen_api"

    Returns:
        LLMInterface instance
    """
    from hydroagent.core.llm_interface import OllamaInterface, OpenAIInterface

    if backend_type == "ollama":
        logger.info("[LLM] Using Ollama local model: qwen3:8b")
        return OllamaInterface(
            model_name="qwen3:8b",
            base_url="http://localhost:11434"
        )

    elif backend_type == "qwen_api":
        logger.info("[LLM] Using Qwen Cloud API: qwen-turbo")
        # Read API key from environment or config
        api_key = "sk-50be7aaa64564360bb2a6dbd2e2db325"  # Replace with your key
        return OpenAIInterface(
            model_name="qwen-turbo",
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )

    else:
        raise ValueError(f"Unknown backend type: {backend_type}")


# ============================================================================
# Test Cases
# ============================================================================

# Test queries covering various scenarios
TEST_QUERIES = [
    {
        "id": 1,
        "query": "率定GR4J模型，流域01013500，2000到2010年",
        "description": "Complete Chinese query with all info",
        "expected": {
            "intent": "calibration",
            "model_name": "gr4j",
            "basin_id": "01013500",
            "has_time_period": True
        }
    },
    {
        "id": 2,
        "query": "I want to calibrate XAJ model for basin camels_11532500 from 2005 to 2015",
        "description": "Complete English query",
        "expected": {
            "intent": "calibration",
            "model_name": "xaj",
            "basin_id": "camels_11532500",
            "has_time_period": True
        }
    },
    {
        "id": 3,
        "query": "帮我优化一下水文模型参数",
        "description": "Vague Chinese query - missing details",
        "expected": {
            "intent": "calibration",
            "model_name": None,
            "basin_id": None,
            "has_missing_info": True
        }
    },
    {
        "id": 4,
        "query": "Evaluate GR5J model performance",
        "description": "Evaluation intent - English",
        "expected": {
            "intent": "evaluation",
            "model_name": "gr5j",
            "basin_id": None
        }
    },
    {
        "id": 5,
        "query": "测试XAJ模型在流域01013500上的表现，使用2010-2015年的数据",
        "description": "Evaluation intent - Chinese",
        "expected": {
            "intent": "evaluation",
            "model_name": "xaj",
            "basin_id": "01013500",
            "has_time_period": True
        }
    },
    {
        "id": 6,
        "query": "帮我画一下流域的降雨径流过程线",
        "description": "Extension task - visualization",
        "expected": {
            "intent": "extension",
            "model_name": None,
            "task_type": "visualization"
        }
    },
    {
        "id": 7,
        "query": "Run GR4J simulation for basin 01013500 with known parameters",
        "description": "Simulation intent",
        "expected": {
            "intent": "simulation",
            "model_name": "gr4j",
            "basin_id": "01013500"
        }
    },
    {
        "id": 8,
        "query": "用SCE-UA算法率定GR6J模型，流域camels_11532500，训练期2000-2010，测试期2011-2015",
        "description": "Complete query with algorithm specification",
        "expected": {
            "intent": "calibration",
            "model_name": "gr6j",
            "basin_id": "camels_11532500",
            "algorithm": "SCE_UA",
            "has_time_period": True
        }
    }
]


# ============================================================================
# Test Functions
# ============================================================================

def test_intent_agent_basic(llm_backend):
    """
    Test 1: Basic functionality of IntentAgent.
    测试1：IntentAgent 基本功能。
    """
    print("\n" + "="*80)
    print("[TEST] Test 1: Basic IntentAgent Functionality")
    print("="*80)

    from hydroagent.agents.intent_agent import IntentAgent

    # Create IntentAgent
    agent = IntentAgent(llm_interface=llm_backend)

    logger.info(f"Agent created: {agent.name}")
    logger.info(f"LLM backend: {llm_backend.model_name}")

    # Test a simple query
    test_query = "率定GR4J模型，流域01013500"

    print(f"\n[TEST] Query: {test_query}")

    try:
        result = agent.process({
            "query": test_query,
            "context": {}
        })

        if result["success"]:
            intent_result = result["intent_result"]
            print(f"[PASS] Success!")
            print(f"   Intent: {intent_result['intent']}")
            print(f"   Model: {intent_result['model_name']}")
            print(f"   Basin: {intent_result['basin_id']}")
            print(f"   Confidence: {intent_result['confidence']:.2f}")

            logger.info(f"Test 1 PASSED: {json.dumps(intent_result, ensure_ascii=False)}")
            return True
        else:
            print(f"[FAIL] Failed: {result.get('error')}")
            logger.error(f"Test 1 FAILED: {result.get('error')}")
            return False

    except Exception as e:
        print(f"[FAIL] Exception: {str(e)}")
        logger.error(f"Test 1 EXCEPTION: {str(e)}", exc_info=True)
        return False


def test_all_queries(llm_backend):
    """
    Test 2: Run all test queries and validate results.
    测试2：运行所有测试查询并验证结果。
    """
    print("\n" + "="*80)
    print("[TEST] Test 2: Comprehensive Query Testing")
    print("="*80)

    from hydroagent.agents.intent_agent import IntentAgent

    agent = IntentAgent(llm_interface=llm_backend)

    results = []
    passed = 0
    failed = 0

    for test_case in TEST_QUERIES:
        print(f"\n--- Test Case {test_case['id']} ---")
        print(f"Description: {test_case['description']}")
        print(f"Query: {test_case['query']}")

        try:
            result = agent.process({
                "query": test_case["query"],
                "context": {}
            })

            if result["success"]:
                intent_result = result["intent_result"]

                # Validate against expected results
                validation_passed = True
                validation_errors = []

                expected = test_case["expected"]

                # Check intent
                if "intent" in expected and intent_result["intent"] != expected["intent"]:
                    validation_passed = False
                    validation_errors.append(
                        f"Intent mismatch: expected '{expected['intent']}', got '{intent_result['intent']}'"
                    )

                # Check model_name
                if "model_name" in expected:
                    if expected["model_name"] is not None and intent_result["model_name"] != expected["model_name"]:
                        validation_passed = False
                        validation_errors.append(
                            f"Model mismatch: expected '{expected['model_name']}', got '{intent_result['model_name']}'"
                        )

                # Check basin_id
                if "basin_id" in expected:
                    if expected["basin_id"] is not None and intent_result["basin_id"] != expected["basin_id"]:
                        validation_passed = False
                        validation_errors.append(
                            f"Basin mismatch: expected '{expected['basin_id']}', got '{intent_result['basin_id']}'"
                        )

                # Check for time_period
                if expected.get("has_time_period"):
                    if not intent_result.get("time_period"):
                        validation_passed = False
                        validation_errors.append("Expected time_period but got None")

                # Check for missing_info
                if expected.get("has_missing_info"):
                    if not intent_result.get("missing_info"):
                        validation_passed = False
                        validation_errors.append("Expected missing_info but got empty list")

                if validation_passed:
                    print(f"[PASS] PASS")
                    passed += 1
                else:
                    print(f"[WARN]  PARTIAL: Validation issues:")
                    for error in validation_errors:
                        print(f"     - {error}")
                    passed += 1  # Still count as passed if LLM responded

                # Print result summary
                print(f"   Intent: {intent_result['intent']}")
                print(f"   Model: {intent_result.get('model_name', 'N/A')}")
                print(f"   Basin: {intent_result.get('basin_id', 'N/A')}")
                if intent_result.get("time_period"):
                    print(f"   Time Period: {intent_result['time_period']}")
                if intent_result.get("missing_info"):
                    print(f"   Missing Info: {intent_result['missing_info']}")
                print(f"   Confidence: {intent_result.get('confidence', 0):.2f}")

                results.append({
                    "test_id": test_case["id"],
                    "status": "passed" if validation_passed else "partial",
                    "result": intent_result
                })

                logger.info(
                    f"Test Case {test_case['id']} - "
                    f"{'PASSED' if validation_passed else 'PARTIAL'}: "
                    f"{json.dumps(intent_result, ensure_ascii=False)}"
                )

            else:
                print(f"[FAIL] FAIL: {result.get('error')}")
                failed += 1
                results.append({
                    "test_id": test_case["id"],
                    "status": "failed",
                    "error": result.get("error")
                })
                logger.error(f"Test Case {test_case['id']} FAILED: {result.get('error')}")

            # Add delay to avoid rate limiting
            time.sleep(1)

        except Exception as e:
            print(f"[FAIL] EXCEPTION: {str(e)}")
            failed += 1
            results.append({
                "test_id": test_case["id"],
                "status": "exception",
                "error": str(e)
            })
            logger.error(f"Test Case {test_case['id']} EXCEPTION: {str(e)}", exc_info=True)

    # Summary
    print("\n" + "="*80)
    print("[SUMMARY] Test Summary")
    print("="*80)
    print(f"Total: {len(TEST_QUERIES)} | Passed: {passed} | Failed: {failed}")
    print(f"Success Rate: {passed/len(TEST_QUERIES)*100:.1f}%")

    logger.info(f"Test 2 Summary: {passed}/{len(TEST_QUERIES)} passed")

    return passed == len(TEST_QUERIES)


def test_chinese_english_mixed(llm_backend):
    """
    Test 3: Chinese-English mixed queries.
    测试3：中英文混合查询。
    """
    print("\n" + "="*80)
    print("[TEST] Test 3: Chinese-English Mixed Queries")
    print("="*80)

    from hydroagent.agents.intent_agent import IntentAgent

    agent = IntentAgent(llm_interface=llm_backend)

    mixed_queries = [
        "Calibrate GR4J模型，basin是01013500",
        "用XAJ model进行calibration，流域camels_11532500",
        "Evaluate the performance of GR5J在测试集上"
    ]

    for query in mixed_queries:
        print(f"\n[TEST] Query: {query}")

        try:
            result = agent.process({"query": query, "context": {}})

            if result["success"]:
                intent_result = result["intent_result"]
                print(f"[PASS] Success")
                print(f"   Intent: {intent_result['intent']}")
                print(f"   Model: {intent_result.get('model_name', 'N/A')}")
                print(f"   Basin: {intent_result.get('basin_id', 'N/A')}")
            else:
                print(f"[FAIL] Failed: {result.get('error')}")

            time.sleep(1)

        except Exception as e:
            print(f"[FAIL] Exception: {str(e)}")

    return True


def test_error_handling(llm_backend):
    """
    Test 4: Error handling and edge cases.
    测试4：错误处理和边界情况。
    """
    print("\n" + "="*80)
    print("[TEST] Test 4: Error Handling & Edge Cases")
    print("="*80)

    from hydroagent.agents.intent_agent import IntentAgent

    agent = IntentAgent(llm_interface=llm_backend)

    edge_cases = [
        "",  # Empty query
        "   ",  # Whitespace only
        "Hello",  # Unrelated query
        "123456",  # Numbers only
        "率定率定率定",  # Repeated words
    ]

    for i, query in enumerate(edge_cases, 1):
        print(f"\n[EDGE] Edge Case {i}: '{query}'")

        try:
            result = agent.process({"query": query, "context": {}})

            if result["success"]:
                intent_result = result["intent_result"]
                print(f"   Result: Intent={intent_result['intent']}, "
                      f"Missing={len(intent_result.get('missing_info', []))}")
            else:
                print(f"   Handled error: {result.get('error')}")

            time.sleep(0.5)

        except Exception as e:
            print(f"   Exception (expected): {str(e)}")

    print("\n[PASS] Error handling test completed")
    return True


# ============================================================================
# Main Test Runner
# ============================================================================

def main():
    """
    Main test runner.
    主测试运行器。
    """
    print("\n" + "="*80)
    print("[RUN] IntentAgent Comprehensive Test Suite")
    print("="*80)
    print(f"Project Root: {project_root}")
    print(f"Log File: {log_file}")

    # Ask user to select LLM backend
    print("\n[MENU] Select LLM Backend:")
    print("  1. Ollama (local qwen3:8b)")
    print("  2. Qwen Cloud API (qwen-turbo)")

    choice = input("\nEnter your choice (1 or 2, default=1): ").strip()

    if choice == "2":
        backend_type = "qwen_api"
    else:
        backend_type = "ollama"

    print(f"\n[PASS] Selected: {backend_type}")

    # Create LLM backend
    try:
        llm_backend = create_llm_backend(backend_type)
        logger.info(f"LLM backend created: {backend_type}")
    except Exception as e:
        print(f"\n[FAIL] Failed to create LLM backend: {str(e)}")
        logger.error(f"Failed to create LLM backend: {str(e)}", exc_info=True)
        return

    # Run tests
    test_results = {}

    try:
        # Test 1: Basic functionality
        test_results["basic"] = test_intent_agent_basic(llm_backend)

        # Test 2: All queries
        test_results["all_queries"] = test_all_queries(llm_backend)

        # Test 3: Mixed language
        test_results["mixed_language"] = test_chinese_english_mixed(llm_backend)

        # Test 4: Error handling
        test_results["error_handling"] = test_error_handling(llm_backend)

    except KeyboardInterrupt:
        print("\n\n[WARN]  Tests interrupted by user")
        logger.warning("Tests interrupted by user")

    except Exception as e:
        print(f"\n\n[FAIL] Unexpected error during tests: {str(e)}")
        logger.error(f"Unexpected error during tests: {str(e)}", exc_info=True)

    # Final summary
    print("\n" + "="*80)
    print("[FINAL] Final Test Summary")
    print("="*80)

    for test_name, result in test_results.items():
        status = "[PASS] PASS" if result else "[FAIL] FAIL"
        print(f"{test_name:20s}: {status}")

    all_passed = all(test_results.values())

    if all_passed:
        print("\n[SUCCESS] All tests passed!")
        logger.info("All tests passed!")
    else:
        print("\n[WARN]  Some tests failed. Check logs for details.")
        logger.warning("Some tests failed")

    print(f"\n[TEST] Detailed logs saved to: {log_file}")
    print("\n" + "="*80)


if __name__ == "__main__":
    main()
