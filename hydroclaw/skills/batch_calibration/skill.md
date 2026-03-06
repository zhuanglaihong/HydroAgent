---
name: Batch Calibration
description: 批量率定多个流域，汇总 NSE/RMSE 统计表，支持重复实验稳定性分析
keywords: [批量, batch, 多个流域, 多流域, 重复, 稳定性]
tools: [batch_calibrate, validate_basin, evaluate_model]
when_to_use: 需要在多个流域重复执行率定和评估，或分析算法稳定性
---

## 批量率定工作流

### 多流域批量率定

1. 调用 `batch_calibrate`，传入流域列表和模型参数
2. 工具内部对每个流域执行率定 + 评估
3. 返回汇总统计表（NSE、RMSE、KGE 各流域）
4. 用中文撰写批量分析报告

### 重复实验（稳定性分析）

当用户要求"重复率定N次"时，向 `batch_calibrate` 传入：
- `repeat_runs`: 重复次数
- `random_seeds`: 随机种子列表（可选，自动生成）

工具自动使用不同随机种子重复率定，计算 NSE 均值、标准差等稳定性指标。

### 结果汇总格式

```
| 流域      | NSE   | RMSE  | KGE   | 评级  |
|-----------|-------|-------|-------|-------|
| 12025000  | 0.82  | 1.23  | 0.79  | 优秀  |
| 01022500  | 0.71  | 1.67  | 0.68  | 良好  |
| 01031500  | 0.54  | 2.45  | 0.51  | 一般  |
```

### 注意事项

- 批量任务耗时较长，每个流域约 10-30 分钟
- 结果保存在各自的 output_dir 中
- 如需 LLM 智能调参，改用 `llm_calibrate`（LLM Calibration 技能）
