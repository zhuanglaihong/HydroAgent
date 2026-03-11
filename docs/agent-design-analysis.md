# Agent 设计分析：OpenClaw vs HydroClaw

> 日期：2026-03-10
> 来源：对比分析 D:\project\Agent\openclaw 源码与 HydroClaw 当前实现
> 目的：理解"agent 像呆子"的根本原因，制定改进计划

---

## 一、OpenClaw 设计理念

OpenClaw 是一个生产级 agentic 系统，其核心理念可以归结为三个词：

**主动、受约束、可观测。**

### 1.1 主动认知（Active Cognition）

OpenClaw 的 agent 不是被动接收信息的容器，而是主动决策的行为者。

最典型的体现在 Skill 的加载方式：

```
# OpenClaw system prompt 中写的是：
## Skills (mandatory)
- If exactly one skill applies: READ SKILL.md, then follow it
- If multiple apply: choose the most specific one
- Constraints: never read more than one skill upfront
```

Agent 看到这段话后，会**主动调用 `read` 工具读取 SKILL.md**。这是一个行为决策——agent 需要先判断"哪个 skill 适用"，再决定"读哪个文件"，才能获得工作流指导。

**认知意义**：agent 对自己"在做什么"有意识。它知道自己是在"看手册后行动"，而不是被动遵循注入的信息。

### 1.2 推理优先（Thinking Before Acting）

OpenClaw 原生支持 Extended Thinking：

```typescript
params.thinkLevel = "basic" | "deep"
// System Prompt 约束：
// ALL reasoning MUST be inside <think>...</think>
// Format: <think>...</think> then <final>...</final>
```

Agent 在调用任何工具之前，先在内部推理块中思考：
- 用户真正要什么？
- 哪个工具最合适？
- 上次出错的原因是什么？
- 当前方案有没有更好的替代？

这个 `<think>` 块对用户不可见，但决定了行动质量。**没有草稿纸的做题者，不是聪明，是鲁莽。**

### 1.3 单一权威来源（Single Source of Truth）

System prompt 由单一函数 `buildAgentSystemPrompt()` 构建（725行），优先级完全确定。工具描述、skill 列表、记忆规则、安全约束都在同一个地方统筹，不存在"两个文件说不同的话"的情况。

### 1.4 工具循环检测（Semantic Loop Detection）

OpenClaw 有 623 行专门的 `tool-loop-detection.ts`，检测的不只是"同一个工具被调用超过 N 次"，而是语义层面的循环：
- 同类工具反复调用（即使参数不同）
- 输出结果没有进展的循环
- Per-tool 自定义检测规则

### 1.5 主动记忆检索（Active Memory Retrieval）

OpenClaw 的记忆是工具化的：

```
# System prompt 中写的是：
## Memory Recall
Before answering re: prior work, decisions, dates, people:
  run memory_search on MEMORY.md
  use memory_get to pull needed lines
```

Agent 主动搜索记忆，而不是把所有历史都塞进 system prompt。这避免了"记忆太多反而干扰判断"的问题。

---

## 二、HydroClaw 当前设计与差距

### 2.1 被动信息接收（核心问题）

HydroClaw 的 skill 加载方式：

```python
# agent.py _build_context()
skill_contents = self.skill_registry.match(query)  # 关键词匹配
for skill_content in skill_contents:
    system_content += "\n\n" + skill_content        # 直接注入
```

Skill 内容在 agent 看到第一个字之前就已经注入进 system prompt 了。Agent 没有"决定看哪本手册"的过程，只是被动接收了一堆信息。

**后果**：
- System prompt 随着 skill 数量增多而膨胀
- 多个 skill 注入时，agent 不知道哪条规则优先
- 与 system.md 的全局规则容易产生矛盾（A05 案例就是典型）

### 2.2 无推理过程（直接行动）

HydroClaw 的 agent 直接输出 tool call：

```
用户查询 -> _build_context() -> llm.chat() -> tool call
```

中间没有任何"想一想"的步骤。遇到模糊情况（比如"找不到数据路径"），agent 的第一反应是立即行动（调用 inspect_dir），而不是先推理（我应该用 validate_basin 还是 inspect_dir？）。

### 2.3 指令分散，无优先级

HydroClaw 的指令来源：

| 文件 | 内容 | 优先级 |
|------|------|--------|
| `skills/system.md` | 全局工作原则、工具序列 | 未定义 |
| `skills/<name>/skill.md` | 专用任务流程 | 未定义 |
| `knowledge/*.md` | 领域参数知识 | 未定义 |

三处内容都直接注入 system prompt，没有明确的优先级规则。当它们发生矛盾时（如 A05 案例：system.md 说"代码生成跳过 validate_basin"，skill.md 说"先调用 validate_basin"），agent 无法判断听谁的。

### 2.4 工具循环检测过于简单

```python
# agent.py：仅检测同名工具的连续调用次数
_consecutive[tc.name] = _consecutive.get(tc.name, 0) + 1
if _consecutive[tc.name] > _MAX_CONSECUTIVE:  # 默认 5 次
    # 停止循环
```

`inspect_dir("path/a")` -> `inspect_dir("path/b")` -> `inspect_dir("path/c")` 这种"在找数据"的语义循环完全无法识别，因为每次参数都不同，计数器一直为 1。

### 2.5 记忆被动注入

```python
# agent.py：所有记忆内容直接加入 system prompt
memory = self.memory.load_knowledge()
system_content += "\n\n## Memory (from previous sessions)\n" + memory
```

记忆越积越多，system prompt 越来越大，对 agent 的干扰也越来越大。Agent 没有工具可以"主动查询我之前做过什么"，只能被动接收所有历史。

---

## 三、差距对比总表

| 设计维度 | OpenClaw | HydroClaw | 影响 |
|----------|----------|-----------|------|
| Skill 加载 | Agent 主动 read（行为） | 直接注入 system prompt（信息） | agent 有无认知主动性 |
| 推理过程 | Extended Thinking `<think>` | 无，直接 tool call | 工具选择质量 |
| 指令来源 | 单一构建函数，优先级确定 | 分散多文件，无优先级 | 指令冲突概率 |
| 工具循环检测 | 语义级，623行，per-tool规则 | 名称+计数，5次上限 | 能否识别"找数据"类循环 |
| 记忆使用 | 工具化（memory_search） | 全量注入 system prompt | 记忆干扰与信噪比 |
| 工具描述 | per-tool summary 注入 prompt | docstring 自动生成 schema | agent 是否知道何时用哪个工具 |

---

## 四、改进计划

改进分三个优先级，均在不重构核心 agent 的前提下进行。

### P1：解决指令冲突（立即可做）

**目标**：消除 system.md 与 skill.md 之间的矛盾，建立明确优先级。

**方式**：
- System.md 只写**全局硬约束**（不可违反的规则），如"inspect_dir 连续不超过 2 次"、"validate_basin 用于获取流域数据路径"
- Skill.md 写**场景专用流程**（在全局规则框架下的具体步骤）
- 在 system.md 顶部明确声明：**本文件规则优先于所有 skill 的流程建议**

**已做**：system.md 的 validate_basin/inspect_dir 矛盾已修复（2026-03-10）。

---

### P2：给 Agent 打草稿的地方（中期）

**目标**：在不换模型的前提下，引入结构化推理。

**方式 A（prompt 层面）**：在 system.md 加入显式推理格式要求：

```markdown
## 工具选择原则

在调用工具之前，先在回复中写一行推理说明：
"[推理] 我需要...，因此选择...工具，参数为..."
然后再调用工具。
```

**方式 B（模型层面）**：换用支持 thinking 的模型版本（DeepSeek R1、Qwen-thinking、Claude 3.7 Sonnet extended thinking），并在 `llm.py` 的请求中加入 `thinking` 参数。

---

### P3：Skill 改为主动加载（长期，论文 Phase 3）

**目标**：让 agent 主动决定"看哪本手册"，而不是被动接收所有注入的信息。

**设计方案**：

```
System prompt 中只包含：
- 可用 skill 列表（名称 + 一句话描述 + 路径）
- 规则："若任务匹配某 skill，先用 read_file 读取其 skill.md，再执行"

Skill.md 不再注入 system prompt。
```

**实现改动**：
1. `skill_registry.available_skills_prompt()` 只返回列表，不返回内容
2. `_build_context()` 不再调用 `skill_registry.match()`
3. `read_file` 工具需支持读取 skill.md（已支持）

**预期效果**：
- Agent 会主动 `read_file("hydroclaw/skills/calibration/skill.md")`
- System prompt 大幅缩短（去掉 skill 内容注入）
- Agent 对当前任务"用了哪个工作流"有明确意识

---

### 附：不打算改的部分

| 项目 | 原因 |
|------|------|
| Sub-agent 编排 | 论文聚焦单 Agentic Loop，不需要多 agent |
| 沙箱 | 实验环境可控，不需要 Docker 隔离 |
| 向量数据库记忆 | 当前流域档案数量少，文本记忆够用 |
| 插件钩子系统 | 过度工程化，不适合论文原型 |

---

## 五、论文写作建议

这次对比分析本身是好素材：

- **Section 3（系统设计）**：可以引用 OpenClaw 的 skill 主动加载设计，说明 HydroClaw 借鉴了其"工作流指引"理念，但针对水文领域简化为注入式（并分析取舍）
- **Section 5（讨论与局限）**：指令分散导致行为冲突（A05 案例）是真实局限，可以诚实写出，并指向 P3 作为未来工作
- **贡献点**：三层知识注入（skill + domain knowledge + basin profiles）是 HydroClaw 相对于通用 agentic 框架的领域创新，即使实现方式比 OpenClaw 简单
