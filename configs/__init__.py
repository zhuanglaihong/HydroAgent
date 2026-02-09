"""
Configuration management for HydroClaw.

Provides project paths, API keys, and dataset directories.
HydroClaw reads from definitions_private.py (user-specific) or definitions.py (defaults).
"""

# Try to import private definitions first, fall back to public definitions
try:
    from configs.definitions_private import *
except ImportError:
    from configs.definitions import *
