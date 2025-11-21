"""
Author: zhuanglaihong & Claude
Date: 2025-11-20 23:00:00
LastEditTime: 2025-11-20 23:00:00
LastEditors: Claude
Description: Full pipeline test: Intent → Config → Runner
             完整管道测试：意图 → 配置 → 执行
FilePath: \\HydroAgent\\scripts\\run_runner_agent_pipeline.py
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

# 确保logs目录存在
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

# 设置详细日志
log_file = logs_dir / f"full_pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
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
    """打印欢迎横幅"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║            HydroAgent 完整管道测试                           ║
║     Intent → Config → Runner (3-Agent Pipeline)             ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)
    print(f"日志文件: {log_file}\n")


def print_separator(char="═", length=70):
    """打印分隔线"""
    print(char * length)


def format_time(seconds):
    """格式化时间"""
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    else:
        return f"{seconds/60:.1f}min"


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='完整管道测试: Intent → Config → Runner'
    )
    parser.add_argument(
        'query',
        type=str,
        nargs='?',
        default="率定GR4J模型，流域ID为01013500, 使用SCE-UA算法",
        help='用户查询'
    )
    parser.add_argument(
        '--backend',
        type=str,
        default='api',
        choices=['ollama', 'openai', 'api'],
        help='LLM后端 (default: ollama)'
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
    return parser.parse_args()


def load_config():
    """从配置文件加载API设置"""
    try:
        from configs import definitions_private as config
    except ImportError:
        from configs import definitions as config

    return {
        'api_key': getattr(config, 'OPENAI_API_KEY', None),
        'base_url': getattr(config, 'OPENAI_BASE_URL', None),
    }


def create_llm(backend, model_name=None):
    """创建LLM接口"""
    from hydroagent.core.llm_interface import create_llm_interface

    config = load_config()

    if backend == 'api':
        backend = 'openai'

    # 确定模型名称
    if model_name is None:
        model_name = 'qwen3:8b' if backend == 'ollama' else 'qwen-turbo'

    # 创建LLM接口
    if backend == 'ollama':
        llm = create_llm_interface('ollama', model_name)
        return llm, f"Ollama ({model_name})"
    elif backend == 'openai':
        api_key = config.get('api_key') or os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("API key未配置")

        kwargs = {'api_key': api_key}
        if base_url := config.get('base_url'):
            kwargs['base_url'] = base_url

        llm = create_llm_interface('openai', model_name, **kwargs)
        return llm, f"OpenAI ({model_name})"
    else:
        raise ValueError(f"不支持的后端: {backend}")


def run_full_pipeline(query: str, llm, llm_desc: str, use_mock: bool = False, save_config: bool = False, show_progress: bool = True):
    """
    运行完整的3-Agent管道

    Args:
        query: 用户查询
        llm: LLM接口
        llm_desc: LLM描述
        use_mock: 是否使用Mock模式
        save_config: 是否保存配置
    """
    print_separator()
    print(f"查询: {query}")
    print(f"LLM: {llm_desc}")
    print(f"模式: {'Mock (不调用真实hydromodel)' if use_mock else 'Real'}")
    print_separator()
    print()

    # 初始化agents
    from hydroagent.agents.intent_agent import IntentAgent
    from hydroagent.agents.config_agent import ConfigAgent
    from hydroagent.agents.runner_agent import RunnerAgent

    workspace_dir = project_root / "results" / datetime.now().strftime("%Y%m%d_%H%M%S")
    workspace_dir.mkdir(parents=True, exist_ok=True)

    intent_agent = IntentAgent(llm_interface=llm)
    config_agent = ConfigAgent(llm_interface=llm, workspace_dir=workspace_dir)
    runner_agent = RunnerAgent(
        llm_interface=llm,
        workspace_dir=workspace_dir,
        show_progress=show_progress  # 控制是否显示hydromodel进度条
    )

    print("✅ Agents初始化完成\n")

    total_start = time.time()

    # ========================================================================
    # Step 1: IntentAgent - 意图分析
    # ========================================================================
    print("🔍 [Step 1/3] IntentAgent - 分析用户意图...")
    intent_start = time.time()

    try:
        intent_result = intent_agent.process({"query": query})
        intent_elapsed = time.time() - intent_start

        if not intent_result.get("success"):
            print(f"❌ Intent分析失败: {intent_result.get('error')}")
            return False

        print(f"✅ Intent分析完成 ({format_time(intent_elapsed)})")
        print(f"\n意图摘要:")
        intent = intent_result["intent_result"]
        print(f"  意图: {intent.get('intent').upper()}")
        print(f"  模型: {intent.get('model_name')}")
        print(f"  流域: {intent.get('basin_id')}")
        print(f"  算法: {intent.get('algorithm')}")
        print()

    except Exception as e:
        print(f"❌ Intent分析异常: {str(e)}")
        logger.error("Intent分析失败", exc_info=True)
        return False

    # ========================================================================
    # Step 2: ConfigAgent - 配置生成
    # ========================================================================
    print("⚙️  [Step 2/3] ConfigAgent - 生成hydromodel配置...")
    config_start = time.time()

    try:
        config_result = config_agent.process(intent_result)
        config_elapsed = time.time() - config_start

        if not config_result.get("success"):
            print(f"❌ Config生成失败: {config_result.get('error')}")
            return False

        print(f"✅ Config生成完成 ({format_time(config_elapsed)})")
        print(f"\n配置摘要:")
        print(config_result.get("config_summary", ""))
        print()

        # 保存配置（可选）
        if save_config:
            config_file = workspace_dir / "generated_config.json"
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_result["config"], f, indent=2, ensure_ascii=False)
            print(f"💾 配置已保存: {config_file}\n")

    except Exception as e:
        print(f"❌ Config生成异常: {str(e)}")
        logger.error("Config生成失败", exc_info=True)
        return False

    # ========================================================================
    # Step 3: RunnerAgent - 执行hydromodel
    # ========================================================================
    print("🚀 [Step 3/3] RunnerAgent - 执行hydromodel...")
    runner_start = time.time()

    try:
        if use_mock:
            # Mock模式 - 不调用真实hydromodel
            print("   使用Mock模式（模拟执行）\n")

            mock_result = {
                "best_params": {"x1": 350.0, "x2": 0.5, "x3": 100.0, "x4": 2.0},
                "metrics": {"NSE": 0.85, "RMSE": 2.5, "KGE": 0.82},
                "output_files": ["results/calibrated_params.json"]
            }

            # 创建模拟的hydromodel模块
            mock_hydromodel = MagicMock()
            mock_hydromodel.calibrate = Mock(return_value=mock_result)
            mock_hydromodel.evaluate = Mock(return_value=mock_result)  # 提供evaluate函数

            with patch.dict('sys.modules', {'hydromodel': mock_hydromodel}):
                runner_result = runner_agent.process(config_result)

        else:
            # 真实模式 - 调用真实hydromodel
            print("   调用真实hydromodel API\n")
            runner_result = runner_agent.process(config_result)

        runner_elapsed = time.time() - runner_start

        if not runner_result.get("success"):
            print(f"❌ 执行失败: {runner_result.get('error')}")
            if traceback := runner_result.get('traceback'):
                print(f"\n错误详情:\n{traceback}")
            return False

        print(f"✅ 执行完成 ({format_time(runner_elapsed)})")
        print(f"\n执行结果:")
        result = runner_result.get("result", {})

        # 显示性能指标
        if metrics := result.get("metrics"):
            print(f"  性能指标:")
            for key, value in metrics.items():
                print(f"    {key}: {value}")

        # 显示最优参数
        if best_params := result.get("best_params"):
            print(f"  最优参数:")
            for key, value in best_params.items():
                print(f"    {key}: {value}")

        # 显示输出文件
        if output_files := result.get("output_files"):
            print(f"  输出文件:")
            for file in output_files:
                print(f"    - {file}")

        print()

    except Exception as e:
        print(f"❌ 执行异常: {str(e)}")
        logger.error("Runner执行失败", exc_info=True)
        return False

    # ========================================================================
    # 总结
    # ========================================================================
    total_elapsed = time.time() - total_start

    print_separator()
    print("✅ 完整管道执行成功!")
    print_separator()
    print(f"\n时间统计:")
    print(f"  Intent分析: {format_time(intent_elapsed)}")
    print(f"  Config生成: {format_time(config_elapsed)}")
    print(f"  Runner执行: {format_time(runner_elapsed)}")
    print(f"  总计时间:   {format_time(total_elapsed)}")
    print(f"\n工作目录: {workspace_dir}")
    print(f"日志文件: {log_file}")
    print_separator()

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
        show_progress=not args.no_progress  # --no-progress时为False
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
