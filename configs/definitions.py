"""
Author: zhuanglaihong
Date: 2025-11-21 21:30:00
LastEditTime: 2025-11-21 21:30:00
LastEditors: zhuanglaihong
Description: Project-wide configuration definitions for HydroAgent
FilePath: /HydroAgent/configs/definitions.py
Copyright (c) 2024-2025 HydroAgent. All rights reserved.
"""

# NOTE: Create configs/definitions_private.py for your private configuration
# Copy the code in 'except ImportError:' block and modify the paths/keys

import os

try:
    import configs.definitions_private as definitions_private

    # ============================================================================
    # Core Directories
    # ============================================================================
    PROJECT_DIR = definitions_private.PROJECT_DIR
    RESULT_DIR = definitions_private.RESULT_DIR
    DATASET_DIR = definitions_private.DATASET_DIR
    LOG_DIR = getattr(definitions_private, 'LOG_DIR', "logs")

    # ============================================================================
    # LLM API Configuration
    # ============================================================================
    OPENAI_API_KEY = definitions_private.OPENAI_API_KEY
    OPENAI_BASE_URL = getattr(
        definitions_private,
        'OPENAI_BASE_URL',
        "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )

    # Ollama Configuration (optional, for local models)
    OLLAMA_BASE_URL = getattr(
        definitions_private,
        'OLLAMA_BASE_URL',
        "http://localhost:11434"
    )

    # ============================================================================
    # Knowledge Base (for future RAG integration)
    # ============================================================================
    KNOWLEDGE_BASE_DIR = getattr(
        definitions_private,
        'KNOWLEDGE_BASE_DIR',
        "documents"
    )

except ImportError:
    # ============================================================================
    # Default Configuration (Fallback)
    # ============================================================================

    # Project root directory
    PROJECT_DIR = os.getcwd()

    # Results output directory (calibration/evaluation results)
    RESULT_DIR = "results"

    # Dataset directory (CAMELS data, etc.)
    DATASET_DIR = "data"

    # Logs directory
    LOG_DIR = "logs"

    # ============================================================================
    # LLM API Configuration
    # ============================================================================

    # OpenAI-compatible API key (e.g., Qwen API)
    OPENAI_API_KEY = "your-api-key-here"
    print("⚠️  Warning: Using default API key. Please set your own key in configs/definitions_private.py")

    # API base URL (Qwen, OpenAI, or other compatible services)
    OPENAI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # Ollama base URL for local models (optional)
    OLLAMA_BASE_URL = "http://localhost:11434"

