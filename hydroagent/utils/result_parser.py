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


# ============================================================================
#   Utility Functions for Parsing hydromodel Results
#   从RunnerAgent提取的工具函数，用于解析hydromodel的返回值
# ============================================================================

def parse_calibration_result(result: Any, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    解析率定结果。
    Parse calibration result.

    Args:
        result: hydromodel calibrate() 的返回值
        config: 原始配置（用于获取输出目录）

    Returns:
        解析后的结果字典，包含calibration_dir
    """
    parsed = {
        "metrics": {},
        "best_params": {},
        "output_files": [],
        "calibration_dir": None
    }

    try:
        # hydromodel的calibrate()会保存结果到output_dir，并返回结果字典
        logger.info(f"[ResultParser] calibrate()返回类型: {type(result)}")

        # 获取输出目录
        output_dir = config.get("training_cfgs", {}).get("output_dir")
        if output_dir:
            output_path = Path(output_dir)
            logger.info(f"[ResultParser] 查找率定输出目录: {output_path}")

            # 🔧 FIX: 支持两种情况
            # 1. 有子目录: output_dir/experiment_name/calibration_results.json (旧版)
            # 2. 无子目录: output_dir/calibration_results.json (experiment_name="" 时)
            if output_path.exists():
                # 先检查是否直接在 output_path 中有 calibration_results.json
                results_file_direct = output_path / "calibration_results.json"

                if results_file_direct.exists():
                    # 情况2：直接保存在 output_dir（experiment_name=""）
                    calibration_dir = str(output_path)
                    logger.info(f"[ResultParser] 找到率定目录（直接模式）: {calibration_dir}")
                    parsed["calibration_dir"] = calibration_dir

                    # 读取 calibration_results.json
                    with open(results_file_direct, 'r') as f:
                        calib_results = json.load(f)
                        logger.info(f"[ResultParser] 读取calibration_results.json")

                        # 提取第一个basin的参数
                        if calib_results:
                            basin_id = list(calib_results.keys())[0]
                            basin_data = calib_results[basin_id]

                            if "best_params" in basin_data:
                                # best_params格式: {"gr4j": {"x1": ..., "x2": ...}}
                                model_params = basin_data["best_params"]
                                # 提取第一个模型的参数
                                if model_params:
                                    model_name = list(model_params.keys())[0]
                                    parsed["best_params"] = model_params[model_name]
                                    logger.info(f"[ResultParser] 提取参数: {parsed['best_params']}")
                else:
                    # 情况1：查找最新的实验子目录（旧版逻辑）
                    experiment_dirs = sorted([d for d in output_path.iterdir() if d.is_dir()],
                                           key=lambda x: x.stat().st_mtime,
                                           reverse=True)

                    if experiment_dirs:
                        calibration_dir = str(experiment_dirs[0])
                        logger.info(f"[ResultParser] 找到率定目录（子目录模式）: {calibration_dir}")
                        parsed["calibration_dir"] = calibration_dir

                        # 尝试读取calibration_results.json
                        results_file = Path(calibration_dir) / "calibration_results.json"
                        if results_file.exists():
                            with open(results_file, 'r') as f:
                                calib_results = json.load(f)
                                logger.info(f"[ResultParser] 读取calibration_results.json")

                                # 提取第一个basin的参数
                                if calib_results:
                                    basin_id = list(calib_results.keys())[0]
                                    basin_data = calib_results[basin_id]

                                    if "best_params" in basin_data:
                                        # best_params格式: {"gr4j": {"x1": ..., "x2": ...}}
                                        model_params = basin_data["best_params"]
                                        # 提取第一个模型的参数
                                        if model_params:
                                            model_name = list(model_params.keys())[0]
                                            parsed["best_params"] = model_params[model_name]
                                            logger.info(f"[ResultParser] 提取参数: {parsed['best_params']}")
                        else:
                            logger.warning(f"[ResultParser] 未找到calibration_results.json: {results_file}")
                    else:
                        logger.warning(f"[ResultParser] 输出目录中没有实验目录或结果文件: {output_path}")
            else:
                logger.warning(f"[ResultParser] 输出目录不存在: {output_path}")
        else:
            logger.warning("[ResultParser] 配置中没有output_dir")

        # 如果result是dict，也尝试从中提取信息
        if isinstance(result, dict):
            logger.info(f"[ResultParser] result的keys: {list(result.keys())}")

            if "metrics" in result:
                parsed["metrics"] = result["metrics"]
            elif "performance" in result:
                parsed["metrics"] = result["performance"]

        logger.info(f"[ResultParser] 解析结果: calibration_dir={parsed['calibration_dir']}, best_params={len(parsed['best_params'])}个")

    except Exception as e:
        logger.error(f"[ResultParser] 解析率定结果时出错: {str(e)}", exc_info=True)

    return parsed


def parse_evaluation_result(result: Any) -> Dict[str, Any]:
    """
    解析评估结果。
    Parse evaluation result.

    Args:
        result: hydromodel evaluate() 的返回值
                格式: {basin_id: {"metrics": {...}, "parameters": {...}}, ...}

    Returns:
        解析后的结果字典
    """
    parsed = {
        "metrics": {},
        "performance": {},
        "output_files": []
    }

    try:
        if isinstance(result, dict):
            # hydromodel的evaluate()返回格式: {basin_id: {"metrics": {...}, "parameters": {...}}}
            # 提取第一个basin的metrics（通常只有一个basin）
            if result:
                first_basin_id = list(result.keys())[0]
                basin_result = result[first_basin_id]

                if isinstance(basin_result, dict):
                    # 提取metrics
                    if "metrics" in basin_result:
                        metrics = basin_result["metrics"]
                        # hydromodel返回的metrics可能是dict或有数组值的dict
                        # 例如: {"NSE": array([0.85]), "RMSE": array([1.23])}
                        # 将数组值转换为标量
                        flat_metrics = {}
                        for key, value in metrics.items():
                            if isinstance(value, (list, np.ndarray)):
                                flat_metrics[key] = float(value[0]) if len(value) > 0 else None
                            else:
                                flat_metrics[key] = value

                        parsed["metrics"] = flat_metrics
                        parsed["performance"] = flat_metrics
                        logger.info(f"[ResultParser] 提取basin {first_basin_id}的metrics: {list(flat_metrics.keys())}")

                    # 提取parameters
                    if "parameters" in basin_result:
                        parsed["parameters"] = basin_result["parameters"]

            # 旧格式兼容（直接包含metrics的情况）
            elif "metrics" in result:
                parsed["metrics"] = result["metrics"]
                parsed["performance"] = result["metrics"]
            elif "performance" in result:
                parsed["performance"] = result["performance"]
                parsed["metrics"] = result["performance"]

            # 提取输出文件
            if "output_files" in result:
                parsed["output_files"] = result["output_files"]
            elif "files" in result:
                parsed["output_files"] = result["files"]

        logger.debug(f"[ResultParser] 解析评估结果: {len(parsed['metrics'])} 个指标")

    except Exception as e:
        logger.warning(f"[ResultParser] 解析评估结果时出错: {str(e)}", exc_info=True)

    return parsed


# ============================================================================
#   ResultParser Class (Intelligent Analysis Middleware)
# ============================================================================

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
