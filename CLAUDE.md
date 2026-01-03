# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

**Version**: v6.0 (2026-01-02)
**Architecture**: Orchestrator v5.0 + **Unified Tool Chain Execution** (Legacy Removed)

## 🚀 Latest Updates (v6.0 - Architecture Unification)

**Major Change**: 完全移除 Legacy 模式，所有任务统一使用工具链执行

**Key Changes**:
- ✅ **Phase 1**: 移除 TaskPlanner 和 RunnerAgent 的路由逻辑，强制使用工具系统
- ✅ **Phase 2**: 多模型组合支持 - TaskPlanner 生成多个 tool_chain subtasks，Orchestrator 循环执行
- ✅ **Phase 3**: 清理 Legacy 代码 - 重命名所有 Legacy 方法为 `*_DEPRECATED`，标记为废弃
- ✅ **统一架构**: 上层（Orchestrator）决定循环，下层（RunnerAgent）统一用工具链执行
- ✅ **覆盖所有查询**: 不仅多模型查询，所有查询都使用新架构
- ⚠️ **InterpreterAgent 保留**: 仍用于多组合任务的 config 生成

**Modified Files (Phase 1, 2 & 3)**:
- `hydroagent/agents/task_planner.py`:
  - L171-211: 移除路由，强制 `_process_with_tools()`
  - L1126-1201: 多模型组合生成 tool_chain subtasks
  - L213-217: 标记 Legacy decomposition 方法为 DEPRECATED
- `hydroagent/agents/runner_agent.py`:
  - L321-323: 移除路由，强制 `_process_with_tools()`
  - L325-329: 添加 DEPRECATED 标记
  - L331-468: `_process_legacy` 重命名为 `_process_legacy_DEPRECATED`
  - L470-1629: 所有 Legacy 方法重命名为 `*_DEPRECATED`
- `hydroagent/agents/orchestrator.py`:
  - L987-1075: 添加循环执行多 tool_chain subtasks 的逻辑
  - L342-347: 注释说明 InterpreterAgent 仍需保留
- `configs/config.py` (L254): `USE_TOOL_SYSTEM = True` (默认启用)

---

## 🌊 Project Overview

**HydroAgent** is an intelligent multi-agent system for hydrological model calibration and evaluation. The system uses **5 specialized agents** coordinated by an **Orchestrator** with a state machine to transform natural language queries into complete model calibration workflows.

### Architecture: Orchestrator v5.0 + Unified Tool Chain (v6.0)

```
                        ┌─────────────────────────────┐
                        │   Orchestrator (v5.0)       │
                        │   State Machine Driven      │
                        │   + Loop Controller (v6.0)  │
                        └─────────────────────────────┘
                                     ↓
        ┌────────────────────────────┴────────────────────────────┐
        │                                                          │
        ↓                                                          ↓
   User Query                                                 Execution
(中文/English)                                                  Context
        ↓                                                          ↓
   IntentAgent ──────────────────────────────────────────────────→│
   (意图识别)                                                      │
        ↓                                                          │
   TaskPlanner (v6.0) ───────────────────────────────────────────→│
   (任务规划 - 统一工具链)                                         │
        │                                                          │
        ├───────── Single Task ──────────────────────────────────┤
        │          1 tool_chain                                   │
        │          ↓                                              │
        │    ToolOrchestrator → RunnerAgent (1 call)             │
        │                                                          │
        └───────── Multi-Combination (NEW v6.0) ─────────────────┤
                   N tool_chain subtasks                          │
                   (models × basins × algorithms)                 │
                   ↓                                              │
             Orchestrator LOOP (v6.0):                            │
               For each subtask:                                  │
                 → InterpreterAgent (配置生成)                    │
                 → RunnerAgent (tool_chain 执行)                  │
                 → DeveloperAgent (分析)                          │
               Next subtask...                                    │
                                                                  │
                                    ↓                             │
                            DeveloperAgent ←─────────────────────┘
                            (统一后处理分析)
                                    ↓
                          Analysis Report + Results
                          (analysis_report.md)
```

**Current Status**: ✅ Orchestrator v5.0 State Machine | ✅ **Unified Tool Chain (v6.0)** | ✅ Multi-Combination Loop Support

### 🔧 Unified Tool Chain Execution (v6.0)

**HydroAgent v6.0 所有任务统一使用工具链执行（Legacy 模式已完全移除）**

#### Scenario 1: Single Task (单任务 - 单模型×单流域)

**适用场景**:
- ✅ 1个模型 × 1个流域 × 1个算法
- ✅ 简单顺序执行 (simple mode)
- ✅ 迭代优化 (iterative mode)
- ✅ 重复实验 (repeated mode)

**执行流程** (一次性执行):
```
TaskPlanner (v6.0)
    ↓ 调用 _process_with_tools()
ToolOrchestrator (生成工具链)
    ↓ tool_chain = [validate, calibrate, evaluate, visualize]
    ↓ execution_mode = "simple" / "iterative" / "repeated"
    ↓ 返回 {tool_chain, execution_mode, mode_params}
Orchestrator
    ↓ GENERATING_CONFIG → 生成 config
    ↓ EXECUTING_TASK → 调用 RunnerAgent.process(tool_chain)
RunnerAgent (v6.0 - 统一工具链执行)
    ↓ _process_with_tools()
    ↓ tool_executor.execute_chain(tool_chain)
    ↓ 返回 tool_output = {tool_results: [...], aggregated_data: {...}}
DeveloperAgent
    ↓ _analyze_tool_system_output(tool_output)
    ↓ 生成 analysis_report.md ✅
```

#### Scenario 2: Multi-Combination (多模型组合 - NEW v6.0)

**适用场景**:
- ✅ M个模型 × N个流域 × K个算法 (M×N×K > 1)
- ✅ 例如：2个模型 × 2个流域 × 1个算法 = 4个组合

**执行流程** (Orchestrator 循环执行):
```
TaskPlanner (v6.0)
    ↓ 检测到多组合: M×N×K > 1
    ↓ 为每个组合生成独立的 tool_chain subtask
    ↓ 返回 {task_plan: {subtasks: [
           {task_id: "task_1", tool_chain: [...], intent_result: {...}},
           {task_id: "task_2", tool_chain: [...], intent_result: {...}},
           ...
        ], use_tool_chains: True}}
Orchestrator (v6.0 - Loop Controller)
    ↓ GENERATING_CONFIG → 检测到 use_tool_chains=True
    ↓ 提取下一个待执行的 subtask (task_1)
    ↓ 为 subtask 生成 config (InterpreterAgent)
    ↓ EXECUTING_TASK → RunnerAgent.process(subtask.tool_chain)
    ↓ ANALYZING_RESULTS → DeveloperAgent 分析
    ↓ 检查是否还有未完成的 subtasks (task_2, task_3, ...)
    ↓ 如果有 → 循环回 GENERATING_CONFIG，处理下一个 subtask
    ↓ 如果无 → 完成，生成最终 analysis_report.md ✅
RunnerAgent (v6.0)
    ↓ 每个 subtask 都通过 _process_with_tools() 执行
    ↓ 统一使用工具链，无 Legacy 路径
```

**Key Difference (v6.0 vs v5.1)**:
- ❌ v5.1: 多模型组合 → 回退到 Legacy 路径 (InterpreterAgent 逐个执行)
- ✅ v6.0: 多模型组合 → 生成多个 tool_chain subtasks，Orchestrator 循环执行
- ✅ v6.0: **所有路径都使用工具链**，无 Legacy 路由
```

**关键特征 (v6.0)**:
- **统一执行方式**：所有任务都使用工具链，无 Legacy 路径
- **灵活循环控制**：单任务一次执行，多组合 Orchestrator 循环执行
- **模式支持**：simple/iterative/repeated 模式在工具链内部处理

#### 🔑 v6.0 架构优势

| 特性 | v5.1 (双路径) | v6.0 (统一工具链) |
|------|--------------|------------------|
| **执行方式** | 工具系统 + Legacy 双路径 | ✅ 统一工具链 |
| **多模型组合支持** | ❌ 回退到 Legacy | ✅ 生成多个 tool_chain subtasks |
| **Orchestrator循环** | ⚠️ 仅用于 Legacy | ✅ 用于所有多组合任务 |
| **RunnerAgent** | `_process_with_tools()` + `_process_legacy()` | ✅ 仅 `_process_with_tools()` |
| **代码复杂度** | 高（双路径维护） | ✅ 低（单一执行路径） |
| **架构清晰度** | 中等 | ✅ 高（上层循环，下层统一执行） |

**本质改进**：
- ❌ v5.1: "两种执行方式（工具链 vs Legacy），根据任务选择"
- ✅ v6.0: **"统一工具链执行，上层决定循环次数"**

#### 🆕 Design Philosophy (v6.0)

**设计原则**:
1. **下层统一**：RunnerAgent 只用工具链执行（`_process_with_tools()`）
2. **上层决策**：Orchestrator 决定循环逻辑（单次 vs. 多次）
3. **移除冗余**：删除 Legacy 路径路由（未来 Phase 3 将删除 Legacy 代码）
4. **保证覆盖**：所有查询（不只多模型）都用统一架构

**用户反馈驱动的改进**:
- 用户质疑："为什么不能在顶层多次调用工具系统？"
- v6.0 回答：**完全可以！Orchestrator 循环调用 RunnerAgent，每次执行一个 tool_chain**
- 结果：架构更清晰，职责明确，代码简洁

#### Tool-Based Execution Flow Details

```
User Query → IntentAgent → TaskPlanner → ToolOrchestrator
                                              ↓
                                   Generate Tool Chain
                                   + Execution Mode
                                              ↓
                            RunnerAgent (Tool Executor)
                                              ↓
                        Execute Tools: validate → calibrate
                                    → evaluate → visualize
                                              ↓
                                      DeveloperAgent
                                              ↓
                                  Analysis Report + Results
```

#### 9 Core Tools

| Tool | Category | Responsibility |
|------|----------|----------------|
| **DataValidationTool** | VALIDATION | Validate basin IDs, time ranges, variables |
| **CalibrationTool** | CALIBRATION | Model parameter calibration (decoupled) |
| **EvaluationTool** | EVALUATION | Model performance evaluation |
| **SimulationTool** | SIMULATION | Run model predictions with given parameters |
| **VisualizationTool** | VISUALIZATION | Generate plots and charts |
| **CodeGenerationTool** | ANALYSIS | Generate custom analysis code |
| **CustomAnalysisTool** | ANALYSIS | LLM-assisted custom tasks |

#### 3 Execution Modes

- **simple**: Sequential one-time execution
- **iterative**: Loop until NSE threshold or max iterations
- **repeated**: Repeat N times for stability analysis

#### Tool System Status

- ✅ **Phase 1**: Core infrastructure (base_tool, registry, executor)
- ✅ **Phase 2**: All tools migrated + default enabled (`USE_TOOL_SYSTEM=True`)
- 🚧 **Phase 3**: Multi-model combination support (planned)

**See `docs/TOOL_SYSTEM_GUIDE.md` for detailed usage.**

---

## 🚧 Phase 3 Roadmap: Multi-Model Combination Support

### Current Limitation

**工具系统当前的核心限制**：一个 `tool_chain` 只能处理**一组配置**

```python
# 当前工具系统可以处理：
tool_chain = [validate, calibrate, evaluate, visualize]
config = {
    "model_name": "GR4J",           # 单个模型
    "basin_ids": ["01013500", "11532500"],  # 多个流域 ✅
    "algorithm": "SCE_UA"           # 单个算法
}
# 执行：GR4J 率定 2 个流域（批量处理）
```

**工具系统当前无法处理**：
```python
# 需求：2个模型 × 2个流域 = 4个组合
models = ["GR4J", "XAJ"]
basins = ["01013500", "11532500"]

# 期望执行：
# 1. GR4J + 01013500
# 2. GR4J + 11532500
# 3. XAJ + 01013500
# 4. XAJ + 11532500

# 问题：CalibrationTool 的 config 只接受单个 model_name
# 无法在一个 tool_chain 里完成所有组合
```

### Why Legacy Path Still Needed?

**Legacy 路径的优势**：
- 将多模型组合**拆解成 N 个独立 subtasks**
- 每个 subtask 独立生成 config（单模型 + 单/多流域）
- Orchestrator 循环执行 N 次，每次处理一个组合

```python
# Legacy 拆解：
subtasks = [
    {task_id: "task_1", model: "GR4J", basins: ["01013500"]},
    {task_id: "task_2", model: "GR4J", basins: ["11532500"]},
    {task_id: "task_3", model: "XAJ", basins: ["01013500"]},
    {task_id: "task_4", model: "XAJ", basins: ["11532500"]},
]
# 每个 subtask 生成独立配置，RunnerAgent 执行 4 次
```

### Phase 3 Solution Options

**有三种可能的解决方案：**

#### 方案 A：工具级别支持多模型（推荐）

**核心思路**：让 `CalibrationTool` 原生支持 `model_names`（多个模型）

```python
# 增强后的 CalibrationTool
config = {
    "model_names": ["GR4J", "XAJ"],  # 🆕 支持多个模型
    "basin_ids": ["01013500", "11532500"],
    "algorithm": "SCE_UA"
}

# CalibrationTool 内部循环：
for model in model_names:
    for basin in basin_ids:
        calibrate(model, basin, algorithm)
        # 保存结果到 results[model][basin]
```

**优点**：
- ✅ 工具系统完全替代 Legacy 路径
- ✅ 统一的 `tool_output` 格式
- ✅ 用户透明，体验一致

**缺点**：
- ⚠️ CalibrationTool 逻辑变复杂
- ⚠️ 需要重构结果聚合逻辑

#### 方案 B：执行器级别支持组合模式

**核心思路**：引入新的执行模式 `combination_mode`

```python
# TaskPlanner 生成：
{
    "tool_chain": [validate, calibrate, evaluate, visualize],
    "execution_mode": "combination",  # 🆕 新模式
    "combinations": [
        {"model": "GR4J", "basins": ["01013500"]},
        {"model": "GR4J", "basins": ["11532500"]},
        {"model": "XAJ", "basins": ["01013500"]},
        {"model": "XAJ", "basins": ["11532500"]},
    ]
}

# ToolExecutor 执行：
for combo in combinations:
    config = generate_config(combo)
    execute_chain(tool_chain, config)
    results.append(result)
```

**优点**：
- ✅ 工具逻辑不变（向后兼容）
- ✅ 执行器负责组合管理

**缺点**：
- ⚠️ 类似 Legacy 循环执行，没有本质优化
- ⚠️ 执行器逻辑变复杂

#### 方案 C：引入 MultiModelTool

**核心思路**：创建专门的 `MultiModelCalibrationTool`

```python
# 专门处理多模型组合的工具
tool_chain = [
    validate,
    multi_model_calibrate,  # 🆕 新工具
    multi_model_evaluate,   # 🆕 新工具
    visualize
]
```

**优点**：
- ✅ 职责分离，单一工具保持简单

**缺点**：
- ⚠️ 工具数量增加，维护成本高
- ⚠️ 与现有工具重复

### 🎯 推荐方案

**Phase 3 推荐采用方案 A**：

1. **扩展 CalibrationTool**：
   - 支持 `model_names`（列表）
   - 内部循环处理多模型
   - 统一输出格式

2. **扩展 EvaluationTool** 同理

3. **ToolOrchestrator 增强**：
   - 检测多模型意图
   - 自动生成支持多模型的 config

4. **完全移除 Legacy 路径**：
   - 所有任务都通过工具系统
   - InterpreterAgent 可以退役
   - 简化 Orchestrator 状态机

### 迁移时间线（预估）

- **Phase 3.1** (Q1 2026): CalibrationTool 支持多模型
- **Phase 3.2** (Q2 2026): EvaluationTool 支持多模型
- **Phase 3.3** (Q2 2026): 移除 Legacy 路径，InterpreterAgent 退役
- **Phase 3.4** (Q3 2026): LLM-assisted orchestration（智能工具链生成）

---

## 🚀 Quick Start

### Environment Setup

```bash
# Install uv package manager
pip install uv

# Sync dependencies
uv sync

# Activate virtual environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac
```

### Running the System

```bash
# Interactive mode with API backend (recommended)
python scripts/run_developer_agent_pipeline.py --backend api

# Single query mode
python scripts/run_developer_agent_pipeline.py --backend api "率定GR4J模型，流域01013500"

# Using Ollama local model
python scripts/run_developer_agent_pipeline.py --backend ollama
```

---

## 📂 Project Structure

### Core Package: `hydroagent/`

```
hydroagent/
├── core/                      # Base classes and interfaces
│   ├── base_agent.py         # BaseAgent abstract class
│   └── llm_interface.py      # LLM API wrappers (OpenAI/Ollama)
├── agents/                    # Specialized Agents
│   ├── intent_agent.py       # NLU and intent recognition
│   ├── task_planner.py       # Task planning and decomposition
│   ├── runner_agent.py       # Model execution (tool executor)
│   ├── developer_agent.py    # Result analysis
│   └── tool_orchestrator.py  # Tool chain orchestration (NEW)
├── tools/                     # Tool System (NEW - Phase 2)
│   ├── base_tool.py          # BaseTool abstract class
│   ├── registry.py           # Tool registry
│   ├── executor.py           # Tool executor with reference resolution
│   ├── validation_tool.py    # Data validation
│   ├── calibration_tool.py   # Model calibration
│   ├── evaluation_tool.py    # Model evaluation
│   ├── simulation_tool.py    # Model simulation
│   ├── visualization_tool.py # Visualization
│   ├── code_generation_tool.py  # Code generation
│   └── custom_analysis_tool.py  # Custom analysis
├── utils/                     # Utility modules
│   ├── prompt_manager.py     # Dynamic prompt management
│   ├── basin_validator.py    # Basin data validation (extended)
│   └── validation_handler.py # Validation failure handling
└── resources/                 # Static resources
    ├── algorithm_params_schema.txt
    ├── config_agent_prompt.txt
    ├── runner_agent_prompt.txt
    └── developer_agent_prompt.txt
```

### Configuration: `configs/`

```
configs/
├── definitions.py             # Public config template (paths, API)
├── definitions_private.py     # Private config (API keys, local paths)
├── example_definitions_private.py  # Template for new users
└── config.py                  # Global parameters (LLM, algorithms, thresholds)
```

### Scripts: `scripts/`

```
scripts/
├── run_developer_agent_pipeline.py  # Main entry point (4-Agent pipeline)
├── run_agent.py                     # Alternative entry (expandable)
└── *.py                             # Utility scripts
```

### Tests: `test/`

```
test/
├── test_intent_agent.py
├── test_config_agent.py
├── test_developer_agent_pipeline.py
└── test_unified_tools.py
```

---

## 🧠 Agent Responsibilities

### 1. IntentAgent (意图智能体)

**Purpose**: Natural language understanding and intent extraction

**Input**: User query in Chinese/English
```
"率定GR4J模型，流域01013500, 使用SCE-UA算法，算法迭代只需要500轮就行"
```

**Output**: Structured intent
```python
{
    "intent": "calibration",
    "model": "gr4j",
    "basin": "01013500",
    "algorithm": "SCE_UA",
    "extra_params": {"rep": 500},
    "confidence": 0.95
}
```

**Features**:
- ✅ Dynamic prompt system with algorithm parameter schema
- ✅ Context-aware prompt generation
- ✅ Supports Chinese keywords (迭代500轮 → rep=500)

---

### 2. ConfigAgent (配置智能体)

**Purpose**: Generate hydromodel-compatible configuration dictionaries

**Input**: Intent result from IntentAgent

**Output**: Complete config dictionary
```python
{
    "data_cfgs": {
        "basin_ids": ["01013500"],
        "train_period": ["1985-10-01", "1995-09-30"],
        "test_period": ["2005-10-01", "2014-09-30"],
        ...
    },
    "model_cfgs": {...},
    "training_cfgs": {...}
}
```

**Features**:
- ✅ Uses defaults from `configs/config.py`
- ✅ Applies user-specified parameters
- ✅ Adjusts algorithm complexity based on model type
- ❌ Currently rule-based (no LLM)

---

### 3. RunnerAgent (执行智能体)

**Purpose**: Execute hydromodel calibration, evaluation, and simulation

**Modes**:
1. **Calibrate**: Run parameter optimization
2. **Evaluate**: Calculate metrics on test period
3. **Simulate**: Generate predictions

**Key Features**:
- ✅ Auto-evaluation after calibration
- ✅ Intelligent output filtering (progress bars only, hide emojis/tables)
- ✅ Structured result parsing from files
- ✅ Complete logging to `logs/` directory
- ❌ Currently deterministic (no LLM)

**Output Management**:
```
Terminal: SCE-UA Progress: 100%|███████| 500/500 [02:15<00:00]
Logs:     All hydromodel output (complete record)
Results:  calibration_results.json, basins_metrics.csv, *.nc
```

---

### 4. DeveloperAgent (分析智能体 - 统一后处理)

**Purpose**: 统一的结果分析和报告生成智能体（无论执行路径）

**Critical Role**:
- **唯一负责生成最终 `analysis_report.md` 的智能体**
- 处理**两种执行路径**的输出：工具系统 (`tool_output`) 和 Legacy (`subtask_results`)
- 保证用户始终得到专业的 Markdown 分析报告

**Input Types**:
1. **Tool System Path**: `tool_output` (包含 `tool_results`, `aggregated_data`)
2. **Legacy Path**: `orchestrator_output` (包含 `subtask_results`, `task_plan`)

**Output**:
1. **Terminal Summary** (文本分析)
```
📊 质量评估: 良好 (Good)
   NSE=0.68, RMSE=1.45

🔧 最优参数: 4 个
   x1=0.77, x2=0.0002, x3=0.30, x4=0.70

💡 改进建议:
  1. 模型性能合理，接近良好水平
  2. 可考虑延长训练期或增加迭代轮数进一步优化
  3. 建议在更多流域验证参数迁移性
```

2. **Session Report** (`analysis_report.md`) - **LLM 生成的专业报告**
   - 执行概述、任务详情、性能指标
   - 批量任务的流域对比分析
   - 改进建议和后续步骤
   - 文件路径清单

**Key Methods**:
- `_analyze_tool_system_output()`: 处理工具系统路径 → 生成报告 ✅
- `_analyze_orchestrator_output()`: 处理 Legacy 路径 → 生成报告 ✅ (v5.1修复)
- `_generate_session_report()`: 统一的报告生成逻辑（支持两种路径）

**Features**:
- ✅ **Unified Post-Processing**: 无论哪种执行路径，都生成统一格式的报告
- ✅ Dynamic prompt system
- ✅ NSE quality thresholds (from `config.py`)
- ✅ Batch processing support (多流域、多模型汇总分析)
- ✅ **Code generation capability** (实验4)
- ✅ **Dual-LLM mode** (通用模型+代码专用模型)

#### 🆕 Code Generation (实验4)

**Purpose**: Generate Python scripts for custom analysis tasks beyond hydromodel's native features

**Dual-LLM Architecture**:
```
IntentAgent (通用LLM) → 识别需要代码生成
    ↓
DeveloperAgent:
  - 思考分析: 使用通用LLM (qwen-turbo, qwen3:8b)
  - 代码生成: 使用代码专用LLM (qwen-coder-turbo, deepseek-coder:6.7b)
```

**Supported Tasks**:
- ✅ 径流系数计算 (Runoff Coefficient)
- ✅ 流量历时曲线 (Flow Duration Curve, FDC)
- ✅ 自定义水文指标分析
- ✅ 数据可视化脚本

**Key Points**:
- API模式: `qwen-turbo` (通用) + `qwen-coder-turbo` (代码生成)
- Ollama模式: `qwen3:8b` + `deepseek-coder:6.7b`
- 生成完整可运行的Python脚本（type hints、注释、错误处理）
- 结果自动保存到`generated_code/`目录

**示例**: "率定完成后，请帮我计算流域的径流系数，并画FDC曲线" → 生成 `runoff_coefficient_analysis.py` 和 `plot_fdc.py`

---

## ⚙️ Configuration Management

### Configuration File Hierarchy

**Priority Order** (highest to lowest):
1. `configs/definitions_private.py` - User-specific (API keys, paths)
2. `configs/definitions.py` - Project defaults
3. `configs/config.py` - Adjustable parameters
4. Environment variables
5. Hard-coded defaults

### Configuration Files

#### `definitions_private.py` (User-Specific, Not in Git)

```python
# Paths
PROJECT_DIR = r"D:\your\path\to\HydroAgent"
RESULT_DIR = r"D:\your\path\to\results"
DATASET_DIR = r"D:\your\path\to\data"

# LLM API
OPENAI_API_KEY = "sk-your-qwen-api-key"
OPENAI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# Ollama (optional)
OLLAMA_BASE_URL = "http://localhost:11434"
```

#### `config.py` (Global Parameters)

```python
# LLM Settings
DEFAULT_MODEL = "qwen-turbo"
TEMPERATURE = 0.1

# Data Configuration
DEFAULT_TRAIN_PERIOD = ["1985-10-01", "1995-09-30"]
DEFAULT_TEST_PERIOD = ["2005-10-01", "2014-09-30"]
DEFAULT_WARMUP_DAYS = 365

# Algorithm Defaults
DEFAULT_SCE_UA_PARAMS = {
    "rep": 500,
    "ngs": 200,
    "kstop": 500,
    ...
}

# Performance Thresholds
NSE_EXCELLENT = 0.75
NSE_GOOD = 0.65
NSE_FAIR = 0.50
NSE_POOR = 0.35
```

### Standard Configuration Loading Pattern

```python
try:
    from configs import definitions_private
    API_KEY = definitions_private.OPENAI_API_KEY
    PROJECT_DIR = definitions_private.PROJECT_DIR
except ImportError:
    from configs import definitions
    API_KEY = definitions.OPENAI_API_KEY
    PROJECT_DIR = definitions.PROJECT_DIR
```

---

## 🎨 Dynamic Prompt System

Agents use dynamic prompt management: `Final Prompt = Static Template + Schema/Context + Dynamic Feedback`

**Prompt Files**: `hydroagent/resources/*.txt` (algorithm_params_schema, config_agent_prompt, runner_agent_prompt, developer_agent_prompt)

**Benefits**: Centralized management, version control, A/B testing, multi-language support

---

## 📝 Development Standards

### File Header (MANDATORY)

Every new Python file must include:

```python
"""
Author: [Your Name]
Date: [Creation Date YYYY-MM-DD HH:MM:SS]
LastEditTime: [Last Edit YYYY-MM-DD HH:MM:SS]
LastEditors: [Editor Name]
Description: [Brief description of file purpose]
FilePath: /HydroAgent/path/to/file.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""
```

### Directory Structure Rules

**CRITICAL**: Place files in correct directories:

| File Type | Directory | Example |
|-----------|-----------|---------|
| Agent implementations | `hydroagent/agents/` | `intent_agent.py` |
| Core base classes | `hydroagent/core/` | `base_agent.py` |
| Utility functions | `hydroagent/utils/` | `prompt_manager.py` |
| Static resources | `hydroagent/resources/` | `*.txt`, `*.yaml` |
| Configuration files | `configs/` | `config.py` |
| Entry point scripts | `scripts/` | `run_*.py` |
| Test files | `test/` | `test_*.py` |
| Examples | `examples/` | `simple_workflow_example.py` |

### Logging Standards

**Test Files**: All tests must save logs to `logs/` directory

```python
import logging
from datetime import datetime
from pathlib import Path

logs_dir = Path(__file__).parent.parent / "logs"
logs_dir.mkdir(exist_ok=True)

log_file = logs_dir / f"test_{test_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)
```

**Log File Naming**:
- Format: `test_{name}_{YYYYMMDD_HHMMSS}.log`
- Location: `logs/` directory
- **No timestamps**, use datetime format

---

## 🧪 Testing

### Running Tests

```bash
# Test IntentAgent
python test/test_intent_agent.py --backend api

# Test ConfigAgent
python test/test_config_agent.py

# Test complete pipeline
python test/test_developer_agent_pipeline.py

# Test unified tools
python test/test_unified_tools.py
```

### Test Coverage

- ✅ IntentAgent: Intent recognition, parameter extraction
- ✅ ConfigAgent: Configuration generation, validation
- ✅ RunnerAgent: Model execution, result parsing
- ✅ DeveloperAgent: Result analysis, recommendations
- ✅ Integration: Full 4-agent pipeline

---

## 🔧 Common Tasks

### Adding a New Agent

1. Create agent in `hydroagent/agents/`, inherit from `BaseAgent`, implement `process()`
2. Add prompt file in `resources/` (optional)
3. Integrate into pipeline script

### Adding Algorithm Parameter Recognition

Edit `hydroagent/resources/algorithm_params_schema.txt` - add algorithm section with parameter mappings and Chinese keywords

### Modifying Global Defaults

Edit `configs/config.py` - adjust DEFAULT_TRAIN_PERIOD, DEFAULT_SCE_UA_PARAMS, NSE_EXCELLENT thresholds, etc.

### Customizing Output Filtering

Edit `hydroagent/agents/runner_agent.py` - modify `filter_patterns` list to control terminal output

### Using Checkpoint/Resume for Long Tasks

For long-running multi-task experiments (e.g., batch calibration), use the checkpoint system:

```bash
# Start experiment
python scripts/run_with_checkpoint.py \
  --query "批量率定20个流域" \
  --backend api

# Interrupt with Ctrl+C (progress auto-saved)

# Resume from checkpoint
python scripts/run_with_checkpoint.py \
  --resume results/session_xxx \
  --backend api
```

**Key Features**:
- Auto-save after each subtask completion
- Skip completed tasks on resume
- Supports failure recovery

See `docs/CHECKPOINT_SYSTEM.md` for details.

---

## 📊 Supported Features

### Hydrological Models

- **GR Series**: GR1Y, GR2M, GR4J, GR5J, GR6J
- **XAJ**: Xinanjiang model
- **More**: Extensible through hydromodel

### Calibration Algorithms

| Algorithm | Parameters | Chinese Keywords |
|-----------|------------|------------------|
| **SCE-UA** | rep, ngs | 迭代轮数, 复合体数量 |
| **DE** | max_generations, pop_size | 代数, 种群大小 |
| **PSO** | max_iterations, swarm_size | 迭代次数, 粒子数 |
| **GA** | generations, population_size | 代数, 种群大小 |

### Performance Metrics

- **NSE**: Nash-Sutcliffe Efficiency
- **RMSE**: Root Mean Square Error
- **KGE**: Kling-Gupta Efficiency
- **PBIAS**: Percentage Bias
- **R²**: Coefficient of Determination

---

## 🧪 Running Experiments

HydroAgent提供了7个核心实验脚本，用于验证系统功能。所有实验脚本位于 `experiment/` 目录。

### 快速开始

```bash
# 运行所有实验（推荐）
python experiment/run_experiments.py all --backend api --mock

# 运行单个实验
python experiment/run_experiments.py 1 --backend api  # 实验1
python experiment/run_experiments.py 2b --backend api # 实验2B
python experiment/run_experiments.py 3 --backend api  # 实验3

# 使用独立脚本（所有7个实验都有对应的exp_*.py脚本）
python experiment/exp_1_standard_calibration.py --backend api --mock
python experiment/exp_2a_full_params.py --backend api --mock
python experiment/exp_2b_missing_info.py --backend api --mock
python experiment/exp_2c_custom_data.py --backend api --mock
python experiment/exp_3_iterative_optimization.py --backend api --mock
python experiment/exp_4_extended_analysis.py --backend api --mock
python experiment/exp_5_stability.py --backend api --mock
```

### 实验列表

| ID | 名称 | 查询 | 验证点 |
|----|------|------|--------|
| **1** | 标准流域验证 | "率定流域 01013500..." | task_type, 1个子任务 |
| **2a** | 全信息率定 | "使用SCE-UA, rep=500..." | 参数提取 |
| **2b** | 缺省信息补全 | "帮我率定流域..." | 信息自动补全 |
| **2c** | 自定义数据 | "用D盘my_data..." | 自定义数据路径 |
| **3** | 参数自适应优化 | "如果参数收敛到边界..." | 2阶段，依赖关系 |
| **4** | 扩展分析 | "计算径流系数，画FDC..." | 代码生成 |
| **5** | 稳定性验证 | "重复率定5次..." | 统计分析 |

详细说明见 `experiment/README.md`

---

## 🚧 Future Development

**Planned**: RAG integration, Web UI (Gradio/Streamlit), Interactive visualization, Multi-basin parallel processing, Model comparison, Parameter sensitivity analysis, Docker deployment

**Experimental flags in `config.py`**: ENABLE_RAG, ENABLE_VISUALIZATION, ENABLE_PARALLEL_BASINS

---

## 📚 Dependencies

### Core Dependencies

- **Python**: 3.11+
- **hydromodel**: Hydrological model library
- **hydrodataset**: CAMELS data management
- **hydroutils**: Utility functions
- **openai**: API client (for Qwen/OpenAI)

### Optional Dependencies

- **ollama**: Local model inference
- **gradio/streamlit**: Web UI (future)

### Installation

```bash
uv sync  # Install all dependencies
```

---

## 🔖 Checkpoint/Resume System (New!)

**Version**: v1.0 | **Date**: 2025-01-25

HydroAgent now supports **task interruption and recovery** for long-running experiments!

### Key Features

- ✅ **Safe Interruption**: Use Ctrl+C to stop at any time
- ✅ **Auto-Save**: Progress saved after each subtask
- ✅ **Smart Resume**: Only executes pending tasks
- ✅ **Cost Reduction**: Avoid restarting from scratch

### Architecture

```
hydroagent/core/checkpoint_manager.py  # Checkpoint管理器
hydroagent/agents/orchestrator.py     # 集成checkpoint支持
```

### Quick Start

```bash
# Run test
python test/test_checkpoint_resume.py

# Start experiment with checkpoint
python scripts/run_with_checkpoint.py \
  --query "重复率定5次" --backend api --mock

# Resume after interruption
python scripts/run_with_checkpoint.py \
  --resume results/session_xxx --backend api --mock
```

### Use Cases

1. **Multi-Basin Calibration**: 20+ basins, interrupt after 10, resume later
2. **Repeated Experiments**: 100 repetitions, pause at any point
3. **Model×Algorithm Matrix**: 12 combinations, resume from failure

### Implementation

The checkpoint system is **integrated into Orchestrator** (central coordinator), NOT in `experiment/BaseExperiment` (user-facing wrapper).

**Key Classes**:
- `CheckpointManager`: Core checkpoint logic
- `Orchestrator`: Integrates checkpoint in process() pipeline

**Checkpoint File** (`checkpoint.json`):
- Intent results
- Task plan with subtask status
- Config and results for each subtask
- Progress tracking

See `docs/CHECKPOINT_SYSTEM.md` for complete documentation.

---

## ❓ Troubleshooting

### IntentAgent Returns UNKNOWN

**Check**:
1. LLM backend connected? (check logs for `HTTP Request`)
2. API key correct in `definitions_private.py`?
3. Query includes model name, basin ID?

### Calibration Very Slow

**Solution**: Reduce iterations
```
率定GR4J模型，流域01013500，算法迭代100轮即可
```

### How to View Complete hydromodel Output?

**Answer**: Check log file `logs/run_developer_agent_pipeline_*.log`

### Evaluation Metrics Not Showing

**Check**:
1. `_parse_evaluation_result()` correctly extracts metrics
2. Calibration completed successfully
3. `calibration_results.json` exists

---

## 📖 Additional Resources

- **README.md**: User-facing documentation
- **hydromodel docs**: https://github.com/OuyangWenyu/hydromodel
- **Issue tracker**: GitHub Issues

---

## ✅ Development Checklist

When contributing code:

- [ ] Follow file header standard
- [ ] Place file in correct directory
- [ ] Update `config.py` if adding parameters
- [ ] Create/update prompt files for new agents
- [ ] Test with both API and Ollama backends
- [ ] Update CLAUDE.md if architecture changes
- [ ] Commit logs to understand changes

---

## 🚧 Architecture Evolution & Current Status

### Current Architecture (v5.1 - 2026-01-02)

**Major Update**: Unified Post-Processing across all execution paths

```
                        Orchestrator v5.0 (State Machine)
                                     ↓
                    ┌────────────────┴────────────────┐
                    │                                 │
              Tool System Path                  Legacy Path
                    │                                 │
             ToolOrchestrator                  Legacy Decomposition
                    │                                 │
              (Single tool_output)          (Multiple subtask_results)
                    │                                 │
                    └────────────┬────────────────────┘
                                 ↓
                         DeveloperAgent
                    (Unified Post-Processing)
                                 ↓
                         analysis_report.md
                    (Both paths generate report)
```

**System Status**:
- ✅ **Orchestrator v5.0**: State machine driven coordination
- ✅ **Dual Execution Paths**: Tool System (推荐) + Legacy (兼容)
- ✅ **Unified Post-Processing**: DeveloperAgent 统一处理两种路径 (v5.1 修复)
- ✅ **Tool System Phase 2**: 7 tools fully functional
- 🚧 **Tool System Phase 3**: Multi-model combinations support (planned)

**System Goals**: Support all calibration workflows with consistent user experience

**Design Philosophy**:
- **Execution Path Independence**: 工具系统只是 RunnerAgent 的执行方式，不应影响后处理
- **Unified User Experience**: 无论内部用哪种路径，用户都应得到专业的分析报告
- **Progressive Enhancement**: Legacy 路径保证向后兼容，工具系统逐步替代
- Strategic (Intent) → Tactical (Planning) → Configuration → Execution → **Analysis**

### 🆕 v5.1 Critical Fix (2026-01-02)

**Problem Discovered**:
```
Query 15: "对流域14325000,11532500使用GR4J和XAJ两个模型分别率定并对比性能"
├── TaskPlanner 检测到 2模型 × 2流域 = 4组合
├── 使用 Legacy Decomposition (工具系统不支持多模型组合)
├── 执行 4 个 subtasks，每个成功完成
├── DeveloperAgent 被调用 4 次，每次分析单个 RunnerAgent 输出
└── ❌ 没有生成最终的 analysis_report.md (设计缺陷)
```

**Root Cause**:
- `_analyze_tool_system_output()`: ✅ 生成报告
- `_analyze_orchestrator_output()`: ❌ 不生成报告（只在 v5.1 前）

**Solution** (`developer_agent.py:346-401`):
1. 在 `_analyze_orchestrator_output()` 中添加报告生成逻辑
2. 从 `subtask_results` 提取所有流域的 metrics
3. 构造统一的 `tool_output` 格式传给 `_generate_session_report()`
4. 确保 Legacy 路径也生成专业的 Markdown 报告

**Impact**:
- ✅ 所有批量任务（无论路径）现在都生成 `analysis_report.md`
- ✅ 多模型对比任务现在有完整的分析报告
- ✅ 用户体验统一，不会因为内部执行路径不同而缺失报告

**Verification**:
```bash
# Query 13 (工具系统路径): 3流域 × 1模型 → ✅ 有报告
# Query 15 (Legacy 路径):   2流域 × 2模型 → ✅ 现在也有报告
python test/test_exp_b_queries.py --query 15 --backend api --mock
```
- Clear separation of concerns between agents

**详细架构文档见**: `docs/ARCHITECTURE_FINAL.md`, `docs/TESTING_GUIDE.md`

---

**Last Updated**: 2026-01-02

**Architecture Version**: v5.1 (Orchestrator + Dual Paths + Unified Post-Processing)

**Previous Major Milestones**:
- v5.0 (2025-12): Orchestrator state machine + Tool system Phase 2
- v4.0 (2025-11): Dual-LLM code generation + Iterative optimization
- v3.5 (2025-01): 5-Agent pipeline + Base experiment framework

---

## 🚀 Future Development

### v4.0 Planned Enhancements

详细的v4.0改进计划（代码生成迁移、可视化绘图、自动迭代率定）见：
- `docs/v4.0_improvements_summary.md` - v4.0已实现的功能总结
- Architecture planning documents in `docs/` directory

### Other Planned Features

- [ ] **RAG Integration**: Knowledge-enhanced workflow generation
- [ ] **Web Interface**: Gradio/Streamlit UI
- [ ] **Multi-Basin Parallel**: Process multiple basins simultaneously
- [ ] **Model Comparison**: Compare performance across models
- [ ] **Parameter Sensitivity**: Analyze parameter importance
- [ ] **Docker Deployment**: Containerized distribution
