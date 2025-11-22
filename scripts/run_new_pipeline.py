"""
Author: Claude
Date: 2025-01-22 17:30:00
LastEditTime: 2025-01-22 17:30:00
LastEditors: Claude
Description: New 5-Agent pipeline (Phase 2): Intent → TaskPlanner → Interpreter → Runner → Developer
             新的5-Agent管道（Phase 2）：意图 → 任务规划 → 解释器 → 执行 → 分析
FilePath: \\HydroAgent\\scripts\\run_new_pipeline.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import sys
import logging
import json
import argparse
import time
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, Mock, MagicMock

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 设置控制台编码（Windows兼容）
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 确保logs目录存在
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

# 设置详细日志
log_file = logs_dir / f"run_new_pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


def print_banner():
    """打印横幅"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║            HydroAgent 新5-Agent管道测试 (Phase 2)           ║
║  Intent → TaskPlanner → Interpreter → Runner → Developer    ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)
    print(f"日志文件: {log_file}\n")


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='新5-Agent管道测试 (Phase 2): Intent → TaskPlanner → Interpreter → Runner → Developer'
    )
    parser.add_argument(
        'query',
        type=str,
        nargs='?',
        default="率定GR4J模型，流域01013500",
        help='用户查询（默认：率定GR4J模型）'
    )
    parser.add_argument(
        '--backend',
        type=str,
        default='api',
        choices=['ollama', 'openai', 'api'],
        help='LLM后端 (default: api)'
    )
    parser.add_argument(
        '--model',
        type=str,
        default=None,
        help='模型名称'
    )
    parser.add_argument(
        '--mock',
        action='store_true',
        help='使用Mock模式（不调用真实hydromodel）'
    )
    parser.add_argument(
        '--save-all',
        action='store_true',
        help='保存所有中间结果'
    )
    return parser.parse_args()


def load_config():
    """从配置文件加载API设置"""
    try:
        from configs import definitions_private as config
    except ImportError:
        try:
            from configs import definitions as config
        except ImportError:
            config = None

    if config:
        return {
            'api_key': getattr(config, 'OPENAI_API_KEY', None),
            'base_url': getattr(config, 'OPENAI_BASE_URL', None),
        }
    return {'api_key': None, 'base_url': None}


def create_llm(backend: str, model: str = None):
    """创建LLM接口"""
    from hydroagent.core.llm_interface import create_llm_interface

    config = load_config()

    if backend == 'ollama':
        model = model or 'qwen3:8b'
        llm = create_llm_interface('ollama', model)
        desc = f"Ollama ({model})"
    elif backend == 'openai':
        model = model or 'gpt-4'
        llm = create_llm_interface('openai', model, api_key=config['api_key'])
        desc = f"OpenAI ({model})"
    elif backend == 'api':
        model = model or 'qwen-turbo'
        llm = create_llm_interface('openai', model,
                                   api_key=config['api_key'],
                                   base_url=config['base_url'])
        desc = f"通义千问 API ({model})"
    else:
        raise ValueError(f"不支持的后端: {backend}")

    return llm, desc


def run_new_pipeline(query: str, llm, llm_desc: str, use_mock: bool = False,
                     save_all: bool = False):
    """
    运行新的5-Agent管道 (Phase 2)

    Args:
        query: 用户查询
        llm: LLM接口
        llm_desc: LLM描述
        use_mock: 是否使用Mock模式
        save_all: 是否保存所有中间结果

    Returns:
        是否成功
    """
    from hydroagent.agents.intent_agent import IntentAgent
    from hydroagent.agents.task_planner import TaskPlanner
    from hydroagent.agents.interpreter_agent import InterpreterAgent
    from hydroagent.agents.runner_agent import RunnerAgent
    from hydroagent.agents.developer_agent import DeveloperAgent
    from hydroagent.core.prompt_pool import PromptPool

    workspace_dir = project_root / "results" / datetime.now().strftime("%Y%m%d_%H%M%S")
    workspace_dir.mkdir(parents=True, exist_ok=True)

    # 初始化5个Agents
    intent_agent = IntentAgent(llm_interface=llm)

    prompt_pool = PromptPool(pool_dir=workspace_dir / "prompt_pool")
    task_planner = TaskPlanner(
        llm_interface=llm,
        prompt_pool=prompt_pool,
        workspace_dir=workspace_dir
    )

    interpreter_agent = InterpreterAgent(
        llm_interface=llm,
        workspace_dir=workspace_dir
    )

    runner_agent = RunnerAgent(
        llm_interface=llm,
        workspace_dir=workspace_dir,
        show_progress=True
    )

    developer_agent = DeveloperAgent(
        llm_interface=llm,
        workspace_dir=workspace_dir,
        enable_code_gen=True
    )

    print("✅ 5个Agents初始化完成 (IntentAgent, TaskPlanner, InterpreterAgent, RunnerAgent, DeveloperAgent)\n")

    total_start = time.time()

    # ========================================================================
    # Step 1: IntentAgent - 意图分析 & 任务决策
    # ========================================================================
    print("🔍 [Step 1/5] IntentAgent - 分析用户意图 & 决策任务类型...")
    intent_start = time.time()

    try:
        intent_result = intent_agent.process({"query": query})
        intent_elapsed = time.time() - intent_start

        if not intent_result.get("success"):
            print(f"❌ Intent分析失败: {intent_result.get('error')}")
            return False

        print(f"✅ Intent分析完成 ({intent_elapsed:.1f}s)\n")

        # 显示意图摘要
        intent_data = intent_result.get("intent_result", {})
        print("意图摘要:")

        task_type = intent_data.get('task_type', 'N/A')
        print(f"  🎯 任务类型: {task_type}")
        print(f"  意图:      {intent_data.get('intent', 'N/A').upper()}")
        print(f"  模型:      {intent_data.get('model_name', 'N/A')}")
        print(f"  流域:      {intent_data.get('basin_id', 'N/A')}")
        print(f"  算法:      {intent_data.get('algorithm', 'SCE_UA')}")

        # 任务类型特定信息
        if task_type == "iterative_optimization":
            strategy = intent_data.get('strategy', {})
            if strategy:
                print(f"  🔄 策略:    {strategy.get('phases', [])}")

        elif task_type == "extended_analysis":
            needs = intent_data.get('needs', [])
            if needs:
                print(f"  🔬 扩展分析: {', '.join(needs)}")

        elif task_type == "repeated_experiment":
            n_repeats = intent_data.get('n_repeats', 10)
            print(f"  🔁 重复次数: {n_repeats}")

        print()

        # 保存
        if save_all:
            intent_file = workspace_dir / "intent_result.json"
            with open(intent_file, 'w', encoding='utf-8') as f:
                json.dump(intent_result, f, indent=2, ensure_ascii=False)
            print(f"💾 Intent结果已保存: {intent_file}\n")

    except Exception as e:
        print(f"❌ Intent分析异常: {str(e)}")
        logger.error(f"Intent分析异常: {str(e)}", exc_info=True)
        return False

    # ========================================================================
    # Step 2: TaskPlanner - 任务拆解 & 提示词生成
    # ========================================================================
    print("📋 [Step 2/5] TaskPlanner - 任务拆解 & 生成提示词...")
    planner_start = time.time()

    try:
        planner_result = task_planner.process({"intent_result": intent_data})
        planner_elapsed = time.time() - planner_start

        if not planner_result.get("success"):
            print(f"❌ 任务规划失败: {planner_result.get('error')}")
            return False

        print(f"✅ 任务规划完成 ({planner_elapsed:.1f}s)\n")

        # 显示任务计划
        task_plan = planner_result.get("task_plan", {})
        subtasks = task_plan.get("subtasks", [])
        total_subtasks = task_plan.get("total_subtasks", 0)

        print(f"任务计划: {total_subtasks} 个子任务")
        for i, subtask in enumerate(subtasks, 1):
            task_id = subtask["task_id"]
            task_type = subtask["task_type"]
            description = subtask["description"]
            dependencies = subtask.get("dependencies", [])

            print(f"  [{i}] {task_id}")
            print(f"      类型: {task_type}")
            print(f"      描述: {description}")
            if dependencies:
                print(f"      依赖: {', '.join(dependencies)}")

        print()

        # 保存
        if save_all:
            plan_file = workspace_dir / "task_plan.json"
            with open(plan_file, 'w', encoding='utf-8') as f:
                json.dump(planner_result, f, indent=2, ensure_ascii=False)
            print(f"💾 任务计划已保存: {plan_file}\n")

    except Exception as e:
        print(f"❌ 任务规划异常: {str(e)}")
        logger.error(f"任务规划异常: {str(e)}", exc_info=True)
        return False

    # ========================================================================
    # Step 3: InterpreterAgent - 为每个子任务生成配置
    # ========================================================================
    print("🔧 [Step 3/5] InterpreterAgent - 生成hydromodel配置...")
    interpreter_start = time.time()

    configs = []

    try:
        for i, subtask in enumerate(subtasks, 1):
            task_id = subtask["task_id"]
            print(f"  [{i}/{total_subtasks}] 生成配置: {task_id}...")

            interpreter_result = interpreter_agent.process({
                "subtask": subtask,
                "intent_result": intent_data
            })

            if not interpreter_result.get("success"):
                print(f"❌ 配置生成失败 ({task_id}): {interpreter_result.get('error')}")
                return False

            configs.append(interpreter_result)
            print(f"      ✅ 配置已生成")

        interpreter_elapsed = time.time() - interpreter_start
        print(f"\n✅ 所有配置生成完成 ({interpreter_elapsed:.1f}s)\n")

        # 保存
        if save_all:
            for i, config_result in enumerate(configs, 1):
                config_file = workspace_dir / f"config_{i}.json"
                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump(config_result.get("config", {}), f, indent=2, ensure_ascii=False)
            print(f"💾 配置已保存到 {workspace_dir}\n")

    except Exception as e:
        print(f"❌ 配置生成异常: {str(e)}")
        logger.error(f"配置生成异常: {str(e)}", exc_info=True)
        return False

    # ========================================================================
    # Step 4: RunnerAgent - 执行子任务
    # ========================================================================
    print("🚀 [Step 4/5] RunnerAgent - 执行hydromodel...")
    runner_start = time.time()

    execution_results = []

    try:
        for i, config_result in enumerate(configs, 1):
            task_id = config_result.get("task_id", f"task_{i}")
            print(f"  [{i}/{total_subtasks}] 执行任务: {task_id}...")

            if use_mock:
                # Mock模式
                print(f"      使用Mock模式")

                mock_result = {
                    "best_params": {"x1": 350.0, "x2": 0.5, "x3": 100.0, "x4": 2.0},
                    "metrics": {"NSE": 0.85, "RMSE": 2.5, "KGE": 0.82, "PBIAS": 5.2},
                    "output_files": ["results/calibrated_params.json"]
                }

                # 创建模拟的hydromodel模块
                mock_hydromodel = MagicMock()
                mock_hydromodel.calibrate = Mock(return_value=mock_result)
                mock_hydromodel.evaluate = Mock(return_value=mock_result)

                with patch.dict('sys.modules', {'hydromodel': mock_hydromodel}):
                    runner_result = runner_agent.process(config_result)

            else:
                # 真实模式
                runner_result = runner_agent.process(config_result)

            if not runner_result.get("success"):
                print(f"❌ 执行失败 ({task_id}): {runner_result.get('error')}")
                return False

            execution_results.append(runner_result)
            print(f"      ✅ 执行完成")

            # 显示关键指标
            result_data = runner_result.get("result", {})
            metrics = result_data.get("metrics", {})
            if metrics and "NSE" in metrics:
                nse = metrics["NSE"]
                print(f"      NSE: {nse:.4f}")

        runner_elapsed = time.time() - runner_start
        print(f"\n✅ 所有任务执行完成 ({runner_elapsed:.1f}s)\n")

    except Exception as e:
        print(f"❌ Runner执行异常: {str(e)}")
        logger.error(f"Runner执行异常: {str(e)}", exc_info=True)
        return False

    # ========================================================================
    # Step 5: DeveloperAgent - 结果分析
    # ========================================================================
    print("📊 [Step 5/5] DeveloperAgent - 分析结果...")
    developer_start = time.time()

    try:
        # 合并所有执行结果（简化版，实际可能需要更复杂的合并逻辑）
        combined_result = execution_results[0] if execution_results else {}

        developer_result = developer_agent.process(combined_result)
        developer_elapsed = time.time() - developer_start

        if not developer_result.get("success"):
            print(f"❌ 结果分析失败: {developer_result.get('error')}")
            return False

        print(f"✅ 分析完成 ({developer_elapsed:.1f}s)\n")

        # 显示分析结果
        analysis = developer_result.get("analysis", {})
        print("=" * 70)
        print("分析报告:")
        print("=" * 70)

        # 质量评估
        if "quality" in analysis:
            print(f"\n📈 质量评估: {analysis['quality']}")

        # 性能指标
        if "metrics" in analysis and analysis["metrics"]:
            print("\n🎯 性能指标:")
            for key, value in analysis["metrics"].items():
                print(f"  {key}: {value}")

        # 参数信息
        if "parameters" in analysis and analysis["parameters"]:
            print(f"\n🔧 最优参数: {len(analysis['parameters'])} 个")

        # 建议
        if "recommendations" in analysis and analysis["recommendations"]:
            print(f"\n💡 改进建议:")
            for i, rec in enumerate(analysis["recommendations"], 1):
                print(f"  {i}. {rec}")

        print("\n" + "=" * 70)

        # 保存
        if save_all:
            analysis_file = workspace_dir / "analysis_report.json"
            with open(analysis_file, 'w', encoding='utf-8') as f:
                json.dump(developer_result, f, indent=2, ensure_ascii=False)
            print(f"\n💾 分析报告已保存: {analysis_file}")

    except Exception as e:
        print(f"❌ Developer分析异常: {str(e)}")
        logger.error(f"Developer分析异常: {str(e)}", exc_info=True)
        return False

    # ========================================================================
    # 总结
    # ========================================================================
    total_elapsed = time.time() - total_start

    print("\n" + "=" * 70)
    print("✅ 新5-Agent管道执行成功! (Phase 2)")
    print("=" * 70)
    print()
    print("时间统计:")
    print(f"  Intent分析:        {intent_elapsed:.1f}s")
    print(f"  TaskPlanner:       {planner_elapsed:.1f}s")
    print(f"  InterpreterAgent:  {interpreter_elapsed:.1f}s")
    print(f"  Runner执行:        {runner_elapsed:.1f}s")
    print(f"  Developer分析:     {developer_elapsed:.1f}s")
    print(f"  总计时间:          {total_elapsed:.1f}s")
    print()
    print(f"工作目录: {workspace_dir}")
    print(f"日志文件: {log_file}")
    print()
    print("🎉 Phase 2 架构验证成功!")
    print("   - IntentAgent: 战略决策 (task_type)")
    print("   - TaskPlanner: 战术拆解 (subtasks + prompts)")
    print("   - InterpreterAgent: 配置生成 (LLM-driven)")
    print("   - RunnerAgent: 执行")
    print("   - DeveloperAgent: 分析")
    print("=" * 70)

    return True


def main():
    """主函数"""
    args = parse_args()

    print_banner()

    # 创建LLM接口
    try:
        llm, llm_desc = create_llm(args.backend, args.model)
        print(f"✅ LLM后端: {llm_desc}\n")
    except Exception as e:
        print(f"❌ LLM初始化失败: {str(e)}")
        return 1

    # 运行新管道
    success = run_new_pipeline(
        query=args.query,
        llm=llm,
        llm_desc=llm_desc,
        use_mock=args.mock,
        save_all=args.save_all
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
