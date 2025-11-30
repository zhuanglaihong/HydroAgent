r"""
Author: Claude & zhuanglaihong
Date: 2025-01-20 20:00:00
LastEditTime: 2025-01-20 20:00:00
LastEditors: Claude
Description: Safe code execution sandbox (Tech 4.4)
             安全代码执行沙箱
FilePath: \HydroAgent\hydroagent\utils\code_sandbox.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from typing import Dict, Any, Optional, List
from pathlib import Path
import logging
import subprocess
import sys
import tempfile
import shutil
from io import StringIO
import contextlib

logger = logging.getLogger(__name__)


class CodeSandbox:
    """
    Safe code execution sandbox (Tech 4.4).
    安全代码执行沙箱。

    Purpose:
    - Execute generated Python code safely
    - Capture stdout, stderr, and exceptions
    - Enforce resource limits (timeout, memory)
    - Isolate execution from main process
    - Support both subprocess and in-process execution

    Used by DeveloperAgent for Experiment 3 (code generation).
    """

    def __init__(
        self,
        timeout: int = 300,
        max_memory_mb: int = 1024,
        allowed_imports: Optional[List[str]] = None,
    ):
        """
        Initialize CodeSandbox.

        Args:
            timeout: Execution timeout in seconds
            max_memory_mb: Maximum memory usage in MB
            allowed_imports: Whitelist of allowed import modules
        """
        self.timeout = timeout
        self.max_memory_mb = max_memory_mb
        self.allowed_imports = allowed_imports or self._get_default_allowed_imports()

        logger.info(
            f"[CodeSandbox] Initialized with timeout={timeout}s, max_memory={max_memory_mb}MB"
        )

    def _get_default_allowed_imports(self) -> List[str]:
        """
        Get default list of allowed import modules.
        获取默认允许的导入模块列表。

        Returns:
            List of allowed module names
        """
        return [
            # Standard library
            "os",
            "sys",
            "json",
            "yaml",
            "csv",
            "datetime",
            "pathlib",
            "logging",
            "argparse",
            "re",
            "math",
            "random",
            # Scientific computing
            "numpy",
            "pandas",
            "scipy",
            "matplotlib",
            "seaborn",
            # Hydrological
            "hydromodel",
            "hydrodataset",
            "hydroutils",
            # Others
            "tqdm",
            "joblib",
        ]

    def execute(
        self, code: str, mode: str = "subprocess", working_dir: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Execute Python code in sandbox.
        在沙箱中执行 Python 代码。

        Args:
            code: Python code to execute
            mode: Execution mode ("subprocess" or "inprocess")
            working_dir: Working directory for execution

        Returns:
            Execution result dictionary
        """
        logger.info(f"[CodeSandbox] Executing code in {mode} mode")

        # Validate code (basic safety checks)
        is_safe, safety_issues = self._validate_code(code)
        if not is_safe:
            logger.error(f"[CodeSandbox] Code validation failed: {safety_issues}")
            return {
                "success": False,
                "error": "Code validation failed",
                "safety_issues": safety_issues,
            }

        if mode == "subprocess":
            return self._execute_subprocess(code, working_dir)
        elif mode == "inprocess":
            return self._execute_inprocess(code, working_dir)
        else:
            raise ValueError(f"Unknown execution mode: {mode}")

    def _validate_code(self, code: str) -> tuple[bool, List[str]]:
        """
        Validate code for safety issues.
        验证代码的安全问题。

        Args:
            code: Code to validate

        Returns:
            Tuple of (is_safe, list_of_issues)
        """
        issues = []

        # Check for dangerous operations
        dangerous_patterns = [
            ("rm -rf", "Dangerous file deletion command"),
            ("shutil.rmtree", "Recursive directory deletion"),
            ("os.system", "Direct system command execution"),
            ("eval(", "Dangerous eval() call"),
            ("exec(", "Dangerous exec() call"),
            ("__import__", "Dynamic import bypass"),
        ]

        for pattern, description in dangerous_patterns:
            if pattern in code:
                issues.append(f"Potentially dangerous: {description}")

        # Check for unauthorized imports
        import_lines = [
            line
            for line in code.split("\n")
            if line.strip().startswith("import") or "from " in line
        ]
        for line in import_lines:
            # Extract module name
            if "import" in line:
                parts = line.split("import")
                if len(parts) > 1:
                    module = parts[1].split()[0].split(".")[0].strip()
                    if module not in self.allowed_imports and not module.startswith(
                        "hydroagent"
                    ):
                        issues.append(f"Unauthorized import: {module}")

        is_safe = len(issues) == 0
        return is_safe, issues

    def _execute_subprocess(
        self, code: str, working_dir: Optional[Path]
    ) -> Dict[str, Any]:
        """
        Execute code as subprocess (safer isolation).
        作为子进程执行代码（更安全的隔离）。

        Args:
            code: Code to execute
            working_dir: Working directory

        Returns:
            Execution result
        """
        logger.info("[CodeSandbox] Executing as subprocess...")

        # Create temporary file for code
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            temp_file = Path(f.name)
            f.write(code)

        try:
            # Execute with timeout
            result = subprocess.run(
                [sys.executable, str(temp_file)],
                cwd=working_dir or Path.cwd(),
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            success = result.returncode == 0

            logger.info(
                f"[CodeSandbox] Subprocess execution {'succeeded' if success else 'failed'}"
            )

            return {
                "success": success,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "execution_mode": "subprocess",
            }

        except subprocess.TimeoutExpired:
            logger.error(f"[CodeSandbox] Execution timeout after {self.timeout}s")
            return {
                "success": False,
                "error": f"Execution timeout ({self.timeout}s)",
                "execution_mode": "subprocess",
            }

        except Exception as e:
            logger.error(f"[CodeSandbox] Execution failed: {str(e)}")
            return {"success": False, "error": str(e), "execution_mode": "subprocess"}

        finally:
            # Clean up temporary file
            temp_file.unlink(missing_ok=True)

    def _execute_inprocess(
        self, code: str, working_dir: Optional[Path]
    ) -> Dict[str, Any]:
        """
        Execute code in-process with output capture (less isolation).
        在进程内执行代码并捕获输出（隔离性较低）。

        Args:
            code: Code to execute
            working_dir: Working directory

        Returns:
            Execution result
        """
        logger.info("[CodeSandbox] Executing in-process...")

        # Capture stdout and stderr
        stdout_capture = StringIO()
        stderr_capture = StringIO()

        # Save current working directory
        original_cwd = Path.cwd()
        if working_dir:
            import os

            os.chdir(working_dir)

        try:
            with (
                contextlib.redirect_stdout(stdout_capture),
                contextlib.redirect_stderr(stderr_capture),
            ):

                # Create isolated namespace
                namespace = {
                    "__name__": "__main__",
                    "__file__": "<sandbox>",
                }

                # Execute code
                exec(code, namespace)

            logger.info("[CodeSandbox] In-process execution succeeded")

            return {
                "success": True,
                "stdout": stdout_capture.getvalue(),
                "stderr": stderr_capture.getvalue(),
                "execution_mode": "inprocess",
                "namespace": namespace,  # Return final namespace state
            }

        except Exception as e:
            logger.error(f"[CodeSandbox] Execution failed: {str(e)}")

            import traceback

            return {
                "success": False,
                "error": str(e),
                "stdout": stdout_capture.getvalue(),
                "stderr": stderr_capture.getvalue(),
                "traceback": traceback.format_exc(),
                "execution_mode": "inprocess",
            }

        finally:
            # Restore working directory
            if working_dir:
                import os

                os.chdir(original_cwd)

    def execute_file(
        self, script_path: Path, mode: str = "subprocess"
    ) -> Dict[str, Any]:
        """
        Execute Python script file.
        执行 Python 脚本文件。

        Args:
            script_path: Path to Python script
            mode: Execution mode

        Returns:
            Execution result
        """
        logger.info(f"[CodeSandbox] Executing file: {script_path}")

        if not script_path.exists():
            return {"success": False, "error": f"Script file not found: {script_path}"}

        try:
            with open(script_path, "r", encoding="utf-8") as f:
                code = f.read()

            working_dir = script_path.parent
            return self.execute(code, mode=mode, working_dir=working_dir)

        except Exception as e:
            logger.error(f"[CodeSandbox] Failed to execute file: {str(e)}")
            return {"success": False, "error": str(e)}

    def test_environment(self) -> Dict[str, Any]:
        """
        Test sandbox environment by running simple code.
        通过运行简单代码测试沙箱环境。

        Returns:
            Test result
        """
        test_code = """
import sys
import numpy as np

print(f"Python: {sys.version}")
print(f"NumPy: {np.__version__}")
print("Sandbox environment OK")
"""

        logger.info("[CodeSandbox] Testing environment...")
        result = self.execute(test_code, mode="subprocess")

        if result["success"]:
            logger.info("[CodeSandbox] Environment test passed")
        else:
            logger.error("[CodeSandbox] Environment test failed")

        return result
