# 核心架构

## 设计哲学

HydroClaw 的核心原则：**让 LLM 做决策，代码只做执行。**

传统水文模型系统需要大量 if-else 逻辑来编排工作流。HydroClaw 把编排权交给 LLM——LLM 看到工具描述和场景指引后，自然地决定调用顺序。

```
传统方式：  代码路由 -> Agent A -> 代码路由 -> Agent B -> 代码路由 -> Agent C
HydroClaw： LLM 推理 -> Tool -> LLM 推理 -> Tool -> LLM 推理 -> 最终回答
```

---

## 五层架构（大脑-脊椎-四肢模型）

HydroClaw 的完整架构可以用人体神经运动系统来类比：

```
┌─────────────────────────────────────────────────────┐
│  【大脑】Agent Core (LLM ReAct Loop)                 │
│   - 推理、规划、决策："下一步做什么？"                │
│   - 不关心任何包的 API 细节                          │
│   - 由 Skill / 领域知识 / 记忆 塑造决策模式          │
└──────────────────────────┬──────────────────────────┘
                           │ 意图（调用哪个工具、传什么参数）
┌──────────────────────────▼──────────────────────────┐
│  【小脑/脑干】Skill（技能说明书）                     │
│   - 程序记忆：告诉大脑"面对率定任务应该怎么思考"     │
│   - 注入 system prompt，影响决策模式而不直接执行     │
│   - 不是四肢，是让大脑运作更好的经验积累             │
└──────────────────────────┬──────────────────────────┘
                           │ 工具调用（Function Calling）
┌──────────────────────────▼──────────────────────────┐
│  【脊椎/中枢】PackageAdapter（适配器层）              │
│   - 双向翻译："率定 gr4j" -> build_cfg() + hm_calibrate()
│   - 处理错误、重试、进度监控（神经反射）             │
│   - 屏蔽包差异，大脑不需要知道底层用哪个包           │
│   - 热插拔：新包只需实现 4 个方法，无需改大脑代码    │
└──────────────────────────┬──────────────────────────┘
                           │ 包调用
┌──────────────────────────▼──────────────────────────┐
│  【神经末梢】Tool（工具函数）                         │
│   - 大脑可以命令的动作接口                           │
│   - 薄路由：接收意图 -> 找对应适配器 -> 执行         │
│   - 公开函数自动生成 Function Calling Schema         │
└──────────────────────────┬──────────────────────────┘
                           │ Python API 调用
┌──────────────────────────▼──────────────────────────┐
│  【肌肉】Package（功能包）                            │
│   - hydromodel、hydrodataset 等已发布的包            │
│   - pip 安装，做真正的数值计算                        │
│   - 完全不知道 Agent 的存在                          │
└─────────────────────────────────────────────────────┘
```

### 各层职责边界

| 层级 | 代表模块 | 核心问题 | 知道 Agent 的存在？ |
|------|----------|----------|-------------------|
| 大脑 | `agent.py` (ReAct Loop) | "下一步做什么？" | 是（就是 Agent 本身） |
| 小脑 | `skills/*/skill.md` | "这类任务该怎么思考？" | 间接（只是文本指引） |
| 脊椎 | `adapters/*/adapter.py` | "如何把意图翻译成包调用？" | 是（接收 `_cfg`, `_ui`） |
| 神经末梢 | `skills/*/xxx.py`, `tools/*.py` | "哪个适配器来处理？" | 部分（薄路由） |
| 肌肉 | `hydromodel`, `hydrodataset` | "执行计算" | 否 |

### Skill 不是"四肢"，是"经验"

Skill 有两种形态，容易混淆：

- **`skill.md`**（指引文档）：注入 system prompt，影响 LLM 的决策方式。这是"小脑程序记忆"——LLM 读了它，面对同类任务就知道该怎么思考和行动。
- **`skill.py`**（工具实现）：注册为可调用的 Tool，这部分才是真正的"动作"。

所以一个完整的 Skill = 经验（.md 指引大脑） + 动作（.py 被大脑调用）。

---

## 知识注入机制：Prompt Stuffing vs RAG

### 当前实现：关键词匹配 + 直接注入（Prompt Stuffing）

HydroClaw 目前**不使用向量数据库或语义检索（RAG）**，而是关键词触发的静态文档注入：

```
用户查询包含 "率定/calibrat"
  -> 读取 knowledge/calibration_guide.md 全文 -> 直接追加到 system prompt
  -> 读取 skills/calibration/skill.md 全文  -> 直接追加到 system prompt
```

这是 **Prompt Stuffing**，本质是"把相关文档整段塞进上下文"。

| 维度 | 当前方案（Prompt Stuffing） | RAG（向量检索） |
|------|---------------------------|----------------|
| 实现复杂度 | 极低（读文件 + 字符串拼接） | 中（需向量库 + embedding 模型） |
| 适用规模 | 知识文档 < 10 个，单文档 < 2000 字 | 文档 > 50 个，或单文档很长 |
| 检索精度 | 关键词匹配，粗粒度 | 语义相似度，细粒度 |
| 上下文占用 | 整文档注入，占用较多 | 只取最相关片段，节省 token |
| 当前瓶颈 | 知识文档较少，暂时够用 | 暂不必要 |

**何时应升级为 RAG**：当 `knowledge/` 目录下文档超过 10 个，或某个文档超过 3000 字，直接注入会明显消耗 token 时，考虑引入向量检索，只注入最相关的 N 个片段。

---

### 记忆增长与上下文控制

**三种信息的增长特征不同**：

| 信息类型 | 增长速度 | 当前上限 | 风险 |
|----------|----------|---------|------|
| `MEMORY.md`（跨会话通用知识） | 慢（手动 + 偶尔自动写入） | 4,000 字符截断 | 低 |
| `basin_profiles/<id>.json`（流域档案） | 中（每次率定成功写一条） | 3,000 字符截断 | 中（流域多时叠加） |
| `messages[]`（对话历史） | **快**（每轮 +2 条） | 触发 `_maybe_compress_history()` | **高**（长任务主要风险） |

**当前对话历史控制机制**（`agent.py`）：
```python
# 超过 60,000 估算 token 时压缩
def _maybe_compress_history(messages):
    # 保留：[system, 原始查询, 最近 4 条]
    # 压缩：中间历史 -> 一段 LLM 生成的摘要
```

**已知局限**：这是"一次性压缩"策略，压缩后摘要本身也会继续增长。长达 30+ 轮的批量任务中，仍可能出现上下文超限。更完整的方案是分层记忆（工作记忆 + 短期记忆 + 长期档案），但当前实现暂时够用。

---

## PackageAdapter 解耦架构

### 动机

在早期版本中，工具函数直接 `import hydromodel`，技能说明硬编码 hydromodel 的调用方式。新增任何水文包都需要修改核心代码。

PackageAdapter 层的引入解决了这个问题：**核心 Agent 只负责推理/决策，水文包操作通过适配器接入，动态加载，无需修改核心代码。**

### 目录结构

```
hydroclaw/adapters/
├── __init__.py               # 自动扫描 + get_adapter() + get_all_skill_docs()
├── base.py                   # PackageAdapter 抽象接口
├── hydromodel/
│   ├── adapter.py            # HydromodelAdapter（移入全部 hydromodel 耦合逻辑）
│   └── skills/
│       └── hydromodel.md     # hydromodel 调用方式说明（注入 system prompt）
└── generic/
    └── adapter.py            # GenericAdapter（兜底，返回结构化引导）
```

### 适配器接口

每个适配器必须实现 4 个方法：

```python
class PackageAdapter(ABC):
    name: str = ""
    priority: int = 0  # 数字越大优先级越高

    def can_handle(self, data_source: str, model_name: str) -> bool: ...
    def calibrate(self, workspace: Path, **kw) -> dict: ...
    def evaluate(self, workspace: Path, **kw) -> dict: ...
    def visualize(self, workspace: Path, **kw) -> dict: ...
    def simulate(self, workspace: Path, **kw) -> dict: ...
```

### 路由逻辑

```
calibrate_model(model_name="gr4j", data_source="camels_us")
    -> get_adapter("camels_us", "gr4j")
    -> 遍历已加载适配器（按 priority 降序）
    -> HydromodelAdapter.can_handle() -> True (priority=10)
    -> HydromodelAdapter.calibrate(...)
```

当所有已加载适配器都不能处理时（`_adapters` 为空，即 hydromodel 安装失败），回退到 `GenericAdapter`，返回结构化引导而非抛异常，LLM 可以读懂并用 `generate_code` 另辟蹊径。

### 热插拔新包

用 `create_adapter` 元工具，LLM 可以为新水文包动态生成骨架：

```python
create_adapter("xaj_model", "XAJ rainfall-runoff model", supported_models=["xaj_v2"])
# 生成 hydroclaw/adapters/xaj_model/adapter.py (骨架)
# 生成 hydroclaw/adapters/xaj_model/skills/skill.md
# 自动调用 reload_adapters()，立即生效，无需重启
```

开发者填写 4 个方法后，Agent 即可驱动新包，全程无需修改 agent.py 或 tools/ 中的任何文件。

### Adapter Skill Docs 注入

每个适配器的 `skills/*.md` 在 `_build_context()` 中自动注入 system prompt：

```
system prompt
  = system.md
  + 匹配的 Skill 说明书
  + [NEW] Package Adapter Skills (hydromodel.md, ...)  <- 各包的调用方式
  + 领域知识
  + 流域档案记忆
```

---

## Agentic Loop

### 核心循环

`agent.py` 中的 `HydroClaw.run()` 实现了 ReAct 模式的核心循环：

```python
for turn in range(max_turns):
    response = llm.chat(messages, tools=tool_schemas)

    if response.is_text():
        # LLM 给出最终回答 -> 结束
        return response.text

    # LLM 要调用工具
    for tool_call in response.tool_calls:
        result = execute_tool(tool_call.name, tool_call.arguments)
        messages.append(tool_result_message(result))
    # 继续循环，让 LLM 看到工具结果后继续推理
```

**没有状态机、没有分支路由。** 循环何时结束完全由 LLM 决定——当 LLM 认为任务完成时，它输出纯文本而非工具调用，循环自然结束。

### 三层知识注入

每次对话的 system prompt 由三层动态内容构建：

```
System Prompt
  = system.md（核心人设 + 工具能力概述）
  + 匹配的 Skill（场景工作流指引）       <- 第一层：Skill 说明书
  + 领域知识（参数物理含义 + 率定经验）   <- 第二层：领域知识库
  + 流域历史档案（跨会话先验信息）        <- 第三层：跨会话记忆
```

三层知识的作用：

| 层级 | 内容 | 作用 |
|------|------|------|
| Skill 说明书 | 工作流步骤、工具调用顺序 | 告诉 LLM "该怎么做" |
| 领域知识库 | 参数物理含义、率定诊断经验 | 告诉 LLM "为什么这样做" |
| 跨会话记忆 | 该流域历史率定参数和 NSE | 告诉 LLM "上次做到哪了" |

## Skill 系统

### 目录结构

每个 Skill 是一个子目录，包含工作流指引和工具实现：

```
hydroclaw/skills/
├── system.md                      # 系统基础 prompt（每次都注入）
├── calibration/
│   ├── skill.md                   # 工作流指引（匹配关键词时注入）
│   └── calibrate.py               # calibrate_model() 工具实现
├── evaluation/
│   ├── skill.md
│   └── evaluate.py                # evaluate_model() 工具实现
├── llm_calibration/
│   ├── skill.md
│   └── llm_calibrate.py           # llm_calibrate() 工具实现
├── batch_calibration/
│   ├── skill.md
│   └── batch_calibrate.py
├── code_analysis/
│   ├── skill.md
│   ├── generate_code.py           # generate_code() 工具实现
│   └── run_code.py                # run_code() 工具实现
├── model_comparison/
│   ├── skill.md
│   └── compare_models.py
└── visualization/
    ├── skill.md
    └── visualize.py
```

### 独立工具（非 Skill）

```
hydroclaw/tools/
├── __init__.py         # 工具发现引擎
├── validate.py         # validate_basin() -- 每次对话都可能用到
├── simulate.py         # run_simulation()
└── create_skill.py     # create_skill() -- 元工具，运行时生成新 Skill
```

### Skill 匹配（SkillRegistry）

`skill_registry.py` 扫描每个 Skill 目录的 `skill.md` 头部关键词，在查询时自动匹配：

```
查询: "率定GR4J模型" -> 匹配 calibration/ -> 注入 calibration/skill.md
查询: "智能率定"     -> 匹配 llm_calibration/ -> 注入 llm_calibration/skill.md
查询: "代码分析"     -> 匹配 code_analysis/  -> 注入 code_analysis/skill.md
```

### 动态 Skill 创建（元能力）

用户请求新功能时，LLM 调用 `create_skill`，在 `skills/` 目录下自动生成新子目录：

```
create_skill(name="mcmc_uncertainty", description="用 spotpy 做 MCMC 不确定性分析")
-> hydroclaw/skills/mcmc_uncertainty/
   ├── skill.md      # LLM 生成的工作流指引
   └── tool.py       # LLM 生成的工具实现
```

新 Skill 立即注册，无需重启。

## 工具发现

`hydroclaw/tools/__init__.py` 在启动时扫描两个位置：

1. `hydroclaw/tools/` — 独立工具文件
2. `hydroclaw/skills/*/` — 每个 Skill 子目录中的 `.py` 文件

对每个公开函数（不以 `_` 开头）自动生成 OpenAI Function Calling Schema：

```python
def calibrate_model(
    basin_ids: list[str],          # -> {"type": "array", "items": {"type": "string"}}
    model_name: str = "xaj",       # -> {"type": "string", "default": "xaj"}
    algorithm_params: dict | None, # -> {"type": "object"}
    _cfg: dict | None = None,      # -> 跳过（_ 前缀 = 内部参数）
) -> dict:
    """Calibrate a model.          # -> description
    Args:
        basin_ids: Basin IDs       # -> parameter description
    """
```

### 内部参数注入

以 `_` 开头的参数不暴露给 LLM，由 Agent 在运行时自动注入：

| 参数 | 注入值 | 用途 |
|------|--------|------|
| `_workspace` | 当前工作目录 | 文件读写路径 |
| `_cfg` | 全局配置字典 | API Key、默认参数等 |
| `_llm` | LLM 客户端实例 | 需要调用 LLM 的工具 |

## LLM 客户端

### 双模式支持

`llm.py` 实现了两种工具调用模式，自动检测：

**Mode A: 原生 Function Calling**（GPT、Qwen、DeepSeek 等）

```python
response = client.chat.completions.create(
    model=model, messages=messages, tools=tool_schemas
)
# response.choices[0].message.tool_calls -> 结构化工具调用
```

**Mode B: Prompt 降级**（Ollama 等不支持 Function Calling 的模型）

```python
# 将工具描述注入 System Prompt
# LLM 返回包含 JSON 的文本块，解析后执行
```

首次调用时尝试 Function Calling，失败则自动降级并记录。

## 记忆系统

### 三层记忆

```
会话内记忆     messages[]           当前对话上下文（随会话结束清空）
跨会话知识     workspace/MEMORY.md  Agent 自主维护的通用经验
流域档案       workspace/basin_profiles/<id>.json   流域专属率定历史
```

### 流域档案（Basin Profiles）

每次率定成功后自动保存：

```json
{
  "basin_id": "12025000",
  "records": [
    {
      "model": "gr4j",
      "algorithm": "SCE_UA",
      "train_nse": 0.783,
      "best_params": {"x1": 1180.6, "x2": -3.94, "x3": 36.9, "x4": 1.22},
      "calibrated_at": "2026-03-07T..."
    }
  ]
}
```

下次对同一流域发起查询时，历史记录自动注入 system prompt，LLM 可以：
- 使用历史参数作为先验初始化新一轮率定
- 识别参数是否与历史差异异常（对抗先验检测）
- 对比多次率定结果，判断是否已收敛

## 与 HydroAgent 的对比

| 方面 | HydroAgent v6.0 | HydroClaw |
|------|-----------------|-----------|
| 架构 | 5 Agent + 状态机 + Orchestrator | 单一 Agentic Loop |
| 代码量 | ~27,000 行 | ~3,000 行 |
| 工作流编排 | 硬编码状态转换 | LLM 自主推理 |
| 工具选择 | if-else 路由 (960行) | LLM Function Calling |
| 知识注入 | 无 | 三层结构化注入 |
| 跨会话记忆 | 无 | 流域档案自动积累 |
| 工具扩展 | 改 Agent + 注册 + 路由 | 运行时 create_skill |
