"""
Author: Claude
Date: 2025-01-22 21:30:00
LastEditTime: 2025-01-22 21:30:00
LastEditors: Claude
Description: 通用实验运行器 - 运行所有5个实验
             Universal Experiment Runner - Run all 5 experiments
FilePath: /HydroAgent/experiment/run_experiments.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import sys
from pathlib import Path
import json
import time
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set console encoding (Windows compatible)
import io

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

import logging
import argparse


# 实验配置
EXPERIMENTS = {
    "1": {
        "name": "标准流域验证",
        "query": "率定流域 01013500，使用标准 XAJ 模型",
        "expected_task_type": "standard_calibration",
        "expected_subtasks": 1,
        "success_criteria": {
            "task_type_match": True,
            "subtask_count": 1,
            "config_generated": True,
        },
    },
    "2a": {
        "name": "全信息率定",
        "query": "使用 SCE-UA 算法，设置 rep=500, ngs=100，率定 CAMELS_US 的 01013500 流域，时间 1990-2000",
        "expected_task_type": "standard_calibration",
        "expected_subtasks": 1,
        "success_criteria": {
            "task_type_match": True,
            "param_extraction": ["rep", "ngs"],
        },
    },
    "2b": {
        "name": "缺省信息补全",
        "query": "帮我率定流域 01013500",
        "expected_task_type": "info_completion",
        "expected_subtasks": 1,
        "success_criteria": {
            "task_type_match": True,
            "info_completed": ["model_name", "algorithm"],
        },
    },
    "2c": {
        "name": "自定义数据路径",
        "query": "用我 D 盘 my_data 文件夹里的数据跑一下模型",
        "expected_task_type": "custom_data",
        "expected_subtasks": 1,
        "success_criteria": {"task_type_match": True, "data_path_extracted": True},
    },
    "3": {
        "name": "参数自适应优化",
        "query": "率定流域 01013500，如果参数收敛到边界，自动调整范围重新率定",
        "expected_task_type": "iterative_optimization",
        "expected_subtasks": 2,
        "success_criteria": {
            "task_type_match": True,
            "subtask_count": 2,
            "has_dependencies": True,
        },
    },
    "4": {
        "name": "扩展分析",
        "query": "率定完成后，请帮我计算流域的径流系数，并画一张流路历时曲线 FDC",
        "expected_task_type": "extended_analysis",
        "expected_subtasks": 3,
        "success_criteria": {
            "task_type_match": True,
            "needs_extracted": ["runoff_coefficient", "FDC"],
            "subtask_count": 3,
        },
    },
    "5": {
        "name": "稳定性验证",
        "query": "重复率定流域 01013500 五次，使用不同随机种子",
        "expected_task_type": "repeated_experiment",
        "expected_subtasks": 6,  # 5 repeats + 1 statistical analysis
        "success_criteria": {
            "task_type_match": True,
            "n_repeats": 5,
            "subtask_count": 6,
        },
    },
}


def setup_logging(exp_id):
    """Setup logging for experiment."""
    logs_dir = project_root / "logs"
    logs_dir.mkdir(exist_ok=True)

    log_file = logs_dir / f"exp_{exp_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )

    return log_file


def run_experiment(exp_id, llm, use_mock=True):
    """
    运行指定实验

    Args:
        exp_id: 实验ID (1, 2a, 2b, 2c, 3, 4, 5)
        llm: LLM接口
        use_mock: 是否使用Mock模式

    Returns:
        实验结果字典
    """
    from hydroagent.agents.intent_agent import IntentAgent
    from hydroagent.agents.task_planner import TaskPlanner
    from hydroagent.agents.interpreter_agent import InterpreterAgent
    from hydroagent.core.prompt_pool import PromptPool

    if exp_id not in EXPERIMENTS:
        return {"success": False, "error": f"Unknown experiment: {exp_id}"}

    exp_config = EXPERIMENTS[exp_id]
    query = exp_config["query"]

    print("\n" + "=" * 70)
    print(f"【实验{exp_id.upper()}：{exp_config['name']}】")
    print("=" * 70)
    print(f"查询: {query}")
    print(f"预期任务类型: {exp_config['expected_task_type']}")
    print(f"预期子任务数: {exp_config['expected_subtasks']}")
    print()

    # 创建工作目录
    workspace_dir = (
        project_root
        / "experiment_results"
        / f"exp{exp_id}"
        / datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    workspace_dir.mkdir(parents=True, exist_ok=True)

    total_start = time.time()
    results = {
        "experiment_id": exp_id,
        "experiment_name": exp_config["name"],
        "query": query,
        "workspace": str(workspace_dir),
        "start_time": datetime.now().isoformat(),
        "validation": {},
    }

    # ========================================================================
    # Step 1: IntentAgent
    # ========================================================================
    print("🔍 [Step 1/3] IntentAgent...")
    intent_start = time.time()

    intent_agent = IntentAgent(llm_interface=llm)
    intent_result = intent_agent.process({"query": query})

    if not intent_result.get("success"):
        print(f"❌ Intent分析失败")
        results["success"] = False
        return results

    intent_data = intent_result["intent_result"]
    task_type = intent_data.get("task_type")

    print(f"✅ 完成 ({time.time() - intent_start:.1f}s)")
    print(f"   任务类型: {task_type}")

    # 验证task_type
    if task_type == exp_config["expected_task_type"]:
        print(f"   ✅ 任务类型匹配")
        results["validation"]["task_type"] = True
    else:
        print(f"   ⚠️  任务类型不匹配（预期: {exp_config['expected_task_type']}）")
        results["validation"]["task_type"] = False

    # 保存Intent结果
    with open(workspace_dir / "intent_result.json", "w", encoding="utf-8") as f:
        json.dump(intent_result, f, indent=2, ensure_ascii=False)

    # ========================================================================
    # Step 2: TaskPlanner
    # ========================================================================
    print("\n📋 [Step 2/3] TaskPlanner...")
    planner_start = time.time()

    prompt_pool = PromptPool(pool_dir=workspace_dir / "prompt_pool")
    task_planner = TaskPlanner(
        llm_interface=llm, prompt_pool=prompt_pool, workspace_dir=workspace_dir
    )

    planner_result = task_planner.process({"intent_result": intent_data})

    if not planner_result.get("success"):
        print(f"❌ 任务规划失败")
        results["success"] = False
        return results

    task_plan = planner_result["task_plan"]
    subtasks = task_plan["subtasks"]

    print(f"✅ 完成 ({time.time() - planner_start:.1f}s)")
    print(f"   子任务数量: {len(subtasks)}")

    # 验证子任务数量
    if len(subtasks) == exp_config["expected_subtasks"]:
        print(f"   ✅ 子任务数量匹配")
        results["validation"]["subtask_count"] = True
    else:
        print(f"   ⚠️  子任务数量不匹配（预期: {exp_config['expected_subtasks']}）")
        results["validation"]["subtask_count"] = False

    # 保存任务计划
    with open(workspace_dir / "task_plan.json", "w", encoding="utf-8") as f:
        json.dump(planner_result, f, indent=2, ensure_ascii=False)

    # ========================================================================
    # Step 3: InterpreterAgent
    # ========================================================================
    print("\n🔧 [Step 3/3] InterpreterAgent...")
    interpreter_start = time.time()

    interpreter = InterpreterAgent(llm_interface=llm, workspace_dir=workspace_dir)

    configs = []
    for i, subtask in enumerate(subtasks, 1):
        print(f"   [{i}/{len(subtasks)}] {subtask['task_id']}...")

        config_result = interpreter.process(
            {"subtask": subtask, "intent_result": intent_data}
        )

        if not config_result.get("success"):
            print(f"❌ 配置生成失败")
            results["success"] = False
            return results

        configs.append(config_result)

    print(f"✅ 完成 ({time.time() - interpreter_start:.1f}s)")

    # 验证配置生成
    results["validation"]["configs_generated"] = len(configs) == len(subtasks)

    # 保存配置
    for i, config_result in enumerate(configs, 1):
        with open(workspace_dir / f"config_{i}.json", "w", encoding="utf-8") as f:
            json.dump(config_result["config"], f, indent=2, ensure_ascii=False)

    # ========================================================================
    # 总结
    # ========================================================================
    total_elapsed = time.time() - total_start

    all_validations_passed = all(results["validation"].values())
    results["success"] = all_validations_passed
    results["end_time"] = datetime.now().isoformat()
    results["elapsed_time"] = total_elapsed

    print("\n" + "=" * 70)
    if all_validations_passed:
        print(f"✅ 实验{exp_id.upper()}通过!")
    else:
        print(f"⚠️  实验{exp_id.upper()}部分验证失败")

    print("=" * 70)
    print(f"\n验证结果:")
    for key, value in results["validation"].items():
        status = "✅" if value else "❌"
        print(f"  {status} {key}")

    print(f"\n总耗时: {total_elapsed:.1f}s")
    print(f"工作目录: {workspace_dir}")
    print("=" * 70)

    # 保存结果
    with open(workspace_dir / "experiment_result.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    return results


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="运行HydroAgent实验")
    parser.add_argument(
        "experiment",
        type=str,
        nargs="?",
        default="all",
        help="实验ID: 1, 2a, 2b, 2c, 3, 4, 5, all (default: all)",
    )
    parser.add_argument(
        "--backend",
        type=str,
        default="api",
        choices=["ollama", "api"],
        help="LLM backend (default: api)",
    )
    parser.add_argument("--model", type=str, default=None, help="Model name")
    parser.add_argument("--mock", action="store_true", help="Use mock mode")
    args = parser.parse_args()

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║           HydroAgent 实验运行器                             ║")
    print("╚══════════════════════════════════════════════════════════════╝\n")

    # Load config
    try:
        from configs import definitions_private as config
    except ImportError:
        from configs import definitions as config

    # Create LLM interface
    from hydroagent.core.llm_interface import create_llm_interface

    print(f"正在初始化LLM接口 (backend: {args.backend})...")

    if args.backend == "ollama":
        model = args.model or "qwen3:8b"
        llm = create_llm_interface("ollama", model)
        print(f"✅ LLM接口初始化完成 (Ollama: {model})\n")
    else:
        api_key = getattr(config, "OPENAI_API_KEY", None)
        base_url = getattr(config, "OPENAI_BASE_URL", None)

        if not api_key:
            print("❌ API key未配置，请设置configs/definitions_private.py")
            return 1

        model = args.model or "qwen-turbo"
        llm = create_llm_interface("openai", model, api_key=api_key, base_url=base_url)
        print(f"✅ LLM接口初始化完成 (API: {model})\n")

    # Determine which experiments to run
    if args.experiment == "all":
        exp_ids = list(EXPERIMENTS.keys())
    else:
        if args.experiment not in EXPERIMENTS:
            print(f"❌ 未知实验: {args.experiment}")
            print(f"可用实验: {', '.join(EXPERIMENTS.keys())}, all")
            return 1
        exp_ids = [args.experiment]

    # Run experiments
    results = {}
    for exp_id in exp_ids:
        log_file = setup_logging(exp_id)
        print(f"📝 日志: {log_file}")

        result = run_experiment(exp_id, llm, use_mock=args.mock)
        results[exp_id] = result

    # Summary
    print("\n" + "=" * 70)
    print("总结:")
    print("=" * 70)

    for exp_id, result in results.items():
        status = "✅ 通过" if result.get("success") else "❌ 失败"
        exp_name = EXPERIMENTS[exp_id]["name"]
        print(f"实验{exp_id.upper()} ({exp_name}): {status}")

    all_passed = all(r.get("success") for r in results.values())

    if all_passed:
        print("\n🎉 所有实验通过!")
        return 0
    else:
        print("\n⚠️  部分实验失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
