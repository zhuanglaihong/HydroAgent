# v6.0 Legacy代码清单与删除计划

**日期**: 2026-01-12
**任务**: 方案C - 完全移除Legacy路径，彻底统一为v6.0架构

---

## 📋 Legacy代码清单

### 1. Orchestrator.py

#### L1236-1353: Legacy subtasks处理逻辑

**代码块**:
```python
# Legacy mode: use subtasks
subtasks = task_plan.get("subtasks", [])
...
# 选择下一个pending subtask
# 生成config (调用InterpreterAgent)
# 特殊处理analysis任务
# 返回config_result
```

**功能**: 处理旧格式的subtasks（非tool_chain格式）

**依赖关系**:
- 依赖TaskPlanner生成旧格式的subtasks
- 依赖InterpreterAgent生成config
- 可能依赖RunnerAgent的fallback逻辑

**删除影响**:
- 如果TaskPlanner不再生成旧格式，这段代码永远不会执行
- **可安全删除**

#### L989: Legacy注释
```python
# Legacy mode: extract task_plan directly
task_plan = task_plan_result.get("task_plan", {})
```

**处理**: 保留，这是兼容TaskPlanner返回格式的逻辑

---

### 2. TaskPlanner.py

#### L213-218: DEPRECATED注释块
```python
# ⚠️ DEPRECATED (v6.0): Legacy decomposition methods no longer used
# All tasks now use tool chains, not subtask-based decomposition
# Kept for reference, may be removed in future versions
```

#### L219-1069: 所有Legacy分解方法

**方法列表**:
1. `_decompose_task()` (L219-269) - 主分解入口
2. `_decompose_standard_calibration()` (L294-322)
3. `_decompose_info_completion()` (L324-333)
4. `_decompose_iterative_optimization()` (L335-396)
5. `_decompose_repeated_experiment()` (L398-447)
6. `_decompose_extended_analysis()` (L449-507)
7. `_decompose_batch_processing()` (L509-585)
8. `_decompose_custom_data()` (L587-614)
9. `_decompose_auto_iterative_calibration()` (L616-778)
10. `_decompose_task_with_llm()` (L780-1069) - LLM分解

**总计**: ~850行代码

**功能**: 将任务分解为旧格式的subtasks列表

**删除影响**:
- TaskPlanner.process()在L211强制调用`_process_with_tools()`
- 这些方法**从未被调用**
- **可安全删除**

---

### 3. RunnerAgent.py

#### L326-329: DEPRECATED注释块
```python
# ⚠️ DEPRECATED (v6.0): Legacy execution methods no longer used
# All tasks now use tool chains
```

#### L331-468: `_process_legacy_DEPRECATED()` 主方法

**功能**: Legacy执行入口，路由到不同的_run_*_DEPRECATED方法

#### L470-1629: 所有Legacy _run_*_DEPRECATED方法

**方法列表**:
1. `_run_calibration_DEPRECATED()` (L470-721) - ~250行
2. `_run_evaluation_DEPRECATED()` (L723-796) - ~70行
3. `_run_simulation_DEPRECATED()` (L798-1020) - ~220行
4. `_run_boundary_check_recalibration_DEPRECATED()` (L1022-1340) - ~320行
5. `_run_statistical_analysis_DEPRECATED()` (L1342-1500) - ~160行
6. `_run_custom_analysis_DEPRECATED()` (L1502-1629) - ~130行

**总计**: ~1300行代码

**功能**: 直接调用hydromodel执行各种任务

**删除影响**:
- RunnerAgent.process()在L321-323强制调用`_process_with_tools()`
- L1967有fallback逻辑：`return self._process_legacy(input_data)`
- **需要先删除L1967的fallback，然后再删除所有DEPRECATED方法**

#### L1967: Fallback调用（需要先删除）
```python
logger.warning("[RunnerAgent] No tool_chain found, attempting to execute as legacy config")
return self._process_legacy(input_data)
```

---

### 4. DeveloperAgent.py

#### L347: Legacy注释
```python
# CRITICAL FIX: Legacy mode should also generate session report, just like tool system mode
```

#### L610, L624, L708: Legacy支持逻辑
```python
subtask_results = tool_output.get("subtask_results", [])  # 🆕 Legacy mode support
...
if not tool_results and subtask_results:
    logger.info("[DeveloperAgent] Legacy mode detected, extracting metrics from subtask_results")
```

**功能**: 兼容处理Legacy路径的输出

**删除影响**:
- 如果Orchestrator不再生成subtask_results，这些逻辑不再触发
- **可安全删除**（但建议保留，作为向后兼容）

---

## ✅ v6.0路径覆盖范围验证

### TaskPlanner覆盖所有任务类型

**v6.0路径**: `_process_with_tools()` (L1071-1199)

**覆盖的task_type**:
1. ✅ `standard_calibration`: 单个tool_chain
2. ✅ `batch_processing`:
   - 单组合 → 单个tool_chain
   - 多组合 (M×N×K > 1) → 多个tool_chain subtasks (v6.0新增)
3. ✅ `iterative_optimization`: execution_mode=iterative
4. ✅ `repeated_experiment`: execution_mode=repeated
5. ✅ `extended_analysis`: compound tool_chain (calibrate + code_generation)
6. ✅ `info_completion`: 与standard_calibration相同
7. ✅ `custom_data`: 与standard_calibration相同，传递data_source

**覆盖范围**: **100% - 所有Legacy分解方法的功能都已被工具链覆盖**

### ToolOrchestrator覆盖所有执行模式

**工具链生成**: `generate_tool_chain()` 支持：
- ✅ simple模式: 顺序执行
- ✅ iterative模式: 循环执行直到达到阈值
- ✅ repeated模式: 重复执行N次

**工具覆盖**:
- ✅ calibration → CalibrationTool
- ✅ evaluation → EvaluationTool
- ✅ simulation → SimulationTool
- ✅ validation → DataValidationTool
- ✅ visualization → VisualizationTool
- ✅ code_generation → CodeGenerationTool
- ✅ custom_analysis → CustomAnalysisTool

**覆盖范围**: **100% - 所有Legacy _run_*方法的功能都已被工具覆盖**

---

## 🚨 删除前检查清单

### 1. TaskPlanner检查

- [x] `process()`强制调用`_process_with_tools()` (L211)
- [x] 所有task_type都有对应的工具链生成逻辑
- [x] 没有代码调用`_decompose_task()`或其他分解方法

**结论**: ✅ TaskPlanner的Legacy方法可安全删除

### 2. RunnerAgent检查

- [x] `process()`强制调用`_process_with_tools()` (L321-323)
- [ ] ⚠️ L1967有fallback到`_process_legacy()`
- [x] 所有功能都已被工具覆盖

**结论**: ⚠️ 需要先删除L1967的fallback，然后才能删除Legacy方法

### 3. Orchestrator检查

- [x] L1060-1148处理use_tool_chains=True（v6.0多组合）
- [x] L1150-1234处理use_tool_system=True（v6.0单任务）
- [x] TaskPlanner不再生成use_tool_chains=False的旧格式
- [x] L1236-1353的Legacy逻辑不会被触发

**结论**: ✅ Orchestrator的Legacy处理逻辑可安全删除

### 4. DeveloperAgent检查

- [x] 可以处理tool_output（v6.0）
- [x] 兼容处理subtask_results（Legacy）
- [ ] ⚠️ 建议保留Legacy兼容逻辑（向后兼容）

**结论**: ✅ 可以删除Legacy注释，但保留兼容处理逻辑

---

## 📝 删除计划

### Phase 1: 删除RunnerAgent的fallback (高优先级)

**文件**: `runner_agent.py`
**行号**: L1965-1967
**代码**:
```python
logger.warning("[RunnerAgent] No tool_chain found, attempting to execute as legacy config")
# Fallback: if no tool_chain, treat as legacy mode
return self._process_legacy(input_data)
```

**修改为**:
```python
logger.error("[RunnerAgent v6.0] No tool_chain found in input_data - all tasks must use tool system")
return {
    "success": False,
    "error": "No tool_chain found - v6.0 requires tool system execution",
    "output": {}
}
```

### Phase 2: 删除Orchestrator的Legacy处理逻辑

**文件**: `orchestrator.py`
**行号**: L1236-1353
**删除原因**: TaskPlanner不再生成旧格式subtasks，这段代码永远不会执行

**保留**: L989的兼容代码（用于提取task_plan）

### Phase 3: 删除TaskPlanner的所有分解方法

**文件**: `task_planner.py`
**行号**: L213-1069 (~850行)
**删除原因**: process()强制调用_process_with_tools()，这些方法从未被调用

**保留**: L1071+的_process_with_tools()方法

### Phase 4: 删除RunnerAgent的所有DEPRECATED方法

**文件**: `runner_agent.py`
**行号**: L326-1629 (~1300行)
**删除原因**: process()强制调用_process_with_tools()，且fallback已删除

**保留**: L1-325的工具系统执行逻辑

### Phase 5: 清理DeveloperAgent的Legacy注释

**文件**: `developer_agent.py`
**行号**: L347, L610, L624, L708
**修改**: 删除Legacy注释，但**保留兼容处理逻辑**（subtask_results兼容）

---

## ⚠️ 风险评估

### 低风险
- ✅ TaskPlanner的分解方法：确认未被调用
- ✅ Orchestrator的Legacy处理：确认不会触发

### 中风险
- ⚠️ RunnerAgent的fallback删除：需要确保所有调用都传递tool_chain
- ⚠️ RunnerAgent的DEPRECATED方法：需要确保没有外部直接调用

### 缓解措施
1. 先运行所有实验（A, B, C, D）验证v6.0路径工作正常
2. 逐个Phase删除，每次删除后运行测试
3. 保留git commit，方便回滚
4. 更新CLAUDE.md文档，标注v6.0为唯一路径

---

## 📊 代码减少统计

| 文件 | 删除行数 | 当前总行数 | 减少比例 |
|------|---------|----------|---------|
| TaskPlanner.py | ~850 | ~1600 | 53% |
| RunnerAgent.py | ~1300 | ~2000 | 65% |
| Orchestrator.py | ~120 | ~1800 | 7% |
| **总计** | **~2270** | **~5400** | **42%** |

**预计删除代码**: ~2270行
**架构简化**: 单一执行路径，维护成本降低50%+

---

## ✅ 删除后验证计划

1. 运行实验A (基础功能)
2. 运行实验B (复杂任务)
3. 运行实验C (错误处理)
4. 运行实验D (大规模组合)
5. 检查所有日志，确认没有Legacy路径警告
6. 更新CLAUDE.md，标注v6.0为唯一架构

---

**准备状态**: ✅ 清单完成，等待执行删除操作
