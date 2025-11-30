"""
Author: Claude
Date: 2025-01-27 10:35:00
LastEditTime: 2025-01-27 11:00:00
LastEditors: Claude
Description: Data loading utilities for DeveloperAgent
             从实验结果目录提取指标数据供后处理分析
FilePath: /HydroAgent/hydroagent/utils/data_loader.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

核心功能：
1. 从session目录中提取所有任务的指标数据
2. 支持不同实验类型（重复率定、多流域、迭代优化等）
3. 返回结构化数据供DeveloperAgent的LLM分析
"""

from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import json
import logging
import pandas as pd

logger = logging.getLogger(__name__)


class DataLoader:
    """
    数据加载器 - 从实验结果目录提取指标数据

    设计原则：
    1. 清晰地从session目录中提取所有任务的指标数据
    2. 不做分析判断，只做数据加载和整理
    3. 返回标准化的数据结构供LLM分析

    核心方法：
    - extract_metrics_from_session(): 从session目录提取所有指标
    - load_repeated_calibration_data(): 加载重复率定数据
    - load_multi_basin_data(): 加载多流域数据
    - load_iterative_calibration_data(): 加载迭代率定数据
    """

    @staticmethod
    def _extract_metrics_and_params(result_data: Dict[str, Any]) -> Tuple[Dict, Dict]:
        """
        从calibration_results.json中提取指标和参数（兼容两种结构）

        支持的结构：
        1. 扁平结构：{"metrics": {...}, "best_params": {...}}
        2. 嵌套结构：{"14301000": {"best_params": {"xaj": {...}}, "metrics": {...}}}

        Args:
            result_data: JSON数据

        Returns:
            (metrics, best_params) 元组
        """
        # 方式1：扁平结构（优先）
        if "metrics" in result_data or "best_params" in result_data:
            metrics = result_data.get("metrics", {})
            best_params = result_data.get("best_params", {})
            return metrics, best_params

        # 方式2：嵌套结构（流域ID包裹）
        # 查找第一个流域数据（通常只有一个流域）
        for key, value in result_data.items():
            if isinstance(value, dict):
                # 尝试提取指标
                metrics = value.get("metrics", {})

                # 提取参数（可能嵌套在模型名下，如 {"xaj": {...}}）
                best_params_raw = value.get("best_params", {})

                # 如果best_params嵌套了一层模型名，展平它
                if best_params_raw and len(best_params_raw) == 1:
                    model_name = list(best_params_raw.keys())[0]
                    if isinstance(best_params_raw[model_name], dict):
                        best_params = best_params_raw[model_name]
                    else:
                        best_params = best_params_raw
                else:
                    best_params = best_params_raw

                logger.debug(f"[DataLoader] 从嵌套结构提取数据 (流域: {key})")
                return metrics, best_params

        # 如果都没有找到，返回空字典
        logger.warning("[DataLoader] 未找到metrics或best_params")
        return {}, {}

    @staticmethod
    def extract_metrics_from_session(
        session_dir: Path, metrics_to_extract: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        从session目录中提取所有任务的指标数据

        这是核心方法，会遍历session目录下的所有task目录，
        提取calibration_results.json和basins_metrics.csv中的指标。

        Args:
            session_dir: 会话目录
            metrics_to_extract: 要提取的指标列表，None表示提取所有

        Returns:
            {
                "tasks": {
                    "task_1": {
                        "metrics": {"NSE": 0.68, "RMSE": 1.2, ...},
                        "best_params": {"x1": 350.0, ...}
                    },
                    "task_2": {...},
                    ...
                },
                "summary": {
                    "total_tasks": 20,
                    "successful_tasks": 18,
                    "failed_tasks": 2,
                    "metrics_matrix": DataFrame
                }
            }
        """
        from hydroagent.utils.path_manager import PathManager
        from configs import config

        if metrics_to_extract is None:
            metrics_to_extract = config.POST_ANALYSIS_METRICS

        tasks_data = {}
        all_metrics = []

        # 遍历session目录下的所有子目录，只处理以"task_"开头的任务目录
        # 使用自然排序（按任务编号排序）
        task_dirs = [
            d
            for d in session_dir.iterdir()
            if d.is_dir() and d.name.startswith("task_")
        ]

        # 自然排序：提取task_后的数字部分进行排序
        def natural_sort_key(path):
            task_name = path.name
            # 提取task_后的部分，分离数字和文本
            parts = task_name.replace("task_", "").split("_")
            try:
                # 第一部分是数字
                return (int(parts[0]), task_name)
            except (ValueError, IndexError):
                # 如果不是数字，使用字符串排序
                return (float("inf"), task_name)

        for task_dir in sorted(task_dirs, key=natural_sort_key):
            task_id = task_dir.name

            # 查找calibration_results.json
            calib_result_file = PathManager.find_calibration_results(task_dir)

            if calib_result_file:
                try:
                    with open(calib_result_file, "r", encoding="utf-8") as f:
                        result_data = json.load(f)

                    # 提取指标和参数（兼容两种结构）
                    metrics, best_params = DataLoader._extract_metrics_and_params(
                        result_data
                    )

                    # 如果calibration_results.json没有metrics，尝试从basins_metrics.csv加载
                    if not metrics:
                        metrics_csv = task_dir / "basins_metrics.csv"
                        if metrics_csv.exists():
                            try:
                                df = pd.read_csv(metrics_csv, index_col=0)
                                if not df.empty:
                                    # 取第一行数据（通常只有一个流域）
                                    metrics = df.iloc[0].to_dict()
                                    logger.debug(
                                        f"[DataLoader] 从basins_metrics.csv加载指标: {task_id}"
                                    )
                            except Exception as csv_e:
                                logger.warning(
                                    f"[DataLoader] 无法读取basins_metrics.csv: {csv_e}"
                                )

                    filtered_metrics = {
                        k: v
                        for k, v in metrics.items()
                        if k in metrics_to_extract or not metrics_to_extract
                    }

                    tasks_data[task_id] = {
                        "metrics": filtered_metrics,
                        "best_params": best_params,
                        "result_file": str(calib_result_file),
                        "status": "success",
                    }

                    # 记录到矩阵（用于后续分析）
                    metric_row = {"task_id": task_id, **filtered_metrics}
                    all_metrics.append(metric_row)

                    logger.debug(f"[DataLoader] Loaded metrics from {task_id}")

                except Exception as e:
                    logger.warning(
                        f"[DataLoader] Failed to load {calib_result_file}: {e}"
                    )
                    tasks_data[task_id] = {"status": "failed", "error": str(e)}
            else:
                logger.debug(f"[DataLoader] No calibration results found in {task_dir}")
                tasks_data[task_id] = {"status": "no_results"}

        # 创建metrics矩阵（DataFrame）
        metrics_df = pd.DataFrame(all_metrics) if all_metrics else pd.DataFrame()

        summary = {
            "total_tasks": len(tasks_data),
            "successful_tasks": sum(
                1 for t in tasks_data.values() if t.get("status") == "success"
            ),
            "failed_tasks": sum(
                1 for t in tasks_data.values() if t.get("status") == "failed"
            ),
            "no_results_tasks": sum(
                1 for t in tasks_data.values() if t.get("status") == "no_results"
            ),
            "metrics_matrix": metrics_df,
        }

        logger.info(
            f"[DataLoader] Extracted metrics from {summary['successful_tasks']}/{summary['total_tasks']} tasks"
        )

        return {"tasks": tasks_data, "summary": summary}

    @staticmethod
    def load_repeated_calibration_data(
        workspace_dir: Path, n_repeats: int
    ) -> Dict[str, Any]:
        """
        加载重复率定实验的数据（基于extract_metrics_from_session）

        Args:
            workspace_dir: 工作目录
            n_repeats: 重复次数

        Returns:
            数据字典:
            {
                "task_type": "repeated_calibration",
                "n_repeats": 20,
                "found_count": 18,
                "metrics": {
                    "NSE": [0.68, 0.69, 0.67, ...],
                    "RMSE": [1.2, 1.3, 1.1, ...]
                },
                "parameters": {
                    "x1": [350.0, 352.1, 348.5, ...],
                    ...
                },
                "task_ids": [1, 2, 3, ...]
            }
        """
        # 使用通用方法提取数据
        session_data = DataLoader.extract_metrics_from_session(workspace_dir)

        # 过滤重复率定的任务（task_*_repeat）
        metrics_data = {}
        params_data = {}
        task_ids = []

        for task_id, task_info in session_data["tasks"].items():
            if "repeat" not in task_id or task_info.get("status") != "success":
                continue

            # 提取任务编号（task_3_repeat -> 3）
            try:
                task_num = int(task_id.split("_")[1])
                task_ids.append(task_num)
            except (IndexError, ValueError):
                logger.warning(f"[DataLoader] Cannot parse task number from {task_id}")
                continue

            # 提取指标
            for metric_name, metric_value in task_info["metrics"].items():
                if metric_name not in metrics_data:
                    metrics_data[metric_name] = []
                metrics_data[metric_name].append(metric_value)

            # 提取参数
            for param_name, param_value in task_info["best_params"].items():
                if param_name not in params_data:
                    params_data[param_name] = []
                params_data[param_name].append(param_value)

        return {
            "task_type": "repeated_calibration",
            "n_repeats": n_repeats,
            "found_count": len(task_ids),
            "metrics": metrics_data,
            "parameters": params_data,
            "task_ids": sorted(task_ids),
            "session_data": session_data,  # 完整数据供调试
        }

    @staticmethod
    def load_multi_basin_data(
        workspace_dir: Path, basin_ids: List[str]
    ) -> Dict[str, Any]:
        """
        加载多流域实验数据

        Args:
            workspace_dir: 工作目录
            basin_ids: 流域ID列表

        Returns:
            数据字典
        """
        data = {"task_type": "multi_basin", "basins": {}, "metrics_summary": {}}

        for i, basin_id in enumerate(basin_ids, 1):
            task_id = f"task_{i}"
            from hydroagent.utils.path_manager import PathManager

            paths = PathManager.get_standard_paths(workspace_dir, task_id)

            if paths["calibration_results"] and paths["calibration_results"].exists():
                with open(paths["calibration_results"], "r") as f:
                    result = json.load(f)

                data["basins"][basin_id] = {
                    "metrics": result.get("metrics", {}),
                    "best_params": result.get("best_params", {}),
                }

        return data

    @staticmethod
    def load_iterative_calibration_data(
        workspace_dir: Path, n_iterations: int
    ) -> Dict[str, Any]:
        """
        加载迭代率定数据

        Args:
            workspace_dir: 工作目录
            n_iterations: 迭代次数

        Returns:
            数据字典
        """
        data = {
            "task_type": "iterative_calibration",
            "iterations": [],
            "metrics_progression": {},
            "parameter_progression": {},
        }

        for i in range(n_iterations):
            task_id = f"calibration_iter{i}"
            from hydroagent.utils.path_manager import PathManager

            paths = PathManager.get_standard_paths(workspace_dir, task_id)

            if paths["calibration_results"] and paths["calibration_results"].exists():
                with open(paths["calibration_results"], "r") as f:
                    result = json.load(f)

                iter_data = {
                    "iteration": i,
                    "metrics": result.get("metrics", {}),
                    "best_params": result.get("best_params", {}),
                }
                data["iterations"].append(iter_data)

                # 收集指标演变
                for metric_name, metric_value in iter_data["metrics"].items():
                    if metric_name not in data["metrics_progression"]:
                        data["metrics_progression"][metric_name] = []
                    data["metrics_progression"][metric_name].append(metric_value)

                # 收集参数演变
                for param_name, param_value in iter_data["best_params"].items():
                    if param_name not in data["parameter_progression"]:
                        data["parameter_progression"][param_name] = []
                    data["parameter_progression"][param_name].append(param_value)

        return data

    @staticmethod
    def summarize_data_for_llm(data: Dict[str, Any]) -> str:
        """
        将数据总结为LLM可读的文本

        Args:
            data: 数据字典

        Returns:
            文本摘要
        """
        import numpy as np

        task_type = data.get("task_type", "unknown")
        summary_lines = [f"Task Type: {task_type}", ""]

        if task_type == "repeated_calibration":
            summary_lines.append(
                f"Repetitions: {data['found_count']}/{data['n_repeats']}"
            )
            summary_lines.append("\nMetrics Statistics:")

            for metric_name, values in data.get("metrics", {}).items():
                mean_val = np.mean(values)
                std_val = np.std(values)
                min_val = np.min(values)
                max_val = np.max(values)
                cv = std_val / mean_val if mean_val != 0 else 0

                summary_lines.append(
                    f"  {metric_name}: mean={mean_val:.4f}, std={std_val:.4f}, "
                    f"min={min_val:.4f}, max={max_val:.4f}, CV={cv:.4f}"
                )

            summary_lines.append("\nParameter Statistics:")
            for param_name, values in data.get("parameters", {}).items():
                mean_val = np.mean(values)
                std_val = np.std(values)
                summary_lines.append(
                    f"  {param_name}: mean={mean_val:.4f}, std={std_val:.4f}"
                )

        elif task_type == "multi_basin":
            summary_lines.append(f"Number of Basins: {len(data.get('basins', {}))}")
            summary_lines.append("\nBasin Results:")

            for basin_id, basin_data in data.get("basins", {}).items():
                metrics = basin_data.get("metrics", {})
                nse = metrics.get("NSE", "N/A")
                summary_lines.append(f"  {basin_id}: NSE={nse}")

        elif task_type == "iterative_calibration":
            summary_lines.append(
                f"Number of Iterations: {len(data.get('iterations', []))}"
            )
            summary_lines.append("\nMetrics Progression:")

            for metric_name, values in data.get("metrics_progression", {}).items():
                summary_lines.append(
                    f"  {metric_name}: {' → '.join([f'{v:.4f}' for v in values])}"
                )

        return "\n".join(summary_lines)
