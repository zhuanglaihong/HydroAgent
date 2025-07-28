# Workflow 智能工作流编排系统

## 概述

Workflow系统是一个基于LLM和RAG的智能工作流编排系统，能够根据用户输入自动生成详细的、可执行的工作流计划。系统集成了意图理解、查询扩展、知识检索、上下文构建和工作流生成等核心功能。

## 系统架构

```
Workflow系统
├── 意图处理器 (IntentProcessor) - 第1步
├── 查询扩展器 (QueryExpander) - 第2步  
├── 知识检索器 (KnowledgeRetriever) - 第3步
├── 上下文构建器 (ContextBuilder) - 第4步
├── 工作流生成器 (WorkflowGenerator) - 第5步
└── 主编排器 (WorkflowOrchestrator) - 协调器
```

## 核心组件

### 1. 意图处理器 (IntentProcessor)
**功能**: 将模糊的用户查询重构为明确的指令
- 识别任务类型和实体信息
- 提供置信度评估
- 建议合适的工具组合

**示例**:
```python
from workflow import IntentProcessor

processor = IntentProcessor(llm)
intent = processor.process_intent("我想率定一个GR4J模型")
print(f"任务类型: {intent.task_type}")
print(f"建议工具: {intent.suggested_tools}")
```

### 2. 查询扩展器 (QueryExpander)
**功能**: 改写和扩展原始意图以获得更丰富的上下文
- LLM智能扩展
- 规则基础扩展
- 水文领域专业术语扩展

**示例**:
```python
from workflow import QueryExpander

expander = QueryExpander(llm)
expanded_query = expander.expand_query(intent_analysis)
print(f"扩展查询: {expanded_query}")
```

### 3. 知识检索器 (KnowledgeRetriever) ⭐ **RAG集成**
**功能**: 从本地知识库检索相关文档片段
- 支持RAG系统集成
- 向量相似性检索
- 默认知识库回退机制
- 内容后处理和去重

**RAG集成特性**:
- 自动检测现有知识库索引
- 支持多种检索策略（vector, bm25, ensemble）
- 智能内容清理和评分调整
- 完整的错误处理和回退机制

**示例**:
```python
from workflow import KnowledgeRetriever

# 使用RAG系统
retriever = KnowledgeRetriever(
    rag_system=rag_system,  # 你的RAG系统实例
    faiss_index_path="./faiss_db",
    enable_fallback=True
)

# 检索知识片段
fragments = retriever.retrieve_knowledge(
    expanded_query="GR4J模型参数率定",
    k=5,
    score_threshold=0.3,
    retriever_type="vector"
)
```

### 4. 上下文构建器 (ContextBuilder)
**功能**: 拼接用户输入和检索到的知识片段
- 构建结构化的LLM提示
- 包含工具描述和示例
- 长度控制和优化

**示例**:
```python
from workflow import ContextBuilder

builder = ContextBuilder()
context = builder.build_context(
    user_query="率定GR4J模型",
    intent_analysis=intent,
    knowledge_fragments=fragments
)
```

### 5. 工作流生成器 (WorkflowGenerator)
**功能**: 基于上下文生成详细的工作流计划
- 输出严格的JSON格式
- 确保LangChain框架兼容性
- 包含依赖关系和错误处理

**示例**:
```python
from workflow import WorkflowGenerator

generator = WorkflowGenerator(llm)
workflow_plan = generator.generate_workflow(
    context=context,
    user_query="率定GR4J模型",
    intent_analysis=intent
)
```

### 6. 主编排器 (WorkflowOrchestrator)
**功能**: 整合所有步骤的主要协调器
- 端到端工作流处理
- 分步执行和调试
- 统计信息和系统监控

**示例**:
```python
from workflow import WorkflowOrchestrator

orchestrator = WorkflowOrchestrator(
    llm=llm,
    rag_system=rag_system,  # 可选：集成RAG系统
    tools=tools,
    enable_debug=True
)

# 处理用户查询
workflow_plan = orchestrator.process_query("我想率定一个GR4J模型")

# 分步执行
step_results = orchestrator.process_query_step_by_step("查询GR4J参数")
```

## RAG系统集成

### 设置RAG系统

1. **初始化RAG系统**:
```python
from RAG import RAGSystem
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_ollama import ChatOllama

# 初始化模型
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)
llm = ChatOllama(model="granite3-dense:8b")

# 创建RAG系统
rag_system = RAGSystem(
    embeddings=embeddings,
    llm=llm,
    index_path="./faiss_db"
)
```

2. **构建知识库**:
```python
# 加载文档
doc_count = rag_system.load_documents("./documents")

# 创建索引
rag_system.create_index()
```

3. **集成到Workflow**:
```python
# 创建知识检索器
knowledge_retriever = KnowledgeRetriever(
    rag_system=rag_system,
    faiss_index_path="./faiss_db"
)

# 在编排器中使用
orchestrator = WorkflowOrchestrator(
    llm=llm,
    rag_system=rag_system,
    tools=tools
)
```

### 知识库管理

**加载文档到RAG系统**:
```python
# 加载文档
success = knowledge_retriever.load_documents_to_rag(
    document_path="./documents",
    file_extensions=[".txt", ".md", ".pdf"]
)
```

**测试检索功能**:
```python
# 测试检索
test_result = knowledge_retriever.test_retrieval("GR4J模型参数")
print(f"检索结果: {test_result}")
```

## 使用示例

### 基本使用

```python
from workflow import WorkflowOrchestrator
from tool.langchain_tool import get_hydromodel_tools

# 初始化编排器
orchestrator = WorkflowOrchestrator(
    llm=llm,
    tools=get_hydromodel_tools(),
    enable_debug=True
)

# 处理查询
workflow_plan = orchestrator.process_query("我想率定一个GR4J模型")

# 导出LangChain格式
langchain_format = orchestrator.export_workflow_to_langchain_format(workflow_plan)
```

### 带RAG系统的完整示例

```python
# 1. 设置RAG系统
from RAG import RAGSystem
rag_system = RAGSystem(embeddings=embeddings, llm=llm, index_path="./faiss_db")

# 2. 构建知识库
rag_system.load_documents("./documents")
rag_system.create_index()

# 3. 创建编排器
orchestrator = WorkflowOrchestrator(
    llm=llm,
    rag_system=rag_system,  # 集成RAG系统
    tools=get_hydromodel_tools()
)

# 4. 处理查询（现在会使用知识库）
workflow_plan = orchestrator.process_query("我想了解GR4J模型参数并进行率定")
```

### 分步执行

```python
# 分步执行，查看每步结果
results = orchestrator.process_query_step_by_step("率定GR4J模型")

for step_name, step_result in results['steps'].items():
    print(f"{step_name}: {step_result['status']}")
    print(f"耗时: {step_result['execution_time']:.2f}秒")
```

## 配置选项

### 知识检索器配置

```python
knowledge_retriever = KnowledgeRetriever(
    rag_system=rag_system,           # RAG系统实例
    faiss_index_path="./faiss_db",   # FAISS索引路径
    embeddings=embeddings,           # 嵌入模型
    llm=llm,                        # 语言模型
    enable_fallback=True             # 启用回退机制
)
```

### 编排器配置

```python
orchestrator = WorkflowOrchestrator(
    llm=llm,                    # 语言模型
    embeddings=embeddings,      # 嵌入模型（可选）
    rag_system=rag_system,      # RAG系统（可选）
    tools=tools,                # 工具列表
    enable_debug=True           # 调试模式
)
```

## 测试

### 运行基本测试

```bash
python workflow/example.py
```

### 运行RAG集成测试

```bash
python workflow/rag_integration_example.py
```

### 单独测试组件

```python
# 测试知识检索器
from workflow import KnowledgeRetriever
retriever = KnowledgeRetriever()
test_result = retriever.test_retrieval("GR4J模型参数")
print(test_result)
```

## 性能优化

### 1. 知识检索优化

- **调整检索参数**: 修改 `k` 和 `score_threshold`
- **使用集成检索器**: 结合多种检索策略
- **内容后处理**: 自动清理和去重

### 2. 上下文长度控制

- **动态截断**: 根据模型限制自动调整
- **重要性排序**: 保留最重要的内容部分
- **压缩策略**: 智能压缩长文本

### 3. 缓存机制

- **检索结果缓存**: 避免重复检索
- **上下文缓存**: 相似查询复用上下文
- **工作流缓存**: 相似任务复用工作流

## 扩展功能

### 1. 自定义知识检索器

```python
class CustomKnowledgeRetriever(KnowledgeRetriever):
    def retrieve_knowledge(self, query, **kwargs):
        # 自定义检索逻辑
        pass
```

### 2. 自定义上下文构建器

```python
class CustomContextBuilder(ContextBuilder):
    def build_context(self, **kwargs):
        # 自定义上下文构建逻辑
        pass
```

### 3. 自定义工作流生成器

```python
class CustomWorkflowGenerator(WorkflowGenerator):
    def generate_workflow(self, **kwargs):
        # 自定义工作流生成逻辑
        pass
```

## 故障排除

### 常见问题

1. **RAG系统无法初始化**
   - 检查依赖包是否正确安装
   - 确认模型文件是否存在
   - 检查索引路径权限

2. **知识检索返回空结果**
   - 检查知识库是否已构建
   - 调整检索参数（k, score_threshold）
   - 启用回退机制

3. **工作流生成失败**
   - 检查LLM连接状态
   - 验证上下文长度是否超限
   - 查看错误日志

### 调试模式

```python
# 启用调试模式
orchestrator.enable_debug_mode()

# 查看系统信息
info = orchestrator.get_system_info()
print(info)

# 验证组件状态
validation = orchestrator.validate_components()
print(validation)
```

## 待完成的组件

目前系统已完成前5步的核心功能，第6步（任务执行器）计划在 `tool` 模块中实现：

- ✅ 第1步：意图理解 (IntentProcessor)
- ✅ 第2步：查询扩展 (QueryExpander)  
- ✅ 第3步：知识检索 (KnowledgeRetriever) - **已集成RAG系统**
- ✅ 第4步：上下文构建 (ContextBuilder)
- ✅ 第5步：工作流生成 (WorkflowGenerator)
- 🔄 第6步：任务执行 (TaskExecutor) - **计划在tool模块实现**

## 贡献指南

欢迎提交Issue和Pull Request来改进Workflow系统。在提交代码前，请确保：

1. 运行所有测试并确保通过
2. 添加适当的文档和注释
3. 遵循项目的代码风格
4. 更新相关文档

## 许可证

本项目采用MIT许可证。详见LICENSE文件。 