"""
Author: Claude & zhuanglaihong
Date: 2025-01-20 20:00:00
LastEditTime: 2025-01-20 20:00:00
LastEditors: Claude
Description: Configuration schema validator for hydromodel configs (Tech 4.1)
             配置模式校验器 - 用于验证 hydromodel 配置文件
FilePath: \\HydroAgent\\hydroagent\\utils\\schema_validator.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path
import logging
import yaml
import json
from datetime import datetime

logger = logging.getLogger(__name__)


class SchemaValidator:
    """
    Schema validator for hydromodel configuration files.
    hydromodel 配置文件的模式校验器。

    Purpose (Tech 4.1):
    - Ensure Config Agent output conforms to hydromodel API
    - Avoid "hallucination" parameters
    - Pre-flight check before calling hydromodel
    - Provide detailed error messages for corrections

    Based on hydromodel's configs/example_config.yaml
    """

    def __init__(self, schema_path: Optional[Path] = None):
        """
        Initialize SchemaValidator.

        Args:
            schema_path: Path to JSON schema definition file
        """
        self.schema_path = schema_path
        self.schema = self._load_schema() if schema_path else self._get_default_schema()

    def _load_schema(self) -> Dict[str, Any]:
        """
        Load schema from JSON file.
        从 JSON 文件加载模式。

        Returns:
            Schema dictionary
        """
        if not self.schema_path.exists():
            logger.warning(f"Schema file not found: {self.schema_path}")
            return self._get_default_schema()

        try:
            with open(self.schema_path, "r", encoding="utf-8") as f:
                schema = json.load(f)
            logger.info(f"Loaded schema from {self.schema_path}")
            return schema
        except Exception as e:
            logger.error(f"Failed to load schema: {str(e)}")
            return self._get_default_schema()

    def _get_default_schema(self) -> Dict[str, Any]:
        """
        Get default schema definition based on hydromodel API.
        获取基于 hydromodel API 的默认模式定义。

        Returns:
            Default schema dictionary
        """
        return {
            "required_fields": ["model_name", "basin_id", "train_period"],
            "optional_fields": [
                "exp_name",
                "test_period",
                "data",
                "training_cfgs",
                "warmup",
            ],
            "model_name": {
                "type": "string",
                "enum": ["xaj", "xaj_mz", "gr4j", "gr5j", "gr6j", "gr1y", "gr2m"],
            },
            "algorithm_name": {"type": "string", "enum": ["SCE_UA", "GA", "scipy"]},
            "time_period": {
                "type": "array",
                "items": {"type": "string", "format": "date"},  # YYYY-MM-DD
                "minItems": 2,
                "maxItems": 2,
            },
            "training_cfgs": {
                "type": "object",
                "properties": {
                    "algorithm": {"ref": "algorithm_name"},
                    "ngs": {"type": "integer", "minimum": 1},
                    "npg": {"type": "integer", "minimum": 1},
                    "npt": {"type": "integer", "minimum": 1},
                    "rep": {"type": "integer", "minimum": 1},
                    "maxn": {"type": "integer", "minimum": 100},
                },
            },
        }

    def validate(self, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate configuration against schema.
        根据模式验证配置。

        Args:
            config: Configuration dictionary to validate

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Check required fields
        errors.extend(self._check_required_fields(config))

        # Validate model_name
        errors.extend(self._validate_model_name(config))

        # Validate algorithm
        errors.extend(self._validate_algorithm(config))

        # Validate time periods
        errors.extend(self._validate_time_periods(config))

        # Validate training_cfgs
        errors.extend(self._validate_training_cfgs(config))

        # Check for unknown fields (potential hallucinations)
        errors.extend(self._check_unknown_fields(config))

        is_valid = len(errors) == 0

        if is_valid:
            logger.info("[SchemaValidator] Configuration is valid")
        else:
            logger.warning(
                f"[SchemaValidator] Validation failed with {len(errors)} errors"
            )

        return is_valid, errors

    def _check_required_fields(self, config: Dict[str, Any]) -> List[str]:
        """Check if all required fields are present."""
        errors = []
        required = self.schema.get("required_fields", [])

        for field in required:
            if field not in config:
                errors.append(f"Missing required field: '{field}'")

        return errors

    def _validate_model_name(self, config: Dict[str, Any]) -> List[str]:
        """Validate model_name field."""
        errors = []

        if "model_name" not in config:
            return errors  # Already caught by required fields check

        model_name = config["model_name"]
        valid_models = self.schema["model_name"]["enum"]

        if model_name not in valid_models:
            errors.append(
                f"Invalid model_name: '{model_name}'. "
                f"Must be one of: {', '.join(valid_models)}"
            )

        return errors

    def _validate_algorithm(self, config: Dict[str, Any]) -> List[str]:
        """Validate algorithm in training_cfgs."""
        errors = []

        if "training_cfgs" not in config:
            return errors

        training_cfgs = config["training_cfgs"]
        if not isinstance(training_cfgs, dict):
            errors.append("training_cfgs must be a dictionary")
            return errors

        if "algorithm" not in training_cfgs:
            errors.append("training_cfgs.algorithm is required")
            return errors

        algorithm = training_cfgs["algorithm"]
        valid_algorithms = self.schema["algorithm_name"]["enum"]

        if algorithm not in valid_algorithms:
            errors.append(
                f"Invalid algorithm: '{algorithm}'. "
                f"Must be one of: {', '.join(valid_algorithms)}"
            )

        return errors

    def _validate_time_periods(self, config: Dict[str, Any]) -> List[str]:
        """Validate time period formats."""
        errors = []

        for period_field in ["train_period", "test_period"]:
            if period_field not in config:
                if period_field == "train_period":
                    errors.append(f"Missing required field: '{period_field}'")
                continue

            period = config[period_field]

            # Check if it's a list/array
            if not isinstance(period, (list, tuple)):
                errors.append(f"{period_field} must be an array [start_date, end_date]")
                continue

            # Check length
            if len(period) != 2:
                errors.append(f"{period_field} must have exactly 2 dates [start, end]")
                continue

            # Validate date formats
            for i, date_str in enumerate(period):
                if not self._is_valid_date(date_str):
                    errors.append(
                        f"{period_field}[{i}] = '{date_str}' is not a valid date. "
                        f"Use format: YYYY-MM-DD"
                    )

            # Check logical order (start < end)
            if (
                len(period) == 2
                and self._is_valid_date(period[0])
                and self._is_valid_date(period[1])
            ):
                try:
                    start = datetime.strptime(period[0], "%Y-%m-%d")
                    end = datetime.strptime(period[1], "%Y-%m-%d")
                    if start >= end:
                        errors.append(
                            f"{period_field}: start date must be before end date"
                        )
                except Exception:
                    pass  # Date format errors already caught above

        return errors

    def _validate_training_cfgs(self, config: Dict[str, Any]) -> List[str]:
        """Validate training_cfgs parameters."""
        errors = []

        if "training_cfgs" not in config:
            return errors

        training_cfgs = config["training_cfgs"]
        if not isinstance(training_cfgs, dict):
            return errors  # Already caught earlier

        schema_training = self.schema.get("training_cfgs", {})
        properties = schema_training.get("properties", {})

        # Validate numeric parameters
        for param_name, param_schema in properties.items():
            if param_name not in training_cfgs:
                continue  # Optional parameters

            value = training_cfgs[param_name]

            # Check type
            if param_schema.get("type") == "integer":
                if not isinstance(value, int):
                    errors.append(
                        f"training_cfgs.{param_name} must be an integer, got {type(value).__name__}"
                    )
                    continue

                # Check minimum
                if "minimum" in param_schema:
                    minimum = param_schema["minimum"]
                    if value < minimum:
                        errors.append(
                            f"training_cfgs.{param_name} = {value} is below minimum {minimum}"
                        )

        return errors

    def _check_unknown_fields(self, config: Dict[str, Any]) -> List[str]:
        """Check for unknown fields that might be hallucinations."""
        warnings = []

        known_fields = set(
            self.schema["required_fields"] + self.schema["optional_fields"]
        )
        config_fields = set(config.keys())

        unknown_fields = config_fields - known_fields

        if unknown_fields:
            warnings.append(
                f"Warning: Unknown fields detected (possible hallucinations): "
                f"{', '.join(unknown_fields)}"
            )

        return warnings

    def _is_valid_date(self, date_str: str) -> bool:
        """
        Check if string is valid date in YYYY-MM-DD format.
        检查字符串是否为有效的 YYYY-MM-DD 格式日期。

        Args:
            date_str: Date string to validate

        Returns:
            True if valid date format
        """
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except (ValueError, TypeError):
            return False

    def validate_file(self, config_path: Path) -> Tuple[bool, List[str]]:
        """
        Validate a YAML configuration file.
        验证 YAML 配置文件。

        Args:
            config_path: Path to YAML configuration file

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            logger.info(f"[SchemaValidator] Validating {config_path}")
            return self.validate(config)

        except Exception as e:
            logger.error(f"[SchemaValidator] Failed to load config file: {str(e)}")
            return False, [f"Failed to load configuration file: {str(e)}"]

    def get_schema(self) -> Dict[str, Any]:
        """
        Get current schema definition.

        Returns:
            Schema dictionary
        """
        return self.schema.copy()
