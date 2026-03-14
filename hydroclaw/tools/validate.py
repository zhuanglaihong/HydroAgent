"""
Author: HydroClaw Team
Date: 2026-03-06
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
        basin_ids: CAMELS basin ID list, e.g. ["12025000"]
        train_period: Training period ["YYYY-MM-DD", "YYYY-MM-DD"]
        test_period: Testing period ["YYYY-MM-DD", "YYYY-MM-DD"]
        data_source: Dataset name, default "camels_us"

    Returns:
        {"valid": bool, "valid_basins": [...], "invalid_basins": [...], "warnings": [...]}
    """
    from hydroclaw.utils.basin_validator import validate_basin_list, validate_time_range

    defaults = (_cfg or {}).get("defaults", {})
    # Normalize selfmade alias
    if data_source.lower() in ("selfmade",):
        data_source = "selfmadehydrodataset"
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

    # Expose data_path and dataset metadata so downstream tools (e.g. generate_code)
    # have everything they need to read data correctly without guessing.
    from hydroclaw.utils.basin_validator import (
        _dataset_dir, _DATASET_CLASS_MAP, _has_hydrodataset,
        _has_hydrodatasource, _selfmade_data_path, _selfmade_dataset_name,
    )
    if data_source.lower() in ("selfmade", "selfmadehydrodataset"):
        data_path = str(_selfmade_data_path) if _selfmade_data_path else None
    else:
        data_path = str(_dataset_dir) if _dataset_dir else None
    dataset_info = _probe_dataset_info(
        data_source, _dataset_dir, _has_hydrodataset, _DATASET_CLASS_MAP,
        selfmade_data_path=_selfmade_data_path,
        selfmade_dataset_name=_selfmade_dataset_name,
        has_hydrodatasource=_has_hydrodatasource,
    )

    result = {
        "valid": all_valid or len(valid_basins) > 0,
        "valid_basins": valid_basins,
        "invalid_basins": invalid_basins,
        "warnings": warnings,
        "train_period": train_period,
        "test_period": test_period,
        "data_path": data_path,
        **dataset_info,
    }

    logger.info(
        f"Validation: {len(valid_basins)}/{len(basin_ids)} valid, "
        f"{len(warnings)} warnings"
    )
    return result


validate_basin.__agent_hint__ = (
    "Returns data_path, available_variables, full_time_range, read_api_note. "
    "Pass data_path+available_variables+full_time_range to generate_code. "
    "If data_path=None, use ask_user to get the dataset directory."
)


def _probe_dataset_info(data_source: str, dataset_dir, has_hydrodataset: bool, class_map: dict,
                        selfmade_data_path=None, selfmade_dataset_name=None,
                        has_hydrodatasource=False) -> dict:
    """Query the dataset object for metadata useful to code generation.

    Returns a dict with keys:
      available_variables  - list of readable variable names
      full_time_range      - ["YYYY-MM-DD", "YYYY-MM-DD"] full available period
      time_resolution      - "daily" / "hourly" / unknown
      read_api_note        - one-line reminder of the correct read call
    """
    info: dict = {
        "available_variables": None,
        "full_time_range": None,
        "time_resolution": "daily",
        "read_api_note": (
            "Use ds.read_ts_xrdataset(gage_id_lst=[...], t_range=[start, end], var_lst=[...]). "
            "t_range is REQUIRED — omitting it triggers a full cache rebuild and may fail."
        ),
    }
    # selfmade datasets: probe via SelfMadeHydroDataset
    if data_source.lower() in ("selfmade", "selfmadehydrodataset"):
        if has_hydrodatasource and selfmade_data_path and selfmade_dataset_name:
            try:
                from hydrodatasource.reader.data_source import SelfMadeHydroDataset
                ds = SelfMadeHydroDataset(
                    data_path=selfmade_data_path,
                    dataset_name=selfmade_dataset_name,
                    time_unit=["1D"],
                )
                if hasattr(ds, "read_object_ids"):
                    basin_ids = ds.read_object_ids()
                    if basin_ids is not None:
                        info["available_basins"] = [str(b) for b in basin_ids]
                # Attempt to detect variables from units_info.json
                import json
                from pathlib import Path
                units_file = Path(selfmade_data_path) / selfmade_dataset_name / "timeseries" / "1D_units_info.json"
                if units_file.exists():
                    units = json.loads(units_file.read_text(encoding="utf-8"))
                    info["available_variables"] = list(units.keys())
                info["read_api_note"] = (
                    "Use SelfMadeHydroDataset(data_path, dataset_name, time_unit=['1D']). "
                    "Then reader.read_ts_xrdataset(gage_id_lst=[...], t_range=[start,end], "
                    "var_lst=[...], time_units=['1D'])."
                )
            except Exception as e:
                logger.debug("selfmade _probe_dataset_info failed: %s", e)
        return info

    if not has_hydrodataset or not dataset_dir:
        return info

    entry = class_map.get(data_source.lower())
    if entry is None:
        return info

    mod_name, cls_name = entry
    try:
        import importlib
        mod = importlib.import_module(mod_name)
        cls = getattr(mod, cls_name, None)
        if cls is None:
            return info
        ds = cls(data_path=dataset_dir)

        if hasattr(ds, "_dynamic_variable_mapping") and ds._dynamic_variable_mapping:
            info["available_variables"] = list(ds._dynamic_variable_mapping.keys())

        if hasattr(ds, "default_t_range") and ds.default_t_range:
            info["full_time_range"] = ds.default_t_range

    except Exception as e:
        logger.debug("_probe_dataset_info failed for %s: %s", data_source, e)

    return info
