---
name: Standard Calibration
description: 使用 SCE-UA/GA/scipy 对单个或多个流域进行标准水文模型率定
keywords: [率定, calibrat, 优化参数, 参数优化, SCE_UA, GA, scipy]
tools: [calibrate_model, validate_basin, evaluate_model, visualize, inspect_dir, read_file]
when_to_use: 单流域或多流域，使用传统优化算法，首选工作流
---

## 目标

完成一次完整的水文模型率定实验，获得：
1. 已保存到磁盘的最优参数（`calibration_dir`）
2. **训练期**的 NSE / KGE / RMSE 指标（拟合质量）
3. **测试期**的 NSE / KGE / RMSE 指标（泛化能力）
4. 基于指标和参数边界情况的专业改进建议

## 判断框架

### 任务开始时

- 涉及流域数据（率定/评估）→ **先调用 `validate_basin`**，确认数据存在再继续
- 用户已提供 `calibration_dir` 且只需评估 → 跳过率定，直接调用 `evaluate_model`

### 率定完成后（`calibrate_model` 返回 `success: True`）

`calibrate_model` **只返回参数，不返回任何指标**。必须显式调用评估：

```
evaluate_model(calibration_dir, eval_period=train_period)   # 训练期
evaluate_model(calibration_dir, eval_period=test_period)    # 测试期
```

`train_period` 和 `test_period` 在 `calibrate_model` 的返回值中已给出，直接使用。

### 如何判断是否需要观测文件

| 情况 | 该怎么做 |
|------|---------|
| 返回了 `calibration_dir` 但不确定文件是否完整 | `inspect_dir(calibration_dir)` |
| `evaluate_model` 失败，报 config 不存在 | `inspect_dir(calibration_dir)` 诊断根因 |
| 想验证最优参数的具体值 | `read_file(observable_files['calibration_results.json'])` |
| 想看完整指标（而非摘要） | `read_file(observable_files['metrics_csv'])` |
| 指标异常（NSE < 0 或极低）| 先读 `calibration_results.json`，对照下方边界表判断 |

### 参数边界判断（无需额外工具，直接推理）

读取参数后，对照标准范围：

| 模型 | 参数 | 典型范围 |
|------|------|---------|
| GR4J | x1 (产流库容) | [1, 2000] mm |
| GR4J | x2 (地下水交换) | [-5, 3] mm/d |
| GR4J | x3 (汇流库容) | [1, 500] mm |
| GR4J | x4 (单位线时基) | [0.5, 4] d |

若某参数距边界 < 5%（如 x1=1980，接近上界 2000），视为**触边界**。
触边界且 NSE < 0.65 → 推荐改用 `llm_calibrate` 扩展搜索范围。

### 如何解读评估结果

- NSE ≥ 0.75: 优秀，可直接报告
- NSE ≥ 0.65: 良好，可接受
- NSE ≥ 0.50: 一般，建议分析原因（边界？数据？）
- NSE < 0.50: 较差，主动诊断：检查参数是否触边界，建议 `llm_calibrate`

### 是否需要可视化

- 用户明确要求图形 → 调用 `visualize`
- 用户只要数字结果 → 不必强制可视化

## 异常处理

| 异常 | 检查什么 | 怎么处理 |
|------|---------|---------|
| `validate_basin` 失败 | 流域 ID 格式（8 位）？数据目录配置？ | 告知用户并给出有效 ID 示例 |
| `calibrate_model` 失败，HDF error | 文件锁 | 再试一次（工具内部已自动重试） |
| `calibrate_model` 失败，dataset path | DATASET_DIR 未指向 CAMELS_US 父目录 | 提示用户检查 `configs/definitions_private.py` |
| `evaluate_model` 失败，config not found | 率定未完成 | `inspect_dir(calibration_dir)` 确认文件列表 |
| NSE 极低（< 0） | 参数触边界 | 建议换 `llm_calibrate` 或扩展 `param_range_file` |

## 报告格式

最终报告（中文）包含：
- 模型名称、流域 ID、算法
- 训练期指标：NSE / KGE / RMSE
- 测试期指标：NSE / KGE / RMSE（泛化能力）
- 最优参数值及边界情况分析
- 质量等级（优秀/良好/一般/较差）
- 改进建议（如触边界 → llm_calibrate，如 NSE 过低 → 换算法）

## 关键配置参考

- `algorithm_params`: 算法参数 dict，如 `{"rep": 500, "ngs": 200}`（不是字符串）
- `param_range_file`: 自定义参数范围 YAML，迭代扩展边界时使用
- 默认训练期：2000-01-01 ~ 2009-12-31 | 默认测试期：2010-01-01 ~ 2014-12-31
