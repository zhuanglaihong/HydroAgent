---
name: Standard Calibration
description: 使用 SCE-UA/GA/scipy 对单个或多个流域进行标准水文模型率定
keywords: [率定, calibrat, 优化参数, 参数优化, SCE_UA, GA, scipy]
tools: [calibrate_model, validate_basin, evaluate_model, visualize]
when_to_use: 单流域或多流域，使用传统优化算法，首选工作流
---

## 标准率定工作流

你正在帮助用户进行水文模型率定。请按以下步骤执行：

1. 调用 `validate_basin` 验证流域数据是否存在
2. 调用 `calibrate_model` 执行率定
3. 调用 `evaluate_model` 在测试期评估
4. 调用 `visualize` 生成水文过程线图
5. 用中文撰写分析报告

## 质量评估标准

- NSE ≥ 0.75: 优秀（Excellent）
- NSE ≥ 0.65: 良好（Good）
- NSE ≥ 0.50: 一般（Fair）
- NSE < 0.50: 较差（Poor）

## 报告格式

包含以下内容：
- 模型和流域信息
- 率定算法和参数设置
- NSE、RMSE、KGE 等性能指标
- 最优参数值
- 质量评估等级
- 改进建议

## hydromodel 配置结构参考

HydroClaw 的工具会自动构建正确的 hydromodel 配置，你**不需要**手动构建配置。
只需向 `calibrate_model` 传入正确的参数即可。

**关键字段说明**:
- `algorithm_name`: 算法名称 "SCE_UA" / "GA" / "scipy"
- `algorithm_params`: 算法参数（嵌套在 algorithm_params 内，不是顶层）
- `loss_config.obj_func`: 目标函数 "RMSE"（默认）/ "spotpy_kge" / "spotpy_nashsutcliffe"
- `param_range_file`: 自定义参数范围 YAML 文件路径（迭代优化时扩展边界用，默认 null）

## 注意事项

- 如果用户指定了算法参数（如 rep=500），确保传递给 calibrate_model 的 algorithm_params
- 如果流域验证失败，告知用户并建议有效的流域ID
- 率定完成后务必评估，提供训练期和测试期的对比
- 如果需要自定义参数范围（迭代优化场景），使用 `param_range_file` 参数指定 YAML 文件路径

## 迭代优化（手动）

当 NSE 较低时，可检测参数边界效应并手动迭代：

1. 先执行标准率定（calibrate_model）
2. 检查 NSE 是否达到目标（默认 0.65）
3. 如果参数触碰边界（距 min/max < 5%），扩展参数范围后重新率定
4. 如果 NSE 仍低但无边界问题，换随机种子再试（algorithm_params={"random_seed": 5678}）
5. 最多迭代 5 次，报告所有迭代的 NSE 变化轨迹

> 提示：若需要 LLM 自动完成边界分析和范围调整，改用 `llm_calibrate` 工具（LLM Calibration 技能）。
