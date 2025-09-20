# HydroMCP 增强版本说明

## 概述

本次更新为HydroMCP包添加了增强的工作流执行和Agent统一接口功能，以适应新的工作流格式，支持基于任务复杂度的智能执行策略。

## 主要更新内容

### 1. 新增增强工作流执行器 (`enhanced_workflow_executor.py`)

- **支持新工作流格式**：完全兼容包含`task_type`字段的新工作流格式
- **智能任务分发**：根据`task_type`自动选择执行策略
  - `simple_action`：使用现有MCP工具直接执行
  - `complex_reasoning`：调用复杂任务处理器生成新工具（示例实现）
- **依赖关系处理**：支持任务间的依赖关系和数据传递
- **执行结果追踪**：详细的执行状态和结果统计

### 2. Agent统一接口 (`agent_interface.py`)

为主界面Agent提供统一的调用接口，整合工作流生成和执行功能：

#### 异步接口 (`HydroAgentInterface`)
```python
from hydromcp import create_hydro_agent_interface

# 创建Agent接口
agent = await create_hydro_agent_interface(
    llm_model="qwen3:8b",
    enable_rag=True,
    enable_complex_tasks=True
)

# 处理用户请求（生成+执行工作流）
result = await agent.process_user_request("使用GR4J模型进行流域参数率定")

# 仅生成工作流
workflow_result = await agent.generate_workflow_only("分析降雨径流数据")

# 仅执行工作流
execution_result = await agent.execute_workflow_only(workflow_data)
```

#### 同步接口 (`SyncHydroAgentInterface`)
```python
from hydromcp import create_sync_hydro_agent_interface

# 创建同步Agent接口
sync_agent = create_sync_hydro_agent_interface()

# 同步处理用户请求
result = sync_agent.process_user_request("加载CSV数据并计算统计信息")
```

### 3. 复杂任务处理增强 (`task_handlers.py`)

- **新增V2处理接口**：适配新工作流格式的复杂任务处理
- **智能任务识别**：根据任务描述自动识别任务类型
- **示例实现**：
  - 模型率定复杂任务
  - 模型评估复杂任务  
  - 复杂数据分析任务
  - 通用复杂任务

### 4. 任务复杂度枚举更新 (`task_dispatcher.py`)

更新任务复杂度枚举以匹配新工作流格式：
```python
class TaskComplexity(Enum):
    SIMPLE_ACTION = "simple_action"           # 简单操作
    COMPLEX_REASONING = "complex_reasoning"   # 复杂推理
    UNKNOWN = "unknown"                       # 未知复杂度
```

## 使用示例

### 基本使用

```python
import asyncio
from hydromcp import create_hydro_agent_interface

async def main():
    # 创建Agent
    agent = await create_hydro_agent_interface(
        llm_model="qwen3:8b",
        enable_rag=True,
        enable_complex_tasks=True
    )
    
    # 处理用户请求
    result = await agent.process_user_request(
        "使用GR4J模型对流域进行参数率定，然后评估率定结果"
    )
    
    if result["success"]:
        print(f"工作流执行成功！")
        print(f"总任务数: {result['overall_summary']['total_tasks']}")
        print(f"成功率: {result['overall_summary']['success_rate']:.1%}")
        print(f"总耗时: {result['overall_summary']['total_time']:.2f}秒")
    
    await agent.cleanup()

asyncio.run(main())
```

### 工作流格式示例

新支持的工作流格式包含`task_type`字段：

```json
{
  "workflow_id": "example_workflow",
  "name": "GR4J模型率定工作流",
  "description": "完整的模型率定和评估流程",
  "tasks": [
    {
      "task_id": "load_data",
      "name": "加载数据",
      "description": "读取流域观测数据",
      "action": "read_csv",
      "task_type": "simple_action",
      "parameters": {"file_path": "basin_data.csv"},
      "dependencies": []
    },
    {
      "task_id": "calibrate_model", 
      "name": "模型率定",
      "description": "使用SCE-UA算法率定GR4J模型参数",
      "action": "gr4j_calibration",
      "task_type": "complex_reasoning",
      "parameters": {"model": "GR4J", "algorithm": "SCE-UA"},
      "dependencies": ["load_data"]
    }
  ]
}
```

## 执行策略

### 简单任务 (`simple_action`)
- 直接使用现有MCP工具执行
- 包括：数据读写、基本计算、文件操作等
- 快速执行，低延迟

### 复杂任务 (`complex_reasoning`)  
- 调用复杂任务处理器
- 包括：模型率定、参数优化、复杂分析等
- 当前为示例实现，返回模拟结果
- 未来可扩展为真实的代码生成和执行

## 系统架构

```
用户指令 → Agent接口 → 工作流生成器 → 增强执行器
                                      ↓
                            ┌─ 简单任务处理器 (现有工具)
                            └─ 复杂任务处理器 (生成新工具)
```

## 配置选项

- `llm_model`: LLM模型名称 (默认: "qwen3:8b")
- `enable_rag`: 是否启用RAG系统 (默认: True)
- `enable_complex_tasks`: 是否启用复杂任务处理 (默认: True)
- `enable_debug`: 是否启用调试模式 (默认: False)

## 运行演示

运行包含的演示文件查看功能：

```bash
cd hydromcp/
python demo_enhanced_agent.py
```

演示包括：
- 异步和同步接口使用
- 不同复杂度任务的处理
- 工作流生成和执行分离
- 系统状态检查

## 扩展指南

### 添加新的复杂任务类型

1. 在`ComplexTaskHandler`中添加新的模拟方法
2. 在`_demo_complex_task_processing_v2`中添加识别逻辑  
3. 返回符合规范的结果格式

### 集成真实的代码生成

1. 替换示例实现为真实的LLM代码生成
2. 添加代码验证和安全检查
3. 实现动态工具注册和执行

## 兼容性

- 完全向后兼容现有MCP工具
- 支持新旧工作流格式
- 渐进式升级，可选择启用新功能

## 版本更新

- 版本号更新至 v1.0.0 
- 新增模块不影响现有功能
- 建议逐步迁移到新接口
