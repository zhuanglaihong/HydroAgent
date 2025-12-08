"""
Test script for basin_validator.py
测试basin_validator的功能
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_hydrodataset_api():
    """Test hydrodataset API to understand how to get basin IDs."""
    logger.info("=== Testing hydrodataset API ===")

    try:
        from hydrodataset import CamelsUs

        logger.info("✓ Successfully imported CamelsUs")

        # Try to create instance
        camels = CamelsUs(data_path="D:\project\data")
        logger.info("✓ Successfully created CamelsUs instance")

        # Check available methods
        logger.info("\nAvailable methods:")
        methods = [m for m in dir(camels) if not m.startswith('_') and callable(getattr(camels, m))]
        for method in methods[:20]:  # Show first 20 methods
            logger.info(f"  - {method}")

        # Try to get basin IDs
        if hasattr(camels, 'read_object_ids'):
            logger.info("\n✓ Found read_object_ids() method")
            basin_ids = camels.read_object_ids()
            logger.info(f"  Total basins: {len(basin_ids)}")
            logger.info(f"  Sample IDs: {basin_ids[:10]}")

            # Check if our test IDs are in the list
            test_ids = ['01013500', '11532500', '12025000', '14301000', '14306500', '14325000']
            for test_id in test_ids:
                if test_id in basin_ids:
                    logger.info(f"  ✓ {test_id} found in dataset")
                else:
                    logger.warning(f"  ✗ {test_id} NOT found in dataset")
        else:
            logger.warning("✗ read_object_ids() method not found")

        # Try to get data source description
        if hasattr(camels, 'data_source_description'):
            logger.info("\n✓ Found data_source_description")
            logger.info(f"  {camels.data_source_description}")

    except ImportError as e:
        logger.error(f"✗ Failed to import hydrodataset: {str(e)}")
    except Exception as e:
        logger.error(f"✗ Error testing hydrodataset: {str(e)}", exc_info=True)


def test_basin_validator():
    """Test BasinValidator class."""
    logger.info("\n=== Testing BasinValidator ===")

    try:
        from hydroagent.utils.basin_validator import BasinValidator, validate_basin_id, get_validation_info

        # Create validator
        validator = BasinValidator()
        logger.info("✓ Created BasinValidator instance")

        # Get validation info
        info = get_validation_info()
        logger.info(f"\nValidation Info:")
        logger.info(f"  Data source: {info.get('data_source')}")
        logger.info(f"  Hydrodataset available: {info.get('hydrodataset_available')}")
        logger.info(f"  Validation method: {info.get('validation_method')}")
        if 'total_basins' in info:
            logger.info(f"  Total basins: {info.get('total_basins')}")
            logger.info(f"  Sample basins: {info.get('sample_basins')}")

        # Test valid basin IDs
        logger.info("\n--- Testing Valid Basin IDs ---")
        valid_ids = ['01013500', '11532500', '12025000', '14301000', '14306500', '14325000']
        for basin_id in valid_ids:
            is_valid, error_msg = validate_basin_id(basin_id)
            if is_valid:
                logger.info(f"  ✓ {basin_id}: VALID")
            else:
                logger.error(f"  ✗ {basin_id}: INVALID - {error_msg}")

        # Test invalid basin IDs
        logger.info("\n--- Testing Invalid Basin IDs ---")
        invalid_ids = ['99999999', '123', 'invalid', '00000000']
        for basin_id in invalid_ids:
            is_valid, error_msg = validate_basin_id(basin_id)
            if not is_valid:
                logger.info(f"  ✓ {basin_id}: Correctly rejected")
                logger.info(f"    Error: {error_msg}")
            else:
                logger.warning(f"  ✗ {basin_id}: Should have been rejected but was accepted")

    except Exception as e:
        logger.error(f"✗ Error testing BasinValidator: {str(e)}", exc_info=True)


if __name__ == "__main__":
    # First test hydrodataset API
    test_hydrodataset_api()

    # Then test our validator
    test_basin_validator()

    logger.info("\n=== Test Complete ===")
