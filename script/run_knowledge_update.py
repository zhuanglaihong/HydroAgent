"""
Author: zhuanglaihong
Date: 2025-09-27 15:15:00
LastEditTime: 2025-09-27 15:15:00
LastEditors: zhuanglaihong
Description: 知识库更新运行脚本，支持全量重建、增量更新、备份恢复等功能
FilePath: \HydroAgent\script\run_knowledge_update.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import sys
import argparse
import json
from pathlib import Path
from typing import List, Optional
import time

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from hydrorag.knowledge_updater import KnowledgeUpdater
from hydrorag.config import default_config
from utils.logger_config import LoggerConfig, TestLoggerContext


def format_duration(seconds: float) -> str:
    """格式化时间显示"""
    if seconds < 60:
        return f"{seconds:.1f}秒"
    elif seconds < 3600:
        return f"{seconds/60:.1f}分钟"
    else:
        return f"{seconds/3600:.1f}小时"


def print_stats(stats: dict, title: str = "知识库统计信息"):
    """打印统计信息"""
    print(f"\n=== {title} ===")

    if "error" in stats:
        print(f"[ERROR] 获取统计信息失败: {stats['error']}")
        return

    # 向量数据库信息
    vector_info = stats.get("vector_database", {})
    print(f"[VECTOR DB] 向量数据库:")
    print(f"   文档数量: {vector_info.get('document_count', 0)}")
    print(f"   集合数量: {vector_info.get('collection_count', 0)}")

    # 文件系统信息
    fs_info = stats.get("file_system", {})
    print(f"[FILE SYS] 文件系统:")
    print(f"   原始文档: {fs_info.get('raw_files_count', 0)} 个")
    print(f"   处理文档: {fs_info.get('processed_files_count', 0)} 个")

    # 最后更新时间
    last_updated = stats.get("last_updated", "未知")
    print(f"[TIME] 最后更新: {last_updated}")


def print_result(result: dict, operation: str):
    """打印操作结果"""
    print(f"\n=== {operation}结果 ===")

    status = result.get("status", "unknown")
    if status == "success":
        print("[SUCCESS] 操作成功完成")
    else:
        print("[FAILED] 操作失败")
        if "error" in result:
            print(f"   错误: {result['error']}")

    # 显示详细信息
    if "start_time" in result and "end_time" in result:
        try:
            from datetime import datetime
            start = datetime.fromisoformat(result["start_time"])
            end = datetime.fromisoformat(result["end_time"])
            duration = (end - start).total_seconds()
            print(f"[TIME] 耗时: {format_duration(duration)}")
        except:
            pass

    # 显示具体统计
    if operation == "全量重建":
        print(f"处理文档: {result.get('processed_files', 0)} 个")
        print(f"索引块数: {result.get('indexed_documents', 0)} 个")
        if result.get("backup_created"):
            print(f"备份路径: {result.get('backup_path', '未知')}")

    elif operation == "增量更新":
        print(f"更新文件: {len(result.get('updated_files', []))} 个")
        print(f"新增文档: {result.get('added_documents', 0)} 个")
        print(f"更新文档: {result.get('updated_documents', 0)} 个")
        print(f"➖ 删除文档: {result.get('removed_documents', 0)} 个")

    elif operation == "文档添加":
        print(f"成功添加: {result.get('added_count', 0)} 个")
        print(f"添加失败: {result.get('failed_count', 0)} 个")

    elif operation == "文档删除":
        print(f"➖ 成功删除: {result.get('removed_count', 0)} 个")
        print(f"删除失败: {result.get('failed_count', 0)} 个")

    # 显示错误信息
    errors = result.get("errors", [])
    if errors:
        print(f"警告/错误 ({len(errors)}个):")
        for error in errors[:5]:  # 只显示前5个错误
            print(f"   - {error}")
        if len(errors) > 5:
            print(f"   ... 还有 {len(errors) - 5} 个错误")


def full_rebuild(updater: KnowledgeUpdater, backup: bool = True, quiet: bool = False):
    """执行全量重建"""
    if not quiet:
        print("开始全量重建知识库...")
        if backup:
            print("将创建现有知识库的备份")

    start_time = time.time()
    result = updater.full_rebuild(backup_existing=backup)
    end_time = time.time()

    if not quiet:
        print_result(result, "全量重建")

    return result["status"] == "success"


def incremental_update(updater: KnowledgeUpdater, file_paths: Optional[List[str]] = None, quiet: bool = False):
    """执行增量更新"""
    if not quiet:
        if file_paths:
            print(f"开始更新指定的 {len(file_paths)} 个文件...")
        else:
            print("开始自动检测并增量更新知识库...")

    start_time = time.time()
    result = updater.incremental_update(file_paths=file_paths)
    end_time = time.time()

    if not quiet:
        print_result(result, "增量更新")

    return result["status"] == "success"


def show_stats(updater: KnowledgeUpdater):
    """显示知识库统计信息"""
    stats = updater.get_knowledge_base_stats()
    print_stats(stats)

    # 显示详细文件列表
    fs_info = stats.get("file_system", {})
    raw_files = fs_info.get("raw_files", [])
    processed_files = fs_info.get("processed_files", [])

    if raw_files:
        print(f"\n原始文档列表:")
        for i, file_name in enumerate(raw_files[:10], 1):  # 只显示前10个
            print(f"   {i:2d}. {file_name}")
        if len(raw_files) > 10:
            print(f"   ... 还有 {len(raw_files) - 10} 个文件")

    if processed_files:
        print(f"\n处理文档列表:")
        for i, file_name in enumerate(processed_files[:10], 1):  # 只显示前10个
            print(f"   {i:2d}. {file_name}")
        if len(processed_files) > 10:
            print(f"   ... 还有 {len(processed_files) - 10} 个文件")


def create_backup(updater: KnowledgeUpdater, backup_name: Optional[str] = None, quiet: bool = False):
    """创建备份"""
    if not quiet:
        print("开始创建知识库备份...")

    try:
        backup_path = updater.create_backup(backup_name)
        if not quiet:
            print(f"✅ 备份创建成功: {backup_path}")
        return True
    except Exception as e:
        if not quiet:
            print(f"备份创建失败: {e}")
        return False


def restore_backup(updater: KnowledgeUpdater, backup_path: str, quiet: bool = False):
    """恢复备份"""
    if not quiet:
        print(f"开始恢复备份: {backup_path}")

    result = updater.restore_backup(backup_path)

    if not quiet:
        if result["status"] == "success":
            print("✅ 备份恢复成功")
            if "current_backup" in result:
                print(f"当前状态已备份至: {result['current_backup']}")
        else:
            print(f"备份恢复失败: {result.get('error', '未知错误')}")

    return result["status"] == "success"


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="HydroAgent 知识库更新工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 显示知识库统计信息
  python run_knowledge_update.py --stats

  # 全量重建知识库（带备份）
  python run_knowledge_update.py --rebuild

  # 全量重建知识库（不备份）
  python run_knowledge_update.py --rebuild --no-backup

  # 增量更新知识库
  python run_knowledge_update.py --update

  # 更新指定文件
  python run_knowledge_update.py --update --files doc1.md doc2.txt

  # 创建备份
  python run_knowledge_update.py --backup

  # 恢复备份
  python run_knowledge_update.py --restore path/to/backup

  # 静默模式运行
  python run_knowledge_update.py --rebuild --quiet
        """
    )

    # 操作选项
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument("--rebuild", action="store_true",
                             help="完全重建知识库")
    action_group.add_argument("--update", action="store_true",
                             help="增量更新知识库")
    action_group.add_argument("--stats", action="store_true",
                             help="显示知识库统计信息")
    action_group.add_argument("--backup", action="store_true",
                             help="创建知识库备份")
    action_group.add_argument("--restore", type=str, metavar="BACKUP_PATH",
                             help="恢复指定的备份")

    # 附加选项
    parser.add_argument("--files", nargs="+", metavar="FILE",
                       help="指定要更新的文件路径（仅用于 --update）")
    parser.add_argument("--no-backup", action="store_true",
                       help="重建时不创建备份（仅用于 --rebuild）")
    parser.add_argument("--backup-name", type=str,
                       help="指定备份名称（仅用于 --backup）")
    parser.add_argument("--quiet", action="store_true",
                       help="静默模式，减少输出信息")
    parser.add_argument("--log-file", action="store_true",
                       help="使用日志文件记录详细信息")

    args = parser.parse_args()

    # 使用上下文管理器确保资源正确释放
    if not args.quiet:
        print("HydroAgent 知识库更新工具")
        print("=" * 50)

    success = False

    try:
        # 使用上下文管理器初始化知识库更新器
        with KnowledgeUpdater(default_config, lazy_init=True) as updater:
            # 执行相应操作
            if args.log_file and not args.stats:
                # 使用日志文件模式
                operation_name = "knowledge_update"
                operation_desc = "知识库更新操作"

                with TestLoggerContext(operation_name, operation_desc) as logger_config:
                    logger_config.log_step("开始知识库操作")

                    if args.rebuild:
                        success = full_rebuild(updater, backup=not args.no_backup, quiet=args.quiet)
                    elif args.update:
                        success = incremental_update(updater, file_paths=args.files, quiet=args.quiet)
                    elif args.backup:
                        success = create_backup(updater, backup_name=args.backup_name, quiet=args.quiet)
                    elif args.restore:
                        success = restore_backup(updater, args.restore, quiet=args.quiet)

                    logger_config.log_step("知识库操作", "完成" if success else "失败")
                    logger_config.log_result("操作结果", {
                        "status": "success" if success else "failed",
                        "operation": "rebuild" if args.rebuild else "update" if args.update else "backup" if args.backup else "restore"
                    })
            else:
                # 直接执行模式
                if args.stats:
                    show_stats(updater)
                    success = True
                elif args.rebuild:
                    success = full_rebuild(updater, backup=not args.no_backup, quiet=args.quiet)
                elif args.update:
                    success = incremental_update(updater, file_paths=args.files, quiet=args.quiet)
                elif args.backup:
                    success = create_backup(updater, backup_name=args.backup_name, quiet=args.quiet)
                elif args.restore:
                    success = restore_backup(updater, args.restore, quiet=args.quiet)

            # 显示最新统计信息（在上下文管理器内部）
            if not args.quiet and not args.stats and success and (args.rebuild or args.update):
                try:
                    print_stats(updater.get_knowledge_base_stats(), "更新后统计信息")
                except:
                    pass

    except KeyboardInterrupt:
        if not args.quiet:
            print("\n操作被用户中断")
        success = False
    except Exception as e:
        if not args.quiet:
            print(f"\n操作执行失败: {e}")
            import traceback
            print(f"详细错误:\n{traceback.format_exc()}")
        success = False

    # 显示最终结果
    if not args.quiet and not args.stats:
        print("\n" + "=" * 50)
        if success:
            print("知识库操作成功完成！")
        else:
            print("知识库操作失败！")

    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)