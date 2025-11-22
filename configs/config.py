"""
Author: zhuanglaihong
Date: 2024-11-22 10:10:00
LastEditTime: 2024-11-22 10:10:00
LastEditors: zhuanglaihong
Description: Global configuration parameters for HydroAgent
FilePath: /HydroAgent/configs/config.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

# ============================================================================
# LLM Configuration
# ============================================================================

# Default LLM model for API backend
DEFAULT_MODEL = "qwen-turbo"

# LLM temperature (0.0 = deterministic, 1.0 = creative)
TEMPERATURE = 0.1

# Max tokens for LLM response
MAX_TOKENS = 2000

# Request timeout (seconds)
REQUEST_TIMEOUT = 60

# ============================================================================
# Data Configuration
# ============================================================================

# Default training period for calibration
DEFAULT_TRAIN_PERIOD = ["1985-10-01", "1995-09-30"]

# Default testing period for evaluation
DEFAULT_TEST_PERIOD = ["2005-10-01", "2014-09-30"]

# Default warmup period (days)
DEFAULT_WARMUP_DAYS = 365

# ============================================================================
# Algorithm Default Parameters
# ============================================================================

# SCE-UA (Shuffled Complex Evolution) default parameters
DEFAULT_SCE_UA_PARAMS = {
    "rep": 500,          # Number of evolution steps (迭代轮数)
    "ngs": 200,           # Number of complexes (复合体数量)
    "kstop": 500,         # Convergence criterion (收敛判据)
    "peps": 0.1,          # Convergence threshold (收敛阈值)
    "pcento": 0.1,        # Percentage change (百分比变化)
    "random_seed": 1234,  # Random seed for reproducibility
}

# Differential Evolution (DE) default parameters
DEFAULT_DE_PARAMS = {
    "max_generations": 1000,
    "pop_size": 50,
    "mutation_factor": 0.8,
    "crossover_prob": 0.7,
    "random_seed": 1234,
}

# Particle Swarm Optimization (PSO) default parameters
DEFAULT_PSO_PARAMS = {
    "max_iterations": 1000,
    "swarm_size": 50,
    "inertia_weight": 0.9,
    "cognitive_coef": 2.0,
    "social_coef": 2.0,
    "random_seed": 1234,
}

# Genetic Algorithm (GA) default parameters
DEFAULT_GA_PARAMS = {
    "generations": 1000,
    "population_size": 50,
    "mutation_rate": 0.1,
    "crossover_rate": 0.8,
    "random_seed": 1234,
}

# ============================================================================
# Model Configuration
# ============================================================================

# Supported hydrological models
SUPPORTED_MODELS = [
    "gr1y",      # GR1Y - 1 parameter
    "gr2m",      # GR2M - 2 parameters
    "gr4j",      # GR4J - 4 parameters (most common)
    "gr5j",      # GR5J - 5 parameters
    "gr6j",      # GR6J - 6 parameters
    "xaj",       # XAJ - Xinanjiang model
]

# Supported calibration algorithms
SUPPORTED_ALGORITHMS = [
    "SCE_UA",    # Shuffled Complex Evolution
    "DE",        # Differential Evolution
    "PSO",       # Particle Swarm Optimization
    "GA",        # Genetic Algorithm
]

# Default objective function
DEFAULT_OBJECTIVE = "RMSE"  # Root Mean Square Error

# Available objective functions
AVAILABLE_OBJECTIVES = [
    "RMSE",      # Root Mean Square Error
    "NSE",       # Nash-Sutcliffe Efficiency
    "KGE",       # Kling-Gupta Efficiency
    "MAE",       # Mean Absolute Error
]

# ============================================================================
# Execution Configuration
# ============================================================================

# Show progress bar during calibration
SHOW_PROGRESS = True

# Maximum execution timeout (seconds)
MAX_EXECUTION_TIMEOUT = 7200  # 2 hours

# Auto-run evaluation after calibration
AUTO_EVALUATE = True

# ============================================================================
# Output Configuration
# ============================================================================

# Save calibration results
SAVE_CALIBRATION_RESULTS = True

# Save evaluation results
SAVE_EVALUATION_RESULTS = True

# Result file format
RESULT_FORMAT = "json"  # json, yaml, csv

# NetCDF output for time series
SAVE_NETCDF = True

# ============================================================================
# Logging Configuration
# ============================================================================

# Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL = "INFO"

# Log format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Date format in logs
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Save logs to file
SAVE_LOGS = True

# ============================================================================
# Agent Configuration
# ============================================================================

# Enable dynamic prompt system for IntentAgent
USE_DYNAMIC_PROMPT = True

# Confidence threshold for intent recognition
INTENT_CONFIDENCE_THRESHOLD = 0.5

# Enable auto-evaluation in RunnerAgent
RUNNER_AUTO_EVALUATE = True

# DeveloperAgent analysis detail level
ANALYSIS_DETAIL_LEVEL = "detailed"  # brief, normal, detailed

# ============================================================================
# Performance Thresholds
# ============================================================================

# NSE quality thresholds
NSE_EXCELLENT = 0.75   # 优秀
NSE_GOOD = 0.65        # 良好
NSE_FAIR = 0.50        # 一般
NSE_POOR = 0.35        # 较差
# Below NSE_POOR is considered unsatisfactory (不合格)

# ============================================================================
# Experimental Features (Future)
# ============================================================================

# Enable RAG system (when implemented)
ENABLE_RAG = False

# Enable visualization (when implemented)
ENABLE_VISUALIZATION = False

# Enable multi-basin parallel processing (when implemented)
ENABLE_PARALLEL_BASINS = False
