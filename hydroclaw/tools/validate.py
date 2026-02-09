"""
Author: HydroClaw Team
Date: 2026-02-08
Description: Basin data validation tool.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def validate_basin(
    basin_ids: list[str],
    train_period: list[str] | None = None,
    test_period: list[str] | None = None,
    data_source: str = "camels_us",
    _workspace: Path | None = None,
    _cfg: dict | None = None,
) -> dict:
    """Validate basin IDs and time ranges against the CAMELS dataset.

    Args:
        basin_ids: CAMELS basin ID list, e.g. ["01013500"]
        train_period: Training period ["YYYY-MM-DD", "YYYY-MM-DD"]
        test_period: Testing period ["YYYY-MM-DD", "YYYY-MM-DD"]
        data_source: Dataset name, default "camels_us"

    Returns:
        {"valid": bool, "valid_basins": [...], "invalid_basins": [...], "warnings": [...]}
    """
    from hydroclaw.utils.basin_validator import validate_basin_list, validate_time_range

    defaults = (_cfg or {}).get("defaults", {})
    train_period = train_period or defaults.get("train_period", ["2000-01-01", "2009-12-31"])
    test_period = test_period or defaults.get("test_period", ["2010-01-01", "2014-12-31"])

    valid_basins = []
    invalid_basins = []
    warnings = []

    # Validate each basin ID
    for bid in basin_ids:
        is_valid, err = validate_basin_list([bid], data_source)
        if is_valid:
            valid_basins.append(bid)
        else:
            invalid_basins.append({"basin_id": bid, "reason": err[0] if err else "Unknown"})

    # Validate time ranges
    ok, err = validate_time_range(train_period, data_source)
    if not ok:
        warnings.append(f"Training period issue: {err}")

    if test_period:
        ok, err = validate_time_range(test_period, data_source)
        if not ok:
            warnings.append(f"Test period issue: {err}")

    all_valid = len(invalid_basins) == 0 and len(warnings) == 0

    result = {
        "valid": all_valid or len(valid_basins) > 0,
        "valid_basins": valid_basins,
        "invalid_basins": invalid_basins,
        "warnings": warnings,
        "train_period": train_period,
        "test_period": test_period,
    }

    logger.info(
        f"Validation: {len(valid_basins)}/{len(basin_ids)} valid, "
        f"{len(warnings)} warnings"
    )
    return result
