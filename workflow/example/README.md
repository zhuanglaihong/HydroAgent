# 工作流示例文件

本目录包含了HydroAgent系统的标准工作流示例，用于测试和演示不同类型的水文建模任务。

## 示例工作流说明

### 1. 简单工作流示例

#### `simple_get_model_params.json`
- **功能**: 获取GR4J模型参数
- **类型**: 单任务简单工作流
- **用途**: 演示最基本的模型参数查询功能

#### `simple_prepare_data.json`
- **功能**: 数据准备和预处理
- **类型**: 单任务简单工作流
- **用途**: 演示数据准备工具的使用

### 2. 复杂工作流示例

#### `complex_model_calibration.json`
- **功能**: 完整的模型率定流程
- **类型**: 多任务顺序工作流，包含简单和复杂任务
- **包含步骤**:
  1. 准备输入数据
  2. 获取模型参数
  3. 执行模型率定（复杂任务）
  4. 评估模型性能
- **用途**: 演示完整的水文模型率定工作流程

#### `parallel_comparison.json`
- **功能**: 并行比较多个水文模型
- **类型**: 并行执行工作流
- **包含步骤**:
  1. 准备共同数据
  2. 并行获取不同模型参数
  3. 并行执行模型率定
  4. 比较模型性能
- **用途**: 演示并行执行和模型比较功能

## 工作流格式规范

### 基本结构
```json
{
  "workflow_id": "唯一工作流标识符",
  "name": "工作流名称",
  "description": "工作流描述",
  "mode": "sequential|parallel",
  "global_settings": {
    "error_handling": "continue_on_error|stop_on_error",
    "timeout": 总超时时间（秒）,
    "max_parallel_tasks": 最大并行任务数（仅并行模式）
  },
  "tasks": [任务列表]
}
```

### 任务格式

#### 简单任务（Simple Task）
```json
{
  "task_id": "任务ID",
  "name": "任务名称",
  "type": "simple",
  "tool_name": "工具名称",
  "parameters": {参数对象},
  "dependencies": ["依赖任务ID列表"],
  "timeout": 任务超时时间（秒）,
  "retry_count": 重试次数
}
```

#### 复杂任务（Complex Task）
```json
{
  "task_id": "任务ID",
  "name": "任务名称",
  "type": "complex",
  "description": "任务描述",
  "knowledge_query": "知识查询字符串",
  "parameters": {参数对象},
  "dependencies": ["依赖任务ID列表"],
  "timeout": 任务超时时间（秒）,
  "retry_count": 重试次数
}
```

## 可用工具清单

### 简单工具
- `get_model_params`: 获取模型参数
- `prepare_data`: 准备数据
- `calibrate_model`: 率定模型
- `evaluate_model`: 评估模型

### 复杂任务知识查询示例
- `"率定GR4J模型"`: GR4J模型率定
- `"率定XAJ模型"`: XAJ模型率定
- `"比较水文模型性能"`: 模型性能比较
- `"优化模型参数"`: 参数优化

## 使用方法

### 在测试中使用示例工作流
```python
from pathlib import Path

# 加载示例工作流
example_dir = Path("workflow/example")
workflow_file = example_dir / "simple_get_model_params.json"

with open(workflow_file, 'r', encoding='utf-8') as f:
    workflow_json = f.read()

# 执行工作流
executor = ExecutorEngine()
result = executor.execute_workflow(workflow_json, mode="sequential")
```

### 在构建器测试中使用
测试程序可以选择使用预定义的示例工作流而不是动态生成，这样可以确保工作流格式的正确性和一致性。

## 注意事项

1. **参数验证**: 所有示例工作流都经过格式验证，确保可以被执行器正确解析
2. **依赖关系**: 任务依赖关系已经正确设置，确保执行顺序的合理性
3. **超时设置**: 超时时间根据任务复杂度合理设置
4. **错误处理**: 默认采用`continue_on_error`策略，确保测试可以完整执行
5. **重试机制**: 简单任务设置重试，复杂任务通常不重试以避免重复的长时间计算

## 扩展示例

如需添加新的示例工作流，请遵循以下原则：
1. 文件命名格式：`{类型}_{功能描述}.json`
2. 确保JSON格式正确
3. 包含必要的字段和合理的参数
4. 更新本README文件的说明