# 独立工具参考

独立工具（`hydroclaw/tools/`）是不附属于特定 Skill 工作流的通用工具，任何场景下均可调用。

Skill 工具（`hydroclaw/skills/*/`）的详细说明见 [skills.md](skills.md)。

---

## 工具列表

| 工具 | 功能 |
|------|------|
| `validate_basin` | 验证 CAMELS 流域 ID 是否存在 |
| `run_simulation` | 使用已有参数运行模型模拟 |
| `create_skill` | 运行时生成新 Skill（元工具） |

---

## validate_basin

验证 CAMELS-US 流域 ID 是否存在且数据可用。通常是任何率定流程的第一步。

```python
validate_basin(basin_ids=["12025000", "99999999"])
# -> {
#     "valid_basins": ["12025000"],
#     "invalid_basins": ["99999999"],
#     "valid": true,
#     "success": true
#    }
```

当流域 ID 无效时，Agent 会提前告知用户，不会触发后续率定。

---

## run_simulation

使用已有率定参数运行模型模拟，不重新做参数优化。适用于：
- 在训练/测试期以外的时段运行模拟
- 使用固定参数集进行情景分析

```python
run_simulation(
    calibration_dir="results/gr4j_12025000",
    sim_period=["2015-01-01", "2020-12-31"],
)
# -> {"simulation_file": "results/gr4j_12025000/simulation.nc", "success": true}
```

---

## create_skill

元工具（Meta-tool）：LLM 在运行时自动生成新的 Skill 目录，包含 `skill.md` 工作流指引和工具实现文件，立即注册进工具表。

```python
create_skill(
    skill_name="mcmc_uncertainty",
    description="使用 spotpy 对水文模型参数做 MCMC 不确定性分析",
    requirements=["spotpy"],
)
# -> {
#     "skill_dir": "hydroclaw/skills/mcmc_uncertainty/",
#     "files_created": ["skill.md", "tool.py"],
#     "tool_registered": true,
#     "success": true
#    }
```

生成示例：

```
# 用户: 帮我做参数敏感性分析，用SALib包

hydroclaw/skills/sensitivity_analysis/
├── skill.md      <- LLM 生成的工作流指引
└── tool.py       <- LLM 生成的工具实现（语法已验证）
```

新工具在当前对话中立即可用，下次启动时也会自动加载。

---

## 工具发现机制

`hydroclaw/tools/__init__.py` 在启动时扫描：

1. `hydroclaw/tools/*.py` — 独立工具文件
2. `hydroclaw/skills/*/*.py` — 每个 Skill 子目录中的工具文件

所有不以 `_` 开头的公开函数自动生成 OpenAI Function Calling Schema 并注册。

| Python 类型 | JSON Schema 类型 |
|-------------|-----------------|
| `str` | `"string"` |
| `int` | `"integer"` |
| `float` | `"number"` |
| `bool` | `"boolean"` |
| `list[str]` | `{"type": "array", "items": {"type": "string"}}` |
| `dict` | `"object"` |
| `str \| None` | `"string"`（Optional 展开） |
| `_xxx` 前缀参数 | 不出现在 Schema 中（Agent 自动注入） |

热加载：

```python
from hydroclaw.tools import reload_tools
reload_tools()   # create_skill 完成后自动调用
```
