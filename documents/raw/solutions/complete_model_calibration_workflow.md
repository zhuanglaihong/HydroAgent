# 完整水文模型率定工作流解决方案

## 概述
本文档提供了一个完整的水文模型率定工作流解决方案，从数据准备到模型评估的端到端过程。这是一个经过验证的、可复现的标准流程，适用于大多数日尺度水文模型率定任务。

## 标准工作流步骤

### 第一步：数据准备 (prepare_data)
**目的**: 预处理时序数据，确保数据格式正确且质量良好

**关键参数配置**:
```json
{
  "tool_name": "prepare_data",
  "parameters": {
    "data_type": "owndata",
    "data_dir": "path/to/your/data",
    "target_data_scale": "D"
  },
  "timeout": 120,
  "retry_count": 1
}
```

**输出**: 格式化的NetCDF时序数据文件

### 第二步：获取模型参数信息 (get_model_params)
**目的**: 了解目标模型的参数结构，为率定做准备

**关键参数配置**:
```json
{
  "tool_name": "get_model_params",
  "parameters": {
    "model_name": "gr4j"
  },
  "dependencies": ["task_prepare_data"],
  "timeout": 60,
  "retry_count": 1
}
```

**输出**: 模型参数名称、范围和数量信息

### 第三步：模型参数率定 (calibrate_model)
**目的**: 使用优化算法找到最优参数组合

**关键参数配置**:
```json
{
  "tool_name": "calibrate_model",
  "parameters": {
    "data_type": "owndata",
    "data_dir": "path/to/your/data",
    "exp_name": "calibration_experiment",
    "model": {
      "name": "gr4j",
      "source_type": "sources",
      "source_book": "HF",
      "kernel_size": 15,
      "time_interval_hours": 24
    },
    "basin_ids": ["your_basin_id"],
    "periods": ["2000-01-01", "2020-12-31"],
    "calibrate_period": ["2000-01-01", "2015-12-31"],
    "test_period": ["2016-01-01", "2020-12-31"],
    "warmup": 365,
    "cv_fold": 1,
    "algorithm": {
      "name": "SCE_UA",
      "random_seed": 1234,
      "rep": 500,
      "ngs": 30,
      "kstop": 10,
      "peps": 0.01,
      "pcento": 0.01
    },
    "loss": {
      "type": "time_series",
      "obj_func": "NSE",
      "events": null
    }
  },
  "dependencies": ["task_prepare_data", "task_get_params"],
  "timeout": 1800,
  "retry_count": 0
}
```

**输出**: 率定完成的模型参数和配置文件

### 第四步：模型性能评估 (evaluate_model)
**目的**: 评估率定后的模型在训练期和验证期的性能

**关键参数配置**:
```json
{
  "tool_name": "evaluate_model",
  "parameters": {
    "result_dir": "path/to/calibration/results",
    "exp_name": "evaluation_experiment",
    "cv_fold": 1
  },
  "dependencies": ["task_calibrate_model"],
  "timeout": 300,
  "retry_count": 1
}
```

**输出**: 各种性能指标(NSE, R2, RMSE等)和模拟结果

## 完整工作流JSON示例

```json
{
  "workflow_id": "complete_model_calibration",
  "name": "完整模型率定工作流",
  "description": "从数据准备到模型评估的端到端率定流程",
  "mode": "sequential",
  "global_settings": {
    "error_handling": "stop_on_error",
    "timeout": 3600
  },
  "tasks": [
    {
      "task_id": "task_1",
      "name": "准备数据",
      "type": "simple",
      "tool_name": "prepare_data",
      "parameters": {
        "data_type": "owndata",
        "data_dir": "/path/to/basin/data",
        "target_data_scale": "D"
      },
      "dependencies": [],
      "timeout": 120,
      "retry_count": 1
    },
    {
      "task_id": "task_2",
      "name": "获取模型参数信息",
      "type": "simple",
      "tool_name": "get_model_params",
      "parameters": {
        "model_name": "gr4j"
      },
      "dependencies": ["task_1"],
      "timeout": 60,
      "retry_count": 1
    },
    {
      "task_id": "task_3",
      "name": "率定模型",
      "type": "simple",
      "tool_name": "calibrate_model",
      "parameters": {
        "data_type": "owndata",
        "data_dir": "/path/to/basin/data",
        "exp_name": "gr4j_calibration",
        "model": {
          "name": "gr4j",
          "source_type": "sources",
          "source_book": "HF",
          "kernel_size": 15,
          "time_interval_hours": 24
        },
        "basin_ids": ["basin_001"],
        "periods": ["2000-01-01", "2020-12-31"],
        "calibrate_period": ["2000-01-01", "2015-12-31"],
        "test_period": ["2016-01-01", "2020-12-31"],
        "warmup": 365,
        "cv_fold": 1,
        "algorithm": {
          "name": "SCE_UA",
          "random_seed": 1234,
          "rep": 500,
          "ngs": 30,
          "kstop": 10,
          "peps": 0.01,
          "pcento": 0.01
        },
        "loss": {
          "type": "time_series",
          "obj_func": "NSE",
          "events": null
        }
      },
      "dependencies": ["task_1", "task_2"],
      "timeout": 1800,
      "retry_count": 0
    },
    {
      "task_id": "task_4",
      "name": "评估模型性能",
      "type": "simple",
      "tool_name": "evaluate_model",
      "parameters": {
        "result_dir": "/path/to/results/gr4j_calibration",
        "exp_name": "gr4j_evaluation",
        "cv_fold": 1
      },
      "dependencies": ["task_3"],
      "timeout": 300,
      "retry_count": 1
    }
  ]
}
```

## 时间配置建议

- **数据准备**: 通常1-3分钟，设置timeout=120秒
- **获取参数**: 几秒钟内完成，设置timeout=60秒
- **模型率定**: 取决于算法参数和数据量，建议15-30分钟，设置timeout=1800秒
- **模型评估**: 通常2-5分钟，设置timeout=300秒

## 关键成功因素

1. **数据质量**: 确保时序数据完整性和格式正确性
2. **时间段划分**: 合理的率定期和验证期划分(通常70%-30%)
3. **预热期设置**: 日尺度模型建议设置1年(365天)预热期
4. **算法参数**: SCE-UA算法建议rep=500以上获得稳定结果
5. **目标函数选择**: NSE适用于径流模拟，RMSE适用于关注峰值

## 预期结果

成功的率定工作流应该产生：
- 训练期NSE > 0.6 (良好), > 0.75 (很好)
- 验证期NSE > 0.5 (可接受), > 0.65 (良好)
- 训练期和验证期性能差异 < 0.15

## 故障排除提示

- **数据准备失败**: 检查数据目录路径和文件格式
- **率定收敛慢**: 增加rep参数或调整kstop、peps参数
- **评估失败**: 确认率定结果目录路径正确
- **性能差**: 检查数据质量、时间段划分和预热期设置