# Token 统计功能使用指南

> **版本**: v2.0
> **更新日期**: 2025-12-05
> **作者**: Claude

## 📊 概述

HydroAgent v2.0 引入了完整的 Token 使用统计功能，可以跟踪所有 LLM API 调用的 token 消耗，帮助：

- ✅ **成本估算**: 实时追踪 API token 消耗
- ✅ **性能分析**: 对比不同实验的 token 使用效率
- ✅ **实验评估**: 将 token 消耗作为重要的评估指标

---

## 🚀 快速开始

### 1. 基本使用

```python
from hydroagent.core.llm_interface import create_llm_interface

# 创建 LLM 接口（自动启用 token 追踪）
llm = create_llm_interface(
    backend="openai",
    model_name="qwen-turbo"
)

# 使用 LLM
response = llm.generate(
    system_prompt="You are a helpful assistant.",
    user_prompt="What is machine learning?"
)

# 获取 token 统计
stats = llm.get_token_usage()
print(f"Total tokens: {stats['total_tokens']}")
print(f"Total calls: {stats['total_calls']}")
```

### 2. 在实验中自动统计

实验框架（`BaseExperiment`）会**自动**统计和导出 token 使用情况：

```python
from experiment.base_experiment import create_experiment

# 创建实验
exp = create_experiment(
    exp_name="exp_1_standard",
    exp_description="标准率定测试"
)

# 运行实验（自动统计 token）
results = exp.run_batch(
    queries=["率定GR4J模型流域01013500"],
    backend="api",
    use_mock=False
)

# Token 统计会自动：
# 1. 显示在终端
# 2. 保存到 JSON 文件
# 3. 包含在实验报告中
```

---

## 📈 输出格式

### 1. 终端输出

```
📈 Token 使用统计:
   主模型 (qwen-turbo):
      总调用次数: 15
      总 tokens: 12,345
         - Prompt: 8,000
         - Completion: 4,345
      平均每次调用: 823.0 tokens

   代码模型 (qwen-coder-turbo):
      总调用次数: 3
      总 tokens: 2,100
         - Prompt: 1,200
         - Completion: 900
      平均每次调用: 700.0 tokens
```

### 2. JSON 文件

```json
{
  "total_calls": 15,
  "total_prompt_tokens": 8000,
  "total_completion_tokens": 4345,
  "total_tokens": 12345,
  "average_tokens_per_call": 823.0,
  "model_name": "qwen-turbo",
  "backend": "OpenAIInterface"
}
```

**文件位置**: `experiment_results/<exp_name>/<timestamp>/data/<exp_name>_main_llm_token_usage.json`

### 3. CSV 摘要

实验结果 CSV 会包含每个任务的 token 统计：

| query | success | elapsed_time | total_tokens | prompt_tokens | completion_tokens | api_calls |
|-------|---------|--------------|--------------|---------------|-------------------|-----------|
| 率定GR4J... | True | 45.2 | 8234 | 5120 | 3114 | 12 |

### 4. 实验报告

Markdown 报告会自动包含 Token 统计章节：

```markdown
### Token 使用统计

- **总 Token 数**: 12,345
- **平均每任务**: 823 tokens
- **Prompt Tokens**: 8,000
- **Completion Tokens**: 4,345
- **平均API调用数**: 12.3 次/任务
```

---

## 🔧 高级功能

### 1. 导出 Token 统计到文件

```python
from hydroagent.utils.token_stats import export_token_stats

# 导出统计
export_token_stats(
    llm_interface=llm,
    output_dir="results/my_experiment",
    experiment_name="exp_1"
)
# 生成: exp_1_token_usage.json
```

### 2. 格式化报告

```python
from hydroagent.utils.token_stats import format_token_stats_report

stats = llm.get_token_usage()
report = format_token_stats_report(stats)
print(report)
```

输出：
```
======================================================================
📊 Token Usage Statistics
======================================================================

Model: qwen-turbo
Backend: OpenAIInterface

Total API Calls: 15
Total Tokens: 12,345
  - Prompt Tokens: 8,000
  - Completion Tokens: 4,345
Average Tokens per Call: 823.0

======================================================================
```

### 3. 聚合多个实验的统计

```python
from hydroagent.utils.token_stats import aggregate_token_stats_from_files

# 聚合目录中所有 token 统计文件
aggregated = aggregate_token_stats_from_files(
    results_dir="experiment_results/exp_1/20251205_100000/data",
    pattern="*_token_usage.json"
)

print(f"总实验数: {aggregated['experiments']}")
print(f"总 tokens: {aggregated['total_tokens']}")
print(f"平均每实验: {aggregated['average_tokens_per_experiment']}")
```

### 4. 重置统计

```python
# 重置 token 统计（在新实验开始前）
llm.reset_token_usage()
```

---

## 📊 实验指标对比

Token 统计已经集成到 `calculate_metrics()` 中，可以和其他指标一起对比：

```python
metrics = exp.calculate_metrics(results)

print(f"时间效率:")
print(f"  平均耗时: {metrics['average_time']}s")

print(f"Token 效率:")
print(f"  总 tokens: {metrics['total_tokens_sum']}")
print(f"  平均每任务: {metrics['average_tokens_per_task']} tokens")
```

**指标包含**:
- `total_tokens_sum`: 所有任务的总 token 数
- `average_tokens_per_task`: 平均每任务 token 数
- `total_prompt_tokens_sum`: 总 prompt tokens
- `total_completion_tokens_sum`: 总 completion tokens
- `average_api_calls_per_task`: 平均每任务 API 调用次数

---

## 💡 最佳实践

### 1. 实验前重置统计

```python
llm = create_llm_interface("openai", "qwen-turbo")
llm.reset_token_usage()  # 确保统计从零开始
```

### 2. 对比不同模型的 token 效率

```python
# 实验 1: qwen-turbo
llm1 = create_llm_interface("openai", "qwen-turbo")
result1 = exp.run_experiment(query, llm1)
stats1 = llm1.get_token_usage()

# 实验 2: qwen3-max
llm2 = create_llm_interface("openai", "qwen3-max")
result2 = exp.run_experiment(query, llm2)
stats2 = llm2.get_token_usage()

print(f"qwen-turbo: {stats1['total_tokens']} tokens")
print(f"qwen3-max: {stats2['total_tokens']} tokens")
```

### 3. 监控成本

```python
# 估算 API 成本（以 qwen-turbo 为例）
PRICE_PER_1K_TOKENS = 0.001  # 假设价格

stats = llm.get_token_usage()
estimated_cost = (stats['total_tokens'] / 1000) * PRICE_PER_1K_TOKENS
print(f"预估成本: ${estimated_cost:.4f}")
```

### 4. 实验后保存统计

```python
# 在 run_batch 结束后自动保存
# 位置: experiment_results/<exp_name>/<timestamp>/data/

# 手动保存（如果需要）
export_token_stats(llm, workspace, "custom_name")
```

---

## 🔍 故障排查

### Q: Token 统计为 0

**原因**: Ollama 本地模型可能不返回精确的 token 计数

**解决**:
- Ollama 会使用估算值（文本长度 / 4）
- 使用 API 模式获取精确统计

### Q: 统计文件没有生成

**检查**:
1. `workspace` 目录是否正确创建
2. 是否调用了 `run_batch()` 方法
3. 检查日志文件中的错误信息

### Q: CSV 中 token 列为空

**原因**: 实验失败或未执行

**解决**: 检查 `results` 中的 `success` 字段

---

## 📝 API 参考

### LLMInterface

```python
# 获取 token 统计
stats = llm.get_token_usage()

# 重置统计
llm.reset_token_usage()

# 获取模型信息（包含 token 统计）
info = llm.get_model_info()
```

### TokenUsageTracker

```python
from hydroagent.core import TokenUsageTracker

tracker = TokenUsageTracker()
tracker.record_usage(prompt_tokens=100, completion_tokens=50, model="qwen-turbo")
summary = tracker.get_summary()
tracker.reset()
```

---

## 🎯 示例脚本

查看完整示例：
- `examples/example_token_tracking.py` - 基本使用示例
- `experiment/exp_*.py` - 实验中的 token 统计

---

## 📚 相关文档

- [LLM Interface 文档](../hydroagent/core/llm_interface.py)
- [BaseExperiment 文档](../experiment/base_experiment.py)
- [实验指南](experiments.md)

---

**更新历史**:
- 2025-12-05: v2.0 初始版本，完整 token 统计功能
