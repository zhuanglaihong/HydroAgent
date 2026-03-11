---
name: Evaluation
description: 在任意时段评估已率定的水文模型，计算 NSE、RMSE、KGE、PBIAS 指标
keywords: [评估, evaluat, 测试期, 训练期, 验证, test period, 指标, metrics]
tools: [evaluate_model, inspect_dir, read_file, visualize]
when_to_use: 率定完成后，评估模型在训练期或测试期的性能；或单独评估已有率定结果
---

## 目标

从已率定模型的输出目录中获取指定时段的性能指标：
- NSE（Nash-Sutcliffe Efficiency）
- KGE（Kling-Gupta Efficiency）
- RMSE（均方根误差）
- PBIAS（水量偏差百分比）

成功标志：返回包含上述指标的 `metrics` 字典，且 `success: True`。

## 判断框架

### 调用前：确认 `calibration_dir` 有效

`evaluate_model` 需要 `calibration_dir` 下存在 `calibration_config.yaml`。
若不确定率定是否完整，先观测：

```
inspect_dir(calibration_dir)   # 检查文件是否存在
```

若 `calibration_config.yaml` 不在文件列表中 → 率定可能未完成，告知用户。

### 选择评估时段

`evaluate_model` 支持任意时段（不只是测试期）：

| 场景 | eval_period 传什么 |
|------|------------------|
| 训练期性能（拟合质量）| calibrate_model 返回的 train_period |
| 测试期性能（泛化能力）| calibrate_model 返回的 test_period |
| 自定义时段 | ["YYYY-MM-DD", "YYYY-MM-DD"] |
| 使用率定配置中的默认测试期 | 不传 eval_period（eval_period=None）|

### 评估完成后：如何获取完整指标

`evaluate_model` 的返回值 `metrics` 是摘要。完整指标在 CSV 文件中：

```
read_file(observable_files['metrics_csv'])   # 读取 basins_metrics.csv
```

提示：返回值中的 `hint` 字段会告诉你 CSV 的路径。

### 如何解读指标

| 指标 | 含义 | 优秀 | 良好 | 一般 | 较差 |
|------|------|------|------|------|------|
| NSE  | 整体拟合优度 | ≥ 0.75 | ≥ 0.65 | ≥ 0.50 | < 0.50 |
| KGE  | 综合（相关性+偏差+变异性）| ≥ 0.75 | ≥ 0.65 | ≥ 0.50 | < 0.50 |
| PBIAS | 水量偏差 | < ±10% | < ±20% | < ±30% | ≥ ±30% |
| RMSE | 绝对误差（越小越好）| — | — | — | — |

### 何时调用可视化

- 用户要求查看过程线/散点图 → 调用 `visualize(calibration_dir, ...)`
- 纯数字结果请求 → 不必强制可视化

## 异常处理

| 异常 | 检查 | 处理 |
|------|------|------|
| `calibration_config.yaml` not found | `inspect_dir(calibration_dir)` | 率定未完成，告知用户 |
| NSE 返回 None 或 -999 | `read_file(metrics_csv)` 看原始数据 | 可能数据期对不上，检查 eval_period |
| `eval_period` 超出数据范围 | 对比 config 中的 train/test 期与请求期 | 调整到数据覆盖范围内 |
| 指标文件路径不存在 | `inspect_dir(metrics_dir)` | evaluate 可能静默失败，查看日志 |

## 输出

报告应包含：
- 评估时段（训练期/测试期）
- 各指标值及质量等级
- 与训练期对比（若已有训练期指标）：泛化差距分析
- 若指标较差：基于指标特征的可能原因推断
  - NSE 差但 KGE 好 → 峰值误差大
  - PBIAS 大 → 系统性偏差，可能是蒸散发估计问题
