# HydroRAG - 智能水文知识检索增强生成系统

HydroRAG是一个专门为水文建模领域设计的智能RAG（Retrieval-Augmented Generation）系统。该系统基于ChromaDB向量数据库，支持Qwen API和本地Ollama嵌入模型，为水文智能体提供高质量的知识检索服务。

## 🚀 核心特性

### 1. 混合嵌入模型支持
- **优先级1**: Qwen API嵌入模型 (`text-embedding-v1`) - 高质量云端向量化
- **优先级2**: 本地Ollama嵌入模型 - 离线备份方案
- **智能降级**: API不可用时自动切换到本地模型
- **错误处理**: 完善的异常处理和重试机制

### 2. 智能文档处理
- **多格式支持**: PDF、Word、Markdown、TXT、JSON等格式
- **增量处理**: 仅处理新增或修改的文档
- **智能分块**: 基于语义的文本分段策略
- **元数据管理**: 完整的文档来源和版本信息

### 3. 高性能向量检索
- **ChromaDB**: 持久化向量数据库
- **语义搜索**: 基于余弦相似度的精确匹配
- **智能重排序**: 多维度结果优化
- **阈值过滤**: 可配置的质量控制

### 4. 系统级功能
- **状态管理**: 向量库构建状态持久化
- **健康监控**: 组件可用性实时检测
- **备份恢复**: 完整的数据备份和恢复
- **性能统计**: 详细的处理和查询性能指标

## 📦 环境配置

### 1. 安装依赖
```bash
# 使用uv管理依赖
uv sync

# 或手动安装关键依赖
pip install chromadb openai ollama langchain-community langchain-text-splitters
pip install pypdf python-docx  # 文档处理支持
```

### 2. 配置API密钥 (definitions_private.py)
```python
# Qwen API配置
OPENAI_API_KEY = "your-qwen-api-key"
OPENAI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 知识库路径
KNOWLEDGE_BASE_DIR = "documents"
```

### 3. 本地Ollama配置（备用）
```bash
# 安装Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# 下载嵌入模型
ollama pull nomic-embed-text
ollama pull mxbai-embed-large
```

## 🏗️ 系统架构

### 核心组件
```text
hydrorag/
├── README.md                    # 系统文档
├── config.py                   # 配置管理
├── rag_system.py              # RAG系统主接口
├── document_processor.py      # 文档处理器
├── embeddings_manager.py      # 嵌入模型管理器
├── vector_store.py            # 向量数据库管理
├── query_processor.py         # 查询处理和重排序
└── test_hydrorag.py          # 系统测试
```

### 数据流架构
```text
原始文档(raw) → 文档处理 → 统一格式(processed) → 向量化 → ChromaDB
                                                            ↓
用户查询 → 查询向量化 → 相似度匹配 → 重排序 → 知识片段输出
```

### 嵌入模型选择流程
```text
用户查询 → 尝试Qwen API → 成功？ → 返回向量
                ↓         ↑
          失败/超时    是的
                ↓
         尝试本地Ollama → 成功？ → 返回向量
                ↓         ↑
          失败/不可用   是的
                ↓
           返回错误停止
```

## 📖 快速开始

### 1. 基础使用

```python
from hydrorag import RAGSystem, Config

# 使用默认配置创建RAG系统
rag_system = RAGSystem()

# 或者使用自定义配置
config = Config(
    documents_dir="./my_documents",
    embedding_model_name="sentence-transformers/all-MiniLM-L6-v2",
    chunk_size=512,
    top_k=10
)
rag_system = RAGSystem(config)
```

### 2. 完整设置流程

```python
# 从原始文档完整设置系统
setup_result = rag_system.setup_from_raw_documents()

if setup_result["status"] == "success":
    print("RAG系统设置成功!")
    print(f"处理了 {setup_result['steps']['document_processing']['processed']} 个文档")
    print(f"构建了 {setup_result['steps']['index_building']['total_chunks_added']} 个文本块的索引")
else:
    print(f"设置失败: {setup_result['error']}")
```

### 3. 查询知识库

```python
# 查询相关文档
result = rag_system.query(
    query_text="GR4J模型的参数有哪些？",
    top_k=5,
    score_threshold=0.5
)

if result["status"] == "success":
    print(f"找到 {result['total_found']} 个相关文档:")
    for i, doc in enumerate(result["results"]):
        print(f"\n{i+1}. 分数: {doc['score']:.3f}")
        print(f"内容: {doc['content'][:200]}...")
        if "metadata" in doc:
            print(f"来源: {doc['metadata']['source_file']}")
```

## 📁 目录结构

系统使用以下目录结构存储文档和数据：

```text
documents/
├── raw/              # 原始文档
│   ├── model_docs/   # 模型文档
│   ├── papers/       # 学术论文
│   └── manuals/      # 用户手册
├── processed/        # 处理后的文档
│   ├── *.json        # 分块后的文档数据
│   └── *.meta.json   # 文档元数据
└── vector_db/        # 向量数据库
    └── chroma/       # Chroma数据库文件
```

## ⚙️ 配置选项

### 基础配置

```python
config = Config(
    # 路径配置
    documents_dir="./documents",
    raw_documents_dir="./documents/raw",
    processed_documents_dir="./documents/processed",
    vector_db_dir="./documents/vector_db",
    
    # 嵌入模型配置
    embedding_model_name="sentence-transformers/all-MiniLM-L6-v2",
    embedding_device="cpu",  # 或 "cuda"
    
    # 文档处理配置
    chunk_size=500,
    chunk_overlap=50,
    
    # 检索配置
    top_k=5,
    score_threshold=0.5,
    
    # Chroma配置
    chroma_collection_name="hydro_knowledge",
    chroma_distance_function="cosine"  # cosine, l2, ip
)
```

### 支持的文件格式

- **文本文件**: `.txt`, `.md`, `.markdown`, `.rst`
- **代码文件**: `.py`, `.yaml`, `.yml`, `.json`
- **文档文件**: `.pdf`, `.docx`, `.doc`

## 🔧 高级功能

### 1. 分步骤设置

```python
# 步骤1: 处理原始文档
process_result = rag_system.process_documents(force_reprocess=True)

# 步骤2: 构建向量索引
index_result = rag_system.build_vector_index(rebuild=True)

# 步骤3: 测试查询
test_result = rag_system.query("测试查询", top_k=3)
```

### 2. 系统监控

```python
# 获取系统状态
status = rag_system.get_system_status()
print("系统初始化状态:", status["is_initialized"])

# 健康检查
health = rag_system.health_check()
print("系统健康状态:", health["overall_status"])

# 获取统计信息
if rag_system.vector_store:
    stats = rag_system.vector_store.get_statistics()
    print(f"向量数据库包含 {stats['total_documents']} 个文档")
```

### 3. 备份和恢复

```python
# 备份整个系统
backup_result = rag_system.backup_system("./backups")

# 恢复向量数据库
if rag_system.vector_store:
    restore_result = rag_system.vector_store.restore_collection(
        "./backups/vector_store_20241201_120000.json"
    )
```

### 4. 高级查询

```python
# 带元数据过滤的查询
result = rag_system.vector_store.query(
    query_text="模型参数",
    n_results=10,
    score_threshold=0.3,
    where={"source_file": {"$regex": ".*gr4j.*"}}  # 只查询GR4J相关文档
)

# 批量文档添加
new_chunks = [
    {
        "chunk_id": "new_001",
        "content": "新的知识内容",
        "source_file": "new_document.txt",
        "metadata": {"category": "model"}
    }
]
add_result = rag_system.vector_store.add_documents(new_chunks)
```

## 🔗 与工作流集成

HydroRAG设计用于与`workflow/knowledge_retriever.py`集成，提供知识检索服务：

```python
# 在knowledge_retriever.py中使用
from hydrorag import RAGSystem

class KnowledgeRetriever:
    def __init__(self):
        # 初始化HydroRAG系统
        self.hydrorag = RAGSystem()
        
    def retrieve_knowledge(self, query, k=5, score_threshold=0.3):
        # 使用HydroRAG进行检索
        result = self.hydrorag.query(
            query_text=query,
            top_k=k,
            score_threshold=score_threshold
        )
        
        # 转换为KnowledgeFragment格式
        fragments = []
        if result["status"] == "success":
            for item in result["results"]:
                fragment = KnowledgeFragment(
                    content=item["content"],
                    source=item["metadata"]["source_file"],
                    score=item["score"],
                    metadata=item["metadata"]
                )
                fragments.append(fragment)
        
        return fragments
```

## 🐛 常见问题

### 1. 嵌入模型初始化失败

```python
# 检查模型是否可用
if not rag_system.embeddings_manager.is_available():
    print("嵌入模型不可用，请检查:")
    print("1. 是否安装了sentence-transformers")
    print("2. 网络连接是否正常（首次下载模型需要网络）")
    print("3. 磁盘空间是否足够")
```

### 2. Chroma数据库问题

```python
# 重置数据库
if rag_system.vector_store:
    clear_result = rag_system.vector_store.clear_collection()
    print("数据库已清空，重新构建索引")
```

### 3. 文档处理失败

```python
# 检查文档处理状态
if rag_system.document_processor:
    stats = rag_system.document_processor.get_statistics()
    print(f"原始文档: {stats['raw_documents_count']}")
    print(f"已处理: {stats['processed_documents_count']}")
    
    # 强制重新处理
    process_result = rag_system.process_documents(force_reprocess=True)
```

## 📊 性能优化

### 1. 嵌入模型选择

- **轻量级**: `sentence-transformers/all-MiniLM-L6-v2`（默认）
- **中等性能**: `sentence-transformers/all-mpnet-base-v2`
- **高性能**: `sentence-transformers/all-roberta-large-v1`

### 2. 文档分块优化

```python
# 根据文档类型调整分块大小
config.chunk_size = 300    # 较短的技术文档
config.chunk_size = 800    # 较长的论文文档
config.chunk_overlap = config.chunk_size // 10  # 通常设为chunk_size的10%
```

### 3. 检索优化

```python
# 调整检索参数
config.top_k = 10              # 增加候选结果
config.score_threshold = 0.3   # 降低阈值获得更多结果
```

## 🤝 贡献

欢迎提交Issue和Pull Request来改进系统！

## 📄 许可证

本项目使用MIT许可证。
