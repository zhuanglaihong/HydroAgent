"""
Author: Claude
Date: 2025-11-22 16:30:00
LastEditTime: 2025-11-22 16:30:00
LastEditors: Claude
Description: Interpreter Agent - LLM-driven hydromodel config generation
             解释器智能体 - 基于LLM的hydromodel配置生成
FilePath: /HydroAgent/hydroagent/agents/interpreter_agent.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from typing import Dict, Any, Optional, List
from pathlib import Path
import json
import logging
import re

from ..core.base_agent import BaseAgent
from ..core.llm_interface import LLMInterface
from ..utils.path_manager import PathManager
from configs import config

logger = logging.getLogger(__name__)


class InterpreterAgent(BaseAgent):
    """
    Interpreter Agent - Generates hydromodel config using LLM.
    解释器智能体 - 使用LLM生成hydromodel配置。

    Responsibilities (职责):
    1. Parse prompts from TaskPlanner (解析TaskPlanner的提示词)
    2. Use LLM to generate hydromodel config JSON (使用LLM生成配置JSON)
    3. Validate generated config (验证生成的配置)
    4. Self-correction if validation fails (验证失败时自我修正)
    5. Return hydromodel-compatible config dict (返回hydromodel兼容的配置字典)

    Key Design:
    - LLM-driven (not rule-based like old ConfigAgent)
    - Takes structured prompts from TaskPlanner
    - Outputs standardized hydromodel config format
    - Handles self-correction via LLM feedback loop
    """

    def __init__(
        self,
        llm_interface: LLMInterface,
        workspace_dir: Optional[Path] = None,
        max_correction_attempts: int = 3,
        **kwargs,
    ):
        """
        Initialize InterpreterAgent.

        Args:
            llm_interface: LLM API interface
            workspace_dir: Working directory for results
            max_correction_attempts: Maximum attempts for self-correction
            **kwargs: Additional configuration
        """
        super().__init__(
            name="InterpreterAgent",
            llm_interface=llm_interface,
            workspace_dir=workspace_dir,
            **kwargs,
        )

        self.max_correction_attempts = max_correction_attempts

        # Load system prompt from file or use default
        self.system_prompt = self._load_system_prompt()

    def _get_default_system_prompt(self) -> str:
        """
        Return default system prompt for InterpreterAgent.
        Dynamically injects algorithm parameters from config.py.
        """
        # Load algorithm defaults from config.py
        sce_ua_params = getattr(
            config,
            "DEFAULT_SCE_UA_PARAMS",
            {
                "rep": 5000,
                "ngs": 7,
                "kstop": 3,
                "pcento": 0.0001,
                "peps": 0.001,
                "random_seed": 1234,
            },
        )
        ga_params = getattr(
            config,
            "DEFAULT_GA_PARAMS",
            {
                "generations": 100,
                "population_size": 50,
                "crossover_prob": 0.9,
                "mutation_prob": 0.1,
            },
        )
        de_params = getattr(
            config,
            "DEFAULT_DE_PARAMS",
            {"max_generations": 100, "pop_size": 50, "F": 0.5, "CR": 0.9},
        )

        # Format algorithm parameters section dynamically
        sce_ua_section = "\n".join([f"- {k}: {v}" for k, v in sce_ua_params.items()])
        ga_section = "\n".join([f"- {k}: {v}" for k, v in ga_params.items()])
        de_section = "\n".join([f"- {k}: {v}" for k, v in de_params.items()])

        return f"""You are the Interpreter Agent of HydroAgent.

Your role is to generate hydromodel-compatible configuration dictionaries from task prompts.

**TASK TYPES**:
1. **Hydromodel tasks** (calibrate/evaluate/simulate): Generate full hydromodel config
2. **Custom analysis tasks** (custom_analysis): Generate minimal config with metadata only

**CRITICAL REQUIREMENTS**:
1. Output MUST be valid JSON
2. For hydromodel tasks, config MUST follow the unified format with these sections:
   - data_cfgs
   - model_cfgs
   - training_cfgs
   - evaluation_cfgs (optional)
3. For custom_analysis tasks, generate MINIMAL config (see below)
4. All required fields must be present
5. Use exact field names (case-sensitive)
6. **experiment_name**: MUST be empty string "" to avoid nested directories
   - Use "" for flat structure (recommended)
   - OLD (deprecated): "{{model_name}}_{{algorithm}}_{{task_type}}" creates nested dirs

**Configuration Structure**:

```json
{{
  "data_cfgs": {{
    "data_source_type": "camels_us" or "custom",
    "data_source_path": null or "/path/to/data",
    "basin_ids": ["12025000"],
    "warmup_length": 365,
    "variables": ["precipitation", "potential_evapotranspiration", "streamflow"],
    "train_period": ["1985-10-01", "1995-09-30"],
    "test_period": ["2005-10-01", "2014-09-30"]
  }},
  "model_cfgs": {{
    "model_name": "xaj" | "gr4j" | "gr5j" | "gr6j",
    "model_params": {{
      "source_type": "sources",
      "source_book": "HF",
      "kernel_size": 15
    }}
  }},
  "training_cfgs": {{
    "algorithm_name": "SCE_UA" | "GA" |  "scipy",
    "algorithm_params": {{
      // Algorithm-specific parameters (see schema below)
    }},
    "loss_config": {{
      "type": "time_series",
      "obj_func": "RMSE"
    }},
    "param_range_file": null,
    "output_dir": "results",
    "experiment_name": "",  // MUST be empty string to avoid nested directories
    "random_seed": 1234,
    "save_config": true
  }},
  "evaluation_cfgs": {{
    "metrics": ["NSE", "RMSE", "KGE", "PBIAS"],
    "save_results": true,
    "plot_results": true
  }}
}}
```

**Algorithm Parameters (from configs/config.py)**:

SCE_UA:
{sce_ua_section}

GA:
{ga_section}

DE:
{de_section}

**Custom Analysis Tasks (task_type: custom_analysis)**:

For custom_analysis tasks (e.g., runoff coefficient, FDC curves), generate a MINIMAL config:

```json
{{
  "task_metadata": {{
    "task_type": "custom_analysis",
    "analysis_type": "runoff_coefficient" or "FDC" or other,
    "basin_id": "01013500",
    "model_name": "xaj"
  }}
}}
```

**DO NOT** generate data_cfgs, model_cfgs, or training_cfgs for custom_analysis tasks.
These tasks will be handled by code generation, not hydromodel execution.

**Response Format**:
ONLY output the JSON config. No explanations, no markdown code blocks, just pure JSON.

If you include explanations, wrap the JSON in ```json ... ``` tags.
"""

    def _load_system_prompt(self) -> str:
        """Load system prompt from file or use default."""
        prompt_file = (
            Path(__file__).parent.parent / "resources" / "interpreter_agent_prompt.txt"
        )

        if prompt_file.exists():
            try:
                with open(prompt_file, "r", encoding="utf-8") as f:
                    prompt = f.read()
                logger.info(
                    f"[InterpreterAgent] Loaded system prompt from {prompt_file}"
                )
                return prompt
            except Exception as e:
                logger.warning(f"[InterpreterAgent] Failed to load prompt file: {e}")

        return self._get_default_system_prompt()

    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate hydromodel config from TaskPlanner prompt.
        从TaskPlanner提示词生成hydromodel配置。

        Args:
            input_data: Subtask from TaskPlanner
                {
                    "subtask": {
                        "task_id": "task_1",
                        "prompt": "...",
                        "parameters": {...}
                    },
                    "intent_result": {...}  # Optional: for context
                }

        Returns:
            Dict containing:
                {
                    "success": True,
                    "config": {...},  # hydromodel-compatible config
                    "task_id": "task_1"
                }
        """
        subtask = input_data.get("subtask", {})
        intent_result = input_data.get("intent_result", {})

        task_id = subtask.get("task_id", "unknown")
        prompt = subtask.get("prompt", "")
        parameters = subtask.get("parameters", {})

        logger.info(f"[InterpreterAgent] Processing subtask: {task_id}")

        try:
            # Step 1: Generate config with LLM
            config = self._generate_config_with_llm(prompt, parameters)

            # Step 2: Validate config
            is_valid, validation_errors = self._validate_config(config)

            # Step 3: Self-correction if needed
            correction_attempt = 0
            while not is_valid and correction_attempt < self.max_correction_attempts:
                logger.warning(
                    f"[InterpreterAgent] Validation failed (attempt {correction_attempt + 1}): "
                    f"{validation_errors}"
                )

                # Use LLM to fix errors
                config = self._self_correct(
                    config, validation_errors, prompt, parameters
                )

                # Re-validate
                is_valid, validation_errors = self._validate_config(config)
                correction_attempt += 1

            if not is_valid:
                logger.error(
                    f"[InterpreterAgent] Validation failed after {correction_attempt} attempts"
                )
                return {
                    "success": False,
                    "error": "Config validation failed",
                    "validation_errors": validation_errors,
                    "task_id": task_id,
                }

            # Step 4: Apply workspace directory (only for hydromodel tasks)
            # ⭐ Use PathManager for unified path handling
            if self.workspace_dir and "training_cfgs" in config:
                config = PathManager.configure_hydromodel_output(
                    config=config,
                    session_dir=self.workspace_dir,
                    task_id=task_id,
                    use_flat_structure=True,  # 使用扁平结构，避免嵌套
                )
                logger.info(f"[InterpreterAgent] Path configured by PathManager")

            # Step 5: Add parameters to config for RunnerAgent to detect task type
            # ⭐ CRITICAL: RunnerAgent needs config["parameters"]["task_type"] to route correctly
            config["parameters"] = parameters.copy()  # Copy to avoid modifying original

            # ⭐ BUG FIX: Add task_type from subtask (not in parameters dict)
            task_type = subtask.get("task_type")
            if task_type:
                config["parameters"]["task_type"] = task_type
                logger.info(f"[InterpreterAgent] Set task_type in config: {task_type}")

            logger.info(
                f"[InterpreterAgent] Config generated successfully for {task_id}"
            )

            return {"success": True, "config": config, "task_id": task_id}

        except Exception as e:
            logger.error(
                f"[InterpreterAgent] Config generation failed: {str(e)}", exc_info=True
            )
            return {"success": False, "error": str(e), "task_id": task_id}

    def _generate_config_with_llm(
        self, prompt: str, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Use LLM to generate config from prompt.
        使用LLM从提示词生成配置。

        Args:
            prompt: Complete prompt from TaskPlanner
            parameters: Subtask parameters

        Returns:
            Generated config dict
        """
        # Construct user message
        user_message = f"{prompt}\n\n**直接输出JSON配置，不要任何解释。**"

        # Call LLM
        try:
            # Try to use generate_json for direct JSON parsing
            config = self.llm.generate_json(
                system_prompt=self.system_prompt,
                user_prompt=user_message,
                temperature=0.1,  # Low temperature for consistent output
            )
            return config
        except Exception as e:
            logger.warning(
                f"[InterpreterAgent] generate_json failed, falling back to generate: {e}"
            )
            # Fallback to generate and parse manually
            response = self.llm.generate(
                system_prompt=self.system_prompt,
                user_prompt=user_message,
                temperature=0.1,
            )
            # Parse JSON from response
            config = self._parse_llm_response(response)

        return config

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """
        Parse JSON config from LLM response.
        从LLM响应中解析JSON配置。

        Args:
            response: Raw LLM response

        Returns:
            Parsed config dict

        Raises:
            ValueError: If JSON parsing fails
        """
        if not response or not response.strip():
            logger.error("[InterpreterAgent] Received empty response from LLM")
            raise ValueError("LLM returned empty response")

        # Try to extract JSON from markdown code blocks
        json_match = re.search(r"```json\s*\n(.*?)\n```", response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            logger.info("[InterpreterAgent] Extracted JSON from markdown code block")
        else:
            # Try to find JSON directly
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                logger.info("[InterpreterAgent] Extracted JSON from response body")
            else:
                json_str = response
                logger.warning(
                    "[InterpreterAgent] No JSON pattern found, using entire response"
                )

        # Parse JSON
        try:
            config = json.loads(json_str)
            logger.info(
                f"[InterpreterAgent] Successfully parsed JSON config with {len(config)} sections"
            )
            return config
        except json.JSONDecodeError as e:
            logger.error(f"[InterpreterAgent] JSON parsing failed: {e}")
            logger.error(
                f"[InterpreterAgent] Response length: {len(response)} characters"
            )
            logger.error(
                f"[InterpreterAgent] Response preview (first 500 chars): {response[:500]}"
            )
            logger.error(
                f"[InterpreterAgent] Extracted JSON string (first 500 chars): {json_str[:500]}"
            )
            raise ValueError(f"Failed to parse JSON from LLM response: {e}")

    def _validate_config(self, config: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate configuration dict.
        验证配置字典。

        Args:
            config: Configuration to validate

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Check if this is a custom_analysis task (minimal config)
        task_metadata = config.get("task_metadata", {})
        if task_metadata.get("task_type") == "custom_analysis":
            # For custom_analysis, only validate task_metadata
            if not task_metadata.get("analysis_type"):
                errors.append("task_metadata.analysis_type is required")
            if not task_metadata.get("basin_id"):
                errors.append("task_metadata.basin_id is required")
            if not task_metadata.get("model_name"):
                errors.append("task_metadata.model_name is required")

            is_valid = len(errors) == 0
            return is_valid, errors

        # For hydromodel tasks, check required top-level sections
        required_sections = ["data_cfgs", "model_cfgs", "training_cfgs"]
        for section in required_sections:
            if section not in config:
                errors.append(f"Missing required section: {section}")

        # Validate data_cfgs
        if "data_cfgs" in config:
            data_cfgs = config["data_cfgs"]

            # Required fields
            if not data_cfgs.get("basin_ids"):
                errors.append("data_cfgs.basin_ids is required")
            elif not isinstance(data_cfgs["basin_ids"], list):
                errors.append("data_cfgs.basin_ids must be a list")

            if not data_cfgs.get("train_period"):
                errors.append("data_cfgs.train_period is required")
            elif len(data_cfgs.get("train_period", [])) != 2:
                errors.append("data_cfgs.train_period must have exactly 2 dates")

            # Variables
            if not data_cfgs.get("variables"):
                errors.append("data_cfgs.variables is required")

        # Validate model_cfgs
        if "model_cfgs" in config:
            model_cfgs = config["model_cfgs"]

            if not model_cfgs.get("model_name"):
                errors.append("model_cfgs.model_name is required")
            else:
                valid_models = ["xaj", "xaj_mz", "gr4j", "gr5j", "gr6j", "gr1y", "gr2m"]
                if model_cfgs["model_name"] not in valid_models:
                    errors.append(
                        f"Invalid model_name: {model_cfgs['model_name']}. "
                        f"Must be one of: {', '.join(valid_models)}"
                    )

        # Validate training_cfgs
        if "training_cfgs" in config:
            training_cfgs = config["training_cfgs"]

            if not training_cfgs.get("algorithm_name"):
                errors.append("training_cfgs.algorithm_name is required")
            else:
                valid_algorithms = ["SCE_UA", "GA", "DE", "PSO", "scipy"]
                if training_cfgs["algorithm_name"] not in valid_algorithms:
                    errors.append(
                        f"Invalid algorithm_name: {training_cfgs['algorithm_name']}. "
                        f"Must be one of: {', '.join(valid_algorithms)}"
                    )

            # Check algorithm_params exists
            if "algorithm_params" not in training_cfgs:
                errors.append("training_cfgs.algorithm_params is required")

        is_valid = len(errors) == 0
        return is_valid, errors

    def _self_correct(
        self,
        config: Dict[str, Any],
        errors: List[str],
        original_prompt: str,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Use LLM to fix validation errors.
        使用LLM修正验证错误。

        Args:
            config: Current config (possibly invalid)
            errors: List of validation errors
            original_prompt: Original task prompt
            parameters: Subtask parameters

        Returns:
            Corrected config dict
        """
        error_message = "\n".join(f"- {e}" for e in errors)

        correction_prompt = f"""
之前生成的配置有以下错误：

{error_message}

**原始任务**:
{original_prompt}

**当前配置** (有错误):
```json
{json.dumps(config, indent=2, ensure_ascii=False)}
```

**请修正这些错误，输出完整的正确配置（纯JSON格式）**。
"""

        # Call LLM for correction
        try:
            # Try to use generate_json for direct JSON parsing
            corrected_config = self.llm.generate_json(
                system_prompt=self.system_prompt,
                user_prompt=correction_prompt,
                temperature=0.1,
            )
            logger.info("[InterpreterAgent] Config corrected via LLM (generate_json)")
            return corrected_config
        except Exception as e:
            logger.warning(
                f"[InterpreterAgent] generate_json failed in correction: {e}"
            )
            try:
                # Fallback to generate and parse manually
                response = self.llm.generate(
                    system_prompt=self.system_prompt,
                    user_prompt=correction_prompt,
                    temperature=0.1,
                )
                corrected_config = self._parse_llm_response(response)
                logger.info(
                    "[InterpreterAgent] Config corrected via LLM (generate + parse)"
                )
                return corrected_config
            except Exception as e2:
                logger.error(f"[InterpreterAgent] Self-correction failed: {e2}")
                # Return original config if correction fails
                return config

    def batch_process(self, subtasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process multiple subtasks in batch.
        批量处理多个子任务。

        Args:
            subtasks: List of subtask dicts from TaskPlanner

        Returns:
            List of results
        """
        results = []

        for subtask in subtasks:
            result = self.process({"subtask": subtask})
            results.append(result)

        return results
