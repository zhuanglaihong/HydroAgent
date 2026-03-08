# 核心架构

## 设计哲学

HydroClaw 的核心原则：**让 LLM 做决策，代码只做执行。**

传统水文模型系统需要大量 if-else 逻辑来编排工作流。HydroClaw 把编排权交给 LLM——LLM 看到工具描述和场景指引后，自然地决定调用顺序。

```
传统方式：  代码路由 -> Agent A -> 代码路由 -> Agent B -> 代码路由 -> Agent C
HydroClaw： LLM 推理 -> Tool -> LLM 推理 -> Tool -> LLM 推理 -> 最终回答
```

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
