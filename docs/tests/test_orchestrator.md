# Orchestrator & HydroAgent System Testing Documentation

## 测试概述

本文档描述了Orchestrator（中央编排器）和HydroAgent系统API的测试方法、测试用例和使用说明。

## 测试文件

- **测试文件**: `test/test_orchestrator.py`
- **运行脚本**: `scripts/run_hydro_agent.py`
- **日志目录**: `logs/`

## 测试内容

### 测试用例列表

| # | 测试名称 | 描述 | 验证内容 |
|---|---------|------|----------|
| 1 | Orchestrator初始化 | 测试Orchestrator的基本初始化 | 名称、工作目录、会话状态 |
| 2 | 会话管理 | 测试会话的创建和子Agent初始化 | 会话ID、工作目录、子Agents |
| 3 | 完整管道 (Mock) | 测试4-Agent完整管道流程 | Intent→Config→Runner→Developer |
| 4 | HydroAgent API | 测试HydroAgent系统API | API接口、结果格式 |
| 5 | 对话历史记录 | 测试多轮对话和历史记录 | 对话存储、消息格式 |
| 6 | 错误处理 | 测试各种错误情况的处理 | 错误捕获、错误信息 |

## 测试用例详解

### 测试1: Orchestrator初始化测试

**目的**: 验证Orchestrator能正确初始化

**测试代码**:
```python
from hydroagent.agents.orchestrator import Orchestrator
from hydroagent.core.llm_interface import create_llm_interface

llm = create_llm_interface('ollama', 'qwen3:8b')
workspace_root = Path("results/test_orchestrator")

orchestrator = Orchestrator(
    llm_interface=llm,
    workspace_root=workspace_root,
    show_progress=False
)

# 验证
assert orchestrator.name == "Orchestrator"
assert orchestrator.workspace_root == workspace_root
assert orchestrator.current_session_id is None
```

**验证点**:
- ✅ Orchestrator名称正确
- ✅ 工作目录配置正确
- ✅ 初始会话为None

---

### 测试2: 会话管理测试

**目的**: 验证会话的创建、子Agent的初始化

**测试代码**:
```python
orchestrator = Orchestrator(llm_interface=llm, workspace_root=workspace_root)

# 启动会话
session_id = orchestrator.start_new_session()

# 验证会话
assert session_id is not None
assert orchestrator.current_workspace.exists()

# 验证子Agents
assert orchestrator.intent_agent is not None
assert orchestrator.config_agent is not None
assert orchestrator.runner_agent is not None
assert orchestrator.developer_agent is not None
```

**会话ID格式**:
```
session_20251121_153045_a1b2c3d4
        ^      ^     ^      ^
        |      |     |      |
       年月日  时分秒  UUID(前8位)
```

**验证点**:
- ✅ 会话ID生成正确
- ✅ 工作目录创建成功
- ✅ 4个子Agent全部初始化

---

### 测试3: 完整管道测试 (Mock)

**目的**: 验证4-Agent完整管道流程

**测试数据**:
```python
# Mock IntentAgent输出
MOCK_INTENT_RESULT = {
    "success": True,
    "intent_result": {
        "intent": "calibration",
        "model_name": "gr4j",
        "basin_id": "01013500",
        "algorithm": "SCE_UA",
        "confidence": 0.95
    }
}

# Mock ConfigAgent输出
MOCK_CONFIG_RESULT = {
    "success": True,
    "config": {"model": "gr4j", "basin_id": "01013500"},
    "config_summary": "GR4J model configuration"
}

# Mock RunnerAgent输出
MOCK_RUNNER_SUCCESS_RESULT = {
    "success": True,
    "mode": "calibrate",
    "result": {
        "metrics": {"NSE": 0.85, "RMSE": 2.5},
        "best_params": {"x1": 350.0, "x2": 0.5}
    }
}

# Mock DeveloperAgent输出
MOCK_DEVELOPER_RESULT = {
    "success": True,
    "analysis": {
        "quality": "优秀 (Excellent)",
        "metrics": {"NSE": 0.85},
        "recommendations": []
    }
}
```

**测试代码**:
```python
orchestrator.start_new_session()

# Mock所有子Agents
orchestrator.intent_agent.process = Mock(return_value=MOCK_INTENT_RESULT)
orchestrator.config_agent.process = Mock(return_value=MOCK_CONFIG_RESULT)
orchestrator.runner_agent.process = Mock(return_value=MOCK_RUNNER_SUCCESS_RESULT)
orchestrator.developer_agent.process = Mock(return_value=MOCK_DEVELOPER_RESULT)

# 运行管道
result = orchestrator.process({"query": "率定GR4J模型，流域01013500"})

# 验证
assert result["success"]
assert "intent" in result
assert "config" in result
assert "execution" in result
assert "analysis" in result
assert "summary" in result
```

**数据流图**:
```
Query: "率定GR4J模型，流域01013500"
    ↓
IntentAgent
    → intent_result (intent=calibration, model=gr4j, basin=01013500)
    ↓
ConfigAgent
    → config (完整配置字典)
    ↓
RunnerAgent
    → execution_result (metrics, params)
    ↓
DeveloperAgent
    → analysis (quality, recommendations)
    ↓
Orchestrator aggregates
    → Final result with summary
```

**验证点**:
- ✅ 管道成功执行
- ✅ 4个阶段的结果都存在
- ✅ 生成了summary
- ✅ 记录了会话ID和工作目录

---

### 测试4: HydroAgent API测试

**目的**: 验证HydroAgent系统API的易用性和正确性

**测试代码**:
```python
from hydroagent import HydroAgent

# 创建HydroAgent
agent = HydroAgent(backend='ollama', model='qwen3:8b', show_progress=False)

# 启动会话并Mock
agent.start_session()
agent.orchestrator.intent_agent.process = Mock(return_value=MOCK_INTENT_RESULT)
agent.orchestrator.config_agent.process = Mock(return_value=MOCK_CONFIG_RESULT)
agent.orchestrator.runner_agent.process = Mock(return_value=MOCK_RUNNER_SUCCESS_RESULT)
agent.orchestrator.developer_agent.process = Mock(return_value=MOCK_DEVELOPER_RESULT)

# 运行查询
result = agent.run("率定GR4J模型，流域01013500")

# 验证
assert result["success"]
assert "summary" in result
```

**API调用示例**:
```python
# 方式1: 使用HydroAgent类
agent = HydroAgent()
result = agent.run("query")

# 方式2: 使用工厂函数
from hydroagent import create_hydro_agent
agent = create_hydro_agent(backend='ollama')
result = agent.run("query")

# 方式3: 快速运行单个查询
from hydroagent import run_query
result = run_query("query")
```

**验证点**:
- ✅ HydroAgent API初始化正确
- ✅ `run()` 方法正确执行
- ✅ `get_workspace()` 返回正确路径
- ✅ 返回格式符合预期

---

### 测试5: 对话历史记录测试

**目的**: 验证多轮对话和历史记录功能

**测试代码**:
```python
agent = HydroAgent()
agent.start_session()

# Mock agents
# ...

# 运行多个查询
agent.run("率定GR4J模型")
agent.run("评估模型性能")

# 获取历史
history = agent.get_history()

# 验证
assert len(history) >= 4  # 至少2个查询 + 2个响应

user_messages = [msg for msg in history if msg["role"] == "user"]
assert len(user_messages) >= 2
```

**历史记录格式**:
```python
[
    {
        "role": "user",
        "content": "率定GR4J模型",
        "timestamp": "2025-11-21T15:30:45.123456"
    },
    {
        "role": "assistant",
        "content": "任务类型: CALIBRATION\n模型: gr4j...",
        "timestamp": "2025-11-21T15:30:52.987654"
    },
    ...
]
```

**验证点**:
- ✅ 历史记录正确保存
- ✅ 包含用户和助手消息
- ✅ 时间戳格式正确
- ✅ 内容完整

---

### 测试6: 错误处理测试

**目的**: 验证各种错误情况的处理

**测试场景**:

#### 场景1: IntentAgent失败
```python
agent.orchestrator.intent_agent.process = Mock(return_value={
    "success": False,
    "error": "Intent parsing failed"
})

result = agent.run("invalid query")

assert not result["success"]
assert "error" in result
```

#### 场景2: RunnerAgent执行失败
```python
agent.orchestrator.runner_agent.process = Mock(return_value={
    "success": False,
    "mode": "calibrate",
    "error": "hydromodel execution failed"
})

result = agent.run("query")

# 管道继续执行到DeveloperAgent
assert "analysis" in result  # DeveloperAgent可以分析失败原因
```

#### 场景3: 空查询
```python
result = agent.run("")

assert not result["success"]
assert "No query provided" in result["error"]
```

**验证点**:
- ✅ 错误被正确捕获
- ✅ 返回包含error字段
- ✅ 日志记录错误信息
- ✅ 即使某个Agent失败，管道仍继续（如果可能）

---

## 运行测试

### 方法1: 直接运行测试脚本

```bash
# 运行所有测试
python test/test_orchestrator.py
```

**预期输出**:
```
======================================================================
Orchestrator & HydroAgent 单元测试套件
======================================================================
日志文件: logs/test_orchestrator_20251121_153045.log

======================================================================
Test Case 1: Orchestrator 初始化测试
======================================================================
✅ Orchestrator 初始化测试通过

======================================================================
Test Case 2: 会话管理测试
======================================================================
✅ 会话管理测试通过
   Session ID: session_20251121_153045_a1b2c3d4
   Workspace: D:\project\Agent\HydroAgent\results\test_orchestrator\...

...

======================================================================
测试总结
======================================================================
1. ✅ PASS - Orchestrator初始化
2. ✅ PASS - 会话管理
3. ✅ PASS - 完整管道 (Mock)
4. ✅ PASS - HydroAgent API
5. ✅ PASS - 对话历史记录
6. ✅ PASS - 错误处理

总计: 6/6 通过
成功率: 100.0%
======================================================================

详细日志: logs/test_orchestrator_20251121_153045.log
```

### 方法2: 使用交互式系统测试

```bash
# 启动交互式系统
python scripts/run_hydro_agent.py

# 或者使用Mock模式
python scripts/run_hydro_agent.py --mock
```

**交互式测试流程**:
```
╔══════════════════════════════════════════════════════════════╗
║                      HydroAgent System                       ║
║          Intelligent Hydrological Model Calibration          ║
╚══════════════════════════════════════════════════════════════╝

Initializing HydroAgent system...
✅ HydroAgent initialized
   Backend: ollama (qwen3:8b)
   Workspace: D:\project\Agent\HydroAgent\results

✅ Session started: session_20251121_153045_a1b2c3d4

══════════════════════════════════════════════════════════════
Interactive Mode - Enter your queries below.
Commands:
  'quit' or 'exit' - Exit the program
  'history' - Show conversation history
  'workspace' - Show current workspace
══════════════════════════════════════════════════════════════

[Query #1]
You: 率定GR4J模型，流域01013500

🚀 Processing query through 4-Agent pipeline...

══════════════════════════════════════════════════════════════
【Pipeline Result】
──────────────────────────────────────────────────────────────
Status: ✅ SUCCESS
Time: 12.3s
Session: session_20251121_153045_a1b2c3d4
Workspace: D:\project\Agent\HydroAgent\results\...

Summary:
──────────────────────────────────────────────────────────────
任务类型: CALIBRATION
模型: gr4j, 流域: 01013500

性能指标:
  NSE: 0.85
  RMSE: 2.5

质量评估: 优秀 (Excellent)
──────────────────────────────────────────────────────────────

[Query #2]
You: history

Conversation history (4 messages):
──────────────────────────────────────────────────────────────
1. [user] 率定GR4J模型，流域01013500...
2. [assistant] 任务类型: CALIBRATION...
──────────────────────────────────────────────────────────────
```

---

## 测试数据说明

### Mock数据设计原则

1. **真实性**: Mock数据模拟真实的Agent输出格式
2. **完整性**: 包含所有必需字段
3. **可变性**: 可以修改Mock数据测试不同场景

### Mock数据示例

#### 成功的率定结果
```python
MOCK_RUNNER_SUCCESS_RESULT = {
    "success": True,
    "mode": "calibrate",
    "result": {
        "status": "success",
        "metrics": {
            "NSE": 0.85,      # 优秀
            "RMSE": 2.5,
            "KGE": 0.82,
            "PBIAS": 5.2
        },
        "best_params": {
            "x1": 350.0,
            "x2": 0.5,
            "x3": 100.0,
            "x4": 2.0
        },
        "output_files": [
            "results/calibrated_params.json",
            "results/performance_plot.png"
        ]
    },
    "execution_log": {
        "stdout": "Calibration completed successfully",
        "stderr": ""
    }
}
```

#### 质量较低的结果（用于测试建议生成）
```python
MOCK_LOW_QUALITY_RESULT = {
    "success": True,
    "mode": "calibrate",
    "result": {
        "metrics": {
            "NSE": 0.55,      # 可接受但不理想
            "PBIAS": 30.0     # 偏差较大
        }
    }
}

# DeveloperAgent应该生成改进建议
```

#### 失败的执行结果
```python
MOCK_RUNNER_FAILURE_RESULT = {
    "success": False,
    "mode": "calibrate",
    "error": "Configuration error: invalid parameter range",
    "traceback": "Traceback...",
    "execution_log": {
        "stdout": "",
        "stderr": "Error: invalid parameter range"
    }
}
```

---

## 测试质量标准

### 通过标准

✅ **全部测试通过**: 所有6个测试用例的断言都成功

### 关键验证点

1. **初始化**: 所有组件正确初始化
2. **数据流**: 数据在4个Agent之间正确传递
3. **错误处理**: 错误被正确捕获和报告
4. **结果格式**: 返回结果符合API规范
5. **日志记录**: 所有操作都有日志记录

---

## 常见测试问题

### 问题1: "LLM timeout"

**症状**: 测试卡住，等待LLM响应

**原因**: Ollama服务未启动或响应慢

**解决**:
```bash
# 检查Ollama状态
ollama list

# 如果未启动，启动Ollama
ollama serve

# 或者使用Mock模式测试
```

### 问题2: "Agent not initialized"

**症状**: `RuntimeError: IntentAgent not initialized`

**原因**: 忘记调用 `start_new_session()`

**解决**:
```python
orchestrator = Orchestrator(llm_interface=llm)
orchestrator.start_new_session()  # 必须调用
result = orchestrator.process({"query": "..."})
```

### 问题3: 测试日志过多

**症状**: 控制台输出过多日志

**解决**:
```python
# 调整日志级别
logging.basicConfig(level=logging.WARNING)  # 只显示WARNING及以上
```

---

## 扩展测试

### 添加新的测试用例

```python
def test_custom_scenario():
    """测试7: 自定义场景"""
    print_test_header(7, "自定义场景测试")

    # 测试代码
    agent = HydroAgent()
    # ...

    # 断言
    assert result["success"]

    print("✅ 自定义测试通过")
    return result

# 在run_all_tests()中添加
try:
    test_custom_scenario()
    results.append(("自定义场景", True, None))
except Exception as e:
    results.append(("自定义场景", False, str(e)))
```

### 集成测试建议

对于完整的端到端测试（包括真实hydromodel执行）：

```bash
# 使用真实hydromodel测试（需要数据）
python scripts/run_full_agent_pipeline.py --backend api "率定GR4J模型，流域01013500"

# 对比Mock和真实结果
python scripts/run_hydro_agent.py --mock "query" > mock_output.txt
python scripts/run_hydro_agent.py "query" > real_output.txt
diff mock_output.txt real_output.txt
```

---

## 性能测试

### 测试管道性能

```python
import time

agent = HydroAgent()
agent.start_session()

queries = [
    "率定GR4J模型，流域01013500",
    "评估XAJ模型，流域11532500",
    "模拟GR5J模型"
]

for query in queries:
    start = time.time()
    result = agent.run(query)
    elapsed = time.time() - start

    print(f"Query: {query[:30]}... - Time: {elapsed:.2f}s")
```

**性能基准** (Mock模式):
- Intent: < 1s
- Config: < 1s
- Runner: < 0.1s (Mock)
- Developer: < 0.5s
- **总计**: < 3s

**性能基准** (真实模式):
- Runner: 30s - 5min (取决于hydromodel复杂度)
- **总计**: 30s - 5min

---

## 相关文档

- [Orchestrator API文档](../orchestrator.md)
- [HydroAgent系统架构](../architecture.md)
- [IntentAgent测试](test_intent_agent.md)
- [ConfigAgent测试](test_config_agent.md)
- [RunnerAgent测试](test_runner_agent.md)
- [DeveloperAgent测试](test_developer_agent.md)

---

## 更新日志

### 2025-11-21
- 创建Orchestrator和HydroAgent系统测试文档
- 添加6个核心测试用例
- 提供Mock数据示例和测试指南

## License

Copyright (c) 2023-2025 HydroAgent. All rights reserved.
