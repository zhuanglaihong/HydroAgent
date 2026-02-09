"""
Global configuration parameters for HydroClaw.

NOTE: HydroClaw has its own built-in defaults in hydroclaw/config.py.
This file is kept for reference and for any parameters that users want to
override beyond the built-in defaults.

Most users should NOT need to modify this file. Instead:
- API keys and paths: use configs/definitions_private.py
- Algorithm params, periods, models: pass directly in your query or
  create a config.json and pass to HydroClaw(config_path="config.json")
"""

# ============================================================================
# LLM Configuration
# ============================================================================

DEFAULT_MODEL = "deepseek-v3.1"
TEMPERATURE = 0.1
MAX_TOKENS = 20000
REQUEST_TIMEOUT = 60

# ============================================================================
# Data Configuration
# ============================================================================

DEFAULT_TRAIN_PERIOD = ["2000-01-01", "2009-12-31"]
DEFAULT_TEST_PERIOD = ["2010-01-01", "2014-12-31"]
DEFAULT_WARMUP_DAYS = 365

# ============================================================================
# Algorithm Default Parameters
# ============================================================================

DEFAULT_SCE_UA_PARAMS = {
    "rep": 1000,
    "ngs": 200,
    "kstop": 500,
    "peps": 0.1,
    "pcento": 0.1,
    "random_seed": 1234,
}

DEFAULT_GA_PARAMS = {
    "pop_size": 40,
    "n_generations": 25,
    "cx_prob": 0.7,
    "mut_prob": 0.2,
    "random_seed": 1234,
}

DEFAULT_scipy_PARAMS = {
    "method": "SLSQP",
    "max_iterations": 500,
    "ftol": 1e-6,
    "gtol": 1e-5,
}

# ============================================================================
# Supported Models and Algorithms
# ============================================================================

SUPPORTED_MODELS = ["gr4j", "gr5j", "gr6j", "xaj"]
SUPPORTED_ALGORITHMS = ["SCE_UA", "scipy", "GA"]

# ============================================================================
# Performance Thresholds (used by LLM for quality assessment)
# ============================================================================

NSE_EXCELLENT = 0.75
NSE_GOOD = 0.65
NSE_FAIR = 0.50
NSE_POOR = 0.35
