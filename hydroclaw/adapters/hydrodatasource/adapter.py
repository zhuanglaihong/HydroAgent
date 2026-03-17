"""
HydroDataSourceAdapter: wraps the hydrodatasource Python package.

Handles custom/selfmade datasets: listing basins, reading attributes/
timeseries, and converting raw CSV files to NetCDF cache.

Operations:
    list_basins    -- read_object_ids() from SelfMadeHydroDataset
    read_data      -- read_attributes or read_timeseries
    convert_to_nc  -- cache_attributes_xrdataset + cache_timeseries_xrdataset
"""

import logging
from pathlib import Path

from hydroclaw.adapters.base import PackageAdapter

logger = logging.getLogger(__name__)


class Adapter(PackageAdapter):
    name = "hydrodatasource"
    priority = 15  # higher than hydromodel (10); handles selfmade/custom first

    def can_handle(self, data_source: str, model_name: str) -> bool:
        return data_source in ("selfmade", "custom")

    def supported_operations(self) -> list[str]:
        return ["list_basins", "read_data", "convert_to_nc"]

    # ── list_basins ──────────────────────────────────────────────────

    def list_basins(self, workspace: Path, **kw) -> dict:
        """Return all basin IDs in a custom dataset."""
        data_path = kw.get("data_path", "")
        dataset_name = kw.get("dataset_name", "")
        time_unit = kw.get("time_unit", "1D")

        try:
            from hydrodatasource.reader.data_source import SelfMadeHydroDataset
        except ImportError:
            return {
                "success": False,
                "error": "hydrodatasource is not installed. Run: pip install hydrodatasource",
            }

        if not data_path:
            return {"success": False, "error": "data_path is required"}
        if not dataset_name:
            return {"success": False, "error": "dataset_name is required"}

        try:
            ds = SelfMadeHydroDataset(
                data_path=str(data_path),
                dataset_name=dataset_name,
                time_unit=[time_unit],
            )
            ids = ds.read_object_ids()
            basin_ids = ids.tolist() if hasattr(ids, "tolist") else list(ids)
            return {
                "success": True,
                "basin_ids": basin_ids,
                "count": len(basin_ids),
                "dataset_name": dataset_name,
            }
        except Exception as exc:
            import traceback
            logger.error("[hydrodatasource] list_basins failed:\n%s", traceback.format_exc())
            return {"success": False, "error": str(exc)}

    # ── read_data ────────────────────────────────────────────────────

    def read_data(self, workspace: Path, **kw) -> dict:
        """Read attributes or timeseries from a custom dataset.

        kw:
            data_path     -- path to dataset root
            dataset_name  -- dataset identifier
            time_unit     -- "1D" (default)
            mode          -- "attributes" (default) or "timeseries"
            basin_ids     -- list of basin IDs; None = all basins
            t_range_list  -- [[start, end]] for timeseries mode
        """
        data_path = kw.get("data_path", "")
        dataset_name = kw.get("dataset_name", "")
        time_unit = kw.get("time_unit", "1D")
        mode = kw.get("mode", "attributes")
        basin_ids = kw.get("basin_ids")
        t_range_list = kw.get("t_range_list")

        try:
            from hydrodatasource.reader.data_source import SelfMadeHydroDataset
        except ImportError:
            return {
                "success": False,
                "error": "hydrodatasource is not installed. Run: pip install hydrodatasource",
            }

        if not data_path or not dataset_name:
            return {"success": False, "error": "data_path and dataset_name are required"}

        try:
            ds = SelfMadeHydroDataset(
                data_path=str(data_path),
                dataset_name=dataset_name,
                time_unit=[time_unit],
            )
            if mode == "timeseries":
                result = ds.read_timeseries(
                    object_ids=basin_ids,
                    t_range_list=t_range_list,
                )
                return {"success": True, "mode": "timeseries", "data_keys": list(result.keys())}
            else:
                result = ds.read_attributes(object_ids=basin_ids)
                shape = result.shape if hasattr(result, "shape") else None
                return {
                    "success": True,
                    "mode": "attributes",
                    "shape": list(shape) if shape is not None else None,
                }
        except Exception as exc:
            import traceback
            logger.error("[hydrodatasource] read_data failed:\n%s", traceback.format_exc())
            return {"success": False, "error": str(exc)}

    # ── convert_to_nc ────────────────────────────────────────────────

    def convert_to_nc(self, workspace: Path, **kw) -> dict:
        """Convert raw CSV files to NetCDF cache for faster access.

        kw:
            data_path     -- path to dataset root
            dataset_name  -- dataset identifier
            time_unit     -- "1D" (default)
        """
        data_path = kw.get("data_path", "")
        dataset_name = kw.get("dataset_name", "")
        time_unit = kw.get("time_unit", "1D")

        try:
            from hydrodatasource.reader.data_source import SelfMadeHydroDataset
        except ImportError:
            return {
                "success": False,
                "error": "hydrodatasource is not installed. Run: pip install hydrodatasource",
            }

        if not data_path or not dataset_name:
            return {"success": False, "error": "data_path and dataset_name are required"}

        try:
            ds = SelfMadeHydroDataset(
                data_path=str(data_path),
                dataset_name=dataset_name,
                time_unit=[time_unit],
            )
            logger.info("[hydrodatasource] caching attributes for %s ...", dataset_name)
            ds.cache_attributes_xrdataset()
            logger.info("[hydrodatasource] caching timeseries for %s ...", dataset_name)
            ds.cache_timeseries_xrdataset()
            logger.info("[hydrodatasource] NC conversion complete for %s", dataset_name)
            return {
                "success": True,
                "dataset_name": dataset_name,
                "message": f"NetCDF cache created for dataset '{dataset_name}'",
            }
        except Exception as exc:
            import traceback
            logger.error("[hydrodatasource] convert_to_nc failed:\n%s", traceback.format_exc())
            return {"success": False, "error": str(exc)}
