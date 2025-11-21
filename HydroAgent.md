# HydroAgent系统概述 (System Overview)
HydroAgent 是一个专为水文建模设计的智能体系统。它利用大语言模型（LLM）的语义理解与推理能力，将用户的自然语言指令转化为 hydromodel 的标准执行流程。

该系统的核心目标是实现 "Conversation-to-Simulation"（对话即模拟），自动化处理从数据准备、参数配置、模型率定到结果分析的全过程，降低水文模型应用的技术门槛
# 1.设计哲学 (Design Philosophy)
非侵入式 (Non-intrusive): 不修改 hydromodel 的任何源码。HydroAgent 视为 hydromodel 的一个“高级用户”。

配置驱动 (Configuration Driven): 利用 hydromodel 基于 YAML 配置文件的特性，智能体通过读写配置文件来控制底层引擎。

工作区隔离 (Workspace Isolation): 所有的中间文件（配置、日志、结果）都存储在独立的工作目录中，保持环境整洁。


# 2 .系统架构 (System Architecture)

HydroAgent 是一个独立的项目，hydromodel 只是它的一个依赖项

```
HydroAgent/
├── hydroagent/                 # [核心包] 所有的业务逻辑都在这里
│   ├── __init__.py                # 暴露核心接口，如 Orchestrator
│   ├── core/                      # [新增] 核心基础类
│   │   ├── __init__.py
│   │   ├── base_agent.py          # 智能体基类 (定义通用 Prompt 处理)
│   │   └── llm_interface.py       # LLM API 统一接口 (OpenAI/Claude)
│   ├── agents/                    # [智能体层] 具体智能体实现
│   │   ├── __init__.py
│   │   ├── orchestrator.py        # 中央编排器 (系统大脑)
│   │   ├── intent_agent.py        # 意图与数据智能体 (Exp 1 & 4)
│   │   ├── config_agent.py        # 配置生成智能体 (Exp 2)
│   │   ├── runner_agent.py        # 执行监控智能体 (调用 hydromodel)
│   │   └── developer_agent.py     # 开发者智能体 (Exp 3, 代码生成)
│   ├── utils/                     # [工具层] 对应之前的关键技术实现
│   │   ├── __init__.py
│   │   ├── schema_validator.py    # (对应技术 4.1) 配置校验器
│   │   ├── result_parser.py       # (对应技术 4.2) 结果解析中间件
│   │   ├── error_handler.py       # (对应技术 4.5) 异常拦截与反馈
│   │   └── code_sandbox.py        # (对应技术 4.4) 沙箱代码执行器
│   └── resources/                 # [资源层] (对应技术 4.6) RAG 静态文件
│       ├── __init__.py            # 使其可被 pkg_resources 读取
│       ├── schema_definition.json # hydromodel 配置规范
│       ├── api_signatures.yaml    # hydromodel 函数签名知识库
│       └── few_shot_prompts.py    # 提示词模板
├── scripts/                       # [调用层] 命令行脚本与入口
│   ├── cli.py                     # 交互式命令行入口
│   ├── run_experiment_1.py        # 专门运行通用性实验的脚本
│   ├── run_experiment_2.py        # 专门运行自适应优化实验的脚本
│   └── run_experiment_3.py        # 专门运行代码扩展实验的脚本
├── tests/                         # [测试层] 单元测试与集成测试
│   ├── __init__.py
│   ├── test_agents/               # 测试各个 Agent 的逻辑
│   │   ├── test_intent.py
│   │   └── test_config_gen.py
│   └── test_integration/          # 端到端集成测试
│       └── test_full_flow.py
├── docs/                          # [文档层]
│   ├── architecture.md            # 架构设计文档
│   └── user_guide.md              # 使用说明
├── examples/                      # [示例数据]
│   └── user_queries.txt           # 测试用的自然语言指令集
├── workspace/                     # [运行时] 自动生成的工作目录 (git ignored)
├── pyproject.toml                 # 现代化构建配置 (或 setup.py)
├── requirements.txt               # 依赖列表 (hydromodel, langchain, etc.)
└── README.md                      # 项目主页
```    


# 3. 多智能体架构详解 (Multi-Agent Architecture)
3.1 中央编排器 (Orchestrator)
职责: 维护对话状态、管理 workspace 目录创建、在智能体之间传递上下文（Context）。

3.2 🟢 Intent Agent (意图与数据智能体)

角色: 类似于 OpenFOAMGPT 的 Pre-processing Agent 。

功能:

意图分类: 区分 Calibration / Evaluation / Simulation / Extension (扩展功能)。

数据校验: 使用 hydromodel 的 hydrodataset 模块检查数据是否存在。

信息补全: 如果用户只说“跑一下模型”，它负责决定默认使用哪个流域、什么时间段。

与 hydromodel 交互: 仅导入 hydrodataset 用于查询数据路径。

3.3 🔵 Config Agent (配置专家智能体)

角色: 类似于 OpenFOAMGPT 的 Prompt Generation Agent 。



功能:

配置合成: 基于 Intent Agent 的输出，生成符合 hydromodel 标准的 YAML 字典。

参数策略: 决定 training_cfgs 中的算法参数（如 SCE_UA 的 rep 次数）。

自适应调整: 在实验2中，它负责读取旧的 param_range.yaml，根据上一轮结果生成新的 param_range_new.yaml。

输出: 在 workspace/exp_id/ 下写入 config.yaml。

3.4 🟠 Runner Agent (执行与监控智能体)

角色: 类似于 OpenFOAMGPT Simulator 。



功能:

API 调用: 通过 Python 代码 from hydromodel.trainers.unified_calibrate import calibrate 启动任务。

进程监控: 捕获标准输出（stdout）和错误（stderr）。

错误反馈: 如果 hydromodel 抛出异常（如配置错误），将 Traceback 反馈给 Orchestrator，触发重试机制。

3.5 🟣 Developer Agent (开发者智能体 - 核心升级)

角色: 类似于 OpenFOAMGPT Post-processing Agent，但能力更强 。


功能:

结果分析: 读取 results/ 下的 JSON/CSV 文件，计算 NSE 提升率（用于实验2）。

代码生成 (Code Gen): 针对 hydromodel 不支持的功能（实验3），编写全新的 Python 脚本。

工具执行: 在沙箱环境中运行生成的脚本。

# 4. 关键技术实现 (Key Technical Implementations)

这套技术栈的核心在于：如何让一个外部的 Python 程序像人类专家一样，通过读写文件和执行命令来操控 hydromodel。

4.1 外部配置协议与校验器 (Configuration Protocol & Validator)
对应实验: 实验 1 (通用性)

由于 Agent 生成的是文本，而 hydromodel 需要严格的 YAML，必须建立中间层来确保生成的配置不会导致程序崩溃。

目的: 确保 Config Agent 输出的 YAML 文件严格符合 hydromodel 的 API 要求，避免“幻觉”参数。

实现:

Schema 定义: 基于 hydromodel 的 configs/example_config.yaml 建立 JSON Schema。明确规定：

model_name 枚举值: ["xaj", "xaj_mz", "gr4j"]。

algorithm_name 枚举值: ["SCE_UA", "GA", "scipy"]。

train_period: 必须是 ["YYYY-MM-DD", "YYYY-MM-DD"] 格式列表。

Pre-flight Check (预检机制): 在调用 calibrate() 之前，Wrapper 先运行一个轻量级校验脚本。如果 Schema 校验失败，直接反馈给 Agent 重写，而不去打扰底层的 hydromodel。

4.2 智能结果分析中间件 (Intelligent Result Middleware)
对应实验: 实验 2 (参数自适应)

LLM 无法直接“看”懂数万行的 CSV 历史文件，需要一个中间件将数据转化为“洞察”。

目的: 从结果文件中诊断模型表现，特别是识别参数边界效应（Boundary Effect）。

实现: 编写 ResultAnalyzer 类。

读取: 解析 results/{exp_name}/{basin_id}_sceua.csv 或 calibration_results.json。

诊断算法:

收敛性判断: 计算 CSV 后 10% 数据的方差，判断是否收敛。

边界触碰检测: 读取 param_range.yaml（参数范围），对比最优参数（Best Params）。如果某参数（如 K）的最优值距离上界或下界小于 1%，则标记为 Warning: Boundary Hit。

输出给 Agent: 生成一段简短摘要，例如："NSE=0.75。警告：参数 'K' 触碰上界 (1.0)，建议扩大搜索范围。参数 'B' 收敛良好。"

4.3 动态文件注入与覆写 (Dynamic File Injection)
对应实验: 实验 2 (参数自适应)

这是实现“自适应优化”的核心。hydromodel 默认读取静态配置，Wrapper 必须具备动态修改能力。

目的: 让 Agent 能够物理修改硬盘上的 param_range.yaml，并强制 hydromodel 使用新范围。

实现:

范围解析器: Agent 需要能读取 YAML 格式的参数范围文件。

注入逻辑:

Config Agent 接收到 ResultAnalyzer 的建议（如“扩大 K 范围”）。

计算新的上下界（例如：new_upper = old_upper * 1.2）。

生成新的文件 workspace/{exp_id}/param_range_refined.yaml。

关键点: 在生成的 config.yaml 中，显式设置 training_cfgs 的相关参数（如果 hydromodel 支持）或者覆盖默认路径下的 param_range.yaml。

4.5 异常拦截与反馈回路 (Error Interception Loop)
对应实验: 实验 1 & 3 (通用性与纠错)

作为 External Wrapper，必须能看懂 hydromodel 的崩溃信息。

目的: 将 Python 的 Traceback 转化为自然语言反馈，指导 Agent 自我修复。

实现:

日志捕获: 在调用 hydromodel 时，使用 try...except 块（如果是 API 调用）或 subprocess.stderr（如果是命令行调用）。

语义映射: 建立常见错误映射表（RAG 的一部分）。

错误: KeyError: 'prec' -> 提示: "变量名错误，hydromodel 中降雨变量通常为 'prcp' 或 'precipitation'"。

错误: FileNotFoundError -> 提示: "数据路径配置错误，请检查 datasets-origin 设置"。

4.6 知识库与工具提示词 (Knowledge Base & Tool Prompts)
全实验通用

内容更新:

API 文档: 索引 hydromodel 的 calibrate, evaluate 函数签名。

数据结构说明: 明确说明 calibration_results.json 的 JSON 结构和 _sceua.csv 的列名结构，这对实验 2 和 3 至关重要。

Few-Shot Examples: 增加“多轮优化”的对话范例，让 Agent 理解如何根据反馈修改配置。