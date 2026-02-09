# 核心架构

## 设计哲学

HydroClaw 的核心原则：**让 LLM 做决策，代码只做执行。**

传统水文模型系统需要大量 if-else 逻辑来编排工作流。HydroClaw 把编排权交给 LLM——LLM 看到工具描述和场景指引后，自然地决定调用顺序。

```
传统方式：  代码路由 → Agent A → 代码路由 → Agent B → 代码路由 → Agent C
HydroClaw： LLM 推理 → Tool → LLM 推理 → Tool → LLM 推理 → 最终回答
```

## Agentic Loop

### 核心循环

`agent.py` 中的 `HydroClaw.run()` 实现了核心循环：

```python
for turn in range(max_turns):
    response = llm.chat(messages, tools=tool_schemas)

    if response.is_text():
        # LLM 给出最终回答 → 结束
        return response.text

    # LLM 要调用工具
    for tool_call in response.tool_calls:
        result = execute_tool(tool_call.name, tool_call.arguments)
        messages.append(tool_result_message(result))
    # 继续循环，让 LLM 看到工具结果后继续推理
```

**没有状态机、没有分支路由。** 循环何时结束完全由 LLM 决定——当 LLM 认为任务完成时，它输出纯文本而非工具调用，循环自然结束。

### 上下文构建

每次对话的初始上下文由三部分组成：

```
System Prompt = system.md（核心人设）
              + 匹配的 Skill（场景指引）
              + MEMORY.md（跨会话知识）
```

Skill 匹配基于查询关键词：

| 查询关键词 | 匹配 Skill |
|---|---|
| 率定、calibrate | calibration.md |
| 迭代、边界 | iterative.md |
| 对比、比较 | comparison.md |
| 批量、多流域 | batch.md |
| 分析、FDC | analysis.md |

## 工具系统

### 自动发现

`hydroclaw/tools/__init__.py` 在启动时扫描 `tools/` 目录：

1. 遍历所有 `.py` 模块（跳过 `_` 开头的）
2. 找到所有公开函数（不以 `_` 开头）
3. 从函数签名和 docstring 自动生成 OpenAI Function Calling Schema
4. 注册到全局工具表

```
tools/calibrate.py  →  def calibrate_model(...)  →  工具 "calibrate_model"
tools/evaluate.py   →  def evaluate_model(...)   →  工具 "evaluate_model"
tools/xxx.py        →  def xxx(...)              →  工具 "xxx"
```

**添加新工具就是添加新文件，无需修改任何注册代码。**

### Schema 生成

函数签名自动转换为 JSON Schema：

```python
def calibrate_model(
    basin_ids: list[str],          # → {"type": "array", "items": {"type": "string"}}
    model_name: str = "xaj",       # → {"type": "string", "default": "xaj"}
    algorithm_params: dict | None, # → {"type": "object"}
    _cfg: dict | None = None,      # → 跳过（_ 前缀 = 内部参数）
) -> dict:
    """Calibrate a model.    # → description

    Args:
        basin_ids: Basin IDs   # → parameter description
    """
```

### 内部参数注入

以 `_` 开头的参数不暴露给 LLM，由 Agent 在运行时自动注入：

| 参数 | 注入值 | 用途 |
|---|---|---|
| `_workspace` | 当前工作目录 | 文件读写路径 |
| `_cfg` | 全局配置字典 | API Key、默认参数等 |
| `_llm` | LLM 客户端实例 | 需要调用 LLM 的工具（如 llm_calibrate） |

### 热加载

`create_tool` 创建新工具后，调用 `reload_tools()` 清除缓存并重新扫描：

```python
# __init__.py
def reload_tools():
    _TOOLS.clear()
    # 清除 Python 模块缓存
    for k in list(sys.modules):
        if k.startswith("hydroclaw.tools."):
            del sys.modules[k]
    return discover_tools()
```

Agent 在检测到 `create_tool` 成功后自动刷新工具表和 Schema。

## LLM 客户端

### 双模式支持

`llm.py` 实现了两种工具调用模式：

**Mode A: 原生 Function Calling**

适用于 GPT、Qwen、DeepSeek 等支持 `tools` 参数的模型：

```python
response = client.chat.completions.create(
    model=model, messages=messages, tools=tool_schemas
)
# response.choices[0].message.tool_calls → 结构化工具调用
```

**Mode B: Prompt 降级**

适用于 Ollama 等不支持 Function Calling 的模型：

```python
# 将工具描述注入 System Prompt
system_prompt += format_tools_as_text(tool_schemas)
# LLM 返回包含 JSON 的文本
# 解析 ```json {"tool": "...", "arguments": {...}} ``` 块
```

自动检测：首次调用时尝试 Function Calling，失败则自动降级。

## 会话记忆

### 双层记忆

```
MEMORY.md           跨会话持久知识（LLM 自主维护）
sessions/*.jsonl    会话级工具调用记录（自动记录）
```

- **MEMORY.md**：Agent 在对话中发现的重要知识（如某流域特点、常见错误），持久保存
- **JSONL**：每个会话的完整工具调用日志，用于回溯和断点续跑

## 与 HydroAgent 的对比

| 方面 | HydroAgent (v6.0) | HydroClaw |
|---|---|---|
| 架构 | 5 Agent + 状态机 + Orchestrator | 单一 Agentic Loop |
| 代码量 | ~27,000 行 | ~2,600 行 |
| 工作流编排 | 硬编码状态转换 | LLM 自主推理 |
| 工具选择 | if-else 路由 (960行) | LLM Function Calling |
| 添加新工具 | 改 Agent + 注册 + 路由 | 放一个 .py 文件 |
| LLM 调用次数 | 每步 1 次（固定流程） | 按需（LLM 决定） |
| 多模型对比 | 需要 Orchestrator 循环 | LLM 自然循环调用 |
