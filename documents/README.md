# HydroAgent 文档中心

本目录包含HydroAgent项目的所有知识文档，用于RAG系统的知识检索和LLM代码生成。

## 目录结构

```
documents/
├── README.md                      # 本文件 - 文档索引
├── tools/                         # 工具示例代码
│   ├── prepare_data.md           # 数据准备工具
│   ├── calibrate_model.md        # 模型率定工具
│   └── evaluate_model.md         # 模型评估工具
├── knowledge/                     # 领域知识库
│   ├── hydro_data_analysis.md    # 水文数据分析知识
│   └── code_generation_patterns.md # 代码生成模式
└── guides/                        # 使用指南
    └── rag_complex_test_guide.md  # RAG复杂任务测试指南
```

## 文档分类

### 📦 工具文档 (tools/)

包含HydroAgent系统中各个工具的完整实现代码、使用示例和API文档。这些文档用于帮助LLM理解如何正确使用现有工具。

#### prepare_data.md
- **用途**：水文数据预处理工具
- **功能**：CSV/TXT转NetCDF、数据验证、时间尺度转换
- **包含内容**：
  - 完整实现代码
  - 参数说明和返回值格式
  - 使用示例（基本用法、不同时间尺度）
  - 常见问题和解决方案
  - 输入输出格式规范

#### calibrate_model.md
- **用途**：水文模型参数率定工具
- **功能**：SCE-UA算法优化模型参数
- **包含内容**：
  - 核心实现代码
  - 模型配置说明（GR4J、XAJ等）
  - 算法参数调优指南
  - 交叉验证示例
  - 参数范围配置
  - 最佳实践建议

#### evaluate_model.md
- **用途**：模型性能评估工具
- **功能**：计算NSE、R2、RMSE等评估指标
- **包含内容**：
  - 评估实现代码
  - 评估指标详细说明
  - 训练期/测试期对比
  - 结果解读指南
  - 性能诊断方法

### 📚 知识文档 (knowledge/)

包含水文建模和代码生成的领域知识，用于增强LLM的专业能力。

#### hydro_data_analysis.md
- **用途**：水文数据分析完整知识库
- **包含内容**：
  - 数据读取方法（CSV、NetCDF）
  - 质量检查（缺失值、异常值、完整性）
  - 统计分析（基础统计、时间序列模式）
  - 极端事件识别（极端降雨、洪水）
  - 降雨-径流关系分析（相关性、径流系数）
  - 数据可视化（时间序列图、统计图表）
  - 完整分析示例代码

#### code_generation_patterns.md
- **用途**：代码生成标准模式和最佳实践
- **包含内容**：
  - 标准代码结构模板
  - 5种常见任务代码模式：
    1. 数据统计分析
    2. 时间序列特征提取
    3. 数据可视化
    4. 事件识别
    5. 相关性分析
  - 复杂任务组合模式
  - 错误处理最佳实践
  - 代码质量检查清单
  - 代码生成提示词模板

### 📖 使用指南 (guides/)

详细的使用文档和教程。

#### rag_complex_test_guide.md
- **用途**：RAG系统对复杂任务影响测试指南
- **包含内容**：
  - 测试系统概述
  - 文件结构说明
  - 复杂任务工作流详解
  - RAG知识库说明
  - 执行器修改说明
  - 运行测试步骤
  - 结果分析方法
  - 故障排查指南

## RAG系统集成

这些文档被集成到HydroAgent的RAG（Retrieval-Augmented Generation）系统中，用于：

1. **知识检索**：当执行复杂任务时，RAG系统会检索相关文档片段
2. **代码生成**：LLM使用检索到的代码示例和模式生成高质量代码
3. **工具理解**：帮助LLM正确理解和使用现有工具
4. **问题解决**：提供常见问题的解决方案

### RAG配置

documents目录由`hydrorag/rag_system.py`管理：

```python
# 初始化RAG系统
from hydrorag.rag_system import HydroRAG

rag_system = HydroRAG(
    collection_name="hydro_knowledge",
    persist_directory="hydrorag/chroma_db"
)

# 加载documents目录
rag_system.add_documents_from_directory("documents/")
```

### 文档更新流程

1. **添加新文档**：在相应子目录创建`.md`文件
2. **更新索引**：运行RAG系统重新索引
3. **测试检索**：验证新文档能被正确检索
4. **更新本README**：添加新文档说明

## 文档编写规范

### 格式要求

1. **Markdown格式**：所有文档使用Markdown格式
2. **代码块标注**：使用```python标注Python代码
3. **结构清晰**：使用标题层级组织内容
4. **示例完整**：提供可运行的完整代码示例

### 内容要求

1. **准确性**：确保技术内容正确无误
2. **完整性**：包含所有必要的信息
3. **可理解**：使用清晰的语言和示例
4. **可检索**：包含关键词便于RAG检索

### 工具文档模板

```markdown
# 工具名称

## 工具标识
tool_name - 工具描述

## 功能描述
详细功能说明

## 核心实现代码
\```python
# 完整可运行的实现代码
\```

## 使用示例
### 示例1: 基本用法
\```python
# 示例代码
\```

## 参数说明
| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|

## 返回值说明
详细说明返回值格式

## 常见问题
列出常见问题和解决方案

## 最佳实践
使用建议和注意事项
```

## 使用示例

### 1. 人工查阅

直接浏览documents目录下的文档：

```bash
# 查看工具文档
cat documents/tools/prepare_data.md

# 查看知识文档
cat documents/knowledge/hydro_data_analysis.md

# 查看使用指南
cat documents/guides/rag_complex_test_guide.md
```

### 2. RAG系统检索

在代码中使用RAG系统检索：

```python
from hydrorag.rag_system import HydroRAG

# 初始化
rag = HydroRAG()

# 检索相关知识
results = rag.search("如何进行水文数据分析", top_k=3)
for result in results:
    print(f"来源: {result['source']}")
    print(f"内容: {result['content']}")
```

### 3. 测试系统

使用RAG对比测试验证文档效果：

```bash
# 运行RAG对比测试
python test/test_rag_complex_workflow_comparison.py

# 查看测试结果
cat logs/rag_comparison_results_*.json
```

## 维护和更新

### 定期维护

- **月度检查**：检查文档内容是否过时
- **版本同步**：代码更新时同步更新文档
- **质量审核**：确保示例代码可运行

### 扩展计划

未来计划添加的文档：

- [ ] `tools/advanced_calibration.md` - 高级率定策略
- [ ] `tools/model_comparison.md` - 模型对比工具
- [ ] `knowledge/model_selection.md` - 模型选择知识
- [ ] `knowledge/parameter_sensitivity.md` - 参数敏感性分析
- [ ] `guides/workflow_design.md` - 工作流设计指南

## 相关资源

- **主项目文档**：`README.md`
- **项目指南**：`CLAUDE.md`
- **RAG系统文档**：`hydrorag/README.md`
- **测试文档**：`test/README.md`

## 贡献指南

欢迎贡献新的文档！请遵循以下步骤：

1. 在相应子目录创建文档
2. 遵循文档编写规范
3. 更新本README索引
4. 提交前测试RAG检索效果

## 许可证

本文档集合遵循项目主许可证。

---

**文档版本**: v1.0
**最后更新**: 2025-10-11
**维护者**: HydroAgent Team
