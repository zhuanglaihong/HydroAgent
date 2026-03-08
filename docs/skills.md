# Skill 参考

Skill 是 HydroClaw 的核心扩展单元，每个 Skill 是一个子目录，包含两部分：

- `skill.md` — 工作流指引，描述 LLM 在匹配该场景时应遵循的步骤
- `*.py` — 工具实现，自动发现注册为可调用工具

```
hydroclaw/skills/
├── system.md                  # 系统基础 prompt（每次都注入）
├── calibration/               # 标准率定 Skill
│   ├── skill.md
│   └── calibrate.py           # calibrate_model()
├── evaluation/                # 模型评估 Skill
│   ├── skill.md
│   └── evaluate.py            # evaluate_model()
├── llm_calibration/           # LLM 智能率定 Skill
│   ├── skill.md
│   └── llm_calibrate.py       # llm_calibrate()
├── batch_calibration/         # 批量率定 Skill
│   ├── skill.md
│   └── batch_calibrate.py     # batch_calibrate()
├── model_comparison/          # 多模型对比 Skill
│   ├── skill.md
│   └── compare_models.py      # compare_models()
├── code_analysis/             # 代码生成/执行 Skill
│   ├── skill.md
│   ├── generate_code.py       # generate_code()
│   └── run_code.py            # run_code()
└── visualization/             # 可视化 Skill
    ├── skill.md
    └── visualize.py           # visualize()
```

---

## Skill 工具详解

### calibrate_model

传统算法率定，支持 SCE-UA / GA / scipy。率定完成后自动评估训练期指标，结果存入 `train_metrics/`。

```python
calibrate_model(
    basin_ids=["12025000"],
    model_name="gr4j",          # gr4j / xaj / gr5j / gr6j
    algorithm="SCE_UA",         # SCE_UA / GA / scipy
    algorithm_params={"rep": 1000},
    param_range_file=None,      # 自定义参数范围 YAML（迭代优化用）
    train_period=["2000-01-01", "2009-12-31"],
    test_period=["2010-01-01", "2014-12-31"],
    output_dir="results/my_run",
)
# -> {
#     "best_params": {"x1": 1180.6, "x2": -3.94, "x3": 36.9, "x4": 1.22},
#     "train_metrics": {"NSE": 0.783, "KGE": 0.833, "RMSE": 1.45, ...},
#     "calibration_dir": "results/my_run",
#     "success": true
#    }
```

`param_range_file` 格式（YAML）：

```yaml
gr4j:
  x1: [100.0, 3000.0]    # 生产存储容量 (mm)
  x2: [-10.0, 10.0]      # 地下水交换系数 (mm/day)
  x3: [10.0, 500.0]      # 汇流存储容量 (mm)
  x4: [0.5, 10.0]        # 单位线时间基底 (days)
```

### evaluate_model

在指定时段评估已率定模型，结果存入 `test_metrics/` 子目录。

```python
evaluate_model(
    calibration_dir="results/gr4j_12025000",
    test_period=["2010-01-01", "2014-12-31"],   # 可选，默认从 config 读取
)
# -> {"metrics": {"NSE": 0.747, "KGE": 0.843, "RMSE": 2.13, ...}, "success": true}
```

### llm_calibrate

LLM 智能迭代率定。每轮 SCE-UA 结束后，LLM 分析参数边界情况并调整范围。

```python
llm_calibrate(
    basin_ids=["12025000"],
    model_name="gr4j",
    max_rounds=5,         # 最多迭代轮数
    nse_target=0.75,      # 目标 NSE，达到后提前退出
    algorithm="SCE_UA",
)
# -> {
#     "best_params": {...},
#     "best_nse": 0.791,
#     "rounds_used": 3,
#     "history": [{"round": 1, "nse": 0.748, "boundary_hit": true}, ...],
#     "success": true
#    }
```

工作原理：

```
Round N:
  SCE-UA 在当前参数范围内优化
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
    model_names=["gr4j", "xaj"],
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
    calibration_dir="results/gr4j_12025000",   # 可选，提供数据上下文
)
# -> {"code": "...", "file_path": "generated_code/monthly_runoff.py", "success": true}
```

### run_code

执行 Python 脚本，捕获标准输出和错误。

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

## 动态 Skill 创建

用户请求不存在的功能时，LLM 调用 `create_skill`（见 [tools.md](tools.md)）在运行时生成新的 Skill 目录，包含 `skill.md` 和工具实现，立即注册可用。

---

## 添加自定义 Skill

在 `hydroclaw/skills/` 下创建子目录：

```
hydroclaw/skills/my_skill/
├── skill.md      # 工作流指引（头部声明关键词）
└── my_tool.py    # 工具实现
```

**skill.md 头部格式**：

```markdown
---
keywords: [关键词1, my_keyword, ...]
---

## My Skill 工作流

当用户需要 XXX 时使用此工作流。

### 步骤
1. 调用 `validate_basin` 验证流域
2. 调用 `my_tool` 执行分析
3. 输出结果摘要
```

重启后 SkillRegistry 自动扫描注册，无需修改任何配置。
