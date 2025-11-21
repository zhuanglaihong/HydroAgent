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
        **kwargs
    ):
        """
        Initialize DeveloperAgent.

        Args:
            llm_interface: LLM API interface
            workspace_dir: Working directory
            enable_code_gen: Enable code generation capability
            **kwargs: Additional configuration
        """
        super().__init__(
            name="DeveloperAgent",
            llm_interface=llm_interface,
            workspace_dir=workspace_dir,
            **kwargs
        )

        self.enable_code_gen = enable_code_gen

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

    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process results and optionally generate code.
        处理结果并可选地生成代码。

        Args:
            input_data: Analysis configuration
                {
                    "mode": "analyze"|"generate_code",
                    "result_dir": Path,
                    "workspace_dir": Path,
                    "task_description": str (for code gen)
                }

        Returns:
            Dict containing analysis or code generation result
        """
        mode = input_data.get("mode", "analyze")
        result_dir = input_data.get("result_dir")
        workspace_dir = input_data.get("workspace_dir", self.workspace_dir)

        logger.info(f"[DeveloperAgent] Mode: {mode}")

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
        Generate Python code for custom tasks (Experiment 3).
        为自定义任务生成 Python 代码（实验3）。

        Args:
            task_description: Description of what code should do
            workspace_dir: Where to save generated code

        Returns:
            Code generation result
        """
        logger.info(f"[DeveloperAgent] Generating code for: {task_description}")

        user_prompt = f"""Generate a complete Python script for this task:

Task: {task_description}

Requirements:
1. Use hydromodel API if applicable
2. Include proper error handling
3. Add comments explaining the code
4. Save results to files
5. Print progress messages

Return the complete Python code as a string."""

        try:
            code = self.call_llm(user_prompt, temperature=0.3)

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
