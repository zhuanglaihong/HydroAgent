"""
Project-wide configuration definitions for HydroClaw.

This file provides default values. For actual use, create definitions_private.py
with your own paths and API keys (see example_definitions_private.py).
"""

import os

try:
    import configs.definitions_private as definitions_private

    # Core Directories
    PROJECT_DIR = definitions_private.PROJECT_DIR
    RESULT_DIR = definitions_private.RESULT_DIR
    DATASET_DIR = definitions_private.DATASET_DIR

    # LLM API Configuration
    OPENAI_API_KEY = definitions_private.OPENAI_API_KEY
    OPENAI_BASE_URL = getattr(
        definitions_private,
        "OPENAI_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

except ImportError:
    # Default Configuration (Fallback)
    PROJECT_DIR = os.getcwd()
    RESULT_DIR = "results"
    DATASET_DIR = "data"

    OPENAI_API_KEY = "your-api-key-here"
    print("Warning: Using default API key. Set your key in configs/definitions_private.py")

    OPENAI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
