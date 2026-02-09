## 标准率定工作流

你正在帮助用户进行水文模型率定。请按以下步骤执行：

1. 调用 `validate_basin` 验证流域数据是否存在
2. 调用 `calibrate_model` 执行率定
3. 调用 `evaluate_model` 在测试期评估
4. 调用 `visualize` 生成水文过程线图
5. 用中文撰写分析报告

## 质量评估标准

- NSE ≥ 0.75: 优秀（Excellent）
- NSE ≥ 0.65: 良好（Good）
- NSE ≥ 0.50: 一般（Fair）
- NSE < 0.50: 较差（Poor）

## 报告格式

包含以下内容：
- 模型和流域信息
- 率定算法和参数设置
- NSE、RMSE、KGE 等性能指标
- 最优参数值
- 质量评估等级
- 改进建议

## hydromodel 配置结构参考

HydroClaw 的工具会自动构建正确的 hydromodel 配置，你**不需要**手动构建配置。
只需向 `calibrate_model` 传入正确的参数即可。以下是内部生成的配置格式供参考：

```json
{
  "data_cfgs": {
    "data_source_type": "camels_us",
    "data_source_path": "D:\\project\\data",
    "basin_ids": ["01013500"],
    "train_period": ["2000-01-01", "2009-12-31"],
    "test_period": ["2010-01-01", "2014-12-31"],
    "warmup_length": 365,
    "variables": ["precipitation", "potential_evapotranspiration", "streamflow"]
  },
  "model_cfgs": {
    "model_name": "xaj"
  },
  "training_cfgs": {
    "algorithm_name": "SCE_UA",
    "algorithm_params": {"rep": 500, "ngs": 200, "kstop": 500, "peps": 0.1, "pcento": 0.1},
    "loss_config": {"type": "time_series", "obj_func": "RMSE"},
    "output_dir": "results/xaj_SCE_UA_01013500",
    "experiment_name": "",
    "random_seed": 1234,
    "save_config": true,
    "param_range_file": null
  }
}
```

**关键字段说明**:
- `data_source_type`: 数据集类型，支持 "camels_us", "camels_gb", "camels_aus" 等 35+ 数据集
- `data_source_path`: 数据集本地路径（从 hydro_setting.yml 自动获取，可不填）
- `algorithm_name`: 算法名称 "SCE_UA" / "GA" / "scipy"
- `algorithm_params`: 算法参数（嵌套在 algorithm_params 内，不是顶层）
- `loss_config.obj_func`: 目标函数 "RMSE"（默认）/ "spotpy_kge" / "spotpy_nashsutcliffe"
- `param_range_file`: 自定义参数范围 YAML 文件路径（迭代优化时扩展边界用，默认 null）

## 注意事项

- 如果用户指定了算法参数（如 rep=500），确保传递给 calibrate_model 的 algorithm_params
- 如果流域验证失败，告知用户并建议有效的流域ID
- 率定完成后务必评估，提供训练期和测试期的对比
- 如果需要自定义参数范围（迭代优化场景），使用 `param_range_file` 参数指定 YAML 文件路径
