"""
Author: Claude
Date: 2025-11-25 12:00:00
LastEditTime: 2025-11-25 12:00:00
LastEditors: Claude
Description: Test Orchestrator as unified interface (5-Agent + checkpoint)
             测试Orchestrator作为统一接口（5-Agent + checkpoint）
FilePath: /HydroAgent/test/test_orchestrator_unified.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

测试目标:
1. 验证Orchestrator是完整的对外统一接口
2. 验证5-Agent流程正确串联
3. 验证checkpoint功能集成
4. 验证多任务场景支持
"""

import sys
from pathlib import Path
import io
import logging
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# Setup logging
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)
log_file = logs_dir / f"test_orchestrator_unified_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


def test_orchestrator_as_unified_interface():
    """
    测试1: Orchestrator作为统一接口
    """
    print("\n" + "=" * 70)
    print("测试1: Orchestrator作为统一接口")
    print("=" * 70)

    try:
        from configs import definitions_private as config
    except ImportError:
        from configs import definitions as config

    from hydroagent.core.llm_interface import create_llm_interface
    from hydroagent.agents.orchestrator import Orchestrator

    # 创建LLM接口（使用Mock或真实API）
    print("\n初始化LLM接口...")
    api_key = getattr(config, "OPENAI_API_KEY", None)
    base_url = getattr(config, "OPENAI_BASE_URL", None)

    if not api_key:
        print("⚠️  警告: API key未配置，测试可能失败")
        print("    请配置configs/definitions_private.py")
        return False

    llm = create_llm_interface("openai", "qwen-turbo", api_key=api_key, base_url=base_url)
    print("✅ LLM接口初始化完成")

    # 创建Orchestrator（统一接口）
    print("\n创建Orchestrator...")
    orchestrator = Orchestrator(
        llm_interface=llm,
        workspace_root=project_root / "test_workspace" / "orchestrator_test",
        enable_checkpoint=True,  # 启用checkpoint
        show_progress=False,
        enable_code_gen=False
    )
    print("✅ Orchestrator初始化完成")

    # 开始会话
    print("\n开始新会话...")
    session_id = orchestrator.start_new_session()
    print(f"✅ Session ID: {session_id}")

    # 测试查询（简单的单流域率定）
    query = "率定流域12025000，使用GR4J模型"
    print(f"\n📋 测试查询: {query}")
    print("\n执行完整5-Agent流程...")
    print("  1. IntentAgent - 意图识别")
    print("  2. TaskPlanner - 任务拆解")
    print("  3. InterpreterAgent - 配置生成")
    print("  4. RunnerAgent - 模型执行")
    print("  5. DeveloperAgent - 结果分析")

    # 调用统一接口
    result = orchestrator.process({
        "query": query,
        "use_mock": True  # 使用Mock模式加快测试
    })

    # 验证结果
    print("\n" + "=" * 70)
    print("验证结果")
    print("=" * 70)

    success = result.get("success", False)
    print(f"\n{'✅' if success else '❌'} 执行成功: {success}")

    if success:
        print(f"\n📊 结果摘要:")
        print(f"  Session ID: {result['session_id']}")
        print(f"  工作目录: {result['workspace']}")

        # Intent
        intent = result.get("intent", {})
        intent_data = intent.get("intent_result", {})
        print(f"\n  1️⃣  Intent:")
        print(f"      task_type: {intent_data.get('task_type')}")
        print(f"      model: {intent_data.get('model_name')}")
        print(f"      basin: {intent_data.get('basin_id')}")

        # Task Plan
        task_plan = result.get("task_plan", {})
        subtasks = task_plan.get("subtasks", [])
        print(f"\n  2️⃣  Task Plan:")
        print(f"      subtasks: {len(subtasks)} 个")

        # Configs
        configs = result.get("configs", [])
        print(f"\n  3️⃣  Configs:")
        print(f"      生成数量: {len(configs)} 个")

        # Execution
        execution_results = result.get("execution_results", [])
        successful = sum(1 for r in execution_results if r.get("success"))
        print(f"\n  4️⃣  Execution:")
        print(f"      成功: {successful}/{len(execution_results)}")

        # Analysis
        analysis = result.get("analysis", {})
        print(f"\n  5️⃣  Analysis:")
        print(f"      quality: {analysis.get('analysis', {}).get('quality', 'N/A')}")

        print(f"\n⏱️  总耗时: {result.get('elapsed_time', 0):.1f}s")

        # 验证checkpoint
        if orchestrator.checkpoint_manager:
            print(f"\n🔖 Checkpoint:")
            print(f"  文件: {orchestrator.checkpoint_manager.checkpoint_file}")
            progress = orchestrator.checkpoint_manager.get_progress_summary()
            print(f"  进度: {progress['completed']}/{progress['total']} 任务完成")

        return True
    else:
        print(f"\n❌ 错误: {result.get('error')}")
        return False


def test_orchestrator_multi_task():
    """
    测试2: 多任务场景（重复率定）
    """
    print("\n" + "=" * 70)
    print("测试2: 多任务场景（重复率定3次）")
    print("=" * 70)

    try:
        from configs import definitions_private as config
    except ImportError:
        from configs import definitions as config

    from hydroagent.core.llm_interface import create_llm_interface
    from hydroagent.agents.orchestrator import Orchestrator

    # 创建LLM接口
    api_key = getattr(config, "OPENAI_API_KEY", None)
    base_url = getattr(config, "OPENAI_BASE_URL", None)

    if not api_key:
        print("⚠️  跳过测试（API key未配置）")
        return False

    llm = create_llm_interface("openai", "qwen-turbo", api_key=api_key, base_url=base_url)

    # 创建Orchestrator
    orchestrator = Orchestrator(
        llm_interface=llm,
        workspace_root=project_root / "test_workspace" / "orchestrator_multitask",
        enable_checkpoint=True,
        show_progress=False
    )

    session_id = orchestrator.start_new_session()
    print(f"✅ Session ID: {session_id}")

    # 多任务查询
    query = "重复率定流域12025000三次，使用GR4J模型"
    print(f"\n📋 测试查询: {query}")

    # 执行
    result = orchestrator.process({
        "query": query,
        "use_mock": True
    })

    # 验证多任务
    if result.get("success"):
        task_plan = result.get("task_plan", {})
        subtasks = task_plan.get("subtasks", [])
        execution_results = result.get("execution_results", [])

        print(f"\n✅ 多任务执行成功!")
        print(f"  子任务数: {len(subtasks)}")
        print(f"  执行结果数: {len(execution_results)}")

        assert len(subtasks) >= 3, "应该有至少3个子任务"
        assert len(execution_results) >= 3, "应该有至少3个执行结果"

        print("\n✅ 测试2通过!")
        return True
    else:
        print(f"\n❌ 测试2失败: {result.get('error')}")
        return False


def main():
    """运行所有测试"""
    print("\n" + "╔" + "=" * 68 + "╗")
    print("║" + "  测试Orchestrator统一接口".center(68) + "║")
    print("╚" + "=" * 68 + "╝")

    results = []

    try:
        # 测试1: 统一接口
        result1 = test_orchestrator_as_unified_interface()
        results.append(("统一接口", result1))

        # 测试2: 多任务
        result2 = test_orchestrator_multi_task()
        results.append(("多任务场景", result2))

    except Exception as e:
        logger.error(f"测试失败: {str(e)}", exc_info=True)
        print(f"\n❌ 测试异常: {str(e)}")
        return 1

    # 总结
    print("\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)

    for test_name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {test_name}: {status}")

    all_passed = all(passed for _, passed in results)

    if all_passed:
        print("\n🎉 所有测试通过!")
        print(f"\n📝 日志文件: {log_file}")
        return 0
    else:
        print("\n⚠️  部分测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
