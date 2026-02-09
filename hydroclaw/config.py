"""
Author: HydroClaw Team
Date: 2026-02-08
Description: Configuration loader and hydromodel config builder.
"""

import json
import os
from pathlib import Path
from typing import Any


# Default configuration values
DEFAULTS = {
    "llm": {
        "model": "deepseek-v3.1",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key_env": "LLM_API_KEY",
        "temperature": 0.1,
        "max_tokens": 20000,
        "timeout": 60,
        "supports_function_calling": None,  # None = auto-detect
    },
    "defaults": {
        "model": "xaj",
        "algorithm": "SCE_UA",
        "train_period": ["2000-01-01", "2009-12-31"],
        "test_period": ["2010-01-01", "2014-12-31"],
        "warmup": 365,
    },
    "algorithms": {
        "SCE_UA": {"rep": 500, "ngs": 200, "kstop": 500, "peps": 0.1, "pcento": 0.1, "random_seed": 1234},
        "GA": {"pop_size": 40, "n_generations": 25, "cx_prob": 0.7, "mut_prob": 0.2, "random_seed": 1234},
        "scipy": {"method": "SLSQP", "max_iterations": 500, "ftol": 1e-6, "gtol": 1e-5},
    },
    "paths": {
        "dataset_dir": None,
        "results_dir": "results",
        "project_dir": None,
    },
    "max_turns": 30,
}


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load configuration from JSON file, falling back to defaults."""
    cfg = _deep_copy(DEFAULTS)

    # Try loading from file
    if config_path and Path(config_path).exists():
        with open(config_path, "r", encoding="utf-8") as f:
            user_cfg = json.load(f)
        _deep_merge(cfg, user_cfg)

    # Try loading from HydroAgent's existing config
    _load_from_hydroagent(cfg)

    # Override API key from environment
    api_key_env = cfg["llm"].get("api_key_env", "LLM_API_KEY")
    env_key = os.environ.get(api_key_env)
    if env_key:
        cfg["llm"]["api_key"] = env_key

    return cfg


def _load_from_hydroagent(cfg: dict):
    """Try to load settings from existing HydroAgent configs."""
    try:
        from configs import definitions_private
        if not cfg["llm"].get("api_key"):
            cfg["llm"]["api_key"] = getattr(definitions_private, "OPENAI_API_KEY", None)
        if not cfg["llm"].get("base_url") or cfg["llm"]["base_url"] == DEFAULTS["llm"]["base_url"]:
            cfg["llm"]["base_url"] = getattr(definitions_private, "OPENAI_BASE_URL", cfg["llm"]["base_url"])
        if not cfg["paths"]["dataset_dir"]:
            cfg["paths"]["dataset_dir"] = getattr(definitions_private, "DATASET_DIR", None)
        if not cfg["paths"]["project_dir"]:
            cfg["paths"]["project_dir"] = getattr(definitions_private, "PROJECT_DIR", None)
        if not cfg["paths"]["results_dir"] or cfg["paths"]["results_dir"] == "results":
            cfg["paths"]["results_dir"] = getattr(definitions_private, "RESULT_DIR", "results")
    except ImportError:
        try:
            from configs import definitions
            if not cfg["llm"].get("api_key"):
                cfg["llm"]["api_key"] = getattr(definitions, "OPENAI_API_KEY", None)
            if not cfg["paths"]["dataset_dir"]:
                cfg["paths"]["dataset_dir"] = getattr(definitions, "DATASET_DIR", None)
        except ImportError:
            pass


def build_hydromodel_config(
    basin_ids: list[str],
    model_name: str = "xaj",
    algorithm: str = "SCE_UA",
    train_period: list[str] | None = None,
    test_period: list[str] | None = None,
    algorithm_params: dict | None = None,
    param_range_file: str | None = None,
    warmup: int | None = None,
    output_dir: str | None = None,
    cfg: dict | None = None,
) -> dict[str, Any]:
    """Build a hydromodel-compatible configuration dictionary.

    Args:
        basin_ids: CAMELS basin IDs.
        model_name: Hydrological model name.
        algorithm: Calibration algorithm.
        train_period: Training period [start, end].
        test_period: Testing period [start, end].
        algorithm_params: Algorithm parameter overrides.
        param_range_file: Path to custom parameter range YAML file.
        warmup: Warmup days.
        output_dir: Output directory for results.
        cfg: Global config dict (from load_config).

    Returns:
        Dictionary ready for hydromodel.calibrate().
    """
    if cfg is None:
        cfg = load_config()

    defaults = cfg.get("defaults", DEFAULTS["defaults"])
    algo_defaults = cfg.get("algorithms", DEFAULTS["algorithms"])

    train_period = train_period or defaults["train_period"]
    test_period = test_period or defaults["test_period"]
    warmup = warmup if warmup is not None else defaults.get("warmup", 365)

    # Build algorithm params
    algo_params = dict(algo_defaults.get(algorithm, {}))
    if algorithm_params:
        algo_params.update(algorithm_params)

    # Extract random_seed separately (it's a training_cfg, not algorithm_param)
    random_seed = algo_params.pop("random_seed", 1234)

    # Determine output directory
    if not output_dir:
        results_dir = cfg.get("paths", {}).get("results_dir", "results")
        output_dir = str(Path(results_dir) / f"{model_name}_{algorithm}_{basin_ids[0]}")

    # Get dataset directory
    dataset_dir = cfg.get("paths", {}).get("dataset_dir")

    config = {
        "data_cfgs": {
            "data_source_type": "camels_us",
            "data_source_path": dataset_dir,
            "basin_ids": basin_ids,
            "train_period": train_period,
            "test_period": test_period,
            "warmup_length": warmup,
            "variables": [
                "precipitation",
                "potential_evapotranspiration",
                "streamflow",
            ],
        },
        "model_cfgs": {
            "model_name": model_name,
        },
        "training_cfgs": {
            "algorithm_name": algorithm,
            "algorithm_params": algo_params,
            "loss_config": {
                "type": "time_series",
                "obj_func": "RMSE",
            },
            "output_dir": output_dir,
            "experiment_name": "",
            "random_seed": random_seed,
            "save_config": True,
            **({"param_range_file": param_range_file} if param_range_file else {}),
        },
    }

    return config


def _deep_copy(d: dict) -> dict:
    """Simple deep copy for nested dicts/lists."""
    result = {}
    for k, v in d.items():
        if isinstance(v, dict):
            result[k] = _deep_copy(v)
        elif isinstance(v, list):
            result[k] = list(v)
        else:
            result[k] = v
    return result


def _deep_merge(base: dict, override: dict):
    """Merge override into base, modifying base in place."""
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
