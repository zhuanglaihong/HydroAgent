"""
Author: HydroAgent Team
Date: 2025-12-08 21:30:00
LastEditTime: 2025-12-08 21:30:00
LastEditors: HydroAgent Team
Description: Dynamic basin ID validator using actual dataset information
             动态流域ID验证器，使用真实数据集信息进行验证
FilePath: /HydroAgent/hydroagent/utils/basin_validator.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from typing import Optional, List, Set, Dict, Any
import logging
import re
from functools import lru_cache

logger = logging.getLogger(__name__)


class BasinValidator:
    """
    Dynamic basin ID validator using actual dataset information.
    动态流域ID验证器，使用真实数据集信息进行验证。

    Key Features:
    1. Uses hydrodataset to get actual available basin IDs
    2. No hardcoded ranges - checks against real data
    3. Supports multiple datasets (CAMELS-US, CAMELS-CL, etc.)
    4. Provides helpful error messages with suggestions
    5. Caches basin lists for performance
    """

    def __init__(self):
        """Initialize BasinValidator."""
        self._dataset_cache: Dict[str, Set[str]] = {}
        self._has_hydrodataset = False
        self._camels_us_class = None
        self._dataset_dir = None

        # Try to get dataset directory from config
        try:
            from configs import definitions
            self._dataset_dir = definitions.DATASET_DIR
            logger.debug(f"[BasinValidator] Using DATASET_DIR: {self._dataset_dir}")
        except Exception as e:
            logger.warning(f"[BasinValidator] Could not load DATASET_DIR from config: {str(e)}")

        # Try to import hydrodataset
        try:
            from hydrodataset import CamelsUs
            self._camels_us_class = CamelsUs
            self._has_hydrodataset = True
            logger.info("[BasinValidator] hydrodataset module available")
        except ImportError:
            logger.warning("[BasinValidator] hydrodataset not available, using basic format validation")

    @lru_cache(maxsize=1)
    def _get_camels_us_basin_ids(self) -> Optional[Set[str]]:
        """
        Get all available CAMELS-US basin IDs from hydrodataset.
        获取所有可用的CAMELS-US流域ID。

        Returns:
            Set of basin IDs if successful, None if hydrodataset not available
        """
        if not self._has_hydrodataset or self._camels_us_class is None:
            return None

        if not self._dataset_dir:
            logger.warning("[BasinValidator] DATASET_DIR not configured, cannot load basin IDs")
            return None

        try:
            # Initialize CamelsUs with data_path
            camels = self._camels_us_class(data_path=self._dataset_dir)
            logger.debug("[BasinValidator] Successfully initialized CamelsUs")

            # Try to use read_object_ids() method
            if hasattr(camels, 'read_object_ids'):
                basin_ids_list = camels.read_object_ids()
                # Convert to set of strings
                basin_ids = {str(bid) for bid in basin_ids_list}
                logger.info(f"[BasinValidator] Loaded {len(basin_ids)} CAMELS-US basin IDs from dataset")
                return basin_ids
            else:
                logger.warning("[BasinValidator] CamelsUs object does not have read_object_ids() method")
                return None

        except FileNotFoundError as e:
            logger.warning(f"[BasinValidator] Dataset path not found: {str(e)}")
            return None
        except Exception as e:
            logger.warning(f"[BasinValidator] Failed to load basin IDs from hydrodataset: {str(e)}")
            logger.debug("[BasinValidator] Exception details:", exc_info=True)
            return None

    def validate_basin_id(
        self,
        basin_id: str,
        data_source: str = "camels_us"
    ) -> tuple[bool, Optional[str]]:
        """
        Validate basin ID against actual dataset.
        根据实际数据集验证流域ID。

        Args:
            basin_id: Basin ID to validate
            data_source: Data source name (default: "camels_us")

        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
                - is_valid: Whether the basin ID is valid
                - error_message: Error message if invalid, None otherwise
        """
        # Step 1: Basic format validation (8-digit number)
        if not isinstance(basin_id, str):
            return False, f"流域ID必须是字符串格式，当前类型: {type(basin_id).__name__}"

        if not re.match(r'^\d{8}$', basin_id):
            return False, (
                f"流域ID格式错误: {basin_id}。"
                f"流域ID应为8位数字（如 01013500）"
            )

        # Step 2: Check against actual dataset if available
        if data_source.lower() == "camels_us" and self._has_hydrodataset:
            available_basins = self._get_camels_us_basin_ids()

            if available_basins is not None:
                if basin_id not in available_basins:
                    # Provide helpful error with similar basin IDs
                    similar = self._find_similar_basin_ids(basin_id, available_basins)
                    error_msg = (
                        f"流域ID '{basin_id}' 在 CAMELS-US 数据集中不存在。\n"
                        f"💡 提示: 数据集共有 {len(available_basins)} 个流域。"
                    )
                    if similar:
                        error_msg += f"\n   可能您想找的是: {', '.join(similar[:5])}"

                    return False, error_msg

                # Basin ID exists in dataset
                logger.debug(f"[BasinValidator] Basin ID {basin_id} validated successfully")
                return True, None
            else:
                # Could not load basin list, use basic validation
                logger.warning(
                    f"[BasinValidator] Could not load basin list, "
                    f"using basic format validation for {basin_id}"
                )
                return True, None  # Accept if we can't verify

        # Step 3: Fallback for other data sources or when hydrodataset unavailable
        # Just check format - let hydromodel handle actual data loading errors
        logger.debug(
            f"[BasinValidator] Basic format validation passed for {basin_id} "
            f"(dataset validation unavailable)"
        )
        return True, None

    def _find_similar_basin_ids(
        self,
        target_id: str,
        available_ids: Set[str],
        max_results: int = 5
    ) -> List[str]:
        """
        Find similar basin IDs for helpful error messages.
        查找相似的流域ID，用于提供有用的错误提示。

        Args:
            target_id: Target basin ID
            available_ids: Set of available basin IDs
            max_results: Maximum number of results to return

        Returns:
            List of similar basin IDs
        """
        try:
            # Simple similarity: find IDs that start with same prefix
            prefix_len = min(4, len(target_id))
            prefix = target_id[:prefix_len]

            similar = [
                bid for bid in available_ids
                if bid.startswith(prefix)
            ]

            # Sort and return top results
            return sorted(similar)[:max_results]

        except Exception as e:
            logger.debug(f"[BasinValidator] Error finding similar IDs: {str(e)}")
            return []

    def get_validation_info(self, data_source: str = "camels_us") -> Dict[str, Any]:
        """
        Get information about basin validation for a data source.
        获取数据源的流域验证信息。

        Args:
            data_source: Data source name

        Returns:
            Dictionary with validation information
        """
        info = {
            "data_source": data_source,
            "hydrodataset_available": self._has_hydrodataset,
            "validation_method": "unknown"
        }

        if data_source.lower() == "camels_us" and self._has_hydrodataset:
            available_basins = self._get_camels_us_basin_ids()
            if available_basins is not None:
                info["validation_method"] = "dataset_lookup"
                info["total_basins"] = len(available_basins)
                info["sample_basins"] = sorted(list(available_basins))[:10]
            else:
                info["validation_method"] = "format_only"
        else:
            info["validation_method"] = "format_only"

        return info

    def validate_basin_list(
        self,
        basin_ids: List[str],
        data_source: str = "camels_us"
    ) -> tuple[bool, List[str]]:
        """
        Validate a list of basin IDs.
        验证流域ID列表。

        Args:
            basin_ids: List of basin IDs to validate
            data_source: Data source name

        Returns:
            Tuple[bool, List[str]]: (all_valid, error_messages)
        """
        errors = []

        for basin_id in basin_ids:
            is_valid, error_msg = self.validate_basin_id(basin_id, data_source)
            if not is_valid and error_msg:
                errors.append(error_msg)

        return len(errors) == 0, errors


# Create global validator instance
_validator = BasinValidator()


def validate_basin_id(basin_id: str, data_source: str = "camels_us") -> tuple[bool, Optional[str]]:
    """
    Convenience function: Validate basin ID.
    便捷函数：验证流域ID。

    Args:
        basin_id: Basin ID to validate
        data_source: Data source name

    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    return _validator.validate_basin_id(basin_id, data_source)


def validate_basin_list(basin_ids: List[str], data_source: str = "camels_us") -> tuple[bool, List[str]]:
    """
    Convenience function: Validate list of basin IDs.
    便捷函数：验证流域ID列表。

    Args:
        basin_ids: List of basin IDs
        data_source: Data source name

    Returns:
        Tuple[bool, List[str]]: (all_valid, error_messages)
    """
    return _validator.validate_basin_list(basin_ids, data_source)


def get_validation_info(data_source: str = "camels_us") -> Dict[str, Any]:
    """
    Convenience function: Get validation info.
    便捷函数：获取验证信息。

    Args:
        data_source: Data source name

    Returns:
        Dictionary with validation information
    """
    return _validator.get_validation_info(data_source)
