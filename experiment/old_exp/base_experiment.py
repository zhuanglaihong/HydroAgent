"""
Author: Claude
Date: 2025-01-23 00:00:00
LastEditTime: 2025-01-23 00:00:00
LastEditors: Claude
Description: 基础实验类 - 所有实验的通用执行框架
             Base Experiment Class - Common execution framework for all experiments
FilePath: /HydroAgent/experiment/base_experiment.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.

用途：
- 提供统一的实验执行流程
- 自动处理工作目录命名
- 标准化的日志记录
- 5-Agent pipeline 的通用封装
"""

import sys
from pathlib import Path
import json
import time
from datetime import datetime
import logging

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class BaseExperiment:
    """
    基础实验类，封装通用的实验执行流程。

    所有具体实验（exp_1, exp_2a, ...）都应该使用这个类来执行。
    """

    def __init__(self, exp_name: str, exp_description: str):
        """
        初始化实验。

        Args:
            exp_name: 实验名称（如 "exp_1_standard_calibration"）
            exp_description: 实验描述（如 "标准流域验证"）
        """
        self.exp_name = exp_name
        self.exp_description = exp_description
        self.project_root = project_root

    def setup_logging(self):
        """设置日志记录。"""
        logs_dir = self.project_root / "logs"
        logs_dir.mkdir(exist_ok=True)

        log_file = logs_dir / f"{self.exp_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

        # 检查 root logger 是否已经配置了 handlers
        root_logger = logging.getLogger()

        # 如果已经有 handlers，说明 logging 已被配置过，直接添加文件 handler
        if root_logger.handlers:
            # 添加文件 handler 到现有配置
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(
                logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            )
            root_logger.addHandler(file_handler)
        else:
            # 第一次配置，使用 basicConfig
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                handlers=[
                    logging.StreamHandler(),
                    logging.FileHandler(log_file, encoding="utf-8"),
                ],
            )

        return log_file

    def create_workspace(self):
        """创建实验工作目录。"""
        workspace_dir = (
            self.project_root
            / "experiment_results"
            / self.exp_name  # ← 使用实验名称，不再硬编码 "exp1"
            / datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        workspace_dir.mkdir(parents=True, exist_ok=True)
        return workspace_dir

    def run_experiment(self, query: str, llm, use_mock: bool = True, code_llm=None):
        """
        运行完整的实验流程（使用Orchestrator统一接口）。

        Args:
            query: 用户查询
            llm: LLM接口（通用模型）
            use_mock: 是否使用Mock模式
            code_llm: 代码专用LLM接口（可选）
                如果提供，RunnerAgent将使用此模型生成代码
                例如: qwen-coder-turbo, deepseek-coder:6.7b

        Returns:
            实验结果字典
        """
        from hydroagent.agents.orchestrator import Orchestrator

        print("\n" + "=" * 70)
        print(f"【{self.exp_description}】")
        print("=" * 70)
        print(f"查询: {query}")
        print(f"模式: {'Mock (模拟)' if use_mock else 'Real (真实hydromodel)'}")
        print()

        # 设置日志记录
        log_file = self.setup_logging()

        # 创建实验工作目录根路径
        experiment_workspace_root = (
            self.project_root
            / "experiment_results"
            / self.exp_name
        )
        experiment_workspace_root.mkdir(parents=True, exist_ok=True)

        total_start = time.time()

        # ====================================================================
        # 使用 Orchestrator 统一接口（5-Agent + checkpoint）
        # ====================================================================
        print("🎯 初始化 Orchestrator（统一接口）...\n")

        orchestrator = Orchestrator(
            llm_interface=llm,
            workspace_root=experiment_workspace_root,
            show_progress=True,
            enable_code_gen=True,
            enable_checkpoint=True,  # 自动支持checkpoint
            code_llm_interface=code_llm  # 🆕 v4.0: 传入代码专用LLM
        )

        # 开始新会话
        session_id = orchestrator.start_new_session()
        print(f"✅ Session ID: {session_id}")
        print(f"   工作目录: {orchestrator.current_workspace}\n")

        # 执行完整流程（一行代码完成 5-Agent pipeline）
        print("🚀 开始执行完整流程...\n")
        result = orchestrator.process({
            "query": query,
            "use_mock": use_mock
        })

        total_elapsed = time.time() - total_start

        # ====================================================================
        # 展示结果
        # ====================================================================
        print("\n" + "=" * 70)
        print("执行结果")
        print("=" * 70)

        if result.get("success"):
            print("\n✅ 实验执行成功!\n")

            # Intent
            intent_data = result.get("intent", {}).get("intent_result", {})
            print("🔍 Intent识别:")
            print(f"   任务类型: {intent_data.get('task_type')}")
            print(f"   模型: {intent_data.get('model_name')}")
            print(f"   流域: {intent_data.get('basin_id')}")

            # Task Plan
            task_plan = result.get("task_plan", {})
            subtasks = task_plan.get("subtasks", [])
            print(f"\n📋 任务规划:")
            print(f"   子任务数量: {len(subtasks)}")

            # Execution
            execution_results = result.get("execution_results", [])
            successful = sum(1 for r in execution_results if r.get("success"))
            print(f"\n🚀 执行结果:")
            print(f"   成功: {successful}/{len(execution_results)}")

            # Analysis
            analysis = result.get("analysis", {}).get("analysis", {})
            print(f"\n📊 分析报告:")

            if "quality" in analysis:
                print(f"   质量评估: {analysis['quality']}")

            if "metrics" in analysis and analysis["metrics"]:
                print(f"   性能指标:")
                for key, value in analysis["metrics"].items():
                    print(f"      {key}: {value}")

            if "recommendations" in analysis and analysis["recommendations"]:
                print(f"   改进建议:")
                for i, rec in enumerate(analysis["recommendations"], 1):
                    print(f"      {i}. {rec}")

            # Timing
            print(f"\n  总耗时: {total_elapsed:.1f}s")
            print(f"   工作目录: {result['workspace']}")

            # Checkpoint info
            if orchestrator.checkpoint_manager:
                print(f"\n🔖 Checkpoint:")
                progress = orchestrator.checkpoint_manager.get_progress_summary()
                print(f"   进度: {progress['completed']}/{progress['total']} 任务完成")
                print(f"   文件: {orchestrator.checkpoint_manager.checkpoint_file}")

        else:
            # 失败情况：显示详细错误信息
            print(f"\n❌ 实验失败")
            print(f"\n错误类型: {result.get('error_type', 'Unknown')}")
            print(f"错误信息: {result.get('error', 'No error message')}")
            print(f"\n💡 详细日志文件: {log_file}")
            if result.get('workspace'):
                print(f"   工作目录: {result['workspace']}")
            print(f"   已执行时长: {total_elapsed:.1f}s")

        print("\n" + "=" * 70)

        # 添加实验元数据
        result["experiment"] = self.exp_name
        result["description"] = self.exp_description
        result["query"] = query
        result["mode"] = "mock" if use_mock else "real"
        result["elapsed_time"] = total_elapsed

        return result
