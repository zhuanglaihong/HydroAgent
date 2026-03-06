---
name: LLM Calibration
description: LLM 智能参数范围调整，突破边界限制，迭代优化 NSE
keywords: [ai率定, 智能率定, 专家模式, llm率定, ai calibrat, llm calibrat]
tools: [llm_calibrate, validate_basin, evaluate_model, visualize]
when_to_use: 传统率定 NSE 偏低时，或用户明确要求 AI/智能率定
---

## LLM 专家率定工作流（智能参数范围调整）

当用户要求"AI率定"、"智能率定"、"专家模式率定"、"LLM率定"时使用此工作流。

### 核心机制

`llm_calibrate` 工具将 LLM 作为**虚拟水文专家**，在 SCE-UA 优化算法外层构建迭代决策循环：

```
轮次 1: SCE-UA 在初始参数范围内优化 → 得到最优参数
    ↓
LLM 分析：参数是否碰到边界？NSE 是否满足目标？
    ↓ 是 (边界效应)
轮次 2: SCE-UA 在调整后的更大范围内重新优化
    ↓
... 最多 max_rounds 轮，直到满足 nse_target 或无需调整
```

**关键区别**：与传统 SCE-UA 相比，LLM 负责识别边界效应并智能扩展搜索空间，而非替代优化算法本身。

### 执行步骤

1. 调用 `validate_basin` 验证流域
2. 调用 `llm_calibrate` 执行 LLM 闭环率定
   - 默认最多 5 轮（每轮执行完整 SCE-UA）
   - 目标 NSE ≥ 0.75（可调）
   - LLM 检测参数边界效应并调整范围
3. 调用 `evaluate_model` 在测试期验证最优参数
4. 调用 `visualize` 生成收敛曲线 + 水文过程线
5. 生成报告，包含：
   - 每轮迭代的 NSE 变化（收敛过程）
   - 最优参数及其物理解释
   - LLM 调整的参数范围记录
   - 与标准 SCE-UA（单轮）的性能对比

### 何时推荐此模式

- 传统单轮 SCE-UA 结果较差（NSE < 0.65），怀疑参数范围设置不合理
- 用户明确要求"AI率定"或"智能调参"
- 想要了解参数边界对率定结果的影响

### 参考文献

Zhu et al. (2026), Geophysical Research Letters, doi:10.1029/2025GL120043
HydroClaw 在此基础上扩展：LLM 不直接搜索参数，而是通过范围调整指导 SCE-UA 跳出局部最优。
