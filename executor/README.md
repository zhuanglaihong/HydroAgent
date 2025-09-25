# Executor 系统 - 智能工作流执行引擎

## 概述

Executor 系统是 HydroAgent 的核心执行层，负责接收 Builder 生成的工作流并智能执行。系统采用分层架构，支持简单任务直接执行和复杂任务智能分解，实现高效的水文建模工作流自动化。

## 系统架构

```
executor/
├── __init__.py                 # 包初始化
├── main.py                     # 主执行引擎
├── core/                       # 核心执行组件
│   ├── __init__.py
│   ├── workflow_receiver.py    # 工作流接收器
│   ├── task_dispatcher.py      # 智能任务分发器
│   ├── simple_executor.py      # 简单任务执行器
│   ├── complex_solver.py       # 复杂任务解决器
│   ├── react_executor.py       # React执行器 (目标导向)
│   └── llm_client.py          # LLM客户端工厂
├── models/                     # 数据模型
│   ├── __init__.py
│   ├── workflow.py            # 工作流模型
│   ├── task.py               # 任务模型
│   └── result.py             # 执行结果模型
├── tools/                      # 工具集成
│   ├── __init__.py
│   ├── base_tool.py          # 工具基类
│   ├── registry.py           # 工具注册表
│   ├── get_model_params_tool.py
│   └── prepare_data_tool.py
├── visualization/              # 结果可视化
│   ├── __init__.py
│   ├── result_visualizer.py   # 结果可视化器
│   └── chart_generator.py     # 图表生成器
└── README.md                  # 本文档
```

## 核心组件

### 1. ExecutorEngine (主执行引擎)
- **职责**: 系统统一入口，协调各个执行组件
- **功能**:
  - 工作流接收和解析
  - 智能任务分发
  - 多模式执行支持
  - 结果收集和可视化
- **接口**: `execute_workflow(workflow_data, mode) -> WorkflowResult`

### 2. WorkflowReceiver (工作流接收器)
- **职责**: 接收和解析Builder生成的工作流
- **功能**:
  - 多格式输入支持 (JSON字符串、字典、文件路径)
  - 工作流结构验证
  - Pydantic模型转换
  - 格式兼容性检查

### 3. TaskDispatcher (智能任务分发器)
- **职责**: 分析任务特征并分发到合适的执行器
- **功能**:
  - 任务类型识别 (Simple vs Complex)
  - 依赖关系分析
  - 优先级计算
  - 资源需求评估
  - 执行器负载平衡

### 4. SimpleTaskExecutor (简单任务执行器)
- **职责**: 执行简单的直接工具调用任务
- **特点**:
  - 直接工具调用，无需LLM推理
  - 快速执行，资源消耗小
  - 高可靠性，结果确定性
- **适用场景**: 参数获取、数据准备、简单计算

### 5. ComplexTaskSolver (复杂任务解决器)
- **职责**: 使用LLM+RAG智能解决复杂任务
- **功能**:
  - 任务智能分解
  - 解决方案规划
  - 分步执行管理
  - 结果整合
- **适用场景**: 模型率定、复杂分析、多步骤处理

### 6. ReactExecutor (React执行器)
- **职责**: 目标导向的反应式执行
- **功能**:
  - 目标状态监控
  - 迭代执行管理
  - 自适应调整
  - 收敛性判断
- **适用场景**: 模型优化、性能目标达成

## 执行模式

### 1. Sequential模式 (顺序执行)
```python
# 特点：严格按依赖关系顺序执行
# 适用：简单工作流，任务间依赖关系明确
execution_result = engine.execute_workflow(workflow_json, mode="sequential")
```

### 2. React模式 (反应式执行)
```python
# 特点：目标导向，支持迭代和反馈
# 适用：模型率定、优化任务
execution_result = engine.execute_workflow(workflow_json, mode="react")
```

## 任务类型系统

### 简单任务 (TaskType.SIMPLE)
```python
{
    "task_id": "get_params",
    "name": "获取模型参数",
    "type": "simple",
    "tool_name": "get_model_params_tool",
    "parameters": {"model_name": "GR4J"},
    "dependencies": [],
    "timeout": 60
}
```

**特征**:
- 必须指定具体的工具名称
- 参数结构简单明确
- 执行时间可预期
- 无需LLM推理

### 复杂任务 (TaskType.COMPLEX)
```python
{
    "task_id": "calibrate_model",
    "name": "模型参数率定",
    "type": "complex",
    "description": "使用遗传算法率定GR4J模型参数，目标NSE>0.7",
    "knowledge_query": "GR4J模型率定最佳实践",
    "parameters": {"target_metric": "nse", "threshold": 0.7},
    "dependencies": ["prepare_data"],
    "timeout": 1800
}
```

**特征**:
- 提供任务描述而非具体工具
- 支持知识库查询
- 执行时间较长
- 需要LLM智能分解

## 配置参数

执行器系统的配置参数在 `config.py` 中：

```python
# 执行器配置
EXECUTOR_MAX_CONCURRENT_TASKS = 4        # 最大并发任务数
EXECUTOR_DEFAULT_TIMEOUT = 300           # 默认超时时间(秒)
EXECUTOR_ENABLE_VISUALIZATION = True     # 启用结果可视化

# 代码生成模型配置 (用于ComplexTaskSolver)
CODER_USE_API_FIRST = True              # 优先使用API代码模型
CODER_API_MODEL = "qwen3-coder-plus"    # API代码生成模型
CODER_FALLBACK_MODEL = "deepseek-coder:6.7b"  # 本地代码模型

# 简单任务配置
SIMPLE_TASK_DEFAULT_TIMEOUT = 300       # 简单任务默认超时(秒)
SIMPLE_TASK_MAX_RETRIES = 2             # 简单任务最大重试次数

# 复杂任务配置
COMPLEX_TASK_DEFAULT_TIMEOUT = 1800     # 复杂任务默认超时(秒)
COMPLEX_TASK_MAX_ITERATIONS = 5         # 复杂任务最大迭代次数
COMPLEX_TASK_MIN_CONFIDENCE = 0.7       # 解决方案最小置信度

# React模式配置
REACT_MAX_ITERATIONS = 3                # React模式最大迭代次数
REACT_CONVERGENCE_THRESHOLD = 0.01      # 收敛判断阈值
REACT_TARGET_PATIENCE = 2               # 目标等待轮次
```

## 使用示例

### 1. 基本执行
```python
from executor.main import ExecutorEngine

# 初始化执行引擎
engine = ExecutorEngine(enable_debug=True)

# 执行工作流
result = engine.execute_workflow(workflow_json, mode="sequential")

print(f"执行状态: {result.status}")
print(f"成功率: {result.metrics.success_rate:.2%}")
```

### 2. React模式执行
```python
# React模式工作流 (包含目标配置)
react_workflow = {
    "workflow_id": "model_calibration_001",
    "mode": "react",
    "target": {
        "type": "performance_goal",
        "metric": "nse",
        "threshold": 0.7,
        "max_iterations": 3
    },
    "tasks": [...]
}

result = engine.execute_workflow(
    json.dumps(react_workflow),
    mode="react"
)

print(f"目标达成: {result.target_achieved}")
```

### 3. 带可视化的执行
```python
# 执行并生成可视化报告
result, report_path = engine.execute_workflow_with_visualization(
    workflow_json,
    mode="sequential",
    generate_visualization=True
)

if report_path:
    print(f"可视化报告: {report_path}")
```

## 工具系统

### 工具注册表
```python
from executor.tools.registry import HydroToolRegistry

# 获取工具注册表
registry = HydroToolRegistry()

# 调用工具
result = registry.call_tool("get_model_params_tool", {
    "model_name": "GR4J"
})
```

### 支持的工具

1. **get_model_params_tool**: 获取水文模型参数信息
2. **prepare_data_tool**: 数据准备和预处理
3. **calibrate_model_tool**: 模型参数率定
4. **evaluate_model_tool**: 模型性能评估

### 自定义工具
```python
from executor.tools.base_tool import BaseTool

class CustomTool(BaseTool):
    def __init__(self):
        super().__init__(name="custom_tool", description="自定义工具")

    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        # 实现具体逻辑
        return {"status": "success", "result": "..."}

# 注册工具
registry.register_tool("custom_tool", CustomTool())
```

## 数据模型

### 工作流模型
```python
class Workflow(BaseModel):
    workflow_id: str
    name: str
    description: str
    mode: WorkflowMode  # SEQUENTIAL | REACT
    tasks: List[Task]
    target: Optional[WorkflowTarget] = None
    global_settings: GlobalSettings
```

### 任务模型
```python
class Task(BaseModel):
    task_id: str
    name: str
    type: TaskType  # SIMPLE | COMPLEX
    priority: TaskPriority

    # 简单任务字段
    tool_name: Optional[str] = None
    parameters: Dict[str, Any] = {}

    # 复杂任务字段
    description: Optional[str] = None
    knowledge_query: Optional[str] = None

    # 通用字段
    dependencies: List[str] = []
    timeout: Optional[int] = None
    retry_count: int = 0
```

### 结果模型
```python
class WorkflowResult(BaseModel):
    execution_id: str
    workflow_id: str
    status: ExecutionStatus
    task_results: List[TaskResult] = []
    target_achieved: bool = False
    metrics: Optional[ExecutionMetrics] = None
    start_time: datetime
    end_time: Optional[datetime] = None
```

## 执行统计

```python
# 获取执行统计
stats = engine.task_dispatcher.get_execution_statistics()

print(f"总任务数: {stats['total_tasks']}")
print(f"成功率: {stats['success_rate']:.2%}")
print(f"执行器负载: {stats['executor_load']}")
```

## 错误处理

### 1. 任务级错误处理
- **重试机制**: 自动重试失败的任务
- **降级策略**: 复杂任务失败时尝试简化
- **依赖跳过**: 依赖失败时智能跳过后续任务

### 2. 工作流级错误处理
- **部分成功**: 支持部分任务成功的工作流
- **错误恢复**: 从失败点继续执行
- **状态持久化**: 支持执行状态的保存和恢复

## 性能优化

### 1. 并发执行
```python
# 配置最大并发数
engine.task_dispatcher.max_concurrent = 4

# 并行执行无依赖任务
ready_tasks = engine.task_dispatcher.get_ready_tasks(workflow.tasks)
```

### 2. 缓存机制
```python
# 启用工具结果缓存
registry.enable_cache(cache_ttl=3600)

# 启用LLM响应缓存
complex_solver.enable_llm_cache(cache_size=100)
```

### 3. 资源管理
```python
# 资源限制配置
resource_limits = {
    "max_memory_mb": 4096,
    "max_cpu_cores": 2,
    "max_execution_time": 3600
}
```

## 可视化功能

### 1. 执行报告生成
```python
from executor.visualization import ResultVisualizer

visualizer = ResultVisualizer()
report_path = visualizer.generate_summary_report(result, workflow)
```

### 2. 支持的可视化内容
- 工作流执行时间线
- 任务成功率统计
- 资源使用情况
- 错误分布分析
- 性能指标趋势

## 测试

Executor 系统提供完整的测试套件：

```bash
# 简单任务执行测试
python test/test_executor_simple.py

# 复杂任务执行测试
python test/test_executor_complex.py

# 格式兼容性测试
python test/test_builder_executor_integration.py
```

## 与 Builder 对接

Executor 完全兼容 Builder 生成的工作流格式：

1. **格式转换**: 自动转换Builder格式到执行器内部格式
2. **参数映射**: 智能映射工具参数
3. **模式识别**: 根据复杂度自动选择执行模式
4. **依赖处理**: 完整支持任务依赖关系

## 扩展性

### 1. 新工具集成
```python
# 继承基类实现新工具
class NewTool(BaseTool):
    def execute(self, parameters):
        # 实现工具逻辑
        pass

# 注册到系统
registry.register_tool("new_tool", NewTool())
```

### 2. 新执行模式
```python
# 扩展ExecutorEngine添加新模式
def execute_custom_mode(self, workflow):
    # 实现自定义执行逻辑
    pass
```

### 3. 自定义可视化
```python
# 扩展ResultVisualizer
class CustomVisualizer(ResultVisualizer):
    def generate_custom_chart(self, result):
        # 生成自定义图表
        pass
```

## 依赖关系

- **必需依赖**: Python 3.8+, Pydantic, asyncio
- **LLM依赖**: 配置的代码生成模型 (API或本地Ollama)
- **工具依赖**: hydroutils, hydromodel等水文建模库
- **可视化依赖**: matplotlib, plotly (可选)

Executor 系统为 HydroAgent 提供了强大而灵活的工作流执行能力，是连接工作流规划和实际执行的关键桥梁。