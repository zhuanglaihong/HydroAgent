# HydroAgent 工具使用综合指南

本文档详细介绍HydroAgent系统中所有可用工具的功能、参数和使用方法。

## 核心工具概览

HydroAgent提供4个核心工具，支持完整的水文建模工作流：

1. **get_model_params** - 获取模型参数信息
2. **prepare_data** - 数据准备和预处理
3. **calibrate_model** - 模型参数率定
4. **evaluate_model** - 模型性能评估

## 1. get_model_params - 模型参数查询工具

### 功能描述
获取指定水文模型的参数信息，包括参数名称、范围、默认值等。

### 参数配置
```json
{
  "tool_name": "get_model_params",
  "parameters": {
    "model_name": "gr4j",              // 模型名称
    "include_ranges": true,            // 是否包含参数范围
    "include_descriptions": true       // 是否包含参数描述
  }
}
```

### 支持的模型
- `gr1y`, `gr2m`, `gr4j`, `gr5j`, `gr6j`
- `xaj`
- 自定义模型（需要参数配置文件）

### 输出示例
```json
{
  "model_name": "gr4j",
  "parameters": {
    "x1": {"range": [1, 3000], "description": "土壤水容量"},
    "x2": {"range": [-30, 30], "description": "地下水交换系数"},
    "x3": {"range": [1, 1000], "description": "汇流水库容量"},
    "x4": {"range": [1, 240], "description": "单位线时间常数"}
  }
}
```

### 使用场景
- 工作流设计前了解模型结构
- 参数敏感性分析准备
- 自定义参数范围设置

## 2. prepare_data - 数据准备工具

### 功能描述
处理和验证水文时间序列数据，转换为模型可用的标准格式。

### 参数配置
```json
{
  "tool_name": "prepare_data",
  "parameters": {
    "data_dir": "{DATASET_DIR}/camels_11532500",
    "target_data_scale": "D",          // 时间尺度: D/M/Y
    "basin_ids": ["11532500"],         // 流域ID列表（可选）
    "start_date": "2000-01-01",        // 开始日期（可选）
    "end_date": "2023-12-31",          // 结束日期（可选）
    "validate_data": true,             // 数据验证开关
    "fill_missing": false              // 缺失值填充开关
  }
}
```

### 数据要求

#### 输入文件结构
```
data_dir/
├── basin_11532500.csv          # 主要时间序列
├── basin_11532500_monthly.csv  # 月尺度数据（可选）
├── basin_11532500_yearly.csv   # 年尺度数据（可选）
└── basin_attributes.csv        # 流域属性
```

#### CSV格式要求
```csv
date,prcp,tmean,pet,streamflow
2000-01-01,2.5,5.2,1.8,10.5
2000-01-02,0.0,6.1,2.1,9.8
2000-01-03,1.2,4.8,1.5,9.2
```

**必需列**：
- `date`: 日期（YYYY-MM-DD格式）
- `prcp`: 降水量（mm）
- `tmean`: 平均温度（°C）
- `pet`: 潜在蒸散发（mm）
- `streamflow`: 径流量（mm或m³/s）

### 输出结果
```json
{
  "status": "success",
  "processed_files": ["attributes.nc", "timeseries.nc"],
  "data_summary": {
    "time_range": ["2000-01-01", "2023-12-31"],
    "total_records": 8766,
    "missing_data_percentage": 0.05,
    "data_quality_score": 0.95
  }
}
```

### 数据验证规则
1. **时间连续性**: 检查日期序列完整性
2. **数值合理性**: 降水和径流非负值检查
3. **缺失值比例**: 超过20%缺失值会发出警告
4. **异常值检测**: 使用3σ准则检测极值

## 3. calibrate_model - 模型率定工具

### 功能描述
使用优化算法自动率定水文模型参数，最小化观测与模拟值之间的差异。

### 完整参数配置
```json
{
  "tool_name": "calibrate_model",
  "parameters": {
    "data_type": "owndata",                    // 数据类型
    "data_dir": "{DATASET_DIR}/camels_11532500",
    "result_dir": "{RESULT_DIR}",
    "exp_name": "calibration_experiment",

    // 时间配置
    "cv_fold": 1,
    "warmup": 720,                            // 预热期（天）
    "periods": ["2000-01-01", "2023-12-31"],
    "train_period": ["2000-01-01", "2018-12-31"],
    "test_period": ["2019-01-01", "2023-12-31"],

    // 流域配置
    "basin_ids": ["11532500"],

    // 模型配置
    "model": {
      "name": "gr4j",                         // 模型名称
      "source_type": "sources",               // 源码类型
      "source_book": "HF",                    // 源码库
      "kernel_size": 15,                      // 核大小
      "time_interval_hours": 24               // 时间间隔
    },

    // 参数范围文件
    "param_range_file": "{PROJECT_DIR}/hydromodel/models/param.yaml",

    // 优化算法
    "algorithm": {
      "name": "SCE_UA",                       // 算法名称
      "random_seed": 1234,
      "rep": 30,                              // 重复次数
      "ngs": 10,                              // 复合体数量
      "kstop": 3,                             // 停止代数
      "peps": 0.1,                            // 收敛精度
      "pcento": 0.1                           // 百分比收敛
    },

    // 损失函数
    "loss": {
      "type": "time_series",
      "obj_func": "RMSE",                     // NSE, RMSE, KGE
      "events": null
    }
  }
}
```

### 支持的优化算法

#### SCE-UA算法（推荐）
```json
{
  "algorithm": {
    "name": "SCE_UA",
    "rep": 30,        // 复合体数量，越大收敛越好但耗时越长
    "ngs": 10,        // 每个复合体中的点数
    "kstop": 3,       // 连续停止代数
    "peps": 0.1,      // 收敛判据
    "pcento": 0.1     // 百分比收敛判据
  }
}
```

#### 遗传算法
```json
{
  "algorithm": {
    "name": "GA",
    "pop_size": 50,
    "max_generations": 100,
    "crossover_rate": 0.8,
    "mutation_rate": 0.1
  }
}
```

### 输出结果
```json
{
  "status": "success",
  "calibrated_parameters": {
    "x1": 156.23,
    "x2": -0.45,
    "x3": 78.91,
    "x4": 1.67
  },
  "objective_value": 45.67,
  "training_metrics": {
    "NSE": 0.82,
    "RMSE": 45.67,
    "R2": 0.85
  }
}
```

## 4. evaluate_model - 模型评估工具

### 功能描述
评估已率定模型在测试期的性能，计算多种评估指标。

### 参数配置
```json
{
  "tool_name": "evaluate_model",
  "parameters": {
    "result_dir": "{RESULT_DIR}/calibration_experiment",
    "metrics": ["NSE", "RMSE", "R2", "KGE", "Bias"],
    "generate_plots": true,               // 生成结果图表
    "save_detailed_results": true        // 保存详细结果
  }
}
```

### 评估指标说明

#### Nash-Sutcliffe效率系数 (NSE)
- **范围**: (-∞, 1]
- **最优值**: 1
- **解释**: 1表示完美拟合，0表示模拟精度等于均值，负值表示模拟效果差于均值

#### 决定系数 (R²)
- **范围**: [0, 1]
- **最优值**: 1
- **解释**: 表示模拟值与观测值的线性相关程度

#### 均方根误差 (RMSE)
- **范围**: [0, +∞)
- **最优值**: 0
- **解释**: 越小表示预测精度越高

#### Kling-Gupta效率 (KGE)
- **范围**: (-∞, 1]
- **最优值**: 1
- **解释**: 综合考虑相关性、偏差和变异性的指标

### 输出结果
```json
{
  "status": "success",
  "evaluation_results": {
    "train_metrics": {
      "NSE": 0.82,
      "RMSE": 45.67,
      "R2": 0.85,
      "KGE": 0.79,
      "Bias": -2.34
    },
    "test_metrics": {
      "NSE": 0.75,
      "RMSE": 52.18,
      "R2": 0.81,
      "KGE": 0.72,
      "Bias": 3.45
    }
  },
  "performance_assessment": "Good",
  "generated_files": [
    "evaluation_report.html",
    "timeseries_plot.png",
    "scatter_plot.png"
  ]
}
```

## 工具链接和工作流

### 标准工作流序列
```
prepare_data → calibrate_model → evaluate_model
```

### 高级工作流示例
```json
{
  "tasks": [
    {
      "task_id": "get_params",
      "tool_name": "get_model_params",
      "parameters": {"model_name": "gr4j"}
    },
    {
      "task_id": "prepare",
      "tool_name": "prepare_data",
      "dependencies": [],
      "conditions": {"execute_iterations": "first_only"}
    },
    {
      "task_id": "calibrate",
      "tool_name": "calibrate_model",
      "dependencies": ["prepare"]
    },
    {
      "task_id": "evaluate",
      "tool_name": "evaluate_model",
      "dependencies": ["calibrate"]
    }
  ]
}
```

## 性能优化建议

### 率定效率优化
1. **算法参数调整**：
   - 小流域：rep=20, ngs=8
   - 大流域：rep=50, ngs=15

2. **数据预处理**：
   - 使用合适的warmup期（通常365-730天）
   - 确保数据质量，减少缺失值

3. **参数范围设置**：
   - 基于物理意义设置合理范围
   - 避免过宽的参数空间

### 内存和计算优化
1. **并行处理**：多个流域可并行率定
2. **数据缓存**：重复使用处理过的数据
3. **结果存储**：合理设置结果保存级别

## 常见问题和解决方案

### 数据相关问题
1. **"缺少必需列"**：检查CSV文件列名是否正确
2. **"数据格式错误"**：确保日期格式为YYYY-MM-DD
3. **"缺失值过多"**：考虑数据预处理或更换数据源

### 率定相关问题
1. **"收敛失败"**：增加rep和ngs参数值
2. **"参数超出范围"**：检查param_range_file配置
3. **"内存不足"**：减少并行任务数或数据量

### 评估相关问题
1. **"无法找到率定结果"**：检查result_dir路径
2. **"指标计算异常"**：验证观测数据完整性
3. **"图表生成失败"**：检查matplotlib依赖安装

## 最佳实践总结

1. **数据准备**：确保高质量的输入数据
2. **模型选择**：根据流域特征选择合适模型
3. **算法配置**：平衡精度和效率
4. **结果验证**：多个指标综合评估
5. **文档记录**：保存完整的配置和结果信息