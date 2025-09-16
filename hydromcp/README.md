# 水文模型MCP工具系统

这是一个基于MCP (Model Context Protocol) 的水文模型工具系统，允许Ollama等本地LLM通过MCP协议使用水文建模工具。

## 系统架构

```
MCP工具系统
├── 服务端 (server.py)         - 暴露水文工具为MCP服务
├── 客户端 (client.py)         - Agent连接和使用MCP工具
├── 工具实现 (tools.py)        - 核心水文建模功能
├── 任务分发器 (task_dispatcher.py) - 智能任务分类和路径选择
├── 任务处理器 (task_handlers.py)   - 简单/复杂任务处理器
├── 工作流执行器               - 基于MCP的工作流执行
├── Agent集成                 - Ollama LLM与MCP的集成
└── 参数模式 (schemas.py)      - 工具参数定义
```

## 核心特性

### 🔧 MCP工具
- **get_model_params**: 获取水文模型参数信息
- **prepare_data**: 准备和预处理水文数据
- **calibrate_model**: 率定水文模型参数
- **evaluate_model**: 评估模型性能

### 🤖 智能Agent
- 支持直接工具调用模式
- 支持智能工作流模式
- 智能任务分发和路径选择
- 自动意图识别和工具选择
- 与本地Ollama模型集成

### 🧠 任务分发器
- 自动判断任务复杂度（简单/复杂/未知）
- 智能选择执行路径（MCP工具/代码生成/人工审查）
- 基于LLM的任务分类和置信度评估
- 支持多种任务类别识别

### ⚡ 工作流支持
- 基于用户查询生成工作流
- MCP工具的自动编排执行
- 依赖关系管理
- 错误处理和重试机制

## 快速开始

### 1. 安装依赖

```bash
# 基础依赖
pip install langchain-ollama pydantic

# MCP依赖 (可选)
pip install model-context-protocol
```

### 2. 启动MCP服务器

```python
# 方式1: 直接模式 (推荐用于开发)
from MCP.server import hydro_mcp_server

# 获取可用工具
tools = hydro_mcp_server.get_available_tools()
print(f"可用工具: {[tool['name'] for tool in tools]}")

# 直接调用工具
result = await hydro_mcp_server.call_tool_direct(
    "get_model_params", 
    {"model_name": "gr4j"}
)
```

```bash
# 方式2: 外部进程模式
python MCP/server.py
```

### 3. 使用MCP客户端

```python
import asyncio
from MCP.client import HydroMCPClient

async def main():
    # 创建客户端
    client = HydroMCPClient()  # 直接模式
    
    # 连接服务器
    await client.connect()
    
    # 调用工具
    result = await client.call_tool(
        "get_model_params", 
        {"model_name": "gr4j"}
    )
    
    print(f"结果: {result}")
    await client.disconnect()

asyncio.run(main())
```

### 4. 使用智能Agent（带任务分发器）

```python
import asyncio
from hydromcp import create_mcp_agent

async def main():
    # 创建Agent
    agent = await create_mcp_agent(
        llm_model="granite3-dense:8b",
        enable_workflow=True,
        enable_debug=True
    )
    
    # 简单任务 - 会被分发到MCP工具
    result = await agent.chat("我想获取GR4J模型的参数信息")
    print(f"执行类型: {result['execution_type']}")  # simple_task
    print(f"Agent回复: {result['response']}")
    
    # 复杂任务 - 会被分发到代码生成器
    result = await agent.chat("请绘制一个流量过程线图")
    print(f"执行类型: {result['execution_type']}")  # complex_task
    print(f"生成工具: {result['task_result'].get('generated_tools', [])}")
    
    await agent.cleanup()

asyncio.run(main())
```

### 5. 使用任务分发器

```python
import asyncio
from hydromcp import TaskDispatcher, TaskComplexity
from langchain_ollama import ChatOllama

async def main():
    # 创建分发器
    llm = ChatOllama(model="granite3-dense:8b", temperature=0.1)
    dispatcher = TaskDispatcher(llm)
    
    # 分析任务
    classification, strategy = await dispatcher.dispatch_task("绘制流量过程线图")
    
    print(f"任务复杂度: {classification.complexity.value}")
    print(f"任务类别: {classification.category.value}")
    print(f"置信度: {classification.confidence}")
    print(f"执行策略: {strategy['execution_type']}")
    print(f"推理: {classification.reasoning}")

asyncio.run(main())
```

### 6. 执行工作流

```python
import asyncio
from MCP.workflow_executor import execute_workflow_with_mcp
from workflow.workflow_types import WorkflowPlan, WorkflowStep, StepType

async def main():
    # 创建工作流
    workflow = WorkflowPlan(
        plan_id="test_001",
        name="获取模型参数",
        description="测试工作流",
        steps=[
            WorkflowStep(
                step_id="step_1",
                name="获取GR4J参数",
                description="获取GR4J模型参数信息",
                step_type=StepType.TOOL_CALL,
                tool_name="get_model_params",
                parameters={"model_name": "gr4j"},
                dependencies=[],
                conditions={},
                retry_count=0,
                timeout=30
            )
        ],
        user_query="获取GR4J模型参数",
        expanded_query="",
        context="测试"
    )
    
    # 执行工作流
    result = await execute_workflow_with_mcp(workflow, enable_debug=True)
    print(f"执行结果: {result}")

asyncio.run(main())
```

## 工具详细说明

### get_model_params
获取指定水文模型的参数信息

**参数:**
- `model_name` (必需): 模型名称，支持 "gr4j", "xaj", "hymod" 等

**返回:**
```json
{
    "success": true,
    "model_name": "gr4j",
    "param_names": ["x1", "x2", "x3", "x4"],
    "param_ranges": [[1, 3000], [0, 30], [1, 300], [0.5, 4]],
    "param_count": 4
}
```

### prepare_data
准备和预处理水文数据

**参数:**
- `data_dir` (必需): 数据目录路径
- `target_data_scale` (可选): 时间尺度，默认 "D" (日尺度)

**返回:**
```json
{
    "success": true,
    "message": "数据准备完成，已转换为nc格式",
    "data_dir": "/path/to/data",
    "data_scale": "D"
}
```

### calibrate_model
率定水文模型参数

**参数:**
- `model_name` (必需): 模型名称
- `data_dir` (必需): 数据目录
- `exp_name` (可选): 实验名称
- `calibrate_period` (可选): 率定时间段
- `test_period` (可选): 测试时间段
- 其他配置参数...

**返回:**
```json
{
    "success": true,
    "message": "模型 gr4j 率定完成",
    "result_dir": "/path/to/results",
    "exp_name": "model_calibration",
    "model_name": "gr4j"
}
```

### evaluate_model
评估已率定模型的性能

**参数:**
- `result_dir` (必需): 率定结果目录
- `exp_name` (必需): 实验名称
- `model_name` (可选): 模型名称
- `cv_fold` (可选): 交叉验证折数

**返回:**
```json
{
    "success": true,
    "message": "模型 gr4j 评估完成",
    "model_name": "gr4j",
    "exp_name": "model_calibration",
    "metrics": {
        "训练期R2": "0.8543",
        "测试期R2": "0.7891"
    }
}
```

## 测试

运行完整的测试套件：

```bash
python test/test_mcp_workflow.py
```

测试包括：
- MCP服务器功能
- MCP客户端连接
- 工作流执行器
- Agent集成
- 完整工作流流程

## 配置选项

### Agent配置
```python
agent = MCPAgent(
    llm_model="granite3-dense:8b",    # Ollama模型名称
    server_command=None,              # MCP服务器命令，None=直接模式
    enable_workflow=True,             # 是否启用工作流
    enable_debug=False                # 是否启用调试
)
```

### 工作流执行器配置
```python
executor = MCPWorkflowExecutor(
    server_command=None,              # MCP服务器命令
    enable_debug=False                # 是否启用调试
)
```

## 与原LangChain工具的对比

| 特性 | LangChain工具 | MCP工具 |
|------|---------------|---------|
| 集成方式 | 函数级集成 | 协议级集成 |
| 模型支持 | LangChain生态 | 任何支持MCP的模型 |
| 工具发现 | 静态定义 | 动态发现 |
| 参数验证 | Pydantic | JSON Schema |
| 错误处理 | Python异常 | 结构化响应 |
| 扩展性 | 中等 | 很好 |

## 故障排除

### 常见问题

1. **MCP库未安装**
   ```
   解决方案: pip install model-context-protocol
   或使用直接模式（无需MCP库）
   ```

2. **Ollama模型未启动**
   ```
   解决方案: 确保Ollama服务运行并拉取了相应模型
   ollama pull granite3-dense:8b
   ```

3. **水文模型模块导入失败**
   ```
   解决方案: 检查hydromodel包是否正确安装
   确保所有依赖都已安装
   ```

4. **数据路径不存在**
   ```
   解决方案: 确保data/camels_11532500目录存在
   或在调用时提供正确的数据路径
   ```

### 调试技巧

1. 启用调试模式
2. 检查日志输出
3. 使用测试套件验证组件
4. 单独测试每个工具

## 扩展开发

### 添加新工具

1. 在 `tools.py` 中实现工具方法
2. 在 `schemas.py` 中定义参数模式
3. 在 `server.py` 中注册工具
4. 更新测试用例

### 自定义Agent行为

继承 `MCPAgent` 类并重写相关方法：

```python
class CustomMCPAgent(MCPAgent):
    async def _should_use_workflow(self, user_message: str) -> bool:
        # 自定义工作流判断逻辑
        return custom_logic(user_message)
    
    async def _analyze_and_select_tool(self, user_message: str):
        # 自定义工具选择逻辑
        return custom_tool_selection(user_message)
```

## 未来发展

- [ ] 支持更多水文模型
- [ ] 增强工作流依赖处理
- [ ] 添加实时执行监控
- [ ] 支持分布式执行
- [ ] 集成更多LLM平台
