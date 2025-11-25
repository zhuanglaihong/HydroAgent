# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

---

## 🌊 Project Overview

**HydroAgent** is an intelligent multi-agent system for hydrological model calibration and evaluation. The system uses **4 specialized agents** working in pipeline to transform natural language queries into complete model calibration workflows.

### Architecture: 4-Agent Pipeline

```
User Query (中文/English)
      ↓
IntentAgent (意图识别)
      ↓
ConfigAgent (配置生成)
      ↓
RunnerAgent (模型执行)
      ↓
DeveloperAgent (结果分析)
      ↓
Analysis Report + Results
```

**Current Status**: ✅ Core 4-Agent system fully functional

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
├── agents/                    # 4 Specialized Agents
│   ├── intent_agent.py       # NLU and intent recognition
│   ├── config_agent.py       # Configuration generation
│   ├── runner_agent.py       # Model execution
│   └── developer_agent.py    # Result analysis
├── utils/                     # Utility modules
│   └── prompt_manager.py     # Dynamic prompt management
└── resources/                 # Static resources
    ├── algorithm_params_schema.txt
    ├── intent_agent_prompt.txt (planned)
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

### 4. DeveloperAgent (分析智能体)

**Purpose**: Analyze results and provide expert recommendations

**Input**: Execution results from RunnerAgent

**Output**: Analysis report
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

**Features**:
- ✅ Dynamic prompt system
- ✅ NSE quality thresholds (from `config.py`)
- ✅ Actionable recommendations
- ✅ Supports brief/normal/detailed analysis levels
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

## 🚧 Architecture Evolution

### Current Architecture (v3.5)

```
IntentAgent (战略决策) → TaskPlanner (战术拆解) → InterpreterAgent (配置生成)
    ↓                        ↓                          ↓
决定"要做什么"            拆解任务+生成提示词          LLM生成config
                                                        ↓
                                                   RunnerAgent → DeveloperAgent
```

**System Goals**: Support 5 core experiments (standard calibration, info completion, iterative optimization, code generation, stability validation)

**Status**: ✅ Core system fully functional (Phases 1-4 completed)

**Design Philosophy**:
- Experiment-driven, layered decision-making
- Strategic (Intent) → Tactical (Planning) → Configuration → Execution
- Clear separation of concerns between agents

**详细架构文档见**: `docs/ARCHITECTURE_FINAL.md`, `docs/TESTING_GUIDE.md`

---

**Last Updated**: 2025-01-23

**Architecture Version**: 5-Agent Pipeline v3.5 (All Experiments Ready)

### 🆕 Latest Updates (v3.5):
1. **实验脚本重构** (`experiment/base_experiment.py`)
   - 所有实验使用统一的BaseExperiment类
   - 自动使用实验名称作为输出目录（不再硬编码"exp1"）
   - 终端显示正确的实验名称

2. **自适应迭代优化** (实验3)
   - 动态range_scale调整（60% → 15%）
   - 智能停止条件（NSE达标、连续无改善、迭代上限）
   - 以最佳参数为中心缩小搜索范围
   - 自动生成参数范围YAML文件

3. **双LLM代码生成** (实验4)
   - 通用LLM（思考分析）+ 代码专用LLM（代码生成）
   - API模式：qwen-turbo + qwen-coder-turbo
   - Ollama模式：qwen3:8b + deepseek-coder:6.7b
   - 支持径流系数、FDC曲线等自定义分析

**Architecture**:
- IntentAgent (战略决策) → TaskPlanner (战术拆解) → InterpreterAgent (配置生成) → RunnerAgent (迭代执行) → DeveloperAgent (双LLM代码生成)

**Status**:
- ✅ 实验1-5核心功能完成
- ✅ 参数范围调整算法验证通过
- ✅ 代码生成框架就绪
- 📝 待验证：实验4的实际代码生成效果

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
