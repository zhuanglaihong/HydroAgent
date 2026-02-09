## 批量处理工作流

当用户要求处理多个流域、重复实验时使用此工作流。

### 多流域批量率定

1. 对每个流域分别执行率定和评估
2. 汇总所有流域的结果
3. 生成批量分析报告

### 重复实验（稳定性分析）

当用户要求"重复率定N次"时：

1. 使用不同随机种子重复率定 N 次
2. 计算统计指标：NSE 的均值、标准差、最大值、最小值
3. 评估结果的稳定性
4. 生成稳定性分析报告

**随机种子控制方式**：通过 `algorithm_params` 中的 `random_seed` 参数控制

```python
# 第 1 次率定（默认种子 1234）
calibrate_model(basin_ids=["01013500"], model_name="gr4j")

# 第 2 次率定（换种子）
calibrate_model(
    basin_ids=["01013500"],
    model_name="gr4j",
    algorithm_params={"random_seed": 2345}
)

# 第 3 次率定（再换种子）
calibrate_model(
    basin_ids=["01013500"],
    model_name="gr4j",
    algorithm_params={"random_seed": 3456}
)
```

每次率定务必使用不同的 `output_dir`，避免结果覆盖：

```python
calibrate_model(
    basin_ids=["01013500"],
    model_name="gr4j",
    algorithm_params={"random_seed": 2345},
    output_dir="results/gr4j_SCE_UA_01013500_run2"
)
```

### 结果汇总

- 逐流域/逐次的 NSE、RMSE 表格
- 统计量（均值、标准差、变异系数）
- 最优和最差结果分析
