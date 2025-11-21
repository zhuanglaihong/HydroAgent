"""
Author: zhuanglaihong & Claude
Date: 2025-11-21 11:00:00
LastEditTime: 2025-11-21 11:00:00
LastEditors: Claude
Description: Full 4-Agent pipeline test: Intent → Config → Runner → Developer
             完整4-Agent管道测试：意图 → 配置 → 执行 → 分析
FilePath: \\HydroAgent\\scripts\\run_developer_agent_pipeline.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

import sys
import logging
import json
import argparse
import os
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
log_file = logs_dir / f"run_developer_agent_pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
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
║            HydroAgent 完整4-Agent管道测试                    ║
║     Intent → Config → Runner → Developer                    ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)
    print(f"日志文件: {log_file}\n")


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='完整4-Agent管道测试: Intent → Config → Runner → Developer'
    )
    parser.add_argument(
        'query',
        type=str,
        nargs='?',
        default="率定GR4J模型，流域01013500, 使用SCE-UA算法，算法迭代只需要500轮就行",
        help='用户查询（默认：率定GR4J模型）'
    )
    parser.add_argument(
        '--backend',
        type=str,
        default='ollama',
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
        '--save-config',
        action='store_true',
        help='保存配置到文件'
    )
    parser.add_argument(
        '--no-progress',
        action='store_true',
        help='不显示hydromodel执行进度（后台模式）'
    )
    parser.add_argument(
        '--save-analysis',
        action='store_true',
        help='保存分析结果到文件'
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


def run_full_pipeline(query: str, llm, llm_desc: str, use_mock: bool = False,
                      save_config: bool = False, show_progress: bool = True,
                      save_analysis: bool = False):
    """
    运行完整的4-Agent管道

    Args:
        query: 用户查询
        llm: LLM接口
        llm_desc: LLM描述
        use_mock: 是否使用Mock模式
        save_config: 是否保存配置
        show_progress: 是否显示进度
        save_analysis: 是否保存分析结果

    Returns:
        是否成功
    """
    from hydroagent.agents.intent_agent import IntentAgent
    from hydroagent.agents.config_agent import ConfigAgent
    from hydroagent.agents.runner_agent import RunnerAgent
    from hydroagent.agents.developer_agent import DeveloperAgent

    workspace_dir = project_root / "results" / datetime.now().strftime("%Y%m%d_%H%M%S")
    workspace_dir.mkdir(parents=True, exist_ok=True)

    intent_agent = IntentAgent(llm_interface=llm)
    config_agent = ConfigAgent(llm_interface=llm, workspace_dir=workspace_dir)
    runner_agent = RunnerAgent(
        llm_interface=llm,
        workspace_dir=workspace_dir,
        show_progress=show_progress
    )
    developer_agent = DeveloperAgent(
        llm_interface=llm,
        workspace_dir=workspace_dir,
        enable_code_gen=True
    )

    print("✅ 4个Agents初始化完成\n")

    total_start = time.time()

    # ========================================================================
    # Step 1: IntentAgent - 意图分析
    # ========================================================================
    print("🔍 [Step 1/4] IntentAgent - 分析用户意图...")
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
        print(f"  意图: {intent_data.get('intent', 'N/A').upper()}")
        print(f"  模型: {intent_data.get('model_name', 'N/A')}")
        print(f"  流域: {intent_data.get('basin_id', 'N/A')}")
        print(f"  算法: {intent_data.get('algorithm', 'SCE_UA')}")
        print()

    except Exception as e:
        print(f"❌ Intent分析异常: {str(e)}")
        logger.error(f"Intent分析异常: {str(e)}", exc_info=True)
        return False

    # ========================================================================
    # Step 2: ConfigAgent - 生成配置
    # ========================================================================
    print("⚙️  [Step 2/4] ConfigAgent - 生成hydromodel配置...")
    config_start = time.time()

    try:
        config_result = config_agent.process(intent_result)
        config_elapsed = time.time() - config_start

        if not config_result.get("success"):
            print(f"❌ Config生成失败: {config_result.get('error')}")
            return False

        print(f"✅ Config生成完成 ({config_elapsed:.1f}s)\n")

        # 显示配置摘要
        config_summary = config_result.get("config_summary", "")
        print("配置摘要:")
        print(config_summary)
        print()

        # 保存配置
        if save_config:
            config_file = workspace_dir / "generated_config.json"
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_result.get("config", {}), f, indent=2, ensure_ascii=False)
            print(f"💾 配置已保存: {config_file}\n")

    except Exception as e:
        print(f"❌ Config生成异常: {str(e)}")
        logger.error(f"Config生成异常: {str(e)}", exc_info=True)
        return False

    # ========================================================================
    # Step 3: RunnerAgent - 执行hydromodel
    # ========================================================================
    print("🚀 [Step 3/4] RunnerAgent - 执行hydromodel...")
    runner_start = time.time()

    try:
        if use_mock:
            # Mock模式
            print("   使用Mock模式（模拟执行）\n")

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
            print("   调用真实hydromodel API\n")
            runner_result = runner_agent.process(config_result)

        runner_elapsed = time.time() - runner_start

        if not runner_result.get("success"):
            print(f"❌ 执行失败: {runner_result.get('error')}")
            if traceback := runner_result.get('traceback'):
                print(f"\n错误详情:\n{traceback}")
            return False

        print(f"✅ 执行完成 ({runner_elapsed:.1f}s)\n")

        # 显示执行结果
        result_data = runner_result.get("result", {})
        metrics = result_data.get("metrics", {})
        if metrics:
            print("执行结果:")
            print("  性能指标:")
            for key, value in metrics.items():
                print(f"    {key}: {value}")
        if best_params := result_data.get("best_params"):
            print("  最优参数:")
            for key, value in best_params.items():
                print(f"    {key}: {value}")
        print()

    except Exception as e:
        print(f"❌ Runner执行异常: {str(e)}")
        logger.error(f"Runner执行异常: {str(e)}", exc_info=True)
        return False

    # ========================================================================
    # Step 4: DeveloperAgent - 结果分析
    # ========================================================================
    print("📊 [Step 4/4] DeveloperAgent - 分析结果...")
    developer_start = time.time()

    try:
        # DeveloperAgent自动接收RunnerAgent输出
        developer_result = developer_agent.process(runner_result)
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

        # 执行日志摘要
        if "execution_summary" in analysis:
            exec_sum = analysis["execution_summary"]
            print(f"\n📝 执行日志:")
            print(f"  输出行数: {exec_sum.get('stdout_lines', 0)}")
            print(f"  错误行数: {exec_sum.get('stderr_lines', 0)}")

        print("\n" + "=" * 70)

        # 保存分析结果
        if save_analysis:
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
    print("✅ 完整4-Agent管道执行成功!")
    print("=" * 70)
    print()
    print("时间统计:")
    print(f"  Intent分析: {intent_elapsed:.1f}s")
    print(f"  Config生成: {config_elapsed:.1f}s")
    print(f"  Runner执行: {runner_elapsed:.1f}s")
    print(f"  Developer分析: {developer_elapsed:.1f}s")
    print(f"  总计时间:   {total_elapsed:.1f}s")
    print()
    print(f"工作目录: {workspace_dir}")
    print(f"日志文件: {log_file}")
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

    # 运行完整管道
    success = run_full_pipeline(
        query=args.query,
        llm=llm,
        llm_desc=llm_desc,
        use_mock=args.mock,
        save_config=args.save_config,
        show_progress=not args.no_progress,
        save_analysis=args.save_analysis
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
