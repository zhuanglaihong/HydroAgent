"""
Author: Claude & zhuanglaihong
Date: 2025-01-20 19:55:00
LastEditTime: 2025-01-20 19:55:00
LastEditors: Claude
Description: Developer agent for result analysis and code generation (Exp 3)
             开发者智能体 - 负责结果分析和代码生成
FilePath: \HydroAgent\hydroagent\agents\developer_agent.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from typing import Dict, Any, Optional, List
from pathlib import Path
import logging
import json

from ..core.base_agent import BaseAgent
from ..core.llm_interface import LLMInterface
from ..utils.prompt_manager import PromptManager

logger = logging.getLogger(__name__)


class DeveloperAgent(BaseAgent):
    """
    Developer agent for advanced analysis and visualization (v4.0).
    开发者智能体 - 高级分析和可视化（v4.0）。

    Similar to OpenFOAMGPT's Post-processing Agent.

    🆕 v4.0 Changes:
    - **Removed** code generation (moved to RunnerAgent)
    - **Added** visualization plotting methods
    - **Focus** on analysis, reporting, and visualization

    Responsibilities:
    - Result analysis: Parse results/ directory (JSON, CSV)
    - Calculate NSE improvement rate (for Experiment 2)
    - Detect boundary effects in parameter optimization
    - 🆕 Visualization: Generate publication-quality plots
      * Streamflow fit plots
      * NSE convergence plots
      * Parameter distribution plots
      * Metrics comparison plots
    - Generate analysis reports with recommendations
    """

    def __init__(
        self,
        llm_interface: LLMInterface,
        workspace_dir: Optional[Path] = None,
        use_dynamic_prompt: bool = True,
        **kwargs
    ):
        """
        Initialize DeveloperAgent (v4.0 simplified).

        Args:
            llm_interface: LLM API interface for analysis and reporting
            workspace_dir: Working directory for results and plots
            use_dynamic_prompt: Use dynamic prompt management system
            **kwargs: Additional configuration

        Note:
            代码生成功能已迁移到RunnerAgent（v4.0改进）
            Code generation has been moved to RunnerAgent (v4.0 enhancement)
        """
        super().__init__(
            name="DeveloperAgent",
            llm_interface=llm_interface,
            workspace_dir=workspace_dir,
            **kwargs
        )

        self.use_dynamic_prompt = use_dynamic_prompt
        logger.info("[DeveloperAgent] v4.0 - Focus on analysis and visualization")

        # Initialize PromptManager for dynamic prompts
        if self.use_dynamic_prompt:
            self.prompt_manager = PromptManager()
            # Load static prompt from file
            prompt_text = self._load_prompt_from_file("developer_agent_prompt.txt")
            if prompt_text:
                self.prompt_manager.register_static_prompt("DeveloperAgent", prompt_text)
                logger.info("[DeveloperAgent] Dynamic prompt system enabled")
            else:
                logger.warning("[DeveloperAgent] Failed to load prompt file, using default")
                self.prompt_manager.register_static_prompt("DeveloperAgent", self._get_default_system_prompt())

    def _get_default_system_prompt(self) -> str:
        """Return default system prompt for DeveloperAgent (v4.0)."""
        return """You are the Developer Agent of HydroAgent (v4.0), an expert in hydrological model analysis and visualization.

Your tasks:
1. **Result Analysis**: Parse and interpret hydromodel outputs
   - Read calibration_results.json
   - Parse *_sceua.csv files
   - Calculate performance metrics (NSE, RMSE, etc.)
   - Compute improvement rates between iterations

2. **Boundary Effect Detection**: Identify optimization issues
   - Compare optimal parameters with param_range bounds
   - Detect when parameters hit upper/lower limits
   - Recommend range expansions or adjustments
   - Calculate convergence metrics

3. **🆕 Visualization** (v4.0): Generate publication-quality plots
   - Streamflow fit plots (observed vs simulated)
   - NSE convergence curves (for iterative calibration)
   - Parameter distribution plots (for stability validation)
   - Metrics comparison charts (for batch processing)
   - All plots saved at 300 DPI for publication use

4. **Analysis Reporting**: Provide clear recommendations
   - Assess model performance quality
   - Suggest calibration improvements
   - Identify data quality issues
   - Recommend next steps

Example analysis output:
{
    "nse": 0.75,
    "quality": "good",
    "convergence": "stable",
    "boundary_warnings": [
        "Parameter 'K' hit upper bound (1.0)",
        "Recommend expanding K range to [0, 1.5]"
    ],
    "recommendations": [
        "Increase rep from 500 to 1000",
        "Expand parameter search space for K"
    ],
    "plot_files": [
        "streamflow_fit_01013500_test.png",
        "parameter_distribution.png"
    ]
}

Note: Code generation功能已迁移到RunnerAgent (v4.0改进)
Always explain your analysis and provide actionable recommendations."""

    def _load_prompt_from_file(self, filename: str) -> Optional[str]:
        """
        Load prompt text from resources directory.

        Args:
            filename: Name of prompt file

        Returns:
            Prompt text or None if file not found
        """
        try:
            from pathlib import Path
            project_root = Path(__file__).parent.parent.parent
            prompt_file = project_root / "hydroagent" / "resources" / filename

            if prompt_file.exists():
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                logger.warning(f"[DeveloperAgent] Prompt file not found: {prompt_file}")
                return None
        except Exception as e:
            logger.error(f"[DeveloperAgent] Error loading prompt file: {str(e)}")
            return None

    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process results and optionally generate code.
        处理结果并可选地生成代码。

        Args:
            input_data: 可以是以下两种格式之一：
                1. RunnerAgent的输出（自动分析模式）:
                {
                    "success": True,
                    "mode": "calibrate"|"evaluate",
                    "result": {...},
                    "execution_log": {...}
                }

                2. 手动分析配置:
                {
                    "mode": "analyze"|"generate_code",
                    "result_dir": Path,
                    "workspace_dir": Path,
                    "task_description": str (for code gen)
                }

        Returns:
            Dict containing analysis or code generation result
        """
        # 检测输入类型：RunnerAgent输出 vs 手动配置
        # RunnerAgent输出特征：有"success"和"mode"字段
        if "success" in input_data and "mode" in input_data:
            # RunnerAgent输出 - 自动分析模式
            logger.info("[DeveloperAgent] 检测到RunnerAgent输出，进行结果分析")
            return self._analyze_runner_output(input_data)

        # 手动配置模式
        mode = input_data.get("mode", "analyze")
        result_dir = input_data.get("result_dir")
        workspace_dir = input_data.get("workspace_dir", self.workspace_dir)

        logger.info(f"[DeveloperAgent] 手动模式: {mode}")

        try:
            if mode == "analyze":
                result = self._analyze_results(result_dir)
            elif mode == "generate_code":
                if not self.enable_code_gen:
                    raise ValueError("Code generation is disabled")
                task_desc = input_data.get("task_description", "")
                result = self._generate_code(task_desc, workspace_dir)
            else:
                raise ValueError(f"Unknown mode: {mode}")

            return {
                "success": True,
                "result": result
            }

        except Exception as e:
            logger.error(f"[DeveloperAgent] Processing failed: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def _analyze_runner_output(self, runner_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析RunnerAgent的输出结果。
        Analyze RunnerAgent output.

        Args:
            runner_output: RunnerAgent的输出
                {
                    "success": True/False,
                    "mode": "calibrate"|"evaluate"|"simulate",
                    "result": {...},
                    "execution_log": {...}
                }

        Returns:
            分析结果 Analysis result
        """
        logger.info("[DeveloperAgent] 分析RunnerAgent输出...")

        if not runner_output.get("success"):
            logger.error("[DeveloperAgent] RunnerAgent执行失败")
            return {
                "success": False,
                "error": "RunnerAgent execution failed",
                "runner_error": runner_output.get("error")
            }

        mode = runner_output.get("mode", "unknown")
        result_data = runner_output.get("result", {})

        logger.info(f"[DeveloperAgent] 分析模式: {mode}")

        try:
            # 根据模式进行不同的分析
            if mode == "calibrate":
                analysis = self._analyze_calibration_result(result_data)
            elif mode == "evaluate":
                analysis = self._analyze_evaluation_result(result_data)
            elif mode == "simulate":
                analysis = self._analyze_simulation_result(result_data)
            elif mode == "custom_analysis":
                # ⭐ 处理自定义分析，触发代码生成
                analysis = self._handle_custom_analysis_and_generate_code(result_data)
            elif mode == "auto_iterative":
                # 🆕 v4.0: 处理自动迭代率定结果
                analysis = self._analyze_auto_iterative_result(result_data)
            else:
                analysis = {"warning": f"未知模式: {mode}"}

            # 添加执行日志摘要
            exec_log = runner_output.get("execution_log", {})
            if exec_log:
                analysis["execution_summary"] = self._summarize_execution_log(exec_log)

            return {
                "success": True,
                "mode": mode,
                "analysis": analysis,
                "timestamp": self._get_timestamp()
            }

        except Exception as e:
            logger.error(f"[DeveloperAgent] 分析失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "traceback": self._format_traceback()
            }

    def _analyze_calibration_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析率定结果。
        Analyze calibration result.

        Args:
            result: 率定结果数据

        Returns:
            详细分析
        """
        logger.info("[DeveloperAgent] 分析率定结果...")

        analysis = {
            "summary": {},
            "metrics": {},
            "parameters": {},
            "quality": "unknown",
            "recommendations": []
        }

        # Initialize quality with default value
        quality = "unknown"

        # 提取性能指标
        metrics = result.get("metrics", {})
        if metrics:
            analysis["metrics"] = metrics

            # 评估率定质量
            nse = metrics.get("NSE", 0)
            if nse > 0.75:
                quality = "优秀 (Excellent)"
            elif nse > 0.65:
                quality = "良好 (Good)"
            elif nse > 0.50:
                quality = "可接受 (Acceptable)"
            else:
                quality = "不满意 (Unsatisfactory)"

            analysis["quality"] = quality
            analysis["summary"]["nse"] = nse
            analysis["summary"]["quality_assessment"] = quality

        # 提取最优参数
        best_params = result.get("best_params", {})
        if best_params:
            analysis["parameters"] = best_params
            analysis["summary"]["param_count"] = len(best_params)

        # 生成建议
        recommendations = []
        if metrics.get("NSE", 0) < 0.65:
            recommendations.append("NSE较低，建议增加训练时期长度或调整参数范围")
        if metrics.get("PBIAS", 0) and abs(metrics.get("PBIAS", 0)) > 25:
            recommendations.append(f"PBIAS={metrics.get('PBIAS'):.2f}%偏高，模型存在系统性偏差")

        analysis["recommendations"] = recommendations

        logger.info(f"[DeveloperAgent] 率定质量: {quality}")
        return analysis

    def _analyze_evaluation_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析评估结果。
        Analyze evaluation result.

        Args:
            result: 评估结果数据

        Returns:
            详细分析
        """
        logger.info("[DeveloperAgent] 分析评估结果...")

        analysis = {
            "summary": {},
            "metrics": {},
            "performance": {},
            "quality": "unknown",
            "recommendations": []
        }

        # Initialize quality with default value
        quality = "unknown"

        # 提取性能指标
        metrics = result.get("metrics", result.get("performance", {}))
        if metrics:
            analysis["metrics"] = metrics
            analysis["performance"] = metrics

            # 评估性能
            nse = metrics.get("NSE", 0)
            if nse > 0.75:
                quality = "优秀 (Excellent)"
            elif nse > 0.65:
                quality = "良好 (Good)"
            elif nse > 0.50:
                quality = "可接受 (Acceptable)"
            else:
                quality = "不满意 (Unsatisfactory)"

            analysis["quality"] = quality
            analysis["summary"]["nse"] = nse
            analysis["summary"]["quality_assessment"] = quality

        logger.info(f"[DeveloperAgent] 评估质量: {quality}")
        return analysis

    def _analyze_simulation_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析模拟结果。
        Analyze simulation result.

        Args:
            result: 模拟结果数据

        Returns:
            详细分析
        """
        logger.info("[DeveloperAgent] 分析模拟结果...")

        analysis = {
            "summary": {},
            "status": result.get("status", "unknown")
        }

        # TODO: 添加更详细的模拟结果分析

        return analysis

    def _analyze_auto_iterative_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析自动迭代率定结果（v4.0新功能）。
        Analyze auto-iterative calibration result (v4.0 new feature).

        Args:
            result: 自动迭代率定结果
                {
                    "status": "converged" | "max_iterations_reached",
                    "converged": True/False,
                    "iteration_history": [
                        {"iteration": 1, "nse": 0.65, "metrics": {...}, ...},
                        ...
                    ],
                    "final_metrics": {...},
                    "final_params": {...},
                    "nse_threshold": 0.7,
                    "max_iterations": 10,
                    "total_iterations": 5,
                    "output_dir": Path
                }

        Returns:
            详细分析包括NSE收敛图
        """
        logger.info("[DeveloperAgent] 分析自动迭代率定结果...")

        analysis = {
            "summary": {},
            "convergence": {},
            "final_metrics": {},
            "final_params": {},
            "recommendations": [],
            "plot_files": []
        }

        # 1. 提取基本信息
        status = result.get("status", "unknown")
        converged = result.get("converged", False)
        iteration_history = result.get("iteration_history", [])
        nse_threshold = result.get("nse_threshold", 0.7)
        max_iterations = result.get("max_iterations", 10)
        total_iterations = result.get("total_iterations", 0)
        output_dir = result.get("output_dir", self.workspace_dir)

        analysis["summary"]["status"] = status
        analysis["summary"]["converged"] = converged
        analysis["summary"]["total_iterations"] = total_iterations
        analysis["summary"]["nse_threshold"] = nse_threshold

        # 2. 收敛性分析
        if iteration_history:
            nse_values = [h.get("nse", 0.0) for h in iteration_history]
            initial_nse = nse_values[0] if nse_values else 0.0
            final_nse = nse_values[-1] if nse_values else 0.0
            best_nse = max(nse_values) if nse_values else 0.0

            analysis["convergence"]["initial_nse"] = initial_nse
            analysis["convergence"]["final_nse"] = final_nse
            analysis["convergence"]["best_nse"] = best_nse
            analysis["convergence"]["improvement"] = final_nse - initial_nse
            analysis["convergence"]["improvement_rate"] = (
                (final_nse - initial_nse) / abs(initial_nse) * 100
                if initial_nse != 0 else 0.0
            )

            # 检测NSE趋势
            if len(nse_values) >= 3:
                recent_trend = nse_values[-1] - nse_values[-3]
                if recent_trend > 0.01:
                    analysis["convergence"]["trend"] = "improving"
                elif recent_trend < -0.01:
                    analysis["convergence"]["trend"] = "degrading"
                else:
                    analysis["convergence"]["trend"] = "stable"
            else:
                analysis["convergence"]["trend"] = "insufficient_data"

        # 3. 最终指标和参数
        final_metrics = result.get("final_metrics", {})
        final_params = result.get("final_params", {})

        analysis["final_metrics"] = final_metrics
        analysis["final_params"] = final_params

        # 评估最终质量
        final_nse = final_metrics.get("NSE", 0.0)
        if final_nse > 0.75:
            quality = "优秀 (Excellent)"
        elif final_nse > 0.65:
            quality = "良好 (Good)"
        elif final_nse > 0.50:
            quality = "可接受 (Acceptable)"
        else:
            quality = "不满意 (Unsatisfactory)"

        analysis["summary"]["quality"] = quality

        # 4. 生成NSE收敛图
        if iteration_history and output_dir:
            try:
                output_path = Path(output_dir)
                plot_file = self.plot_nse_convergence(
                    iteration_history=iteration_history,
                    nse_threshold=nse_threshold,
                    output_path=output_path
                )
                analysis["plot_files"].append(plot_file)
                logger.info(f"[DeveloperAgent] NSE收敛图已生成: {plot_file}")
            except Exception as e:
                logger.error(f"[DeveloperAgent] 生成NSE收敛图失败: {str(e)}")
                analysis["plot_error"] = str(e)

        # 5. 生成建议
        recommendations = []

        if converged:
            recommendations.append(
                f"✅ 成功收敛！在第 {total_iterations} 次迭代达到NSE阈值 {nse_threshold}"
            )
            if total_iterations >= max_iterations * 0.8:
                recommendations.append(
                    f"⚠️ 接近最大迭代次数（{total_iterations}/{max_iterations}），"
                    "建议增加max_iterations以探索更优解"
                )
        else:
            recommendations.append(
                f"❌ 未收敛，在 {total_iterations} 次迭代后NSE={final_nse:.3f}仍低于阈值{nse_threshold}"
            )

            # 根据趋势提供建议
            trend = analysis["convergence"].get("trend", "unknown")
            if trend == "improving":
                recommendations.append(
                    "💡 NSE仍在上升中，建议增加max_iterations继续优化"
                )
            elif trend == "stable":
                recommendations.append(
                    "💡 NSE趋于稳定，建议调整参数范围或算法参数（如增加ngs、rep）"
                )
            elif trend == "degrading":
                recommendations.append(
                    "⚠️ NSE呈下降趋势，可能陷入局部最优，建议重新初始化或调整算法"
                )

            # NSE阈值建议
            if final_nse > nse_threshold * 0.9:
                recommendations.append(
                    f"💡 NSE已接近阈值（{final_nse:.3f} vs {nse_threshold}），"
                    "可考虑适当降低阈值或再迭代几轮"
                )
            elif final_nse < nse_threshold * 0.7:
                recommendations.append(
                    "💡 NSE距离阈值较远，建议检查：\n"
                    "   - 参数范围是否合理\n"
                    "   - 训练数据质量\n"
                    "   - 模型适用性"
                )

        # 通用建议
        if final_nse < 0.65:
            recommendations.append(
                "💡 整体性能较低，建议：\n"
                "   - 延长训练时期\n"
                "   - 增加SCE-UA的rep和ngs参数\n"
                "   - 检查数据质量和完整性"
            )

        analysis["recommendations"] = recommendations

        logger.info(
            f"[DeveloperAgent] 自动迭代率定分析完成: "
            f"收敛={converged}, 迭代次数={total_iterations}, 最终NSE={final_nse:.3f}"
        )

        return analysis

    def _summarize_execution_log(self, exec_log: Dict[str, Any]) -> Dict[str, Any]:
        """
        总结执行日志。
        Summarize execution log.

        Args:
            exec_log: 执行日志

        Returns:
            日志摘要
        """
        stdout = exec_log.get("stdout", "")
        stderr = exec_log.get("stderr", "")

        summary = {
            "stdout_lines": len(stdout.split('\n')) if stdout else 0,
            "stderr_lines": len(stderr.split('\n')) if stderr else 0,
            "has_errors": bool(stderr and len(stderr.strip()) > 0)
        }

        return summary

    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _format_traceback(self) -> str:
        """格式化异常回溯"""
        import traceback
        return traceback.format_exc()

    def _analyze_results(self, result_dir: Path) -> Dict[str, Any]:
        """
        Analyze hydromodel results from directory.
        从目录分析 hydromodel 结果。

        Args:
            result_dir: Directory containing results

        Returns:
            Analysis result dictionary
        """
        logger.info(f"[DeveloperAgent] Analyzing results in {result_dir}")

        if not result_dir or not Path(result_dir).exists():
            logger.warning(f"Result directory not found: {result_dir}")
            return {"error": "Result directory not found"}

        result_dir = Path(result_dir)

        # Find result files
        json_files = list(result_dir.glob("**/calibration_results.json"))
        csv_files = list(result_dir.glob("**/*_sceua.csv"))

        logger.info(f"Found {len(json_files)} JSON files, {len(csv_files)} CSV files")

        analysis = {
            "summary": {},
            "boundary_warnings": [],
            "recommendations": [],
            "files_analyzed": []
        }

        # Analyze JSON results
        for json_file in json_files:
            try:
                json_analysis = self._analyze_json_result(json_file)
                analysis["summary"].update(json_analysis)
                analysis["files_analyzed"].append(str(json_file))
            except Exception as e:
                logger.error(f"Failed to analyze {json_file}: {str(e)}")

        # Analyze CSV files (SCE-UA convergence)
        for csv_file in csv_files:
            try:
                csv_analysis = self._analyze_csv_result(csv_file)
                analysis["boundary_warnings"].extend(csv_analysis.get("warnings", []))
                analysis["files_analyzed"].append(str(csv_file))
            except Exception as e:
                logger.error(f"Failed to analyze {csv_file}: {str(e)}")

        # Generate recommendations using LLM
        if analysis["boundary_warnings"]:
            recommendations = self._generate_recommendations(analysis)
            analysis["recommendations"] = recommendations

        logger.info(f"[DeveloperAgent] Analysis complete")
        return analysis

    def _analyze_json_result(self, json_path: Path) -> Dict[str, Any]:
        """
        Analyze calibration_results.json file.
        分析 calibration_results.json 文件。

        Args:
            json_path: Path to JSON file

        Returns:
            Analysis summary
        """
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Extract key metrics
        summary = {}

        # TODO: Implement detailed JSON parsing
        # - Extract NSE, RMSE values
        # - Get optimal parameters
        # - Calculate convergence metrics

        logger.info(f"[DeveloperAgent] Analyzed JSON: {json_path}")
        return summary

    def _analyze_csv_result(self, csv_path: Path) -> Dict[str, Any]:
        """
        Analyze SCE-UA CSV file for boundary effects.
        分析 SCE-UA CSV 文件以检测边界效应。

        Args:
            csv_path: Path to CSV file

        Returns:
            Analysis result with warnings
        """
        import pandas as pd

        df = pd.read_csv(csv_path)

        warnings = []

        # TODO: Implement boundary detection
        # - Read param_range.yaml
        # - Compare final parameters with bounds
        # - Detect if parameters are within 1% of boundaries
        # - Calculate convergence variance

        logger.info(f"[DeveloperAgent] Analyzed CSV: {csv_path}")

        return {
            "convergence_variance": 0.0,
            "warnings": warnings
        }

    def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """
        Generate actionable recommendations using LLM.
        使用 LLM 生成可操作的建议。

        Args:
            analysis: Analysis result

        Returns:
            List of recommendation strings
        """
        user_prompt = f"""Based on this analysis of hydromodel calibration results:

Boundary warnings:
{chr(10).join(analysis['boundary_warnings'])}

Summary:
{json.dumps(analysis['summary'], indent=2)}

Provide 3-5 actionable recommendations to improve the calibration:
1. Parameter range adjustments
2. Algorithm parameter tuning
3. Data preprocessing suggestions
4. Other optimization strategies

Format: Return a JSON array of recommendation strings."""

        try:
            response = self.llm.generate_json(
                system_prompt=self.system_prompt,
                user_prompt=user_prompt,
                temperature=0.5
            )

            if isinstance(response, dict) and "recommendations" in response:
                return response["recommendations"]
            elif isinstance(response, list):
                return response
            else:
                return []

        except Exception as e:
            logger.error(f"Failed to generate recommendations: {str(e)}")
            return ["Unable to generate recommendations"]

    # ========================================================================
    # 🚫 DEPRECATED (v4.0): Code generation methods moved to RunnerAgent
    # ========================================================================
    # The following methods have been removed in v4.0:
    # - _handle_custom_analysis_and_generate_code()
    # - _build_task_description()
    # - _generate_code()
    #
    # These functionalities are now handled by RunnerAgent with code_llm_interface.
    # DeveloperAgent now focuses on analysis, reporting, and visualization.
    # ========================================================================

    def _handle_custom_analysis_and_generate_code(self, result_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        🚫 DEPRECATED in v4.0: This method has been moved to RunnerAgent.

        Code generation functionality is now handled by RunnerAgent with code_llm_interface.
        DeveloperAgent now focuses on analysis, reporting, and visualization.

        Returns:
            Error message indicating method has been deprecated
        """
        logger.error("[DeveloperAgent] _handle_custom_analysis_and_generate_code() is DEPRECATED in v4.0")
        logger.error("[DeveloperAgent] Code generation has been moved to RunnerAgent")
        logger.error("[DeveloperAgent] Please configure RunnerAgent with code_llm_interface parameter")

        return {
            "status": "method_deprecated",
            "error": "Code generation has been moved to RunnerAgent in v4.0",
            "message": "请使用RunnerAgent的code_llm_interface参数进行代码生成",
            "migration_guide": "See CLAUDE.md v4.0 Architecture section for migration instructions"
        }

    # ========================================================================
    # 🆕 v4.0: Visualization Methods
    # ========================================================================

    def plot_streamflow_fit(
        self,
        obs_data: 'np.ndarray',
        sim_data: 'np.ndarray',
        dates: 'np.ndarray',
        basin_id: str,
        metrics: Dict[str, float],
        output_path: Path,
        period_type: str = "test"
    ) -> str:
        """
        绘制径流拟合图（观测值 vs 模拟值）。
        Plot streamflow fit (observed vs simulated).

        Args:
            obs_data: 观测流量数组
            sim_data: 模拟流量数组
            dates: 日期数组
            basin_id: 流域ID
            metrics: 性能指标字典（NSE, RMSE等）
            output_path: 输出目录路径
            period_type: 时期类型（train/test/iter1等）

        Returns:
            图片文件路径
        """
        try:
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
            import numpy as np

            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

            # 子图1：时间序列
            ax1.plot(dates, obs_data, label='Observed', color='black', linewidth=1)
            ax1.plot(dates, sim_data, label='Simulated', color='red', linewidth=1, alpha=0.7)
            ax1.set_ylabel('Streamflow (mm/day)', fontsize=12)
            ax1.legend(loc='upper right')
            ax1.grid(True, alpha=0.3)
            ax1.set_title(
                f'Basin {basin_id} - {period_type.capitalize()} Period',
                fontsize=14,
                fontweight='bold'
            )

            # 添加指标标注
            metrics_text = f"NSE = {metrics.get('NSE', 0):.3f}\nRMSE = {metrics.get('RMSE', 0):.3f}"
            ax1.text(
                0.02, 0.98, metrics_text,
                transform=ax1.transAxes,
                verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5)
            )

            # 子图2：散点图
            ax2.scatter(obs_data, sim_data, alpha=0.5, s=10)
            ax2.plot(
                [obs_data.min(), obs_data.max()],
                [obs_data.min(), obs_data.max()],
                'r--', linewidth=2, label='1:1 line'
            )
            ax2.set_xlabel('Observed Streamflow (mm/day)', fontsize=12)
            ax2.set_ylabel('Simulated Streamflow (mm/day)', fontsize=12)
            ax2.legend()
            ax2.grid(True, alpha=0.3)

            plt.tight_layout()

            # 保存高分辨率图片
            output_file = output_path / f"streamflow_fit_{basin_id}_{period_type}.png"
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()

            logger.info(f"[DeveloperAgent] Saved plot: {output_file}")
            return str(output_file)

        except Exception as e:
            logger.error(f"[DeveloperAgent] Failed to plot streamflow fit: {str(e)}", exc_info=True)
            raise

    def plot_nse_convergence(
        self,
        iteration_history: List[Dict],
        nse_threshold: float,
        output_path: Path
    ) -> str:
        """
        绘制NSE收敛曲线（自动迭代率定）。
        Plot NSE convergence curve (auto-iterative calibration).

        Args:
            iteration_history: 迭代历史列表
                [{"iteration": 1, "nse": 0.65, ...}, ...]
            nse_threshold: NSE达标阈值
            output_path: 输出目录路径

        Returns:
            图片文件路径
        """
        try:
            import matplotlib.pyplot as plt

            iterations = [h["iteration"] for h in iteration_history]
            nse_values = [h["nse"] for h in iteration_history]

            fig, ax = plt.subplots(figsize=(10, 6))

            # 绘制NSE曲线
            ax.plot(
                iterations, nse_values,
                marker='o', linewidth=2, markersize=8,
                color='blue', label='NSE'
            )

            # 绘制阈值线
            ax.axhline(
                y=nse_threshold,
                color='red', linestyle='--', linewidth=2,
                label=f'Threshold (NSE = {nse_threshold})'
            )

            # 标注最佳点
            best_idx = nse_values.index(max(nse_values))
            ax.scatter(
                iterations[best_idx], nse_values[best_idx],
                s=200, color='green', marker='*', zorder=5,
                label=f'Best NSE = {nse_values[best_idx]:.3f}'
            )

            ax.set_xlabel('Iteration', fontsize=12)
            ax.set_ylabel('NSE', fontsize=12)
            ax.set_title(
                'NSE Convergence during Auto-Iterative Calibration',
                fontsize=14,
                fontweight='bold'
            )
            ax.legend(loc='lower right', fontsize=10)
            ax.grid(True, alpha=0.3)

            plt.tight_layout()

            output_file = output_path / "nse_convergence.png"
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()

            logger.info(f"[DeveloperAgent] Saved NSE convergence plot: {output_file}")
            return str(output_file)

        except Exception as e:
            logger.error(f"[DeveloperAgent] Failed to plot NSE convergence: {str(e)}", exc_info=True)
            raise

    def plot_parameter_distribution(
        self,
        param_stats: Dict[str, Dict],
        output_path: Path
    ) -> str:
        """
        绘制参数分布图（稳定性验证）。
        Plot parameter distribution (stability validation).

        Args:
            param_stats: 参数统计字典
                {"x1": {"mean": 0.5, "std": 0.05, ...}, ...}
            output_path: 输出目录路径

        Returns:
            图片文件路径
        """
        try:
            import matplotlib.pyplot as plt

            param_names = list(param_stats.keys())
            means = [param_stats[p]["mean"] for p in param_names]
            stds = [param_stats[p]["std"] for p in param_names]

            fig, ax = plt.subplots(figsize=(10, 6))

            x_pos = range(len(param_names))
            ax.bar(x_pos, means, yerr=stds, capsize=5, alpha=0.7, color='steelblue')
            ax.set_xticks(x_pos)
            ax.set_xticklabels(param_names, fontsize=11)
            ax.set_ylabel('Parameter Value', fontsize=12)
            ax.set_title(
                'Parameter Distribution from Repeated Experiments',
                fontsize=14,
                fontweight='bold'
            )
            ax.grid(True, axis='y', alpha=0.3)

            plt.tight_layout()

            output_file = output_path / "parameter_distribution.png"
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()

            logger.info(f"[DeveloperAgent] Saved parameter distribution plot: {output_file}")
            return str(output_file)

        except Exception as e:
            logger.error(f"[DeveloperAgent] Failed to plot parameter distribution: {str(e)}", exc_info=True)
            raise

    def plot_metrics_comparison(
        self,
        results: List[Dict],
        output_path: Path,
        metric_names: List[str] = None
    ) -> str:
        """
        绘制性能指标对比图（批量处理）。
        Plot metrics comparison (batch processing).

        Args:
            results: 结果列表
                [{"basin_id": "01013500", "metrics": {...}}, ...]
            output_path: 输出目录路径
            metric_names: 要对比的指标名称列表（默认：NSE, RMSE, KGE）

        Returns:
            图片文件路径
        """
        try:
            import matplotlib.pyplot as plt
            import numpy as np

            if metric_names is None:
                metric_names = ["NSE", "RMSE", "KGE"]

            basin_ids = [r["basin_id"] for r in results]

            fig, axes = plt.subplots(1, len(metric_names), figsize=(15, 5))
            if len(metric_names) == 1:
                axes = [axes]

            for i, metric in enumerate(metric_names):
                values = [r["metrics"].get(metric, 0) for r in results]
                axes[i].bar(range(len(basin_ids)), values, color='steelblue', alpha=0.7)
                axes[i].set_xticks(range(len(basin_ids)))
                axes[i].set_xticklabels(basin_ids, rotation=45, ha='right', fontsize=9)
                axes[i].set_ylabel(metric, fontsize=11)
                axes[i].set_title(f'{metric} Comparison', fontsize=12, fontweight='bold')
                axes[i].grid(True, axis='y', alpha=0.3)

            plt.tight_layout()

            output_file = output_path / "metrics_comparison.png"
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()

            logger.info(f"[DeveloperAgent] Saved metrics comparison plot: {output_file}")
            return str(output_file)

        except Exception as e:
            logger.error(f"[DeveloperAgent] Failed to plot metrics comparison: {str(e)}", exc_info=True)
            raise

    def _load_streamflow_data(self, calibration_dir: str) -> tuple:
        """
        从率定目录加载流量数据。
        Load streamflow data from calibration directory.

        Args:
            calibration_dir: 率定结果目录路径

        Returns:
            (obs_data, sim_data, dates) - 观测值、模拟值、日期数组
        """
        try:
            import numpy as np
            import pandas as pd
            from pathlib import Path

            calib_path = Path(calibration_dir)

            # TODO: 实现数据加载逻辑
            # 可以从以下来源读取：
            # 1. NetCDF files: *.nc
            # 2. calibration_results.json
            # 3. CSV files: *_sceua.csv

            # Placeholder implementation
            logger.warning("[DeveloperAgent] _load_streamflow_data() is not fully implemented yet")
            logger.warning("[DeveloperAgent] Returning mock data for now")

            # Return mock data (for now)
            n_points = 365 * 5  # 5 years
            dates = pd.date_range('2000-01-01', periods=n_points, freq='D')
            obs_data = np.random.rand(n_points) * 10
            sim_data = obs_data + np.random.randn(n_points) * 0.5

            return obs_data, sim_data, dates.to_numpy()

        except Exception as e:
            logger.error(f"[DeveloperAgent] Failed to load streamflow data: {str(e)}", exc_info=True)
            raise

    # ========================================================================
    # Boundary Effect Detection and Parameter Analysis
    # ========================================================================

    def detect_boundary_effects(
        self,
        params: Dict[str, float],
        param_ranges: Dict[str, List[float]],
        threshold: float = 0.01
    ) -> List[str]:
        """
        Detect if parameters are hitting boundaries.
        检测参数是否触碰边界。

        Args:
            params: Optimized parameter values
            param_ranges: Parameter range definitions {param: [min, max]}
            threshold: Boundary proximity threshold (default 1%)

        Returns:
            List of warning messages
        """
        warnings = []

        for param_name, param_value in params.items():
            if param_name not in param_ranges:
                continue

            min_val, max_val = param_ranges[param_name]
            param_range = max_val - min_val

            # Check lower boundary
            if abs(param_value - min_val) < threshold * param_range:
                warnings.append(
                    f"Parameter '{param_name}' = {param_value:.4f} is close to lower bound {min_val}"
                )

            # Check upper boundary
            if abs(param_value - max_val) < threshold * param_range:
                warnings.append(
                    f"Parameter '{param_name}' = {param_value:.4f} is close to upper bound {max_val}"
                )

        return warnings
