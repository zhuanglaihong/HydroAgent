"""
Author: Claude
Date: 2025-11-27 09:30:00
LastEditTime: 2025-11-27 09:30:00
LastEditors: Claude
Description: Unified path management for HydroAgent
             Centralizes all path handling logic to avoid nested directories
FilePath: /HydroAgent/hydroagent/utils/path_manager.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from pathlib import Path
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class PathManager:
    """
    统一的路径管理器

    解决问题：
    1. 避免多层嵌套目录（session/task/experiment_name/results）
    2. 统一管理所有输出路径
    3. 简化路径查找逻辑

    路径规范：
    - Session目录：experiment_results/{exp_name}/session_{timestamp}_{uuid}/
    - Task目录：{session_dir}/{task_id}/
    - 结果文件：{task_dir}/calibration_results.json（直接在task目录下，不再嵌套）
    """

    def __init__(self, session_dir: Optional[Path] = None):
        """
        初始化路径管理器

        Args:
            session_dir: 会话根目录（可选）
        """
        self.session_dir = Path(session_dir) if session_dir else None

    @staticmethod
    def get_task_output_dir(session_dir: Path, task_id: str) -> Path:
        """
        获取任务输出目录（标准化）

        Args:
            session_dir: 会话目录
            task_id: 任务ID（如 "task_1", "task_3_repeat"）

        Returns:
            任务输出目录路径

        Example:
            >>> session_dir = Path("experiment_results/exp_2a/session_xxx")
            >>> task_dir = PathManager.get_task_output_dir(session_dir, "task_3_repeat")
            >>> # Returns: experiment_results/exp_2a/session_xxx/task_3_repeat
        """
        return session_dir / task_id

    @staticmethod
    def configure_hydromodel_output(
        config: Dict[str, Any],
        session_dir: Path,
        task_id: str,
        use_flat_structure: bool = True
    ) -> Dict[str, Any]:
        """
        配置 hydromodel 的输出路径（避免嵌套）

        Args:
            config: hydromodel 配置字典
            session_dir: 会话目录
            task_id: 任务ID
            use_flat_structure: 是否使用扁平结构（推荐True，避免嵌套）

        Returns:
            更新后的配置字典

        Implementation:
            如果 use_flat_structure=True:
                - output_dir = session_dir/task_id
                - experiment_name = ""  # 关键：避免 hydromodel 创建子目录
            如果 use_flat_structure=False（兼容旧版）:
                - output_dir = session_dir
                - experiment_name = "{model}_{algorithm}_{task_type}"
        """
        if "training_cfgs" not in config:
            logger.warning("[PathManager] Config missing 'training_cfgs'")
            return config

        if use_flat_structure:
            # 扁平结构：结果直接保存在 task_dir/calibration_results.json
            task_dir = PathManager.get_task_output_dir(session_dir, task_id)
            config["training_cfgs"]["output_dir"] = str(task_dir)
            config["training_cfgs"]["experiment_name"] = ""  # 🔑 关键：空字符串避免嵌套

            logger.info(f"[PathManager] 使用扁平结构: {task_dir}")
            logger.info(f"[PathManager] experiment_name 设置为空（避免嵌套）")
        else:
            # 旧版结构：结果保存在 session_dir/experiment_name/calibration_results.json
            config["training_cfgs"]["output_dir"] = str(session_dir)
            # experiment_name 保持不变（LLM 生成的）

            logger.info(f"[PathManager] 使用旧版结构: {session_dir}/{config['training_cfgs'].get('experiment_name', 'N/A')}")

        return config

    @staticmethod
    def find_calibration_results(task_dir: Path) -> Optional[Path]:
        """
        查找率定结果文件（支持扁平和嵌套两种结构）

        Args:
            task_dir: 任务目录

        Returns:
            calibration_results.json 的路径，如果不存在返回 None

        Search Order:
            1. {task_dir}/calibration_results.json（扁平结构，优先）
            2. {task_dir}/*/calibration_results.json（嵌套结构，向后兼容）
        """
        # 方式1：扁平结构（推荐）
        flat_result = task_dir / "calibration_results.json"
        if flat_result.exists():
            logger.debug(f"[PathManager] Found calibration results (flat): {flat_result}")
            return flat_result

        # 方式2：嵌套结构（向后兼容）
        nested_results = list(task_dir.glob("*/calibration_results.json"))
        if nested_results:
            result = nested_results[0]  # 取第一个匹配
            logger.debug(f"[PathManager] Found calibration results (nested): {result}")
            logger.warning(f"[PathManager] 检测到嵌套结构，建议使用扁平结构（experiment_name=''）")
            return result

        logger.debug(f"[PathManager] No calibration results found in {task_dir}")
        return None

    @staticmethod
    def get_calibration_dir(task_dir: Path) -> Optional[str]:
        """
        获取率定结果目录（包含 calibration_results.json 的目录）

        Args:
            task_dir: 任务目录

        Returns:
            率定结果目录的字符串路径，如果不存在返回 None
        """
        result_file = PathManager.find_calibration_results(task_dir)
        if result_file:
            # 返回包含 calibration_results.json 的目录
            return str(result_file.parent)
        return None

    @staticmethod
    def collect_repeated_calibration_results(
        session_dir: Path,
        n_repeats: int,
        task_id_pattern: str = "task_{i}_repeat"
    ) -> Dict[str, Any]:
        """
        收集重复率定实验的所有结果（用于统计分析）

        Args:
            session_dir: 会话目录
            n_repeats: 重复次数
            task_id_pattern: 任务ID模式（支持 {i} 占位符）

        Returns:
            收集结果的字典:
            {
                "found_count": 15,
                "total_count": 20,
                "results": [
                    {
                        "task_id": "task_1_repeat",
                        "result_file": Path(...),
                        "data": {...}  # calibration_results.json 的内容
                    },
                    ...
                ]
            }
        """
        import json

        results = []

        for i in range(1, n_repeats + 1):
            task_id = task_id_pattern.format(i=i)
            task_dir = PathManager.get_task_output_dir(session_dir, task_id)
            result_file = PathManager.find_calibration_results(task_dir)

            if result_file and result_file.exists():
                try:
                    with open(result_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    results.append({
                        "task_id": task_id,
                        "result_file": result_file,
                        "data": data
                    })

                    logger.debug(f"[PathManager] Loaded result from {task_id}")
                except Exception as e:
                    logger.warning(f"[PathManager] Failed to load {result_file}: {e}")
            else:
                logger.warning(f"[PathManager] No result found for {task_id}")

        return {
            "found_count": len(results),
            "total_count": n_repeats,
            "results": results
        }

    @staticmethod
    def get_standard_paths(session_dir: Path, task_id: str) -> Dict[str, Path]:
        """
        获取所有标准路径（便捷函数）

        Args:
            session_dir: 会话目录
            task_id: 任务ID

        Returns:
            路径字典:
            {
                "task_dir": Path(...),
                "calibration_results": Path(...) or None,
                "calibration_dir": Path(...) or None,
                "basins_metrics": Path(...) or None,
                "param_range_yaml": Path(...) or None
            }
        """
        task_dir = PathManager.get_task_output_dir(session_dir, task_id)
        calibration_results = PathManager.find_calibration_results(task_dir)
        calibration_dir = calibration_results.parent if calibration_results else None

        return {
            "task_dir": task_dir,
            "calibration_results": calibration_results,
            "calibration_dir": calibration_dir,
            "basins_metrics": task_dir / "basins_metrics.csv" if (task_dir / "basins_metrics.csv").exists() else None,
            "param_range_yaml": task_dir / "param_range.yaml" if (task_dir / "param_range.yaml").exists() else None
        }


# ============================================================================
#   Utility Functions for File Scanning
#   从RunnerAgent提取的工具函数，用于扫描生成的输出文件
# ============================================================================

def scan_output_files(workspace_dir: Optional[Path] = None) -> list[str]:
    """
    扫描生成的输出文件。
    Scan generated output files.

    Args:
        workspace_dir: 工作目录（可选）

    Returns:
        输出文件路径列表
    """
    output_files = []
    if workspace_dir:
        workspace_path = Path(workspace_dir)
        for ext in ['.csv', '.png', '.pdf', '.json', '.txt']:
            output_files.extend(
                [str(f) for f in workspace_path.glob(f'*{ext}')]
            )
    return output_files


# ============================================================================
#   Backward Compatibility Functions
# ============================================================================

# Convenience function for backward compatibility
def configure_task_output_dir(
    config: Dict[str, Any],
    session_dir: Path,
    task_id: str
) -> Dict[str, Any]:
    """
    向后兼容的便捷函数

    Deprecated: 请使用 PathManager.configure_hydromodel_output()
    """
    logger.warning("[PathManager] configure_task_output_dir() is deprecated, use PathManager.configure_hydromodel_output()")
    return PathManager.configure_hydromodel_output(config, session_dir, task_id, use_flat_structure=True)
