# Dify知识库构建器

## 概述

Dify知识库构建器是一个专门用于从Dify服务器调用分词模型来构建本地知识库的工具。它结合了Dify服务器的智能分词能力和本地向量存储，为RAG系统提供高质量的知识库支持。

## 功能特性

### 🔧 核心功能
- **Dify服务器集成**: 调用Dify服务器的分词模型进行智能文档分块
- **多格式支持**: 支持TXT、MD、PDF、DOCX、CSV等多种文档格式
- **向量存储**: 使用FAISS进行高效的向量索引和检索
- **智能分块**: 基于语义的分块策略，保持文档的语义完整性
- **质量保证**: 自动过滤短片段，确保知识片段的质量

### 🚀 高级特性
- **连接测试**: 自动测试Dify服务器连接状态
- **错误处理**: 完善的错误处理和回退机制
- **进度监控**: 详细的处理进度和日志记录
- **查询测试**: 内置知识库查询测试功能
- **配置灵活**: 支持自定义分块参数和嵌入模型

## 安装依赖

```bash
pip install requests
pip install langchain
pip install langchain-community
pip install faiss-cpu
pip install sentence-transformers
```

## 快速开始

### 1. 基本使用

```python
from dify_knowledge_builder import DifyKnowledgeBuilder

# 创建构建器
builder = DifyKnowledgeBuilder(
    dify_api_url="http://localhost:5001",
    dify_api_key="your-api-key",
    embeddings_model="sentence-transformers/all-MiniLM-L6-v2"
)

# 构建知识库
success = builder.build_knowledge_base("./documents")
```

### 2. 命令行使用

```bash
python dify_knowledge_builder.py \
  --dify_url "http://localhost:5001" \
  --dify_key "your-api-key" \
  --source "./documents" \
  --index_name "my_knowledge_base"
```

### 3. 自定义参数

```bash
python dify_knowledge_builder.py \
  --dify_url "http://localhost:5001" \
  --dify_key "your-key" \
  --source "./sample_documents" \
  --chunk_size 800 \
  --chunk_overlap 150 \
  --embeddings_model "sentence-transformers/all-MiniLM-L6-v2" \
  --test_query "GR4J模型参数"
```

## 详细使用指南

### 初始化配置

```python
from dify_knowledge_builder import DifyKnowledgeBuilder

# 基本配置
builder = DifyKnowledgeBuilder(
    dify_api_url="http://localhost:5001",      # Dify服务器地址
    dify_api_key="your-api-key",               # API密钥
    embeddings_model="sentence-transformers/all-MiniLM-L6-v2",  # 嵌入模型
    chunk_size=1000,                           # 分块大小
    chunk_overlap=200,                         # 分块重叠
    index_path="./faiss_db"                    # 索引保存路径
)
```

### 测试连接

```python
# 测试Dify服务器连接
if builder.test_dify_connection():
    print("✅ 连接成功")
else:
    print("❌ 连接失败")
```

### 构建知识库

```python
# 从单个文件构建
success = builder.build_knowledge_base("./document.txt")

# 从目录构建
success = builder.build_knowledge_base(
    source_path="./documents",
    file_extensions=[".txt", ".md", ".pdf"],
    index_name="hydrology_knowledge"
)
```

### 查询知识库

```python
# 查询知识库
results = builder.query_knowledge_base("GR4J模型参数", k=5)

for i, result in enumerate(results, 1):
    print(f"结果{i}: {result['content'][:100]}...")
    print(f"分数: {result['score']:.4f}")
    print(f"来源: {result['metadata']['source']}")
```

### 获取系统信息

```python
# 获取知识库信息
info = builder.get_knowledge_base_info()
print(f"索引存在: {info['index_exists']}")
print(f"索引大小: {info.get('index_size', 'unknown')}")
print(f"连接状态: {info['dify_connection']}")
```

## 配置参数

### DifyKnowledgeBuilder参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `dify_api_url` | str | 必需 | Dify服务器API地址 |
| `dify_api_key` | str | 必需 | Dify API密钥 |
| `embeddings_model` | str | "sentence-transformers/all-MiniLM-L6-v2" | 嵌入模型名称 |
| `chunk_size` | int | 1000 | 文档分块大小 |
| `chunk_overlap` | int | 200 | 分块重叠大小 |
| `index_path` | str | "./faiss_db" | 向量索引保存路径 |

### 命令行参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--dify_url` | Dify服务器URL | `http://localhost:5001` |
| `--dify_key` | Dify API密钥 | `your-api-key` |
| `--source` | 源文档路径 | `./documents` |
| `--index_name` | 索引名称 | `my_knowledge_base` |
| `--chunk_size` | 分块大小 | `800` |
| `--chunk_overlap` | 分块重叠 | `150` |
| `--embeddings_model` | 嵌入模型 | `sentence-transformers/all-MiniLM-L6-v2` |
| `--test_query` | 测试查询 | `GR4J模型参数` |

## 使用示例

### 示例1：基本知识库构建

```python
from dify_knowledge_builder import DifyKnowledgeBuilder

# 创建构建器
builder = DifyKnowledgeBuilder(
    dify_api_url="http://localhost:5001",
    dify_api_key="your-api-key"
)

# 测试连接
if not builder.test_dify_connection():
    print("无法连接到Dify服务器")
    exit(1)

# 构建知识库
success = builder.build_knowledge_base("./documents")

if success:
    print("知识库构建成功！")
    
    # 测试查询
    results = builder.query_knowledge_base("水文模型参数")
    for result in results:
        print(f"内容: {result['content'][:100]}...")
else:
    print("知识库构建失败")
```

### 示例2：自定义配置

```python
# 自定义配置
builder = DifyKnowledgeBuilder(
    dify_api_url="http://your-dify-server:5001",
    dify_api_key="your-key",
    embeddings_model="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    chunk_size=800,
    chunk_overlap=150,
    index_path="./custom_faiss_db"
)

# 构建知识库
success = builder.build_knowledge_base(
    source_path="./hydrology_docs",
    file_extensions=[".txt", ".md", ".pdf"],
    index_name="hydrology_knowledge"
)
```

### 示例3：批量处理

```python
import os
from pathlib import Path

# 处理多个目录
doc_dirs = ["./docs1", "./docs2", "./docs3"]

for doc_dir in doc_dirs:
    if os.path.exists(doc_dir):
        print(f"处理目录: {doc_dir}")
        success = builder.build_knowledge_base(doc_dir)
        if success:
            print(f"✅ {doc_dir} 处理成功")
        else:
            print(f"❌ {doc_dir} 处理失败")
```

## 与RAG系统集成

### 集成到现有RAG系统

```python
from RAG import RAGSystem
from dify_knowledge_builder import DifyKnowledgeBuilder

# 创建Dify知识库构建器
dify_builder = DifyKnowledgeBuilder(
    dify_api_url="http://localhost:5001",
    dify_api_key="your-key"
)

# 构建知识库
dify_builder.build_knowledge_base("./documents")

# 创建RAG系统
rag_system = RAGSystem(
    embeddings=embeddings,
    llm=llm,
    index_path="./faiss_db"
)

# 使用构建的知识库
results = rag_system.query("查询内容")
```

### 与Workflow系统集成

```python
from workflow import WorkflowOrchestrator
from dify_knowledge_builder import DifyKnowledgeBuilder

# 构建Dify知识库
dify_builder = DifyKnowledgeBuilder(
    dify_api_url="http://localhost:5001",
    dify_api_key="your-key"
)
dify_builder.build_knowledge_base("./documents")

# 创建Workflow编排器
orchestrator = WorkflowOrchestrator(
    llm=llm,
    rag_system=rag_system,  # 使用包含Dify知识库的RAG系统
    tools=tools
)

# 处理查询
workflow_plan = orchestrator.process_query("我想了解GR4J模型参数")
```

## 故障排除

### 常见问题

1. **Dify服务器连接失败**
   ```
   错误: 无法连接到Dify服务器
   解决: 检查服务器地址和API密钥是否正确
   ```

2. **分词服务调用失败**
   ```
   错误: 分词失败: 404 - Not Found
   解决: 确认Dify服务器支持tokenization API
   ```

3. **文档处理失败**
   ```
   错误: 处理文档失败
   解决: 检查文档格式和编码是否正确
   ```

4. **向量索引创建失败**
   ```
   错误: 创建向量索引失败
   解决: 检查磁盘空间和权限
   ```

### 调试技巧

```python
# 启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 测试连接
builder.test_dify_connection()

# 检查知识库信息
info = builder.get_knowledge_base_info()
print(info)

# 测试查询
results = builder.query_knowledge_base("测试查询")
print(f"查询结果数量: {len(results)}")
```

## 性能优化

### 1. 分块参数优化

```python
# 根据文档特点调整分块参数
builder = DifyKnowledgeBuilder(
    chunk_size=800,      # 较小的分块适合短文档
    chunk_overlap=150    # 适度的重叠保持语义连贯
)
```

### 2. 嵌入模型选择

```python
# 中文文档推荐使用多语言模型
embeddings_model = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# 英文文档可以使用专用模型
embeddings_model = "sentence-transformers/all-MiniLM-L6-v2"
```

### 3. 批量处理优化

```python
# 批量处理大文档
import time

for doc_path in large_documents:
    builder.process_document_with_dify(doc_path)
    time.sleep(0.5)  # 避免API限制
```

## 扩展功能

### 自定义分词处理

```python
class CustomDifyKnowledgeBuilder(DifyKnowledgeBuilder):
    def call_dify_tokenization(self, text: str) -> List[str]:
        # 自定义分词逻辑
        # 可以添加预处理、后处理等
        return super().call_dify_tokenization(text)
```

### 添加文档过滤器

```python
def filter_documents(self, documents: List[Document]) -> List[Document]:
    """过滤文档"""
    filtered = []
    for doc in documents:
        if len(doc.page_content) > 50:  # 过滤太短的文档
            filtered.append(doc)
    return filtered
```

## 最佳实践

1. **文档准备**
   - 确保文档格式正确
   - 检查文档编码（推荐UTF-8）
   - 预处理文档内容

2. **参数调优**
   - 根据文档特点调整分块大小
   - 选择合适的嵌入模型
   - 测试不同的重叠参数

3. **质量保证**
   - 定期测试知识库查询效果
   - 监控分词质量
   - 验证向量索引性能

4. **维护管理**
   - 定期更新知识库
   - 备份重要索引
   - 监控存储空间

## 许可证

本项目采用MIT许可证。详见LICENSE文件。 