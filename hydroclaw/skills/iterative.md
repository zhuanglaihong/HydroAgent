## 迭代优化工作流

当用户要求迭代优化、参数调整、边界检查时使用此工作流。

### 执行步骤

1. 先执行标准率定（calibrate_model）
2. 检查 NSE 是否达到目标（默认 0.65）
3. 如果参数触碰边界（距 min/max < 5%），扩展参数范围后重新率定
4. 如果 NSE 仍低但无边界问题，换随机种子再试
5. 最多迭代 5 次
6. 报告所有迭代的 NSE 变化轨迹

### 边界检测

如果某个参数值距离其允许范围的上界或下界不到 5%，说明参数可能受到了边界限制，
需要扩展参数范围后重新率定。

### 参数范围调整方法

当检测到参数触碰边界需要扩展范围时，有两种方式：

**方式 1：使用 `param_range_file` 参数**（推荐）

先用 `generate_code` 工具创建自定义参数范围 YAML 文件，然后传给 `calibrate_model`：

```python
# 1. 生成自定义参数范围文件
generate_code(
    task_description="创建扩展参数范围文件",
    code_content="""
import yaml
param_ranges = {
    'gr4j': {
        'x1': [0.5, 3000.0],   # 扩展上界
        'x2': [-15.0, 15.0],   # 扩展两端
        'x3': [0.5, 800.0],    # 扩展上界
        'x4': [0.3, 15.0],     # 扩展上界
    }
}
with open('custom_param_ranges.yaml', 'w') as f:
    yaml.dump(param_ranges, f)
"""
)

# 2. 用扩展范围重新率定
calibrate_model(
    basin_ids=["01013500"],
    model_name="gr4j",
    param_range_file="custom_param_ranges.yaml"
)
```

**方式 2：通过 `algorithm_params` 换随机种子**

```python
calibrate_model(
    basin_ids=["01013500"],
    model_name="gr4j",
    algorithm_params={"random_seed": 5678}  # 换种子重试
)
```

### 报告

- 列出每次迭代的 NSE 值
- 说明是否检测到边界效应
- 说明参数范围调整详情（如果有）
- 给出最终最优参数和性能指标
