"""
Author: Claude
Date: 2025-11-28 14:30:00
LastEditTime: 2025-11-28 14:30:00
LastEditors: Claude
Description: Task type detector for multi-task post-processing
             任务类型检测器 - 智能识别批量任务类型以生成对应汇总文件
FilePath: /HydroAgent/hydroagent/utils/task_detector.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class TaskTypeDetector:
    """
    任务类型检测器

    职责：
    - 智能分析subtask_results、task_plan、intent的内容
    - 识别多任务的类型（多流域、多算法、重复实验等）
    - 返回标准化的任务类型字符串

    支持的任务类型：
    - "multi_basin": 多流域批量率定
    - "multi_algorithm": 多算法×模型组合
    - "repeated_calibration": 重复实验（稳定性验证）
    - "iterative_optimization": 迭代优化
    - "single_task": 单任务
    - "multi_task_generic": 通用多任务（兜底）
    """

    @staticmethod
    def detect_task_type(
        subtask_results: List[Dict], task_plan: Dict, intent: Dict
    ) -> str:
        """
        检测任务类型（增强版，支持多种数据结构）。

        Args:
            subtask_results: 子任务结果列表
            task_plan: 任务计划（来自TaskPlanner）
            intent: 意图结果（来自IntentAgent）

        Returns:
            任务类型字符串

        Detection Logic:
            1. 单任务检测（n_tasks == 1）
            2. 关键词检测（任务描述中的"重复"、"迭代"等）
            3. Intent分析（basin_ids、algorithms、models数量）
            4. Task plan分析（从subtasks提取basin/algorithm/model）
            5. Config分析（从subtask_results提取算法、模型组合）
            6. 兜底返回（multi_task_generic）
        """
        n_tasks = len(subtask_results)

        # ===== 检测1: 单任务 =====
        if n_tasks == 1:
            logger.debug("[TaskDetector] Detected single_task (n_tasks=1)")
            return "single_task"

        # ===== 检测2: 任务描述关键词 =====
        subtasks = task_plan.get("subtasks", [])
        descriptions = [st.get("description", "") for st in subtasks]

        # 重复实验（实验5）
        if any("重复" in d or "repeat" in d.lower() for d in descriptions):
            logger.info(
                f"[TaskDetector] Detected repeated_calibration (keyword match in {n_tasks} tasks)"
            )
            return "repeated_calibration"

        # 迭代优化（实验3）
        if any("迭代" in d or "iteration" in d.lower() for d in descriptions):
            logger.info(
                f"[TaskDetector] Detected iterative_optimization (keyword match in {n_tasks} tasks)"
            )
            return "iterative_optimization"

        # ===== 检测3: Intent中的流域/算法/模型数量（多路径提取）=====
        basin_ids = TaskTypeDetector._extract_basin_ids(
            intent, task_plan, subtask_results
        )
        algorithms = TaskTypeDetector._extract_algorithms(
            intent, task_plan, subtask_results
        )
        models = TaskTypeDetector._extract_models(intent, task_plan, subtask_results)

        logger.debug(
            f"[TaskDetector] Extracted: {len(basin_ids)} basins, "
            f"{len(algorithms)} algorithms, {len(models)} models"
        )

        # 多流域检测
        if len(basin_ids) > 1:
            logger.info(
                f"[TaskDetector] Detected multi_basin ({len(basin_ids)} basins)"
            )
            return "multi_basin"

        # 多算法或多模型检测
        if len(algorithms) > 1 or len(models) > 1:
            logger.info(
                f"[TaskDetector] Detected multi_algorithm "
                f"({len(algorithms)} algorithms × {len(models)} models)"
            )
            return "multi_algorithm"

        # ===== 检测4: 兜底 =====
        logger.info(
            f"[TaskDetector] Detected multi_task_generic ({n_tasks} tasks, no specific pattern)"
        )
        return "multi_task_generic"

    @staticmethod
    def _extract_basin_ids(
        intent: Dict, task_plan: Dict, subtask_results: List[Dict]
    ) -> List[str]:
        """
        从多个数据源提取basin_ids（向后兼容）。

        数据源优先级：
        1. intent.intent_result.basin_ids（最高优先级）
        2. task_plan.subtasks[*].parameters.basin_id
        3. subtask_results[*].config.data_cfgs.basin_ids

        Returns:
            去重后的basin_ids列表
        """
        basin_ids = set()

        # 数据源1: Intent（支持多种结构）
        # 结构1: {"intent_result": {"basin_ids": [...]}}
        intent_result = intent.get("intent_result", {})
        if isinstance(intent_result, dict):
            ids = intent_result.get("basin_ids", [])
            if ids:
                basin_ids.update(ids if isinstance(ids, list) else [ids])

        # 数据源2: Task Plan
        for subtask in task_plan.get("subtasks", []):
            params = subtask.get("parameters", {})
            basin_id = params.get("basin_id")
            if basin_id:
                basin_ids.add(basin_id)

        # 数据源3: Subtask Results (从config中提取)
        for result in subtask_results:
            config = result.get("config", {})
            data_cfgs = config.get("data_cfgs", {})
            ids = data_cfgs.get("basin_ids", [])
            if ids:
                basin_ids.update(ids if isinstance(ids, list) else [ids])

        return list(basin_ids)

    @staticmethod
    def _extract_algorithms(
        intent: Dict, task_plan: Dict, subtask_results: List[Dict]
    ) -> List[str]:
        """
        从多个数据源提取algorithms（向后兼容）。

        数据源优先级：
        1. intent.intent_result.algorithms
        2. task_plan.subtasks[*].parameters.algorithm
        3. subtask_results[*].config.training_cfgs.algorithm_name

        Returns:
            去重后的algorithms列表
        """
        algorithms = set()

        # 数据源1: Intent
        intent_result = intent.get("intent_result", {})
        if isinstance(intent_result, dict):
            algos = intent_result.get("algorithms", [])
            if algos:
                algorithms.update(algos if isinstance(algos, list) else [algos])

        # 数据源2: Task Plan
        for subtask in task_plan.get("subtasks", []):
            params = subtask.get("parameters", {})
            algo = params.get("algorithm")
            if algo and not (isinstance(algo, str) and algo.startswith("[")):
                # 排除字符串形式的列表（如"['SCE_UA', 'GA']"）
                algorithms.add(algo)

        # 数据源3: Subtask Results (从config中提取)
        for result in subtask_results:
            config = result.get("config", {})
            training_cfgs = config.get("training_cfgs", {})
            algo = training_cfgs.get("algorithm_name", "")
            if algo:
                algorithms.add(algo)

        return list(algorithms)

    @staticmethod
    def _extract_models(
        intent: Dict, task_plan: Dict, subtask_results: List[Dict]
    ) -> List[str]:
        """
        从多个数据源提取models（向后兼容）。

        数据源优先级：
        1. intent.intent_result.model_names
        2. task_plan.subtasks[*].parameters.model_name
        3. subtask_results[*].config.model_cfgs.model_name

        Returns:
            去重后的models列表
        """
        models = set()

        # 数据源1: Intent
        intent_result = intent.get("intent_result", {})
        if isinstance(intent_result, dict):
            model_names = intent_result.get("model_names", [])
            if model_names:
                models.update(
                    model_names if isinstance(model_names, list) else [model_names]
                )

        # 数据源2: Task Plan
        for subtask in task_plan.get("subtasks", []):
            params = subtask.get("parameters", {})
            model = params.get("model_name")
            if model:
                models.add(model)

        # 数据源3: Subtask Results (从config中提取)
        for result in subtask_results:
            config = result.get("config", {})
            model_cfgs = config.get("model_cfgs", {})
            model = model_cfgs.get("model_name", "")
            if model:
                models.add(model)

        return list(models)


# ============================================================================
#   Utility Functions (for future extensions)
# ============================================================================


def get_task_type_description(task_type: str) -> str:
    """
    获取任务类型的中文描述。

    Args:
        task_type: 任务类型字符串

    Returns:
        中文描述
    """
    descriptions = {
        "single_task": "单任务",
        "multi_basin": "多流域批量率定",
        "multi_algorithm": "多算法×模型组合",
        "repeated_calibration": "重复率定（稳定性验证）",
        "iterative_optimization": "迭代优化",
        "multi_task_generic": "通用多任务",
    }

    return descriptions.get(task_type, "未知类型")
