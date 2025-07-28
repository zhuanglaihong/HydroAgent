"""
Author: zhuanglaihong
Date: 2025-07-24 15:03:46
LastEditTime: 2025-07-24 15:03:46
LastEditors: zhuanglaihong
Description: RAG系统测试模块 - 测试文档加载、向量存储、检索和生成功能
FilePath: test/test_rag_system.py
Copyright: Copyright (c) 2021-2024 zhuanglaihong. All rights reserved.
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path
import unittest
from typing import List, Dict, Any

# 添加项目根目录到路径
repo_path = Path(os.path.abspath(__file__)).parent.parent
sys.path.append(str(repo_path))

import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TestDocumentLoader(unittest.TestCase):
    """文档加载器测试"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test.txt")

        # 创建测试文件
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write("这是一个测试文档。\n它包含多个段落。\n用于测试文档加载功能。")

    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir)

    def test_document_loader_import(self):
        """测试文档加载器导入"""
        try:
            from RAG.document_loader import DocumentLoader

            loader = DocumentLoader()
            self.assertIsNotNone(loader)
            print("✅ 文档加载器导入成功")
        except Exception as e:
            self.fail(f"文档加载器导入失败: {e}")

    def test_load_single_document(self):
        """测试加载单个文档"""
        try:
            from RAG.document_loader import DocumentLoader

            loader = DocumentLoader()
            documents = loader.load_document(self.test_file)

            self.assertIsInstance(documents, list)
            self.assertGreater(len(documents), 0)
            self.assertIn("测试文档", documents[0].page_content)

            print(f"✅ 成功加载文档，文档数量: {len(documents)}")

        except Exception as e:
            self.fail(f"加载单个文档失败: {e}")

    def test_split_documents(self):
        """测试文档分割"""
        try:
            from RAG.document_loader import DocumentLoader

            loader = DocumentLoader(chunk_size=50, chunk_overlap=10)
            documents = loader.load_document(self.test_file)
            split_docs = loader.split_documents(documents)

            self.assertGreater(len(split_docs), len(documents))
            print(f"✅ 文档分割成功，原始: {len(documents)}, 分割后: {len(split_docs)}")

        except Exception as e:
            self.fail(f"文档分割失败: {e}")


class TestVectorStore(unittest.TestCase):
    """向量存储测试"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.index_path = os.path.join(self.temp_dir, "test_index")

        # 创建模拟嵌入模型
        class MockEmbeddings:
            def embed_documents(self, texts):
                return [[0.1] * 384] * len(texts)

            def embed_query(self, text):
                return [0.1] * 384

        self.embeddings = MockEmbeddings()

    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir)

    def test_vector_store_import(self):
        """测试向量存储导入"""
        try:
            from RAG.vector_store import VectorStore

            vector_store = VectorStore(self.embeddings)
            self.assertIsNotNone(vector_store)
            print("✅ 向量存储导入成功")
        except Exception as e:
            self.fail(f"向量存储导入失败: {e}")

    def test_create_index(self):
        """测试创建索引"""
        try:
            from RAG.vector_store import VectorStore
            from langchain.schema import Document

            vector_store = VectorStore(self.embeddings, self.index_path)

            # 创建测试文档
            documents = [
                Document(
                    page_content="这是第一个测试文档", metadata={"source": "test1"}
                ),
                Document(
                    page_content="这是第二个测试文档", metadata={"source": "test2"}
                ),
            ]

            vector_store.create_index(documents)

            # 检查索引是否创建
            info = vector_store.get_index_info()
            self.assertIn("status", info)

            print("✅ 向量索引创建成功")

        except Exception as e:
            self.fail(f"创建索引失败: {e}")


class TestRetriever(unittest.TestCase):
    """检索器测试"""

    def setUp(self):
        """测试前准备"""

        # 创建模拟嵌入模型
        class MockEmbeddings:
            def embed_documents(self, texts):
                return [[0.1] * 384] * len(texts)

            def embed_query(self, text):
                return [0.1] * 384

        self.embeddings = MockEmbeddings()

        # 创建测试文档
        from langchain.schema import Document

        self.documents = [
            Document(
                page_content="这是关于机器学习的文档", metadata={"source": "ml_doc"}
            ),
            Document(
                page_content="这是关于深度学习的文档", metadata={"source": "dl_doc"}
            ),
            Document(
                page_content="这是关于自然语言处理的文档",
                metadata={"source": "nlp_doc"},
            ),
        ]

    def test_retriever_import(self):
        """测试检索器导入"""
        try:
            from RAG.retriever import Retriever

            retriever = Retriever(documents=self.documents)
            self.assertIsNotNone(retriever)
            print("✅ 检索器导入成功")
        except Exception as e:
            self.fail(f"检索器导入失败: {e}")

    def test_available_retrievers(self):
        """测试可用检索器"""
        try:
            from RAG.retriever import Retriever

            retriever = Retriever(documents=self.documents)
            available = retriever.get_available_retrievers()

            self.assertIsInstance(available, list)
            self.assertGreater(len(available), 0)

            print(f"✅ 可用检索器: {available}")

        except Exception as e:
            self.fail(f"获取可用检索器失败: {e}")


class TestGenerator(unittest.TestCase):
    """生成器测试"""

    def setUp(self):
        """测试前准备"""

        # 创建模拟语言模型
        class MockLLM:
            def __call__(self, prompt):
                return "这是一个模拟的回答。"

            def generate(self, prompts):
                return ["这是一个模拟的回答。"] * len(prompts)

        self.llm = MockLLM()

        # 创建测试文档
        from langchain.schema import Document

        self.documents = [
            Document(
                page_content="机器学习是人工智能的一个分支",
                metadata={"source": "ml_doc"},
            ),
            Document(
                page_content="深度学习使用神经网络进行学习",
                metadata={"source": "dl_doc"},
            ),
        ]

    def test_generator_import(self):
        """测试生成器导入"""
        try:
            from RAG.generator import Generator

            generator = Generator(self.llm)
            self.assertIsNotNone(generator)
            print("✅ 生成器导入成功")
        except Exception as e:
            self.fail(f"生成器导入失败: {e}")

    def test_available_generators(self):
        """测试可用生成器"""
        try:
            from RAG.generator import Generator

            generator = Generator(self.llm)
            available = generator.get_available_generators()

            self.assertIsInstance(available, list)
            self.assertGreater(len(available), 0)

            print(f"✅ 可用生成器: {available}")

        except Exception as e:
            self.fail(f"获取可用生成器失败: {e}")


class TestRAGSystem(unittest.TestCase):
    """RAG系统集成测试"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.index_path = os.path.join(self.temp_dir, "rag_index")

        # 创建模拟嵌入模型
        class MockEmbeddings:
            def embed_documents(self, texts):
                return [[0.1] * 384] * len(texts)

            def embed_query(self, text):
                return [0.1] * 384

        # 创建模拟语言模型
        class MockLLM:
            def __call__(self, prompt):
                return "这是一个基于检索结果的回答。"

            def generate(self, prompts):
                return ["这是一个基于检索结果的回答。"] * len(prompts)

        self.embeddings = MockEmbeddings()
        self.llm = MockLLM()

        # 创建测试文件
        self.test_file = os.path.join(self.temp_dir, "test_doc.txt")
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write(
                """
            机器学习是人工智能的一个重要分支。
            它通过算法和统计模型使计算机系统能够自动学习和改进。
            深度学习是机器学习的一个子领域，使用多层神经网络。
            自然语言处理是人工智能的另一个重要应用领域。
            """
            )

    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir)

    def test_rag_system_import(self):
        """测试RAG系统导入"""
        try:
            from RAG.rag_system import RAGSystem

            rag_system = RAGSystem(self.embeddings, self.llm, self.index_path)
            self.assertIsNotNone(rag_system)
            print("✅ RAG系统导入成功")
        except Exception as e:
            self.fail(f"RAG系统导入失败: {e}")

    def test_load_documents(self):
        """测试加载文档"""
        try:
            from RAG.rag_system import RAGSystem

            rag_system = RAGSystem(self.embeddings, self.llm, self.index_path)
            doc_count = rag_system.load_documents(self.test_file)

            self.assertGreater(doc_count, 0)
            print(f"✅ 成功加载 {doc_count} 个文档")

        except Exception as e:
            self.fail(f"加载文档失败: {e}")

    def test_create_index(self):
        """测试创建索引"""
        try:
            from RAG.rag_system import RAGSystem

            rag_system = RAGSystem(self.embeddings, self.llm, self.index_path)
            rag_system.load_documents(self.test_file)

            success = rag_system.create_index()
            self.assertTrue(success)
            print("✅ 索引创建成功")

        except Exception as e:
            self.fail(f"创建索引失败: {e}")

    def test_query_system(self):
        """测试查询系统"""
        try:
            from RAG.rag_system import RAGSystem

            rag_system = RAGSystem(self.embeddings, self.llm, self.index_path)
            rag_system.load_documents(self.test_file)
            rag_system.create_index()

            # 执行查询
            result = rag_system.query("什么是机器学习？")

            self.assertIsInstance(result, dict)
            self.assertIn("success", result)
            self.assertIn("answer", result)

            print(f"✅ 查询成功，结果: {result['answer'][:50]}...")

        except Exception as e:
            self.fail(f"查询系统失败: {e}")

    def test_system_info(self):
        """测试系统信息"""
        try:
            from RAG.rag_system import RAGSystem

            rag_system = RAGSystem(self.embeddings, self.llm, self.index_path)
            rag_system.load_documents(self.test_file)
            rag_system.create_index()

            info = rag_system.get_system_info()

            self.assertIsInstance(info, dict)
            self.assertIn("documents_loaded", info)
            self.assertIn("index_created", info)

            print(f"✅ 系统信息: {info}")

        except Exception as e:
            self.fail(f"获取系统信息失败: {e}")


def test_rag_integration():
    """RAG系统集成测试"""
    print("\n=== RAG系统集成测试 ===")

    try:
        # 测试基本导入
        from RAG import RAGSystem, DocumentLoader, VectorStore, Retriever, Generator

        print("✅ RAG模块导入成功")

        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        test_file = os.path.join(temp_dir, "integration_test.txt")

        # 创建测试文件
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(
                """
            这是一个集成测试文档。
            它包含了多个段落和不同的主题。
            用于测试RAG系统的完整功能。
            包括文档加载、向量化、检索和生成。
            """
            )

        # 创建模拟模型
        class MockEmbeddings:
            def embed_documents(self, texts):
                return [[0.1] * 384] * len(texts)

            def embed_query(self, text):
                return [0.1] * 384

        class MockLLM:
            def __call__(self, prompt):
                return "基于检索结果，这是集成测试的回答。"

        # 初始化RAG系统
        embeddings = MockEmbeddings()
        llm = MockLLM()
        index_path = os.path.join(temp_dir, "test_index")

        rag_system = RAGSystem(embeddings, llm, index_path)

        # 测试完整流程
        print("1. 加载文档...")
        doc_count = rag_system.load_documents(test_file)
        print(f"   加载了 {doc_count} 个文档")

        print("2. 创建索引...")
        success = rag_system.create_index()
        print(f"   索引创建{'成功' if success else '失败'}")

        print("3. 执行查询...")
        result = rag_system.query("什么是集成测试？")
        print(f"   查询结果: {result['answer'][:50]}...")

        print("4. 获取系统信息...")
        info = rag_system.get_system_info()
        print(f"   系统信息: {info}")

        # 清理
        shutil.rmtree(temp_dir)

        print("✅ RAG系统集成测试完成")
        return True

    except Exception as e:
        print(f"❌ RAG系统集成测试失败: {e}")
        return False


def main():
    """主测试函数"""
    print("开始RAG系统测试...")

    # 运行单元测试
    test_suite = unittest.TestSuite()

    # 添加测试类
    test_suite.addTest(unittest.makeSuite(TestDocumentLoader))
    test_suite.addTest(unittest.makeSuite(TestVectorStore))
    test_suite.addTest(unittest.makeSuite(TestRetriever))
    test_suite.addTest(unittest.makeSuite(TestGenerator))
    test_suite.addTest(unittest.makeSuite(TestRAGSystem))

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)

    # 运行集成测试
    integration_success = test_rag_integration()

    # 总结结果
    print(f"\n=== 测试总结 ===")
    print(f"单元测试: {'通过' if result.wasSuccessful() else '失败'}")
    print(f"集成测试: {'通过' if integration_success else '失败'}")

    if result.wasSuccessful() and integration_success:
        print("🎉 所有测试通过！")
    else:
        print("⚠️  部分测试失败，请检查错误信息")


if __name__ == "__main__":
    main()
