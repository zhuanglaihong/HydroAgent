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

### 水文模型

| 模型名称 | 说明          |
|---------|---------------|
| GR1Y    | GR年尺度模型   |
| GR2M    | GR月尺度模型   |
| GR4J    | GR日尺度模型   |
| GR5J    | GR日尺度模型   |
| GR6J    | GR日尺度模型   |
| XAJ     | 新安江模型     |

## 🏗️ 系统架构


## 🚀 核心功能

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


## 📄 许可证

本项目采用 MIT 许可证，详见 LICENSE 文件。

## 📞 联系方式

- **开发者**: zhuanglaihong
- **项目地址**: [https://gitcode.com/dlut-water/langchain-query.git]
- **问题反馈**: [https://gitcode.com/dlut-water/langchain-query/issues]

---

**版本**: v1.0.0  
**最后更新**: 2025年7月28日