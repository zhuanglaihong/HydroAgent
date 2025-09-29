# HydroRAG - 智能水文知识检索增强生成系统

HydroRAG是一个专门为水文建模领域设计的智能RAG（Retrieval-Augmented Generation）系统。该系统基于FAISS向量数据库，支持API和本地Ollama双重嵌入模型架构，通过多级检索和重排序优化，为水文智能体提供高精度的知识检索服务。

## 🚀 核心特性

### 1. 双重嵌入模型架构
- **优先级1**: API嵌入模型 (如Qwen API `text-embedding-v1`) - 高质量云端向量化
- **优先级2**: 本地Ollama嵌入模型 - 离线备份方案
- **智能超时机制**: API模型30秒超时自动切换到Ollama，Ollama 60秒超时提示不可用
- **线程池控制**: 精确的超时控制和资源管理
- **故障追踪**: 自动记录模型状态和切换历史

### 2. FAISS高性能向量存储
- **多种索引类型**: Flat（精确搜索）、IVF（聚类索引）、HNSW（图索引）
- **GPU加速支持**: 可选的GPU加速计算（需要faiss-gpu）
- **向量归一化**: 支持余弦相似度的优化计算
- **内存优化**: 高效的向量存储和检索
- **批量操作**: 支持大规模文档的批量索引构建

### 3. 智能文档处理系统
- **文档类型检测**: 自动识别代码、Markdown、纯文本等文档类型
- **语义边界保持**: 智能分块保持内容完整性和上下文连贯性
- **并行处理**: 多线程文档处理提升效率
- **质量验证**: 内容质量检查和过滤
- **增量更新**: 仅处理新增或修改的文档

### 4. 多级检索和重排序优化
- **多级检索策略**: 粗检索+精排序的两阶段检索
- **查询融合**: RRF（Reciprocal Rank Fusion）算法融合多查询结果
- **重排序算法**: 基于文本相似度、多样性和长度的综合评分
- **查询扩展**: 自动生成相关查询提升召回率
- **去重优化**: 智能的结果去重和聚合

### 5. 知识库更新和维护
- **增量更新**: 智能检测文档变更，仅更新必要部分
- **版本管理**: 完整的知识库版本控制和回滚
- **自动备份**: 可配置的自动备份和恢复机制
- **更新历史**: 详细的更新日志和统计信息
- **维护工具**: 知识库清理、压缩和优化工具

### 6. 系统级功能
- **动态后端切换**: 支持FAISS和Chroma的运行时切换
- **健康监控**: 全方位的组件状态监控
- **性能统计**: 详细的查询和处理性能指标
- **配置管理**: 灵活的参数配置和运行时调整

## 📦 环境配置

### 1. 安装依赖
```bash
# 使用uv管理依赖
uv sync

# 或手动安装关键依赖
pip install faiss-cpu  # 或 faiss-gpu（GPU版本）
pip install openai ollama langchain-community langchain-text-splitters
pip install pypdf python-docx  # 文档处理支持
pip install sentence-transformers  # 本地嵌入模型支持
```

### 2. 配置API密钥 (definitions_private.py)
```python
# API嵌入模型配置（优先级1）
OPENAI_API_KEY = "your-api-key"
OPENAI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 知识库路径
KNOWLEDGE_BASE_DIR = "documents"
PROJECT_DIR = "/path/to/your/project"
```

### 3. 本地Ollama配置（备用模型）
```bash
# 安装Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# 下载嵌入模型
ollama pull nomic-embed-text
ollama pull mxbai-embed-large

# 启动Ollama服务
ollama serve
```

### 4. 配置参数 (config.py)
```python
# FAISS配置
FAISS_INDEX_TYPE = "Flat"               # 索引类型: Flat, IVF, HNSW
FAISS_IVF_NLIST = 100                   # IVF聚类数量
FAISS_HNSW_M = 16                       # HNSW连接数
FAISS_ENABLE_GPU = False                # GPU加速

# 嵌入模型配置
EMBEDDING_API_TIMEOUT = 30              # API模型超时时间（秒）
EMBEDDING_OLLAMA_TIMEOUT = 60           # Ollama模型超时时间（秒）
EMBEDDING_API_MODEL = "text-embedding-v1"
EMBEDDING_OLLAMA_MODEL = "nomic-embed-text"

# 重排序配置
RERANK_ENABLED = True                   # 启用重排序
RERANK_TOP_K_CANDIDATES = 20            # 重排序候选数量
RERANK_FINAL_K = 5                      # 最终返回数量
```

## 🏗️ 系统架构

### 核心组件
```text
hydrorag/
├── README.md                    # 系统文档
├── config.py                   # 配置管理
├── rag_system.py              # RAG系统主接口
├── document_processor.py      # 智能文档处理器
├── embeddings_manager.py      # 双重嵌入模型管理器
├── faiss_vector_store.py      # FAISS向量存储管理
├── knowledge_updater.py       # 知识库更新模块
└── query_processor.py         # 查询处理和重排序（如需要）
```

### 数据流架构
```text
原始文档(raw) → 智能分块处理 → 统一格式(processed) → 双重向量化 → FAISS索引
                                                                    ↓
用户查询 → 查询扩展 → 多级检索 → 重排序优化 → 结果融合 → 知识片段输出
```

### 嵌入模型选择流程
```text
用户查询 → 尝试API模型 → 30s超时？ → 成功 → 返回向量
                ↓           ↑
             超时/失败      否
                ↓
         尝试Ollama模型 → 60s超时？ → 成功 → 返回向量
                ↓           ↑
             超时/失败      否
                ↓
           记录错误，提示不可用
```

### FAISS索引类型选择
```text
数据规模 < 10万   → Flat索引（精确搜索）
数据规模 10万-100万 → IVF索引（聚类搜索）
数据规模 > 100万   → HNSW索引（图搜索）
```

## 📖 快速开始

### 1. 基础使用
```python
from hydrorag import RAGSystem, Config

# 使用默认配置创建RAG系统
rag_system = RAGSystem()

# 或者使用自定义配置
config = Config(
    raw_documents_dir="./documents/raw",
    processed_documents_dir="./documents/processed",
    vector_db_dir="./documents/vector_db",
    faiss_index_type="Flat",
    enable_rerank=True
)
rag_system = RAGSystem(config)
```

### 2. 完整设置流程
```python
# 从原始文档完整设置系统
setup_result = rag_system.setup_from_raw_documents()

if setup_result["status"] == "success":
    print("RAG系统设置成功!")
    print(f"处理了 {setup_result['document_processing']['processed_count']} 个文档")
    print(f"构建了 {setup_result['index_building']['total_vectors']} 个向量的索引")
    print(f"使用的嵌入模型: {setup_result['embedding_model_info']['active_model']}")
else:
    print(f"设置失败: {setup_result['error']}")
```

### 3. 高级查询示例
```python
# 多级检索查询
result = rag_system.query(
    query_text="GR4J模型的参数含义和率定方法",
    top_k=5,
    score_threshold=0.4,
    enable_rerank=True,          # 启用重排序
    enable_expansion=True,       # 启用查询扩展
    include_metadata=True        # 包含元数据
)

if result["status"] == "success":
    print(f"找到 {result['total_found']} 个相关文档:")
    print(f"后端: {result['backend']}, 重排序: {result['rerank_enabled']}")

    for i, doc in enumerate(result["results"]):
        print(f"\n{i+1}. 分数: {doc['score']:.3f}")
        print(f"重排序分数: {doc.get('rerank_score', 'N/A')}")
        print(f"内容: {doc['content'][:200]}...")
        if "metadata" in doc:
            print(f"来源: {doc['metadata']['source_file']}")
            print(f"文档类型: {doc['metadata'].get('doc_type', 'unknown')}")
```

### 4. 知识库更新
```python
from hydrorag import KnowledgeUpdater

# 创建知识库更新器
updater = KnowledgeUpdater(rag_system.config)

# 检查更新
check_result = updater.check_for_updates()
if check_result["has_changes"]:
    print(f"发现 {len(check_result['changes']['new'])} 个新文档")
    print(f"发现 {len(check_result['changes']['modified'])} 个修改文档")

    # 执行增量更新
    update_result = updater.update_knowledge_base()
    if update_result["status"] == "success":
        print("知识库更新成功!")
        print(f"更新耗时: {update_result['update_time']:.2f}秒")

# 强制完整更新
full_update_result = updater.update_knowledge_base(force_full_update=True)
```

## 📁 目录结构

系统使用以下目录结构存储文档和数据：

```text
documents/
├── raw/                    # 原始文档
│   ├── model_docs/        # 模型文档
│   ├── papers/            # 学术论文
│   ├── manuals/           # 用户手册
│   └── code_examples/     # 代码示例
├── processed/             # 处理后的文档
│   ├── *.json            # 分块后的文档数据
│   ├── *.meta.json       # 文档元数据
│   └── processing.log    # 处理日志
├── vector_db/            # 向量数据库
│   ├── faiss/           # FAISS索引文件
│   │   ├── *.index      # 向量索引
│   │   ├── *.metadata   # 元数据
│   │   └── config.json  # 索引配置
│   └── backups/         # 备份文件
└── updates/             # 更新记录
    ├── update_*.log     # 更新日志
    └── versions/        # 版本历史
```

## ⚙️ 高级配置

### FAISS索引配置
```python
config = Config(
    # FAISS索引类型配置
    faiss_index_type="IVF",         # Flat, IVF, HNSW
    faiss_ivf_nlist=100,            # IVF聚类数量
    faiss_hnsw_m=16,                # HNSW连接数
    faiss_hnsw_ef_search=64,        # HNSW搜索候选数
    faiss_enable_gpu=True,          # 启用GPU加速

    # 向量标准化
    faiss_normalize_vectors=True,    # 向量归一化（用于余弦相似度）

    # 批量操作
    faiss_batch_size=1000,          # 批量添加大小
)
```

### 嵌入模型配置
```python
config = Config(
    # API模型配置
    embedding_api_model="text-embedding-v1",
    embedding_api_timeout=30,
    embedding_api_max_retries=2,

    # Ollama模型配置
    embedding_ollama_model="nomic-embed-text",
    embedding_ollama_timeout=60,
    embedding_ollama_base_url="http://localhost:11434",

    # 模型选择策略
    embedding_prefer_api=True,       # 优先使用API模型
    embedding_auto_fallback=True,    # 自动降级
)
```

### 重排序配置
```python
config = Config(
    # 重排序开关
    rerank_enabled=True,

    # 候选文档配置
    rerank_top_k_candidates=20,      # 初筛候选数量
    rerank_final_k=5,                # 最终返回数量

    # 评分权重
    rerank_vector_score_weight=0.7,   # 向量相似度权重
    rerank_text_score_weight=0.3,     # 文本匹配权重

    # 多样性控制
    rerank_diversity_threshold=0.8,   # 相似度去重阈值
    rerank_max_same_source=2,         # 同源文档最大数量
)
```

### 文档处理配置
```python
config = Config(
    # 智能分块配置
    chunk_size=500,                  # 基础分块大小
    chunk_overlap=50,                # 重叠大小
    chunk_min_size=100,              # 最小分块大小
    chunk_max_size=1000,             # 最大分块大小

    # 文档类型特定配置
    code_chunk_size=300,             # 代码文档分块大小
    markdown_chunk_size=600,         # Markdown文档分块大小

    # 质量控制
    min_content_quality=0.3,         # 最低内容质量分数
    filter_empty_chunks=True,        # 过滤空分块

    # 并行处理
    processing_workers=4,            # 处理线程数
)
```

## 🔧 高级功能和API

### 1. 系统监控和诊断
```python
# 获取系统状态
status = rag_system.get_system_status()
print(f"系统初始化: {status['is_initialized']}")
print(f"向量库状态: {status['vector_store_status']}")
print(f"嵌入模型状态: {status['embedding_model_status']}")

# 健康检查
health = rag_system.health_check()
print(f"整体健康状态: {health['overall_status']}")
print(f"组件状态: {health['components']}")

# 获取性能统计
stats = rag_system.get_performance_stats()
print(f"平均查询时间: {stats['avg_query_time']:.3f}秒")
print(f"总查询数: {stats['total_queries']}")
```

### 2. 批量操作
```python
# 批量添加文档
new_docs = [
    {
        "content": "新的知识内容1",
        "metadata": {"source": "doc1.txt", "category": "model"}
    },
    {
        "content": "新的知识内容2",
        "metadata": {"source": "doc2.txt", "category": "method"}
    }
]

add_result = rag_system.vector_store.add_documents(new_docs)
print(f"添加了 {add_result['added_count']} 个文档")

# 批量查询
queries = ["GR4J模型参数", "新安江模型", "水文模型率定"]
batch_results = rag_system.batch_query(queries, top_k=3)

for query, result in zip(queries, batch_results):
    print(f"\n查询: {query}")
    print(f"结果数: {result['total_found']}")
```

### 3. 知识库维护
```python
from hydrorag import KnowledgeUpdater

updater = KnowledgeUpdater(rag_system.config)

# 创建备份
backup_result = updater.create_backup()
print(f"备份创建于: {backup_result['backup_path']}")

# 清理旧版本
cleanup_result = updater.cleanup_old_versions(keep_versions=5)
print(f"清理了 {cleanup_result['cleaned_count']} 个旧版本")

# 压缩知识库
compress_result = updater.compress_knowledge_base()
print(f"压缩后大小: {compress_result['compressed_size']} MB")

# 获取更新历史
history = updater.get_update_history(limit=10)
for record in history:
    print(f"{record['timestamp']}: {record['operation']} - {record['details']}")
```

### 4. 高级查询功能
```python
# 带元数据过滤的查询
result = rag_system.query(
    query_text="模型参数",
    top_k=10,
    score_threshold=0.3,
    metadata_filter={
        "source_file": {"$regex": ".*gr4j.*"},  # 只查询GR4J相关文档
        "doc_type": "code"                      # 只查询代码文档
    }
)

# 多模态查询（如果支持）
result = rag_system.query(
    query_text="流域特征提取",
    query_type="hybrid",                    # 混合查询
    semantic_weight=0.7,                    # 语义权重
    keyword_weight=0.3,                     # 关键词权重
    enable_fuzzy_match=True                 # 启用模糊匹配
)

# 查询解释
result = rag_system.query(
    query_text="GR4J模型",
    explain=True                           # 返回查询解释
)
print("查询解释:", result["explanation"])
```

## 🔗 与工作流集成

HydroRAG设计用于与`workflow/knowledge_retriever.py`集成，提供知识检索服务：

```python
# 在knowledge_retriever.py中使用
from hydrorag import RAGSystem, KnowledgeFragment

class KnowledgeRetriever:
    def __init__(self):
        # 初始化HydroRAG系统
        self.hydrorag = RAGSystem()

        # 确保系统初始化完成
        if not self.hydrorag.get_system_status()["is_initialized"]:
            setup_result = self.hydrorag.setup_from_raw_documents()
            if setup_result["status"] != "success":
                raise RuntimeError(f"RAG系统初始化失败: {setup_result['error']}")

    def retrieve_knowledge(self, query, k=5, score_threshold=0.3, category=None):
        """检索相关知识片段"""
        # 构建元数据过滤器
        metadata_filter = {}
        if category:
            metadata_filter["category"] = category

        # 使用HydroRAG进行检索
        result = self.hydrorag.query(
            query_text=query,
            top_k=k,
            score_threshold=score_threshold,
            enable_rerank=True,
            enable_expansion=True,
            metadata_filter=metadata_filter if metadata_filter else None
        )

        # 转换为KnowledgeFragment格式
        fragments = []
        if result["status"] == "success":
            for item in result["results"]:
                fragment = KnowledgeFragment(
                    content=item["content"],
                    source=item["metadata"]["source_file"],
                    score=item["score"],
                    rerank_score=item.get("rerank_score"),
                    doc_type=item["metadata"].get("doc_type"),
                    metadata=item["metadata"]
                )
                fragments.append(fragment)

        return {
            "fragments": fragments,
            "total_found": result.get("total_found", 0),
            "backend": result.get("backend", "unknown"),
            "query_time": result.get("query_time", 0)
        }

    def update_knowledge_base(self):
        """更新知识库"""
        from hydrorag import KnowledgeUpdater
        updater = KnowledgeUpdater(self.hydrorag.config)
        return updater.update_knowledge_base()
```

## 🐛 常见问题和故障排除

### 1. 嵌入模型问题

```python
# 检查嵌入模型状态
embeddings_status = rag_system.embeddings_manager.check_model_availability()
print("API模型可用:", embeddings_status["api_available"])
print("Ollama模型可用:", embeddings_status["ollama_available"])

# 强制切换到特定模型
rag_system.embeddings_manager.force_model_type("ollama")

# 测试嵌入功能
test_result = rag_system.embeddings_manager.test_embedding("测试文本")
if test_result["status"] == "success":
    print(f"嵌入维度: {len(test_result['embedding'])}")
else:
    print(f"嵌入测试失败: {test_result['error']}")
```

### 2. FAISS索引问题

```python
# 检查FAISS索引状态
if rag_system.vector_store:
    index_info = rag_system.vector_store.get_index_info()
    print(f"索引类型: {index_info['index_type']}")
    print(f"向量数量: {index_info['total_vectors']}")
    print(f"向量维度: {index_info['vector_dimension']}")

    # 重建索引
    rebuild_result = rag_system.vector_store.rebuild_index()
    if rebuild_result["status"] == "success":
        print("索引重建成功")
    else:
        print(f"索引重建失败: {rebuild_result['error']}")
```

### 3. 文档处理问题

```python
# 检查文档处理统计
if rag_system.document_processor:
    stats = rag_system.document_processor.get_processing_stats()
    print(f"总文档数: {stats['total_documents']}")
    print(f"成功处理: {stats['successful_count']}")
    print(f"处理失败: {stats['failed_count']}")

    # 查看失败的文档
    failed_docs = rag_system.document_processor.get_failed_documents()
    for doc_info in failed_docs:
        print(f"失败文档: {doc_info['file_path']}")
        print(f"错误信息: {doc_info['error']}")

    # 重新处理失败的文档
    retry_result = rag_system.document_processor.retry_failed_documents()
    print(f"重试结果: {retry_result}")
```

### 4. 性能优化建议

```python
# 1. 根据数据规模选择合适的FAISS索引
document_count = rag_system.vector_store.get_document_count()
if document_count < 100000:
    recommended_index = "Flat"
elif document_count < 1000000:
    recommended_index = "IVF"
else:
    recommended_index = "HNSW"
print(f"推荐索引类型: {recommended_index}")

# 2. 调整查询参数
if document_count > 500000:
    # 大数据集：减少候选数量，提高精度阈值
    optimized_params = {
        "top_k": 3,
        "score_threshold": 0.6,
        "rerank_top_k_candidates": 10
    }
else:
    # 小数据集：增加候选数量，降低精度阈值
    optimized_params = {
        "top_k": 8,
        "score_threshold": 0.3,
        "rerank_top_k_candidates": 20
    }

print("推荐查询参数:", optimized_params)
```

## 📊 性能基准测试

### 查询性能测试
```python
import time
import statistics

def benchmark_query_performance(rag_system, test_queries, iterations=10):
    """查询性能基准测试"""
    results = {
        "query_times": [],
        "result_counts": [],
        "scores": []
    }

    for query in test_queries:
        query_times = []
        for _ in range(iterations):
            start_time = time.time()
            result = rag_system.query(
                query_text=query,
                top_k=5,
                enable_rerank=True
            )
            end_time = time.time()

            query_times.append(end_time - start_time)
            if result["status"] == "success":
                results["result_counts"].append(len(result["results"]))
                if result["results"]:
                    results["scores"].append(result["results"][0]["score"])

        results["query_times"].extend(query_times)

    # 统计结果
    print(f"平均查询时间: {statistics.mean(results['query_times']):.3f}秒")
    print(f"查询时间标准差: {statistics.stdev(results['query_times']):.3f}秒")
    print(f"平均结果数量: {statistics.mean(results['result_counts']):.1f}")
    print(f"平均最高分数: {statistics.mean(results['scores']):.3f}")

    return results

# 运行基准测试
test_queries = [
    "GR4J模型参数含义",
    "新安江模型特点",
    "水文模型率定方法",
    "降雨径流模拟",
    "流域特征提取"
]

benchmark_results = benchmark_query_performance(rag_system, test_queries)
```

## 🤝 贡献指南

### 开发环境设置
```bash
# 克隆仓库
git clone [repository-url]
cd HydroAgent

# 安装开发依赖
uv sync --dev

# 安装预提交钩子
pre-commit install

# 运行测试
python -m pytest test/test_hydrorag_faiss_integration.py -v
```

### 代码规范
- 遵循PEP 8代码风格
- 使用类型提示
- 编写完整的文档字符串
- 确保测试覆盖率 > 80%

### 提交规范
- 功能: `feat: 添加新的重排序算法`
- 修复: `fix: 修复FAISS索引构建问题`
- 文档: `docs: 更新API文档`
- 测试: `test: 添加嵌入模型测试`

## 📄 许可证

本项目使用MIT许可证。详见LICENSE文件。

## 🔄 版本历史

### v2.0.0 (当前版本)
- ✨ 完全重构为FAISS向量存储
- ✨ 双重嵌入模型架构（API + Ollama）
- ✨ 多级检索和重排序优化
- ✨ 智能文档处理系统
- ✨ 知识库更新和维护模块
- ✨ 综合性能优化

### v1.0.0 (历史版本)
- 基于ChromaDB的RAG系统
- 基础文档处理和检索功能
- 单一嵌入模型支持

---

**更多信息和支持**，请查看项目文档或提交Issue。