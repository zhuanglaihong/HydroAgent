#!/usr/bin/env python
"""
HydroAgent - 启动脚本
智能水文模型助手

使用方法:
    python run.py                        # 交互模式
    python run.py "你的查询"              # 单次查询
    python run.py --resume [路径]        # 恢复会话
    python run.py --examples             # 查看示例
    python run.py --help                 # 查看帮助
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from hydroagent.system import HydroAgent, setup_logging


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="HydroAgent - 智能水文模型助手",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run.py
      启动交互式界面

  python run.py "率定GR4J模型，流域01013500"
      单次查询模式

  python run.py --resume
      恢复最近的会话

  python run.py --resume experiment_results/exp_3/session_xxx
      恢复指定会话

  python run.py --backend ollama
      使用 Ollama 本地模型

  python run.py --examples
      查看查询示例

更多信息请访问: https://github.com/your-repo/HydroAgent
        """
    )

    parser.add_argument(
        'query',
        nargs='?',
        help='自然语言查询（留空则进入交互模式）'
    )

    parser.add_argument(
        '--backend',
        choices=['api', 'ollama'],
        default='api',
        help='LLM后端 (默认: api)'
    )

    parser.add_argument(
        '--resume',
        nargs='?',
        const='',  # 不带参数时的默认值
        metavar='PATH',
        help='恢复会话（可选指定会话目录路径）'
    )

    parser.add_argument(
        '--workspace',
        type=Path,
        default=Path('experiment_results'),
        help='工作目录 (默认: experiment_results)'
    )

    parser.add_argument(
        '--no-checkpoint',
        action='store_true',
        help='禁用checkpoint功能'
    )

    parser.add_argument(
        '--examples',
        action='store_true',
        help='显示查询示例并退出'
    )

    parser.add_argument(
        '--history',
        action='store_true',
        help='显示历史会话并退出'
    )

    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='日志级别 (默认: INFO)'
    )

    parser.add_argument(
        '--log-file',
        type=Path,
        help='日志文件路径（可选）'
    )

    parser.add_argument(
        '--version',
        action='version',
        version='HydroAgent v1.0.0'
    )

    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()

    # 配置日志
    log_file = args.log_file
    if not log_file and not args.query:
        # 交互模式默认记录日志
        logs_dir = Path('logs')
        logs_dir.mkdir(exist_ok=True)
        log_file = logs_dir / f"hydroagent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    setup_logging(log_level=args.log_level, log_file=log_file)

    # 创建系统实例
    system = HydroAgent(
        backend=args.backend,
        workspace_dir=args.workspace,
        enable_checkpoint=not args.no_checkpoint
    )

    # 处理特殊命令
    if args.examples:
        system.show_examples()
        return

    if args.history:
        system.list_history()
        return

    # 恢复会话
    if args.resume is not None:
        resume_path = args.resume if args.resume else None
        system.run_single_query(query="", resume_from=resume_path)
        return

    # 单次查询模式
    if args.query:
        system.run_single_query(args.query)
        return

    # 交互模式
    system.run_interactive()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 再见！")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 发生严重错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
