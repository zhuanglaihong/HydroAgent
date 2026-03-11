---
name: Visualization
description: 生成水文过程线图、散点图等可视化结果
keywords: [可视化, visualiz, 画图, 绘图, 过程线, 散点图, plot, figure, 图表]
tools: [visualize, inspect_dir, read_file]
when_to_use: 展示模型模拟结果、率定评估图形时
---

## 目标

生成水文模型结果的可视化图形，让用户能直观判断模型拟合质量。

成功标志：图片文件已保存到磁盘，告知用户完整路径。

## 判断框架

### 调用前提

`visualize` 需要评估结果目录（其中包含观测值和模拟值的对比数据）。
若只有 `calibration_dir` 但未评估 → 先调用 `evaluate_model`，再可视化。

**判断是否需要先评估：**

```
inspect_dir(calibration_dir)
```

若目录中没有 `train_metrics/` 或 `test_metrics/` 子目录 → 需要先评估。
若子目录存在 → 可直接可视化。

### 选择图形类型

| 用户意图 | 图形类型 |
|---------|---------|
| 查看拟合效果（时间序列）| `timeseries`（默认）|
| 查看模拟 vs 观测散点分布 | `scatter` |
| 没有特别指定 | 同时生成 `["timeseries", "scatter"]` |

### 何时不需要先评估

若用户提供的 `eval_dir`（如 `calibration_dir/test_metrics/`）已包含评估结果，
可直接传入该子目录，无需重新评估。

### 多流域场景

- 指定 `basin_ids` 只绘制特定流域
- 不指定 → 对所有率定流域生成图形

## 异常处理

| 异常 | 检查 | 处理 |
|------|------|------|
| `visualize` 报找不到数据文件 | `inspect_dir(eval_dir)` | 确认评估已完成且路径正确 |
| 图片路径不存在 | `inspect_dir(figures/)` | 检查 matplotlib backend 是否为 Agg |
| 只有训练期结果，没有测试期 | 确认用户需求 | 只绘训练期，或先评估测试期 |

## 输出

告知用户：
- 生成了哪些图（类型 + 文件名）
- 保存路径（完整路径，用户可直接找到）
- 若有多个流域，说明每个流域对应的文件名规律

**不要假设图片生成成功——检查 `visualize` 的返回值中是否包含实际文件路径。**
