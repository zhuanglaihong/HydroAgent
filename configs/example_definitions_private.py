"""
Private configuration template for HydroAgent
Copy this file to definitions_private.py and modify with your actual paths and keys

IMPORTANT: Do not commit definitions_private.py to version control!
"""

import os

# ============================================================================
# Core Directories
# ============================================================================

# Project root directory (absolute path recommended)
PROJECT_DIR = r"D:\path\to\your\HydroAgent"

# Results output directory (calibration/evaluation results)
# Can be relative to PROJECT_DIR or absolute path
RESULT_DIR = r"D:\path\to\your\HydroAgent\results"

# Dataset directory (CAMELS data, managed by hydrodataset)
# This is where hydrodataset downloads and caches data
DATASET_DIR = r"D:\path\to\your\data"

# Logs directory (optional, defaults to "logs")
LOG_DIR = "logs"

# ============================================================================
# LLM API Configuration
# ============================================================================

# Option 1: Qwen API (Alibaba Cloud DashScope)
# Get your API key from: https://dashscope.console.aliyun.com/
OPENAI_API_KEY = "sk-your-qwen-api-key-here"
OPENAI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# Option 2: OpenAI API
# OPENAI_API_KEY = "sk-your-openai-api-key-here"
# OPENAI_BASE_URL = "https://api.openai.com/v1"

# Option 3: Other OpenAI-compatible APIs
# OPENAI_API_KEY = "your-api-key"
# OPENAI_BASE_URL = "https://your-custom-endpoint/v1"

# Ollama base URL for local models (optional)
# Only needed if you want to use Ollama instead of API
OLLAMA_BASE_URL = "http://localhost:11434"

# ============================================================================
# Knowledge Base (for future RAG integration)
# ============================================================================

# Knowledge base directory for RAG system
# Will be used when RAG features are implemented
KNOWLEDGE_BASE_DIR = "documents"
