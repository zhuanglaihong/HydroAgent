r"""
Author: Claude & zhuanglaihong
Date: 2025-01-20 20:00:00
LastEditTime: 2025-01-20 20:00:00
LastEditors: Claude
Description: Result analysis middleware for boundary detection (Tech 4.2)
             结果分析中间件 - 用于边界效应检测
FilePath: \HydroAgent\hydroagent\utils\result_parser.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import logging
import json
import yaml
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class ResultParser:
    """
    Intelligent result analysis middleware (Tech 4.2).
    智能结果分析中间件。

    Purpose:
    - Parse hydromodel output files (JSON, CSV)
    - Detect boundary effects in parameter optimization
    - Calculate convergence metrics
    - Generate actionable insights for agents

    Transforms raw data into "insights" that LLMs can understand.
    """

    def __init__(self, boundary_threshold: float = 0.01):
        """
        Initialize ResultParser.

        Args:
            boundary_threshold: Threshold for boundary detection (default 1%)
        """
        self.boundary_threshold = boundary_threshold

    def parse_calibration_results(
        self,
        result_dir: Path,
        param_range_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Parse calibration results and generate comprehensive analysis.
        解析率定结果并生成综合分析。

        Args:
            result_dir: Directory containing result files
            param_range_path: Path to param_range.yaml for boundary detection

        Returns:
            Analysis dictionary with insights
        """
        logger.info(f"[ResultParser] Parsing results from {result_dir}")

        analysis = {
            "summary": {},
            "convergence": {},
            "boundary_effects": {},
            "warnings": [],
            "recommendations": []
        }

        if not result_dir.exists():
            logger.error(f"Result directory not found: {result_dir}")
            return analysis

        # Parse JSON results
        json_files = list(result_dir.glob("**/calibration_results.json"))
        for json_file in json_files:
            json_summary = self._parse_json_result(json_file)
            analysis["summary"].update(json_summary)

        # Parse CSV results (SCE-UA iterations)
        csv_files = list(result_dir.glob("**/*_sceua.csv"))
        for csv_file in csv_files:
            csv_analysis = self._parse_csv_result(csv_file)
            analysis["convergence"].update(csv_analysis)

        # Boundary effect detection
        if param_range_path and param_range_path.exists():
            optimal_params = analysis["summary"].get("optimal_params", {})
            if optimal_params:
                boundary_analysis = self._detect_boundary_effects(
                    optimal_params,
                    param_range_path
                )
                analysis["boundary_effects"] = boundary_analysis
                analysis["warnings"].extend(boundary_analysis.get("warnings", []))

        # Generate recommendations
        analysis["recommendations"] = self._generate_recommendations(analysis)

        logger.info("[ResultParser] Analysis complete")
        return analysis

    def _parse_json_result(self, json_path: Path) -> Dict[str, Any]:
        """
        Parse calibration_results.json file.
        解析 calibration_results.json 文件。

        Args:
            json_path: Path to JSON result file

        Returns:
            Summary dictionary
        """
        logger.info(f"[ResultParser] Parsing JSON: {json_path}")

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            summary = {
                "nse": None,
                "rmse": None,
                "optimal_params": {},
                "file_path": str(json_path)
            }

            # TODO: Extract actual structure from hydromodel results
            # This depends on the exact format of calibration_results.json

            # Example structure (adjust based on actual format):
            if "metrics" in data:
                summary["nse"] = data["metrics"].get("nse")
                summary["rmse"] = data["metrics"].get("rmse")

            if "parameters" in data:
                summary["optimal_params"] = data["parameters"]

            logger.info(f"[ResultParser] Extracted NSE: {summary['nse']}")

            return summary

        except Exception as e:
            logger.error(f"Failed to parse JSON: {str(e)}")
            return {}

    def _parse_csv_result(self, csv_path: Path) -> Dict[str, Any]:
        """
        Parse SCE-UA CSV file for convergence analysis.
        解析 SCE-UA CSV 文件进行收敛分析。

        Args:
            csv_path: Path to CSV file

        Returns:
            Convergence analysis dictionary
        """
        logger.info(f"[ResultParser] Parsing CSV: {csv_path}")

        try:
            df = pd.read_csv(csv_path)

            convergence = {
                "total_iterations": len(df),
                "final_value": None,
                "convergence_rate": None,
                "variance_last_10pct": None,
                "is_converged": False
            }

            # Assume first column is objective function value
            if len(df.columns) > 0:
                obj_col = df.columns[0]
                values = df[obj_col].values

                convergence["final_value"] = float(values[-1])

                # Calculate convergence metrics
                # Variance of last 10% of iterations
                last_10pct = int(len(values) * 0.1)
                if last_10pct > 0:
                    last_values = values[-last_10pct:]
                    variance = np.var(last_values)
                    convergence["variance_last_10pct"] = float(variance)

                    # Consider converged if variance < threshold
                    convergence["is_converged"] = variance < 0.001

                # Calculate improvement rate
                if len(values) > 1:
                    initial = values[0]
                    final = values[-1]
                    if initial != 0:
                        improvement = (initial - final) / abs(initial) * 100
                        convergence["convergence_rate"] = float(improvement)

            logger.info(f"[ResultParser] Convergence: {convergence['is_converged']}")

            return convergence

        except Exception as e:
            logger.error(f"Failed to parse CSV: {str(e)}")
            return {}

    def _detect_boundary_effects(
        self,
        optimal_params: Dict[str, float],
        param_range_path: Path
    ) -> Dict[str, Any]:
        """
        Detect boundary effects in optimized parameters (Tech 4.2 core).
        检测优化参数中的边界效应。

        Args:
            optimal_params: Optimized parameter values
            param_range_path: Path to param_range.yaml

        Returns:
            Boundary analysis result
        """
        logger.info("[ResultParser] Detecting boundary effects...")

        try:
            with open(param_range_path, 'r', encoding='utf-8') as f:
                param_ranges = yaml.safe_load(f)

            boundary_analysis = {
                "params_at_boundary": [],
                "params_converged_well": [],
                "warnings": [],
                "suggested_adjustments": {}
            }

            for param_name, param_value in optimal_params.items():
                if param_name not in param_ranges:
                    logger.warning(f"Parameter '{param_name}' not in param_range.yaml")
                    continue

                param_range = param_ranges[param_name]

                # Assume param_range is [min, max]
                if isinstance(param_range, (list, tuple)) and len(param_range) == 2:
                    min_val, max_val = param_range
                    range_span = max_val - min_val

                    # Calculate proximity to boundaries
                    lower_proximity = abs(param_value - min_val) / range_span
                    upper_proximity = abs(param_value - max_val) / range_span

                    # Check if hitting boundaries
                    if lower_proximity < self.boundary_threshold:
                        # Hitting lower boundary
                        boundary_analysis["params_at_boundary"].append(param_name)
                        boundary_analysis["warnings"].append(
                            f"Parameter '{param_name}' = {param_value:.4f} hit lower bound ({min_val:.4f})"
                        )

                        # Suggest expanding lower bound
                        new_min = min_val - range_span * 0.2  # Expand by 20%
                        boundary_analysis["suggested_adjustments"][param_name] = [new_min, max_val]

                    elif upper_proximity < self.boundary_threshold:
                        # Hitting upper boundary
                        boundary_analysis["params_at_boundary"].append(param_name)
                        boundary_analysis["warnings"].append(
                            f"Parameter '{param_name}' = {param_value:.4f} hit upper bound ({max_val:.4f})"
                        )

                        # Suggest expanding upper bound
                        new_max = max_val + range_span * 0.2  # Expand by 20%
                        boundary_analysis["suggested_adjustments"][param_name] = [min_val, new_max]

                    else:
                        # Well converged within bounds
                        boundary_analysis["params_converged_well"].append(param_name)

            logger.info(
                f"[ResultParser] Boundary effects detected: "
                f"{len(boundary_analysis['params_at_boundary'])} parameters at boundary"
            )

            return boundary_analysis

        except Exception as e:
            logger.error(f"Boundary detection failed: {str(e)}")
            return {"warnings": [f"Boundary detection error: {str(e)}"]}

    def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """
        Generate actionable recommendations based on analysis.
        基于分析生成可操作的建议。

        Args:
            analysis: Full analysis result

        Returns:
            List of recommendation strings
        """
        recommendations = []

        # Recommendations based on boundary effects
        boundary_effects = analysis.get("boundary_effects", {})
        params_at_boundary = boundary_effects.get("params_at_boundary", [])

        if params_at_boundary:
            recommendations.append(
                f"Expand parameter ranges for: {', '.join(params_at_boundary)}"
            )

            suggested_adjustments = boundary_effects.get("suggested_adjustments", {})
            if suggested_adjustments:
                recommendations.append(
                    "Suggested new param_range.yaml values:"
                )
                for param, new_range in suggested_adjustments.items():
                    recommendations.append(
                        f"  {param}: [{new_range[0]:.4f}, {new_range[1]:.4f}]"
                    )

        # Recommendations based on convergence
        convergence = analysis.get("convergence", {})
        if not convergence.get("is_converged", False):
            recommendations.append(
                "Calibration did not fully converge. Consider:"
            )
            recommendations.append("  - Increase maxn (max iterations)")
            recommendations.append("  - Increase rep (SCE-UA repetitions)")

        # Recommendations based on performance
        summary = analysis.get("summary", {})
        nse = summary.get("nse")
        if nse is not None and nse < 0.6:
            recommendations.append(
                f"Low NSE ({nse:.3f}). Consider:"
            )
            recommendations.append("  - Check input data quality")
            recommendations.append("  - Try different model structure")
            recommendations.append("  - Increase warmup period")

        return recommendations

    def generate_summary_text(self, analysis: Dict[str, Any]) -> str:
        """
        Generate human-readable summary text from analysis.
        从分析生成人类可读的摘要文本。

        Args:
            analysis: Analysis result dictionary

        Returns:
            Formatted summary text
        """
        lines = []

        lines.append("=== Calibration Result Analysis ===\n")

        # Performance metrics
        summary = analysis.get("summary", {})
        if "nse" in summary and summary["nse"] is not None:
            lines.append(f"NSE: {summary['nse']:.4f}")
        if "rmse" in summary and summary["rmse"] is not None:
            lines.append(f"RMSE: {summary['rmse']:.4f}")

        lines.append("")

        # Convergence status
        convergence = analysis.get("convergence", {})
        if convergence:
            is_converged = convergence.get("is_converged", False)
            status = "✓ Converged" if is_converged else "✗ Not fully converged"
            lines.append(f"Convergence: {status}")

            if "variance_last_10pct" in convergence:
                lines.append(f"Variance (last 10%): {convergence['variance_last_10pct']:.6f}")

        lines.append("")

        # Warnings
        warnings = analysis.get("warnings", [])
        if warnings:
            lines.append("⚠️  Warnings:")
            for warning in warnings:
                lines.append(f"  - {warning}")
            lines.append("")

        # Recommendations
        recommendations = analysis.get("recommendations", [])
        if recommendations:
            lines.append("💡 Recommendations:")
            for rec in recommendations:
                lines.append(f"  {rec}")

        return "\n".join(lines)
