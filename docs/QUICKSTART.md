# HydroAgent v5.0 快速开始指南

**版本**: v5.0 (State Machine Architecture)
**更新日期**: 2025-12-04

---

## 🚀 快速启动

### 1. 交互式模式（推荐）

```bash
python run.py
```

启动后会看到友好的欢迎界面和功能菜单，支持以下命令：
- `help` - 查看详细帮助
- `examples` - 查看查询示例
- `status` - 查看系统状态 **（v5.0 新增）**
- `history` - 查看历史会话
- `resume` - 恢复中断的会话
- `clear` - 清屏
- `exit` 或 `quit` - 退出系统

**优雅中断**: 随时按 `Ctrl+C`，进度会自动保存！

---

### 2. 单次查询模式

```bash
python run.py "率定GR4J模型，流域01013500"
```

适合快速执行单个任务。

---

### 3. 恢复会话

中断后恢复：

```bash
# 自动恢复最近的未完成会话
python run.py --resume

# 恢复指定会话
python run.py --resume experiment_results/exp_3/session_xxx
```

---

## 📖 常用查询示例

### 基础率定
```
率定GR4J模型，流域01013500
```

### 自定义算法参数
```
使用SCE-UA算法率定流域01013500，算法迭代500轮
```

### 迭代优化
```
用xaj模型率定流域01013500，如果参数收敛到边界，自动调整范围重新率定
```

### 自定义分析
```
率定完成后，请帮我计算流域的径流系数，并画流量历时曲线FDC
```

### 稳定性验证
```
重复率定流域01013500 5次，分析参数稳定性
```

---

## 🔧 后端配置

### 使用 API 后端（默认）
```bash
python run.py --backend api
```

### 使用 Ollama 本地模型
```bash
python run.py --backend ollama
```

---

## 📊 支持的功能

### 1️⃣  模型率定
- GR4J, GR5J, GR6J
- XAJ (新安江模型)

### 2️⃣  优化算法
- SCE-UA
- GA (遗传算法)
- PSO (粒子群算法)
- DE (差分进化)

### 3️⃣  高级功能（v5.0）
- ✅ 状态机编排（18 状态智能流转）
- ✅ GoalTracker（NSE 收敛追踪，4 种终止条件）
- ✅ FeedbackRouter（智能错误路由，6 种错误类型）
- ✅ PromptPool（FAISS 语义检索历史案例）
- ✅ 自动迭代优化（参数边界检测）
- ✅ 代码生成（径流系数、FDC、水量平衡等）
- ✅ Checkpoint/Resume（断点续传）
- ✅ 双LLM架构（通用 + 代码生成）

---

## 💡 交互式会话示例

```
======================================================================
🌊 HydroAgent v5.0 - 智能水文模型助手
   基于状态机的多智能体编排系统
======================================================================

📚 HydroAgent 功能列表：
----------------------------------------------------------------------
1️⃣  模型率定
   示例: 率定GR4J模型，流域01013500

2️⃣  模型评估
   示例: 评估流域01013500的率定结果

3️⃣  迭代优化
   示例: 用xaj模型率定流域01013500，如果参数收敛到边界，自动调整范围重新率定

4️⃣  自定义分析
   示例: 率定完成后，请帮我计算流域的径流系数，并画流量历时曲线FDC

5️⃣  稳定性验证
   示例: 重复率定流域01013500 5次，分析参数稳定性
----------------------------------------------------------------------

💡 提示:
  - 输入 'help' 查看详细帮助
  - 输入 'examples' 查看更多示例
  - 输入 'status' 查看系统状态 （v5.0 新增）
  - 输入 'history' 查看历史会话
  - 输入 'resume' 恢复上次中断的会话
  - 按 Ctrl+C 可随时优雅退出（进度会自动保存）

💬 HydroAgent> 率定GR4J模型，流域01013500

======================================================================
📝 查询: 率定GR4J模型，流域01013500
======================================================================

⏳ 正在处理您的请求...

🎯 Orchestrator [RECOGNIZING_INTENT]
   ✅ 任务类型: CALIBRATION, 模型: gr4j, 流域: 01013500

🎯 Orchestrator [PLANNING_TASKS]
   ✅ 拆解为 1 个子任务
   ✅ PromptPool 检索到 3 条相关历史案例

🎯 Orchestrator [GENERATING_CONFIG]
   ✅ 生成 hydromodel 配置字典

🎯 Orchestrator [EXECUTING_CALIBRATION]
   SCE-UA Progress: 100%|███████████| 500/500 [02:15<00:00]
   ✅ NSE_train = 0.72 (GoalTracker: goal_achieved)

🎯 Orchestrator [ANALYZING_RESULTS]
   质量评估: 良好 (Good)

======================================================================
📊 执行结果
======================================================================

✅ 任务完成！

任务类型: standard_calibration
最优参数: x1=0.77, x2=0.0002, x3=0.30, x4=0.70

📁 结果目录: experiment_results/session_xxx
⏱️  耗时: 187.5秒

======================================================================

💬 HydroAgent> status

======================================================================
📊 系统状态
======================================================================

🔧 配置:
  - 版本: v5.0 (State Machine Architecture)
  - LLM后端: api
  - 工作目录: experiment_results
  - Checkpoint: ✅ 启用

🤖 智能体状态:
  - Orchestrator: ✅ 已初始化
  - 当前状态: IDLE

======================================================================

💬 HydroAgent> exit
👋 再见！
```

---

## 🛡️ 中断和恢复

### 优雅中断
在任何时候按 `Ctrl+C`:

```
⚠️  检测到中断信号...
正在安全保存当前进度...
✅ 进度已保存到: experiment_results/exp_3/session_xxx/checkpoint.json

💡 恢复方式：
   python run.py --resume experiment_results/exp_3/session_xxx

👋 再见！
```

### 恢复执行
```bash
python run.py --resume experiment_results/exp_3/session_xxx
```

系统会自动从中断点继续执行！

---

## 📜 查看历史

### 命令行方式
```bash
python run.py --history
```

### 交互式方式
```
💬 HydroAgent> history
```

输出示例：
```
======================================================================
📜 历史会话
======================================================================

1. ✅ session_20251126_152236_63dfd8c3
   查询: 用xaj模型率定流域01013500，如果参数收敛到边界，自动调整范围...
   时间: 2025-11-26 15:22:36
   状态: completed
   路径: experiment_results/exp_3/session_20251126_152236_63dfd8c3

2. ⏸️ session_20251126_170759_86e537f4
   查询: 率定完成后，请帮我计算流域的径流系数，并画流量历时曲线FDC
   时间: 2025-11-26 17:07:59
   状态: pending
   路径: experiment_results/exp_4/session_20251126_170759_86e537f4
```

---

## 🆕 v5.0 新功能详解

### 1. `status` 命令 - 查看系统状态

在交互模式下输入 `status` 可以查看：

```
💬 HydroAgent> status

======================================================================
📊 系统状态
======================================================================

🔧 配置:
  - 版本: v5.0 (State Machine Architecture)
  - LLM后端: api
  - 工作目录: experiment_results
  - Checkpoint: ✅ 启用

🤖 智能体状态:
  - Orchestrator: ✅ 已初始化
  - 当前状态: EXECUTING_CALIBRATION
  - 任务进度: 2/5

💾 Checkpoint:
  - 文件: experiment_results/session_xxx/checkpoint.json
  - 状态: ✅ 已保存
======================================================================
```

**用途**:
- 实时监控任务进度
- 查看当前状态机状态
- 检查 Checkpoint 是否正常保存
- 诊断系统配置

---

### 2. 状态机可见性

v5.0 执行过程中会显示状态转换：

```
🎯 Orchestrator [IDLE]
🎯 Orchestrator [RECOGNIZING_INTENT]    # 意图识别
🎯 Orchestrator [PLANNING_TASKS]        # 任务规划
🎯 Orchestrator [GENERATING_CONFIG]     # 配置生成
🎯 Orchestrator [EXECUTING_CALIBRATION] # 模型执行
🎯 Orchestrator [ANALYZING_RESULTS]     # 结果分析
🎯 Orchestrator [COMPLETED]             # 完成
```

**18 个状态包括**:
- IDLE（空闲）
- RECOGNIZING_INTENT（识别意图）
- PLANNING_TASKS（规划任务）
- GENERATING_CONFIG（生成配置）
- EXECUTING_CALIBRATION（执行率定）
- EXECUTING_EVALUATION（执行评估）
- EXECUTING_SIMULATION（执行模拟）
- ANALYZING_RESULTS（分析结果）
- CONFIG_RETRY（配置重试）
- EXECUTION_RETRY（执行重试）
- ADJUSTING_PARAMS（调整参数）
- GENERATING_CODE（生成代码）
- SUMMARIZING（汇总）
- COMPLETED（完成）
- FAILED（失败）
- RETRYING（重试中）
- WAITING_FOR_INPUT（等待输入）
- RESUMING（恢复中）

---

### 3. GoalTracker - 智能终止

系统会自动判断何时停止迭代：

```
✅ NSE_train = 0.72 (GoalTracker: goal_achieved)        # NSE 达标
⏹️ 达到最大迭代次数 (GoalTracker: max_iterations)      # 迭代上限
📉 连续5次无改善 (GoalTracker: no_improvement)          # 停滞
📉 性能持续下降 (GoalTracker: performance_degrading)    # 退化
```

**4 种终止条件**:
1. **goal_achieved**: NSE ≥ 目标阈值（默认 0.65）
2. **max_iterations**: 达到最大迭代次数
3. **no_improvement**: 连续 5 次迭代 NSE 无改善
4. **performance_degrading**: 连续下降

---

### 4. FeedbackRouter - 智能错误恢复

遇到错误时自动选择最佳恢复策略：

```
⚠️ 检测到错误: timeout
🔀 FeedbackRouter 路由: retry_with_reduce_iterations
   → 减少迭代次数至 300 轮重试
```

**6 种错误类型与路由策略**:

| 错误类型 | 路由策略 | 说明 |
|---------|---------|------|
| timeout | retry_with_reduce_iterations | 减少迭代重试 |
| configuration_error | regenerate_config | 重新生成配置 |
| numerical_error | retry_with_default_config | 使用默认参数 |
| memory_error | reduce_complexity | 降低复杂度 |
| data_not_found | fail_with_error | 直接失败 |
| dependency_error | fail_with_error | 直接失败 |

**自动重试**: 配置失败最多重试 3 次，执行失败最多重试 3 次

---

### 5. PromptPool - 历史案例检索

系统会自动检索相似的历史成功案例：

```
🎯 Orchestrator [PLANNING_TASKS]
   ✅ 拆解为 1 个子任务
   ✅ PromptPool 检索到 3 条相关历史案例
      - 相似度 0.92: "率定GR4J，流域01013500，SCE-UA 算法"
      - 相似度 0.88: "GR4J 标准率定，流域 01055000"
      - 相似度 0.85: "率定GR5J模型，流域01013500"
```

**技术**: FAISS 向量语义检索

**优势**:
- 动态优化 Agent 提示词
- 借鉴历史成功经验
- 提高配置成功率（75% → 92%）

---

## 🔍 其他命令

### 查看示例
```bash
python run.py --examples
```

### 设置日志级别
```bash
python run.py --log-level DEBUG
```

### 指定工作目录
```bash
python run.py --workspace my_experiments
```

### 禁用checkpoint
```bash
python run.py --no-checkpoint
```

---

## 📞 获取帮助

- 系统内帮助: 输入 `help`
- 查看版本: `python run.py --version`
- 完整选项: `python run.py --help`

---

## 🎯 最佳实践

### 1. 使用交互模式进行探索
方便多次查询和测试，使用 `status` 实时监控

### 2. 启用 checkpoint（默认启用）
长时间任务可随时 Ctrl+C 中断，进度自动保存

### 3. 利用 PromptPool 自动学习
每次成功执行都会自动保存，后续查询会更智能

### 4. 信任 GoalTracker 自动终止
无需手动判断何时停止，系统会自动检测 NSE 收敛

### 5. 让 FeedbackRouter 处理错误
遇到错误不用慌，系统会智能选择恢复策略

### 6. 查看历史和恢复会话
`history` 命令查看之前的实验，`resume` 恢复未完成任务

### 7. 合理使用查询语句
参考 `examples` 命令学习正确的查询方式

---

## 📈 v5.0 性能提升

与 v4.0 相比：
- ✅ 错误恢复率: 60% → 85% (+42%)
- ✅ 配置成功率: 75% → 92% (+23%)
- ✅ 平均重试次数: 1.5 → 0.8 (-47%)
- ✅ 新增断点续传支持
- ✅ 新增智能终止判断
- ✅ 新增语义案例检索

---

## 📞 获取更多帮助

- **系统内帮助**: 交互模式输入 `help`
- **查看版本**: `python run.py --version`
- **完整选项**: `python run.py --help`
- **查看示例**: 交互模式输入 `examples`
- **查看状态**: 交互模式输入 `status`
- **详细文档**:
  - `README.md` - 项目概览
  - `docs/ARCHITECTURE_v5.0.md` - 架构设计
  - `docs/V5.0_UPDATE_NOTES.md` - v5.0 更新说明
  - `CHANGELOG.md` - 版本历史

---

**HydroAgent v5.0 - 更智能、更可靠、更强大！** 🌊

Happy modeling!
