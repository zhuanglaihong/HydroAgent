#!/usr/bin/env python3
"""
简化的HydroRAG测试脚本
用于验证基本功能
"""

import sys
import os
from pathlib import Path

# 添加项目根路径
repo_path = Path(os.path.abspath(__file__)).parent.parent
sys.path.append(str(repo_path))

def test_config():
    """测试配置功能"""
    print("测试配置功能...")
    try:
        from hydrorag.config import Config
        
        config = Config()
        print(f"✅ 默认配置创建成功")
        print(f"   chunk_size: {config.chunk_size}")
        print(f"   embedding_model: {config.embedding_model_name}")
        
        # 验证配置
        if config.validate():
            print("✅ 配置验证通过")
        else:
            print("❌ 配置验证失败")
            
    except Exception as e:
        print(f"❌ 配置测试失败: {e}")

def test_document_processor():
    """测试文档处理器"""
    print("\n测试文档处理器...")
    try:
        from hydrorag.config import Config
        from hydrorag.document_processor import DocumentProcessor
        
        config = Config(
            documents_dir="./documents",
            raw_documents_dir="./documents/raw",
            processed_documents_dir="./documents/processed"
        )
        
        processor = DocumentProcessor(config)
        print("✅ 文档处理器创建成功")
        
        # 扫描文档
        files = processor.scan_raw_documents()
        print(f"✅ 扫描到 {len(files)} 个文档")
        
        if files:
            # 尝试处理第一个文档
            result = processor.process_document(files[0])
            if result["status"] == "success":
                print(f"✅ 文档处理成功: {result['chunks_count']} 个文本块")
            else:
                print(f"❌ 文档处理失败: {result.get('reason', '未知错误')}")
        
    except Exception as e:
        print(f"❌ 文档处理器测试失败: {e}")

def test_basic_rag():
    """测试基本RAG功能"""
    print("\n测试基本RAG功能...")
    try:
        from hydrorag import RAGSystem, Config
        
        config = Config(
            documents_dir="./documents",
            raw_documents_dir="./documents/raw",
            processed_documents_dir="./documents/processed",
            vector_db_dir="./documents/vector_db"
        )
        
        print("正在初始化RAG系统...")
        rag_system = RAGSystem(config)
        
        if rag_system.is_initialized:
            print("✅ RAG系统初始化成功")
            
            # 获取系统状态
            status = rag_system.get_system_status()
            print(f"   嵌入模型可用: {status['components']['embeddings_manager']['available']}")
            print(f"   向量数据库可用: {status['components']['vector_store']['available']}")
            print(f"   文档处理器可用: {status['components']['document_processor']['available']}")
            
        else:
            print("❌ RAG系统初始化失败")
            for error in rag_system.initialization_errors:
                print(f"   错误: {error}")
                
    except Exception as e:
        print(f"❌ RAG系统测试失败: {e}")

def test_imports():
    """测试导入功能"""
    print("测试模块导入...")
    
    modules = [
        "hydrorag.config",
        "hydrorag.document_processor", 
        "hydrorag.embeddings_manager",
        "hydrorag.vector_store",
        "hydrorag.rag_system"
    ]
    
    for module in modules:
        try:
            __import__(module)
            print(f"✅ {module} 导入成功")
        except Exception as e:
            print(f"❌ {module} 导入失败: {e}")
    
    # 测试嵌入模型依赖
    print("\n测试嵌入模型依赖...")
    
    # 检查新版HuggingFace包
    try:
        import langchain_huggingface
        print("✅ langchain-huggingface (新版) 可用")
    except ImportError:
        print("⚠️  langchain-huggingface (新版) 不可用")
        
        # 检查旧版包
        try:
            import langchain_community.embeddings
            print("✅ langchain-community (旧版) 可用")
        except ImportError:
            print("⚠️  langchain-community (旧版) 不可用")
    
    # 检查sentence-transformers
    try:
        import sentence_transformers
        print("✅ sentence-transformers 可用")
    except ImportError:
        print("❌ sentence-transformers 不可用")
    
    # 检查chromadb
    try:
        import chromadb
        print("✅ chromadb 可用")
    except ImportError:
        print("❌ chromadb 不可用")
    
    # 检查Ollama连接和模型
    print("\n测试Ollama连接和模型...")
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = [model['name'] for model in data.get('models', [])]
            print(f"✅ Ollama服务可用，发现模型: {models}")
            
            # 检查bge-large:335m模型
            if "bge-large:335m" in models:
                print("✅ 找到bge-large:335m嵌入模型")
            elif any("bge" in model for model in models):
                bge_models = [model for model in models if "bge" in model]
                print(f"✅ 找到BGE嵌入模型: {bge_models}")
            else:
                print("⚠️  未找到BGE嵌入模型，但Ollama服务可用")
        else:
            print(f"❌ Ollama服务响应错误: HTTP {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到Ollama服务（http://localhost:11434）")
    except Exception as e:
        print(f"❌ 检查Ollama时出错: {e}")

def main():
    """主测试函数"""
    print("🚀 HydroRAG 简化测试")
    print("=" * 50)
    
    test_imports()
    test_config()
    test_document_processor()
    test_basic_rag()
    
    print("\n" + "=" * 50)
    print("🎉 测试完成!")

if __name__ == "__main__":
    main()
