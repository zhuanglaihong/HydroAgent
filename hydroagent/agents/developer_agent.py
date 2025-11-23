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
    Developer agent for advanced analysis and code generation.
    开发者智能体 - 高级分析和代码生成。

    Similar to OpenFOAMGPT's Post-processing Agent, but more capable.

    Responsibilities:
    - Result analysis: Parse results/ directory (JSON, CSV)
    - Calculate NSE improvement rate (for Experiment 2)
    - Detect boundary effects in parameter optimization
    - Code generation: Write Python scripts for unsupported features
    - Tool execution: Run generated code in sandbox environment
    - Visualization: Generate custom plots and charts
    """

    def __init__(
        self,
        llm_interface: LLMInterface,
        workspace_dir: Optional[Path] = None,
        enable_code_gen: bool = True,
        use_dynamic_prompt: bool = True,
        code_llm_interface: Optional[LLMInterface] = None,
        **kwargs
    ):
        """
        Initialize DeveloperAgent.

        Args:
            llm_interface: LLM API interface for general tasks (思考、分析)
            workspace_dir: Working directory
            enable_code_gen: Enable code generation capability
            use_dynamic_prompt: Use dynamic prompt management system
            code_llm_interface: Optional LLM interface for code generation (代码生成专用)
                If provided, will use this for code generation tasks
                Examples: qwen-coder-turbo, deepseek-coder:6.7b
            **kwargs: Additional configuration
        """
        super().__init__(
            name="DeveloperAgent",
            llm_interface=llm_interface,
            workspace_dir=workspace_dir,
            **kwargs
        )

        self.enable_code_gen = enable_code_gen
        self.use_dynamic_prompt = use_dynamic_prompt

        # 🆕 代码专用LLM（如果提供）
        self.code_llm = code_llm_interface if code_llm_interface else llm_interface
        if code_llm_interface:
            logger.info(f"[DeveloperAgent] 使用专用代码模型: {code_llm_interface.model_name}")
        else:
            logger.info(f"[DeveloperAgent] 使用通用模型进行代码生成: {llm_interface.model_name}")

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
        """Return default system prompt for DeveloperAgent."""
        return """You are the Developer Agent of HydroAgent, the most advanced agent with coding capabilities.

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

3. **Code Generation** (Experiment 3): Create custom Python scripts
   - For features not in hydromodel
   - Custom analysis workflows
   - Data preprocessing scripts
   - Visualization code

4. **Tool Execution**: Run generated code safely
   - Execute in sandbox environment
   - Capture outputs and errors
   - Return results to user

5. **Visualization**: Create custom plots
   - Parameter convergence plots
   - Performance comparison charts
   - Spatial/temporal analysis figures

Example analysis output:
{
    "nse": 0.75,
    "convergence": "good",
    "boundary_warnings": [
        "Parameter 'K' hit upper bound (1.0)",
        "Recommend expanding K range to [0, 1.5]"
    ],
    "recommendations": [
        "Increase rep from 5 to 10",
        "Expand parameter search space"
    ]
}

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

    def _generate_code(self, task_description: str, workspace_dir: Path) -> Dict[str, Any]:
        """
        Generate Python code for custom tasks (Experiment 4).
        为自定义任务生成 Python 代码（实验4）。

        Args:
            task_description: Description of what code should do
            workspace_dir: Where to save generated code

        Returns:
            Code generation result
        """
        logger.info(f"[DeveloperAgent] 生成代码任务: {task_description}")
        logger.info(f"[DeveloperAgent] 使用代码模型: {self.code_llm.model_name}")

        system_prompt = """你是一个专业的Python代码生成助手，擅长编写水文数据分析和可视化代码。

你的任务：
1. 生成完整可运行的Python脚本
2. 使用hydromodel、hydrodataset、pandas、numpy、matplotlib等常用库
3. 包含详细的注释和错误处理
4. 生成的图表要清晰美观
5. 将结果保存到文件

代码风格：
- 使用type hints
- 遵循PEP 8规范
- 添加docstring
- 包含进度提示

输出格式：
只返回Python代码，不要包含任何解释文字。代码应该直接可以执行。"""

        user_prompt = f"""请为以下任务生成Python代码：

任务描述：{task_description}

常见任务参考：
- 计算径流系数：Runoff Coefficient = Total Runoff / Total Precipitation
- 绘制流量历时曲线（FDC）：对流量数据排序，计算累积频率，绘制图表
- 分析水文指标：使用hydromodel或pandas计算各种统计指标

生成的代码应该：
1. 从calibration_results.json或NetCDF文件读取数据
2. 进行必要的计算和分析
3. 生成可视化图表（如果需要）
4. 将结果保存为CSV或图片文件
5. 打印清晰的进度和结果信息

请生成完整的Python代码："""

        try:
            # 🆕 使用代码专用LLM
            code = self.code_llm.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.1,  # 代码生成使用低温度以确保准确性
                max_tokens=2000
            )

            # Extract code from response (remove markdown formatting if present)
            if "```python" in code:
                code = code.split("```python")[1].split("```")[0].strip()
            elif "```" in code:
                code = code.split("```")[1].split("```")[0].strip()

            # Save code to file
            code_file = workspace_dir / "generated_script.py"
            code_file.write_text(code, encoding='utf-8')

            logger.info(f"[DeveloperAgent] Code saved to: {code_file}")

            return {
                "code": code,
                "code_file": str(code_file),
                "execution_ready": True
            }

        except Exception as e:
            logger.error(f"Code generation failed: {str(e)}")
            return {
                "error": str(e),
                "execution_ready": False
            }

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
