"""
测试HydroRAG系统与知识检索器的集成
涉及到hydrorag的全部功能以及workflow的知识检索器功能
测试从原始文档构建向量库，并通过知识检索器获取信息
"""

import unittest
import logging
import sys
import os
from pathlib import Path
from typing import List, Dict, Any

# 添加项目根路径
repo_path = Path(os.path.abspath(__file__)).parent.parent
sys.path.append(str(repo_path))

# 导入相关模块
from hydrorag.rag_system import RAGSystem, quick_setup
from hydrorag.config import Config
from workflow.knowledge_retriever import KnowledgeRetriever
from workflow.workflow_types import KnowledgeFragment

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestHydroRAGKnowledgeIntegration(unittest.TestCase):
    """HydroRAG系统与知识检索器集成测试"""
    
    def setUp(self):
        """测试前设置"""
        self.documents_dir = os.path.join(repo_path, "documents")
        self.raw_documents_dir = os.path.join(self.documents_dir, "raw")
        
        # 配置HydroRAG系统
        self.config = Config(
            documents_dir=self.documents_dir,
            raw_documents_dir=self.raw_documents_dir,
            processed_documents_dir=os.path.join(self.documents_dir, "processed"),
            vector_db_dir=os.path.join(self.documents_dir, "vector_db"),
            chunk_size=300,  # 稍大的块用于更好的语义完整性
            chunk_overlap=50,
            top_k=5,
            score_threshold=0.3
        )
        
        # 初始化RAG系统
        self.rag_system = None
        self.knowledge_retriever = None
        
    def tearDown(self):
        """测试后清理"""
        # 不清理向量数据库，以便后续使用
        pass
    
    def test_01_setup_rag_system(self):
        """测试1：设置RAG系统"""
        logger.info("=" * 60)
        logger.info("测试1：设置RAG系统")
        logger.info("=" * 60)
        
        try:
            # 使用快速设置
            self.rag_system = quick_setup(self.documents_dir)
            
            self.assertIsNotNone(self.rag_system, "RAG系统应该初始化成功")
            self.assertTrue(self.rag_system.is_initialized, "RAG系统应该完全初始化")
            
            logger.info("✅ RAG系统设置成功")
            
        except Exception as e:
            logger.error(f"❌ RAG系统设置失败: {e}")
            self.fail(f"RAG系统设置失败: {e}")
    
    def test_02_process_documents(self):
        """测试2：处理原始文档"""
        logger.info("=" * 60)
        logger.info("测试2：处理原始文档")
        logger.info("=" * 60)
        
        # 如果RAG系统未初始化，先初始化
        if self.rag_system is None:
            self.test_01_setup_rag_system()
        
        try:
            # 处理文档
            result = self.rag_system.setup_from_raw_documents()
            
            self.assertEqual(result["status"], "success", "处理应该成功完成")
            
            # 检查处理结果
            if result.get("skipped", False):
                # 使用已存在的向量库是正常情况
                logger.info("✅ 使用已存在的处理结果:")
                logger.info(f"   已处理文档数: {result.get('processed', 0)}")
                logger.info(f"   向量库文档数: {result.get('in_vector_store', 0)}")
                
                # 验证已有的数据
                self.assertGreater(result.get("processed", 0), 0, "应该有已处理的文档")
                self.assertGreater(result.get("in_vector_store", 0), 0, "向量库应该有文档")
            else:
                # 新处理文档的情况
                logger.info("✅ 完成新文档处理:")
                process_result = result["steps"]["document_processing"]
                index_result = result["steps"]["index_building"]
                
                # 验证处理结果
                self.assertIn(process_result["status"], ["completed", "success"], "文档处理步骤应该成功")
                self.assertGreater(process_result.get("processed", 0), 0, "应该处理至少1个文档")
                
                # 输出处理统计
                logger.info(f"   处理的文档数: {process_result.get('processed', 0)}")
                logger.info(f"   失败的文档数: {process_result.get('failed', 0)}")
                logger.info(f"   添加到向量库的块数: {index_result.get('total_chunks_added', 0)}")
            
        except Exception as e:
            logger.error(f"❌ 系统设置过程中出错: {e}")
            self.fail(f"系统设置失败: {e}")
    
    def test_03_setup_knowledge_retriever(self):
        """测试3：设置知识检索器"""
        logger.info("=" * 60)
        logger.info("测试3：设置知识检索器")
        logger.info("=" * 60)
        
        # 确保RAG系统已初始化
        if self.rag_system is None:
            self.test_01_setup_rag_system()
        
        try:
            # 初始化知识检索器
            self.knowledge_retriever = KnowledgeRetriever(
                rag_system=self.rag_system,
                enable_fallback=True
            )
            
            self.assertIsNotNone(self.knowledge_retriever, "知识检索器应该初始化成功")
            
            # 获取系统信息
            system_info = self.knowledge_retriever.get_system_info()
            logger.info("✅ 知识检索器设置成功")
            logger.info(f"   RAG系统可用: {system_info['rag_system_available']}")
            logger.info(f"   回退模式启用: {system_info['fallback_enabled']}")
            logger.info(f"   默认知识库片段数: {system_info['default_knowledge_count']}")
            
            # 验证系统状态
            self.assertTrue(system_info['rag_system_available'], "RAG系统应该可用")
            self.assertTrue(system_info['fallback_enabled'], "回退模式应该启用")
            self.assertGreater(system_info['default_knowledge_count'], 0, "应该有默认知识片段")
            
        except Exception as e:
            logger.error(f"❌ 知识检索器设置失败: {e}")
            self.fail(f"知识检索器设置失败: {e}")
    
    def test_04_test_different_queries(self):
        """测试4：测试不同类型的查询"""
        logger.info("=" * 60)
        logger.info("测试4：测试不同类型的查询")
        logger.info("=" * 60)
        
        # 确保系统已初始化
        if self.rag_system is None:
            self.test_01_setup_rag_system()
        if self.knowledge_retriever is None:
            self.test_03_setup_knowledge_retriever()
        
        # 定义测试查询
        test_queries = [
            {
                "query": "GR4J模型有哪些参数？",
                "category": "模型参数",
                "expected_keywords": ["X1", "X2", "X3", "X4", "参数", "GR4J"]
            },
            {
                "query": "如何进行模型率定？",
                "category": "模型率定",
                "expected_keywords": ["率定", "calibration", "优化", "参数调整"]
            },
            {
                "query": "模型评估指标有哪些？",
                "category": "模型评估",
                "expected_keywords": ["NSE", "RMSE", "MAE", "评估", "指标"]
            },
            {
                "query": "数据预处理包含哪些步骤？",
                "category": "数据处理",
                "expected_keywords": ["预处理", "清洗", "格式", "缺失值"]
            },
            {
                "query": "CAMELS数据集的特点",
                "category": "数据集",
                "expected_keywords": ["CAMELS", "数据集", "流域", "水文"]
            }
        ]
        
        results = []
        
        for i, test_case in enumerate(test_queries, 1):
            logger.info(f"\n--- 查询 {i}: {test_case['category']} ---")
            logger.info(f"问题: {test_case['query']}")
            
            try:
                # 执行检索
                fragments = self.knowledge_retriever.retrieve_knowledge(
                    expanded_query=test_case['query'],
                    k=3,
                    score_threshold=0.2,
                    use_rag_system=True
                )
                
                # 后处理
                processed_fragments = self.knowledge_retriever.post_process_fragments(fragments)
                
                # 分析结果
                result = self._analyze_retrieval_result(
                    test_case, processed_fragments
                )
                results.append(result)
                
                # 输出结果
                logger.info(f"检索到片段数: {len(processed_fragments)}")
                
                if processed_fragments:
                    for j, fragment in enumerate(processed_fragments[:2], 1):
                        logger.info(f"  片段 {j} (得分: {fragment.score:.3f}):")
                        logger.info(f"    内容: {fragment.content[:150]}...")
                        logger.info(f"    来源: {fragment.source}")
                
                # 检查是否包含期望的关键词
                found_keywords = self._check_keywords(processed_fragments, test_case['expected_keywords'])
                logger.info(f"  找到的期望关键词: {found_keywords}")
                
                if len(processed_fragments) > 0:
                    logger.info("✅ 检索成功")
                else:
                    logger.warning("⚠️  未检索到结果")
                
            except Exception as e:
                logger.error(f"❌ 查询失败: {e}")
                results.append({
                    "query": test_case['query'],
                    "category": test_case['category'],
                    "success": False,
                    "error": str(e)
                })
        
        # 总结测试结果
        self._summarize_test_results(results)
        
        # 至少应该有一些成功的查询
        successful_queries = sum(1 for r in results if r.get('success', False))
        self.assertGreater(successful_queries, 0, "至少应该有一个成功的查询")
    
    def test_05_integration_with_workflow(self):
        """测试5：与工作流集成测试"""
        logger.info("=" * 60)
        logger.info("测试5：与工作流集成测试")
        logger.info("=" * 60)
        
        # 确保系统已初始化
        if self.rag_system is None:
            self.test_01_setup_rag_system()
        if self.knowledge_retriever is None:
            self.test_03_setup_knowledge_retriever()
        
        try:
            # 模拟工作流场景：用户想要了解如何使用GR4J模型
            workflow_query = "我想用GR4J模型进行流域建模，需要了解模型参数、数据准备和率定评估的完整流程"
            
            logger.info(f"工作流查询: {workflow_query}")
            
            # 检索相关知识
            fragments = self.knowledge_retriever.retrieve_knowledge(
                expanded_query=workflow_query,
                k=5,
                score_threshold=0.2
            )
            
            # 后处理
            processed_fragments = self.knowledge_retriever.post_process_fragments(fragments)
            
            # 生成知识总结
            summary = self.knowledge_retriever.summarize_fragments(processed_fragments)
            
            logger.info("\n📚 检索到的知识总结:")
            logger.info(summary)
            
            # 验证集成效果
            self.assertGreater(len(processed_fragments), 0, "应该检索到相关知识片段")
            self.assertIsInstance(summary, str, "总结应该是字符串")
            self.assertGreater(len(summary), 50, "总结应该包含足够的内容")
            
            # 验证知识片段的多样性（应该涵盖不同类别）
            categories = set()
            for fragment in processed_fragments:
                if 'category' in fragment.metadata:
                    categories.add(fragment.metadata['category'])
            
            logger.info(f"涵盖的知识类别: {list(categories)}")
            logger.info("✅ 工作流集成测试成功")
            
        except Exception as e:
            logger.error(f"❌ 工作流集成测试失败: {e}")
            self.fail(f"工作流集成测试失败: {e}")
    
    def test_06_system_health_check(self):
        """测试6：系统健康检查"""
        logger.info("=" * 60)
        logger.info("测试6：系统健康检查")
        logger.info("=" * 60)
        
        try:
            # RAG系统健康检查
            if self.rag_system:
                rag_health = self.rag_system.health_check()
                logger.info("RAG系统健康状态:")
                logger.info(f"  整体状态: {rag_health['overall_status']}")
                
                for component, status in rag_health['checks'].items():
                    logger.info(f"  {component}: {status['status']}")
            
            # 知识检索器系统信息
            if self.knowledge_retriever:
                system_info = self.knowledge_retriever.get_system_info()
                logger.info("\n知识检索器系统信息:")
                for key, value in system_info.items():
                    if key != 'rag_system_info':  # 跳过复杂的嵌套信息
                        logger.info(f"  {key}: {value}")
            
            logger.info("✅ 系统健康检查完成")
            
        except Exception as e:
            logger.error(f"❌ 系统健康检查失败: {e}")
            self.fail(f"系统健康检查失败: {e}")
    
    def _analyze_retrieval_result(self, test_case: Dict[str, Any], fragments: List[KnowledgeFragment]) -> Dict[str, Any]:
        """分析检索结果"""
        result = {
            "query": test_case['query'],
            "category": test_case['category'],
            "success": len(fragments) > 0,
            "fragment_count": len(fragments),
            "avg_score": sum(f.score for f in fragments) / len(fragments) if fragments else 0,
            "keyword_matches": 0,
            "sources": []
        }
        
        # 检查关键词匹配
        all_content = " ".join(f.content for f in fragments).lower()
        for keyword in test_case['expected_keywords']:
            if keyword.lower() in all_content:
                result["keyword_matches"] += 1
        
        # 收集来源
        result["sources"] = list(set(f.source for f in fragments))
        
        return result
    
    def _check_keywords(self, fragments: List[KnowledgeFragment], expected_keywords: List[str]) -> List[str]:
        """检查片段中是否包含期望的关键词"""
        found_keywords = []
        all_content = " ".join(f.content for f in fragments).lower()
        
        for keyword in expected_keywords:
            if keyword.lower() in all_content:
                found_keywords.append(keyword)
        
        return found_keywords
    
    def _summarize_test_results(self, results: List[Dict[str, Any]]):
        """总结测试结果"""
        logger.info("\n" + "=" * 60)
        logger.info("测试结果总结")
        logger.info("=" * 60)
        
        total_queries = len(results)
        successful_queries = sum(1 for r in results if r.get('success', False))
        
        logger.info(f"总查询数: {total_queries}")
        logger.info(f"成功查询数: {successful_queries}")
        logger.info(f"成功率: {successful_queries/total_queries*100:.1f}%")
        
        # 按类别分析
        categories = {}
        for result in results:
            category = result['category']
            if category not in categories:
                categories[category] = {"total": 0, "success": 0}
            categories[category]["total"] += 1
            if result.get('success', False):
                categories[category]["success"] += 1
        
        logger.info("\n按类别的成功率:")
        for category, stats in categories.items():
            success_rate = stats["success"] / stats["total"] * 100
            logger.info(f"  {category}: {stats['success']}/{stats['total']} ({success_rate:.1f}%)")
        
        # 平均性能指标
        avg_fragments = sum(r.get('fragment_count', 0) for r in results if r.get('success', False))
        if successful_queries > 0:
            avg_fragments /= successful_queries
            logger.info(f"\n平均检索片段数: {avg_fragments:.1f}")
        
        # 关键词匹配统计  
        total_keyword_matches = sum(r.get('keyword_matches', 0) for r in results)
        # 从测试用例中获取期望关键词数量
        total_expected_keywords = 0
        test_queries = [
            {"expected_keywords": ["X1", "X2", "X3", "X4", "参数", "GR4J"]},
            {"expected_keywords": ["率定", "calibration", "优化", "参数调整"]},
            {"expected_keywords": ["NSE", "RMSE", "MAE", "评估", "指标"]},
            {"expected_keywords": ["预处理", "清洗", "格式", "缺失值"]},
            {"expected_keywords": ["CAMELS", "数据集", "流域", "水文"]}
        ]
        for i in range(min(len(results), len(test_queries))):
            total_expected_keywords += len(test_queries[i]['expected_keywords'])
        keyword_match_rate = total_keyword_matches / total_expected_keywords * 100 if total_expected_keywords > 0 else 0
        
        logger.info(f"关键词匹配率: {keyword_match_rate:.1f}%")


def run_integration_test():
    """运行集成测试"""
    # 设置详细的日志格式
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True
    )
    
    # 创建测试套件
    test_suite = unittest.TestSuite()
    
    # 添加测试方法（按顺序执行）
    test_methods = [
        'test_01_setup_rag_system',
        'test_02_process_documents', 
        'test_03_setup_knowledge_retriever',
        'test_04_test_different_queries',
        'test_05_integration_with_workflow',
        'test_06_system_health_check'
    ]
    
    for method in test_methods:
        test_suite.addTest(TestHydroRAGKnowledgeIntegration(method))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    print("🚀 开始HydroRAG系统与知识检索器集成测试")
    print("=" * 80)
    
    success = run_integration_test()
    
    print("\n" + "=" * 80)
    if success:
        print("🎉 所有测试通过！系统集成成功")
    else:
        print("❌ 部分测试失败，请检查日志")
    
    exit(0 if success else 1)
