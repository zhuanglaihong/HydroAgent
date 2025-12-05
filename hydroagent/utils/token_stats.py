"""
Author: Claude
Date: 2025-12-05 21:00:00
LastEditTime: 2025-12-05 21:00:00
LastEditors: Claude
Description: Token usage statistics utilities for experiments
             实验的 Token 使用统计工具
FilePath: /HydroAgent/hydroagent/utils/token_stats.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from pathlib import Path
from typing import Dict, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)


def export_token_stats(
    llm_interface,
    output_dir: Path,
    experiment_name: str = "experiment",
) -> Path:
    """
    Export token usage statistics to JSON file.
    导出 token 使用统计到 JSON 文件。

    Args:
        llm_interface: LLM interface instance with token tracker
        output_dir: Output directory
        experiment_name: Experiment name for file naming

    Returns:
        Path to the exported JSON file
    """
    try:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get token usage summary
        token_stats = llm_interface.get_token_usage()

        # Add model info
        token_stats["model_name"] = llm_interface.model_name
        token_stats["backend"] = llm_interface.__class__.__name__

        # Export to JSON
        output_file = output_dir / f"{experiment_name}_token_usage.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(token_stats, f, indent=2, ensure_ascii=False)

        logger.info(f"[TokenStats] Token usage exported to: {output_file}")
        logger.info(f"[TokenStats] Total calls: {token_stats['total_calls']}, Total tokens: {token_stats['total_tokens']}")

        return output_file

    except Exception as e:
        logger.error(f"[TokenStats] Failed to export token stats: {str(e)}", exc_info=True)
        return None


def format_token_stats_report(token_stats: Dict[str, Any]) -> str:
    """
    Format token usage statistics as a readable report.
    将 token 使用统计格式化为可读的报告。

    Args:
        token_stats: Token usage dictionary

    Returns:
        Formatted report string
    """
    report_lines = []
    report_lines.append("\n" + "=" * 70)
    report_lines.append("📊 Token Usage Statistics")
    report_lines.append("=" * 70 + "\n")

    report_lines.append(f"Model: {token_stats.get('model_name', 'N/A')}")
    report_lines.append(f"Backend: {token_stats.get('backend', 'N/A')}\n")

    report_lines.append(f"Total API Calls: {token_stats.get('total_calls', 0)}")
    report_lines.append(f"Total Tokens: {token_stats.get('total_tokens', 0):,}")
    report_lines.append(f"  - Prompt Tokens: {token_stats.get('total_prompt_tokens', 0):,}")
    report_lines.append(f"  - Completion Tokens: {token_stats.get('total_completion_tokens', 0):,}")
    report_lines.append(f"Average Tokens per Call: {token_stats.get('average_tokens_per_call', 0):.1f}")

    report_lines.append("\n" + "=" * 70 + "\n")

    return "\n".join(report_lines)


def aggregate_token_stats_from_files(
    results_dir: Path,
    pattern: str = "*_token_usage.json"
) -> Dict[str, Any]:
    """
    Aggregate token usage statistics from multiple JSON files.
    从多个 JSON 文件聚合 token 使用统计。

    Args:
        results_dir: Directory containing token usage JSON files
        pattern: File pattern to match

    Returns:
        Aggregated token statistics
    """
    results_dir = Path(results_dir)
    json_files = list(results_dir.glob(pattern))

    if not json_files:
        logger.warning(f"[TokenStats] No token usage files found in {results_dir}")
        return {
            "total_calls": 0,
            "total_tokens": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "experiments": 0
        }

    aggregated = {
        "total_calls": 0,
        "total_tokens": 0,
        "total_prompt_tokens": 0,
        "total_completion_tokens": 0,
        "experiments": len(json_files),
        "per_experiment": []
    }

    for json_file in json_files:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                stats = json.load(f)

            aggregated["total_calls"] += stats.get("total_calls", 0)
            aggregated["total_tokens"] += stats.get("total_tokens", 0)
            aggregated["total_prompt_tokens"] += stats.get("total_prompt_tokens", 0)
            aggregated["total_completion_tokens"] += stats.get("total_completion_tokens", 0)

            aggregated["per_experiment"].append({
                "experiment": json_file.stem,
                "total_calls": stats.get("total_calls", 0),
                "total_tokens": stats.get("total_tokens", 0)
            })

        except Exception as e:
            logger.warning(f"[TokenStats] Failed to read {json_file}: {str(e)}")

    aggregated["average_tokens_per_experiment"] = (
        aggregated["total_tokens"] / aggregated["experiments"]
        if aggregated["experiments"] > 0 else 0
    )

    return aggregated
