"""
Author: Claude
Date: 2025-11-28 14:35:00
LastEditTime: 2025-11-28 14:35:00
LastEditors: Claude
Description: Multi-task post-processing engine
             多任务后处理引擎 - 根据任务类型生成对应的汇总文件
FilePath: /HydroAgent/hydroagent/utils/post_processor.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import logging
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class PostProcessingEngine:
    """
    多任务后处理引擎

    职责：
    - 根据任务类型分发到对应的处理器
    - 生成汇总CSV、对比图表、排名JSON、分析报告
    - 调用已有的DataLoader、PlottingToolkit、ReportGenerator

    设计模式：
    - Strategy Pattern: 每个任务类型对应一个处理器方法
    - Dependency Injection: workspace_dir通过构造函数注入
    - Graceful Degradation: 后处理失败不影响整体分析
    """

    def __init__(self, workspace_dir: Path):
        """
        初始化后处理引擎。

        Args:
            workspace_dir: 工作目录（session目录）
        """
        self.workspace_dir = Path(workspace_dir)

    def process(
        self,
        task_type: str,
        subtask_results: List[Dict],
        task_plan: Dict,
        intent: Dict
    ) -> Dict[str, Any]:
        """
        统一入口：根据任务类型分发到对应处理器。

        Args:
            task_type: 任务类型（来自TaskTypeDetector）
            subtask_results: 子任务结果列表
            task_plan: 任务计划
            intent: 意图结果

        Returns:
            后处理结果:
            {
                "success": bool,
                "task_type": str,
                "summary_files": {
                    "csv": str,
                    "plots": [str, ...],
                    "json": str or [str, ...],
                    "report": str
                },
                "error": str (if failed)
            }
        """
        logger.info(f"[PostProcessor] Starting post-processing for task_type={task_type}")

        # 处理器映射
        processors = {
            "multi_basin": self._process_multi_basin,
            "multi_algorithm": self._process_multi_algorithm,
            "repeated_calibration": self._process_repeated_calibration,
            "iterative_optimization": self._process_iterative_optimization,
            "multi_task_generic": self._process_generic
        }

        # 获取对应处理器（兜底到generic）
        processor = processors.get(task_type, self._process_generic)

        try:
            result = processor(subtask_results, task_plan, intent)
            logger.info(f"[PostProcessor] ✅ Post-processing completed for {task_type}")
            return result

        except Exception as e:
            logger.error(f"[PostProcessor] ❌ Post-processing failed for {task_type}: {str(e)}", exc_info=True)
            return {
                "success": False,
                "task_type": task_type,
                "error": str(e)
            }

    # ========================================================================
    #   Core Processors (Phase 2)
    # ========================================================================

    def _process_multi_basin(
        self,
        subtask_results: List[Dict],
        task_plan: Dict,
        intent: Dict
    ) -> Dict[str, Any]:
        """
        实验2B：多流域批量率定后处理

        生成文件：
        1. multi_basin_summary.csv - 所有流域的性能指标汇总
        2. metrics_comparison.png - NSE/RMSE/KGE对比柱状图
        3. basin_ranking.json - 流域性能排名
        4. analysis_report.md - 分析报告（可选）
        """
        logger.info("[PostProcessor] Processing multi_basin tasks")

        # Step 1: 使用DataLoader提取所有流域数据
        from hydroagent.utils.data_loader import DataLoader

        data = DataLoader.extract_metrics_from_session(self.workspace_dir)

        # Step 2: 生成CSV汇总表
        summary_csv = self._generate_multi_basin_csv(data)

        # Step 3: 生成对比图表
        plots = []
        metrics_plot = self._generate_metrics_comparison_plot(data)
        if metrics_plot:
            plots.append(str(metrics_plot))

        # Step 4: 生成排名JSON
        ranking_json = self._generate_basin_ranking(data)

        # Step 5: 使用ReportGenerator生成分析报告（可选）
        report_path = None
        try:
            from hydroagent.utils.report_generator import ReportGenerator

            report_path = ReportGenerator.generate_multi_basin_report(
                analysis={},
                basin_results=data.get("tasks", {}),
                plots=plots,
                output_path=self.workspace_dir
            )
        except Exception as e:
            logger.warning(f"[PostProcessor] Report generation failed: {e}")

        return {
            "success": True,
            "task_type": "multi_basin",
            "summary_files": {
                "csv": str(summary_csv),
                "plots": plots,
                "json": str(ranking_json),
                "report": str(report_path) if report_path else None
            }
        }

    def _process_repeated_calibration(
        self,
        subtask_results: List[Dict],
        task_plan: Dict,
        intent: Dict
    ) -> Dict[str, Any]:
        """
        实验5：重复率定稳定性验证后处理

        生成文件：
        1. stability_summary.csv - 稳定性统计（均值、标准差、变异系数）
        2. nse_boxplot.png - NSE箱线图
        3. parameter_distribution.png - 参数分布图（可选）
        4. convergence_analysis.json - 收敛性分析
        """
        logger.info("[PostProcessor] Processing repeated_calibration tasks")

        # 加载重复率定数据
        from hydroagent.utils.data_loader import DataLoader

        data = DataLoader.load_repeated_calibration_data(
            workspace_dir=self.workspace_dir,
            n_repeats=len(subtask_results)
        )

        # 生成稳定性摘要CSV
        summary_csv = self._generate_stability_summary_csv(data)

        # 生成箱线图
        plots = []
        nse_boxplot = self._generate_nse_boxplot(data)
        if nse_boxplot:
            plots.append(str(nse_boxplot))

        # 生成收敛分析JSON
        convergence_json = self._generate_convergence_analysis(data)

        # 生成分析报告（可选）
        report_path = None
        try:
            from hydroagent.utils.report_generator import ReportGenerator

            report_path = ReportGenerator.generate_repeated_calibration_report(
                analysis={},
                repeated_results=data.get("tasks", {}),
                plots=plots,
                output_path=self.workspace_dir
            )
        except Exception as e:
            logger.warning(f"[PostProcessor] Report generation failed: {e}")

        return {
            "success": True,
            "task_type": "repeated_calibration",
            "summary_files": {
                "csv": str(summary_csv),
                "plots": plots,
                "json": str(convergence_json),
                "report": str(report_path) if report_path else None
            }
        }

    def _process_multi_algorithm(
        self,
        subtask_results: List[Dict],
        task_plan: Dict,
        intent: Dict
    ) -> Dict[str, Any]:
        """
        实验2C：多算法×多模型组合后处理

        生成文件：
        1. model_algorithm_matrix.csv - 性能矩阵
        2. nse_heatmap.png - NSE热力图
        3. algorithm_ranking.json - 算法平均性能排名
        4. model_ranking.json - 模型平均性能排名
        5. best_combination.json - 最佳组合推荐
        """
        logger.info("[PostProcessor] Processing multi_algorithm tasks")

        # 提取算法×模型矩阵数据
        data = self._extract_algorithm_model_matrix(subtask_results)

        # 生成矩阵CSV
        matrix_csv = self._generate_algorithm_model_matrix_csv(data)

        # 生成热力图
        plots = []
        heatmap = self._generate_nse_heatmap(data)
        if heatmap:
            plots.append(str(heatmap))

        # 生成排名JSON（算法、模型、最佳组合）
        algorithm_ranking = self._rank_algorithms(data)
        model_ranking = self._rank_models(data)
        best_combination = self._find_best_combination(data)

        json_files = [
            str(algorithm_ranking),
            str(model_ranking),
            str(best_combination)
        ]

        # 生成分析报告（可选）
        report_path = None
        try:
            from hydroagent.utils.report_generator import ReportGenerator

            report_path = ReportGenerator.generate_summary_report(
                analysis={},
                results=data.get("matrix", {}),
                plots=plots,
                output_path=self.workspace_dir / "analysis_report.md"
            )
        except Exception as e:
            logger.warning(f"[PostProcessor] Report generation failed: {e}")

        return {
            "success": True,
            "task_type": "multi_algorithm",
            "summary_files": {
                "csv": str(matrix_csv),
                "plots": plots,
                "json": json_files,
                "report": str(report_path) if report_path else None
            }
        }

    # ========================================================================
    #   Auxiliary Processors (Phase 3)
    # ========================================================================

    def _process_iterative_optimization(
        self,
        subtask_results: List[Dict],
        task_plan: Dict,
        intent: Dict
    ) -> Dict[str, Any]:
        """
        实验3：迭代优化后处理

        生成文件：
        1. nse_convergence.png - NSE收敛曲线
        2. parameter_evolution.json - 参数演化轨迹
        """
        logger.info("[PostProcessor] Processing iterative_optimization tasks")

        # 提取迭代历史
        iteration_history = []
        for i, result in enumerate(subtask_results, 1):
            metrics = result.get("evaluation_metrics", {})
            params = result.get("best_params", {})

            iteration_history.append({
                "iteration": i,
                "NSE": metrics.get("NSE", None),
                "RMSE": metrics.get("RMSE", None),
                "params": params
            })

        # 生成收敛曲线图
        plots = []
        convergence_plot = self._generate_convergence_plot(iteration_history)
        if convergence_plot:
            plots.append(str(convergence_plot))

        # 生成参数演化JSON
        param_evolution = self.workspace_dir / "parameter_evolution.json"
        with open(param_evolution, 'w', encoding='utf-8') as f:
            json.dump(iteration_history, f, indent=2, ensure_ascii=False)

        logger.info(f"[PostProcessor] Generated: {param_evolution}")

        return {
            "success": True,
            "task_type": "iterative_optimization",
            "summary_files": {
                "plots": plots,
                "json": str(param_evolution)
            }
        }

    def _process_generic(
        self,
        subtask_results: List[Dict],
        task_plan: Dict,
        intent: Dict
    ) -> Dict[str, Any]:
        """
        通用多任务后处理（兜底）

        生成文件：
        1. task_summary.csv - 基础任务汇总表
        2. performance_comparison.png - 简单性能对比图（如果有性能指标）
        """
        logger.info("[PostProcessor] Processing multi_task_generic")

        # 生成基础汇总表
        summary_csv = self._generate_generic_summary(subtask_results)

        # 尝试生成简单对比图
        plots = []
        try:
            comparison_plot = self._generate_generic_comparison_plot(subtask_results)
            if comparison_plot:
                plots.append(str(comparison_plot))
        except Exception as e:
            logger.warning(f"[PostProcessor] Generic plot generation failed: {e}")

        return {
            "success": True,
            "task_type": "multi_task_generic",
            "summary_files": {
                "csv": str(summary_csv),
                "plots": plots
            }
        }

    # ========================================================================
    #   Helper Methods (Multi-Basin)
    # ========================================================================

    def _generate_multi_basin_csv(self, data: Dict) -> Path:
        """生成多流域汇总CSV"""
        import pandas as pd
        import yaml

        rows = []
        for task_id, task_data in data.get("tasks", {}).items():
            metrics = task_data.get("metrics", {})

            # 从配置文件读取basin_id
            basin_id = "N/A"
            task_dir = self.workspace_dir / task_id
            config_file = task_dir / "calibration_config.yaml"

            if config_file.exists():
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f)
                    basin_ids = config.get("data_cfgs", {}).get("basin_ids", [])
                    if basin_ids:
                        basin_id = basin_ids[0]
                except Exception as e:
                    logger.warning(f"[PostProcessor] Failed to read basin_id from {config_file}: {e}")

            rows.append({
                "basin_id": basin_id,
                "NSE": metrics.get("NSE", None),
                "RMSE": metrics.get("RMSE", None),
                "KGE": metrics.get("KGE", None),
                "PBIAS": metrics.get("PBIAS", None)
            })

        df = pd.DataFrame(rows)
        output_path = self.workspace_dir / "multi_basin_summary.csv"
        df.to_csv(output_path, index=False)

        logger.info(f"[PostProcessor] Generated: {output_path}")
        return output_path

    def _generate_basin_ranking(self, data: Dict) -> Path:
        """生成流域性能排名JSON"""
        import yaml

        basins = []
        for task_id, task_data in data.get("tasks", {}).items():
            nse = task_data.get("metrics", {}).get("NSE", 0.0) or 0.0

            # 从配置文件读取basin_id
            basin_id = "N/A"
            task_dir = self.workspace_dir / task_id
            config_file = task_dir / "calibration_config.yaml"

            if config_file.exists():
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f)
                    basin_ids = config.get("data_cfgs", {}).get("basin_ids", [])
                    if basin_ids:
                        basin_id = basin_ids[0]
                except Exception as e:
                    logger.warning(f"[PostProcessor] Failed to read basin_id from {config_file}: {e}")

            basins.append({"basin_id": basin_id, "NSE": nse})

        # 按NSE降序排序
        basins.sort(key=lambda x: x["NSE"], reverse=True)

        ranking = {
            "ranking": basins,
            "best_basin": basins[0] if basins else None,
            "worst_basin": basins[-1] if basins else None
        }

        output_path = self.workspace_dir / "basin_ranking.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(ranking, f, indent=2, ensure_ascii=False)

        logger.info(f"[PostProcessor] Generated: {output_path}")
        return output_path

    def _generate_metrics_comparison_plot(self, data: Dict) -> Optional[Path]:
        """生成metrics对比图（调用已有方法）"""
        from hydroagent.utils.plotting import PlottingToolkit
        import yaml

        # 准备数据
        basins = []
        nse_values = []
        rmse_values = []
        kge_values = []

        for task_id, task_data in data.get("tasks", {}).items():
            metrics = task_data.get("metrics", {})

            # 从配置文件读取basin_id
            basin_id = "N/A"
            task_dir = self.workspace_dir / task_id
            config_file = task_dir / "calibration_config.yaml"

            if config_file.exists():
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f)
                    basin_ids = config.get("data_cfgs", {}).get("basin_ids", [])
                    if basin_ids:
                        basin_id = basin_ids[0]
                except Exception as e:
                    logger.warning(f"[PostProcessor] Failed to read basin_id from {config_file}: {e}")

            basins.append(basin_id)
            nse_values.append(metrics.get("NSE", 0.0) or 0.0)
            rmse_values.append(metrics.get("RMSE", 0.0) or 0.0)
            kge_values.append(metrics.get("KGE", 0.0) or 0.0)

        if not basins:
            logger.warning("[PostProcessor] No basin data for metrics comparison plot")
            return None

        # 调用PlottingToolkit
        output_path = self.workspace_dir / "metrics_comparison.png"

        success = PlottingToolkit.plot_metrics_comparison(
            basin_ids=basins,
            nse_values=nse_values,
            rmse_values=rmse_values,
            kge_values=kge_values,
            output_path=output_path
        )

        if success:
            logger.info(f"[PostProcessor] Generated: {output_path}")
            return output_path

        return None

    # ========================================================================
    #   Helper Methods (Repeated Calibration)
    # ========================================================================

    def _generate_stability_summary_csv(self, data: Dict) -> Path:
        """生成稳定性摘要CSV"""
        import pandas as pd
        import numpy as np

        metrics_data = data.get("metrics", {})

        rows = []
        for metric_name, values in metrics_data.items():
            if not values:
                continue

            rows.append({
                "metric": metric_name,
                "mean": np.mean(values),
                "std": np.std(values),
                "cv": np.std(values) / np.mean(values) if np.mean(values) != 0 else None,
                "min": np.min(values),
                "max": np.max(values)
            })

        df = pd.DataFrame(rows)
        output_path = self.workspace_dir / "stability_summary.csv"
        df.to_csv(output_path, index=False)

        logger.info(f"[PostProcessor] Generated: {output_path}")
        return output_path

    def _generate_nse_boxplot(self, data: Dict) -> Optional[Path]:
        """生成NSE箱线图"""
        from hydroagent.utils.plotting import PlottingToolkit

        nse_values = data.get("metrics", {}).get("NSE", [])
        if not nse_values:
            logger.warning("[PostProcessor] No NSE values for boxplot")
            return None

        output_path = self.workspace_dir / "nse_boxplot.png"

        success = PlottingToolkit.plot_boxplot(
            data={"NSE": nse_values},
            x_label="Repetition",
            y_label="NSE",
            title="NSE Stability Across Repetitions",
            output_path=output_path
        )

        if success:
            logger.info(f"[PostProcessor] Generated: {output_path}")
            return output_path

        return None

    def _generate_convergence_analysis(self, data: Dict) -> Path:
        """生成收敛性分析JSON"""
        import numpy as np

        metrics_data = data.get("metrics", {})
        nse_values = metrics_data.get("NSE", [])

        if nse_values:
            convergence = {
                "converged": np.std(nse_values) < 0.05,  # CV < 0.05为收敛
                "mean_NSE": np.mean(nse_values),
                "std_NSE": np.std(nse_values),
                "cv_NSE": np.std(nse_values) / np.mean(nse_values) if np.mean(nse_values) != 0 else None,
                "n_repeats": len(nse_values)
            }
        else:
            convergence = {"error": "No NSE values available"}

        output_path = self.workspace_dir / "convergence_analysis.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(convergence, f, indent=2, ensure_ascii=False)

        logger.info(f"[PostProcessor] Generated: {output_path}")
        return output_path

    # ========================================================================
    #   Helper Methods (Multi-Algorithm)
    # ========================================================================

    def _extract_algorithm_model_matrix(self, subtask_results: List[Dict]) -> Dict:
        """提取算法×模型矩阵数据（从文件系统读取）"""
        from hydroagent.utils.data_loader import DataLoader

        # 使用DataLoader从文件系统提取所有任务的metrics
        session_data = DataLoader.extract_metrics_from_session(self.workspace_dir)

        matrix = {}

        # 遍历每个任务，提取算法、模型和metrics
        for task_id, task_info in session_data.get("tasks", {}).items():
            if task_info.get("status") != "success":
                continue

            # 从workspace_dir/task_id目录读取config
            task_dir = self.workspace_dir / task_id
            config_file = task_dir / "calibration_config.yaml"

            if not config_file.exists():
                logger.warning(f"[PostProcessor] Config file not found for {task_id}")
                continue

            try:
                import yaml
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)

                # 提取算法和模型名称
                algorithm = config.get("training_cfgs", {}).get("algorithm_name", "N/A")
                model = config.get("model_cfgs", {}).get("model_name", "N/A")

                # 提取metrics
                metrics = task_info.get("metrics", {})

                key = f"{algorithm}_{model}"
                matrix[key] = {
                    "algorithm": algorithm,
                    "model": model,
                    "NSE": metrics.get("NSE", None),
                    "RMSE": metrics.get("RMSE", None),
                    "KGE": metrics.get("KGE", None)
                }

                logger.debug(f"[PostProcessor] Extracted {key}: NSE={metrics.get('NSE')}")

            except Exception as e:
                logger.warning(f"[PostProcessor] Failed to extract config for {task_id}: {e}")
                continue

        return {"matrix": matrix}

    def _generate_algorithm_model_matrix_csv(self, data: Dict) -> Path:
        """生成算法×模型矩阵CSV"""
        import pandas as pd

        rows = []
        for key, item in data.get("matrix", {}).items():
            rows.append({
                "algorithm": item["algorithm"],
                "model": item["model"],
                "NSE": item.get("NSE"),
                "RMSE": item.get("RMSE"),
                "KGE": item.get("KGE")
            })

        df = pd.DataFrame(rows)
        output_path = self.workspace_dir / "model_algorithm_matrix.csv"
        df.to_csv(output_path, index=False)

        logger.info(f"[PostProcessor] Generated: {output_path}")
        return output_path

    def _generate_nse_heatmap(self, data: Dict) -> Optional[Path]:
        """生成NSE热力图"""
        from hydroagent.utils.plotting import PlottingToolkit

        # 提取矩阵数据
        matrix_data = data.get("matrix", {})
        if not matrix_data:
            logger.warning("[PostProcessor] No matrix data for heatmap")
            return None

        # 提取所有唯一的算法和模型
        algorithms = sorted(set(item["algorithm"] for item in matrix_data.values()))
        models = sorted(set(item["model"] for item in matrix_data.values()))

        if not algorithms or not models:
            logger.warning("[PostProcessor] No algorithms or models found for heatmap")
            return None

        # 构建2D矩阵 (algorithms × models)
        nse_matrix = []
        for algo in algorithms:
            row = []
            for model in models:
                # 查找对应的NSE值
                nse = 0.0
                for item in matrix_data.values():
                    if item["algorithm"] == algo and item["model"] == model:
                        nse = item.get("NSE", 0.0) or 0.0
                        break
                row.append(nse)
            nse_matrix.append(row)

        # 调用PlottingToolkit绘制热力图
        output_path = self.workspace_dir / "nse_heatmap.png"

        success = PlottingToolkit.plot_heatmap(
            data=nse_matrix,
            x_labels=models,
            y_labels=algorithms,
            title="NSE Heatmap: Algorithms × Models",
            output_path=output_path,
            cbar_label="NSE",
            cmap="RdYlGn",
            show_values=True
        )

        if success:
            logger.info(f"[PostProcessor] Generated: {output_path}")
            return output_path

        return None

    def _rank_algorithms(self, data: Dict) -> Path:
        """生成算法排名JSON"""
        from collections import defaultdict

        algorithm_scores = defaultdict(list)

        for key, item in data.get("matrix", {}).items():
            algo = item["algorithm"]
            nse = item.get("NSE", 0.0)
            algorithm_scores[algo].append(nse)

        # 计算平均NSE
        ranking = []
        for algo, scores in algorithm_scores.items():
            import numpy as np
            ranking.append({
                "algorithm": algo,
                "mean_NSE": np.mean(scores),
                "count": len(scores)
            })

        ranking.sort(key=lambda x: x["mean_NSE"], reverse=True)

        output_path = self.workspace_dir / "algorithm_ranking.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({"ranking": ranking}, f, indent=2, ensure_ascii=False)

        logger.info(f"[PostProcessor] Generated: {output_path}")
        return output_path

    def _rank_models(self, data: Dict) -> Path:
        """生成模型排名JSON"""
        from collections import defaultdict

        model_scores = defaultdict(list)

        for key, item in data.get("matrix", {}).items():
            model = item["model"]
            nse = item.get("NSE", 0.0)
            model_scores[model].append(nse)

        # 计算平均NSE
        ranking = []
        for model, scores in model_scores.items():
            import numpy as np
            ranking.append({
                "model": model,
                "mean_NSE": np.mean(scores),
                "count": len(scores)
            })

        ranking.sort(key=lambda x: x["mean_NSE"], reverse=True)

        output_path = self.workspace_dir / "model_ranking.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({"ranking": ranking}, f, indent=2, ensure_ascii=False)

        logger.info(f"[PostProcessor] Generated: {output_path}")
        return output_path

    def _find_best_combination(self, data: Dict) -> Path:
        """查找最佳组合"""
        best = None
        best_nse = -float('inf')

        for key, item in data.get("matrix", {}).items():
            nse = item.get("NSE", -float('inf'))
            if nse > best_nse:
                best_nse = nse
                best = item

        output_path = self.workspace_dir / "best_combination.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({"best_combination": best}, f, indent=2, ensure_ascii=False)

        logger.info(f"[PostProcessor] Generated: {output_path}")
        return output_path

    # ========================================================================
    #   Helper Methods (Generic)
    # ========================================================================

    def _generate_generic_summary(self, subtask_results: List[Dict]) -> Path:
        """生成通用汇总表（从文件系统读取metrics）"""
        import pandas as pd
        from hydroagent.utils.data_loader import DataLoader

        # 使用DataLoader从文件系统提取所有任务的metrics
        session_data = DataLoader.extract_metrics_from_session(self.workspace_dir)

        # 自然排序task_id（task_1, task_2, ..., task_10, task_11, ...）
        def natural_sort_key(task_id):
            parts = task_id.replace("task_", "").split("_")
            try:
                return (int(parts[0]), task_id)
            except (ValueError, IndexError):
                return (float('inf'), task_id)

        rows = []
        for task_id, task_info in sorted(session_data.get("tasks", {}).items(), key=lambda x: natural_sort_key(x[0])):
            metrics = task_info.get("metrics", {})
            status = task_info.get("status", "unknown")

            rows.append({
                "task_id": task_id,
                "NSE": metrics.get("NSE", None),
                "RMSE": metrics.get("RMSE", None),
                "status": status
            })

        df = pd.DataFrame(rows)
        output_path = self.workspace_dir / "task_summary.csv"
        df.to_csv(output_path, index=False)

        logger.info(f"[PostProcessor] Generated: {output_path}")
        return output_path

    def _generate_generic_comparison_plot(self, subtask_results: List[Dict]) -> Optional[Path]:
        """生成通用对比图"""
        # 简化实现：如果有NSE数据，生成柱状图
        nse_values = [
            r.get("evaluation_metrics", {}).get("NSE", 0.0)
            for r in subtask_results
        ]

        if not any(nse_values):
            return None

        from hydroagent.utils.plotting import PlottingToolkit

        output_path = self.workspace_dir / "performance_comparison.png"

        # TODO: 调用简单柱状图方法
        # 暂时跳过
        logger.warning("[PostProcessor] Generic comparison plot not yet implemented")
        return None

    def _generate_convergence_plot(self, iteration_history: List[Dict]) -> Optional[Path]:
        """生成迭代收敛曲线"""
        from hydroagent.utils.plotting import PlottingToolkit

        iterations = [h["iteration"] for h in iteration_history]
        nse_values = [h.get("NSE", 0.0) for h in iteration_history]

        if not nse_values:
            return None

        output_path = self.workspace_dir / "nse_convergence.png"

        # TODO: 调用线图绘制方法
        # 暂时跳过
        logger.warning("[PostProcessor] Convergence plot not yet implemented")
        return None
