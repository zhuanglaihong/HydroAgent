# Builder 系统 - 工作流规划与生成

## 概述

Builder 系统是 HydroAgent 的核心规划层，负责将用户的自然语言查询转换为可执行的结构化工作流。系统结合 RAG (Retrieval-Augmented Generation) 知识检索和 CoT (Chain-of-Thought) 推理，智能生成符合执行器要求的工作流定义。

## 系统架构

```
builder/
├── __init__.py              # 包初始化
├── workflow_builder.py      # 主工作流构建器
├── rag_planner.py          # RAG规划器 (CoT推理)
├── llm_client.py           # LLM客户端 (API优先+本地降级)
├── execution_mode.py       # 执行模式分析器
├── api_client.py           # API客户端封装
└── README.md               # 本文档
```

## 核心组件

### 1. WorkflowBuilder (工作流构建器)
- **职责**: 系统入口，协调各个子组件
- **功能**:
  - 整合RAG规划和执行模式分析
  - 应用执行模式优化
  - 最终验证和统计
- **接口**: `build_workflow(query, context) -> WorkflowBuildResult`

### 2. RAGPlanner (RAG规划器)
- **职责**: 基于知识检索的工作流规划
- **功能**:
  - RAG知识检索
  - CoT思维链推理
  - 工作流结构生成
  - JSON格式验证
- **特色**: 结合项目知识库智能规划

### 3. LLMClient (LLM客户端)
- **职责**: 统一的LLM调用接口
- **功能**:
  - API优先调用 (test_qwen.py)
  - 本地Ollama降级
  - 调用统计和监控
  - 错误处理和重试
- **优势**: 高可用性和灵活性

### 4. ExecutionModeAnalyzer (执行模式分析器)
- **职责**: 分析工作流复杂度并推荐执行模式
- **执行模式**:
  - `LINEAR`: 简单顺序执行
  - `REACT`: 复杂反应式执行 (支持条件、循环、反馈)
  - `HYBRID`: 混合模式 (简单任务线性，复杂任务反应式)
- **分析维度**: 任务复杂度、依赖关系、循环条件等

## 工作流输出格式

Builder 生成的工作流严格遵循与 Executor 对接的标准格式：

```json
{
  "workflow_id": "唯一工作流ID",
  "name": "工作流名称",
  "description": "工作流描述",
  "execution_mode": "linear|react|hybrid",
  "tasks": [
    {
      "task_id": "任务ID",
      "name": "任务名称",
      "description": "任务描述",
      "action": "工具名称",
      "task_type": "simple_action|complex_reasoning",
      "parameters": {
        "参数名": "参数值"
      },
      "dependencies": ["依赖任务ID"],
      "conditions": {
        "retry_count": 3,
        "timeout": 300,
        "if": "执行条件"
      },
      "expected_output": "期望输出"
    }
  ],
  "metadata": {
    "created_time": "ISO时间戳",
    "complexity": "复杂度评级",
    "estimated_duration": "预估时间"
  }
}
```

## 可用工具

Builder 系统严格限制工作流只能使用以下4个工具：

1. **get_model_params**: 获取水文模型参数信息
2. **prepare_data**: 数据准备和预处理
3. **calibrate_model**: 模型参数率定
4. **evaluate_model**: 模型性能评估

## 任务类型分类

- **simple_action**: 简单直接操作
  - 数据读写
  - 参数查询
  - 简单计算

- **complex_reasoning**: 复杂推理任务
  - 模型率定
  - 参数优化
  - 性能分析
  - 决策制定

## 配置参数

Builder 系统的配置参数在 `config.py` 中：

```python
# CoT推理配置
COT_TEMPERATURE = 0.2                   # CoT推理温度
COT_KNOWLEDGE_CHUNKS = 5                # 知识片段数量

# 构建器配置
BUILDER_MAX_TASKS = 20                  # 最大任务数
BUILDER_TIMEOUT = 120                   # 构建超时时间

# 执行模式分析
MODE_COMPLEXITY_THRESHOLD_LOW = 0.3     # 线性模式阈值
MODE_COMPLEXITY_THRESHOLD_HIGH = 0.7    # 反应式模式阈值

# LLM配置
LLM_USE_API_FIRST = True                # 优先使用API
LLM_API_MODEL_NAME = "qwen3-coder-plus" # API模型
LLM_FALLBACK_MODEL = "qwen3:8b"         # 本地降级模型
```

## 使用示例

### 基本使用

```python
from builder import WorkflowBuilder

# 初始化构建器
builder = WorkflowBuilder(rag_system=rag_system)

# 构建工作流
result = builder.build_workflow("率定并评估GR4J模型")

if result.success:
    workflow = result.workflow
    execution_mode = result.execution_mode
    print(f"生成工作流: {workflow['name']}")
    print(f"执行模式: {execution_mode.value}")
    print(f"任务数量: {len(workflow['tasks'])}")
else:
    print(f"构建失败: {result.error_message}")
```

### 高级使用

```python
# 带上下文的构建
context = {
    "data_period": "2010-2020",
    "model_type": "GR4J",
    "optimization_method": "SCE-UA"
}

result = builder.build_workflow(
    query="使用历史数据率定模型并验证性能",
    context=context
)

# 获取详细信息
print(f"规划时间: {result.planning_result.planning_time:.2f}秒")
print(f"CoT步骤: {len(result.planning_result.cot_steps)}")
print(f"知识片段: {len(result.planning_result.rag_context.fragments)}")
print(f"复杂度评分: {result.mode_analysis.complexity_score:.2f}")
```

## 测试

Builder 系统提供了完整的测试套件：

```bash
# 基础功能测试（无外部依赖）
python test/test_builder_basic.py

# 完整集成测试（需要API和RAG）
python test/test_builder_integration.py
```

测试覆盖：
- ✅ 执行模式智能分析
- ✅ 工作流结构验证
- ✅ 标准JSON格式输出
- ✅ 任务类型识别
- ✅ 依赖关系管理
- ✅ 复杂度评估

## 与 Executor 对接

Builder 生成的工作流完全兼容 Executor 的执行要求：

1. **格式兼容**: 标准JSON格式
2. **执行模式**: 明确的执行策略标识
3. **任务分类**: simple_action vs complex_reasoning
4. **参数验证**: 严格的工具参数验证
5. **依赖管理**: 完整的任务依赖关系

## 性能特性

- **高可用性**: API+本地双重保障
- **智能推理**: RAG知识增强
- **模式自适应**: 根据复杂度选择执行模式
- **错误容错**: 多级fallback机制
- **统计监控**: 完整的性能指标

## 扩展性

Builder 系统设计为模块化架构，易于扩展：

- **新工具支持**: 在工具约束中添加新工具
- **新推理策略**: 扩展CoT推理模板
- **新执行模式**: 增加执行模式类型
- **新知识源**: 集成更多RAG数据源

## 依赖关系

- **必需依赖**: Python 3.8+
- **API依赖**: OpenAI兼容API (test_qwen.py)
- **本地依赖**: Ollama (可选降级)
- **RAG依赖**: HydroRAG系统 (可选增强)

Builder 系统为 HydroAgent 提供了强大的工作流规划能力，是连接用户需求和系统执行的关键桥梁。