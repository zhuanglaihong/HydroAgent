# RAG系统对复杂任务影响对比测试

## 概述

这个测试系统用于评估RAG（Retrieval-Augmented Generation）系统对复杂任务执行的影响。通过对比启用和不启用RAG的执行效果，量化RAG系统带来的性能提升。

## 测试目标

1. **验证RAG集成**：确认RAG系统能够正确集成到executor中
2. **评估知识检索效果**：测试RAG系统能否检索到相关知识
3. **对比执行性能**：比较加载RAG和不加载RAG的执行差异
4. **量化改进幅度**：用数据说明RAG系统的实际价值

## 文件结构

```
HydroAgent/
├── workflow/example/
│   └── complex_data_analysis.json    # 复杂任务示例工作流
├── hydrorag/documents/
│   ├── tool_prepare_data_example.md           # 数据准备工具示例
│   ├── tool_calibrate_model_example.md        # 模型率定工具示例
│   ├── tool_evaluate_model_example.md         # 模型评估工具示例
│   ├── hydro_data_analysis_knowledge.md       # 水文数据分析知识
│   └── code_generation_patterns.md            # 代码生成模式
├── executor/core/
│   └── complex_executor.py            # 增强了RAG集成的复杂任务解决器
└── test/
    ├── test_rag_complex_workflow_comparison.py  # 对比测试脚本
    └── README_RAG_COMPLEX_TEST.md               # 本文档
```

## 复杂任务工作流说明

### workflow/example/complex_data_analysis.json

这个工作流包含5个任务，其中3个是复杂任务（需要LLM代码生成）：

1. **task_custom_analysis** (复杂任务)
   - 类型：complex
   - 功能：自定义数据分析和特征提取
   - 需求：生成代码进行数据统计、极端事件识别、降雨-径流分析
   - RAG知识需求：数据分析方法、pandas/numpy使用

2. **task_prepare** (简单任务)
   - 类型：simple
   - 功能：调用prepare_data工具处理数据
   - 依赖：task_custom_analysis

3. **task_adaptive_calibration** (复杂任务)
   - 类型：complex
   - 功能：自适应模型率定
   - 需求：根据数据分析结果生成自适应参数优化代码
   - RAG知识需求：模型率定策略、参数优化方法
   - 依赖：task_prepare

4. **task_evaluate** (简单任务)
   - 类型：simple
   - 功能：调用evaluate_model工具评估模型
   - 依赖：task_adaptive_calibration

5. **task_result_synthesis** (复杂任务)
   - 类型：complex
   - 功能：综合结果分析
   - 需求：生成报告生成代码
   - RAG知识需求：报告格式、结果可视化
   - 依赖：task_evaluate

## RAG知识库文档说明

### 1. tool_prepare_data_example.md
- **内容**：PrepareDataTool完整实现代码和使用示例
- **用途**：为LLM提供标准工具调用模式
- **关键信息**：参数说明、返回值格式、错误处理

### 2. tool_calibrate_model_example.md
- **内容**：CalibrateModelTool核心实现和配置示例
- **用途**：指导LLM理解模型率定过程
- **关键信息**：SCE-UA算法参数、参数范围配置

### 3. tool_evaluate_model_example.md
- **内容**：EvaluateModelTool实现和评估指标说明
- **用途**：帮助LLM理解模型评估标准
- **关键信息**：NSE/R2/RMSE等指标含义

### 4. hydro_data_analysis_knowledge.md
- **内容**：水文数据分析完整知识库
- **用途**：为LLM生成数据分析代码提供模板
- **包含**：
  - 数据读取（CSV/NetCDF）
  - 统计分析（基础统计、时间序列特征）
  - 极端事件识别（极端降雨、洪水）
  - 降雨-径流关系分析（相关性、径流系数）
  - 数据可视化（时间序列图、柱状图）

### 5. code_generation_patterns.md
- **内容**：代码生成的标准模式和最佳实践
- **用途**：规范LLM生成的代码结构
- **包含**：
  - 标准代码结构模板
  - 5种常见任务代码模式
  - 错误处理最佳实践
  - 代码质量检查清单

## 执行器修改说明

### executor/core/complex_executor.py 的增强

#### 1. 增强的知识检索 (_query_knowledge_base)
```python
# 实际调用RAG系统
rag_results = self.rag_system.search(query, top_k=5)

# 转换为标准格式
knowledge_chunks.append({
    "content": result.get("content"),
    "source": result.get("source"),
    "relevance": result.get("score"),
    "metadata": result.get("metadata")
})
```

#### 2. 代码生成时的知识检索 (_execute_code_generation_step)
```python
# 为代码生成专门检索知识
if self.rag_system:
    rag_results = self.rag_system.search(step.description, top_k=3)
    # 将检索到的代码示例传递给LLM
```

#### 3. 增强的代码生成提示 (_build_code_generation_prompt)
```python
# 包含RAG检索到的代码示例
if code_knowledge:
    knowledge_section = "\n相关代码示例和知识:\n"
    for knowledge in code_knowledge:
        knowledge_section += f"\n示例: {knowledge['content']}\n"
```

## 测试脚本功能

### test_rag_complex_workflow_comparison.py

#### 主要功能

1. **RAGComparisonTest类**
   - `initialize_rag_system()`: 初始化RAG系统，加载documents文档
   - `initialize_executor(with_rag)`: 创建执行器，可选择是否启用RAG
   - `execute_workflow_test()`: 执行工作流并收集统计数据
   - `compare_results()`: 对比两次测试结果
   - `run_comparison_test()`: 完整测试流程

2. **统计指标**
   - 复杂任务成功率
   - 执行时间
   - 知识片段使用数量
   - LLM调用次数
   - 任务状态详情

3. **输出文件**
   - 详细日志：`logs/test_rag_complex_comparison_YYYYMMDD_HHMMSS.log`
   - JSON结果：`logs/rag_comparison_results_YYYYMMDD_HHMMSS.json`

## 运行测试

### 前提条件

1. **安装依赖**
```bash
uv sync  # 或 pip install -r requirements.txt
```

2. **Ollama模型**
```bash
# 确保Ollama服务运行
ollama list

# 需要的模型
ollama pull qwen3:8b
ollama pull granite3-dense:8b
```

3. **数据准备**
- 确保测试数据目录存在（可选，测试会模拟执行）

### 执行测试

```bash
# 激活虚拟环境
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# 运行测试
python test/test_rag_complex_workflow_comparison.py
```

### 预期输出

```
================================================================================
RAG系统对复杂任务执行影响对比测试
================================================================================

日志将保存到: D:\project\Agent\HydroAgent\logs\test_rag_complex_comparison_20251011_123456.log

============================================================
第一轮测试: 不启用RAG系统
============================================================

正在初始化执行器 (RAG: False)...
执行器初始化完成
开始执行工作流...

测试 without_rag 完成:
  - 状态: True/False
  - 耗时: X.XX秒
  - 复杂任务: X/3
  - 知识片段使用: 0


============================================================
第二轮测试: 启用RAG系统
============================================================

正在初始化RAG系统...
找到 5 个文档文件
正在加载文档到RAG系统...
  已添加: tool_prepare_data_example.md
  已添加: tool_calibrate_model_example.md
  已添加: tool_evaluate_model_example.md
  已添加: hydro_data_analysis_knowledge.md
  已添加: code_generation_patterns.md
RAG系统初始化完成

正在初始化执行器 (RAG: True)...
RAG系统已集成到执行器
执行器初始化完成
开始执行工作流...

测试 with_rag 完成:
  - 状态: True/False
  - 耗时: X.XX秒
  - 复杂任务: X/3
  - 知识片段使用: X


============================================================
对比分析
============================================================

成功率对比:
  - 启用RAG: X/3
  - 未启用RAG: X/3
  - 改进: X.X%

执行时间对比:
  - 启用RAG: X.XX秒
  - 未启用RAG: X.XX秒
  - 差异: X.XX秒

知识使用情况:
  - 启用RAG: X 个知识片段
  - 未启用RAG: 0 个知识片段

结论:
  1. RAG系统提升了 X.X% 的成功率
  2. RAG系统增加了/减少了 X.XX秒 的执行时间
  3. RAG系统成功检索并使用了 X 个知识片段

================================================================================
测试完成！
================================================================================

详细日志: D:\project\Agent\HydroAgent\logs\test_rag_complex_comparison_20251011_123456.log
测试结果: D:\project\Agent\HydroAgent\logs\rag_comparison_results_20251011_123456.json
```

## 结果分析

### JSON结果文件结构

```json
{
  "test_time": "2025-10-11T12:34:56",
  "with_rag": {
    "test_name": "with_rag",
    "with_rag": true,
    "success": true,
    "duration_seconds": 123.45,
    "complex_tasks_count": 3,
    "complex_tasks_success": 3,
    "knowledge_chunks_used": 15,
    "workflow_result": {
      "status": "completed",
      "target_achieved": true,
      "iterations": 1,
      "task_count": 5
    }
  },
  "without_rag": {
    "test_name": "without_rag",
    "with_rag": false,
    "success": false,
    "duration_seconds": 98.76,
    "complex_tasks_count": 3,
    "complex_tasks_success": 1,
    "knowledge_chunks_used": 0,
    "workflow_result": {
      "status": "failed",
      "target_achieved": false
    }
  },
  "comparison": {
    "success_rate": {
      "with_rag": "3/3",
      "without_rag": "1/3",
      "improvement": 66.7
    },
    "execution_time": {
      "with_rag": 123.45,
      "without_rag": 98.76,
      "difference": 24.69
    },
    "knowledge_usage": {
      "with_rag": 15,
      "without_rag": 0
    },
    "conclusion": [
      "RAG系统提升了 66.7% 的成功率",
      "RAG系统增加了 24.69秒 的执行时间",
      "RAG系统成功检索并使用了 15 个知识片段"
    ]
  }
}
```

### 预期效果

#### RAG系统带来的改进

1. **成功率提升**
   - 无RAG：复杂任务可能因缺乏示例而失败
   - 有RAG：通过检索相关代码示例，生成正确代码

2. **代码质量提升**
   - 无RAG：生成的代码可能缺少错误处理
   - 有RAG：参考示例，生成更健壮的代码

3. **执行时间权衡**
   - RAG检索需要额外时间（通常<5秒）
   - 但可能通过减少重试次数来节省时间

## 注意事项

1. **测试不会实际执行工具**
   - 复杂任务主要测试代码生成能力
   - 简单任务会尝试调用工具（可能失败但不影响测试）

2. **日志很重要**
   - 所有详细信息都在日志中
   - 包括LLM的输入输出、知识检索结果等

3. **首次运行可能较慢**
   - RAG系统需要初始化向量数据库
   - Ollama首次加载模型需要时间

4. **结果可能有波动**
   - LLM输出有随机性
   - 建议多次运行取平均值

## 故障排查

### 问题1：RAG系统初始化失败
```
解决方法：
1. 检查 hydrorag/documents 目录是否存在
2. 确认文档文件是否创建
3. 查看日志中的具体错误信息
```

### 问题2：Ollama连接失败
```
解决方法：
1. 确认Ollama服务是否运行: ollama list
2. 检查模型是否下载: ollama pull qwen3:8b
3. 查看Ollama日志
```

### 问题3：导入错误
```
解决方法：
1. 确认项目路径正确
2. 检查 __init__.py 文件
3. 运行: uv sync 重新安装依赖
```

## 下一步工作

1. **扩展知识库**
   - 添加更多水文建模知识
   - 包含更多代码示例

2. **优化RAG检索**
   - 调整top_k参数
   - 优化查询关键词

3. **改进评估指标**
   - 增加代码质量评分
   - 添加执行成功率细分

4. **性能优化**
   - 缓存常用知识片段
   - 并行化RAG检索

## 总结

这个测试系统全面评估了RAG对复杂任务执行的影响，为后续优化提供了数据支持。通过对比实验，我们可以清楚地看到RAG系统在知识增强、代码生成质量等方面的实际效果。
