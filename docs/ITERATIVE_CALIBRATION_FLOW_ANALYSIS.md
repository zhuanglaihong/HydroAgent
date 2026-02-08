# Iterative Calibration执行流程分析

**用户查询**: "率定GR4J模型流域14325000，迭代优化直到NSE≥0.65，最多3次"

**问题**: Iteration 2使用的param_range与Iteration 1完全相同，导致NSE无法改善

---

## 1. IntentAgent - 意图识别

**日志行55-71**

```
[IntentAgent] Processing query: 率定GR4J模型流域14325000，迭代优化直到NSE≥0.65，最多3次
LLM selected task_type: auto_iterative_calibration
Extracted NSE threshold: 0.65
Extracted max iterations: 3
```

**输出**:
```python
{
    "intent": "calibration",
    "task_type": "auto_iterative_calibration",  # ✅ 正确识别
    "max_iterations": 3,                        # ✅ 正确提取
    "nse_threshold": 0.65,                      # ✅ 正确提取
    "model_name": "gr4j",
    "basin_ids": ["14325000"],
    ...
}
```

**结论**: ✅ IntentAgent工作正常

---

## 2. TaskPlanner - 任务规划

**日志行78-92**

```
[TaskPlanner] Decomposing task: auto_iterative_calibration
[ToolOrchestrator] Set execution_mode=iterative
mode_params: {
    'max_iterations': 3,
    'nse_threshold': 0.65,
    'boundary_threshold': 0.05,
    'min_nse_improvement': 0.01
}
```

**生成的tool_chain**:
```python
[
    {"tool": "validate_data", ...},
    {"tool": "calibrate", ...},
    {"tool": "evaluate", ...}
]
```

**执行模式**: `iterative`

**结论**: ✅ TaskPlanner工作正常，正确设置了iterative模式和参数

---

## 3. InterpreterAgent - 配置生成

**日志行100-114**

```
[InterpreterAgent] Processing subtask: auto_iterative_calibration
Config generated successfully
```

**生成的config结构** (从日志行142-146推断):
```python
{
    "data_cfgs": {...},
    "model_cfgs": {
        "model_name": "gr4j",
        "model_params": {}
        # ❌ 缺少param_range字段！
    },
    "training_cfgs": {
        "param_range_file": null,  # ❌ 没有指定param_range文件
        ...
    }
}
```

**问题1**: ❌ **InterpreterAgent生成的初始config中没有param_range字段**

这意味着hydromodel在Iteration 1会使用其内部默认的param_range:
```python
# hydromodel的GR4J默认参数范围
{
    "x1": [100.0, 1200.0],
    "x2": [-5.0, 3.0],
    "x3": [20.0, 300.0],   # 注意这个下限是20.0
    "x4": [1.1, 2.9]       # 注意这个上限是2.9
}
```

---

## 4. RunnerAgent - Iteration 1

**日志行127-169**

### 4.1 执行calibrate

```
Iteration 1 output dir: .../iteration_1
Set calibration output_dir: .../iteration_1

[CalibrationTool] DEBUG: 完整的model_cfgs结构:
{
  "model_name": "gr4j",
  "model_params": {}
  # ❌ 没有param_range!
}

Calling calibrate(config)
Calibration completed
```

**hydromodel的行为**:
1. 检测config中没有`model_cfgs.param_range`
2. 检测`training_cfgs.param_range_file = null`
3. **使用hydromodel内部默认的param_range**
4. 将默认param_range保存到`iteration_1/param_range.yaml`
5. 用默认范围进行率定

**结果**:
- NSE = -1.3955 (未达标)
- 归一化参数: `x1=0.0877, x2=0.8659, x3=0.0412, x4=0.9582`
- 反归一化参数: `x1=196.46, x2=1.927, x3=31.549, x4=2.8247`

### 4.2 调用param_range_adjuster

**日志行170-213**

```
[ParamRangeAdjuster] 上一次参数范围:
    {'x1': [100.0, 1200.0], 'x2': [-5.0, 3.0], 'x3': [20.0, 300.0], 'x4': [1.1, 2.9]}

参数 x3: 接近下边界 → 向下扩展 → 新范围: [0.0, 300.0]  ✅
参数 x4: 接近上边界 → 向上扩展 → 新范围: [1.1, 3.8]    ✅

[RunnerAgent] 调整后的参数范围:
    {'x1': [100.0, 1200.0], 'x2': [-5.0, 3.0], 'x3': [0.0, 300.0], 'x4': [1.1, 3.8]}
✓ 已保存调整后的param_range到_prev_adjusted_param_range
```

**结论**: ✅ param_range_adjuster工作正常，成功生成调整后的范围

---

## 5. RunnerAgent - Iteration 2

**日志行214-249**

### 5.1 注入调整后的param_range

```
=== Iteration 2/3 ===
Set calibration output_dir: .../iteration_2

注入调整后的param_range到config:
    {'x1': [100.0, 1200.0], 'x2': [-5.0, 3.0], 'x3': [0.0, 300.0], 'x4': [1.1, 3.8]}

DEBUG: config['model_cfgs']['param_range'] =
    {'x1': [100.0, 1200.0], 'x2': [-5.0, 3.0], 'x3': [0.0, 300.0], 'x4': [1.1, 3.8]}
```

✅ RunnerAgent成功注入调整后的param_range

### 5.2 ToolExecutor传递param_range

```
[ToolExecutor] calibrate工具的param_range:
    {'x1': [100.0, 1200.0], 'x2': [-5.0, 3.0], 'x3': [0.0, 300.0], 'x4': [1.1, 3.8]}
```

✅ ToolExecutor正确传递param_range给CalibrationTool

### 5.3 CalibrationTool接收param_range

```
[CalibrationTool] DEBUG: 完整的model_cfgs结构:
{
  "model_name": "gr4j",
  "model_params": {},
  "param_range": {
    "x1": [100.0, 1200.0],
    "x2": [-5.0, 3.0],
    "x3": [0.0, 300.0],   ✅ 正确！
    "x4": [1.1, 3.8]      ✅ 正确！
  }
}

Calling calibrate(config)
```

✅ CalibrationTool收到了正确的param_range

---

## 6. **关键问题：hydromodel的param_range读取逻辑**

**实际观察到的结果**:

查看`iteration_2/param_range.yaml`:
```yaml
gr4j:
  param_range:
    x1: [100.0, 1200.0]
    x2: [-5.0, 3.0]
    x3: [20.0, 300.0]    # ❌ 旧值！应该是[0.0, 300.0]
    x4: [1.1, 2.9]       # ❌ 旧值！应该是[1.1, 3.8]
```

查看`iteration_2/basins_denorm_params.csv`:
```
x1=196.46, x2=1.927, x3=31.549, x4=2.8247
```
完全与iteration_1相同！

**验证计算**:
- 如果使用新范围`x3=[0.0, 300.0]`，要得到`denorm=31.549`，需要`norm=31.549/300=0.1052`
- 但实际`norm=0.0412`（与iteration 1相同）
- 反推：`0.0412 * (300-20) + 20 = 31.549` ✅ 这证明hydromodel使用了旧范围`[20.0, 300.0]`！

---

## 7. **Root Cause分析**

### 问题定位

**hydromodel.calibrate()的param_range读取优先级**（推测）:

```python
def calibrate(config):
    # 优先级1: 读取已存在的param_range.yaml文件（如果存在）
    output_dir = config['training_cfgs']['output_dir']
    param_range_file = Path(output_dir) / "param_range.yaml"

    if param_range_file.exists():
        # ❌ 问题在这里！优先读取已存在的文件
        param_range = read_yaml(param_range_file)
        return param_range

    # 优先级2: 读取config中的param_range_file路径
    if config['training_cfgs']['param_range_file']:
        param_range = read_yaml(config['training_cfgs']['param_range_file'])
        return param_range

    # 优先级3: 读取config['model_cfgs']['param_range']
    if 'param_range' in config['model_cfgs']:
        param_range = config['model_cfgs']['param_range']
        return param_range

    # 优先级4: 使用hydromodel内部默认值
    param_range = get_default_param_range(model_name)
    return param_range
```

**当前发生的情况**:

1. **Iteration 1**:
   - `iteration_1`目录刚创建，没有param_range.yaml
   - config中也没有param_range
   - hydromodel使用默认值，并保存到`iteration_1/param_range.yaml`

2. **Iteration 2**:
   - 我们设置`output_dir = iteration_2`（新目录）
   - `iteration_2`目录刚创建，**没有**param_range.yaml
   - 我们注入了`config['model_cfgs']['param_range']`（新值）
   - ❌ **但hydromodel为什么还是用了旧值？**

### 可能的原因

**假设1**: hydromodel在创建output_dir之前，先从**某个全局位置**读取param_range.yaml

**假设2**: hydromodel有缓存机制，缓存了第一次的param_range

**假设3**: hydromodel的实现有bug，忽略了`config['model_cfgs']['param_range']`

**假设4**: 我们注入param_range的**时机有问题**
- ToolExecutor._resolve_references()会创建config的deep copy
- 可能我们注入的param_range在deep copy时丢失了

---

## 8. **实验验证**

为了确定root cause，需要验证：

### 实验1: 检查_resolve_references是否保留param_range

添加debug日志，在_resolve_references前后对比config:

```python
# runner_agent.py, before execute_chain
logger.info(f"Before execute_chain: param_range = {config['model_cfgs'].get('param_range')}")

# tool_executor.py, in execute_chain after _resolve_references
logger.info(f"After _resolve_references: param_range = {resolved_inputs['config']['model_cfgs'].get('param_range')}")
```

### 实验2: 检查hydromodel的param_range读取优先级

在CalibrationTool中，调用calibrate前：

```python
# 1. 确保output_dir是新目录
assert not Path(output_dir).exists() or not (Path(output_dir) / "param_range.yaml").exists()

# 2. 打印完整config
logger.info(f"Complete config: {json.dumps(config, indent=2)}")

# 3. 调用calibrate
result = calibrate(config)

# 4. 检查生成的param_range.yaml
with open(Path(output_dir) / "param_range.yaml") as f:
    saved_range = yaml.safe_load(f)
    logger.info(f"Saved param_range: {saved_range}")
```

### 实验3: 直接传递param_range_file

不使用`config['model_cfgs']['param_range']`，而是：

```python
# 在iteration 2开始前
# 1. 保存adjusted_param_range到临时文件
temp_file = iteration_dir / "adjusted_param_range.yaml"
save_yaml(adjusted_param_range, temp_file)

# 2. 设置param_range_file
config['training_cfgs']['param_range_file'] = str(temp_file)

# 3. 不设置model_cfgs.param_range
# del config['model_cfgs']['param_range']
```

---

## 9. **可能的解决方案**

### 方案1: 使用param_range_file而非param_range字段

```python
# runner_agent.py, iteration 2+
if iteration > 1 and self._prev_adjusted_param_range:
    # 保存到YAML文件
    param_range_file = iteration_dir / "param_range_input.yaml"
    save_yaml_with_model_name(self._prev_adjusted_param_range, param_range_file, model_name)

    # 设置param_range_file路径
    config['training_cfgs']['param_range_file'] = str(param_range_file)

    # 不设置model_cfgs.param_range
```

### 方案2: 在调用calibrate前删除output_dir中的旧param_range.yaml

```python
# runner_agent.py, before execute_chain
if iteration > 1:
    # 删除可能存在的旧param_range.yaml
    old_file = iteration_dir / "param_range.yaml"
    if old_file.exists():
        old_file.unlink()
```

### 方案3: 修改hydromodel库（不推荐）

直接修改hydromodel的param_range读取逻辑，优先使用config['model_cfgs']['param_range']

---

## 10. **总结**

### 当前系统流程

```
IntentAgent (✅)
  → TaskPlanner (✅)
  → InterpreterAgent (⚠️ 未包含param_range)
  → RunnerAgent:
      - Iteration 1: calibrate (✅ 使用默认范围)
      - param_range_adjuster (✅ 生成调整后范围)
      - Iteration 2:
          - RunnerAgent注入param_range到config (✅)
          - ToolExecutor传递param_range (✅)
          - CalibrationTool接收param_range (✅)
          - hydromodel.calibrate() (❌ **使用了旧范围！**)
```

### Root Cause

**hydromodel.calibrate()没有正确使用config['model_cfgs']['param_range']**

可能原因:
1. hydromodel优先读取已存在的param_range.yaml文件（但iteration_2是新目录，不应该有旧文件）
2. hydromodel有缓存机制
3. hydromodel忽略了model_cfgs中的param_range字段
4. _resolve_references丢失了param_range（已验证不是这个原因）

### 下一步

1. 运行**实验2**，确认hydromodel的param_range读取逻辑
2. 尝试**方案1**，使用param_range_file而非param_range字段
3. 如果方案1无效，尝试**方案2**，删除旧文件
