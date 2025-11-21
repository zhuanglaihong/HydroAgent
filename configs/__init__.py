"""
Author: zhuanglaihong
Date: 2025-11-13 20:00:00
LastEditTime: 2025-11-13 20:00:00
LastEditors: zhuanglaihong
Description: Configuration management for HydroAgent
FilePath: \\HydroAgent\\configs\\__init__.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

# Try to import private definitions first, fall back to public definitions
try:
    from configs.definitions_private import *
except ImportError:
    from configs.definitions import *


__all__ = []
