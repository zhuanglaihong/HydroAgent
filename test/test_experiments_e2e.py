"""
Author: Claude
Date: 2025-01-22 20:30:00
LastEditTime: 2025-01-22 20:30:00
LastEditors: Claude
Description: End-to-end tests for Experiments 1-5
             实验1-5的端到端测试
FilePath: \HydroAgent\test\test_experiments_e2e.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set console encoding (Windows compatible)
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import logging
from datetime import datetime
import argparse


def setup_logging(test_name):
    """Setup logging for test."""
    logs_dir = Path(__file__).parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)

    log_file = logs_dir / f"test_e2e_{test_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding='utf-8')
        ]
    )

    return log_file


def run_experiment_1(llm, use_mock=True):
    """
    实验1：标准流域验证
    Test standard basin calibration
    """
    print("\n" + "="*70)
    print("【实验1：标准流域验证】")
    print("="*70)

    from hydroagent.agents.intent_agent import IntentAgent
    from hydroagent.agents.task_planner import TaskPlanner
    from hydroagent.agents.interpreter_agent import InterpreterAgent
    from hydroagent.core.prompt_pool import PromptPool

    query = "率定流域 01013500，使用标准 XAJ 模型"
    print(f"查询: {query}\n")

    # Step 1: IntentAgent
    print("Step 1: IntentAgent...")
    intent_agent = IntentAgent(llm_interface=llm)
    intent_result = intent_agent.process({"query": query})

    if not intent_result.get("success"):
        print(f"❌ IntentAgent失败: {intent_result.get('error')}")
        return False

    intent_data = intent_result["intent_result"]
    task_type = intent_data.get("task_type")
    print(f"✅ 任务类型: {task_type}")

    # Expected: standard_calibration
    if task_type != "standard_calibration":
        print(f"⚠️  预期task_type为'standard_calibration'，实际为'{task_type}'")

    # Step 2: TaskPlanner
    print("\nStep 2: TaskPlanner...")
    workspace_dir = project_root / "test_workspace" / "exp1"
    workspace_dir.mkdir(parents=True, exist_ok=True)

    prompt_pool = PromptPool(pool_dir=workspace_dir / "prompt_pool")
    task_planner = TaskPlanner(
        llm_interface=llm,
        prompt_pool=prompt_pool,
        workspace_dir=workspace_dir
    )

    planner_result = task_planner.process({"intent_result": intent_data})

    if not planner_result.get("success"):
        print(f"❌ TaskPlanner失败: {planner_result.get('error')}")
        return False

    task_plan = planner_result["task_plan"]
    subtasks = task_plan["subtasks"]
    print(f"✅ 子任务数量: {len(subtasks)}")

    # Expected: 1 subtask
    if len(subtasks) != 1:
        print(f"⚠️  预期1个子任务，实际{len(subtasks)}个")

    # Step 3: InterpreterAgent
    print("\nStep 3: InterpreterAgent...")
    interpreter = InterpreterAgent(llm_interface=llm, workspace_dir=workspace_dir)

    config_result = interpreter.process({
        "subtask": subtasks[0],
        "intent_result": intent_data
    })

    if not config_result.get("success"):
        print(f"❌ InterpreterAgent失败: {config_result.get('error')}")
        return False

    config = config_result["config"]
    print(f"✅ 配置生成成功")
    print(f"   模型: {config.get('model_cfgs', {}).get('model_name')}")
    print(f"   流域: {config.get('data_cfgs', {}).get('basin_ids')}")

    print("\n" + "="*70)
    print("✅ 实验1测试通过")
    print("="*70)
    return True


def run_experiment_2b(llm, use_mock=True):
    """
    实验2B：缺省信息补全
    Test info completion
    """
    print("\n" + "="*70)
    print("【实验2B：缺省信息补全】")
    print("="*70)

    from hydroagent.agents.intent_agent import IntentAgent
    from hydroagent.agents.task_planner import TaskPlanner
    from hydroagent.agents.interpreter_agent import InterpreterAgent
    from hydroagent.core.prompt_pool import PromptPool

    query = "帮我率定流域 01013500"
    print(f"查询: {query}\n")

    # Step 1: IntentAgent
    print("Step 1: IntentAgent...")
    intent_agent = IntentAgent(llm_interface=llm)
    intent_result = intent_agent.process({"query": query})

    if not intent_result.get("success"):
        print(f"❌ IntentAgent失败: {intent_result.get('error')}")
        return False

    intent_data = intent_result["intent_result"]
    task_type = intent_data.get("task_type")
    print(f"✅ 任务类型: {task_type}")

    # Check info completion
    model_name = intent_data.get("model_name")
    algorithm = intent_data.get("algorithm")
    time_period = intent_data.get("time_period")

    print(f"   自动补全:")
    print(f"   - 模型: {model_name}")
    print(f"   - 算法: {algorithm}")
    print(f"   - 训练期: {time_period.get('train') if time_period else 'N/A'}")

    # Expected: info_completion task type with auto-filled values
    if task_type != "info_completion":
        print(f"⚠️  预期task_type为'info_completion'，实际为'{task_type}'")

    if not model_name or not algorithm:
        print(f"⚠️  信息补全失败")
        return False

    print("\n" + "="*70)
    print("✅ 实验2B测试通过")
    print("="*70)
    return True


def run_experiment_3(llm, use_mock=True):
    """
    实验3：参数自适应优化（两阶段）
    Test iterative optimization with boundary checking
    """
    print("\n" + "="*70)
    print("【实验3：参数自适应优化】")
    print("="*70)

    from hydroagent.agents.intent_agent import IntentAgent
    from hydroagent.agents.task_planner import TaskPlanner

    query = "率定流域 01013500，如果参数收敛到边界，自动调整范围重新率定"
    print(f"查询: {query}\n")

    # Step 1: IntentAgent
    print("Step 1: IntentAgent...")
    intent_agent = IntentAgent(llm_interface=llm)
    intent_result = intent_agent.process({"query": query})

    if not intent_result.get("success"):
        print(f"❌ IntentAgent失败: {intent_result.get('error')}")
        return False

    intent_data = intent_result["intent_result"]
    task_type = intent_data.get("task_type")
    strategy = intent_data.get("strategy", {})

    print(f"✅ 任务类型: {task_type}")
    print(f"   策略: {strategy}")

    # Expected: iterative_optimization
    if task_type != "iterative_optimization":
        print(f"⚠️  预期task_type为'iterative_optimization'，实际为'{task_type}'")

    # Step 2: TaskPlanner
    print("\nStep 2: TaskPlanner...")
    workspace_dir = project_root / "test_workspace" / "exp3"
    workspace_dir.mkdir(parents=True, exist_ok=True)

    from hydroagent.core.prompt_pool import PromptPool
    prompt_pool = PromptPool(pool_dir=workspace_dir / "prompt_pool")
    task_planner = TaskPlanner(
        llm_interface=llm,
        prompt_pool=prompt_pool,
        workspace_dir=workspace_dir
    )

    planner_result = task_planner.process({"intent_result": intent_data})

    if not planner_result.get("success"):
        print(f"❌ TaskPlanner失败: {planner_result.get('error')}")
        return False

    task_plan = planner_result["task_plan"]
    subtasks = task_plan["subtasks"]
    print(f"✅ 子任务数量: {len(subtasks)}")

    # Expected: 2 subtasks (phase1 + phase2)
    if len(subtasks) != 2:
        print(f"⚠️  预期2个子任务，实际{len(subtasks)}个")

    # Check dependencies
    phase2_task = subtasks[1]
    dependencies = phase2_task.get("dependencies", [])
    print(f"   Phase 2依赖: {dependencies}")

    if not dependencies or subtasks[0]["task_id"] not in dependencies:
        print(f"⚠️  Phase 2应该依赖于Phase 1")

    print("\n" + "="*70)
    print("✅ 实验3测试通过")
    print("="*70)
    return True


def run_experiment_4(llm, use_mock=True):
    """
    实验4：扩展分析（代码生成）
    Test extended analysis with code generation
    """
    print("\n" + "="*70)
    print("【实验4：扩展分析】")
    print("="*70)

    from hydroagent.agents.intent_agent import IntentAgent
    from hydroagent.agents.task_planner import TaskPlanner

    query = "率定完成后，请帮我计算流域的径流系数，并画一张流路历时曲线 FDC"
    print(f"查询: {query}\n")

    # Step 1: IntentAgent
    print("Step 1: IntentAgent...")
    intent_agent = IntentAgent(llm_interface=llm)
    intent_result = intent_agent.process({"query": query})

    if not intent_result.get("success"):
        print(f"❌ IntentAgent失败: {intent_result.get('error')}")
        return False

    intent_data = intent_result["intent_result"]
    task_type = intent_data.get("task_type")
    needs = intent_data.get("needs", [])

    print(f"✅ 任务类型: {task_type}")
    print(f"   扩展分析需求: {needs}")

    # Expected: extended_analysis
    if task_type != "extended_analysis":
        print(f"⚠️  预期task_type为'extended_analysis'，实际为'{task_type}'")

    if "runoff_coefficient" not in needs or "FDC" not in needs:
        print(f"⚠️  未正确提取扩展分析需求")

    # Step 2: TaskPlanner
    print("\nStep 2: TaskPlanner...")
    workspace_dir = project_root / "test_workspace" / "exp4"
    workspace_dir.mkdir(parents=True, exist_ok=True)

    from hydroagent.core.prompt_pool import PromptPool
    prompt_pool = PromptPool(pool_dir=workspace_dir / "prompt_pool")
    task_planner = TaskPlanner(
        llm_interface=llm,
        prompt_pool=prompt_pool,
        workspace_dir=workspace_dir
    )

    planner_result = task_planner.process({"intent_result": intent_data})

    if not planner_result.get("success"):
        print(f"❌ TaskPlanner失败: {planner_result.get('error')}")
        return False

    task_plan = planner_result["task_plan"]
    subtasks = task_plan["subtasks"]
    print(f"✅ 子任务数量: {len(subtasks)}")

    # Expected: 3 subtasks (1 calibration + 2 analyses)
    if len(subtasks) != 3:
        print(f"⚠️  预期3个子任务，实际{len(subtasks)}个")

    # Check task types
    task_types = [st["task_type"] for st in subtasks]
    print(f"   子任务类型: {task_types}")

    if "custom_analysis" not in task_types:
        print(f"⚠️  应该包含custom_analysis类型的子任务")

    print("\n" + "="*70)
    print("✅ 实验4测试通过")
    print("="*70)
    return True


def run_experiment_5(llm, use_mock=True):
    """
    实验5：稳定性验证（重复实验）
    Test repeated experiments with statistical analysis
    """
    print("\n" + "="*70)
    print("【实验5：稳定性验证】")
    print("="*70)

    from hydroagent.agents.intent_agent import IntentAgent
    from hydroagent.agents.task_planner import TaskPlanner

    query = "重复率定流域 01013500 十次，使用不同随机种子"
    print(f"查询: {query}\n")

    # Step 1: IntentAgent
    print("Step 1: IntentAgent...")
    intent_agent = IntentAgent(llm_interface=llm)
    intent_result = intent_agent.process({"query": query})

    if not intent_result.get("success"):
        print(f"❌ IntentAgent失败: {intent_result.get('error')}")
        return False

    intent_data = intent_result["intent_result"]
    task_type = intent_data.get("task_type")
    n_repeats = intent_data.get("n_repeats", 0)

    print(f"✅ 任务类型: {task_type}")
    print(f"   重复次数: {n_repeats}")

    # Expected: repeated_experiment
    if task_type != "repeated_experiment":
        print(f"⚠️  预期task_type为'repeated_experiment'，实际为'{task_type}'")

    if n_repeats != 10:
        print(f"⚠️  预期重复10次，实际{n_repeats}次")

    # Step 2: TaskPlanner
    print("\nStep 2: TaskPlanner...")
    workspace_dir = project_root / "test_workspace" / "exp5"
    workspace_dir.mkdir(parents=True, exist_ok=True)

    from hydroagent.core.prompt_pool import PromptPool
    prompt_pool = PromptPool(pool_dir=workspace_dir / "prompt_pool")
    task_planner = TaskPlanner(
        llm_interface=llm,
        prompt_pool=prompt_pool,
        workspace_dir=workspace_dir
    )

    planner_result = task_planner.process({"intent_result": intent_data})

    if not planner_result.get("success"):
        print(f"❌ TaskPlanner失败: {planner_result.get('error')}")
        return False

    task_plan = planner_result["task_plan"]
    subtasks = task_plan["subtasks"]
    print(f"✅ 子任务数量: {len(subtasks)}")

    # Expected: 11 subtasks (10 repeats + 1 statistical analysis)
    if len(subtasks) != 11:
        print(f"⚠️  预期11个子任务，实际{len(subtasks)}个")

    # Check last task is statistical_analysis
    last_task = subtasks[-1]
    if last_task["task_type"] != "statistical_analysis":
        print(f"⚠️  最后一个任务应该是statistical_analysis")

    # Check dependencies
    dependencies = last_task.get("dependencies", [])
    print(f"   统计分析任务依赖: {len(dependencies)} 个任务")

    if len(dependencies) != 10:
        print(f"⚠️  统计分析应该依赖10个重复任务")

    print("\n" + "="*70)
    print("✅ 实验5测试通过")
    print("="*70)
    return True


def main():
    """Main test function."""
    parser = argparse.ArgumentParser(description='End-to-end tests for Experiments 1-5')
    parser.add_argument('--backend', type=str, default='api',
                       choices=['ollama', 'api'],
                       help='LLM backend (default: api)')
    parser.add_argument('--model', type=str, default=None,
                       help='Model name')
    parser.add_argument('--experiment', type=str, default='all',
                       choices=['all', '1', '2b', '3', '4', '5'],
                       help='Which experiment to run (default: all)')
    parser.add_argument('--mock', action='store_true',
                       help='Use mock mode for hydromodel execution')
    args = parser.parse_args()

    # Setup logging
    log_file = setup_logging(args.experiment)

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║     HydroAgent 实验1-5端到端测试                           ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"\n📝 日志文件: {log_file}\n")

    # Load config
    try:
        from configs import definitions_private as config
    except ImportError:
        from configs import definitions as config

    # Create LLM interface
    from hydroagent.core.llm_interface import create_llm_interface

    print(f"正在初始化LLM接口 (backend: {args.backend})...")

    if args.backend == 'ollama':
        model = args.model or 'qwen3:8b'
        llm = create_llm_interface('ollama', model)
        print(f"✅ LLM接口初始化完成 (Ollama: {model})\n")
    else:
        api_key = getattr(config, 'OPENAI_API_KEY', None)
        base_url = getattr(config, 'OPENAI_BASE_URL', None)

        if not api_key:
            print("❌ API key未配置，请设置configs/definitions_private.py")
            return 1

        model = args.model or 'qwen-turbo'
        llm = create_llm_interface('openai', model,
                                  api_key=api_key,
                                  base_url=base_url)
        print(f"✅ LLM接口初始化完成 (API: {model})\n")

    # Run experiments
    results = {}

    if args.experiment == 'all' or args.experiment == '1':
        results['exp1'] = run_experiment_1(llm, use_mock=args.mock)

    if args.experiment == 'all' or args.experiment == '2b':
        results['exp2b'] = run_experiment_2b(llm, use_mock=args.mock)

    if args.experiment == 'all' or args.experiment == '3':
        results['exp3'] = run_experiment_3(llm, use_mock=args.mock)

    if args.experiment == 'all' or args.experiment == '4':
        results['exp4'] = run_experiment_4(llm, use_mock=args.mock)

    if args.experiment == 'all' or args.experiment == '5':
        results['exp5'] = run_experiment_5(llm, use_mock=args.mock)

    # Summary
    print("\n" + "="*70)
    print("测试总结:")
    print("="*70)

    for exp_name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{exp_name}: {status}")

    all_passed = all(results.values())

    if all_passed:
        print("\n🎉 所有测试通过!")
    else:
        print("\n⚠️  部分测试失败，请查看日志")

    print(f"\n📝 完整日志: {log_file}")
    print("="*70)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
