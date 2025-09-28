# Builder系统 - 智能工作流构建器

Builder系统是HydroAgent的核心规划层，负责将用户的自然语言指令转换为可执行的工作流。系统采用模块化设计，结合规则匹配、RAG知识检索和LLM推理，实现高效准确的工作流生成。

## 🏗️ 系统架构

```
用户指令 → 意图解析 → 执行模式分析 → RAG规划 → 工作流输出
          ↓            ↓              ↓
      规则匹配    复杂度评估      知识增强推理
      (快速)      (轻量级)        (LLM推理)
```

### 设计理念

Builder系统采用**混合架构**设计，平衡性能与功能：

- **快速响应层**：意图解析和模式分析使用规则匹配，确保毫秒级响应
- **智能推理层**：RAG规划使用LLM推理，保证工作流质量和准确性
- **灵活配置**：支持API和本地LLM模式，适应不同部署环境

## 📁 模块组成

### 核心组件

| 组件 | 文件 | 功能 | LLM使用 | 响应时间 |
|------|------|------|---------|---------|
| **工作流构建器** | `workflow_builder.py` | 总体协调和工作流组装 | 控制器 | 1-10秒 |
| **意图解析器** | `intent_parser.py` | 指令理解和实体识别 | ❌ 规则匹配 | < 0.01秒 |
| **执行模式分析器** | `execution_mode.py` | 执行模式推荐 | ❌ 规则评估 | < 0.05秒 |
| **RAG规划器** | `rag_planner.py` | 知识检索和思维链推理 | ✅ LLM推理 | 1-5秒 |
| **LLM客户端** | `llm_client.py` | 统一的LLM调用接口 | ✅ API/本地 | 按需 |

### 支持组件

| 组件 | 功能 | 说明 |
|------|------|------|
| **API客户端** | `api_client.py` | OpenAI API调用封装 |
| **提示模板** | `prompts/` | 结构化的LLM提示模板 |

## 🚀 快速开始

### 基本使用

```python
from builder.workflow_builder import WorkflowBuilder

# 创建构建器实例（推荐配置）
builder = WorkflowBuilder(
    enable_rag=True,        # 启用RAG知识检索
    use_api_llm=False       # 使用本地Ollama（稳定快速）
)

# 构建工作流
result = builder.build_workflow("生成完整的GR4J模型率定和评估工作流")

if result.success:
    workflow = result.workflow
    print(f"工作流名称: {workflow['name']}")
    print(f"任务数量: {len(workflow['tasks'])}")
    print(f"执行模式: {result.execution_mode.value}")
    print(f"构建时间: {result.build_time:.2f}秒")

    # 意图分析结果
    print(f"识别意图: {result.intent_result.intent_type.value}")
    print(f"意图置信度: {result.intent_result.confidence:.2f}")
else:
    print(f"构建失败: {result.error_message}")
```

### LLM模式控制

```python
# 方式1: 本地Ollama模式（推荐 - 快速稳定）
builder = WorkflowBuilder(use_api_llm=False)

# 方式2: API优先模式（功能强大但可能超时）
builder = WorkflowBuilder(use_api_llm=True)

# 方式3: 禁用RAG的轻量模式（测试专用）
builder = WorkflowBuilder(enable_rag=False)

# 方式4: 完全规则模式（最快，功能有限）
builder = WorkflowBuilder(enable_rag=False)
```

## 📋 详细使用指南

### 1. 意图解析器 (IntentParser)

负责快速理解用户意图，**默认不使用LLM**以确保响应速度。

```python
from builder.intent_parser import IntentParser

# 默认配置（推荐 - 纯规则匹配）
parser = IntentParser()  # 毫秒级响应

# 特殊场景启用LLM增强（不推荐）
parser = IntentParser(enable_llm_enhancement=True)

# 解析指令
result = parser.parse_instruction("率定GR4J模型并评估性能")
print(f"意图类型: {result.intent_type.value}")
print(f"实体识别: {result.entities}")
print(f"建议工具: {result.suggested_tools}")
```

**支持的意图类型：**
- `data_acquisition` - 数据获取和准备
- `model_calibration` - 模型参数率定
- `model_simulation` - 模型运行模拟
- `model_evaluation` - 模型性能评估
- `visualization` - 数据可视化
- `content_generation` - 内容生成
- `control_operation` - 控制操作

**实体识别能力：**
- **模型名称**：GR4J, XAJ, LSTM, GR1Y, GR2M等
- **时间范围**：2020-2022, 最近3年, 从2010到2020等
- **参数名称**：X1-X6, 学习率, 批量大小等
- **数据类型**：降雨量, 径流量, 蒸发量, 温度等
- **文件路径**：支持各种数据文件格式
- **阈值条件**：性能指标阈值等

### 2. 执行模式分析器 (ExecutionModeAnalyzer)

评估任务复杂度并推荐执行模式，使用轻量级规则评估。

```python
from builder.execution_mode import ExecutionModeAnalyzer

analyzer = ExecutionModeAnalyzer()
result = analyzer.analyze_execution_mode(intent_result, query)

print(f"推荐模式: {result.recommended_mode.value}")
print(f"复杂度评分: {result.complexity_score:.2f}")
print(f"推荐理由: {result.reasoning}")
print(f"检测特征: {result.features}")
```

**执行模式类型：**
- `sequential` - 顺序执行（默认，适合标准流程）
- `parallel` - 并行执行（独立任务可同时运行）
- `react` - 反应式执行（需要条件判断、循环和反馈）

**复杂度评估维度：**
- 优化和迭代需求
- 条件判断复杂性
- 并行处理可能性
- 用户交互需求
- 错误处理要求

### 3. RAG规划器 (RAGPlanner)

使用检索增强生成进行工作流规划，**需要LLM推理**。

```python
from builder.rag_planner import RAGPlanner

planner = RAGPlanner(rag_system=rag_system, llm_client=llm_client)

result = planner.plan_workflow(
    intent_result=intent_result,
    execution_mode=ExecutionMode.SEQUENTIAL,
    context={"dataset": "camels_11532500", "model": "GR4J"}
)

print(f"规划时间: {result.planning_time:.2f}秒")
print(f"思维链步骤: {len(result.cot_steps)}")
print(f"知识片段数: {len(result.rag_context.fragments)}")
```

**规划过程：**
1. **知识检索** - 从向量数据库检索相关文档
2. **思维链推理** - 逐步分解复杂任务
3. **工具映射** - 匹配可用的4个执行工具
4. **工作流组装** - 生成完整的JSON工作流
5. **格式验证** - 确保输出符合执行器要求

### 4. LLM客户端 (LLMClient)

统一的LLM调用接口，支持API和本地模式自动切换。

```python
from builder.llm_client import LLMClient, get_llm_client

# 获取默认客户端
client = get_llm_client()

# 自定义配置
client = LLMClient(
    use_api_first=False,    # 优先使用本地Ollama
    force_local=True        # 强制本地模式，避免API超时
)

# 调用LLM
response = client.generate(
    prompt="请分析这个水文建模任务的复杂度",
    temperature=0.3,
    max_tokens=500
)

if response.success:
    print(f"响应内容: {response.content}")
    print(f"使用模型: {response.model_used}")
    print(f"响应时间: {response.response_time:.2f}秒")
```

**客户端特性：**
- **API优先**: 默认尝试API调用，功能强大
- **本地降级**: API失败时自动切换到Ollama
- **强制本地**: 可配置仅使用本地模型
- **调用统计**: 记录成功率和响应时间
- **错误处理**: 完整的超时和重试机制

## 🔧 配置选项

### WorkflowBuilder参数详解

```python
WorkflowBuilder(
    rag_system=None,        # RAG系统实例，None则自动初始化
    llm_client=None,        # LLM客户端，None则使用默认配置
    enable_rag=True,        # 是否启用RAG系统
    use_api_llm=False       # LLM模式选择
)
```

### LLM模式对比

| 模式 | use_api_llm | 优点 | 缺点 | 适用场景 |
|------|-------------|------|------|----------|
| **本地模式** | `False` | 快速、稳定、无网络依赖 | 功能相对有限 | 开发测试、离线环境 |
| **API模式** | `True` | 功能强大、效果优秀 | 需要网络、可能超时 | 生产环境、复杂任务 |

### 配置建议

```python
# 开发调试环境
builder = WorkflowBuilder(enable_rag=False)  # 最快

# 测试环境
builder = WorkflowBuilder(use_api_llm=False)  # 稳定

# 生产环境
builder = WorkflowBuilder(use_api_llm=True)   # 最优效果
```

## 📊 性能特征

### 处理时间基准

| 组件 | 本地模式 | API模式 | 说明 |
|------|----------|---------|------|
| 意图解析 | < 0.01秒 | < 0.01秒 | 纯规则匹配，不使用LLM |
| 模式分析 | < 0.05秒 | < 0.05秒 | 轻量级评估算法 |
| RAG规划 | 1-3秒 | 2-8秒 | 取决于网络和模型 |
| **总体构建** | **1-5秒** | **2-15秒** | 包含所有步骤 |

### 内存使用

- **基础模式** (enable_rag=False): ~50MB
- **本地LLM模式**: ~2GB (Ollama模型)
- **API模式**: ~100MB (仅网络调用)

### 并发能力

- **意图解析**: 支持高并发（无状态）
- **RAG规划**: 受LLM并发限制
- **建议**: 生产环境使用连接池管理

## 🧪 测试和调试

### 运行测试套件

```bash
# 基础功能测试（最快，无LLM依赖）
python test/test_intent_parser.py --skip-llm

# 完整集成测试（本地LLM模式）
python test/test_workflow_builder.py

# API模式测试（需要网络）
python test/test_workflow_builder.py --use-api

# 模拟测试（生成测试日志，无实际调用）
python test/test_workflow_builder.py --simulate

# 性能诊断测试
python test/test_intent_parser.py --quick
```

### 调试和诊断

```python
# 1. 启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 2. 检查组件状态
status = builder.is_ready()
for component, ready in status.items():
    print(f"{component}: {'✓' if ready else '✗'}")

# 3. 分析构建结果
result = builder.build_workflow(query)
print(f"意图分析: {result.intent_result.to_dict()}")
print(f"模式分析: {result.mode_analysis.__dict__}")
print(f"规划统计: 用时{result.planning_result.planning_time:.2f}秒")

# 4. 性能监控
print(f"构建统计: {builder.get_stats()}")
```

### 性能诊断工具

```python
# 诊断LLM调用瓶颈
def diagnose_llm_performance():
    from builder.llm_client import get_llm_client
    import time

    client = get_llm_client()
    start = time.time()
    response = client.generate("测试响应速度", max_tokens=50)
    end = time.time()

    print(f"LLM响应时间: {end-start:.3f}秒")
    print(f"LLM可用性: {client.is_available()}")
    return end - start < 5.0  # 5秒内为可接受

# 诊断意图解析性能
def diagnose_intent_performance():
    from builder.intent_parser import IntentParser
    import time

    parser = IntentParser()  # 默认无LLM配置
    start = time.time()
    result = parser.parse_instruction("测试意图解析速度")
    end = time.time()

    print(f"意图解析时间: {end-start:.3f}秒")
    return end - start < 0.1  # 100ms内为优秀
```

## 🔍 故障排除

### 常见问题及解决方案

1. **意图解析器响应慢**
   ```python
   # 问题：误启用了LLM增强
   # 解决：确保使用默认配置
   parser = IntentParser()  # 正确
   # parser = IntentParser(enable_llm_enhancement=True)  # 错误
   ```

2. **API调用超时**
   ```python
   # 问题：网络不稳定或API限制
   # 解决：切换到本地模式
   builder = WorkflowBuilder(use_api_llm=False)
   ```

3. **RAG系统初始化失败**
   ```python
   # 问题：嵌入模型不可用
   # 解决：禁用RAG或检查Ollama服务
   builder = WorkflowBuilder(enable_rag=False)
   # 或检查: ollama list
   ```

4. **工作流生成质量差**
   ```python
   # 问题：知识库不完整或模型限制
   # 解决：更新知识库或使用API模式
   builder = WorkflowBuilder(use_api_llm=True)
   ```

5. **内存占用过高**
   ```python
   # 问题：Ollama模型占用内存
   # 解决：使用API模式或优化模型
   builder = WorkflowBuilder(use_api_llm=True)
   ```

### 性能优化建议

1. **开发阶段**:
   ```python
   builder = WorkflowBuilder(enable_rag=False)  # 最快响应
   ```

2. **测试环境**:
   ```python
   builder = WorkflowBuilder(use_api_llm=False)  # 稳定可靠
   ```

3. **生产环境**:
   ```python
   builder = WorkflowBuilder(use_api_llm=True)  # 最佳效果
   ```

4. **批量处理**:
   ```python
   # 复用构建器实例，避免重复初始化
   builder = WorkflowBuilder()
   for query in queries:
       result = builder.build_workflow(query)
   ```

## 📈 扩展开发

### 添加新的意图类型

```python
# 1. 在 IntentType 枚举中添加
class IntentType(Enum):
    DATA_VISUALIZATION = "data_visualization"  # 新增

# 2. 更新关键词映射
self.intent_keywords[IntentType.DATA_VISUALIZATION] = [
    "可视化", "绘图", "图表", "展示"
]

# 3. 更新工具映射
self.tool_mapping[IntentType.DATA_VISUALIZATION] = [
    "evaluate_model"  # 可视化通常在评估中
]
```

### 自定义LLM客户端

```python
from builder.llm_client import LLMClient

class CustomLLMClient(LLMClient):
    def generate(self, prompt, **kwargs):
        # 实现自定义逻辑
        # 例如：调用本地部署的其他模型
        return custom_model_call(prompt, **kwargs)

# 使用自定义客户端
builder = WorkflowBuilder(llm_client=CustomLLMClient())
```

### 添加新的执行模式

```python
# 1. 在 ExecutionMode 枚举中添加
class ExecutionMode(Enum):
    STREAM = "stream"  # 流式处理模式

# 2. 更新分析逻辑
def _detect_stream_mode(self, query: str) -> bool:
    stream_keywords = ["实时", "流式", "在线"]
    return any(keyword in query for keyword in stream_keywords)

# 3. 更新 RAG 规划器支持新模式
```

## 🌟 最佳实践

### 代码示例

```python
from builder.workflow_builder import WorkflowBuilder
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)

class HydroWorkflowService:
    def __init__(self, mode="production"):
        """水文工作流服务

        Args:
            mode: "development", "testing", "production"
        """
        if mode == "development":
            self.builder = WorkflowBuilder(enable_rag=False)
        elif mode == "testing":
            self.builder = WorkflowBuilder(use_api_llm=False)
        else:  # production
            self.builder = WorkflowBuilder(use_api_llm=True)

    def create_workflow(self, user_query: str, context: dict = None):
        """创建工作流

        Returns:
            dict: 包含工作流和元数据的结果
        """
        try:
            result = self.builder.build_workflow(user_query, context)

            if result.success:
                return {
                    "success": True,
                    "workflow": result.workflow,
                    "metadata": {
                        "intent_type": result.intent_result.intent_type.value,
                        "execution_mode": result.execution_mode.value,
                        "build_time": result.build_time,
                        "complexity": result.mode_analysis.complexity_score
                    }
                }
            else:
                return {
                    "success": False,
                    "error": result.error_message
                }

        except Exception as e:
            logging.error(f"工作流创建失败: {e}")
            return {"success": False, "error": str(e)}

    def health_check(self):
        """健康检查"""
        status = self.builder.is_ready()
        return {
            "overall_ready": status["overall_ready"],
            "components": status
        }

# 使用示例
service = HydroWorkflowService(mode="production")

# 健康检查
health = service.health_check()
print(f"服务状态: {health}")

# 创建工作流
result = service.create_workflow(
    "率定GR4J模型并评估在camels_11532500数据集上的性能",
    context={"dataset": "camels_11532500", "optimization_target": "NSE"}
)

if result["success"]:
    workflow = result["workflow"]
    print(f"✓ 工作流创建成功: {workflow['name']}")
    print(f"  执行模式: {result['metadata']['execution_mode']}")
    print(f"  任务数量: {len(workflow['tasks'])}")
    print(f"  构建时间: {result['metadata']['build_time']:.2f}秒")
else:
    print(f"✗ 工作流创建失败: {result['error']}")
```

## 📚 相关文档

- [HydroAgent总体架构](../README.md)
- [RAG系统文档](../hydrorag/README.md)
- [工作流执行引擎](../hydrotool/README.md)
- [MCP集成文档](../hydromcp/README.md)

## 🤝 贡献指南

1. **代码风格**: 遵循项目现有的代码风格和架构设计
2. **性能优先**: 新功能不应影响现有性能表现
3. **测试覆盖**: 为新功能添加完整的单元测试和集成测试
4. **文档更新**: 更新相关文档和使用示例
5. **向后兼容**: 确保新版本与现有接口兼容

### 提交检查清单

- [ ] 代码通过所有现有测试
- [ ] 新功能有对应的测试用例
- [ ] 性能没有显著退化
- [ ] 文档已更新
- [ ] 示例代码可正常运行

---

**设计理念**: Builder系统优先考虑性能和稳定性，采用"快速响应 + 智能推理"的混合架构。意图解析使用规则匹配确保毫秒级响应，复杂工作流生成使用LLM推理保证质量。这种设计在保证功能完整性的同时最大化了系统的响应速度和可靠性。