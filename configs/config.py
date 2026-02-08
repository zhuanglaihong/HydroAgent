"""
Author: zhuanglaihong
Date: 2025-11-22 10:10:00
LastEditTime: 2025-11-22 10:10:00
LastEditors: zhuanglaihong
Description: Global configuration parameters for HydroAgent
FilePath: /HydroAgent/configs/config.py
Copyright (c) 2024-2025 HydroAgent. All rights reserved.
"""

# ============================================================================
# LLM Configuration
# ============================================================================

# Default LLM model for API backend
DEFAULT_MODEL = "deepseek-v3.1"

# Default code-specific LLM model (for DeveloperAgent code generation)
DEFAULT_CODE_MODEL = "qwen3-coder-plus"

# Default LLM model for ollama backend
OLLAMA_DEFAULT_MODEL = "qwen3:8b"

# Default LLM model for ollama backend
OLLAMA_DEFAULT_CODE_MODEL ="deepseek-coder:6.7b" 

# LLM temperature (0.0 = deterministic, 1.0 = creative)
TEMPERATURE = 0.1

# Max tokens for LLM response
MAX_TOKENS = 20000

# Request timeout (seconds)
REQUEST_TIMEOUT = 60

# ============================================================================
# Data Configuration
# ============================================================================

# Default training period for calibration
DEFAULT_TRAIN_PERIOD = ["2000-01-01", "2009-12-31"]

# Default testing period for evaluation
DEFAULT_TEST_PERIOD = ["2010-01-01", "2014-12-31"]

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

# Scipy optimizer default parameters (scipy.optimize.minimize)
DEFAULT_scipy_PARAMS = {
    "method": "SLSQP",                # Optimization method (default: SLSQP, options: L-BFGS-B, TNC, etc.)
    "max_iterations": 500,            # Maximum number of iterations (default: 500)
    "ftol": 1e-6,                     # Function tolerance (default: 1e-6)
    "gtol": 1e-5                      # Gradient tolerance (default: 1e-5)
}

# Genetic Algorithm (GA) default parameters
DEFAULT_GA_PARAMS = {
    "pop_size": 40,                    # Population size (default: 80)
    "n_generations": 25,               # Number of generations (default: 50, recommended: 100+ for production)
    "cx_prob": 0.7,                    # Crossover probability (default: 0.7)
    "mut_prob": 0.2,                   # Mutation probability (default: 0.2)
    "random_seed": 1234,               # Random seed for reproducibility (default: 1234)
}

# ============================================================================
# Model Configuration
# ============================================================================

# Supported hydrological models
SUPPORTED_MODELS = [
    "gr4j",      # GR4J - 4 parameters (most common)
    "gr5j",      # GR5J - 5 parameters
    "gr6j",      # GR6J - 6 parameters
    "xaj",       # XAJ - Xinanjiang model
]

# Supported calibration algorithms
SUPPORTED_ALGORITHMS = [
    "SCE_UA",    # Shuffled Complex Evolution
    "scipy",     # Scipy optimizer
    "GA",        # Genetic Algorithm
]

# Default objective function
DEFAULT_OBJECTIVE = "RMSE"  # Root Mean Square Error

# Available objective functions
AVAILABLE_OBJECTIVES = [
    "RMSE",      # Root Mean Square Error
    "NSE",       # Nash-Sutcliffe Efficiency
    "KGE",       # Kling-Gupta Efficiency
    "PBIAS"      # Percent bias pbias
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
RESULT_FORMAT = "json"  

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

# NSE quality thresholds (used by DeveloperAgent for quality assessment)
NSE_EXCELLENT = 0.75   # 优秀 (Excellent)
NSE_GOOD = 0.65        # 良好 (Good)
NSE_FAIR = 0.50        # 一般 (Fair)
NSE_POOR = 0.35        # 较差 (Poor)
# Below NSE_POOR is considered unsatisfactory (不合格)

# ============================================================================
# Visualization Configuration (绘图配置)
# ============================================================================

# Enable automatic plotting after calibration/evaluation
# 是否在率定/评估后自动绘图
ENABLE_AUTO_PLOT = True

# Plot types to generate
# 要生成的图表类型
PLOT_STREAMFLOW_COMPARISON = True  # 径流对比图 (observed vs simulated)
PLOT_WITH_PRECIPITATION = True     # 包含降水的对比图

# Plot output format
PLOT_FORMAT = "png"  # Options: png, pdf, svg
PLOT_DPI = 300       # Resolution for publication quality

# Plot save location
# 图表保存位置：与calibration_results.json同目录
SAVE_PLOTS_IN_RESULT_DIR = True

# ============================================================================
# Post-Processing Analysis Configuration (后处理分析配置)
# ============================================================================

# Metrics to analyze in post-processing
# 后处理分析的指标（DeveloperAgent会提取这些指标）
POST_ANALYSIS_METRICS = [
    "NSE",      # Nash-Sutcliffe Efficiency
    "RMSE",     # Root Mean Square Error
    "KGE",      # Kling-Gupta Efficiency
    "PBIAS",    # Percent Bias
    "R2",       # Coefficient of Determination
]

# Enable intelligent analysis with LLM
# 是否使用LLM进行智能分析
ENABLE_LLM_ANALYSIS = True

# Analysis detail level
# 分析详细程度：brief, normal, detailed
ANALYSIS_DETAIL_LEVEL = "normal"

# Enable post-processing after model execution
ENABLE_POST_PROCESSING = True

# Enable visualization/plotting
ENABLE_VISUALIZATION = True

# Plot types to generate (set to empty list to disable all plots)
PLOT_TYPES = [
    "hydrograph",          # 流量过程线（观测vs模拟）
    "scatter",             # 散点图（观测vs模拟）
    "residual",            # 残差图
    "flow_duration_curve", # 流量历时曲线（FDC）
]

# Plot format (png, pdf, svg)
PLOT_FORMAT = "png"

# Plot DPI (resolution)
PLOT_DPI = 300

# Save plots to result directory
SAVE_PLOTS = True

# ============================================================================
# Tool System Configuration
# ============================================================================

# Enable tool system
USE_TOOL_SYSTEM = True

# Tool execution timeout (seconds)
TOOL_EXECUTION_TIMEOUT = 3600

# Enable tool result caching
TOOL_CACHE_ENABLED = True

# Validation strict mode
# - False: Interactive mode - ask user if continue when partial validation fails
# - True: Strict mode - abort on any validation failure
# 验证严格模式
# - False: 交互模式 - 部分验证失败时询问用户是否继续
# - True: 严格模式 - 任何验证失败都终止执行
VALIDATION_STRICT_MODE = False

# Tool retry on failure
# 工具失败时是否重试
TOOL_RETRY_ON_FAILURE = True

# Maximum retries for failed tools
# 工具失败最大重试次数
TOOL_MAX_RETRIES = 3


# 边界检测阈值（参数收敛到边界的判定标准）
BOUNDARY_THRESHOLD = 0.1  
# NSE达标阈值（达到此值时停止迭代优化）
NSE_THRESHOLD_FOR_ITERATION = 0.7  # 降低此值以触发更多迭代

# 最大迭代次数
MAX_ITERATIONS = 5

# 最小NSE改善幅度（低于此值视为无改善）
MIN_NSE_IMPROVEMENT = 0.01

# 初始参数范围缩放比例（第一次迭代时）
INITIAL_RANGE_SCALE = 0.6  # 60% of original range

# 自动保存调整后的参数范围文件
SAVE_ADJUSTED_PARAM_RANGE = True

# ============================================================================
# PromptPool and FAISS Configuration (v5.0)
# ============================================================================

# Enable FAISS semantic search in PromptPool
USE_FAISS_SEMANTIC_SEARCH = True

# FAISS index storage directory
FAISS_INDEX_PATH = "prompt_pool/faiss_index"

# Sentence transformer model for embedding generation
FAISS_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Maximum history records in PromptPool (v5.0 increased from 50 to 100)
PROMPT_POOL_MAX_HISTORY = 100

# Number of similar cases to retrieve for prompt enhancement
PROMPT_POOL_SIMILAR_CASES_LIMIT = 3

# Enable LLM-driven prompt fusion (vs simple concatenation)
ENABLE_LLM_PROMPT_FUSION = True

# ============================================================================
# State Machine Configuration (v5.0)
# ============================================================================

# Maximum state transitions before aborting (防止无限循环)
STATE_MACHINE_MAX_TRANSITIONS = 100

# State machine execution timeout (seconds)
STATE_MACHINE_TIMEOUT = 7200  # 2 hours

# ============================================================================
# Retry and Recovery Configuration (v5.0)
# ============================================================================

# RunnerAgent: Maximum retries for failed executions
RUNNER_MAX_RETRIES = 3

# RunnerAgent: Timeout for single calibration task (seconds)
RUNNER_TIMEOUT = 3600  # 1 hour

# RunnerAgent: Exponential backoff factor for retries
RUNNER_RETRY_BACKOFF = 2  # 2^n seconds

# ============================================================================
# Goal Tracker Configuration (v5.0)
# ============================================================================

# Convergence tolerance for trend analysis
GOAL_TRACKER_CONVERGENCE_TOLERANCE = 0.01

# Maximum iterations before stopping iterative optimization
GOAL_TRACKER_MAX_ITERATIONS = 10

# ============================================================================
# Experimental Features (Future)
# ============================================================================

# Enable RAG system (when implemented)
ENABLE_RAG = False

# Enable multi-basin parallel processing (when implemented)
ENABLE_PARALLEL_BASINS = False
