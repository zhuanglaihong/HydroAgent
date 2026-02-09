"""
Author: HydroClaw Team
Date: 2026-02-08
Description: Basin ID and time range validation utilities.
             Reuses logic from HydroAgent's basin_validator.
"""

import logging
import re
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

_dataset_dir = None
_camels_class = None
_has_hydrodataset = False

# Initialize on import
try:
    from configs import definitions
    _dataset_dir = getattr(definitions, "DATASET_DIR", None)
except ImportError:
    pass

try:
    from hydrodataset import CamelsUs
    _camels_class = CamelsUs
    _has_hydrodataset = True
except ImportError:
    pass


@lru_cache(maxsize=1)
def _get_basin_ids() -> set[str] | None:
    """Get all available CAMELS-US basin IDs."""
    if not _has_hydrodataset or not _camels_class or not _dataset_dir:
        return None
    try:
        camels = _camels_class(data_path=_dataset_dir)
        if hasattr(camels, "read_object_ids"):
            return {str(bid) for bid in camels.read_object_ids()}
    except Exception as e:
        logger.warning(f"Failed to load basin IDs: {e}")
    return None


def validate_basin_list(
    basin_ids: list[str], data_source: str = "camels_us"
) -> tuple[bool, list[str]]:
    """Validate a list of basin IDs.

    Returns:
        (all_valid, error_messages)
    """
    errors = []
    for bid in basin_ids:
        ok, err = validate_basin_id(bid, data_source)
        if not ok and err:
            errors.append(err)
    return len(errors) == 0, errors


def validate_basin_id(
    basin_id: str, data_source: str = "camels_us"
) -> tuple[bool, Optional[str]]:
    """Validate a single basin ID."""
    if not isinstance(basin_id, str):
        return False, f"Basin ID must be string, got {type(basin_id).__name__}"

    if not re.match(r"^\d{8}$", basin_id):
        return False, f"Basin ID format error: {basin_id}. Must be 8 digits (e.g., 01013500)"

    if data_source.lower() == "camels_us" and _has_hydrodataset:
        available = _get_basin_ids()
        if available and basin_id not in available:
            similar = sorted([b for b in available if b[:4] == basin_id[:4]])[:5]
            msg = f"Basin '{basin_id}' not in CAMELS-US ({len(available)} basins)."
            if similar:
                msg += f" Similar: {', '.join(similar)}"
            return False, msg

    return True, None


def validate_time_range(
    time_range: list[str], data_source: str = "camels_us"
) -> tuple[bool, Optional[str]]:
    """Validate a time range [start, end]."""
    if not isinstance(time_range, list) or len(time_range) != 2:
        return False, "Time range must be [start_date, end_date]"

    start, end = time_range
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", start) or not re.match(r"^\d{4}-\d{2}-\d{2}$", end):
        return False, "Date format must be YYYY-MM-DD"

    if start >= end:
        return False, f"Start date must be before end date: {start} >= {end}"

    return True, None
