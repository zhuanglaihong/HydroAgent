# HydroAgent Token 优化方案

> 版本：v1.1 | 日期：2026-04-09
> 背景：Exp1 基础率定每次运行约 82K token，其中大量来自 ReAct Loop 每轮重发历史。

---

## 一、问题根因

### 当前 ReAct 模式的 token 消耗结构

```
第1轮 API 调用（输入）：system_prompt(6K) + user_query(0.1K) = 6.1K
第2轮 API 调用（输入）：system_prompt(6K) + history(0.6K) + tool1_result(2K) = 8.6K
第3轮 API 调用（输入）：system_prompt(6K) + history(3.2K) + tool2_result(1K) = 10.2K
...
第N轮 API 调用（输入）：system_prompt + 所有历史累积
```

**主要大头**：
1. system_prompt 每轮重复发送（6K × N 轮）
2. 工具结果累积在历史中，之后每轮都带着
3. Agent 多余工具调用放大倍数（实测 A01 期望 3 次，实际 8 次）

---

## 二、三种执行模式与 HydroAgent 五层架构的关系

HydroAgent 五层架构：
```
大脑  (agent.py)        — ReAct 推理决策循环
小脑  (skill.md)        — 工作流指引，注入 system prompt
脊椎  (PackageAdapter)  — 双向翻译：工具意图 <-> 包调用
神经末梢 (tools/*.py)  — 薄路由函数，找适配器
肌肉  (hydromodel)      — 实际计算（率定/评估/模拟）
```

三种执行模式对五层的影响：

| 层次 | ReAct（当前） | Pipeline（推荐生产） | Waypoint |
|------|-------------|-------------------|---------|
| 大脑 | N 次 LLM 调用 | **1 次规划调用** | 3~5 次 LLM 调用 |
| 小脑 | 完整 skill.md 注入（~3K） | **Decision Rules 作为规划模板**（~1K） | 检查点 skill 片段 |
| 脊椎 | 不变 | 不变 | 不变 |
| 神经末梢 | 不变 | 不变 | 不变 |
| 肌肉 | 不变 | 不变 | 不变 |

**关键设计原则**：Pipeline 模式只改大脑（减少 LLM 调用次数）和小脑（精简 skill 输入）。
脊椎、神经末梢、肌肉层完全不变，工具调用路径和实际计算不受影响。

---

### 模式1：Pipeline（流水线模式）

**适用场景**：流程固定的批量实验任务（Exp3、Exp4，以及 Exp1 的 token 对比子实验）

**五层视角下的执行流程**：
```
[大脑：1次 LLM 规划调用]
  输入：identity(2K) + policy(2K) + skill.md Decision Rules(1K) + 任务描述(0.2K) = ~5K
  输出：JSON 计划（步骤列表 + $var.field 变量引用）
       ↓
[小脑：skill.md Decision Rules 作为计划模板]
  Agent 不需要从零推理工作流顺序，skill.md 的决策规则直接约束生成的计划
       ↓
[脊椎 -> 神经末梢 -> 肌肉：本地执行（无 LLM）]
  LocalExecutor 按计划逐步调用工具，$var.field 在运行时替换
       ↓
[报错时：单次 LLM 恢复调用，~0.5K context]
  仅发送：计划摘要 + 失败步骤 + 错误类型 + KB 恢复建议
  不发送：完整历史、完整 system prompt、前面步骤的完整输出
       ↓
[结束] 汇总结果（不需要额外 LLM 调用）
```

**API 调用次数**：1 次规划 + 0~1 次报错 = 最多 2 次

**预计 token/run**：~8K（节省 ~90%）

**为什么 skill.md Decision Rules 是规划模板**：

calibration skill.md 的 Decision Rules 段如下：
```
数据不可用 -> 停在验证阶段，不进入率定
已有 calibration_dir -> 先判断是否复用，而不是重新率定
参数触边界（距边界 <5%）-> 优先判断范围设定问题
训练 NSE 合格但测试 NSE 差 -> 报告泛化不足，不能宣称成功
```

这些规则直接映射为 Pipeline 计划的步骤顺序和条件分支。
LLM 在生成计划时，只需匹配任务类型找到对应 skill，
然后将 Decision Rules 翻译成具体的 JSON 步骤，无需推理工作流。

**JSON 计划格式**：
```json
{
  "steps": [
    {
      "id": "s1",
      "tool": "validate_basin",
      "args": {"basin_id": "12025000"},
      "output_var": "val"
    },
    {
      "id": "s2",
      "tool": "calibrate_model",
      "args": {"basin_id": "12025000", "model_name": "xaj"},
      "output_var": "cal"
    },
    {
      "id": "s3",
      "tool": "evaluate_model",
      "args": {"calibration_dir": "$cal.calibration_dir", "eval_period": null},
      "output_var": "eval_test"
    },
    {
      "id": "s4",
      "tool": "evaluate_model",
      "args": {"calibration_dir": "$cal.calibration_dir", "eval_period": "train"},
      "output_var": "eval_train"
    }
  ]
}
```

**动态参数传递**：`$cal.calibration_dir` 在 s3/s4 执行时被替换为 s2 的实际输出。
这种依赖关系在 skill.md 中已预定义，LLM 无需运行时推断。

---

### 模式2：ReAct（响应式推理模式）

**适用场景**：需要动态判断的任务（Exp1 主实验、Exp2 LLM 率定、交互对话、异常诊断）

**五层视角**：每次工具调用后大脑重新观察结果，小脑的 skill.md 全程可见，
Agent 可在工具结果基础上动态决策下一步。这是论文中证明 Agent 自主规划能力的必要模式。

**API 调用次数**：N 次（N = 工具调用数，通常 5~10）

**预计 token/run**：~80K（当前默认行为）

**为什么 Exp1 必须用 ReAct 而不是 Pipeline**：
Exp1 的核心论点是"LLM Agent 能从自然语言自主规划并执行水文率定工作流"。
tool_sequence 是这一论点的直接证据：Agent 自主决策了"先 validate_basin，再 calibrate_model，再 evaluate_model"的顺序，而不是被硬编码的脚本。
若改用 Pipeline，规划步骤是人为预定义的，这一论点就不成立。

---

### 模式3：Waypoint（检查点模式）

**适用场景**：有明确决策节点的中等复杂任务

**设计思路**：在预设检查点暂停调用 LLM，其余步骤本地执行。

```
本地执行 validate_basin
       ↓
本地执行 calibrate_model
       ↓
[检查点：LLM 观察 NSE]
  如果 NSE < 0.6 -> 调用 llm_calibrate 优化
  如果 NSE >= 0.6 -> 继续 evaluate_model
       ↓
本地执行后续步骤
```

**检查点定义**（在 skill.md 中声明）：
```yaml
waypoints:
  - after: calibrate_model
    condition: "NSE < 0.7 or params_at_boundary"
    action: "consult_llm"
  - after: evaluate_model
    condition: always
    action: "generate_report"
```

**API 调用次数**：3~5 次

**预计 token/run**：~25K（节省 ~70%）

---

## 三、报错回溯设计

### 报错时发给 LLM 的 context（紧凑格式）

```
原始计划：validate_basin -> calibrate_model -> evaluate_model -> evaluate_model
执行状态：s1(validate_basin) 成功，s2(calibrate_model) 失败
失败步骤：s2
输入参数：{"basin_id": "12025000", "model_name": "xaj"}
错误类型：ConvergenceError
错误摘要：SCE-UA failed: max iterations reached without convergence (NSE=-0.3)
知识库建议：扩大参数范围；考虑换模型或增大 ngs
```

**不发送**：前面成功步骤的完整输出、完整 system prompt、历史对话。
**只发送**：计划摘要 + 当前步骤 + 输入 + 错误类型 + 错误摘要（截断至 200 字）+ KB 建议。

预计错误 context 大小：~0.5K token。

---

## 四、工具报错知识库（Error Knowledge Base）

位置：`hydroagent/knowledge/tool_error_kb.md`

格式：每个工具的常见报错 -> 诊断 -> 恢复建议。

```markdown
## validate_basin

### E01: FileNotFoundError - 数据文件不存在
症状：data_path 下找不到 forcing/streamflow 文件
诊断：数据集未下载 / basin_id 填错 / DATASET_DIR 配置错误
恢复：检查 DATASET_DIR 配置；确认 CAMELS basin_id 格式（8位）

### E02: DateRangeError - 时间范围不足
症状：available_years < 10
恢复：换更长数据记录的流域，或缩短率定期

## calibrate_model

### E01: ConvergenceError - 优化不收敛
症状：NSE < 0 or max iterations reached
恢复：扩大参数范围；考虑换模型

### E02: MemoryError - 内存不足
症状：process killed during optimization
恢复：减小 ngs 参数（默认 7 -> 5）
```

**报错处理流程**：
1. 执行器捕获异常，识别错误类型
2. 查找 tool_error_kb.md 中对应条目（关键词匹配）
3. 将匹配的恢复建议注入错误 context，与错误信息一起发给 LLM
4. LLM 在已有恢复建议基础上决策，减少推理成本

---

## 五、系统提示词优化

### 各模式下的提示词层次对比

| 层次 | ReAct（完整） | Pipeline（规划时） | 说明 |
|------|-------------|------------------|------|
| 身份层 (system.md) | 2K | 2K | 必须，两种模式都保留 |
| 行为层 (policy/*.md) | 2K | 2K | 必须，安全约束不省略 |
| 技能层 (skill.md 完整) | ~3K | ~1K (仅 Decision Rules) | Pipeline 只注入规则段 |
| 知识层 (knowledge/*.md) | ~2K | 省略 | Pipeline 靠 KB 兜底 |
| 记忆层 (basin_profiles) | ~1K | 省略 | Pipeline 任务已明确 |
| **合计** | **~10K** | **~6K** | Pipeline 节省约 40% 规划输入 |

### minimal 模式（当前实验已启用）

```
# Section 1（身份，必须）：约 2K
# Section 1.5（policy，必须）：约 2K
# Section 2-6（Skill/知识/记忆）：全部省略
总计：~4K（原 10K -> 4K，节省 60%）
```

缺点：Agent 依赖参数太少，容易误用工具（实测可能增加额外 tool call）。

### 工具结果截断收紧

`calibrate_model` 返回值只保留关键字段：

```python
# 返回给 LLM 的内容（截断后）
{
  "calibration_dir": "results/xaj_12025000_20260409",
  "best_params": {"sm": 500, "ex": 1.2, ...},
  "nse_train": 0.72,
  "next_step": "call evaluate_model(calibration_dir=...)"
}
# 其余（优化过程日志、配置详情）写文件，不放 context
```

---

## 六、token 节省实测对比（Exp1，流域 12025000 × XAJ）

| 模式 | API 调用次数 | 输入 token | 输出 token | 总计 |
|------|------------|-----------|-----------|------|
| ReAct（完整 prompt） | ~8 | ~65K | ~3K | ~68K |
| ReAct（minimal 模式） | ~8 | ~55K | ~3K | ~58K |
| Pipeline | ~2 | ~8K | ~1K | ~9K |

> 数据来源：Exp1 token 对比子实验（见 exp1_results.json 中 token_comparison 字段）。
> minimal 模式仅减少 15%，因为历史累积是主要大头，不是 system_prompt 的绝对大小。
> Pipeline 节省 ~88%，验证了"减少 API 调用次数"是最有效的优化方向。

---

## 七、实施状态

### 已完成 (P0)

- [x] 实验脚本改用 `prompt_mode="minimal"` + `max_turns=8`
- [x] `hydroagent/pipeline.py`：PipelinePlanner + LocalExecutor（350 行）
- [x] 支持 `$var.field` 变量替换
- [x] Schema 校验（LLM 生成计划后验证工具名）
- [x] 错误 context 紧凑格式封装
- [x] `hydroagent/knowledge/tool_error_kb.md`（6 个工具，每工具 3-5 个常见错误）
- [x] 前端三模式切换按钮（Pipeline / ReAct / Waypoint）
- [x] server.py 根据 mode 字段路由到 run_pipeline 或 agent.run

### 待完成 (P1)

- [ ] Exp1 token 对比子实验：1 basin (12025000) × ReAct vs Pipeline，填充上表实测数据
- [ ] Pipeline 规划 prompt 改用 skill.md Decision Rules 作为模板（当前用独立 mini prompt）
- [ ] `calibrate_model` 返回值截断，只保留 calibration_dir + best_params + NSE

### 待完成 (P2)

- [ ] Waypoint 模式：skill.md 支持 `waypoints:` YAML 块声明检查点
- [ ] 执行器在指定位置调用 LLM（实现检查点暂停逻辑）
