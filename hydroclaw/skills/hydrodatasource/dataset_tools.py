"""
Author: HydroClaw Team
Date: 2026-03-17
Description: Custom dataset tools - routes to the HydroDataSourceAdapter.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def list_basins(
    data_path: str,
    dataset_name: str,
    time_unit: str = "1D",
    _workspace: Path | None = None,
) -> dict:
    """List all basin IDs in a custom (selfmade) dataset.

    Args:
        data_path: Absolute path to the dataset root directory
        dataset_name: Dataset identifier (used as folder/file name prefix)
        time_unit: Time resolution, e.g. "1D" (daily, default), "1h" (hourly), "3h" (3-hourly), "8D" (8-day)

    Returns:
        {"success": True, "basin_ids": [...], "count": N, "dataset_name": "..."}
    """
    from hydroclaw.adapters import get_adapter

    adapter = get_adapter("selfmade", "")
    return adapter.execute(
        "list_basins",
        workspace=_workspace or Path("."),
        data_path=data_path,
        dataset_name=dataset_name,
        time_unit=time_unit,
    )


def read_dataset(
    data_path: str,
    dataset_name: str,
    mode: str = "attributes",
    basin_ids: list[str] | None = None,
    t_range_list: list | None = None,
    time_unit: str = "1D",
    _workspace: Path | None = None,
) -> dict:
    """Read attributes or timeseries data from a custom dataset.

    Args:
        data_path: Absolute path to the dataset root directory
        dataset_name: Dataset identifier
        mode: "attributes" (static basin properties) or "timeseries" (P/E/Q series)
        basin_ids: List of basin IDs to read; None = all basins
        t_range_list: Time range [[start, end]] for timeseries mode, e.g. [["2000-01-01", "2010-12-31"]]
        time_unit: "1D" (daily, default), "1h" (hourly), "3h" (3-hourly), "8D" (8-day)

    Returns:
        {"success": True, "mode": "...", "shape": [...]} or {"mode": "timeseries", "data_keys": [...]}
    """
    from hydroclaw.adapters import get_adapter

    adapter = get_adapter("selfmade", "")
    return adapter.execute(
        "read_data",
        workspace=_workspace or Path("."),
        data_path=data_path,
        dataset_name=dataset_name,
        mode=mode,
        basin_ids=basin_ids,
        t_range_list=t_range_list,
        time_unit=time_unit,
    )


def convert_dataset_to_nc(
    data_path: str,
    dataset_name: str,
    time_unit: str = "1D",
    _workspace: Path | None = None,
) -> dict:
    """Convert a custom dataset's raw CSV files to NetCDF cache for faster access.

    Run this once before using the dataset for calibration or reading.
    Creates .nc files under the dataset root directory.

    Args:
        data_path: Absolute path to the dataset root directory
        dataset_name: Dataset identifier
        time_unit: "1D" (daily, default), "1h" (hourly), "3h" (3-hourly), "8D" (8-day)

    Returns:
        {"success": True, "dataset_name": "...", "message": "..."}
    """
    from hydroclaw.adapters import get_adapter

    adapter = get_adapter("selfmade", "")
    return adapter.execute(
        "convert_to_nc",
        workspace=_workspace or Path("."),
        data_path=data_path,
        dataset_name=dataset_name,
        time_unit=time_unit,
    )


# Chinese metadata for Web UI
list_basins.__zh_name__ = "列出流域"
list_basins.__zh_desc__ = "列出自定义数据集中所有流域的 ID 列表"

read_dataset.__zh_name__ = "读取数据集"
read_dataset.__zh_desc__ = "读取自定义数据集的属性或时序数据"

convert_dataset_to_nc.__zh_name__ = "转换为 NC"
convert_dataset_to_nc.__zh_desc__ = "将自定义数据集的 CSV 原始文件转换为 NetCDF 缓存，加速后续读取"
