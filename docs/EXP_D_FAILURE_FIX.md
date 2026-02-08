# 实验D失败问题修复说明

**日期**: 2026-01-12
**版本**: v6.0
**问题**: 实验D所有查询执行失败
**根本原因**: FeedbackRouter不认识"Orchestrator"作为source_agent

---

## 问题描述

### 错误日志

```
[FeedbackRouter] WARNING - Unknown source agent: Orchestrator
[FeedbackRouter] Action: abort
[Orchestrator] ERROR - FeedbackRouter requested abort: Unknown abort reason
```

### 失败场景

实验D的6个大规模组合查询全部失败，所有查询都在`GENERATING_CONFIG`状态被abort。

---

## 根本原因分析

### 问题根源

在**Orchestrator v6.0**的多组合任务处理逻辑中（`orchestrator.py:1140-1148`），当处理完tool_chain subtask的config生成后，返回：

```python
return {
    "context_updates": {...},
    "source_agent": "Orchestrator",  # ❌ 错误：FeedbackRouter不认识
    "agent_result": config_result,
}
```

### FeedbackRouter的限制

`FeedbackRouter.route_feedback()`只认识这5个agent：
- IntentAgent
- TaskPlanner
- RunnerAgent
- DeveloperAgent
- InterpreterAgent

**没有"Orchestrator"的处理分支**，遇到未知agent时返回abort：

```python
# feedback_router.py:129-136
else:
    logger.warning(f"[FeedbackRouter] Unknown source agent: {source_agent}")
    return {
        "target_agent": None,
        "action": "abort",
        "parameters": {},
        "retryable": False
    }
```

### 为什么v6.0会有这个问题？

v6.0引入了Orchestrator循环执行架构，Orchestrator在处理多组合任务时：
1. 自己负责提取下一个待执行的subtask
2. 调用InterpreterAgent生成config
3. **自己组装config_result并返回**（新逻辑）

这个"自己组装并返回"的逻辑错误地设置了`source_agent: "Orchestrator"`，导致FeedbackRouter无法路由。

---

## 修复方案

### 设计原则

**Orchestrator的内部流程控制不应该经过FeedbackRouter路由**

FeedbackRouter的设计目的是路由**各个Agent的执行结果**，而Orchestrator的v6.0循环控制逻辑是**内部流程管理**，不需要外部路由。

### 修复方法

移除3处返回的`source_agent`和`agent_result`字段，让Orchestrator的内部决策不触发FeedbackRouter：

#### 修复1: 多组合任务的config生成（v6.0核心逻辑）

**文件**: `orchestrator.py:1140-1148`

**修复前**:
```python
return {
    "context_updates": {
        "config_result": config_result,
        "current_config": config_result,
        "current_subtask": current_subtask,
    },
    "source_agent": "Orchestrator",
    "agent_result": config_result,
}
```

**修复后**:
```python
return {
    "context_updates": {
        "config_result": config_result,
        "current_config": config_result,
        "current_subtask": current_subtask,
    },
    # ✅ v6.0: No source_agent/agent_result - Orchestrator internal flow control
    # FeedbackRouter should not route Orchestrator's own decisions
}
```

#### 修复2: 工具系统单任务模式（不需要config的场景）

**文件**: `orchestrator.py:1228-1235`

**修复前**:
```python
return {
    "context_updates": {
        "config_result": config_result,
        "current_config": config_result,
    },
    "source_agent": "Orchestrator",
    "agent_result": config_result,
}
```

**修复后**:
```python
return {
    "context_updates": {
        "config_result": config_result,
        "current_config": config_result,
    },
    # ✅ v6.0: No source_agent/agent_result - Orchestrator internal flow control
}
```

#### 修复3: Legacy模式下的分析任务特殊处理

**文件**: `orchestrator.py:1306-1313`

**修复前**:
```python
return {
    "context_updates": {
        "config_result": config_result,
        "current_config": config_result.get("config"),
    },
    "source_agent": "Orchestrator",  # Direct routing, no InterpreterAgent
    "agent_result": config_result,
}
```

**修复后**:
```python
return {
    "context_updates": {
        "config_result": config_result,
        "current_config": config_result.get("config"),
    },
    # ✅ No source_agent/agent_result - Orchestrator internal flow control
    # (Direct routing for analysis tasks, no InterpreterAgent)
}
```

---

## 验证修复

### 预期行为

修复后，Orchestrator在处理多组合任务时：

1. **GENERATING_CONFIG状态**:
   - 提取下一个待执行的subtask
   - 调用InterpreterAgent生成config
   - 组装config_result并更新context
   - **不触发FeedbackRouter** ✅

2. **状态转换**:
   - `GENERATING_CONFIG` → `EXECUTING_TASK`（自动，无需路由）

3. **执行subtask**:
   - RunnerAgent执行tool_chain
   - DeveloperAgent分析结果
   - 检查是否还有待执行的subtasks
   - 如果有 → 循环回`GENERATING_CONFIG`
   - 如果无 → 完成

### 测试方法

```bash
# 重新运行实验D
python experiment/exp_D.py --backend api --mock

# 预期结果
# - Query 1 (3×4×1=12组合): ✅ 成功
# - Query 2 (2×2×2=8组合): ✅ 成功
# - Query 3 (1×3×3=9组合): ✅ 成功
# - Query 4 (10×1=10组合): ✅ 成功
# - Query 5 (5×3=15组合): ✅ 成功
# - Query 6 (2×4×2=16组合): ✅ 成功
```

---

## 架构改进

### v6.0架构清晰化

这次修复进一步明确了v6.0的架构设计原则：

**职责分离**:
- **FeedbackRouter**: 路由Agent之间的执行结果和错误反馈
- **Orchestrator**: 内部流程控制和状态转换逻辑

**内部决策不路由**:
- Orchestrator的循环控制、subtask选择、config组装都是内部逻辑
- 不应该通过FeedbackRouter路由
- 直接通过`context_updates`更新上下文即可

**Agent结果才路由**:
- IntentAgent的intent识别结果
- TaskPlanner的task_plan生成结果
- InterpreterAgent的config生成结果
- RunnerAgent的执行结果
- DeveloperAgent的分析结果

这些才需要通过FeedbackRouter路由，决定下一步动作。

---

## 经验总结

### 问题根源

v6.0引入新逻辑时，**复用了旧的返回格式**（包含`source_agent`和`agent_result`），但没有考虑到FeedbackRouter的限制。

### 设计原则

1. **内部流程控制**和**Agent执行结果**要区分清楚
2. 引入新逻辑时，要检查所有涉及的系统组件（如FeedbackRouter）
3. 返回数据结构要符合下游处理逻辑的预期

### 未来改进

考虑重构state_result的返回格式，明确区分：
- **Agent执行结果**: 需要FeedbackRouter路由
- **Orchestrator内部决策**: 直接更新context，不路由

可以通过不同的字段名或标志位来区分。

---

**修复状态**: ✅ 已完成
**测试状态**: ⏳ 待验证
**影响范围**: Orchestrator v6.0的所有多组合任务执行路径
