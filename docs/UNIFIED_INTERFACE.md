# HydroAgent 统一接口文档

**版本**: v1.0
**日期**: 2025-01-25
**核心组件**: `Orchestrator`

---

## 🎯 核心概念

**Orchestrator** 是 HydroAgent 系统的**唯一对外统一接口**，集成了完整的 5-Agent 流程和 checkpoint 机制。

### 架构定位

```
用户层 (experiment/)     ← 用户调用脚本
    ↓
═══════════════════════════════════════
hydroagent/ (系统内部)
    ↓
Orchestrator (统一接口)  ← ⭐ 核心入口
    ├─ IntentAgent       (意图识别)
    ├─ TaskPlanner       (任务拆解)
    ├─ InterpreterAgent  (配置生成)
    ├─ RunnerAgent       (模型执行)
    └─ DeveloperAgent    (结果分析)
    ↓
Checkpoint Manager       (中断恢复)
═══════════════════════════════════════
```

---

## 🔧 完整的 5-Agent 流程

### 流程图

```
用户查询 (Query)
    ↓
┌─────────────────────────────────────────────────────┐
│  Orchestrator.process({"query": "..."})             │
│                                                      │
│  Step 1: IntentAgent                                │
│    ├─ 识别任务类型 (standard, repeated, batch...)  │
│    ├─ 提取模型名称 (GR4J, XAJ...)                   │
│    └─ 提取流域ID、算法、时间段等                    │
│        ↓                                             │
│  Step 2: TaskPlanner ⭐ NEW                         │
│    ├─ 拆解为多个子任务                              │
│    ├─ 支持重复率定 (5次 → 5个子任务)               │
│    ├─ 支持批量处理 (10个流域 → 10个子任务)         │
│    └─ 支持矩阵测试 (4模型×3算法 → 12个子任务)      │
│        ↓                                             │
│  Step 3: InterpreterAgent ⭐ NEW                    │
│    ├─ 为每个子任务生成 hydromodel 配置              │
│    └─ 应用默认参数和用户指定参数                    │
│        ↓                                             │
│  Step 4: RunnerAgent                                │
│    ├─ 逐个执行子任务                                │
│    ├─ 调用 hydromodel API (calibrate/evaluate)     │
│    ├─ 🔖 每个任务完成后自动保存 checkpoint         │
│    └─ 支持从 checkpoint 恢复 (跳过已完成任务)      │
│        ↓                                             │
│  Step 5: DeveloperAgent                             │
│    ├─ 分析所有执行结果                              │
│    ├─ 生成质量评估和改进建议                        │
│    └─ (可选) 生成自定义分析代码                     │
└─────────────────────────────────────────────────────┘
    ↓
返回结果 + 保存到 workspace/
```

---

## 🚀 使用方式

### 基本用法

```python
from hydroagent.core.llm_interface import create_llm_interface
from hydroagent.agents.orchestrator import Orchestrator

# 1. 创建 LLM 接口
llm = create_llm_interface("openai", "qwen-turbo",
                          api_key="your-key",
                          base_url="your-url")

# 2. 创建 Orchestrator（统一接口）
orchestrator = Orchestrator(
    llm_interface=llm,
    workspace_root=Path("results"),
    enable_checkpoint=True,    # 启用checkpoint
    show_progress=True,        # 显示hydromodel进度
    enable_code_gen=True       # 启用代码生成
)

# 3. 开始会话
session_id = orchestrator.start_new_session()

# 4. 处理查询（一行代码完成全部流程！）
result = orchestrator.process({
    "query": "率定流域12025000，使用GR4J模型",
    "use_mock": False  # True=Mock模式，False=真实hydromodel
})

# 5. 查看结果
if result["success"]:
    print(f"Session: {result['session_id']}")
    print(f"Workspace: {result['workspace']}")
    print(f"Summary:\n{result['summary']}")
```

### 恢复中断的会话

```python
# 从 checkpoint 恢复
orchestrator.resume_session(Path("results/session_20250125_120000_abc"))

# 继续执行（会跳过已完成的任务）
result = orchestrator.process({
    "query": "...",  # 原始查询会从checkpoint加载
    "use_mock": False
})
```

---

## 📊 支持的查询类型

### 1. 标准单流域率定

```python
result = orchestrator.process({
    "query": "率定流域12025000，使用GR4J模型"
})

# 结果: 1个子任务
```

### 2. 重复率定（稳定性测试）

```python
result = orchestrator.process({
    "query": "重复率定流域12025000五次，使用SCE-UA算法"
})

# 结果: 5个子任务（每次独立执行）
```

### 3. 批量多流域

```python
result = orchestrator.process({
    "query": "批量率定流域12025000, 01013500, 01022500，使用XAJ模型"
})

# 结果: 3个子任务（每个流域一个）
```

### 4. 模型×算法矩阵

```python
result = orchestrator.process({
    "query": "使用GR4J和XAJ模型，分别用SCE-UA和GA算法率定流域12025000"
})

# 结果: 4个子任务（2模型×2算法）
```

### 5. 扩展分析（代码生成）

```python
result = orchestrator.process({
    "query": "率定后计算径流系数并绘制FDC曲线"
})

# 结果: 生成自定义分析代码
```

---

## 🔖 Checkpoint 集成

Orchestrator 自动集成 checkpoint 功能：

```python
# 启用 checkpoint
orchestrator = Orchestrator(
    llm_interface=llm,
    enable_checkpoint=True  # ← 默认启用
)

# 执行长时间任务
result = orchestrator.process({
    "query": "重复率定20次"
})

# 执行到第10次时 Ctrl+C 中断
# checkpoint 自动保存进度

# 稍后恢复
orchestrator.resume_session(workspace_path)
result = orchestrator.process({"query": "..."})
# ✅ 只执行剩余10次，跳过已完成的10次
```

### Checkpoint 文件位置

```
results/
└── session_20250125_120000_abc/
    ├── checkpoint.json          # ← checkpoint状态
    ├── intent_result.json
    ├── task_plan.json
    ├── config_1.json
    ├── config_2.json
    └── ...
```

---

## 📤 返回结果结构

```python
result = {
    "success": True,
    "session_id": "session_20250125_120000_abc",
    "workspace": "/path/to/results/session_xxx",

    # Step 1: Intent
    "intent": {
        "intent_result": {
            "task_type": "repeated_calibration",
            "model_name": "gr4j",
            "basin_id": "12025000",
            ...
        }
    },

    # Step 2: Task Plan
    "task_plan": {
        "subtasks": [
            {"task_id": "task_1", "description": "..."},
            {"task_id": "task_2", "description": "..."},
            ...
        ]
    },

    # Step 3: Configs
    "configs": [
        {"task_id": "task_1", "config": {...}},
        {"task_id": "task_2", "config": {...}},
        ...
    ],

    # Step 4: Execution Results
    "execution_results": [
        {
            "success": True,
            "task_id": "task_1",
            "result": {
                "best_params": {...},
                "metrics": {"NSE": 0.68, "RMSE": 2.5},
                ...
            }
        },
        ...
    ],

    # Step 5: Analysis
    "analysis": {
        "analysis": {
            "quality": "good",
            "recommendations": ["建议1", "建议2"]
        }
    },

    # Summary
    "summary": "任务类型: REPEATED_CALIBRATION\n...",
    "elapsed_time": 125.3
}
```

---

## 🧪 测试

### 运行测试

```bash
# 测试统一接口功能
python test/test_orchestrator_unified.py
```

### 测试覆盖

1. ✅ 单任务场景
2. ✅ 多任务场景（重复率定）
3. ✅ Checkpoint 集成
4. ✅ 5-Agent 流程完整性

---

## 🆚 对比：旧架构 vs 新架构

### 旧架构（不统一）

```
experiment/BaseExperiment (5-Agent)  ← 用户层，完整流程
hydroagent/Orchestrator (4-Agent)    ← 系统内部，不完整
    ❌ 两套流程并存
    ❌ 没有统一入口
    ❌ Orchestrator 不支持多任务
```

### 新架构（统一）

```
experiment/BaseExperiment            ← 用户层封装（现在内部调用Orchestrator）
hydroagent/Orchestrator (5-Agent)    ← ⭐ 系统唯一入口，完整流程
    ✅ 统一接口
    ✅ 支持多任务
    ✅ 集成 checkpoint
    ✅ 完整的 5-Agent 流程
```

---

## 🎯 最佳实践

### 1. 始终使用 Orchestrator

```python
# ✅ 推荐：使用 Orchestrator
from hydroagent.agents.orchestrator import Orchestrator
orchestrator = Orchestrator(...)
result = orchestrator.process({"query": "..."})

# ❌ 不推荐：直接调用单个 Agent
from hydroagent.agents.intent_agent import IntentAgent
intent_agent = IntentAgent(...)  # 缺少后续流程
```

### 2. 启用 Checkpoint（长时间任务）

```python
# 长时间任务（批量、重复）：启用 checkpoint
orchestrator = Orchestrator(
    llm_interface=llm,
    enable_checkpoint=True  # ← 必须启用
)
```

### 3. 使用 Mock 模式加快开发

```python
# 开发/测试阶段：使用 Mock 模式
result = orchestrator.process({
    "query": "...",
    "use_mock": True  # ← 不调用真实 hydromodel
})
```

---

## 📚 相关文档

- [Checkpoint 系统文档](CHECKPOINT_SYSTEM.md)
- [系统架构文档](ARCHITECTURE_FINAL.md)
- [测试指南](TESTING_GUIDE.md)

---

**最后更新**: 2025-01-25
**维护者**: HydroAgent Team
