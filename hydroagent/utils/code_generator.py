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
        带错误反馈的代码生成（v4.0增强）。
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
                logger.info(f"[RunnerAgent] 代码执行成功（尝试 {attempt}/{max_retries}）")
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
            logger.warning(f"[RunnerAgent] 代码执行失败（尝试 {attempt}/{max_retries}）")

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
    从LLM响应中提取代码（去除markdown格式）。
    Extract code from LLM response (remove markdown formatting).

    Args:
        response: LLM的完整响应

    Returns:
        提取的纯代码字符串
    """
    code = response

    # 提取代码块
    if "```python" in code:
        code = code.split("```python")[1].split("```")[0].strip()
    elif "```" in code:
        code = code.split("```")[1].split("```")[0].strip()

    return code


def generate_analysis_code(
    code_llm,
    analysis_type: str,
    params: Dict[str, Any],
    prompt: str,
    project_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    调用Code LLM生成分析代码。
    Call Code LLM to generate analysis code.

    Args:
        code_llm: Code LLM接口实例
        analysis_type: 分析类型（runoff_coefficient, FDC等）
        params: 参数字典
        prompt: 代码生成提示词
        project_root: 项目根目录（用于保存生成的代码）

    Returns:
        生成结果 {"code_file": str, "code": str} 或 {"error": str}
    """
    if not code_llm:
        return {"error": "Code LLM not configured"}

    try:
        # 使用Code LLM生成代码
        logger.info(f"[CodeGenerator] 调用Code LLM: {code_llm.model_name}")
        response = code_llm.generate(
            system_prompt="你是一个专业的Python代码生成助手，擅长编写水文数据分析和可视化代码。",
            user_prompt=prompt,
            temperature=0.1,  # 低温度确保代码准确性
            max_tokens=2000,
        )

        # 提取代码
        code = extract_code_from_markdown(response)

        # 保存代码到文件（统一保存到项目 generated_code 目录）
        if project_root is None:
            # 默认使用当前文件的祖父目录的祖父目录（utils -> hydroagent -> HydroAgent）
            project_root = Path(__file__).parent.parent.parent

        generated_code_dir = project_root / "generated_code"
        generated_code_dir.mkdir(exist_ok=True)

        # 生成带时间戳的文件名，方便查看历史记录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        code_file = generated_code_dir / f"{analysis_type}_analysis_{timestamp}.py"
        code_file.write_text(code, encoding="utf-8")

        logger.info(f"[CodeGenerator] Generated code saved to: {code_file}")
        logger.info(
            f"[CodeGenerator] 💡 Code saved to project directory for easy inspection"
        )

        return {"code_file": str(code_file), "code": code}

    except Exception as e:
        logger.error(f"[CodeGenerator] Code generation failed: {str(e)}", exc_info=True)
        return {"error": str(e)}


def execute_generated_code(
    code_file: str, workspace_dir: Optional[Path] = None, timeout: int = 300
) -> Dict[str, Any]:
    """
    执行生成的代码。
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
