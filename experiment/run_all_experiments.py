"""
Author: Claude
Date: 2025-12-21 19:20:00
LastEditTime: 2025-12-21 19:20:00
LastEditors: Claude
Description: 托管脚本 - 顺序运行所有4个核心实验
             Supervisor script to run all 4 core experiments sequentially
FilePath: /HydroAgent/experiment/run_all_experiments.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import argparse
import logging
import subprocess
import time
from datetime import datetime


def setup_logging():
    """设置日志系统"""
    logs_dir = project_root / "logs"
    logs_dir.mkdir(exist_ok=True)

    log_file = logs_dir / f"run_all_experiments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding='utf-8')
        ]
    )

    return logging.getLogger(__name__)


def run_experiment_with_timeout(exp_script, backend, mock, timeout_seconds=600):
    """
    运行单个实验，带超时控制

    Args:
        exp_script: 实验脚本路径
        backend: LLM后端 (api/ollama)
        mock: 是否使用mock模式
        timeout_seconds: 超时时间（秒），默认600秒（10分钟）

    Returns:
        dict: 执行结果 {success, elapsed_time, error_msg}
    """
    logger = logging.getLogger(__name__)

    logger.info(f"启动实验: {exp_script.name}")
    logger.info(f"  Backend: {backend}")
    logger.info(f"  Mock: {mock}")
    logger.info(f"  Timeout: {timeout_seconds}秒 ({timeout_seconds/60:.1f}分钟)")

    # 构建命令
    cmd = [sys.executable, str(exp_script), "--backend", backend]
    if mock:
        cmd.append("--mock")

    start_time = time.time()

    try:
        # 使用subprocess.run with timeout (不捕获输出，直接显示在终端)
        result = subprocess.run(
            cmd,
            timeout=timeout_seconds,
            # capture_output=False,  # 允许输出直接显示
            # 注释掉capture_output，让输出直接显示在终端
        )

        elapsed_time = time.time() - start_time

        # 检查返回码
        if result.returncode == 0:
            logger.info(f"[OK] 实验 {exp_script.name} 成功完成")
            logger.info(f"     执行时间: {elapsed_time:.1f}秒")
            return {
                "success": True,
                "elapsed_time": elapsed_time,
                "error_msg": None
            }
        else:
            logger.error(f"[FAIL] 实验 {exp_script.name} 执行失败 (返回码: {result.returncode})")
            return {
                "success": False,
                "elapsed_time": elapsed_time,
                "error_msg": f"Exit code {result.returncode}"
            }

    except subprocess.TimeoutExpired:
        elapsed_time = time.time() - start_time
        logger.warning(f"[TIMEOUT] 实验 {exp_script.name} 超时 ({timeout_seconds}秒)")
        logger.warning(f"          已执行时间: {elapsed_time:.1f}秒，强制终止并继续下一个实验")
        return {
            "success": False,
            "elapsed_time": elapsed_time,
            "error_msg": f"Timeout after {timeout_seconds} seconds"
        }

    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"[FAIL] 实验 {exp_script.name} 执行异常: {str(e)}")
        return {
            "success": False,
            "elapsed_time": elapsed_time,
            "error_msg": str(e)
        }


def main():
    """主函数 - 运行所有实验"""
    parser = argparse.ArgumentParser(description="顺序运行所有4个核心实验（托管模式）")
    parser.add_argument("--backend", choices=["api", "ollama"], default="api",
                      help="LLM backend: api (default) or ollama")
    parser.add_argument("--mock", action="store_true",
                      help="Use mock mode (skip actual calibration)")
    parser.add_argument("--timeout", type=int, default=600,
                      help="Timeout per experiment in seconds (default: 600 = 10 minutes)")
    args = parser.parse_args()

    # 设置日志
    logger = setup_logging()

    logger.info("=" * 80)
    logger.info("HydroAgent 核心实验托管运行")
    logger.info("=" * 80)
    logger.info(f"Backend: {args.backend}")
    logger.info(f"Mock mode: {args.mock}")
    logger.info(f"Timeout per experiment: {args.timeout}秒 ({args.timeout/60:.1f}分钟)")
    logger.info("")

    # 定义实验列表
    experiments = [
        {
            "id": 1,
            "name": "基础任务处理能力",
            "script": project_root / "experiment" / "exp_1.py",
            "description": "验证系统对水文建模核心任务的支持完整性"
        },
        {
            "id": 2,
            "name": "多智能体协同能力",
            "script": project_root / "experiment" / "exp_2.py",
            "description": "验证5个智能体在复杂多步骤任务中的协同工作能力"
        },
        {
            "id": 3,
            "name": "鲁棒性与容错能力",
            "script": project_root / "experiment" / "exp_3.py",
            "description": "验证系统对异常输入和错误的处理能力"
        },
        {
            "id": 4,
            "name": "扩展性与实用性",
            "script": project_root / "experiment" / "exp_4.py",
            "description": "验证系统在实际应用场景中的扩展能力"
        }
    ]

    logger.info("实验列表:")
    for exp in experiments:
        logger.info(f"  实验{exp['id']}: {exp['name']}")
        logger.info(f"    {exp['description']}")
    logger.info("")

    # 运行所有实验
    results = []
    total_start_time = time.time()

    for i, exp in enumerate(experiments, 1):
        logger.info("=" * 80)
        logger.info(f"开始执行: 实验{exp['id']} - {exp['name']} ({i}/{len(experiments)})")
        logger.info("=" * 80)

        # 检查脚本是否存在
        if not exp["script"].exists():
            logger.error(f"[FAIL] 脚本不存在: {exp['script']}")
            results.append({
                "exp_id": exp['id'],
                "exp_name": exp['name'],
                "success": False,
                "elapsed_time": 0,
                "error_msg": "Script file not found"
            })
            continue

        # 运行实验
        result = run_experiment_with_timeout(
            exp_script=exp["script"],
            backend=args.backend,
            mock=args.mock,
            timeout_seconds=args.timeout
        )

        results.append({
            "exp_id": exp['id'],
            "exp_name": exp['name'],
            "success": result["success"],
            "elapsed_time": result["elapsed_time"],
            "error_msg": result["error_msg"]
        })

        logger.info("")

    # 计算总执行时间
    total_elapsed_time = time.time() - total_start_time

    # 汇总结果
    logger.info("=" * 80)
    logger.info("所有实验执行完毕 - 结果汇总")
    logger.info("=" * 80)

    total_experiments = len(results)
    success_count = sum(1 for r in results if r["success"])
    success_rate = success_count / total_experiments * 100 if total_experiments > 0 else 0

    logger.info(f"总实验数: {total_experiments}")
    logger.info(f"成功数: {success_count}")
    logger.info(f"失败数: {total_experiments - success_count}")
    logger.info(f"成功率: {success_rate:.1f}%")
    logger.info(f"总执行时间: {total_elapsed_time:.1f}秒 ({total_elapsed_time/60:.1f}分钟)")
    logger.info("")

    # 详细结果
    logger.info("详细结果:")
    for result in results:
        status = "[PASS]" if result["success"] else "[FAIL]"
        logger.info(f"{status} 实验{result['exp_id']}: {result['exp_name']}")
        logger.info(f"        执行时间: {result['elapsed_time']:.1f}秒")
        if result["error_msg"]:
            logger.info(f"        错误信息: {result['error_msg'][:100]}")

    logger.info("")
    logger.info("=" * 80)
    logger.info(f"实验托管运行完成，成功率: {success_rate:.1f}%")
    logger.info("=" * 80)

    # 保存汇总结果
    import json
    experiment_results_dir = project_root / "experiment_results"
    experiment_results_dir.mkdir(exist_ok=True)

    summary_file = experiment_results_dir / f"all_experiments_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump({
            "run_time": datetime.now().isoformat(),
            "backend": args.backend,
            "mock_mode": args.mock,
            "timeout_per_experiment": args.timeout,
            "total_experiments": total_experiments,
            "success_count": success_count,
            "success_rate": success_rate,
            "total_elapsed_time": total_elapsed_time,
            "results": results
        }, f, indent=2, ensure_ascii=False)

    logger.info(f"汇总结果已保存到: {summary_file}")

    # 返回状态码（所有实验成功则返回0，否则返回1）
    return 0 if success_count == total_experiments else 1


if __name__ == "__main__":
    sys.exit(main())
