# IntentAgent 混合策略 (Rule + LLM)

**Version**: v5.1
**Date**: 2025-12-22
**Status**: ✅ Implemented

---

## 🎯 问题背景

### 原问题
用户查询："批量率定3个流域（12025000, 14301000, 14306500），使用XAJ模型，完成后计算各流域的径流系数"

**期望**:
- Task Type: `batch_processing`
- 拆解为: 3个并行calibration + 1个aggregated analysis (径流系数)

**实际（v5.0之前）**:
- Task Type: `extended_analysis` ❌
- 原因: "径流系数"关键词在规则检测中优先级高于"批量"
- 结果: LLM错误拆解为7个串行任务（只计算了第一个流域的径流系数）

### 根本原因
纯规则检测存在**优先级冲突**问题：
```python
# 旧代码结构
if "径流系数" in query:
    return "extended_analysis"  # 优先匹配
if "批量" in query or len(basins) > 1:
    return "batch_processing"   # 永远不会执行
```

---

## 💡 解决方案：混合策略

采用**规则优先 + LLM兜底**的三步策略：

```
User Query
    ↓
Step 1: 规则检测（快速）
    → 返回所有匹配的task_type + 置信度
    ↓
Step 2: 冲突检测
    → 如果只有1个匹配 → 直接返回（高效）
    → 如果有多个匹配 → 进入Step 3
    ↓
Step 3: LLM智能分析（准确）
    → 根据上下文选择最合适的task_type
    → 带fallback机制（LLM失败时用规则最高分）
```

---

## 🔧 实现细节

### 1. `_decide_task_type()` - 主入口

```python
def _decide_task_type(self, query: str, intent_result: Dict[str, Any]) -> str:
    # Step 1: 规则检测，收集所有匹配项
    rule_matches = self._rule_based_detection_with_scores(query, intent_result)

    # Step 2: 冲突检测
    if len(rule_matches) > 1:
        # 多个匹配 → LLM智能分析
        task_type = self._llm_task_type_analysis(query, intent_result, rule_matches)
    elif len(rule_matches) == 1:
        # 唯一匹配 → 直接返回
        task_type = list(rule_matches.keys())[0]
    else:
        # 无匹配 → 默认
        task_type = "standard_calibration"

    # Step 3: 设置必要参数
    self._apply_task_type_parameters(query, intent_result, task_type)

    return task_type
```

### 2. `_rule_based_detection_with_scores()` - 规则检测

返回**所有**匹配的task_type及置信度：

```python
def _rule_based_detection_with_scores(
    self, query: str, intent_result: Dict[str, Any]
) -> Dict[str, float]:
    matches = {}

    # 检测1: 自动迭代率定 (0.95)
    if any(kw in query_lower for kw in ["迭代地", "直到nse", ...]):
        matches["auto_iterative_calibration"] = 0.95

    # 检测2: 重复实验 (0.9)
    if any(kw in query_lower for kw in ["重复", "多次", ...]):
        matches["repeated_experiment"] = 0.9

    # 检测3: 迭代优化 (0.85)
    if any(kw in query_lower for kw in ["边界", "调整范围", ...]):
        matches["iterative_optimization"] = 0.85

    # 检测4: 批量处理 (0.92) - 提高优先级
    if len(basins) > 1 or len(algorithms) > 1 or len(models) > 1:
        matches["batch_processing"] = 0.92

    # 检测5: 扩展分析 (0.8)
    if any(kw in query_lower for kw in ["径流系数", "fdc", ...]):
        matches["extended_analysis"] = 0.8

    # 检测6: 自定义数据 (0.9)
    # 检测7: 信息补全 (0.7)

    return matches  # 可能返回多个匹配项
```

**示例输出**（批量 + 径流系数查询）:
```python
{
    "batch_processing": 0.92,      # 3个流域
    "extended_analysis": 0.8       # "径流系数"关键词
}
```

### 3. `_llm_task_type_analysis()` - LLM智能分析

当检测到多个匹配项时，调用LLM判断：

```python
def _llm_task_type_analysis(
    self, query: str, intent_result: Dict[str, Any], rule_matches: Dict[str, float]
) -> str:
    # 构建清晰的提示词
    system_prompt = """你是水文建模任务类型分析专家。

优先级规则:
1. 如果有**多个流域**且有**后续分析需求** → batch_processing
2. 如果只有**单个流域**且有**分析需求** → extended_analysis
3. 其他情况根据主要意图选择

返回JSON: {"task_type": "...", "reason": "..."}"""

    user_prompt = f"""
用户查询: {query}
流域数量: {len(basins)}
规则检测结果: {rule_matches}

请选择最合适的任务类型。
"""

    try:
        response = self.llm.generate_json(system_prompt, user_prompt, temperature=0.1)
        task_type = response.get("task_type", "standard_calibration")

        # 验证有效性
        if task_type not in valid_task_types:
            task_type = max(rule_matches, key=rule_matches.get)  # Fallback

        return task_type

    except Exception as e:
        # LLM失败 → Fallback到规则最高分
        return max(rule_matches, key=rule_matches.get)
```

**LLM分析示例**（批量 + 径流系数）:
```json
{
  "task_type": "batch_processing",
  "reason": "查询包含3个流域（批量处理）且有后续分析需求（径流系数），应使用batch_processing而非extended_analysis"
}
```

### 4. `_apply_task_type_parameters()` - 参数设置

根据选定的task_type设置必要参数：

```python
def _apply_task_type_parameters(
    self, query: str, intent_result: Dict[str, Any], task_type: str
):
    if task_type == "batch_processing":
        # 提取多流域信息
        basins = self._extract_multiple_basins(query, intent_result)
        intent_result["basin_ids"] = basins

        # 🆕 检测是否有后续分析需求
        needs = self._extract_analysis_needs(query)
        if needs:
            intent_result["needs"] = needs
            logger.info(f"Batch processing with analysis needs: {needs}")

    elif task_type == "extended_analysis":
        needs = self._extract_analysis_needs(query)
        intent_result["needs"] = needs

    # ... 其他task_type的参数设置
```

---

## 📊 效果对比

### 测试用例1: 批量 + 径流系数

**查询**: "批量率定3个流域（12025000, 14301000, 14306500），使用XAJ模型，完成后计算各流域的径流系数"

| 版本 | Task Type | 拆解结果 | 是否正确 |
|------|-----------|----------|---------|
| **v5.0 (纯规则)** | `extended_analysis` | 7个串行任务（只计算第一个流域） | ❌ |
| **v5.1 (混合策略)** | `batch_processing` | 3个并行calibration + 1个aggregated analysis | ✅ |

**执行流程**:
```
规则检测 → {batch_processing: 0.92, extended_analysis: 0.8}
    ↓ (检测到冲突)
LLM分析 → 选择 batch_processing（因为有3个流域）
    ↓
设置参数 → basin_ids=[...], needs=["runoff_coefficient"]
    ↓
TaskPlanner → 使用 _decompose_batch_processing()
    ↓
生成正确的并行 + 聚合结构
```

### 测试用例2: 单流域 + 径流系数

**查询**: "率定流域01539000，使用GR4J模型，完成后计算径流系数"

| 版本 | Task Type | 拆解结果 | 是否正确 |
|------|-----------|----------|---------|
| **v5.0** | `extended_analysis` | calibration + analysis | ✅ |
| **v5.1** | `extended_analysis` | calibration + analysis | ✅ |

**执行流程**:
```
规则检测 → {extended_analysis: 0.8}
    ↓ (唯一匹配)
直接返回 → extended_analysis（无需LLM）
```

### 测试用例3: 迭代优化

**查询**: "率定GR4J模型，流域01539000，如果参数收敛到边界则调整参数范围重新率定"

| 版本 | Task Type | 正确性 |
|------|-----------|--------|
| **v5.0** | `iterative_optimization` | ✅ |
| **v5.1** | `iterative_optimization` | ✅ |

**执行流程**:
```
规则检测 → {iterative_optimization: 0.85, extended_analysis: 0.8}
    ↓ (检测到冲突)
LLM分析 → 选择 iterative_optimization（主要意图是参数调整）
```

---

## ⚡ 性能优化

### 规则检测优先（快速路径）
- **单一匹配**: 直接返回，无需LLM（~0ms overhead）
- **适用场景**: 80%的查询（标准率定、信息补全等）

### LLM仅在冲突时介入（准确性保证）
- **多个匹配**: 调用LLM判断（~2-5s）
- **适用场景**: 20%的复杂查询（批量+分析、迭代+分析等）

### Fallback机制（稳定性）
- LLM调用失败 → 返回规则最高分
- LLM返回无效值 → 返回规则最高分
- 保证系统永远有合理输出

---

## 🔄 与TaskPlanner的集成

### 完整流程

```
User Query
    ↓
IntentAgent (v5.1 混合策略)
    ↓
intent_result = {
    "task_type": "batch_processing",
    "basin_ids": ["12025000", "14301000", "14306500"],
    "model_name": "xaj",
    "algorithm": "SCE_UA",
    "needs": ["runoff_coefficient"]  # 🆕 分析需求
}
    ↓
TaskPlanner
    ↓
_decompose_batch_processing(intent_result)
    ↓
Subtasks:
  - task_1: Calibrate basin 12025000 (no dependencies)
  - task_2: Calibrate basin 14301000 (no dependencies)
  - task_3: Calibrate basin 14306500 (no dependencies)
  - task_4_analysis: Aggregated runoff_coefficient (depends on task_1,2,3)
    ↓
Orchestrator → 执行3个并行率定 → 执行聚合分析
```

---

## 📝 关键改进点

### 1. 规则检测返回**所有匹配**而非第一个
**Before**:
```python
if "径流系数" in query:
    return "extended_analysis"  # 立即返回，忽略后续规则
```

**After**:
```python
matches = {}
if "径流系数" in query:
    matches["extended_analysis"] = 0.8
if len(basins) > 1:
    matches["batch_processing"] = 0.92  # 也会被检测到
return matches  # 返回所有匹配项
```

### 2. LLM提示词包含优先级规则
```
如果有**多个流域**且有**后续分析需求** → batch_processing
如果只有**单个流域**且有**分析需求** → extended_analysis
```

### 3. batch_processing支持needs参数
`_apply_task_type_parameters()`中：
```python
if task_type == "batch_processing":
    needs = self._extract_analysis_needs(query)  # 🆕
    if needs:
        intent_result["needs"] = needs
```

### 4. TaskPlanner的batch方法支持聚合分析
`_decompose_batch_processing()`中：
```python
# Step 1: 创建并行calibration任务
for basin in basins:
    subtasks.append(SubTask(calibration, no dependencies))

# Step 2: 创建聚合分析任务（如果有needs）
if needs:
    subtasks.append(SubTask(
        task_type="custom_analysis",
        basin_ids=basins,  # 所有流域
        dependencies=all_calibration_task_ids  # 依赖所有率定任务
    ))
```

---

## 🎯 优势总结

| 方面 | 纯规则 (v5.0) | 混合策略 (v5.1) |
|------|--------------|----------------|
| **速度** | 快 (~0ms) | 快（单一匹配）/ 稍慢（冲突场景） |
| **准确性** | 受优先级限制 | 高（LLM智能判断） |
| **鲁棒性** | 易受关键词冲突影响 | Fallback机制保证稳定 |
| **可扩展性** | 需手动调整优先级 | 自动适应复杂场景 |
| **成本** | 0 | 仅冲突场景调用LLM |

---

## 📚 相关文件

- `hydroagent/agents/intent_agent.py` - IntentAgent实现（混合策略）
- `hydroagent/agents/task_planner.py` - TaskPlanner实现（batch拆解）
- `test/test_intent_hybrid_strategy.py` - 混合策略单元测试
- `test/test_batch_with_analysis.py` - TaskPlanner batch拆解测试

---

## 🔮 未来优化方向

1. **规则置信度动态调整**: 根据历史数据微调各规则的置信度
2. **LLM缓存**: 相似查询复用LLM结果
3. **规则学习**: 从LLM决策中学习新的规则模式
4. **A/B测试**: 对比纯规则vs混合策略的准确率

---

**Last Updated**: 2025-12-22
**Version**: v5.1
**Status**: ✅ Production Ready
