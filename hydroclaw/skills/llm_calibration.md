## LLM 专家率定工作流（Zhu et al. 2026 方法）

当用户要求"用AI率定"、"智能率定"、"专家模式率定"时使用此工作流。

### 执行步骤

1. 调用 `validate_basin` 验证流域
2. 调用 `llm_calibrate` 执行 LLM 闭环率定
   - LLM 扮演水文专家，直接建议参数
   - 每轮模拟后分析 NSE/RMSE，智能调整参数
   - 默认最多 200 轮，目标 NSE ≥ 0.75
3. 调用 `evaluate_model` 在测试期验证
4. 调用 `visualize` 生成收敛曲线 + 水文过程线
5. 生成报告，包含：
   - 迭代收敛过程（NSE 随迭代变化）
   - 最优参数及其物理解释
   - 与传统算法的对比（如有）

### 何时推荐此模式

- 用户想要更具物理可解释性的参数
- 传统算法收敛慢或陷入局部最优
- 用户明确要求"AI率定"或"智能调参"

### 参考文献

Zhu et al. (2026), Geophysical Research Letters, doi:10.1029/2025GL120043
"LLM as Virtual Hydrologist: 200 iterations to near-optimal convergence"
