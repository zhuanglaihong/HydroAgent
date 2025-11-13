# HydroRAG 资源清理指南

## 概述

HydroRAG 集成了自动资源清理机制，确保嵌入模型的 httpx 连接等资源被正确释放，避免端口占用和内存泄漏问题。

## 问题背景

在使用 Ollama 嵌入模型时，底层的 httpx 客户端可能不会自动释放连接，导致：
- 端口被占用，后续请求挂起或超时
- 内存泄漏
- 需要重启 Ollama 服务才能恢复

## 解决方案

### 1. 资源管理模块

新增 `hydrorag/resource_manager.py` 模块，提供：

- **ResourceManager**: 统一的资源清理管理器
- **CleanupContext**: 上下文管理器，确保资源自动清理
- **EmbeddingClientPool**: 客户端池，复用连接

### 2. 自动清理机制

#### EmbeddingsManager 自动清理

```python
from hydrorag.embeddings_manager import EmbeddingsManager
from hydrorag.config import default_config

# 方式1: 手动清理
embeddings = EmbeddingsManager(default_config)
embedding = embeddings.embed_text("测试文本")
embeddings.cleanup()  # 手动调用清理

# 方式2: 自动清理（推荐）
# 对象销毁时自动调用 __del__ 清理
embeddings = EmbeddingsManager(default_config)
embedding = embeddings.embed_text("测试文本")
del embeddings  # 触发自动清理
```

#### RAGSystem 上下文管理器

```python
from hydrorag.rag_system import RAGSystem
from hydrorag.config import default_config

# 使用 with 语句，退出时自动清理所有资源
with RAGSystem(default_config) as rag:
    result = rag.query("GR4J模型参数", top_k=5)
    print(result)
# 退出 with 语句时自动清理
```

### 3. 核心清理功能

#### 清理嵌入模型客户端

```python
from hydrorag.resource_manager import ResourceManager

# 清理单个嵌入模型
ResourceManager.cleanup_embedding_client(embeddings)

# 强制垃圾回收
ResourceManager.force_gc(generation=2)
```

#### 安全清理任意对象

```python
from hydrorag.resource_manager import ResourceManager

# 通用清理方法
ResourceManager.safe_cleanup(obj, cleanup_method='close')
```

## 使用模式

### 模式1: 一次性使用（推荐用 with）

```python
from hydrorag.rag_system import RAGSystem
from hydrorag.config import default_config

# 适用于脚本或单次查询
with RAGSystem(default_config) as rag:
    # 执行 RAG 操作
    result = rag.query("查询内容")
    print(result)
# 自动清理，无需手动操作
```

### 模式2: 长期使用（手动管理）

```python
from hydrorag.rag_system import RAGSystem
from hydrorag.config import default_config

# 适用于服务或长时间运行的程序
rag = RAGSystem(default_config)

try:
    # 执行多次操作
    for query in queries:
        result = rag.query(query)
        process_result(result)
finally:
    # 确保清理资源
    rag.cleanup()
```

### 模式3: 多次创建-销毁循环

```python
from hydrorag.embeddings_manager import EmbeddingsManager
from hydrorag.config import default_config
import gc

for i in range(10):
    # 创建嵌入模型
    embeddings = EmbeddingsManager(default_config)

    # 使用
    result = embeddings.embed_text(f"文本 {i}")

    # 清理
    embeddings.cleanup()
    del embeddings

    # 强制GC（可选，但推荐）
    gc.collect()
```

## 测试验证

运行资源清理测试脚本：

```bash
python test/test_resource_cleanup.py
```

测试包括：
1. 嵌入模型资源清理测试
2. RAG系统上下文管理器测试
3. 多次创建清理循环测试（验证无端口占用）
4. 超时场景资源清理测试

## 最佳实践

### ✅ 推荐做法

1. **优先使用上下文管理器**
   ```python
   with RAGSystem(config) as rag:
       # 你的代码
       pass
   ```

2. **显式调用 cleanup()**
   ```python
   rag = RAGSystem(config)
   try:
       # 使用 rag
       pass
   finally:
       rag.cleanup()
   ```

3. **在循环中及时清理**
   ```python
   for item in items:
       embeddings = EmbeddingsManager(config)
       # 使用 embeddings
       embeddings.cleanup()
   ```

### ❌ 避免的做法

1. **不清理就创建新实例**
   ```python
   # 错误：可能导致资源泄漏
   for i in range(100):
       rag = RAGSystem(config)  # 未清理旧实例
       rag.query("test")
   ```

2. **忘记在异常处理中清理**
   ```python
   # 错误：异常时不会清理
   rag = RAGSystem(config)
   rag.query("test")  # 如果抛异常，rag 不会被清理
   ```

## 技术细节

### 清理流程

1. **同步客户端清理**
   - 调用 `client.close()` 关闭同步客户端

2. **异步客户端清理（httpx）**
   - 获取或创建事件循环
   - 在线程池中执行 `client.aclose()`
   - 带超时保护（默认5秒）

3. **对象引用清理**
   - 删除对象引用 `del embeddings`

4. **强制垃圾回收**
   - 调用 `gc.collect()` 立即回收内存

### 支持的清理对象

- **OllamaEmbeddings** (langchain_ollama)
- **OllamaEmbeddings** (langchain_community)
- **QwenAPIEmbeddings** (自定义)
- **OpenAI客户端**

### 超时保护

所有清理操作都有超时保护，默认5秒：

```python
ResourceManager.cleanup_embedding_client(
    embeddings,
    timeout=5.0  # 超时时间
)
```

## 日志监控

启用 DEBUG 日志级别可以看到详细的清理过程：

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# 你会看到类似的日志：
# DEBUG - 成功关闭同步客户端
# DEBUG - 成功关闭异步客户端
# DEBUG - 嵌入模型客户端资源清理完成
# INFO - 嵌入模型资源清理完成，清理了 2 个模型
```

## 常见问题

### Q1: 为什么需要手动清理？

Python 的垃圾回收是非确定性的，httpx 异步客户端需要显式关闭才能释放连接。

### Q2: 清理会影响性能吗？

清理操作很轻量（几毫秒），建议在每次使用后都清理，避免累积问题。

### Q3: 如何验证清理成功？

运行 `test/test_resource_cleanup.py`，如果测试通过，说明清理机制正常工作。

### Q4: 旧代码需要修改吗？

不需要。新增的清理机制向后兼容，但建议使用 `with` 语句获得更好的资源管理。

## 更新历史

- **2025-10-12**: 初始版本，集成资源清理机制
  - 新增 `resource_manager.py` 模块
  - 更新 `EmbeddingsManager` 添加 `cleanup()` 方法
  - 更新 `RAGSystem` 完善上下文管理器
  - 新增资源清理测试脚本

## 参考资料

- [Python上下文管理器](https://docs.python.org/3/reference/datamodel.html#context-managers)
- [httpx异步客户端](https://www.python-httpx.org/async/)
- [Python垃圾回收](https://docs.python.org/3/library/gc.html)
