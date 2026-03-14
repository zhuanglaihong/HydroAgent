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
_has_hydrodataset = False
_has_hydrodatasource = False
_selfmade_data_path = None
_selfmade_dataset_name = None

# Initialize on import
try:
    from configs import definitions
    _dataset_dir = getattr(definitions, "DATASET_DIR", None)
except ImportError:
    pass

try:
    from configs import private as _priv
    _selfmade_data_path = getattr(_priv, "SELFMADE_DATA_PATH", None)
    _selfmade_dataset_name = getattr(_priv, "SELFMADE_DATASET_NAME", None)
except ImportError:
    pass

try:
    import hydrodataset  # noqa: F401
    _has_hydrodataset = True
except ImportError:
    pass

try:
    import hydrodatasource  # noqa: F401
    _has_hydrodatasource = True
except ImportError:
    pass

# data_source -> (module, class) mapping，与 hydrodataset examples/read_dataset.py 保持一致
_DATASET_CLASS_MAP = {
    "camels_us":    ("hydrodataset.camels_us",          "CamelsUs"),
    "camels_gb":    ("hydrodataset.camels_gb",          "CamelsGb"),
    "camels_br":    ("hydrodataset.camels_br",          "CamelsBr"),
    "camels_aus":   ("hydrodataset.camels_aus",         "CamelsAus"),
    "camels_cl":    ("hydrodataset.camels_cl",          "CamelsCl"),
    "camels_col":   ("hydrodataset.camels_col",         "CamelsCol"),
    "camels_de":    ("hydrodataset.camels_de",          "CamelsDe"),
    "camels_dk":    ("hydrodataset.camels_dk",          "CamelsDk"),
    "camels_fi":    ("hydrodataset.camels_fi",          "CamelsFi"),
    "camels_fr":    ("hydrodataset.camels_fr",          "CamelsFr"),
    "camels_ch":    ("hydrodataset.camels_ch",          "CamelsCh"),
    "camels_se":    ("hydrodataset.camels_se",          "CamelsSe"),
    "camels_ind":   ("hydrodataset.camels_ind",         "CamelsInd"),
    "camels_lux":   ("hydrodataset.camels_lux",         "CamelsLux"),
    "camels_nz":    ("hydrodataset.camels_nz",          "CamelsNz"),
    "camels_es":    ("hydrodataset.camels_es",          "CamelsEs"),
    "camelsh_kr":   ("hydrodataset.camelsh_kr",         "CamelshKr"),
    "camelsh":      ("hydrodataset.camelsh",            "Camelsh"),
    "caravan":      ("hydrodataset.caravan",            "Caravan"),
    "caravan_dk":   ("hydrodataset.caravan_dk",         "CaravanDK"),
    "grdc_caravan": ("hydrodataset.grdc_caravan",       "GrdcCaravan"),
    "lamah_ce":     ("hydrodataset.lamah_ce",           "LamahCe"),
    "lamah_ice":    ("hydrodataset.lamah_ice",          "LamahIce"),
    "hysets":       ("hydrodataset.hysets",             "Hysets"),
    "estreams":     ("hydrodataset.estreams",           "Estreams"),
    "hype":         ("hydrodataset.hype",               "Hype"),
    "mopex":        ("hydrodataset.mopex",              "Mopex"),
}


@lru_cache(maxsize=8)
def _get_basin_ids(data_source: str = "camels_us") -> set[str] | None:
    """Get all basin IDs for the given data source."""
    ds_key = data_source.lower()

    # selfmade / selfmadehydrodataset -> use hydrodatasource
    if ds_key in ("selfmade", "selfmadehydrodataset"):
        if not _has_hydrodatasource or not _selfmade_data_path or not _selfmade_dataset_name:
            return None
        try:
            from hydrodatasource.reader.data_source import SelfMadeHydroDataset
            ds = SelfMadeHydroDataset(
                data_path=_selfmade_data_path,
                dataset_name=_selfmade_dataset_name,
                time_unit=["1D"],
            )
            return {str(bid) for bid in ds.read_object_ids()}
        except Exception as e:
            logger.warning(f"Failed to load basin IDs for selfmade dataset: {e}")
        return None

    # public datasets -> use hydrodataset
    if not _has_hydrodataset or not _dataset_dir:
        return None
    entry = _DATASET_CLASS_MAP.get(ds_key)
    if entry is None:
        return None
    mod_name, cls_name = entry
    try:
        import importlib
        mod = importlib.import_module(mod_name)
        cls = getattr(mod, cls_name, None)
        if cls is None:
            return None
        ds = cls(data_path=_dataset_dir)
        if hasattr(ds, "read_object_ids"):
            return {str(bid) for bid in ds.read_object_ids()}
    except Exception as e:
        logger.warning(f"Failed to load basin IDs for {data_source}: {e}")
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

    if not basin_id.strip():
        return False, "Basin ID cannot be empty"

    # Try to validate against actual dataset basin list
    if _has_hydrodataset:
        available = _get_basin_ids(data_source.lower())
        if available:
            if basin_id not in available:
                similar = sorted([b for b in available if b[:4] == basin_id[:4]])[:5]
                msg = f"Basin '{basin_id}' not found in {data_source} ({len(available)} basins)."
                if similar:
                    msg += f" Similar: {', '.join(similar)}"
                return False, msg
            return True, None

    # selfmade: no fixed format requirement, accept any non-empty string
    if data_source.lower() in ("selfmade", "selfmadehydrodataset"):
        return True, None

    # Fallback: format-only check (CAMELS-US uses 8-digit IDs)
    if data_source.lower() == "camels_us" and not re.match(r"^\d{8}$", basin_id):
        return False, f"Basin ID format error: '{basin_id}'. CAMELS-US expects 8 digits (e.g., 12025000)"

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
