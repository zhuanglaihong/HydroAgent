"""
配置兼容桥接 - configs/definitions.py
=======================================
此文件提供向后兼容，对外暴露 PROJECT_DIR、RESULT_DIR、DATASET_DIR、
OPENAI_API_KEY、OPENAI_BASE_URL 等常量。

私密配置请填写 configs/private.py（推荐）或 configs/definitions_private.py（旧版）。
"""

import os

_defs = None
for _mod in ("configs.private", "configs.definitions_private"):
    try:
        import importlib
        _defs = importlib.import_module(_mod)
        break
    except ImportError:
        continue

if _defs is not None:
    PROJECT_DIR    = getattr(_defs, "PROJECT_DIR", os.getcwd())
    RESULT_DIR     = getattr(_defs, "RESULT_DIR", "results")
    DATASET_DIR    = getattr(_defs, "DATASET_DIR", "data")
    OPENAI_API_KEY = getattr(_defs, "OPENAI_API_KEY", "your-api-key-here")
    OPENAI_BASE_URL = getattr(
        _defs,
        "OPENAI_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
else:
    PROJECT_DIR    = os.getcwd()
    RESULT_DIR     = "results"
    DATASET_DIR    = "data"
    OPENAI_API_KEY = "your-api-key-here"
    OPENAI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    print("Warning: configs/private.py not found. Please fill in your API key and paths.")
