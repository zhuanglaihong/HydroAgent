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

## 工作流构建测试 **test_workflow_builder.py** 
# 使用Ollama本地模型测试
python test/test_workflow_builder.py --mode ollama --model qwen3:8b

# 使用API模型测试
python test/test_workflow_builder.py --mode api --model gpt-3.5-turbo

# 指定输出目录
python test/test_workflow_builder.py --output-dir ./test_results