# HydroAgent 认知架构设计：三类记忆重构计划

> 更新：2026-04-10 | 目标：让 Agent 像人类水文专家一样使用知识

---

## 零、认知架构总图

```
                    ┌─────────────────────────────────┐
                    │         system.md               │
                    │   与生俱来的原则与常识底座        │
                    │  （方向感、工作原则、底层规则）   │
                    └──────────────┬──────────────────┘
                                   │ 始终在
                                   ▼
用户提问 ──────────────────► Agent 推理（ReAct Loop）
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
         程序性记忆           语义记忆              情节记忆
     skill 索引（system）    knowledge/          memory/ + basin_profiles
    完整内容 read_file       按需 read_file       开始前 search_memory
    （我会做什么）          （遇事查手册）         任务后写入
                                   │
                                   ▼
                              执行 → 结果
                                   │
                              写入情节记忆
```

HydroAgent 是一个有**原则**（system.md）、有**技能**（skills）、有**参考**（knowledge）、有**记忆**（memory）的水文专家 Agent，
不是把所有东西都背下来的检索系统，也不是写死流程的脚本。

---

## 一、核心思想

人类专家工作时有三类记忆，各自的触发方式不同：

| 记忆类型 | 人类行为 | HydroAgent 对应 | 触发方式 |
|---------|---------|--------------|---------|
| **程序性**（procedural）| 知道怎么做，不需要查 | `skill.md` | 任务开始自动注入 system prompt |
| **语义性**（semantic）| 遇到问题翻参考书 | `knowledge/` | Agent 主动 `read_file` |
| **情节性**（episodic）| 记得之前的经历 | `memory/` + basin_profiles | 开始时摘要加载，任务后主动写入 |

**当前问题**：系统把三类全部在任务开始时塞进 system prompt，Agent 没有"主动检索"的意识，也没有"主动记录"的习惯。

**目标**：Skill 始终激活（程序性）；Knowledge 遇到问题才查（语义性）；Memory 开始时检索历史、结束时写入经验（情节性）。

---

## 二、改动方案（P0 → P2，按优先级）

---

### P0：修复语义记忆访问方式（1天，低风险）

#### 改动 1：删除 `_load_domain_knowledge()` 自动注入

**文件**：`hydroagent/agent.py`

```python
# 删除这一段（约 544-549 行）：
domain_knowledge = self._load_domain_knowledge(query)
if domain_knowledge:
    parts.append(
        "## Domain Knowledge\n"
        + semantic_truncate(domain_knowledge, self._MAX_MEMORY_CHARS, "domain knowledge")
    )
```

`_load_domain_knowledge()` 函数本身保留（不影响其他调用），只去掉在 `_build_system_prompt()` 中的调用。

**效果**：每次调用节省约 500-2000 tokens；消除截断导致的残缺知识注入。

---

#### 改动 2：在 skill.md 中加入知识库查阅触发

让 Agent 在遇到特定问题时知道主动查哪个文件。

**文件**：`hydroagent/skills/calibration/skill.md` 异常处理部分新增：

```markdown
## 知识库查阅

遇到以下情况时，主动调用 read_file 查阅对应文件：

| 情况 | 查阅文件 |
|------|---------|
| 报错原因不明、不知道如何恢复 | `hydroagent/knowledge/failure_modes.md` |
| 工具连续报同一个错 | `hydroagent/knowledge/tool_error_kb.md` |
| 不确定数据集支持哪些流域或变量 | `hydroagent/knowledge/datasets.md` |
| 不确定模型参数的物理含义 | `hydroagent/knowledge/model_parameters.md` |
```

**文件**：`hydroagent/skills/llm_calibration/skill.md` 异常处理部分同样新增上述表格。

---

### P1：补全情节记忆的写入（半天，低风险）

**目前问题**：`save_basin_profile` 由工具层自动调用，Agent 不知道自己在"记录经验"，也不会主动总结本次有价值的发现。

#### 改动：在 skill.md Stop Conditions 中加入主动记录步骤

**文件**：`hydroagent/skills/calibration/skill.md` 和 `llm_calibration/skill.md` 的结尾加：

```markdown
## 完成后必做

任务成功结束后（拿到 train + test 双期指标），执行：

1. 确认 `save_basin_profile` 已被调用（calibrate_model 成功时自动触发）
2. 如果本次率定发现了值得记录的信息（参数触边界原因、特殊的流域行为），
   主动在回复中明确说明，方便用户将其纳入长期记忆
3. 不要仅仅输出数字，要用一句话解释"这次结果说明了什么"
```

**效果**：Agent 从"机械执行任务"变为"有意识地总结经验"。

---

### P2：补全情节记忆的检索（半天，低风险）

**目前问题**：Agent 不会主动查询"我之前有没有处理过这个流域"，有时会重复已经做过的工作。

#### 改动：在 skill.md 任务开始前加入历史检索步骤

**文件**：`hydroagent/skills/calibration/skill.md` 的"任务开始"部分新增：

```markdown
### 任务开始前：检索历史记录

在调用 validate_basin 之前，先调用 search_memory：

```
search_memory(query="basin_id <流域ID>")
```

如果有历史记录：
- 告知用户之前的率定结果（NSE/KGE、使用的模型）
- 询问是否复用历史结果或重新率定
- 若重新率定，参考历史参数范围作为初始猜测

如果没有历史记录：
- 继续正常流程（validate_basin -> calibrate）
```

**效果**：避免重复工作；历史信息成为当前任务的先验。

---

## 三、预期实现效果

### 改动前（当前行为）

```
用户："率定XAJ，流域03439000"
Agent：把 skill.md + knowledge/ + memory/ 全部注入（~8000 tokens）
      → 执行 validate -> calibrate -> evaluate
      → 输出数字，不解释
      → 结束
```

### 改动后（目标行为）

```
用户："率定XAJ，流域03439000"
Agent：system prompt 只含 skill.md（~3000 tokens）
      → 主动调用 search_memory("03439000")，告知用户历史记录
      → validate_basin -> get_basin_attributes（如果是 LLM 率定）
      → calibrate/llm_calibrate
      → 遇到报错：主动 read_file("knowledge/failure_modes.md") 诊断
      → 完成后：解释"本次结果说明 03439000 具有较强的基流调蓄，CG 参数接近上界"
      → 提醒用户这条经验值得记录
```

---

## 四、Token 效益估算

| 改动 | 节省 token（每次调用）|
|------|---------------------|
| 删除 knowledge/ 自动注入 | ~500-2000 tokens |
| 不命中时不注入 skill（已有）| 已实现 |
| memory 摘要按需而非全量（现状）| 已有 4000 char 上限 |
| **合计节省** | **约 10-25%** |

知识库文件在 Agent 真正需要时仍然可以被完整读取（read_file 无截断），
实际上获得的知识质量反而更高。

---

## 五、实现顺序

```
Day 1（P0）：
  [x] agent.py 删除 _load_domain_knowledge() 调用
  [x] calibration/skill.md 加知识库查阅触发表
  [x] llm_calibration/skill.md 加知识库查阅触发表

Day 1（P1）：
  [x] calibration/skill.md 加"完成后必做"section
  [x] llm_calibration/skill.md 加"完成后必做"section

Day 2（P2）：
  [x] calibration/skill.md 加"任务开始前检索历史"
  [x] llm_calibration/skill.md 加"任务开始前检索历史"

验证：
  python -m hydroagent "率定XAJ，流域12025000"
  → 检查是否调用了 search_memory
  → 检查是否没有 knowledge/ 自动注入
  → 检查完成后是否有解释性总结
```

---

## 六、设计原则（写入论文）

> HydroAgent 的知识组织遵循认知科学的三分法：
>
> - **程序性知识**（skill.md）在任务开始时激活，指导 Agent 的行为决策，不需要显式检索。
> - **语义知识**（knowledge/）作为按需参考库，Agent 在遇到不确定情况时主动查阅，
>   避免将低使用率的参考资料长期占用上下文窗口。
> - **情节知识**（memory/）在会话开始时加载摘要、在任务结束后主动写入，
>   实现跨会话的经验积累与复用。
>
> 这种设计在 token 效率和知识可用性之间取得平衡，
> 使 Agent 的知识使用模式接近人类水文专家的认知工作流。
