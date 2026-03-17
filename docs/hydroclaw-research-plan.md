# HydroClaw 研究调研与规划文档

> 状态：主动开发中 | 日期：2026-03-08

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
| **Large Language Models as Calibration Agents** (Zhu et al., 2026) | *Geophysical Research Letters* | 用 5 个 LLM（GPT-4o-mini, DeepSeek-R1/V3, Llama 等）直接提议 VIC 模型参数值，与 SCE-UA/NSGA-III 对比；**单一流域**（88个0.25°网格），VIC 分布式模型 | 最直接参照。核心发现：DeepSeek-R1 **NSE 与 SCE-UA 相同**（0.895 vs 0.895），但**收敛仅需 865 次迭代 vs SCE-UA 的 1269 次（快约 32%）**。方法局限：仅聚焦"LLM 作为参数提议器"替代单一优化步骤，未构建完整 Agent 工作流；只测试 1 个流域，泛化性未验证 |
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

4. **LLM 智能参数范围调整（兼收敛效率提升）**
   LLM 作为虚拟水文专家，在 SCE-UA 优化器外层构建决策循环：检测参数边界效应 → 扩展/收窄搜索空间 → 同步调整算法超参数（rep/ngs）→ 触发重新优化（新随机种子）。

   与 Zhu et al. 2026 的关系：
   - Zhu：LLM 直接提议参数**值**（替代优化器角色），单一流域，NSE 等同于 SCE-UA 但迭代数少 32%
   - HydroClaw：LLM 调控**搜索空间 + 算法配置**（辅助优化器），SCE-UA 执行实际搜索；在 **3 个气候区流域**上验证泛化性
   - **共同结论**：LLM 参与率定的核心价值在于**更快收敛**而非大幅提升 NSE 上限；两方法互补，分别覆盖"参数空间引导"和"参数值直接建议"两条路径

5. **Agent 自驱动任务规划（Self-Driven Task Planning）**
   区别于传统多 Agent 系统（外部 Orchestrator 分发任务给子 Agent）和脚本批量执行（硬编码执行顺序），HydroClaw 将任务规划能力内化为三个普通工具：`create_task_list` / `get_pending_tasks` / `update_task`。Agent 在同一个 Agentic Loop 中自主制定计划、逐步执行、根据中间结果调整策略，直至目标完成——整个过程无需人工干预，也无需外部协调者。任务状态持久化到磁盘，支持中断恢复。这与旧版 HydroAgent（Orchestrator + 5个子Agent状态机）形成鲜明对比：同等能力，架构从 N 个组件压缩为 1 个 Loop + 3 个工具。

6. **四层知识体系（Knowledge Layering）**

   专精水文 Agent 的能力来源于四个相互独立、各司其职的知识层，而非统一塞入系统提示词：

   | 层次 | 载体 | 回答的问题 | 维护者 |
   |------|------|-----------|--------|
   | **工具调用层**（how to call right） | `__agent_hint__` 函数属性 | 这个工具怎么调对？有哪些隐性约束？输出传给谁？ | 工具开发者 |
   | **工作流层**（how to do） | `skills/*/skill.md` | 做这类任务走哪条路？遇到异常怎么判断？ | 水文应用开发者 |
   | **领域知识层**（what to know） | `knowledge/*.md` | 为什么这样做？参数物理含义是什么？率定经验是什么？ | 水文领域专家 |
   | **记忆层**（what happened） | `basin_profiles/*.json` | 这个流域之前的结果是什么？有无历史最优参数？ | 运行时自动积累 |

   **核心设计原则**：每层独立演进，互不侵入。工具新增了新约束，只修改该工具的 `__agent_hint__`；水文经验更新，只改 `knowledge/`；新流域上线，记忆层自动积累。系统提示词不膨胀。

   **与通用 Agent 的本质区别**：通用 Agent（如 OpenClaw）的工具调用知识散落在系统提示词或 skill.md 里，随使用方增加而无序膨胀。HydroClaw 将其下沉到工具本身——工具自描述，而不是让 Agent 去猜。这是水文专精 Agent 可维护性的核心保证。

7. **工具自描述协议（Tool Self-Description Protocol）**

   这是本文对 Agentic 系统工程的独立贡献，也是四层知识体系中"工具调用层"的具体实现机制。

   **背景**：当 LLM 遇到 API 约束（如 `t_range` 必填、`calibrate_model` 不返回 NSE 等），现有系统有两种处理方式：
   - **硬编码进提示词**（通用 Agent 的做法）：随着工具增加，提示词持续膨胀，且与工具代码脱节——工具改了，提示词没改，Agent 还在用旧知识
   - **交给 LLM 自行推断**（让 LLM 猜）：反复失败、产生循环、消耗大量 token

   **HydroClaw 的解法**：在工具函数上定义 `__agent_hint__` 属性，工具的约束知识与工具代码绑定在一起，`fn_to_schema()` 自动将其注入 LLM 的 schema description。

   ```python
   # 工具函数定义（calibrate.py）
   def calibrate_model(...): ...

   # 工具自描述——约束知识与代码同步维护
   calibrate_model.__agent_hint__ = (
       "Returns calibration_dir and best_params — NO metrics (NSE/KGE). "
       "Must call evaluate_model(calibration_dir=...) separately to get metrics."
   )
   ```

   **三类自描述内容**（设计规范）：
   1. **必填约束**：type hint 表达不了的隐性规则（如 `t_range` 缺省会触发全量缓存重建）
   2. **输出→输入关系**：`calibrate_model` 的 `calibration_dir` 传给 `evaluate_model`；`validate_basin` 的 `data_path` 传给 `generate_code`
   3. **最常见错误的一句话预防**：如"After 3 failures, use ask_user instead of regenerating"

   **与 MCP 的关系**：这一机制在设计哲学上与 MCP（Model Context Protocol）完全一致——工具服务器声明自己的 capability manifest，客户端（LLM）据此正确调用，无需外部文档。区别在于：`__agent_hint__` 是同进程内的轻量实现（Python 函数属性），MCP 是跨进程/跨网络的标准协议。两者互补：HydroClaw 内部用 `__agent_hint__`，若未来接入外部水文服务，MCP server 是自然扩展路径。

   **可扩展性意义**：第三方开发者为 HydroClaw 贡献新水文工具包时，只需在工具函数上挂 `__agent_hint__`，`discover_tools()` 即可自动将正确调用方式带给 Agent，无需修改任何核心代码或提示词。这是实现"水文工具包生态"的基础。

8. **包生态自扩展（Package Ecosystem Self-Extension）**【思考点，待确认是否写入论文】

   当前水文 Agentic 系统均假设工具集静态固定，若用户需要使用未集成的水文包，只能手动修改源码。HydroClaw 提出了两个层次的自扩展机制：

   **层次 A：运行时动态生成 Skill**（已实现，创新点3）
   - `create_skill` 让 LLM 在运行时为任意 Python 包生成工具函数，无需重启
   - 已在实验中验证（Exp3-B）

   **层次 B：包级别自动适配**（Phase 8，工程探索）
   - `install_package`：在用户明确授权下安装新包，Agent 不自主决定
   - `register_package`：通过 PyPI API + importlib 探测 + LLM 分析，自动生成适配器骨架乃至可用实现
   - 授权约束设计：Agent 发现缺少包时，先通过 `ask_user` 请求用户允许安装，不允许自主决策。这一约束本身体现了"Human-in-the-loop"的安全设计原则——对于影响环境的不可逆操作，始终需要人类确认。

   **设计讨论点**（可作为 Discussion 章节内容）：
   - **Skill vs 多 Agent vs 包生态**：三种扩展路径的权衡——多 Agent 协调复杂（GeoLLM-Squad），Skill 包扩展快但依赖现有包，包生态自扩展打通了"新包→新能力"的全链路
   - **工具冲突管理作为系统可靠性问题**：随着工具数量增长，同名覆盖和同功能重复都会降低 Agent 行为可预测性；优先级元数据 + 语义去重是工程上保证可靠性的必要手段
   - **"安装即使用"的摩擦消除**：传统水文软件需要用户自行安装配置包；`register_package` 将这一步纳入 Agent 工作流，水文学者只需告诉 Agent 包名，其余自动完成

9. **观测驱动的 Agent 设计（Observation-Driven Agent Design）**
   这是 HydroClaw v3 的核心架构升级，也是与同类工作最本质的区别。

   **核心洞察**：LLM 的智能能否充分发挥，取决于它能"看到"什么。大多数 Agentic 系统将工具设计为黑盒——成功返回摘要，失败返回错误码——LLM 只能执行预设路径，无法基于真实世界状态做推理。

   HydroClaw v3 的设计原则：**工具是实验室仪器，返回值是仪器读数。**

   三个层次的改造：

   **(a) 观测工具**：赋予 Agent 主动观察世界的能力
   - `read_file(path)`：直接读取 CSV/JSON 结果文件，Agent 自行解析指标
   - `inspect_dir(path)`：查看目录结构，Agent 能知道"现场有什么"
   - 意义：Agent 不再依赖工具函数内部的数据提取逻辑，而是像研究员一样直接查看原始输出

   **(b) 诊断性返回值**：工具失败时给出可推理的上下文
   ```python
   # 旧设计（黑盒，LLM 无法推理）
   {"error": "Evaluation failed", "success": False}

   # 新设计（诊断性，LLM 可推理）
   {
     "error": "basins_metrics.csv not found",
     "success": False,
     "diagnosis": {
       "calibration_dir_exists": True,
       "files_found": ["calibration_results.json", "param_range.yaml"],
       "metrics_dir_exists": False,
     },
     "hint": "calibration_results.json exists — try re-running evaluate_model"
   }
   ```

   **(c) 目标导向的 Skill 设计**：Skill 描述目标与判断标准，而非固定步骤序列
   ```markdown
   # 旧设计（流程图，约束 LLM）
   步骤1: validate_basin
   步骤2: calibrate_model
   步骤3: evaluate_model（测试期）

   # 新设计（判断框架，解放 LLM）
   目标：得到训练期和测试期的 NSE/KGE
   判断：calibrate_model 只返回参数，不含指标
         -> 主动调用 evaluate_model 两次
   异常处理：calibration_dir 为空 -> 用 inspect_dir 诊断
   ```

   **与现有工作的本质区别**：
   - Zhu et al. 2026 / NHRI 2025：LLM 替代或辅助优化步骤，工具仍是黑盒
   - AgentHPO（ICLR 2025）：工具返回超参数评估结果，但无观测层设计
   - HydroClaw v3：工具暴露真实世界状态，LLM 基于观测推理，而非执行脚本

---

## 四、完整系统架构

### 4.1 设计哲学

| 维度 | 旧 HydroAgent | HydroClaw v2 | HydroClaw v3（当前） |
|------|--------------|-----------|---------------------|
| 执行主体 | 5个 Agent + Orchestrator 状态机 | 1个 Agentic Loop | 同左，+观测层 |
| 扩展方式 | 新增 Agent（改核心代码） | 新增 Skill 包（不改核心） | 同左 |
| 工具调用知识 | 无（硬编码在子 Agent 逻辑里）| 散落在 system.md 提示词里 | 工具自描述（`__agent_hint__`），与代码同步维护 |
| 工具返回 | 摘要（pass/fail） | 摘要（pass/fail） | 诊断性返回（带现场信息） |
| Agent 视野 | 只看工具摘要 | 只看工具摘要 | 可用 read_file/inspect_dir 主动观测 |
| 知识层次 | 无 | 两层（Skill说明书 + 领域知识库）| 四层（工具调用层 + Skill + 领域知识 + 记忆） |
| Skill 设计 | 无 | 步骤序列（流程图） | 目标+判断框架 |
| 智能体现 | 状态机路由 | LLM 选择工具 | LLM 基于观测推理，动态应对异常 |
| 交互方式 | 脚本调用 | 对话驱动 | 对话驱动 + 主动澄清（ask_user） |

**核心设计原则转变**：

```
v2 的隐含假设（自动化思维）：
  工具知道用户需要什么 -> 工具内部处理完，返回结果 -> LLM 汇报

v3 的设计原则（观测思维）：
  工具做且只做一件事 -> 返回真实现场状态 -> LLM 观察并推理 -> LLM 决定下一步

类比：
  v2 = 全自动洗衣机（放进去，出来干净衣服，中间不透明）
  v3 = 实验室仪器（显示读数，研究员基于读数判断下一步操作）
```

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
│   ├── observe.py         # 观测工具：read_file / inspect_dir ★ v3 新增
│   └── create_skill.py    # 元工具：运行时生成新 Skill 包 ★
│
└── knowledge/             # 领域知识库（独立于 Skill，供 LLM 推理用）
    ├── model_parameters.md  # 参数物理含义、典型范围
    └── calibration_guide.md # 率定策略、诊断经验
```

### 4.3 运行时信息流（v3 观测驱动版）

```
用户输入："帮我用 GR4J 率定流域 12025000，如果 NSE 不好再用智能率定"
         ↓
  [Agent._build_context()]
  ├── System Prompt（角色定义）
  ├── 匹配 Skill 说明书（calibration/skill.md + llm_calibration/skill.md）
  ├── 领域知识（model_parameters.md -> GR4J 参数含义）
  └── 加载记忆（12025000 流域历史率定记录，如有）
         ↓
  [LLM 推理] -> 调用 validate_basin
  [工具执行] -> {"valid": True, "data_available": "2000-2014"}
         ↓
  [LLM 推理] -> 调用 calibrate_model(gr4j, SCE_UA)
  [工具执行] -> {"best_params": {...}, "calibration_dir": "results/gr4j_12025000",
                 "train_period": [...], "next_step": "call evaluate_model for metrics"}
         ↓
  [LLM 推理] 看到 next_step 提示 -> 调用 evaluate_model(calibration_dir, train_period)
  [工具执行] -> {"metrics": {"NSE": 0.58, "KGE": 0.61}, "metrics_dir": "..."}
         ↓
  [LLM 推理] NSE=0.58 < 0.65，怀疑参数触边界，主动观测
              -> 调用 read_file("results/gr4j_12025000/calibration_results.json")
  [工具执行] -> {"x1": 1998.2, "x2": -4.9, "x3": 35.1, "x4": 1.8}
              LLM 发现 x1=1998.2 极接近上界 2000 -> "触边界！"
         ↓
  [LLM 推理] 确认边界问题 -> 调用 llm_calibrate(gr4j, nse_target=0.75)
  [工具执行 + LLM 迭代范围调整]
         ↓
  [LLM 生成最终报告] 写入 session memory
```

**v2 vs v3 的关键差异**：v2 中 LLM 无法自己发现 x1 触边界，必须依赖工具内部逻辑告知；
v3 中 LLM 通过 `read_file` 直接看到参数值，自主做出"触边界"的判断，
与研究员查看率定结果的过程完全一致。

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
   3.1 整体架构与设计哲学（自动化 vs 观测驱动）
   3.2 Agentic Loop（ReAct 模式）
   3.3 Skill 包系统（工具 + 说明书自包含，动态扩展）
   3.4 四层知识体系（工具调用层 / Skill说明书 / 领域知识库 / 跨会话记忆）
       3.4.1 各层职责划分与独立演进原则
       3.4.2 工具自描述协议（__agent_hint__ 机制）
       3.4.3 与 MCP 的设计同源性及扩展路径
   3.5 LLM 智能参数范围调整机制
   3.6 观测驱动的 Agent 设计
       3.6.1 观测工具（read_file / inspect_dir）
       3.6.2 诊断性工具返回值设计
       3.6.3 目标导向的 Skill 说明书（vs 步骤序列）
       3.6.4 与现有 Agentic 框架的对比（工具黑盒 vs 仪器读数）

4. Experiments
   4.1 实验设置（流域、模型、LLM后端）
   4.2 实验1：端到端标准率定（工具链正确性 + NSE/KGE基线）
   4.3 实验2：自主 LLM 率定工作流（vs 标准SCE-UA vs Zhu et al. 2026）
        模型：GR4J（4参数，经典基准）
        核心论点：C 在零人工干预下完成完整率定，NSE 与 A 等价（C ≈ A），
                  与 Zhu 结论一致（LLM 参与不提升 NSE 上限，价值在于流程自动化）
        指标：NSE 等价性（C ≈ A）、工具序列正确性、轮次（C_rn）、总评估次数（eval_ratio）
        预期结论：
          - C_rn > 1（Agent 自主检测 NSE < target，继续迭代而非停下来等用户）
          - NSE_C ≈ NSE_A（自动化不以精度为代价）
          - 各轮 NSE 轨迹有变化（不同随机种子），Best NSE ≥ Round1 NSE（多轮探索有效）
          - eval_ratio > 1（C 用更多总计算换取零人工干预，是合理 trade-off）
   4.4 实验3：Agent能力广度（NL鲁棒性 + 动态Skill生成 + 自驱动任务规划）
   4.5 实验4：三层知识消融（K0-K3逐层累加，含跨会话记忆验证）

5. Discussion
   5.1 能力边界：LLM 能做什么，不能做什么
   5.2 与 Zhu et al. 2026 的定位对比
        Zhu：1流域，LLM替代优化器，NSE持平，快32%
        HydroClaw：3流域，LLM辅助调控，同样验证"LLM不提升NSE上限但加速收敛"；额外贡献是完整Agentic工作流
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
- ✅ 记忆系统（会话日志 + 跨会话 basin_profiles）
- ✅ 基础工具（calibrate/evaluate/simulate/validate/visualize）
- ✅ LLM 智能率定（`llm_calibrate.py`，参数范围迭代调整）
- ✅ 动态工具生成（`create_tool.py`）
- ✅ 领域知识库（`knowledge/`，含 datasets.md / model_parameters.md / calibration_guide.md）
- ✅ Skill 包系统重构（每个 Skill = skill.md + tool.py 自包含目录）
- ✅ v2.1 核心 Bug 修复（见下）

**v2.1 修复记录（2026-03-08）**
- 修复 NSE/KGE 率定方向反转：SCE-UA/GA 均为最小化器，spotpy_nashsutcliffe 直接传入
  会找最差参数；改为运行时注入 neg_nashsutcliffe/neg_kge，最小化 -NSE = 最大化 NSE
- 修复 AquaFetch 路径层级：DATASET_DIR 需填父目录，否则自动触发重新下载
- 修复 Ctrl+C 无法中断 SCE-UA：移除 ThreadPoolExecutor，改为主线程执行
- 修复 hydromodel 需要 datasets-interim 字段：_ensure_hydro_setting 自动补全
- 配置体系重构：configs/model_config.py + configs/private.py，~/hydro_setting.yml 自动生成

### 待实现

**P0：上下文自动摘要**（前置条件，其余所有长任务都依赖此功能）
- [ ] `agent.py` 每轮前检测历史 token 数，超过阈值（如 80% context window）时
      调一次 LLM 将历史压缩为摘要，用摘要替换历史继续运行
- [ ] 保证 20+ 轮次的批量任务不会因上下文溢出崩溃

**P1：任务状态持久化**（批量实验可靠性）
- [ ] 引入 `task_state.json`，记录每个子任务状态（pending/running/done/failed）和结果
- [ ] 中断后从 pending 任务恢复，已完成任务不重跑
- [ ] 结构示例：`{"goal": "...", "tasks": [{"id": "12025000_gr4j", "status": "done", "nse": 0.72}]}`

**P2：Agent 自驱动任务规划**（已完成架构设计，实现"一句话启动等待结果"）
- [x] `task_state.py`：任务状态 JSON 持久化层（pending/running/done/failed，支持断点恢复）
- [x] `tools/task_tools.py`：三个工具函数注册进 Agentic Loop：
      - `create_task_list(goal, tasks)`：Agent 自行制定工作计划
      - `get_pending_tasks()`：取下一个待执行任务 + 进度摘要
      - `update_task(task_id, status, nse, kge, notes)`：标记完成/失败
- [ ] 在 `skills/system.md` 中补充批量任务工作流指引，让 Agent 知道何时主动创建任务列表
- 关键设计：规划与执行在同一 Agentic Loop 中，无外部协调者，与旧 HydroAgent
  Orchestrator 架构形成鲜明对比（同等能力，N 个组件 → 1 个 Loop + 3 个工具）

**P3：LLM 推理驱动的自适应策略**（已完成，论文差异化贡献）
- [x] `add_task(description)` 工具：Agent 在执行过程中动态追加新任务
- 关键设计：自适应逻辑不依赖硬编码规则（NSE < 阈值 → 重试），
  而是依赖 LLM 的领域推理能力：
    观察结果模式 → 结合 calibration_guide.md 知识解释原因
    → 生成新假设（如"GR4J 线性汇流不适合干旱流域"）
    → 调用 add_task() 追加验证任务 → 执行 → 汇报推理链
- 论文价值：与规则驱动自适应的对比——相同工具、相同结构，
  但适应策略来自 LLM 领域推理而非 if-else 逻辑，
  体现"LLM 即策略"的核心论点

**Phase 4：观测驱动设计升级（v3）** ✅ 已完成（2026-03-08）

*Step 1：观测工具* ✅
- [x] 新建 `hydroclaw/tools/observe.py`：`read_file` / `inspect_dir` 两个工具
- [x] 自动注册进工具发现机制
- [x] 在 `system.md` 中加入"主动观测原则"和触发场景表

*Step 2：诊断性返回值* ✅
- [x] `calibrate_model`：失败时加 `diagnosis`（目录/文件存在情况）；成功时加 `observable_files` + `next_steps`
- [x] `evaluate_model`：加前置检查（calibration_config.yaml 是否存在）；成功时加 `observable_files`（metrics_csv 路径）；修复 Windows emoji 崩溃
- [x] `llm_calibrate`：每轮后调 `evaluate_model` 获取 NSE，加 `boundary_hits` / `final_boundary_hits`；修复 YAML format 和 -999 类型 bug

*Step 3：Skill 说明书重写* ✅
- [x] 全部 7 个 `skill.md` 从"步骤序列"改为"目标 + 判断框架 + 异常处理表"
- [x] 统一加入"何时需要 `inspect_dir` / `read_file`"判断触发条件

**Phase 5：实验设计重构**（2026-03-08，根据论文结构精简）

原 7 个脚本过于分散，评估维度重叠，已整合为 **4 个核心实验**：

| 新编号 | 原脚本来源 | 内容 | 论文节 |
|--------|-----------|------|--------|
| Exp1 | exp1 | 基线率定（5流域×2模型×SCE-UA）| 4.2 |
| Exp2 | exp2 | LLM参数范围调整 vs 标准 vs Zhu et al. | 4.3 |
| Exp3 | exp3+exp4+exp7 合并 | Agent能力广度：NL鲁棒性+动态Skill+自驱动规划 | 4.4 |
| Exp4 | exp5+exp6 合并 | 三层知识消融（K0-K3），K3层内嵌记忆验证 | 4.5 |

**合并理由：**
- Exp3（2知识条件）= Exp6（K0/K3）的子集，单独列出冗余
- Exp5（记忆3阶段）= Exp6 K3层验证的详细版，合并后更紧凑
- Exp4（动态Skill）+ Exp7（自驱动规划）同属"Agent能力演示"，合并为能力广度实验

**脚本状态：**
- [x] exp1_standard_calibration.py — 已完成并测试（2026-03-08）
- [ ] exp2_llm_calibration.py — 待重跑（已修复：随机种子每轮变化、LLM可调整rep/ngs、_DEFAULT_ALGO_PARAMS保证基准值）
  - 根因分析：旧代码 random_seed 恒为1234 → 每轮 SCE-UA 从同一起点出发 → NSE 完全相同（轨迹全平）
  - 修复后预期：各轮 NSE 出现差异，最终 best_nse ≥ A；核心比较指标转向总评估次数和收敛轮次
- [x] exp3_capability_breadth.py — 已重构（合并原 exp3+exp4+exp7，三个 Section）
- [x] exp4_knowledge_ablation.py — 已重构（合并原 exp5+exp6，主消融+对抗先验鲁棒性）

**原 exp5/exp6/exp7/exp4_create_skill 已被合并，保留源文件但不再作为主实验运行。**

**Phase 6：工具自描述与知识层次重构** ✅ 已完成（2026-03-10）

- [x] `fn_to_schema()` 支持读取 `__agent_hint__` 属性并注入 schema description
- [x] 核心工具全部加入 `__agent_hint__`：validate_basin / calibrate_model / evaluate_model /
      generate_code / run_code / llm_calibrate / visualize / compare_models
- [x] `validate_basin` 升级为数据探针：返回 available_variables / full_time_range /
      read_api_note，从"能不能用"扩展为"有什么可用"
- [x] `generate_code` 系统提示词加入完整 CAMELS API 规范（含 t_range 必填说明）
- [x] 更新 `hydroclaw-research-plan.md`：
      三层知识体系 → 四层知识体系，新增"工具自描述协议"创新点（含与 MCP 的关系论述）

**Phase 7：论文写作**（与实验并行）
- [ ] Related Work 初稿
- [ ] System Design 章节（随开发同步更新）
- [ ] 实验结果整理与可视化（plot_paper_figures.py）

**Phase 8：生态扩展基础设施**（2026-03，工程完整性）

目标：让 Agent 能够在用户允许下自主接入新水文包，并妥善管理不断增长的工具集。

*Step 1：包安装工具（`install_package`）*
- [ ] 新建 `hydroclaw/tools/install_package.py`
- 核心约束：**Agent 绝不自主安装**，须用户明确允许；内部通过 `ask_user` 请求授权
- 用 `sys.executable -m pip install` 命中当前 venv，无需硬编码路径
- 错误分级处理：包名不存在 / 版本冲突 / 权限不足 / 网络超时，每类返回可推理的 diagnosis
- `__agent_hint__`：重点标注"ONLY call when user has EXPLICITLY approved"，防止 Agent 自作主张

*Step 2：工具注册优先级元数据（改 `tools/__init__.py`）*
- [ ] 新增 `_TOOL_META: dict[str, dict]`，记录每个工具的 `source`、`priority`、`registered_at`
- 优先级层级（高→低）：adapter 路由函数(30) > tools/ 核心工具(20) > skills/ 工作流工具(10) > 动态生成 skill(5)
- 同名冲突：保留高优先级，低优先级记 warning；相同优先级保留后注册者（符合"更新覆盖"直觉）
- 新增 `list_tools()` 工具函数：Agent 可查询当前所有工具的名称、来源、优先级，支持冲突诊断

*Step 3：README 解析自动注册（`register_package`）*
- [ ] 新建 `hydroclaw/tools/register_package.py`
- 流程：fetch PyPI JSON API → `importlib` 探测公开 API 签名 → LLM 分析生成 adapter 实现 → `create_adapter()` → `reload_adapters()`
- 与 `create_adapter` 的区别：`create_adapter` 只生成骨架（stub），`register_package` 尝试生成可用实现（LLM 看到真实 API 后生成 calibrate/evaluate 方法体）
- LLM 生成代码加 `# AUTO-GENERATED` 注释；方法体失败时 fallback 到 `raise NotImplementedError`，而非静默崩溃
- 需要 `_llm` 注入；整个流程在一次 `register_package` 调用内完成，返回 `{"adapter_file": ..., "auto_implemented": [...], "stubs_remaining": [...], "success": bool}`

*Step 4：`create_skill` 语义去重检查*
- [ ] 在 `create_skill` 调用前，对现有工具 description 做词袋相似度检查（无需向量库，5-50 个工具规模足够）
- 相似度 > 0.6 时，返回警告 + 候选工具列表，让 Agent 决定是否继续创建
- 防止批量任务中因同一需求被多次触发 `create_skill` 而产生大量同功能重复工具

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
