# HydroRAG与知识检索器集成测试

本目录包含了HydroRAG系统与工作流知识检索器集成的测试文件。

## 文件说明

### 1. `test_hydrorag_knowledge_integration.py`
完整的集成测试套件，包含以下测试：

- **测试1**: RAG系统设置
- **测试2**: 处理原始文档 
- **测试3**: 设置知识检索器
- **测试4**: 测试不同类型的查询
- **测试5**: 与工作流集成测试
- **测试6**: 系统健康检查

### 2. `demo_knowledge_integration.py`
快速演示脚本，展示基本的集成流程。

## 运行方式

### 运行完整测试

```bash
cd D:\MCP\HydroAgent
python test/test_hydrorag_knowledge_integration.py
```

### 运行快速演示

```bash
cd D:\MCP\HydroAgent  
python test/demo_knowledge_integration.py
```

### 运行单独的测试方法

```bash
cd D:\MCP\HydroAgent
python -m unittest test.test_hydrorag_knowledge_integration.TestHydroRAGKnowledgeIntegration.test_01_setup_rag_system -v
```

## 测试内容

### 测试的查询类型

1. **模型参数查询**: "GR4J模型有哪些参数？"
   - 期望关键词: X1, X2, X3, X4, 参数, GR4J

2. **模型率定查询**: "如何进行模型率定？"
   - 期望关键词: 率定, calibration, 优化, 参数调整

3. **模型评估查询**: "模型评估指标有哪些？"
   - 期望关键词: NSE, RMSE, MAE, 评估, 指标

4. **数据预处理查询**: "数据预处理包含哪些步骤？"
   - 期望关键词: 预处理, 清洗, 格式, 缺失值

5. **数据集查询**: "CAMELS数据集的特点"
   - 期望关键词: CAMELS, 数据集, 流域, 水文

### 测试的文档来源

测试会读取 `documents/raw/` 目录下的所有文档：

- `evaluation_metrics.txt` - 模型评估指标
- `gr4j_model.txt` - GR4J模型介绍
- `model_calibration.txt` - 模型率定方法
- `test_doc.txt` - 测试文档
- `markdown.md` - 完整的技术文档

## 预期结果

### 成功指标

- RAG系统成功初始化
- 文档成功处理并构建向量索引
- 知识检索器成功初始化
- 至少80%的查询能检索到相关结果
- 关键词匹配率 > 50%
- 系统健康检查通过

### 测试输出示例

```
🚀 开始HydroRAG系统与知识检索器集成测试
========================================

测试1：设置RAG系统
✅ RAG系统设置成功

测试2：处理原始文档
✅ 文档处理完成
   处理的文档数: 5
   失败的文档数: 0
   添加到向量库的块数: 25

测试3：设置知识检索器
✅ 知识检索器设置成功
   RAG系统可用: True
   回退模式启用: True
   默认知识库片段数: 5

测试4：测试不同类型的查询
--- 查询 1: 模型参数 ---
问题: GR4J模型有哪些参数？
检索到片段数: 3
  片段 1 (得分: 0.850):
    内容: GR4J是一个概念性水文模型，包含4个参数：X1土壤蓄水容量、X2地下水交换系数...
    来源: gr4j_model.txt
✅ 检索成功

...

测试结果总结
========================================
总查询数: 5
成功查询数: 5
成功率: 100.0%
关键词匹配率: 85.0%

🎉 所有测试通过！系统集成成功
```

## 工作流集成说明

测试成功后，知识检索器可以集成到工作流中：

1. **初始化阶段**: 在工作流启动时初始化知识检索器
2. **查询扩展**: 在查询扩展阶段使用检索器获取相关知识
3. **上下文增强**: 将检索到的知识片段添加到工作流上下文中
4. **答案生成**: 基于增强的上下文生成更准确的答案

### 集成示例代码

```python
from workflow.knowledge_retriever import KnowledgeRetriever
from hydrorag.rag_system import quick_setup

# 初始化
rag_system = quick_setup("./documents")
knowledge_retriever = KnowledgeRetriever(rag_system=rag_system)

# 在工作流中使用
def enhance_query_with_knowledge(user_query):
    fragments = knowledge_retriever.retrieve_knowledge(
        expanded_query=user_query,
        k=5,
        score_threshold=0.3
    )
    
    knowledge_context = knowledge_retriever.summarize_fragments(fragments)
    return knowledge_context
```

## 故障排除

### 常见问题

1. **Ollama连接失败**
   - 确保Ollama服务正在运行
   - 检查端口11434是否可访问

2. **文档处理失败**
   - 检查documents/raw目录是否存在
   - 确保文档格式正确

3. **向量存储初始化失败**
   - 检查chromadb是否正确安装
   - 确保有足够的磁盘空间

4. **查询无结果**
   - 降低score_threshold阈值
   - 检查查询关键词是否与文档内容匹配

### 调试模式

设置更详细的日志级别：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```
