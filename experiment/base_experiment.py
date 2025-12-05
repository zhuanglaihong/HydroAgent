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
        self.workspace = None  # 将在 setup() 时初始化

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
        """
        创建实验批次工作目录。

        目录结构:
        experiment_results/
        └── exp_1a_standard_calibration/
            └── 20251205_010000/              # 本次批量执行
                ├── data/                     # 汇总数据
                ├── plots/                    # 汇总图表
                ├── reports/                  # 汇总报告
                └── session_xxx/              # Orchestrator创建的单任务目录
        """
        workspace_dir = (
            self.project_root
            / "experiment_results"
            / self.exp_name
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

        # 🔧 确保工作目录已创建（用于存放所有session）
        # 如果 run_batch 已调用 setup()，self.workspace 已存在
        # 如果单独调用 run_experiment()，需要创建
        if not self.workspace:
            self.workspace = self.create_workspace()

        total_start = time.time()

        # ====================================================================
        # 使用 Orchestrator 统一接口（5-Agent + checkpoint）
        # ====================================================================
        print("🎯 初始化 Orchestrator（统一接口）...\n")

        orchestrator = Orchestrator(
            llm_interface=llm,
            workspace_root=self.workspace,  # 使用统一的workspace
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
            "use_mock": use_mock,
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
                progress = orchestrator.checkpoint_manager.get_progress_summary()
                if progress:  # 检查是否为空字典
                    print(f"\n🔖 Checkpoint:")
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

        # 🆕 添加 Token 使用统计
        result["token_usage"] = llm.get_token_usage()
        if code_llm:
            result["code_token_usage"] = code_llm.get_token_usage()

        return result

    def run_batch(self, queries: list, backend: str = "api", use_mock: bool = True):
        """
        批量执行多个查询。

        Args:
            queries: 查询列表
            backend: LLM后端 ("api" or "ollama")
            use_mock: 是否使用Mock模式

        Returns:
            结果列表
        """
        from hydroagent.core.llm_interface import create_llm_interface
        from configs.config import (
            DEFAULT_MODEL,
            DEFAULT_CODE_MODEL,
            OLLAMA_DEFAULT_MODEL,
            OLLAMA_DEFAULT_CODE_MODEL
        )
        from configs.definitions import OPENAI_API_KEY, OPENAI_BASE_URL

        # 🔧 在批量执行开始时设置工作目录（用于保存汇总结果）
        if not self.workspace:
            self.setup()

        # 初始化LLM
        if backend == "api":
            llm = create_llm_interface(
                backend="openai",
                model_name=DEFAULT_MODEL,
                api_key=OPENAI_API_KEY,
                base_url=OPENAI_BASE_URL
            )
            code_llm = create_llm_interface(
                backend="openai",
                model_name=DEFAULT_CODE_MODEL,
                api_key=OPENAI_API_KEY,
                base_url=OPENAI_BASE_URL
            )
        else:
            llm = create_llm_interface(backend="ollama", model_name=OLLAMA_DEFAULT_MODEL)
            code_llm = create_llm_interface(backend="ollama", model_name=OLLAMA_DEFAULT_CODE_MODEL)

        results = []
        total_queries = len(queries)

        print(f"\n🚀 开始批量执行 {total_queries} 个查询...")
        print(f"   后端: {backend}")
        print(f"   Mock模式: {use_mock}")
        print(f"   汇总目录: {self.workspace}")
        print("=" * 70)

        for i, query in enumerate(queries, 1):
            print(f"\n[{i}/{total_queries}] 执行查询: {query}")

            try:
                result = self.run_experiment(
                    query=query,
                    llm=llm,
                    use_mock=use_mock,
                    code_llm=code_llm
                )
                results.append(result)

                if result.get("success"):
                    print(f"[{i}/{total_queries}] ✅ 成功")
                else:
                    print(f"[{i}/{total_queries}] ❌ 失败: {result.get('error', 'Unknown error')}")

            except Exception as e:
                print(f"[{i}/{total_queries}] ❌ 异常: {str(e)}")
                results.append({
                    "success": False,
                    "query": query,
                    "error": str(e),
                    "experiment": self.exp_name,
                    "mode": "mock" if use_mock else "real"
                })

        print("\n" + "=" * 70)
        print(f"📊 批量执行完成:")
        successful = sum(1 for r in results if r.get("success"))
        print(f"   成功: {successful}/{total_queries}")
        print(f"   失败: {total_queries - successful}/{total_queries}")

        # 🆕 显示 Token 使用统计
        print(f"\n📈 Token 使用统计:")
        main_llm_stats = llm.get_token_usage()
        print(f"   主模型 ({llm.model_name}):")
        print(f"      总调用次数: {main_llm_stats['total_calls']}")
        print(f"      总 tokens: {main_llm_stats['total_tokens']:,}")
        print(f"         - Prompt: {main_llm_stats['total_prompt_tokens']:,}")
        print(f"         - Completion: {main_llm_stats['total_completion_tokens']:,}")
        print(f"      平均每次调用: {main_llm_stats['average_tokens_per_call']:.1f} tokens")

        if code_llm:
            code_llm_stats = code_llm.get_token_usage()
            if code_llm_stats['total_calls'] > 0:
                print(f"\n   代码模型 ({code_llm.model_name}):")
                print(f"      总调用次数: {code_llm_stats['total_calls']}")
                print(f"      总 tokens: {code_llm_stats['total_tokens']:,}")
                print(f"         - Prompt: {code_llm_stats['total_prompt_tokens']:,}")
                print(f"         - Completion: {code_llm_stats['total_completion_tokens']:,}")
                print(f"      平均每次调用: {code_llm_stats['average_tokens_per_call']:.1f} tokens")

        # 🆕 导出 Token 统计到文件
        from hydroagent.utils.token_stats import export_token_stats
        export_token_stats(llm, self.workspace / "data", f"{self.exp_name}_main_llm")
        if code_llm:
            export_token_stats(code_llm, self.workspace / "data", f"{self.exp_name}_code_llm")

        print("=" * 70)

        return results

    def setup(self):
        """设置实验工作目录。"""
        self.workspace = self.create_workspace()
        (self.workspace / "data").mkdir(exist_ok=True)
        (self.workspace / "plots").mkdir(exist_ok=True)
        (self.workspace / "reports").mkdir(exist_ok=True)
        print(f"✅ 工作目录已创建: {self.workspace}")
        return self.workspace

    def save_results(self, results: list, filename: str = "results"):
        """
        保存实验结果到JSON和CSV。

        Args:
            results: 结果列表
            filename: 文件名（不含扩展名）
        """
        if not self.workspace:
            self.setup()

        # 清理results，确保可序列化
        from hydroagent.utils.result_serializer import sanitize_results
        results = sanitize_results(results)

        # 保存JSON（完整数据）
        json_file = self.workspace / "data" / f"{filename}.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"✅ 保存JSON: {json_file}")

        # 保存CSV（摘要数据，包含 Token 统计）
        import pandas as pd
        csv_data = []
        for r in results:
            token_usage = r.get("token_usage", {})
            row = {
                "query": r.get("query", ""),
                "success": r.get("success", False),
                "elapsed_time": r.get("elapsed_time", 0),
                "mode": r.get("mode", ""),
                # 🆕 添加 Token 统计列
                "total_tokens": token_usage.get("total_tokens", 0) if token_usage else 0,
                "prompt_tokens": token_usage.get("total_prompt_tokens", 0) if token_usage else 0,
                "completion_tokens": token_usage.get("total_completion_tokens", 0) if token_usage else 0,
                "api_calls": token_usage.get("total_calls", 0) if token_usage else 0,
                "error": r.get("error", "")
            }
            csv_data.append(row)

        df = pd.DataFrame(csv_data)
        csv_file = self.workspace / "data" / f"{filename}.csv"
        df.to_csv(csv_file, index=False, encoding="utf-8-sig")
        print(f"✅ 保存CSV: {csv_file}")

        return json_file, csv_file

    def calculate_metrics(self, results: list) -> dict:
        """
        计算评估指标（包括时间和Token统计）。

        Args:
            results: 结果列表

        Returns:
            指标字典
        """
        import numpy as np

        total = len(results)
        if total == 0:
            return {}

        success_count = sum(1 for r in results if r.get("success"))
        times = [r.get("elapsed_time", 0) for r in results]

        # 🆕 统计 Token 使用
        total_tokens = []
        total_prompt_tokens = []
        total_completion_tokens = []
        total_calls = []

        for r in results:
            token_usage = r.get("token_usage", {})
            if token_usage and token_usage.get("total_tokens", 0) > 0:
                total_tokens.append(token_usage.get("total_tokens", 0))
                total_prompt_tokens.append(token_usage.get("total_prompt_tokens", 0))
                total_completion_tokens.append(token_usage.get("total_completion_tokens", 0))
                total_calls.append(token_usage.get("total_calls", 0))

        metrics = {
            # 任务统计
            "total_tasks": total,
            "success_count": success_count,
            "failure_count": total - success_count,
            "success_rate": success_count / total,

            # 时间统计
            "average_time": float(np.mean(times)),
            "median_time": float(np.median(times)),
            "std_time": float(np.std(times)),
            "min_time": float(np.min(times)),
            "max_time": float(np.max(times)),

            # 🆕 Token 统计
            "total_tokens_sum": int(np.sum(total_tokens)) if total_tokens else 0,
            "average_tokens_per_task": float(np.mean(total_tokens)) if total_tokens else 0,
            "total_prompt_tokens_sum": int(np.sum(total_prompt_tokens)) if total_prompt_tokens else 0,
            "total_completion_tokens_sum": int(np.sum(total_completion_tokens)) if total_completion_tokens else 0,
            "average_api_calls_per_task": float(np.mean(total_calls)) if total_calls else 0,
        }

        return metrics

    def save_metrics(self, metrics: dict, filename: str = "metrics"):
        """保存评估指标。"""
        if not self.workspace:
            self.setup()

        metrics_file = self.workspace / "data" / f"{filename}.json"
        with open(metrics_file, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)
        print(f"✅ 保存指标: {metrics_file}")

        return metrics_file

    def generate_report(
        self,
        results: list,
        metrics: dict = None,
        additional_sections: dict = None
    ):
        """
        生成实验报告（Markdown格式）。

        Args:
            results: 结果列表
            metrics: 评估指标（可选）
            additional_sections: 额外的报告章节（可选）
        """
        if not self.workspace:
            self.setup()

        report_file = self.workspace / "reports" / "experiment_report.md"

        # 生成报告内容
        lines = []
        lines.append(f"# {self.exp_description}")
        lines.append(f"\n实验名称: `{self.exp_name}`")
        lines.append(f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("\n---\n")

        # 基本统计
        lines.append("## 实验统计\n")
        if metrics:
            lines.append(f"- **总任务数**: {metrics.get('total_tasks', 0)}")
            lines.append(f"- **成功数**: {metrics.get('success_count', 0)}")
            lines.append(f"- **失败数**: {metrics.get('failure_count', 0)}")
            lines.append(f"- **成功率**: {metrics.get('success_rate', 0):.1%}")

            # 时间统计
            lines.append(f"\n### 时间统计\n")
            lines.append(f"- **平均耗时**: {metrics.get('average_time', 0):.1f}s")
            lines.append(f"- **中位耗时**: {metrics.get('median_time', 0):.1f}s")
            lines.append(f"- **最短耗时**: {metrics.get('min_time', 0):.1f}s")
            lines.append(f"- **最长耗时**: {metrics.get('max_time', 0):.1f}s")
            lines.append(f"- **标准差**: {metrics.get('std_time', 0):.1f}s")

            # 🆕 Token 统计
            if metrics.get('total_tokens_sum', 0) > 0:
                lines.append(f"\n### Token 使用统计\n")
                lines.append(f"- **总 Token 数**: {metrics.get('total_tokens_sum', 0):,}")
                lines.append(f"- **平均每任务**: {metrics.get('average_tokens_per_task', 0):.0f} tokens")
                lines.append(f"- **Prompt Tokens**: {metrics.get('total_prompt_tokens_sum', 0):,}")
                lines.append(f"- **Completion Tokens**: {metrics.get('total_completion_tokens_sum', 0):,}")
                lines.append(f"- **平均API调用数**: {metrics.get('average_api_calls_per_task', 0):.1f} 次/任务")

        # 额外章节
        if additional_sections:
            for title, content in additional_sections.items():
                lines.append(f"\n## {title}\n")
                lines.append(content)

        # 写入文件
        with open(report_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        print(f"✅ 生成报告: {report_file}")
        return report_file

    def plot_results(self, results: list, plot_type: str = "success_rate"):
        """
        生成可视化图表。

        Args:
            results: 结果列表
            plot_type: 图表类型 ("success_rate", "time_distribution")
        """
        if not self.workspace:
            self.setup()

        import matplotlib.pyplot as plt
        import matplotlib
        matplotlib.use('Agg')  # 使用非交互式后端

        if plot_type == "success_rate":
            # 成功率饼图
            success_count = sum(1 for r in results if r.get("success"))
            failure_count = len(results) - success_count

            fig, ax = plt.subplots(figsize=(8, 6))
            ax.pie(
                [success_count, failure_count],
                labels=["成功", "失败"],
                autopct="%1.1f%%",
                colors=["#4CAF50", "#F44336"]
            )
            ax.set_title("任务成功率")

            plot_file = self.workspace / "plots" / "success_rate.png"
            plt.savefig(plot_file, dpi=150, bbox_inches="tight")
            plt.close()

            print(f"✅ 生成图表: {plot_file}")

        elif plot_type == "time_distribution":
            # 时间分布直方图
            times = [r.get("elapsed_time", 0) for r in results if r.get("success")]

            fig, ax = plt.subplots(figsize=(10, 6))
            ax.hist(times, bins=20, color="#2196F3", alpha=0.7, edgecolor="black")
            ax.set_xlabel("执行时间 (秒)")
            ax.set_ylabel("频次")
            ax.set_title("任务执行时间分布")
            ax.grid(True, alpha=0.3)

            plot_file = self.workspace / "plots" / "time_distribution.png"
            plt.savefig(plot_file, dpi=150, bbox_inches="tight")
            plt.close()

            print(f"✅ 生成图表: {plot_file}")

        return plot_file


def create_experiment(exp_name: str, exp_description: str) -> BaseExperiment:
    """
    工厂函数：创建实验对象。

    Args:
        exp_name: 实验名称（如 "exp_1a_standard_calibration"）
        exp_description: 实验描述（如 "标准率定测试"）

    Returns:
        BaseExperiment 实例
    """
    return BaseExperiment(exp_name=exp_name, exp_description=exp_description)
