

https://github.com/user-attachments/assets/7cc17ea2-b83d-4f17-88fd-a2bce1f9d98c

# HydroAgent：LLM 驱动的水文模型率定智能体

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![HydroModel](https://img.shields.io/badge/hydromodel-0.3+-orange.svg)](https://github.com/OuyangWenyu/hydromodel)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**一句自然语言，完成从数据验证到模型评估的完整水文率定流程**

</div>

---

## 演示视频

<div align="center">



https://github.com/user-attachments/assets/acdff374-2e64-4798-bf99-63a456a1135d



<sub><i>演示视频（约 50 秒）</i></sub>

<!-- 上传演示视频步骤（在 GitHub 网页执行，无需修改本地仓库）：
     1. 仓库页 → 点 README 右上角铅笔图标进入编辑
     2. 删除上方 <img> 标签（保留 <div> 和 <sub>）
     3. 把本地 docs/media/hydroagent_demo.mp4 拖入编辑框
     4. 等待上传，GitHub 自动插入形如 https://github.com/user-attachments/assets/<uuid> 的链接
     5. 提交保存，README 即在原位置显示内联视频播放器
-->

</div>

---

## 项目简介

HydroAgent 是一个基于大语言模型（LLM）Agentic Loop 的水文模型率定系统。用户只需用自然语言描述任务，Agent 自主决定调用哪些工具、以何种顺序执行，最终输出率定参数、评估指标和分析报告。

系统支持 GR4J、XAJ 等概念性水文模型，使用 CAMELS-US 数据集，率定算法包括传统 SCE-UA/GA 和 LLM 智能率定两种模式。

---

## 系统架构

HydroAgent 采用**五层架构**，每层职责明确：

```
大脑 (Brain)         agent.py            LLM 推理与工具调度（ReAct Loop）
小脑 (Cerebellum)    skills/*/skill.md   Skill 工作流说明书，注入 system prompt
脊椎 (Spine)         adapters/           PackageAdapter，双向翻译任务意图与包调用
神经末梢 (Nerve)     tools/*.py          工具路由函数，薄包装
肌肉 (Muscle)        hydromodel pkg      数值计算：SCE-UA 优化、GR4J/XAJ 模拟
```

**System Prompt 七段式动态拼装**（每次 `agent.run()` 时按需组装）：

| 段 | 来源 | 内容 |
|----|------|------|
| §1 | `skills/system.md` | 身份与行为原则 |
| §1.5 | `policy/*.md` | 行为约束（何时停止、何时询问）|
| §1.7 | `skills/expert_hydrologist/skill.md` | 水文学家认知框架（始终注入）|
| §2 | `skill_registry.py` | 可用 Skill 索引与读取路径 |
| §3 | `adapters/` | PackageAdapter 能力文档 |
| §4 | `knowledge/*.md` | 领域知识（参数含义、故障诊断）|
| §5 | `basin_profiles/` + `MEMORY.md` | 流域历史档案与跨会话记忆 |

---

## 快速开始

### 安装

```bash
git clone https://github.com/your-org/HydroAgent.git
cd HydroAgent

python -m venv .venv

# Windows
.venv\Scripts\python.exe -m pip install -r requirements.txt

# Linux / macOS
.venv/bin/python -m pip install -r requirements.txt
```

### 配置

```bash
cp configs/example_private.py configs/private.py
```

编辑 `configs/private.py`，填写以下必填项：

```python
OPENAI_API_KEY  = "sk-your-api-key"
OPENAI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"  # 或 DeepSeek / OpenAI 端点
DATASET_DIR     = r"/path/to/CAMELS_US_parent"   # CAMELS_US/ 的父目录
RESULT_DIR      = r"/path/to/results"
```

支持任何 OpenAI 兼容接口（Qwen、DeepSeek、OpenAI、本地 Ollama）。

### 运行

HydroAgent 有两种面向用户的交互模式，以及一种面向开发者的脚本模式：

**终端交互模式**（精简输出，适合日常使用）：

```bash
python -m hydroagent                                          # 进入交互 REPL
python -m hydroagent "率定 GR4J 模型，流域 12025000"          # 单次查询后退出
python -m hydroagent -w results/my_experiment                 # 指定工作目录
```

**Web 前端模式**（浏览器界面，FastAPI + WebSocket）：

```bash
python -m hydroagent --server           # 默认 http://localhost:7860
python -m hydroagent --server --port 8080
```

**开发者脚本模式**（论文实验 / 系统测试）：

直接在 Python 脚本中实例化 `HydroAgent`，完整记录工具调用序列和中间结果：

```python
from hydroagent.agent import HydroAgent
from hydroagent.interface.ui import ConsoleUI

agent = HydroAgent(workspace=Path("results/exp1"), ui=ConsoleUI(mode="dev"))
agent.run("率定 GR4J 模型，流域 12025000，SCE-UA 算法")
```

论文实验脚本均采用此模式，详见 `experiment/` 目录。

---

## 主要功能

### 标准率定

```
用户> 率定 GR4J 模型，流域 12025000

Agent:
  [工具] validate_basin(["12025000"])        -> 数据完整
  [工具] calibrate_model("gr4j", "SCE_UA")  -> train NSE=0.783
  [工具] evaluate_model(period="test")      -> test  NSE=0.747

  流域 12025000 的 GR4J 率定完成。
  最优参数：x1=1180.6 mm, x2=-3.94, x3=36.9 mm, x4=1.22 days
  训练期 NSE=0.783，测试期 NSE=0.747，结果已保存至 results/gr4j_12025000/
```

### LLM 智能率定

LLM 不直接提议参数值，而是分析参数是否触边界，动态调整搜索范围，配合 SCE-UA 迭代优化：

```
Round 1: 默认范围 -> SCE-UA -> NSE=0.65, x1=1998（触上界 2000）
         LLM 诊断："x1 持续触上界，说明流域蓄水容量被低估，建议扩展至 [1, 3000]"
Round 2: 新范围  -> SCE-UA -> NSE=0.74，无触界参数
         LLM 诊断："NSE 达标且参数未触界，收敛，结束"
```

### 跨会话记忆

每次率定成功后自动保存流域档案（`basin_profiles/<basin_id>.json`）。下次对同一流域发起任务时，历史档案注入 LLM 上下文，支持先验初始化和对比分析。

### 认知框架（Expert Hydrologist Skill）

`skills/expert_hydrologist/skill.md` 是一个始终注入的认知型 Skill，编码了资深水文学家的思维模式：三种心智模型（参数即假设、先分类再搜索、误差三层剥洋葱）、五条决策启发式和四个诚实边界。

---

## 项目结构

```
HydroAgent/
├── hydroagent/
│   ├── agent.py                  # Agentic Loop 核心（ReAct 模式）
│   ├── llm.py                    # LLM 客户端（Function Calling）
│   ├── memory.py                 # 跨会话记忆（会话日志 + MEMORY.md + 流域档案）
│   ├── skill_registry.py         # Skill 自动扫描、关键词匹配、认知 Skill 注入
│   ├── config.py                 # 配置加载
│   ├── adapters/                 # PackageAdapter 插件层
│   │   ├── base.py               # PackageAdapter 基类
│   │   ├── hydromodel/           # hydromodel 适配器（GR4J / XAJ / HBV 等）
│   │   └── hydrodatasource/      # 数据源适配器（CAMELS-US）
│   ├── interface/
│   │   ├── cli.py                # CLI 入口 + 交互 REPL
│   │   ├── ui.py                 # Rich 终端 UI（user / dev 模式）
│   │   └── server.py             # FastAPI Web 服务
│   ├── tools/                    # 工具集（自动发现注册）
│   │   ├── validate.py           # validate_basin
│   │   ├── simulate.py           # run_simulation
│   │   ├── search_memory.py      # search_memory
│   │   ├── task_tools.py         # 批量任务管理
│   │   └── create_skill.py       # 动态生成新 Skill（元工具）
│   ├── skills/                   # Skill 包（工作流说明书 + 工具实现）
│   │   ├── calibration/          # 标准率定（SCE-UA / GA / scipy）
│   │   ├── llm_calibration/      # LLM 智能率定
│   │   ├── evaluation/           # 模型评估
│   │   ├── batch_calibration/    # 批量率定
│   │   ├── model_comparison/     # 多模型对比
│   │   ├── code_analysis/        # 代码生成与执行
│   │   ├── visualization/        # 可视化
│   │   └── expert_hydrologist/   # 水文学家认知框架（始终注入）
│   ├── policy/                   # 行为约束层（agent_behavior / calibration_policy 等）
│   ├── knowledge/                # 结构化领域知识
│   │   ├── model_parameters.md   # 参数物理含义与边界
│   │   ├── failure_modes.md      # 水文故障分类与诊断
│   │   ├── calibration_guide.md  # 率定经验
│   │   └── datasets.md           # 数据集说明
│   └── utils/
│       ├── context_utils.py      # Token 估算与上下文截断
│       ├── task_state.py         # 批量任务状态持久化
│       └── basin_validator.py    # 流域数据验证
├── configs/
│   ├── example_private.py        # 配置模板（提交到仓库）
│   └── private.py                # 实际配置（gitignore）
├── experiment/                   # 论文实验脚本
│   ├── exp1_standard_calibration.py
│   ├── exp2_llm_calibration.py
│   ├── exp3_capability_breadth.py
│   └── exp4_knowledge_ablation.py
├── results/paper/                # 实验结果
└── plot/                         # 论文配图脚本与输出
```

---

## 复现论文实验

所有实验结果保存在 `results/paper/`，配图脚本在 `plot/`。

```bash
# 运行实验（各约 2-4 小时）
python experiment/exp1_standard_calibration.py   # Exp1：标准率定基线
python experiment/exp2_llm_calibration.py        # Exp2：LLM 率定三路对比
python experiment/exp3_capability_breadth.py     # Exp3：Agent 能力广度
python experiment/exp4_knowledge_ablation.py     # Exp4：知识层消融

# 生成论文配图
python plot/exp1_figures.py
python plot/exp2_figures.py
python plot/exp3_figures.py
python plot/exp4_figures.py
```

详见 `experiment/README.md` 和 `plot/README.md`。

---

## 技术依赖

| 类别 | 组件 |
|------|------|
| LLM | 任意 OpenAI 兼容接口（Qwen / DeepSeek / GPT-4o / 本地 Ollama）|
| 水文建模 | [hydromodel](https://github.com/OuyangWenyu/hydromodel)（GR4J / XAJ / SACSMA）|
| 数据集 | CAMELS-US（671 流域，[aquaFetch](https://github.com/AtrCheema/aquaFetch) 下载）|
| 终端 UI | [Rich](https://github.com/Textualize/rich) |
| Web 服务 | FastAPI + WebSocket |
| Python | 3.11+ |

---

## 参考文献

> Zhu, S. et al. (2026). Large Language Models as Virtual Hydrologists. *Geophysical Research Letters*.

HydroAgent 与 Zhu et al. 方法的核心区别：LLM 调整参数**搜索范围**（而非直接提议参数值），配合 SCE-UA 全局优化，LLM 调用次数减少约 100 倍，同时保持等价的率定精度。
