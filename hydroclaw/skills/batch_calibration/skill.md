---
name: Batch Calibration
description: 批量率定多个流域或多个模型，使用任务列表追踪进度，汇总 NSE/RMSE 统计
keywords: [批量, batch, 多个流域, 多流域, 多模型, 重复, 稳定性, 对比实验]
tools: [calibrate_model, validate_basin, evaluate_model, inspect_dir, read_file]
when_to_use: 需要在多个流域或多个模型重复执行率定和评估时
---

## 目标

自主完成多个率定子任务，无需用户介入，最终汇报：
- 每个流域/模型组合的 NSE（训练期 + 测试期）
- 汇总统计表（所有组合，包含失败记录）
- 最优组合推荐 + 改进建议

## 判断框架

### 任务启动：规划先于行动

接到批量任务时，**先制定完整任务列表**，再逐一执行：

```
create_task_list(
    goal="批量率定 [N] 个流域的 [模型] 模型",
    tasks=[
        {"id": "basin_X_modelY", "basin": "X", "model": "Y", "status": "pending"},
        ...
    ]
)
```

任务列表保存到磁盘，断点可恢复——即使中途失败也不会丢失进度。

### 执行循环

```
while get_pending_tasks() 返回待执行任务:
    取出当前任务
    validate_basin(basin_id)         # 确认数据
    calibrate_model(...)             # 率定
    evaluate_model(..., train_period) # 训练期指标
    evaluate_model(..., test_period)  # 测试期指标
    update_task(id, "done", nse=..., kge=...)
```

### 失败处理：不中止整个批次

某子任务失败时：
1. 调用 `update_task(id, "failed", notes="错误原因")`
2. 继续下一个任务
3. 记录失败原因，供最终报告参考

**不要因为单个子任务失败而中断整个批次。**

### 何时需要观测文件

| 情况 | 操作 |
|------|------|
| 某任务 `calibrate_model` 返回成功，但后续 `evaluate_model` 报找不到 config | `inspect_dir(calibration_dir)` |
| 某任务 NSE 异常低（< 0）| `read_file(calibration_dir/calibration_results.json)` 查参数是否触边界 |
| 不确定之前的任务是否已运行 | 检查任务列表状态（get_pending_tasks 会告知进度）|

### 动态调整：运行中追加任务

若发现多个流域 NSE 普遍 < 0.5（怀疑边界问题）：
- 追加 `llm_calibrate` 重试任务，标记为更高优先级
- 在任务备注中说明追加原因

### 何时汇报

**所有任务完成（无 pending 任务）后**再汇报，不要在执行途中打断。

## 汇总报告格式

```
| 流域      | 模型  | 训练 NSE | 测试 NSE | KGE  | 等级  | 备注  |
|-----------|-------|---------|---------|------|-------|-------|
| 12025000  | GR4J  | 0.82    | 0.79    | 0.77 | 优秀  |       |
| 01022500  | GR4J  | 0.71    | 0.64    | 0.68 | 良好  |       |
| 01031500  | XAJ   | 0.43    | 0.38    | 0.40 | 较差  | 触边界|
```

报告包含：
- 成功/失败任务数统计
- 最优流域-模型组合
- 失败任务的错误摘要
- 改进建议（如哪些流域应换 llm_calibrate 重试）

## 注意

- 批量任务耗时较长（每个流域约 10-30 分钟）
- 向用户报告整体进度（"已完成 3/10，当前：流域 X"）
- 若用户中途问进度，读取任务列表状态回答，不要重新率定
