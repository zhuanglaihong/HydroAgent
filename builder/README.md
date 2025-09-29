# Builder系统 - 智能工作流构建器

Builder系统是HydroAgent的核心规划层，负责将用户的自然语言指令转换为可执行的工作流。系统采用**五阶段工作流构建流程**，结合意图解析、RAG知识检索、思维链推理和智能模式分析，实现高质量的工作流生成。

## 🏗️ 五阶段工作流构建架构

```text
用户查询 → [意图解析] → [RAG规划] → [执行模式分析] → [模式应用] → [工作流最终化]
    ↓            ↓           ↓            ↓            ↓
  原始查询    意图理解    知识增强规划   模式推荐    优化配置   → 可执行工作流
```

### 工作流程详解

1. **阶段1: 意图解析与理解** - 基于规则匹配快速识别用户意图和实体
2. **阶段2: RAG规划生成工作流** - 结合知识检索和思维链推理生成初步工作流
3. **阶段3: 执行模式分析** - 基于复杂度评分智能推荐执行模式
4. **阶段4: 执行模式应用** - 针对不同模式优化工作流配置
5. **阶段5: 工作流最终化** - 添加元数据、验证和确保完整性

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

基于多维度特征检测和加权评分机制，智能评估任务复杂度并推荐最适合的执行模式。

```python
from builder.execution_mode import ExecutionModeAnalyzer

analyzer = ExecutionModeAnalyzer()
result = analyzer.analyze_workflow(workflow)

print(f"推荐模式: {result.recommended_mode.value}")
print(f"复杂度评分: {result.complexity_score:.2f}")
print(f"推荐理由: {result.reasoning}")
print(f"检测特征: {result.features}")
```

**执行模式类型：**
- `LINEAR` - 线性执行（简单顺序任务，复杂度 < 0.3）
- `REACT` - 反应式执行（复杂推理任务，复杂度 ≥ 0.7 或包含率定/反馈）
- `HYBRID` - 混合模式（中等复杂度任务，0.3 ≤ 复杂度 < 0.7）

#### **复杂度评分机制详解**

**六个评分维度及权重：**
```python
complexity_weights = {
    "task_count": 0.1,          # 任务数量权重 (10%)
    "dependency_depth": 0.2,     # 依赖深度权重 (20%)
    "branch_count": 0.15,        # 分支数量权重 (15%)
    "loop_count": 0.25,          # 循环数量权重 (25%) - 最高权重
    "condition_count": 0.15,     # 条件数量权重 (15%)
    "complex_task_ratio": 0.15,  # 复杂任务比例权重 (15%)
}
```

**特征检测列表：**
```python
features = {
    "has_loops": False,              # 循环任务 (retry_count > 1)
    "has_conditions": False,         # 条件判断 (if/while)
    "has_complex_tasks": False,      # 复杂推理任务 (task_type="complex")
    "has_parallel_branches": False,  # 并行分支
    "has_error_handling": False,     # 错误处理 (on_error/timeout)
    "has_dynamic_params": False,     # 动态参数 (${variable})
    "requires_feedback": False,      # 反馈循环
    "has_model_calibration": False,  # 模型率定 (calibrate动作)
}
```

**评分计算示例：**
- **任务数量评分**: `min(task_count / 10.0, 1.0)` (10个任务为满分)
- **依赖深度评分**: `min(max_depth / 5.0, 1.0)` (5层依赖为满分)
- **循环数量评分**: `min(loop_count / 2.0, 1.0)` (2个循环为满分)
- **复杂任务比例**: `complex_tasks / total_tasks` (全部复杂为满分)

**模式推荐决策规则：**
```python
# 高复杂度特征列表
high_complexity_features = [
    "has_loops", "has_conditions", "requires_feedback",
    "has_model_calibration", "has_dynamic_params"
]

# 决策逻辑
if complexity_score >= 0.7 or high_complexity_count >= 3:
    return ExecutionMode.REACT      # 反应模式
elif has_model_calibration or requires_feedback:
    return ExecutionMode.REACT      # 特殊情况强制反应模式
elif complexity_score >= 0.4 or has_parallel_branches:
    return ExecutionMode.HYBRID     # 混合模式
else:
    return ExecutionMode.LINEAR     # 线性模式
```

**实际应用示例：**

*简单任务 (LINEAR)*:
```json
{
  "tasks": [{"action": "get_model_params", "task_type": "simple"}]
}
// 复杂度评分: ≈0.05 → LINEAR模式
```

*中等复杂任务 (HYBRID)*:
```json
{
  "tasks": [
    {"action": "prepare_data", "task_type": "simple"},
    {"action": "analyze_data", "task_type": "complex", "retry_count": 2}
  ]
}
// 有复杂任务+循环 → 复杂度评分: ≈0.5 → HYBRID模式
```

*高复杂任务 (REACT)*:
```json
{
  "tasks": [{
    "action": "calibrate_model", "task_type": "complex",
    "conditions": {"retry_count": 3, "if": "${score} < 0.8"},
    "feedback_enabled": true
  }]
}
// 模型率定+循环+条件+反馈 → 强制REACT模式
```

### 3. RAG规划器 (RAGPlanner)

RAG规划器是Builder系统的核心智能组件，结合知识检索和思维链推理，生成高质量的工作流。

```python
from builder.rag_planner import RAGPlanner

planner = RAGPlanner(rag_system=rag_system, llm_client=llm_client)

result = planner.plan_workflow(
    query="率定GR4J模型并评估性能",
    context={
        "dataset": "camels_11532500",
        "intent_result": intent_result,
        "suggested_tools": ["prepare_data", "calibrate_model"]
    }
)

print(f"规划时间: {result.planning_time:.2f}秒")
print(f"思维链步骤: {len(result.cot_steps)}")
print(f"知识片段数: {len(result.rag_context.fragments)}")
```

#### **三阶段RAG规划流程**

**阶段1: 知识检索 (HydroRAG集成)**
```python
def _retrieve_knowledge(self, query):
    # 1. 查询扩展和预处理
    expanded_queries = self._expand_query(query)

    # 2. 调用HydroRAG进行多级检索
    result = self.rag_system.query(
        query_text=query,
        top_k=COT_KNOWLEDGE_CHUNKS,  # 默认5个知识片段
        enable_rerank=True,          # 启用重排序优化
        enable_expansion=True        # 启用查询扩展
    )

    # 3. 转换为知识片段格式
    fragments = [
        KnowledgeFragment(
            content=item["content"],
            source=item["metadata"]["source_file"],
            score=item["score"],
            fragment_type=self._classify_fragment_type(item["content"])
        ) for item in result.get("results", [])
    ]

    return RAGContext(query, fragments, len(fragments), retrieval_time)
```

**阶段2: 思维链推理 (CoT)**
```python
def _chain_of_thought_reasoning(self, query, rag_context):
    cot_steps = []

    # 生成推理步骤 (最多5次迭代)
    for i in range(COT_MAX_ITERATIONS):
        step_question = self._generate_step_question(query, i, rag_context)

        # 调用LLM进行推理
        reasoning_response = self.llm_client.generate(
            prompt=self._build_cot_prompt(step_question, rag_context),
            temperature=COT_TEMPERATURE,  # 0.2，保持推理稳定性
            max_tokens=2000
        )

        step = CoTStep(
            step_number=i+1,
            question=step_question,
            reasoning=reasoning_response.content,
            conclusion=self._extract_conclusion(reasoning_response.content),
            confidence=reasoning_response.confidence
        )
        cot_steps.append(step)

        # 判断是否需要继续推理
        if self._should_stop_reasoning(step, cot_steps):
            break

    return cot_steps
```

**阶段3: 工作流生成**
```python
def _generate_workflow_with_knowledge(self, query, rag_context, cot_steps):
    # 构建综合提示词，包含：
    # - 用户原始查询
    # - 检索到的知识片段
    # - 思维链推理结论
    # - 可用工具列表和规范

    # 调用LLM生成结构化工作流
    workflow_response = self.llm_client.generate(
        prompt=self._build_workflow_generation_prompt(...),
        temperature=0.1,  # 低温度确保结构稳定
        max_tokens=4000
    )

    # 解析和验证JSON格式
    workflow = self._parse_and_validate_workflow(workflow_response.content)

    return workflow
```

#### **知识增强特性**

**知识片段分类：**
```python
fragment_types = {
    "model_definition": "模型定义和原理",
    "calibration_method": "率定方法和技巧",
    "parameter_guidance": "参数设置指导",
    "code_example": "代码实现示例",
    "best_practice": "最佳实践建议"
}
```

**思维链推理示例：**
```text
CoT步骤1: 任务分解
问题: 如何将"率定GR4J模型"分解为具体步骤？
推理: 根据知识片段，GR4J率定需要数据准备、参数初始化、优化算法选择、结果评估等步骤
结论: 分解为4个主要任务：数据准备→模型率定→性能评估→结果可视化

CoT步骤2: 工具映射
问题: 每个步骤应该使用哪些可用工具？
推理: prepare_data用于数据准备，calibrate_model用于率定，evaluate_model用于评估
结论: 工具序列为 prepare_data → calibrate_model → evaluate_model

CoT步骤3: 参数配置
问题: 每个工具需要什么参数配置？
推理: 基于知识片段中的参数说明和最佳实践，设置合适的默认值
结论: 生成详细的参数配置方案
```

#### **工作流生成特点**

- **知识驱动**: 基于检索到的专业知识生成任务步骤
- **结构化输出**: 严格按照执行器要求的JSON格式
- **参数智能化**: 根据领域知识自动设置合理参数
- **依赖管理**: 智能分析任务依赖关系
- **错误预防**: 基于最佳实践添加错误处理机制

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