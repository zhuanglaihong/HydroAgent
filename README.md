# 🤖 水文模型自动率定HydroAgent

基于 LangChain 和 ollama 构建的水文模型率定系统,能够让 LLM 根据已有的模型和数据构建工作流,自动化率定水文模型参数

和传统的聊天式 Agent 不同之处在于, HydroAgent 还有任务规划、调用工具、自主思考的功能,以任务为导向形成工作流

## 📦 安装部署

### 环境要求

- Python 3.11+
- Ollama (本地大模型服务)
- 推荐使用uv进行环境管理

### 快速安装

```bash
# 1. 安装uv
pip install uv

# 2. 同步依赖
uv sync

# 3. 激活虚拟环境
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# 4. 安装Ollama
# 访问 https://ollama.ai/ 下载安装
# 查看模型列表
ollama list 

# 5. 模型下载
ollama pull qwen3:8b
ollama pull granite3-dense:8b

# 模型删除
# ollama rm <model name>
```

## 🚀 使用说明

### 智能体主界面 (Agent.py)

**🎯 基于工作流的智能水文模型助手**：

- 🤖 **工作流智能规划**: 自动分析任务并生成执行计划
- 🧠 **RAG知识库增强**: 集成HydroRAG系统，基于专业水文领域文档智能生成工作流
- 📚 **智能知识检索**: 自动从知识库检索相关模型配置、参数设置等专业信息
- ⚡ **自动化执行**: 智能调度和执行水文建模任务
- 🔧 **专业工具集成**: 无缝对接水文模型工具链
- 📊 **智能结果分析**: 自动评估和展示执行结果

**使用方法**:

```bash
# 交互模式（默认启用RAG知识库）
python Agent.py

# 启用RAG知识库增强（推荐，默认已启用）
python Agent.py --enable-rag

# 禁用RAG使用基础模式
python Agent.py --disable-rag

# 调试模式（显示详细日志）
python Agent.py --debug

# 指定模型
python Agent.py --model qwen3:8b

# 单次查询
python Agent.py --query "率定并评估GR4J模型"

# 组合使用RAG和调试模式
python Agent.py --enable-rag --debug --model granite3-dense:8b

# MCP服务模式（需要先启动服务器）
# 1. 启动MCP服务器（在新终端中）
python hydromcp/run_server.py

# 2. 启动Agent（使用服务模式）
python Agent.py --mcp-mode service

# 注意：服务器日志会保存在 mcp_server.log 中

# 查看帮助
python Agent.py --help
```

**支持的任务类型**:

- 模型率定: "率定GR4J模型"
- 模型评估: "评估XAJ模型性能"
- 数据准备: "准备数据"
- 参数查询: "查看gr4j参数"

**🧠 RAG知识库增强功能**:

- **智能模型配置**: 基于专业文档自动推荐最佳模型参数配置
- **上下文感知**: 根据任务类型自动检索相关的专业知识片段
- **专业术语理解**: 自动识别和扩展水文建模领域的专业术语
- **工作流优化**: 结合知识库信息生成更完整和专业的执行步骤
- **参数建议**: 提供基于文献和最佳实践的参数设置建议
- 系统信息: "info"

## 🏗️ 系统架构

HydroAgent采用模块化设计，各个模块职责明确，协同工作形成完整的水文模型智能体系统。

```text
HydroAgent系统
├── Agent.py               # 智能体主程序
│
├── workflow/              # 工作流编排层
│   ├── orchestrator.py    # 工作流编排器
│   ├── intent_processor.py # 意图理解
│   ├── query_expander.py  # 查询扩展
│   ├── knowledge_retriever.py # 知识检索器
│   ├── context_builder.py # 上下文构建
│   ├── workflow_generator.py # 工作流生成
│   └── rag_integration_example.py # RAG集成示例
│
├── tool/                  # 工具执行层
│   ├── langchain_tool.py  # LangChain工具集成
│   ├── workflow_executor.py # 工作流执行器
│   └── ollama_config.py   # Ollama配置管理
│
├── hydrorag/             # RAG知识库系统 🆕
│   ├── rag_system.py     # RAG系统主接口
│   ├── document_processor.py # 文档处理
│   ├── embeddings_manager.py # 嵌入模型管理
│   ├── vector_store.py   # 向量数据库
│   ├── config.py         # 配置管理
│   └── example.py        # 使用示例
│
├── RAG/                   # 传统知识库层（待迁移）
│   ├── document_loader.py # 文档加载
│   ├── vector_store.py    # 向量存储
│   └── retriever.py       # 知识检索
│
├── hydromodel/           # 水文模型层
│   ├── models/          # 水文模型集合
│   │   ├── gr4j.py     # GR4J模型
│   │   └── xaj.py      # 新安江模型
│   ├── datasets/       # 数据处理
│   └── trainers/       # 模型训练器
│
└── test/                 # 测试层
    ├── test_workflow_use_tool.py # 工作流测试
    └── test_tools.py    # 工具测试
```

### 系统工作流程

1. **系统初始化**:
   - 检查 Ollama 服务和模型可用性
   - 加载水文模型工具集
   - 初始化工作流组件
   - 选择MCP工具执行模式：
     * 兼容模式（默认）：直接在本地执行工具，简单高效
     * 服务模式：通过独立的MCP服务器执行工具，支持分布式部署

2. **用户交互**:
   - 支持交互式对话和单次查询两种模式
   - 提供调试模式查看详细执行过程
   - 可指定使用的语言模型

3. **知识增强工作流生成**:
   - 意图处理器分析用户需求
   - 查询扩展器优化任务描述
   - 知识检索器从向量库获取相关知识
   - 上下文构建器整合任务信息和知识片段
   - 工作流生成器基于知识库规划执行步骤

4. **工作流执行**:
   - 工作流执行器调度任务
   - 验证工作流可执行性
   - 按步骤执行工具调用
   - 实时监控执行状态

5. **结果处理**:
   - 收集各步骤执行结果
   - 分析模型评估指标
   - 整理执行过程日志
   - 生成任务执行报告

### 核心特点

- **知识驱动**: 基于RAG系统的知识库增强工作流生成
- **工作流驱动**: 智能规划和自动执行任务流程
- **模块化设计**: 组件化架构，职责分明
- **智能调度**: 自动选择和调用合适的工具
- **错误处理**: 完善的异常处理和故障诊断
- **日志追踪**: 详细的执行日志和调试信息
- **可扩展性**: 易于添加新的模型和工具

### RAG知识库系统 🆕

HydroAgent现已集成完整的RAG知识库系统，能够从领域文档中提取知识并智能生成工作流：

**主要功能**:
- 📚 **文档处理**: 自动解析和分块处理技术文档
- 🧠 **向量化存储**: 使用本地Ollama嵌入模型构建向量库
- 🔍 **智能检索**: 根据用户查询检索相关知识片段
- ⚡ **工作流增强**: 基于检索到的知识生成更准确的工作流

**快速体验**:
```bash
# 测试RAG系统集成
python workflow/rag_integration_example.py

# 运行知识库构建和检索测试
python test/test_hydrorag_knowledge_integration.py

# 快速演示
python hydrorag/demo_knowledge_integration.py
```

**支持的文档类型**:
- Markdown文档 (.md)
- 文本文件 (.txt)
- PDF文档 (.pdf)
- Word文档 (.docx)

**知识检索示例**:
```python
from workflow.rag_integration_example import RAGEnhancedWorkflowSystem

# 初始化增强系统
system = RAGEnhancedWorkflowSystem()

# 基于知识库生成工作流
result = system.generate_workflow_with_knowledge(
    user_query="使用GR4J模型进行流域建模",
    use_knowledge=True,
    knowledge_top_k=5
)
```

### 水文模型

| 模型名称 | 说明          |
|---------|---------------|
| GR1Y    | GR年尺度模型   |
| GR2M    | GR月尺度模型   |
| GR4J    | GR日尺度模型   |
| GR5J    | GR日尺度模型   |
| GR6J    | GR日尺度模型   |
| XAJ     | 新安江模型     |

## 🎯 开发路线

### 已完成功能 ✅

- [x] 基于工作流的智能体架构
- [x] 水文模型工具集成
- [x] 本地Ollama模型支持
- [x] 工作流生成和执行
- [x] 完整的日志系统
- [x] 基础测试框架
- [x] **RAG知识库系统集成** 🆕
- [x] **知识驱动的工作流生成** 🆕
- [x] **本地向量库构建和检索** 🆕

### 进行中功能 🚧

- [ ] Agent与RAG系统的深度集成
- [ ] 工作流执行并行化
- [ ] 执行结果可视化
- [ ] 更多水文模型支持
- [ ] 用户前端交互界面
- [ ] 优化hydromodel改为统一的接口
- [ ] 知识库自动更新机制

## 📄 许可证

本项目采用 MIT 许可证，详见 LICENSE 文件。

## 📞 联系方式

- **开发者**: zhuanglaihong
- **项目地址**: [https://gitcode.com/dlut-water/langchain-query.git]
- **问题反馈**: [https://gitcode.com/dlut-water/langchain-query/issues]

---

**版本**: v1.1.0  
**最后更新**: 2025年9月17日  
**新增**: RAG知识库系统集成，支持知识驱动的工作流生成