"""
Author: zhuanglaihong 
Date: 2025-11-13 20:00:00
LastEditTime: 2025-11-20 20:05:00
LastEditors: zhuanglaihong
Description: Provide a complete user interface, support elegant interruption and session recovery
FilePath: \HydroAgent\hydroagent\system.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import sys
import signal
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import json

from hydroagent.agents.orchestrator import Orchestrator
from hydroagent.core.llm_interface import LLMInterface

logger = logging.getLogger(__name__)


class HydroAgentSystem:
    """
    HydroAgent 系统主类
    提供用户友好的交互界面和会话管理
    """

    def __init__(
        self,
        backend: str = "api",
        workspace_dir: Optional[Path] = None,
        enable_checkpoint: bool = True
    ):
        """
        初始化 HydroAgent 系统

        Args:
            backend: LLM后端 ("api" 或 "ollama")
            workspace_dir: 工作目录
            enable_checkpoint: 是否启用checkpoint功能
        """
        self.backend = backend
        self.workspace_dir = workspace_dir or Path("experiment_results")
        self.enable_checkpoint = enable_checkpoint
        self.orchestrator: Optional[Orchestrator] = None
        self.current_session_id: Optional[str] = None
        self.interrupted = False

        # 注册信号处理器（优雅中断）
        signal.signal(signal.SIGINT, self._handle_interrupt)

        print("\n" + "=" * 70)
        print("🌊 欢迎使用 HydroAgent - 智能水文模型助手")
        print("=" * 70)

    def _handle_interrupt(self, signum, frame):
        """处理中断信号（Ctrl+C）"""
        self.interrupted = True
        print("\n\n⚠️  检测到中断信号...")
        print("正在安全保存当前进度...")

        if self.orchestrator and self.orchestrator.checkpoint_manager:
            checkpoint_file = self.orchestrator.checkpoint_manager.checkpoint_file
            print(f"✅ 进度已保存到: {checkpoint_file}")
            print(f"\n💡 恢复方式：")
            print(f"   python run.py --resume {checkpoint_file.parent}")
        else:
            print("⚠️  未检测到活动会话")

        print("\n👋 再见！")
        sys.exit(0)

    def initialize(self):
        """初始化系统组件"""
        try:
            print("\n⏳ 正在初始化系统...")

            # 创建 LLM 接口
            if self.backend == "api":
                print("  📡 连接到 API 后端 (Qwen)...")
                try:
                    from configs import definitions_private
                    api_key = definitions_private.OPENAI_API_KEY
                    base_url = definitions_private.OPENAI_BASE_URL
                except ImportError:
                    from configs import definitions
                    api_key = definitions.OPENAI_API_KEY
                    base_url = definitions.OPENAI_BASE_URL

                llm = LLMInterface(
                    backend="openai",
                    api_key=api_key,
                    base_url=base_url,
                    model_name="qwen-turbo"
                )

                # 代码生成专用 LLM
                code_llm = LLMInterface(
                    backend="openai",
                    api_key=api_key,
                    base_url=base_url,
                    model_name="qwen-coder-turbo"
                )

            elif self.backend == "ollama":
                print("  🖥️  连接到 Ollama 本地服务...")
                try:
                    from configs import definitions_private
                    base_url = definitions_private.OLLAMA_BASE_URL
                except (ImportError, AttributeError):
                    from configs import definitions
                    base_url = getattr(definitions, "OLLAMA_BASE_URL", "http://localhost:11434")

                llm = LLMInterface(
                    backend="ollama",
                    base_url=base_url,
                    model_name="qwen2.5:7b"
                )

                code_llm = LLMInterface(
                    backend="ollama",
                    base_url=base_url,
                    model_name="deepseek-coder:6.7b"
                )

            else:
                raise ValueError(f"Unknown backend: {self.backend}")

            # 创建 Orchestrator
            print("  🎯 初始化智能体编排器...")
            self.orchestrator = Orchestrator(
                llm_interface=llm,
                code_llm_interface=code_llm,
                enable_checkpoint=self.enable_checkpoint
            )

            print("✅ 系统初始化完成！\n")
            return True

        except Exception as e:
            print(f"❌ 初始化失败: {e}")
            logger.error(f"System initialization failed: {e}", exc_info=True)
            return False

    def show_welcome(self):
        """显示欢迎信息和功能菜单"""
        print("\n📚 HydroAgent 功能列表：")
        print("-" * 70)
        print("1️⃣  模型率定")
        print("   示例: 率定GR4J模型，流域01013500")
        print()
        print("2️⃣  模型评估")
        print("   示例: 评估流域01013500的率定结果")
        print()
        print("3️⃣  迭代优化")
        print("   示例: 用xaj模型率定流域01013500，如果参数收敛到边界，自动调整范围重新率定")
        print()
        print("4️⃣  自定义分析")
        print("   示例: 率定完成后，请帮我计算流域的径流系数，并画流量历时曲线FDC")
        print()
        print("5️⃣  稳定性验证")
        print("   示例: 重复率定流域01013500 5次，分析参数稳定性")
        print("-" * 70)
        print("\n💡 提示:")
        print("  - 输入 'help' 查看详细帮助")
        print("  - 输入 'examples' 查看更多示例")
        print("  - 输入 'history' 查看历史会话")
        print("  - 输入 'resume' 恢复上次中断的会话")
        print("  - 按 Ctrl+C 可随时优雅退出（进度会自动保存）")
        print("  - 输入 'exit' 或 'quit' 退出系统")
        print()

    def show_help(self):
        """显示详细帮助信息"""
        print("\n" + "=" * 70)
        print("📖 HydroAgent 详细帮助")
        print("=" * 70)

        print("\n🎯 支持的模型:")
        print("  - GR系列: GR4J, GR5J, GR6J")
        print("  - XAJ (新安江模型)")

        print("\n🔧 支持的算法:")
        print("  - SCE-UA: 适合复杂模型")
        print("  - GA (遗传算法): 适合多目标优化")
        print("  - PSO (粒子群算法): 快速收敛")
        print("  - DE (差分进化): 鲁棒性强")

        print("\n📊 性能指标:")
        print("  - NSE (Nash-Sutcliffe Efficiency)")
        print("  - RMSE (Root Mean Square Error)")
        print("  - KGE (Kling-Gupta Efficiency)")
        print("  - R² (Coefficient of Determination)")

        print("\n🆕 高级功能:")
        print("  - 自动迭代优化: 参数收敛到边界时自动调整范围")
        print("  - 代码生成: 支持自定义分析（径流系数、FDC、水量平衡等）")
        print("  - 双LLM架构: 通用LLM + 代码专用LLM")
        print("  - Checkpoint: 支持中断恢复")

        print("\n💬 自然语言支持:")
        print("  - 支持中英文混合输入")
        print("  - 自动识别模型、流域、算法等参数")
        print("  - 智能补全缺失信息")

        print("\n" + "=" * 70 + "\n")

    def show_examples(self):
        """显示示例查询"""
        print("\n" + "=" * 70)
        print("💡 查询示例")
        print("=" * 70)

        examples = [
            {
                "title": "基础率定",
                "query": "率定GR4J模型，流域01013500",
                "description": "使用默认参数率定模型"
            },
            {
                "title": "指定算法参数",
                "query": "使用SCE-UA算法率定流域01013500，算法迭代500轮",
                "description": "自定义算法参数"
            },
            {
                "title": "自定义时间段",
                "query": "率定xaj模型，流域01013500，训练期1990-2000，测试期2005-2010",
                "description": "指定训练和测试时间段"
            },
            {
                "title": "迭代优化",
                "query": "用xaj模型率定流域01013500，如果参数收敛到边界，自动调整范围重新率定",
                "description": "自适应参数范围调整"
            },
            {
                "title": "扩展分析",
                "query": "率定完成后，请帮我计算流域的径流系数，并画FDC曲线",
                "description": "率定 + 自定义代码分析"
            },
            {
                "title": "稳定性验证",
                "query": "重复率定流域01013500 5次，分析参数稳定性",
                "description": "多次重复实验"
            }
        ]

        for i, example in enumerate(examples, 1):
            print(f"\n{i}. {example['title']}")
            print(f"   查询: {example['query']}")
            print(f"   说明: {example['description']}")

        print("\n" + "=" * 70 + "\n")

    def list_history(self):
        """列出历史会话"""
        print("\n" + "=" * 70)
        print("📜 历史会话")
        print("=" * 70)

        try:
            sessions = []
            for exp_dir in self.workspace_dir.iterdir():
                if exp_dir.is_dir():
                    for session_dir in exp_dir.iterdir():
                        if session_dir.is_dir() and session_dir.name.startswith("session_"):
                            checkpoint_file = session_dir / "checkpoint.json"
                            if checkpoint_file.exists():
                                with open(checkpoint_file, 'r', encoding='utf-8') as f:
                                    checkpoint_data = json.load(f)
                                    sessions.append({
                                        "path": session_dir,
                                        "checkpoint": checkpoint_data
                                    })

            if not sessions:
                print("\n  暂无历史会话")
            else:
                # 按时间排序
                sessions.sort(key=lambda x: x["checkpoint"].get("created_at", ""), reverse=True)

                for i, session in enumerate(sessions[:10], 1):  # 最多显示10个
                    checkpoint = session["checkpoint"]
                    status = checkpoint.get("status", "unknown")
                    query = checkpoint.get("query", "N/A")
                    created = checkpoint.get("created_at", "N/A")

                    # 状态图标
                    status_icon = {
                        "completed": "✅",
                        "pending": "⏸️",
                        "failed": "❌"
                    }.get(status, "❓")

                    print(f"\n{i}. {status_icon} {session['path'].name}")
                    print(f"   查询: {query[:60]}{'...' if len(query) > 60 else ''}")
                    print(f"   时间: {created[:19] if len(created) > 19 else created}")
                    print(f"   状态: {status}")
                    print(f"   路径: {session['path']}")

                if len(sessions) > 10:
                    print(f"\n  ... 还有 {len(sessions) - 10} 个历史会话")

        except Exception as e:
            print(f"\n  ❌ 读取历史失败: {e}")

        print("\n" + "=" * 70 + "\n")

    def resume_session(self, session_path: Optional[str] = None):
        """恢复会话"""
        try:
            if session_path:
                resume_path = Path(session_path)
            else:
                # 查找最近的未完成会话
                print("🔍 查找最近的未完成会话...")
                resume_path = None

                for exp_dir in sorted(self.workspace_dir.iterdir(), reverse=True):
                    if exp_dir.is_dir():
                        for session_dir in sorted(exp_dir.iterdir(), reverse=True):
                            checkpoint_file = session_dir / "checkpoint.json"
                            if checkpoint_file.exists():
                                with open(checkpoint_file, 'r', encoding='utf-8') as f:
                                    data = json.load(f)
                                    if data.get("status") == "pending":
                                        resume_path = session_dir
                                        break
                    if resume_path:
                        break

                if not resume_path:
                    print("❌ 未找到可恢复的会话")
                    return

            print(f"\n📂 恢复会话: {resume_path}")

            # 初始化系统
            if not self.orchestrator:
                if not self.initialize():
                    return

            # 恢复会话
            result = self.orchestrator.process(
                query="",  # 空查询表示恢复
                resume_from=resume_path
            )

            self._display_result(result)

        except Exception as e:
            print(f"❌ 恢复会话失败: {e}")
            logger.error(f"Resume session failed: {e}", exc_info=True)

    def process_query(self, query: str):
        """处理用户查询"""
        try:
            # 初始化系统（如果未初始化）
            if not self.orchestrator:
                if not self.initialize():
                    return

            print("\n" + "=" * 70)
            print(f"📝 查询: {query}")
            print("=" * 70)
            print("\n⏳ 正在处理您的请求...\n")

            # 处理查询
            result = self.orchestrator.process(query=query)

            # 显示结果
            self._display_result(result)

        except Exception as e:
            print(f"\n❌ 处理失败: {e}")
            logger.error(f"Query processing failed: {e}", exc_info=True)

    def _display_result(self, result: Dict[str, Any]):
        """显示执行结果"""
        print("\n" + "=" * 70)
        print("📊 执行结果")
        print("=" * 70)

        if result.get("success"):
            print("\n✅ 任务完成！")

            # 显示摘要
            summary = result.get("summary", "")
            if summary:
                print("\n" + summary)

            # 显示工作目录
            workspace = result.get("workspace", "")
            if workspace:
                print(f"\n📁 结果目录: {workspace}")

            # 显示耗时
            elapsed = result.get("elapsed_time", 0)
            if elapsed:
                print(f"⏱️  耗时: {elapsed:.1f}秒")

        else:
            print("\n❌ 任务失败")
            error = result.get("error", "未知错误")
            print(f"错误: {error}")

        print("\n" + "=" * 70 + "\n")

    def run_interactive(self):
        """运行交互式会话"""
        self.show_welcome()

        while not self.interrupted:
            try:
                # 读取用户输入
                user_input = input("💬 HydroAgent> ").strip()

                if not user_input:
                    continue

                # 处理特殊命令
                if user_input.lower() in ['exit', 'quit', 'q']:
                    print("\n👋 再见！")
                    break

                elif user_input.lower() == 'help':
                    self.show_help()

                elif user_input.lower() == 'examples':
                    self.show_examples()

                elif user_input.lower() == 'history':
                    self.list_history()

                elif user_input.lower() == 'resume':
                    self.resume_session()

                elif user_input.lower() == 'clear':
                    import os
                    os.system('cls' if os.name == 'nt' else 'clear')
                    self.show_welcome()

                else:
                    # 处理查询
                    self.process_query(user_input)

            except EOFError:
                print("\n\n👋 再见！")
                break

            except Exception as e:
                print(f"\n❌ 发生错误: {e}")
                logger.error(f"Interactive loop error: {e}", exc_info=True)

    def run_single_query(self, query: str, resume_from: Optional[str] = None):
        """运行单个查询（非交互模式）"""
        if resume_from:
            self.resume_session(resume_from)
        else:
            self.process_query(query)


def setup_logging(log_level: str = "INFO", log_file: Optional[Path] = None):
    """配置日志系统"""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    handlers = [logging.StreamHandler()]

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding='utf-8'))

    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        handlers=handlers
    )
