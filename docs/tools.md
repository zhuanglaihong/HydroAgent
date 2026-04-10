# 工具完整参考

> 版本：v2.6 | 日期：2026-03-25

HydroClaw 的所有工具按来源分为三类，详细 API 见 [skills.md](skills.md)：

| 来源 | priority | 位置 | 工具列表 |
|------|----------|------|---------|
| 核心工具 | 20 | `tools/*.py` | validate_basin, run_simulation, read_file, inspect_dir, create_task_list, get_pending_tasks, update_task, add_task, search_memory, save_basin_profile, record_error_solution, ask_user, create_skill, create_adapter, install_package, register_package, add_local_package, add_local_tool, spawn_agent |
| Skill 工具 | 10 | `skills/*/` | calibrate_model, evaluate_model, llm_calibrate, batch_calibrate, compare_models, generate_code, run_code, visualize, run_simulation, list_basins, read_dataset, convert_dataset_to_nc, list_camels_basins, check_camels_data |
| 外部插件工具 | 5 | PluginRegistry（`single_file` 类型）| 由 `add_local_tool()` 注册的任意 .py 文件函数 |
| 动态工具 | 5 | `create_skill` 生成 | 任意（运行时生成） |

同名冲突时保留高优先级工具；调用 `list_tools()` 可查询当前注册状态。

---

## 核心工具（tools/，priority=20）

### 观测类

| 工具 | 说明 |
|------|------|
| `validate_basin(basin_id, t_range)` | 验证流域 ID 是否有效，返回数据探针（变量列表、时间范围、读取 API 说明） |
| `read_file(path)` | 读取工作区内 JSON/YAML/CSV/TXT 文件，截断到 8K |
| `inspect_dir(path)` | 查看目录文件列表与结构 |

### 任务管理类

| 工具 | 说明 |
|------|------|
| `create_task_list(goal, tasks)` | 为批量任务创建持久化任务列表（写入 task_state.json） |
| `get_pending_tasks()` | 获取下一个待执行任务及整体进度摘要 |
| `update_task(task_id, status, nse, kge, notes)` | 标记任务为 done/failed，记录结果 |
| `add_task(description)` | 动态追加新任务（Agent 根据中间结果决定） |

### 记忆类

| 工具 | 说明 |
|------|------|
| `search_memory(query)` | 检索跨会话历史（MEMORY.md + 流域档案） |
| `save_basin_profile(basin_id, model, ...)` | 保存流域率定档案（通常由 PostToolUse hook 自动调用） |
| `record_error_solution(error, solution)` | 将错误-解决方案对写入 error_solutions.json 知识库 |

### 交互类

| 工具 | 说明 |
|------|------|
| `ask_user(question)` | 暂停并向用户提问（信息不足时使用） |

### 仿真类

| 工具 | 说明 |
|------|------|
| `run_simulation(calibration_dir, sim_period)` | 用已率定参数在任意时段做径流模拟 |

### 元工具（动态扩展类）

| 工具 | 说明 |
|------|------|
| `create_skill(name, description)` | 运行时生成新 Skill 包（skill.md + tool.py），立即注册（priority=5） |
| `create_adapter(name, description, supported_models)` | 生成 PackageAdapter 骨架 + skills/skill.md，自动 reload |
| `install_package(package_name, version)` | 受控 pip 安装（需用户授权） |
| `register_package(package_name)` | fetch PyPI API + importlib 探测 + LLM 分析，自动生成适配器 |
| `add_local_package(path, name, description)` | 注册本地目录包，写入 plugins.json + 热重载 |
| `add_local_tool(path)` | 注册单 .py 文件，自动发现公开函数并注册为工具（priority=5） |
| `spawn_agent(name, task)` | 委派任务给子代理（depth limit=1，防递归） |

---

## 工具发现机制

`hydroclaw/tools/__init__.py` 在启动时扫描四层来源：

1. `hydroclaw/tools/*.py` — 核心工具（priority=20）
2. `hydroclaw/skills/*/*.py` — 每个 Skill 子目录（priority=10）
3. PluginRegistry（`single_file` 类型）— 外部 .py 文件函数（priority=5）
4. `create_skill` 动态生成的目录（priority=5，生成后立即触发重扫）

同名冲突时保留 **高优先级**；同优先级时后注册覆盖先注册（便于 hot-reload）。

**Schema 自动生成规则**：

| Python 类型 | JSON Schema 类型 |
|-------------|-----------------|
| `str` | `"string"` |
| `int` | `"integer"` |
| `float` | `"number"` |
| `bool` | `"boolean"` |
| `list[str]` | `{"type": "array", "items": {"type": "string"}}` |
| `dict` | `"object"` |
| `str | None` | `"string"`（Optional 展开） |
| `_xxx` 前缀参数 | 不出现在 Schema（Agent 运行时自动注入） |

**`__agent_hint__` 协议**：工具函数可附加 `__agent_hint__` 属性，描述隐性约束和输出->输入关系，
`fn_to_schema()` 自动追加到 schema description，LLM 调用前即可看到：

```python
calibrate_model.__agent_hint__ = (
    "Returns calibration_dir, NO metrics. "
    "Call evaluate_model(calibration_dir=...) separately for NSE/KGE."
)
```

---

## 内部参数注入（_ 前缀约定）

以 `_` 开头的参数不出现在 Function Calling Schema 中，由 Agent 在运行时自动注入：

| 参数 | 注入值 | 用途 |
|------|--------|------|
| `_workspace` | 当前工作目录（Path） | 文件读写路径 |
| `_cfg` | 全局配置字典 | API Key、默认参数等 |
| `_llm` | LLM 客户端实例 | 需要调用 LLM 的工具（llm_calibrate 等） |
| `_ui` | UI 实例 | 进度显示 |

---

## 热加载

```python
from hydroclaw.tools import reload_tools
reload_tools()  # create_skill / create_adapter 完成后自动调用
```

查询当前工具集：

```python
from hydroclaw.tools import get_all_tools
for name, (fn, priority) in sorted(get_all_tools().items()):
    print(f"  [{priority:2d}] {name}")
```
