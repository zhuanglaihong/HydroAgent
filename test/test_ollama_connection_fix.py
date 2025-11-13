r"""
Author: Claude Code
Date: 2025-10-12 18:00:00
LastEditTime: 2025-10-12 18:00:00
LastEditors: Claude Code
Description: 测试Ollama嵌入模型连接资源清理修复
FilePath: \HydroAgent\test\test_ollama_connection_fix.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import sys
from pathlib import Path
import subprocess
import time

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def run_check_script():
    """运行检查脚本并返回结果"""
    script_path = project_root / "script" / "check_ollama_status.py"

    print(f"\n{'='*80}")
    print(f"运行脚本: {script_path}")
    print(f"{'='*80}\n")

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=30,
            encoding='utf-8',
            errors='ignore'
        )

        print("STDOUT:")
        print(result.stdout)

        if result.stderr:
            print("\nSTDERR:")
            print(result.stderr)

        print(f"\n返回码: {result.returncode}")
        return result.returncode == 0

    except subprocess.TimeoutExpired:
        print("[ERROR] 脚本运行超时（30秒）")
        return False
    except Exception as e:
        print(f"[ERROR] 运行失败: {e}")
        return False

def main():
    print("=" * 80)
    print("测试 Ollama 嵌入模型连接资源清理修复")
    print("=" * 80)
    print("\n测试目标: 连续运行两次检查脚本，验证第二次不会卡住")
    print("\n" + "=" * 80)

    # 第一次运行
    print("\n【第一次运行】")
    success1 = run_check_script()

    # 等待一下
    print("\n\n" + "="*80)
    print("等待 2 秒后进行第二次运行...")
    print("="*80)
    time.sleep(2)

    # 第二次运行
    print("\n【第二次运行】")
    success2 = run_check_script()

    # 总结
    print("\n\n" + "="*80)
    print("测试结果总结")
    print("="*80)
    print(f"第一次运行: {'✓ 成功' if success1 else '✗ 失败'}")
    print(f"第二次运行: {'✓ 成功' if success2 else '✗ 失败'}")

    if success1 and success2:
        print("\n[SUCCESS] 修复成功！两次运行都正常完成")
    elif success1 and not success2:
        print("\n[FAILED] 第二次运行失败或超时，连接清理可能仍有问题")
    else:
        print("\n[FAILED] 第一次运行就失败了，请检查 Ollama 服务状态")

    print("="*80)

if __name__ == "__main__":
    main()
