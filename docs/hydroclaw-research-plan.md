# HydroClaw 研究调研与规划文档

> 状态：主动开发中 | 日期：2026-03-19

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
| **Large Language Models as Calibration Agents** (Zhu et al., 2026) | *Geophysical Research Letters* | 5 个 LLM 直接提议 VIC 模型参数值，与 SCE-UA/NSGA-III 对比；**单一流域**（88 个 0.25° 格网） | 最直接参照。DeepSeek-R1 NSE≈SCE-UA（0.895），**收敛快 32%**。局限：仅替代单一优化步骤，无完整工作流，单流域泛化性未验证 |
| **AQUAH** (Yan et al., 2025) | *ICCVW 2025 SEA Workshop* | 首个端到端 NL 驱动水文 Agent（CREST 模型），自动完成数据获取→模型配置→模拟→PDF 报告，Vision-enabled LLM | **直接竞品**，但聚焦冷启动**模拟**（simulation setup），不做参数**率定**；无量化 NSE/KGE，采用专家主观评分（7/10）；无跨会话记忆；无动态能力扩展 |
| **INDRA + CONFLUENCE** (Eythorsson et al., 2025) | *Hydrological Processes* | **5 专家 Agent 协作**（水文、水文地质、气象、数据科学、GIS），Claude API 驱动，集成 CONFLUENCE 模块化水文框架 | **架构对立面**：多 Agent Orchestrator 路线（与旧 HydroAgent 类似）。**无量化实验**（perspectives 类论文）。HydroClaw 用单一 Agentic Loop 实现同等能力，代码量压缩 5×，是对多 Agent 复杂性必要性的反驳 |
| **Wang et al. 2025** | *Water Research* (Elsevier) | 3 种 Agent 策略（Knowledge/Modelling/Coding）对比，用于水分配网络率定与泵站优化，DeepSeek 驱动 | Coding Agent（迭代生成优化代码）最稳定，印证 HydroClaw "LLM 调控外部优化器"优于"LLM 直接提议参数值"的设计选择 |
| **IWMS-LLM** (2025) | *Journal of Hydroinformatics* | 基于 LLM 的智能水资源管理系统 | 对话界面类似，但偏决策支持而非模型执行 |
| **WaterGPT** (2024) | *Water (MDPI)* | 领域微调 LLM | 知识层面，未涉及工作流自动化 |
| **HydroLLM** (2025) | *Environmental Data Science* | 水文领域 LLM 知识评测基准 | 评估基准，非执行框架 |

**核心空白**：现有工作要么停留在"LLM 作为知识问答/单步替代"（Zhu, WaterGPT），要么是无量化验证的多 Agent 系统展望（INDRA），要么聚焦模拟而非率定（AQUAH）。**没有将 LLM 嵌入完整水文率定工作流、以单一 Agentic Loop 实现、具备动态扩展能力、并有量化实证的系统。**

### 2.2 地球科学 Agent 与实验评估方法（领域拓展参考）

| 工作 | 方法要点 | 对 HydroClaw 的启示 |
|------|----------|---------------------|
| **GeoLLM-Squad** (Lee et al., 2025) | 遥感工作流 5 域多 Agent（AutoGen），2000 个合成 prompt，GPT-4o-mini + Qwen，正确率/误差/Token 成本三维评估 | **实验设计参照**：Correctness Rate（工具调用序列正确率）+ 消融（±工具选择、±工作流记忆）+ Token 成本，HydroClaw exp3/exp4 可参考此评估框架 |
| **SUMMA-CAMELS** (Farahani et al., HESS 2025) | 627 流域大样本率定，ML emulator vs 单站，5 折空间交叉验证，normalized KGE' 主指标 | **水文率定实验标准**：KGE' 优于 NSE（理论依据）；数据分割规范（率定期/验证期选择）；5 个流域的合理性辩护方式 |
| **GeoEvolve** (2025, arXiv) | 代码进化器 + RAG + Agentic Controller | 迭代优化 + 知识检索的组合；RAG vs Prompt Stuffing 的设计对比参照 |
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
  LLM 知识问答              ←─── WaterGPT, HydroLLM
  LLM 替代单一优化步骤      ←─── Zhu et al. 2026（单流域，无工作流）
  LLM 辅助决策              ←─── IWMS-LLM
  NL 驱动模拟（无率定）     ←─── AQUAH（无量化指标，无动态扩展）
  多 Agent 系统展望         ←─── INDRA（多 Agent 复杂架构，无量化实验）

HydroClaw 的层次（填补所有空白）：
  自然语言
    → 意图理解
    → Skill 选择（工具 + 领域知识 + 执行策略）
    → PackageAdapter 路由（解耦，热插拔）
    → 工具执行（可动态扩展）
    → 跨会话记忆积累
    → 结果分析 + 报告输出
  ↑ 完整端到端率定-评估-分析 Agentic 工作流
    + 单一 Agentic Loop（对比 INDRA 的多 Agent 复杂性）
    + 量化实证（对比 AQUAH 的主观评分 / INDRA 的无实验）
    + 动态能力扩展（现有所有工作均未覆盖）
```

**关于 INDRA 的定位说明**：INDRA 采用 5 个专家 Agent + Orchestrator 的多 Agent 架构，与 HydroAgent（旧版）的设计路线高度相似，代表了"用复杂系统应对复杂问题"的思路。HydroClaw 的贡献之一正是证明这一复杂性是不必要的——单一 Agentic Loop + 结构化知识注入 + PackageAdapter 可以实现同等能力，代码量仅约 1/5，且有量化验证。INDRA 是 perspectives 类论文（无实验），HydroClaw 是实证系统。两者不竞争，INDRA 反而为 HydroClaw 的简洁性论点提供了对照。

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

9. **PackageAdapter 插件架构（Plugin-Based Hydrology Package Ecosystem）**

   现有水文 Agentic 系统均假设工具集与特定计算包静态绑定。HydroClaw 引入 **PackageAdapter 层**将 Agent 核心与水文计算包完全解耦，并以"五层大脑-脊椎-四肢"模型形式化这一设计：

   ```
   [大脑]  agent.py (ReAct Loop)      推理/决策，不关心包 API
   [小脑]  skills/*/skill.md          程序记忆，塑造决策模式
   [脊椎]  adapters/*/adapter.py      双向翻译：意图 -> 包调用
   [末梢]  skills/*/xxx.py + tools/   薄路由，找适配器
   [肌肉]  hydromodel / hydrodataset  数值计算，不知 Agent 存在
   ```

   **三项关键机制：**

   - **优先级路由 + 优雅降级**：`get_adapter(data_source, model_name)` 按 priority 降序匹配第一个 `can_handle=True` 的适配器（hydrodatasource=15, hydromodel=10, generic=0）；若无专用适配器，GenericAdapter 返回结构化引导而非报错，LLM 可读懂并通过 `generate_code` 另辟蹊径。

   - **灵活接口（supported_operations + execute dispatch）**：适配器不再被强制实现固定的 4 个方法（calibrate/evaluate/visualize/simulate），而是声明自己支持的操作集合并统一路由。hydrodatasource 可暴露 `list_basins / read_data / convert_to_nc`，hydromodel 暴露 `calibrate / evaluate / simulate`——接口与操作集完全解耦。

   - **热插拔（Hot-swap via create_adapter）**：元工具 `create_adapter(name, desc)` 生成适配器骨架 + `adapters/<name>/skills/skill.md`，随后自动调用 `reload_adapters()`——新包即时生效，无需重启 Agent。

   **工具优先级元数据体系**（与适配器层配合）：
   `tools/__init__.py` 为每个工具记录来源和优先级（核心工具=20，Skill工具=10，动态生成=5），同名冲突时保留高优先级者并记录 warning。`list_tools()` 工具让 Agent 可自查当前工具集，支持冲突诊断。

   **论文价值**：PackageAdapter 层是"工具调用层"（创新点7）的系统级实现——`__agent_hint__` 解决单个工具的调用正确性问题，PackageAdapter 解决整包接入与生态扩展问题。两者共同构成 HydroClaw 可持续扩展的工程基础。

10. **观测驱动的 Agent 设计（Observation-Driven Agent Design）**
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
| 包集成方式 | 硬耦合（直接 import hydromodel） | 同左 | PackageAdapter 插件层（解耦，热插拔） |
| 扩展方式 | 新增 Agent（改核心代码） | 新增 Skill 包（不改核心） | 新增适配器 + 新增 Skill 包（均不改核心） |
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

### 4.2 目录结构（当前实现状态，v2.5）

```
hydroclaw/
├── agent.py               # Agentic Loop 核心（ReAct 模式）
├── llm.py                 # LLM 客户端（Function Calling + Prompt 降级）
├── memory.py              # 三层记忆（会话/MEMORY.md/流域档案）
├── config.py              # 配置管理
│
├── adapters/              # ★ v2.5 新增：PackageAdapter 插件层
│   ├── __init__.py        # 自动扫描发现 + get_adapter() + get_all_skill_docs()
│   ├── base.py            # PackageAdapter 抽象接口（supported_operations + execute）
│   ├── hydromodel/
│   │   ├── adapter.py     # HydromodelAdapter（priority=10，负责率定/评估/可视化）
│   │   └── skills/
│   │       └── hydromodel.md   # hydromodel 调用方式（注入 system prompt）
│   ├── hydrodatasource/
│   │   ├── adapter.py     # HydrodatasourceAdapter（priority=15，负责自定义数据集）
│   │   └── skills/
│   │       └── hydrodatasource.md
│   └── generic/
│       └── adapter.py     # GenericAdapter（priority=0，兜底，返回结构化引导）
│
├── skills/                # Skill 包（工作流说明书 + 工具实现，双层含义）
│   ├── system.md          # 系统基础 prompt（每次都注入）
│   ├── calibration/
│   │   ├── skill.md       # 工作流指引（关键词匹配时注入）
│   │   └── calibrate.py   # calibrate_model() 工具（priority=10）
│   ├── llm_calibration/
│   │   ├── skill.md
│   │   └── llm_calibrate.py
│   ├── evaluation/
│   │   ├── skill.md
│   │   └── evaluate.py
│   ├── visualization/
│   │   ├── skill.md
│   │   └── visualize.py
│   ├── hydrodatasource/   # 自定义数据集工具（Skill 级别，priority=10）
│   │   └── dataset_tools.py  # list_basins / read_dataset / convert_dataset_to_nc
│   ├── hydrodataset/      # 公开数据集工具
│   │   └── hydrodataset_tools.py  # list_camels_basins / check_camels_data
│   └── [动态生成 Skill]   # create_skill 生成，立即注册（priority=5）
│       ├── skill.md
│       └── tool.py
│
├── tools/                 # 核心基础工具（优先级=20，最高）
│   ├── __init__.py        # 工具发现引擎（扫描 tools/ + skills/，记录优先级元数据）
│   ├── validate.py        # validate_basin()
│   ├── simulate.py        # run_simulation()
│   ├── observe.py         # read_file() / inspect_dir()  ★ 观测工具
│   ├── task_tools.py      # create_task_list / get_pending_tasks / update_task / add_task
│   ├── create_skill.py    # 元工具：动态生成 Skill 包
│   ├── create_adapter.py  # 元工具：动态生成 PackageAdapter 骨架 ★ v2.5
│   ├── install_package.py # 受控包安装（需用户授权）
│   └── register_package.py# LLM 分析 PyPI API 自动生成适配器实现
│
└── knowledge/             # 领域知识库（按关键词注入，独立于 Skill）
    ├── model_parameters.md  # 参数物理含义、典型范围（GR4J/GR5J/GR6J/HBV/LSTM）
    └── calibration_guide.md # 率定策略、诊断经验、边界效应识别
```

**两种 Skill 的区分（容易混淆的设计决策）**：

| 类型 | 位置 | 注入时机 | 作用 |
|------|------|---------|------|
| 工作流 Skill | `skills/*/skill.md` | 关键词匹配时注入 | 告诉 LLM "这类任务该怎么做"（程序记忆） |
| 适配器 Skill | `adapters/*/skills/*.md` | 每次对话都注入 | 告诉 LLM "这个包的 API 怎么调"（包文档） |

**知识注入顺序**（system prompt 构建）：
```
system.md
+ 匹配的工作流 Skill 说明书       <- Skill 层（按查询关键词筛选）
+ 适配器包文档（hydromodel.md 等）<- Adapter 层（全量注入）
+ 领域知识（calibration_guide.md）<- Knowledge 层（按关键词筛选）
+ 流域档案（basin_profiles/）     <- Memory 层（按 basin_id 筛选）
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

### 4.5 知识检索策略：Prompt Stuffing vs RAG

HydroClaw 当前**不使用向量数据库或语义检索（RAG）**，而采用关键词触发的静态文档注入（Prompt Stuffing）。这是一个有意识的工程决策，值得在论文方法论部分说明：

| 维度 | Prompt Stuffing（当前方案） | RAG（向量检索） |
|------|---------------------------|----------------|
| 实现复杂度 | 极低（读文件 + 字符串拼接） | 中（需向量库 + embedding 模型） |
| 适用规模 | 知识文档 < 10 个，单文档 < 2000 字 | 文档 > 50 个，或单文档很长 |
| 检索精度 | 关键词匹配，粗粒度 | 语义相似度，细粒度 |
| 上下文占用 | 整文档注入，占用较多 | 只取最相关片段，节省 token |

**当前为何够用**：HydroClaw 的知识文档数量少（< 10 个）、单文档紧凑（< 2000 字），Skill 匹配精度够用。**升级条件**：`knowledge/` 目录超过 10 个文档，或某文档超过 3000 字时，引入向量检索。

**论文价值**：这一决策本身体现"轻量 Agentic 系统"的设计哲学——在规模允许范围内选择最简实现，不过度工程化。与以 RAG 为核心贡献的工作（如 GeoEvolve）形成互补定位。

### 4.6 上下文长度控制

长批量任务（20+ 轮次）的上下文爆炸是 Agentic 系统的工程难题。HydroClaw 的处理策略：

- **工具结果截断**：`context_utils.py` 的 `truncate_tool_result()`，字段级 8K + 整体 16K 上限，防止 run_code stdout 等大输出填满上下文
- **历史压缩**：`_maybe_compress_history()`，对话历史超过 60,000 估算 token 时，保留 [system + 原始查询 + 最近 4 条]，中间历史由 LLM 压缩为摘要
- **任务状态外化**：`task_state.json` 持久化任务列表到磁盘，`get_pending_tasks()` 每轮只返回摘要，避免任务列表累积在 messages 中

**当前局限**：历史压缩是"一次性"策略，压缩后摘要本身也会继续增长；30+ 轮的极端长任务中仍可能超限。分层记忆（工作记忆 + 短期摘要 + 长期档案）是未来方向。

---

## 五、论文写作规划

### 5.1 论文定位

> 本节经 2026-03-30 专项调研后更新，覆盖期刊选择、命名说明、题目确定及完整调研报告。

**首投期刊（确定）**：*Geoscientific Model Development*（EGU，**JCR Q1**，IF≈6.0，开放获取强制）

> **注意**：GMD 在**中科院分区**为地学 **Q2**（IF 6.0 低于 Q1 门槛约 6.5），在 **JCR 分区**（Geosciences Multidisciplinary）为 **Q1**。若所在单位/导师要求中科院 Q1，请改投 JoH。
>
> 选择依据：HydroClaw 本质是建模框架，框架本身即贡献。GMD 专门发表地球系统模型/工具开发论文，
> 不要求"水文科学发现"作为主叙事，与 HydroClaw 论文体质天然契合。
> AI4Water v1.0（GMD 2022）、smash v1.0（GMD 2025）是直接先例。

**拒稿后备选（降序）**：

1. *Journal of Hydrology*（Elsevier，**中科院地学 Q1**，IF≈6.5）— 若需中科院 Q1 则优先此项；需将主叙事改为"LLM 如何改善水文率定结果"，补充参数物理解释，压缩框架描述
2. *Hydrology and Earth System Sciences*（EGU，中科院地学 Q1，IF≈6.0，开放获取）
3. *Environmental Modelling & Software*（Elsevier，中科院工程/环境 **Q2**（多数年份），IF≈5.5）— 内容最契合，但底层栈（hydromodel/hydrodataset）的框架论文已于 EM&S 2026 发表，存在"增量工作"拒稿风险
4. *Journal of Hydroinformatics*（多篇 LLM+水文前例，门槛相对低）

**论文类型**：Model Description Paper + Empirical Validation（GMD 标准论文类型）

**确定题目**：
> **HydroClaw v1.0: an LLM-powered agentic framework for automated hydrological model calibration with structured domain knowledge**

格式对标 GMD 惯例（系统名+版本号+冒号+一句话描述），关键词覆盖：LLM / agentic / automated / calibration / domain knowledge。

**项目命名说明（论文 Introduction 第一段写入）**：

> HydroClaw derives its name from OpenClaw, the lightweight agentic loop framework that inspired
> its architectural design. The "Hydro" prefix marks its domain-specific adaptation to hydrological
> modeling workflows — following the same pattern by which domain-specialized tools extend general
> computational frameworks for geoscientific applications (cf. HydroLang, AI4Water).

命名逻辑的学术价值：直接建立技术谱系（OpenClaw -> HydroClaw），印证论文核心论点"通用 Agentic Loop + 领域知识注入 = 专精 Agent"，名字本身即对这一论点的演示。

---

### 5.0 期刊调研报告（2026-03-27）

#### 5.0.1 Journal of Hydrology 范围与偏好

根据 JoH 官方作者指南和近年发表规律：

| 维度 | 期刊偏好 | HydroClaw 对齐度 |
|------|---------|----------------|
| **空间尺度** | **流域尺度**，明确排斥纯站点实验 | GR4J/HBV 在 CAMELS 流域率定，符合 |
| **科学问题** | 水文过程理解、预测精度、参数不确定性 | **弱**：HydroClaw 重点是工作流自动化，非新水文发现 |
| **数据规模** | 大样本（CAMELS，10+ 流域）是近年主流 | **偏少**：5 流域，审稿人可能要求扩大 |
| **方法论文** | 接受，但必须有量化 NSE/KGE 验证 | 有量化指标，符合 |
| **软件框架** | 较少，框架类更常见于 EM&S/GMD | **风险**：Exp3/Exp4 偏 AI 系统评估，需包装成水文问题 |

投 JoH 核心前提：主叙事必须是"LLM Agent 如何改善水文率定的科学结果"，框架是手段，水文发现是目的。

#### 5.0.2 近年相关文献地图（2024-2026）

**A. 直接竞品（LLM + 水文工作流）**

| 论文 | 期刊 | 年份 | 与 HydroClaw 差异 |
|------|------|------|-----------------|
| Zhu et al. — LLMs as Calibration Agents | *GRL* | 2026 | 仅替换单步参数提议；HydroClaw 是端到端闭环 + 多流域 |
| Wang et al. — LLMs for Water Distribution Network | *Water Research* | 2025 | 管网水力优化（非降雨径流率定）；无跨会话记忆；无动态扩展 |
| INDRA — Automated Scientific Discovery in Hydrology | *Hydrological Processes* | 2025 | 概念框架，无量化实验；HydroClaw 有完整实证 |
| AQUAH | *ICCVW SEA Workshop* | 2025 | 只做模拟设置，不做率定；主观评分（7/10），无 NSE/KGE |

**B. GMD 框架论文先例（直接参照）**

| 论文 | 年份 | 对 HydroClaw 的参照价值 |
|------|------|----------------------|
| AI4Water v1.0（ML/DL 水文时序 Python 包） | 2022 | 结构最相似：框架即贡献，基准案例验证，无新水文发现 |
| RoGeR v3.0.5（过程水文 Python 工具箱） | 2024 | 模块化工具箱描述范式 |
| smash v1.0（可微水文建模+数据同化框架） | 2025 | 复杂框架在 GMD 发表的案例 |
| Python framework for differentiable hydrology（hydromodel/hydrodataset 栈） | EM&S 2026 | HydroClaw 底层依赖栈，已发表于 EM&S → EM&S 再投有增量风险 |

#### 5.0.3 GMD 路线论文结构

```
1. Introduction（15%）
   - 水文模型率定自动化需求
   - 现有框架局限：手动配置、无 NL 接口、无工作流编排
   - HydroClaw 设计目标与三条贡献

2. Framework Design（50% — GMD 核心）
   2.1 整体架构：五层模型（大脑/小脑/脊椎/末梢/肌肉）
   2.2 Agentic Loop（ReAct 模式，工具调用协议）
   2.3 PackageAdapter 插件层（优先级路由、热插拔）
   2.4 Skill 包系统（工作流说明书 + 工具自包含）
   2.5 四层知识体系（工具自描述/Skill/领域知识/跨会话记忆）
   2.6 LLM 参数范围调控机制（llm_calibrate）
   2.7 上下文控制策略（截断机制、Token 预算）

3. System Evaluation（25%）
   3.1 正确性基准（Exp1）：Agent 是否复现标准 SCE-UA 结果？
   3.2 LLM 调控模块验证（Exp2 A/B/C）：参数范围调整 -> NSE 改进因果链
   3.3 框架鲁棒性与可扩展性（Exp3）：NL 多样性 + 动态 Skill 生成
   3.4 知识注入模块消融（Exp4 K0-K3）：各知识层贡献量化

4. Limitations and Future Development（10%）
   - LLM 随机性与可复现性（报告 mean±std）
   - Token 成本与延迟（TokenTracker 数据）
   - 当前支持模型范围（GR4J/GR5J/GR6J/HBV）
   - 大样本验证路线（50-100 流域）

5. Code and Data Availability（必须）
   - GitHub 仓库链接 + Zenodo DOI（v1.0 tag release）
   - 安装文档、实验复现脚本、最小可运行示例
```

#### 5.0.4 GMD 审稿人预期质疑与应对

| 预期质疑 | 应对策略 |
|---------|---------|
| "LLM 有随机性，结果可复现吗？" | 每实验重复 3 次报告 mean±std；提供完整配置文件；工具调用序列可记录 |
| "依赖哪个 LLM，版本锁定怎么办？" | 说明 OpenAI-compatible API 可替换性；实验用 Qwen/DeepSeek（非付费 GPT-4 only）|
| "代码在哪？许可证？" | GitHub 链接 + Zenodo DOI + Apache-2.0 许可 |
| "与 AI4Water 的区别？" | AI4Water = DL 预测模型训练工具；HydroClaw = 过程模型率定 Agentic 框架（NL -> SCE-UA/LLM 调控）|
| "Token 成本实用吗？" | 报告每次率定的 token 消耗（TokenTracker）和估算美元成本 |

#### 5.0.5 面向 JoH（备选）的撰写策略

若 GMD 拒稿转投 JoH，需做以下调整：

- **主叙事重构**：从"我们构建了一个框架"改为"我们研究了 LLM 参与水文率定的条件和效果"
- **实验重新定位**：Exp1/Exp2 升级为主实验（水文科学结果），Exp3 降格为补充验证，Exp4 改名"领域知识贡献量化"
- **加参数物理解释**：记录 LLM 每轮调整 GR4J 参数方向，与流域气候特征（干旱指数 AI、面积）关联分析
- **5 流域规模论证**：覆盖 3 个气候区 + 每组 3 次重复 + 引用 Zhu 2026（GRL，单流域）说明探索性研究规模惯例

---

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
       3.1.1 从多 Agent 状态机到单 Agentic Loop：架构演进对比
       3.1.2 五层大脑-脊椎-四肢模型（Agent 核心 / Skill 说明书 / PackageAdapter / 工具路由 / 功能包）
       3.1.3 设计原则：让 LLM 做决策，代码只做执行
   3.2 Agentic Loop（ReAct 模式）
       3.2.1 无状态机的核心循环（LLM 决定何时结束）
       3.2.2 Agent 自驱动任务规划（create_task_list / get_pending_tasks 内化编排）
   3.3 PackageAdapter 插件架构（水文包生态解耦）
       3.3.1 动机：打破 Agent 与计算包的硬耦合
       3.3.2 适配器接口设计（supported_operations + execute dispatch vs 固定方法集）
       3.3.3 优先级路由与优雅降级（GenericAdapter 结构化引导）
       3.3.4 热插拔：create_adapter + reload_adapters() 无重启生效
       3.3.5 工具优先级元数据体系（priority=20/10/5，同名冲突解决策略）
   3.4 Skill 包系统（工具 + 说明书自包含，动态扩展）
       3.4.1 双层 Skill 概念（工作流说明书 vs 适配器包文档）
       3.4.2 关键词匹配注入 vs 全量注入的设计权衡
       3.4.3 动态 Skill 生成（create_skill 元能力）
   3.5 四层知识体系（工具调用层 / Skill说明书 / 领域知识库 / 跨会话记忆）
       3.5.1 各层职责划分与独立演进原则
       3.5.2 工具自描述协议（__agent_hint__ 机制与 MCP 的设计同源性）
       3.5.3 知识注入顺序与上下文控制（Prompt Stuffing vs RAG 的选择依据）
   3.6 LLM 智能参数范围调整机制
   3.7 观测驱动的 Agent 设计
       3.7.1 观测工具（read_file / inspect_dir）
       3.7.2 诊断性工具返回值设计
       3.7.3 目标导向的 Skill 说明书（vs 步骤序列）
       3.7.4 与现有 Agentic 框架的对比（工具黑盒 vs 仪器读数）

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
   5.3 单一 Agentic Loop vs 多 Agent 系统（以 INDRA 为对照）
        INDRA：5 专家 Agent + Orchestrator，无量化验证，多 Agent 协调复杂
        HydroClaw：单一 Loop + PackageAdapter + Skill，同等能力，代码量 1/5，有量化实证
        结论：水文领域的 Agent 复杂性需求可由单 Loop + 结构化知识注入满足，不需要多 Agent 状态机
   5.4 与 AQUAH 的差异化：模拟 vs 率定，主观评分 vs 量化指标
        AQUAH：冷启动模拟，专家主观评分，无跨会话记忆，无动态扩展
        HydroClaw：率定-评估-分析闭环，量化 KGE/NSE，跨会话流域档案，create_skill 动态扩展
   5.5 局限性与未来方向（多流域扩展、RAG 升级、分布式模型支持）

6. Conclusion
```

### 5.3 核心论证逻辑

**论文核心论点**：
> "将 LLM 嵌入水文建模工作流的关键不在于让 LLM 替代优化算法，而在于构建五层插件化 Agentic 框架——以 PackageAdapter 解耦水文计算包、以 Skill 包封装领域工作流知识、以工具自描述协议确保调用正确性、以观测驱动设计赋予 Agent 自主诊断能力——LLM 作为智能协调者，通过四层结构化知识驱动完整工作流，并在能力不足时动态扩展自身。"

与现有工作的关系：
- vs Zhu et al. 2026：LLM **调控搜索空间**（范围调整）而非替代搜索算法 → 互补；HydroClaw 额外提供完整 Agentic 工作流
- vs WaterGPT/HydroLLM：不是训练专用模型，而是让通用 LLM 通过结构化知识注入获得领域能力 → 更轻量
- vs GeoLLM-Squad：单 Agentic Loop + PackageAdapter 插件层，而非多 Agent 状态机 → 同等扩展能力，更简洁可控
- vs OpenClaw：引入 PackageAdapter 层对接领域计算包，并将 Skill 从"预安装"升级为"按需生成" → 更适合科学计算场景

**架构演进的核心数据点**（可作为 System Design 章节的量化对比）：

| 指标 | HydroAgent（旧） | HydroClaw |
|------|-----------------|-----------|
| 代码量 | ~27,000 行 | ~5,000 行 |
| 核心组件数 | 5 Agent + 1 Orchestrator | 1 Agentic Loop |
| 工作流编排代码 | 960 行 if-else 路由 | 0 行（LLM 推理） |
| 新增水文包所需改动 | 改 Agent + 注册 + 路由（数十处） | 实现 1 个适配器类（~100行） |
| 新增工作流能力 | 改子 Agent + 重新部署 | create_skill（运行时，~30s） |

### 5.4 实验设计改进建议（基于文献对比）

对比 Zhu 2026（GRL）、GeoLLM-Squad 2025、SUMMA-CAMELS 2025 等文献的实验规范，HydroClaw 当前实验设计需要以下改进：

#### P0 级（审稿必须满足）

| 问题 | 现状 | 改进方向 | 文献依据 |
|------|------|---------|---------|
| 缺乏统计显著性 | Exp1/Exp2 每组单次运行 | 每组至少 3 次不同随机种子，报告 mean ± std | GeoLLM-Squad（多次评估），SCE-UA 本身有随机性 |
| NSE vs KGE 主指标 | NSE 为主，KGE 辅助 | 改为 **KGE 为主，NSE 辅助**，引用 Knoben et al. 2019 说明理由 | SUMMA-CAMELS：KGE' 对均值偏差更敏感，比 NSE 更均衡 |
| 训练/验证期未文档化 | 脚本中未显式记录 | 论文实验设置部分加一个"流域数据时段表" | SUMMA-CAMELS 明确记录 1982-1989 / 2003-2009 |

#### P1 级（强化论文说服力）

| 问题 | 现状 | 改进方向 | 文献依据 |
|------|------|---------|---------|
| Exp2 只测 1 个 LLM | Method C 用单一 LLM | 加第 2 个 LLM 对比（推理型 DeepSeek-R1 vs 对话型 Qwen/GPT-4o），加一列结论 | Zhu 2026 测 5 个 LLM，推理型优势明显 |
| 缺效率指标 | 只有 eval_ratio | 所有实验加 `total_tokens`（已有计数）+ `wall_time_sec` | GeoLLM-Squad 报告 Token Cost 作为独立维度 |
| 缺 AQUAH 对比 | Related Work 未提 | 加入 Related Work，说明率定 vs 模拟、量化 vs 主观评分的差异 | AQUAH (ICCVW 2025)，最新直接竞品 |

#### P2 级（锦上添花）

| 问题 | 现状 | 改进方向 | 文献依据 |
|------|------|---------|---------|
| 缺失败类型分类 | 只记录成功/失败 | 从日志中提取失败类型（工具序列错误/参数错误/上下文超限）并列表 | Wang et al. 2025 专门分析 LLM 失败模式 |
| 缺参数敏感性分析 | boundary_hits 已记录但未分析 | 从 boundary_hits 提取"LLM 最常调整哪些参数"，与水文专家认知对比 | Zhu 2026 用 SHAP+XGBoost 做参数重要性（轻量版同样有效） |
| 场景重复性不足 | Exp3 Section A 6 场景各跑 1 次 | 每场景重复 3 次，报告工具序列一致性（consistency rate） | AgentBench：重复性是 agentic 评估的基本要求 |

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

**Phase 8：生态扩展基础设施** ✅ 已完成（2026-03-19）

目标：让 Agent 能够在用户允许下自主接入新水文包，并妥善管理不断增长的工具集。

*Step 1：PackageAdapter 框架* ✅
- [x] `hydroclaw/adapters/base.py`：PackageAdapter 抽象接口（supported_operations + execute dispatch）
- [x] `hydroclaw/adapters/__init__.py`：自动扫描 + get_adapter() 路由 + reload_adapters() 热重载
- [x] HydromodelAdapter（priority=10）、HydrodatasourceAdapter（priority=15）、GenericAdapter（priority=0）
- [x] `hydroclaw/tools/create_adapter.py`：元工具，动态生成适配器骨架 + 自动 reload

*Step 2：工具注册优先级元数据* ✅
- [x] `tools/__init__.py`：PRIORITY_TOOLS=20, PRIORITY_SKILLS=10, PRIORITY_DYNAMIC=5
- [x] 同名冲突：保留高优先级，低优先级记 warning；`list_tools()` 工具可查询工具集状态

*Step 3：包安装与自动注册工具* ✅
- [x] `hydroclaw/tools/install_package.py`：受控包安装（需用户授权，__agent_hint__ 防止自主安装）
- [x] `hydroclaw/tools/register_package.py`：fetch PyPI JSON API → importlib 探测 → LLM 分析 → create_adapter() → reload_adapters()
- [x] `create_adapter` 生成骨架（stub）；`register_package` 尝试生成可用实现，失败 fallback 到 NotImplementedError

*Step 4：hydrodatasource 接入* ✅
- [x] `hydroclaw/skills/hydrodatasource/dataset_tools.py`：list_basins / read_dataset / convert_dataset_to_nc（priority=10）
- [x] `hydroclaw/skills/hydrodataset/hydrodataset_tools.py`：list_camels_basins / check_camels_data
- [x] Web UI 数据集管理：公开数据集状态展示、自定义数据集 NC 缓存（含多时间尺度支持）

---

## 七、参考文献（已识别）

### 水文领域 LLM / Agentic 系统（核心）

1. Zhu et al. (2026). *Large Language Models as Calibration Agents in Hydrological Modeling: Feasibility and Limitations*. Geophysical Research Letters. https://doi.org/10.1029/2025GL120043

2. Yan et al. (2025). *AQUAH: Automatic Quantification and Unified Agent in Hydrology*. ICCV 2025 SEA Workshop. https://arxiv.org/abs/2508.02936
   — 首个端到端 NL 驱动水文 Agent（模拟方向），HydroClaw 的直接竞品（率定方向）

3. Eythorsson et al. (2025). *Toward Automated Scientific Discovery in Hydrology: The Opportunities and Dangers of AI Augmented Research Frameworks*. Hydrological Processes. https://doi.org/10.1002/hyp.70065
   — INDRA 多 Agent 系统（5 专家 Agent），perspectives 类，无量化实验，与 HydroClaw 单 Loop 形成架构对比

4. Wang, Fu, Savic (2025). *Leveraging Large Language Models for Automating Water Distribution Network Optimization*. Water Research. https://doi.org/10.1016/j.watres.2025.124536
   — 3 种 Agent 策略对比；Coding Agent 最优，印证"LLM 调控外部优化器"设计

5. IWMS-LLM (2025). *An intelligent water resources management system based on large language models*. Journal of Hydroinformatics. https://iwaponline.com/jh/article/27/11/1685/110111/

6. WaterGPT (2024). *Training a Large Language Model to Become a Hydrology Expert*. Water (MDPI). https://www.mdpi.com/2073-4441/16/21/3075

7. HydroLLM (2025). *Toward HydroLLM: a benchmark dataset for hydrology-specific knowledge assessment*. Environmental Data Science. https://www.cambridge.org/core/journals/environmental-data-science/article/toward-hydrollm/585BFB32C8F14A7C8E8D93F1E0E08020

### 大样本水文率定（实验设计规范参照）

8. Farahani et al. (2025). *Calibrating a Large-Domain Land/Hydrology Process Model in the Age of AI: the SUMMA CAMELS Emulator Experiments*. Hydrology and Earth System Sciences, 29(18), 4515-4537. https://doi.org/10.5194/hess-29-4515-2025
   — 627 流域，5 折交叉验证，normalized KGE' 主指标，水文率定实验设计的黄金标准

9. Knoben et al. (2019). *Inherent benchmark or not? Comparing Nash–Sutcliffe and Kling–Gupta efficiency scores*. Hydrology and Earth System Sciences, 23, 4323-4331.
   — KGE 优于 NSE 的理论依据（必引）

### 地球科学 Agentic 系统

10. Lee et al. (2025). GeoLLM-Squad. *Accelerating earth science discovery via multi-agent LLM systems*. Frontiers in AI. https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1674927/full
    — 实验设计参照：Correctness Rate + Token Cost + 消融实验框架

11. GeoEvolve (2025). *Automating Geospatial Model Discovery via Multi-Agent Large Language Models*. arXiv. https://arxiv.org/html/2509.21593v1

### Agentic 系统评估方法论

12. Liu et al. (2023). *AgentBench: Evaluating LLMs as Agents*. ICLR 2024. https://arxiv.org/abs/2308.03688
    — 工具调用序列正确率的评估框架参照

### 其他水文 / LLM 相关

13. AI-driven multi-agent water resource planning (2025). Journal of Hydroinformatics. https://iwaponline.com/jh/article/27/7/1217/108550/

---

*本文档随项目进展持续更新*
