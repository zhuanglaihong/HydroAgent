"""
HydroRAG系统测试文件
包含各个组件的单元测试和集成测试
"""

import unittest
import tempfile
import shutil
import json
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch

# 添加项目根路径
repo_path = Path(os.path.abspath(__file__)).parent.parent
sys.path.append(str(repo_path))

# 导入要测试的模块
from hydrorag.config import Config
from hydrorag.document_processor import DocumentProcessor
from hydrorag.embeddings_manager import EmbeddingsManager
from hydrorag.vector_store import VectorStore
from hydrorag.rag_system import RAGSystem


class TestConfig(unittest.TestCase):
    """配置类测试"""
    
    def setUp(self):
        """测试前设置"""
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_default_config(self):
        """测试默认配置"""
        config = Config()
        
        # 检查默认值
        self.assertEqual(config.chunk_size, 500)
        self.assertEqual(config.chunk_overlap, 50)
        self.assertEqual(config.top_k, 5)
        self.assertEqual(config.score_threshold, 0.5)
        
        # 检查支持的文件扩展名
        self.assertIn(".pdf", config.supported_file_extensions)
        self.assertIn(".md", config.supported_file_extensions)
        self.assertIn(".txt", config.supported_file_extensions)
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = Config(
            documents_dir=self.temp_dir,
            chunk_size=1000,
            top_k=10
        )
        
        self.assertEqual(config.documents_dir, self.temp_dir)
        self.assertEqual(config.chunk_size, 1000)
        self.assertEqual(config.top_k, 10)
    
    def test_config_validation(self):
        """测试配置验证"""
        # 有效配置
        config = Config(documents_dir=self.temp_dir)
        self.assertTrue(config.validate())
        
        # 无效配置
        config.chunk_size = -1
        self.assertFalse(config.validate())
        
        config.chunk_size = 500
        config.chunk_overlap = 600  # 大于chunk_size
        self.assertFalse(config.validate())
    
    def test_config_save_load(self):
        """测试配置保存和加载"""
        config = Config(
            documents_dir=self.temp_dir,
            chunk_size=800,
            top_k=15
        )
        
        # 保存配置
        config_file = os.path.join(self.temp_dir, "test_config.json")
        config.save_to_file(config_file)
        
        # 加载配置
        loaded_config = Config.load_from_file(config_file)
        
        self.assertEqual(loaded_config.documents_dir, self.temp_dir)
        self.assertEqual(loaded_config.chunk_size, 800)
        self.assertEqual(loaded_config.top_k, 15)


class TestDocumentProcessor(unittest.TestCase):
    """文档处理器测试"""
    
    def setUp(self):
        """测试前设置"""
        # 使用项目的documents目录
        self.documents_dir = os.path.join(repo_path, "documents")
        self.config = Config(
            documents_dir=self.documents_dir,
            raw_documents_dir=os.path.join(self.documents_dir, "raw"),
            processed_documents_dir=os.path.join(self.documents_dir, "processed")
        )
        self.processor = DocumentProcessor(self.config)
        
        # 创建测试文档
        self.raw_dir = Path(self.config.raw_documents_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建测试文本文件
        test_content = "这是一个测试文档。\n\n包含水文模型GR4J的相关信息。\n\n模型有4个参数：X1、X2、X3、X4。"
        with open(self.raw_dir / "test_doc.txt", "w", encoding="utf-8") as f:
            f.write(test_content)
    
    def tearDown(self):
        """测试后清理"""
        if hasattr(self, 'temp_dir'):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        elif hasattr(self, 'documents_dir'):
            # 清理processed和vector_db目录
            processed_dir = os.path.join(self.documents_dir, "processed")
            vector_db_dir = os.path.join(self.documents_dir, "vector_db")
            for dir_path in [processed_dir, vector_db_dir]:
                if os.path.exists(dir_path):
                    shutil.rmtree(dir_path)
                    os.makedirs(dir_path, exist_ok=True)
    
    def test_scan_raw_documents(self):
        """测试扫描原始文档"""
        files = self.processor.scan_raw_documents()
        
        # 检查是否包含我们创建的测试文档
        test_doc_found = any(f.name == "test_doc.txt" for f in files)
        self.assertTrue(test_doc_found)
        self.assertGreater(len(files), 0)
    
    def test_process_document(self):
        """测试处理单个文档"""
        test_file = self.raw_dir / "test_doc.txt"
        result = self.processor.process_document(test_file)
        
        self.assertEqual(result["status"], "success")
        self.assertGreater(result["chunks_count"], 0)
        
        # 检查是否生成了处理后的文件
        processed_file = Path(result["processed_file"])
        self.assertTrue(processed_file.exists())
        
        # 检查处理后的数据格式
        with open(processed_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        self.assertIn("chunks", data)
        self.assertIn("source_file", data)
        self.assertGreater(len(data["chunks"]), 0)
    
    def test_process_all_documents(self):
        """测试处理所有文档"""
        result = self.processor.process_all_documents()
        
        self.assertEqual(result["status"], "completed")
        self.assertGreater(result["processed"], 0)  # 处理的文档数量应该大于0
        self.assertEqual(result["failed"], 0)
    
    def test_get_statistics(self):
        """测试获取统计信息"""
        # 先处理文档
        self.processor.process_all_documents()
        
        stats = self.processor.get_statistics()
        
        self.assertGreater(stats["raw_documents_count"], 0)  # 应该有原始文档
        self.assertGreater(stats["processed_documents_count"], 0)  # 应该有处理后的文档
        self.assertGreater(stats["total_chunks"], 0)


class TestEmbeddingsManager(unittest.TestCase):
    """嵌入模型管理器测试"""
    
    def setUp(self):
        """测试前设置"""
        self.config = Config(
            embedding_model_name="sentence-transformers/all-MiniLM-L6-v2",
            embedding_device="cpu"
        )
    
    @patch('hydrorag.embeddings_manager.EmbeddingsManager._try_ollama_embeddings')
    @patch('langchain_huggingface.HuggingFaceEmbeddings')
    def test_embeddings_manager_init(self, mock_embeddings, mock_ollama):
        """测试嵌入模型管理器初始化"""
        # 禁用Ollama尝试
        mock_ollama.return_value = False
        
        # 模拟嵌入模型
        mock_model = Mock()
        mock_model.embed_query.return_value = [0.1, 0.2, 0.3]
        mock_embeddings.return_value = mock_model
        
        manager = EmbeddingsManager(self.config)
        
        self.assertIsNotNone(manager.model)
        self.assertTrue(manager.is_available())
    
    @patch('hydrorag.embeddings_manager.EmbeddingsManager._try_ollama_embeddings')
    @patch('langchain_huggingface.HuggingFaceEmbeddings')
    def test_embed_text(self, mock_embeddings, mock_ollama):
        """测试文本嵌入"""
        # 禁用Ollama尝试
        mock_ollama.return_value = False
        
        # 模拟嵌入模型
        mock_model = Mock()
        test_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        mock_model.embed_query.return_value = test_embedding
        mock_embeddings.return_value = mock_model
        
        manager = EmbeddingsManager(self.config)
        
        # 测试单个文本嵌入
        embedding = manager.embed_text("测试文本")
        
        self.assertIsNotNone(embedding)
        self.assertEqual(len(embedding), len(test_embedding))  # 使用实际返回的长度
        self.assertIsInstance(embedding, list)
    
    @patch('hydrorag.embeddings_manager.EmbeddingsManager._try_ollama_embeddings')
    @patch('langchain_huggingface.HuggingFaceEmbeddings')
    def test_embed_documents_chunks(self, mock_embeddings, mock_ollama):
        """测试文档块嵌入"""
        # 禁用Ollama尝试
        mock_ollama.return_value = False
        
        # 模拟嵌入模型
        mock_model = Mock()
        mock_model.embed_query.return_value = [0.1, 0.2, 0.3]  # 用于测试模型
        mock_model.embed_documents.return_value = [
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6]
        ]
        mock_embeddings.return_value = mock_model
        
        manager = EmbeddingsManager(self.config)
        
        # 测试文档块嵌入
        chunks = [
            {"content": "第一个文本块"},
            {"content": "第二个文本块"}
        ]
        
        processed_chunks = manager.embed_documents_chunks(chunks)
        
        self.assertEqual(len(processed_chunks), 2)
        self.assertTrue(processed_chunks[0]["has_embedding"])
        self.assertTrue(processed_chunks[1]["has_embedding"])
        self.assertIsNotNone(processed_chunks[0]["embedding"])
        self.assertIsNotNone(processed_chunks[1]["embedding"])


class TestVectorStore(unittest.TestCase):
    """向量数据库测试"""
    
    def setUp(self):
        """测试前设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.config = Config(
            vector_db_dir=self.temp_dir,
            chroma_collection_name="test_collection"
        )
        
        # 模拟嵌入模型管理器
        self.mock_embeddings_manager = Mock()
        self.mock_embeddings_manager.is_available.return_value = True
        self.mock_embeddings_manager.embed_text.return_value = [0.1, 0.2, 0.3, 0.4, 0.5]
        self.mock_embeddings_manager.embed_documents_chunks.return_value = [
            {
                "content": "测试内容",
                "embedding": [0.1, 0.2, 0.3, 0.4, 0.5],
                "has_embedding": True
            }
        ]
    
    def tearDown(self):
        """测试后清理"""
        if hasattr(self, 'temp_dir'):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        elif hasattr(self, 'documents_dir'):
            # 清理processed和vector_db目录
            processed_dir = os.path.join(self.documents_dir, "processed")
            vector_db_dir = os.path.join(self.documents_dir, "vector_db")
            for dir_path in [processed_dir, vector_db_dir]:
                if os.path.exists(dir_path):
                    shutil.rmtree(dir_path)
                    os.makedirs(dir_path, exist_ok=True)
    
    @patch('chromadb.PersistentClient')
    def test_vector_store_init(self, mock_chromadb):
        """测试向量数据库初始化"""
        # 模拟Chroma客户端
        mock_client = Mock()
        mock_collection = Mock()
        mock_collection.count.return_value = 0
        mock_collection.metadata = {}
        
        mock_client.get_collection.side_effect = Exception("Collection not found")
        mock_client.create_collection.return_value = mock_collection
        mock_chromadb.return_value = mock_client
        
        vector_store = VectorStore(self.config, self.mock_embeddings_manager)
        
        self.assertIsNotNone(vector_store.client)
        self.assertIsNotNone(vector_store.collection)
        self.assertTrue(vector_store.is_available())
    
    @patch('chromadb.PersistentClient')
    def test_add_documents(self, mock_chromadb):
        """测试添加文档"""
        # 模拟Chroma
        mock_client = Mock()
        mock_collection = Mock()
        mock_collection.count.return_value = 1
        mock_collection.add = Mock()
        
        mock_client.get_collection.return_value = mock_collection
        mock_chromadb.return_value = mock_client
        
        vector_store = VectorStore(self.config, self.mock_embeddings_manager)
        
        # 测试添加文档
        chunks = [
            {
                "chunk_id": "test_001",
                "content": "测试文档内容",
                "source_file": "test.txt",
                "embedding": [0.1, 0.2, 0.3, 0.4, 0.5],
                "has_embedding": True
            }
        ]
        
        result = vector_store.add_documents(chunks)
        
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["added"], 1)
        mock_collection.add.assert_called_once()
    
    @patch('chromadb.PersistentClient')
    def test_query(self, mock_chromadb):
        """测试查询"""
        # 模拟Chroma查询结果
        mock_client = Mock()
        mock_collection = Mock()
        mock_collection.query.return_value = {
            "documents": [["测试文档内容"]],
            "metadatas": [[{"source_file": "test.txt"}]],
            "distances": [[0.1]]
        }
        
        mock_client.get_collection.return_value = mock_collection
        mock_chromadb.return_value = mock_client
        
        vector_store = VectorStore(self.config, self.mock_embeddings_manager)
        
        # 测试查询
        result = vector_store.query(
            query_text="测试查询",
            n_results=5,
            score_threshold=0.5
        )
        
        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["documents"]), 1)
        self.assertGreater(result["scores"][0], 0.5)


class TestRAGSystem(unittest.TestCase):
    """RAG系统集成测试"""
    
    def setUp(self):
        """测试前设置"""
        # 使用项目的documents目录
        self.documents_dir = os.path.join(repo_path, "documents")
        self.config = Config(
            documents_dir=self.documents_dir,
            raw_documents_dir=os.path.join(self.documents_dir, "raw"),
            processed_documents_dir=os.path.join(self.documents_dir, "processed"),
            vector_db_dir=os.path.join(self.documents_dir, "vector_db")
        )
        
        # 创建测试文档
        raw_dir = Path(self.config.raw_documents_dir)
        raw_dir.mkdir(parents=True, exist_ok=True)
        
        test_content = "GR4J是一个概念性水文模型，包含4个参数。X1是土壤蓄水容量参数。"
        with open(raw_dir / "gr4j_model.txt", "w", encoding="utf-8") as f:
            f.write(test_content)
    
    def tearDown(self):
        """测试后清理"""
        if hasattr(self, 'temp_dir'):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        elif hasattr(self, 'documents_dir'):
            # 清理processed和vector_db目录
            processed_dir = os.path.join(self.documents_dir, "processed")
            vector_db_dir = os.path.join(self.documents_dir, "vector_db")
            for dir_path in [processed_dir, vector_db_dir]:
                if os.path.exists(dir_path):
                    shutil.rmtree(dir_path)
                    os.makedirs(dir_path, exist_ok=True)
    
    @patch('hydrorag.embeddings_manager.EmbeddingsManager._try_ollama_embeddings')
    @patch('langchain_huggingface.HuggingFaceEmbeddings')
    @patch('chromadb.PersistentClient')
    def test_rag_system_init(self, mock_chromadb, mock_embeddings, mock_ollama):
        """测试RAG系统初始化"""
        # 禁用Ollama尝试
        mock_ollama.return_value = False
        
        # 模拟嵌入模型
        mock_model = Mock()
        mock_model.embed_query.return_value = [0.1, 0.2, 0.3]
        mock_embeddings.return_value = mock_model
        
        # 模拟Chroma
        mock_client = Mock()
        mock_collection = Mock()
        mock_collection.count.return_value = 0
        mock_collection.metadata = {}
        
        mock_client.get_collection.side_effect = Exception("Collection not found")
        mock_client.create_collection.return_value = mock_collection
        mock_chromadb.return_value = mock_client
        
        # 创建RAG系统
        rag_system = RAGSystem(self.config)
        
        self.assertTrue(rag_system.is_initialized)
        self.assertIsNotNone(rag_system.embeddings_manager)
        self.assertIsNotNone(rag_system.vector_store)
        self.assertIsNotNone(rag_system.document_processor)
    
    @patch('hydrorag.embeddings_manager.EmbeddingsManager._try_ollama_embeddings')
    @patch('langchain_huggingface.HuggingFaceEmbeddings')
    @patch('chromadb.PersistentClient')
    def test_process_documents(self, mock_chromadb, mock_embeddings, mock_ollama):
        """测试文档处理"""
        # 禁用Ollama尝试
        mock_ollama.return_value = False
        
        # 模拟组件
        self._setup_mocks(mock_chromadb, mock_embeddings)
        
        rag_system = RAGSystem(self.config)
        
        # 测试文档处理
        result = rag_system.process_documents()
        
        self.assertEqual(result["status"], "completed")
        self.assertGreater(result["processed"], 0)
    
    @patch('hydrorag.embeddings_manager.EmbeddingsManager._try_ollama_embeddings')
    @patch('langchain_huggingface.HuggingFaceEmbeddings')
    @patch('chromadb.PersistentClient')
    def test_health_check(self, mock_chromadb, mock_embeddings, mock_ollama):
        """测试健康检查"""
        # 禁用Ollama尝试
        mock_ollama.return_value = False
        
        # 模拟组件
        self._setup_mocks(mock_chromadb, mock_embeddings)
        
        rag_system = RAGSystem(self.config)
        
        # 测试健康检查
        health = rag_system.health_check()
        
        # 注意：健康检查可能显示"unhealthy"因为向量数据库为空，这是正常的
        self.assertIn(health["overall_status"], ["healthy", "unhealthy"])
        self.assertEqual(health["checks"]["initialization"]["status"], "passed")
        self.assertEqual(health["checks"]["embeddings"]["status"], "passed")
        self.assertEqual(health["checks"]["vector_store"]["status"], "passed")
        self.assertEqual(health["checks"]["document_processor"]["status"], "passed")
    
    def _setup_mocks(self, mock_chromadb, mock_embeddings):
        """设置模拟对象"""
        # 模拟嵌入模型
        mock_model = Mock()
        mock_model.embed_query.return_value = [0.1, 0.2, 0.3, 0.4, 0.5]
        mock_model.embed_documents.return_value = [[0.1, 0.2, 0.3, 0.4, 0.5]]
        mock_embeddings.return_value = mock_model
        
        # 模拟Chroma
        mock_client = Mock()
        mock_collection = Mock()
        mock_collection.count.return_value = 0
        mock_collection.metadata = {}
        mock_collection.add = Mock()
        
        # 修复向量存储的统计信息模拟
        mock_collection.get.return_value = {
            'ids': [],
            'documents': [],
            'metadatas': []
        }
        
        # 模拟_get_collection_info方法
        mock_collection.metadata = {}
        
        mock_client.get_collection.side_effect = Exception("Collection not found")
        mock_client.create_collection.return_value = mock_collection
        mock_chromadb.return_value = mock_client


class TestIntegration(unittest.TestCase):
    """集成测试"""
    
    def setUp(self):
        """测试前设置"""
        # 使用项目的documents目录
        self.documents_dir = os.path.join(repo_path, "documents")
        
        # 创建完整的测试环境
        self.config = Config(
            documents_dir=self.documents_dir,
            raw_documents_dir=os.path.join(self.documents_dir, "raw"),
            processed_documents_dir=os.path.join(self.documents_dir, "processed"),
            vector_db_dir=os.path.join(self.documents_dir, "vector_db"),
            chunk_size=100,  # 小一点的块用于测试
            chunk_overlap=20
        )
        
        # 创建多个测试文档
        raw_dir = Path(self.config.raw_documents_dir)
        raw_dir.mkdir(parents=True, exist_ok=True)
        
        docs = {
            "gr4j_model.txt": "GR4J是一个概念性水文模型，包含4个参数：X1土壤蓄水容量、X2地下水交换系数、X3最大地下水蓄水容量、X4单位线时间参数。",
            "model_calibration.txt": "模型率定是通过优化算法调整模型参数，使模型输出与观测数据匹配的过程。常用的优化算法包括SCE-UA、遗传算法等。",
            "evaluation_metrics.txt": "模型评估指标包括NSE、RMSE、MAE等。NSE值越接近1表示模型性能越好。"
        }
        
        for filename, content in docs.items():
            with open(raw_dir / filename, "w", encoding="utf-8") as f:
                f.write(content)
    
    def tearDown(self):
        """测试后清理"""
        if hasattr(self, 'temp_dir'):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        elif hasattr(self, 'documents_dir'):
            # 清理processed和vector_db目录
            processed_dir = os.path.join(self.documents_dir, "processed")
            vector_db_dir = os.path.join(self.documents_dir, "vector_db")
            for dir_path in [processed_dir, vector_db_dir]:
                if os.path.exists(dir_path):
                    shutil.rmtree(dir_path)
                    os.makedirs(dir_path, exist_ok=True)
    
    def test_quick_setup_function(self):
        """测试快速设置函数"""
        from hydrorag.rag_system import quick_setup
        
        # 由于快速设置需要真实的模型，这里只测试配置部分
        with patch('langchain_huggingface.HuggingFaceEmbeddings') as mock_embeddings, \
                patch('chromadb.PersistentClient') as mock_chromadb:
            
            # 模拟组件
            mock_model = Mock()
            mock_model.embed_query.return_value = [0.1, 0.2, 0.3]
            mock_embeddings.return_value = mock_model
            
            mock_client = Mock()
            mock_collection = Mock()
            mock_collection.count.return_value = 0
            mock_collection.metadata = {}
            
            mock_client.get_collection.side_effect = Exception("Collection not found")
            mock_client.create_collection.return_value = mock_collection
            mock_chromadb.return_value = mock_client
            
            # 测试快速设置
            rag_system = quick_setup(self.documents_dir)
            
            self.assertIsNotNone(rag_system)
            self.assertEqual(rag_system.config.documents_dir, self.documents_dir)


def run_tests():
    """运行所有测试"""
    import logging
    
    # 设置日志级别
    logging.basicConfig(level=logging.ERROR)
    
    # 创建测试套件
    test_suite = unittest.TestSuite()
    
    # 添加测试类
    test_classes = [
        TestConfig,
        TestDocumentProcessor,
        TestEmbeddingsManager,
        TestVectorStore,
        TestRAGSystem,
        TestIntegration
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # 返回测试结果
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
