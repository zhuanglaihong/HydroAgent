"""
Author: Claude Code
Date: 2025-10-12 16:10:00
LastEditTime: 2025-10-12 16:10:00
LastEditors: Claude Code
Description: 快速重建RAG向量索引（跳过嵌入模型测试，直接重建）
FilePath: \HydroAgent\script\quick_rag_rebuild.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import sys
from pathlib import Path
import logging
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 确保logs目录存在
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

# 设置详细日志
log_file = logs_dir / f"quick_rag_rebuild_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

def main():
    """快速重建RAG向量索引（跳过模型测试）"""
    try:
        logger.info("=" * 80)
        logger.info("快速重建RAG向量索引")
        logger.info(f"日志文件: {log_file}")
        logger.info("=" * 80)

        # 首先检查Ollama服务
        logger.info("\n步骤1: 检查Ollama服务...")
        import requests
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=3)
            if response.status_code == 200:
                models = [m["name"] for m in response.json().get("models", [])]
                logger.info(f"✓ Ollama服务正常运行")
                logger.info(f"  可用模型: {models}")

                # 检查是否有嵌入模型
                embed_models = [m for m in models if any(x in m.lower() for x in ["embed", "bge"])]
                if not embed_models:
                    logger.error("❌ 没有找到嵌入模型！")
                    logger.info("请运行: ollama pull bge-large:335m")
                    return
                else:
                    logger.info(f"  嵌入模型: {embed_models}")
            else:
                logger.error(f"❌ Ollama服务响应异常: HTTP {response.status_code}")
                return
        except requests.exceptions.ConnectionError:
            logger.error("❌ 无法连接到Ollama服务!")
            logger.info("请确保Ollama正在运行: ollama serve")
            return
        except Exception as e:
            logger.error(f"❌ 检查Ollama服务失败: {e}")
            return

        # 导入并配置
        logger.info("\n步骤2: 导入RAG系统...")
        from hydrorag.config import create_default_config
        from hydrorag.vector_store import VectorStore
        from hydrorag.embeddings_manager import EmbeddingsManager
        from hydrorag.document_processor import DocumentProcessor

        config = create_default_config()
        logger.info(f"配置:")
        logger.info(f"  - 向量数据库目录: {config.vector_db_dir}")
        logger.info(f"  - 文档目录: {config.documents_dir}")

        # 创建嵌入管理器（不测试模型）
        logger.info("\n步骤3: 初始化嵌入管理器（跳过测试）...")

        # 直接创建Ollama嵌入模型
        try:
            from langchain_ollama import OllamaEmbeddings
        except ImportError:
            from langchain_community.embeddings import OllamaEmbeddings

        # 使用找到的第一个嵌入模型
        embedding_model_name = embed_models[0]
        logger.info(f"使用嵌入模型: {embedding_model_name}")

        ollama_embeddings = OllamaEmbeddings(
            model=embedding_model_name,
            base_url="http://localhost:11434"
        )

        # 测试嵌入（简单测试，不用超时）
        logger.info("测试嵌入模型...")
        try:
            test_embedding = ollama_embeddings.embed_query("测试")
            embedding_dim = len(test_embedding)
            logger.info(f"✓ 嵌入模型工作正常，维度: {embedding_dim}")
        except Exception as e:
            logger.error(f"❌ 嵌入模型测试失败: {e}")
            logger.info("提示: 可能是模型需要时间加载，请重试")
            return

        # 创建向量存储
        logger.info("\n步骤4: 初始化向量数据库...")

        # 创建一个简化的嵌入管理器类
        class SimpleEmbeddingsManager:
            def __init__(self, model):
                self.model = model
                self.current_model_type = "ollama"

            def embed_text(self, text):
                return self.model.embed_query(text)

            def embed_texts(self, texts):
                return self.model.embed_documents(texts)

            def embed_documents_chunks(self, chunks):
                texts = [chunk.get("content", "") for chunk in chunks]
                embeddings = self.embed_texts(texts)

                processed_chunks = []
                for chunk, embedding in zip(chunks, embeddings):
                    processed_chunk = chunk.copy()
                    if embedding:
                        processed_chunk["embedding"] = embedding
                        processed_chunk["embedding_model"] = embedding_model_name
                        processed_chunk["has_embedding"] = True
                    else:
                        processed_chunk["embedding"] = None
                        processed_chunk["has_embedding"] = False
                    processed_chunks.append(processed_chunk)

                return processed_chunks

        embeddings_manager = SimpleEmbeddingsManager(ollama_embeddings)
        vector_store = VectorStore(config, embeddings_manager)

        # 检查现有数据
        stats = vector_store.get_statistics()
        logger.info(f"现有数据库统计:")
        logger.info(f"  - 文档总数: {stats.get('total_documents', 0)}")

        # 询问确认
        print("\n" + "=" * 80)
        print("警告: 此操作将清空现有向量数据库并重新构建索引!")
        print("=" * 80)
        response = input("是否继续? (yes/no): ")

        if response.lower() not in ['yes', 'y']:
            logger.info("用户取消操作")
            return

        # 清空集合
        logger.info("\n步骤5: 清空现有向量集合...")
        clear_result = vector_store.clear_collection()
        if clear_result.get("status") == "success":
            logger.info(f"✓ 成功清空集合，删除了 {clear_result.get('deleted', 0)} 个文档")

        # 处理文档
        logger.info("\n步骤6: 处理文档...")
        doc_processor = DocumentProcessor(config)

        documents_dir = Path(config.documents_dir)
        if not documents_dir.exists():
            logger.error(f"文档目录不存在: {documents_dir}")
            return

        # 获取所有文档文件
        doc_files = []
        for ext in config.supported_file_extensions:
            doc_files.extend(documents_dir.glob(f"**/*{ext}"))

        logger.info(f"找到 {len(doc_files)} 个文档文件")

        if not doc_files:
            logger.warning("没有找到文档文件")
            return

        # 处理并添加文档
        success_count = 0
        fail_count = 0

        for i, doc_file in enumerate(doc_files, 1):
            logger.info(f"\n处理文档 [{i}/{len(doc_files)}]: {doc_file.name}")

            try:
                # 处理文档
                chunks = doc_processor.process_file(str(doc_file))

                if not chunks:
                    logger.warning(f"  ⚠ 未能提取文档块")
                    fail_count += 1
                    continue

                logger.info(f"  - 提取了 {len(chunks)} 个文档块")

                # 添加到向量数据库
                result = vector_store.add_documents(chunks)

                if result.get("status") == "success":
                    logger.info(f"  ✓ 成功添加 {result.get('added', 0)} 个文档块")
                    success_count += 1
                else:
                    logger.error(f"  ✗ 添加失败: {result.get('error', 'Unknown')}")
                    fail_count += 1

            except Exception as e:
                logger.error(f"  ✗ 处理出错: {e}")
                fail_count += 1

        # 输出统计
        logger.info("\n" + "=" * 80)
        logger.info("文档处理完成")
        logger.info(f"  - 成功: {success_count}")
        logger.info(f"  - 失败: {fail_count}")
        logger.info("=" * 80)

        # 检查最终状态
        logger.info("\n步骤7: 检查重建后的数据库...")
        final_stats = vector_store.get_statistics()
        logger.info(f"重建后数据库统计:")
        logger.info(f"  - 文档总数: {final_stats.get('total_documents', 0)}")
        logger.info(f"  - 嵌入模型: {final_stats.get('embedding_models', [])}")

        # 测试查询
        logger.info("\n步骤8: 测试RAG查询功能...")
        test_query = "如何使用GR4J模型进行率定"

        try:
            query_result = vector_store.query(test_query, n_results=3)

            if query_result.get("status") == "success":
                results = query_result.get("documents", [])
                logger.info(f"✓ 查询成功，返回 {len(results)} 个结果")

                for i, (doc, score) in enumerate(zip(
                    query_result.get("documents", []),
                    query_result.get("scores", [])
                ), 1):
                    logger.info(f"\n结果 {i}:")
                    logger.info(f"  - 分数: {score:.4f}")
                    logger.info(f"  - 内容: {doc[:100]}...")
            else:
                logger.error(f"✗ 查询失败: {query_result.get('error', 'Unknown')}")

        except Exception as e:
            logger.error(f"✗ 查询出错: {e}")

        logger.info("\n" + "=" * 80)
        logger.info("RAG索引重建完成!")
        logger.info(f"详细日志: {log_file}")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"重建索引失败: {e}", exc_info=True)

if __name__ == "__main__":
    main()
