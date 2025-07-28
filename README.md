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
# ollama list 

# 5. 模型下载（推荐支持tool调用的模型）
ollama pull granite3-dense:8b

# 模型删除
# ollama rm <model name>
```

## 🚀 使用说明

### 智能体主界面 (script/Agent.py)

**🎯 一键启动的水文模型智能体系统**：

- 🤖 **自然语言交互**: 通过中文对话进行水文建模
- ⚡ **自动率定**: 一键完成模型率定的完整流程
- 🔧 **工具集成**: 智能调用专业水文模型工具
- 📊 **结果分析**: 自动分析和解释率定结果

**使用方法**:

```bash
# 交互模式
python script/Agent.py

# 自动率定
python script/Agent.py --auto gr4j data/camels_11532500

# 单次问答
python script/Agent.py --message "请获取 gr4j 模型的参数信息"
```


## 🏗️ 系统架构

HydroAgent采用模块化设计，各个模块职责明确，协同工作形成完整的水文模型智能体系统。

```
HydroAgent系统
├── script/                  # 用户交互层
│   └── Agent.py            # 主交互接口，集成所有功能
│
├── workflow/               # 工作流编排层
│   ├── IntentProcessor     # 意图理解
│   ├── QueryExpander       # 查询扩展
│   ├── KnowledgeRetriever  # 知识检索
│   ├── ContextBuilder     # 上下文构建
│   └── WorkflowGenerator  # 工作流生成
│
├── tool/                   # 工具执行层
│   ├── langchain_tool     # LangChain工具集成
│   └── run_hydromodel     # 水文模型执行工具
│
├── RAG/                    # 知识库层
│   ├── document_loader    # 文档加载
│   ├── vector_store      # 向量存储
│   └── retriever         # 知识检索
│
├── hydromodel/            # 模型层
│   ├── models/           # 水文模型集合
│   └── trainers/         # 模型训练器
│
└── test/                  # 测试层
    └── 各模块测试文件
```

### 系统工作流程

1. **用户交互**: 
   - 通过`Agent.py`接收用户自然语言输入
   - 支持交互式对话、自动率定和单次问答三种模式

2. **工作流编排**:
   - 意图处理器解析用户需求
   - 查询扩展器丰富查询内容
   - 知识检索器从RAG系统获取相关知识
   - 上下文构建器组织提示信息
   - 工作流生成器制定执行计划

3. **知识支持**:
   - RAG系统管理本地文档知识库
   - 支持向量检索和相似度匹配
   - 为工作流提供专业知识支持

4. **工具执行**:
   - 工具层接收工作流指令
   - 调用相应的水文模型和功能
   - 执行具体的计算和分析任务

5. **模型支持**:
   - 提供多种水文模型选择
   - 支持模型参数率定
   - 实现模型评估和应用

### 核心特点

- **模块化设计**: 各模块独立且职责明确
- **智能工作流**: 自动规划和执行任务流程
- **知识驱动**: 集成RAG系统提供专业知识支持
- **工具丰富**: 支持多种水文模型和分析工具
- **可扩展性**: 易于添加新的模型和功能

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

- [x] 水文模型工具集成
- [x] 本地Ollama支持
- [x] 基础测试框架


### 进行中功能 🚧

- [ ] RAG知识库系统
- [ ] Agent任务规划模块
- [ ] 自主思考能力
- [ ] 工作流执行测试
- [ ] 用户前端交互界面
- [ ] 修改hydromodel包,去掉不必要的包


## 📄 许可证

本项目采用 MIT 许可证，详见 LICENSE 文件。

## 📞 联系方式

- **开发者**: zhuanglaihong
- **项目地址**: [https://gitcode.com/dlut-water/langchain-query.git]
- **问题反馈**: [https://gitcode.com/dlut-water/langchain-query/issues]

---

**版本**: v1.0.0  
**最后更新**: 2025年7月28日