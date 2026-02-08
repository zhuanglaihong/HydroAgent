# CustomAnalysisTool 问题修复方案

**日期**: 2025-12-24
**版本**: v1.0
**状态**: In Progress

---

## 📋 问题概述

实验A中Query 13-14（CustomAnalysisTool相关任务）失败并消耗大量token（~60k tokens）。

### 查询示例
- Query 13: `率定GR4J模型流域01013500后，分析洪峰流量的模拟误差`
- Query 14: `率定XAJ模型流域01539000后，统计枯水期的模拟精度`

### 失败表现
- 执行状态: `FAILED_UNRECOVERABLE`
- 错误类型: `Unknown error`
- 成功工具: 3/4 (validate, calibrate, evaluate成功; visualize失败)
- Token消耗: 59,031 - 63,788 tokens

---

## 🔍 根本原因分析

### 原因1: Optional Tool失败导致整体失败 ✅ **已修复**

**问题流程**:
```
1. VisualizationTool失败 (No module named 'hydromodel.visual')
2. ToolExecutor.execute_chain停止执行 (旧版不检查required字段)
3. RunnerAgent._aggregate_results判定 all(r.success) = False
4. FeedbackRouter归类为 unknown error
5. State Machine → FAILED_UNRECOVERABLE
```

**修复内容**:
- `hydroagent/tools/executor.py:174-190` - 检查`required`字段
- `hydroagent/agents/runner_agent.py:2207-2226` - 只检查required工具成功

**测试验证**: 需要重新运行实验A验证修复效果

---

### 原因2: IntentAgent误判任务类型 ❌ **未修复**

**问题**:
```python
Query: "率定GR4J模型流域01013500后，分析洪峰流量的模拟误差"

# 实际识别结果:
{
  "intent": "calibration",
  "task_type": "standard_calibration"
}

# 预期识别结果:
{
  "intent": "calibration",  # 第一步
  "task_type": "extended_analysis",  # 或compound_task
  "subtasks": [
    {"intent": "calibration", "task_type": "standard_calibration"},
    {"intent": "custom_analysis", "task_type": "custom_analysis"}
  ]
}
```

**根本问题**:
- IntentAgent没有识别"后，分析..."为复合任务
- 或者即使识别为复合任务，也没有正确识别第二个subtask为custom_analysis

**修复方案**:

#### 方案A: 增强IntentAgent的复合任务识别（推荐）

**修改文件**: `hydroagent/agents/intent_agent.py`

```python
# 1. 增强复合任务标记词
COMPOUND_TASK_MARKERS = [
    "后，",          # 已有
    "然后",          # 已有
    "接着",          # 已有
    "并",            # 新增: "率定并分析"
    "同时",          # 新增: "率定同时分析"
    "之后分析",      # 新增: 明确的"之后分析"
    "完成后分析",    # 新增
]

# 2. 增强自定义分析关键词
CUSTOM_ANALYSIS_KEYWORDS = [
    "分析",
    "统计",
    "计算",
    "诊断",
    "评价",
    "研究",
    "洪峰流量",      # 新增: 具体分析对象
    "枯水期",        # 新增
    "丰水期",        # 新增
    "径流系数",      # 新增
    "FDC",           # 新增
    "流量历时曲线",  # 新增
]

# 3. 优化第二个subtask的识别逻辑
def _parse_subtask(self, query_segment: str, context: Dict) -> Dict:
    """解析单个subtask，优先识别custom_analysis"""

    # 检查是否包含自定义分析关键词
    if any(kw in query_segment for kw in CUSTOM_ANALYSIS_KEYWORDS):
        # 构建专门的prompt识别custom_analysis
        prompt = f"""
用户需求: {query_segment}

这是一个复合任务的第二部分，请判断是否为自定义分析任务。

自定义分析任务的特征:
- 需要计算派生指标 (径流系数、水量平衡等)
- 需要统计分析 (洪峰误差、枯水期精度等)
- 需要绘制自定义图表 (FDC曲线、散点图等)
- 超出hydromodel的calibrate/evaluate/simulate功能范围

请返回JSON:
{{
    "intent": "custom_analysis",  # 如果是自定义分析
    "analysis_request": "具体的分析需求描述",
    ...
}}
"""
        # 调用LLM识别
        ...
```

#### 方案B: 优化TaskPlanner识别extended_analysis任务

**修改文件**: `hydroagent/agents/task_planner.py`

即使IntentAgent识别为standard_calibration，TaskPlanner也可以检测到分析需求并调整tool chain。

```python
def decompose_task(self, intent_result: Dict) -> Dict:
    """任务分解 - 增强custom_analysis检测"""

    # 获取原始查询
    original_query = self.context.get("original_query", "")

    # 检测是否需要custom_analysis (即使intent不是extended_analysis)
    needs_custom_analysis = any([
        "分析" in original_query and intent_result.get("intent") == "calibration",
        "统计" in original_query,
        "计算" in original_query and "参数" not in original_query,
        "洪峰" in original_query,
        "枯水期" in original_query,
    ])

    if needs_custom_analysis:
        # 覆盖task_type为extended_analysis
        intent_result["task_type"] = "extended_analysis"
        intent_result["analysis_request"] = self._extract_analysis_request(original_query)

    ...
```

#### 方案C: 简化 - 在ToolOrchestrator中检测（最简单）

**修改文件**: `hydroagent/agents/tool_orchestrator.py`

```python
def _rule_based_orchestration(
    self,
    task_type: str,
    intent_result: Dict[str, Any]
) -> Dict[str, Any]:
    """规则orchestration - 增强分析需求检测"""

    # 🆕 检测原始查询中的分析关键词
    original_query = intent_result.get("original_query", "")
    analysis_keywords = ["分析", "统计", "计算", "诊断", "洪峰", "枯水期"]

    has_analysis_request = any(kw in original_query for kw in analysis_keywords)

    # 如果是standard_calibration但包含分析需求，升级为extended_analysis
    if task_type == "standard_calibration" and has_analysis_request:
        logger.info(f"[ToolOrchestrator] Detected analysis request in calibration task, upgrading to extended_analysis")
        task_type = "extended_analysis"
        intent_result["analysis_request"] = original_query.split("后，")[-1] if "后，" in original_query else "自定义分析"

    # 继续原有逻辑
    ...
```

---

### 原因3: Token消耗统计不准确 ⚠️ **需要调查**

**发现**:
- JSON显示24-26次LLM调用
- 但日志中只找到1次实际调用
- 怀疑是实验框架的token统计累积问题

**修复方案**: 检查`base_experiment.py`的token统计逻辑

---

## ✅ 推荐修复顺序

### Phase 1: 立即修复（已完成）
- [x] ToolExecutor: Optional tool失败继续执行
- [x] RunnerAgent: 只检查required工具成功

### Phase 2: 核心修复（推荐优先）
- [ ] **方案C** - ToolOrchestrator检测分析需求（最简单，风险最低）
  - 文件: `hydroagent/agents/tool_orchestrator.py`
  - 修改量: ~10行代码
  - 影响范围: 只影响tool chain生成，不影响intent识别

### Phase 3: 长期优化（可选）
- [ ] **方案A** - 增强IntentAgent复合任务识别
  - 需要更新prompt
  - 需要extensive testing
- [ ] **方案B** - TaskPlanner智能调整task_type
  - 需要context传递
  - 可能影响其他实验

### Phase 4: 验证测试
- [ ] 重新运行实验A，验证Query 13-14成功
- [ ] 检查token消耗是否正常
- [ ] 验证CustomAnalysisTool被正确调用

---

## 📝 实施清单

### 必须修复（P0）
- [x] ToolExecutor: optional tool失败处理
- [x] RunnerAgent: required工具检查
- [ ] ToolOrchestrator: 检测分析需求并升级task_type

### 应该修复（P1）
- [ ] IntentAgent: 增强自定义分析关键词
- [ ] 验证测试: 重新运行实验A

### 可以优化（P2）
- [ ] CustomAnalysisTool._understand_task: 简化prompt减少token消耗
- [ ] Token统计: 修复累积统计问题

---

## 🧪 测试验证

### 测试用例
```python
# Test Case 1: Optional tool失败不影响整体成功
query = "率定GR4J模型流域01013500"
expected = {
    "success": True,  # 即使visualize失败
    "tools_success": {"validate": True, "calibrate": True, "evaluate": True, "visualize": False}
}

# Test Case 2: 自定义分析任务正确识别
query = "率定GR4J模型流域01013500后，分析洪峰流量的模拟误差"
expected = {
    "task_type": "extended_analysis",  # 不是standard_calibration
    "tool_chain": ["validate", "calibrate", "evaluate", "custom_analysis"]
}

# Test Case 3: Token消耗合理
query = "率定GR4J模型流域01013500后，统计枯水期的模拟精度"
expected = {
    "total_tokens": < 10000,  # 不应该超过10k
    "total_calls": < 10
}
```

---

## 📚 相关文件

- `hydroagent/tools/executor.py` - Tool执行器
- `hydroagent/agents/runner_agent.py` - 执行Agent
- `hydroagent/agents/intent_agent.py` - 意图识别
- `hydroagent/agents/tool_orchestrator.py` - 工具编排
- `hydroagent/tools/custom_analysis_tool.py` - 自定义分析工具
- `experiment/exp_A.py` - 实验A脚本

---

**下一步**: 实施Phase 2修复（ToolOrchestrator检测分析需求）
