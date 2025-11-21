"""
Author: Claude & zhuanglaihong
Date: 2025-01-20 20:00:00
LastEditTime: 2025-01-20 20:00:00
LastEditors: Claude
Description: Resources module - RAG static files and knowledge base (Tech 4.6)
             资源模块 - RAG 静态文件和知识库
FilePath: \HydroAgent\hydroagent\resources\__init__.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from pathlib import Path

# Resource directory path
RESOURCE_DIR = Path(__file__).parent

# Resource file paths
SCHEMA_DEFINITION = RESOURCE_DIR / "schema_definition.json"
API_SIGNATURES = RESOURCE_DIR / "api_signatures.yaml"
FEW_SHOT_PROMPTS_MODULE = "hydroagent.resources.few_shot_prompts"

__all__ = [
    'RESOURCE_DIR',
    'SCHEMA_DEFINITION',
    'API_SIGNATURES',
    'FEW_SHOT_PROMPTS_MODULE',
]
