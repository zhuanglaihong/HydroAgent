# 🌊 HydroAgent - 智能水文建模系统

基于 LangChain、RAG 和多模型架构构建的下一代智能水文建模系统。HydroAgent 集成了工作流规划、知识检索增强和智能执行三大核心能力，实现从自然语言到水文建模任务的端到端自动化。

## 🎯 核心特色

与传统的聊天式 Agent 不同，HydroAgent 具备：
- 🧠 **智能工作流规划**: Builder 系统将自然语言转换为结构化工作流
- 📚 **RAG 知识增强**: HydroRAG 提供领域专业知识检索和推理
- ⚡ **智能执行引擎**: Executor 系统支持简单任务直接执行和复杂任务智能分解
- 🎛️ **多模型架构**: 推理模型、代码模型、嵌入模型各司其职，优化性能
- 🔧 **面向任务**: 以水文建模任务为导向，形成完整的自动化流程

## 📦 环境配置

### 系统要求

- Python 3.8+
- uv (Python 包管理器)
- Ollama (本地模型服务，可选)
- API 密钥 (qwen-turbo 或兼容的 OpenAI API)

### 1. 环境安装

```bash
# 安装 uv 包管理器
pip install uv

# 同步项目依赖
uv sync

# 激活虚拟环境
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac
```

### 2. 模型配置

#### API 模型配置 (推荐)

创建 `definitions_private.py` 配置文件：

```python
# API 配置 (用于推理和代码生成)
OPENAI_API_KEY = "your-qwen-api-key"  # 通义千问 API Key
OPENAI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 项目路径配置
PROJECT_DIR = r"D:\MCP\HydroAgent"
DATASET_DIR = r"D:\MCP\HydroAgent\data"
RESULT_DIR = r"D:\MCP\HydroAgent\results"

# 知识库配置
KNOWLEDGE_BASE_DIR = r"D:\MCP\HydroAgent\documents"
```

#### 本地模型配置 (降级备用)

```bash
# 安装 Ollama
# 访问 https://ollama.ai/ 下载安装

# 下载推理模型
ollama pull qwen3:8b

# 下载代码模型
ollama pull deepseek-coder:6.7b

# 下载嵌入模型
ollama pull bge-large:335m

# 查看已安装模型
ollama list
```

### 3. 参数配置

系统参数在 `config.py` 中统一配置，主要包括：

```python
# 推理模型 (Builder 阶段使用)
REASONING_API_MODEL = "qwen-turbo"          # API 推理模型
REASONING_FALLBACK_MODEL = "qwen3:8b"       # 本地推理模型

# 代码模型 (Executor 阶段使用)
CODER_API_MODEL = "qwen3-coder-plus"        # API 代码模型
CODER_FALLBACK_MODEL = "deepseek-coder:6.7b"  # 本地代码模型

# 嵌入模型 (RAG 系统使用)
EMBEDDING_API_MODEL = "text-embedding-v1"   # API 嵌入模型
EMBEDDING_FALLBACK_MODEL = "bge-large:335m"  # 本地嵌入模型
```

## 🚀 快速开始

### 交互式使用

```bash
# 启动智能体 (推荐，包含完整功能)
python Agent.py

# 禁用 RAG 模式 (仅基础功能)
python Agent.py --disable-rag

# 调试模式
python Agent.py --debug

# 单次查询模式
python Agent.py --query "率定并评估GR4J模型"

# 指定推理模型
python Agent.py --model qwen3:8b
```

### 支持的任务类型

#### 📊 **模型管理**
- `"获取GR4J模型参数"`
- `"查看XAJ模型配置"`
- `"比较不同模型特点"`

#### 📁 **数据处理**
- `"准备建模数据"`
- `"数据质量检查"`
- `"时间序列预处理"`

#### 🎯 **模型率定**
- `"率定GR4J模型"`
- `"使用2010-2015年数据率定XAJ模型"`
- `"多目标优化模型参数"`

#### 📈 **模型评估**
- `"评估模型性能"`
- `"计算NSE和KGE指标"`
- `"生成模拟结果对比图"`

#### 🔄 **复合任务**
- `"准备数据，率定XAJ模型，然后评估性能"`
- `"使用2010-2015年数据率定模型，用2016-2020年数据验证"`

### 系统信息
- 查看系统状态：`"info"` 或 `"系统信息"`
- 帮助信息：`"help"` 或 `"帮助"`
- 退出系统：`"exit"` 或 `"退出"`

## 🏗️ 系统架构

HydroAgent 采用三层分离的智能架构设计：

```
┌─────────────────────────────────────────────────────────────┐
│                      用户接口层                                │
│  Agent.py - 统一对话接口，支持多种交互模式和参数配置          │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────┼───────────────────────────────────────┐
│              核心业务层 (三大系统)                             │
├─────────────────────┼───────────────────────────────────────┤
│  📋 Builder 系统    │  📚 HydroRAG 系统   │  ⚙️ Executor 系统  │
│  • 工作流规划        │  • 知识检索          │  • 智能执行         │
│  • 意图识别          │  • 文档处理          │  • 任务分发         │
│  • 执行模式分析      │  • 向量化存储        │  • 结果收集         │
│  • RAG增强推理      │  • 语义搜索          │  • 可视化展示       │
└─────────────────────┼───────────────────────────────────────┘
                      │
┌─────────────────────┼───────────────────────────────────────┐
│                  工具执行层                                    │
│  水文建模工具链：模型参数、数据处理、率定算法、评估指标        │
└─────────────────────────────────────────────────────────────┘
```

### 🔧 三大核心系统

#### 📋 Builder 系统 - 智能工作流规划
- **智能意图识别**: 解析自然语言查询意图
- **RAG增强规划**: 结合知识库生成专业工作流
- **执行模式分析**: 根据任务复杂度选择最优执行策略
- **工作流验证**: 确保生成的工作流结构正确且可执行

#### 📚 HydroRAG 系统 - 知识检索增强
- **智能文档处理**: 支持PDF、Word、Markdown等格式
- **混合嵌入架构**: API优先 + 本地降级的双重保障
- **语义检索**: 基于ChromaDB的高效向量检索
- **知识融合**: 将检索到的领域知识融入工作流生成

#### ⚙️ Executor 系统 - 智能执行引擎
- **智能任务分发**: 区分简单任务和复杂任务，采用不同执行策略
- **简单任务直接执行**: 工具直调，高效快速
- **复杂任务智能分解**: LLM分解 + 步骤执行 + 结果整合
- **React模式**: 支持目标导向的迭代执行

### 🎯 多模型架构

HydroAgent 采用专业化模型架构，每种任务使用最适合的模型：

| 模型类型 | 使用场景 | API模型 | 本地模型 | 特点 |
|---------|---------|---------|----------|------|
| **推理模型** | Builder阶段工作流规划 | qwen-turbo | qwen3:8b | 逻辑推理能力强 |
| **代码模型** | Executor阶段工具调用 | qwen3-coder-plus | deepseek-coder:6.7b | 代码生成专业 |
| **嵌入模型** | RAG系统知识检索 | text-embedding-v1 | bge-large:335m | 语义理解精准 |

### 💡 设计理念

- **🧠 智能优先**: 基于知识和推理的智能决策
- **📊 数据驱动**: 以水文数据为核心的建模流程
- **🔄 工作流导向**: 结构化任务执行，可追溯可重现
- **🎛️ 分层解耦**: 规划、检索、执行三层分离，职责明确
- **⚡ 性能优化**: API优先 + 本地降级，平衡效果与成本
- **🔧 易于扩展**: 模块化设计，支持新模型和工具的集成


### 🌊 支持的水文模型

| 模型名称 | 全称 | 时间尺度 | 参数数量 | 特点 |
|---------|------|---------|----------|------|
| **GR1Y** | GR Annual | 年 | 2 | 年尺度水平衡 |
| **GR2M** | GR Monthly | 月 | 2 | 月尺度径流模拟 |
| **GR4J** | GR Daily | 日 | 4 | 经典日尺度模型 |
| **GR5J** | GR Daily | 日 | 5 | 增强版日尺度模型 |
| **GR6J** | GR Daily | 日 | 6 | 完整版日尺度模型 |
| **XAJ** | 新安江模型 | 日 | 15 | 中国经典分布式模型 |

### 🛠️ 核心工具集

| 工具名称 | 功能描述 | 输入 | 输出 |
|---------|---------|------|------|
| **get_model_params** | 获取模型参数信息 | 模型名称 | 参数配置 |
| **prepare_data** | 数据准备和预处理 | 数据路径 | 处理后数据 |
| **calibrate_model** | 模型参数率定 | 模型+数据 | 最优参数 |
| **evaluate_model** | 模型性能评估 | 模型+参数 | 评估指标 |

## 🎯 开发路线

### ✅ 已完成功能

**🏗️ 核心架构**
- [x] 三层分离架构设计 (Builder + HydroRAG + Executor)
- [x] 多模型架构 (推理/代码/嵌入模型分工)
- [x] 统一配置管理 (config.py + definitions_private.py)
- [x] 完整的测试框架

**📋 Builder 系统**
- [x] 智能工作流规划和生成
- [x] 执行模式智能分析 (Linear/React/Hybrid)
- [x] RAG增强的Chain-of-Thought推理
- [x] 意图识别和任务分类

**📚 HydroRAG 系统**
- [x] 多格式文档处理 (PDF/Word/Markdown/TXT)
- [x] 向量数据库构建 (ChromaDB)
- [x] 混合嵌入模型支持 (API + 本地)
- [x] 智能语义检索和重排序

**⚙️ Executor 系统**
- [x] 智能任务分发 (简单/复杂任务区分)
- [x] 简单任务直接执行
- [x] 复杂任务智能分解
- [x] React模式目标导向执行
- [x] 结果可视化和统计

**🔧 工具集成**
- [x] 水文模型工具链 (GR系列 + XAJ)
- [x] 数据处理和模型率定
- [x] 性能评估和指标计算

### 🚧 开发中功能

**🌐 系统集成**
- [ ] MCP (Model Context Protocol) 服务模式
- [ ] 分布式执行引擎
- [ ] 更多水文模型集成
- [ ] GPU加速计算支持

**🔍 智能增强**
- [ ] 多模态文档处理 (图表、公式识别)
- [ ] 自适应模型选择
- [ ] 知识库自动更新和版本管理
- [ ] 交互式工作流调试

**📊 用户界面**
- [ ] Web前端界面
- [ ] 实时执行监控
- [ ] 交互式结果分析
- [ ] 工作流可视化编辑器

### 🔮 未来规划

- [ ] 多语言支持 (英文/中文)
- [ ] 云端部署方案
- [ ] 企业级权限管理
- [ ] API服务化
- [ ] 移动端支持

## 📄 许可证

本项目采用 MIT 许可证，详见 LICENSE 文件。

## 📞 联系方式

- **开发团队**: DLUT Water Resources Lab
- **项目地址**: [https://gitcode.com/dlut-water/HydroAgent]
- **问题反馈**: [https://gitcode.com/dlut-water/HydroAgent/issues]
- **文档地址**: [查看完整文档](./CLAUDE.md)

## 🧪 测试

系统提供完整的测试套件：

```bash
# Builder 系统测试
python test/test_builder_basic.py          # 基础功能测试
python test/test_builder_integration.py    # 完整集成测试

# HydroRAG 系统测试
python test/test_enhanced_rag.py           # RAG系统测试

# Executor 系统测试
python test/test_executor_simple.py        # 简单任务测试
python test/test_executor_complex.py       # 复杂任务测试

# 系统集成测试
python test/run_integration_test.py        # 端到端集成测试
```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交改动 (`git commit -m 'Add some amazing feature'`)
4. 推送分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

---

<div align="center">
  <strong>版本</strong>: v2.0.0<br>
  <strong>更新时间</strong>: 2025年1月25日<br>
  <strong>重大更新</strong>: 全新三层架构 + 多模型系统 + 完整测试覆盖<br><br>

  <strong>🌊 让水文建模变得更智能</strong>
</div>