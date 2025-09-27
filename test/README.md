# Test Directory

本目录包含HydroAgent系统的所有测试文件。测试文件按功能模块和复杂度分类。

## 测试文件概览

### 核心执行器测试
- **test_executor_simple.py** - 简单任务执行器测试，包含基础工具功能验证
- **test_executor_complex.py** - 复杂任务执行器测试，验证多步骤工作流执行能力
- **test_executor_visualization.py** - 可视化功能测试，验证图表生成和数据展示

### 构建器测试
- **test_builder_basic.py** - 基础构建器测试，验证工作流构建基本功能
- **test_builder_integration.py** - 构建器集成测试，验证与其他组件的协作

### RAG系统测试
- **test_enhanced_rag.py** - 增强RAG系统功能测试
- **test_rag_effectiveness_comparison.py** - RAG效果对比测试，验证RAG系统对复杂任务处理能力的提升

### LLM客户端测试
- **test_intelligent_llm_client.py** - 智能LLM客户端测试
- **test_qwen.py** - Qwen模型特定功能测试

### 系统支持测试
- **test_logging_system.py** - 日志系统功能测试

## 运行测试

### 运行单个测试
```bash
python test/test_executor_simple.py
python test/test_rag_effectiveness_comparison.py
```

### 运行所有测试
```bash
# 在项目根目录下运行
python -m pytest test/
```

## 测试分类

### 按复杂度分类
- **简单测试**: test_executor_simple.py, test_builder_basic.py
- **复杂测试**: test_executor_complex.py, test_rag_effectiveness_comparison.py
- **集成测试**: test_builder_integration.py

### 按功能模块分类
- **执行器模块**: test_executor_*.py
- **构建器模块**: test_builder_*.py
- **RAG模块**: test_enhanced_rag.py, test_rag_effectiveness_comparison.py
- **LLM模块**: test_intelligent_llm_client.py, test_qwen.py
- **支持模块**: test_logging_system.py, test_executor_visualization.py

## 特殊测试说明

### RAG效果对比测试 (test_rag_effectiveness_comparison.py)
- 专门用于验证RAG系统对复杂任务处理能力的提升
- 包含6个不同复杂度的测试用例
- 支持A/B对比测试（启用/禁用RAG）
- 详细的质量评估和效果分析

### 复杂任务测试 (test_executor_complex.py)
- 验证多步骤、跨工具的复杂工作流执行
- 包含真实水文建模场景测试
- 测试错误处理和恢复机制

## 测试数据和结果

- 测试结果保存在 `test/results/` 目录
- 测试日志保存在 `utils/logs/` 目录
- 测试配置可在各测试文件中调整