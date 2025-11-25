"""
Author: Claude & zhuanglaihong
Date: 2025-01-20 19:55:00
LastEditTime: 2025-01-22 14:00:00
LastEditors: Claude
Description: Intent and data validation agent (Exp 1-5) - Enhanced with task decision
             意图与数据智能体 - 负责意图分类、任务决策和数据校验
FilePath: /HydroAgent/hydroagent/agents/intent_agent.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from typing import Dict, Any, Optional, List
from pathlib import Path
import logging

from ..core.base_agent import BaseAgent
from ..core.llm_interface import LLMInterface
from ..utils.prompt_manager import PromptManager, AgentContext

logger = logging.getLogger(__name__)


# 任务类型定义（支持实验1-5）
TASK_TYPES = {
    "standard_calibration": "标准单任务率定（实验1）",
    "info_completion": "缺省信息补全型率定（实验2B）",
    "iterative_optimization": "两阶段迭代优化（实验3）",
    "repeated_experiment": "重复实验-多随机种子（实验5）",
    "extended_analysis": "扩展分析-超出hydromodel功能（实验4）",
    "batch_processing": "批量处理-多流域/多算法",
    "custom_data": "自定义数据路径（实验2C）"
}


class IntentAgent(BaseAgent):
    """
    Intent and data validation agent (Enhanced for Experiments 1-5).
    意图与数据智能体（增强版，支持实验1-5）。

    Responsibilities (Enhanced):
    1. **Intent classification** (calibration / evaluation / simulation / extension)
    2. **Task type decision** (🆕) - Decide "what to do" based on query complexity
       - standard_calibration: Simple single-basin calibration
       - info_completion: Query with missing information
       - iterative_optimization: Two-phase adaptive calibration
       - repeated_experiment: Multiple runs with different seeds
       - extended_analysis: Tasks beyond hydromodel (e.g., FDC plotting)
       - batch_processing: Multi-basin or multi-algorithm tasks
       - custom_data: Custom data path handling
    3. **Information completion** (🆕) - Fill missing fields with intelligent defaults
       - Model name (default: xaj)
       - Algorithm (default: SCE_UA)
       - Time period (infer from data or use defaults)
       - Data source (infer from basin ID format)
    4. **Data availability validation** using hydrodataset
    5. **Query expansion and clarification**

    Output Format (Enhanced):
    {
        "success": True,
        "intent_result": {
            "task_type": "...",  # 🆕 Task type classification
            "intent": "calibration",
            "model_name": "gr4j",
            "basin_id": "01013500",
            "algorithm": "SCE_UA",
            "extra_params": {...},
            "strategy": {...},  # 🆕 Strategy information (if iterative)
            "needs": [...],     # 🆕 Extended analysis needs (if extended_analysis)
            "n_repeats": 10,    # 🆕 Number of repetitions (if repeated_experiment)
            ...
        }
    }
    """

    def __init__(
        self,
        llm_interface: LLMInterface,
        workspace_dir: Optional[Path] = None,
        use_dynamic_prompt: bool = True,
        **kwargs
    ):
        """
        Initialize IntentAgent.

        Args:
            llm_interface: LLM API interface
            workspace_dir: Working directory
            use_dynamic_prompt: Whether to use dynamic prompt system (default: True)
            **kwargs: Additional configuration
        """
        super().__init__(
            name="IntentAgent",
            llm_interface=llm_interface,
            workspace_dir=workspace_dir,
            **kwargs
        )

        # Dynamic Prompt System
        self.use_dynamic_prompt = use_dynamic_prompt
        if self.use_dynamic_prompt:
            self.prompt_manager = PromptManager()
            # Register static prompt skeleton
            self.prompt_manager.register_static_prompt("IntentAgent", self._get_default_system_prompt())
            # Load algorithm parameters schema for accurate parameter extraction
            self.prompt_manager.load_schema("algorithm_params")
            logger.info("[IntentAgent] Dynamic prompt system enabled with algorithm schema")
        else:
            self.prompt_manager = None
            logger.info("[IntentAgent] Using static prompt system")

        # Try to import hydrodataset for data validation
        try:
            from hydrodataset import CamelsUs
            self.has_hydrodataset = True
            logger.info("hydrodataset module available")
        except ImportError:
            self.has_hydrodataset = False
            logger.warning("hydrodataset not available, data validation disabled")

    def _get_default_system_prompt(self) -> str:
        """Return default system prompt for IntentAgent (enhanced for accuracy)."""
        return """你是一个水文模型意图分析助手。从用户查询中提取结构化信息。

**任务**: 分析水文模型查询，提取意图、模型、流域、时间、算法等信息

**意图分类**:
- calibration (中文: 率定/校准/参数率定)
- evaluation (中文: 评估/验证/测试)
- simulation (中文: 模拟/预测/计算)
- extension (中文: 其他/绘图/可视化/分析)

**支持的模型** (大小写不敏感):
- xaj, xaj_mz (新安江模型)
- gr4j, gr5j, gr6j (GR系列模型)
- gr1y, gr2m (年度/月度模型)

**关键信息提取**:
1. **模型名称** (model_name): 从查询中识别模型类型
   - 中文: "XAJ模型" → xaj, "GR4J模型" → gr4j
   - 英文: "XAJ model" → xaj, "calibrate GR4J" → gr4j

2. **流域ID** (basin_id): 流域编号/站点编号
   - 关键词: "流域", "basin", "站点", "site"
   - 格式: 数字编号如"01013500", "camels_11532500", "11532500"

3. **时间段** (time_period): 训练和测试时期
   - 默认: 训练10年 + 测试5年
   - 格式: {"train": ["2000-01-01", "2010-12-31"], "test": ["2011-01-01", "2015-12-31"]}

4. **算法** (algorithm): 优化算法
   - 默认: "SCE_UA"
   - 其他: "DE", "PSO", "GA", "SCEUA", "SCE_UA"

5. **额外参数** (extra_params): 其他配置参数
   - 迭代次数: max_iterations, ngs, kstop等
   - 人口数量: npop, ncomplex等

**输出格式** (必须是有效JSON):
{
  "intent": "calibration",
  "model_name": "gr4j",
  "basin_id": "01013500",
  "time_period": {
    "train": ["2000-01-01", "2010-12-31"],
    "test": ["2011-01-01", "2015-12-31"]
  },
  "algorithm": "SCE_UA",
  "extra_params": {
    "max_iterations": 500
  },
  "missing_info": [],
  "clarifications_needed": [],
  "confidence": 0.95
}

**示例**:

输入: "率定GR4J模型，流域01013500, 使用SCE-UA算法，算法迭代只需要500轮就行"
输出: {"intent":"calibration","model_name":"gr4j","basin_id":"01013500","algorithm":"SCE_UA","extra_params":{"max_iterations":500},"missing_info":[],"confidence":0.95}

输入: "评估XAJ模型在流域11532500的表现"
输出: {"intent":"evaluation","model_name":"xaj","basin_id":"11532500","algorithm":"SCE_UA","missing_info":[],"confidence":0.9}

输入: "Calibrate GR5J for basin camels_01013500"
输出: {"intent":"calibration","model_name":"gr5j","basin_id":"camels_01013500","algorithm":"SCE_UA","missing_info":[],"confidence":0.9}

输入: "率定一个水文模型"
输出: {"intent":"calibration","model_name":null,"basin_id":null,"missing_info":["model_name","basin_id","time_period"],"clarifications_needed":["请指定模型类型(如GR4J,XAJ)","请提供流域ID"],"confidence":0.6}

**重要**:
- 只输出JSON，不要其他文本
- confidence范围: 0.0-1.0
- 缺失信息加入missing_info列表
- 额外参数放入extra_params字典"""

    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process user query to extract intent and validate data (Enhanced).
        处理用户查询以提取意图并验证数据（增强版）。

        Args:
            input_data: User query and context
                {
                    "query": str,
                    "context": dict (optional)
                }

        Returns:
            Dict containing intent analysis result with task_type decision
                {
                    "success": True,
                    "intent_result": {
                        "task_type": "...",  # 🆕
                        "intent": "...",
                        "model_name": "...",
                        "basin_id": "...",
                        ...
                    }
                }
        """
        query = input_data.get("query", "")
        context = input_data.get("context", {})

        logger.info(f"[IntentAgent] Processing query: {query}")

        try:
            # Step 1: Call LLM to analyze intent (基础信息提取)
            intent_result = self._analyze_intent(query, context)

            # Check if LLM call failed (indicated by "error" field in intent_result)
            if "error" in intent_result and intent_result.get("confidence", 1.0) == 0.0:
                logger.error(f"[IntentAgent] LLM analysis failed: {intent_result['error']}")
                return {
                    "success": False,
                    "error": f"LLM analysis failed: {intent_result['error']}",
                    "intent_result": intent_result  # Include partial result for debugging
                }

            # Step 2: 🆕 Decide task type (战略决策)
            task_type = self._decide_task_type(query, intent_result)
            intent_result["task_type"] = task_type
            logger.info(f"[IntentAgent] Task type: {task_type}")

            # Step 3: 🆕 Complete missing information (信息补全)
            intent_result = self._complete_missing_info(intent_result, query)

            # Step 4: 🆕 Add strategy information (if needed)
            if task_type == "iterative_optimization":
                intent_result["strategy"] = {
                    "phases": ["coarse_calibration", "fine_calibration"],
                    "trigger": "boundary_effect"
                }

            # Step 5: 🆕 Extract extended analysis needs (if needed)
            if task_type == "extended_analysis":
                intent_result["needs"] = self._extract_analysis_needs(query)

            # Step 6: 🆕 Extract repetition count (if needed)
            if task_type == "repeated_experiment":
                intent_result["n_repeats"] = self._extract_n_repeats(query)

            # Step 7: Validate data availability (existing logic)
            if intent_result.get("basin_id"):
                data_valid = self._validate_data(intent_result)
                intent_result["data_available"] = data_valid

            # Store result in context
            self.update_context("intent_result", intent_result)

            logger.info(f"[IntentAgent] Intent: {intent_result.get('intent')}, Task: {task_type}")

            return {
                "success": True,
                "intent_result": intent_result
            }

        except Exception as e:
            logger.error(f"[IntentAgent] Processing failed: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def _analyze_intent(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze user query to extract intent using LLM.
        使用 LLM 分析用户查询以提取意图。

        Args:
            query: User query
            context: Additional context (may include feedback)

        Returns:
            Intent analysis result
        """
        # =====================================================================
        # Dynamic Prompt System
        # =====================================================================
        if self.use_dynamic_prompt and self.prompt_manager:
            # Create agent context
            agent_context = self.prompt_manager.create_context(
                agent_name="IntentAgent",
                user_query=query,
                workspace_dir=self.workspace_dir
            )

            # Add feedback if present
            if context and "feedback" in context:
                for fb in context["feedback"]:
                    agent_context.add_feedback(fb)

            # Add iteration info if present
            if context and "iteration" in context:
                for _ in range(context["iteration"]):
                    agent_context.increment_iteration()

            # Build dynamic prompt with algorithm schema
            final_prompt = self.prompt_manager.build_prompt(
                "IntentAgent",
                agent_context,
                include_schema=True,  # Include algorithm parameters schema
                include_feedback=True
            )

            # Add instruction
            final_prompt += "\n\nRespond with ONLY valid JSON, no extra text."

            logger.debug(f"[IntentAgent] Using dynamic prompt (length: {len(final_prompt)} chars)")

        # =====================================================================
        # Static Prompt System (Fallback)
        # =====================================================================
        else:
            # Build user prompt (original method)
            context_str = ""
            if context:
                context_str = f"\n\nAdditional context:\n{context}"

            final_prompt = f"""Analyze this hydrological modeling query and extract structured information.

User query: "{query}"{context_str}

Instructions:
1. Determine the primary intent (calibration/evaluation/simulation/extension)
2. Extract model name, basin ID, time period if mentioned
3. Identify missing information
4. Suggest clarification questions if needed

Respond with ONLY valid JSON, no extra text."""

            logger.debug(f"[IntentAgent] Using static prompt")

        # =====================================================================
        # Call LLM
        # =====================================================================
        try:
            # Try to use generate_json if available
            if hasattr(self.llm, 'generate_json'):
                response = self.llm.generate_json(
                    system_prompt=self.system_prompt if not self.use_dynamic_prompt else "",
                    user_prompt=final_prompt,
                    temperature=0.2  # Low temperature for structured output
                )
                logger.debug(f"[IntentAgent] LLM response (JSON): {response}")
                return self._validate_and_normalize_response(response)

        except (AttributeError, NotImplementedError, Exception) as e:
            logger.debug(f"[IntentAgent] generate_json not available or failed: {str(e)}, falling back to text parsing")

        # Fallback: Use regular text generation and parse JSON
        import json
        import re

        try:
            response_text = self.call_llm(final_prompt, temperature=0.2)
            logger.debug(f"[IntentAgent] LLM raw response: {response_text[:200]}...")

            # Extract JSON from response text
            # Try multiple extraction strategies
            json_result = None

            # Strategy 1: Direct JSON parse (if response is pure JSON)
            try:
                json_result = json.loads(response_text.strip())
            except json.JSONDecodeError:
                pass

            # Strategy 2: Find JSON block between { }
            if json_result is None:
                # Find the first complete JSON object
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    try:
                        json_result = json.loads(json_str)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse extracted JSON: {str(e)}")

            # Strategy 3: Find JSON in code blocks (```json ... ```)
            if json_result is None:
                code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                if code_block_match:
                    json_str = code_block_match.group(1)
                    try:
                        json_result = json.loads(json_str)
                    except json.JSONDecodeError:
                        pass

            if json_result is not None:
                return self._validate_and_normalize_response(json_result)
            else:
                raise ValueError("Could not extract valid JSON from LLM response")

        except Exception as e:
            logger.error(f"[IntentAgent] Failed to parse LLM response: {str(e)}")
            # Return error response with fallback
            return {
                "intent": "unknown",
                "model_name": None,
                "basin_id": None,
                "time_period": None,
                "algorithm": "SCE_UA",
                "missing_info": ["all"],
                "clarifications_needed": ["Unable to parse query, please rephrase"],
                "confidence": 0.0,
                "error": str(e),
                "raw_response": response_text[:500] if 'response_text' in locals() else "No response"
            }

    def _validate_and_normalize_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and normalize LLM response to ensure consistent structure.
        验证并规范化 LLM 响应以确保结构一致。

        Args:
            response: Raw LLM response dictionary

        Returns:
            Normalized response with all required fields
        """
        # Ensure all required fields exist
        normalized = {
            "intent": response.get("intent", "unknown"),
            "model_name": response.get("model_name"),
            "basin_id": response.get("basin_id"),
            "time_period": response.get("time_period"),
            "algorithm": response.get("algorithm", "SCE_UA"),
            "extra_params": response.get("extra_params", {}),
            "missing_info": response.get("missing_info", []),
            "clarifications_needed": response.get("clarifications_needed", []),
            "confidence": response.get("confidence", 0.8)
        }

        # Normalize model_name to lowercase
        if normalized["model_name"]:
            normalized["model_name"] = str(normalized["model_name"]).lower()

        # Validate model_name against known models
        valid_models = ["xaj", "xaj_mz", "gr4j", "gr5j", "gr6j", "gr1y", "gr2m"]
        if normalized["model_name"] and normalized["model_name"] not in valid_models:
            logger.warning(f"Unknown model: {normalized['model_name']}, setting to None")
            normalized["model_name"] = None
            if "model_name" not in normalized["missing_info"]:
                normalized["missing_info"].append("model_name")

        # Validate intent
        valid_intents = ["calibration", "evaluation", "simulation", "extension", "unknown"]
        if normalized["intent"] not in valid_intents:
            logger.warning(f"Unknown intent: {normalized['intent']}, setting to 'unknown'")
            normalized["intent"] = "unknown"

        # Normalize algorithm
        if normalized["algorithm"]:
            normalized["algorithm"] = str(normalized["algorithm"]).upper().replace("-", "_")

        # Copy extension-specific fields if present
        if normalized["intent"] == "extension":
            normalized["task_type"] = response.get("task_type", "unknown")
            normalized["task_description"] = response.get("task_description", "")

        logger.debug(f"[IntentAgent] Normalized response: {normalized}")
        return normalized

    def _validate_data(self, intent_result: Dict[str, Any]) -> bool:
        """
        Validate data availability using hydrodataset.
        使用 hydrodataset 验证数据可用性。

        Args:
            intent_result: Intent analysis result containing basin_id

        Returns:
            True if data is available, False otherwise
        """
        if not self.has_hydrodataset:
            logger.warning("Cannot validate data: hydrodataset not available")
            return False

        basin_id = intent_result.get("basin_id")
        if not basin_id:
            return False

        try:
            # TODO: Implement actual data validation using hydrodataset
            # Example:
            # from hydrodataset import Camels
            # camels = Camels()
            # data = camels.read_target_cols(basin_id=basin_id, ...)
            # return data is not None

            logger.info(f"[IntentAgent] Data validation for basin {basin_id}: OK (placeholder)")
            return True

        except Exception as e:
            logger.error(f"[IntentAgent] Data validation failed: {str(e)}")
            return False

    def classify_intent(self, query: str) -> str:
        """
        Quick intent classification without full processing.
        快速意图分类，不进行完整处理。

        Args:
            query: User query

        Returns:
            Intent label (calibration/evaluation/simulation/extension)
        """
        result = self.process({"query": query})
        if result.get("success"):
            return result["intent_result"].get("intent", "unknown")
        return "unknown"

    # ===== 🆕 Phase 1 Enhancement Methods =====

    def _decide_task_type(self, query: str, intent_result: Dict[str, Any]) -> str:
        """
        决策任务类型（战略决策）。

        根据用户查询和提取的意图，决定后续处理方式。

        Args:
            query: 用户原始查询
            intent_result: LLM提取的意图信息

        Returns:
            Task type string
        """
        query_lower = query.lower()

        # 检测关键词 → 任务类型映射
        # 优先级从高到低

        # 🆕 0. 自动迭代率定（v4.0新功能）- 最高优先级
        # 关键词：迭代地去率定、直到NSE达到、自动运行
        auto_iter_keywords = ["迭代地", "迭代率定", "自动运行", "自动执行", "不断尝试", "直到nse", "直到 nse"]
        if any(kw in query_lower for kw in auto_iter_keywords):
            logger.debug("[IntentAgent] Detected: auto_iterative_calibration (v4.0)")
            # 提取NSE阈值和最大次数
            import re
            nse_match = re.search(r'nse\s*[>>=]+\s*(\d+\.?\d*)', query_lower)
            if nse_match:
                intent_result["nse_threshold"] = float(nse_match.group(1))
                logger.info(f"[IntentAgent] Extracted NSE threshold: {intent_result['nse_threshold']}")

            max_iter_match = re.search(r'最多\s*(\d+)|(\d+)\s*次', query_lower)
            if max_iter_match:
                max_iter = int(max_iter_match.group(1) or max_iter_match.group(2))
                intent_result["max_iterations"] = max_iter
                logger.info(f"[IntentAgent] Extracted max iterations: {max_iter}")

            return "auto_iterative_calibration"

        # 1. 重复实验（实验5）
        if any(kw in query_lower for kw in ["重复", "多次", "repeat", "multiple times", "不同种子", "different seed"]):
            logger.debug("[IntentAgent] Detected: repeated_experiment")
            return "repeated_experiment"

        # 2. 迭代优化（实验3 - 参数范围调整）
        if any(kw in query_lower for kw in ["迭代", "边界", "调整范围", "adaptive", "boundary", "iterative", "两阶段", "two-phase"]):
            logger.debug("[IntentAgent] Detected: iterative_optimization")
            return "iterative_optimization"

        # 3. 扩展分析（实验4）
        extended_keywords = ["径流系数", "runoff coefficient", "fdc", "flow duration", "历时曲线", "绘制", "画", "plot", "可视化", "visualization"]
        if any(kw in query_lower for kw in extended_keywords):
            logger.debug("[IntentAgent] Detected: extended_analysis")
            return "extended_analysis"

        # 4. 自定义数据路径（实验2C）
        if any(kw in query_lower for kw in ["d盘", "d:", "文件夹", "folder", "my_data", "自定义数据", "custom data"]):
            logger.debug("[IntentAgent] Detected: custom_data")
            return "custom_data"

        # 5. 批量处理（多流域/多算法）
        # 检测是否有多个流域或多个算法
        basins = self._extract_multiple_basins(query, intent_result)
        algorithms = self._extract_multiple_algorithms(query, intent_result)

        if len(basins) > 1 or len(algorithms) > 1:
            logger.debug(f"[IntentAgent] Detected: batch_processing (basins={len(basins)}, algorithms={len(algorithms)})")
            return "batch_processing"

        # 6. 信息补全（实验2B）
        # 检测缺失的关键信息
        missing = intent_result.get("missing_info", [])
        required_fields = ["model_name", "basin_id"]
        has_missing_required = any(field in missing for field in required_fields)

        if has_missing_required:
            logger.debug(f"[IntentAgent] Detected: info_completion (missing={missing})")
            return "info_completion"

        # 7. 标准率定（实验1，默认）
        logger.debug("[IntentAgent] Detected: standard_calibration (default)")
        return "standard_calibration"

    def _complete_missing_info(self, intent_result: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        补全缺失信息（智能填充默认值）。

        Args:
            intent_result: 当前意图结果
            query: 用户原始查询

        Returns:
            补全后的intent_result
        """
        # 1. 补全模型名称
        if not intent_result.get("model_name"):
            # 默认使用XAJ模型
            intent_result["model_name"] = "xaj"
            logger.info("[IntentAgent] Filled missing model_name: xaj (default)")

        # 2. 补全算法
        if not intent_result.get("algorithm"):
            intent_result["algorithm"] = "SCE_UA"
            logger.info("[IntentAgent] Filled missing algorithm: SCE_UA (default)")

        # 3. 补全时间范围
        if not intent_result.get("time_period"):
            # 使用默认的训练和测试时段
            intent_result["time_period"] = {
                "train": ["1990-01-01", "2000-12-31"],  # 默认10年训练
                "test": ["2001-01-01", "2005-12-31"]     # 默认5年测试
            }
            logger.info("[IntentAgent] Filled missing time_period: default 10y train + 5y test")

        # 4. 推断数据源（基于流域ID格式）
        basin_id = intent_result.get("basin_id", "")
        if basin_id and "data_source" not in intent_result:
            # 判断流域ID格式
            if basin_id.startswith("0") and len(basin_id) == 8 and basin_id.isdigit():
                # CAMELS_US格式：8位数字，以0开头
                intent_result["data_source"] = "camels_us"
                logger.info(f"[IntentAgent] Inferred data_source: camels_us (basin_id={basin_id})")
            elif "camels_" in basin_id.lower():
                intent_result["data_source"] = "camels_us"
                logger.info(f"[IntentAgent] Inferred data_source: camels_us (contains 'camels_')")
            else:
                intent_result["data_source"] = "unknown"
                logger.warning(f"[IntentAgent] Could not infer data_source for basin_id={basin_id}")

        # 5. 补全data_source_type（用于自定义数据）
        if intent_result.get("task_type") == "custom_data":
            # 从查询中提取数据路径
            data_path = self._extract_data_path(query)
            if data_path:
                intent_result["data_source_type"] = "selfmadehydrodataset"
                intent_result["data_source_path"] = data_path
                logger.info(f"[IntentAgent] Set data_source_type: selfmadehydrodataset, path={data_path}")

        # 6. 更新missing_info列表（移除已补全的）
        original_missing = set(intent_result.get("missing_info", []))
        completed_fields = set()

        if intent_result.get("model_name"):
            completed_fields.add("model_name")
        if intent_result.get("basin_id"):
            completed_fields.add("basin_id")
        if intent_result.get("time_period"):
            completed_fields.add("time_period")
        if intent_result.get("algorithm"):
            completed_fields.add("algorithm")

        still_missing = original_missing - completed_fields
        intent_result["missing_info"] = list(still_missing)

        if completed_fields:
            logger.info(f"[IntentAgent] Completed fields: {completed_fields}")

        return intent_result

    def _extract_analysis_needs(self, query: str) -> List[str]:
        """
        提取扩展分析需求（实验4）。

        Args:
            query: 用户查询

        Returns:
            需求列表，如 ["runoff_coefficient", "FDC"]
        """
        needs = []
        query_lower = query.lower()

        # 检测径流系数
        if any(kw in query_lower for kw in ["径流系数", "runoff coefficient"]):
            needs.append("runoff_coefficient")

        # 检测流路历时曲线
        if any(kw in query_lower for kw in ["fdc", "flow duration", "历时曲线"]):
            needs.append("FDC")

        # 其他可扩展的分析
        if any(kw in query_lower for kw in ["参数敏感性", "sensitivity"]):
            needs.append("parameter_sensitivity")

        logger.info(f"[IntentAgent] Extracted analysis needs: {needs}")
        return needs

    def _extract_n_repeats(self, query: str) -> int:
        """
        提取重复次数（实验5）。

        Args:
            query: 用户查询

        Returns:
            重复次数（默认10）
        """
        import re

        # 查找数字 + "次"/"times"
        patterns = [
            r'(\d+)\s*次',  # "10次"
            r'重复\s*(\d+)',  # "重复10"
            r'(\d+)\s*times',  # "10 times"
            r'repeat\s*(\d+)',  # "repeat 10"
        ]

        for pattern in patterns:
            match = re.search(pattern, query.lower())
            if match:
                n = int(match.group(1))
                logger.info(f"[IntentAgent] Extracted n_repeats: {n}")
                return n

        # 默认10次
        logger.info("[IntentAgent] Using default n_repeats: 10")
        return 10

    def _extract_data_path(self, query: str) -> Optional[str]:
        """
        提取自定义数据路径（实验2C）。

        Args:
            query: 用户查询

        Returns:
            数据路径或None
        """
        import re

        # 查找路径模式
        patterns = [
            r'([A-Za-z]:\\[^\s]+)',  # Windows路径：D:\path\to\data
            r'(/[^\s]+)',  # Unix路径：/path/to/data
            r'([A-Za-z]盘[^\s]+)',  # 中文路径：D盘\my_data
        ]

        for pattern in patterns:
            match = re.search(pattern, query)
            if match:
                path = match.group(1)
                logger.info(f"[IntentAgent] Extracted data_path: {path}")
                return path

        # 查找文件夹名称
        if "文件夹" in query or "folder" in query.lower():
            # 简单提取："my_data 文件夹" → "my_data"
            match = re.search(r'(\w+)\s*(?:文件夹|folder)', query, re.IGNORECASE)
            if match:
                folder_name = match.group(1)
                logger.info(f"[IntentAgent] Extracted folder name: {folder_name}")
                return folder_name

        return None

    def _extract_multiple_basins(self, query: str, intent_result: Dict[str, Any]) -> List[str]:
        """
        提取多个流域ID。

        Args:
            query: 用户查询
            intent_result: 意图结果

        Returns:
            流域ID列表
        """
        import re

        basins = []

        # 先从intent_result获取单一basin_id
        if intent_result.get("basin_id"):
            basins.append(intent_result["basin_id"])

        # 在查询中查找额外的流域ID（8位数字格式）
        pattern = r'\b(0\d{7})\b'  # CAMELS_US格式：0XXXXXXX
        matches = re.findall(pattern, query)
        for match in matches:
            if match not in basins:
                basins.append(match)

        return basins

    def _extract_multiple_algorithms(self, query: str, intent_result: Dict[str, Any]) -> List[str]:
        """
        提取多个算法。

        Args:
            query: 用户查询
            intent_result: 意图结果

        Returns:
            算法列表
        """
        algorithms = []

        # 先从intent_result获取单一algorithm
        if intent_result.get("algorithm"):
            algorithms.append(intent_result["algorithm"])

        query_lower = query.lower()

        # 检测查询中的多个算法
        algorithm_keywords = {
            "SCE_UA": ["sce-ua", "sce_ua", "sceua"],
            "GA": ["ga", "genetic", "遗传"],
            "DE": ["de", "differential evolution"],
            "PSO": ["pso", "particle swarm"]
        }

        for algo, keywords in algorithm_keywords.items():
            for kw in keywords:
                if kw in query_lower and algo not in algorithms:
                    algorithms.append(algo)
                    break

        return algorithms
