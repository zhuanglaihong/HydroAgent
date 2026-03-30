# Skill 与工具参考

> 版本：v2.6 | 日期：2026-03-25

Skill 是 HydroClaw 的核心扩展单元，每个 Skill 是一个子目录，包含两部分：

- `skill.md` — 工作流指引，描述 LLM 在匹配该场景时应遵循的目标与判断框架
- `*.py` — 工具实现，自动发现注册为可调用工具（priority=10）

独立工具（`tools/*.py`，priority=20）不属于 Skill，但同样自动发现注册。

---

## 目录结构（v2.6）

```
hydroclaw/
├── skills/
│   ├── system.md                  # 系统基础 prompt（每次都注入）
│   ├── calibration/               # 标准率定 Skill
│   │   ├── skill.md               # keywords: [calibrat, 率定, sce, ga]
│   │   └── calibrate.py           # calibrate_model()
│   ├── evaluation/                # 模型评估 Skill
│   │   ├── skill.md               # keywords: [evaluat, 评估, nse, kge]
│   │   └── evaluate.py            # evaluate_model()
│   ├── llm_calibration/           # LLM 智能率定 Skill
│   │   ├── skill.md               # keywords: [llm_calibrat, 智能率定, 参数范围]
│   │   └── llm_calibrate.py       # llm_calibrate()
│   ├── batch_calibration/         # 批量率定 Skill
│   │   ├── skill.md
│   │   └── batch_calibrate.py     # batch_calibrate()
│   ├── model_comparison/          # 多模型对比 Skill
│   │   ├── skill.md
│   │   └── compare_models.py      # compare_models()
│   ├── code_analysis/             # 代码生成/执行 Skill
│   │   ├── skill.md
│   │   ├── generate_code.py       # generate_code()
│   │   └── run_code.py            # run_code()
│   ├── visualization/             # 可视化 Skill
│   │   ├── skill.md
│   │   └── visualize.py           # visualize()
│   ├── hydrodatasource/           # 自定义数据集工具
│   │   └── dataset_tools.py       # list_basins / read_dataset / convert_dataset_to_nc
│   └── hydrodataset/              # 公开数据集工具
│       └── hydrodataset_tools.py  # list_camels_basins / check_camels_data
│
└── tools/                         # 核心工具（priority=20）
    ├── validate.py                # validate_basin()
    ├── simulate.py                # run_simulation()
    ├── observe.py                 # read_file() / inspect_dir()
    ├── task_tools.py              # create_task_list / get_pending_tasks / update_task / add_task
    ├── memory_tools.py            # search_memory / save_basin_profile / record_error_solution
    ├── ask_user.py                # ask_user()
    ├── create_skill.py            # create_skill() -- 元工具
    ├── create_adapter.py          # create_adapter() -- 元工具
    ├── install_package.py         # install_package()
    ├── register_package.py        # register_package()
    ├── add_local_package.py       # add_local_package() -- 注册本地目录包
    ├── add_local_tool.py          # add_local_tool() -- 注册单文件工具
    └── spawn_agent.py             # spawn_agent() -- 委派子代理
```

---

## skill.md 前置格式

```yaml
---
keywords: [calibrat, 率定, gr4j, sce]
priority: 10
---

## 工作流目标

当用户需要 XXX 时使用此工作流。

### 目标与判断框架
目标：得到训练期和测试期的 NSE/KGE
判断：calibrate_model 只返回参数，不含指标 -> 主动调用 evaluate_model
异常：calibration_dir 为空 -> 用 inspect_dir 诊断

### 工具序列（参考，非强制）
1. validate_basin（验证数据可用性）
2. calibrate_model（执行率定）
3. evaluate_model（评估指标）
```

---

## Skill 工具详解

### calibrate_model

传统算法率定，支持 SCE-UA / GA / scipy。

```python
calibrate_model(
    basin_ids=["12025000"],
    model_name="gr4j",          # gr4j / gr5j / gr6j / xaj / lstm
    algorithm="SCE_UA",         # SCE_UA / GA / scipy
    algorithm_params={"rep": 1000},
    param_range_file=None,      # 自定义参数范围 YAML（llm_calibrate 迭代时使用）
    train_period=["2000-01-01", "2009-12-31"],
    test_period=["2010-01-01", "2014-12-31"],
    output_dir="results/my_run",
)
# -> {
#     "best_params": {"x1": 1180.6, "x2": -3.94, "x3": 36.9, "x4": 1.22},
#     "calibration_dir": "results/my_run",
#     "observable_files": ["calibration_results.json", "param_range.yaml"],
#     "next_steps": "Call evaluate_model(calibration_dir=...) to get NSE/KGE",
#     "success": true
#    }
```

**注意（__agent_hint__）**：返回值不含 NSE/KGE，必须单独调用 `evaluate_model`。
`save_basin_profile` 在成功后由 PostToolUse hook 自动调用，无需手动触发。

### evaluate_model

在指定时段评估已率定模型。

```python
evaluate_model(
    calibration_dir="results/gr4j_12025000",
    eval_period=["2010-01-01", "2014-12-31"],  # 留空则自动从 config 读取测试期
)
# -> {"metrics": {"NSE": 0.747, "KGE": 0.843, "RMSE": 2.13}, "success": true}
```

### llm_calibrate

LLM 智能迭代率定：每轮 SCE-UA 结束后，LLM 分析参数边界并调整范围。

```python
llm_calibrate(
    basin_ids=["12025000"],
    model_name="gr4j",
    max_rounds=5,
    nse_target=0.75,
    algorithm="SCE_UA",
)
# -> {
#     "best_params": {...},
#     "best_nse": 0.791,
#     "rounds_used": 3,
#     "boundary_hits": {"x1": 2, "x3": 1},
#     "history": [{"round": 1, "nse": 0.748, "boundary_hit": true}, ...],
#     "success": true
#    }
```

工作原理：
```
Round N:
  SCE-UA 在当前参数范围内优化（每轮随机种子不同）
  -> LLM 检查最优参数距边界是否 < 5%
  -> 若触界: 扩展该参数边界（x1.5~x2），进入 Round N+1
  -> 若 NSE >= target: 提前退出
  -> 若无触界且 NSE 无改善: 停止
```

### batch_calibrate

对多个流域批量执行率定和评估。

```python
batch_calibrate(
    basin_ids=["12025000", "03439000", "11532500"],
    model_name="gr4j",
    algorithm="SCE_UA",
    output_dir="results/batch_run",
)
# -> {"results": [{basin_id, train_metrics, test_metrics, ...}, ...], "success": true}
```

### compare_models

对同一流域用多个模型分别率定，生成对比表格。

```python
compare_models(
    basin_id="12025000",
    model_names=["gr4j", "gr5j", "gr6j"],
    algorithm="SCE_UA",
)
# -> {"comparison": [{"model": "gr4j", "train_nse": 0.783, "test_nse": 0.747}, ...]}
```

### generate_code

LLM 生成 Python 水文分析脚本。

```python
generate_code(
    task_description="计算流域12025000的月均径流变化曲线",
    output_filename="monthly_runoff.py",
    calibration_dir="results/gr4j_12025000",  # 可选，提供数据上下文
)
# -> {"code": "...", "file_path": "generated_code/monthly_runoff.py", "success": true}
```

### run_code

执行 Python 脚本，捕获标准输出和错误（stdout 截断到 8K）。

```python
run_code(file_path="generated_code/monthly_runoff.py")
# -> {"stdout": "...", "stderr": "", "returncode": 0, "success": true}
```

### visualize

生成水文过程线图、模拟-观测散点图。

```python
visualize(
    calibration_dir="results/gr4j_12025000",
    plot_types=["timeseries", "scatter"],
)
# -> {"plot_files": ["figures/timeseries.png", "figures/scatter.png"], "success": true}
```

---

## 核心工具（tools/，priority=20）

### validate_basin

验证流域 ID 是否有效、数据是否可用，并返回数据探针信息。

```python
validate_basin(
    basin_id="12025000",
    t_range=["2000-01-01", "2014-12-31"],  # 可选
)
# -> {
#     "valid": true,
#     "available_variables": ["prcp", "pet", "flow"],
#     "full_time_range": ["1980-01-01", "2014-12-31"],
#     "data_path": "D:/data/camels/basin_timeseries/12025000.nc",
#     "read_api_note": "hydro_dataset.read(basin_id, t_range=..., var_type=...)"
#    }
```

### run_simulation

用已率定参数对指定时段进行径流模拟。

```python
run_simulation(
    calibration_dir="results/gr4j_12025000",
    sim_period=["2015-01-01", "2020-12-31"],
)
# -> {"sim_flow": [...], "output_file": "results/.../simulation.csv", "success": true}
```

### read_file

读取工作区内文本、JSON、YAML、CSV 文件内容（截断到 8K）。

```python
read_file(path="results/gr4j_12025000/calibration_results.json")
# -> {"content": "...", "success": true}
```

### inspect_dir

查看目录的文件列表与结构。

```python
inspect_dir(path="results/gr4j_12025000")
# -> {"files": ["calibration_config.yaml", "calibration_results.json", ...], "success": true}
```

### create_task_list

为批量任务创建持久化任务列表（写入 task_state.json）。

```python
create_task_list(
    goal="用 GR4J 率定 5 个流域",
    tasks=[
        {"id": "12025000_gr4j", "description": "率定流域 12025000"},
        {"id": "03439000_gr4j", "description": "率定流域 03439000"},
    ]
)
```

### get_pending_tasks

获取下一个待执行任务及整体进度摘要。

```python
get_pending_tasks()
# -> {"next_task": {"id": "...", "description": "..."}, "progress": "2/5 完成", "success": true}
```

### update_task

将任务标记为已完成或失败，记录结果指标。

```python
update_task(
    task_id="12025000_gr4j",
    status="done",          # done / failed
    nse=0.783,
    kge=0.833,
    notes="训练期 NSE 0.783，测试期 NSE 0.747",
)
```

### add_task

动态向任务列表追加新任务（LLM 根据中间结果决定）。

```python
add_task(description="对触边界流域 12025000 追加 llm_calibrate 验证")
```

### ask_user

当信息不足时暂停并向用户提问。

```python
ask_user(question="请提供目标流域 ID 和率定时段")
# -> {"answer": "...", "success": true}
```

### search_memory

检索跨会话的历史操作记录（MEMORY.md + 流域档案）。

```python
search_memory(query="流域 12025000 GR4J 历史率定")
# -> {"results": [...], "success": true}
```

### save_basin_profile

将率定结果保存为流域长期档案（通常由 PostToolUse hook 自动调用）。

```python
save_basin_profile(
    basin_id="12025000",
    model="gr4j",
    algorithm="SCE_UA",
    train_nse=0.783,
    test_nse=0.747,
    best_params={"x1": 1180.6, "x2": -3.94, "x3": 36.9, "x4": 1.22},
    calibration_dir="results/gr4j_12025000",
)
```

### spawn_agent

委派任务给指定的子代理（在 `hydroclaw/agents/` 或 `.hydroclaw/agents/` 中定义）。

```python
spawn_agent(
    name="calibrate-worker",
    task="用 GR4J + SCE-UA 率定流域 12025000，训练期 2000-2009，测试期 2010-2014",
)
# -> {"success": true, "result": "basin_id: 12025000, train_NSE: 0.783, ...", "agent": "calibrate-worker"}
```

**注意**：子代理不能再委派子代理（depth limit=1）。

### add_local_package

注册本地目录包（包根目录需有 `hydroclaw_adapter.py`）。

```python
add_local_package(
    path="D:/project/autohydro",
    name="autohydro",
    description="AutoHydro 自动水文分析包",
)
# -> 写入 <workspace>/.hydroclaw/plugins.json，调用 reload_adapters()
```

### add_local_tool

注册单 .py 文件工具（自动发现文件中的公开函数并注册为工具）。

```python
add_local_tool(path="D:/scripts/fdc.py")
# -> 动态 import，注册 calculate_fdc 等函数为工具（priority=5）
```

---

## 元工具

### create_skill

运行时动态生成新 Skill 包（目录 + skill.md + tool.py），立即注册可用。

```python
create_skill(
    name="spotpy_mcmc",
    description="用 spotpy 做 MCMC 不确定性分析，返回参数后验分布",
)
# -> 生成 skills/spotpy_mcmc/skill.md + tool.py
# -> discover_tools() 重新扫描，立即注册（priority=5）
```

### create_adapter

为新水文包生成 PackageAdapter 骨架（adapter.py + skills/skill.md），立即注册。

```python
create_adapter(
    name="xaj_model",
    description="新安江降雨径流模型",
    supported_models=["xaj_v2"],
)
# -> 生成 adapters/xaj_model/adapter.py（骨架）+ skills/skill.md
# -> reload_adapters()，立即生效
```

### install_package

受控 pip 安装（需用户在 `ask_user` 中明确授权，Agent 不自主决定安装）。

```python
install_package(package_name="spotpy", version="1.6.0")
```

---

## 动态 Skill 创建

当现有工具不满足需求时：

```
用户："帮我用 spotpy 做 MCMC 不确定性分析"
  -> LLM 调用 create_skill(name="spotpy_mcmc", ...)
  -> 生成 skills/spotpy_mcmc/skill.md + tool.py
  -> 立即注册，本次对话即可使用
```

---

## 添加自定义 Skill

在 `hydroclaw/skills/` 下创建子目录：

```
hydroclaw/skills/my_skill/
├── skill.md      # 工作流指引（头部声明关键词）
└── my_tool.py    # 工具实现（公开函数自动注册）
```

重启后 SkillRegistry 自动扫描注册，无需修改任何配置。

---

## 工具优先级体系

| 来源 | 优先级 | 说明 |
|------|--------|------|
| `tools/*.py` | 20 | 核心工具，最高优先级，不可被覆盖 |
| `skills/*/` | 10 | Skill 工具，标准优先级 |
| `create_skill` 动态生成 | 5 | 最低优先级，同名时被核心工具覆盖 |

同名冲突时保留高优先级者，并记录 warning。调用 `list_tools()` 可查询当前工具集状态。
