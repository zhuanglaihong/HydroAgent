# HydroClaw 研究调研与规划文档

> 状态：主动开发中 | 日期：2026-03-06

---

## 一、研究背景与动机

### 问题陈述

水文模型率定（Calibration）是水文建模的核心环节，传统流程需要用户：
1. 手动配置模型参数（数据路径、率定期、算法超参数等）
2. 调用优化算法（SCE-UA、DE、PSO 等）迭代求解
3. 解读评估指标（NSE、KGE、RMSE 等）
4. 根据结果调整策略、重新运行

这一过程门槛高、重复性强，对非编程背景的水文学者尤其不友好。

### 研究动机

近年来 LLM（大语言模型）的涌现能力（推理、工具调用、代码生成）使得"自然语言驱动科学工作流"成为可能。HydroClaw 的目标是：**让水文学者用一句话完成完整的模型率定-评估-分析流程。**

灵感来源：OpenClaw（2025年11月发布）展示了轻量自主 Agent 的工程范式——本地运行、外接 LLM、工具驱动执行、跨会话记忆，以及最重要的 **Skill 包系统**（能力自包含、可扩展安装）。HydroClaw 将这一范式引入水文领域，并在此基础上提出适合科学计算场景的改进。

---

## 二、相关研究调研

### 2.1 水文领域 LLM 应用（直接相关）

| 工作 | 来源 | 核心方法 | 与 HydroClaw 的关系 |
|------|------|----------|---------------------|
| **Large Language Models as Calibration Agents** (Zhu et al., 2026) | *Geophysical Research Letters* | 用 5 个 LLM 直接参与 VIC 模型参数搜索，与 SCE-UA/NSGA-III 对比 | 最直接参照：验证 LLM 可参与率定，但仅聚焦"LLM 替代优化算法"，未构建完整 Agent 工作流 |
| **IWMS-LLM** (2025) | *Journal of Hydroinformatics* | 基于 LLM 的智能水资源管理系统 | 对话界面类似，但偏决策支持而非模型执行 |
| **WaterGPT** (2024) | *Water (MDPI)* | 领域微调 LLM | 知识层面，未涉及工作流自动化 |
| **HydroLLM** (2025) | *Environmental Data Science* | 水文领域 LLM 知识评测基准 | 评估基准，非执行框架 |
| **水分布网络 LLM 优化** (2025) | *ScienceDirect* | LLM 驱动水力模型率定与泵站优化 | 工程应用类似，领域不同 |

**核心空白**：现有工作要么停留在"LLM 作为知识问答"，要么是"LLM 替代单一优化步骤"，**没有将 LLM 嵌入完整水文建模工作流、且具备动态扩展能力的 Agentic 系统**。

### 2.2 地球科学 Agent（领域拓展参考）

| 工作 | 方法要点 | 对 HydroClaw 的启示 |
|------|----------|---------------------|
| **GeoLLM-Squad** (Lee et al., 2025) | 遥感工作流多 Agent（AutoGen） | 多 Agent 范式，但协调复杂 |
| **GeoEvolve** (2025, arXiv) | 代码进化器 + RAG + Agentic Controller | 迭代优化 + 知识检索的组合 |
| **PANGAEA GPT** (2025) | 地球科学 MAS + 大规模数据库 | 数据集成方式 |

### 2.3 通用 Agentic 架构趋势

**Agentic Loop + Tool Use** 是当前主流：接收目标 → 选择工具 → 执行 → 观察 → 循环至完成。

**OpenClaw Skill 系统的关键启示**：
- Skill = 自包含能力包（skill.md 说明书 + 执行代码）
- 通过 ClawHub 市场安装/分发，类似 npm
- 与 HydroClaw 的差异：OpenClaw skill 是预安装的静态能力；HydroClaw 引入**运行时动态生成 skill** 的元能力（`create_tool`），更进一步

---

## 三、HydroClaw 定位与创新点

### 3.1 与现有工作的差异化

```
现有工作层次：
  LLM 知识问答           ←─── WaterGPT, HydroLLM
  LLM 替代单一优化步骤   ←─── Zhu et al. 2026
  LLM 辅助决策           ←─── IWMS-LLM

HydroClaw 的层次：
  自然语言
    → 意图理解
    → Skill 选择（工具 + 领域知识 + 执行策略）
    → 工具执行（可动态扩展）
    → 结果分析 + 报告输出
  ↑ 完整端到端 Agentic 工作流 + 动态扩展能力（现有工作均未覆盖）
```

### 3.2 核心创新点（论文角度）

1. **端到端 Agentic 水文工作流**
   首个将 LLM Agentic Loop 应用于完整水文模型率定管道的系统（意图→配置→执行→分析），单一对话驱动全流程。

2. **Skill 包系统：工具 + 说明书自包含**
   每个 Skill = tool.py（执行能力）+ skill.md（使用说明 + 领域策略），两者绑定。Agent 按需注入相关 Skill 的说明书作为上下文，调用其工具执行任务。新 Skill 可独立添加，不修改核心代码。

3. **动态 Skill 生成（元能力）**
   当现有工具不满足需求时，`create_tool` 元工具让 LLM 在运行时生成新工具代码并即时注册，突破静态工具集的限制。这是对 OpenClaw "预安装 Skill" 范式的超越——从"安装已有能力"升级为"按需生成能力"。

4. **LLM 智能参数范围调整**
   LLM 作为虚拟水文专家，在 SCE-UA 优化器外层构建决策循环：检测参数边界效应 → 扩展搜索空间 → 触发重新优化。与 Zhu et al. 2026（LLM 替代优化器）形成互补：LLM 调控搜索空间，专业算法执行搜索。

5. **三层知识体系**
   - **Skill 说明书**（how to do）：工作流步骤、工具调用顺序
   - **领域知识库**（what to know）：参数物理含义、率定经验、诊断规则
   - **跨会话记忆**（what happened）：流域档案、历史最优参数

---

## 四、完整系统架构

### 4.1 设计哲学

| 维度 | 旧 HydroAgent | HydroClaw |
|------|--------------|-----------|
| 执行主体 | 5个 Agent + Orchestrator 状态机 | 1个 Agentic Loop |
| 扩展方式 | 新增 Agent（改核心代码） | 新增 Skill 包（不改核心） |
| 工具僵化 | 硬编码 hydromodel 接口 | Skill 包 + 动态生成兜底 |
| 知识组织 | 散落在各 Agent prompt 里 | 分层：Skill说明书 / 知识库 / 记忆 |
| 交互方式 | 脚本调用 | 对话驱动 |

### 4.2 目录结构（目标状态）

```
hydroclaw/
├── agent.py               # Agentic Loop 核心
├── llm.py                 # LLM 客户端
├── memory.py              # 记忆系统
├── config.py              # 配置管理
│
├── skills/                # Skill 包（工具 + 说明书 自包含）
│   ├── calibration/
│   │   ├── skill.md       # 说明书：标准率定流程、参数说明、注意事项
│   │   └── calibrate.py   # 工具代码
│   ├── llm_calibration/
│   │   ├── skill.md       # 说明书：智能率定流程、何时使用、边界扩展策略
│   │   └── llm_calibrate.py
│   ├── evaluation/
│   │   ├── skill.md
│   │   └── evaluate.py
│   ├── visualization/
│   │   ├── skill.md
│   │   └── visualize.py
│   ├── analysis/          # 代码生成 + 执行
│   │   ├── skill.md
│   │   ├── generate_code.py
│   │   └── run_code.py
│   └── [用户自定义 Skill]  # 通过 create_skill 生成，可随意扩展
│       ├── skill.md
│       └── my_tool.py
│
├── tools/                 # 核心基础工具（不属于特定 Skill）
│   ├── __init__.py        # 统一自动发现（扫描 skills/ + tools/）
│   ├── validate.py        # 数据验证
│   ├── simulate.py        # 模型模拟
│   └── create_skill.py    # 元工具：运行时生成新 Skill 包 ★
│
└── knowledge/             # 领域知识库（独立于 Skill，供 LLM 推理用）
    ├── model_parameters.md  # 参数物理含义、典型范围
    └── calibration_guide.md # 率定策略、诊断经验
```

### 4.3 运行时信息流

```
用户输入："帮我用 GR4J 率定流域 12025000，如果 NSE 不好再用智能率定"
         ↓
  [Agent._build_context()]
  ├── System Prompt（角色定义）
  ├── 匹配 Skill 说明书（calibration/skill.md + llm_calibration/skill.md）
  ├── 注入领域知识（model_parameters.md → GR4J 参数含义）
  └── 加载记忆（12025000 流域历史率定记录，如有）
         ↓
  [LLM 推理]
  决定调用：validate_basin → calibrate_model(gr4j) → evaluate_model
         ↓
  [工具执行]（tools/__init__.py 统一调度）
         ↓
  [LLM 观察结果] NSE=0.58 < 0.65
  决定调用：llm_calibrate(gr4j, nse_target=0.75)
         ↓
  [工具执行 + LLM 迭代范围调整]
         ↓
  [LLM 生成最终报告] 写入 session memory
```

### 4.4 工具扩展路径

**场景：用户想用 spotpy 做 MCMC 率定**

```
方案A（推荐）：用户描述需求 → create_skill 生成
  "帮我创建一个用 spotpy 做 MCMC 率定的工具"
  → LLM 生成 skills/spotpy_mcmc/skill.md + spotpy_mcmc.py
  → 自动注册，立即可用

方案B：用户手动添加 Skill 包
  在 skills/ 下新建目录，放入 tool.py + skill.md
  → 下次启动自动发现
```

**工具发现机制**（`tools/__init__.py`）：
- 扫描 `hydroclaw/tools/*.py`（核心工具）
- 扫描 `hydroclaw/skills/*/` 下所有 `*.py`（Skill 工具）
- 所有公开函数自动注册为 LLM 可调用工具

---

## 五、论文写作规划

### 5.1 论文定位

**目标期刊**（候选，按契合度排序）：
- *Environmental Modelling & Software*（水文+软件工程，最契合）
- *Journal of Hydroinformatics*（已有多篇 LLM+水文论文）
- *Geophysical Research Letters*（短文快发，同 Zhu et al. 2026）

**论文类型**：系统设计 + 实验验证

### 5.2 论文结构

```
1. Introduction
   - 水文模型率定的挑战与现状
   - LLM Agent 的机遇（工具调用、推理、代码生成）
   - 现有工作的不足（表格：知识问答/单步替代/无工作流）
   - 本文贡献（4点创新）

2. Related Work
   2.1 LLM in Hydrology（知识、优化、对话三个层次）
   2.2 Agentic AI Systems（单/多 Agent 架构权衡）
   2.3 Tool Use & Skill Systems（Function Calling, OpenClaw Skill 范式）

3. HydroClaw System Design
   3.1 整体架构与设计哲学
   3.2 Agentic Loop（ReAct 模式）
   3.3 Skill 包系统（工具 + 说明书自包含，动态扩展）
   3.4 三层知识体系（Skill说明书 / 领域知识库 / 跨会话记忆）
   3.5 LLM 智能参数范围调整机制

4. Experiments
   4.1 实验设置（流域、模型、LLM后端）
   4.2 实验1：端到端标准率定（正确性验证）
   4.3 实验2：自然语言参数理解（"迭代500轮"→ rep=500）
   4.4 实验3：智能参数范围调整（vs 单轮 SCE-UA 的 NSE 对比）
   4.5 实验4：动态 Skill 生成（create_skill 生成 spotpy 工具并执行）
   4.6 实验5：跨会话记忆（历史知识对率定效率的影响）

5. Discussion
   5.1 能力边界：LLM 能做什么，不能做什么
   5.2 与 Zhu et al. 2026 的定位对比
   5.3 Skill 系统 vs 多 Agent 系统的权衡
   5.4 局限性与未来方向

6. Conclusion
```

### 5.3 核心论证逻辑

**论文核心论点**：
> "将 LLM 嵌入水文建模工作流的关键不在于让 LLM 替代优化算法，而在于构建一个以 Skill 包为扩展单元的 Agentic 框架——LLM 作为智能协调者，通过自包含的 Skill（工具能力 + 领域知识）驱动完整工作流，并在工具不足时动态生成新 Skill。"

与现有工作的关系：
- vs Zhu et al. 2026：LLM **调控搜索空间**（范围调整）而非替代搜索算法 → 互补
- vs WaterGPT/HydroLLM：不是训练专用模型，而是让通用 LLM 通过结构化知识注入获得领域能力 → 更轻量
- vs GeoLLM-Squad：单 Agentic Loop 而非多 Agent，Skill 包替代子 Agent → 更简洁可控

---

## 六、开发计划

### 已完成

- ✅ Agentic Loop 核心（`agent.py`，ReAct 模式）
- ✅ LLM 客户端（Function Calling + Prompt fallback）
- ✅ 记忆系统（会话日志 + 跨会话 MEMORY.md）
- ✅ 基础工具（calibrate/evaluate/simulate/validate/visualize）
- ✅ LLM 智能率定（`llm_calibrate.py`，参数范围迭代调整）
- ✅ 动态工具生成（`create_tool.py`）
- ✅ 领域知识库骨架（`knowledge/`）
- ✅ Phase 1 修复（gr5j/gr6j 参数范围，skill 描述一致性）

### 待实现

**Phase 3：Skill 包系统重构**（架构核心，论文 Section 3.3）
- [ ] 将现有 `skills/*.md` 归入 `knowledge/`（它们本质是知识，非 Skill）
- [ ] 重构目录：每个 Skill = `skills/<name>/skill.md` + `skills/<name>/<tool>.py`
- [ ] 更新 `tools/__init__.py`：同时扫描 `tools/` 和 `skills/*/` 发现工具
- [ ] 更新 `agent.py`：按查询匹配并注入对应 Skill 的 `skill.md`
- [ ] 将 `create_tool` 升级为 `create_skill`（同时生成 .py + skill.md）

**Phase 4：记忆升级**（论文 Section 3.4）
- [ ] `memory.py` 增加 `save_basin_profile()` / `load_basin_profile()`
- [ ] 率定结束后自动写入流域档案（model × basin → NSE, best_params）
- [ ] agent 初始化时按流域 ID 加载历史先验

**Phase 5：实验脚本**（论文 Section 4）
- [ ] `experiment/exp1_standard_calibration.py`
- [ ] `experiment/exp2_nl_understanding.py`
- [ ] `experiment/exp3_llm_calibration_vs_sce.py`
- [ ] `experiment/exp4_create_skill.py`
- [ ] `experiment/exp5_memory.py`

**Phase 6：论文写作**（与 Phase 5 并行）
- [ ] Related Work 初稿
- [ ] System Design 章节（随开发同步）
- [ ] 实验结果整理

---

## 七、参考文献（已识别）

1. Zhu et al. (2026). *Large Language Models as Calibration Agents in Hydrological Modeling: Feasibility and Limitations*. GRL. https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2025GL120043

2. IWMS-LLM (2025). *An intelligent water resources management system based on large language models*. Journal of Hydroinformatics. https://iwaponline.com/jh/article/27/11/1685/110111/

3. WaterGPT (2024). *Training a Large Language Model to Become a Hydrology Expert*. Water. https://www.mdpi.com/2073-4441/16/21/3075

4. HydroLLM (2025). *Toward HydroLLM: a benchmark dataset for hydrology-specific knowledge assessment*. Environmental Data Science. https://www.cambridge.org/core/journals/environmental-data-science/article/toward-hydrollm/585BFB32C8F14A7C8E8D93F1E0E08020

5. Lee et al. (2025). GeoLLM-Squad. *Accelerating earth science discovery via multi-agent LLM systems*. Frontiers in AI. https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1674927/full

6. GeoEvolve (2025). *Automating Geospatial Model Discovery via Multi-Agent Large Language Models*. arXiv. https://arxiv.org/html/2509.21593v1

7. AI-driven multi-agent water resource planning (2025). Journal of Hydroinformatics. https://iwaponline.com/jh/article/27/7/1217/108550/

8. Water distribution network optimization with LLM (2025). ScienceDirect. https://www.sciencedirect.com/science/article/pii/S004313542501440X

---

*本文档随项目进展持续更新*
