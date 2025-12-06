# HydroAgent v5.0 实验方案

**版本**: v5.0 State Machine Architecture
**设计时间**: 2025-12-04
**最后更新**: 2025-12-06
**目标**: 论文发表 - 系统能力验证与性能评估

---

## 📋 实验设计总则

### 核心目标
1. **验证系统核心功能**：意图理解、配置生成、任务执行、结果分析
2. **评估 v5.0 创新点**：状态机、GoalTracker、FeedbackRouter、PromptPool
3. **证明系统鲁棒性**：错误恢复、大规模处理、断点续传

### 设计原则
- **可重复性**：固定种子、标准测试集、明确参数
- **可对比性**：设置基线、量化指标、统计检验
- **真实性**：使用真实数据、避免过拟合、报告失败

---

## 🎯 实验体系（精简版）

```
实验体系
├── Part 1: 系统基础能力（3个实验）
│   ├── Exp 1. 端到端功能验证 ✅ (已实现)
│   ├── Exp 2. 自然语言理解鲁棒性 ✅ (已实现)
│   └── Exp 3. 配置生成可靠性 ✅ (已实现)
│
├── Part 2: v5.0 核心创新（3个实验）
│   ├── Exp 4. 状态机智能编排 (待实现)
│   ├── Exp 5. 错误恢复机制 (待实现)
│   └── Exp 6. 语义案例检索 (待实现)
│
└── Part 3: 系统鲁棒性（2个实验）
    ├── Exp 7. 大规模任务处理 (待实现)
    └── Exp 8. 断点续传可靠性 (待实现)
```

---

## 📊 Part 1: 系统基础能力

### Exp 1: 端到端功能验证 ✅

**目标**: 验证完整流程的准确性和成功率

**实验组成** (4个子实验):

#### **Exp 1a: 标准问题模板测试** ✅ (已精简)
- **测试集**: 15个代表性模板（原40个）
- **模板分类**:
  - **率定任务模板** (6个): 从最简单到最复杂
    1. 基础率定: `率定GR4J模型，流域01539000`
    2. 指定算法: `率定XAJ模型，流域02070000，使用SCE-UA算法`
    3. 指定算法参数: `率定GR4J模型，流域02177000，使用SCE-UA算法，迭代500轮`
    4. 指定时间期: `率定XAJ模型，流域03346000，训练期1990-2000，测试期2005-2015`
    5. 指定warmup: `率定GR4J模型，流域03500000，warmup期365天`
    6. 全参数率定: `率定GR4J模型，流域11532500，使用SCE-UA算法，迭代600轮，复合体数量200，训练期1985-1995，测试期2005-2014，warmup期365天`

  - **其他任务类型** (9个):
    7. 评估任务 (evaluation)
    8. 模拟任务 (simulation)
    9-11. 扩展分析 (extended_analysis) - 径流系数、FDC曲线
    12-13. 迭代优化 (iterative_optimization) - 参数边界/NSE目标
    14-15. 复杂组合

- **有效流域**: 01539000, 02070000, 02177000, 03346000, 03500000, 11532500, 12025000, 14301000, 14306500, 14325000

- **实现文件**: `exp_1a_standard_calibration.py`

#### **Exp 1b: 算法×模型全覆盖测试** ✅
- **测试集**: 36个 (3算法 × 4模型 × 3流域)
- **算法**: SCE-UA, scipy, GA
- **模型**: GR4J, XAJ, GR5J, GR6J
- **流域**: 从有效流域中选择3个

- **实现文件**: `exp_1b_algorithm_model_coverage.py`

#### **Exp 1c: 多任务查询测试** ✅
- **测试集**: 20个多任务查询
- **任务类型**:
  - 代码生成任务 (8个): 计算径流系数、画FDC曲线等
  - 参数调整任务 (8个): 指定迭代轮数、训练期等
  - 迭代优化任务 (4个): 参数边界调整、NSE目标驱动

- **实现文件**: `exp_1c_multi_task.py`

#### **Exp 1d: 批量处理测试** (可选)
- **测试集**: 10个流域批量率定
- **实现文件**: `exp_1d_batch_processing.py`

**评估指标**:
```
核心指标：
- Intent Recognition Accuracy (意图识别准确率): ≥95%
- Config Generation Success Rate (配置生成成功率): ≥92%
- Task Execution Success Rate (任务执行成功率): ≥90%
- End-to-End Success Rate (端到端成功率): ≥85%

辅助指标：
- Average Execution Time (平均执行时间): 记录基准
- Parameter Extraction Completeness (参数提取完整度): ≥90%
```

---

### Exp 2: 自然语言理解鲁棒性 ✅

**目标**: 测试系统对非标准输入的容错能力

**测试集**: 60 个包含"噪音"的查询
- 拼写错误: 15 个（"率定"→"率顶"）
- 标点异常: 15 个（缺失、错误）
- 参数顺序混乱: 10 个
- 口语化表达: 10 个
- 中英混合: 10 个

**有效流域**: 已替换为10个有效流域（01539000, 02070000, 03500000等）

**评估指标**:
```
- Noise Tolerance Rate (噪音容忍率): ≥85%
- Key Information Extraction Rate (关键信息提取率): ≥90%
- Error Recovery Rate (错误恢复率): ≥80%
```

**噪音类型对照**:
| 噪音类型 | 原始 | 噪音版本 | 目标准确率 |
|---------|------|---------|-----------|
| 拼写错误 | 率定GR4J | 率顶GR4J摸型 | ≥80% |
| 标点缺失 | 率定GR4J，流域01539000 | 率定GR4J流域01539000 | ≥90% |
| 顺序混乱 | 率定GR4J，流域01539000 | 流域01539000率定GR4J | ≥85% |
| 口语化 | 率定流域01539000 | 帮我跑一下01539000这个流域 | ≥75% |

**实现文件**: `exp_2_nlp_robustness.py`

---

### Exp 3: 配置生成可靠性 ✅

**目标**: 验证配置生成的成功率和正确性

**测试集**: 60 个配置生成任务（不执行hydromodel）
- 标准配置: 30 个（完整参数）
- 缺省配置: 20 个（部分参数，需自动补全）
- 边界配置: 10 个（极端参数值）

**有效流域**: 已替换为10个有效流域

**评估指标**:
```
- Config Generation Success Rate (配置生成成功率): ≥92%
- Config Validation Pass Rate (配置验证通过率): 100%
- Default Parameter Fill Rate (默认参数补全率): ≥95%
- Average Retry Count (平均重试次数): <1.0
- Max Retry Count (最大重试次数): ≤3
```

**对照实验**:
```
对照组: v4.0 简单重试（如果有历史版本）
实验组: v5.0 FeedbackRouter + PromptPool
期望提升: 配置成功率 75% → 92% (+23%)
```

**实现文件**: `exp_3_config_reliability.py`

---

## 🔧 v5.0 系统修复记录

### 2025-12-06 修复: 多任务执行循环问题

**问题描述**:
实验1c中的extended_analysis任务（如"率定GR4J模型，流域01539000，完成后计算径流系数"）只执行了第一个子任务（calibration），后续子任务（evaluation、analysis）未执行，系统陷入无限循环。

**根本原因**:
1. **FeedbackRouter逻辑错误**: 对所有task_type都触发iterative_optimization，未区分extended_analysis
2. **状态机GENERATING_CONFIG**: 总是选择第一个子任务（`subtasks[0]`），未选择下一个pending subtask
3. **execution_results覆盖**: 每次执行覆盖而非追加，导致已完成任务信息丢失

**修复内容**:

1. **FeedbackRouter** (`hydroagent/core/feedback_router.py:353-406`)
   ```python
   # ⭐ 只有iterative_optimization任务才触发迭代优化
   task_type = context.get("intent_result", {}).get("intent_result", {}).get("task_type")

   if task_type != "iterative_optimization":
       logger.info(f"Task type is '{task_type}', not 'iterative_optimization'. "
                   f"Completing current subtask (NSE={nse:.4f}).")
       return {"action": "complete_success", ...}
   ```

2. **Orchestrator GENERATING_CONFIG** (`hydroagent/agents/orchestrator.py:662-682`)
   ```python
   # ⭐ 选择下一个pending subtask，而不是总是第一个
   execution_results = self.execution_context.get("execution_results", [])
   completed_ids = {r.get("task_id") for r in execution_results if r.get("success")}

   subtask = None
   for st in subtasks:
       if st.get("task_id") not in completed_ids:
           subtask = st
           break
   ```

3. **Orchestrator EXECUTING_TASK** (`hydroagent/agents/orchestrator.py:780-787`)
   ```python
   # ⭐ 追加execution_results，而不是覆盖
   existing_results = self.execution_context.get("execution_results", [])
   updated_results = existing_results + [runner_result]

   return {
       "context_updates": {
           "execution_results": updated_results,  # 追加
       },
       ...
   }
   ```

**影响范围**:
- ✅ extended_analysis任务现在可以正确执行所有子任务
- ✅ iterative_optimization任务仍然正常触发迭代
- ✅ 状态机不再陷入无限循环（避免达到100次转换上限）

**验证**:
- 测试脚本: `test/test_exp1c_fix.py`
- 验证查询: "率定GR4J模型，流域01539000，完成后计算径流系数"
- 预期行为: 系统识别3个子任务（calibration, evaluation, analysis）并顺序执行

---

## 🆕 Part 2: v5.0 核心创新

### Exp 4: 状态机智能编排 (待实现)

**目标**: 验证状态机架构的效率和可维护性

**测试集**: 50 个任务（覆盖正常和异常场景）
- 正常场景: 30 个（顺利执行）
- 配置错误: 10 个（触发配置重试）
- 执行错误: 10 个（触发执行重试）

**评估指标**:
```
状态机效率：
- Average State Transitions (平均状态转换次数): 记录
- State Transition Overhead (状态转换开销): <5%
- Execution Time Comparison (执行时间对比): v5.0 ≈ 基准±5%

错误恢复：
- Error Recovery Success Rate (错误恢复成功率): ≥85%
- Average Recovery Time (平均恢复时间): 记录
- Retry Efficiency (重试效率): v5.0 > 简单重试
```

**实现文件**: `exp_4_state_machine.py`

---

### Exp 5: 错误恢复机制 (待实现)

**目标**: 验证 FeedbackRouter 智能路由的有效性

**测试集**: 60 个错误场景（模拟或真实触发）
- timeout: 10 个
- configuration_error: 15 个
- numerical_error: 15 个
- memory_error: 10 个
- data_not_found: 5 个
- dependency_error: 5 个

**评估指标**:
```
错误分类：
- Error Type Recognition Accuracy (错误类型识别准确率): ≥95%
- Routing Decision Accuracy (路由决策准确率): ≥90%

恢复效果：
- Recovery Success Rate (恢复成功率): v5.0 (85%) vs 简单重试 (60%)
- Average Recovery Attempts (平均恢复尝试次数): v5.0 < 简单重试
- Overall Task Success Rate (总体成功率): v5.0 (92%) vs 基准 (75%)
```

**实现文件**: `exp_5_error_recovery.py`

---

### Exp 6: 语义案例检索 (待实现)

**目标**: 验证 PromptPool FAISS 检索的效果

**实验设计**: 三阶段测试
```
阶段1 - 冷启动（0个历史案例）:
  执行50个任务，记录配置成功率

阶段2 - 学习期（积累50个成功案例）:
  保存所有成功案例到PromptPool

阶段3 - 检索期（使用语义检索）:
  执行50个新任务，使用语义检索辅助
```

**评估指标**:
```
检索质量：
- Average Retrieval Similarity (平均检索相似度): 记录分布
- Case Usage Rate (案例使用率): ≥80%
- Retrieval Time (检索时间): <0.5s

性能提升：
- Cold Start Success Rate (冷启动成功率): 基准
- Warm Start Success Rate (学习后成功率): 提升≥20%
- High Similarity Task Success Rate (高相似任务成功率): ≥95%
```

**实现文件**: `exp_6_prompt_pool.py`

---

## 🔧 Part 3: 系统鲁棒性

### Exp 7: 大规模任务处理 (待实现)

**目标**: 验证系统在大规模任务下的稳定性

**测试集**: 3 个规模梯度
```
小规模: 10个流域（GR4J模型，标准率定）
中规模: 50个流域（GR4J模型，标准率定）
大规模: 100个流域（GR4J模型，标准率定）
```

**评估指标**:
```
成功率：
- Overall Success Rate (总体成功率): ≥90% @ 100流域
- Failure Distribution (失败分布): 分析失败原因

性能：
- Average Task Time (平均单任务时间): 与规模关系
- Total Execution Time (总执行时间): 线性增长
- Memory Usage (内存占用): 峰值<8GB
- CPU Usage (CPU占用): 平均<80%

稳定性：
- System Crash Rate (系统崩溃率): 0%
- Checkpoint Save Success Rate (Checkpoint保存成功率): 100%
```

**实现文件**: `exp_7_large_scale.py`

---

### Exp 8: 断点续传可靠性 (待实现)

**目标**: 验证 Checkpoint 机制的可靠性

**测试集**: 20 个多任务场景（每个5-10个子任务）

**测试方法**: 中断-恢复循环
```
每个任务执行3次中断-恢复:
1. 中断点20% → 恢复
2. 中断点50% → 恢复
3. 中断点80% → 恢复
```

**评估指标**:
```
保存与恢复：
- Checkpoint Save Success Rate (保存成功率): 100%
- Resume Accuracy Rate (恢复准确率): 100%
- Skip Completed Tasks Accuracy (跳过已完成任务准确率): 100%

数据一致性：
- Data Consistency Check (数据一致性检查): 100%通过
- Result Integrity (结果完整性): 无数据丢失
- State Recovery Correctness (状态恢复正确性): 100%

性能影响：
- Checkpoint Overhead (Checkpoint开销): <2%
- Resume Time (恢复时间): <5s
- Post-Resume Success Rate (恢复后成功率): ≥95%
```

**实现文件**: `exp_8_checkpoint_resume.py`

---

## 📈 实验执行计划

### Phase 1: 基础能力验证 ✅ (2025-12-04 ~ 2025-12-06)
```
✅ Exp 1a: 标准问题模板测试（15个模板）
✅ Exp 1b: 算法×模型全覆盖（36个任务）
✅ Exp 1c: 多任务查询测试（20个查询）
✅ Exp 2: 自然语言鲁棒性（60个噪音查询）
✅ Exp 3: 配置生成可靠性（60个配置任务）
✅ 系统Bug修复: 多任务执行循环问题
```

### Phase 2: 核心创新验证 (Week 3-4)
```
□ Exp 4: 状态机智能编排（50个任务）
□ Exp 5: 错误恢复机制（60个错误场景）
□ Exp 6: 语义案例检索（三阶段，共150个任务）
```

### Phase 3: 鲁棒性评估 (Week 5-6)
```
□ Exp 7: 大规模任务处理（10/50/100流域）
□ Exp 8: 断点续传可靠性（20个多任务×3次中断）
```

### Phase 4: 数据分析与撰写 (Week 7-8)
```
□ 汇总所有实验数据
□ 统计分析与可视化
□ 撰写论文实验章节
□ 准备补充材料
```

---

## 🎓 论文贡献映射

| 实验 | 验证内容 | 论文贡献点 | 状态 |
|------|---------|-----------|------|
| Exp 1 | 端到端成功率≥85% | 系统完整性与可用性 | ✅ 已实现 |
| Exp 2 | 噪音容忍率≥85% | 自然语言鲁棒性 | ✅ 已实现 |
| Exp 3 | 配置成功率92% (+23%) | PromptPool效果初步验证 | ✅ 已实现 |
| Exp 4 | 状态机效率与可维护性 | **创新点1**: 状态机架构设计 | 待实现 |
| Exp 5 | 错误恢复率85% (+42%) | **创新点2**: 智能错误恢复机制 | 待实现 |
| Exp 6 | 检索后成功率92% (+23%) | **创新点3**: 语义检索的案例复用 | 待实现 |
| Exp 7 | 100流域成功率≥90% | 系统可扩展性与稳定性 | 待实现 |
| Exp 8 | Checkpoint可靠性100% | 系统工程实践（断点续传）| 待实现 |

---

## 📝 实验实现规范

### 1. 文件结构

```
experiment/
├── base_experiment.py          # 基础实验类（统一框架）
├── exp_1a_standard_calibration.py  # ✅ 实验1a
├── exp_1b_algorithm_model_coverage.py  # ✅ 实验1b
├── exp_1c_multi_task.py        # ✅ 实验1c
├── exp_2_nlp_robustness.py     # ✅ 实验2
├── exp_3_config_reliability.py # ✅ 实验3
├── exp_4_state_machine.py      # 待实现
├── exp_5_error_recovery.py     # 待实现
├── exp_6_prompt_pool.py        # 待实现
├── exp_7_large_scale.py        # 待实现
├── exp_8_checkpoint_resume.py  # 待实现
└── experiments.md              # 本文档
```

### 2. 运行方法

```bash
# 使用Mock模式快速验证
python experiment/exp_1a_standard_calibration.py --backend api --mock

# 使用真实hydromodel执行
python experiment/exp_1a_standard_calibration.py --backend api --no-mock

# 使用Ollama本地模型
python experiment/exp_1a_standard_calibration.py --backend ollama --mock
```

### 3. 结果目录结构

```
experiment_results/
└── exp_1a_standard_calibration/
    └── YYYYMMDD_HHMMSS/
        ├── session_*/            # HydroAgent执行记录
        ├── results.json          # 详细结果
        ├── results.csv           # 表格数据
        ├── metrics.json          # 评估指标
        ├── report.md             # 实验报告
        └── figures/              # 可视化图表
            ├── success_rate.png
            └── time_distribution.png
```

---

## 🔧 有效流域列表

**10个CAMELS US有效流域** (已验证数据可用):
```
01539000  # Pennsylvania
02070000  # North Carolina
02177000  # South Carolina
03346000  # Kentucky
03500000  # Tennessee
11532500  # California
12025000  # Washington
14301000  # Oregon
14306500  # Oregon
14325000  # Oregon
```

**使用说明**:
- 所有实验应从此列表中选择流域
- 实验2和3已更新为使用这些有效流域
- 替换脚本: `scripts/replace_basins.py`

---

## ✅ 质量检查清单

### 实验前
- [x] 测试集准备完毕（Exp 1-3）
- [x] 评估指标明确定义
- [x] 有效流域验证
- [x] 代码审查通过
- [x] Mock数据可用

### 实验中
- [ ] 日志记录完整
- [ ] 中间结果保存
- [ ] 异常情况记录
- [ ] 资源监控运行

### 实验后
- [ ] 结果保存完整
- [ ] 数据分析完成
- [ ] 图表生成清晰
- [ ] 报告撰写完整
- [ ] 可重复性验证

---

## 📞 注意事项

### 1. 数据真实性
- 使用真实CAMELS数据集（10个有效流域）
- 不过度调参
- 报告所有失败案例
- 记录随机种子（已设置seed=42）

### 2. 统计有效性
- 足够的样本量（已满足：15-60个测试用例）
- 报告置信区间
- 进行显著性检验（如有对照）
- 多次重复关键实验

### 3. 可重复性
```python
# 固定随机种子
import random
random.seed(42)

# 记录环境信息
import sys
print(f"Python: {sys.version}")
print(f"HydroAgent: v5.0")
```

### 4. 资源限制
- Mock模式用于快速验证
- 真实模式用于最终数据
- 注意API调用配额（阿里云Qwen）
- 监控系统资源

---

**HydroAgent v5.0 实验方案**
精炼、聚焦、面向论文发表 🎓

---

*最后更新: 2025-12-06*
*设计者: Claude*
*状态: Phase 1 完成 ✅, Phase 2-3 待实现*
