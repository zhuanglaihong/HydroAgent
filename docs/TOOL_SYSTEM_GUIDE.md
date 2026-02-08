# HydroAgent Tool System Guide
**Version**: 2.0 (Phase 2 Complete)
**Date**: 2025-12-24
**Status**: ✅ Production Ready

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Core Tools](#core-tools)
4. [Execution Modes](#execution-modes)
5. [Usage Guide](#usage-guide)
6. [Tool Development](#tool-development)
7. [Troubleshooting](#troubleshooting)

---

## Overview

### What is the Tool System?

The **HydroAgent Tool System** is a modular architecture that decouples complex hydrological modeling workflows into **independent, reusable tools**. This design provides:

- ✅ **Modularity**: Each tool has a single, well-defined responsibility
- ✅ **Flexibility**: Tools can be combined in different ways for different tasks
- ✅ **Maintainability**: Tools can be updated independently
- ✅ **Extensibility**: New tools can be added easily
- ✅ **Testability**: Each tool can be tested in isolation

### Phase 2 Completion Status

| Component | Status | Description |
|-----------|--------|-------------|
| **Core Infrastructure** | ✅ Complete | BaseTool, ToolRegistry, ToolExecutor |
| **Tool Migration** | ✅ Complete | All 9 core tools implemented |
| **Tool Orchestration** | ✅ Complete | ToolOrchestrator with 3 execution modes |
| **Integration** | ✅ Complete | Integrated into RunnerAgent |
| **Default Mode** | ✅ Enabled | `USE_TOOL_SYSTEM = True` |
| **Documentation** | ✅ Complete | This guide + updated CLAUDE.md |

---

## Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     HydroAgent Tool System                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐      ┌──────────────┐                    │
│  │ IntentAgent │─────▶│ TaskPlanner  │                    │
│  └─────────────┘      └──────┬───────┘                    │
│                               │                             │
│                               ▼                             │
│                    ┌──────────────────┐                    │
│                    │ ToolOrchestrator │                    │
│                    └────────┬─────────┘                    │
│                             │                               │
│              ┌──────────────┼──────────────┐              │
│              │              │              │              │
│         ┌────▼────┐    ┌───▼────┐    ┌───▼────┐         │
│         │ simple  │    │iterative│   │repeated│         │
│         │  mode   │    │  mode  │    │  mode  │         │
│         └────┬────┘    └───┬────┘    └───┬────┘         │
│              │              │              │              │
│              └──────────────┼──────────────┘              │
│                             ▼                               │
│                    ┌─────────────────┐                    │
│                    │  ToolExecutor   │                    │
│                    └────────┬────────┘                    │
│                             │                               │
│              ┌──────────────┼──────────────┐              │
│              ▼              ▼              ▼              │
│        ┌─────────┐    ┌─────────┐   ┌─────────┐         │
│        │validate │    │calibrate│   │evaluate │  etc.    │
│        └─────────┘    └─────────┘   └─────────┘         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Core Components

#### 1. BaseTool (Abstract Base Class)

**Location**: `hydroagent/tools/base_tool.py`

All tools inherit from `BaseTool` and implement:

```python
class BaseTool(ABC):
    @abstractmethod
    def execute(self, inputs: Dict[str, Any]) -> ToolResult:
        """Execute the tool's core logic"""
        pass

    def validate_inputs(self, inputs: Dict[str, Any]) -> tuple[bool, str]:
        """Validate input parameters"""
        pass

    @abstractmethod
    def _define_metadata(self) -> ToolMetadata:
        """Define tool metadata (name, description, schema)"""
        pass
```

#### 2. ToolRegistry (Tool Management)

**Location**: `hydroagent/tools/registry.py`

The registry manages all available tools:

```python
# Register a tool
from hydroagent.tools.registry import registry
registry.register(CalibrationTool())

# Get a tool
tool = registry.get_tool("calibrate")

# List all tools
tools = registry.list_tools()  # or by category
tools = registry.list_tools(category=ToolCategory.CALIBRATION)
```

#### 3. ToolExecutor (Execution Engine)

**Location**: `hydroagent/tools/executor.py`

The executor runs tool chains:

```python
from hydroagent.tools.executor import ToolExecutor

executor = ToolExecutor(registry)

# Execute a single tool
result = executor.execute_tool("calibrate", inputs)

# Execute a tool chain
tool_chain = [
    {"tool": "validate_data", "inputs": {...}},
    {"tool": "calibrate", "inputs": {...}},
    {"tool": "evaluate", "inputs": {"calibration_dir": "${calibrate.calibration_dir}"}}
]

results = executor.execute_chain(tool_chain)
```

**Key Features**:
- ✅ Parameter reference resolution (e.g., `${calibrate.calibration_dir}`)
- ✅ Input validation before execution
- ✅ Error handling and logging
- ✅ Optional result caching

#### 4. ToolOrchestrator (Workflow Generator)

**Location**: `hydroagent/agents/tool_orchestrator.py`

Generates tool chains based on task type:

```python
from hydroagent.agents.tool_orchestrator import ToolOrchestrator

orchestrator = ToolOrchestrator()

# Generate tool chain for standard calibration
tool_chain_info = orchestrator.generate_tool_chain(
    task_type="standard_calibration",
    intent_result={"model": "gr4j", "basin_ids": ["01013500"]}
)

# Returns:
# {
#     "tool_chain": [...],
#     "execution_mode": "simple",
#     "mode_params": {}
# }
```

---

## Core Tools

### 1. DataValidationTool

**Category**: VALIDATION
**Name**: `validate_data`
**Purpose**: Validate basin IDs, time ranges, and variable availability

**Inputs**:
- `basin_ids`: List of basin IDs to validate
- `train_period`: Training period `[start, end]`
- `test_period`: Test period `[start, end]` (optional)
- `required_variables`: List of required variables (e.g., `["streamflow", "precipitation"]`)

**Outputs**:
- `valid_basins`: List of valid basin IDs
- `invalid_basins`: Dict of invalid basins with reasons
- `warnings`: List of warnings
- `data_availability`: Detailed availability info

**Example**:
```python
result = executor.execute_tool("validate_data", {
    "basin_ids": ["01013500", "99999999"],
    "train_period": ["1990-01-01", "2000-01-01"],
    "required_variables": ["streamflow", "precipitation"]
})

# result.data:
# {
#     "valid_basins": ["01013500"],
#     "invalid_basins": {"99999999": "Basin not found in dataset"},
#     ...
# }
```

---

### 2. CalibrationTool

**Category**: CALIBRATION
**Name**: `calibrate`
**Purpose**: Execute model parameter calibration (decoupled from evaluation/visualization)

**Inputs**:
- `config`: Hydromodel configuration dict
- `show_progress`: Whether to show progress (default: True)

**Outputs**:
- `calibration_dir`: Output directory path
- `best_params`: Optimized parameters for each basin
- `calibration_metrics`: Training period metrics (NSE, RMSE, etc.)
- `output_files`: Generated files
- `raw_result`: Raw hydromodel result

**Dependencies**: `validate_data` (recommended)

**Example**:
```python
result = executor.execute_tool("calibrate", {
    "config": {
        "data_cfgs": {...},
        "model_cfgs": {"model_name": "gr4j"},
        "training_cfgs": {"algorithm": "SCE_UA"}
    }
})
```

---

### 3. EvaluationTool

**Category**: EVALUATION
**Name**: `evaluate`
**Purpose**: Evaluate model performance on test period

**Inputs**:
- `calibration_dir`: Calibration results directory (if evaluating calibration)
- `config`: Hydromodel configuration (if independent evaluation)
- `params`: Model parameters (if independent evaluation)

**Outputs**:
- `evaluation_metrics`: Test period metrics
- `evaluation_files`: Generated files

**Dependencies**: `calibrate` (optional, can run independently)

**Example**:
```python
# Evaluate calibration results
result = executor.execute_tool("evaluate", {
    "calibration_dir": "/path/to/calibration_results",
    "config": {...}
})
```

---

### 4. SimulationTool

**Category**: SIMULATION
**Name**: `simulate`
**Purpose**: Run model predictions with given parameters

**Inputs**:
- `config`: Hydromodel configuration
- `params`: Model parameters (optional if loading from calibration)
- `calibration_dir`: Calibration directory to load parameters from (optional)
- `show_progress`: Show progress (default: True)

**Outputs**:
- `simulation_dir`: Output directory
- `predictions`: Simulated streamflow
- `output_files`: Generated files

**Use Cases**:
- Scenario analysis with custom parameters
- Prediction on new time periods
- Testing parameter sensitivity

**Example**:
```python
# Simulate using calibrated parameters
result = executor.execute_tool("simulate", {
    "config": {...},
    "calibration_dir": "/path/to/calibration"
})

# Or simulate with custom parameters
result = executor.execute_tool("simulate", {
    "config": {...},
    "params": {"01013500": {"x1": 0.5, "x2": 0.3, "x3": 0.2, "x4": 0.8}}
})
```

---

### 5. VisualizationTool

**Category**: VISUALIZATION
**Name**: `visualize`
**Purpose**: Generate plots and charts

**Inputs**:
- `calibration_dir`: Results directory
- `basin_ids`: Basin IDs to plot
- `plot_types`: Types of plots (e.g., `["hydrograph", "metrics"]`)

**Outputs**:
- `plot_files`: Generated plot files
- `plot_dir`: Plot directory

**Example**:
```python
result = executor.execute_tool("visualize", {
    "calibration_dir": "/path/to/results",
    "basin_ids": ["01013500"],
    "plot_types": ["hydrograph", "metrics"]
})
```

---

### 6. CodeGenerationTool

**Category**: ANALYSIS
**Name**: `generate_code`
**Purpose**: Generate custom analysis code using LLM

**Inputs**:
- `task_description`: Description of the analysis task
- `data_info`: Information about available data
- `code_llm`: Code-specialized LLM to use (optional)

**Outputs**:
- `generated_code`: Python code
- `code_file`: Saved code file path
- `execution_result`: Result if code was executed

**Example**:
```python
result = executor.execute_tool("generate_code", {
    "task_description": "Calculate runoff coefficient for basin 01013500",
    "data_info": {
        "nc_file_path": "/path/to/data.nc",
        "basin_id": "01013500"
    }
})
```

---

### 7. CustomAnalysisTool

**Category**: ANALYSIS
**Name**: `custom_analysis`
**Purpose**: LLM-assisted handling of unforeseen tasks

**Inputs**:
- `task_description`: Description of the task
- `context`: Additional context

**Outputs**:
- `analysis_result`: Analysis result
- `recommendations`: Recommendations

---

## Execution Modes

### 1. Simple Mode (One-Time Sequential Execution)

**When to use**: Standard workflows with a single pass

**Tool Chain Example**:
```python
{
    "execution_mode": "simple",
    "tool_chain": [
        {"tool": "validate_data", "inputs": {...}},
        {"tool": "calibrate", "inputs": {...}},
        {"tool": "evaluate", "inputs": {"calibration_dir": "${calibrate.calibration_dir}"}},
        {"tool": "visualize", "inputs": {"calibration_dir": "${calibrate.calibration_dir}"}}
    ]
}
```

**User Query Examples**:
- "率定GR4J模型，流域01013500，然后评估"
- "Calibrate XAJ model, basin 02070000, evaluate, and visualize"

---

### 2. Iterative Mode (Loop Until Condition Met)

**When to use**: Auto-optimization tasks with convergence criteria

**Mode Parameters**:
- `nse_threshold`: Target NSE value (e.g., 0.7)
- `max_iterations`: Maximum iterations (e.g., 5)
- `boundary_threshold`: Parameter boundary threshold (e.g., 0.05)

**Tool Chain Example**:
```python
{
    "execution_mode": "iterative",
    "mode_params": {
        "nse_threshold": 0.7,
        "max_iterations": 5,
        "boundary_threshold": 0.05
    },
    "tool_chain": [...]  # Will loop this chain
}
```

**User Query Examples**:
- "一直率定到NSE达到0.7为止"
- "如果参数收敛到边界，则调整范围重新率定，最多5次"

**Stopping Conditions**:
1. NSE ≥ threshold
2. Max iterations reached
3. No improvement for N consecutive iterations

---

### 3. Repeated Mode (Execute N Times)

**When to use**: Stability analysis, statistical experiments

**Mode Parameters**:
- `num_repetitions`: Number of repetitions (e.g., 10)
- `aggregate_results`: Whether to compute statistics

**Tool Chain Example**:
```python
{
    "execution_mode": "repeated",
    "mode_params": {
        "num_repetitions": 10,
        "aggregate_results": true
    },
    "tool_chain": [...]  # Will repeat this chain
}
```

**User Query Examples**:
- "重复率定5次，验证稳定性"
- "批量重复率定10次，计算统计指标"

**Aggregated Metrics**:
- Mean, std, min, max of NSE, RMSE, etc.
- Parameter variability analysis

---

## Usage Guide

### Enabling/Disabling Tool System

**Config**: `configs/config.py`

```python
# Enable tool system (default: True in Phase 2)
USE_TOOL_SYSTEM = True

# To use legacy mode (not recommended):
USE_TOOL_SYSTEM = False
```

### Using Tool System via RunnerAgent

The tool system is automatically used when `USE_TOOL_SYSTEM=True`:

```python
from hydroagent.agents.runner_agent import RunnerAgent

runner = RunnerAgent(llm_interface=None, use_tool_system=True)

# TaskPlanner provides task_plan with tool_chain
task_plan = {
    "execution_mode": "simple",
    "tool_chain": [...]
}

result = runner.process(task_plan)
```

### Direct Tool Execution (Advanced)

For testing or custom workflows:

```python
from hydroagent.tools.registry import registry
from hydroagent.tools.executor import ToolExecutor

# Initialize executor
executor = ToolExecutor(registry)

# Execute single tool
result = executor.execute_tool("calibrate", {"config": {...}})

# Execute tool chain
results = executor.execute_chain([
    {"tool": "validate_data", "inputs": {...}},
    {"tool": "calibrate", "inputs": {...}}
])
```

---

## Tool Development

### Creating a Custom Tool

**Step 1**: Create tool file in `hydroagent/tools/`

```python
from hydroagent.tools.base_tool import BaseTool, ToolResult, ToolMetadata, ToolCategory

class MyCustomTool(BaseTool):
    def _define_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="my_tool",
            description="My custom tool",
            category=ToolCategory.ANALYSIS,
            version="1.0.0",
            input_schema={"param1": "str - Description"},
            output_schema={"result": "Any - Description"},
            dependencies=[],
            required_config_keys=["param1"]
        )

    def execute(self, inputs: Dict[str, Any]) -> ToolResult:
        param1 = inputs["param1"]

        try:
            # Your logic here
            result = do_something(param1)

            return ToolResult(
                success=True,
                data={"result": result}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e)
            )
```

**Step 2**: Register the tool

```python
from hydroagent.tools.registry import registry

registry.register(MyCustomTool())
```

**Step 3**: Use in tool chains

```python
{
    "tool": "my_tool",
    "inputs": {"param1": "value"}
}
```

---

## Troubleshooting

### Tool Not Found

**Error**: `Tool 'xxx' not found in registry`

**Solution**:
1. Check if tool is registered: `registry.list_tools()`
2. Ensure tool is imported in `__init__.py`
3. Check tool name matches exactly

### Parameter Reference Not Resolved

**Error**: `Reference '${tool.field}' could not be resolved`

**Solution**:
1. Check if previous tool exists in chain
2. Verify field name is correct
3. Check tool execution order

### Tool Execution Failed

**Error**: Tool returns `success=False`

**Solution**:
1. Check `result.error` for error message
2. Verify input parameters meet schema requirements
3. Check tool dependencies are satisfied
4. Review logs for detailed error info

### Legacy Mode Issues

**Symptom**: System behaves differently than expected

**Solution**:
- Verify `USE_TOOL_SYSTEM = True` in `configs/config.py`
- Check RunnerAgent initialization: `use_tool_system=True`
- Review logs for mode indicators

---

## Additional Resources

- **Architecture Documentation**: See `docs/ARCHITECTURE_v5.0.md`
- **Experiment Design**: See `experiment/experiments_tool_system.md`
- **Phase 1 Plan**: See plan document at `C:\Users\zlh15\.claude\plans\cuddly-enchanting-origami.md`
- **Code Templates**: See `hydroagent/resources/code_templates/`

---

## Version History

- **v2.0** (2025-12-24): Phase 2 complete - all tools migrated, default enabled
- **v1.0** (2025-01-25): Phase 1 complete - core infrastructure

---

**Last Updated**: 2025-12-24
**Maintainer**: HydroAgent Team
**License**: Copyright (c) 2023-2025 HydroAgent. All rights reserved.
