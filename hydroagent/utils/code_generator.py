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
                # 🆕 v5.1: 重新生成，附带完整的stdout/stderr错误信息
                last_error = error_history[-1]
                enhanced_params = params.copy()
                enhanced_params["previous_error"] = last_error["error_message"]
                enhanced_params["error_analysis"] = last_error["analysis"]
                enhanced_params["retry_attempt"] = attempt
                # 🆕 传递实际的stdout和stderr给LLM
                enhanced_params["previous_stdout"] = last_error.get("stdout", "")
                enhanced_params["previous_stderr"] = last_error.get("stderr", "")

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
            # Extract calibration_dir from params to pass to generated code
            calibration_dir = params.get("calibration_dir") or params.get("output_dir")

            exec_result = execute_generated_code(
                code_file=code_file,
                workspace_dir=workspace_dir,
                calibration_dir=calibration_dir,
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

            # 🆕 v5.1: 保存完整的stdout和stderr用于LLM反馈
            error_history.append({
                "attempt": attempt,
                "error_message": error_msg,
                "analysis": error_analysis,
                "code_file": code_file,
                "stdout": exec_result.get("stdout", ""),  # 🆕 捕获标准输出
                "stderr": exec_result.get("stderr", ""),  # 🆕 捕获错误输出
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
    import textwrap

    code = response

    # 提取代码块
    if "```python" in code:
        code = code.split("```python")[1].split("```")[0].strip()
    elif "```" in code:
        code = code.split("```")[1].split("```")[0].strip()

    # ✅ FIX: Use textwrap.dedent to remove common leading whitespace
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
    调用Code LLM生成分析代码（优先使用模板）。
    Call Code LLM to generate analysis code (template-based first, LLM fallback).

    🆕 v5.1: 批量任务强制使用LLM生成代码（模板不支持循环处理）

    Args:
        code_llm: Code LLM接口实例
        analysis_type: 分析类型（runoff_coefficient, FDC等）
        params: 参数字典
        prompt: 代码生成提示词
        project_root: 项目根目录（用于保存生成的代码）

    Returns:
        生成结果 {"code_file": str, "code": str} 或 {"error": str}
    """
    # 🆕 v5.1: 检测是否是批量任务
    basin_ids = params.get("basin_ids")
    is_batch_task = isinstance(basin_ids, list) and len(basin_ids) > 1

    if is_batch_task:
        logger.info(f"[CodeGenerator] 检测到批量任务（{len(basin_ids)}个流域），使用LLM生成代码（模板不支持批量）")
        # 跳过模板，直接使用LLM
        # 继续执行到PRIORITY 2部分
    else:
        # ✅ PRIORITY 1: Try template-based generation first (100% reliability)
        template_manager = TemplateManager()

        if template_manager.has_template(analysis_type):
            logger.info(f"[CodeGenerator] ✓ Template found for '{analysis_type}', using template-based generation")

            try:
                # Debug: log params (filter out large fields like calibration progress)
                filtered_params = {
                    k: v for k, v in params.items()
                    if k not in ["calibration_output", "evaluation_output", "previous_results"]
                }
                logger.info(f"[CodeGenerator] Params keys: {list(params.keys())}")
                logger.debug(f"[CodeGenerator] Filtered params: {filtered_params}")

                # ⭐ CRITICAL FIX: Extract nc_file_path from previous_results if available
                nc_file_path = params.get("output_dir_path") or params.get("nc_file_path", "")

                # If nc_file_path is empty, try to extract from previous_results
                if not nc_file_path:
                    previous_results = params.get("previous_results", [])
                    if previous_results:
                        logger.info(f"[CodeGenerator] Extracting nc_file_path from {len(previous_results)} previous results...")

                        # ⭐ CRITICAL FIX: Find the most recent calibration/evaluation task result
                        # Skip analysis/code_generation tasks as they don't produce .nc files
                        for result in reversed(previous_results):
                            result_data = result.get("result", {})

                            # ⭐ Skip analysis tasks - they don't produce .nc files
                            # Check multiple indicators:
                            # 1. analysis_type field (present in custom_analysis results)
                            # 2. generated_code_path field (present in code generation results)
                            # 3. status field with "success" but no calibration-specific fields
                            if result_data.get("analysis_type") or result_data.get("generated_code_path"):
                                task_id = result.get("task_id", "unknown")
                                logger.debug(f"[CodeGenerator] Skipping analysis task {task_id} (no .nc files expected)")
                                continue

                            # Try to get output_dir from result
                            output_dir_candidate = result_data.get("output_dir") or result_data.get("calibration_dir")

                            if output_dir_candidate:
                                # ⭐ Verify the directory actually contains .nc files before using it
                                path_obj = Path(output_dir_candidate)
                                if path_obj.exists() and path_obj.is_dir():
                                    nc_files_found = list(path_obj.glob("*.nc"))
                                    if nc_files_found:
                                        logger.info(f"[CodeGenerator] ✓ Found .nc files in {output_dir_candidate}")
                                        nc_file_path = output_dir_candidate
                                        break
                                    else:
                                        logger.debug(f"[CodeGenerator] Skipping {output_dir_candidate} (no .nc files found)")
                                        continue
                                else:
                                    logger.debug(f"[CodeGenerator] Skipping {output_dir_candidate} (directory doesn't exist)")
                                    continue

                            # Alternatively, scan for .nc files in result
                            nc_files = result_data.get("nc_files", [])
                            if nc_files:
                                logger.info(f"[CodeGenerator] Found nc_files from previous result: {nc_files[0]}")
                                nc_file_path = str(nc_files[0])
                                break

                        if nc_file_path:
                            logger.info(f"[CodeGenerator] ✓ Extracted nc_file_path from previous_results: {nc_file_path}")
                        else:
                            logger.warning("[CodeGenerator] ⚠ No nc_file_path found in previous_results")

                basin_id = params.get("basin_id", "unknown")
                output_dir = params.get("output_dir", "results")

                logger.info(f"[CodeGenerator] Extracted: nc_file_path='{nc_file_path}', basin_id='{basin_id}', output_dir='{output_dir}'")

                # Support both .nc file and directory paths
                if nc_file_path and not nc_file_path.endswith('.nc'):
                    # It's a directory, find the .nc file
                    path_obj = Path(nc_file_path)  # Use unique variable name to avoid scope issues
                    if path_obj.exists() and path_obj.is_dir():
                        nc_files = list(path_obj.glob("*.nc"))
                        if nc_files:
                            nc_file_path = str(nc_files[0])
                            logger.info(f"[CodeGenerator] Found .nc file: {nc_file_path}")
                        else:
                            logger.warning(f"[CodeGenerator] No .nc file found in {nc_file_path}")

                placeholders = extract_placeholders(nc_file_path, basin_id, output_dir)

                # Generate code from template
                code = template_manager.generate_code(analysis_type, placeholders)

                if code:
                    logger.info(f"[CodeGenerator] ✓ Template-based code generated successfully ({len(code)} chars)")

                    # Save code to file
                    proj_root = project_root
                    if proj_root is None:
                        proj_root = Path(__file__).parent.parent.parent

                    generated_code_dir = proj_root / "generated_code"
                    generated_code_dir.mkdir(exist_ok=True)

                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    code_file = generated_code_dir / f"{analysis_type}_analysis_{timestamp}.py"
                    code_file.write_text(code, encoding="utf-8")

                    logger.info(f"[CodeGenerator] ✓ Template-based code saved to: {code_file}")

                    return {"code_file": str(code_file), "code": code, "generation_method": "template"}

            except Exception as e:
                logger.warning(f"[CodeGenerator] Template-based generation failed: {e}, falling back to LLM")
                import traceback
                logger.warning(f"[CodeGenerator] Exception traceback: {traceback.format_exc()}")

    # ✅ FALLBACK: LLM-based generation if no template or template failed
    if not code_llm:
        return {"error": "Code LLM not configured and no template available"}

    try:
        # 🆕 v5.1: 增强的system prompt - Windows路径 + 批量任务支持
        enhanced_system_prompt = """你是一个专业的Python代码生成专家，专注于水文数据分析和可视化。

**关键要求**:
1. **Windows路径处理**: 所有文件路径必须使用原始字符串 r"..." 或双反斜杠 \\\\ 避免转义错误
   - 正确: r"D:\\project\\data.nc" 或 "D:\\\\project\\\\data.nc"
   - 错误: "D:\\project\\data.nc" (会导致 \\x 转义错误)

2. **简洁实用**: 生成代码应该简洁高效
   - **不要**定义复杂的类（除非必须）
   - **优先**使用函数式编程
   - **避免**过度封装和抽象
   - 代码长度控制在**100-150行**以内

3. **参数化处理**:
   - **必须使用命令行参数或sys.argv读取关键路径**，不要硬编码路径
   - 示例：
   ```python
   import sys
   workspace_dir = sys.argv[1] if len(sys.argv) > 1 else "."
   ```
   - **绝对不允许**硬编码如 `r"D:\\project\\calibration_results"` 这样的路径

4. **批量任务处理**: 如果是多个流域，使用简单循环
   ```python
   for basin_id in basins:
       process_basin(basin_id)
   ```

5. **NetCDF时间序列处理（重要！）**:
   ```python
   import xarray as xr
   import pandas as pd

   # 正确的时间处理方式
   ds = xr.open_dataset(nc_file)
   time_var = ds['time']

   # ✅ 方法1：直接使用xarray的时间索引
   time_index = pd.to_datetime(time_var.values)

   # ✅ 方法2：转换为pandas DatetimeIndex
   time_index = pd.DatetimeIndex(time_var.values)

   # ❌ 错误：numpy.datetime64没有strftime方法
   # time_index = [t.strftime() for t in time_var]  # 会报错！
   ```

6. **数据读取最佳实践**:
   ```python
   import xarray as xr

   # 读取NetCDF时检查变量名
   ds = xr.open_dataset(nc_file)
   print(f"可用变量: {list(ds.variables.keys())}")

   # hydromodel常用变量名：qobs(观测), qsim(模拟), prcp(降水), pet(蒸发)
   # 不要假设变量名，先检查再使用
   ```

7. **代码规范**:
   - 基本类型提示（不要过度使用）
   - 关键位置的错误处理（try-except）
   - 包含 if __name__ == "__main__": 入口
   - 使用 pathlib.Path 处理路径

8. **输出管理**:
   - 使用 print() 输出关键信息（不要过度）
   - 保存结果到CSV文件
   - 生成可视化图表（PNG格式）

**只返回纯Python代码，不要markdown标记，不要额外说明。代码要简洁实用，避免过度工程化。**
"""

        # 🆕 v5.1: 检测并增强user prompt（批量任务）
        if is_batch_task:
            # 批量任务：提取所有流域的nc文件路径
            basin_ids_list = basin_ids
            previous_results = params.get("previous_results", [])

            # 为每个流域找到对应的nc文件
            nc_files_map = {}
            for result in previous_results:
                result_data = result.get("result", {})
                # 跳过analysis任务
                if result_data.get("analysis_type") or result_data.get("generated_code_path"):
                    continue

                output_dir = result_data.get("output_dir") or result_data.get("calibration_dir")
                if output_dir:
                    path_obj = Path(output_dir)
                    if path_obj.exists():
                        nc_files = list(path_obj.glob("*.nc"))
                        if nc_files:
                            # 尝试从路径推断basin_id
                            for basin in basin_ids_list:
                                if basin in str(output_dir):
                                    nc_files_map[basin] = str(nc_files[0])
                                    break

            enhanced_user_prompt = f"""请生成代码来批量处理 {len(basin_ids_list)} 个流域的{analysis_type}分析。

**流域列表**: {basin_ids_list}

**数据文件** (每个流域对应一个.nc文件):
{chr(10).join([f'  - {basin}: r"{nc_files_map.get(basin, "待查找")}"' for basin in basin_ids_list])}

**输出目录**: results

**任务要求**:
1. 循环处理所有流域
2. 为每个流域生成独立的结果文件（CSV + PNG图表）
3. 生成汇总CSV文件包含所有流域的结果
4. 生成对比可视化图表
5. 所有文件路径使用原始字符串 r"..." 格式

**代码结构建议**:
```python
# -*- coding: utf-8 -*-
import pandas as pd
from pathlib import Path

def process_basin(basin_id: str, nc_file: str, output_dir: str):
    \"\"\"处理单个流域\"\"\"
    # TODO: 具体处理逻辑
    return {{'basin_id': basin_id, 'result': value}}

def main():
    basins = {basin_ids_list}
    nc_files = [...]  # 使用r"..."格式

    results = []
    for basin_id, nc_file in zip(basins, nc_files):
        try:
            result = process_basin(basin_id, nc_file, "results")
            results.append(result)
        except Exception as e:
            print(f"[ERROR] 流域 {{basin_id}} 失败: {{e}}")

    # 汇总
    df = pd.DataFrame(results)
    df.to_csv("batch_summary.csv", index=False)
    print(f"[OK] 批量处理完成，共 {{len(results)}} 个流域")

if __name__ == "__main__":
    main()
```

只返回完整可执行的Python代码。
"""
        else:
            # 单流域任务：使用原始prompt
            enhanced_user_prompt = prompt

        # 使用Code LLM生成代码
        logger.info(f"[CodeGenerator] Using LLM-based generation: {code_llm.model_name}")
        logger.info(f"[CodeGenerator] Batch task: {is_batch_task}, Basin count: {len(basin_ids) if is_batch_task else 1}")

        response = code_llm.generate(
            system_prompt=enhanced_system_prompt,
            user_prompt=enhanced_user_prompt,
            temperature=0.1,  # 低温度确保代码准确性
            max_tokens=3000,  # 增加token限制以支持更复杂的批量代码
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

        return {"code_file": str(code_file), "code": code, "generation_method": "llm"}

    except Exception as e:
        logger.error(f"[CodeGenerator] Code generation failed: {str(e)}", exc_info=True)
        return {"error": str(e)}


def execute_generated_code(
    code_file: str,
    workspace_dir: Optional[Path] = None,
    calibration_dir: Optional[str] = None,
    timeout: int = 300
) -> Dict[str, Any]:
    """
    执行生成的代码。
    Execute generated code.

    Args:
        code_file: 代码文件路径
        workspace_dir: 工作目录（可选）
        calibration_dir: 率定结果目录（传递给生成的代码作为sys.argv[1]）
        timeout: 超时时间（秒）

    Returns:
        执行结果
    """
    logger.info(f"[CodeGenerator] Executing code: {code_file}")
    if calibration_dir:
        logger.info(f"[CodeGenerator] Passing calibration_dir as argument: {calibration_dir}")

    try:
        # 构建命令：传递calibration_dir作为第一个参数
        cmd = [sys.executable, code_file]
        if calibration_dir:
            cmd.append(calibration_dir)

        # 使用subprocess执行代码
        result = subprocess.run(
            cmd,
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
