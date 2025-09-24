"""
Author: zhuanglaihong
Date: 2024-09-24 16:35:00
LastEditTime: 2024-09-24 16:35:00
LastEditors: zhuanglaihong
Description: Global parameter configuration for HydroAgent system
FilePath: \HydroAgent\config.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

# ============================================================================
# HydroAgent Global Configuration Parameters
#
# This file contains all adjustable parameters for the HydroAgent system.
# Users can modify these values without touching the core code files.
# ============================================================================

# ============================================================================
# RAG System Parameters
# ============================================================================

# Document Processing
RAG_CHUNK_SIZE = 1000                    # Text chunk size for document splitting
RAG_CHUNK_OVERLAP = 200                  # Overlap between chunks
RAG_MAX_CHUNK_SIZE = 2000               # Maximum chunk size
RAG_SUPPORTED_EXTENSIONS = [             # Supported file extensions
    ".txt", ".md", ".markdown", ".rst",
    ".pdf", ".docx", ".doc", ".py",
    ".yaml", ".yml", ".json"
]

# Query and Retrieval
RAG_TOP_K = 5                           # Default number of results to return
RAG_SCORE_THRESHOLD = 0.7               # Minimum similarity score threshold
RAG_RERANK_ENABLED = True               # Enable result reranking
RAG_QUERY_EXPANSION = True              # Enable query expansion

# Reranking Weights
RAG_SEMANTIC_WEIGHT = 0.6               # Weight for semantic similarity
RAG_DIVERSITY_WEIGHT = 0.3              # Weight for result diversity
RAG_RECENCY_WEIGHT = 0.1                # Weight for content recency

# Vector Database
VECTOR_DB_COLLECTION_NAME = "hydro_knowledge"
VECTOR_DB_DISTANCE_FUNCTION = "cosine"   # cosine, l2, ip

# ============================================================================
# LLM Model Parameters
# ============================================================================

# Primary LLM Configuration (API优先)
LLM_USE_API_FIRST = True                # 优先使用API模型
LLM_API_MODEL_NAME = "qwen3-coder-plus" # API模型名称 (用于复杂任务)
LLM_API_TIMEOUT = 30                    # API调用超时时间（秒）
LLM_API_MAX_RETRIES = 2                 # API调用最大重试次数

# Local Fallback Configuration (本地降级)
LLM_FALLBACK_MODEL = "deepseek-coder:6.7b"  # 降级使用的本地Ollama模型
LLM_FALLBACK_TIMEOUT = 60               # 本地模型调用超时时间（秒）

# General LLM Parameters
LLM_MODEL_NAME = "qwen3:8b"             # Default LLM model (for simple tasks)
LLM_TEMPERATURE = 0.1                   # Temperature for text generation
LLM_MAX_TOKENS = 4000                   # Maximum tokens in response
LLM_TOP_P = 0.95                        # Top-p sampling parameter

# Embedding Model Configuration
EMBEDDING_MODEL_API = "text-embedding-v1"      # API embedding model
EMBEDDING_MODEL_LOCAL = "nomic-embed-text"     # Local embedding model fallback
EMBEDDING_DIMENSION = 1536                     # Expected embedding dimension
EMBEDDING_DEVICE = "cpu"                       # Device for local embeddings

# ============================================================================
# Builder Parameters (Workflow Planning System)
# ============================================================================

# Chain of Thought (CoT) Reasoning
COT_MAX_ITERATIONS = 5                  # Maximum CoT reasoning iterations
COT_TEMPERATURE = 0.2                   # Temperature for CoT reasoning
COT_KNOWLEDGE_CHUNKS = 5                # Number of knowledge chunks for CoT

# Workflow Builder Configuration
BUILDER_MAX_TASKS = 20                  # Maximum tasks in a workflow
BUILDER_TIMEOUT = 120                   # Timeout in seconds for building workflow
BUILDER_RETRY_ATTEMPTS = 2              # Number of retry attempts for building

# Execution Mode Analysis
MODE_COMPLEXITY_THRESHOLD_LOW = 0.3     # Low complexity threshold for linear mode
MODE_COMPLEXITY_THRESHOLD_HIGH = 0.7    # High complexity threshold for react mode
MODE_CONFIDENCE_THRESHOLD = 0.6         # Minimum confidence for mode recommendation

# Workflow Validation
VALIDATE_WORKFLOW_STRUCTURE = True      # Enable workflow structure validation
VALIDATE_TOOL_AVAILABILITY = True      # Enable tool availability validation
VALIDATE_DEPENDENCY_CYCLES = True      # Enable circular dependency detection

# Builder Performance
BUILDER_CACHE_ENABLED = True            # Enable builder result caching
BUILDER_CACHE_TTL = 1800               # Cache time-to-live in seconds (30 minutes)
BUILDER_STATS_ENABLED = True           # Enable builder statistics collection

# ============================================================================
# Workflow Execution Parameters (for Executor)
# ============================================================================

# Workflow Execution
WORKFLOW_MAX_STEPS = 10                 # Maximum steps in a workflow
WORKFLOW_TIMEOUT = 300                  # Timeout in seconds per workflow
WORKFLOW_RETRY_ATTEMPTS = 3             # Number of retry attempts

# ============================================================================
# Model Calibration Parameters
# ============================================================================

# Optimization Settings
CALIB_MAX_ITERATIONS = 100              # Maximum optimization iterations
CALIB_TOLERANCE = 1e-6                  # Convergence tolerance
CALIB_POPULATION_SIZE = 50              # Population size for genetic algorithms

# Objective Functions
CALIB_PRIMARY_METRIC = "nse"            # Primary calibration metric (nse, kge, etc.)
CALIB_SECONDARY_METRICS = ["r2", "rmse", "mae"]  # Additional metrics to track

# Cross-validation
CALIB_CV_FOLDS = 5                      # Number of cross-validation folds
CALIB_VALIDATION_SPLIT = 0.3            # Fraction of data for validation

# ============================================================================
# Data Processing Parameters
# ============================================================================

# Time Series Processing
TS_MIN_YEARS = 3                        # Minimum years of data required
TS_MAX_MISSING_RATIO = 0.1              # Maximum allowed missing data ratio
TS_INTERPOLATION_METHOD = "linear"      # Interpolation method for missing data

# Quality Control
QC_MIN_FLOW = 0.001                     # Minimum valid flow value (m³/s)
QC_MAX_FLOW_RATIO = 100                 # Maximum flow change ratio between timesteps
QC_OUTLIER_THRESHOLD = 3.0              # Standard deviations for outlier detection

# ============================================================================
# Logging and Monitoring
# ============================================================================

# Logging Configuration
LOG_LEVEL = "INFO"                      # Logging level (DEBUG, INFO, WARNING, ERROR)
LOG_MAX_FILE_SIZE = 10 * 1024 * 1024   # Maximum log file size (10MB)
LOG_BACKUP_COUNT = 5                    # Number of backup log files to keep
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Performance Monitoring
MONITOR_ENABLED = True                  # Enable performance monitoring
MONITOR_INTERVAL = 60                   # Monitoring interval in seconds
MONITOR_METRICS = ["cpu", "memory", "disk"]  # Metrics to monitor

# ============================================================================
# API and Network Configuration
# ============================================================================

# API Settings
API_TIMEOUT = 30                        # API request timeout in seconds
API_MAX_RETRIES = 3                     # Maximum API retry attempts
API_RETRY_DELAY = 1.0                   # Initial retry delay in seconds
API_BACKOFF_FACTOR = 2.0                # Exponential backoff multiplier

# Rate Limiting
API_RATE_LIMIT = 100                    # API calls per minute
API_BURST_LIMIT = 20                    # Maximum burst API calls

# ============================================================================
# Cache Configuration
# ============================================================================

# Cache Settings
CACHE_ENABLED = True                    # Enable caching
CACHE_TTL = 3600                        # Cache time-to-live in seconds
CACHE_MAX_SIZE = 1000                   # Maximum number of cached items
CACHE_CLEANUP_INTERVAL = 600            # Cache cleanup interval in seconds

# ============================================================================
# Development and Testing
# ============================================================================

# Development Settings
DEBUG_MODE = False                      # Enable debug mode
VERBOSE_LOGGING = False                 # Enable verbose logging
PROFILE_PERFORMANCE = False             # Enable performance profiling

# Testing Configuration
TEST_DATA_PATH = "test/data"            # Path to test data
TEST_TIMEOUT = 60                       # Test timeout in seconds
TEST_PARALLEL = True                    # Enable parallel testing

# Mock Settings
MOCK_APIS = False                       # Use mock APIs for testing
MOCK_DELAY = 0.1                        # Mock API response delay

# ============================================================================
# Resource Limits
# ============================================================================

# Memory Management
MAX_MEMORY_USAGE = 8 * 1024 * 1024 * 1024  # Maximum memory usage (8GB)
MAX_CHUNK_MEMORY = 500 * 1024 * 1024       # Maximum memory per chunk (500MB)
GARBAGE_COLLECT_INTERVAL = 300              # Garbage collection interval

# Disk Usage
MAX_DISK_USAGE = 50 * 1024 * 1024 * 1024   # Maximum disk usage (50GB)
TEMP_FILE_CLEANUP = True                    # Enable temporary file cleanup
TEMP_FILE_MAX_AGE = 86400                   # Maximum age of temp files (24h)

# Processing Limits
MAX_CONCURRENT_TASKS = 4                # Maximum concurrent processing tasks
MAX_FILE_SIZE = 100 * 1024 * 1024      # Maximum file size to process (100MB)
MAX_DOCUMENTS_BATCH = 100               # Maximum documents per batch

# ============================================================================
# Feature Flags
# ============================================================================

# System Features
ENABLE_RAG = True                       # Enable RAG functionality
ENABLE_MCP = True                       # Enable MCP integration
ENABLE_WORKFLOW = True                  # Enable workflow execution
ENABLE_VISUALIZATION = True             # Enable result visualization

# Experimental Features
EXPERIMENTAL_MULTIMODAL = False         # Enable multimodal processing
EXPERIMENTAL_DISTRIBUTED = False       # Enable distributed processing
EXPERIMENTAL_GPU_ACCELERATION = False  # Enable GPU acceleration

# ============================================================================
# Model-Specific Parameters
# ============================================================================

# GR4J Model
GR4J_PARAM_BOUNDS = {
    "X1": [1.0, 3000.0],        # Production store capacity
    "X2": [-30.0, 30.0],        # Groundwater exchange coefficient
    "X3": [1.0, 500.0],         # Routing store capacity
    "X4": [0.5, 10.0]           # Unit hydrograph time constant
}

# XAJ Model
XAJ_PARAM_BOUNDS = {
    "K": [0.1, 1.5],            # Evapotranspiration coefficient
    "B": [0.1, 0.5],            # Tension water capacity distribution
    "IM": [0.0, 0.05],          # Impervious area ratio
    "WM": [50.0, 500.0],        # Tension water storage capacity
    "WUM": [5.0, 50.0],         # Upper layer capacity
    "WLM": [10.0, 100.0],       # Lower layer capacity
    "C": [0.1, 0.3],            # Deep percolation coefficient
    "SM": [10.0, 100.0],        # Free water storage capacity
    "EX": [1.0, 2.0],           # Free water storage distribution
    "KI": [0.0, 0.7],           # Interflow outflow coefficient
    "KG": [0.0, 0.7],           # Groundwater outflow coefficient
    "A": [0.0, 1.0],            # Recession constant
    "THETA": [0.0, 1.0],        # Recession constant
    "CI": [0.5, 0.95],          # Lag time
    "CG": [0.8, 0.998]          # Lag time
}

# ============================================================================
# User Customization Section
# ============================================================================

# Users can override any of the above parameters by uncommenting and modifying:

# Override example:
# RAG_TOP_K = 10                        # Increase default results
# LLM_TEMPERATURE = 0.3                 # More creative responses
# LOG_LEVEL = "DEBUG"                   # More detailed logging

# Custom parameters can be added here:
# CUSTOM_PARAMETER = "custom_value"