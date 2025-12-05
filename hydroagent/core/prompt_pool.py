"""
Author: Claude & zhuanglaihong
Date: 2025-01-25 10:00:00
LastEditTime: 2025-01-25 10:00:00
LastEditors: Claude
Description: Advanced Prompt Pool with FAISS Semantic Search and LLM Fusion
             增强版提示词池 - FAISS语义检索 + LLM动态融合
FilePath: /HydroAgent/hydroagent/core/prompt_pool.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

v5.0 Architecture Update:
- FAISS vector database for semantic similarity search
- LLM-driven prompt fusion from historical cases
- Incremental learning with quality-based case retention
- Automatic embedding generation for new cases
"""

from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import json
import logging
from datetime import datetime
import numpy as np

# Import NumpyJSONEncoder from checkpoint_manager
from .checkpoint_manager import NumpyJSONEncoder

logger = logging.getLogger(__name__)


class PromptPool:
    """
    v5.0 高级提示词池。

    核心改进：
    1. FAISS向量数据库：语义相似度检索
    2. LLM动态融合：智能合并历史案例到新提示词
    3. 增量学习：每次成功案例自动更新知识库
    4. 质量评分：基于NSE等指标筛选高质量案例
    5. 降级支持：FAISS不可用时自动切换到规则匹配

    依赖：
    - faiss-cpu: 向量数据库
    - sentence-transformers: 文本embedding
    """

    def __init__(
        self,
        pool_dir: Optional[Path] = None,
        max_history: int = 100,
        use_faiss: bool = False,
        llm_interface=None,
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    ):
        """
        初始化Prompt Pool。

        Args:
            pool_dir: 存储目录（默认: prompt_pool/）
            max_history: 最大历史记录数（v5.0提升到100）
            use_faiss: 是否使用FAISS语义检索（False则使用规则匹配）
            llm_interface: LLM接口（用于动态融合提示词）
            embedding_model: Embedding模型名称
        """
        self.pool_dir = pool_dir or Path("prompt_pool")
        self.pool_dir.mkdir(exist_ok=True)
        self.max_history = max_history
        self.use_faiss = use_faiss
        self.llm = llm_interface
        self.embedding_model_name = embedding_model

        # 当前会话的提示词存储
        self.prompts: Dict[str, Dict[str, Any]] = {}

        # 历史记录
        self.history: List[Dict[str, Any]] = []

        # FAISS相关组件
        self.faiss_index = None
        self.embedding_model = None
        self.case_ids = []  # 存储每个向量对应的case索引

        # 初始化FAISS
        if use_faiss:
            self._initialize_faiss()
        else:
            logger.info("[PromptPool] FAISS disabled, using rule-based matching")

        # 加载历史
        self._load_history()

        logger.info(
            f"[PromptPool] Initialized with {len(self.history)} history records "
            f"(FAISS={'enabled' if self.use_faiss and self.faiss_index else 'disabled'})"
        )

    # =========================================================================
    # FAISS Initialization
    # =========================================================================

    def _initialize_faiss(self):
        """初始化FAISS向量数据库和Embedding模型"""
        try:
            import faiss
            from sentence_transformers import SentenceTransformer

            # 加载Embedding模型
            logger.info(f"[PromptPool] Loading embedding model: {self.embedding_model_name}")
            self.embedding_model = SentenceTransformer(self.embedding_model_name)

            # 确定向量维度
            embedding_dim = self.embedding_model.get_sentence_embedding_dimension()

            # 创建或加载FAISS索引
            index_file = self.pool_dir / "faiss_index.bin"
            if index_file.exists():
                self.faiss_index = faiss.read_index(str(index_file))
                logger.info(f"[PromptPool] Loaded FAISS index from {index_file}")
            else:
                # 使用L2距离的平面索引（适合中小规模数据）
                self.faiss_index = faiss.IndexFlatL2(embedding_dim)
                logger.info(f"[PromptPool] Created new FAISS index (dim={embedding_dim})")

            logger.info("[PromptPool] FAISS initialization successful")

        except ImportError as e:
            logger.warning(
                f"[PromptPool] FAISS or SentenceTransformer not available: {e}. "
                "Falling back to rule-based matching."
            )
            self.use_faiss = False
            self.embedding_model = None
            self.faiss_index = None

        except Exception as e:
            logger.error(f"[PromptPool] FAISS initialization failed: {e}")
            self.use_faiss = False
            self.embedding_model = None
            self.faiss_index = None

    def _save_faiss_index(self):
        """保存FAISS索引到磁盘"""
        if not self.use_faiss or not self.faiss_index:
            return

        try:
            import faiss
            index_file = self.pool_dir / "faiss_index.bin"
            faiss.write_index(self.faiss_index, str(index_file))
            logger.debug(f"[PromptPool] FAISS index saved to {index_file}")
        except Exception as e:
            logger.error(f"[PromptPool] Failed to save FAISS index: {e}")

    # =========================================================================
    # Core Prompt Storage (Same as v3.5)
    # =========================================================================

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

    # =========================================================================
    # History Management with Quality Scoring
    # =========================================================================

    def add_history(
        self,
        task_type: str,
        intent: Dict[str, Any],
        config: Dict[str, Any],
        result: Dict[str, Any],
        success: bool
    ):
        """
        添加历史记录（增强版）。

        v5.0新功能：
        - 只存储成功案例
        - 计算质量分数（基于NSE）
        - 自动向量化并添加到FAISS索引
        - 保留高质量案例（超过max_history时）

        Args:
            task_type: 任务类型
            intent: 用户意图
            config: 配置字典
            result: 执行结果
            success: 是否成功
        """
        # 只存储成功案例
        if not success:
            logger.debug("[PromptPool] Skipping failed case (not storing)")
            return

        # 计算质量分数
        quality_score = self._calculate_quality_score(result)

        record = {
            "task_type": task_type,
            "intent": intent,
            "config": config,
            "result": result,
            "success": success,
            "quality_score": quality_score,
            "timestamp": datetime.now().isoformat()
        }

        self.history.append(record)
        logger.debug(
            f"[PromptPool] Added history record (quality={quality_score:.3f}), "
            f"total={len(self.history)}"
        )

        # 限制大小（保留高质量案例）
        if len(self.history) > self.max_history:
            self.history = sorted(
                self.history,
                key=lambda x: x.get("quality_score", 0),
                reverse=True
            )[:self.max_history]
            logger.info(
                f"[PromptPool] Pruned history to top {self.max_history} quality cases"
            )

        # 添加到FAISS索引
        if self.use_faiss and self.faiss_index is not None:
            self._add_to_faiss(record)

        # 保存到磁盘
        self._save_history()
        if self.use_faiss:
            self._save_faiss_index()

    def _calculate_quality_score(self, result: Dict[str, Any]) -> float:
        """
        计算案例质量分数。

        Args:
            result: 执行结果

        Returns:
            质量分数（0-1）
        """
        metrics = result.get("metrics", {})

        # 主要指标：NSE
        nse = metrics.get("NSE")
        if nse is not None:
            # NSE范围 [-inf, 1], 归一化到 [0, 1]
            # NSE < 0 -> 0, NSE >= 0.75 -> 1.0
            if nse < 0:
                return 0.0
            elif nse >= 0.75:
                return 1.0
            else:
                return nse / 0.75

        # 备选指标：KGE
        kge = metrics.get("KGE")
        if kge is not None:
            if kge < 0:
                return 0.0
            elif kge >= 0.75:
                return 1.0
            else:
                return kge / 0.75

        # 无可用指标，返回默认值
        return 0.5

    def _add_to_faiss(self, record: Dict[str, Any]):
        """
        将案例向量化并添加到FAISS索引。

        Args:
            record: 历史记录
        """
        try:
            # 将intent转换为文本
            text = self._intent_to_text(record["intent"])

            # 生成embedding
            embedding = self.embedding_model.encode([text])[0]

            # 添加到索引
            self.faiss_index.add(np.array([embedding], dtype=np.float32))

            # 记录case_id（FAISS索引位置 -> history索引）
            self.case_ids.append(len(self.history) - 1)

            logger.debug(f"[PromptPool] Added case to FAISS index (total={self.faiss_index.ntotal})")

        except Exception as e:
            logger.error(f"[PromptPool] Failed to add case to FAISS: {e}")

    # =========================================================================
    # Semantic Search with FAISS
    # =========================================================================

    def get_similar_cases(
        self,
        intent: Dict[str, Any],
        limit: int = 3,
        only_success: bool = True,
        use_semantic: bool = True
    ) -> List[Dict[str, Any]]:
        """
        检索相似案例。

        v5.0改进：
        - 优先使用FAISS语义检索
        - 降级到规则匹配（FAISS不可用时）
        - 返回相似度分数

        Args:
            intent: 当前意图
            limit: 返回数量
            only_success: 是否只返回成功案例
            use_semantic: 是否使用语义检索

        Returns:
            相似案例列表（包含similarity字段）
        """
        if use_semantic and self.use_faiss and self.faiss_index:
            return self._semantic_search(intent, limit)
        else:
            return self._rule_based_search(intent, limit, only_success)

    def search_similar(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        🆕 Search for similar cases using a text query (for TaskPlanner).
        使用文本查询检索相似案例（TaskPlanner专用接口）。

        This is a convenience method that converts a text query to a pseudo-intent
        and calls get_similar_cases. Used by TaskPlanner._retrieve_historical_cases.

        Args:
            query: Text query (e.g., "任务类型: standard_calibration 模型: gr4j")
            top_k: Number of cases to return

        Returns:
            List of similar cases
        """
        # Parse query text to pseudo-intent
        pseudo_intent = self._parse_query_text(query)

        # Call get_similar_cases
        return self.get_similar_cases(pseudo_intent, limit=top_k, use_semantic=True)

    def _parse_query_text(self, query: str) -> Dict[str, Any]:
        """
        Parse text query to pseudo-intent dictionary.
        将文本查询解析为伪意图字典。

        Args:
            query: Query text (e.g., "任务类型: standard_calibration 模型: gr4j")

        Returns:
            Pseudo-intent dictionary
        """
        import re

        intent = {}

        # Extract task_type
        task_match = re.search(r"任务类型[:：]\s*(\w+)", query)
        if task_match:
            intent["task_type"] = task_match.group(1)

        # Extract model_name
        model_match = re.search(r"模型[:：]\s*(\w+)", query)
        if model_match:
            intent["model_name"] = model_match.group(1)

        # Extract algorithm
        algo_match = re.search(r"算法[:：]\s*(\w+)", query)
        if algo_match:
            intent["algorithm"] = algo_match.group(1)

        # If no structured info, use query as task_description
        if not intent:
            intent["task_description"] = query

        logger.debug(f"[PromptPool] Parsed query to pseudo-intent: {intent}")
        return intent

    def _semantic_search(self, intent: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        """
        FAISS语义检索。

        Args:
            intent: 当前意图
            limit: 返回数量

        Returns:
            相似案例列表
        """
        try:
            # 将intent转换为文本
            query_text = self._intent_to_text(intent)

            # 生成query embedding
            query_embedding = self.embedding_model.encode([query_text])[0]

            # FAISS搜索
            k = min(limit, self.faiss_index.ntotal)
            if k == 0:
                return []

            distances, indices = self.faiss_index.search(
                np.array([query_embedding], dtype=np.float32),
                k
            )

            # 转换为案例列表
            similar_cases = []
            for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
                if idx < 0:  # FAISS返回-1表示无效索引
                    continue

                # 获取对应的history索引
                history_idx = self.case_ids[idx] if idx < len(self.case_ids) else idx

                if history_idx < len(self.history):
                    case = self.history[history_idx].copy()
                    # 距离转相似度（L2距离，越小越相似）
                    case["similarity"] = 1.0 / (1.0 + float(dist))
                    similar_cases.append(case)

            logger.debug(
                f"[PromptPool] FAISS search returned {len(similar_cases)} cases"
            )
            return similar_cases

        except Exception as e:
            logger.error(f"[PromptPool] FAISS search failed: {e}, falling back to rule-based")
            return self._rule_based_search(intent, limit, only_success=True)

    def _rule_based_search(
        self,
        intent: Dict[str, Any],
        limit: int,
        only_success: bool
    ) -> List[Dict[str, Any]]:
        """
        规则匹配检索（降级方案）。

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
            if (not only_success or r.get("success", False))
        ]

        if not candidates:
            return []

        # 简单相似度计算
        scored_cases = []
        for case in candidates:
            score = self._calculate_rule_similarity(intent, case["intent"])
            if score > 0:
                case_copy = case.copy()
                case_copy["similarity"] = score / 3.0  # 归一化到 [0, 1]
                scored_cases.append((score, case_copy))

        # 排序并返回top-k
        scored_cases.sort(key=lambda x: x[0], reverse=True)
        return [case for _, case in scored_cases[:limit]]

    def _calculate_rule_similarity(self, intent1: Dict, intent2: Dict) -> float:
        """
        计算两个意图的规则相似度。

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

    def _intent_to_text(self, intent: Dict[str, Any]) -> str:
        """
        将意图转换为文本描述（用于向量化）。

        Args:
            intent: 意图字典

        Returns:
            文本描述
        """
        parts = []
        parts.append(f"Model: {intent.get('model_name', 'N/A')}")
        parts.append(f"Basin: {intent.get('basin_id', 'N/A')}")
        parts.append(f"Algorithm: {intent.get('algorithm', 'N/A')}")
        parts.append(f"Task: {intent.get('task_description', intent.get('task_type', 'N/A'))}")

        # 添加算法参数
        algo_params = intent.get('algorithm_params', {})
        if algo_params:
            params_str = json.dumps(algo_params, ensure_ascii=False)
            parts.append(f"Parameters: {params_str}")

        return " | ".join(parts)

    # =========================================================================
    # LLM-Driven Prompt Fusion
    # =========================================================================

    def generate_enhanced_prompt(
        self,
        base_prompt: str,
        intent: Dict[str, Any],
        similar_cases: Optional[List[Dict]] = None,
        error_log: Optional[str] = None
    ) -> str:
        """
        使用LLM动态融合历史案例到提示词。

        v5.0核心功能：
        - LLM智能提取历史案例经验
        - 融合成功经验到新提示词
        - 避免历史错误做法
        - 结合错误反馈调整提示词

        Args:
            base_prompt: 基础提示词
            intent: 当前意图
            similar_cases: 相似案例（可选，自动检索）
            error_log: 错误日志（可选）

        Returns:
            增强后的提示词
        """
        # 自动检索相似案例（如果未提供）
        if similar_cases is None:
            similar_cases = self.get_similar_cases(intent, limit=3)

        # 无LLM或无历史案例，使用简单拼接（降级）
        if not self.llm or not similar_cases:
            return self._simple_context_prompt(base_prompt, intent, similar_cases, error_log)

        # 使用LLM动态融合
        try:
            fusion_prompt = self._build_fusion_prompt(
                base_prompt, intent, similar_cases, error_log
            )

            # 调用LLM生成增强提示词
            enhanced_prompt = self.llm.generate(
                system_prompt="你是提示词优化专家，擅长从历史案例中提取经验并融合到新提示词中。",
                user_prompt=fusion_prompt,
                temperature=0.2  # 较低温度，保证稳定性
            )

            logger.info("[PromptPool] LLM-enhanced prompt generated successfully")
            return enhanced_prompt

        except Exception as e:
            logger.error(f"[PromptPool] LLM fusion failed: {e}, using simple concatenation")
            return self._simple_context_prompt(base_prompt, intent, similar_cases, error_log)

    def _build_fusion_prompt(
        self,
        base_prompt: str,
        intent: Dict,
        similar_cases: List[Dict],
        error_log: Optional[str]
    ) -> str:
        """
        构建LLM融合提示词。

        Args:
            base_prompt: 基础提示词
            intent: 当前意图
            similar_cases: 相似案例
            error_log: 错误日志

        Returns:
            LLM融合提示词
        """
        parts = [
            "## 任务：提示词增强",
            "",
            "请将以下历史成功案例的经验融合到新任务的提示词中。",
            "",
            "## 新任务提示词",
            base_prompt,
            "",
            "## 历史成功案例"
        ]

        for i, case in enumerate(similar_cases, 1):
            similarity = case.get("similarity", 0)
            parts.append(f"\n### 案例{i} (相似度: {similarity:.2f})")
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
                rmse = metrics.get('RMSE', 'N/A')
                parts.append(f"- 性能: NSE={nse}, RMSE={rmse}")

        # 添加错误反馈
        if error_log:
            parts.append("\n## 上次执行失败")
            parts.append(error_log)
            parts.append("\n**请根据错误信息调整配置，避免重复错误。**")

        parts.append("\n## 请求")
        parts.append("请生成增强后的提示词，要求：")
        parts.append("1. 保留新任务的核心需求")
        parts.append("2. 吸收历史案例的成功经验（如有效的参数设置、算法选择）")
        parts.append("3. 避免历史案例中可能的问题")
        parts.append("4. 如果有错误日志，针对性地调整配置")
        parts.append("5. 输出完整的提示词文本（不要包含额外说明或元信息）")

        return "\n".join(parts)

    def _simple_context_prompt(
        self,
        base_prompt: str,
        intent: Dict,
        similar_cases: Optional[List[Dict]],
        error_log: Optional[str]
    ) -> str:
        """
        简单的上下文提示词拼接（降级方案）。

        Args:
            base_prompt: 基础提示词
            intent: 当前意图
            similar_cases: 相似案例
            error_log: 错误日志

        Returns:
            拼接后的提示词
        """
        parts = [base_prompt]

        # 添加历史成功案例
        if similar_cases:
            parts.append("\n### 📚 历史成功案例参考")
            for i, case in enumerate(similar_cases, 1):
                similarity = case.get("similarity", 0)
                parts.append(f"\n**案例{i}** (相似度: {similarity:.2f}):")
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

    # 别名：保持API兼容性
    def generate_context_prompt(
        self,
        base_prompt: str,
        intent: Dict[str, Any],
        error_log: Optional[str] = None
    ) -> str:
        """
        生成带上下文的完整提示词（兼容v3.5 API）。

        Args:
            base_prompt: 基础提示词
            intent: 当前意图
            error_log: 错误日志（可选）

        Returns:
            完整提示词
        """
        return self.generate_enhanced_prompt(base_prompt, intent, error_log=error_log)

    # =========================================================================
    # Statistics and Utilities
    # =========================================================================

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息。

        Returns:
            统计字典
        """
        total = len(self.history)
        successful = sum(1 for r in self.history if r.get("success", False))

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

        # 平均质量分数
        avg_quality = (
            sum(r.get("quality_score", 0) for r in self.history) / total
            if total > 0 else 0
        )

        return {
            "total_records": total,
            "successful_records": successful,
            "success_rate": successful / total if total > 0 else 0,
            "average_quality_score": avg_quality,
            "task_type_distribution": task_types,
            "model_usage": models,
            "faiss_enabled": self.use_faiss and self.faiss_index is not None,
            "faiss_index_size": self.faiss_index.ntotal if self.faiss_index else 0
        }

    def _load_history(self):
        """从磁盘加载历史记录"""
        history_file = self.pool_dir / "history.json"
        if history_file.exists():
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    self.history = json.load(f)

                # 重建FAISS索引
                if self.use_faiss and self.faiss_index is not None:
                    self._rebuild_faiss_index()

                logger.info(f"[PromptPool] Loaded {len(self.history)} records from {history_file}")
            except Exception as e:
                logger.error(f"[PromptPool] Failed to load history: {e}")
                self.history = []
        else:
            logger.info("[PromptPool] No existing history file, starting fresh")

    def _rebuild_faiss_index(self):
        """从历史记录重建FAISS索引"""
        if not self.use_faiss or not self.faiss_index:
            return

        logger.info("[PromptPool] Rebuilding FAISS index from history...")
        self.case_ids = []

        for i, record in enumerate(self.history):
            try:
                text = self._intent_to_text(record["intent"])
                embedding = self.embedding_model.encode([text])[0]
                self.faiss_index.add(np.array([embedding], dtype=np.float32))
                self.case_ids.append(i)
            except Exception as e:
                logger.warning(f"[PromptPool] Failed to add case {i} to FAISS: {e}")

        logger.info(f"[PromptPool] FAISS index rebuilt ({self.faiss_index.ntotal} vectors)")

    def _save_history(self):
        """保存历史记录到磁盘"""
        history_file = self.pool_dir / "history.json"
        try:
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False, cls=NumpyJSONEncoder)
        except Exception as e:
            logger.error(f"[PromptPool] Failed to save history: {e}")

    def clear_session(self):
        """清除当前会话的提示词（不影响历史记录）"""
        self.prompts.clear()
        logger.info("[PromptPool] Cleared session prompts")
