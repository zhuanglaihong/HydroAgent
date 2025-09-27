# 水文建模工具调用最佳实践指南

## 概述
本文档提供了HydroAgent中四个核心工具的最佳使用实践，包括推荐参数配置、常见陷阱和优化技巧。遵循这些实践可以显著提高工作流的成功率和结果质量。

## 1. get_model_params 工具最佳实践

### 推荐用法
```json
{
  "tool_name": "get_model_params",
  "parameters": {
    "model_name": "gr4j"  // 使用小写，支持: gr4j, gr2m, gr5j, gr6j, xaj, hymod
  },
  "timeout": 60,
  "retry_count": 1
}
```

### 支持的模型及参数数量
- **gr4j**: 4个参数 (X1: 土壤蓄水容量, X2: 地下水交换系数, X3: 最大地下水蓄水容量, X4: 单位线时间参数)
- **gr2m**: 2个参数 (月尺度简化模型)
- **gr5j**: 5个参数 (扩展的GR4J)
- **gr6j**: 6个参数 (进一步扩展)
- **xaj**: 15个参数 (新安江模型，适用于湿润地区)
- **hymod**: 5个参数 (概念性模型)

### 最佳实践
- 总是在率定前调用此工具了解参数结构
- 使用返回的参数范围信息指导率定算法设置
- 对于新模型，先查看参数说明再进行率定

### 常见错误
- 模型名称大小写错误 ❌ `"GR4J"` → ✅ `"gr4j"`
- 使用不支持的模型名称

## 2. prepare_data 工具最佳实践

### 推荐配置

#### 日尺度数据处理
```json
{
  "tool_name": "prepare_data",
  "parameters": {
    "data_dir": "/absolute/path/to/basin/data",
    "target_data_scale": "D"  // 日尺度
  },
  "timeout": 180,  // 大数据集可能需要更长时间
  "retry_count": 2
}
```

#### 月尺度数据处理
```json
{
  "tool_name": "prepare_data",
  "parameters": {
    "data_dir": "/absolute/path/to/basin/data",
    "target_data_scale": "M"  // 月尺度
  },
  "timeout": 120,
  "retry_count": 2
}
```

### 数据目录结构要求
```
basin_data/
├── basin_12345.csv          # 时序数据文件
├── attributes.nc            # 流域属性文件(可选)
└── timeseries.nc           # 已处理的时序文件(如果存在会被重新生成)
```

### CSV文件格式要求
```csv
date,prcp,pet,flow,et
1980-01-01,4.5,2.1,10.5,1.8
1980-01-02,0.0,2.3,9.2,2.0
```

### 最佳实践
- 使用绝对路径，避免相对路径问题
- 确保CSV文件包含必需列：date, prcp, pet, flow
- 日期格式使用ISO标准：YYYY-MM-DD
- 对于大型数据集，适当增加timeout时间
- 数据预处理失败时，检查文件编码(推荐UTF-8)

### 常见错误
- 使用相对路径导致找不到文件
- CSV缺少必需的列名
- 日期格式不正确
- 数据中有过多的缺失值

## 3. calibrate_model 工具最佳实践

### 标准日尺度率定配置
```json
{
  "tool_name": "calibrate_model",
  "parameters": {
    "data_type": "owndata",
    "data_dir": "/absolute/path/to/basin/data",
    "exp_name": "gr4j_daily_calibration",
    "model": {
      "name": "gr4j",
      "source_type": "sources",
      "source_book": "HF",
      "kernel_size": 15,
      "time_interval_hours": 24
    },
    "basin_ids": ["basin_12345"],
    "periods": ["2000-01-01", "2020-12-31"],           // 总时间段
    "calibrate_period": ["2000-01-01", "2015-12-31"],  // 率定期(75%)
    "test_period": ["2016-01-01", "2020-12-31"],       // 验证期(25%)
    "warmup": 365,                                      // 1年预热期
    "cv_fold": 1,                                      // 无交叉验证
    "algorithm": {
      "name": "SCE_UA",
      "random_seed": 1234,
      "rep": 500,        // 推荐500-1000获得稳定结果
      "ngs": 30,         // 群体数量
      "kstop": 10,       // 停止准则
      "peps": 0.01,      // 收敛精度
      "pcento": 0.01     // 收敛百分比
    },
    "loss": {
      "type": "time_series",
      "obj_func": "NSE",   // 推荐使用NSE
      "events": null
    }
  },
  "timeout": 1800,      // 30分钟，根据数据量调整
  "retry_count": 0       // 率定通常不重试
}
```

### 不同场景的优化算法配置

#### 快速测试 (开发阶段)
```json
"algorithm": {
  "name": "SCE_UA",
  "random_seed": 1234,
  "rep": 100,
  "ngs": 20,
  "kstop": 5,
  "peps": 0.05,
  "pcento": 0.05
}
```

#### 高精度率定 (生产环境)
```json
"algorithm": {
  "name": "SCE_UA",
  "random_seed": 1234,
  "rep": 1000,
  "ngs": 50,
  "kstop": 15,
  "peps": 0.005,
  "pcento": 0.005
}
```

### 时间段划分最佳实践
- **预热期**: 日尺度建议1年(365天)，月尺度建议12个月
- **率定期**: 占总时间的70%-80%
- **验证期**: 占总时间的20%-30%
- **避免**: 验证期太短(<2年)或率定期太短(<5年)

### 目标函数选择指导
- **NSE**: 综合性能评估，适用于大部分径流模拟
- **RMSE**: 关注绝对误差，适用于极值事件
- **KGE**: 平衡偏差、相关性和变异性

### 最佳实践
- 始终设置预热期，避免模型初始状态影响
- 使用固定随机种子确保结果可重现
- 根据计算资源调整rep参数
- 对于多流域，考虑使用批处理模式

## 4. evaluate_model 工具最佳实践

### 标准评估配置
```json
{
  "tool_name": "evaluate_model",
  "parameters": {
    "result_dir": "/path/to/calibration/results",
    "exp_name": "detailed_evaluation",
    "cv_fold": 1
  },
  "timeout": 300,
  "retry_count": 1
}
```

### 评估结果解释

#### NSE值解释
- **NSE > 0.75**: 很好的模拟效果
- **0.65 < NSE ≤ 0.75**: 良好的模拟效果
- **0.50 < NSE ≤ 0.65**: 可接受的模拟效果
- **NSE ≤ 0.50**: 不可接受的模拟效果

#### R²值解释
- **R² > 0.80**: 强相关性
- **0.60 < R² ≤ 0.80**: 中等相关性
- **R² ≤ 0.60**: 弱相关性

### 最佳实践
- 总是在率定完成后立即评估
- 检查训练期和验证期性能差异
- 保存评估结果用于模型比较
- 关注多个指标，不仅仅是NSE

## 工具链组合最佳实践

### 标准4步骤工作流
```
1. prepare_data → 2. get_model_params → 3. calibrate_model → 4. evaluate_model
```

### 依赖关系设计
```json
"dependencies": {
  "task_2": ["task_1"],              // get_model_params 依赖 prepare_data
  "task_3": ["task_1", "task_2"],    // calibrate_model 依赖前两步
  "task_4": ["task_3"]               // evaluate_model 依赖 calibrate_model
}
```

### 错误处理策略
```json
"global_settings": {
  "error_handling": "stop_on_error",  // 率定工作流建议停止于错误
  "timeout": 3600,                   // 全局超时1小时
  "max_parallel_tasks": 1            // 顺序执行确保依赖关系
}
```

## 性能优化技巧

### 计算资源管理
1. **内存**: 大流域数据建议预留4GB+内存
2. **CPU**: SCE-UA可利用多核，设置ngs=CPU核数×2
3. **存储**: 确保结果目录有足够空间(1-2GB per experiment)

### 时间优化
1. **并行化**: 多流域可并行处理
2. **缓存**: 重用已处理的数据
3. **渐进式**: 先快速测试，再精细率定

## 质量保证检查清单

### 数据质量
- [ ] 时序数据完整性检查
- [ ] 异常值识别和处理
- [ ] 时间段连续性验证

### 配置检查
- [ ] 路径存在性验证
- [ ] 参数范围合理性检查
- [ ] 时间段逻辑一致性

### 结果验证
- [ ] NSE值合理性(>0.5)
- [ ] 训练/验证期性能一致性
- [ ] 参数值在合理范围内