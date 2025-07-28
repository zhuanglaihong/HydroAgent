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

# 首选模型
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
