# HydroAgent Orchestrator & System API Documentation

## 概述

HydroAgent是一个基于多智能体架构的水文模型自动率定系统。Orchestrator（中央编排器）是系统的核心，负责协调4个子智能体完成完整的水文建模任务流程。

## 系统架构

### 4-Agent管道

```
User Query
    ↓
┌───────────────────────────────────────────────┐
│            Orchestrator (中央编排器)            │
├───────────────────────────────────────────────┤
│  1. IntentAgent   (意图分析)                   │
│      - 解析用户意图                            │
│      - 提取模型、流域、时间等信息                │
│      ↓                                        │
│  2. ConfigAgent   (配置生成)                   │
│      - 生成hydromodel配置                      │
│      - 验证配置完整性                           │
│      ↓                                        │
│  3. RunnerAgent   (执行引擎)                   │
│      - 调用hydromodel API                     │
│      - 监控执行进度                            │
│      ↓                                        │
│  4. DeveloperAgent (结果分析)                  │
│      - 分析模型性能                            │
│      - 生成改进建议                            │
└───────────────────────────────────────────────┘
    ↓
Result + Analysis
```

### 组件职责

| 组件 | 职责 | 输入 | 输出 |
|------|------|------|------|
| **IntentAgent** | 意图识别、信息提取 | 用户查询 | 结构化意图 |
| **ConfigAgent** | 配置生成、参数设置 | 意图结果 | hydromodel配置 |
| **RunnerAgent** | 模型执行、进度监控 | 配置 | 执行结果 |
| **DeveloperAgent** | 结果分析、建议生成 | 执行结果 | 分析报告 |
| **Orchestrator** | 协调调度、状态管理 | 查询 | 完整结果 |

## HydroAgent API

### 快速开始

#### 1. 基本使用

```python
from hydroagent import HydroAgent

# 创建HydroAgent实例
agent = HydroAgent(backend='ollama', model='qwen3:8b')

# 运行查询
result = agent.run("率定GR4J模型，流域01013500")

# 查看结果
print(result['summary'])
```

#### 2. 使用API后端

```python
from hydroagent import HydroAgent

# 使用通义千问API
agent = HydroAgent(
    backend='api',
    model='qwen-turbo',
    api_key='your-api-key',
    base_url='https://dashscope.aliyuncs.com/compatible-mode/v1'
)

result = agent.run("评估XAJ模型在流域11532500的表现")
```

#### 3. 快速运行单个查询

```python
from hydroagent import run_query

# 最简单的使用方式
result = run_query("率定GR4J模型，流域01013500")
print(result['summary'])
```

### API参考

#### HydroAgent类

```python
class HydroAgent:
    def __init__(
        self,
        llm_interface: Optional[LLMInterface] = None,
        backend: str = "ollama",
        model: str = None,
        api_key: str = None,
        base_url: str = None,
        workspace_root: Optional[Path] = None,
        show_progress: bool = True,
        enable_code_gen: bool = True,
        **kwargs
    )
```

**参数说明**:
- `backend`: LLM后端 ('ollama', 'openai', 'api')
- `model`: 模型名称 (默认: ollama用'qwen3:8b', api用'qwen-turbo')
- `api_key`: API密钥 (用于OpenAI兼容API)
- `base_url`: API基础URL
- `workspace_root`: 工作目录根路径 (默认: `results/`)
- `show_progress`: 是否显示hydromodel执行进度
- `enable_code_gen`: 是否启用代码生成功能

#### 主要方法

##### run()
```python
def run(query: str, **kwargs) -> Dict[str, Any]:
    """
    运行查询并返回结果。

    Args:
        query: 用户查询（自然语言）
        **kwargs: 额外上下文

    Returns:
        {
            "success": bool,
            "session_id": str,
            "workspace": str,
            "intent": dict,
            "config": dict,
            "execution": dict,
            "analysis": dict,
            "summary": str,
            "elapsed_time": float
        }
    """
```

##### start_session()
```python
def start_session(session_id: Optional[str] = None) -> str:
    """
    开始新会话。

    Returns:
        会话ID
    """
```

##### get_workspace()
```python
def get_workspace() -> Optional[Path]:
    """
    获取当前工作目录。

    Returns:
        工作目录路径
    """
```

##### get_history()
```python
def get_history() -> list:
    """
    获取对话历史。

    Returns:
        对话消息列表
    """
```

## 使用示例

### 示例1: 率定GR4J模型

```python
from hydroagent import HydroAgent

# 初始化
agent = HydroAgent(backend='ollama')

# 运行率定
result = agent.run("率定GR4J模型，流域01013500，使用SCE-UA算法，迭代500次")

# 检查结果
if result['success']:
    print("率定成功!")
    print(f"NSE: {result['execution']['result']['metrics']['NSE']}")
    print(f"工作目录: {result['workspace']}")
else:
    print(f"失败: {result['error']}")
```

### 示例2: 评估模型性能

```python
from hydroagent import HydroAgent

agent = HydroAgent(backend='api', model='qwen-turbo')

result = agent.run("评估XAJ模型在流域camels_11532500的表现")

# 查看分析
analysis = result['analysis']['analysis']
print(f"质量评估: {analysis['quality']}")
print("改进建议:")
for i, rec in enumerate(analysis['recommendations'], 1):
    print(f"  {i}. {rec}")
```

### 示例3: 多轮对话

```python
from hydroagent import HydroAgent

agent = HydroAgent()

# 启动会话
session_id = agent.start_session()
print(f"会话ID: {session_id}")

# 第一轮：率定
result1 = agent.run("率定GR4J模型，流域01013500")
print(result1['summary'])

# 第二轮：评估
result2 = agent.run("评估刚才率定的模型")
print(result2['summary'])

# 查看对话历史
history = agent.get_history()
print(f"共 {len(history)} 条消息")
```

### 示例4: Mock模式测试

```python
from hydroagent import HydroAgent
from unittest.mock import Mock

agent = HydroAgent()
agent.start_session()

# Mock hydromodel执行（用于测试）
mock_result = {
    "best_params": {"x1": 350.0, "x2": 0.5},
    "metrics": {"NSE": 0.85, "RMSE": 2.5}
}
agent.orchestrator.runner_agent._run_calibration = Mock(return_value=mock_result)

# 运行（不会真正调用hydromodel）
result = agent.run("率定GR4J模型")
```

## Orchestrator工作原理

### 会话管理

每个查询都在一个会话（Session）中执行。会话包含：
- **会话ID**: 唯一标识符 (格式: `session_YYYYMMDD_HHMMSS_uuid`)
- **工作目录**: 独立的结果存储目录
- **对话历史**: 所有用户查询和系统响应
- **子智能体**: 为该会话初始化的4个Agent

```python
# 会话生命周期
orchestrator = Orchestrator(llm_interface)
session_id = orchestrator.start_new_session()  # 创建会话，初始化Agents
result = orchestrator.process({"query": "..."})  # 处理查询
# 会话结束，资源保留在工作目录
```

### 数据流

```
1. User Query
   ↓
2. IntentAgent.process({"query": query})
   → {"intent_result": {...}}
   ↓
3. ConfigAgent.process(intent_result)
   → {"config": {...}}
   ↓
4. RunnerAgent.process(config_result)
   → {"result": {...}, "execution_log": {...}}
   ↓
5. DeveloperAgent.process(execution_result)
   → {"analysis": {...}}
   ↓
6. Orchestrator aggregates all results
   → Final result with summary
```

### 错误处理

Orchestrator实现了多层错误处理：

1. **Agent级别**: 每个Agent独立处理错误，返回`success=False`
2. **Pipeline级别**: Orchestrator捕获异常，记录日志
3. **继续执行**: 即使某个Agent失败，后续Agent仍会尝试执行（如DeveloperAgent可分析失败原因）

```python
# 错误处理示例
result = orchestrator.process({"query": "invalid query"})

if not result['success']:
    print(f"Pipeline failed: {result['error']}")
    # 可以检查各个阶段的结果
    if result.get('intent'):
        print("Intent analysis succeeded")
    if result.get('config'):
        print("Config generation succeeded")
    # ...
```

## 命令行工具

### run_hydro_agent.py

完整的交互式系统运行脚本。

**使用方法**:
```bash
# 交互模式
python scripts/run_hydro_agent.py

# 单查询模式
python scripts/run_hydro_agent.py "率定GR4J模型，流域01013500"

# 指定后端和模型
python scripts/run_hydro_agent.py --backend api --model qwen-turbo

# Mock模式
python scripts/run_hydro_agent.py --mock "率定GR4J模型"

# 禁用进度条（后台运行）
python scripts/run_hydro_agent.py --no-progress

# 自定义工作目录
python scripts/run_hydro_agent.py --workspace /path/to/workspace
```

**交互模式命令**:
- `quit` / `exit` / `q` - 退出程序
- `clear` - 清屏
- `help` - 显示帮助
- `history` - 显示对话历史
- `workspace` - 显示当前工作目录

## 配置

### LLM配置

在 `configs/definitions_private.py` 中配置API密钥：

```python
# OpenAI兼容API配置（如通义千问）
OPENAI_API_KEY = "your-api-key-here"
OPENAI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
```

### 工作目录结构

```
results/
└── session_20251121_153045_a1b2c3d4/
    ├── config.json              # 生成的配置
    ├── execution_log.txt        # 执行日志
    ├── results.json             # 执行结果
    ├── analysis.json            # 分析报告
    └── figures/                 # 可视化图表（如果有）
        ├── performance.png
        └── timeseries.png
```

## 性能优化

### 1. 选择合适的模型

| 模型 | 速度 | 质量 | 推荐场景 |
|------|------|------|----------|
| qwen3:8b (Ollama) | 快 | 中 | 本地开发、快速测试 |
| qwen-turbo (API) | 快 | 高 | 生产环境 |
| qwen-plus (API) | 中 | 很高 | 复杂任务 |

### 2. 禁用不需要的功能

```python
agent = HydroAgent(
    show_progress=False,     # 后台运行时禁用进度条
    enable_code_gen=False    # 不需要代码生成时禁用
)
```

### 3. Mock模式测试

在开发和测试时使用Mock模式，避免实际调用hydromodel：

```bash
python scripts/run_hydro_agent.py --mock
```

## 故障排查

### 问题1: "IntentAgent not initialized"

**原因**: 没有调用 `start_session()`

**解决**:
```python
agent = HydroAgent()
agent.start_session()  # 必须先启动会话
result = agent.run("query")
```

### 问题2: "API key not provided"

**原因**: 使用API后端但未提供API密钥

**解决**:
```python
# 方法1: 参数传递
agent = HydroAgent(backend='api', api_key='your-key')

# 方法2: 配置文件
# 在 configs/definitions_private.py 中设置 OPENAI_API_KEY
```

### 问题3: "hydromodel execution failed"

**原因**: hydromodel API调用失败（如数据不存在、参数错误）

**解决**:
1. 检查流域ID是否正确
2. 检查时间范围是否有数据
3. 使用Mock模式验证其他部分是否正常
4. 查看 `execution_log` 获取详细错误信息

## 最佳实践

### 1. 会话管理

```python
# 好的做法：为每个任务创建新会话
agent = HydroAgent()

# 任务1
agent.start_session()
result1 = agent.run("率定GR4J")

# 任务2（新会话，独立工作目录）
agent.start_session()
result2 = agent.run("评估XAJ")
```

### 2. 错误处理

```python
agent = HydroAgent()
agent.start_session()

try:
    result = agent.run("率定GR4J模型，流域01013500")

    if result['success']:
        # 处理成功结果
        workspace = result['workspace']
        # 保存或进一步分析
    else:
        # 处理失败
        logger.error(f"Pipeline failed: {result['error']}")

except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
```

### 3. 日志记录

```python
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('hydroagent.log'),
        logging.StreamHandler()
    ]
)

# 使用HydroAgent
agent = HydroAgent()
# 所有操作都会自动记录日志
```

## 开发指南

### 扩展新的Agent

如果需要添加新的Agent到管道中：

1. 创建Agent类（继承 `BaseAgent`）
2. 实现 `process()` 方法
3. 在 `Orchestrator._initialize_agents()` 中初始化
4. 在 `Orchestrator.process()` 中调用

### 自定义Orchestrator

```python
from hydroagent.agents import Orchestrator
from hydroagent.core.llm_interface import create_llm_interface

# 自定义Orchestrator
class MyOrchestrator(Orchestrator):
    def _process_intent(self, query: str):
        # 自定义意图处理逻辑
        result = super()._process_intent(query)
        # 额外处理
        return result

# 使用自定义Orchestrator
llm = create_llm_interface('ollama', 'qwen3:8b')
orchestrator = MyOrchestrator(llm_interface=llm)
```

## 相关文档

- [IntentAgent文档](intent_agent.md) - 意图分析智能体
- [ConfigAgent文档](config_agent.md) - 配置生成智能体
- [RunnerAgent文档](runner_agent.md) - 执行引擎智能体
- [DeveloperAgent文档](developer_agent.md) - 结果分析智能体
- [测试文档](tests/test_orchestrator.md) - Orchestrator测试说明

## 更新日志

### v0.2.0-alpha (2025-11-21)
- 完善Orchestrator核心逻辑
- 创建统一的HydroAgent API
- 添加会话管理和对话历史
- 实现完整的4-Agent管道
- 添加Mock模式支持
- 创建交互式运行脚本

## License

Copyright (c) 2023-2025 HydroAgent. All rights reserved.
