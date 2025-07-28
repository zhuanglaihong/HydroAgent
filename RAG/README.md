# RAG系统 - 基于LangChain的外部知识库接入模块

## 概述

RAG（Retrieval-Augmented Generation）系统是一个基于LangChain框架构建的完整知识库问答解决方案。该系统支持多种文档格式的加载、向量化存储、智能检索和答案生成，为构建智能问答系统提供了完整的工具链。

## 系统架构

```
RAG系统
├── 文档加载器 (DocumentLoader)
├── 向量存储 (VectorStore)
├── 检索器 (Retriever)
└── 生成器 (Generator)
```

### 核心组件

1. **文档加载器 (DocumentLoader)**
   - 支持多种文档格式：TXT、CSV、PDF、DOC、DOCX、XLS、XLSX、JSON
   - 智能文档分割和预处理
   - 元数据管理和文档过滤

2. **向量存储 (VectorStore)**
   - 基于FAISS的高效向量索引
   - 支持相似性搜索和阈值过滤
   - 索引持久化和加载

3. **检索器 (Retriever)**
   - 向量相似性检索
   - BM25和TF-IDF检索
   - 集成检索器（多检索器组合）
   - 上下文压缩检索

4. **生成器 (Generator)**
   - 问答链生成器
   - 总结生成器
   - 对话生成器
   - 检索问答生成器

## 安装依赖

```bash
pip install langchain==0.3.26
pip install langchain_community==0.3.27
pip install langchain_core==0.3.70
pip install faiss-cpu==1.7.4
pip install streamlit==1.47.0
```

## 快速开始

### 基本使用

```python
from RAG import RAGSystem
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.llms import Ollama

# 初始化模型
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
llm = Ollama(model="llama2")

# 创建RAG系统
rag_system = RAGSystem(
    embeddings=embeddings,
    llm=llm,
    index_path="./faiss_index"
)

# 加载文档
doc_count = rag_system.load_documents("./documents")

# 创建索引
rag_system.create_index()

# 执行查询
result = rag_system.query("什么是机器学习？")
print(result["answer"])
```

### 高级使用

```python
# 使用不同的检索器和生成器
result = rag_system.query(
    query="什么是深度学习？",
    retriever_name="ensemble",  # 集成检索器
    generator_name="qa",        # 问答生成器
    k=4,                       # 检索文档数量
    score_threshold=0.5        # 相似度阈值
)

# 批量查询
queries = ["什么是机器学习？", "深度学习有什么特点？"]
results = rag_system.batch_query(queries)
```

## 功能特性

### 1. 多格式文档支持

```python
# 支持多种文档格式
doc_count = rag_system.load_documents(
    source="./documents",
    file_extensions=[".txt", ".pdf", ".docx", ".csv"],
    add_metadata={"source": "company_docs", "category": "technical"},
    filter_min_length=50,
    filter_max_length=10000
)
```

### 2. 多种检索策略

```python
# 向量检索
result = rag_system.query("查询内容", retriever_name="vector")

# BM25检索
result = rag_system.query("查询内容", retriever_name="bm25")

# 集成检索
result = rag_system.query("查询内容", retriever_name="ensemble")
```

### 3. 多种生成模式

```python
# 问答模式
result = rag_system.query("问题", generator_name="qa")

# 总结模式
result = rag_system.query("总结主题", generator_name="summarize")

# 对话模式
result = rag_system.query("对话内容", generator_name="conversational")
```

### 4. 系统管理

```python
# 获取系统信息
info = rag_system.get_system_info()
print(f"文档数量: {info['documents_loaded']}")
print(f"可用检索器: {info['available_retrievers']}")
print(f"可用生成器: {info['available_generators']}")

# 保存和加载系统状态
rag_system.save_system("./saved_system")
rag_system.load_system("./saved_system")

# 清除系统状态
rag_system.clear_system()
```

## 自定义配置

### 自定义提示模板

```python
from RAG.generator import QAChainGenerator
from langchain.prompts import PromptTemplate

# 自定义提示模板
custom_prompt = PromptTemplate(
    template="""
    基于以下上下文信息回答问题：
    
    上下文：{context}
    
    问题：{question}
    
    请提供详细、准确的回答：
    """,
    input_variables=["context", "question"]
)

# 创建自定义生成器
custom_generator = QAChainGenerator(
    llm=llm,
    chain_type="stuff",
    prompt_template=custom_prompt.template
)

# 添加到RAG系统
rag_system.generator.add_generator("custom", custom_generator)
```

### 自定义检索器

```python
from RAG.retriever import Retriever

# 创建自定义检索器
retriever = Retriever(vector_store=vector_store, documents=documents)

# 添加集成检索器
retriever.add_ensemble_retriever(
    name="custom_ensemble",
    retrievers=["vector", "bm25"],
    weights=[0.7, 0.3]
)
```

## 使用示例

运行使用示例来了解RAG系统的功能：

```bash
# 运行RAG系统使用示例
python RAG/example.py
```

## 测试

运行测试以确保系统正常工作：

```bash
# 运行单元测试
python test/test_rag_system.py
```

## 性能优化

### 1. 文档分块优化

```python
# 调整分块大小和重叠
rag_system = RAGSystem(
    embeddings=embeddings,
    llm=llm,
    chunk_size=1000,      # 分块大小
    chunk_overlap=200     # 重叠大小
)
```

### 2. 检索参数调优

```python
# 调整检索参数
result = rag_system.query(
    query="查询内容",
    k=5,                    # 检索文档数量
    score_threshold=0.3     # 相似度阈值
)
```

### 3. 索引优化

```python
# 使用GPU加速（如果可用）
# pip install faiss-gpu
```

## 常见问题

### Q: 如何处理大文档？
A: 系统会自动将大文档分割成小块，可以通过调整`chunk_size`和`chunk_overlap`参数来优化分割效果。

### Q: 如何提高检索精度？
A: 可以尝试以下方法：
- 使用集成检索器
- 调整相似度阈值
- 优化文档分块策略
- 使用更高质量的嵌入模型

### Q: 如何添加新的文档格式支持？
A: 在`DocumentLoader`类中添加新的加载器，支持更多文档格式。

### Q: 如何自定义检索算法？
A: 继承`BaseRetriever`类并实现自定义检索逻辑。

## 扩展功能

### 1. 添加新的文档加载器

```python
from RAG.document_loader import DocumentLoader

class CustomDocumentLoader(DocumentLoader):
    def load_custom_format(self, file_path):
        # 实现自定义格式加载逻辑
        pass
```

### 2. 添加新的检索器

```python
from RAG.retriever import BaseRetriever

class CustomRetriever(BaseRetriever):
    def retrieve(self, query: str, k: int = 4):
        # 实现自定义检索逻辑
        pass
```

### 3. 添加新的生成器

```python
from RAG.generator import BaseGenerator

class CustomGenerator(BaseGenerator):
    def generate(self, query: str, context: List[Document], **kwargs):
        # 实现自定义生成逻辑
        pass
```

## 贡献指南

欢迎提交Issue和Pull Request来改进RAG系统。在提交代码前，请确保：

1. 运行所有测试并确保通过
2. 添加适当的文档和注释
3. 遵循项目的代码风格
