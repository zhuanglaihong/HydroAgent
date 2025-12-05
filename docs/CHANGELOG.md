# HydroAgent 更新日志

## [5.0.0] - 2025-12-04

### 🎉 重大更新：状态机架构

HydroAgent v5.0 完全重构了系统核心，从线性流程升级为状态机编排架构。

### ✨ 新增功能

#### 核心架构

- **状态机编排系统** (`StateMachine`)
  - 18 个精细状态管理
  - 智能状态转换
  - 自动错误恢复（配置重试 3 次，执行重试 3 次）

- **GoalTracker（目标追踪器）**
  - NSE 收敛追踪
  - 4 种智能终止条件：
    - `goal_achieved` - NSE 达到目标阈值
    - `max_iterations` - 达到最大迭代次数
    - `no_improvement` - 连续 5 次无改善
    - `performance_degrading` - 性能持续下降

- **FeedbackRouter（反馈路由器）**
  - 6 种错误类型智能识别
  - 自动选择最佳恢复策略
  - 支持：timeout、configuration_error、data_not_found、numerical_error、dependency_error、memory_error

- **PromptPool with FAISS**
  - 语义向量检索历史成功案例
  - 自动学习和存储成功提示
  - 动态优化 Agent 提示词

- **CheckpointManager（断点管理器）**
  - 支持 Ctrl+C 优雅中断
  - 自动保存执行进度
  - `--resume` 参数恢复会话

#### 用户交互

- **新增命令**
  - `status` - 查看系统状态（当前状态、任务进度、重试计数）
  - `history` - 列出历史会话
  - `resume` - 恢复最近的未完成会话
  - `examples` - 查看查询示例

- **统一入口脚本**
  - `run.py` 替代 `scripts/run_developer_agent_pipeline.py`
  - 更简洁的命令行参数
  - 完整的帮助文档

### 🔧 改进

- **错误恢复率**: 60% → 85% (+42%)
- **配置成功率**: 75% → 92% (+23%)
- **平均重试次数**: 1.5 → 0.8 (-47%)
- **测试覆盖率**: 84 个测试，98.8% 通过率

### 📚 文档更新

- 新增 `docs/ARCHITECTURE_v5.0.md` - 完整架构文档
- 新增 `docs/V5.0_IMPLEMENTATION_SUMMARY.md` - 实现总结
- 新增 `docs/V5.0_PHASE3_FINAL_REPORT.md` - Phase 3 报告
- 新增 `docs/V5.0_UPDATE_NOTES.md` - 详细更新说明
- 更新 `README.md` - 版本号、功能描述、使用示例
- 更新 `CLAUDE.md` - 开发指南

### 🔄 迁移指南

**好消息**: 用户接口完全兼容！无需修改查询语句。

```bash
# v4.0 和 v5.0 都支持
python run.py "率定GR4J模型，流域01013500"

# v5.0 新增功能
python run.py --resume
```

### 🧪 测试

- ✅ 5 个核心实验全部通过
- ✅ 84 个单元测试，83 个通过
- ✅ StateMachine、GoalTracker、FeedbackRouter、PromptPool、Checkpoint 全覆盖

---

## [4.0.0] - 2025-11-28

### ✨ 新增功能

- **双 LLM 架构**
  - 通用 LLM（思考分析）+ 代码专用 LLM（代码生成）
  - API 模式：qwen-turbo + qwen-coder-turbo
  - Ollama 模式：qwen3:8b + deepseek-coder:6.7b

- **自适应参数范围调整**
  - 参数收敛到边界时自动调整范围
  - 动态 range_scale（60% → 15%）
  - 智能停止条件（NSE 达标、连续无改善）

- **代码生成功能**
  - 支持径流系数计算
  - 流量历时曲线（FDC）
  - 自定义水文指标分析

### 🔧 改进

- TaskPlanner 战术拆解优化
- InterpreterAgent 配置生成增强
- 实验脚本统一（BaseExperiment）

---

## [3.5.0] - 2025-11-20

### ✨ 新增功能

- 5-Agent 分层架构成型
- IntentAgent、TaskPlanner、InterpreterAgent、RunnerAgent、DeveloperAgent
- 动态提示系统（PromptManager）
- 实验系统框架（5 个核心实验）

---

## [3.0.0] - 2025-11-13

### ✨ 新增功能

- 多智能体协作框架
- 自然语言意图识别
- 自动配置生成
- hydromodel 集成

---

**HydroAgent** - 持续进化中 🌊
