# 迭代率定参数范围调整修复（最终版）

**Author**: Claude
**Date**: 2025-12-30
**Status**: ✅ 已修复

---

## 📋 问题总结

Query 7的迭代率定功能虽然创建了独立的iteration目录，调用了param_range_adjuster，但**参数范围调整未生效**：

```
Iteration 1: NSE=-1.3955, 参数: x1=0.0877, x2=0.866, x3=0.0412, x4=0.958
调整后范围: x3=[0.0, 300.0] (原20.0), x4=[1.1, 3.8] (原2.9)

Iteration 2: NSE=-1.3955, 参数: x1=0.0877, x2=0.866, x3=0.0412, x4=0.958  ❌ 完全相同！
```

---

## 🔍 根本原因分析

### 问题链条

#### 1. ToolExecutor的_resolve_references创建新字典

`hydroagent/tools/executor.py:289-290`:

```python
elif isinstance(value, dict):
    return {k: resolve_value(v) for k, v in value.items()}  # 递归创建新字典
```

**影响**: 即使config没有${}引用，也会创建新的inputs对象

#### 2. 数据流丢失修改

```
Iteration 1结束:
  → adjust_param_range()
  → 更新 tool_chain中的config["model_cfgs"]["param_range"]
  → ✅ tool_chain引用被修改

Iteration 2开始:
  → execute_chain(tool_chain)
  → for step in tool_chain:
       inputs = step.get("inputs", {})  # 获取引用
       inputs = _resolve_references(inputs, context)  # ❌ 创建新字典！
       tool.execute(inputs)  # 使用新字典，不包含之前的修改
```

#### 3. hydromodel覆盖YAML文件

即使我们在执行前保存了param_range.yaml，`hydromodel.calibrate(config)`也会：

1. 读取`config["model_cfgs"]["param_range"]`
2. 用这个值重新生成param_range.yaml
3. **覆盖**我们保存的文件

---

## 🔧 解决方案

### 核心思路

**在每次迭代开始时，重新注入调整后的param_range到config，确保_resolve_references复制到的是新值**。

### 实现步骤

#### Step 1: 保存调整后的范围到实例变量

`runner_agent.py:2207-2215`:

```python
if adjustment_result.get("success"):
    new_param_range = adjustment_result.get("new_param_range", {})
    logger.info(f"[RunnerAgent] ✓ 参数范围调整成功")
    logger.info(f"[RunnerAgent] 调整后的参数范围: {new_param_range}")

    # 保存到实例变量，下次迭代开始时会读取
    self._prev_adjusted_param_range = new_param_range
    logger.info(f"[RunnerAgent] ✓ 已保存调整后的param_range到_prev_adjusted_param_range")
```

#### Step 2: 迭代开始时重新注入

`runner_agent.py:2107-2135`:

```python
# Iteration 2+需要使用上一次调整后的param_range
# 问题: execute_chain会调用_resolve_references创建新的inputs字典，丢失之前的修改
# 解决: 在每次迭代开始时重新注入调整后的param_range到config
if iteration_dir and iteration > 1:
    # 从prev_adjusted_param_range获取调整后的范围
    if hasattr(self, '_prev_adjusted_param_range') and self._prev_adjusted_param_range:
        logger.info(f"[RunnerAgent] 注入调整后的param_range到config: {self._prev_adjusted_param_range}")
        if "model_cfgs" not in config:
            config["model_cfgs"] = {}
        config["model_cfgs"]["param_range"] = self._prev_adjusted_param_range

        # 保存到YAML文件（虽然可能被hydromodel覆盖，但作为备份）
        import yaml
        model_name = config.get("model_cfgs", {}).get("model_name", "gr4j")
        param_range_file = iteration_dir / "param_range.yaml"

        param_range_data = {
            model_name: {
                "param_name": list(self._prev_adjusted_param_range.keys()),
                "param_range": self._prev_adjusted_param_range
            }
        }

        with open(param_range_file, "w") as f:
            yaml.dump(param_range_data, f, default_flow_style=False)

        logger.info(f"[RunnerAgent] ✓ 已保存param_range到: {param_range_file}")
```

#### Step 3: 初始化变量

`runner_agent.py:2067-2068`:

```python
# Track adjusted param_range for next iteration
self._prev_adjusted_param_range = None
```

---

## 📊 修复后的数据流

```
Iteration 1:
  → 执行calibrate, evaluate
  → NSE=-1.3955 (未达标)
  → 调用param_range_adjuster
  → 调整后: x3=[0.0, 300.0], x4=[1.1, 3.8]
  → 保存到 self._prev_adjusted_param_range ✅

Iteration 2:
  → 检测到 self._prev_adjusted_param_range 存在
  → 注入到 config["model_cfgs"]["param_range"]  ✅
  → execute_chain()
      → _resolve_references(inputs)
          → 递归复制config
          → 新inputs包含调整后的param_range ✅
      → calibrate_tool.execute(新inputs)
          → hydromodel.calibrate(config with 新param_range)
          → 使用 x3=[0.0, 300.0], x4=[1.1, 3.8] ✅
  → 归一化参数应该不同了！
```

---

## ✅ 预期效果

运行Query 7后：

### 目录结构

```
workspace/
├── iteration_1/
│   ├── param_range.yaml          (原始范围)
│   ├── basins_denorm_params.csv  (x3=31.5, x4=2.82)
│   ├── calibration_results.json
│   └── ...
├── iteration_2/
│   ├── param_range.yaml          (调整后范围: x3=[0,300], x4=[1.1,3.8])
│   ├── basins_denorm_params.csv  (参数应该不同)
│   ├── calibration_results.json
│   └── ...
└── iteration_3/ (如果需要)
```

### 日志关键信息

```
[RunnerAgent] === Iteration 1/3 ===
[RunnerAgent] Iteration 1: NSE=-1.3955
[ParamRangeAdjuster] 调整后: x3=[0.0, 300.0], x4=[1.1, 3.8]
[RunnerAgent] ✓ 已保存调整后的param_range到_prev_adjusted_param_range

[RunnerAgent] === Iteration 2/3 ===
[RunnerAgent] 注入调整后的param_range到config: {'x1': [100.0, 1200.0], ...}
[RunnerAgent] ✓ 已保存param_range到: iteration_2/param_range.yaml
[ResultParser] 提取参数: {'x1': 0.XXX, 'x2': 0.XXX, 'x3': 0.XXX, 'x4': 0.XXX}  ← 应该不同
[RunnerAgent] Iteration 2: NSE=X.XXXX  ← 应该有改善或不同
```

---

## 🧪 验证方法

### 1. 检查param_range.yaml文件

```bash
# Iteration 1
cat iteration_1/param_range.yaml
# x3: [20.0, 300.0]
# x4: [1.1, 2.9]

# Iteration 2
cat iteration_2/param_range.yaml
# x3: [0.0, 300.0]  ✅ 已调整
# x4: [1.1, 3.8]    ✅ 已调整
```

### 2. 检查归一化参数

```bash
# Iteration 1
cat iteration_1/basins_norm_params.csv
# x1,x2,x3,x4
# 0.087690875,0.8659038,0.04124756,0.9581741

# Iteration 2
cat iteration_2/basins_norm_params.csv
# x1,x2,x3,x4
# ?,?,?,?  ← 应该不同（特别是x3和x4）
```

### 3. 检查NSE变化

```
Iteration 1: NSE=-1.3955
Iteration 2: NSE=?  (可能改善/恶化/不变，但归一化参数应该不同)
Iteration 3: NSE=?  (继续调整)
```

---

## 📝 关键代码位置

| 文件 | 行号 | 功能 |
|------|------|------|
| `runner_agent.py` | 2068 | 初始化 `_prev_adjusted_param_range` |
| `runner_agent.py` | 2107-2135 | Iteration N开始时注入调整后的范围 |
| `runner_agent.py` | 2207-2215 | Iteration N结束时保存调整后的范围 |
| `executor.py` | 289-290 | `_resolve_references` 创建新字典 |
| `param_range_adjuster.py` | 20-65 | 参数范围调整算法 |

---

## 🚀 后续测试

```bash
# 清除旧结果
rm -rf experiment_results/test_query_7

# 运行测试
python test/test_exp_b_queries.py --backend api --mock

# 检查结果
ls -la experiment_results/test_query_7/*/session_*/iteration_*
cat experiment_results/test_query_7/*/session_*/iteration_2/param_range.yaml
```

**期望结果**:
- ✅ 创建3个iteration目录（或根据停止条件决定）
- ✅ iteration_2/param_range.yaml包含调整后的范围
- ✅ iteration_2的归一化参数与iteration_1不同
- ✅ NSE逐步改善（或至少参数在搜索空间中移动）

---

**修复完成时间**: 2025-12-30
**验证状态**: ⏳ 待测试
