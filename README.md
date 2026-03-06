# HydroClaw: LLM 驱动的水文模型率定智能体

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg?style=for-the-badge&logo=python)](https://python.org)
[![HydroModel](https://img.shields.io/badge/HydroModel-v0.3+-orange.svg?style=for-the-badge)](https://github.com/OuyangWenyu/hydromodel)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)

**让 LLM 做决策，代码只做执行**

[快速开始](#-快速开始) · [系统架构](#-系统架构) · [使用示例](#-使用示例) · [详细文档](#-详细文档)

</div>

---

## 项目概览

HydroClaw 是一个 LLM 驱动的水文模型率定智能体。采用**单一 Agentic Loop** 架构——LLM 自主决定调用哪个工具、何时结束，代码只负责执行。

由前身 HydroAgent（27,000 行、5 个硬编码 Agent、15 状态状态机）重构而来，HydroClaw 用 **~2,600 行 Python + ~200 行 Markdown** 实现了同等甚至更强的功能。

### 核心特性

- **自然语言交互** — 中英文对话式操作，支持交互模式和单次查询
- **双模式率定** — 传统算法（SCE-UA/GA）+ LLM 智能率定（LLM 调整参数范围，SCE-UA 优化）
- **自动工具发现** — 函数签名自动生成 Tool Schema，新工具放入 `tools/` 即可用
- **LLM 自动创建工具** — 需要集成新包时，LLM 自动编写工具脚本并热加载，无需手写代码
- **Skill 引导** — Markdown 文件引导 LLM 工作流，替代硬编码 if-else 逻辑
- **会话记忆** — JSONL 会话记录 + MEMORY.md 跨会话知识积累

---

## 快速开始

### 安装

```bash
git clone https://github.com/your-org/HydroAgent.git
cd HydroAgent

pip install uv && uv sync

# 激活虚拟环境
.venv\Scripts\activate     # Windows
source .venv/bin/activate   # Linux/macOS
```

### 配置 API Key

```bash
cp configs/example_definitions_private.py configs/definitions_private.py
```

编辑 `configs/definitions_private.py`：

```python
OPENAI_API_KEY = "sk-your-api-key"
OPENAI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DATASET_DIR = r"D:\your\path\to\camels_data"
```

### 运行

```bash
# 交互模式（推荐）
python -m hydroclaw

# 单次查询
python -m hydroclaw "率定GR4J模型，流域12025000"

# 指定工作目录 + 详细日志
python -m hydroclaw -w results/exp1 -v
```

> 详见 [docs/getting-started.md](docs/getting-started.md)

---

## 系统架构

```
User ←→ 对话界面 (CLI)
           │
           ▼
    ┌─────────────────────────────────────────┐
    │          Agentic Loop (agent.py)         │
    │                                         │
    │  System Prompt + Skill + Memory + Query │
    │       ↓                                 │
    │  LLM 推理 → 选择工具 → 执行 → 返回结果  │
    │       ↓                                 │
    │  LLM 继续推理 → 再调用 or 最终回答       │
    └─────────────┬───────────────────────────┘
                  │
    ┌─────────────▼───────────────────────────┐
    │           9 个内置工具                    │
    │                                         │
    │  validate_basin    流域数据验证           │
    │  calibrate_model   SCE-UA/GA 率定        │
    │  evaluate_model    测试期评估             │
    │  run_simulation    模型模拟               │
    │  visualize         可视化                 │
    │  llm_calibrate     LLM 智能迭代率定  ★   │
    │  generate_code     代码生成               │
    │  run_code          代码执行               │
    │  create_tool       自动创建新工具    ★   │
    └─────────────┬───────────────────────────┘
                  │
           ┌──────▼──────┐
           │  hydromodel  │  水文模型后端
           └─────────────┘
```

### LLM 智能率定

LLM 不直接调参数值，而是调**参数范围**，让 SCE-UA 在范围内做快速优化：

```
Round 1: 默认范围 → SCE-UA 500轮 → NSE=0.65, x1=1998(触上界)
                                    ↓
         LLM 分析: "x1 触上界，扩展到 [1, 3000]"
                                    ↓
Round 2: 新范围 → SCE-UA 500轮 → NSE=0.74, 无触界
                                    ↓
         LLM: "达标，无需调整" → 结束
```

LLM 只调用 2-3 次，每次搭配一轮完整 SCE-UA 优化。

### 自动工具创建

当现有工具无法满足需求时，LLM 自动编写新的工具脚本：

```
用户: "帮我做参数敏感性分析"

HydroClaw → 发现没有敏感性分析工具
         → 调用 create_tool("sensitivity_analysis", "使用 SALib 做敏感性分析", "SALib")
         → LLM 生成 hydroclaw/tools/sensitivity_analysis.py
         → 热加载，工具立即可用
         → 调用 sensitivity_analysis(...) 完成任务
```

> 详见 [docs/architecture.md](docs/architecture.md)

---

## 使用示例

### 标准率定

```
You> 率定GR4J模型，流域12025000，SCE-UA算法

  >> validate_basin(["12025000"])  ✓
  >> calibrate_model("gr4j", "SCE_UA")  → NSE=0.748
  >> evaluate_model(...)  → 测试期 NSE=0.712
  >> visualize(...)  → 2 plots

  流域 12025000 的 GR4J 模型率定结果：
  - 训练期 NSE = 0.748（良好）
  - 测试期 NSE = 0.712（良好）
  - 最优参数：x1=350.2, x2=0.23, x3=90.5, x4=1.7
```

### 迭代优化（LLM 智能率定）

```
You> 智能率定GR4J模型，流域12025000，目标NSE 0.75
```

LLM 自动执行多轮 SCE-UA，每轮分析结果并调整参数范围，直到达标。

### 多模型对比

```
You> 用GR4J和XAJ分别率定流域12025000，对比性能
```

### 自定义分析 + 工具创建

```
You> 帮我做流域12025000的参数敏感性分析
```

如果没有现成工具，LLM 会自动创建并使用。

> 更多示例见 [docs/usage.md](docs/usage.md)

---

## 项目结构

```
HydroAgent/
├── hydroclaw/                    # 核心包
│   ├── agent.py                  # Agentic Loop 核心
│   ├── llm.py                    # LLM 客户端
│   ├── config.py                 # 配置 + hydromodel 配置构建
│   ├── memory.py                 # 会话记忆
│   ├── cli.py                    # CLI 入口
│   ├── tools/                    # 工具函数（自动发现）
│   │   ├── __init__.py           # 自动发现 + Schema 生成 + 热加载
│   │   ├── calibrate.py          # 传统算法率定
│   │   ├── llm_calibrate.py      # LLM 智能率定
│   │   ├── create_tool.py        # 元工具：自动创建新工具
│   │   └── ...                   # validate, evaluate, visualize, etc.
│   └── skills/                   # Markdown 工作流指引
│       ├── system.md             # 系统人设 + 核心能力
│       ├── calibration.md        # 标准率定
│       ├── iterative.md          # 迭代优化
│       └── ...                   # comparison, batch, analysis
├── docs/                         # 详细文档
├── configs/                      # 配置文件
├── results/                      # 率定结果
├── sessions/                     # 会话记录
└── logs/                         # 运行日志
```

---

## 详细文档

| 文档 | 内容 |
|------|------|
| [docs/getting-started.md](docs/getting-started.md) | 安装、配置、首次运行 |
| [docs/architecture.md](docs/architecture.md) | 核心架构、Agentic Loop、工具系统 |
| [docs/usage.md](docs/usage.md) | 完整使用指南、所有场景示例 |
| [docs/tools.md](docs/tools.md) | 工具 API 参考、自动发现机制、创建新工具 |
| [docs/llm-calibration.md](docs/llm-calibration.md) | LLM 智能率定原理与使用 |
| [docs/configuration.md](docs/configuration.md) | 配置系统详解 |
| [docs/development.md](docs/development.md) | 开发指南、添加工具、代码规范 |

---

## 技术栈

| 类别 | 组件 |
|---|---|
| **LLM** | DeepSeek / Qwen / GPT（OpenAI 兼容接口） |
| **水文建模** | [hydromodel](https://github.com/OuyangWenyu/hydromodel) |
| **数据集** | CAMELS-US（671 流域，通过 [hydrodataset](https://github.com/OuyangWenyu/hydrodataset) 管理） |
| **运行环境** | Python 3.11+，uv 包管理 |

---

## 学术参考

LLM 智能率定的思路受以下研究启发：

> Zhu, S. et al. (2026). Large Language Models as Virtual Hydrologists: Closed-Loop Parameter Calibration. *Geophysical Research Letters*. DOI: 10.1029/2025GL120043

HydroClaw 在此基础上改进：LLM 不直接调参数值（慢），而是调参数范围后让 SCE-UA 做优化（快），通常 2-3 轮即可收敛。

---

<div align="center">

**HydroClaw — 用最少的代码，释放 LLM 在水文建模中的全部潜力**

</div>
