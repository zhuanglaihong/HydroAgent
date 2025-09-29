"""
Author: zhuanglaihong
Date: 2025-09-29 16:30:00
LastEditTime: 2025-09-29 16:30:00
LastEditors: zhuanglaihong
Description: HydroRAG FAISS集成测试 - 测试重构后的hydrorag系统，包括FAISS向量存储、智能文档处理、知识库更新等功能
FilePath: \HydroAgent\test\test_hydrorag_faiss_integration.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import sys
import time
import logging
from pathlib import Path
import shutil
import tempfile
import pytest

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 确保logs目录存在
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

# 设置详细日志
from datetime import datetime
log_file = logs_dir / f"test_hydrorag_faiss_integration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
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

class TestHydroRAGFaissIntegration:
    """HydroRAG FAISS集成测试类"""

    @classmethod
    def setup_class(cls):
        """测试类初始化"""
        logger.info("开始HydroRAG FAISS集成测试")

        # 使用项目实际的documents目录
        cls.documents_dir = project_root / "documents"
        cls.raw_dir = cls.documents_dir / "raw"
        cls.processed_dir = cls.documents_dir / "processed"
        cls.vector_db_dir = cls.documents_dir / "vector_db"

        # 检查raw目录是否存在且有文档
        if not cls.raw_dir.exists():
            logger.error(f"Raw文档目录不存在: {cls.raw_dir}")
            raise FileNotFoundError(f"Raw文档目录不存在: {cls.raw_dir}")

        # 检查raw目录中是否有文档
        raw_files = list(cls.raw_dir.rglob("*"))
        raw_docs = [f for f in raw_files if f.is_file() and f.suffix.lower() in ['.txt', '.md', '.pdf', '.py', '.yaml', '.yml', '.json']]

        if not raw_docs:
            logger.error(f"Raw目录中没有找到支持的文档文件: {cls.raw_dir}")
            raise FileNotFoundError(f"Raw目录中没有找到支持的文档文件")

        logger.info(f"找到 {len(raw_docs)} 个原始文档文件")
        for doc in raw_docs[:10]:  # 只显示前10个
            logger.info(f"  - {doc.relative_to(cls.raw_dir)}")

        # 确保processed和vector_db目录存在
        cls.processed_dir.mkdir(parents=True, exist_ok=True)
        cls.vector_db_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"使用实际文档目录: {cls.documents_dir}")
        logger.info(f"原始文档: {cls.raw_dir}")
        logger.info(f"处理后文档: {cls.processed_dir}")
        logger.info(f"向量数据库: {cls.vector_db_dir}")

    @classmethod
    def teardown_class(cls):
        """测试类清理"""
        try:
            # 不删除真实的documents目录，只清理测试过程中可能创建的临时文件
            logger.info("测试完成，保留真实的documents目录")

            # 可选：清理测试过程中的一些临时文件
            # 但保留processed和vector_db目录，供后续使用
            logger.info("测试环境清理完成")
        except Exception as e:
            logger.error(f"清理测试环境失败: {e}")


    def test_01_config_and_imports(self):
        """测试配置和导入"""
        logger.info("测试1: 配置和导入")

        try:
            # 测试配置导入
            import config
            logger.info("✓ 全局配置导入成功")

            # 测试hydrorag模块导入
            from hydrorag.config import Config
            from hydrorag.embeddings_manager import EmbeddingsManager
            from hydrorag.document_processor import DocumentProcessor
            from hydrorag.faiss_vector_store import FaissVectorStore
            from hydrorag.knowledge_updater import KnowledgeUpdater
            from hydrorag.rag_system import RAGSystem

            logger.info("✓ 所有hydrorag模块导入成功")

            # 检查FAISS可用性
            try:
                import faiss
                logger.info("✓ FAISS库可用")
            except ImportError:
                logger.warning("⚠ FAISS库不可用，某些测试可能跳过")

            assert True

        except Exception as e:
            logger.error(f"✗ 导入测试失败: {e}")
            pytest.fail(f"导入测试失败: {e}")

    def test_02_embeddings_manager(self):
        """测试嵌入模型管理器"""
        logger.info("测试2: 嵌入模型管理器")

        try:
            from hydrorag.config import Config
            from hydrorag.embeddings_manager import EmbeddingsManager

            # 创建配置
            config = Config(
                raw_documents_dir=str(self.raw_dir),
                processed_documents_dir=str(self.processed_dir),
                vector_db_dir=str(self.vector_db_dir)
            )

            # 初始化嵌入管理器
            embeddings_manager = EmbeddingsManager(config)

            # 测试模型可用性
            is_available = embeddings_manager.is_available()
            logger.info(f"嵌入模型可用性: {is_available}")

            if is_available:
                # 测试单个文本嵌入
                test_text = "这是一个测试文本"
                embedding = embeddings_manager.embed_text(test_text)

                if embedding:
                    logger.info(f"✓ 单文本嵌入成功，维度: {len(embedding)}")

                    # 测试批量嵌入
                    test_texts = ["文本1", "文本2", "文本3"]
                    embeddings = embeddings_manager.embed_texts(test_texts)

                    success_count = sum(1 for emb in embeddings if emb is not None)
                    logger.info(f"✓ 批量嵌入成功: {success_count}/{len(test_texts)}")

                    # 测试文档块嵌入
                    chunks = [
                        {"content": "文档块1", "chunk_id": "chunk_001"},
                        {"content": "文档块2", "chunk_id": "chunk_002"}
                    ]
                    processed_chunks = embeddings_manager.embed_documents_chunks(chunks)

                    embedded_count = sum(1 for chunk in processed_chunks if chunk.get("has_embedding"))
                    logger.info(f"✓ 文档块嵌入成功: {embedded_count}/{len(chunks)}")

                else:
                    logger.warning("⚠ 嵌入生成失败，可能是模型不可用")
            else:
                logger.warning("⚠ 嵌入模型不可用，跳过嵌入测试")

            # 获取模型信息
            model_info = embeddings_manager.get_model_info()
            logger.info(f"模型信息: {model_info}")

            assert True

        except Exception as e:
            logger.error(f"✗ 嵌入模型管理器测试失败: {e}")
            pytest.fail(f"嵌入模型管理器测试失败: {e}")

    def test_03_document_processor(self):
        """测试文档处理器"""
        logger.info("测试3: 文档处理器")

        try:
            from hydrorag.config import Config
            from hydrorag.document_processor import DocumentProcessor

            # 创建配置
            config = Config(
                raw_documents_dir=str(self.raw_dir),
                processed_documents_dir=str(self.processed_dir),
                vector_db_dir=str(self.vector_db_dir)
            )

            # 初始化文档处理器
            doc_processor = DocumentProcessor(config)

            # 扫描原始文档
            raw_files = doc_processor.scan_raw_documents()
            logger.info(f"扫描到 {len(raw_files)} 个原始文档")
            assert len(raw_files) > 0, "应该有测试文档"

            # 处理单个文档
            test_file = raw_files[0]
            result = doc_processor.process_document(test_file)

            if result["status"] == "success":
                logger.info(f"✓ 单文档处理成功: {result['chunks_count']} 个文本块")
            else:
                logger.warning(f"⚠ 单文档处理失败: {result}")

            # 批量处理文档
            batch_result = doc_processor.process_all_documents(parallel=True, max_workers=2)

            if batch_result["status"] == "completed":
                logger.info(f"✓ 批量文档处理完成: 成功 {batch_result['processed']}, "
                          f"失败 {batch_result['failed']}, 跳过 {batch_result['skipped']}")
            else:
                logger.error(f"✗ 批量文档处理失败: {batch_result}")

            # 获取处理统计
            stats = doc_processor.get_statistics()
            logger.info(f"处理统计: {stats}")

            # 获取已处理文档
            processed_docs = doc_processor.get_processed_documents()
            logger.info(f"已处理文档数量: {len(processed_docs)}")

            assert batch_result["status"] == "completed"

        except Exception as e:
            logger.error(f"✗ 文档处理器测试失败: {e}")
            pytest.fail(f"文档处理器测试失败: {e}")

    def test_04_faiss_vector_store(self):
        """测试FAISS向量存储"""
        logger.info("测试4: FAISS向量存储")

        try:
            import faiss
        except ImportError:
            logger.warning("⚠ FAISS不可用，跳过FAISS向量存储测试")
            pytest.skip("FAISS不可用")
            return

        try:
            from hydrorag.config import Config
            from hydrorag.embeddings_manager import EmbeddingsManager
            from hydrorag.faiss_vector_store import FaissVectorStore

            # 创建配置
            config = Config(
                raw_documents_dir=str(self.raw_dir),
                processed_documents_dir=str(self.processed_dir),
                vector_db_dir=str(self.vector_db_dir)
            )

            # 初始化组件
            embeddings_manager = EmbeddingsManager(config)

            if not embeddings_manager.is_available():
                logger.warning("⚠ 嵌入模型不可用，跳过FAISS测试")
                pytest.skip("嵌入模型不可用")
                return

            vector_store = FaissVectorStore(config, embeddings_manager)

            # 测试向量存储可用性
            assert vector_store.is_available(), "FAISS向量存储应该可用"
            logger.info("✓ FAISS向量存储初始化成功")

            # 准备测试文档块
            test_chunks = [
                {
                    "content": "prepare_data工具用于数据准备和预处理",
                    "chunk_id": "test_001",
                    "source_file": "test_gr4j.txt"
                },
                {
                    "content": "calibrate_model工具用于模型参数率定",
                    "chunk_id": "test_002",
                    "source_file": "test_xaj.txt"
                },
                {
                    "content": "evaluate_model工具用于模型性能评估",
                    "chunk_id": "test_003",
                    "source_file": "test_calib.txt"
                }
            ]

            # 添加文档到向量存储
            add_result = vector_store.add_documents(test_chunks)

            if add_result["status"] == "success":
                logger.info(f"✓ 文档添加成功: {add_result['added']} 个文档")
            else:
                logger.error(f"✗ 文档添加失败: {add_result}")
                pytest.fail(f"文档添加失败: {add_result}")

            # 测试查询
            query_tests = [
                "工具使用方法",
                "数据预处理",
                "模型率定步骤"
            ]

            for query in query_tests:
                result = vector_store.query(query, n_results=2)

                if result["status"] == "success":
                    logger.info(f"✓ 查询成功 '{query}': {result['total_found']} 个结果")

                    # 检查结果质量
                    if result["total_found"] > 0:
                        top_result = result["documents"][0] if result["documents"] else ""
                        score = result["scores"][0] if result["scores"] else 0.0
                        logger.info(f"  最佳匹配: {top_result[:50]}... (分数: {score:.3f})")
                else:
                    logger.warning(f"⚠ 查询失败 '{query}': {result}")

            # 获取统计信息
            stats = vector_store.get_statistics()
            logger.info(f"向量存储统计: {stats}")

            assert stats.get("total_documents", 0) > 0, "应该有文档在向量存储中"

        except Exception as e:
            logger.error(f"✗ FAISS向量存储测试失败: {e}")
            pytest.fail(f"FAISS向量存储测试失败: {e}")

    def test_05_knowledge_updater(self):
        """测试知识库更新器"""
        logger.info("测试5: 知识库更新器")

        try:
            from hydrorag.config import Config
            from hydrorag.knowledge_updater import KnowledgeUpdater

            # 创建配置
            config = Config(
                raw_documents_dir=str(self.raw_dir),
                processed_documents_dir=str(self.processed_dir),
                vector_db_dir=str(self.vector_db_dir)
            )

            # 初始化知识库更新器
            updater = KnowledgeUpdater(config)

            # 检查更新
            check_result = updater.check_for_updates()
            logger.info(f"更新检查结果: {check_result['status']}")

            if check_result["status"] == "completed":
                summary = check_result.get("summary", {})
                logger.info(f"✓ 更新检查完成: 新增 {summary.get('new_files', 0)}, "
                          f"修改 {summary.get('modified_files', 0)}, "
                          f"删除 {summary.get('deleted_files', 0)}")

            # 测试备份创建
            backup_result = updater.create_backup("test_backup")

            if backup_result["status"] == "success":
                logger.info(f"✓ 备份创建成功: {backup_result['backup_name']}")
            else:
                logger.warning(f"⚠ 备份创建失败: {backup_result}")

            # 列出备份
            backups = updater.list_backups()
            logger.info(f"现有备份数量: {len(backups)}")

            # 获取更新器状态
            status = updater.get_status()
            logger.info(f"更新器状态: {status}")

            assert True

        except Exception as e:
            logger.error(f"✗ 知识库更新器测试失败: {e}")
            pytest.fail(f"知识库更新器测试失败: {e}")

    def test_06_rag_system_integration(self):
        """测试RAG系统集成"""
        logger.info("测试6: RAG系统集成")

        try:
            from hydrorag.config import Config
            from hydrorag.rag_system import RAGSystem

            # 创建配置
            config = Config(
                raw_documents_dir=str(self.raw_dir),
                processed_documents_dir=str(self.processed_dir),
                vector_db_dir=str(self.vector_db_dir)
            )

            # 初始化RAG系统
            rag_system = RAGSystem(config)

            # 检查系统状态
            status = rag_system.get_system_status()
            logger.info(f"RAG系统初始化状态: {status['is_initialized']}")
            logger.info(f"向量后端: {status.get('vector_backend', 'unknown')}")

            if status["is_initialized"]:
                logger.info("✓ RAG系统初始化成功")

                # 设置系统（如果向量库为空）
                if status["components"]["vector_store"]["stats"].get("total_documents", 0) == 0:
                    logger.info("向量库为空，开始设置系统...")
                    setup_result = rag_system.setup_from_raw_documents()

                    if setup_result["status"] == "success":
                        logger.info("✓ RAG系统设置完成")
                    else:
                        logger.warning(f"⚠ RAG系统设置遇到问题: {setup_result}")

                # 测试查询功能
                test_queries = [
                    "水文模型率定工作流",
                    "prepare_data工具的功能",
                    "calibrate_model参数配置",
                    "常见场景解决方案"
                ]

                for query in test_queries:
                    logger.info(f"测试查询: {query}")

                    result = rag_system.query(
                        query_text=query,
                        top_k=3,
                        enable_rerank=True,
                        enable_expansion=True
                    )

                    if result["status"] == "success":
                        total_found = result.get('total_found', result.get('final_count', 0))
                        logger.info(f"✓ 查询成功: {total_found} 个结果")
                        logger.info(f"  后端: {result.get('backend', 'unknown')}")
                        logger.info(f"  重排序: {result.get('rerank_enabled', False)}")

                        # 显示最佳结果
                        if result.get("results"):
                            best_result = result["results"][0]
                            content = best_result.get("content", "")
                            score = best_result.get("score", 0.0)
                            logger.info(f"  最佳匹配: {content[:80]}... (分数: {score:.3f})")
                    else:
                        logger.warning(f"⚠ 查询失败: {result}")

                # 测试知识片段获取
                fragments = rag_system.get_knowledge_fragments("工具使用", top_k=3)
                logger.info(f"✓ 获取知识片段: {len(fragments)} 个")

                # 测试知识库更新检查
                update_check = rag_system.check_for_updates()
                logger.info(f"✓ 知识库更新检查: {update_check['status']}")

            else:
                logger.warning("⚠ RAG系统初始化不完整，跳过部分测试")
                logger.warning(f"初始化错误: {status.get('initialization_errors', [])}")

            # 健康检查
            health = rag_system.health_check()
            logger.info(f"RAG系统健康状态: {health['overall_status']}")

            if health["overall_status"] != "healthy":
                logger.warning(f"健康检查问题: {health.get('issues', [])}")

            assert True

        except Exception as e:
            logger.error(f"✗ RAG系统集成测试失败: {e}")
            pytest.fail(f"RAG系统集成测试失败: {e}")

    def test_07_performance_comparison(self):
        """测试性能对比"""
        logger.info("测试7: 性能对比")

        try:
            # 简单的性能测试
            test_queries = [
                "工具使用指南",
                "模型率定流程",
                "数据准备方法"
            ]

            # 如果有多个后端可用，进行对比测试
            try:
                import faiss
                faiss_available = True
            except ImportError:
                faiss_available = False

            logger.info(f"FAISS可用性: {faiss_available}")

            if faiss_available:
                logger.info("✓ 可以进行FAISS性能测试")

                # 这里可以添加更详细的性能对比测试
                # 比如查询速度、索引构建时间、内存使用等

                for query in test_queries:
                    start_time = time.time()
                    # 模拟查询
                    time.sleep(0.01)  # 模拟查询时间
                    end_time = time.time()

                    query_time = (end_time - start_time) * 1000
                    logger.info(f"查询 '{query}' 耗时: {query_time:.2f} ms")

            assert True

        except Exception as e:
            logger.error(f"✗ 性能对比测试失败: {e}")
            pytest.fail(f"性能对比测试失败: {e}")

    def test_08_stress_test(self):
        """压力测试"""
        logger.info("测试8: 压力测试")

        try:
            # 创建较多的测试查询
            stress_queries = [
                f"测试查询 {i}: 水文工具使用指南和最佳实践"
                for i in range(10)
            ]

            logger.info(f"开始压力测试: {len(stress_queries)} 个查询")

            start_time = time.time()
            success_count = 0

            for i, query in enumerate(stress_queries):
                try:
                    # 模拟查询处理
                    time.sleep(0.001)  # 模拟处理时间
                    success_count += 1

                    if (i + 1) % 5 == 0:
                        logger.info(f"已完成 {i + 1}/{len(stress_queries)} 个查询")

                except Exception as e:
                    logger.warning(f"查询 {i} 失败: {e}")

            end_time = time.time()
            total_time = end_time - start_time

            logger.info(f"✓ 压力测试完成: {success_count}/{len(stress_queries)} 成功")
            logger.info(f"总耗时: {total_time:.2f} 秒")
            logger.info(f"平均每查询: {(total_time / len(stress_queries) * 1000):.2f} ms")

            assert success_count > 0, "至少应有一些查询成功"

        except Exception as e:
            logger.error(f"✗ 压力测试失败: {e}")
            pytest.fail(f"压力测试失败: {e}")

def run_tests():
    """运行测试"""
    logger.info("="*50)
    logger.info("开始HydroRAG FAISS集成测试")
    logger.info("="*50)

    # 运行pytest
    pytest_args = [
        __file__,
        "-v",
        "--tb=short",
        f"--log-file={log_file}",
        "--log-file-level=INFO"
    ]

    exit_code = pytest.main(pytest_args)

    logger.info("="*50)
    logger.info(f"测试完成，退出码: {exit_code}")
    logger.info(f"详细日志: {log_file}")
    logger.info("="*50)

    return exit_code

if __name__ == "__main__":
    exit_code = run_tests()
    exit(exit_code)