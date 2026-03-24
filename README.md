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
- **通用包插件系统** — 任意本地包/单文件工具一行命令接入，CLI 和 Web API 统一管理
- **推理型模型感知** — 自动检测 DeepSeek-R1 / QwQ / o1 等推理模型，激活原生 thinking 参数

---

## 快速开始

### 安装

```bash
git clone https://github.com/your-org/HydroAgent.git
cd HydroAgent

python -m venv .venv

.venv\Scripts\python.exe -m pip install -r requirements.txt   # Windows
.venv/bin/python -m pip install -r requirements.txt           # Linux/macOS

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

#### 终端模式

```bash
python -m hydroclaw                    # 交互模式
python -m hydroclaw "率定GR4J，流域12025000"  # 单次查询
python -m hydroclaw --dev              # 开发者模式（显示完整工具日志）
python -m hydroclaw -w results/exp1    # 指定工作目录
```

**交互模式斜杠命令**：

| 命令 | 说明 |
|------|------|
| `/tasks` | 显示当前批量任务列表和进度 |
| `/pause` | 请求暂停（Agent 在当前步骤完成后停下，任务进度自动保存） |
| `/resume` | 恢复上次未完成的批量任务，已完成任务自动跳过 |
| `/plugin list` | 列出所有已注册插件（内置 + 外部） |
| `/plugin add <path>` | 注册本地目录包或 .py 文件 |
| `/plugin enable/disable <name>` | 启用/禁用插件（不删除注册条目） |
| `/plugin remove <name>` | 从注册表删除插件 |
| `/plugin reload` | 手动触发 reload_adapters() |
| `/help` | 列出所有可用命令 |
| `/quit` | 安全退出（有未完成任务时提示确认） |

**Ctrl+C**：中断正在运行的任务，可用 `/resume` 继续。

**CLI 参数**：

```bash
python -m hydroclaw --plugin-add D:/path/to/mypkg  # 注册插件后启动
```

#### Web 服务模式

```bash
python -m hydroclaw --server          # 启动 FastAPI Web 服务（默认端口 7860）
python -m hydroclaw --server --port 8080  # 自定义端口
```

浏览器将自动打开 `http://localhost:7860`，提供对话界面、工具调用可视化和数据集管理。

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

### 通用包插件系统

任意本地包或单 .py 文件可一行命令接入 Agent，无需修改 HydroClaw 核心代码：

```
# 本地目录包（未上传 pip）
python -m hydroclaw "帮我注册本地包 D:/project/myhydro"
> /plugin add D:/project/myhydro

# 单 .py 文件（函数自动注册为工具）
> /plugin add D:/scripts/fdc.py

# Web API
POST http://localhost:7860/api/plugins
{"path": "D:/project/myhydro"}
```

**接入约定（本地目录包）**：在包根目录放 `hydroclaw_adapter.py`：

```python
from hydroclaw.adapters.base import PackageAdapter

class Adapter(PackageAdapter):
    name = "myhydro"
    priority = 12   # 高于 hydromodel(10)

    def can_handle(self, data_source, model_name):
        return model_name == "myhydro"

    def my_operation(self, workspace, **kw) -> dict:
        import myhydro
        ...
```

可选：放 `hydroclaw_adapter_skills/skill.md` 自定义工作流说明，否则自动生成。

注册表采用**两层结构**：全局 `~/.hydroclaw/plugins.json` + 项目级 `<workspace>/.hydroclaw/plugins.json`（本地覆盖全局）。

### 推理型模型感知

HydroClaw 自动检测模型类型并激活对应的推理参数，无需手动配置：

| 模型 | 检测规则 | 行为 |
|------|---------|------|
| DeepSeek-R1/R2/R3 | `deepseek` + `-rN` | 解析响应中的 `<think>...</think>` 标签 |
| QwQ-32B / QwQ-Plus | `qwq` | 传 `extra_body={"enable_thinking": True}`，读 `reasoning_content` |
| OpenAI o1/o3/o4 | `o1`/`o3`/`o4` | 传 `reasoning_effort="high"`，省略 temperature |
| DeepSeek-V3 / Qwen / GPT-4o | 对话关键词 | temperature=0.3，标准调用 |

`LLMResponse.thinking` 字段存储推理过程；dev 模式下以 Panel 形式展示完整推理链。

可在 config 中强制覆盖：`"reasoning_style": "none"` 关闭推理激活。

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
├── hydroclaw/                    # 核心包
│   ├── agent.py                  # Agentic Loop 核心（ReAct 模式）
│   ├── llm.py                    # LLM 客户端（Function Calling + Prompt 降级 + 推理感知）
│   ├── memory.py                 # 三层记忆（会话/MEMORY.md/流域档案）
│   ├── config.py                 # 配置加载 + hydromodel 配置构建
│   ├── skill_registry.py         # Skill 自动扫描与关键词匹配
│   ├── skill_states.py           # Skill 生命周期状态管理
│   ├── adapters/                 # PackageAdapter 插件架构
│   │   ├── __init__.py           # reload_adapters()：内置 + 外部插件统一扫描
│   │   ├── base.py               # PackageAdapter 基类
│   │   ├── hydromodel/           # 内置：hydromodel 适配器（GR4J/XAJ/...）
│   │   └── hydrodatasource/      # 内置：数据源适配器
│   ├── interface/                # 用户界面层
│   │   ├── cli.py                # CLI 入口 + 交互 REPL（含 /plugin 命令）
│   │   ├── ui.py                 # Rich 终端 UI（user / dev 两种模式）
│   │   ├── server.py             # FastAPI + WebSocket 服务（含 /api/plugins 路由）
│   │   └── static/               # Web 前端静态文件
│   ├── tools/                    # 工具集（自动注册）
│   │   ├── add_local_package.py  # 元工具：注册本地目录包
│   │   └── add_local_tool.py     # 元工具：注册单文件 .py 工具
│   ├── skills/                   # Skill 包（工作流指引 + 工具实现）
│   ├── knowledge/                # 结构化领域知识（参数物理含义、率定经验）
│   └── utils/                    # 辅助模块
│       ├── plugin_registry.py    # 插件注册表（全局 + 本地两层）
│       ├── error_kb.py           # 错误知识库（自动积累）
│       ├── task_state.py         # 批量任务状态持久化
│       ├── setup_wizard.py       # 首次启动配置向导
│       ├── context_utils.py      # Token 估算、截断（语义截断）
│       └── basin_validator.py    # 流域数据验证工具
├── configs/
│   ├── model_config.py           # 算法参数（轮次、目标函数等）
│   └── private.py                # API Key、数据路径（gitignore）
├── sessions/                     # 会话历史（*.jsonl + *_summary.json）
├── scripts/                      # 论文实验脚本
└── docs/                         # 项目文档
```

---

## 详细文档

| 文档 | 内容 |
|------|------|
| [getting-started.md](docs/getting-started.md) | 安装、配置、首次运行、FAQ |
| [usage.md](docs/usage.md) | 所有使用场景示例 |
| [architecture.md](docs/architecture.md) | Agentic Loop、五层架构（大脑-脊椎-四肢）、工具发现机制 |
| [integration-plan.md](docs/integration-plan.md) | 通用包插件系统 + Agent 智能升级完整设计文档 |
| [skills.md](docs/skills.md) | Skill 工具 API 参考（calibrate、evaluate、llm_calibrate 等） |
| [tools.md](docs/tools.md) | 独立工具参考（validate、simulate、create_skill、add_local_package 等） |
| [memory.md](docs/memory.md) | 跨会话记忆、流域档案机制 |
| [llm-calibration.md](docs/llm-calibration.md) | LLM 智能率定原理与参数边界诊断 |
| [configuration.md](docs/configuration.md) | 配置层级、所有配置项详解（含 reasoning_style、prompt_mode） |
| [development.md](docs/development.md) | 项目结构、添加 Skill/工具/外部包适配器、代码规范 |

---

## 技术栈

| 类别 | 组件 |
|------|------|
| LLM | DeepSeek-R1/V3 / QwQ / Qwen / GPT-4o（OpenAI 兼容接口） |
| 推理感知 | DeepSeek-R1 `<think>` 解析 / QwQ `enable_thinking` / o1 `reasoning_effort` |
| 水文建模 | [hydromodel](https://github.com/OuyangWenyu/hydromodel)（GR4J / XAJ / SACSMA） |
| 数据集 | CAMELS-US（671 流域） |
| 终端 UI | [Rich](https://github.com/Textualize/rich) |
| Web 服务 | FastAPI + WebSocket |
| 运行环境 | Python 3.11+ |

---

## 学术参考

> Zhu, S. et al. (2026). Large Language Models as Virtual Hydrologists. *Geophysical Research Letters*. DOI: 10.1029/2025GL120043

HydroClaw 在此基础上的改进：LLM 调整参数**搜索范围**（而非直接提议参数值），配合 SCE-UA 全局优化，通常 2-3 轮收敛，LLM 调用次数减少约 100 倍。

---

<div align="center">

**HydroClaw — 用最少的代码，释放 LLM 在水文建模中的全部潜力**

</div>
