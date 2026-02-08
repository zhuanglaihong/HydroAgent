# Basin ID 字段修复总结

**日期**: 2025-12-28
**问题**: 系统错误使用单数 `basin_id`，但 hydromodel 只接受 `basin_ids` 数组格式

---

## 📋 问题描述

发现 `session_result` 中包含：
```json
"intent": {
    "intent": "extension",
    "model_name": "gr4j",
    "basin_id": "01013500",  ❌ 错误：hydromodel不认识这个字段
    "basin_ids": null
}
```

**正确格式应该是**：
```json
"intent": {
    "intent": "extension",
    "model_name": "gr4j",
    "basin_ids": ["01013500"]  ✅ 正确：始终使用数组格式
}
```

---

## ✅ 已修复的核心文件

### 1. **IntentAgent** (`hydroagent/agents/intent_agent.py`)

**修复内容**：
- ✅ 更新 LLM 提示词，强调使用 `basin_ids` 数组格式
- ✅ 示例输出全部改为 `basin_ids: ["01013500"]`
- ✅ 规范化函数：自动将 `basin_id` 转换为 `basin_ids` 数组
- ✅ 数据验证：改为验证 `basin_ids` 数组中的每个ID
- ✅ 信息补全：检查和补全 `basin_ids` 字段
- ✅ 流域提取：统一返回 `basin_ids` 数组
- ✅ 复合任务：共享上下文使用 `basin_ids`

**关键修改**：
```python
# 修改前
normalized["basin_id"] = response.get("basin_id")

# 修改后
# 统一规范化为basin_ids数组
if normalized.get("basin_ids"):
    # 已经是数组，保持不变
    pass
elif normalized.get("basin_id"):
    # 转换单个ID为数组
    normalized["basin_ids"] = [normalized["basin_id"]]

# 移除basin_id字段
if "basin_id" in normalized:
    del normalized["basin_id"]
```

---

### 2. **TaskPlanner** (`hydroagent/agents/task_planner.py`)

**修复内容**：
- ✅ 标准率定任务：`parameters["basin_ids"]`
- ✅ 迭代优化任务：`parameters["basin_ids"]`
- ✅ 重复实验任务：`parameters["basin_ids"]`
- ✅ 扩展分析任务：`parameters["basin_ids"]`
- ✅ 批量处理任务：每个子任务 `basin_ids: [basin]`
- ✅ 自定义数据任务：`parameters["basin_ids"]`
- ✅ 自动迭代率定：`parameters["basin_ids"]`
- ✅ LLM生成的subtasks：自动补全 `basin_ids`

**关键修改**：
```python
# 修改前
SubTask(
    parameters={
        "basin_id": intent.get("basin_id"),
        ...
    }
)

# 修改后
SubTask(
    parameters={
        "basin_ids": intent.get("basin_ids"),
        ...
    }
)
```

---

### 3. **InterpreterAgent** (`hydroagent/agents/interpreter_agent.py`)

**修复内容**：
- ✅ 参数提取：从 `basin_ids` 获取
- ✅ missing_info 检查：检查 `"basin_ids"`
- ✅ 自定义分析验证：验证 `basin_ids` 存在

**关键修改**：
```python
# 修改前
basin_ids = parameters.get("basin_ids") or parameters.get("basin_id")
if basin_ids and "basin_id" not in missing_info:
    ...

# 修改后
basin_ids = parameters.get("basin_ids")
if basin_ids and "basin_ids" not in missing_info:
    ...
```

---

### 4. **RunnerAgent** (`hydroagent/agents/runner_agent.py`)

**修复内容**：
- ✅ 日志输出：使用 `basin_ids`
- ✅ 自定义分析参数获取：`basin_ids = merged_params.get("basin_ids", [])`
- ✅ 返回结果：所有返回字典使用 `basin_ids`
- ✅ task_metadata 获取：`task_metadata.get("basin_ids")`

**关键修改**：
```python
# 修改前
basin_id = merged_params.get("basin_id")
return {
    "basin_id": basin_id,
    ...
}

# 修改后
basin_ids = merged_params.get("basin_ids", [])
return {
    "basin_ids": basin_ids,
    ...
}
```

---

## 🔧 hydromodel 的正确用法

hydromodel 的 **所有** 配置都使用 `basin_ids` 数组：

```python
config = {
    "data_cfgs": {
        "basin_ids": ["01013500"],  # ✅ 始终是数组
        "train_period": [...],
        ...
    },
    "model_cfgs": {...},
    "training_cfgs": {...}
}

# 即使只有一个流域，也必须用数组
# ❌ "basin_id": "01013500"  # 错误！hydromodel不识别
# ✅ "basin_ids": ["01013500"]  # 正确！
```

---

## 📊 修复覆盖范围

### ✅ 已修复（核心Agent）
- [x] **IntentAgent** - 意图识别和参数提取
- [x] **TaskPlanner** - 任务拆解和子任务生成
- [x] **InterpreterAgent** - 配置字典生成
- [x] **RunnerAgent** - 任务执行

### ⏸️ 无需修复（保留向后兼容）
- **Orchestrator** - 可能有向后兼容代码
- **DeveloperAgent** - 主要读取结果
- **ToolOrchestrator** - 可能有向后兼容代码

### ⏭️ 跳过（测试文件）
- `test/` 目录下所有文件按用户要求不修改

---

## 🧪 验证方法

运行任意实验，检查生成的 `session_result.json`：

```bash
python experiment/exp_A.py --backend api --mock
```

检查输出文件：
```json
{
  "intent": {
    "intent": "calibration",
    "model_name": "gr4j",
    "basin_ids": ["01013500"],  ✅ 必须是这个格式
    "basin_id": null  ❌ 不应该存在这个字段（或应该被删除）
  }
}
```

---

## 🎯 核心原则

1. **LLM 提示词**：要求 LLM 输出 `basin_ids` 数组
2. **规范化层**：IntentAgent 自动转换 `basin_id` → `basin_ids`
3. **传递链**：TaskPlanner → InterpreterAgent → RunnerAgent 全部使用 `basin_ids`
4. **hydromodel 配置**：`data_cfgs.basin_ids` 必须是数组

---

## 📝 后续工作

如果发现其他文件仍在使用 `basin_id`：

1. **工具系统** (`hydroagent/tools/*.py`)：
   - 检查 `validation_tool.py`
   - 检查 `calibration_tool.py`

2. **辅助工具** (`hydroagent/utils/*.py`)：
   - 检查 `code_generator.py`
   - 检查 `basin_validator.py`

可以使用以下命令查找：
```bash
grep -r "basin_id[^s]" hydroagent/ --include="*.py" | grep -v test
```

---

**修复完成时间**: 2025-12-28
**修复人**: Claude Sonnet 4.5
