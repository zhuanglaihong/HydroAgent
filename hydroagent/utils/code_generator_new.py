"""
Author: Claude
Date: 2025-01-28 01:00:00
LastEditTime: 2025-01-28 01:00:00
LastEditors: Claude
Description: Code generation utilities using LLM (v4.0 feature)
             代码生成工具 - 使用LLM生成水文分析代码
FilePath: /HydroAgent/hydroagent/utils/code_generator.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from .prompt_manager import build_code_generation_prompt
from .error_handler import analyze_execution_error
from .template_manager import TemplateManager, extract_placeholders

logger = logging.getLogger(__name__)

def generate_code_with_feedback(
        code_llm,
        workspace_dir,
        timeout,
        analysis_type: str,
        params: Dict[str, Any],
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        带错误反馈的代码生成（v4.0增强版）
        Code generation with error feedback loop.

        流程：
        1. 生成代码
        2. 尝试执行
        3. 如果失败，分析错误
        4. 根据错误类型决定：
           - 重新生成代码（附带错误信息）
           - 更新参数
           - 或放弃并返回错误
        5. 循环直到成功或达到最大重试次数

        Args:
            analysis_type: 分析类型
            params: 参数字典
            max_retries: 最大重试次数

        Returns:
            生成和执行结果
        """
        logger.info(f"[RunnerAgent] 开始代码生成（带错误反馈），最大重试{max_retries}次")

        error_history = []  # 记录错误历史

        for attempt in range(1, max_retries + 1):
            logger.info(f"[RunnerAgent] 尝试 {attempt}/{max_retries}")

            # 1. 生成代码（第一次用原始prompt，后续附带错误信息）
            if attempt == 1:
                # 初次生成
                prompt = build_code_generation_prompt(analysis_type, params)
                code_result = generate_analysis_code(
                    code_llm=code_llm,
                    analysis_type=analysis_type,
                    params=params,
                    prompt=prompt
                )
            else:
                # 重新生成，附带错误信息
                last_error = error_history[-1]
                enhanced_params = params.copy()
                enhanced_params["previous_error"] = last_error["error_message"]
                enhanced_params["error_analysis"] = last_error["analysis"]
                enhanced_params["retry_attempt"] = attempt

                prompt = build_code_generation_prompt(analysis_type, enhanced_params)
                code_result = generate_analysis_code(
                    code_llm=code_llm,
                    analysis_type=analysis_type,
                    params=enhanced_params,
                    prompt=prompt
                )

            if "error" in code_result:
                logger.error(f"[RunnerAgent] 代码生成失败: {code_result['error']}")
                return {
                    "status": "code_generation_failed",
                    "error": code_result["error"],
                    "attempt": attempt
                }

            code_file = code_result["code_file"]
            code_content = code_result["code"]

            # 2. 执行代码
            exec_result = execute_generated_code(
                code_file=code_file,
                workspace_dir=workspace_dir,
                timeout=timeout
            )

            # 3. 检查执行结果
            if exec_result.get("status") == "success":
                logger.info(f"[RunnerAgent] 代码执行成功（尝试{attempt}/{max_retries}次）")
                return {
                    "status": "success",
                    "code_file": code_file,
                    "code": code_content,
                    "execution_result": exec_result,
                    "attempts": attempt,
                    "error_history": error_history
                }

            # 4. 执行失败，分析错误
            error_msg = exec_result.get("error", "") or exec_result.get("stderr", "")
            logger.warning(f"[RunnerAgent] 代码执行失败（尝试{attempt}/{max_retries}次）")

            error_analysis = analyze_execution_error(
                error_message=error_msg,
                code_content=code_content,
                execution_context=params
            )

            error_history.append({
                "attempt": attempt,
                "error_message": error_msg,
                "analysis": error_analysis,
                "code_file": code_file
            })

            # 5. 决定是否继续重试
            if not error_analysis["needs_code_regeneration"] and not error_analysis["needs_config_update"]:
                # 不可恢复的错误，立即停止
                logger.error("[RunnerAgent] 检测到不可恢复的错误，停止重试")
                break

            logger.info(f"[RunnerAgent] 错误可能可修复，准备重试...")

        # 所有重试都失败
        logger.error(f"[RunnerAgent] 代码生成和执行在{max_retries}次尝试后仍然失败")
        return {
            "status": "failed_after_retries",
            "error": "代码执行在多次重试后仍然失败",
            "error_history": error_history,
            "attempts": max_retries,
            "last_error": error_history[-1] if error_history else {}
        }

def extract_code_from_markdown(response: str) -> str:
    """
    从LLM响应中提取代码（去除markdown格式）
    Extract code from LLM response (remove markdown formatting).

    Args:
        response: LLM的完整响应

    Returns:
        提取的纯代码字符串
    """
    import textwrap

    code = response

    # 提取代码块
    if "```python" in code:
        code = code.split("```python")[1].split("```")[0].strip()
    elif "```" in code:
        code = code.split("```")[1].split("```")[0].strip()

    # CRITICAL FIX: Use textwrap.dedent to remove common leading whitespace
    # This fixes indentation errors from LLM-generated code
    code = textwrap.dedent(code)

    return code


def generate_analysis_code(
    code_llm,
    analysis_type: str,
    params: Dict[str, Any],
    prompt: str,
    project_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    智能代码生成（模板优先，LLM兜底）
    Smart code generation (template first, LLM fallback).

    v2.0: 使用SmartCodeGenerator，支持通用LLM代码生成

    Args:
        code_llm: Code LLM接口实例
        analysis_type: 分析类型（runoff_coefficient, FDC等）
        params: 参数字典
        prompt: 代码生成提示词（保留用于向后兼容）
        project_root: 项目根目录（用于保存生成的代码）

    Returns:
        生成结果 {"code_file": str, "code": str} 或 {"error": str}
    """
    # v2.0: 使用SmartCodeGenerator（模板优先，LLM兜底）
    from .smart_code_generator import SmartCodeGenerator

    logger.info(f"[CodeGenerator] Using SmartCodeGenerator v2.0 for {analysis_type}")

    # Step 1: 准备参数（提取nc_file_path等）
    prepared_params = _prepare_params_for_code_generation(params, analysis_type)

    if "error" in prepared_params:
        return prepared_params

    # Step 2: 使用SmartCodeGenerator生成代码
    try:
        generator = SmartCodeGenerator(code_llm, templates_dir=None)

        result = generator.generate_code(
            analysis_type=analysis_type,
            params=prepared_params,
            use_template_if_exists=True
        )

        if "error" in result:
            return result

        # Step 3: 保存代码到文件
        code = result["code"]
        method = result["method"]

        if project_root is None:
            project_root = Path(__file__).parent.parent.parent

        generated_code_dir = project_root / "generated_code"
        generated_code_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        code_file = generated_code_dir / f"{analysis_type}_analysis_{timestamp}.py"
        code_file.write_text(code, encoding="utf-8")

        logger.info(f"[CodeGenerator] Code saved to: {code_file} (method: {method})")

        return {
            "code_file": str(code_file),
            "code": code,
            "generation_method": method
        }

    except Exception as e:
        logger.error(f"[CodeGenerator] SmartCodeGenerator failed: {e}", exc_info=True)
        return {"error": str(e)}


def _prepare_params_for_code_generation(params: Dict[str, Any], analysis_type: str) -> Dict[str, Any]:
    """
    准备代码生成所需的参数（提取nc_file_path等）

    Args:
        params: 原始参数
        analysis_type: 分析类型

    Returns:
        准备好的参数字典或错误
    """
    prepared = params.copy()

    # CRITICAL FIX: Extract nc_file_path from previous_results if available
    nc_file_path = prepared.get("output_dir_path") or prepared.get("nc_file_path", "")

    # If nc_file_path is empty, try to extract from previous_results
    if not nc_file_path:
        previous_results = prepared.get("previous_results", [])
        if previous_results:
            logger.info(f"[CodeGenerator] Extracting nc_file_path from {len(previous_results)} previous results...")

            # Find the most recent calibration/evaluation task result
            # CRITICAL FIX: Only use directories that actually contain .nc files
            for result in reversed(previous_results):
                result_data = result.get("result", {})

                # Skip code_generation tasks - they don't produce .nc files
                task_id = result.get("task_id", "")
                mode = result.get("mode", "")
                if mode == "custom_analysis" or mode == "code_generation":
                    logger.debug(f"[CodeGenerator] Skipping {task_id} (mode={mode}, no .nc files)")
                    continue

                # Try to get output_dir from result
                output_dir_candidate = result_data.get("output_dir") or result_data.get("calibration_dir")

                if output_dir_candidate:
                    # CRITICAL: Verify the directory actually contains .nc files
                    from pathlib import Path
                    path_obj = Path(output_dir_candidate)
                    if path_obj.exists() and path_obj.is_dir():
                        nc_files_found = list(path_obj.glob("*.nc"))
                        if nc_files_found:
                            logger.info(f"[CodeGenerator] Found output_dir with .nc file: {output_dir_candidate}")
                            nc_file_path = output_dir_candidate
                            break
                        else:
                            logger.debug(f"[CodeGenerator] Skipping {output_dir_candidate} (no .nc files)")
                    else:
                        logger.debug(f"[CodeGenerator] Skipping {output_dir_candidate} (not a directory)")

                # Alternatively, scan for .nc files in result
                nc_files = result_data.get("nc_files", [])
                if nc_files:
                    logger.info(f"[CodeGenerator] Found nc_files from previous result: {nc_files[0]}")
                    nc_file_path = str(nc_files[0])
                    break

            if nc_file_path:
                logger.info(f"[CodeGenerator] Extracted nc_file_path from previous_results: {nc_file_path}")
            else:
                logger.warning("[CodeGenerator] No nc_file_path found in previous_results")

    # Add extracted nc_file_path to prepared params
    prepared["nc_file_path"] = nc_file_path

    return prepared


def execute_generated_code(
    code_file: str, workspace_dir: Optional[Path] = None, timeout: int = 300
) -> Dict[str, Any]:
    """
    执行生成的代码
    Execute generated code.

    Args:
        code_file: 代码文件路径
        workspace_dir: 工作目录（可选）
        timeout: 超时时间（秒）

    Returns:
        执行结果
    """
    logger.info(f"[CodeGenerator] Executing code: {code_file}")

    try:
        # 使用subprocess执行代码
        result = subprocess.run(
            [sys.executable, code_file],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=workspace_dir,
        )

        if result.returncode == 0:
            logger.info("[CodeGenerator] Code execution successful")

            # 导入scan_output_files（避免循环导入）
            from .path_manager import scan_output_files

            return {
                "status": "success",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "output_files": scan_output_files(workspace_dir),
            }
        else:
            logger.error(
                f"[CodeGenerator] Code execution failed with return code {result.returncode}"
            )
            return {
                "status": "failed",
                "error": result.stderr,
                "stdout": result.stdout,
                "returncode": result.returncode,
            }

    except subprocess.TimeoutExpired:
        logger.error(f"[CodeGenerator] Code execution timeout ({timeout}s)")
        return {
            "status": "timeout",
            "error": f"Execution timeout after {timeout} seconds",
        }

    except Exception as e:
        logger.error(f"[CodeGenerator] Code execution error: {str(e)}", exc_info=True)
        return {"status": "error", "error": str(e)}

