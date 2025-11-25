# HydroAgent Checkpoint/Resume System

**版本**: v1.0
**日期**: 2025-01-25
**作者**: Claude

---

## 📋 概述

HydroAgent 的 Checkpoint/Resume 系统提供了任务中断和恢复功能，允许用户在长时间运行的水文模型率定任务中：

- ✅ **随时中断**: 使用 Ctrl+C 安全地中断任务执行
- ✅ **自动保存**: 每个子任务完成后自动保存进度
- ✅ **智能恢复**: 只执行未完成的任务，跳过已完成的任务
- ✅ **降低成本**: 避免因中断而从头开始，节省计算资源和时间

---

## 🎯 使用场景

### 场景1: 多流域批量率定

```bash
# 开始批量率定20个流域
python scripts/run_with_checkpoint.py \
  --query "批量率定20个流域" \
  --backend api

# 假设执行到第8个流域时需要中断（Ctrl+C）
# Checkpoint自动保存当前进度

# 稍后恢复执行（从第9个流域继续）
python scripts/run_with_checkpoint.py \
  --resume results/session_20250125_120000_abc123 \
  --backend api
```

### 场景2: 重复率定稳定性测试

```bash
# 开始重复率定实验（100次）
python experiment/exp_2a_repeated_calibration.py \
  --repetitions 100 \
  --backend api

# 执行30次后需要暂停
# 使用checkpoint保存的进度，下次继续执行剩余70次
```

### 场景3: 模型×算法矩阵测试

```bash
# 4种模型 × 3种算法 = 12个组合
python experiment/exp_2c_multi_algorithm.py \
  --backend api

# 执行5个组合后中断
# 恢复后只执行剩余7个组合
```

---

## 🏗️ 架构设计

### 核心组件

```
hydroagent/
├── core/
│   └── checkpoint_manager.py    # Checkpoint管理器（核心）
└── agents/
    └── orchestrator.py          # 中央编排器（集成checkpoint）
```

### Checkpoint文件结构

```json
{
  "version": "1.0",
  "experiment_name": "exp_2a_repeated_calibration",
  "query": "重复率定流域01013500五次",
  "created_at": "2025-01-25T10:00:00",
  "last_updated": "2025-01-25T10:15:00",
  "status": "in_progress",
  "total_tasks": 5,
  "completed_tasks": 2,
  "failed_tasks": 0,
  "current_phase": "runner",
  "intent_result": {...},
  "task_plan": {...},
  "subtasks_status": {
    "task_1_rep1": {
      "status": "completed",
      "config": {...},
      "result": {...},
      "completed_at": "2025-01-25T10:05:00"
    },
    "task_2_rep2": {
      "status": "completed",
      "config": {...},
      "result": {...},
      "completed_at": "2025-01-25T10:10:00"
    },
    "task_3_rep3": {
      "status": "in_progress",
      "config": {...},
      "started_at": "2025-01-25T10:14:00"
    },
    "task_4_rep4": {
      "status": "pending"
    },
    "task_5_rep5": {
      "status": "pending"
    }
  }
}
```

---

## 🔧 API 使用

### 1. CheckpointManager 基本用法

```python
from hydroagent.core.checkpoint_manager import CheckpointManager
from pathlib import Path

# 创建工作目录
workspace = Path("results/my_experiment")
workspace.mkdir(parents=True, exist_ok=True)

# 初始化checkpoint
checkpoint = CheckpointManager(workspace)
checkpoint.initialize(
    experiment_name="my_calibration",
    query="率定流域01013500",
    total_tasks=0  # 将在TaskPlanner后更新
)

# 保存Intent结果
intent_result = {"intent": "calibration", "model": "gr4j", ...}
checkpoint.save_intent_result(intent_result)

# 保存任务计划
task_plan = {
    "task_type": "standard_calibration",
    "subtasks": [
        {"task_id": "task_1", "description": "率定任务1"},
        {"task_id": "task_2", "description": "率定任务2"}
    ]
}
checkpoint.save_task_plan(task_plan)

# 执行任务
for subtask in task_plan["subtasks"]:
    task_id = subtask["task_id"]

    # 标记任务开始
    config = {"basin_id": "01013500", "model": "gr4j"}
    checkpoint.mark_subtask_started(task_id, config)

    # 执行任务
    result = run_calibration(config)  # 用户的执行逻辑

    # 标记任务完成
    if result["success"]:
        checkpoint.mark_subtask_completed(task_id, result)
    else:
        checkpoint.mark_subtask_failed(task_id, result["error"])

# 标记实验完成
analysis = {"quality": "good", "nse": 0.75}
checkpoint.mark_experiment_completed(analysis)
```

### 2. 恢复执行

```python
# 加载checkpoint
checkpoint = CheckpointManager(workspace)
checkpoint.load()

# 检查是否可以恢复
if not checkpoint.can_resume():
    print("实验已完成或无待执行任务")
    exit(0)

# 获取进度摘要
progress = checkpoint.get_progress_summary()
print(f"已完成: {progress['completed']}/{progress['total']}")

# 获取待执行任务
pending_tasks = checkpoint.get_pending_subtasks()

# 继续执行
for task in pending_tasks:
    task_id = task["task_id"]
    # ... 执行任务
```

### 3. Orchestrator 集成

```python
from hydroagent.agents.orchestrator import Orchestrator
from hydroagent.core.llm_interface import create_llm_interface

llm = create_llm_interface("api", "qwen-turbo", api_key="...")

# 创建Orchestrator（启用checkpoint）
orchestrator = Orchestrator(
    llm_interface=llm,
    workspace_root=Path("results"),
    enable_checkpoint=True  # 启用checkpoint
)

# 方式1: 新会话
session_id = orchestrator.start_new_session()
# ... checkpoint_manager已自动创建

# 方式2: 恢复会话
session_id = orchestrator.resume_session(Path("results/session_xxx"))
# ... checkpoint_manager已加载
```

---

## 📊 Checkpoint 状态机

```
pending → in_progress → completed
                    ↓
                  failed
```

**状态说明**:
- `pending`: 任务尚未开始
- `in_progress`: 任务正在执行
- `completed`: 任务成功完成
- `failed`: 任务执行失败

---

## 🧪 测试

### 运行单元测试

```bash
# 测试checkpoint基本功能
python test/test_checkpoint_resume.py
```

**测试覆盖**:
1. ✅ Checkpoint创建和基本操作
2. ✅ 从checkpoint恢复执行
3. ✅ 任务失败处理
4. ✅ 数据持久化

### 运行集成测试

```bash
# 使用checkpoint运行实验
python scripts/run_with_checkpoint.py \
  --query "重复率定流域01013500五次" \
  --backend api \
  --mock

# 模拟中断（Ctrl+C）

# 恢复执行
python scripts/run_with_checkpoint.py \
  --resume results/session_xxx \
  --backend api \
  --mock
```

---

## ⚙️ 配置选项

### CheckpointManager 初始化参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `workspace_dir` | Path | 工作目录（存放checkpoint.json） |

### Orchestrator 配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enable_checkpoint` | bool | True | 是否启用checkpoint功能 |

---

## 🔒 最佳实践

### 1. 合理的任务粒度

**推荐**: 将长时间任务拆分为多个子任务

```python
# ✅ 好的做法
task_plan = {
    "subtasks": [
        {"task_id": "basin_1", ...},
        {"task_id": "basin_2", ...},
        {"task_id": "basin_3", ...}
    ]
}
```

```python
# ❌ 不推荐
task_plan = {
    "subtasks": [
        {"task_id": "all_basins_at_once", ...}  # 单个任务太大
    ]
}
```

### 2. 及时保存checkpoint

在每个子任务完成后立即调用 `mark_subtask_completed()`：

```python
for task in tasks:
    try:
        result = execute_task(task)
        checkpoint.mark_subtask_completed(task_id, result)  # 立即保存
    except Exception as e:
        checkpoint.mark_subtask_failed(task_id, str(e))
```

### 3. 处理中断信号

```python
import signal
import sys

def signal_handler(sig, frame):
    print('\n⚠️  收到中断信号，保存checkpoint...')
    if checkpoint_manager:
        progress = checkpoint_manager.get_progress_summary()
        print(f"已完成: {progress['completed']}/{progress['total']}")
    sys.exit(130)

signal.signal(signal.SIGINT, signal_handler)
```

### 4. 验证恢复完整性

```python
# 恢复前检查
checkpoint.load()
progress = checkpoint.get_progress_summary()

if progress['failed'] > 0:
    print(f"⚠️  有 {progress['failed']} 个任务失败")
    # 决定是否重试失败的任务
```

---

## 🚀 性能考虑

### 1. Checkpoint 文件大小

- 每个subtask保存配置和结果
- 对于大规模实验（100+任务），checkpoint文件可达 1-10 MB
- 使用JSON格式，便于人工检查和调试

### 2. 保存频率

- **当前实现**: 每个subtask完成后立即保存
- **开销**: 每次保存约 10-50ms（取决于文件大小）
- **权衡**: 频繁保存保证数据安全，但略微影响性能

### 3. 并发控制

- CheckpointManager **非线程安全**
- 如需并发执行，需要：
  - 每个任务使用独立的CheckpointManager实例
  - 或添加文件锁机制

---

## 📝 文件说明

### 核心文件

| 文件 | 说明 |
|------|------|
| `hydroagent/core/checkpoint_manager.py` | Checkpoint管理器实现 |
| `test/test_checkpoint_resume.py` | 单元测试 |
| `scripts/run_with_checkpoint.py` | 示例脚本 |
| `docs/CHECKPOINT_SYSTEM.md` | 本文档 |

### Checkpoint 文件位置

```
results/
└── session_20250125_120000_abc123/
    ├── checkpoint.json              # ← Checkpoint文件
    ├── intent_result.json
    ├── task_plan.json
    ├── config_1.json
    └── ... (其他结果文件)
```

---

## 🐛 故障排查

### 问题1: Checkpoint文件损坏

**现象**: 加载checkpoint时报错 `JSONDecodeError`

**解决**:
```bash
# 检查文件是否完整
cat results/session_xxx/checkpoint.json | jq .

# 恢复最近的备份（如果有）
cp results/session_xxx/checkpoint.json.bak results/session_xxx/checkpoint.json
```

### 问题2: 无法恢复执行

**现象**: `can_resume()` 返回 False

**原因**:
- 实验已完成 (`status: "completed"`)
- 所有任务已执行（无pending任务）

**检查**:
```python
checkpoint.load()
print(checkpoint.checkpoint_data['status'])
print(checkpoint.get_progress_summary())
```

### 问题3: 任务重复执行

**原因**: 任务完成后未及时调用 `mark_subtask_completed()`

**解决**: 确保在每个任务成功后立即调用：
```python
result = run_task()
checkpoint.mark_subtask_completed(task_id, result)  # 必须调用
```

---

## 🔮 未来扩展

### v2.0 计划功能

- [ ] **增量checkpoint**: 只保存变化的部分，减少文件大小
- [ ] **版本控制**: 支持checkpoint版本回退
- [ ] **并发支持**: 添加文件锁，支持并发写入
- [ ] **压缩**: 对大型结果使用gzip压缩
- [ ] **云存储**: 支持S3/OSS等远程checkpoint存储
- [ ] **UI界面**: Web界面查看和管理checkpoint

---

## 📚 相关文档

- [系统架构文档](ARCHITECTURE_FINAL.md)
- [测试指南](TESTING_GUIDE.md)
- [Orchestrator 设计](../hydroagent/agents/orchestrator.py)

---

**最后更新**: 2025-01-25
**维护者**: HydroAgent Team
