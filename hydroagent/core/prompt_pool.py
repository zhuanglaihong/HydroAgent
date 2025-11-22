"""
Author: Claude
Date: 2025-01-22 15:00:00
LastEditTime: 2025-01-22 15:00:00
LastEditors: Claude
Description: Simplified Prompt Pool for task prompt storage and history management
             简化版提示词池 - 用于任务提示词存储和历史管理
FilePath: /HydroAgent/hydroagent/core/prompt_pool.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class PromptPool:
    """
    简化版提示词池。

    职责：
    1. 存储每个子任务的提示词
    2. 存储历史成功案例（最近50个）
    3. 简单的相似案例检索
    4. 持久化到磁盘

    不做：
    - 复杂的向量检索
    - RAG系统
    - 语义相似度计算
    """

    def __init__(self, pool_dir: Optional[Path] = None, max_history: int = 50):
        """
        初始化Prompt Pool。

        Args:
            pool_dir: 存储目录（默认: prompt_pool/）
            max_history: 最大历史记录数
        """
        self.pool_dir = pool_dir or Path("prompt_pool")
        self.pool_dir.mkdir(exist_ok=True)
        self.max_history = max_history

        # 当前会话的提示词存储
        self.prompts: Dict[str, Dict[str, Any]] = {}

        # 历史记录
        self.history: List[Dict[str, Any]] = []

        # 加载历史
        self._load_history()

        logger.info(f"[PromptPool] Initialized with {len(self.history)} history records")

    def store_prompt(self, task_id: str, prompt: str, params: Dict[str, Any]):
        """
        存储子任务的提示词。

        Args:
            task_id: 子任务ID（如 "task_1"）
            prompt: 提示词内容
            params: 任务参数
        """
        self.prompts[task_id] = {
            "prompt": prompt,
            "params": params,
            "timestamp": datetime.now().isoformat()
        }

        logger.debug(f"[PromptPool] Stored prompt for {task_id}")

    def get_prompt(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取子任务的提示词。

        Args:
            task_id: 子任务ID

        Returns:
            提示词信息或None
        """
        return self.prompts.get(task_id)

    def add_history(
        self,
        task_type: str,
        intent: Dict[str, Any],
        config: Dict[str, Any],
        result: Dict[str, Any],
        success: bool
    ):
        """
        添加历史记录。

        Args:
            task_type: 任务类型
            intent: 用户意图
            config: 配置字典
            result: 执行结果
            success: 是否成功
        """
        record = {
            "task_type": task_type,
            "intent": intent,
            "config": config,
            "result": result,
            "success": success,
            "timestamp": datetime.now().isoformat()
        }

        self.history.append(record)

        # 限制大小
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

        # 保存到磁盘
        self._save_history()

        logger.debug(f"[PromptPool] Added history record (success={success}), total={len(self.history)}")

    def get_similar_cases(
        self,
        intent: Dict[str, Any],
        limit: int = 3,
        only_success: bool = True
    ) -> List[Dict[str, Any]]:
        """
        检索相似的成功案例（简单匹配）。

        Args:
            intent: 当前意图
            limit: 返回数量
            only_success: 是否只返回成功案例

        Returns:
            相似案例列表
        """
        # 过滤
        candidates = [
            r for r in self.history
            if (not only_success or r["success"])
        ]

        if not candidates:
            return []

        # 简单相似度计算
        scored_cases = []
        for case in candidates:
            score = self._calculate_similarity(intent, case["intent"])
            if score > 0:
                scored_cases.append((score, case))

        # 排序并返回top-k
        scored_cases.sort(key=lambda x: x[0], reverse=True)
        return [case for _, case in scored_cases[:limit]]

    def _calculate_similarity(self, intent1: Dict, intent2: Dict) -> float:
        """
        计算两个意图的相似度（简单规则）。

        Args:
            intent1: 意图1
            intent2: 意图2

        Returns:
            相似度分数（0-3.0）
        """
        score = 0.0

        # 模型匹配 (+1.0)
        if intent1.get("model_name") == intent2.get("model_name"):
            score += 1.0

        # 算法匹配 (+0.8)
        if intent1.get("algorithm") == intent2.get("algorithm"):
            score += 0.8

        # 流域匹配 (+0.5)
        if intent1.get("basin_id") == intent2.get("basin_id"):
            score += 0.5

        # 任务类型匹配 (+0.7)
        if intent1.get("task_type") == intent2.get("task_type"):
            score += 0.7

        return score

    def generate_context_prompt(
        self,
        base_prompt: str,
        intent: Dict[str, Any],
        error_log: Optional[str] = None
    ) -> str:
        """
        生成带上下文的完整提示词。

        Args:
            base_prompt: 基础提示词
            intent: 当前意图
            error_log: 错误日志（可选）

        Returns:
            完整提示词
        """
        parts = [base_prompt]

        # 添加历史成功案例
        similar = self.get_similar_cases(intent, limit=2)
        if similar:
            parts.append("\n### 📚 历史成功案例参考")
            for i, case in enumerate(similar, 1):
                parts.append(f"\n**案例{i}**:")
                parts.append(f"- 模型: {case['intent'].get('model_name')}")
                parts.append(f"- 算法: {case['intent'].get('algorithm')}")

                # 算法参数
                algo_params = case['config'].get('training_cfgs', {}).get('algorithm_params', {})
                if algo_params:
                    params_str = json.dumps(algo_params, ensure_ascii=False)
                    parts.append(f"- 算法参数: {params_str}")

                # 性能指标
                metrics = case['result'].get('metrics', {})
                if metrics:
                    nse = metrics.get('NSE', 'N/A')
                    parts.append(f"- 性能: NSE={nse}")

        # 添加错误反馈
        if error_log:
            parts.append("\n### ⚠️ 上次执行失败")
            parts.append(error_log)
            parts.append("\n**请根据错误信息调整配置，避免重复错误。**")

        return "\n".join(parts)

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息。

        Returns:
            统计字典
        """
        total = len(self.history)
        successful = sum(1 for r in self.history if r["success"])

        # 统计任务类型
        task_types = {}
        for record in self.history:
            t = record.get("task_type", "unknown")
            task_types[t] = task_types.get(t, 0) + 1

        # 统计模型使用
        models = {}
        for record in self.history:
            model = record["intent"].get("model_name", "unknown")
            models[model] = models.get(model, 0) + 1

        return {
            "total_records": total,
            "successful_records": successful,
            "success_rate": successful / total if total > 0 else 0,
            "task_type_distribution": task_types,
            "model_usage": models
        }

    def _load_history(self):
        """从磁盘加载历史记录"""
        history_file = self.pool_dir / "history.json"
        if history_file.exists():
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    self.history = json.load(f)
                logger.info(f"[PromptPool] Loaded {len(self.history)} records from {history_file}")
            except Exception as e:
                logger.error(f"[PromptPool] Failed to load history: {e}")
                self.history = []
        else:
            logger.info("[PromptPool] No existing history file, starting fresh")

    def _save_history(self):
        """保存历史记录到磁盘"""
        history_file = self.pool_dir / "history.json"
        try:
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[PromptPool] Failed to save history: {e}")

    def clear_session(self):
        """清除当前会话的提示词（不影响历史记录）"""
        self.prompts.clear()
        logger.info("[PromptPool] Cleared session prompts")
