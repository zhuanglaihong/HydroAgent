"""
Author: Claude
Date: 2025-01-25 10:30:00
LastEditTime: 2025-01-25 10:30:00
LastEditors: Claude
Description: Test FAISS semantic search in PromptPool (v5.0)
FilePath: /HydroAgent/test/test_prompt_pool_semantic.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

Tests:
1. Basic FAISS initialization
2. Semantic search accuracy
3. Quality-based case retention
4. LLM prompt fusion
5. Fallback to rule-based search
"""

import pytest
import logging
from pathlib import Path
from datetime import datetime
import sys
import json
import tempfile

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from hydroagent.core.prompt_pool import PromptPool

# Setup logging
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

log_file = logs_dir / f"test_prompt_pool_semantic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class MockLLM:
    """Mock LLM interface for testing"""
    def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.2):
        # Simple mock: just return the base prompt with a note
        return f"{user_prompt}\n\n[Mock LLM: Enhanced with historical experience]"


@pytest.fixture
def temp_pool_dir():
    """Create temporary directory for test"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_intents():
    """Sample intent data for testing"""
    return [
        {
            "model_name": "gr4j",
            "basin_id": "01013500",
            "algorithm": "SCE_UA",
            "task_type": "calibration",
            "task_description": "标准流域率定"
        },
        {
            "model_name": "gr4j",
            "basin_id": "01022500",
            "algorithm": "SCE_UA",
            "task_type": "calibration",
            "task_description": "多流域率定"
        },
        {
            "model_name": "xaj",
            "basin_id": "01013500",
            "algorithm": "GA",
            "task_type": "calibration",
            "task_description": "XAJ模型率定"
        }
    ]


@pytest.fixture
def sample_configs():
    """Sample config data"""
    return [
        {
            "training_cfgs": {
                "algorithm_params": {
                    "rep": 1000,
                    "ngs": 300
                }
            }
        },
        {
            "training_cfgs": {
                "algorithm_params": {
                    "rep": 500,
                    "ngs": 200
                }
            }
        },
        {
            "training_cfgs": {
                "algorithm_params": {
                    "pop_size": 80,
                    "n_generations": 50
                }
            }
        }
    ]


@pytest.fixture
def sample_results():
    """Sample result data with different NSE scores"""
    return [
        {"metrics": {"NSE": 0.85, "RMSE": 1.2}},  # Excellent
        {"metrics": {"NSE": 0.68, "RMSE": 1.5}},  # Good
        {"metrics": {"NSE": 0.45, "RMSE": 2.1}}   # Fair
    ]


# ============================================================================
# Test 1: Basic FAISS Initialization
# ============================================================================

def test_faiss_initialization(temp_pool_dir):
    """测试 FAISS 初始化"""
    logger.info("\n=== Test 1: FAISS Initialization ===")

    # Test with FAISS enabled
    pool = PromptPool(
        pool_dir=temp_pool_dir,
        use_faiss=True,
        max_history=50
    )

    # Check if FAISS is available
    if pool.faiss_index is not None:
        logger.info("✓ FAISS initialized successfully")
        assert pool.use_faiss == True
        assert pool.embedding_model is not None
        logger.info(f"  Embedding model: {pool.embedding_model_name}")
        logger.info(f"  FAISS index total: {pool.faiss_index.ntotal}")
    else:
        logger.warning("⚠ FAISS not available, using fallback mode")
        assert pool.use_faiss == False

    logger.info("✓ Test 1 passed")


# ============================================================================
# Test 2: Add History with Quality Scoring
# ============================================================================

def test_add_history_with_quality(temp_pool_dir, sample_intents, sample_configs, sample_results):
    """测试历史记录添加和质量评分"""
    logger.info("\n=== Test 2: Add History with Quality Scoring ===")

    pool = PromptPool(pool_dir=temp_pool_dir, use_faiss=True, max_history=10)

    # Add multiple history records
    for i, (intent, config, result) in enumerate(zip(sample_intents, sample_configs, sample_results)):
        pool.add_history(
            task_type="calibration",
            intent=intent,
            config=config,
            result=result,
            success=True
        )
        logger.info(f"  Added case {i+1}: NSE={result['metrics']['NSE']}")

    # Check history
    assert len(pool.history) == 3
    logger.info(f"✓ Added {len(pool.history)} history records")

    # Check quality scores
    for i, record in enumerate(pool.history):
        quality = record.get("quality_score", 0)
        nse = record["result"]["metrics"]["NSE"]
        logger.info(f"  Case {i+1}: NSE={nse:.2f}, Quality={quality:.3f}")
        assert 0 <= quality <= 1.0

    # Check FAISS index
    if pool.faiss_index:
        logger.info(f"✓ FAISS index size: {pool.faiss_index.ntotal}")
        assert pool.faiss_index.ntotal == 3

    logger.info("✓ Test 2 passed")


# ============================================================================
# Test 3: Semantic Search
# ============================================================================

def test_semantic_search(temp_pool_dir, sample_intents, sample_configs, sample_results):
    """测试 FAISS 语义检索"""
    logger.info("\n=== Test 3: Semantic Search ===")

    pool = PromptPool(pool_dir=temp_pool_dir, use_faiss=True, max_history=50)

    # Add history records
    for intent, config, result in zip(sample_intents, sample_configs, sample_results):
        pool.add_history(
            task_type="calibration",
            intent=intent,
            config=config,
            result=result,
            success=True
        )

    # Test query: 查找与 gr4j + SCE_UA 相似的案例
    query_intent = {
        "model_name": "gr4j",
        "basin_id": "01030500",  # Different basin
        "algorithm": "SCE_UA",
        "task_type": "calibration",
        "task_description": "新流域率定"
    }

    similar_cases = pool.get_similar_cases(query_intent, limit=2)

    logger.info(f"Query intent: {query_intent['model_name']} + {query_intent['algorithm']}")
    logger.info(f"Found {len(similar_cases)} similar cases:")

    for i, case in enumerate(similar_cases, 1):
        similarity = case.get("similarity", 0)
        model = case["intent"].get("model_name")
        algo = case["intent"].get("algorithm")
        nse = case["result"]["metrics"]["NSE"]
        logger.info(f"  Case {i}: {model}+{algo}, NSE={nse:.2f}, Similarity={similarity:.3f}")

    # Assertions
    assert len(similar_cases) > 0

    if pool.use_faiss and pool.faiss_index:
        # If FAISS is working, check similarity scores
        for case in similar_cases:
            assert "similarity" in case
            assert 0 <= case["similarity"] <= 1.0
        logger.info("✓ FAISS semantic search working")
    else:
        logger.info("✓ Rule-based search working (FAISS not available)")

    logger.info("✓ Test 3 passed")


# ============================================================================
# Test 4: Quality-Based Case Retention
# ============================================================================

def test_quality_based_retention(temp_pool_dir):
    """测试基于质量的案例保留"""
    logger.info("\n=== Test 4: Quality-Based Case Retention ===")

    pool = PromptPool(pool_dir=temp_pool_dir, use_faiss=True, max_history=5)

    # Add 10 cases with varying NSE scores
    for i in range(10):
        nse = 0.3 + i * 0.07  # 0.3, 0.37, 0.44, ..., 0.93
        pool.add_history(
            task_type="calibration",
            intent={
                "model_name": "gr4j",
                "basin_id": f"0101{i:04d}",
                "algorithm": "SCE_UA",
                "task_type": "calibration"
            },
            config={"training_cfgs": {"algorithm_params": {"rep": 1000}}},
            result={"metrics": {"NSE": nse}},
            success=True
        )

    # Check history size (should be limited to 5)
    assert len(pool.history) == 5
    logger.info(f"✓ History limited to {len(pool.history)} cases (max_history=5)")

    # Check that highest NSE cases are retained
    nse_scores = [r["result"]["metrics"]["NSE"] for r in pool.history]
    logger.info(f"  Retained NSE scores: {nse_scores}")

    # All retained cases should have NSE >= 0.65 (top 5 cases)
    assert all(nse >= 0.65 for nse in nse_scores)
    logger.info("✓ High-quality cases retained (NSE >= 0.65)")

    logger.info("✓ Test 4 passed")


# ============================================================================
# Test 5: LLM Prompt Fusion
# ============================================================================

def test_llm_prompt_fusion(temp_pool_dir, sample_intents, sample_configs, sample_results):
    """测试 LLM 动态融合提示词"""
    logger.info("\n=== Test 5: LLM Prompt Fusion ===")

    mock_llm = MockLLM()
    pool = PromptPool(
        pool_dir=temp_pool_dir,
        use_faiss=True,
        llm_interface=mock_llm,
        max_history=50
    )

    # Add history
    for intent, config, result in zip(sample_intents, sample_configs, sample_results):
        pool.add_history(
            task_type="calibration",
            intent=intent,
            config=config,
            result=result,
            success=True
        )

    # Test prompt enhancement
    base_prompt = "请生成GR4J模型的率定配置"
    query_intent = {
        "model_name": "gr4j",
        "basin_id": "01013500",
        "algorithm": "SCE_UA",
        "task_type": "calibration"
    }

    enhanced_prompt = pool.generate_enhanced_prompt(base_prompt, query_intent)

    logger.info("Base prompt length: " + str(len(base_prompt)))
    logger.info("Enhanced prompt length: " + str(len(enhanced_prompt)))

    # Check that prompt was enhanced
    assert len(enhanced_prompt) > len(base_prompt)
    assert "历史" in enhanced_prompt or "Mock LLM" in enhanced_prompt
    logger.info("✓ Prompt enhanced successfully")

    logger.info("✓ Test 5 passed")


# ============================================================================
# Test 6: Fallback to Rule-Based Search
# ============================================================================

def test_fallback_rule_based(temp_pool_dir, sample_intents, sample_configs, sample_results):
    """测试降级到规则匹配"""
    logger.info("\n=== Test 6: Fallback to Rule-Based Search ===")

    # Force FAISS to be disabled
    pool = PromptPool(pool_dir=temp_pool_dir, use_faiss=False, max_history=50)

    assert pool.use_faiss == False
    logger.info("✓ FAISS disabled (forced)")

    # Add history
    for intent, config, result in zip(sample_intents, sample_configs, sample_results):
        pool.add_history(
            task_type="calibration",
            intent=intent,
            config=config,
            result=result,
            success=True
        )

    # Test rule-based search
    query_intent = {
        "model_name": "gr4j",
        "basin_id": "01013500",
        "algorithm": "SCE_UA",
        "task_type": "calibration"
    }

    similar_cases = pool.get_similar_cases(query_intent, limit=2, use_semantic=False)

    logger.info(f"Found {len(similar_cases)} similar cases (rule-based)")
    assert len(similar_cases) > 0

    for i, case in enumerate(similar_cases, 1):
        similarity = case.get("similarity", 0)
        model = case["intent"].get("model_name")
        logger.info(f"  Case {i}: {model}, Similarity={similarity:.3f}")

    logger.info("✓ Rule-based search working")
    logger.info("✓ Test 6 passed")


# ============================================================================
# Test 7: Persistence
# ============================================================================

def test_persistence(temp_pool_dir, sample_intents, sample_configs, sample_results):
    """测试持久化和恢复"""
    logger.info("\n=== Test 7: Persistence ===")

    # Phase 1: Create and populate pool
    pool1 = PromptPool(pool_dir=temp_pool_dir, use_faiss=True, max_history=50)

    for intent, config, result in zip(sample_intents, sample_configs, sample_results):
        pool1.add_history(
            task_type="calibration",
            intent=intent,
            config=config,
            result=result,
            success=True
        )

    initial_count = len(pool1.history)
    logger.info(f"✓ Created pool with {initial_count} records")

    # Phase 2: Load pool from disk
    pool2 = PromptPool(pool_dir=temp_pool_dir, use_faiss=True, max_history=50)

    restored_count = len(pool2.history)
    logger.info(f"✓ Restored pool with {restored_count} records")

    # Check that history was restored
    assert restored_count == initial_count

    # Check FAISS index was rebuilt
    if pool2.use_faiss and pool2.faiss_index:
        logger.info(f"✓ FAISS index rebuilt ({pool2.faiss_index.ntotal} vectors)")
        assert pool2.faiss_index.ntotal == initial_count

    logger.info("✓ Test 7 passed")


# ============================================================================
# Test 8: Statistics
# ============================================================================

def test_statistics(temp_pool_dir, sample_intents, sample_configs, sample_results):
    """测试统计信息"""
    logger.info("\n=== Test 8: Statistics ===")

    pool = PromptPool(pool_dir=temp_pool_dir, use_faiss=True, max_history=50)

    # Add history
    for intent, config, result in zip(sample_intents, sample_configs, sample_results):
        pool.add_history(
            task_type="calibration",
            intent=intent,
            config=config,
            result=result,
            success=True
        )

    # Get statistics
    stats = pool.get_statistics()

    logger.info("Statistics:")
    logger.info(f"  Total records: {stats['total_records']}")
    logger.info(f"  Successful records: {stats['successful_records']}")
    logger.info(f"  Success rate: {stats['success_rate']:.2%}")
    logger.info(f"  Average quality: {stats['average_quality_score']:.3f}")
    logger.info(f"  FAISS enabled: {stats['faiss_enabled']}")
    logger.info(f"  FAISS index size: {stats['faiss_index_size']}")
    logger.info(f"  Task types: {stats['task_type_distribution']}")
    logger.info(f"  Models: {stats['model_usage']}")

    # Assertions
    assert stats['total_records'] == 3
    assert stats['successful_records'] == 3
    assert stats['success_rate'] == 1.0
    assert stats['average_quality_score'] > 0

    logger.info("✓ Test 8 passed")


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    logger.info("="*80)
    logger.info("Starting PromptPool FAISS Semantic Search Tests")
    logger.info("="*80)

    pytest.main([__file__, "-v", "-s"])

    logger.info("\n" + "="*80)
    logger.info(f"Test log saved to: {log_file}")
    logger.info("="*80)
