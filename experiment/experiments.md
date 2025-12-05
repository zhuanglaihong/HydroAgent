# HydroAgent v5.0 实验方案

**版本**: v5.0 State Machine Architecture
**设计时间**: 2025-12-04
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

## 🎯 实验体系（8 个核心实验）

```
实验体系
├── Part 1: 系统基础能力（3个实验）
│   ├── Exp 1. 端到端功能验证
│   ├── Exp 2. 自然语言理解鲁棒性
│   └── Exp 3. 配置生成可靠性
│
├── Part 2: v5.0 核心创新（3个实验）
│   ├── Exp 4. 状态机智能编排
│   ├── Exp 5. 错误恢复机制
│   └── Exp 6. 语义案例检索
│
└── Part 3: 系统鲁棒性（2个实验）
    ├── Exp 7. 大规模任务处理
    └── Exp 8. 断点续传可靠性
```

---

## 📊 Part 1: 系统基础能力

### Exp 1: 端到端功能验证

**目标**: 验证完整流程的准确性和成功率

**实验组成** (3个子实验):
- **Exp 1a**: 标准率定测试 (40个: GR4J×20, XAJ×20)
- **Exp 1b**: 算法×模型全覆盖测试 (36个: 3算法×4模型×3流域)
- **Exp 1c**: 多任务查询测试 (20个: 代码生成、参数调整)
- **Exp 1d**: 批量处理测试 (10个: 多流域)

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

**测试用例示例**:
```python
[
    "率定GR4J模型，流域01013500",
    "用XAJ模型率定流域01055000，使用SCE-UA算法，迭代500轮",
    "率定完成后评估流域01013500的性能",
    "率定流域01013500、01055000、01057000",
    "率定完成后，计算径流系数并画FDC曲线",
    # ... 共100条
]
```

**实现文件**: `exp_1_end_to_end.py`

---

### Exp 2: 自然语言理解鲁棒性

**目标**: 测试系统对非标准输入的容错能力

**测试集**: 60 个包含"噪音"的查询
- 拼写错误: 15 个（"率定"→"率顶"）
- 标点异常: 15 个（缺失、错误）
- 参数顺序混乱: 10 个
- 口语化表达: 10 个
- 中英混合: 10 个

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
| 标点缺失 | 率定GR4J，流域01013500 | 率定GR4J流域01013500 | ≥90% |
| 顺序混乱 | 率定GR4J，流域01013500 | 流域01013500率定GR4J | ≥85% |
| 口语化 | 率定流域01013500 | 帮我跑一下01013500这个流域 | ≥75% |

**实现文件**: `exp_2_nlp_robustness.py`

---

### Exp 3: 配置生成可靠性

**目标**: 验证配置生成的成功率和正确性

**测试集**: 60 个配置生成任务（不执行hydromodel）
- 标准配置: 30 个（完整参数）
- 缺省配置: 20 个（部分参数，需自动补全）
- 边界配置: 10 个（极端参数值）

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

## 🆕 Part 2: v5.0 核心创新

### Exp 4: 状态机智能编排

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

**状态转换分析**:
```
正常流程: IDLE → RECOGNIZING_INTENT → PLANNING_TASKS →
         GENERATING_CONFIG → EXECUTING_CALIBRATION →
         ANALYZING_RESULTS → COMPLETED

配置错误流程: ... → GENERATING_CONFIG → CONFIG_RETRY →
              GENERATING_CONFIG → ...

执行错误流程: ... → EXECUTING_CALIBRATION → EXECUTION_RETRY →
              EXECUTING_CALIBRATION → ...
```

**实现文件**: `exp_4_state_machine.py`

---

### Exp 5: 错误恢复机制

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

**路由策略验证**:
| 错误类型 | 路由策略 | 预期成功率 |
|---------|---------|-----------|
| timeout | retry_with_reduce_iterations | ≥85% |
| configuration_error | regenerate_config | ≥90% |
| numerical_error | retry_with_default_config | ≥80% |
| memory_error | reduce_complexity | ≥75% |
| data_not_found | fail_with_error | N/A |
| dependency_error | fail_with_error | N/A |

**实现文件**: `exp_5_error_recovery.py`

---

### Exp 6: 语义案例检索

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

**测试任务分布**:
- 高相似度任务 (similarity > 0.8): 20 个
- 中等相似度 (0.5 ≤ similarity ≤ 0.8): 20 个
- 低相似度 (similarity < 0.5): 10 个

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

**对照实验**:
```
对照组: 无PromptPool（静态提示）
实验组: 有PromptPool（语义检索）
期望提升: 75% → 92% (+23%)
```

**实现文件**: `exp_6_prompt_pool.py`

---

## 🔧 Part 3: 系统鲁棒性

### Exp 7: 大规模任务处理

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

**资源监控**:
```python
监控项:
- 内存占用（每分钟采样）
- CPU使用率（每分钟采样）
- 磁盘I/O（总量）
- 网络流量（API调用次数）
```

**实现文件**: `exp_7_large_scale.py`

---

### Exp 8: 断点续传可靠性

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

**中断类型**:
```
1. 正常中断（Ctrl+C）: 15个测试
2. 异常中断（kill进程）: 5个测试
```

**实现文件**: `exp_8_checkpoint_resume.py`

---

## 📝 实验实现规范

### 1. 代码模板

```python
"""
实验X: 实验名称
目标: ...
"""
import sys
from pathlib import Path
from experiment.base_experiment import BaseExperiment
import json
import pandas as pd
import matplotlib.pyplot as plt

def main():
    exp = BaseExperiment(
        exp_name="exp_X_name",
        exp_description="描述"
    )

    # 设置日志
    log_file = exp.setup_logging()

    # 创建工作目录
    workspace = exp.create_workspace()

    # 执行实验
    results = run_experiment()

    # 保存结果
    save_results(results, workspace)

    # 生成报告
    generate_report(results, workspace)

    print(f"✅ 实验完成！结果保存到: {workspace}")

def run_experiment():
    """实验核心逻辑"""
    results = {
        "test_cases": [],
        "metrics": {},
        "statistics": {}
    }
    # TODO: 实现实验逻辑
    return results

def save_results(results, workspace):
    """保存结果为JSON和CSV"""
    # 保存JSON
    with open(workspace / "results.json", "w") as f:
        json.dump(results, f, indent=2)

    # 保存CSV（如果有表格数据）
    if "test_cases" in results:
        df = pd.DataFrame(results["test_cases"])
        df.to_csv(workspace / "test_cases.csv", index=False)

def generate_report(results, workspace):
    """生成Markdown报告"""
    report = f"""# 实验X报告

## 实验概述
...

## 实验结果
...

## 统计分析
...

## 结论
...
"""
    with open(workspace / "report.md", "w", encoding="utf-8") as f:
        f.write(report)

if __name__ == "__main__":
    main()
```

### 2. 结果目录结构

```
experiment_results/
└── exp_X_name/
    └── YYYYMMDD_HHMMSS/
        ├── results.json          # 原始数据
        ├── metrics.json          # 评估指标
        ├── test_cases.csv        # 测试用例结果
        ├── report.md             # 实验报告
        ├── figures/              # 图表
        │   ├── accuracy.png
        │   ├── time_distribution.png
        │   └── comparison.png
        └── logs/
            └── experiment.log
```

### 3. 指标格式

```json
{
  "experiment_name": "exp_X_name",
  "timestamp": "2025-12-04 12:00:00",
  "test_set_size": 100,
  "metrics": {
    "accuracy": 0.95,
    "success_rate": 0.92,
    "average_time": 120.5
  },
  "statistics": {
    "mean": 0.92,
    "std": 0.05,
    "min": 0.85,
    "max": 0.98,
    "ci_95": [0.90, 0.94]
  }
}
```

### 4. 报告模板

```markdown
# 实验X: 实验名称

## 1. 实验概述
- 目标: ...
- 测试集: ...
- 评估指标: ...

## 2. 实验设计
- 测试集构成
- 对照组设置
- 参数配置

## 3. 实验结果

### 3.1 原始数据
| Test Case | Result | Time(s) | Notes |
|-----------|--------|---------|-------|
| ...       | ...    | ...     | ...   |

### 3.2 统计分析
- 均值: 0.92
- 标准差: 0.05
- 95%置信区间: [0.90, 0.94]

### 3.3 可视化
![准确率分布](figures/accuracy.png)

## 4. 分析与讨论
- 结果解读
- 与预期对比
- 异常案例分析

## 5. 结论
- 主要发现
- 系统优势
- 局限性与改进方向
```

---

## 📈 实验执行计划

### Phase 1: 基础能力验证 (Week 1-2)
```
□ Exp 1: 端到端功能验证（100个任务）
□ Exp 2: 自然语言鲁棒性（60个噪音查询）
□ Exp 3: 配置生成可靠性（60个配置任务）
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

| 实验 | 验证内容 | 论文贡献点 |
|------|---------|-----------|
| Exp 1 | 端到端成功率≥85% | 系统完整性与可用性 |
| Exp 2 | 噪音容忍率≥85% | 自然语言鲁棒性 |
| Exp 3 | 配置成功率92% (+23%) | PromptPool效果初步验证 |
| Exp 4 | 状态机效率与可维护性 | **创新点1**: 状态机架构设计 |
| Exp 5 | 错误恢复率85% (+42%) | **创新点2**: 智能错误恢复机制 |
| Exp 6 | 检索后成功率92% (+23%) | **创新点3**: 语义检索的案例复用 |
| Exp 7 | 100流域成功率≥90% | 系统可扩展性与稳定性 |
| Exp 8 | Checkpoint可靠性100% | 系统工程实践（断点续传）|

---

## 🔧 实验工具

### 必需工具
```bash
pip install pandas matplotlib seaborn scipy tqdm pytest
```

### 数据分析脚本
```python
# 使用 pandas 进行统计分析
import pandas as pd
import numpy as np
from scipy import stats

def analyze_results(results):
    df = pd.DataFrame(results)

    # 基本统计
    stats_summary = df.describe()

    # 置信区间
    mean = df['metric'].mean()
    sem = stats.sem(df['metric'])
    ci = stats.t.interval(0.95, len(df)-1, loc=mean, scale=sem)

    return {
        'mean': mean,
        'std': df['metric'].std(),
        'ci_95': ci
    }
```

### 可视化脚本
```python
import matplotlib.pyplot as plt
import seaborn as sns

def plot_comparison(baseline, v5_0, title):
    """对比图"""
    fig, ax = plt.subplots(figsize=(10, 6))

    x = ['Baseline', 'v5.0']
    y = [baseline, v5_0]

    bars = ax.bar(x, y, color=['gray', 'blue'])
    ax.set_ylabel('Success Rate')
    ax.set_title(title)

    # 显示数值
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1%}', ha='center', va='bottom')

    plt.savefig(f'{title}.png', dpi=300, bbox_inches='tight')
```

---

## ✅ 质量检查清单

### 实验前
- [ ] 测试集准备完毕
- [ ] 评估指标明确定义
- [ ] 对照组设置合理
- [ ] 代码审查通过
- [ ] Mock数据可用（如需要）

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
- 使用真实CAMELS数据集
- 不过度调参
- 报告所有失败案例
- 记录随机种子

### 2. 统计有效性
- 足够的样本量（建议≥30）
- 报告置信区间
- 进行显著性检验（如有对照）
- 多次重复关键实验

### 3. 可重复性
```python
# 固定随机种子
import random
import numpy as np
random.seed(42)
np.random.seed(42)

# 记录环境信息
import sys
print(f"Python: {sys.version}")
print(f"HydroAgent: {hydroagent.__version__}")
```

### 4. 资源限制
- Mock模式用于快速验证
- 真实模式用于最终数据
- 注意API调用配额
- 监控系统资源

---

## 🗂️ 旧实验处理

### 建议迁移方案
```bash
# 创建legacy目录
mkdir -p experiment/legacy

# 移动旧实验
mv experiment/exp_1a_standard.py experiment/legacy/
mv experiment/exp_1b_algorithm_model_coverage.py experiment/legacy/
mv experiment/exp_1c_error_handling.py experiment/legacy/
mv experiment/exp_2a_repeated_calibration.py experiment/legacy/
mv experiment/exp_2b_multi_basin.py experiment/legacy/
mv experiment/exp_2c_multi_algorithm.py experiment/legacy/
mv experiment/exp_3_iterative_optimization.py experiment/legacy/
mv experiment/exp_4_extended_analysis.py experiment/legacy/

# 保留作为参考，但不再维护
```

### 新旧映射关系
| 旧实验 | 新实验 | 说明 |
|--------|--------|------|
| exp_1a_standard | Exp 1a | 标准率定测试（40个基础率定任务） |
| exp_1b_algorithm_model_coverage | Exp 1b | **已重构为算法×模型全覆盖测试** |
| exp_1c_error_handling | Exp 5 | 错误处理由FeedbackRouter专项测试 |
| exp_2a_repeated_calibration | Exp 7 | 重复率定纳入大规模测试 |
| exp_2b_multi_basin | Exp 7 | 多流域纳入大规模测试 |
| exp_2c_multi_algorithm | Exp 1b | **现已由Exp 1b专项测试（算法×模型全覆盖）** |
| exp_3_iterative_optimization | Exp 4/5 | 迭代优化由状态机+错误恢复测试 |
| exp_4_extended_analysis | Exp 1 | 扩展分析纳入端到端多任务 |

---

**HydroAgent v5.0 实验方案 v2.0**
精炼、聚焦、面向论文发表 🎓

---

*最后更新: 2025-12-04*
*设计者: Claude*
*审核者: 待定*
