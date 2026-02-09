# 工具参考

## 内置工具一览

| 工具 | 功能 | 需要 LLM | 关键参数 |
|------|------|----------|----------|
| `validate_basin` | 验证流域 ID 是否存在 | 否 | `basin_ids` |
| `calibrate_model` | 传统算法率定 | 否 | `basin_ids`, `model_name`, `algorithm` |
| `evaluate_model` | 测试期评估 | 否 | `calibration_dir` |
| `run_simulation` | 已有参数运行模拟 | 否 | `calibration_dir` |
| `visualize` | 生成图表 | 否 | `calibration_dir`, `plot_types` |
| `llm_calibrate` | LLM 智能迭代率定 | 是 | `basin_ids`, `nse_target` |
| `generate_code` | 生成分析脚本 | 是 | `task_description` |
| `run_code` | 执行 Python 脚本 | 否 | `file_path` |
| `create_tool` | 自动创建新工具 | 是 | `tool_name`, `description` |

## 工具详细说明

### validate_basin

验证 CAMELS 流域 ID 是否存在且数据可用。

```
validate_basin(basin_ids=["01013500", "99999999"])
→ {"valid_basins": ["01013500"], "invalid_basins": ["99999999"], "success": true}
```

### calibrate_model

调用 hydromodel 执行参数优化。

```
calibrate_model(
    basin_ids=["01013500"],
    model_name="gr4j",        # gr4j, xaj, gr5j, gr6j
    algorithm="SCE_UA",       # SCE_UA, GA, scipy
    algorithm_params={"rep": 500},
    param_range_file=None,    # 自定义参数范围 YAML（迭代优化用）
    train_period=["2000-01-01", "2009-12-31"],
    test_period=["2010-01-01", "2014-12-31"],
)
→ {"best_params": {...}, "metrics": {"NSE": 0.748, ...}, "calibration_dir": "...", "success": true}
```

**`param_range_file`**：指向自定义参数范围的 YAML 文件路径，用于迭代优化时扩展参数边界。格式：

```yaml
gr4j:
  x1: [0.5, 3000.0]
  x2: [-15.0, 15.0]
  x3: [0.5, 800.0]
  x4: [0.3, 15.0]
```

### evaluate_model

在测试期评估已率定模型的性能。

```
evaluate_model(
    calibration_dir="results/gr4j_SCE_UA_01013500",
    test_period=["2010-01-01", "2014-12-31"],  # 可选
)
→ {"metrics": {"NSE": 0.712, "RMSE": 1.45, ...}, "success": true}
```

### visualize

生成水文过程线图、散点图等。

```
visualize(
    calibration_dir="results/gr4j_SCE_UA_01013500",
    plot_types=["timeseries", "scatter"],  # 默认两种
    basin_ids=None,                        # 默认所有流域
)
→ {"plot_files": ["figures/ts.png", ...], "plot_count": 2}
```

### llm_calibrate

LLM 智能迭代率定。每轮运行 SCE-UA，LLM 分析结果并调整参数范围。

```
llm_calibrate(
    basin_ids=["01013500"],
    model_name="gr4j",
    max_rounds=5,             # 最多 5 轮
    nse_target=0.75,          # 目标 NSE
    algorithm="SCE_UA",
    algorithm_params={"rep": 500},
)
→ {"best_params": {...}, "best_nse": 0.74, "rounds": 2, "history": [...], "success": true}
```

### generate_code

LLM 生成 Python 分析脚本。

```
generate_code(
    task_description="计算流域01013500的径流系数并画FDC曲线",
    output_filename="fdc_analysis.py",
    calibration_dir="results/gr4j_SCE_UA_01013500",
)
→ {"code": "...", "file_path": "generated_code/fdc_analysis.py", "success": true}
```

### create_tool

LLM 自动创建新的工具脚本。

```
create_tool(
    tool_name="sensitivity_analysis",
    description="使用 SALib 对水文模型参数做 Sobol 敏感性分析",
    package_name="SALib",
    example_usage="from SALib.sample import saltelli\n...",
)
→ {"tool_name": "sensitivity_analysis", "file_path": "hydroclaw/tools/sensitivity_analysis.py", "success": true}
```

新工具立即可用，无需重启。

## 自动发现机制

### 工作原理

启动时，`hydroclaw/tools/__init__.py` 扫描 `tools/` 目录：

```
tools/
├── __init__.py          # 扫描引擎（跳过）
├── calibrate.py         # → 发现 calibrate_model()
├── evaluate.py          # → 发现 evaluate_model()
├── my_new_tool.py       # → 发现 my_new_tool()    ← 新文件自动发现
└── _helpers.py          # → 跳过（_ 开头）
```

规则：
- 文件名不以 `_` 开头的 `.py` 模块会被扫描
- 函数名不以 `_` 开头的公开函数会被注册为工具
- 函数必须定义在该模块中（不是 import 进来的）

### Schema 生成规则

| Python 类型 | JSON Schema 类型 |
|---|---|
| `str` | `"string"` |
| `int` | `"integer"` |
| `float` | `"number"` |
| `bool` | `"boolean"` |
| `list[str]` | `{"type": "array", "items": {"type": "string"}}` |
| `dict` | `"object"` |
| `str \| None` | `"string"`（Optional 会展开） |

- 无默认值的参数 → `required`
- 有默认值的参数 → 可选，Schema 中带 `default`
- `_` 前缀参数 → 完全隐藏，不出现在 Schema 中

### 手动创建工具

如果不想用 `create_tool`，也可以手动添加：

1. 在 `hydroclaw/tools/` 下创建 `.py` 文件
2. 定义一个公开函数，添加类型注解和 docstring
3. 重启 HydroClaw 即可

```python
# hydroclaw/tools/my_analysis.py

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def my_analysis(
    basin_ids: list[str],
    method: str = "default",
    _workspace: Path | None = None,
) -> dict:
    """Run my custom analysis.

    Args:
        basin_ids: CAMELS basin ID list
        method: Analysis method to use

    Returns:
        {"result": ..., "success": bool}
    """
    try:
        # your code here
        return {"result": "done", "success": True}
    except Exception as e:
        return {"error": str(e), "success": False}
```
