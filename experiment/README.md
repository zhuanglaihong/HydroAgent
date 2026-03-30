# HydroClaw 实验脚本说明

> 论文 Section 4: Experiments | 日期：2026-03-11

---

## 一、实验总览

从最初 7 个实验精简为 4 个核心实验（合并逻辑见下文）。

| 脚本 | 实验 | 核心论证点 | 运行模式 | 对比文献 |
|------|------|-----------|---------|---------|
| `exp1_standard_calibration.py` | 标准率定基线 | 系统可靠性：Agent 自主规划完整工作流 | Agent 驱动 | — |
| `exp2_llm_calibration.py` | 自主 LLM 率定工作流 vs 标准 vs Zhu et al. | 创新点：Agent 自主多轮决策，NSE 与 A 等价，零人工干预 | A+C Agent 驱动，B 脚本复现 | Zhu 2026, NHRI 2025 |
| `exp3_capability_breadth.py` | Agent 能力广度（NL 鲁棒性 + 动态 Skill + 自驱动规划） | 创新点：端到端通用性、运行时扩展、无 Orchestrator 批量自治 | 完整 Agent 对话 | AgentHPO 2025, NHRI 2025 |
| `exp4_knowledge_ablation.py` | 三层知识体系消融 + 对抗先验鲁棒性 | 创新点：结构化知识注入的量化贡献；先验合理性判断 | 完整 Agent 对话 | NHRI 2025 |

---

## 二、相关文献与定位

| 文献 | 方法 | HydroClaw 的差异化 |
|------|------|-------------------|
| **Zhu et al. 2026** (GRL) | LLM 直接提议参数值（5 个 LLM），**单一流域**，VIC 分布式模型；核心发现：DeepSeek-R1 NSE == SCE-UA（0.895），但收敛迭代数少 32%（865 vs 1269） | HydroClaw 测试 **3 个气候区流域**，LLM 调控搜索**空间**（范围+算法参数），不替代优化算法；嵌入完整 Agentic 工作流；两者共同结论：LLM 参与不提升 NSE 上限，价值在于自动化 |
| **NHRI 2025** (水科学进展) | 6 个 LLM 交互式优化 HBV/VIC，45 次迭代达 95% 最优，需人工参与 | **完全自主**，无需人工交互；自然语言驱动；Skill 动态扩展 |
| **AgentHPO** (ICLR 2025) | LLM Agent 做 ML 超参数优化，含历史记忆 | **水文领域**专用知识注入；Skill 系统可运行时扩展工具集本身 |

---

## 三、实验设计思路

### 整体论证逻辑

```
Exp1 -> 证明系统"能做"         Agent 自主执行完整率定工作流，tool sequence 可验证
Exp2 -> 证明系统"做得一样好，但不需要人"
                               C ≈ A（NSE），但 C 自主多轮决策，无人工干预；
                               与 Zhu 2026 共同验证：LLM 参与不提升 NSE 上限，
                               价值在于"自动化等价"而非"性能超越"
Exp3 -> 证明系统"足够通用"     自然语言鲁棒性 + 运行时扩展能力 + 自驱动批量规划
Exp4 -> 证明"结构的必要性"     K0-K3 知识消融，每层贡献量化；对抗先验压力测试
```

### 精简合并说明

| 原脚本 | 合并到 | 合并原因 |
|--------|--------|---------|
| exp3_scenario_robustness.py (12场景×2条件) | exp3_capability_breadth.py Section A | 与 exp6 K0/K3 设计重叠，属 exp4 子集 |
| exp4_create_skill.py | exp3_capability_breadth.py Section B | 与 exp7 同属 Agent 能力展示 |
| exp5_memory.py (三阶段) | exp4_knowledge_ablation.py 附加 | 对抗先验 = K3 压力测试，K0/K3 已覆盖基本记忆验证 |
| exp6_knowledge_ablation.py | exp4_knowledge_ablation.py | 直接合并，主体不变 |
| exp7_self_driven_planning.py | exp3_capability_breadth.py Section C | 同属 Agent 能力广度演示 |

---

## 四、各实验详细设计

### Exp1：标准率定基线（Agent 驱动）

**运行模式**：`HydroClaw.run(自然语言查询)` 全程 LLM 驱动，不直接调工具函数。

**设计**：5 流域 × 2 模型（GR4J + XAJ）× SCE-UA

| 流域 | 气候区 | GR4J 适配性 | 选取原因 |
|------|--------|------------|---------|
| 12025000 Fish River, ME | 湿润寒冷 | 好 (NSE~0.78) | 易率定参照 |
| 03439000 French Broad, NC | 湿润温暖 | 中等 | 标准湿润流域 |
| 06043500 Gallatin, MT | 半干旱山区 | 差 (NSE~-0.1) | 高山积雪，参数易碰边界 |
| 08101000 Cowhouse Creek, TX | 半干旱闪洪 | 中等/差 | 强非线性流域 |
| 11532500 Smith, CA | 地中海气候 | 好 (NSE~0.70) | 强季节性 |

**关键评估指标**：

- NSE/KGE 基线值（供 Exp2/Exp4 参照）
- `tool_sequence`：Agent 是否自主调用 `validate_basin -> calibrate_model -> evaluate_model`
- 成功率：10 个任务的完成率

**论文用途**：Section 4.2，建立基线；同时证明 Agent 端到端工作流规划的可靠性。

---

### Exp2：自主 LLM 率定工作流（混合模式）

**模型**：GR4J（4参数，经典基准，LLM 先验知识充分）

**三路对比设计**：

```
Method A: 标准 SCE-UA（Agent 驱动，1次运行）
          validate_basin -> calibrate_model(SCE-UA, rep=750) -> evaluate_model
          [固定默认参数范围，Agent 自主执行，人工指定算法参数]

Method B: Zhu et al. 2026 风格（脚本复现，非 Agent 驱动）
          LLM 直接提议参数值 -> 极窄范围(±3%) -> scipy/SLSQP 评估 -> 迭代 <=15 次
          [保留脚本：精确复现需控制 prompt 格式和窄范围技巧，NL 查询无法表达]

Method C: HydroClaw LLM 参数范围调整（Agent 驱动，本文方法）
          Agent 自主触发 llm_calibrate：
            轮1(seed=1234) -> LLM 分析边界+算法参数 -> 轮2(seed=1371) -> ... -> <=5轮
          [Agent 自主检测 NSE < target，决定继续迭代，无需人工介入]
```

**为什么 Method B 用 scipy 而非 SCE-UA**：

Zhu 方法的核心是"LLM 作为优化器"——LLM 提议一个具体参数点，在该点 ±3% 极窄范围内做单点评估。若换成 SCE-UA，它会在全参数空间自主搜索，LLM 的提议被完全忽略，Method B 就变成 Method A。

**核心论点（已修正）**：

实验证据（与 Zhu 2026 结论一致）：
- `C_NSE ≈ A_NSE`：LLM 参与不能提升 NSE 上限（由模型-流域结构决定）
- `C_rn > 1`：Agent 自主检测 NSE < 目标并继续迭代，无需用户手动干预
- `NSE 轨迹有变化`：各轮使用不同随机种子（1234, 1371, 1508...），探索不同局部最优
- `eval_ratio > 1`：C 用更多总计算换取零人工干预（合理 trade-off）

核心价值不是"算法更好"，而是"用户只需说目标（NSE≥0.80），Agent 自主决定跑几轮、调什么"。

**流域选取逻辑（3 个流域，3 种气候区）**：

| 流域 | 气候区 | GR4J 适配 | 在实验中的作用 |
|------|--------|----------|--------------|
| 12025000 Fish River, ME | 湿润寒冷 | 好 (NSE~0.79) | 基准：NSE 好时 Agent 能否在目标以下正确继续迭代 |
| 11532500 Smith River, CA | 地中海 | 中等 (NSE~0.70) | 中间情况：目标触发多轮，LLM 是否能调整 |
| 06043500 Gallatin, MT | 半干旱山地 | 差 (NSE~-0.12) | 失配：Agent 坚持迭代 5 轮仍无法显著改善——说明结构限制，非系统 bug |

**关键评估指标**：

| 指标 | 含义 | 预期 |
|------|------|------|
| `C_rn` | C 方法自主运行轮数 | >1（Agent 正确判断未达目标） |
| `dC-A` | C vs A 的 NSE 差 | ≈0（自动化等价，非性能超越）|
| `NSE 轨迹` | 各轮 NSE 是否变化 | 有波动（不同种子，不再全平）|
| `eval_ratio` | C/A 总评估次数比 | >1（多轮代价，透明记录）|
| tool_sequence | Agent 决策路径 | C 包含 llm_calibrate，A 不包含 |

**论文用途**：Section 4.3，展示 Agent 自主多轮率定决策能力；与 Zhu 2026 共同支撑"LLM 参与的价值在于自动化而非 NSE 超越"这一核心论点。

---

### Exp3：Agent 能力广度

三个 Section，依次验证三个不同能力维度：

**Section A：自然语言鲁棒性（6 个代表性场景）**

| ID | 类别 | 查询示例 | 核心评估 |
|----|------|---------|---------|
| A01 | 标准率定 | "请帮我率定GR4J模型，流域12025000" | 工具序列正确率 |
| A02 | 含算法参数 | "用SCE-UA迭代500次率定XAJ" | rep=500 正确传参 |
| A03 | 隐含意图 | "参数可能碰到边界，需要智能调整" | 正确选 llm_calibrate |
| A04 | 批量规划 | "对比GR4J和XAJ在3个流域的性能" | 调用任务规划工具 |
| A05 | 代码分析 | "画FDC曲线并计算径流系数" | 调用 generate_code/run_code |
| A06 | 残缺信息 | "率定一下模型" | 主动澄清缺失参数 |

**Section B：动态 Skill 生成（3 个场景）**

每个场景请求默认 Skill 集不存在的能力，验证 `create_skill` 元工具。评估：
- `create_skill` 被正确调用
- 生成的 `tool.py` 语法合法（AST 验证）
- 新工具注册进注册表，后续可调用

**Section C：自驱动任务规划（3 阶段）**

| 阶段 | 场景 | 验证目标 |
|------|------|---------|
| C1 基础批量 | "比较GR4J和XAJ在2个流域，列计划执行" | create_task_list/update_task 被调用，task_state.json 正确 |
| C2 自适应 | "批量率定3流域，NSE低于0.3考虑追加智能率定" | add_task 触发率（涌现行为，非强制）|
| C3 断点恢复 | 预写部分完成的 task_state，再次运行 | 已完成任务跳过，从断点继续 |

**论文用途**：Section 4.4，综合展示系统通用性和可扩展性。

---

### Exp4：三层知识消融 + 对抗先验

**主消融：K0-K3 四条件 × 3 测试场景**

```
K0: 无知识 -> 仅角色描述
K1: +Skill 说明书 -> 工作流步骤、工具选择逻辑
K2: +领域知识库 -> 参数物理含义、率定诊断经验
K3: +跨会话记忆 -> 流域档案先验（完整系统）
```

实现方式：monkey-patch 临时替换 agent 内部方法（`_load_domain_knowledge`、`skill_registry.match`、`memory.format_basin_profiles_for_context`），同一 LLM 后端保证公平对比。

**测试场景**：

| ID | 查询 | 重点验证 |
|----|------|---------|
| T1 | 标准率定 GR4J | 基础工作流完成率 |
| T2 | "参数可能碰边界，调整范围" | 知识驱动的工具选择（K1 vs K2 差异）|
| T3 | "画FDC曲线" | 代码生成能力（非率定任务）|

**评估指标**：工具序列匹配率、首轮工具正确率、LLM token 消耗（知识的"成本"）

**附加：对抗先验鲁棒性（K3 压力测试）**

注入极端错误先验（如 NSE=0.97 但参数全在边界），验证 Agent 能否：
- 识别先验异常（响应包含"可疑/异常"等词）
- 不盲目相信错误历史而产生错误决策

**论文用途**：Section 4.5 消融，提供"结构必要性"的定量证据；对抗测试回应"记忆可能反噬"的质疑。

---

## 五、运行顺序

```bash
# 建议顺序（exp1 无 LLM，优先验证环境）
python experiment/exp1_standard_calibration.py   # ~3h，需要 LLM（Agent 驱动）
python experiment/exp2_llm_calibration.py        # ~4h，需要 LLM（Zhu 迭代 + Agent）
python experiment/exp3_capability_breadth.py     # ~2h，全 Agent 对话
python experiment/exp4_knowledge_ablation.py     # ~2h，全 Agent 对话（含消融条件切换）
```

**注意事项**：

- 所有实验现在均调用 LLM API（包括 Exp1 的 Agent 模式），建议先用单流域测试
- Exp3 Section B 会在 `hydroclaw/skills/` 下生成新目录，实验后如需清理请手动删除
- Exp4 monkey-patch 不修改任何源文件，可安全重复运行
- Exp3 Section C2 的 `add_task` 自适应行为是涌现行为，非强制，统计触发率即可
- **Exp2 随机种子**：A 方法固定 seed=1234（可复现基线）；C 方法每轮自动变化（1234, 1371, 1508...），
  保证各轮 SCE-UA 从不同起点搜索，NSE 轨迹应出现变化而非全平
- Exp2 现用 GR4J（已从 GR5J 切回），A/B 的 GR4J 结果可复用，只需重跑 C 方法
- 所有实验结果均输出为 JSON，方便后续出图

---

## 六、结果目录结构

```
results/paper/
├── exp1/exp1_results.json      # 5x2 率定基线表 + tool_sequence 记录
├── exp2/exp2_results.json      # A/B/C NSE + C_rn/eval_ratio 自动化效率 + proposed_history（Zhu 提议多样性）
├── exp3/exp3_results.json      # 三 Section：NL 匹配率 / Skill 生成验证 / 规划执行
└── exp4/exp4_results.json      # 4条件 x 3场景消融矩阵 + 对抗先验鲁棒性
```

---

## 七、论文章节对应

```
4.1 实验设置（流域/模型/LLM 后端/评估指标）
4.2 Exp1: 端到端标准率定（基线验证 + Agent 工作流规划可靠性）
4.3 Exp2: 自主 LLM 率定工作流（C≈A，NSE 等价；C 自主多轮，零人工干预）
         对比：Zhu 2026（1流域，NSE 持平，迭代少 32%）-> 共同结论：价值在自动化
4.4 Exp3: Agent 能力广度
    - Section A: 自然语言鲁棒性（6 场景工具匹配率）
    - Section B: 动态 Skill 生成（运行时元能力）
    - Section C: 自驱动任务规划（批量执行/自适应/断点恢复）
4.5 Exp4: 三层知识体系消融 + 对抗先验鲁棒性
    - K0-K3 逐层累加，工具匹配率 delta
    - 对抗先验：错误历史下的稳健性
```
