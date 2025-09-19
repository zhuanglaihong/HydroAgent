# 新版工作流生成器 (WorkflowGeneratorV2)

## 概述

这是重新设计和实现的工作流生成器，能够将用户的自然语言指令，通过思维链（CoT）推理和RAG系统的增强，转化为一个结构化的、可执行的工作流计划（DSL）。

## 核心特性

### 🧠 智能理解
- **自然语言处理**: 支持中文自然语言指令输入
- **意图识别**: 自动识别用户意图类型（数据获取、分析、建模等）
- **实体提取**: 提取关键实体（时间、模型名称、参数等）

### 🔗 RAG集成
- **知识检索**: 自动从向量数据库检索相关知识
- **上下文增强**: 利用检索到的知识增强LLM推理
- **回退机制**: 在RAG不可用时提供基础知识

### 🤖 CoT推理
- **逐步思考**: 引导LLM进行链式推理
- **结构化输出**: 生成标准化的工作流JSON格式
- **质量保证**: 多层验证确保输出质量

### 🔧 智能组装
- **自动验证**: 检查工作流的可行性和完整性
- **依赖优化**: 自动识别并行执行的任务
- **错误修复**: 自动修复常见的工作流问题

### 📊 反馈学习
- **自动记录**: 记录执行成功/失败的情况
- **模式识别**: 识别常见的错误模式
- **自我优化**: 将学习结果集成到RAG系统

## 系统架构

```
用户指令 → 指令解析与意图理解 → CoT+RAG推理引擎 → 工作流组装与优化 → 验证与反馈闭环
    ↓              ↓                    ↓                ↓                  ↓
 自然语言        结构化意图           增强推理计划        优化工作流          学习优化
```

### 核心模块

1. **指令解析与意图理解模块** (`instruction_parser.py`)
   - 分词和实体识别
   - 意图分类
   - 参数和约束提取

2. **增强推理引擎** (`cot_rag_engine.py`)
   - RAG知识检索
   - CoT提示词构建
   - LLM推理调用

3. **工作流组装与优化模块** (`workflow_assembler.py`)
   - JSON解析和清洗
   - 可行性验证
   - 执行顺序优化

4. **验证与反馈闭环机制** (`validation_feedback.py`)
   - 执行结果记录
   - 错误模式分析
   - 学习案例管理

5. **主工作流生成器** (`workflow_generator_v2.py`)
   - 统一入口接口
   - 配置管理
   - 统计和监控

## 使用方法

### 基本使用

```python
from workflow import create_workflow_generator, GenerationConfig

# 创建配置
config = GenerationConfig(
    llm_model="qwen2.5:7b",
    llm_temperature=0.7,
    enable_feedback_learning=True
)

# 创建生成器
generator = create_workflow_generator(config=config)

# 生成工作流
result = generator.generate_workflow("我想率定一个GR4J模型")

if result.success:
    print(f"工作流名称: {result.workflow.name}")
    print(f"任务数量: {len(result.workflow.tasks)}")
else:
    print(f"生成失败: {result.error_message}")
```

### 与RAG系统集成

```python
from hydrorag import RAGSystem
from workflow import create_workflow_generator

# 初始化RAG系统
rag_system = RAGSystem()
rag_system.load_documents("./documents")
rag_system.create_index()

# 创建带RAG的生成器
generator = create_workflow_generator(rag_system=rag_system)

# 生成工作流（会自动使用RAG检索相关知识）
result = generator.generate_workflow("分析CAMELS数据集的水文特征")
```

### 与Ollama集成

```python
import ollama
from workflow import create_workflow_generator, GenerationConfig

# 创建Ollama客户端
ollama_client = ollama.Client()

# 配置LLM参数
config = GenerationConfig(
    llm_model="qwen2.5:7b",
    llm_temperature=0.8,
    reasoning_timeout=180
)

# 创建生成器
generator = create_workflow_generator(
    ollama_client=ollama_client,
    config=config
)

# 生成工作流
result = generator.generate_workflow("使用LSTM进行径流预测")
```

### 批量生成

```python
instructions = [
    "加载CAMELS数据集",
    "计算水文指标",
    "创建可视化报告"
]

results = generator.generate_workflow_batch(instructions)

for i, result in enumerate(results, 1):
    print(f"{i}. {'成功' if result.success else '失败'}: {result.workflow.name if result.success else result.error_message}")
```

### 工作流验证

```python
# 验证生成的工作流
validation_result = generator.validate_workflow(result.workflow)

if validation_result['is_valid']:
    print("✅ 工作流验证通过")
else:
    print("❌ 工作流验证失败:")
    for issue in validation_result['issues']:
        print(f"  - {issue}")
```

### 导出不同格式

```python
workflow = result.workflow

# 导出为JSON
json_output = generator.export_workflow_dsl(workflow, "json")

# 导出为YAML
yaml_output = generator.export_workflow_dsl(workflow, "yaml")

# 导出为XML
xml_output = generator.export_workflow_dsl(workflow, "xml")
```

## 配置选项

### GenerationConfig

```python
config = GenerationConfig(
    # LLM配置
    llm_model="qwen2.5:7b",           # LLM模型名称
    llm_temperature=0.7,              # 温度参数
    max_context_length=4000,          # 最大上下文长度
    
    # RAG配置
    rag_retrieval_k=10,               # 检索数量
    rag_score_threshold=0.3,          # 相似度阈值
    enable_rag_fallback=True,         # 启用回退机制
    
    # 验证配置
    enable_validation=True,           # 启用验证
    enable_optimization=True,         # 启用优化
    enable_feedback_learning=True,    # 启用反馈学习
    
    # 超时配置
    parsing_timeout=30,               # 解析超时
    reasoning_timeout=120,            # 推理超时
    assembly_timeout=60,              # 组装超时
    
    # 存储配置
    feedback_storage_path="workflow/feedback_data"  # 反馈存储路径
)
```

## 工作流DSL格式

生成的工作流采用标准化的JSON格式：

```json
{
  "workflow_id": "唯一ID",
  "name": "工作流名称",
  "description": "工作流描述",
  "tasks": [
    {
      "task_id": "task_1",
      "name": "任务名称",
      "description": "任务描述",
      "action": "具体操作",
      "task_type": "simple_action",
      "parameters": {
        "param1": "value1"
      },
      "dependencies": [],
      "conditions": {
        "if": "执行条件",
        "retry_count": 3
      },
      "expected_output": "期望输出"
    }
  ],
  "execution_order": [
    ["task_1"],
    ["task_2", "task_3"]
  ],
  "metadata": {
    "created_time": "2025-01-20T10:00:00",
    "complexity": "medium"
  }
}
```

### 任务类型

- **simple_action**: 简单操作（文件读写、数据计算等）
- **complex_reasoning**: 复杂推理（模型训练、参数优化等）

### 支持的操作

- **数据操作**: `load_data`, `save_data`, `read_csv`, `write_csv`
- **数据分析**: `analyze_data`, `calculate_stats`, `correlation_analysis`
- **模型操作**: `calibrate_model`, `run_model`, `gr4j_calibration`
- **可视化**: `plot_data`, `create_chart`, `visualize_results`
- **评估**: `calculate_nse`, `calculate_rmse`, `evaluate_model`

## 监控和统计

### 获取统计信息

```python
stats = generator.get_generation_statistics()
print(f"成功率: {stats['success_rate']:.2%}")
print(f"系统健康度: {stats['system_health']}")
```

### 触发学习更新

```python
# 手动触发学习更新
generator.trigger_learning_update()
```

### 健康报告

```python
if generator.feedback_system:
    health_report = generator.feedback_system.get_system_health_report()
    print(health_report)
```

## 错误处理

系统具备完善的错误处理机制：

1. **指令解析错误**: 返回具体的解析失败原因
2. **LLM调用错误**: 提供回退机制和重试策略
3. **工作流验证错误**: 自动修复常见问题
4. **执行错误**: 记录错误模式用于学习

## 性能优化

### 并行执行识别

系统自动识别可以并行执行的任务：

```json
"execution_order": [
  ["load_data"],
  ["preprocess_data"],
  ["analyze_data", "visualize_data"],  // 这两个任务可以并行
  ["generate_report"]
]
```

### 缓存机制

- **指令解析缓存**: 相似指令复用解析结果
- **RAG检索缓存**: 避免重复检索
- **工作流模板**: 常用模式快速生成

## 扩展性

### 自定义工具注册

```python
from workflow.workflow_assembler import ToolRegistry

# 扩展工具注册表
tool_registry = ToolRegistry()
tool_registry.available_tools.add("my_custom_tool")

# 使用自定义注册表
assembler = create_workflow_assembler(tool_registry)
```

### 自定义验证规则

```python
from workflow.validation_feedback import ValidationFeedbackSystem

class CustomValidationSystem(ValidationFeedbackSystem):
    def validate_custom_rules(self, workflow):
        # 自定义验证逻辑
        pass
```

## 测试

运行测试套件：

```bash
python test/test_new_workflow_generator.py
```

运行使用示例：

```bash
python workflow/example_usage.py
```

## 与旧版本兼容性

新版生成器与旧版本完全兼容，可以并存使用：

```python
# 使用新版生成器
from workflow import WorkflowGeneratorV2, create_workflow_generator

# 使用旧版生成器（仍然可用）
from workflow import WorkflowOrchestrator, WorkflowGenerator
```

## 最佳实践

1. **明确指令**: 提供具体、明确的指令以获得更好的结果
2. **RAG集成**: 建议集成RAG系统以提升生成质量
3. **反馈学习**: 启用反馈学习以持续改进系统
4. **定期更新**: 定期触发学习更新以优化性能
5. **监控统计**: 关注成功率和健康度指标

## 故障排除

### 常见问题

1. **LLM连接失败**
   - 检查Ollama是否正常运行
   - 验证模型名称是否正确

2. **RAG检索失败**
   - 检查向量数据库是否已构建
   - 确认文档是否已加载

3. **工作流验证失败**
   - 查看验证错误详情
   - 检查工具可用性

4. **JSON解析错误**
   - LLM输出格式问题，系统会自动尝试修复
   - 可以调整温度参数降低随机性

### 调试模式

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# 创建生成器时启用详细日志
generator = create_workflow_generator(config=config)
```

## 贡献指南

欢迎贡献代码改进系统：

1. 添加新的工具支持
2. 改进错误处理机制
3. 优化推理算法
4. 增强验证规则
5. 提供更多示例

## 许可证

本项目采用MIT许可证，详见LICENSE文件。
