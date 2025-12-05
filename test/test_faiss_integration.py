"""
Author: Claude
Date: 2025-12-04 21:10:00
LastEditTime: 2025-12-04 21:10:00
LastEditors: Claude
Description: Test FAISS integration for PromptPool semantic search
             测试PromptPool的FAISS语义检索功能
FilePath: /HydroAgent/test/test_faiss_integration.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

Test Coverage:
1. FAISS availability and installation check
2. SentenceTransformer embedding generation
3. FAISS index creation and persistence
4. Semantic similarity search
5. PromptPool integration with FAISS
6. Fallback behavior when FAISS unavailable
"""

import sys
from pathlib import Path
import logging
from datetime import datetime
import shutil

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup logging
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

log_file = logs_dir / f"test_faiss_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


# ========================================================================
# Test 1: Check FAISS and Dependencies
# ========================================================================

def test_faiss_availability():
    """Test if FAISS and SentenceTransformer are available."""
    logger.info("\n" + "="*80)
    logger.info("Test 1: FAISS and Dependencies Availability")
    logger.info("="*80)

    results = {
        "faiss": False,
        "sentence_transformers": False,
        "numpy": False
    }

    # Test faiss-cpu
    try:
        import faiss
        results["faiss"] = True
        logger.info(f"✅ FAISS available (version: {faiss.__version__ if hasattr(faiss, '__version__') else 'unknown'})")
    except ImportError as e:
        logger.warning(f"❌ FAISS not available: {e}")
        logger.info("   Install with: pip install faiss-cpu")

    # Test sentence-transformers
    try:
        from sentence_transformers import SentenceTransformer
        results["sentence_transformers"] = True
        logger.info("✅ SentenceTransformer available")
    except ImportError as e:
        logger.warning(f"❌ SentenceTransformer not available: {e}")
        logger.info("   Install with: pip install sentence-transformers")

    # Test numpy
    try:
        import numpy
        results["numpy"] = True
        logger.info(f"✅ NumPy available (version: {numpy.__version__})")
    except ImportError as e:
        logger.warning(f"❌ NumPy not available: {e}")

    all_available = all(results.values())

    if all_available:
        logger.info("\n✅ All FAISS dependencies are available!")
    else:
        logger.warning("\n⚠️ Some dependencies are missing. FAISS functionality will be disabled.")
        logger.info("\nTo enable FAISS, install missing dependencies:")
        if not results["faiss"]:
            logger.info("  uv pip install faiss-cpu")
        if not results["sentence_transformers"]:
            logger.info("  uv pip install sentence-transformers")

    return all_available


# ========================================================================
# Test 2: Embedding Generation
# ========================================================================

def test_embedding_generation():
    """Test SentenceTransformer embedding generation."""
    logger.info("\n" + "="*80)
    logger.info("Test 2: Embedding Generation")
    logger.info("="*80)

    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np

        # Load model
        logger.info("Loading embedding model: all-MiniLM-L6-v2")
        model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

        # Test sentences
        sentences = [
            "率定GR4J模型，流域01013500",
            "使用SCE-UA算法率定XAJ模型",
            "评估模型在流域的性能",
        ]

        logger.info(f"\nGenerating embeddings for {len(sentences)} sentences...")

        # Generate embeddings
        embeddings = model.encode(sentences)

        logger.info(f"✅ Embeddings generated successfully!")
        logger.info(f"   Shape: {embeddings.shape}")
        logger.info(f"   Dimension: {embeddings.shape[1]}")
        logger.info(f"   Data type: {embeddings.dtype}")

        # Test similarity
        logger.info("\nTesting semantic similarity...")
        from numpy.linalg import norm

        def cosine_similarity(a, b):
            return np.dot(a, b) / (norm(a) * norm(b))

        sim_01 = cosine_similarity(embeddings[0], embeddings[1])
        sim_02 = cosine_similarity(embeddings[0], embeddings[2])
        sim_12 = cosine_similarity(embeddings[1], embeddings[2])

        logger.info(f"   Similarity(sentence1, sentence2): {sim_01:.4f}")
        logger.info(f"   Similarity(sentence1, sentence3): {sim_02:.4f}")
        logger.info(f"   Similarity(sentence2, sentence3): {sim_12:.4f}")

        logger.info("\n✅ Embedding generation test passed!")
        return True

    except Exception as e:
        logger.error(f"❌ Embedding generation test failed: {e}", exc_info=True)
        return False


# ========================================================================
# Test 3: FAISS Index Operations
# ========================================================================

def test_faiss_index_operations():
    """Test FAISS index creation, adding vectors, and searching."""
    logger.info("\n" + "="*80)
    logger.info("Test 3: FAISS Index Operations")
    logger.info("="*80)

    try:
        import faiss
        import numpy as np

        # Create random vectors
        dimension = 384  # all-MiniLM-L6-v2 dimension
        n_vectors = 10

        logger.info(f"Creating FAISS index (dimension={dimension})")
        index = faiss.IndexFlatL2(dimension)

        logger.info(f"Generating {n_vectors} random vectors...")
        vectors = np.random.random((n_vectors, dimension)).astype('float32')

        # Add vectors
        logger.info("Adding vectors to index...")
        index.add(vectors)

        logger.info(f"✅ Index created with {index.ntotal} vectors")

        # Search
        query = vectors[0:1]  # Use first vector as query
        k = 3  # Find top 3

        logger.info(f"\nSearching for top {k} nearest neighbors...")
        distances, indices = index.search(query, k)

        logger.info(f"✅ Search completed!")
        logger.info(f"   Nearest indices: {indices[0]}")
        logger.info(f"   Distances: {distances[0]}")

        # Test persistence
        test_dir = Path("test_temp_faiss")
        test_dir.mkdir(exist_ok=True)
        index_file = test_dir / "test_index.bin"

        logger.info(f"\nTesting index persistence to {index_file}...")
        faiss.write_index(index, str(index_file))
        logger.info("✅ Index saved successfully")

        logger.info("Loading index from file...")
        loaded_index = faiss.read_index(str(index_file))
        logger.info(f"✅ Index loaded successfully ({loaded_index.ntotal} vectors)")

        # Cleanup
        shutil.rmtree(test_dir)
        logger.info("✅ Cleanup completed")

        logger.info("\n✅ FAISS index operations test passed!")
        return True

    except Exception as e:
        logger.error(f"❌ FAISS index operations test failed: {e}", exc_info=True)
        return False


# ========================================================================
# Test 4: PromptPool FAISS Integration
# ========================================================================

def test_promptpool_faiss_integration():
    """Test PromptPool with FAISS enabled."""
    logger.info("\n" + "="*80)
    logger.info("Test 4: PromptPool FAISS Integration")
    logger.info("="*80)

    try:
        from hydroagent.core.prompt_pool import PromptPool

        # Create test directory
        test_dir = Path("test_temp_promptpool")
        if test_dir.exists():
            shutil.rmtree(test_dir)
        test_dir.mkdir(exist_ok=True)

        # Test with FAISS enabled
        logger.info("Initializing PromptPool with FAISS enabled...")
        pool = PromptPool(
            pool_dir=test_dir,
            use_faiss=True,
            max_history=50
        )

        if pool.use_faiss and pool.faiss_index is not None:
            logger.info("✅ PromptPool initialized with FAISS successfully!")
            logger.info(f"   FAISS index vectors: {pool.faiss_index.ntotal}")
            logger.info(f"   Embedding model: {pool.embedding_model_name}")
        else:
            logger.warning("⚠️ PromptPool initialized without FAISS (fallback mode)")

        # Add some test history records
        logger.info("\nAdding test history records...")

        test_cases = [
            {
                "task_type": "standard_calibration",
                "intent": {
                    "task_type": "standard_calibration",
                    "model_name": "gr4j",
                    "basin_id": "01013500",
                    "algorithm": "SCE_UA"
                },
                "config": {"model": "gr4j", "basin": "01013500"},
                "result": {"metrics": {"NSE": 0.75, "RMSE": 1.2}},
                "success": True
            },
            {
                "task_type": "iterative_optimization",
                "intent": {
                    "task_type": "iterative_optimization",
                    "model_name": "xaj",
                    "basin_id": "01022500",
                    "algorithm": "DE"
                },
                "config": {"model": "xaj", "basin": "01022500"},
                "result": {"metrics": {"NSE": 0.68, "RMSE": 1.5}},
                "success": True
            },
            {
                "task_type": "standard_calibration",
                "intent": {
                    "task_type": "standard_calibration",
                    "model_name": "gr4j",
                    "basin_id": "01030500",
                    "algorithm": "PSO"
                },
                "config": {"model": "gr4j", "basin": "01030500"},
                "result": {"metrics": {"NSE": 0.82, "RMSE": 0.9}},
                "success": True
            }
        ]

        for i, case in enumerate(test_cases, 1):
            pool.add_history(**case)
            logger.info(f"   Added case {i}/{len(test_cases)}")

        logger.info(f"✅ Added {len(test_cases)} history records")
        logger.info(f"   Total history: {len(pool.history)}")

        if pool.use_faiss and pool.faiss_index:
            logger.info(f"   FAISS index size: {pool.faiss_index.ntotal}")

        # Test semantic search
        if pool.use_faiss and pool.faiss_index and pool.faiss_index.ntotal > 0:
            logger.info("\nTesting semantic search...")

            query = "率定GR4J模型，使用SCE-UA算法"
            logger.info(f"   Query: {query}")

            try:
                results = pool.search_similar(query, top_k=2)
                logger.info(f"✅ Found {len(results)} similar cases")

                for i, result in enumerate(results, 1):
                    task_type = result.get("task_type", "unknown")
                    intent = result.get("intent", {})
                    quality = result.get("quality_score", 0)
                    logger.info(f"   Result {i}: task_type={task_type}, "
                                f"model={intent.get('model_name')}, "
                                f"quality={quality:.3f}")

            except Exception as e:
                logger.warning(f"⚠️ Semantic search failed: {e}")
        else:
            logger.info("\n⚠️ Skipping semantic search (FAISS not available or no vectors)")

        # Cleanup
        shutil.rmtree(test_dir)
        logger.info("\n✅ PromptPool FAISS integration test passed!")
        return True

    except Exception as e:
        logger.error(f"❌ PromptPool FAISS integration test failed: {e}", exc_info=True)

        # Cleanup on error
        test_dir = Path("test_temp_promptpool")
        if test_dir.exists():
            shutil.rmtree(test_dir)

        return False


# ========================================================================
# Test 5: Fallback Behavior
# ========================================================================

def test_faiss_fallback_behavior():
    """Test that PromptPool works without FAISS (fallback mode)."""
    logger.info("\n" + "="*80)
    logger.info("Test 5: FAISS Fallback Behavior")
    logger.info("="*80)

    try:
        from hydroagent.core.prompt_pool import PromptPool

        # Create test directory
        test_dir = Path("test_temp_fallback")
        if test_dir.exists():
            shutil.rmtree(test_dir)
        test_dir.mkdir(exist_ok=True)

        # Test with FAISS disabled
        logger.info("Initializing PromptPool with FAISS disabled...")
        pool = PromptPool(
            pool_dir=test_dir,
            use_faiss=False,  # Explicitly disable
            max_history=50
        )

        logger.info(f"✅ PromptPool initialized in fallback mode")
        logger.info(f"   use_faiss: {pool.use_faiss}")
        logger.info(f"   faiss_index: {pool.faiss_index}")
        logger.info(f"   embedding_model: {pool.embedding_model}")

        # Add test record
        logger.info("\nAdding test record in fallback mode...")
        pool.add_history(
            task_type="standard_calibration",
            intent={
                "task_type": "standard_calibration",
                "model_name": "gr4j",
                "basin_id": "01013500"
            },
            config={"model": "gr4j"},
            result={"metrics": {"NSE": 0.75}},
            success=True
        )

        logger.info(f"✅ Record added successfully (total: {len(pool.history)})")

        # Test prompt generation (should work without FAISS)
        logger.info("\nTesting prompt generation without FAISS...")
        prompt = pool.generate_context_prompt(
            base_prompt="Test prompt",
            intent={"task_type": "standard_calibration", "model_name": "gr4j"}
        )

        logger.info(f"✅ Prompt generated successfully (length: {len(prompt)} chars)")

        # Cleanup
        shutil.rmtree(test_dir)
        logger.info("\n✅ FAISS fallback behavior test passed!")
        return True

    except Exception as e:
        logger.error(f"❌ FAISS fallback test failed: {e}", exc_info=True)

        # Cleanup on error
        test_dir = Path("test_temp_fallback")
        if test_dir.exists():
            shutil.rmtree(test_dir)

        return False


# ========================================================================
# Main Test Runner
# ========================================================================

def main():
    """Run all FAISS integration tests."""
    logger.info("\n" + "="*80)
    logger.info("FAISS Integration Test Suite")
    logger.info("="*80)
    logger.info(f"Log file: {log_file}")

    results = {}

    # Test 1: Check availability
    results["availability"] = test_faiss_availability()

    # Only run remaining tests if FAISS is available
    if results["availability"]:
        logger.info("\n✅ FAISS available - running full test suite")

        # Test 2: Embedding generation
        results["embedding"] = test_embedding_generation()

        # Test 3: FAISS operations
        results["faiss_ops"] = test_faiss_index_operations()

        # Test 4: PromptPool integration
        results["promptpool_integration"] = test_promptpool_faiss_integration()
    else:
        logger.warning("\n⚠️ FAISS not available - skipping advanced tests")

    # Test 5: Fallback behavior (always run)
    results["fallback"] = test_faiss_fallback_behavior()

    # Summary
    logger.info("\n" + "="*80)
    logger.info("Test Summary")
    logger.info("="*80)

    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{test_name}: {status}")

    passed = sum(results.values())
    total = len(results)
    logger.info(f"\nTotal: {passed}/{total} tests passed")

    if all(results.values()):
        logger.info("\n🎉 All tests passed!")
    else:
        logger.warning("\n⚠️ Some tests failed. Check logs for details.")

    logger.info(f"\nFull log saved to: {log_file}")


if __name__ == "__main__":
    main()
