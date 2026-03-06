---
name: Evaluation
description: 在测试期评估已率定的水文模型，计算 NSE、RMSE、KGE、PBIAS 指标
keywords: [评估, evaluat, 测试期, 验证, test period, 指标]
tools: [evaluate_model, visualize]
when_to_use: 率定完成后，在独立测试期评估模型泛化性能
---

## 模型评估工作流

用于在独立测试期评估已率定水文模型的泛化性能。

### 执行步骤

1. 调用 `evaluate_model`，传入率定结果目录（`calibration_dir`）
2. 调用 `visualize` 生成测试期水文过程线
3. 输出评估报告

### 评估指标说明

| 指标 | 全称 | 优秀阈值 | 说明 |
|------|------|----------|------|
| NSE  | Nash-Sutcliffe Efficiency | ≥ 0.75 | 模型整体拟合优度 |
| RMSE | Root Mean Square Error | 越小越好 | 流量预测误差 |
| KGE  | Kling-Gupta Efficiency | ≥ 0.75 | 综合考虑相关性、偏差、变异性 |
| PBIAS | Percent Bias | < ±10% | 水量平衡偏差 |

### 注意事项

- `calibration_dir` 是率定工具返回的 `calibration_dir` 字段
- 如果未指定 `test_period`，系统自动从率定配置中读取
- 评估结果保存在 `calibration_dir/evaluation_*/` 子目录
