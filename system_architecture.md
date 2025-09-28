# HydroAgent 系统架构文档

本文档详细描述HydroAgent智能水文建模系统的架构设计、核心组件和运行机制。

## 系统概述

HydroAgent是基于LangChain的智能水文模型率定系统，集成了RAG（检索增强生成）技术，支持工作流驱动的自动化建模流程。

### 核心特性
- **智能工作流**：基于目标导向的React模式执行
- **知识增强**：RAG系统提供专业知识支持
- **多模型支持**：GR系列、XAJ等主流水文模型
- **自动优化**：迭代式参数调优和性能评估
- **可扩展性**：模块化设计，易于扩展新功能

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    用户接口层                            │
├─────────────────────────────────────────────────────────┤
│  Agent.py (主入口)  │  script/run_*.py (执行脚本)        │
└─────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────┐
│                   工作流编排层                           │
├─────────────────────────────────────────────────────────┤
│  workflow/                                              │
│  ├── workflow_generator_v2.py    # 工作流生成           │
│  ├── workflow_assembler.py       # 工作流组装           │
│  ├── cot_rag_engine.py          # CoT+RAG引擎          │
│  └── instruction_parser.py       # 指令解析             │
└─────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────┐
│                    执行引擎层                           │
├─────────────────────────────────────────────────────────┤
│  executor/                                              │
│  ├── main.py                    # 主执行器             │
│  ├── core/                      # 核心执行组件         │
│  │   ├── react_executor.py      # React模式执行器      │
│  │   ├── simple_executor.py     # 简单任务执行器       │
│  │   ├── complex_solver.py      # 复杂任务解决器       │
│  │   ├── task_dispatcher.py     # 任务分发器          │
│  │   └── workflow_receiver.py   # 工作流接收器         │
│  ├── models/                    # 数据模型定义         │
│  └── tools/                     # 工具注册和管理       │
└─────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────┐
│                   知识增强层                           │
├─────────────────────────────────────────────────────────┤
│  hydrorag/                                              │
│  ├── rag_system.py             # RAG主系统             │
│  ├── vector_store.py           # 向量数据库             │
│  ├── embeddings_manager.py     # 嵌入模型管理          │
│  ├── document_processor.py     # 文档处理               │
│  └── query_processor.py        # 查询处理               │
└─────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────┐
│                   工具执行层                           │
├─────────────────────────────────────────────────────────┤
│  hydrotool/                                             │
│  ├── langchain_tool.py         # LangChain工具集成     │
│  ├── workflow_executor.py      # 工作流执行器          │
│  └── ollama_config.py          # Ollama配置管理        │
└─────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────┐
│                   模型计算层                           │
├─────────────────────────────────────────────────────────┤
│  hydromodel/                   # 水文模型核心          │
│  ├── GR系列模型 (GR4J, GR5J等)                         │
│  ├── XAJ模型                                           │
│  └── 优化算法 (SCE-UA, GA等)                           │
└─────────────────────────────────────────────────────────┘
```

## 核心组件详解

### 1. 执行引擎 (executor/)

#### ExecutorEngine (main.py)
- **功能**：系统主入口，统一调度各种执行器
- **支持模式**：Sequential（顺序）、React（迭代）
- **职责**：工作流解析、模式选择、结果收集

#### ReactExecutor (core/react_executor.py)
- **功能**：目标导向的迭代执行器
- **特性**：
  - 自动目标评估和达成判断
  - 智能参数调整策略
  - 条件任务执行（如数据准备只执行一次）
  - 实时NSE指标提取和监控

#### TaskDispatcher (core/task_dispatcher.py)
- **功能**：任务分发和依赖管理
- **特性**：
  - 依赖图构建和拓扑排序
  - 任务状态跟踪
  - 并行执行支持

### 2. 工作流编排 (workflow/)

#### WorkflowGenerator (workflow_generator_v2.py)
- **功能**：基于自然语言生成工作流
- **集成**：CoT推理 + RAG知识检索
- **输出**：标准化JSON工作流配置

#### CoTRAGEngine (cot_rag_engine.py)
- **功能**：链式思维推理与知识检索集成
- **流程**：
  1. 意图理解和任务分解
  2. 知识库检索相关经验
  3. 推理生成最优工作流
  4. 参数配置和验证

### 3. 知识增强系统 (hydrorag/)

#### RAGSystem (rag_system.py)
- **功能**：检索增强生成主系统
- **组件**：
  - 文档处理和分块
  - 向量嵌入和存储
  - 语义检索和排序
  - 上下文增强生成

#### VectorStore (vector_store.py)
- **后端**：ChromaDB
- **嵌入模型**：Ollama nomic-embed-text
- **功能**：
  - 高效向量存储和检索
  - 元数据过滤
  - 相似度计算

### 4. 工具系统 (executor/tools/)

#### ToolRegistry (registry.py)
- **功能**：工具注册和管理中心
- **支持工具**：
  - get_model_params：模型参数查询
  - prepare_data：数据预处理
  - calibrate_model：模型率定
  - evaluate_model：性能评估

#### 工具执行流程
```
1. 工具注册 → 2. 参数验证 → 3. 执行调用 → 4. 结果处理 → 5. 状态更新
```

## 数据流架构

### 1. 输入数据流
```
用户指令 → 指令解析 → 意图识别 → 知识检索 → 工作流生成
```

### 2. 执行数据流
```
工作流JSON → 任务解析 → 依赖分析 → 工具调用 → 结果收集
```

### 3. React迭代流
```
初始执行 → 目标评估 → 参数调整 → 重新执行 → 直到达标或超时
```

## 配置管理

### 层次化配置体系
```
definitions_private.py (用户私有配置)
        ↓
definitions.py (项目默认配置)
        ↓
config.py (全局参数配置)
        ↓
工作流JSON (任务级配置)
```

### 关键配置项
- **路径配置**：PROJECT_DIR, DATASET_DIR, RESULT_DIR
- **模型配置**：OLLAMA_BASE_URL, EMBEDDING_MODEL
- **RAG配置**：KNOWLEDGE_BASE_DIR, chunk_size, top_k
- **执行配置**：timeout, retry_count, debug_mode

## 扩展机制

### 1. 新工具集成
```python
from executor.tools.base_tool import BaseTool

class NewTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="new_tool",
            description="新工具描述"
        )

    def execute(self, **kwargs):
        # 工具实现逻辑
        return result
```

### 2. 新模型支持
```python
# 在hydromodel中添加新模型实现
class NewModel(BaseModel):
    def calibrate(self, data, params):
        # 模型率定逻辑
        pass

    def simulate(self, data, params):
        # 模型模拟逻辑
        pass
```

### 3. 新执行器模式
```python
class CustomExecutor(BaseExecutor):
    def execute_workflow(self, workflow):
        # 自定义执行逻辑
        pass
```

## 性能优化

### 1. 执行优化
- **并行任务执行**：无依赖任务并行处理
- **智能缓存**：数据预处理结果缓存
- **条件执行**：避免重复任务执行

### 2. 内存优化
- **流式处理**：大文件分块处理
- **及时释放**：执行完成后释放资源
- **配置调优**：根据硬件调整参数

### 3. RAG优化
- **嵌入缓存**：重复文档嵌入缓存
- **检索优化**：多级过滤和排序
- **上下文裁剪**：智能上下文长度控制

## 监控和日志

### 日志体系
```
应用日志 (logs/)
├── system.log          # 系统运行日志
├── execution.log       # 执行过程日志
├── rag.log            # RAG系统日志
└── error.log          # 错误日志
```

### 监控指标
- **执行性能**：任务耗时、成功率、资源使用
- **RAG效果**：检索准确率、响应时间
- **模型性能**：NSE、RMSE等评估指标

## 安全和可靠性

### 1. 数据安全
- **路径验证**：防止路径遍历攻击
- **输入验证**：严格的参数类型检查
- **权限控制**：文件操作权限限制

### 2. 执行可靠性
- **异常处理**：完善的错误捕获和恢复
- **超时控制**：防止长时间阻塞
- **状态检查**：执行状态实时监控

### 3. 系统健壮性
- **graceful degradation**：组件故障时优雅降级
- **重试机制**：网络和I/O错误自动重试
- **检查点机制**：长任务执行检查点保存

## 部署架构

### 1. 单机部署
```
HydroAgent
├── 核心服务 (Python进程)
├── Ollama服务 (本地LLM)
├── ChromaDB (向量数据库)
└── 文件系统 (数据和结果存储)
```

### 2. 分布式部署
```
负载均衡器
    ↓
多个HydroAgent实例
    ↓
共享数据存储 (NFS/对象存储)
共享向量数据库 (ChromaDB集群)
```

## 技术栈总结

- **框架**：LangChain (AI编排)
- **LLM**：Ollama (本地推理)
- **向量数据库**：ChromaDB
- **水文建模**：自研hydromodel库
- **数据处理**：pandas, numpy, xarray
- **可视化**：matplotlib, plotly
- **配置管理**：pydantic
- **日志系统**：标准logging模块