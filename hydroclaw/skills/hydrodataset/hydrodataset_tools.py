"""
Author: HydroClaw Team
Date: 2026-03-17
Description: hydrodataset query tools - list basins and check data availability
             for CAMELS-family datasets (US/GB/BR/AUS/CL/DE/FR).
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def list_camels_basins(
    data_source: str = "camels_us",
    _workspace: Path | None = None,
    _cfg: dict | None = None,
) -> dict:
    """List all available basin IDs in a CAMELS-family dataset.

    Args:
        data_source: Dataset identifier, e.g. "camels_us", "camels_gb", "camels_br"

    Returns:
        {"success": True, "basin_ids": [...], "count": N, "data_source": "..."}
    """
    try:
        from hydrodataset import Camels, CamelsUs
    except ImportError:
        return {"success": False, "error": "hydrodataset is not installed"}

    try:
        data_path = _resolve_data_path(data_source, _cfg)
        if not data_path:
            return {
                "success": False,
                "error": (
                    f"Data path for '{data_source}' not found in config. "
                    "Set DATASET_DIR in configs/definitions_private.py or add via the Datasets panel."
                ),
            }
        region = _source_to_region(data_source)
        ds = Camels(data_path=str(data_path), region=region)
        ids = ds.read_object_ids()
        basin_ids = ids.tolist() if hasattr(ids, "tolist") else list(ids)
        return {
            "success": True,
            "data_source": data_source,
            "basin_ids": basin_ids,
            "count": len(basin_ids),
        }
    except Exception as exc:
        import traceback
        logger.error("[hydrodataset] list_camels_basins failed:\n%s", traceback.format_exc())
        return {"success": False, "error": str(exc)}


def check_camels_data(
    basin_ids: list[str],
    data_source: str = "camels_us",
    _workspace: Path | None = None,
    _cfg: dict | None = None,
) -> dict:
    """Check whether the CAMELS dataset is locally available and ready for given basins.

    Args:
        basin_ids: List of basin IDs to check, e.g. ["01010000", "02010000"]
        data_source: Dataset identifier, e.g. "camels_us", "camels_gb"

    Returns:
        {"success": True, "data_source": "...", "is_ready": bool,
         "data_path": "...", "basin_count": N}
    """
    try:
        from hydrodataset import Camels
    except ImportError:
        return {"success": False, "error": "hydrodataset is not installed"}

    try:
        data_path = _resolve_data_path(data_source, _cfg)
        if not data_path:
            return {
                "success": True,
                "is_ready": False,
                "data_source": data_source,
                "data_path": None,
                "message": (
                    f"Data path for '{data_source}' not configured. "
                    "Set DATASET_DIR in configs/definitions_private.py."
                ),
            }
        region = _source_to_region(data_source)
        ds = Camels(data_path=str(data_path), region=region)
        is_ready = ds.is_data_ready()
        all_ids = ds.read_object_ids().tolist()
        missing = [b for b in basin_ids if b not in all_ids]
        return {
            "success": True,
            "data_source": data_source,
            "data_path": str(data_path),
            "is_ready": bool(is_ready),
            "basin_count": len(all_ids),
            "requested_basins": len(basin_ids),
            "missing_basins": missing,
        }
    except Exception as exc:
        import traceback
        logger.error("[hydrodataset] check_camels_data failed:\n%s", traceback.format_exc())
        return {"success": False, "error": str(exc)}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _resolve_data_path(data_source: str, cfg: dict | None) -> Path | None:
    """Look up data path from cfg or config module."""
    if cfg and "dataset_dir" in cfg:
        return Path(cfg["dataset_dir"])
    try:
        from hydroclaw.config import get_config
        c = get_config()
        p = c.get("dataset_dir") or c.get("DATASET_DIR")
        if p:
            return Path(p)
    except Exception:
        pass
    try:
        from configs.definitions_private import DATASET_DIR
        return Path(DATASET_DIR)
    except Exception:
        pass
    return None


def _source_to_region(data_source: str) -> str:
    """Map data_source string to hydrodataset region code."""
    mapping = {
        "camels_us": "US", "camels_gb": "GB", "camels_br": "BR",
        "camels_aus": "AUS", "camels_cl": "CL", "camels_de": "DE",
        "camels_fr": "FR",
    }
    return mapping.get(data_source.lower(), "US")


# Chinese metadata for Web UI
list_camels_basins.__zh_name__ = "列出 CAMELS 流域"
list_camels_basins.__zh_desc__ = "列出指定 CAMELS 数据集中所有可用流域的 ID"

check_camels_data.__zh_name__ = "检查数据可用性"
check_camels_data.__zh_desc__ = "验证 CAMELS 数据集是否已下载到本地、指定流域是否存在"
