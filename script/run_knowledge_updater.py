#!/usr/bin/env python3
"""
Author: Claude
Date: 2025-09-29 13:50:00
LastEditTime: 2025-09-29 13:50:00
LastEditors: Claude
Description: 知识库更新器命令行启动脚本
FilePath: \HydroAgent\script\run_knowledge_updater.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import sys
import os
import argparse
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# 添加项目根路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 确保logs目录存在
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

# 设置日志
log_file = logs_dir / f"knowledge_updater_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

def setup_colorful_logging():
    """设置彩色日志输出"""
    try:
        import colorama
        from colorama import Fore, Style
        colorama.init()

        class ColoredFormatter(logging.Formatter):
            """彩色日志格式化器"""

            COLORS = {
                'DEBUG': Fore.CYAN,
                'INFO': Fore.GREEN,
                'WARNING': Fore.YELLOW,
                'ERROR': Fore.RED,
                'CRITICAL': Fore.MAGENTA
            }

            def format(self, record):
                log_color = self.COLORS.get(record.levelname, '')
                record.levelname = f"{log_color}{record.levelname}{Style.RESET_ALL}"
                return super().format(record)

        # 更新控制台处理器的格式
        console_handler = logging.getLogger().handlers[0]
        console_handler.setFormatter(ColoredFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

    except ImportError:
        pass  # 如果没有colorama，继续使用默认格式

def print_banner():
    """打印启动横幅"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                    HydroRAG 知识库更新器                     ║
║                   Knowledge Base Updater                     ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)
    print(f"📁 日志文件: {log_file}")
    print()


class KnowledgeUpdaterCLI:
    """知识库更新器命令行接口"""

    def __init__(self):
        """初始化CLI"""
        self.config = None
        self.updater = None
        self.rag_system = None

    def _load_config(self) -> bool:
        """加载配置"""
        try:
            from hydrorag import Config

            # 使用默认配置
            self.config = Config()

            logger.info("✅ 配置加载成功")
            logger.info(f"   原始文档目录: {self.config.raw_documents_dir}")
            logger.info(f"   处理文档目录: {self.config.processed_documents_dir}")
            logger.info(f"   向量数据库目录: {self.config.vector_db_dir}")
            return True

        except Exception as e:
            logger.error(f"❌ 配置加载失败: {e}")
            return False

    def _initialize_updater(self, with_rag: bool = False) -> bool:
        """初始化更新器"""
        try:
            from hydrorag import KnowledgeUpdater

            if with_rag:
                from hydrorag import RAGSystem
                logger.info("🔄 初始化RAG系统...")
                self.rag_system = RAGSystem(self.config)

            self.updater = KnowledgeUpdater(self.config, self.rag_system)
            logger.info("✅ 知识库更新器初始化成功")
            return True

        except Exception as e:
            logger.error(f"❌ 知识库更新器初始化失败: {e}")
            return False

    def check_status(self) -> Dict[str, Any]:
        """检查知识库状态"""
        logger.info("🔍 检查知识库状态...")

        if not self._load_config():
            return {"status": "error", "message": "配置加载失败"}

        if not self._initialize_updater():
            return {"status": "error", "message": "更新器初始化失败"}

        try:
            # 获取状态信息
            status = self.updater.get_status()

            print("\n📊 知识库状态报告")
            print("=" * 50)
            print(f"原始文档数量: {status.get('raw_documents_count', 'N/A')}")
            print(f"已处理文档数量: {status.get('processed_documents_count', 'N/A')}")
            print(f"最后更新时间: {status.get('last_update_time', 'N/A')}")
            print(f"版本信息: {status.get('version', 'N/A')}")
            print(f"备份数量: {status.get('backup_count', 'N/A')}")

            # 检查是否有待更新的文档
            check_result = self.updater.check_for_updates()
            if check_result["status"] == "completed":
                changes = check_result.get("changes", {})
                print(f"新文档: {len(changes.get('new', []))}")
                print(f"修改文档: {len(changes.get('modified', []))}")
                print(f"删除文档: {len(changes.get('deleted', []))}")

                if changes.get('new') or changes.get('modified') or changes.get('deleted'):
                    print("⚠️  检测到文档变更，建议运行更新")
                else:
                    print("✅ 知识库是最新的")

            return {"status": "success", "data": status}

        except Exception as e:
            logger.error(f"❌ 状态检查失败: {e}")
            return {"status": "error", "message": str(e)}

    def check_updates(self) -> Dict[str, Any]:
        """检查可用更新"""
        logger.info("🔍 检查知识库更新...")

        if not self._load_config():
            return {"status": "error", "message": "配置加载失败"}

        if not self._initialize_updater():
            return {"status": "error", "message": "更新器初始化失败"}

        try:
            result = self.updater.check_for_updates()

            if result["status"] == "completed":
                changes = result.get("changes", {})

                print("\n📋 更新检查结果")
                print("=" * 50)

                if changes.get("new"):
                    print(f"🆕 新文档 ({len(changes['new'])}):")
                    for file in changes["new"]:
                        print(f"   + {file}")

                if changes.get("modified"):
                    print(f"📝 修改文档 ({len(changes['modified'])}):")
                    for file in changes["modified"]:
                        print(f"   ~ {file}")

                if changes.get("deleted"):
                    print(f"🗑️  删除文档 ({len(changes['deleted'])}):")
                    for file in changes["deleted"]:
                        print(f"   - {file}")

                total_changes = len(changes.get("new", [])) + len(changes.get("modified", [])) + len(changes.get("deleted", []))

                if total_changes == 0:
                    print("✅ 没有检测到变更，知识库是最新的")
                else:
                    print(f"\n📊 总计: {total_changes} 个文档需要更新")

            return result

        except Exception as e:
            logger.error(f"❌ 更新检查失败: {e}")
            return {"status": "error", "message": str(e)}

    def update_knowledge_base(self, force_full: bool = False) -> Dict[str, Any]:
        """更新知识库"""
        update_type = "完全重建" if force_full else "增量更新"
        logger.info(f"🚀 开始知识库{update_type}...")

        if not self._load_config():
            return {"status": "error", "message": "配置加载失败"}

        if not self._initialize_updater(with_rag=True):
            return {"status": "error", "message": "更新器初始化失败"}

        try:
            start_time = datetime.now()

            result = self.updater.update_knowledge_base(force_full_update=force_full)

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            print(f"\n📈 {update_type}结果")
            print("=" * 50)

            if result["status"] == "success":
                print("✅ 更新成功完成")
                print(f"⏱️  耗时: {duration:.2f} 秒")

                if "summary" in result:
                    summary = result["summary"]
                    print(f"📊 处理统计:")
                    print(f"   新增文档: {summary.get('new_documents', 0)}")
                    print(f"   更新文档: {summary.get('updated_documents', 0)}")
                    print(f"   删除文档: {summary.get('deleted_documents', 0)}")
                    print(f"   向量总数: {summary.get('total_vectors', 'N/A')}")

            else:
                print("❌ 更新失败")
                print(f"错误信息: {result.get('error', '未知错误')}")

            return result

        except Exception as e:
            logger.error(f"❌ 知识库更新失败: {e}")
            return {"status": "error", "message": str(e)}

    def create_backup(self, backup_name: Optional[str] = None) -> Dict[str, Any]:
        """创建备份"""
        logger.info("💾 创建知识库备份...")

        if not self._load_config():
            return {"status": "error", "message": "配置加载失败"}

        if not self._initialize_updater():
            return {"status": "error", "message": "更新器初始化失败"}

        try:
            result = self.updater.create_backup(backup_name=backup_name)

            print("\n💾 备份结果")
            print("=" * 50)

            if result["status"] == "success":
                print("✅ 备份创建成功")
                print(f"📁 备份路径: {result.get('backup_path', 'N/A')}")
                print(f"📊 备份大小: {result.get('backup_size', 'N/A')}")
                print(f"⏱️  创建时间: {result.get('creation_time', 'N/A')}")
            else:
                print("❌ 备份创建失败")
                print(f"错误信息: {result.get('error', '未知错误')}")

            return result

        except Exception as e:
            logger.error(f"❌ 备份创建失败: {e}")
            return {"status": "error", "message": str(e)}

    def list_backups(self) -> Dict[str, Any]:
        """列出所有备份"""
        logger.info("📋 列出知识库备份...")

        if not self._load_config():
            return {"status": "error", "message": "配置加载失败"}

        if not self._initialize_updater():
            return {"status": "error", "message": "更新器初始化失败"}

        try:
            backups = self.updater.list_backups()

            print("\n📋 备份列表")
            print("=" * 70)

            if not backups:
                print("🗂️  暂无备份文件")
            else:
                print(f"{'序号':<4} {'备份名称':<25} {'创建时间':<20} {'大小':<10}")
                print("-" * 70)

                for i, backup in enumerate(backups, 1):
                    name = backup.get('name', 'N/A')
                    creation_time = backup.get('creation_time', 'N/A')
                    size = backup.get('size', 'N/A')
                    print(f"{i:<4} {name:<25} {creation_time:<20} {size:<10}")

                print(f"\n📊 总计: {len(backups)} 个备份")

            return {"status": "success", "backups": backups}

        except Exception as e:
            logger.error(f"❌ 备份列表获取失败: {e}")
            return {"status": "error", "message": str(e)}

    def restore_backup(self, backup_name: str) -> Dict[str, Any]:
        """恢复备份"""
        logger.info(f"🔄 恢复备份: {backup_name}")

        if not self._load_config():
            return {"status": "error", "message": "配置加载失败"}

        if not self._initialize_updater():
            return {"status": "error", "message": "更新器初始化失败"}

        try:
            result = self.updater.restore_backup(backup_name)

            print(f"\n🔄 备份恢复结果")
            print("=" * 50)

            if result["status"] == "success":
                print("✅ 备份恢复成功")
                print(f"📁 恢复源: {backup_name}")
                print(f"⏱️  恢复时间: {result.get('restore_time', 'N/A')}")
            else:
                print("❌ 备份恢复失败")
                print(f"错误信息: {result.get('error', '未知错误')}")

            return result

        except Exception as e:
            logger.error(f"❌ 备份恢复失败: {e}")
            return {"status": "error", "message": str(e)}

    def show_history(self, limit: int = 10) -> Dict[str, Any]:
        """显示更新历史"""
        logger.info("📜 显示更新历史...")

        if not self._load_config():
            return {"status": "error", "message": "配置加载失败"}

        if not self._initialize_updater():
            return {"status": "error", "message": "更新器初始化失败"}

        try:
            history = self.updater.get_update_history()

            print("\n📜 更新历史")
            print("=" * 80)

            if not history:
                print("📝 暂无更新历史记录")
            else:
                # 显示最近的记录
                recent_history = history[-limit:] if len(history) > limit else history

                print(f"{'时间':<20} {'操作':<15} {'状态':<10} {'详情':<30}")
                print("-" * 80)

                for record in reversed(recent_history):
                    timestamp = record.get('timestamp', 'N/A')
                    operation = record.get('operation', 'N/A')
                    status = record.get('status', 'N/A')
                    details = record.get('details', 'N/A')

                    # 限制详情长度
                    if len(details) > 27:
                        details = details[:24] + "..."

                    print(f"{timestamp:<20} {operation:<15} {status:<10} {details:<30}")

                if len(history) > limit:
                    print(f"\n📊 显示最近 {limit} 条记录，总计 {len(history)} 条")
                else:
                    print(f"\n📊 总计: {len(history)} 条记录")

            return {"status": "success", "history": history}

        except Exception as e:
            logger.error(f"❌ 历史记录获取失败: {e}")
            return {"status": "error", "message": str(e)}


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="HydroRAG 知识库更新器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  %(prog)s status                    # 检查知识库状态
  %(prog)s check                     # 检查可用更新
  %(prog)s update                    # 增量更新知识库
  %(prog)s rebuild                   # 完全重建知识库
  %(prog)s backup                    # 创建备份
  %(prog)s backup --name my_backup   # 创建命名备份
  %(prog)s list-backups              # 列出所有备份
  %(prog)s restore backup_name       # 恢复指定备份
  %(prog)s history                   # 显示更新历史
  %(prog)s history --limit 20        # 显示最近20条历史
        """
    )

    # 添加子命令
    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # status 命令
    subparsers.add_parser('status', help='检查知识库状态')

    # check 命令
    subparsers.add_parser('check', help='检查可用更新')

    # update 命令
    update_parser = subparsers.add_parser('update', help='增量更新知识库')
    update_parser.add_argument('--force', action='store_true', help='强制完全更新')

    # rebuild 命令
    subparsers.add_parser('rebuild', help='完全重建知识库')

    # backup 命令
    backup_parser = subparsers.add_parser('backup', help='创建知识库备份')
    backup_parser.add_argument('--name', help='备份名称（可选）')

    # list-backups 命令
    subparsers.add_parser('list-backups', help='列出所有备份')

    # restore 命令
    restore_parser = subparsers.add_parser('restore', help='恢复指定备份')
    restore_parser.add_argument('backup_name', help='要恢复的备份名称')

    # history 命令
    history_parser = subparsers.add_parser('history', help='显示更新历史')
    history_parser.add_argument('--limit', type=int, default=10, help='显示记录数量（默认10）')

    # 全局参数
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    parser.add_argument('--no-color', action='store_true', help='禁用彩色输出')
    parser.add_argument('--quiet', action='store_true', help='静默模式')

    args = parser.parse_args()

    # 设置日志级别
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.quiet:
        logging.getLogger().setLevel(logging.WARNING)

    # 设置彩色输出
    if not args.no_color:
        setup_colorful_logging()

    # 显示横幅
    if not args.quiet:
        print_banner()

    # 创建CLI实例
    cli = KnowledgeUpdaterCLI()

    # 执行命令
    try:
        if args.command == 'status':
            result = cli.check_status()
        elif args.command == 'check':
            result = cli.check_updates()
        elif args.command == 'update':
            result = cli.update_knowledge_base(force_full=args.force)
        elif args.command == 'rebuild':
            result = cli.update_knowledge_base(force_full=True)
        elif args.command == 'backup':
            result = cli.create_backup(backup_name=args.name)
        elif args.command == 'list-backups':
            result = cli.list_backups()
        elif args.command == 'restore':
            result = cli.restore_backup(args.backup_name)
        elif args.command == 'history':
            result = cli.show_history(limit=args.limit)
        else:
            parser.print_help()
            return 1

        # 根据结果返回适当的退出代码
        if result.get("status") == "success":
            logger.info("✅ 操作完成")
            return 0
        else:
            logger.error(f"❌ 操作失败: {result.get('message', '未知错误')}")
            return 1

    except KeyboardInterrupt:
        logger.info("🛑 操作被用户中断")
        return 130
    except Exception as e:
        logger.error(f"❌ 发生意外错误: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())