"""
Author: Claude Code
Date: 2025-10-12 17:00:00
LastEditTime: 2025-10-12 17:00:00
LastEditors: Claude Code
Description: 修复嵌入维度不匹配问题 - 诊断并重建向量索引
FilePath: \HydroAgent\script\fix_embedding_dimension_mismatch.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import sys
from pathlib import Path
import logging
from datetime import datetime
import shutil

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 确保logs目录存在
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

# 设置详细日志
log_file = logs_dir / f"fix_embedding_dimension_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

print(f"日志将保存到: {log_file}")


def diagnose_dimension_mismatch():
    """诊断嵌入维度不匹配问题"""
    print("=" * 80)
    print("诊断嵌入维度不匹配问题")
    print("=" * 80)

    try:
        from hydrorag.config import default_config
        from hydrorag.embeddings_manager import EmbeddingsManager
        import json

        # 检查向量数据库元数据
        vector_db_dir = Path(default_config.vector_db_dir)
        metadata_file = vector_db_dir / "metadata.json"

        if not metadata_file.exists():
            logger.warning(f"向量数据库元数据文件不存在: {metadata_file}")
            return None

        # 读取元数据
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        index_dimension = metadata.get('dimension')
        logger.info(f"现有索引维度: {index_dimension}")
        logger.info(f"索引类型: {metadata.get('index_type')}")
        logger.info(f"距离函数: {metadata.get('distance_function')}")
        logger.info(f"文档数量: {metadata.get('total_documents')}")

        # 检查当前嵌入模型维度
        logger.info("\n初始化嵌入模型管理器...")
        embeddings_manager = EmbeddingsManager(default_config)

        if not embeddings_manager.is_available():
            logger.error("嵌入模型不可用")
            return None

        # 获取当前模型维度
        test_embedding = embeddings_manager.embed_text("测试文本")
        if test_embedding:
            current_dimension = len(test_embedding)
            logger.info(f"当前嵌入模型维度: {current_dimension}")
            logger.info(f"当前模型类型: {embeddings_manager.current_model_type}")

            # 清理资源
            embeddings_manager.cleanup()

            # 判断是否匹配
            if index_dimension == current_dimension:
                logger.info("✓ 维度匹配，无需修复")
                print("\n✓ 维度匹配，无需修复")
                return True
            else:
                logger.error(f"✗ 维度不匹配！索引: {index_dimension}, 模型: {current_dimension}")
                print(f"\n✗ 维度不匹配！索引: {index_dimension}, 模型: {current_dimension}")
                return {
                    'index_dimension': index_dimension,
                    'model_dimension': current_dimension,
                    'metadata': metadata
                }
        else:
            logger.error("无法生成测试嵌入")
            return None

    except Exception as e:
        logger.error(f"诊断失败: {e}", exc_info=True)
        return None


def backup_vector_db():
    """备份现有向量数据库"""
    print("\n" + "=" * 80)
    print("备份现有向量数据库")
    print("=" * 80)

    try:
        from hydrorag.config import default_config

        vector_db_dir = Path(default_config.vector_db_dir)
        backup_dir = project_root / "documents" / "backups" / f"vector_db_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        if not vector_db_dir.exists():
            logger.warning(f"向量数据库目录不存在: {vector_db_dir}")
            return None

        # 创建备份
        backup_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(vector_db_dir, backup_dir)

        logger.info(f"✓ 备份完成: {backup_dir}")
        print(f"✓ 备份完成: {backup_dir}")
        return backup_dir

    except Exception as e:
        logger.error(f"备份失败: {e}", exc_info=True)
        return None


def rebuild_vector_index():
    """重建向量索引"""
    print("\n" + "=" * 80)
    print("重建向量索引")
    print("=" * 80)

    try:
        from hydrorag.rag_system import RAGSystem
        from hydrorag.config import default_config

        # 确认操作
        print("\n警告：这将清空现有向量数据库并重建索引")
        print("已经创建了备份，可以安全继续")
        response = input("是否继续？(y/N): ")

        if response.lower() != 'y':
            logger.info("用户取消操作")
            print("操作已取消")
            return False

        # 使用上下文管理器确保资源清理
        with RAGSystem(default_config) as rag:
            # 清空向量数据库
            logger.info("清空现有向量数据库...")
            clear_result = rag.vector_store.clear_collection()
            if clear_result.get("status") == "success":
                logger.info(f"✓ 已删除 {clear_result.get('deleted', 0)} 个文档")
            else:
                logger.error(f"清空失败: {clear_result}")
                return False

            # 重新处理文档并构建索引
            logger.info("重新处理文档...")
            process_result = rag.process_documents(force_reprocess=False)

            if process_result.get("status") != "completed":
                logger.error(f"文档处理失败: {process_result}")
                return False

            logger.info("重新构建向量索引...")
            index_result = rag.build_vector_index(rebuild=True)

            if index_result.get("status") == "success":
                logger.info("✓ 向量索引重建成功")
                logger.info(f"  - 处理文档: {index_result.get('total_documents_processed', 0)}")
                logger.info(f"  - 添加文本块: {index_result.get('total_chunks_added', 0)}")
                logger.info(f"  - 最终文档数: {index_result.get('final_document_count', 0)}")

                # 验证新索引
                logger.info("\n验证新索引...")
                test_result = rag.query("GR4J模型参数", top_k=3)
                if test_result.get("status") == "success":
                    logger.info(f"✓ 测试查询成功，找到 {test_result.get('total_found', 0)} 个结果")
                    print(f"\n✓ 向量索引重建成功！")
                    return True
                else:
                    logger.warning(f"测试查询失败: {test_result}")
                    print(f"\n⚠ 索引重建完成，但测试查询失败")
                    return True
            else:
                logger.error(f"索引构建失败: {index_result}")
                return False

    except Exception as e:
        logger.error(f"重建失败: {e}", exc_info=True)
        return False


def main():
    """主函数"""
    print("\n嵌入维度不匹配修复工具")
    print(f"日志文件: {log_file}\n")

    # 步骤1: 诊断问题
    diagnosis = diagnose_dimension_mismatch()

    if diagnosis is None:
        print("\n诊断失败，请检查日志")
        return

    if diagnosis is True:
        print("\n无需修复，程序退出")
        return

    # 步骤2: 备份向量数据库
    backup_path = backup_vector_db()

    if not backup_path:
        print("\n备份失败，请手动备份后重试")
        return

    # 步骤3: 重建向量索引
    success = rebuild_vector_index()

    if success:
        print("\n" + "=" * 80)
        print("修复完成！")
        print("=" * 80)
        print(f"\n备份位置: {backup_path}")
        print(f"日志文件: {log_file}")
        print("\n现在可以重新运行RAG对比测试")
    else:
        print("\n" + "=" * 80)
        print("修复失败")
        print("=" * 80)
        print(f"\n可以从备份恢复: {backup_path}")
        print(f"详细日志: {log_file}")


if __name__ == "__main__":
    main()
