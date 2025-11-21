"""
Author: zhuanglaihong
Date: 2025-09-01 15:12:55
LastEditTime: 2025-09-24 09:16:41
LastEditors: zhuanlaihong
Description: Some project-wide definitions
FilePath: \\HydroAgent\\definitions.py
Copyright (c) 2023-2024 Wenyu Ouyang. All rights reserved.
"""

# NOTE: create a file in root directory -- definitions_private.py,
# then copy the code after 'except ImportError:' to definitions_private.py
# and modify the paths as your own paths in definitions_private.py
import os

try:
    import definitions_private

    # ============================================================================
    # Core Directory Structure
    # ============================================================================
    PROJECT_DIR = definitions_private.PROJECT_DIR
    RESULT_DIR = definitions_private.RESULT_DIR
    DATASET_DIR = definitions_private.DATASET_DIR
    DEFAULT_BASIN_DATA_DIR = getattr(definitions_private, 'DEFAULT_BASIN_DATA_DIR', "data/camels_{basin_id}")
    PARAM_RANGE_FILE = getattr(definitions_private, 'PARAM_RANGE_FILE', "hydromodel/models/param.yaml")
    OPENAI_API_KEY = definitions_private.OPENAI_API_KEY
    OPENAI_BASE_URL = getattr(definitions_private, 'OPENAI_BASE_URL', "https://dashscope.aliyuncs.com/compatible-mode/v1")
    # ============================================================================
    # Workflow and Processing Directories
    # ============================================================================
    WORKFLOW_DIR = getattr(definitions_private, 'WORKFLOW_DIR', "workflow")
    WORKFLOW_GENERATED_DIR = getattr(definitions_private, 'WORKFLOW_GENERATED_DIR', "workflow/generated")
    WORKFLOW_EXAMPLES_DIR = getattr(definitions_private, 'WORKFLOW_EXAMPLES_DIR', "workflow/examples")

    # ============================================================================
    # Data Processing Paths
    # ============================================================================
    PROCESSED_DATA_DIR = getattr(definitions_private, 'PROCESSED_DATA_DIR', "data/processed")
    DATA_VALIDATION_DIR = getattr(definitions_private, 'DATA_VALIDATION_DIR', "data/validation")
    DATA_BACKUP_DIR = getattr(definitions_private, 'DATA_BACKUP_DIR', "data/backup")

    # ============================================================================
    # API and Service Configuration
    # ============================================================================
    KNOWLEDGE_BASE_DIR = getattr(definitions_private, 'KNOWLEDGE_BASE_DIR', "documents")

    # Optional configurations with fallbacks
    LOG_DIR = getattr(definitions_private, 'LOG_DIR', "logs")
    LOG_LEVEL = getattr(definitions_private, 'LOG_LEVEL', "INFO")
    CACHE_DIR = getattr(definitions_private, 'CACHE_DIR', ".cache")
    TEMP_DIR = getattr(definitions_private, 'TEMP_DIR', "temp")

    # RAG System Paths (computed from KNOWLEDGE_BASE_DIR)
    RAW_DOCUMENTS_DIR = f"{KNOWLEDGE_BASE_DIR}/raw"
    PROCESSED_DOCUMENTS_DIR = f"{KNOWLEDGE_BASE_DIR}/processed"
    VECTOR_DB_DIR = f"{KNOWLEDGE_BASE_DIR}/vector_db"

    # FONT_DIR = definitions_private.FONT_DIR

except ImportError:
    # point to this project
    PROJECT_DIR = os.getcwd()
    
    # ============================================================================
    # Core Directory Structure
    # ============================================================================
    
    # where to put results
    RESULT_DIR = "result"
    # where are the data sources
    DATASET_DIR = "data"
    # default basin data directory template (will be used with basin_id)
    DEFAULT_BASIN_DATA_DIR = "data/camels_{basin_id}"
    # where to specify the param range file
    PARAM_RANGE_FILE = "hydromodel/models/param.yaml"
    # your OpenAI API key (for Qwen API)
    OPENAI_API_KEY = "your openai api key"
    print("Warning: Using default OpenAI API key in definitions.py, please set your own key in definitions_private.py!")
    # your OpenAI API base url if you use other platforms
    OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
    
    # ============================================================================
    # Workflow and Processing Directories
    # ============================================================================
    
    # workflow generation and storage
    WORKFLOW_DIR = "workflow"
    WORKFLOW_GENERATED_DIR = "workflow/generated"
    WORKFLOW_EXAMPLES_DIR = "workflow/examples"

    # ============================================================================
    # Data Processing Paths
    # ============================================================================
    
    # processed data storage
    PROCESSED_DATA_DIR = "data/processed"
    # data validation and quality check results
    DATA_VALIDATION_DIR = "data/validation"
    # data backup directory
    DATA_BACKUP_DIR = "data/backup"
    # knowledge base directory for RAG system
    KNOWLEDGE_BASE_DIR = "documents"

    # ============================================================================
    # Additional Configuration Items
    # ============================================================================

    # RAG System Paths
    RAW_DOCUMENTS_DIR = f"{KNOWLEDGE_BASE_DIR}/raw"
    PROCESSED_DOCUMENTS_DIR = f"{KNOWLEDGE_BASE_DIR}/processed"
    VECTOR_DB_DIR = f"{KNOWLEDGE_BASE_DIR}/vector_db"

    # Logging Configuration
    LOG_DIR = "logs"
    LOG_LEVEL = "INFO"

    # Cache Directory
    CACHE_DIR = ".cache"

    # Temporary Files
    TEMP_DIR = "temp"
