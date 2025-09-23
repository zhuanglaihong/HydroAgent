# HydroTool 新架构设计文档

## 📋 概述

HydroTool 作为 HydroAgent 系统的**智能工具执行层**，负责接收结构化工作流并智能执行。新架构采用任务驱动、目标导向的设计理念，支持简单任务直接执行和复杂任务智能解决。

## 🏗️ 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    HydroTool 执行层                          │
├─────────────────────────────────────────────────────────────┤
│  工作流接收器 (WorkflowReceiver)                             │
│  ├── JSON格式工作流解析                                      │
│  ├── 工作流验证和预处理                                      │
│  └── 执行计划生成                                           │
├─────────────────────────────────────────────────────────────┤
│  工作流执行引擎 (WorkflowExecutor)                           │
│  ├── 执行模式策略 (Execution Strategy)                      │
│  │   ├── Sequential Mode (线性执行模式)                     │
│  │   └── React Mode (目标导向迭代执行模式)                  │
│  ├── 任务分发器 (TaskDispatcher)                           │
│  │   ├── 任务复杂度判断（基于预设标志）                     │
│  │   ├── 简单任务 → 直接工具执行                           │
│  │   └── 复杂任务 → 智能解决方案生成                       │
│  └── 任务处理器 (Task Processors)                          │
│      ├── SimpleTaskExecutor (简单任务执行器)               │
│      │   ├── 工具注册表管理                                │
│      │   ├── 参数验证和转换                                │
│      │   └── 水文工具调用 (准备数据/率定/评估)              │
│      └── ComplexTaskSolver (复杂任务解决器)                │
│          ├── LLM + HydroRAG 知识检索                      │
│          ├── 工具调用序列生成 (推荐方案)                   │
│          ├── 受限代码片段生成 (备选方案)                   │
│          └── 安全执行和验证                                │
├─────────────────────────────────────────────────────────────┤
│  结果管理器 (ResultManager)                                │
│  ├── 执行状态跟踪                                           │
│  ├── 成功率统计                                             │
│  ├── 结果整理和报告                                         │
│  └── 日志和调试信息                                         │
└─────────────────────────────────────────────────────────────┘
```

### 🔄 层级关系说明

**正确的层级关系**：
- **工作流级别**: Sequential/React执行模式
- **任务级别**: Simple/Complex任务处理器
- **工具级别**: 具体的水文建模工具

React模式是工作流的执行策略，负责：
- 设定目标和收敛条件
- 评估当前结果是否达标
- 决定是否需要调整参数重新执行
- 控制迭代次数和收敛逻辑

而Simple/Complex任务处理器专注于单个任务的执行：
- Simple: 直接调用现有工具
- Complex: 通过LLM+RAG生成解决方案

## 📊 工作流数据结构

### 工作流定义 (JSON格式)

```json
{
  "workflow_id": "wf_20250101_001",
  "name": "GR4J模型率定和评估",
  "description": "完整的GR4J模型率定、评估和优化工作流",
  "mode": "sequential|react",
  "target": {
    "type": "performance_goal",
    "metric": "NSE",
    "threshold": 0.7,
    "max_iterations": 5
  },
  "tasks": [
    {
      "task_id": "task_001",
      "name": "数据准备",
      "type": "simple|complex",
      "priority": 1,
      "tool_name": "prepare_data",
      "parameters": {
        "data_dir": "data/camels_11532500",
        "target_data_scale": "D"
      },
      "dependencies": [],
      "success_criteria": {
        "expected_outputs": ["processed_data_path"],
        "validation_rules": ["file_exists", "data_format_valid"]
      }
    },
    {
      "task_id": "task_002",
      "name": "模型率定",
      "type": "simple",
      "priority": 2,
      "tool_name": "calibrate_model",
      "parameters": {
        "model_name": "gr4j",
        "data_dir": "${task_001.output.data_dir}",
        "calibrate_period": ["2013-01-01", "2018-12-31"]
      },
      "dependencies": ["task_001"],
      "success_criteria": {
        "expected_outputs": ["calibration_results", "model_parameters"],
        "validation_rules": ["nse_above_threshold"]
      }
    },
    {
      "task_id": "task_003",
      "name": "高级参数优化",
      "type": "complex",
      "priority": 3,
      "description": "使用多目标优化算法进一步优化模型参数",
      "knowledge_query": "multi-objective optimization for hydrological models",
      "dependencies": ["task_002"],
      "success_criteria": {
        "expected_outputs": ["optimized_parameters"],
        "validation_rules": ["pareto_front_improvement"]
      }
    }
  ],
  "global_settings": {
    "error_handling": "continue_on_error|stop_on_error",
    "logging_level": "INFO",
    "timeout": 3600,
    "checkpoint_enabled": true
  }
}
```

### 执行结果结构

```json
{
  "execution_id": "exec_20250101_001",
  "workflow_id": "wf_20250101_001",
  "status": "running|completed|failed|paused",
  "start_time": "2025-01-01T10:00:00Z",
  "end_time": "2025-01-01T11:30:00Z",
  "total_duration": 5400,
  "task_results": [
    {
      "task_id": "task_001",
      "status": "completed|failed|skipped",
      "start_time": "2025-01-01T10:00:00Z",
      "end_time": "2025-01-01T10:15:00Z",
      "duration": 900,
      "outputs": {
        "data_dir": "result/processed_data_20250101",
        "records_count": 4018,
        "validation_passed": true
      },
      "error": null,
      "retry_count": 0
    }
  ],
  "metrics": {
    "total_tasks": 3,
    "completed_tasks": 2,
    "failed_tasks": 0,
    "success_rate": 0.67,
    "average_task_duration": 1200
  },
  "react_iterations": [
    {
      "iteration": 1,
      "target_achieved": false,
      "current_metric": 0.65,
      "adjustments_made": ["increased_calibration_epochs"],
      "reason": "NSE below threshold (0.7)"
    }
  ],
  "final_report": {
    "overall_success": true,
    "target_achieved": true,
    "final_metric_value": 0.73,
    "key_achievements": [
      "成功率定GR4J模型",
      "NSE达到0.73，超过目标阈值0.7",
      "优化参数提高了模型性能"
    ],
    "recommendations": [
      "建议在其他流域验证参数的可移植性",
      "考虑添加更多验证指标"
    ]
  }
}
```

## 🔧 核心组件设计

### 1. 工作流接收器 (WorkflowReceiver)

```python
class WorkflowReceiver:
    """工作流接收和解析器"""

    def receive_workflow(self, workflow_data: Union[str, Dict]) -> Workflow:
        """接收并解析工作流"""

    def validate_workflow(self, workflow: Workflow) -> ValidationResult:
        """验证工作流的完整性和正确性"""

    def preprocess_workflow(self, workflow: Workflow) -> Workflow:
        """预处理工作流，解决依赖关系和参数替换"""
```

### 2. 任务分发器 (TaskDispatcher)

```python
class TaskDispatcher:
    """智能任务分发器"""

    def dispatch_task(self, task: Task) -> TaskHandler:
        """根据任务类型分发到相应的处理器"""

    def analyze_task_complexity(self, task: Task) -> ComplexityLevel:
        """分析任务复杂度（基于预设标志）"""

    def route_to_executor(self, task: Task) -> ExecutorType:
        """将任务路由到合适的执行器"""
```

### 3. 简单任务执行器 (SimpleTaskExecutor)

```python
class SimpleTaskExecutor:
    """简单任务直接执行器"""

    def __init__(self):
        self.tool_registry = self._load_tools()

    def execute_task(self, task: Task) -> TaskResult:
        """执行简单任务"""

    def validate_parameters(self, tool_name: str, params: Dict) -> bool:
        """验证工具参数"""

    def call_tool(self, tool_name: str, params: Dict) -> Any:
        """调用具体工具"""
```

### 4. 复杂任务解决器 (ComplexTaskSolver)

```python
class ComplexTaskSolver:
    """复杂任务智能解决器"""

    def __init__(self, llm_client, rag_system, simple_executor):
        self.llm_client = llm_client
        self.rag_system = rag_system
        self.simple_executor = simple_executor  # 复用简单任务执行器

    def solve_complex_task(self, task: Task) -> TaskResult:
        """解决复杂任务"""

    def query_knowledge_base(self, query: str) -> List[KnowledgeChunk]:
        """从HydroRAG检索相关知识"""

    def generate_tool_sequence(self, task: Task, knowledge: List[KnowledgeChunk]) -> List[ToolCall]:
        """生成工具调用序列 (推荐方案)"""

    def generate_code_snippet(self, task: Task, knowledge: List[KnowledgeChunk]) -> str:
        """生成受限代码片段 (备选方案)"""

    def execute_tool_sequence(self, tool_calls: List[ToolCall]) -> TaskResult:
        """执行工具调用序列"""

    def execute_code_snippet(self, code: str, context: Dict) -> TaskResult:
        """在沙箱环境执行代码片段"""
```

#### 🎯 复杂任务解决方案

**方案A: 工具调用序列生成 (推荐)**
```json
{
  "task_type": "complex",
  "solution_type": "tool_sequence",
  "steps": [
    {
      "step_id": 1,
      "tool_name": "prepare_data",
      "parameters": {"data_dir": "data/custom", "scale": "D"},
      "condition": null
    },
    {
      "step_id": 2,
      "tool_name": "calibrate_model",
      "parameters": {
        "model_name": "gr4j",
        "data_dir": "${step_1.output.data_dir}",
        "algorithm": "sceua",
        "max_iterations": 1000
      },
      "condition": "${step_1.success} == true"
    },
    {
      "step_id": 3,
      "tool_name": "evaluate_model",
      "parameters": {"result_dir": "${step_2.output.result_dir}"},
      "condition": "${step_2.output.nse} > 0.5"
    }
  ]
}
```

**方案B: 受限代码片段生成 (备选)**
```python
# 生成的代码片段示例
def custom_calibration_workflow(data_dir, target_nse=0.7):
    # 步骤1: 数据预处理
    processed_data = tools.prepare_data(
        data_dir=data_dir,
        target_data_scale="D",
        quality_check=True
    )

    # 步骤2: 多算法率定
    algorithms = ["sceua", "nsga2", "pso"]
    best_result = None
    best_nse = 0

    for algorithm in algorithms:
        result = tools.calibrate_model(
            model_name="gr4j",
            data_dir=processed_data.output_path,
            algorithm=algorithm,
            max_iterations=500
        )

        if result.nse > best_nse:
            best_nse = result.nse
            best_result = result

        if best_nse >= target_nse:
            break

    return best_result
```

### 5. 工作流执行引擎 (WorkflowExecutor)

```python
class WorkflowExecutor:
    """工作流执行引擎 - 支持多种执行策略"""

    def __init__(self, task_dispatcher, simple_executor, complex_solver):
        self.task_dispatcher = task_dispatcher
        self.simple_executor = simple_executor
        self.complex_solver = complex_solver

    def execute_workflow(self, workflow: Workflow) -> WorkflowResult:
        """执行工作流主接口"""
        if workflow.mode == WorkflowMode.REACT:
            return self.execute_react_mode(workflow)
        else:
            return self.execute_sequential_mode(workflow)

    def execute_sequential_mode(self, workflow: Workflow) -> WorkflowResult:
        """线性执行模式"""

    def execute_react_mode(self, workflow: Workflow) -> WorkflowResult:
        """React目标导向执行模式"""

    def evaluate_target_achievement(self, workflow: Workflow, result: WorkflowResult) -> bool:
        """评估是否达到工作流目标"""

    def adjust_workflow_parameters(self, workflow: Workflow, iteration_result: WorkflowResult) -> Workflow:
        """根据结果调整工作流参数"""
```

#### 🎯 React模式执行逻辑

```python
def execute_react_mode(self, workflow: Workflow) -> WorkflowResult:
    """React目标导向执行模式"""
    target = workflow.target
    max_iterations = target.max_iterations
    current_iteration = 0

    while current_iteration < max_iterations:
        # 1. 执行当前工作流
        iteration_result = self.execute_sequential_mode(workflow)

        # 2. 评估目标达成情况
        target_achieved = self.evaluate_target_achievement(workflow, iteration_result)

        # 3. 记录本次迭代
        react_iteration = ReactIteration(
            iteration=current_iteration + 1,
            target_achieved=target_achieved,
            current_metric=self.extract_target_metric(iteration_result, target.metric),
            adjustments_made=[]
        )

        if target_achieved:
            break

        # 4. 调整工作流参数进行下次迭代
        workflow = self.adjust_workflow_parameters(workflow, iteration_result)
        current_iteration += 1

    return self.finalize_react_result(workflow, iteration_result)
```

### 6. 结果管理器 (ResultManager)

```python
class ResultManager:
    """执行结果管理和统计"""

    def track_execution(self, execution_id: str) -> ExecutionTracker:
        """跟踪执行过程"""

    def calculate_metrics(self, results: List[TaskResult]) -> ExecutionMetrics:
        """计算执行指标"""

    def generate_report(self, workflow_result: WorkflowResult) -> ExecutionReport:
        """生成执行报告"""

    def summarize_with_llm(self, results: WorkflowResult) -> str:
        """使用LLM整理最终结果"""
```

## 🚀 执行流程

### 标准执行模式

1. **接收工作流** → 解析JSON格式工作流
2. **任务分发** → 根据type字段分发任务
3. **执行任务** → 简单任务直接执行，复杂任务智能解决
4. **结果收集** → 收集各任务执行结果
5. **状态更新** → 更新执行状态和进度
6. **生成报告** → 整理最终执行报告

### React执行模式

1. **设定目标** → 解析工作流中的target字段
2. **初次执行** → 按标准模式执行工作流
3. **评估结果** → 检查是否达到目标条件
4. **迭代优化** → 未达到目标则调整参数重新执行
5. **收敛判断** → 达到目标或超过最大迭代次数
6. **最终总结** → 使用LLM生成执行总结

## 🔍 关键特性

### 智能任务识别
- 基于任务type字段直接判断复杂度
- 无需在执行阶段调用LLM判断
- 支持工作流生成时的复杂度预判

### 灵活的工具生态
- 支持现有工具的无缝集成
- 支持动态工具生成和执行
- 统一的工具调用接口

### 目标导向执行
- 支持性能指标目标（如NSE > 0.7）
- 支持自定义收敛条件
- 智能迭代优化策略

### 完善的状态管理
- 实时执行状态跟踪
- 详细的错误信息和堆栈
- 支持断点续传和检查点

### 智能结果整理
- 自动计算成功率和执行指标
- LLM驱动的结果总结
- 结构化的执行报告

## 📁 文件结构

```
hydrotool/
├── core/
│   ├── __init__.py
│   ├── workflow_receiver.py      # 工作流接收器
│   ├── task_dispatcher.py        # 任务分发器
│   ├── simple_executor.py        # 简单任务执行器
│   ├── complex_solver.py         # 复杂任务解决器
│   ├── react_executor.py         # React执行器
│   └── result_manager.py         # 结果管理器
├── models/
│   ├── __init__.py
│   ├── workflow.py               # 工作流数据模型
│   ├── task.py                   # 任务数据模型
│   └── result.py                 # 结果数据模型
├── tools/
│   ├── __init__.py
│   ├── registry.py               # 工具注册表
│   ├── base_tool.py              # 工具基类
│   └── hydro_tools/              # 水文工具集合
├── utils/
│   ├── __init__.py
│   ├── validation.py             # 验证工具
│   ├── parameter_resolver.py     # 参数解析器
│   └── logger.py                 # 日志工具
├── examples/
│   ├── workflows/                # 示例工作流
│   └── test_cases.py             # 测试用例
├── README.md                     # 使用文档
└── main.py                       # 主入口
```

## 🛠️ 现有水文工具集成

### 核心水文工具 (基于旧版langchain_tool)

1. **prepare_data** - 数据准备工具
   - 功能：处理和验证水文时间序列数据
   - 输入：数据目录路径、时间尺度
   - 输出：处理后的数据路径、记录数量

2. **calibrate_model** - 模型率定工具
   - 功能：使用SCEUA等算法率定水文模型参数
   - 支持模型：GR4J、XAJ、SAC-SMA等
   - 输入：模型配置、数据路径、率定期
   - 输出：率定结果、最优参数、性能指标

3. **evaluate_model** - 模型评估工具
   - 功能：评估模型在测试期的性能
   - 输入：率定结果目录
   - 输出：评估指标(NSE、RMSE、R²等)

### 工具注册和调用机制

```python
class HydroToolRegistry:
    """水文工具注册表"""

    def __init__(self):
        self.tools = {}
        self._register_default_tools()

    def register_tool(self, name: str, tool_func: Callable, schema: BaseModel):
        """注册新工具"""

    def get_tool(self, name: str) -> ToolInfo:
        """获取工具信息"""

    def call_tool(self, name: str, parameters: Dict) -> Any:
        """调用工具"""
```

## 🎯 实现计划

### Phase 1: 基础架构 ✅
- [x] 设计数据模型和接口
- [x] 实现工作流接收器
- [x] 实现基础任务分发器
- [x] 建立基础测试框架

### Phase 2: 核心执行器 (当前进行中)
- [ ] 实现简单任务执行器
- [ ] 集成现有水文工具
- [ ] 完善工作流执行引擎
- [ ] 添加错误处理和日志

### Phase 3: 智能解决器
- [ ] 实现复杂任务解决器
- [ ] 集成HydroRAG知识库
- [ ] 实现LLM API调用
- [ ] 添加解决方案验证

### Phase 4: React执行模式
- [ ] 实现目标导向执行逻辑
- [ ] 添加迭代优化策略
- [ ] 实现收敛条件判断
- [ ] 添加参数调整机制

### Phase 5: 完善和测试
- [ ] 完善结果管理和报告
- [ ] 添加全面的测试用例
- [ ] 性能优化和调试
- [ ] 文档完善和示例

## 🔧 API接口设计

### 主要接口

```python
# 主执行接口
def execute_workflow(workflow_json: str, mode: str = "sequential") -> WorkflowResult:
    """执行工作流的主接口"""

# React模式接口
def execute_with_goal(workflow_json: str, target_config: Dict) -> WorkflowResult:
    """目标导向执行接口"""

# 状态查询接口
def get_execution_status(execution_id: str) -> ExecutionStatus:
    """查询执行状态"""

# 结果获取接口
def get_execution_result(execution_id: str) -> WorkflowResult:
    """获取执行结果"""
```

## 📈 性能和监控

### 性能指标
- 任务执行时间统计
- 工作流完成率分析
- 资源使用情况监控
- LLM调用次数和耗时

### 监控和告警
- 执行异常自动告警
- 性能瓶颈识别
- 资源使用率监控
- 执行日志实时跟踪

这个新架构将为HydroAgent提供强大而灵活的工具执行能力，支持从简单的工具调用到复杂的智能问题解决，真正实现智能化的水文建模工作流执行。