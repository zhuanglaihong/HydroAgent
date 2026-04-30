"""
HydroAgent - LLM-driven hydrological model calibration agent.

A minimal, agentic system where LLM makes decisions and code only executes.
Replaces the 27,000-line HydroAgent with ~3,500 lines of focused code.
"""

__version__ = "0.1.0"

from hydroagent.agent import HydroAgent

__all__ = ["HydroAgent"]
