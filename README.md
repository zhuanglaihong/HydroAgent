# HydroClaw: LLM 驱动的水文模型率定智能体

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg?style=for-the-badge&logo=python)](https://python.org)
[![HydroModel](https://img.shields.io/badge/HydroModel-v0.3+-orange.svg?style=for-the-badge)](https://github.com/OuyangWenyu/hydromodel)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)

**让 LLM 做决策，代码只做执行**

[快速开始](#-快速开始) · [系统架构](#-系统架构) · [使用示例](#-使用示例) · [项目结构](#-项目结构)

</div>

---

## 项目概览

HydroClaw 是一个 LLM 驱动的水文模型率定智能体。与传统多 Agent 系统不同，HydroClaw 采用**单一 Agentic Loop** 架构——LLM 自主决定调用哪个工具、何时结束，代码只负责执行。

由前身 HydroAgent（27,000 行、5 个硬编码 Agent、15 状态状态机）重构而来，HydroClaw 用 **~2,400 行 Python + ~200 行 Markdown** 实现了同等甚至更强的功能，代码量减少 **91%**。

### 核心理念

| 传统 Multi-Agent 系统 | HydroClaw |
|---|---|
| 5 个 Agent + 状态机编排 | **1 个 Agentic Loop** |
| if-else 路由决策 | **LLM 自主推理** |
| 960 行 Python 做工具选择 | **30 行 Markdown Skill** 引导 |
| 27,000 行代码 | **~2,600 行** |

### 主要特性

- **自然语言交互**：中英文对话式操作，无需手动编写配置
- **双模式率定**：传统优化算法（SCE-UA/GA/scipy）+ LLM 智能率定（Zhu et al. 2026）
- **自动工具发现**：函数签名自动生成 OpenAI Function Calling Schema
- **Skill 系统**：Markdown 文件引导 LLM 工作流，无需硬编码逻辑
- **双模式 LLM**：原生 Function Calling + Prompt 降级（兼容所有模型）
- **会话记忆**：JSONL 会话记录 + MEMORY.md 跨会话知识积累

---

## 快速开始

### 环境要求

- Python >= 3.11
- [hydromodel](https://github.com/OuyangWenyu/hydromodel) 已安装
- CAMELS-US 数据集（通过 hydrodataset 自动管理）

### 安装

```bash
git clone https://github.com/your-org/HydroAgent.git
cd HydroAgent

pip install uv
uv sync

# 激活虚拟环境
.venv\Scripts\activate     # Windows
source .venv/bin/activate   # Linux/macOS
```

### 配置

复制模板并填入你的 API Key 和路径：

```bash
cp configs/example_definitions_private.py configs/definitions_private.py
```

编辑 `configs/definitions_private.py`：

```python
PROJECT_DIR = r"D:\your\path\to\HydroAgent"
DATASET_DIR = r"D:\your\path\to\camels_data"
RESULT_DIR = r"D:\your\path\to\results"

OPENAI_API_KEY = "sk-your-api-key"
OPENAI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
```

### 运行

```bash
# 交互模式
python -m hydroclaw

# 单次查询
python -m hydroclaw "率定GR4J模型，流域01013500，SCE-UA算法，500轮迭代"

# 详细日志
python -m hydroclaw -v

# 指定工作目录
python -m hydroclaw -w results/my_experiment
```

---

## 系统架构

### Agentic Loop

```
User Query
    │
    ▼
┌──────────────────────────────────────────────┐
│              Agentic Loop (核心)              │
│                                              │
│   [System Prompt + Skill + Memory + Tools]   │
│       ↓                                      │
│   LLM 推理 → 决定调用哪个 Tool               │
│       ↓                                      │
│   执行 Tool → 结果返回 LLM                   │
│       ↓                                      │
│   LLM 继续推理 → 再调用 or 生成最终回答       │
│       ↓                                      │
│   循环直到 LLM 输出纯文本（完成）             │
└──────────────────────────────────────────────┘
    │
    ├── validate_basin     流域数据验证
    ├── calibrate_model    传统算法率定
    ├── evaluate_model     模型评估
    ├── simulate           模型模拟
    ├── visualize          可视化
    ├── llm_calibrate      LLM 智能率定 ★
    ├── generate_code      代码生成
    └── run_code           代码执行
         │
    ┌────▼────┐
    │hydromodel│  (执行后端)
    └─────────┘
```

**没有状态机、没有 if-else 路由、没有 Agent 间传递。** LLM 看到工具描述和 Skill 指引后，自然地走完整个流程。

### 双模式率定

**模式 1：传统算法率定**

LLM 调用 `calibrate_model` → hydromodel 执行 SCE-UA/GA/scipy → 返回最优参数和指标

**模式 2：LLM 智能率定**（参考 Zhu et al. 2026, GRL）

LLM 作为"虚拟水文学家"，理解参数物理意义，闭环迭代建议参数：

```
┌→ LLM 推荐参数 → run_simulation → 计算 NSE/RMSE ─┐
└────────── 反馈指标给 LLM，继续调整 ←─────────────┘
               重复直到收敛
```

优势：收敛更快（~200 次 vs SCE-UA ~1200 次），参数更具物理可解释性。

### Skill 系统

Skill 是给 LLM 看的自然语言工作流指引，替代传统的 if-else 编排代码：

| Skill 文件 | 触发关键词 | 用途 |
|---|---|---|
| `calibration.md` | 率定、calibrate | 标准率定流程 |
| `llm_calibration.md` | AI率定、智能率定 | LLM 闭环率定 |
| `iterative.md` | 迭代、边界 | 迭代优化 + 边界检测 |
| `comparison.md` | 对比、比较 | 多模型/多算法对比 |
| `batch.md` | 批量、多流域 | 批量处理 + 稳定性分析 |
| `analysis.md` | 分析、FDC、代码 | 自定义分析 + 代码生成 |

### 双模式 LLM 客户端

```
支持 Function Calling 的模型 (Qwen/GPT/DeepSeek)
  → 原生 Function Calling：结构化工具调用

不支持的模型 (Ollama 等)
  → Prompt 降级：工具描述注入 System Prompt，LLM 输出 JSON
```

自动检测模型能力，无需手动配置。

---

## 使用示例

### 标准率定

```
You> 率定GR4J模型，流域12025000，SCE-UA算法，500轮迭代

  >> Calling: validate_basin({"basin_ids": ["12025000"]})
  << validate_basin: valid=["12025000"]
  >> Calling: calibrate_model({"basin_ids": ["12025000"], "model_name": "gr4j", ...})
  << calibrate_model: {"NSE": 0.748, "RMSE": 1.23, ...}
  >> Calling: evaluate_model({"calibration_dir": "results/gr4j_SCE_UA_12025000"})
  << evaluate_model: {"NSE": 0.712, ...}
  >> Calling: visualize({"calibration_dir": "results/gr4j_SCE_UA_12025000"})
  << visualize: 2 plots generated

  ── 最终报告 ──
  流域 12025000 的 GR4J 模型率定结果：
  - 训练期 NSE = 0.748（良好）
  - 测试期 NSE = 0.712（良好）
  - 最优参数：x1=350.2, x2=0.23, x3=90.5, x4=1.7
  ...
```

### 多模型对比

```
You> 用GR4J和XAJ分别率定流域01013500，对比性能
```

LLM 读取 `comparison.md` Skill 后自动执行：验证 → GR4J 率定 → GR4J 评估 → XAJ 率定 → XAJ 评估 → 可视化 → 生成对比报告。

### LLM 智能率定

```
You> 用AI智能率定GR4J模型，流域01013500
```

LLM 作为虚拟水文专家，每轮分析 NSE/RMSE，智能调整参数直到收敛。

### 自定义分析

```
You> 率定完成后，帮我计算流域的径流系数，并画FDC曲线
```

LLM 调用 `generate_code` 生成 Python 分析脚本，再用 `run_code` 执行。

---

## 项目结构

```
HydroAgent/
├── hydroclaw/                    # 核心包 (~2,400 行)
│   ├── __init__.py               # 包入口
│   ├── agent.py                  # Agentic Loop 核心
│   ├── llm.py                    # LLM 客户端 (Function Calling + Prompt 降级)
│   ├── config.py                 # 配置加载 + hydromodel 配置构建
│   ├── memory.py                 # 会话记忆 (JSONL + MEMORY.md)
│   ├── cli.py                    # CLI 入口
│   ├── __main__.py               # python -m hydroclaw
│   ├── tools/                    # 8 个工具函数
│   │   ├── __init__.py           # 自动发现 + Schema 生成
│   │   ├── validate.py           # 流域数据验证
│   │   ├── calibrate.py          # 传统算法率定
│   │   ├── evaluate.py           # 模型评估
│   │   ├── simulate.py           # 模型模拟
│   │   ├── visualize.py          # 可视化
│   │   ├── llm_calibrate.py      # LLM 闭环率定 ★
│   │   ├── generate_code.py      # 代码生成
│   │   └── run_code.py           # 代码执行
│   ├── skills/                   # Markdown 工作流指引 (~200 行)
│   │   ├── system.md             # 系统人设
│   │   ├── calibration.md        # 标准率定
│   │   ├── llm_calibration.md    # LLM 智能率定
│   │   ├── iterative.md          # 迭代优化
│   │   ├── comparison.md         # 多模型对比
│   │   ├── batch.md              # 批量处理
│   │   └── analysis.md           # 自定义分析
│   └── utils/                    # 工具函数
│       ├── basin_validator.py    # 流域 ID 验证
│       └── result_parser.py      # 结果解析
├── configs/                      # 配置文件
│   ├── definitions_private.py    # 私有配置 (API Key、路径)
│   ├── definitions.py            # 默认配置
│   ├── example_definitions_private.py  # 配置模板
│   └── config.py                 # 全局参数参考
├── sessions/                     # 会话记录 (JSONL)
├── logs/                         # 运行日志
├── results/                      # 率定结果
├── MEMORY.md                     # Agent 跨会话知识 (自动维护)
└── README.md
```

---

## 支持范围

### 水文模型

GR4J · GR5J · GR6J · XAJ（通过 hydromodel 扩展更多）

### 率定算法

| 算法 | 类型 | 关键参数 |
|---|---|---|
| SCE-UA | 全局优化 | rep（迭代数）, ngs（复合体数） |
| GA | 遗传算法 | pop_size, n_generations |
| scipy | 梯度优化 | method (SLSQP, L-BFGS-B) |
| LLM-as-Calibrator | AI 率定 | max_iterations, nse_target |

### 性能指标

NSE · RMSE · KGE · PBIAS · R²

### 评估标准

| NSE 范围 | 评级 |
|---|---|
| >= 0.75 | 优秀 (Excellent) |
| >= 0.65 | 良好 (Good) |
| >= 0.50 | 一般 (Fair) |
| < 0.50 | 较差 (Poor) |

---

## 技术栈

| 类别 | 组件 |
|---|---|
| **LLM** | DeepSeek / Qwen / GPT（OpenAI 兼容接口） |
| **水文建模** | hydromodel, hydrodataset, spotpy |
| **数据处理** | xarray, NetCDF4, pandas |
| **可视化** | matplotlib |
| **数据集** | CAMELS-US（671 个流域，35+ 数据集支持） |

---

## 学术参考

HydroClaw 的 LLM 智能率定模式基于以下研究：

> Zhu, S. et al. (2026). Large Language Models as Virtual Hydrologists: Closed-Loop Parameter Calibration. *Geophysical Research Letters*. DOI: 10.1029/2025GL120043

该研究证明 LLM（DeepSeek-R1）作为"虚拟水文学家"可在 200 次迭代内达到近最优收敛，优于 SCE-UA（>1200 次），且参数更具物理可解释性。

---

## 相关项目

- [hydromodel](https://github.com/OuyangWenyu/hydromodel) — 核心水文模型库
- [hydrodataset](https://github.com/OuyangWenyu/hydrodataset) — CAMELS 数据管理
- [CAMELS](https://ral.ucar.edu/solutions/products/camels) — 流域数据集

---

<div align="center">

**HydroClaw — 用最少的代码，释放 LLM 在水文建模中的全部潜力**

</div>
