"""
Author: Claude & zhuanglaihong
Date: 2025-01-20 21:00:00
LastEditTime: 2025-01-20 21:00:00
LastEditors: Claude
Description: Configuration generation agent - generates hydromodel config dict
             配置生成智能体 - 生成 hydromodel 配置字典
FilePath: \\HydroAgent\\hydroagent\\agents\\config_agent.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from typing import Dict, Any, Optional, List
from pathlib import Path
from copy import deepcopy
import logging

from ..core.base_agent import BaseAgent
from ..core.llm_interface import LLMInterface
from configs import config

logger = logging.getLogger(__name__)


class ConfigAgent(BaseAgent):
    """
    Configuration generation agent.
    配置生成智能体。

    Key Design:
    - Does NOT generate YAML files
    - Modifies default config dict based on user intent
    - Returns unified config format (not simplified format)
    - Config dict is directly passed to hydromodel API

    Workflow:
    1. Get default config from get_default_calibration_config()
    2. Modify fields based on IntentAgent output
    3. Validate the modified config
    4. Return config dict (not file path!)

    关键设计：
    - 不生成 YAML 文件
    - 基于用户意图修改默认配置 dict
    - 返回统一格式配置（不是简化格式）
    - 配置 dict 直接传递给 hydromodel API
    """

    def __init__(
        self,
        llm_interface: LLMInterface,
        workspace_dir: Optional[Path] = None,
        hydro_settings: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """
        Initialize ConfigAgent.

        Args:
            llm_interface: LLM API interface
            workspace_dir: Working directory for results
            hydro_settings: Settings from ~/hydro_setting.yml
            **kwargs: Additional configuration
        """
        super().__init__(
            name="ConfigAgent",
            llm_interface=llm_interface,
            workspace_dir=workspace_dir,
            **kwargs
        )
        self.hydro_settings = hydro_settings or {}

    def _get_default_system_prompt(self) -> str:
        """Return default system prompt for ConfigAgent."""
        return """You are the Configuration Agent of HydroAgent.

Your job is to help validate and refine hydromodel configurations.
You DO NOT generate YAML files - you help adjust configuration parameters.

Key responsibilities:
1. Suggest appropriate algorithm parameters
2. Validate time periods and data ranges
3. Recommend parameter tuning strategies
4. Identify potential configuration issues

Always provide clear, actionable suggestions."""

    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate hydromodel configuration dict based on intent.
        根据意图生成 hydromodel 配置字典。

        Args:
            input_data: Intent analysis result from IntentAgent
                {
                    "intent_result": {
                        "intent": "calibration",
                        "model_name": "gr4j",
                        "basin_id": "01013500",
                        "time_period": {...},
                        "algorithm": "SCE_UA",
                        ...
                    }
                }

        Returns:
            Dict containing:
                {
                    "success": True,
                    "config": {...},  # Unified format config dict
                    "config_summary": "..."  # Human-readable summary
                }
        """
        intent_result = input_data.get("intent_result", {})

        logger.info(f"[ConfigAgent] Generating config for intent: {intent_result.get('intent')}")

        try:
            # Step 1: Get default calibration config
            config = self._get_default_config()

            # Step 2: Modify config based on intent
            config = self._apply_intent_to_config(config, intent_result)

            # Step 3: Validate config
            is_valid, validation_errors = self._validate_config(config)
            if not is_valid:
                logger.error(f"[ConfigAgent] Validation failed: {validation_errors}")
                return {
                    "success": False,
                    "error": "Configuration validation failed",
                    "validation_errors": validation_errors
                }

            # Step 4: Generate human-readable summary
            summary = self._generate_config_summary(config, intent_result)

            logger.info(f"[ConfigAgent] Configuration generated successfully")

            return {
                "success": True,
                "config": config,
                "config_summary": summary
            }

        except Exception as e:
            logger.error(f"[ConfigAgent] Configuration generation failed: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def _get_default_config(self) -> Dict[str, Any]:
        """
        Get default calibration configuration.
        获取默认率定配置。

        This replicates get_default_calibration_config() from hydromodel.
        这复制了 hydromodel 的 get_default_calibration_config()。

        Returns:
            Default config dict in unified format
        """
        # Import here to avoid circular dependency
        try:
            from hydromodel.configs.config_manager import get_default_calibration_config
            config = get_default_calibration_config()
            logger.debug("[ConfigAgent] Loaded default config from hydromodel")
            return config
        except ImportError:
            logger.warning("[ConfigAgent] hydromodel not available, using built-in default")
            return self._get_builtin_default_config()

    def _get_builtin_default_config(self) -> Dict[str, Any]:
        """
        Get built-in default configuration (fallback).
        获取内置默认配置（后备方案）。

        Returns:
            Default config dict
        """
        return {
            "data_cfgs": {
                "data_source_type": "camels_us",
                "data_source_path": None,
                "basin_ids": ["01013500"],
                "warmup_length": config.DEFAULT_WARMUP_DAYS,
                "variables": [
                    "precipitation",
                    "potential_evapotranspiration",
                    "streamflow",
                ],
                "train_period": config.DEFAULT_TRAIN_PERIOD,
                "valid_period": ["2006-07-01", "2007-09-30"],  # Optional, not used in current workflow
                "test_period": config.DEFAULT_TEST_PERIOD,
            },
            "model_cfgs": {
                "model_name": "xaj",
                "model_params": {
                    "source_type": "sources",
                    "source_book": "HF",
                    "kernel_size": 15,
                },
            },
            "training_cfgs": {
                "algorithm_name": "SCE_UA",
                "algorithm_params": config.DEFAULT_SCE_UA_PARAMS.copy(),  # Use defaults from config.py
                "loss_config": {
                    "type": "time_series",
                    "obj_func": config.DEFAULT_OBJECTIVE,
                },
                "param_range_file": None,
                "output_dir": "results",
                "experiment_name": None,
                "random_seed": config.DEFAULT_SCE_UA_PARAMS["random_seed"],
                "save_config": True,
            },
            "evaluation_cfgs": {
                "metrics": ["NSE", "RMSE", "KGE", "PBIAS"],
                "save_results": True,
                "plot_results": True,
                "validation_split": 0.2,
                "bootstrap_samples": None,
            },
        }

    def _apply_intent_to_config(
        self,
        config: Dict[str, Any],
        intent_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply intent result to config dict.
        将意图结果应用到配置字典。

        Args:
            config: Base configuration dict
            intent_result: Intent analysis result

        Returns:
            Modified configuration dict
        """
        # Make a deep copy to avoid modifying original
        config = deepcopy(config)

        # Apply model name
        if intent_result.get("model_name"):
            config["model_cfgs"]["model_name"] = intent_result["model_name"]
            logger.debug(f"[ConfigAgent] Set model_name: {intent_result['model_name']}")

        # Apply basin_id
        if intent_result.get("basin_id"):
            config["data_cfgs"]["basin_ids"] = [intent_result["basin_id"]]
            logger.debug(f"[ConfigAgent] Set basin_ids: [{intent_result['basin_id']}]")

        # Apply time periods
        time_period = intent_result.get("time_period")
        if time_period:
            if "train" in time_period and time_period["train"]:
                config["data_cfgs"]["train_period"] = time_period["train"]
                logger.debug(f"[ConfigAgent] Set train_period: {time_period['train']}")

            if "test" in time_period and time_period["test"]:
                config["data_cfgs"]["test_period"] = time_period["test"]
                logger.debug(f"[ConfigAgent] Set test_period: {time_period['test']}")

            # If only train period is specified, auto-generate test period
            if "train" in time_period and "test" not in time_period:
                train_end = time_period["train"][1]
                # Simple heuristic: test period starts after train period
                # This could be improved with date manipulation
                logger.info("[ConfigAgent] Test period not specified, keeping default")

        # Apply algorithm
        if intent_result.get("algorithm"):
            config["training_cfgs"]["algorithm_name"] = intent_result["algorithm"]
            logger.debug(f"[ConfigAgent] Set algorithm_name: {intent_result['algorithm']}")

        # Apply algorithm-specific parameters based on model complexity
        model_name = config["model_cfgs"]["model_name"]
        self._adjust_algorithm_params(config, model_name)

        # Apply user-specified extra_params (overrides defaults)
        extra_params = intent_result.get("extra_params", {})
        if extra_params:
            for param_name, param_value in extra_params.items():
                config["training_cfgs"]["algorithm_params"][param_name] = param_value
                logger.info(f"[ConfigAgent] Applied extra_param: {param_name}={param_value}")

        # Set output directory to workspace
        if self.workspace_dir:
            config["training_cfgs"]["output_dir"] = str(self.workspace_dir)

        # Generate experiment name if not set
        if not config["training_cfgs"]["experiment_name"]:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            model = config["model_cfgs"]["model_name"]
            algorithm = config["training_cfgs"]["algorithm_name"]
            config["training_cfgs"]["experiment_name"] = f"{model}_{algorithm}_{timestamp}"

        return config

    def _adjust_algorithm_params(
        self,
        config: Dict[str, Any],
        model_name: str
    ) -> None:
        """
        Adjust algorithm parameters based on model complexity.
        根据模型复杂度调整算法参数。

        Args:
            config: Configuration dict to modify (in-place)
            model_name: Model name
        """
        # Model complexity mapping (number of parameters)
        model_complexity = {
            "gr4j": 4,
            "gr5j": 5,
            "gr6j": 6,
            "xaj": 15,
            "xaj_mz": 15,
            "gr1y": 1,
            "gr2m": 2,
        }

        num_params = model_complexity.get(model_name, 10)  # Default to 10

        algorithm = config["training_cfgs"]["algorithm_name"]

        if algorithm == "SCE_UA":
            # Adjust SCE-UA parameters based on model complexity
            # ngs: number of complexes (2-20, more for complex models)
            # rep: number of evolution steps (1000-10000)
            # Use defaults from config.py as baseline

            if num_params <= 5:
                # Simple models: use default values
                config["training_cfgs"]["algorithm_params"]["ngs"] = config.DEFAULT_SCE_UA_PARAMS["ngs"]
                config["training_cfgs"]["algorithm_params"]["rep"] = config.DEFAULT_SCE_UA_PARAMS["rep"]
            elif num_params <= 10:
                # Medium models: increase complexity
                config["training_cfgs"]["algorithm_params"]["ngs"] = config.DEFAULT_SCE_UA_PARAMS["ngs"] + 200
                config["training_cfgs"]["algorithm_params"]["rep"] = config.DEFAULT_SCE_UA_PARAMS["rep"] * 2
            else:
                # Complex models: reduce complexes but more iterations
                config["training_cfgs"]["algorithm_params"]["ngs"] = 100
                config["training_cfgs"]["algorithm_params"]["rep"] = config.DEFAULT_SCE_UA_PARAMS["rep"] * 3

            logger.debug(
                f"[ConfigAgent] Adjusted SCE_UA params for {model_name} "
                f"(ngs={config['training_cfgs']['algorithm_params']['ngs']}, "
                f"rep={config['training_cfgs']['algorithm_params']['rep']})"
            )

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

        # Check required top-level sections
        required_sections = ["data_cfgs", "model_cfgs", "training_cfgs"]
        for section in required_sections:
            if section not in config:
                errors.append(f"Missing required section: {section}")

        # Validate data_cfgs
        if "data_cfgs" in config:
            data_cfgs = config["data_cfgs"]

            if not data_cfgs.get("basin_ids"):
                errors.append("data_cfgs.basin_ids is required")

            if not data_cfgs.get("train_period"):
                errors.append("data_cfgs.train_period is required")
            elif len(data_cfgs["train_period"]) != 2:
                errors.append("data_cfgs.train_period must have exactly 2 dates")

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
                valid_algorithms = ["SCE_UA", "GA", "scipy"]
                if training_cfgs["algorithm_name"] not in valid_algorithms:
                    errors.append(
                        f"Invalid algorithm_name: {training_cfgs['algorithm_name']}. "
                        f"Must be one of: {', '.join(valid_algorithms)}"
                    )

        is_valid = len(errors) == 0
        return is_valid, errors

    def _generate_config_summary(
        self,
        config: Dict[str, Any],
        intent_result: Dict[str, Any]
    ) -> str:
        """
        Generate human-readable configuration summary.
        生成人类可读的配置摘要。

        Args:
            config: Final configuration dict
            intent_result: Original intent result

        Returns:
            Summary string
        """
        lines = []

        lines.append("=== Configuration Summary ===")
        lines.append("")

        # Model info
        model_name = config["model_cfgs"]["model_name"]
        lines.append(f"Model: {model_name}")

        # Data info
        basin_ids = config["data_cfgs"]["basin_ids"]
        train_period = config["data_cfgs"]["train_period"]
        test_period = config["data_cfgs"].get("test_period", ["Not specified"])

        lines.append(f"Basins: {', '.join(basin_ids)}")
        lines.append(f"Training: {train_period[0]} to {train_period[1]}")
        if test_period[0] != "Not specified":
            lines.append(f"Testing: {test_period[0]} to {test_period[1]}")

        # Training info
        algorithm = config["training_cfgs"]["algorithm_name"]
        params = config["training_cfgs"]["algorithm_params"]

        lines.append(f"Algorithm: {algorithm}")
        if algorithm == "SCE_UA":
            lines.append(f"  - Complexes (ngs): {params.get('ngs', 'N/A')}")
            lines.append(f"  - Evolution steps (rep): {params.get('rep', 'N/A')}")

        # Loss function
        loss_config = config["training_cfgs"].get("loss_config", {})
        obj_func = loss_config.get("obj_func", "RMSE")
        lines.append(f"Objective: {obj_func}")

        lines.append("")
        lines.append("============================")

        return "\n".join(lines)

    def get_config_for_hydromodel(self, intent_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convenience method to get config dict directly.
        便捷方法，直接获取配置字典。

        Args:
            intent_result: Intent analysis result

        Returns:
            Config dict ready for hydromodel API

        Raises:
            ValueError: If config generation fails
        """
        result = self.process({"intent_result": intent_result})

        if not result["success"]:
            raise ValueError(f"Config generation failed: {result.get('error')}")

        return result["config"]
