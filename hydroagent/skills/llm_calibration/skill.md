---
name: LLM Calibration
description: LLM 智能参数范围调整，突破边界限制，迭代优化 NSE
keywords: [ai率定, 智能率定, 专家模式, llm率定, ai calibrat, llm calibrat]
tools: [llm_calibrate, validate_basin, evaluate_model, inspect_dir, read_file, visualize]
when_to_use: 传统率定 NSE 偏低时，或用户明确要求 AI/智能率定
---

## 目标

通过 LLM 作为**虚拟水文专家**，迭代调整 SCE-UA 的参数搜索空间，
最终获得比单轮 SCE-UA 更高的训练期 NSE，并在测试期验证泛化能力。

成功标志：
- 达到 `nse_target`（默认 0.75），或在 `max_rounds` 轮内显著改善
- 返回 `history` 中可看到 NSE 随轮次的变化轨迹
- 最终参数无明显边界效应（`final_boundary_hits` 为空列表）

## 判断框架

### 何时选择此技能（而非标准率定）

满足以下任一条件即优先选择 `llm_calibrate`：
- 用户明确要求"AI率定"、"智能调参"、"LLM率定"
- 已知标准 SCE-UA 结果 NSE < 0.65
- 已知某参数触碰边界（距边界 < 5%）
- 想研究参数范围对结果的影响

### 任务开始

- 先调用 `validate_basin` 确认流域数据
- 告知用户：`llm_calibrate` 每轮都是完整 SCE-UA，共最多 `max_rounds` 轮（默认 5），总耗时较长

### `llm_calibrate` 返回后，如何解读结果

`llm_calibrate` 内部已调用 `evaluate_model` 计算每轮的训练期 NSE，
但**测试期评估不在内**，需要在返回后显式调用：

```
evaluate_model(
    calibration_dir=result['calibration_dir'],
    eval_period=test_period
)
```

其中 `test_period` 可从 `llm_calibrate` 返回的 `history[-1]` 或用户输入中获取。

### 如何解读 `history` 和边界信息

检查 `history` 中每轮记录（含 `round`, `nse`, `boundary_hits`, `param_ranges`）：

| 观察到的情况 | 判断 |
|------------|------|
| NSE 逐轮上升，最终达到目标 | 成功，边界扩展有效 |
| NSE 无变化，`boundary_hits` 为空 | 范围本身不是瓶颈，考虑换模型或数据问题 |
| `final_boundary_hits` 非空 | 最终参数仍触边界，可手动扩展 `param_ranges` 再试 |
| 某轮失败（`error` 字段存在）| 跳过该轮，看其余轮次趋势 |

### 何时主动观测文件

| 情况 | 该做什么 |
|------|---------|
| 不确定某轮的 `calibration_dir` 是否完整 | `inspect_dir(history[i]['calibration_dir'])` |
| 想看具体参数值和边界距离 | `read_file(calibration_dir/calibration_results.json)` |
| 测试期 `evaluate_model` 失败 | `inspect_dir(best calibration_dir)` 诊断 |

## 异常处理

| 异常 | 处理方式 |
|------|---------|
| `llm_calibrate` 返回 `success: False` | 检查 `error` 字段；若为 LLM 未连接，检查 API key |
| 所有轮次 NSE 均 < 0.5 | 观测参数文件，检查是否数据问题（而非范围问题）|
| 某轮 calibration_dir 为空字符串 | 该轮失败，查看该轮 `error`，继续看 `best_nse` |
| `nse_target` 始终未达到 | 报告最优 NSE，给出原因分析和后续建议 |

## 报告格式

最终报告包含：
- **收敛轨迹**：每轮 NSE（表格形式，展示改善趋势）
- **LLM 调整记录**：哪些参数范围被扩展了多少
- **最优参数及边界状态**：`final_boundary_hits` 分析
- **测试期泛化指标**：NSE / KGE / RMSE
- **与标准 SCE-UA 对比**：若已知单轮结果，对比提升幅度
- **改进建议**：基于最终边界情况

## 参考

Zhu et al. (2026), GRL, doi:10.1029/2025GL120043
HydroAgent 扩展：LLM 不直接搜索参数，而是通过范围调整指导 SCE-UA 跳出局部最优。
