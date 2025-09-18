#!/usr/bin/env python3
"""
HydroRAG演示脚本
展示完整的RAG系统使用流程
"""

import sys
import os
from pathlib import Path

# 添加项目根路径到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def main():
    """主演示函数"""
    print("🚀 HydroRAG系统演示")
    print("=" * 50)
    
    try:
        # 导入HydroRAG
        from hydrorag import RAGSystem, Config
        
        print("✅ HydroRAG模块导入成功")
        
        # 创建配置
        config = Config(
            documents_dir="./documents",
            raw_documents_dir="./documents/raw", 
            processed_documents_dir="./documents/processed",
            vector_db_dir="./documents/vector_db",
            chunk_size=400,
            chunk_overlap=40,
            top_k=5,
            score_threshold=0.3
        )
        
        print("✅ 配置创建成功")
        print(f"   文档目录: {config.documents_dir}")
        print(f"   嵌入模型: {config.embedding_model_name}")
        print(f"   分块大小: {config.chunk_size}")
        
        # 创建RAG系统
        print("\n🔧 正在初始化RAG系统...")
        rag_system = RAGSystem(config)
        
        # 检查初始化状态
        if rag_system.is_initialized:
            print("✅ RAG系统初始化成功")
        else:
            print("❌ RAG系统初始化失败")
            print("错误信息:")
            for error in rag_system.initialization_errors:
                print(f"   - {error}")
            print("\n💡 可能的解决方案:")
            print("   1. 安装依赖: pip install chromadb sentence-transformers langchain-community")
            print("   2. 确保网络连接正常（首次运行需要下载模型）")
            print("   3. 检查磁盘空间是否充足")
            return
        
        # 执行完整设置
        print("\n📄 开始处理文档和构建索引...")
        setup_result = rag_system.setup_from_raw_documents()
        
        if setup_result['status'] == 'success':
            print("✅ 系统设置成功!")
            
            # 显示处理结果
            doc_result = setup_result['steps']['document_processing']
            index_result = setup_result['steps']['index_building']
            
            print(f"   📄 文档处理: {doc_result['processed']} 成功, {doc_result['failed']} 失败")
            print(f"   🔍 索引构建: {index_result['total_chunks_added']} 个文本块")
            print(f"   📊 数据库总文档数: {index_result['final_document_count']}")
            
        else:
            print(f"❌ 系统设置失败: {setup_result['error']}")
            return
        
        # 测试查询功能
        print("\n🔍 测试查询功能...")
        test_queries = [
            "GR4J模型有哪些参数？",
            "模型率定使用什么优化算法？", 
            "NSE评估指标的含义是什么？",
            "CAMELS数据集包含哪些内容？",
            "水文建模的最佳实践"
        ]
        
        for i, query in enumerate(test_queries, 1):
            print(f"\n查询 {i}: {query}")
            
            result = rag_system.query(
                query_text=query,
                top_k=3,
                score_threshold=0.3
            )
            
            if result['status'] == 'success' and result['total_found'] > 0:
                print(f"   ✅ 找到 {result['total_found']} 个相关文档")
                
                # 显示最相关的结果
                for j, doc in enumerate(result['results'][:2], 1):
                    print(f"   {j}. 相关度: {doc['score']:.3f}")
                    print(f"      内容: {doc['content'][:150]}...")
                    if 'metadata' in doc and doc['metadata'].get('source_file'):
                        print(f"      来源: {doc['metadata']['source_file']}")
            else:
                print("   ❌ 未找到相关文档")
        
        # 显示系统统计信息
        print("\n📊 系统统计信息:")
        if rag_system.vector_store:
            stats = rag_system.vector_store.get_statistics()
            print(f"   向量数据库文档数: {stats.get('total_documents', 0)}")
            print(f"   唯一源文件数: {stats.get('unique_source_files', 0)}")
            print(f"   集合名称: {stats.get('collection_name', 'N/A')}")
        
        if rag_system.document_processor:
            doc_stats = rag_system.document_processor.get_statistics()
            print(f"   原始文档数: {doc_stats.get('raw_documents_count', 0)}")
            print(f"   已处理文档数: {doc_stats.get('processed_documents_count', 0)}")
            print(f"   总文本块数: {doc_stats.get('total_chunks', 0)}")
        
        # 健康检查
        print("\n🏥 系统健康检查:")
        health = rag_system.health_check()
        print(f"   总体状态: {health['overall_status']}")
        
        for component, check in health['checks'].items():
            status = check['status']
            emoji = "✅" if status == "passed" else "❌"
            print(f"   {emoji} {component}: {status}")
        
        # 演示与knowledge_retriever的集成
        print("\n🔗 演示与knowledge_retriever集成:")
        integration_demo(rag_system)
        
        print("\n🎉 演示完成!")
        print("\n📝 说明:")
        print("- 向量数据库文件保存在 documents/vector_db/ 目录")
        print("- 处理后的文档保存在 documents/processed/ 目录")
        print("- 可以通过添加更多文档到 documents/raw/ 目录来扩展知识库")
        print("- 重新运行时系统会自动检测新文档并更新索引")
        
    except ImportError as e:
        print(f"❌ 导入错误: {e}")
        print("\n💡 请安装必要的依赖:")
        print("   pip install chromadb sentence-transformers langchain-community langchain-text-splitters")
        
    except Exception as e:
        print(f"❌ 演示过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


def integration_demo(rag_system):
    """演示与knowledge_retriever的集成"""
    
    # 模拟KnowledgeFragment类
    class KnowledgeFragment:
        def __init__(self, content, source, score, metadata=None):
            self.content = content
            self.source = source
            self.score = score
            self.metadata = metadata or {}
        
        def to_dict(self):
            return {
                "content": self.content,
                "source": self.source,
                "score": self.score,
                "metadata": self.metadata
            }
    
    # 模拟集成的检索器
    class IntegratedKnowledgeRetriever:
        def __init__(self, rag_system):
            self.rag_system = rag_system
            
        def retrieve_knowledge(self, expanded_query, k=5, score_threshold=0.3):
            """检索知识片段，兼容原有接口"""
            
            if not self.rag_system.is_initialized:
                print("   ⚠️  RAG系统未初始化，返回空结果")
                return []
            
            # 使用HydroRAG进行检索
            result = self.rag_system.query(
                query_text=expanded_query,
                top_k=k,
                score_threshold=score_threshold
            )
            
            # 转换为KnowledgeFragment格式
            fragments = []
            if result["status"] == "success":
                for item in result["results"]:
                    fragment = KnowledgeFragment(
                        content=item["content"],
                        source=item.get("metadata", {}).get("source_file", "HydroRAG"),
                        score=item["score"],
                        metadata=item.get("metadata", {})
                    )
                    fragments.append(fragment)
            
            return fragments
    
    # 创建集成检索器
    retriever = IntegratedKnowledgeRetriever(rag_system)
    
    # 测试集成
    query = "GR4J模型参数的物理含义"
    print(f"   查询: {query}")
    
    fragments = retriever.retrieve_knowledge(query, k=3, score_threshold=0.3)
    
    if fragments:
        print(f"   ✅ 检索到 {len(fragments)} 个知识片段")
        for i, fragment in enumerate(fragments, 1):
            print(f"   {i}. 分数: {fragment.score:.3f}")
            print(f"      来源: {fragment.source}")
            print(f"      内容: {fragment.content[:100]}...")
    else:
        print("   ❌ 未检索到知识片段")


if __name__ == "__main__":
    main()
