# 🌊 HydroAgent - 智能水文建模助手

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![HydroModel](https://img.shields.io/badge/hydromodel-latest-green.svg)](https://github.com/OuyangWenyu/hydromodel)

基于多智能体协作的智能水文建模系统。通过自然语言理解、自动配置生成、模型执行和结果分析，实现从用户意图到水文模拟的端到端自动化。

---

## 🎯 核心特性

### 多智能体协作

```
用户查询（中文/英文）
      ↓
IntentAgent（意图识别）→ TaskPlanner（任务规划）
      ↓
InterpreterAgent（配置生成）
      ↓
RunnerAgent（模型执行）
      ↓
DeveloperAgent（结果分析 + 代码生成）
      ↓
分析报告 + 结果文件
```

### 主要功能

- 🎤 **自然语言交互** - 支持中英文对话式任务描述
- 🔄 **自动化流程** - 从意图识别到结果分析全自动化
- 🧠 **智能决策** - 战略层（Intent）→ 战术层（TaskPlanner）→ 配置层（Interpreter）
- 🔧 **自适应优化** - 参数边界检测与自动调整（实验3）
- 💻 **代码生成** - 超出 hydromodel 功能时自动生成 Python 脚本（实验4）
- 🔌 **多后端支持** - Ollama 本地模型 / 通义千问 API / OpenAI API
- 📊 **丰富的模型与算法** - GR 系列、XAJ 等模型 + SCE-UA、DE、PSO、GA 等算法

---

## 📦 快速开始

### 1. 安装

```bash
# 克隆仓库
git clone https://github.com/your-repo/HydroAgent.git
cd HydroAgent

# 安装依赖
pip install uv
uv sync

# 激活环境
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS
```

### 2. 配置

复制 `configs/example_definitions_private.py` 为 `configs/definitions_private.py`：

```python
# API 配置（推荐）
OPENAI_API_KEY = "sk-your-qwen-api-key"
OPENAI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 本地路径
PROJECT_DIR = r"D:\your\path\to\HydroAgent"
DATASET_DIR = r"D:\your\path\to\data"
```

或使用 Ollama 本地模型：
```bash
ollama pull qwen3:8b
ollama pull deepseek-coder:6.7b  # 用于代码生成
```

### 3. 运行

```bash
# 交互模式
python scripts/run_developer_agent_pipeline.py --backend api

# 单次查询
python scripts/run_developer_agent_pipeline.py --backend api "率定GR4J模型，流域01013500"
```

**示例对话**：
```
> 率定GR4J模型，流域01013500，使用SCE-UA算法，迭代500轮

✅ Intent分析: CALIBRATION | 模型: gr4j | 算法: SCE_UA | rep=500
⚙️  Config生成完成
🚀 执行中... SCE-UA Progress: 100%|███| 500/500
✅ 测试期 NSE: 0.65
📊 质量评估: 良好（建议延长训练期或调整参数范围）
```

---

## 📂 项目结构

```
HydroAgent/
├── hydroagent/          # 核心包
│   ├── core/            # 基础类（BaseAgent, LLM接口）
│   ├── agents/          # 5个智能体实现
│   ├── utils/           # 工具函数
│   └── resources/       # 提示词模板和Schema
├── configs/             # 配置文件
│   ├── config.py        # 全局参数
│   ├── definitions.py   # 公共配置
│   └── definitions_private.py  # 私有配置（需创建）
├── scripts/             # 入口脚本
├── experiment/          # 8个核心实验（1A-1C, 2A-2C, 3-4）
│   ├── base_experiment.py   # 实验基类
│   └── exp_*.py         # 独立实验脚本
├── test/                # 测试文件
├── docs/                # 详细文档
│   ├── ARCHITECTURE_FINAL.md   # 完整架构文档
│   ├── TESTING_GUIDE.md        # 测试指南
│   ├── QUICKSTART.md           # 快速上手
│   └── UNIFIED_INTERFACE.md    # 统一接口设计
├── logs/                # 日志输出
└── results/             # 结果输出
```

---

## 🧪 核心实验

HydroAgent 提供 8 个验证系统功能的实验：

```bash
# 基础功能验证（推荐Mock模式）
python experiment/exp_1a_standard.py --backend api --mock
python experiment/exp_1b_info_completion.py --backend api --mock
python experiment/exp_1c_error_handling.py --backend api --mock

# 稳定性与批量处理
python experiment/exp_2a_repeated_calibration.py --backend api --mock
python experiment/exp_2b_multi_basin.py --backend api --mock
python experiment/exp_2c_multi_algorithm.py --backend api --mock

# 高级功能
python experiment/exp_3_iterative_optimization.py --backend api --mock
python experiment/exp_4_extended_analysis.py --backend api --mock
```

### 实验分组

**实验1：基础功能验证**
- **1A** - 标准流程：完整信息率定
- **1B** - 信息补全：自动填充缺失参数
- **1C** - 错误处理：异常情况鲁棒性

**实验2：稳定性与批量**
- **2A** - 重复率定：单流域多次执行（20次）
- **2B** - 多流域：批量处理10个流域
- **2C** - 多算法：对比 SCE-UA/PSO/GA

**实验3-4：高级功能**
- **3** - 自适应优化：参数边界检测与动态调整
- **4** - 智能代码生成：双LLM模式（径流系数、FDC）

详见 `experiment/README.md`

---

## 🔧 高级功能

### 自适应迭代优化（实验3）

当参数收敛到边界时，自动调整搜索范围：

```bash
python experiment/exp_3_iterative_optimization.py --backend api
```

**查询**: "率定流域01013500，如果参数收敛到边界，自动调整范围重新率定"

**执行流程**:
```
Iter 0: 默认范围 → NSE=0.42
Iter 1: 缩小至60% → NSE=0.48 ✅
Iter 2: 缩小至42% → NSE=0.51 ✅ 达标停止
```

### 智能代码生成（实验4）

超出 hydromodel 功能时，自动生成 Python 脚本：

```bash
python experiment/exp_4_extended_analysis.py --backend api \
  --model qwen-turbo --code-model qwen-coder-turbo
```

**查询**: "率定完成后，计算径流系数并画FDC曲线"

**双LLM架构**:
- 通用模型（qwen-turbo）: 意图理解、任务规划
- 代码模型（qwen-coder-turbo）: 生成完整脚本

**输出**: `runoff_coefficient_analysis.py`, `plot_fdc.py`, 结果文件

---

## 📚 文档

| 文档 | 内容 |
|------|------|
| `docs/ARCHITECTURE_FINAL.md` | 完整系统架构、设计决策 |
| `docs/TESTING_GUIDE.md` | 测试策略、实验说明 |
| `docs/QUICKSTART.md` | 快速上手指南 |
| `docs/UNIFIED_INTERFACE.md` | Orchestrator统一接口 |
| `CLAUDE.md` | 开发规范、代码标准 |

---

## 🗺️ 版本状态

### ✅ 当前版本（v3.5）

- 5-Agent 协作架构（IntentAgent → TaskPlanner → InterpreterAgent → RunnerAgent → DeveloperAgent）
- 支持 8 个核心实验（基础验证 3 个、稳定性批量 3 个、高级功能 2 个）
- 双LLM模式（通用模型 + 代码专用模型）
- 参数边界检测与自动调整
- 智能代码生成（径流系数、FDC、自定义分析）

### 🚧 进行中

- RAG 知识库集成
- 可视化结果展示
- Checkpoint/Resume 系统（长任务中断恢复）

### 📅 计划中

- Web 界面（Gradio/Streamlit）
- 多流域并行处理
- 模型性能对比分析

---

## 🤝 开发与贡献

### 运行测试

```bash
python test/test_intent_agent.py --backend api
python test/test_developer_agent_pipeline.py
```

### 贡献规范

- 遵循 PEP 8
- 所有新文件添加标准文件头（见 `CLAUDE.md`）
- 测试文件包含日志配置
- Pull Request 前运行测试

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE)

---

## 🌟 相关项目

- [hydromodel](https://github.com/OuyangWenyu/hydromodel) - 水文模型核心库
- [hydrodataset](https://github.com/OuyangWenyu/hydrodataset) - CAMELS 数据管理
- [hydroutils](https://github.com/OuyangWenyu/hydroutils) - 水文工具函数

---

<div align="center">

**🌊 让水文建模更智能，让科研更高效 🌊**

[⬆ 返回顶部](#-hydroagent---智能水文建模助手)

</div>
