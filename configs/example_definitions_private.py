"""
Private configuration template for HydroClaw.
Copy this file to definitions_private.py and modify with your actual paths and keys.

IMPORTANT: Do not commit definitions_private.py to version control!
"""

# ============================================================================
# Core Directories
# ============================================================================

# Project root directory (absolute path recommended)
PROJECT_DIR = r"D:\path\to\your\HydroAgent"

# Results output directory (calibration/evaluation results)
RESULT_DIR = r"D:\path\to\your\HydroAgent\results"

# Dataset directory (CAMELS data, managed by hydrodataset)
DATASET_DIR = r"D:\path\to\your\data"

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

# Option 3: Other OpenAI-compatible APIs (DeepSeek, etc.)
# OPENAI_API_KEY = "your-api-key"
# OPENAI_BASE_URL = "https://your-custom-endpoint/v1"
