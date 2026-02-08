# HydroAgent Experiments - Quick Start Guide

**Version**: v2.0 (2026-01-14)
**Architecture**: Tool System Phase 1
**Status**: Production Ready

---

## 📁 Experiment Files Overview

### Core Experiment Scripts

| File | Version | Description | Queries | Status |
|------|---------|-------------|---------|--------|
| **exp_A.py** | v2.0 | Individual Tool Validation<br>单一工具执行能力验证 | 14 | ✅ Ready |
| **exp_B.py** | v2.0 | Tool Chain Orchestration<br>工具链编排与执行模式 | 10 | ✅ Ready |
| **exp_C.py** | v4.0 | Robustness & Error Boundary Exploration<br>鲁棒性与错误边界探测 | 18 | ✅ Ready |
| **exp_D.py** | v1.0 | Large-Scale Combination Testing<br>大规模组合任务测试 | 5 | ⚠️ Needs Update |

**Total**: 47 queries across 4 experiments

### Supporting Files

| File | Description |
|------|-------------|
| `base_experiment.py` | Base experiment framework class |
| `run_all_experiments.py` | Batch runner for all experiments |
| `run_all_experiments_ABC.py` | Runner for experiments A, B, C only |
| `experiments_tool_system.md` | Comprehensive experimental design documentation |

### Archive

| Directory | Description |
|-----------|-------------|
| `old-exp/` | Legacy experiments from previous architecture (archived) |

---

## 🚀 Quick Start

### Run Individual Experiments

```bash
# Experiment A - Tool Validation (14 queries)
python experiment/exp_A.py --backend api --mock

# Experiment B - Tool Chain Orchestration (10 queries)
python experiment/exp_B.py --backend api --mock

# Experiment C - Robustness Testing (18 queries)
python experiment/exp_C.py --backend api --mode all --mock

# Experiment D - Large-Scale Testing (5 queries)
python experiment/exp_D.py --backend api --mock
```

### Run All Experiments

```bash
# Run experiments A, B, C (recommended)
python experiment/run_all_experiments_ABC.py --backend api --mock

# Run all four experiments
python experiment/run_all_experiments.py --backend api --mock
```

### Command-Line Options

| Option | Values | Description |
|--------|--------|-------------|
| `--backend` | `api`, `ollama` | LLM backend (default: `api`) |
| `--mock` | flag | Use mock hydromodel execution (fast) |
| `--no-mock` | flag | Use real hydromodel execution |
| `--mode` | `all`, `error`, `boundary`, `stress` | Experiment C mode selection |

---

## 📊 Experiment Design Summary

### Experiment A v2.0 - Individual Tool Validation

**Purpose**: Verify each tool works independently

**Tool Categories** (3):
- **Validation Tools** (2 queries): DataValidationTool → Target: ≥90%
- **Execution Tools** (6 queries): Calibration, Evaluation, Simulation → Target: ≥85%
- **Analysis Tools** (6 queries): Visualization, Code Generation, Custom Analysis → Target: ≥70%

**Key Metrics**:
- Execution Success Rate
- Intent Recognition Accuracy
- Tool Call Accuracy
- Output Consistency

**Report Output**: `experiment_A_report.md`

---

### Experiment B v2.0 - Tool Chain Orchestration

**Purpose**: Verify tool chains are correctly generated and executed

**Execution Mode Categories** (4):
- **Simple Mode** (2 queries): Sequential execution → Target: ≥90%
- **Iterative Mode** (2 queries): Performance-driven optimization → Target: ≥75%
- **Repeated Mode** (4 queries): Stability analysis → Target: ≥85%
- **Parallel/Batch Mode** (2 queries): Multi-basin/model processing → Target: ≥80%

**Key Metrics**:
- Workflow Correctness
- Task Decomposition Accuracy
- Conditional Branch Validity
- Iterative Convergence Rate
- Execution Stability

**Report Output**: `experiment_B_report.md`

---

### Experiment C v4.0 - Robustness & Error Boundary Exploration

**Purpose**: Explore system boundaries and error handling capabilities

**Scenario Categories** (3):
- **Error Scenarios** (6 queries): Verify error detection → Target: ≥80% rejection
- **Boundary Conditions** (6 queries): Explore tolerance limits → Unknown outcome
- **Stress Tests** (6 queries): Validate stability under extreme conditions → Target: ≥80% success

**Key Metrics**:
- Error Detection Rate
- Error Classification Accuracy
- Boundary Coverage
- Stress Test Pass Rate
- System Stability (no crashes)

**Report Output**: `experiment_C_v4_report.md`

---

### Experiment D v1.0 - Large-Scale Combination Testing

**Purpose**: Verify system can handle large-scale model×basin×algorithm combinations

**Scale**:
- 5 queries generating 54 theoretical task combinations
- Tests multi-model, multi-basin batch processing

**Key Metrics**:
- Combination Coverage
- Batch Processing Efficiency
- Result Aggregation Correctness

**Report Output**: `experiment_D_report.md` (TBD)

---

## 📈 Expected Outputs

Each experiment generates:

### 1. Session Reports
Individual analysis reports for each query execution:
```
experiment_results/exp_{X}_{name}_{timestamp}/
├── session_00001_{timestamp}/
│   └── analysis_report.md
├── session_00002_{timestamp}/
│   └── analysis_report.md
...
```

### 2. Experiment Report
BaseExperiment framework report with basic statistics:
```
experiment_results/exp_{X}_{name}_{timestamp}/
└── reports/
    └── experiment_report.md
```

### 3. Comprehensive Report (NEW in v2.0)
Publication-ready comprehensive analysis:
```
experiment_results/exp_{X}_{name}_{timestamp}/
└── experiment_{X}_report.md  ⭐
```

### 4. Data Files
```
experiment_results/exp_{X}_{name}_{timestamp}/
└── data/
    ├── results.csv
    ├── results.json
    └── metrics.json
```

---

## 📚 Documentation

### Primary Documents

1. **README.md** (this file) - Quick start guide
2. **experiments_tool_system.md** - Comprehensive experimental design
3. **docs/EXPERIMENT_C_V4_DESIGN_20260114.md** - Experiment C v4.0 redesign details
4. **docs/EXPERIMENT_AB_V2_IMPROVEMENTS_20260114.md** - Experiments A & B v2.0 improvements

### Architecture Documents

- **CLAUDE.md** - System architecture and development guide
- **docs/TOOL_SYSTEM_GUIDE.md** - Tool system usage guide
- **docs/ARCHITECTURE_FINAL.md** - Final architecture documentation

---

## 🎯 Success Criteria

### Publication-Ready Standards

Each experiment must meet:

1. **Clear Scene Classification**: Explicit categories with indices
2. **Differentiated Targets**: Different success rates for different complexities
3. **Comprehensive Reports**: Independent Markdown files with all sections
4. **Category-Based Analysis**: Per-category success rates calculated

### Minimum Success Rates

| Experiment | Overall Target | Category Targets |
|------------|---------------|-----------------|
| **Experiment A** | ≥80% | Validation: ≥90%<br>Execution: ≥85%<br>Analysis: ≥70% |
| **Experiment B** | ≥80% | Simple: ≥90%<br>Iterative: ≥75%<br>Repeated: ≥85%<br>Parallel: ≥80% |
| **Experiment C** | N/A | Error Detection: ≥80%<br>Boundary: 100% stability<br>Stress: ≥80% |
| **Experiment D** | ≥70% | TBD |

---

## 🔧 Troubleshooting

### Common Issues

**Issue**: Mock mode runs but doesn't test real hydromodel functionality
- **Solution**: Use `--no-mock` flag for full integration testing
- **Note**: Real execution requires CAMELS dataset

**Issue**: Experiments take too long
- **Solution**: Use `--mock` flag for rapid testing
- **Note**: Mock mode uses simulated data

**Issue**: API timeout or connection errors
- **Solution**: Check `configs/definitions_private.py` for correct API keys and endpoints
- **Fallback**: Use `--backend ollama` for local execution

---

## 📊 Version History

| Version | Date | Changes |
|---------|------|---------|
| **v2.0** | 2026-01-14 | - Experiment A v2.0: Added scene categories and comprehensive report<br>- Experiment B v2.0: Added execution mode categories and comprehensive report<br>- Experiment C v4.0: Redesigned for robustness exploration<br>- Removed all backup files |
| **v1.0** | 2025-12-24 | Initial tool system experiments (A, B, C, D) |

---

## 🚧 Future Work

- [ ] Update Experiment D to v2.0 standards
- [ ] Add cross-experiment comparison report
- [ ] Implement automated CI/CD testing
- [ ] Add performance benchmarking metrics

---

## 📞 Contact

For questions or issues:
- GitHub Issues: https://github.com/your-org/HydroAgent/issues
- Documentation: See `experiments_tool_system.md` for detailed design

---

**Last Updated**: 2026-01-14
**Maintained By**: HydroAgent Development Team
