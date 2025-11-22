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

### Architecture

All agents now support dynamic prompt management:

```
Final Prompt = Static Template + Schema/Context + Dynamic Feedback
```

### Prompt Files Location

```
hydroagent/resources/
├── algorithm_params_schema.txt    # IntentAgent: Algorithm parameter mappings
├── config_agent_prompt.txt        # ConfigAgent: Configuration generation guide
├── runner_agent_prompt.txt        # RunnerAgent: Execution workflow documentation
└── developer_agent_prompt.txt     # DeveloperAgent: Analysis guidelines
```

### Usage in Agents

```python
# IntentAgent
self.prompt_manager = PromptManager()
self.prompt_manager.register_static_prompt("IntentAgent", prompt_text)
self.prompt_manager.load_schema("algorithm_params")

# DeveloperAgent
self.prompt_manager = PromptManager()
prompt_text = self._load_prompt_from_file("developer_agent_prompt.txt")
self.prompt_manager.register_static_prompt("DeveloperAgent", prompt_text)
```

**Benefits**:
- ✅ Centralized prompt management
- ✅ Version control for prompts
- ✅ Easy A/B testing
- ✅ Multi-language support ready

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

1. Create agent file in `hydroagent/agents/`
2. Inherit from `BaseAgent`
3. Implement `process()` method
4. Create prompt file in `resources/` (optional)
5. Integrate into pipeline script

```python
from hydroagent.core.base_agent import BaseAgent

class MyAgent(BaseAgent):
    def process(self, input_data):
        # Implementation
        return result
```

### Adding Algorithm Parameter Recognition

1. Edit `hydroagent/resources/algorithm_params_schema.txt`
2. Add algorithm section with parameter mappings
3. Include Chinese keywords

```
## My_Algorithm
Parameters:
- **my_param** (int): Description
  - User keywords: "关键词1", "关键词2", "keyword"
  - Example: "迭代100次" → my_param=100
```

### Modifying Global Defaults

Edit `configs/config.py`:

```python
# Change default training period
DEFAULT_TRAIN_PERIOD = ["1990-01-01", "2000-12-31"]

# Change SCE-UA defaults
DEFAULT_SCE_UA_PARAMS = {
    "rep": 2000,  # Increase iterations
    "ngs": 500,   # Increase complexes
    ...
}

# Change quality thresholds
NSE_EXCELLENT = 0.80  # Stricter threshold
```

### Customizing Output Filtering

Edit `hydroagent/agents/runner_agent.py`:

```python
filter_patterns = [
    "🚀 =====",       # Filter decorative lines
    "📋 Parameters",  # Filter parameter details
    # Add more patterns...
]
```

**Note**: Progress bars (`SCE-UA Progress:`) always display (uses `\r`)

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

## 🚧 Future Development

### Planned Features

- [ ] **RAG Integration**: Knowledge-enhanced workflow generation
- [ ] **Web Interface**: Gradio/Streamlit UI
- [ ] **Visualization**: Interactive result plots
- [ ] **Multi-Basin Parallel**: Process multiple basins simultaneously
- [ ] **Model Comparison**: Compare performance across models
- [ ] **Parameter Sensitivity**: Analyze parameter importance
- [ ] **Docker Deployment**: Containerized distribution

### Experimental Features (in `config.py`)

```python
ENABLE_RAG = False              # RAG knowledge system
ENABLE_VISUALIZATION = False    # Result visualization
ENABLE_PARALLEL_BASINS = False  # Multi-basin processing
```

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

**Last Updated**: 2024-11-22

**Architecture Version**: 4-Agent Pipeline v1.0
