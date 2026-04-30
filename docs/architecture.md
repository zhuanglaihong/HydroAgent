# HydroAgent 核心架构文档

> 版本：v2.6 | 日期：2026-03-25

---

## 目录

1. [设计哲学](#1-设计哲学)
2. [五层架构（大脑-脊椎-四肢模型）](#2-五层架构大脑-脊椎-四肢模型)
3. [Agentic Loop（agent.py）](#3-agentic-loopagentpy)
4. [系统提示构建（六段式）](#4-系统提示构建六段式)
5. [Skill 系统（SkillRegistry）](#5-skill-系统skillregistry)
6. [PackageAdapter 插件层（adapters/）](#6-packageadapter-插件层adapters)
7. [工具发现引擎（tools/__init__.py）](#7-工具发现引擎toolsinitpy)
8. [工具自描述协议（__agent_hint__）](#8-工具自描述协议__agent_hint__)
9. [记忆系统（memory.py）](#9-记忆系统memorypy)
10. [上下文控制（截断 + 压缩）](#10-上下文控制截断--压缩)
11. [LLM 客户端（llm.py）](#11-llm-客户端llmpy)
12. [任务状态注入（CC-2）](#12-任务状态注入cc-2)
13. [PostToolUse Hook 系统（CC-4）](#13-posttooluse-hook-系统cc-4)
14. [子代理系统（AgentRegistry + spawn_agent，CC-3）](#14-子代理系统agentregistry--spawn_agentcc-3)
15. [插件注册表（plugin_registry.py）](#15-插件注册表plugin_registrypy)
16. [界面层（interface/）](#16-界面层interface)
17. [知识注入顺序总览](#17-知识注入顺序总览)
18. [目录结构（v2.6 完整版）](#18-目录结构v26-完整版)
19. [与 HydroAgent 旧版对比](#19-与-hydroagent-旧版对比)

---

## 1. 设计哲学

**核心原则：让 LLM 做决策，代码只做执行。**

传统水文系统需要大量 if-else 逻辑编排工作流；HydroAgent 把编排权交给 LLM，LLM 看到工具描述和场景指引后自然地决定调用顺序。没有状态机，没有路由表，循环何时结束完全由 LLM 决定。

**三个核心权衡（设计决策记录）**：

| 维度 | 选择 | 放弃 | 理由 |
|------|------|------|------|
| 知识注入 | Prompt Stuffing（关键词匹配直接注入） | RAG（向量检索） | 文档 <10 个、单文档 <2000 字时不必要；RAG 增加依赖且精度提升有限 |
| 执行架构 | 单一 Agentic Loop | 多 Agent 状态机 | INDRA(2025) 的多 Agent 路线代码量 5×，无量化优势；Skill + PackageAdapter 满足扩展需求 |
| 包集成 | PackageAdapter 插件层（松耦合） | 直接 import（硬耦合） | 支持热插拔、第三方包、graceful degradation；核心代码不随包增加而膨胀 |

---

## 2. 五层架构（大脑-脊椎-四肢模型）

```
+--------------------------------------------------------------+
|  [大脑]  agent.py (ReAct Loop)                               |
|   - 推理、规划、决策："下一步做什么？"                        |
|   - 不关心任何包的 API 细节                                  |
|   - 由 Skill / 领域知识 / 记忆 / task_note 塑造决策模式       |
+----------------------------+---------------------------------+
                             | 意图（调用哪个工具、传什么参数）
+----------------------------v---------------------------------+
|  [小脑]  skills/*/skill.md（Skill 说明书）                   |
|   - 程序记忆：告诉大脑"面对这类任务该怎么思考"               |
|   - 注入 system prompt，影响决策模式，不直接执行             |
|   - 适配器包文档（adapters/*/skills/*.md）同级注入           |
+----------------------------+---------------------------------+
                             | 工具调用（Function Calling）
+----------------------------v---------------------------------+
|  [脊椎]  adapters/*/adapter.py（PackageAdapter 插件层）      |
|   - 双向翻译："rate gr4j" -> build_cfg() + hm_calibrate()   |
|   - 按 priority 路由，优雅降级到 GenericAdapter              |
|   - 屏蔽包差异，大脑不知道底层用哪个包                       |
|   - 热插拔：create_adapter + reload_adapters()               |
+----------------------------+---------------------------------+
                             | 包调用
+----------------------------v---------------------------------+
|  [神经末梢]  skills/*/xxx.py + tools/*.py（工具路由函数）    |
|   - 薄路由：接收 LLM 意图 -> 找对应适配器 -> 转发            |
|   - 公开函数自动生成 Function Calling Schema                 |
|   - __agent_hint__ 属性注入调用约束                          |
+----------------------------+---------------------------------+
                             | Python API 调用
+----------------------------v---------------------------------+
|  [肌肉]  hydromodel / hydrodataset 等（功能包）              |
|   - pip 安装，做真正的数值计算                               |
|   - 完全不知道 Agent 的存在                                  |
+--------------------------------------------------------------+
```

### 各层职责边界

| 层级 | 代表模块 | 核心问题 | 知道 Agent？ |
|------|----------|----------|-------------|
| 大脑 | `agent.py` | "下一步做什么？" | 是（本身） |
| 小脑 | `skills/*/skill.md` | "这类任务该怎么思考？" | 间接（文本指引） |
| 脊椎 | `adapters/*/adapter.py` | "如何把意图翻译成包调用？" | 是（接收 `_cfg`, `_ui`） |
| 神经末梢 | `skills/*/xxx.py`, `tools/*.py` | "哪个适配器来处理？" | 部分（薄路由） |
| 肌肉 | `hydromodel`, `hydrodataset` | "执行计算" | 否 |

---

## 3. Agentic Loop（agent.py）

### 3.1 核心循环（ReAct 模式）

```python
class HydroAgent:
    def run(self, query: str) -> str:
        messages = [{"role": "system", "content": self._build_system_prompt(query)}]
        messages.append({"role": "user", "content": query})

        for turn in range(self.max_turns):
            response = self.llm.chat(messages, tools=self.tool_schemas)

            if response.is_text():
                # LLM 给出最终回答 -> 结束循环
                self.memory.append_session(query, response.text)
                return response.text

            # LLM 要调用工具
            tool_calls = response.tool_calls
            # 将 LLM 的 assistant 消息加入历史
            messages.append(response.raw_message)

            for tc in tool_calls:
                result = self._execute_tool(tc.name, tc.arguments)
                messages.append(tool_result_message(tc.id, result))

            # CC-2: 在所有工具结果之后，注入任务状态摘要
            task_note = self._get_task_status_note()
            if task_note:
                messages.append({"role": "user", "content": task_note})

            # 上下文过长时压缩
            messages = self._maybe_compress_history(messages)

        return "[达到最大轮次，任务未完成]"
```

**关键设计点**：
- 没有状态机；何时停止完全由 LLM 决定（输出纯文本 = 完成）
- Function Calling 模式下多个工具调用在一个 turn 内批量处理，全部完成后才注入 task_note
- 工具调用顺序由 LLM 决定，不硬编码

### 3.2 工具执行（_execute_tool）

```python
def _execute_tool(self, name: str, arguments: dict) -> dict:
    fn = self.tools.get(name)
    if fn is None:
        return {"success": False, "error": f"Unknown tool: {name}"}

    # 注入内部参数（_ 前缀，不暴露给 LLM）
    injected = {
        "_workspace": self.workspace,
        "_cfg": self.config,
        "_llm": self.llm,
        "_ui": self.ui,
    }
    kwargs = {**arguments, **{k: v for k, v in injected.items() if k in fn.__code__.co_varnames}}

    result = fn(**kwargs)

    # CC-4: PostToolUse hooks
    for hook in self._post_tool_hooks.get(name, []):
        try:
            hook(name, arguments, result)
        except Exception as hook_err:
            logger.warning("PostToolUse hook failed for %s: %s", name, hook_err)

    return result
```

### 3.3 子代理支持（_subagent_system_prompt）

当 `HydroAgent` 作为子代理被 `spawn_agent` 创建时，`_subagent_system_prompt` 属性被设置，
`_load_system_prompt()` 优先使用该覆盖值而非读取 `skills/system.md`。

---

## 4. 系统提示构建（七段式）

`_build_system_prompt(query)` 动态组装七个部分（五层提示模型）：

```
Layer 1 — 身份层（Identity）
  Section 1: 角色与核心原则
    <- skills/system.md（每次对话都注入）

Layer 2 — 行为层（Policy）          [v2.7 新增]
  Section 1.5: 行为约束策略
    <- policy/*.md（全量注入，上限 2000 字符）
    含：agent_behavior / calibration_policy / tool_safety_policy / reporting_policy
    在 full 和 minimal 模式下均注入（安全约束不可省略）

Layer 3 — 技能层（Skills）
  Section 2: 工作流 Skill 说明书
    <- skills/*/skill.md（按查询关键词匹配注入）
    仅注入文档路径列表（让 LLM 按需 read_file），避免全量注入占用 token
  Section 2.5: 可用子代理列表
    <- AgentRegistry.available_agents_prompt()
  Section 3: 适配器包文档
    <- adapters/*/skills/*.md（全量注入，通常较短）

Layer 4 — 知识层（Knowledge）
  Section 4: 领域知识
    <- knowledge/*.md（按查询关键词匹配注入，含 failure_modes.md）
    上限 4000 字符

Layer 5 — 记忆层（Memory）
  Section 5: 流域档案 + 跨会话记忆
    <- basin_profiles/<basin_id>.json（按 basin_id 匹配注入）
    <- MEMORY.md（跨会话通用知识，上限 4000 字符）
    上限 3000 字符

Section 6（工具 schema 内嵌）:
  <- __agent_hint__ 属性（自动附加到工具 schema description）
  不作为独立段落，嵌在工具列表里
```

**Token 预算（目标初始上下文 < 15K tokens）：**

| 层次 | 载体 | token 预算 |
|------|------|-----------|
| 身份层 | system.md | ~2K（约 6K 字符） |
| 行为层 | policy/*.md | 上限 2K 字符 (~700 tokens) |
| 技能层 | skill 路径列表 + adapter docs | ~1-2K |
| 知识层 | knowledge/*.md 片段 | 上限 4K 字符 (~1.3K tokens) |
| 记忆层 | basin_profiles + MEMORY.md | 上限 3K 字符 (~1K tokens) |

**注入顺序的设计理由**：
- 行为层紧跟身份层：约束规则比技能指导更基础，LLM 先建立"不能做什么"再看"怎么做"
- 技能层在前：确保 LLM 先获得"该怎么做"的行为框架
- 知识层在后：在 Skill 框架确定后，知识作为推理的底层依据
- 记忆层最后：作为针对本次查询的具体上下文
- 工具自描述嵌在 schema：与工具定义同位，修改工具时自然同步更新

---

## 5. Skill 系统（SkillRegistry）

### 5.1 两种 Skill

| 类型 | 位置 | 注入方式 | 作用 |
|------|------|---------|------|
| 工作流 Skill | `skills/*/skill.md` | 关键词匹配，注入 path（按需 read_file） | "这类任务怎么做"（程序记忆） |
| 适配器 Skill | `adapters/*/skills/*.md` | 每次全量注入 | "这个包的 API 怎么调"（包文档） |

### 5.2 SkillRegistry 工作流

```python
class SkillRegistry:
    def scan(self):
        # 扫描 skills/*/skill.md，读取 YAML 头部的 keywords 字段
        for skill_dir in skills_root.iterdir():
            md = skill_dir / "skill.md"
            keywords = parse_frontmatter(md).get("keywords", [])
            self._registry[skill_dir.name] = {"keywords": keywords, "path": md}

    def match(self, query: str) -> list[Path]:
        # 返回所有关键词命中的 skill.md 路径
        return [info["path"] for name, info in self._registry.items()
                if any(kw in query.lower() for kw in info["keywords"])]
```

skill.md 头部格式：
```yaml
---
keywords: [calibrat, 率定, gr4j, sce]
priority: 10
---
## 工作流指引
...
```

### 5.3 动态 Skill 生成（create_skill 元能力）

```
用户："帮我创建一个用 spotpy 做 MCMC 率定的工具"
  -> LLM 调用 create_skill(name="spotpy_mcmc", description="...")
  -> 生成 skills/spotpy_mcmc/skill.md + tool.py
  -> discover_tools() 重新扫描，立即注册（priority=5）
  -> 无需重启
```

### 5.4 Skill 生命周期（SkillStates）

`skill_states.py` 追踪每个 Skill 的状态：`draft -> active -> deprecated`。
`create_skill` 生成的 Skill 初始为 `draft`，首次成功调用后升为 `active`。

---

## 6. PackageAdapter 插件层（adapters/）

### 6.1 抽象接口（base.py）

```python
class PackageAdapter(ABC):
    name: str = ""
    priority: int = 0

    @abstractmethod
    def can_handle(self, data_source: str, model_name: str) -> bool: ...

    def supported_operations(self) -> list[str]:
        """声明支持哪些操作（代替固定方法集）"""
        return []

    def execute(self, operation: str, workspace: Path, **kw) -> dict:
        """统一 dispatch，子类可 override 各 operation"""
        method = getattr(self, operation, None)
        if method is None:
            return {"success": False, "error": f"Operation '{operation}' not supported"}
        return method(workspace=workspace, **kw)
```

**接口设计变化（v2.5）**：不再强制实现固定 4 个方法（calibrate/evaluate/visualize/simulate），
改为 `supported_operations()` 声明 + `execute()` dispatch，支持任意操作集合。

### 6.2 内置适配器

| 适配器 | priority | can_handle 条件 | 支持操作 |
|--------|----------|-----------------|---------|
| `HydrodatasourceAdapter` | 15 | data_source 包含自定义数据集路径 | list_basins, read_data, convert_to_nc |
| `HydromodelAdapter` | 10 | model_name 在支持列表中（gr4j/gr5j/gr6j/lstm/...） | calibrate, evaluate, simulate, visualize |
| `GenericAdapter` | 0 | 始终 True（兜底） | 返回结构化引导，不执行计算 |

### 6.3 路由逻辑（get_adapter）

```python
def get_adapter(data_source: str, model_name: str) -> PackageAdapter:
    for adapter in sorted(_adapters, key=lambda a: a.priority, reverse=True):
        if adapter.can_handle(data_source, model_name):
            return adapter
    return GenericAdapter()  # 兜底，始终可用
```

GenericAdapter 不报错，而是返回：
```json
{
  "success": false,
  "guidance": "No adapter found for model 'xaj_v3'. Suggested: use generate_code to write a custom runner.",
  "available_models": ["gr4j", "gr5j", "gr6j", "lstm"]
}
```
LLM 可读懂并用 `generate_code` 另辟蹊径。

### 6.4 热插拔机制

```python
# create_adapter 元工具执行后：
# 1. 在 adapters/<name>/ 生成 adapter.py 骨架 + skills/skill.md
# 2. 调用 reload_adapters() 重新扫描 adapters/ 目录
# 3. 新适配器立即注册，无需重启 Agent

def reload_adapters():
    _adapters.clear()
    for adapter_dir in (adapters_root / "*/adapter.py"):
        spec = importlib.util.spec_from_file_location(...)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls = getattr(module, "Adapter", None)
        if cls and issubclass(cls, PackageAdapter):
            _adapters.append(cls())
```

### 6.5 适配器 Skill Docs 注入

每个适配器目录下的 `skills/*.md` 在 `get_all_skill_docs()` 中收集，
全量注入 system prompt Section 3，告知 LLM 该包的 API 约定。

---

## 7. 工具发现引擎（tools/__init__.py）

### 7.1 扫描路径

启动时扫描两个位置（discover_tools()）：
1. `hydroagent/tools/*.py` — 核心工具（priority=20）
2. `hydroagent/skills/*/` — 每个 Skill 目录下的 `*.py`（priority=10）
3. 动态生成的 Skill（priority=5，`create_skill` 写入后触发重扫）

### 7.2 Schema 自动生成（fn_to_schema）

```python
def fn_to_schema(fn: Callable) -> dict:
    sig = inspect.signature(fn)
    properties = {}
    for name, param in sig.parameters.items():
        if name.startswith("_"):
            continue  # 内部参数，不暴露给 LLM
        properties[name] = type_hint_to_json_schema(param.annotation)
        # 从 docstring Args: 块提取参数说明
        if doc_desc := extract_param_desc(fn.__doc__, name):
            properties[name]["description"] = doc_desc

    # __agent_hint__ 附加到 description
    desc = fn.__doc__.split("\n")[0] if fn.__doc__ else ""
    if hint := getattr(fn, "__agent_hint__", None):
        desc += f"\n\nNOTE: {hint}"

    return {
        "type": "function",
        "function": {
            "name": fn.__name__,
            "description": desc,
            "parameters": {"type": "object", "properties": properties, ...}
        }
    }
```

### 7.3 优先级与冲突解决

```python
_tools: dict[str, tuple[Callable, int]] = {}  # name -> (fn, priority)

def register_tool(fn: Callable, priority: int):
    name = fn.__name__
    if name in _tools and _tools[name][1] >= priority:
        logger.warning("Tool %s (priority=%d) shadowed by existing (priority=%d)", ...)
        return  # 高优先级已存在，跳过
    _tools[name] = (fn, priority)
```

同名冲突时保留高优先级者，并记录 warning。`list_tools()` 工具让 Agent 可自查当前工具集。

### 7.4 内部参数注入（_ 前缀约定）

| 参数名 | 注入值 | 用途 |
|--------|--------|------|
| `_workspace` | 当前工作目录（Path） | 文件读写路径 |
| `_cfg` | 全局配置字典 | API Key、默认参数等 |
| `_llm` | LLM 客户端实例 | 需要调用 LLM 的工具（如 llm_calibrate） |
| `_ui` | UI 实例 | 进度显示 |

`_` 前缀参数不出现在 Function Calling Schema 中，对 LLM 透明。

---

## 8. 工具自描述协议（__agent_hint__）

### 8.1 设计动机

LLM 对工具的隐性约束（API 输出格式、参数依赖关系、最常见错误）有两种处理方式：
- **硬编码进提示词**：随工具增加持续膨胀，工具改了提示词可能没改，产生脱节
- **让 LLM 自行推断**：反复失败、循环、浪费 token

`__agent_hint__` 将约束知识与工具代码绑定：

```python
def calibrate_model(...): ...

calibrate_model.__agent_hint__ = (
    "Returns calibration_dir and best_params — NO metrics (NSE/KGE). "
    "Must call evaluate_model(calibration_dir=...) separately to get metrics. "
    "After calibration succeeds, save_basin_profile is called automatically."
)
```

### 8.2 三类自描述内容

1. **必填约束**：type hint 表达不了的隐性规则（如 `t_range` 缺省会触发全量缓存重建）
2. **输出->输入关系**：`calibrate_model.calibration_dir` -> `evaluate_model(calibration_dir=...)`
3. **最常见错误的一句话预防**：如 "After 3 failures, use ask_user instead of regenerating"

### 8.3 与 MCP 的关系

`__agent_hint__` 是同进程内的轻量实现，设计哲学与 MCP（Model Context Protocol）完全一致——
工具服务器声明自身 capability，客户端（LLM）据此正确调用。区别：`__agent_hint__` 同进程，
MCP 跨进程/跨网络。若未来接入外部水文服务，MCP server 是自然扩展路径。

---

## 9. 记忆系统（memory.py）

### 9.1 三层记忆

```
会话内记忆     messages[]                    当前对话上下文（随会话结束清空）
跨会话知识     <workspace>/MEMORY.md         Agent 自主维护的通用经验
流域档案       <workspace>/basin_profiles/   流域专属率定历史（按 basin_id 索引）
```

### 9.2 流域档案（Basin Profiles）

每次 calibrate_model 或 llm_calibrate 成功后，由 PostToolUse hook 自动调用 `save_basin_profile`：

```json
{
  "basin_id": "12025000",
  "records": [
    {
      "model": "gr4j",
      "algorithm": "SCE_UA",
      "train_nse": 0.783,
      "test_nse": 0.747,
      "best_params": {"x1": 1180.6, "x2": -3.94, "x3": 36.9, "x4": 1.22},
      "calibration_dir": "results/gr4j_12025000",
      "calibrated_at": "2026-03-07T14:23:11"
    }
  ]
}
```

下次对同一流域发起查询时，历史记录自动注入 system prompt：
- LLM 可用历史参数作为先验初始化
- 识别参数是否与历史差异异常（对抗先验检测）
- 对比多次结果，判断是否已收敛

### 9.3 MEMORY.md 跨会话知识

Agent 在每次对话结束时可自主写入 `MEMORY.md`：错误解决方案、数据路径发现、用户偏好等。
下次会话时自动读取并注入 system prompt（截断到 4000 字符）。

### 9.4 错误知识库（error_kb.py）

`record_error_solution(error, solution)` 工具将错误-解决方案对持久化到
`<workspace>/error_solutions.json`，形成可检索的本地知识库。

---

## 10. 上下文控制（截断 + 压缩）

### 10.1 工具结果截断（context_utils.py）

```python
def truncate_tool_result(tool_name: str, result: dict) -> str:
    # 字段级 8K 截断
    for key in result:
        if isinstance(result[key], str) and len(result[key]) > 8192:
            result[key] = result[key][:8192] + "...(truncated)"
    # 整体 16K 上限
    text = json.dumps(result, ensure_ascii=False)
    if len(text) > 16384:
        text = text[:16384] + "...(truncated)"
    return text
```

防止 `run_code` stdout / `read_file` 等大输出填满上下文（历史案例：33M 字符触发 API 429）。

### 10.2 对话历史压缩（_maybe_compress_history）

```python
def _maybe_compress_history(messages: list) -> list:
    estimated_tokens = sum(len(m["content"]) // 4 for m in messages)
    if estimated_tokens < 60_000:
        return messages

    # 保留：system 消息 + 原始用户查询 + 最近 4 条
    preserved = [messages[0], messages[1]] + messages[-4:]
    middle = messages[2:-4]

    # 用 LLM 压缩中间历史
    summary = self.llm.summarize(middle)
    return preserved[:2] + [{"role": "user", "content": f"[历史摘要]\n{summary}"}] + preserved[2:]
```

**已知局限**：一次性压缩；压缩后摘要仍会增长。30+ 轮极端长任务中仍可能超限。
分层记忆（工作记忆 + 短期摘要 + 长期档案）是未来方向。

### 10.3 任务状态外化

`task_state.json` 持久化任务列表到磁盘，`get_pending_tasks()` 每轮只返回摘要（不累积在 messages 中）。
CC-2 每轮注入一次 task_note，替代多次重复的任务查询。

---

## 11. LLM 客户端（llm.py）

### 11.1 双模式支持

**Mode A：原生 Function Calling**（DeepSeek / Qwen / OpenAI 等）

```python
response = client.chat.completions.create(
    model=model_name,
    messages=messages,
    tools=tool_schemas,           # OpenAI-compatible format
    tool_choice="auto",
)
# response.choices[0].message.tool_calls -> 结构化工具调用列表
```

**Mode B：Prompt 降级**（Ollama 等本地模型）

```python
# 将工具描述注入 system prompt：
# "Available tools:\n{tool_schemas_as_text}\n\nTo call a tool, output:\n<tool_call>...</tool_call>"
# 解析 LLM 返回文本中的 <tool_call> JSON 块
```

首次调用时尝试 Function Calling；若失败（API 不支持 tools 参数）自动降级并记录。

### 11.2 模型配置

通过 `configs/definitions_private.py` 配置：

```python
OPENAI_API_KEY = "sk-..."
OPENAI_BASE_URL = "https://api.deepseek.com/v1"  # 或 qwen / ollama
MODEL_NAME = "deepseek-chat"                       # 或 qwen-max / qwen-plus
```

温度默认 0.1（确定性优先），代码生成场景适当提高至 0.2。

---

## 12. 任务状态注入（CC-2）

**背景**：在批量任务中，Agent 容易在多轮工具调用后遗忘整体进度（"计划漂移"问题）。

**实现**：在每个 turn 的所有工具结果消息之后，注入一次 `[任务状态]` user 消息：

```python
def _get_task_status_note(self) -> str:
    from hydroagent.utils.task_state import TaskState, PENDING, RUNNING
    try:
        ts = TaskState(self.workspace)
        if not ts.all_tasks():
            return ""
        pending = ts.pending_tasks()
        running = [t for t in ts.all_tasks() if t["status"] == RUNNING]
        if not pending and not running:
            return ""
        return f"[任务状态]\n{ts.summary()}"
    except Exception:
        return ""
```

**注入时机的关键约束**：必须在 ALL tool 消息之后（作为 user 消息），不能插在相邻 tool 消息之间，
否则违反 API message ordering 要求（assistant -> tool... -> user 的顺序）。

---

## 13. PostToolUse Hook 系统（CC-4）

**背景**：原来 `_execute_tool` 有一个 if-chain 处理特殊工具的后续操作（保存档案、刷新注册表等），
随工具增多会持续膨胀。

**实现**：声明式 hook 注册表，解耦副作用逻辑：

```python
class HydroAgent:
    def __init__(self, ...):
        self._post_tool_hooks: dict[str, list] = {}
        self._register_builtin_post_hooks()

    def register_post_hook(self, tool_name: str, fn: Callable) -> None:
        """公开 API：第三方 Skill 可注册自定义 hook"""
        self._post_tool_hooks.setdefault(tool_name, []).append(fn)

    def _register_builtin_post_hooks(self):
        # 率定成功后自动保存流域档案
        for tool in ("calibrate_model", "llm_calibrate"):
            self.register_post_hook(tool, self._hook_save_basin_profile)
        # 任务状态变更时刷新 UI
        for tool in ("create_task_list", "update_task", "add_task"):
            self.register_post_hook(tool, self._hook_task_progress)
        # 新 Skill/Adapter 生成后重新扫描
        self.register_post_hook("create_skill", self._hook_refresh_registries)
        self.register_post_hook("create_adapter", self._hook_reload_adapters)
```

Hook 函数签名：`fn(tool_name: str, arguments: dict, result: dict) -> None`

**扩展性**：第三方 Skill 加载后可调用 `agent.register_post_hook(...)` 注册自定义后处理逻辑，
不需要修改 agent.py。

---

## 14. 子代理系统（AgentRegistry + spawn_agent，CC-3）

**背景**：批量任务中，让主代理处理所有流域的全程上下文会导致历史过长。
将每个单流域任务委派给独立的子代理实例，实现上下文隔离。

### 14.1 AgentRegistry（agents/__init__.py）

```python
class AgentRegistry:
    """扫描并管理子代理定义文件（.md 格式）"""

    BUILTIN_DIR = Path(__file__).parent  # hydroagent/agents/
    PROJECT_DIR_NAME = ".hydroagent/agents"  # <workspace>/.hydroagent/agents/

    def __init__(self, workspace: Path | None = None):
        self._agents: dict[str, AgentDef] = {}
        self._scan(self.BUILTIN_DIR)
        if workspace:
            self._scan(workspace / self.PROJECT_DIR_NAME)

    def get(self, name: str) -> AgentDef | None: ...
    def list_names(self) -> list[str]: ...
    def available_agents_prompt(self) -> str:
        """格式化为注入 system prompt 的紧凑列表"""
        lines = [f"  - {a['name']}: {a['description']}" for a in self._agents.values()]
        return "Available subagents (use spawn_agent to delegate):\n" + "\n".join(lines)
```

### 14.2 代理定义格式（.md with YAML frontmatter）

```markdown
---
name: calibrate-worker
description: 执行单个流域的完整率定-评估-可视化流程
tools: [calibrate_model, evaluate_model, visualize, save_basin_profile, validate_basin, inspect_dir, read_file, observe]
prompt_mode: minimal
max_turns: 12
---
你是一个专注的水文模型率定工作者。每次只处理一个（流域, 模型）组合。

工作流：
1. 调用 calibrate_model 完成率定（算法优先用 SCE_UA）
2. 调用 evaluate_model 评估训练期和测试期 NSE
3. 可选：调用 visualize 生成过程线图
4. 返回结构化结论：basin_id, model, train_NSE, test_NSE, calibration_dir
```

### 14.3 spawn_agent 工具（tools/spawn_agent.py）

```python
_SPAWN_DEPTH: int = 0
_MAX_SPAWN_DEPTH: int = 1  # 防止子代理递归生成子代理

def spawn_agent(name: str, task: str, _workspace, _cfg, _ui) -> dict:
    global _SPAWN_DEPTH
    if _SPAWN_DEPTH >= _MAX_SPAWN_DEPTH:
        return {"success": False, "error": "Max depth reached"}

    registry = AgentRegistry(_workspace)
    agent_def = registry.get(name)

    sub = HydroAgent(workspace=_workspace, config_override=_cfg, ui=_ui,
                    prompt_mode=agent_def["prompt_mode"])
    sub.max_turns = agent_def["max_turns"]

    # 应用工具白名单
    if allowed := agent_def.get("tools"):
        sub.tools = {k: v for k, v in sub.tools.items() if k in set(allowed)}

    # 应用自定义系统提示
    if custom_prompt := agent_def.get("system_prompt", "").strip():
        sub._subagent_system_prompt = custom_prompt

    _SPAWN_DEPTH += 1
    try:
        result = sub.run(task)
    finally:
        _SPAWN_DEPTH -= 1

    return {"success": True, "result": result, "agent": name}
```

**懒加载（避免循环导入）**：`agent.py` 导入 `tools/`，`spawn_agent.py` 需要导入 `agent.py`，
形成循环。解决方案：`spawn_agent.py` 中的 import 移入函数体内（运行时而非模块加载时执行）。

### 14.4 内置子代理

| 文件 | 名称 | 用途 |
|------|------|------|
| `agents/calibrate_worker.md` | calibrate-worker | 单流域完整率定-评估-可视化，批量任务内循环 |
| `agents/basin_explorer.md` | basin-explorer | 流域数据验证与探索，只读操作 |

---

## 15. 插件注册表（plugin_registry.py）

### 15.1 两层 plugins.json

```
全局：~/.hydroagent/plugins.json     -- 用户级，所有工作区共享
本地：<workspace>/.hydroagent/plugins.json -- 项目级，本地覆盖全局
```

### 15.2 三种插件类型

| 类型 | 示例 | 接入方式 |
|------|------|---------|
| `pip` | hydromodel | pip install + 内置 adapter |
| `local_dir` | D:/project/autohydro/ | sys.path 注入 + hydroagent_adapter.py |
| `single_file` | D:/scripts/fdc.py | 动态 import + 函数级注册为工具 |

### 15.3 本地目录包约定

在包根目录放 `hydroagent_adapter.py`，继承 `PackageAdapter`：

```python
class Adapter(PackageAdapter):
    name = "autohydro"
    priority = 12

    def can_handle(self, data_source, model_name):
        return model_name in ("autohydro", "mean_field")

    def supported_operations(self):
        return ["derive_formula"]
```

`add_local_package(path, name, description)` 元工具完成：
1. 写入本地 plugins.json
2. 注入 sys.path
3. 调用 reload_adapters() 使其立即生效

### 15.4 单文件工具

```python
# D:/scripts/fdc.py
def calculate_fdc(basin_id: str, data_dir: str) -> dict:
    """计算流量历时曲线 (FDC)"""
    ...
```

`add_local_tool(path)` 动态 import 后将所有公开函数注册为工具（priority=5）。

---

## 16. 界面层（interface/）

### 16.1 模块结构

```
interface/
├── cli.py          # CLI 入口 + 交互 REPL（斜杠命令）
├── ui.py           # Rich 终端 UI（user / dev 两种模式）
├── server.py       # FastAPI + WebSocket 服务
└── static/         # Web 前端（模块化 ES5）
    ├── index.html  # 入口，v=27
    ├── style.css   # 全局样式
    ├── utils.js    # 常量、工具函数（marked.js、toast）
    ├── chat.js     # 聊天消息渲染、工具卡片、流式输出
    ├── sessions.js # 会话管理（新建/切换/重命名/删除）
    ├── panels.js   # 侧边面板（工具/技能/水文包/任务）
    ├── toolbar.js  # 顶部工具栏（模型选择/菜单）
    └── app.js      # 主入口（组件组装、WebSocket、斜杠命令）
```

### 16.2 Web UI 架构

前端从单文件（1986 行 app.js）拆分为 6 个模块，依赖顺序加载：

```
utils.js -> chat.js -> sessions.js -> panels.js -> toolbar.js -> app.js
```

WebSocket 协议（server.py <-> app.js）：

```json
// 客户端 -> 服务端
{"type": "query", "message": "...", "session_id": "..."}

// 服务端 -> 客户端（流式）
{"type": "token", "content": "..."}
{"type": "tool_start", "name": "calibrate_model", "arguments": {...}}
{"type": "tool_end", "name": "calibrate_model", "result": {...}}
{"type": "done", "message": "..."}
{"type": "error", "message": "..."}
```

### 16.3 API 路由（server.py）

```
GET  /api/packages         -- 列出已安装 pip 适配器
GET  /api/plugins          -- 列出 local_dir / single_file 插件
POST /api/plugins          -- 注册新本地插件
PATCH /api/plugins/{name}  -- 启用/禁用插件
DELETE /api/plugins/{name} -- 移除插件
POST /api/plugins/{name}/reload -- 热重载插件

GET  /api/skills           -- 列出所有 Skill
GET  /api/tools            -- 列出所有工具（含优先级）
GET  /api/sessions         -- 列出会话列表
POST /api/sessions         -- 新建会话
GET  /api/tasks            -- 获取当前任务列表
```

---

## 17. 认知记忆架构（三类记忆模型）

HydroClaw 的知识组织参照认知科学的三类长期记忆模型：

```
                    ┌─────────────────────────────────┐
                    │         system.md               │
                    │   与生俱来的原则与常识底座        │
                    │  NSE阈值/默认值/工具规则/身份定位 │
                    └──────────────┬──────────────────┘
                                   │ 始终在（每次对话）
                                   ▼
用户提问 ──────────────────► Agent 推理（ReAct Loop）
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
         程序性记忆           语义记忆              情节记忆
     skill 索引 in prompt    knowledge/          memory/ + basin_profiles
     完整内容 read_file       按需 read_file       任务前 search_memory
     「我会做什么」          「遇事查手册」         任务后写入
```

### 三类记忆对照表

| 记忆类型 | 认知科学对应 | 载体 | 触发方式 | 内容 |
|---------|------------|------|---------|------|
| **程序性** | 骑自行车——不需要有意识提取 | `skills/*/skill.md` | 任务开始时 read_file | 操作流程、决策规则、止损条件 |
| **语义性** | 事实知识——需要时查阅 | `knowledge/*.md` | 遇到问题主动 read_file | 报错诊断、参数含义、数据集说明 |
| **情节性** | 个人经历——跨会话积累 | `memory/` + `basin_profiles/` | 任务前 search_memory / 任务后写入 | 历史率定记录、用户偏好、流域档案 |

### 各类记忆在 `_build_system_prompt` 中的位置

```
Section 1   system.md      — 常识底座（与生俱来，始终注入）
Section 2   skill 路径列表 — 程序性记忆索引（始终注入；内容按需 read_file）
Section 4   knowledge/     — 语义记忆（v2.8 起：不再自动注入，Agent 按需 read_file）
Section 5   basin_profiles + MEMORY.md — 情节记忆摘要（full 模式注入）
```

> **v2.8 变更**：`knowledge/` 不再通过 `_load_domain_knowledge()` 自动注入。
> Agent 在遇到报错或不确定情况时，遵循 skill.md 的指引，主动调用 `read_file` 查阅。
> 优势：消除截断问题（原先硬截断 2000 字符）；零冗余注入；知识质量更高。

---

### system prompt 设计质量标准

参照 Cursor / Claude Code / Devin 等顶级 Agent 系统提示分析，优质 system prompt 应包含：

| 模块 | 内容要求 | HydroClaw 现状 |
|------|---------|--------------|
| **角色与边界** | 明确是什么、不是什么、能做什么不能做什么 | ✅ system.md 首段 |
| **工具决策规则** | 何时用哪个工具，不只是列清单 | ✅ 各场景工具序列表 |
| **记忆架构说明** | 告知 Agent 有哪几类记忆及访问方式 | ✅ search_memory 使用规则 |
| **预算自治边界** | 明确何时停止、何时上报、何时询问用户 | ✅ ask_user / Stop Conditions |
| **错误升级路径** | 失败后的决策树，不是"重试三次" | ✅ Failure Recovery 在 skill.md |
| **反思校验** | 输出前检查结果是否合理 | ⚠️ 部分（calibrate_model 无指标提醒存在）|
| **安全约束** | 不可绕过的底线，写入 Identity 而非条件 | ✅ 身份定位段 |
| **输出格式** | 语言、结构、禁止的表达方式 | ✅ 响应语言 + 工具调用原则 |

**当前 system.md 相对薄弱的地方：**
- 缺少对三类记忆的显式说明（Agent 靠 search_memory 的用法示例隐式理解）
- 缺少"反思校验"的明确指令（如"给出最终结论前，先验证指标是否合理"）
- 工具预算约束（最多调用几次同一工具）分散在各处，不够集中

---

## 17.5 知识注入顺序总览

```
用户查询："帮我用 GR4J 率定流域 12025000"
         |
         v
[agent._build_system_prompt(query)]
  |
  +-- [1] system.md（角色、工具风格、观测原则）           <- 身份层
  |
  +-- [1.5] policy/*.md（行为约束，上限 2K 字符）         <- 行为层 [v2.7 新增]
  |         agent_behavior / calibration_policy /
  |         tool_safety_policy / reporting_policy
  |
  +-- [2] 匹配 Skill 说明书路径列表（calibration/skill.md）  <- 技能层
  |       -> LLM 按需调用 read_file 读取详情（CC-1 按需注入）
  |
  +-- [2.5] 可用子代理列表（calibrate-worker, basin-explorer）
  |
  +-- [3] 适配器包文档（hydromodel.md, hydrodatasource.md）
  |
  +-- [4] 领域知识（model_parameters.md + failure_modes.md）  <- 知识层
  |
  +-- [5] 流域档案（basin_profiles/12025000.json，如有历史记录）  <- 记忆层
           + MEMORY.md（跨会话通用知识摘要）
  |
  v
[LLM 推理 + 工具调用循环]
  |
  +-- 每轮工具调用后：
      +-- PostToolUse hooks（自动保存档案、刷新注册表等）
      +-- [CC-2] 注入 task_note（[任务状态] 摘要，如有活跃任务）
      +-- _maybe_compress_history（估算 token > 60K 时触发）
```

---

## 18. 目录结构（v2.7 完整版）

```
hydroagent/
├── agent.py               # Agentic Loop 核心（ReAct + CC-2/CC-4）
├── llm.py                 # LLM 客户端（Function Calling + Prompt 降级）
├── memory.py              # 三层记忆（会话/MEMORY.md/流域档案）
├── config.py              # 配置管理
├── skill_registry.py      # Skill 自动扫描与关键词匹配
├── skill_states.py        # Skill 生命周期状态管理
├── __main__.py            # python -m hydroagent 入口
│
├── adapters/              # PackageAdapter 插件层（v2.5）
│   ├── __init__.py        # reload_adapters() + get_adapter() + get_all_skill_docs()
│   ├── base.py            # PackageAdapter 抽象接口
│   ├── hydromodel/
│   │   ├── adapter.py     # HydromodelAdapter（priority=10）
│   │   └── skills/hydromodel.md
│   ├── hydrodatasource/
│   │   ├── adapter.py     # HydrodatasourceAdapter（priority=15）
│   │   └── skills/hydrodatasource.md
│   └── generic/
│       └── adapter.py     # GenericAdapter（priority=0，兜底）
│
├── policy/                # 行为约束层（v2.7）
│   ├── agent_behavior.md  # Always/Never/When uncertain 通用约束
│   ├── calibration_policy.md  # 率定顺序与边界规则
│   ├── tool_safety_policy.md  # 高副作用工具约束
│   └── reporting_policy.md    # 报告输出规范
│
├── agents/                # 子代理定义（v2.6，CC-3）
│   ├── __init__.py        # AgentRegistry（扫描内置 + 项目级 agents/）
│   ├── calibrate_worker.md
│   └── basin_explorer.md
│
├── knowledge/             # 领域知识库（按关键词注入 LLM 上下文）
│   ├── model_parameters.md       # 参数物理含义与典型范围
│   ├── calibration_guide.md      # 率定经验指南
│   ├── datasets.md               # 数据集说明
│   └── failure_modes.md          # 水文失败模式诊断手册（v2.7）
│
├── skills/                # Skill 包（工作流说明书 + 工具实现）
│   ├── system.md          # 系统基础 prompt
│   ├── calibration/
│   │   ├── skill.md       # keywords: [calibrat, 率定]
│   │   └── calibrate.py   # calibrate_model() priority=10
│   ├── llm_calibration/
│   │   ├── skill.md
│   │   └── llm_calibrate.py
│   ├── evaluation/
│   │   ├── skill.md
│   │   └── evaluate.py
│   ├── visualization/
│   │   ├── skill.md
│   │   └── visualize.py
│   ├── simulation/
│   │   └── simulate.py    # run_simulation()
│   ├── code_analysis/
│   │   ├── skill.md
│   │   ├── generate_code.py
│   │   └── run_code.py
│   ├── model_comparison/
│   │   ├── skill.md
│   │   └── compare_models.py
│   ├── batch_calibration/
│   │   ├── skill.md
│   │   └── batch_calibrate.py
│   ├── hydrodatasource/   # 自定义数据集工具
│   │   └── dataset_tools.py  # list_basins / read_dataset / convert_dataset_to_nc
│   └── hydrodataset/      # 公开数据集工具
│       └── hydrodataset_tools.py
│
├── tools/                 # 核心基础工具（priority=20）
│   ├── __init__.py        # 工具发现引擎（fn_to_schema + 优先级注册）
│   ├── validate.py        # validate_basin()
│   ├── simulate.py        # run_simulation()
│   ├── observe.py         # read_file() / inspect_dir()
│   ├── task_tools.py      # create_task_list / get_pending_tasks / update_task / add_task
│   ├── memory_tools.py    # search_memory / save_basin_profile / record_error_solution
│   ├── ask_user.py        # ask_user()
│   ├── create_skill.py    # 元工具：动态生成 Skill 包
│   ├── create_adapter.py  # 元工具：动态生成 PackageAdapter 骨架
│   ├── install_package.py # 受控包安装（需用户授权）
│   ├── register_package.py# LLM 分析 PyPI 自动生成适配器
│   ├── add_local_package.py # 注册本地目录包（写 plugins.json + reload）
│   ├── add_local_tool.py  # 注册单文件工具（动态 import + 注册）
│   └── spawn_agent.py     # 委派子代理（CC-3）
│
├── utils/                 # 辅助模块
│   ├── context_utils.py   # truncate_tool_result()（字段级 8K + 整体 16K）
│   ├── task_state.py      # TaskState（任务状态持久化到 task_state.json）
│   ├── plugin_registry.py # PluginRegistry（读写 plugins.json，合并全局+本地）
│   ├── basin_validator.py # 流域数据验证工具（validate_basin 的实现后端）
│   ├── error_kb.py        # 错误知识库
│   └── setup_wizard.py    # 首次启动配置向导
│
└── interface/             # 用户界面层
    ├── cli.py             # CLI 入口 + 交互 REPL
    ├── ui.py              # Rich 终端 UI（user / dev 两种模式）
    ├── server.py          # FastAPI + WebSocket 服务
    └── static/            # Web 前端（6 模块，v=27）

llms.txt                   # 包级可发现性声明（v2.7，供 smolagents/LangChain 读取）
```

---

## 19. 与 HydroAgent 旧版对比

| 维度 | HydroAgent v6.0 | HydroAgent v2.6 |
|------|-----------------|----------------|
| 架构 | 5 Agent + Orchestrator 状态机 | 单一 Agentic Loop（+子代理系统） |
| 代码量 | ~27,000 行 | ~5,500 行 |
| 工作流编排 | 硬编码状态转换图 | LLM 自主推理 |
| 工具选择 | if-else 路由（960 行） | LLM Function Calling |
| 知识注入 | 无 | 六段式系统提示（四层知识体系） |
| 跨会话记忆 | 无 | 流域档案 + MEMORY.md 自动积累 |
| 工具扩展 | 改 Agent + 注册 + 路由 | create_skill 运行时生成 |
| 包扩展 | 改核心代码 | PackageAdapter + add_local_package |
| 批量任务 | Orchestrator 硬分配 | create_task_list + spawn_agent |
| 上下文管理 | 无 | 截断 + 压缩 + 任务状态外化 |
| 后处理副作用 | if-chain（随工具增多膨胀） | PostToolUse hook 注册表 |
| 子代理 | 固定 5 个 Agent | 声明式 .md 定义，按需创建 |

---

*本文档随代码同步维护。如发现描述与实际代码不符，以代码为准，并更新此文档。*
