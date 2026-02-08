"""
Author: Claude & zhuanglaihong
Date: 2025-11-20 19:55:00
LastEditTime: 2025-11-22 14:00:00
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
from ..utils.config_validator import validate_basin_id, ConfigValidator

logger = logging.getLogger(__name__)


# 任务类型定义（支持实验1-5）
TASK_TYPES = {
    "standard_calibration": "标准单任务率定（实验1）",
    "info_completion": "缺省信息补全型率定（实验2B）",
    "iterative_optimization": "两阶段迭代优化（实验3）",
    "repeated_experiment": "重复实验-多随机种子（实验5）",
    "extended_analysis": "扩展分析-超出hydromodel功能（实验4）",
    "batch_processing": "批量处理-多流域/多算法",
    "custom_data": "自定义数据路径（实验2C）",
}


class IntentAgent(BaseAgent):
    """
    Intent and data validation agent (Enhanced for Experiments 1-5).
    意图与数据智能体（增强版，支持实验1-5）。

    Responsibilities (Enhanced):
    1. **Intent classification** (calibration / evaluation / simulation / extension)
    2. **Task type decision** () - Decide "what to do" based on query complexity
       - standard_calibration: Simple single-basin calibration
       - info_completion: Query with missing information
       - iterative_optimization: Two-phase adaptive calibration
       - repeated_experiment: Multiple runs with different seeds
       - extended_analysis: Tasks beyond hydromodel (e.g., FDC plotting)
       - batch_processing: Multi-basin or multi-algorithm tasks
       - custom_data: Custom data path handling
    3. **Information completion** () - Fill missing fields with intelligent defaults
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
            "task_type": "...",  #  Task type classification
            "intent": "calibration",
            "model_name": "gr4j",
            "basin_ids": ["01013500"],
            "algorithm": "SCE_UA",
            "extra_params": {...},
            "strategy": {...},  #  Strategy information (if iterative)
            "needs": [...],     #  Extended analysis needs (if extended_analysis)
            "n_repeats": 10,    #  Number of repetitions (if repeated_experiment)
            ...
        }
    }
    """

    def __init__(
        self,
        llm_interface: LLMInterface,
        workspace_dir: Optional[Path] = None,
        use_dynamic_prompt: bool = True,
        **kwargs,
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
            **kwargs,
        )

        # Initialize config validator for parameter validation
        self.validator = ConfigValidator()

        # Dynamic Prompt System
        self.use_dynamic_prompt = use_dynamic_prompt
        if self.use_dynamic_prompt:
            self.prompt_manager = PromptManager()
            # Register static prompt skeleton
            self.prompt_manager.register_static_prompt(
                "IntentAgent", self._get_default_system_prompt()
            )
            # Load algorithm parameters schema for accurate parameter extraction
            self.prompt_manager.load_schema("algorithm_params")
            logger.info(
                "[IntentAgent] Dynamic prompt system enabled with algorithm schema"
            )
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
- extension (中文: 其他/绘图/可视化/分析/数据检查)

**支持的模型** (大小写不敏感):
- xaj, xaj_mz (新安江模型)
- gr4j, gr5j, gr6j (GR系列模型)
- gr1y, gr2m (年度/月度模型)

**关键信息提取**:
1. **模型名称** (model_name): 从查询中识别模型类型
   - 中文: "XAJ模型" → xaj, "GR4J模型" → gr4j
   - 英文: "XAJ model" → xaj, "calibrate GR4J" → gr4j

2. **流域ID** (basin_ids): 流域编号/站点编号（始终使用数组格式）
   - **单流域**: 使用basin_ids数组, 如["01013500"]
   - **多流域**: 使用basin_ids数组, 如["11532500", "12025000", "14301000"]
   - 关键词: "流域", "basin", "站点", "site", "批量"
   - 分隔符识别: 逗号","、顿号"、"、"和"、空格等
   - 格式: 数字编号如"01013500", "camels_11532500", "11532500"
   - **重要**: 即使只有一个流域，也必须使用数组格式basin_ids，不要使用basin_id

3. **时间段** (time_period): 训练和测试时期
   - 默认: 训练10年 + 测试5年
   - 格式: {"train": ["2000-01-01", "2010-12-31"], "test": ["2011-01-01", "2014-12-31"]}

4. **算法** (algorithm): 优化算法
   - 默认: "SCE_UA"
   - 其他: "DE", "PSO", "GA", "SCEUA", "SCE_UA"

5. **额外参数** (extra_params): **仅用于算法内部参数**
   - ⚠️ **CRITICAL**: 只包含算法参数（ngs, kstop, npop等），**不要包含迭代优化相关参数**
   - ⚠️ **不要在extra_params中设置**: rep, max_iterations（这些由系统自动处理）
   - 示例：只有用户明确说"ngs设为200"时才设置 {"ngs": 200}
   - **默认情况**: extra_params应该为空 {}

6. **迭代优化参数** (仅在query提到"最多X次"、"迭代优化"时需要):
   - 这些参数**不要放在extra_params中**
   - 会被单独提取到intent_result的顶层字段
   - 示例：max_iterations, nse_threshold, n_repeats

**输出格式** (必须是有效JSON):
{
  "intent": "calibration",
  "model_name": "gr4j",
  "basin_ids": ["01013500"],
  "time_period": {
    "train": ["2000-01-01", "2010-12-31"],
    "test": ["2011-01-01", "2014-12-31"]
  },
  "algorithm": "SCE_UA",
  "extra_params": {},
  "missing_info": [],
  "clarifications_needed": [],
  "confidence": 0.95
}

**示例**:

输入: "率定GR4J模型，流域01013500, 使用SCE-UA算法，算法迭代只需要500轮就行"
输出: {"intent":"calibration","model_name":"gr4j","basin_ids":["01013500"],"algorithm":"SCE_UA","extra_params":{"rep":500},"missing_info":[],"confidence":0.95}

输入: "率定GR4J模型流域14325000，迭代优化直到NSE≥0.65，最多3次"
输出: {"intent":"calibration","model_name":"gr4j","basin_ids":["14325000"],"algorithm":"SCE_UA","extra_params":{},"missing_info":[],"confidence":0.95}

输入: "用XAJ模型批量率定流域11532500,12025000,14301000,14306500,14325000"
输出: {"intent":"calibration","model_name":"xaj","basin_ids":["11532500","12025000","14301000","14306500","14325000"],"algorithm":"SCE_UA","missing_info":[],"confidence":0.95}

输入: "率定GR4J模型，流域02177000和03346000"
输出: {"intent":"calibration","model_name":"gr4j","basin_ids":["02177000","03346000"],"algorithm":"SCE_UA","missing_info":[],"confidence":0.9}

输入: "评估XAJ模型在流域11532500的表现"
输出: {"intent":"evaluation","model_name":"xaj","basin_ids":["11532500"],"algorithm":"SCE_UA","missing_info":[],"confidence":0.9}

输入: "Calibrate GR5J for basin camels_01013500"
输出: {"intent":"calibration","model_name":"gr5j","basin_ids":["camels_01013500"],"algorithm":"SCE_UA","missing_info":[],"confidence":0.9}

输入: "率定一个水文模型"
输出: {"intent":"calibration","model_name":null,"basin_ids":null,"missing_info":["model_name","basin_ids","time_period"],"clarifications_needed":["请指定模型类型(如GR4J,XAJ)","请提供流域ID"],"confidence":0.6}

输入: "检查流域01539000,02070000,14301000的数据质量"
输出: {"intent":"extension","model_name":null,"basin_ids":["01539000","02070000","14301000"],"time_period":{"train":["2000-01-01","2010-12-31"],"test":["2011-01-01","2014-12-31"]},"missing_info":[],"confidence":0.85}

输入: "验证流域数据是否可用"
输出: {"intent":"extension","model_name":null,"basin_ids":null,"missing_info":["basin_ids"],"clarifications_needed":["请提供流域ID"],"confidence":0.7}

**重要**:
- 只输出JSON，不要其他文本
- confidence范围: 0.0-1.0
- 缺失信息加入missing_info列表
- 额外参数放入extra_params字典

**工具系统说明**:
系统会根据识别的intent自动选择合适的执行模式:
- 数据验证查询(如"检查数据质量") → 使用validate_data工具
- 标准率定/评估 → 使用calibrate/evaluate工具链
- 扩展分析(如"计算径流系数") → 使用code_generation工具
你只需专注提取用户意图和参数,后续工具选择由系统自动完成。"""

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
                        "task_type": "...",  #
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
            # Step 0: 🆕 Check for compound task patterns (复合任务检测)
            compound_tasks = self._detect_compound_tasks(query)
            if compound_tasks:
                logger.info(f"[IntentAgent] Detected compound task with {len(compound_tasks)} subtasks")
                return {
                    "success": True,
                    "intent_result": {
                        "task_type": "compound_task",
                        "compound_tasks": compound_tasks,
                        "query": query,
                    }
                }

            # Step 1: Call LLM to analyze intent (基础信息提取)
            intent_result = self._analyze_intent(query, context)

            # Check if LLM call failed (indicated by "error" field in intent_result)
            if "error" in intent_result and intent_result.get("confidence", 1.0) == 0.0:
                logger.error(
                    f"[IntentAgent] LLM analysis failed: {intent_result['error']}"
                )
                return {
                    "success": False,
                    "error": f"LLM analysis failed: {intent_result['error']}",
                    "intent_result": intent_result,  # Include partial result for debugging
                }

            # Step 2:  Decide task type (战略决策)
            task_type = self._decide_task_type(query, intent_result)
            intent_result["task_type"] = task_type
            logger.info(f"[IntentAgent] Task type: {task_type}")

            # Step 3:  Complete missing information (信息补全)
            intent_result = self._complete_missing_info(intent_result, query)

            # Step 3.5:  Validate basin IDs format (流域ID格式验证)
            basin_ids = intent_result.get("basin_ids")
            if basin_ids:
                for basin_id in basin_ids:
                    validation_error = validate_basin_id(basin_id)
                    if validation_error:
                        logger.error(f"[IntentAgent] Basin ID validation failed for {basin_id}: {validation_error}")
                        return {
                            "success": False,
                            "error": f"流域{basin_id}验证失败: {validation_error}",
                            "error_type": "BasinIDValidationError",
                            "intent_result": intent_result,
                        }

            # Step 3.6:  Validate algorithm parameters (算法参数验证)
            algorithm = intent_result.get("algorithm")
            extra_params = intent_result.get("extra_params", {})

            if algorithm and extra_params:
                param_errors = self._validate_algorithm_params(algorithm, extra_params)
                if param_errors:
                    error_message = "\n".join(param_errors)
                    logger.error(f"[IntentAgent] Algorithm parameter validation failed:\n{error_message}")
                    return {
                        "success": False,
                        "error": f"算法参数验证失败：\n{error_message}",
                        "error_type": "AlgorithmParameterValidationError",
                        "validation_errors": param_errors,
                        "intent_result": intent_result,
                    }

            # Step 4:  Add strategy information (if needed)
            if task_type == "iterative_optimization":
                intent_result["strategy"] = {
                    "phases": ["coarse_calibration", "fine_calibration"],
                    "trigger": "boundary_effect",
                }

            # Step 5:  Extract extended analysis needs (if needed)
            if task_type == "extended_analysis":
                intent_result["needs"] = self._extract_analysis_needs(query)

            # Step 6:  Extract repetition count (if needed)
            if task_type == "repeated_experiment":
                intent_result["n_repeats"] = self._extract_n_repeats(query)

            # Step 7: Validate data availability (existing logic)
            if intent_result.get("basin_ids"):
                data_valid = self._validate_data(intent_result)
                intent_result["data_available"] = data_valid

            # Store result in context
            self.update_context("intent_result", intent_result)

            logger.info(
                f"[IntentAgent] Intent: {intent_result.get('intent')}, Task: {task_type}"
            )

            return {"success": True, "intent_result": intent_result}

        except Exception as e:
            logger.error(f"[IntentAgent] Processing failed: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}

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
                workspace_dir=self.workspace_dir,
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
                include_feedback=True,
            )

            # Add instruction
            final_prompt += "\n\nRespond with ONLY valid JSON, no extra text."

            logger.debug(
                f"[IntentAgent] Using dynamic prompt (length: {len(final_prompt)} chars)"
            )

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
            if hasattr(self.llm, "generate_json"):
                response = self.llm.generate_json(
                    system_prompt=(
                        self.system_prompt if not self.use_dynamic_prompt else ""
                    ),
                    user_prompt=final_prompt,
                    temperature=0.2,  # Low temperature for structured output
                )
                logger.info(f"[IntentAgent] LLM response (JSON): {response}")
                return self._validate_and_normalize_response(response)

        except (AttributeError, NotImplementedError, Exception) as e:
            logger.debug(
                f"[IntentAgent] generate_json not available or failed: {str(e)}, falling back to text parsing"
            )

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
                json_match = re.search(
                    r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", response_text, re.DOTALL
                )
                if json_match:
                    json_str = json_match.group(0)
                    try:
                        json_result = json.loads(json_str)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse extracted JSON: {str(e)}")

            # Strategy 3: Find JSON in code blocks (```json ... ```)
            if json_result is None:
                code_block_match = re.search(
                    r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL
                )
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
                "basin_ids": None,
                "time_period": None,
                "algorithm": "SCE_UA",
                "missing_info": ["all"],
                "clarifications_needed": ["Unable to parse query, please rephrase"],
                "confidence": 0.0,
                "error": str(e),
                "raw_response": (
                    response_text[:500]
                    if "response_text" in locals()
                    else "No response"
                ),
            }

    def _validate_and_normalize_response(
        self, response: Dict[str, Any]
    ) -> Dict[str, Any]:
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
            "basin_ids": response.get("basin_ids"),  # ⭐ 添加多流域支持
            "time_period": response.get("time_period"),
            "algorithm": response.get("algorithm", "SCE_UA"),
            "extra_params": response.get("extra_params", {}),
            "missing_info": response.get("missing_info", []),
            "clarifications_needed": response.get("clarifications_needed", []),
            "confidence": response.get("confidence", 0.8),
        }

        # Normalize basin_id/basin_ids to ALWAYS use basin_ids array format
        # hydromodel只接受basin_ids数组，即使单个流域也要用数组
        if normalized.get("basin_ids") and isinstance(normalized["basin_ids"], list):
            # 已经是basin_ids数组，保持不变
            logger.debug(f"[IntentAgent] Using basin_ids array: {normalized['basin_ids']}")
        elif normalized.get("basin_id"):
            # LLM返回了basin_id（单个），转换为basin_ids数组
            if isinstance(normalized["basin_id"], str):
                normalized["basin_ids"] = [normalized["basin_id"]]
            else:
                normalized["basin_ids"] = [str(normalized["basin_id"])]
            logger.debug(f"[IntentAgent] Converted basin_id to basin_ids array: {normalized['basin_ids']}")

        # 移除basin_id字段（hydromodel不使用它）
        if "basin_id" in normalized:
            del normalized["basin_id"]
            logger.debug("[IntentAgent] Removed basin_id field (using basin_ids only)")

        # Normalize model_name to lowercase
        if normalized["model_name"]:
            normalized["model_name"] = str(normalized["model_name"]).lower()

        # Validate model_name against known models
        valid_models = ["xaj", "xaj_mz", "gr4j", "gr5j", "gr6j", "gr1y", "gr2m"]
        if normalized["model_name"] and normalized["model_name"] not in valid_models:
            logger.warning(
                f"Unknown model: {normalized['model_name']}, setting to None"
            )
            normalized["model_name"] = None
            if "model_name" not in normalized["missing_info"]:
                normalized["missing_info"].append("model_name")

        # Validate intent
        valid_intents = [
            "calibration",
            "evaluation",
            "simulation",
            "extension",
            "unknown",
        ]
        if normalized["intent"] not in valid_intents:
            logger.warning(
                f"Unknown intent: {normalized['intent']}, setting to 'unknown'"
            )
            normalized["intent"] = "unknown"

        # Normalize algorithm
        if normalized["algorithm"]:
            normalized["algorithm"] = (
                str(normalized["algorithm"]).upper().replace("-", "_")
            )

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
            intent_result: Intent analysis result containing basin_ids

        Returns:
            True if data is available, False otherwise
        """
        if not self.has_hydrodataset:
            logger.warning("Cannot validate data: hydrodataset not available")
            return False

        basin_ids = intent_result.get("basin_ids")
        if not basin_ids:
            return False

        try:
            # TODO: Implement actual data validation using hydrodataset
            # Example:
            # from hydrodataset import Camels
            # camels = Camels()
            # data = camels.read_target_cols(basin_ids=basin_ids, ...)
            # return data is not None

            logger.info(
                f"[IntentAgent] Data validation for basins {basin_ids}: OK (placeholder)"
            )
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

    # =====  Phase 1 Enhancement Methods =====

    def _decide_task_type(self, query: str, intent_result: Dict[str, Any]) -> str:
        """
        决策任务类型（战略决策）- v5.1 混合策略版本。

        Strategy:
        1. 规则快速检测 (Rule-based detection)
        2. 复杂场景检测 (Detect conflicts/complexity)
        3. LLM智能分析 (LLM-based analysis for complex cases)

        Args:
            query: 用户原始查询
            intent_result: LLM提取的意图信息

        Returns:
            Task type string
        """
        # Step 1: 规则检测，收集所有匹配的task_type（带置信度）
        rule_matches = self._rule_based_detection_with_scores(query, intent_result)

        # Step 2: 检测是否需要LLM智能分析
        if len(rule_matches) > 1:
            # 多个规则匹配 → 需要LLM判断优先级
            logger.info(f"[IntentAgent] Multiple rule matches detected: {list(rule_matches.keys())}")
            logger.info("[IntentAgent] Using LLM for intelligent task type analysis...")

            task_type = self._llm_task_type_analysis(query, intent_result, rule_matches)
            logger.info(f"[IntentAgent] LLM selected task_type: {task_type}")

            # 根据LLM选择的task_type，设置必要的参数
            self._apply_task_type_parameters(query, intent_result, task_type)

            return task_type
        elif len(rule_matches) == 1:
            # 唯一规则匹配 → 直接返回
            task_type = list(rule_matches.keys())[0]
            logger.info(f"[IntentAgent] Single rule match: {task_type}")

            # 设置必要的参数
            self._apply_task_type_parameters(query, intent_result, task_type)

            return task_type
        else:
            # 🔧 修复：无规则匹配时，调用LLM智能判断，而不是直接默认
            logger.info("[IntentAgent] No rule matches, using LLM for intelligent task type analysis...")

            # 提供所有可能的task_type给LLM判断
            all_task_types = {
                "standard_calibration": 0.5,  # 默认候选，但置信度较低
                "iterative_optimization": 0.4,
                "extended_analysis": 0.3,
                "batch_processing": 0.3,
            }

            task_type = self._llm_task_type_analysis(query, intent_result, all_task_types)
            logger.info(f"[IntentAgent] LLM selected task_type (no rule match): {task_type}")

            # 设置必要的参数
            self._apply_task_type_parameters(query, intent_result, task_type)

            return task_type

    def _rule_based_detection_with_scores(
        self, query: str, intent_result: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        规则检测，返回所有匹配的task_type及置信度。

        Returns:
            Dict[task_type, confidence_score]
        """
        query_lower = query.lower()
        matches = {}

        # 检测1: 自动迭代率定（v4.0）- 明确特征关键词
        # 🔧 方案1修复: 移除"迭代地"、"迭代率定"以消除与iterative_optimization的重叠
        auto_iter_keywords = ["直到nse", "直到 nse", "直到达标", "直到满足", "自动运行", "自动执行", "不断尝试", "自动率定"]
        if any(kw in query_lower for kw in auto_iter_keywords):
            matches["auto_iterative_calibration"] = 0.95

        # 检测2: 重复实验
        if any(kw in query_lower for kw in ["重复", "多次", "repeat", "multiple times", "不同种子", "different seed"]):
            matches["repeated_experiment"] = 0.9

        # 检测3: 迭代优化（参数范围调整）- 明确特征关键词
        # 🔧 方案1修复: 移除"迭代地"、"迭代率定"以消除与auto_iterative_calibration的重叠
        iterative_keywords = ["边界", "调整范围", "调整参数范围", "重新率定", "adaptive", "boundary", "两阶段", "two-phase", "参数收敛"]
        # 🆕 增强：检测"如果...则..."模式（条件触发迭代）
        has_conditional_pattern = ("如果" in query_lower and ("则" in query_lower or "就" in query_lower)) or \
                                  ("if" in query_lower and "then" in query_lower)

        # 🔧 修复：检测算法迭代次数模式（如"迭代5000轮"），排除这种情况
        import re
        algorithm_iteration_pattern = r'(迭代|iteration)\s*\d+\s*(轮|次|代|iterations?)'
        has_algorithm_iteration = re.search(algorithm_iteration_pattern, query_lower)

        if (any(kw in query_lower for kw in iterative_keywords) or has_conditional_pattern) and not has_algorithm_iteration:
            # 🔧 方案1修复: 降低置信度，避免与auto_iterative_calibration冲突
            matches["iterative_optimization"] = 0.85

        # 检测4: 数据验证任务（只验证，不率定）
        validation_keywords = ["验证数据", "检查数据", "数据可用性", "数据质量", "validate data", "check data", "data availability", "data quality"]
        calibration_keywords = ["率定", "calibrate", "校准", "优化", "optimize"]

        has_validation = any(kw in query_lower for kw in validation_keywords)
        has_calibration = any(kw in query_lower for kw in calibration_keywords)

        # 如果只提到验证，没有提到率定，则是纯数据验证任务
        if has_validation and not has_calibration:
            matches["batch_processing"] = 0.95  # 使用batch_processing类型执行validate_data工具

        # 检测5: 批量处理（多流域/多算法/多模型）
        basins = self._extract_multiple_basins(query, intent_result)
        algorithms = self._extract_multiple_algorithms(query, intent_result)
        models = self._extract_multiple_models(query, intent_result)

        if len(basins) > 1 or len(algorithms) > 1 or len(models) > 1:
            # 如果已经匹配了数据验证，保持更高置信度
            if "batch_processing" not in matches:
                matches["batch_processing"] = 0.92  # 高置信度

        # 检测6: 扩展分析
        extended_keywords = ["径流系数", "runoff coefficient", "fdc", "flow duration", "历时曲线", "绘制", "画", "plot", "可视化", "visualization"]
        if any(kw in query_lower for kw in extended_keywords):
            matches["extended_analysis"] = 0.8

        # 检测7: 自定义数据路径
        if any(kw in query_lower for kw in ["d盘", "d:", "文件夹", "folder", "my_data", "自定义数据", "custom data"]):
            matches["custom_data"] = 0.9

        # 检测8: 信息补全
        missing = intent_result.get("missing_info", [])
        required_fields = ["model_name", "basin_ids"]
        has_missing_required = any(field in missing for field in required_fields)
        if has_missing_required:
            matches["info_completion"] = 0.7

        logger.debug(f"[IntentAgent] Rule-based matches: {matches}")
        return matches

    def _llm_task_type_analysis(
        self, query: str, intent_result: Dict[str, Any], rule_matches: Dict[str, float]
    ) -> str:
        """
        使用LLM智能分析复杂场景的task_type。

        当规则检测到多个匹配项时，使用LLM判断最合适的task_type。

        Args:
            query: 用户查询
            intent_result: 基础intent信息
            rule_matches: 规则匹配结果 {task_type: confidence}

        Returns:
            最合适的task_type
        """
        # 构建LLM提示词
        system_prompt = """你是一个水文建模任务类型分析专家。根据用户查询和规则检测结果，选择最合适的任务类型。

**任务类型说明** (🔧 v6.0.1 关键词重构):
1. **batch_processing**: 批量处理多个流域/算法/模型（可能包含后续分析）
   - 特征：多个流域、多个算法、"批量"等关键词
   - 示例："批量率定3个流域，完成后计算径流系数"

2. **extended_analysis**: 单流域率定 + 扩展分析（径流系数、FDC等）
   - 特征：单个流域 + 分析需求
   - 示例："率定流域01539000，完成后计算径流系数"

3. **iterative_optimization**: 参数范围自适应调整（两阶段率定）
   - 特征："边界"、"调整范围"、"参数收敛"、"如果...则..."条件语句
   - 示例："如果参数收敛到边界则调整范围重新率定"、"参数范围自适应调整"
   - ⚠️ 明确特征：不包含"直到NSE"、"直到达标"这类关键词

4. **repeated_experiment**: 重复实验
   - 特征："重复N次"、"不同种子"
   - 示例："重复率定5次"

5. **auto_iterative_calibration**: 自动迭代直到NSE达标（多次完整率定）
   - 特征："直到NSE"、"直到达标"、"自动运行"、"不断尝试"
   - 示例："自动率定直到NSE>0.7"、"不断尝试直到NSE达标，最多3次"
   - ⚠️ 明确特征：不包含"边界"、"调整范围"这类关键词

6. **custom_data**: 自定义数据路径
   - 特征：自定义数据路径
   - 示例："使用D盘的my_data数据"

7. **info_completion**: 信息补全
   - 特征：缺少必要信息
   - 示例："帮我率定一下"（缺流域、模型）

8. **standard_calibration**: 标准率定（默认）
   - 特征：简单的单流域率定
   - 示例："率定GR4J模型，流域01539000"

**优先级规则** (🔧 v6.0.1 明确区分):
1. 如果有**多个流域**且有**后续分析需求** → 选择 `batch_processing`（而非extended_analysis）
2. 如果只有**单个流域**且有**分析需求** → 选择 `extended_analysis`
3. 🆕 如果提到"直到NSE"/"直到达标" → 选择 `auto_iterative_calibration`（而非iterative_optimization）
4. 🆕 如果提到"边界"/"调整范围"/"参数收敛" → 选择 `iterative_optimization`（而非auto_iterative_calibration）
5. 其他情况根据主要意图选择

**输出格式**:
返回JSON: {"task_type": "...", "reason": "选择理由"}
"""

        # 安全获取basin信息
        basin_ids = intent_result.get('basin_ids') or []
        basin_count = len(basin_ids)
        basin_display = intent_result.get('basin_ids') or 'N/A'

        user_prompt = f"""请分析以下查询，选择最合适的任务类型。

**用户查询**: {query}

**基础信息**:
- 流域数量: {basin_count}
- 流域ID: {basin_display}
- 模型: {intent_result.get('model_name') or 'N/A'}
- 算法: {intent_result.get('algorithm') or 'N/A'}

**规则检测结果** (可能有多个匹配):
{', '.join([f'{k} (置信度{v})' for k, v in rule_matches.items()])}

请根据查询的**主要意图**和**关键特征**，选择最合适的任务类型。
特别注意：如果查询包含"批量"+"多个流域"+"完成后分析"，应该选择batch_processing。

只返回JSON格式，不要其他内容。"""

        try:
            response = self.llm.generate_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.1,
            )

            task_type = response.get("task_type", "standard_calibration")
            reason = response.get("reason", "")

            logger.info(f"[IntentAgent] LLM analysis reason: {reason}")

            # 验证返回的task_type是否在候选列表中
            valid_task_types = [
                "batch_processing", "extended_analysis", "iterative_optimization",
                "repeated_experiment", "auto_iterative_calibration", "custom_data",
                "info_completion", "standard_calibration"
            ]

            if task_type not in valid_task_types:
                logger.warning(f"[IntentAgent] LLM returned invalid task_type: {task_type}, using highest rule match")
                task_type = max(rule_matches, key=rule_matches.get)

            return task_type

        except Exception as e:
            logger.error(f"[IntentAgent] LLM task type analysis failed: {str(e)}")
            # Fallback: 返回规则匹配中置信度最高的
            return max(rule_matches, key=rule_matches.get)

    def _apply_task_type_parameters(
        self, query: str, intent_result: Dict[str, Any], task_type: str
    ):
        """
        根据task_type设置必要的参数。

        Args:
            query: 用户查询
            intent_result: intent结果（会被修改）
            task_type: 任务类型
        """
        import re

        if task_type == "auto_iterative_calibration" or task_type == "iterative_optimization":
            # 提取NSE阈值（支持多种表达）
            # 模式1: "NSE大于0.7" / "NSE>0.7" / "NSE≥0.7"
            nse_match = re.search(r"nse\s*[>>=≥]+\s*(\d+\.?\d*)", query.lower())
            if not nse_match:
                # 模式2: "NSE低于0.7" / "NSE小于0.7" / "NSE<0.7" / "NSE≤0.7"
                nse_match = re.search(r"nse\s*[<小低≤]+[于]?\s*(\d+\.?\d*)", query.lower())

            if nse_match:
                nse_value = float(nse_match.group(1))
                intent_result["nse_threshold"] = nse_value
                logger.info(f"[IntentAgent] Extracted NSE threshold: {nse_value}")
            else:
                # 默认值
                intent_result["nse_threshold"] = 0.7
                logger.info("[IntentAgent] No NSE threshold found, using default: 0.7")

            # 提取最大迭代次数（优化正则，避免误匹配算法迭代参数）
            # 🔧 方案1修复: 明确匹配"最多X次"模式，排除"迭代5000轮"等算法参数
            max_iter_match = re.search(r"最多\s*(\d+)\s*次?", query.lower())
            if not max_iter_match:
                # 备用模式: "X次迭代" / "X次优化"（但不包括"X轮"）
                max_iter_match = re.search(r"(\d+)\s*次[迭优]", query.lower())

            if max_iter_match:
                max_iter = int(max_iter_match.group(1))
                intent_result["max_iterations"] = max_iter
                logger.info(f"[IntentAgent] Extracted max iterations: {max_iter}")
            else:
                # 默认值
                intent_result["max_iterations"] = 10
                logger.info("[IntentAgent] No max iterations found, using default: 10")

        elif task_type == "batch_processing":
            # 提取多流域/算法/模型信息
            basins = self._extract_multiple_basins(query, intent_result)
            algorithms = self._extract_multiple_algorithms(query, intent_result)
            models = self._extract_multiple_models(query, intent_result)

            intent_result["basin_ids"] = basins
            intent_result["algorithms"] = algorithms
            intent_result["model_names"] = models

            logger.info(f"[IntentAgent] Stored basin_ids={basins}, algorithms={algorithms}, model_names={models}")

            # 🆕 检测是否有后续分析需求
            needs = self._extract_analysis_needs(query)
            if needs:
                intent_result["needs"] = needs
                logger.info(f"[IntentAgent] Batch processing with analysis needs: {needs}")

        elif task_type == "extended_analysis":
            # 提取分析需求
            needs = self._extract_analysis_needs(query)
            intent_result["needs"] = needs
            logger.info(f"[IntentAgent] Extended analysis needs: {needs}")

        elif task_type == "repeated_experiment":
            # 提取重复次数
            n_repeats = self._extract_n_repeats(query)
            intent_result["n_repeats"] = n_repeats
            logger.info(f"[IntentAgent] Repeated experiment: {n_repeats} times")

    def _complete_missing_info(
        self, intent_result: Dict[str, Any], query: str
    ) -> Dict[str, Any]:
        """
        补全缺失信息（智能填充默认值）。

        Args:
            intent_result: 当前意图结果
            query: 用户原始查询

        Returns:
            补全后的intent_result
        """
        # 1. 补全模型名称
        # 🔧 CRITICAL FIX: Don't overwrite model_name if model_names exists (batch_processing tasks)
        if not intent_result.get("model_name") and not intent_result.get("model_names"):
            # 默认使用XAJ模型
            intent_result["model_name"] = "xaj"
            logger.info("[IntentAgent] Filled missing model_name: xaj (default)")
        elif intent_result.get("model_names") and not intent_result.get("model_name"):
            # batch_processing任务已经有model_names，不需要填充model_name
            logger.info(f"[IntentAgent] Skipping model_name fill (model_names already set: {intent_result.get('model_names')})")

        # 2. 补全算法
        if not intent_result.get("algorithm"):
            intent_result["algorithm"] = "SCE_UA"
            logger.info("[IntentAgent] Filled missing algorithm: SCE_UA (default)")

        # 3. 补全时间范围
        if not intent_result.get("time_period"):
            # 使用默认的训练和测试时段
            intent_result["time_period"] = {
                "train": ["1990-01-01", "2000-12-31"],  # 默认10年训练
                "test": ["2001-01-01", "2005-12-31"],  # 默认5年测试
            }
            logger.info(
                "[IntentAgent] Filled missing time_period: default 10y train + 5y test"
            )

        # 4. 推断数据源（基于流域ID格式）
        basin_ids = intent_result.get("basin_ids", [])
        if basin_ids and "data_source" not in intent_result:
            # 使用第一个流域ID判断格式（假设同一批流域使用相同数据源）
            basin_id = basin_ids[0]
            # Type check to prevent crash on non-string objects
            if (
                isinstance(basin_id, str)
                and len(basin_id) == 8
                and basin_id.isdigit()
            ):
                # ⭐ CRITICAL FIX: CAMELS_US格式：8位数字（不管以什么开头）
                # CAMELS-US有很多流域不以0开头，如14325000, 12025000, 11532500等
                intent_result["data_source"] = "camels_us"
                logger.info(
                    f"[IntentAgent] Inferred data_source: camels_us (basin_ids={basin_ids})"
                )
            elif isinstance(basin_id, str) and "camels_" in basin_id.lower():
                intent_result["data_source"] = "camels_us"
                logger.info(
                    f"[IntentAgent] Inferred data_source: camels_us (contains 'camels_')"
                )
            else:
                intent_result["data_source"] = "unknown"
                logger.warning(
                    f"[IntentAgent] Could not infer data_source for basin_ids={basin_ids}"
                )

        # 5. 补全data_source_type（用于自定义数据）
        if intent_result.get("task_type") == "custom_data":
            # 从查询中提取数据路径
            data_path = self._extract_data_path(query)
            if data_path:
                intent_result["data_source_type"] = "selfmadehydrodataset"
                intent_result["data_source_path"] = data_path
                logger.info(
                    f"[IntentAgent] Set data_source_type: selfmadehydrodataset, path={data_path}"
                )

        # 6. 更新missing_info列表（移除已补全的）
        original_missing = set(intent_result.get("missing_info", []))
        completed_fields = set()

        if intent_result.get("model_name"):
            completed_fields.add("model_name")
        if intent_result.get("basin_ids"):
            completed_fields.add("basin_ids")
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
            r"(\d+)\s*次",  # "10次"
            r"重复\s*(\d+)",  # "重复10"
            r"(\d+)\s*times",  # "10 times"
            r"repeat\s*(\d+)",  # "repeat 10"
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
            r"([A-Za-z]:\\[^\s]+)",  # Windows路径：D:\path\to\data
            r"(/[^\s]+)",  # Unix路径：/path/to/data
            r"([A-Za-z]盘[^\s]+)",  # 中文路径：D盘\my_data
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
            match = re.search(r"(\w+)\s*(?:文件夹|folder)", query, re.IGNORECASE)
            if match:
                folder_name = match.group(1)
                logger.info(f"[IntentAgent] Extracted folder name: {folder_name}")
                return folder_name

        return None

    def _extract_multiple_basins(
        self, query: str, intent_result: Dict[str, Any]
    ) -> List[str]:
        """
        提取多个流域ID（优先使用LLM返回的basin_ids）。

        Args:
            query: 用户查询
            intent_result: 意图结果

        Returns:
            流域ID列表
        """
        # 1. 使用basin_ids（已在规范化阶段统一转换为数组格式）
        if intent_result.get("basin_ids") and isinstance(intent_result["basin_ids"], list):
            basins = intent_result["basin_ids"]
            logger.info(f"[IntentAgent] Using basin_ids: {basins}")
            return basins

        # 2. 都没有，返回空列表
        logger.warning("[IntentAgent] No basin_ids found in LLM result")
        return []

    def _extract_multiple_algorithms(
        self, query: str, intent_result: Dict[str, Any]
    ) -> List[str]:
        """
        提取多个算法。

        Args:
            query: 用户查询
            intent_result: 意图结果

        Returns:
            算法列表
        """
        algorithms = []

        # 先从intent_result获取algorithm（可能是单个值或列表）
        algo_value = intent_result.get("algorithm")
        if algo_value:
            # 情况1：algorithm是一个列表
            if isinstance(algo_value, list):
                algorithms.extend(algo_value)
            # 情况2：algorithm是一个字符串形式的列表（如"['SCE_UA', 'GA']"）
            elif (
                isinstance(algo_value, str)
                and algo_value.startswith("[")
                and algo_value.endswith("]")
            ):
                try:
                    import ast

                    parsed_list = ast.literal_eval(algo_value)
                    if isinstance(parsed_list, list):
                        algorithms.extend(parsed_list)
                    else:
                        algorithms.append(algo_value)
                except (ValueError, SyntaxError):
                    # 如果解析失败，作为单个算法处理
                    algorithms.append(algo_value)
            # 情况3：algorithm是单个字符串
            else:
                algorithms.append(algo_value)

        query_lower = query.lower()

        # 检测查询中的多个算法（只添加不重复的）
        algorithm_keywords = {
            "SCE_UA": ["sce-ua", "sce_ua", "sceua", "sce"],
            "GA": ["ga", "genetic", "遗传"],
            "SCIPY": ["scipy"],
        }

        for algo, keywords in algorithm_keywords.items():
            for kw in keywords:
                if kw in query_lower and algo not in algorithms:
                    algorithms.append(algo)
                    break

        # 去重并保持顺序
        seen = set()
        unique_algorithms = []
        for algo in algorithms:
            if algo not in seen:
                seen.add(algo)
                unique_algorithms.append(algo)

        return unique_algorithms

    def _extract_multiple_models(
        self, query: str, intent_result: Dict[str, Any]
    ) -> List[str]:
        """
        提取多个模型。

        Args:
            query: 用户查询
            intent_result: 意图结果

        Returns:
            模型列表
        """
        models = []

        # 先从intent_result获取model_name（可能是单个值或列表）
        model_value = intent_result.get("model_name")
        if model_value:
            # 情况1：model_name是一个列表
            if isinstance(model_value, list):
                models.extend(model_value)
            # 情况2：model_name是一个字符串形式的列表（如"['xaj', 'gr4j']"）
            elif (
                isinstance(model_value, str)
                and model_value.startswith("[")
                and model_value.endswith("]")
            ):
                try:
                    import ast

                    parsed_list = ast.literal_eval(model_value)
                    if isinstance(parsed_list, list):
                        models.extend(parsed_list)
                    else:
                        models.append(model_value)
                except (ValueError, SyntaxError):
                    # 如果解析失败，作为单个模型处理
                    models.append(model_value)
            # 情况3：model_name是单个字符串
            else:
                models.append(model_value)

        query_lower = query.lower()

        # 检测查询中的多个模型（只添加不重复的）
        model_keywords = {
            "xaj": ["xaj", "新安江"],
            "xaj_mz": ["xaj_mz", "xaj-mz"],
            "gr4j": ["gr4j", "gr-4j"],
            "gr5j": ["gr5j", "gr-5j"],
            "gr6j": ["gr6j", "gr-6j"],
            "gr1y": ["gr1y", "gr-1y"],
            "gr2m": ["gr2m", "gr-2m"],
        }

        for model, keywords in model_keywords.items():
            for kw in keywords:
                if kw in query_lower and model not in models:
                    models.append(model)
                    break

        # 去重并保持顺序
        seen = set()
        unique_models = []
        for model in models:
            if model not in seen:
                seen.add(model)
                unique_models.append(model)

        return unique_models

    def _validate_algorithm_params(
        self, algorithm: str, extra_params: Dict[str, Any]
    ) -> List[str]:
        """
        验证算法参数的合理性。

        Args:
            algorithm: 算法名称
            extra_params: 额外参数字典

        Returns:
            错误信息列表（如果为空则验证通过）
        """
        errors = []

        # 检查算法是否在验证范围内
        if algorithm not in self.validator.ALGORITHM_PARAM_RANGES:
            logger.debug(f"[IntentAgent] Algorithm {algorithm} not in validation range, skipping")
            return errors

        param_ranges = self.validator.ALGORITHM_PARAM_RANGES[algorithm]

        # 验证每个参数
        for param_name, param_value in extra_params.items():
            if param_name in param_ranges:
                error = self.validator.validate_algorithm_param(
                    algorithm, param_name, param_value, param_ranges[param_name]
                )
                if error:
                    errors.append(error)

        return errors

    def _detect_compound_tasks(self, query: str) -> Optional[List[Dict[str, Any]]]:
        """
        检测复合任务（如"率定...后，使用最优参数模拟..."）。

        Detects compound task patterns like:
        - "率定...后，模拟..." (calibrate...then simulate...)
        - "率定...然后评估..." (calibrate...then evaluate...)
        - "率定...接着分析..." (calibrate...then analyze...)

        Args:
            query: 用户查询

        Returns:
            复合任务列表，如果不是复合任务则返回None
            [
                {"query": "率定GR4J模型流域01013500", "intent": "calibration", ...},
                {"query": "使用最优参数模拟2015-2020期间的径流", "intent": "simulation", ...}
            ]
        """
        import re

        # 检测复合任务关键词
        compound_keywords = [
            r"后[，,、]?\s*(?:使用|用|再|并)",  # "后，使用"、"后用"、"后再"
            r"然后",  # "然后"
            r"接着",  # "接着"
            r"完成后",  # "完成后"
            r"之后",  # "之后"
        ]

        # 查找分隔位置
        split_positions = []
        for pattern in compound_keywords:
            for match in re.finditer(pattern, query):
                split_positions.append((match.start(), match.end(), match.group()))

        if not split_positions:
            return None

        logger.info(f"[IntentAgent] Detected compound task markers: {[m[2] for m in split_positions]}")

        # 按位置排序
        split_positions.sort(key=lambda x: x[0])

        # 分割查询
        subtask_queries = []
        last_end = 0

        for start, end, marker in split_positions:
            # 第一个子任务
            subtask1 = query[last_end:start].strip()
            if subtask1:
                subtask_queries.append(subtask1)
            last_end = end

        # 最后一个子任务
        final_subtask = query[last_end:].strip()
        if final_subtask:
            subtask_queries.append(final_subtask)

        if len(subtask_queries) < 2:
            return None

        logger.info(f"[IntentAgent] Split into {len(subtask_queries)} subtasks: {subtask_queries}")

        # 分析每个子任务
        compound_tasks = []
        shared_context = {}  # 共享上下文（流域、模型等）

        for idx, subtask_query in enumerate(subtask_queries):
            # 分析子任务
            subtask_result = self._analyze_intent(subtask_query, {})

            # 如果是第一个任务，保存共享上下文
            if idx == 0:
                shared_context = {
                    "model_name": subtask_result.get("model_name"),
                    "basin_ids": subtask_result.get("basin_ids"),
                    "algorithm": subtask_result.get("algorithm"),
                }

            # 如果后续任务缺少信息，从共享上下文补全
            if idx > 0:
                if not subtask_result.get("model_name") and shared_context.get("model_name"):
                    subtask_result["model_name"] = shared_context["model_name"]
                    logger.info(f"[IntentAgent] Inherited model_name: {shared_context['model_name']}")

                if not subtask_result.get("basin_ids") and shared_context.get("basin_ids"):
                    subtask_result["basin_ids"] = shared_context["basin_ids"]
                    logger.info(f"[IntentAgent] Inherited basin_ids: {shared_context['basin_ids']}")

                if not subtask_result.get("algorithm") and shared_context.get("algorithm"):
                    subtask_result["algorithm"] = shared_context["algorithm"]

                # 🆕 标记后续任务依赖前置任务的结果
                # 这样ToolOrchestrator可以跳过已在前置任务中完成的工具（如calibrate, evaluate）
                subtask_result["depends_on_previous"] = True
                logger.info(f"[IntentAgent] Subtask {idx + 1} marked as depending on previous task results")

            # 决定task_type
            task_type = self._decide_task_type(subtask_query, subtask_result)
            subtask_result["task_type"] = task_type

            # 补全缺失信息
            subtask_result = self._complete_missing_info(subtask_result, subtask_query)

            # 添加到复合任务列表
            compound_tasks.append({
                "task_id": f"task_{idx + 1}",
                "query": subtask_query,
                "intent_result": subtask_result,
                "sequence_order": idx + 1,
                "depends_on": f"task_{idx}" if idx > 0 else None,  # 🆕 添加依赖关系
            })

            logger.info(f"[IntentAgent] Subtask {idx + 1}: intent={subtask_result.get('intent')}, task_type={task_type}")

        return compound_tasks
