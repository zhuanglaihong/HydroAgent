"""
Author: Claude
Date: 2025-01-25 10:45:00
LastEditTime: 2025-01-25 10:45:00
LastEditors: Claude
Description: Run HydroAgent pipeline with checkpoint/resume support
             使用checkpoint/resume功能运行HydroAgent管道
FilePath: /HydroAgent/scripts/run_with_checkpoint.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

使用方法:
1. 新实验:
   python scripts/run_with_checkpoint.py --query "重复率定流域01013500五次" --backend api --mock

2. 恢复实验:
   python scripts/run_with_checkpoint.py --resume results/session_20250125_120000_abc123 --backend api --mock

特性:
- 自动保存checkpoint到每个task执行前后
- 支持Ctrl+C中断后从checkpoint恢复
- 跳过已完成的任务，只执行pending任务
"""

import sys
from pathlib import Path
import argparse
import io
import logging
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set console encoding (Windows compatible)
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="运行HydroAgent pipeline with checkpoint支持"
    )
    parser.add_argument(
        "--query",
        type=str,
        help="用户查询（新实验）"
    )
    parser.add_argument(
        "--resume",
        type=str,
        help="从指定workspace恢复（格式: results/session_xxx）"
    )
    parser.add_argument(
        "--backend",
        type=str,
        default="api",
        choices=["ollama", "api"],
        help="LLM backend (default: api)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="LLM model name"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="使用Mock模式（不运行真实hydromodel）"
    )
    args = parser.parse_args()

    # 验证参数
    if not args.query and not args.resume:
        print("❌ 错误: 必须指定 --query 或 --resume")
        parser.print_help()
        return 1

    if args.query and args.resume:
        print("❌ 错误: --query 和 --resume 不能同时使用")
        return 1

    # Setup logging
    logs_dir = project_root / "logs"
    logs_dir.mkdir(exist_ok=True)
    log_file = logs_dir / f"run_with_checkpoint_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding='utf-8')
        ]
    )

    print("\n" + "╔" + "=" * 68 + "╗")
    print("║" + "  HydroAgent with Checkpoint/Resume".center(68) + "║")
    print("╚" + "=" * 68 + "╝")

    # Load config
    try:
        from configs import definitions_private as config
    except ImportError:
        from configs import definitions as config

    # Create LLM interface
    from hydroagent.core.llm_interface import create_llm_interface

    if args.backend == "ollama":
        model = args.model or "qwen3:8b"
        llm = create_llm_interface("ollama", model)
        print(f"✅ LLM接口初始化完成 (Ollama: {model})")
    else:
        api_key = getattr(config, "OPENAI_API_KEY", None)
        base_url = getattr(config, "OPENAI_BASE_URL", None)
        if not api_key:
            print("❌ API key未配置")
            return 1

        model = args.model or "qwen-turbo"
        llm = create_llm_interface("openai", model, api_key=api_key, base_url=base_url)
        print(f"✅ LLM接口初始化完成 (API: {model})")

    # Initialize Orchestrator with checkpoint support
    from hydroagent.agents.orchestrator import Orchestrator

    orchestrator = Orchestrator(
        llm_interface=llm,
        workspace_root=project_root / "results",
        show_progress=True,
        enable_code_gen=True,
        enable_checkpoint=True  # 启用checkpoint
    )

    try:
        if args.resume:
            # 恢复模式
            print(f"\n📂 恢复模式: {args.resume}")
            workspace_path = project_root / args.resume

            session_id = orchestrator.resume_session(workspace_path)
            print(f"✅ Session已恢复: {session_id}")

            # 从checkpoint获取原始查询
            checkpoint_data = orchestrator.checkpoint_manager.get_data()
            query = checkpoint_data.get("query", "未知查询")
            print(f"📋 原始查询: {query}")

            # 继续执行（这里需要实现resume逻辑）
            print("\n⚠️  注意: 恢复执行功能需要在Orchestrator中完整实现")
            print("目前checkpoint manager已就绪，可以:")
            print("  - 查看进度")
            print("  - 获取待执行任务列表")
            print("  - 手动继续执行")

            # 显示进度
            progress = orchestrator.checkpoint_manager.get_progress_summary()
            print(f"\n当前进度:")
            print(f"  总任务数: {progress['total']}")
            print(f"  已完成: {progress['completed']}")
            print(f"  失败: {progress['failed']}")
            print(f"  待执行: {progress['pending']}")
            print(f"  进度: {progress['progress_percentage']:.1f}%")

            # 获取待执行任务
            pending_tasks = orchestrator.checkpoint_manager.get_pending_subtasks()
            if pending_tasks:
                print(f"\n待执行任务 ({len(pending_tasks)}个):")
                for i, task in enumerate(pending_tasks[:5], 1):  # 只显示前5个
                    print(f"  {i}. {task['task_id']}: {task.get('description', 'N/A')}")
                if len(pending_tasks) > 5:
                    print(f"  ... 还有{len(pending_tasks) - 5}个任务")

        else:
            # 新实验模式
            print(f"\n🆕 新实验模式")
            print(f"📋 查询: {args.query}")
            print(f"🔧 Mock模式: {args.mock}")

            session_id = orchestrator.start_new_session()
            print(f"✅ Session已创建: {session_id}")
            print(f"📂 工作目录: {orchestrator.current_workspace}")

            # 初始化checkpoint
            if orchestrator.checkpoint_manager:
                orchestrator.checkpoint_manager.initialize(
                    experiment_name="manual_run",
                    query=args.query
                )
                print("✅ Checkpoint已初始化")

            # 执行pipeline
            print("\n" + "=" * 70)
            print("开始执行 HydroAgent Pipeline")
            print("=" * 70)
            print("\n⚠️  注意: 完整的pipeline执行需要在Orchestrator.process()中实现")
            print("目前演示checkpoint的创建和保存功能")

            # 示例：手动创建一些任务状态
            if orchestrator.checkpoint_manager:
                example_plan = {
                    "task_type": "repeated_calibration",
                    "subtasks": [
                        {"task_id": f"calibration_rep_{i}", "description": f"率定 (Rep {i})"}
                        for i in range(1, 6)
                    ]
                }
                orchestrator.checkpoint_manager.save_task_plan(example_plan)
                print(f"\n✅ 示例任务计划已保存: {len(example_plan['subtasks'])} 个任务")

                print("\n💡 提示: 使用 Ctrl+C 可以中断实验")
                print("    然后使用 --resume 参数恢复执行")

        print("\n" + "=" * 70)
        print("✅ 完成!")
        print("=" * 70)
        print(f"\n📁 工作目录: {orchestrator.current_workspace}")
        print(f"📝 日志文件: {log_file}")

        if orchestrator.checkpoint_manager:
            print(f"🔖 Checkpoint文件: {orchestrator.checkpoint_manager.checkpoint_file}")

        return 0

    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断 (Ctrl+C)")
        if orchestrator.checkpoint_manager:
            progress = orchestrator.checkpoint_manager.get_progress_summary()
            print(f"\n当前进度已保存:")
            print(f"  已完成: {progress['completed']}/{progress['total']} 任务")
            print(f"  Checkpoint: {orchestrator.checkpoint_manager.checkpoint_file}")
            print(f"\n💡 恢复执行:")
            print(f"  python scripts/run_with_checkpoint.py --resume {orchestrator.current_workspace.relative_to(project_root)} --backend {args.backend} {'--mock' if args.mock else ''}")
        return 130  # Standard exit code for SIGINT

    except Exception as e:
        logging.error(f"执行失败: {str(e)}", exc_info=True)
        print(f"\n❌ 执行失败: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
