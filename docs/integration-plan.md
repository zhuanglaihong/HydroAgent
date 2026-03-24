# HydroClaw 工程集成计划

> 版本：v2.0 | 日期：2026-03-23 | 状态：P0-P3 全部完成
>
> **与 `hydroclaw-research-plan.md` 的关系**：本文件是工程实施文档，聚焦代码架构和功能设计。
> 论文写作（实验设计、Related Work、创新点论述）见 `hydroclaw-research-plan.md`。

---

## 1. 背景与目标

HydroClaw v2.5 已建立 PackageAdapter 插件架构（五层模型：大脑-脊椎-四肢），可以通过 `adapters/*/adapter.py` 动态加载水文包。但存在以下工程缺口：

1. **外部包无法接入**：`reload_adapters()` 只扫描 `hydroclaw/adapters/` 包内目录，外部本地包（未上传 pip）或单 .py 文件完全无法注册
2. **Agent 智能层欠缺**：与 OpenClaw 对比，存在推理机械化、system prompt 静态、模型参数无感知等问题
3. **管理界面缺失**：CLI 无插件管理命令，Server 无本地包管理 API

**目标**：实现真正通用的包集成能力，让 Agent 能自适应地使用任意外部包。

---

## 2. 通用包插件系统

### 2.1 架构概览

```
用户的本地包（任意位置）
  ↓ add_local_package() / add_local_tool()
plugins.json（注册表）
  ↓ reload_adapters() 读取
sys.path 注入 + importlib 动态加载
  ↓
_adapters 列表（内置 + 外部，统一按 priority 排序）
  ↓
get_adapter() 路由 → Agent 调用
```

### 2.2 插件注册表（两层）

```
全局注册表  ~/.hydroclaw/plugins.json    — 用户级，所有工作空间共享
本地注册表  <workspace>/.hydroclaw/plugins.json — 项目级，本地覆盖全局同名条目
```

注册表条目格式：
```json
{
  "name": "autohydro",
  "type": "local_dir",
  "path": "D:/project/Agent/watershed_hydrology",
  "adapter_path": "D:/project/Agent/watershed_hydrology/hydroclaw_adapter.py",
  "enabled": true,
  "description": "水文平均场理论自动推导产流公式",
  "added_at": "2026-03-22T10:00:00"
}
```

### 2.3 三种包类型

| 类型 | 示例 | 接入文件 | 注册方式 |
|------|------|---------|---------|
| `pip` | hydromodel | 内置 adapter | 内置，无需注册 |
| `local_dir` | D:/project/autohydro/ | `hydroclaw_adapter.py`（包根目录） | `add_local_package(path)` |
| `single_file` | D:/scripts/fdc.py | 文件本身（含公开函数） | `add_local_tool(path)` |

### 2.4 外部包约定（hydroclaw_adapter.py）

外部本地目录包在根目录放 `hydroclaw_adapter.py`，声明适配器类：

```python
# <package_root>/hydroclaw_adapter.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))  # 确保包本身可 import

from hydroclaw.adapters.base import PackageAdapter

class Adapter(PackageAdapter):
    name = "my_package"
    priority = 5  # 5=默认外部，12=高于 hydromodel(10)，低于 hydrodatasource(15)

    def can_handle(self, data_source: str, model_name: str) -> bool:
        return model_name == "my_package"

    def supported_operations(self) -> list[str]:
        return ["my_operation"]

    def my_operation(self, workspace, **kw) -> dict:
        try:
            import my_package
            # ... 实际调用
            return {"success": True, ...}
        except ImportError:
            return {"success": False, "error": "my_package not installed"}
```

可选：在 `hydroclaw_adapter_skills/` 目录放 `skill.md`，Agent 会自动注入。若无该目录，HydroClaw 自动生成最小化文档（从 `supported_operations()` + docstring 生成）。

### 2.5 单文件工具约定

单 .py 文件无需 Adapter，直接写普通公开函数即可：

```python
# D:/scripts/fdc.py

def calculate_fdc(basin_id: str, data_dir: str) -> dict:
    """计算流量历时曲线 (Flow Duration Curve)。

    Args:
        basin_id: 8位流域ID
        data_dir: 数据目录路径

    Returns:
        {"exceedance_prob": [...], "flow_values": [...], "plot_path": str}
    """
    ...
```

`add_local_tool()` 自动发现文件中所有公开函数（不以 `_` 开头），注册为 HydroClaw 工具，优先级 `PRIORITY_DYNAMIC=5`。

### 2.6 关键文件变更

| 文件 | 操作 | 说明 |
|------|------|------|
| `hydroclaw/utils/plugin_registry.py` | 新建 | PluginRegistry 类：读写 plugins.json，合并全局+本地 |
| `hydroclaw/adapters/__init__.py` | 修改 | `reload_adapters(workspace)` 增加外部插件扫描 |
| `hydroclaw/tools/__init__.py` | 修改 | `discover_tools()` 增加 single_file 扫描 |
| `hydroclaw/tools/add_local_package.py` | 新建 | 元工具：注册本地目录包 |
| `hydroclaw/tools/add_local_tool.py` | 新建 | 元工具：注册单文件工具 |
| `hydroclaw/interface/cli.py` | 修改 | `/plugin` 斜杠命令 + `--plugin-add` 参数 |
| `hydroclaw/interface/server.py` | 修改 | `/api/plugins` REST 路由组 |

### 2.7 CLI 插件管理命令

交互模式中新增斜杠命令：

```
/plugin list                    列出所有插件（内置 + 外部，含状态）
/plugin add <path>              注册本地目录包或 .py 文件
/plugin enable <name>           启用已禁用的插件
/plugin disable <name>          临时禁用（不删除注册条目）
/plugin remove <name>           从注册表删除
/plugin reload                  手动触发 reload_adapters()
```

### 2.8 Server API

```
GET    /api/plugins              列出所有已注册插件
POST   /api/plugins              注册新插件 {"path": "...", "name": "...", "type": "local_dir"}
PATCH  /api/plugins/{name}       启用/禁用 {"enabled": true/false}
DELETE /api/plugins/{name}       删除注册条目
POST   /api/plugins/{name}/reload 单个插件热重载
```

---

## 3. autohydro 接入示例

**autohydro 包**（`D:/project/Agent/watershed_hydrology/`）是水文平均场理论 PoC：
- 核心：`WatershedModelingPipeline.run(watershed_attrs, P_obs, Q_obs, s0_obs)`
- 功能：LLM 推荐模型 → SymPy 符号推导 → 参数优化 → 报告生成
- 依赖：sympy, scipy, anthropic/openai

**接入步骤**：
1. 在 `D:/project/Agent/watershed_hydrology/` 创建 `hydroclaw_adapter.py`（见 2.4 约定）
2. Agent 调用：`add_local_package("D:/project/Agent/watershed_hydrology")`
3. 验证：`/plugin list` 看到 `autohydro`；调用 `derive_runoff_formula(...)` 工具

**路由规则**：
- `can_handle`: `model_name in ("autohydro", "mean_field")`
- `priority = 12`（高于 hydromodel=10，低于 hydrodatasource=15）

---

## 4. Agent 智能升级路线

### 4.1 与 OpenClaw 对比诊断

经代码对比分析，HydroClaw 与 OpenClaw 的"灵魂差距"主要在：

| 维度 | OpenClaw | HydroClaw（改进前） | 状态 |
|------|----------|-------------------|------|
| 推理表达 | `<think>...</think>` 5级深度，模型级 thinking tokens | 每次强制 `[思考]` 单行注释 | ✅ P0 已修复 |
| 工具叙述 | 复杂/敏感时才叙述，默认直接调用 | 每次都要写 `[思考]` 前缀 | ✅ P0 已修复 |
| 身份约束 | Constitutional AI 段落（no self-preservation...） | 无显式约束 | ✅ P0 已修复 |
| 模型感知 | 自动检测推理/对话型，动态调整参数 | temperature 固定 0.1，所有模型同等对待 | ✅ P1 已完成 |
| 原生 thinking | 推理型模型传 thinking 参数，解析 reasoning_content | 无 | ✅ P1 已完成 |
| Skill 加载 | 探索式选择，"选最匹配的一个读" | "严格按照工作流执行，不要跳步骤" | ✅ P0 已修复 |
| System prompt | 模块化动态生成（10+ section 函数） | 静态 system.md | ✅ P2 已完成 |
| Prompt 模式 | full / minimal 两种模式（主 Agent vs 子任务） | 无 | ✅ P3 已完成 |
| 上下文截断 | 结构化分层 + 警告标记 | 线性 `text[:N] + "(truncated)"` | ✅ P2 已完成 |

### 4.2 P1：模型感知层（hydroclaw/llm.py）✅

新增 `model_profile(model_name)` 和 `detect_reasoning_style(model_name)` 两个函数：

```python
# 三种推理风格自动检测
detect_reasoning_style("deepseek-r1")    # -> "deepseek_r1"   解析 <think> 标签
detect_reasoning_style("qwq-32b")        # -> "qwen_thinking" extra_body={"enable_thinking":True}
detect_reasoning_style("o3-mini")        # -> "openai_reasoning" reasoning_effort="high"
detect_reasoning_style("deepseek-v3")    # -> None            标准对话模型
```

`LLMClient.__init__()` 自动检测 `_reasoning_style` 并设置：
- `deepseek_r1`：API 调用无额外参数，响应后解析 `<think>...</think>` 标签提取 `thinking`
- `qwen_thinking`：传 `extra_body={"enable_thinking": True}`，读 `msg.reasoning_content`
- `openai_reasoning`：传 `reasoning_effort="high"`，省略 `temperature`

`LLMResponse` 新增 `thinking: str | None` 字段，`ui.on_thought()` 显示推理过程。

可在 config 用 `"reasoning_style": "none"` 强制禁用。

### 4.3 P2：System Prompt 模块化 + 语义截断（hydroclaw/agent.py + context_utils.py）✅

**模块化**：`_build_context()` 拆分为两层：
- `_build_system_prompt(query)` — 按 6 个 section 动态组装，各 section 相互独立
- `_build_context(query, prior_messages)` — 仅拼接消息列表，逻辑简洁

6个 section（按注入顺序）：
1. Core system（system.md，始终注入）
2. Skills 列表（始终注入）
3. Adapter 文档（始终注入）
4. Domain knowledge（full 模式）
5. Basin profiles（full 模式）
6. Memory（full 模式）

**语义截断**（`context_utils.py` 新增 `semantic_truncate()`）：
- 优先在 `\n\n` 段落边界截断
- 无段落边界则退到句子边界（`. `）
- 最后才硬切字符
- 截断处附带 `...({label} truncated, N chars omitted)` 说明

### 4.4 P3：full/minimal Prompt 模式（hydroclaw/agent.py）✅

`HydroClaw.__init__()` 新增 `prompt_mode: str = "full"` 参数：

```python
# 主 Agent / 交互模式（默认）
agent = HydroClaw(prompt_mode="full")

# 子 Agent / 批量内循环（节省 ~30% 上下文）
agent = HydroClaw(prompt_mode="minimal")
```

`minimal` 模式跳过 Domain / Basin / Memory 三个重型 section，减少 token 消耗，
适合任务描述已包含足够上下文的场景（batch 实验、脚本调用）。

---

## 5. 优先级矩阵

| 优先级 | 任务 | 预期效果 | 难度 | 状态 |
|--------|------|---------|------|------|
| **P0** | system.md 去掉强制 `[思考]` | 减少机械感 | 低 | ✅ 完成 |
| **P0** | system.md 增加身份约束 | 更有价值观 | 低 | ✅ 完成 |
| **P0** | system.md Skill 规则去严格化 | 更灵活的决策 | 低 | ✅ 完成 |
| **P0** | docs/integration-plan.md | 工程文档 | 低 | ✅ 完成 |
| **P1** | plugin_registry.py | 注册表基础设施 | 低 | ✅ 完成 |
| **P1** | reload_adapters() 外部插件 | 核心集成能力 | 中 | ✅ 完成 |
| **P1** | add_local_package / add_local_tool 元工具 | Agent 可驱动集成 | 中 | ✅ 完成 |
| **P1** | CLI /plugin 命令 | 用户可管理插件 | 低 | ✅ 完成 |
| **P1** | Server /api/plugins | Web 管理界面 | 中 | ✅ 完成 |
| **P1** | autohydro hydroclaw_adapter.py | 端到端验证 | 中 | ✅ 完成 |
| **P1** | llm.py 模型感知 + thinking 参数 | 推理型模型质变 | 中 | ✅ 完成 |
| **P2** | _build_system_prompt() 模块化 | 可组合的 prompt | 中 | ✅ 完成 |
| **P2** | 语义截断替代线性截断 | 减少断句问题 | 中 | ✅ 完成 |
| **P3** | full/minimal prompt 模式 | 子 Agent 节省 token | 中 | ✅ 完成 |

---

## 6. 验证方法

### 插件系统验证

```bash
# Agent 驱动注册（自然语言）
python -m hydroclaw "帮我注册本地包 D:/project/Agent/watershed_hydrology"
# 期望：调用 add_local_package，plugins.json 写入，autohydro adapter 加载

# CLI 插件管理
python -m hydroclaw  # 进入交互模式
> /plugin list       # 看到 autohydro (local_dir, enabled)
> /plugin disable autohydro
> /plugin reload
> /plugin enable autohydro

# 单文件工具
python -m hydroclaw "帮我注册 D:/scripts/fdc.py 作为工具"
python -m hydroclaw "计算流域12025000的FDC曲线"  # 应调用 calculate_fdc

# Server API
curl http://localhost:7860/api/plugins
curl -X POST http://localhost:7860/api/plugins \
  -H "Content-Type: application/json" \
  -d '{"path": "D:/project/Agent/watershed_hydrology", "name": "autohydro"}'
```

### 模型感知验证

```bash
# 在配置中改为推理型模型（如 deepseek-r1）
python -m hydroclaw "分析流域06043500参数是否碰到边界"
# 期望：看到更深入的分析，thinking 参数生效（若 API 支持）
```

### System.md 改进验证

```bash
python -m hydroclaw "率定GR4J模型流域12025000"
# 期望：不再出现每次工具调用前的 "[思考] ..." 机械前缀
# 期望：Skill 匹配后直接按工作流执行，回复风格更自然
```

---

---

## 补充：与 Claude Code 的架构差距分析

> 日期：2026-03-24 | 来源：对比 Claude Code 官方文档与架构逆向分析
>
> 以下差距均排除模型差距（claude-sonnet-4-6 vs 自定义 LLM）和 CLI 工具差距（文件系统集成、IDE 插件），
> 聚焦**系统架构层**可以在 HydroClaw 中实际落地的设计。

### CC-1：Skill 注入策略（最关键）

| | Claude Code | HydroClaw（当前） |
|---|---|---|
| **注入位置** | `isMeta: true` 隐藏 user message | system prompt 内嵌 |
| **注入时机** | 按需：LLM 从 description 摘要中主动选择调用 | 关键词匹配到就注入全文 |
| **权限副作用** | Skill 执行时临时 pre-approve tools / override model，结束后恢复 | 无 |
| **未调用 Skill 的代价** | 只贡献 1 行 description，几乎零 token | 匹配到的全文都进 system prompt |

**问题**：HydroClaw 每次 session 将所有匹配 skill 全文塞进 system prompt，token 浪费严重，
且 LLM 没有"选择"能力，被动接受所有命中的 skill。

**改进方向**：
- `_build_system_prompt()` 里改为只注入 skill description 摘要（`<available_skills>` 块）
- Skill 全文改为在 agent loop 入口以第一条 user message（isMeta）形式注入
- 为 skill 增加 `lazy: true` 标记，标记后的 skill 完全不出现在常驻 context，只在显式调用时加载

### CC-2：工具调用后自动注入任务状态

| | Claude Code | HydroClaw |
|---|---|---|
| **注入时机** | **每次工具调用结束后**，自动注入当前 TODO list 作为 system message | Agent 需要主动调用 get_pending_tasks 工具才能感知进度 |
| **防计划漂移** | LLM 在每轮工具结果后都能看到"已完成 / 进行中 / 待做"列表 | 多轮调用后可能忘记整体任务目标或重复已完成步骤 |

**问题**：exp1/exp2 批量率定任务中，Agent 在连续调用 calibrate -> evaluate -> visualize 后
容易忘记还剩哪些流域，或重复执行已完成项。

**改进方向**：在 `agent.py` 的 `_execute_tool()` 末尾检查是否存在活跃 task list；
若有，则在下一轮 LLM messages 里追加一条简短的 `[任务状态]` system message（不进入历史）。

### CC-3：形式化 Subagent 定义体系

| | Claude Code | HydroClaw |
|---|---|---|
| **定义方式** | `.claude/agents/*.md`（YAML frontmatter + system prompt body） | 只有 `prompt_mode="minimal"` 区分主/子任务 |
| **独立配置** | model、tools 白名单/黑名单、permissionMode、maxTurns、memory scope、hooks | 无，所有场景同一 agent 实例 |
| **LLM 驱动委派** | LLM 读所有 subagent descriptions，自主决定何时委派 | 无，只能脚本显式指定 |

**改进方向**：为 HydroClaw 引入 `.hydroclaw/agents/*.md` 规范，先实现两个典型 subagent：
```markdown
# basin-explorer：快速只读验证
---
name: basin-explorer
description: 验证流域数据可用性。需要确认流域ID或检查数据完整性时自动调用。
tools: validate_basin, read_dataset, list_basins, list_camels_basins
model: (cheap model)
maxTurns: 5
---
```
```markdown
# calibrate-worker：批量率定内循环
---
name: calibrate-worker
description: 执行单个流域的完整率定-评估-可视化流程。
tools: calibrate_model, evaluate_model, visualize, save_basin_profile
prompt_mode: minimal
---
```

### CC-4：PreToolUse / PostToolUse Hook 体系

| | Claude Code | HydroClaw |
|---|---|---|
| **Hook 触发点** | PreToolUse（exit code 2 可阻断）、PostToolUse | 无工具级 hook |
| **用途** | 参数验证、日志、权限细粒度控制 | 逻辑分散在各工具函数内部 |

**改进方向**：在 `_execute_tool()` 中加 pre/post hook 调用点，开放给 tools 层注册：
- PreToolUse `calibrate_model`：验证参数范围，防止 NaN 传入算法
- PostToolUse `calibrate_model`：自动触发 `save_basin_profile`（现在是硬编码 if 判断）
- PostToolUse `run_code`：自动语义截断超长输出

### CC-5：Context Compaction 自动触发

| | Claude Code | HydroClaw |
|---|---|---|
| **触发阈值** | ~92% context 使用率自动压缩，摘要写入 MEMORY.md | 静态截断（8K/字段，16K 整体），不压缩历史 |
| **压缩后持久化** | 对话摘要落入 MEMORY.md，下次 session 前 200 行自动加载 | 无，历史截断后丢失 |

**改进方向**：在 `agent.py` 监控 token 累计量，超过阈值时调用
`memory.compress_history()`，把当前对话摘要写入 MEMORY.md 的 `## Session Summary` 段落。

### CC-6：Skill Lazy 加载标记

Claude Code 的 skill 可设 `disable-model-invocation: true`，让该 skill description
完全不出现在 LLM context，只在用户显式 `/skill-name` 时注入。

对 HydroClaw：`derive_formula`、`run_pipeline` 等偶尔使用的重型 skill，
可加 `lazy: true` 标记，不在默认 skill 列表中出现，节省常驻 token。

---

### 差距总览与实施优先级

| 优先级 | 差距 | 改动范围 | 预期收益 | 状态 |
|--------|------|---------|---------|------|
| **P1** | CC-2：工具调用后自动注入任务状态 | `agent.py` 5 行 | 批量任务计划漂移根治 | 🔲 待实现 |
| **P1** | CC-1：Skill 注入改为 on-demand user message | `agent.py` + `skill_registry.py` | -30% system prompt token | 🔲 待实现 |
| **P2** | CC-4：PreToolUse/PostToolUse hook 体系 | `agent.py` + `tools/__init__.py` | 工具层验证与后处理解耦 | 🔲 待实现 |
| **P2** | CC-3：形式化 Subagent 定义 | 新增 `agents/` 目录规范 | 主 Agent context 更干净 | 🔲 待实现 |
| **P3** | CC-5：Context compaction 自动触发 | `agent.py` + `memory.py` | 长会话不再 OOM | 🔲 待实现 |
| **P3** | CC-6：Skill lazy 加载标记 | `skill_registry.py` | 偶用 skill 不占常驻 token | 🔲 待实现 |

---

## 7. 文件变更总览

```
hydroclaw/
├── utils/
│   └── plugin_registry.py          [新建] PluginRegistry 类
├── adapters/
│   └── __init__.py                 [修改] reload_adapters() 扩展
├── tools/
│   ├── __init__.py                 [修改] discover_tools() 扩展
│   ├── add_local_package.py        [新建] 元工具
│   └── add_local_tool.py           [新建] 元工具
├── skills/
│   └── system.md                   [已修改] P0 改进
├── interface/
│   ├── cli.py                      [修改] /plugin 命令
│   └── server.py                   [修改] /api/plugins 路由
└── llm.py                          [修改] model_profile() + thinking 参数

D:/project/Agent/watershed_hydrology/
└── hydroclaw_adapter.py            [新建] autohydro 适配器声明

docs/
└── integration-plan.md             [本文件]
```
