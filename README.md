# HydroClaw: LLM 驱动的水文模型率定智能体

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg?style=for-the-badge&logo=python)](https://python.org)
[![HydroModel](https://img.shields.io/badge/HydroModel-v0.3+-orange.svg?style=for-the-badge)](https://github.com/OuyangWenyu/hydromodel)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)

**让 LLM 做决策，代码只做执行**

[快速开始](#快速开始) · [系统架构](#系统架构) · [使用示例](#使用示例) · [详细文档](#详细文档)

</div>

---

## 项目概览

HydroClaw 是一个 LLM 驱动的水文模型率定智能体，采用**单一 Agentic Loop** 架构。LLM 自主决定调用哪个工具、何时结束，代码只负责执行。

由前身 HydroAgent（27,000 行、5 个硬编码 Agent、15 状态状态机）重构而来，HydroClaw 用约 3,000 行代码实现了同等甚至更强的功能。

### 核心特性

- **自然语言交互** — 中英文对话式操作，支持交互模式和单次查询
- **三层知识注入** — Skill 说明书 + 领域知识库 + 流域历史档案，按需注入 LLM 上下文
- **双模式率定** — 传统算法（SCE-UA/GA）+ LLM 智能率定（LLM 调整参数范围，SCE-UA 优化）
- **跨会话记忆** — 流域档案自动积累，下次率定同一流域时先验注入，越用越准
- **动态 Skill 扩展** — 运行时生成新 Skill，工具集可按需增长，无需修改任何注册代码

---

## 快速开始

### 安装

```bash
git clone https://github.com/your-org/HydroAgent.git
cd HydroAgent

pip install uv && uv sync

.venv\Scripts\activate      # Windows
source .venv/bin/activate   # Linux/macOS
```

### 配置

**首次运行前必须先填写 `configs/private.py`**，否则无法连接 LLM 和读取数据：

```bash
cp configs/example_private.py configs/private.py
```

编辑 `configs/private.py`，填入必填项：

```python
OPENAI_API_KEY  = "sk-your-api-key"                  # LLM API Key（必填）
OPENAI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DATASET_DIR     = r"D:\your\path\to\CAMELS_US"        # 数据集路径（必填）
RESULT_DIR      = r"D:\your\path\to\results"          # 结果输出目录（必填）
```

> 该文件已加入 `.gitignore`，不会提交到仓库。

在 `configs/model_config.py` 中调整算法参数（可选）：

```python
DEFAULT_OBJ_FUNC     = "NSE"    # 目标函数
DEFAULT_SCE_UA_PARAMS = {"rep": 1000, ...}
```

### 运行

```bash
python -m hydroclaw                    # 交互模式
python -m hydroclaw "率定GR4J，流域12025000"  # 单次查询
python -m hydroclaw -w results/exp1 -v       # 指定工作目录 + 详细日志
```

**交互模式斜杠命令**：

| 命令 | 说明 |
|------|------|
| `/tasks` | 显示当前批量任务列表和进度 |
| `/pause` | 请求暂停（Agent 在当前步骤完成后停下，任务进度自动保存） |
| `/resume` | 恢复上次未完成的批量任务，已完成任务自动跳过 |
| `/help` | 列出所有可用命令 |
| `/quit` | 安全退出（有未完成任务时提示确认） |

**Ctrl+C**：中断正在运行的任务（如率定进度条），返回输入提示符，可用 `/resume` 继续。

详见 [docs/getting-started.md](docs/getting-started.md) · [docs/usage.md](docs/usage.md)

---

## 系统架构

```
用户自然语言查询
      |
      v
+------------------------------------------+
|           Agentic Loop (agent.py)        |
|                                          |
|  System Prompt                           |
|    = system.md                           |
|    + 匹配的 Skill 工作流指引              |  <- 第一层：Skill 说明书
|    + 领域知识（参数物理含义）              |  <- 第二层：领域知识库
|    + 流域历史档案（上次率定结果）          |  <- 第三层：跨会话记忆
|                                          |
|  LLM 推理 -> 选择工具 -> 执行 -> 推理    |
|  循环直到 LLM 输出最终回答               |
+------------------------------------------+
      |
      v
+------------------------------------------+
|  Skills (工作流 + 工具实现)               |
|    calibrate_model   SCE-UA/GA 率定       |
|    evaluate_model    测试期评估            |
|    llm_calibrate     LLM 智能迭代率定 *   |
|    batch_calibrate   批量率定              |
|    compare_models    多模型对比            |
|    generate_code     代码生成             |
|    run_code          代码执行             |
|    visualize         可视化               |
|                                          |
|  Tools (独立工具)                         |
|    validate_basin    流域验证             |
|    run_simulation    模型模拟             |
|    create_skill      生成新 Skill *       |
+------------------------------------------+
      |
      v
  hydromodel (水文模型后端)
```

### LLM 智能率定

LLM 不直接调参数值，而是调**参数搜索范围**，配合 SCE-UA 做高效优化：

```
Round 1: 默认范围 -> SCE-UA 1000 轮 -> NSE=0.65, x1=1998 (触上界 2000)
                      LLM: "x1 触上界，扩展到 [1, 3000]"
Round 2: 新范围  -> SCE-UA 1000 轮 -> NSE=0.74, 无触界
                      LLM: "达标，结束"
```

LLM 只调用 2-3 次（诊断决策），每次搭配一轮完整 SCE-UA 优化（数值搜索）。

### 跨会话记忆

每次率定成功后自动保存流域档案：

```json
// workspace/basin_profiles/12025000.json
{
  "basin_id": "12025000",
  "records": [{
    "model": "gr4j", "algorithm": "SCE_UA",
    "train_nse": 0.783,
    "best_params": {"x1": 1180.6, "x2": -3.94, "x3": 36.9, "x4": 1.22}
  }]
}
```

下次对同一流域发起查询时，历史档案自动注入 LLM 上下文，可用于先验初始化和异常检测。

---

## 使用示例

### 标准率定

```
You> 率定GR4J模型，流域12025000，SCE-UA算法

  >> validate_basin(["12025000"])           valid
  >> calibrate_model("gr4j", "SCE_UA")  ->  train NSE=0.783
  >> evaluate_model(test_period=...)    ->  test  NSE=0.747

  流域 12025000 的 GR4J 模型率定完成：
  - 训练期 NSE=0.783，测试期 NSE=0.747（良好）
  - 最优参数：x1=1180.6mm, x2=-3.94, x3=36.9mm, x4=1.22days
  - 结果已保存至 results/gr4j_12025000/
```

### LLM 智能率定

```
You> 智能率定GR4J，流域06043500，目标NSE 0.75
```

LLM 自动执行多轮迭代，每轮分析参数边界并调整范围。

### 利用历史档案

```
You> 再次率定流域12025000，看看能不能比上次 NSE=0.783 更好
```

LLM 读取历史档案，以上次最优参数缩窄搜索范围，加速收敛。

### 动态创建 Skill

```
You> 帮我做参数敏感性分析，用 SALib 包

  >> create_skill("sensitivity_analysis", "使用 SALib 做 Sobol 敏感性分析")
     -> 生成 hydroclaw/skills/sensitivity_analysis/
     -> 工具已注册，立即可用
  >> sensitivity_analysis(...)
```

更多示例见 [docs/usage.md](docs/usage.md)

---

## 项目结构

```
HydroAgent/
├── hydroclaw/
│   ├── agent.py              # Agentic Loop 核心
│   ├── llm.py                # LLM 客户端（Function Calling + Prompt 降级）
│   ├── memory.py             # 三层记忆（会话/MEMORY.md/流域档案）
│   ├── config.py             # 配置加载 + hydromodel 配置构建
│   ├── skill_registry.py     # Skill 自动扫描与关键词匹配
│   ├── cli.py / ui.py        # CLI 入口 + Rich 终端 UI
│   ├── tools/                # 独立工具（validate, simulate, create_skill）
│   ├── skills/               # Skill 包（工作流指引 + 工具实现）
│   └── knowledge/            # 结构化领域知识（参数物理含义、率定经验）
├── configs/
│   ├── model_config.py       # 用户自定义参数（算法轮次、目标函数等）
│   └── private.py            # API Key、数据路径（gitignore）
├── scripts/                  # 论文实验脚本（exp1~exp6）
└── docs/                     # 项目文档
```

---

## 详细文档

| 文档 | 内容 |
|------|------|
| [getting-started.md](docs/getting-started.md) | 安装、配置、首次运行、FAQ |
| [usage.md](docs/usage.md) | 所有使用场景示例 |
| [architecture.md](docs/architecture.md) | Agentic Loop、三层知识注入、工具发现机制 |
| [skills.md](docs/skills.md) | Skill 工具 API 参考（calibrate、evaluate、llm_calibrate 等） |
| [tools.md](docs/tools.md) | 独立工具参考（validate、simulate、create_skill） |
| [memory.md](docs/memory.md) | 跨会话记忆、流域档案机制 |
| [llm-calibration.md](docs/llm-calibration.md) | LLM 智能率定原理与参数边界诊断 |
| [configuration.md](docs/configuration.md) | 配置层级、所有配置项详解 |
| [development.md](docs/development.md) | 项目结构、添加 Skill/工具、代码规范 |

---

## 技术栈

| 类别 | 组件 |
|------|------|
| LLM | DeepSeek / Qwen / GPT（OpenAI 兼容接口） |
| 水文建模 | [hydromodel](https://github.com/OuyangWenyu/hydromodel) |
| 数据集 | CAMELS-US（671 流域） |
| 终端 UI | [Rich](https://github.com/Textualize/rich) |
| 运行环境 | Python 3.11+，uv 包管理 |

---

## 学术参考

> Zhu, S. et al. (2026). Large Language Models as Virtual Hydrologists. *Geophysical Research Letters*. DOI: 10.1029/2025GL120043

HydroClaw 在此基础上的改进：LLM 调整参数**搜索范围**（而非直接提议参数值），配合 SCE-UA 全局优化，通常 2-3 轮收敛，LLM 调用次数减少约 100 倍。

---

<div align="center">

**HydroClaw — 用最少的代码，释放 LLM 在水文建模中的全部潜力**

</div>
