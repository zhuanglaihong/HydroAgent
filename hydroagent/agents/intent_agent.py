"""
Author: Claude & zhuanglaihong
Date: 2025-01-20 19:55:00
LastEditTime: 2025-01-20 19:55:00
LastEditors: Claude
Description: Intent and data validation agent (Exp 1 & 4)
             意图与数据智能体 - 负责意图分类和数据校验
FilePath: \HydroAgent\hydroagent\agents\intent_agent.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from typing import Dict, Any, Optional, List
from pathlib import Path
import logging

from ..core.base_agent import BaseAgent
from ..core.llm_interface import LLMInterface

logger = logging.getLogger(__name__)


class IntentAgent(BaseAgent):
    """
    Intent and data validation agent.
    意图与数据智能体。

    Responsibilities:
    - Intent classification (calibration / evaluation / simulation / extension)
    - Data availability validation using hydrodataset
    - Information completion (fill defaults if missing)
    - Query expansion and clarification

    Interacts with hydromodel only through hydrodataset module for data queries.
    """

    def __init__(
        self,
        llm_interface: LLMInterface,
        workspace_dir: Optional[Path] = None,
        **kwargs
    ):
        """
        Initialize IntentAgent.

        Args:
            llm_interface: LLM API interface
            workspace_dir: Working directory
            **kwargs: Additional configuration
        """
        super().__init__(
            name="IntentAgent",
            llm_interface=llm_interface,
            workspace_dir=workspace_dir,
            **kwargs
        )

        # Try to import hydrodataset for data validation
        try:
            from hydrodataset import CamelsUs
            self.has_hydrodataset = True
            logger.info("hydrodataset module available")
        except ImportError:
            self.has_hydrodataset = False
            logger.warning("hydrodataset not available, data validation disabled")

    def _get_default_system_prompt(self) -> str:
        """Return default system prompt for IntentAgent (optimized for speed)."""
        return """Extract intent from hydrological model queries (中文/English).

**Intents**: calibration(率定), evaluation(评估), simulation(模拟), extension(其他)
**Models**: xaj, xaj_mz, gr4j, gr5j, gr6j, gr1y, gr2m
**Entities**: model_name, basin_id, time_period, algorithm(default:SCE_UA)

**JSON Output**:
{"intent":"calibration","model_name":"gr4j","basin_id":"01013500","time_period":{"train":["2000-01-01","2010-12-31"],"test":["2011-01-01","2015-12-31"]},"algorithm":"SCE_UA","missing_info":[],"clarifications_needed":[],"confidence":0.9}

**Defaults**: No model→gr4j, No period→10yr+5yr, Missing→add to missing_info

**Examples**:
"率定GR4J，流域01013500" → {"intent":"calibration","model_name":"gr4j","basin_id":"01013500"...}
"Calibrate XAJ" → {"intent":"calibration","model_name":"xaj","basin_id":null,"missing_info":["basin_id","time_period"]...}

JSON only, no text."""

    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process user query to extract intent and validate data.
        处理用户查询以提取意图并验证数据。

        Args:
            input_data: User query and context
                {
                    "query": str,
                    "context": dict (optional)
                }

        Returns:
            Dict containing intent analysis result
        """
        query = input_data.get("query", "")
        context = input_data.get("context", {})

        logger.info(f"[IntentAgent] Processing query: {query}")

        try:
            # Call LLM to analyze intent
            intent_result = self._analyze_intent(query, context)

            # Validate data availability
            if intent_result.get("basin_id"):
                data_valid = self._validate_data(intent_result)
                intent_result["data_available"] = data_valid

            # Store result in context
            self.update_context("intent_result", intent_result)

            logger.info(f"[IntentAgent] Intent: {intent_result.get('intent')}")

            return {
                "success": True,
                "intent_result": intent_result
            }

        except Exception as e:
            logger.error(f"[IntentAgent] Processing failed: {str(e)}")
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
            context: Additional context

        Returns:
            Intent analysis result
        """
        # Build user prompt
        context_str = ""
        if context:
            context_str = f"\n\nAdditional context:\n{context}"

        user_prompt = f"""Analyze this hydrological modeling query and extract structured information.

User query: "{query}"{context_str}

Instructions:
1. Determine the primary intent (calibration/evaluation/simulation/extension)
2. Extract model name, basin ID, time period if mentioned
3. Identify missing information
4. Suggest clarification questions if needed

Respond with ONLY valid JSON, no extra text."""

        try:
            # Try to use generate_json if available
            if hasattr(self.llm, 'generate_json'):
                response = self.llm.generate_json(
                    system_prompt=self.system_prompt,
                    user_prompt=user_prompt,
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
            response_text = self.call_llm(user_prompt, temperature=0.2)
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
