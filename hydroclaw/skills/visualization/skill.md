---
name: Visualization
description: 生成水文过程线图、散点图等可视化结果
keywords: [可视化, visualiz, 画图, 绘图, 过程线, 散点图, plot, figure]
tools: [visualize]
when_to_use: 展示模型模拟结果、率定评估图形时
---

## 可视化工作流

生成水文模型率定和评估结果的可视化图形。

### 执行步骤

1. 调用 `visualize`，传入率定/评估结果目录
2. 指定需要的图形类型（可选）
3. 告知用户生成的图片文件路径

### 支持的图形类型

- `timeseries`（默认）: 水文过程线图（观测 vs 模拟）
- `scatter`: 散点图（观测 vs 模拟）

### 参数说明

- `calibration_dir`: 率定结果目录（必填）
- `plot_types`: 图形类型列表，默认 ["timeseries", "scatter"]
- `basin_ids`: 指定要绘图的流域，默认全部

### 注意事项

- 图片保存在 `calibration_dir/evaluation_*/figures/` 目录
- 需要先完成评估（`evaluate_model`），才能生成测试期的图形
