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
        运行完整的实验流程（5-Agent pipeline）。

        Args:
            query: 用户查询
            llm: LLM接口（通用模型）
            use_mock: 是否使用Mock模式
            code_llm: 代码专用LLM接口（可选）
                如果提供，DeveloperAgent将使用此模型生成代码
                例如: qwen-coder-turbo, deepseek-coder:6.7b

        Returns:
            实验结果字典
        """
        from hydroagent.agents.intent_agent import IntentAgent
        from hydroagent.agents.task_planner import TaskPlanner
        from hydroagent.agents.interpreter_agent import InterpreterAgent
        from hydroagent.agents.runner_agent import RunnerAgent
        from hydroagent.agents.developer_agent import DeveloperAgent
        from hydroagent.core.prompt_pool import PromptPool

        print("\n" + "=" * 70)
        print(f"【{self.exp_description}】")
        print("=" * 70)
        print(f"查询: {query}")
        print(f"模式: {'Mock (模拟)' if use_mock else 'Real (真实hydromodel)'}")
        print()

        # 创建工作目录
        workspace_dir = self.create_workspace()
        print(f"工作目录: {workspace_dir}\n")

        total_start = time.time()
        results = {
            "experiment": self.exp_name,
            "description": self.exp_description,
            "query": query,
            "mode": "mock" if use_mock else "real",
            "workspace": str(workspace_dir),
            "start_time": datetime.now().isoformat(),
        }

        # ====================================================================
        # Step 1: IntentAgent
        # ====================================================================
        print("🔍 [Step 1/5] IntentAgent - 分析用户意图...")
        intent_start = time.time()

        intent_agent = IntentAgent(llm_interface=llm)
        intent_result = intent_agent.process({"query": query})

        intent_elapsed = time.time() - intent_start

        if not intent_result.get("success"):
            print(f"❌ Intent分析失败: {intent_result.get('error')}")
            results["success"] = False
            results["error"] = f"IntentAgent failed: {intent_result.get('error')}"
            return results

        intent_data = intent_result["intent_result"]
        results["intent"] = intent_data

        print(f"✅ Intent分析完成 ({intent_elapsed:.1f}s)")
        print(f"   任务类型: {intent_data.get('task_type')}")
        print(f"   模型: {intent_data.get('model_name')}")
        print(f"   流域: {intent_data.get('basin_id')}")
        print()

        # 保存Intent结果
        with open(workspace_dir / "intent_result.json", "w", encoding="utf-8") as f:
            json.dump(intent_result, f, indent=2, ensure_ascii=False)

        # ====================================================================
        # Step 2: TaskPlanner
        # ====================================================================
        print("📋 [Step 2/5] TaskPlanner - 任务拆解...")
        planner_start = time.time()

        prompt_pool = PromptPool(pool_dir=workspace_dir / "prompt_pool")
        task_planner = TaskPlanner(
            llm_interface=llm, prompt_pool=prompt_pool, workspace_dir=workspace_dir
        )

        planner_result = task_planner.process({"intent_result": intent_data})

        planner_elapsed = time.time() - planner_start

        if not planner_result.get("success"):
            print(f"❌ 任务规划失败: {planner_result.get('error')}")
            results["success"] = False
            results["error"] = f"TaskPlanner failed: {planner_result.get('error')}"
            return results

        task_plan = planner_result["task_plan"]
        subtasks = task_plan["subtasks"]
        results["task_plan"] = task_plan

        print(f"✅ 任务规划完成 ({planner_elapsed:.1f}s)")
        print(f"   子任务数量: {len(subtasks)}")
        for i, subtask in enumerate(subtasks, 1):
            print(f"   [{i}] {subtask['task_id']}: {subtask.get('description', 'N/A')}")
        print()

        # 保存任务计划
        with open(workspace_dir / "task_plan.json", "w", encoding="utf-8") as f:
            json.dump(planner_result, f, indent=2, ensure_ascii=False)

        # ====================================================================
        # Step 3: InterpreterAgent
        # ====================================================================
        print("🔧 [Step 3/5] InterpreterAgent - 生成配置...")
        interpreter_start = time.time()

        interpreter = InterpreterAgent(llm_interface=llm, workspace_dir=workspace_dir)

        configs = []
        for i, subtask in enumerate(subtasks, 1):
            print(f"   [{i}/{len(subtasks)}] 生成配置: {subtask['task_id']}...")

            config_result = interpreter.process(
                {"subtask": subtask, "intent_result": intent_data}
            )

            if not config_result.get("success"):
                print(f"❌ 配置生成失败: {config_result.get('error')}")
                results["success"] = False
                results["error"] = f"InterpreterAgent failed: {config_result.get('error')}"
                return results

            configs.append(config_result)

        interpreter_elapsed = time.time() - interpreter_start
        results["configs"] = configs

        print(f"✅ 所有配置生成完成 ({interpreter_elapsed:.1f}s)\n")

        # 保存配置
        for i, config_result in enumerate(configs, 1):
            with open(workspace_dir / f"config_{i}.json", "w", encoding="utf-8") as f:
                json.dump(config_result["config"], f, indent=2, ensure_ascii=False)

        # ====================================================================
        # Step 4: RunnerAgent
        # ====================================================================
        print("🚀 [Step 4/5] RunnerAgent - 执行任务...")
        runner_start = time.time()

        runner_agent = RunnerAgent(
            llm_interface=llm, workspace_dir=workspace_dir, show_progress=True
        )

        execution_results = []

        if use_mock:
            print("   使用Mock模式（模拟执行）\n")
            from unittest.mock import patch, Mock, MagicMock

            mock_result = {
                "best_params": {"x1": 350.0, "x2": 0.5, "x3": 100.0, "x4": 2.0},
                "metrics": {"NSE": 0.68, "RMSE": 2.5, "KGE": 0.65, "PBIAS": 5.2},
                "output_files": ["calibration_results.json"],
            }

            mock_hydromodel = MagicMock()
            mock_hydromodel.calibrate = Mock(return_value=mock_result)
            mock_hydromodel.evaluate = Mock(return_value=mock_result)

            with patch.dict("sys.modules", {"hydromodel": mock_hydromodel}):
                for i, config_result in enumerate(configs, 1):
                    print(f"   [{i}/{len(configs)}] 执行: {config_result['task_id']}...")
                    runner_result = runner_agent.process(config_result)

                    if not runner_result.get("success"):
                        print(f"❌ 执行失败: {runner_result.get('error')}")
                        results["success"] = False
                        results["error"] = (
                            f"RunnerAgent failed: {runner_result.get('error')}"
                        )
                        return results

                    execution_results.append(runner_result)
        else:
            print("   调用真实hydromodel API\n")
            for i, config_result in enumerate(configs, 1):
                print(f"   [{i}/{len(configs)}] 执行: {config_result['task_id']}...")
                runner_result = runner_agent.process(config_result)

                if not runner_result.get("success"):
                    print(f"❌ 执行失败: {runner_result.get('error')}")
                    results["success"] = False
                    results["error"] = f"RunnerAgent failed: {runner_result.get('error')}"
                    return results

                execution_results.append(runner_result)

        runner_elapsed = time.time() - runner_start
        results["execution_results"] = execution_results

        print(f"✅ 所有任务执行完成 ({runner_elapsed:.1f}s)\n")

        # ====================================================================
        # Step 5: DeveloperAgent
        # ====================================================================
        print("📊 [Step 5/5] DeveloperAgent - 结果分析...")
        developer_start = time.time()

        developer_agent = DeveloperAgent(
            llm_interface=llm,
            workspace_dir=workspace_dir,
            enable_code_gen=True,
            code_llm_interface=code_llm  # 🆕 传入代码专用LLM
        )

        combined_result = execution_results[0] if execution_results else {}
        developer_result = developer_agent.process(combined_result)

        developer_elapsed = time.time() - developer_start
        results["analysis"] = developer_result

        if not developer_result.get("success"):
            print(f"❌ 结果分析失败: {developer_result.get('error')}")
            results["success"] = False
            results["error"] = f"DeveloperAgent failed: {developer_result.get('error')}"
            return results

        print(f"✅ 分析完成 ({developer_elapsed:.1f}s)\n")

        # 显示分析结果
        analysis = developer_result.get("analysis", {})
        print("=" * 70)
        print("分析报告:")
        print("=" * 70)

        if "quality" in analysis:
            print(f"\n📈 质量评估: {analysis['quality']}")

        if "metrics" in analysis and analysis["metrics"]:
            print("\n🎯 性能指标:")
            for key, value in analysis["metrics"].items():
                print(f"  {key}: {value}")

        if "recommendations" in analysis and analysis["recommendations"]:
            print(f"\n💡 改进建议:")
            for i, rec in enumerate(analysis["recommendations"], 1):
                print(f"  {i}. {rec}")

        print("\n" + "=" * 70)

        # 保存分析结果
        with open(workspace_dir / "analysis_report.json", "w", encoding="utf-8") as f:
            json.dump(developer_result, f, indent=2, ensure_ascii=False)

        # ====================================================================
        # 总结
        # ====================================================================
        total_elapsed = time.time() - total_start

        results["success"] = True
        results["end_time"] = datetime.now().isoformat()
        results["timing"] = {
            "intent": intent_elapsed,
            "planner": planner_elapsed,
            "interpreter": interpreter_elapsed,
            "runner": runner_elapsed,
            "developer": developer_elapsed,
            "total": total_elapsed,
        }

        print("\n" + "=" * 70)
        print(f"✅ {self.exp_description}执行成功!")
        print("=" * 70)
        print("\n时间统计:")
        print(f"  IntentAgent:      {intent_elapsed:.1f}s")
        print(f"  TaskPlanner:      {planner_elapsed:.1f}s")
        print(f"  InterpreterAgent: {interpreter_elapsed:.1f}s")
        print(f"  RunnerAgent:      {runner_elapsed:.1f}s")
        print(f"  DeveloperAgent:   {developer_elapsed:.1f}s")
        print(f"  总计时间:         {total_elapsed:.1f}s")
        print()
        print(f"工作目录: {workspace_dir}")
        print("=" * 70)

        # 保存完整结果
        with open(workspace_dir / "experiment_result.json", "w", encoding="utf-8") as f:
            # 移除不能序列化的对象
            save_results = {
                k: v
                for k, v in results.items()
                if k not in ["execution_results", "analysis"]
            }
            save_results["metrics"] = analysis.get("metrics", {})
            save_results["quality"] = analysis.get("quality", "N/A")
            json.dump(save_results, f, indent=2, ensure_ascii=False)

        return results
