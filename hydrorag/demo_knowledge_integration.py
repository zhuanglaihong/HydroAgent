"""
HydroRAG与知识检索器集成演示
快速演示如何使用HydroRAG系统构建知识库并进行检索
"""

import sys
import os
from pathlib import Path
import logging

# 添加项目根路径
repo_path = Path(os.path.abspath(__file__)).parent.parent
sys.path.append(str(repo_path))

from hydrorag.rag_system import quick_setup
from workflow.knowledge_retriever import KnowledgeRetriever

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def main():
    """主演示函数"""
    print("🚀 HydroRAG与知识检索器集成演示")
    print("=" * 60)
    
    documents_dir = os.path.join(repo_path, "documents")
    
    try:
        # 步骤1：初始化RAG系统
        print("\n📚 步骤1：初始化RAG系统...")
        rag_system = quick_setup(documents_dir)
        
        if not rag_system or not rag_system.is_initialized:
            print("❌ RAG系统初始化失败")
            return False
        
        print("✅ RAG系统初始化成功")
        
        # 步骤2：处理文档
        print("\n📄 步骤2：处理原始文档...")
        result = rag_system.setup_from_raw_documents()
        
        if result["status"] != "success":
            print(f"❌ 系统设置失败: {result}")
            return False
        
        # 检查处理结果
        if result.get("skipped", False):
            # 使用已存在的向量库是正常情况
            print("✅ 使用已存在的处理结果:")
            print(f"   已处理文档数: {result.get('processed', 0)}")
            print(f"   向量库文档数: {result.get('in_vector_store', 0)}")
        else:
            # 新处理文档的情况
            print("✅ 完成新文档处理:")
            process_result = result["steps"]["document_processing"]
            index_result = result["steps"]["index_building"]
            print(f"   处理的文档数: {process_result.get('processed', 0)}")
            print(f"   失败的文档数: {process_result.get('failed', 0)}")
            print(f"   添加到向量库的块数: {index_result.get('total_chunks_added', 0)}")
        
        # 步骤3：初始化知识检索器
        print("\n🔍 步骤3：初始化知识检索器...")
        knowledge_retriever = KnowledgeRetriever(rag_system=rag_system)
        
        print("✅ 知识检索器初始化成功")
        
        # 步骤4：测试知识检索
        print("\n🧪 步骤4：测试知识检索...")
        
        test_queries = [
            "GR4J模型有哪些参数？",
            "如何进行模型率定？", 
            "模型评估用什么指标？"
        ]
        
        for i, query in enumerate(test_queries, 1):
            print(f"\n--- 查询 {i}: {query} ---")
            
            # 检索知识
            fragments = knowledge_retriever.retrieve_knowledge(
                expanded_query=query,
                k=3,
                score_threshold=0.2
            )
            
            if fragments:
                print(f"✅ 找到 {len(fragments)} 个相关片段")
                
                # 显示最相关的片段
                for j, fragment in enumerate(fragments[:2], 1):
                    print(f"  片段 {j} (得分: {fragment.score:.3f}):")
                    print(f"    内容: {fragment.content[:200]}...")
                    print(f"    来源: {fragment.source}")
            else:
                print("⚠️  未找到相关片段")
        
        # 步骤5：生成知识总结
        print("\n📋 步骤5：生成知识总结...")
        
        workflow_query = "我想了解GR4J模型的完整使用流程"
        fragments = knowledge_retriever.retrieve_knowledge(
            expanded_query=workflow_query,
            k=5,
            score_threshold=0.2
        )
        
        if fragments:
            summary = knowledge_retriever.summarize_fragments(fragments)
            print("📚 知识总结:")
            print(summary)
        
        # 步骤6：系统状态检查
        print("\n🏥 步骤6：系统状态检查...")
        
        # RAG系统健康检查
        rag_health = rag_system.health_check()
        print("RAG系统健康状态:")
        print(f"  整体状态: {rag_health['overall_status']}")
        for component, status in rag_health['checks'].items():
            print(f"  {component}: {status['status']}")
            if 'document_count' in status:
                print(f"    文档数: {status['document_count']}")
        
        # 知识检索器状态
        retriever_info = knowledge_retriever.get_system_info()
        print("\n知识检索器状态:")
        print(f"  RAG系统可用: {retriever_info['rag_system_available']}")
        print(f"  回退模式启用: {retriever_info['fallback_enabled']}")
        print(f"  默认知识库片段数: {retriever_info['default_knowledge_count']}")
        
        if rag_health['overall_status'] == "healthy":
            print("\n🎉 演示完成！系统运行正常")
            return True
        else:
            print("\n⚠️  演示完成，但系统存在一些问题:")
            for issue in rag_health.get('issues', []):
                print(f"  - {issue}")
            return True  # 仍然返回True因为这可能是预期的状态
        
    except Exception as e:
        print(f"❌ 演示过程中发生错误: {e}")
        logger.exception("详细错误信息:")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
