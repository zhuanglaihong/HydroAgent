# HydroClaw 实验脚本说明

> 论文 Section 4: Experiments | 日期：2026-03-08

---

## 一、实验总览

| 脚本 | 实验 | 核心论证点 | 运行方式 | 对比文献 |
|------|------|-----------|---------|---------|
| `exp1_standard_calibration.py` | 标准率定基线 | 系统正确性 | 直接调工具 | — |
| `exp2_llm_calibration.py` | LLM 范围调整 vs 标准 vs Zhu et al. | 创新点：参数范围迭代 | 直接调工具 + LLM | Zhu 2026, NHRI 2025 |
| `exp3_scenario_robustness.py` | 自然语言鲁棒性 × 知识注入条件 | 创新点：端到端工作流 | 完整对话 | NHRI 2025 |
| `exp4_create_skill.py` | 动态 Skill 生成 | 创新点：运行时元能力 | 完整对话 | AgentHPO 2025 |
| `exp5_memory.py` | 跨会话记忆 + 对抗先验 | 创新点：流域档案先验 | 直接调工具 + LLM | AgentHPO, NHRI 2025 |
| `exp6_knowledge_ablation.py` | 三层知识体系消融 | 创新点：结构化知识注入 | 完整对话 | NHRI 2025 零知识对照 |
| `exp7_self_driven_planning.py` | Agent 自驱动任务规划与自适应策略 | 创新点：无 Orchestrator 批量自治 | 完整对话 | 旧 HydroAgent, 硬编码脚本 |

---

## 二、相关文献与定位

| 文献 | 方法 | HydroClaw 的差异化 |
|------|------|-------------------|
| **Zhu et al. 2026** (GRL) | LLM 直接提议参数值替代优化器，5个LLM对比 | LLM 调控搜索**空间**（范围），不替代优化算法；嵌入完整 Agentic 工作流 |
| **NHRI 2025** (水科学进展) | 6个LLM交互式优化 HBV/VIC，45次迭代达95%最优 | **完全自主**，无需人工交互；自然语言驱动；Skill 动态扩展 |
| **AgentHPO** (ICLR 2025) | LLM Agent 做 ML 超参数优化，含历史记忆 | **水文领域**专用知识注入；Skill 系统可运行时扩展工具集本身 |

---

## 三、实验设计思路

### 整体逻辑

```
Exp1 → 证明系统"能做"         基线正确性，排除 LLM 随机性
Exp2 → 证明系统"做得更好"     LLM 范围调整 vs Zhu et al. 直接提议法
Exp3 → 证明系统"足够通用"     12种查询 × 有无知识注入，验证自然语言泛化
Exp4 → 证明系统"可以扩展"     运行时生成新 Skill，工具集动态增长
Exp5 → 证明系统"越用越好"     跨会话档案先验 + 对抗先验鲁棒性
Exp6 → 证明"结构的必要性"     三层知识消融，每层贡献量化
```

---

### Exp1：标准率定基线

**设计**：5流域 × 2模型（GR4J + XAJ）× SCE-UA，直接调用工具函数。

**5个流域选取原则**（覆盖4个气候区）：

| 流域 | 气候区 | 选取原因 |
|------|------|---------|
| 12025000 Fish River, ME | 湿润寒冷 | 易率定，率定质量参照 |
| 03439000 French Broad, NC | 湿润温暖 | 标准湿润流域 |
| 06043500 Gallatin, MT | 半干旱山区 | 高山积雪，参数易碰边界 |
| 08101000 Cowhouse Creek, TX | 半干旱闪洪 | 半干旱极端流域 |
| 11532500 Smith, CA | 地中海气候 | 强季节性 |

**论文用途**：Section 4.2，建立基线；Exp2/Exp6 的 SCE-UA 参照值来自此处。

---

### Exp2：三路 LLM 率定对比

**设计（三路对比）**：

```
Method A: 标准 SCE-UA（固定默认参数范围）          ← Exp1 基线
Method B: Zhu et al. 2026 风格
          LLM 直接提议参数值 → 极窄范围 → scipy 评估 → 迭代 ≤15次
Method C: HydroClaw LLM 参数范围调整（本文方法）
          LLM 检测边界 → 扩展/收缩范围 → SCE-UA 重新优化 → 迭代 ≤5轮
```

选用 Gallatin、Guadalupe（高维/困难）+ Fish River（易率定对照）。

**Method B 实现说明**：
LLM 收到参数物理范围 + 历史结果 → 生成参数值 JSON → 转换为 ±3% span 的极窄范围
→ scipy L-BFGS-B 在该极窄范围内评估 → 将 NSE 结果反馈 LLM → 下一轮提议。
这是对 Zhu et al. "LLM 作为优化器"核心思路的精神性复现。

**论文用途**：Section 4.3，HydroClaw 与 Zhu et al. 直接对比。核心论点：
LLM 调控搜索**空间**（我们）比 LLM 直接生成参数值（他们）在高维困难流域更有效。

---

### Exp3：自然语言鲁棒性

**设计**：12个场景 × 2个知识条件（full_knowledge / no_knowledge）

| 类别 | 场景数 | 典型示例 |
|------|--------|---------|
| 标准率定（完整信息） | 2 | "率定GR4J，流域12025000" |
| 含算法参数 | 1 | "迭代500轮" → rep=500 |
| 多模型/多流域 | 2 | "对比GR4J和XAJ"（期望使用任务规划工具） |
| LLM 智能率定 | 1 | "用AI智能率定" |
| 代码生成（非率定） | 1 | "画FDC曲线" |
| 残缺信息 | 2 | 缺模型名/缺流域ID |
| 英文查询 | 1 | English input |
| 隐含意图 | 1 | "参数可能碰到边界" |
| 仅评估 | 1 | "评估已有率定结果" |
| 动态技能创建 | 1 | "创建敏感性分析工具" |

> **注**：S03/S04（多模型对比、多流域批量）的 expected_tools 已更新为包含任务规划工具
> （`create_task_list` / `get_pending_tasks` / `update_task`），体现自驱动规划能力。

知识条件对比设计对应 NHRI 2025 的"零知识 vs 专家知识"实验（其 NSE +0.14 作为外部参照）。

**论文用途**：Section 4.4，验证自然语言泛化能力（Zhu et al. 和 NHRI 均无此能力）。

---

### Exp4：动态 Skill 生成

**设计**：3个场景，每个请求默认 Skill 集不存在的能力。

验证清单（每场景 4 项）：

| 验证项 | 说明 |
|--------|------|
| `create_skill` 被调用 | LLM 识别出"能力不足"并调用元工具 |
| `skill.md` 文件生成 | 包含使用说明、触发关键词 |
| `tool.py` 语法合法 | AST 解析验证，可运行 |
| 新工具注册进注册表 | `reload_tools()` 后可调用 |

**论文用途**：Section 4.5，对比 OpenClaw（预安装静态范式）和 AgentHPO（工具集固定），
展示 HydroClaw 可在运行时扩展工具集**本身**。

---

### Exp5：跨会话记忆（三阶段）

**三阶段递进设计**：

| 阶段 | 操作 | 验证目标 |
|------|------|---------|
| A 冷启动 | 率定 → 自动写 basin_profiles/ | JSON 内容正确性：NSE/参数与率定结果一致 |
| B 有先验 | 再次率定同流域 | system prompt 中出现先验段落 |
| C 对抗先验 | 注入极端错误先验（NSE=0.97，参数全到边界）→ 询问 LLM | LLM 响应包含"异常/可疑"等预警词 |

阶段 C 是关键补充：NHRI 2025 发现"专家知识引导 NSE +0.14"，但未测试错误先验的鲁棒性。

**论文用途**：Section 4.6，展示"越用越好"特性；阶段 C 证明系统具备先验合理性判断能力。

---

### Exp6：三层知识体系消融

**四条件逐层累加设计**：

```
K0: 无知识 → 仅角色描述
K1: +Skill 说明书 → 工作流步骤、工具选择逻辑
K2: +领域知识库 → 参数物理含义、率定诊断经验
K3: +跨会话记忆 → 流域档案先验（完整系统）
```

× 三个测试场景（标准率定 / 参数边界感知 / 代码生成）

实现方式：通过临时替换 agent 内部方法（monkey-patch），同一 agent 实例跨条件复用，
保证 LLM 后端和 token 计数一致。

**评估指标**：工具序列匹配率、首轮工具正确率、平均 token 消耗（知识的"成本"）

**论文用途**：Section 4.7 消融，提供"结构必要性"的定量证据；
与 NHRI 2025 的零知识/有知识对比提供跨文献参照。

---

### Exp7：Agent 自驱动任务规划与自适应策略

**设计**：三阶段递进验证，对应第5个创新点（P2+P3）

| 阶段 | 查询 | 验证目标 |
|------|------|---------|
| A 基础批量执行 | "比较GR4J和XAJ在2个流域上的性能，列出计划依次执行" | create_task_list/get_pending_tasks/update_task 被调用；task_state.json 正确生成 |
| B 自适应调整 | "批量率定3个流域，NSE低于0.3时考虑追加智能率定" | add_task 被调用（自适应触发率）；LLM 推理而非硬编码规则驱动 |
| C 断点恢复 | 预写部分完成的 task_state.json，再次运行 | 已完成任务跳过，从断点继续执行 |

**与旧架构的对比**（论文核心对比点）：

```
旧 HydroAgent:   Orchestrator 状态机 → 5个子Agent → 收集结果   （N个组件，硬编码协调）
硬编码脚本:      for basin in basins: calibrate(basin)           （无规划、无恢复、无自适应）
HydroClaw Exp7: 同一 Agentic Loop + 3个规划工具                  （1个Loop，LLM即策略）
```

**关于 Phase B 自适应的说明**：

`add_task()` 由 LLM 根据领域推理自主决定是否调用（而非规则触发），属于涌现行为。
实验中统计触发率而非强制要求：即使未触发，Phase B 也能通过（只要批量执行完成）。
触发则在论文中作为亮点展示 LLM 的领域推理能力。

**论文用途**：Section 4.8，展示"无 Orchestrator 的自治批量执行"，与旧 HydroAgent 的架构复杂度形成对比。

---

## 四、运行顺序

```bash
# 建议顺序（Exp1 结果可辅助后续流域选择验证）
python scripts/exp1_standard_calibration.py   # ~2h，无 LLM
python scripts/exp2_llm_calibration.py        # ~4h，需要 LLM（Zhu + HydroClaw）
python scripts/exp5_memory.py                 # ~1h，少量 LLM
python scripts/exp3_scenario_robustness.py    # ~1h，全 LLM 对话
python scripts/exp7_self_driven_planning.py   # ~3h，全 LLM 对话（含批量率定）
python scripts/exp4_create_skill.py           # ~30min，全 LLM，修改 skills/ 目录
python scripts/exp6_knowledge_ablation.py     # ~1h，全 LLM
```

**注意事项**：
- Exp2/3/4/5/6/7 会调用 LLM API，产生 token 消耗（建议先跑 Exp1 确认环境）
- Exp4 会在 `hydroclaw/skills/` 下生成新目录，实验后如需清理请手动删除
- Exp6 使用 monkey-patch 控制知识条件，不修改任何源文件，可安全重复运行
- Exp7 Phase B 的自适应行为（add_task）是涌现行为，非强制，统计触发率即可
- 所有实验结果均输出为 JSON，方便后续出图

---

## 五、结果目录结构

```
results/paper/
├── exp1/exp1_results.json      # 5×2 率定基线表
├── exp2/exp2_results.json      # A/B/C 三路 NSE 对比
├── exp3/exp3_results.json      # 12场景 × 2条件匹配率
├── exp4/exp4_results.json      # Skill 生成验证（4项指标）
├── exp5/exp5_results.json      # 三阶段记忆验证
├── exp6/exp6_results.json      # 4条件 × 3场景消融矩阵
└── exp7/exp7_results.json      # 3阶段任务规划验证（执行/自适应/断点恢复）
```

---

## 六、论文章节对应

```
4.1 实验设置（流域/模型/LLM后端/评估指标）
4.2 Exp1: 端到端标准率定（基线验证）
4.3 Exp2: LLM 参数范围调整（vs Zhu et al. vs 标准SCE-UA）
4.4 Exp3: 自然语言鲁棒性（12场景，知识注入对比）
4.5 Exp4: 动态 Skill 生成（运行时元能力）
4.6 Exp5: 跨会话记忆（档案先验 + 对抗鲁棒性）
4.7 Exp6: 三层知识体系消融
4.8 Exp7: Agent 自驱动任务规划与自适应策略
        - Phase A: 基础批量执行（规划工具使用率、任务完成率）
        - Phase B: 自适应调整（add_task 触发率，LLM 推理驱动 vs 规则驱动对比）
        - Phase C: 断点恢复（已完成任务跳过验证）
```
