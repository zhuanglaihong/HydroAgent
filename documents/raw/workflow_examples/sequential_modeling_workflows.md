# 顺序执行水文建模工作流模式

## 概述
本文档提供了顺序执行（Sequential/Linear）模式的水文建模工作流模板和最佳实践。顺序模式是最常用的工作流模式，适用于步骤明确、无需反馈循环的标准建模任务。此模式执行效率高、调试简单，是大多数日常建模工作的首选。

## 顺序模式核心特征

### 关键特性
- **线性执行**: 严格按照依赖关系顺序执行任务
- **高效稳定**: 无复杂控制逻辑，执行效率最高
- **易于调试**: 简单的任务链便于问题定位
- **资源可控**: 资源消耗可预测，适合批量处理
- **确定性强**: 相同输入产生相同结果

### 适用场景
- 标准模型率定和评估流程
- 批量流域建模任务
- 模型性能对比研究
- 生产环境的例行建模
- 教学和演示用途

## 完整水文建模工作流模板

### 模板1：GR4J完整建模流水线

```json
{
  "workflow_id": "complete_hydro_workflow",
  "name": "完整水文模型工作流",
  "description": "完整的水文建模流水线：数据准备 -> 模型率定 -> 模型评估",
  "execution_mode": "sequential",
  "tasks": [
    {
      "task_id": "task_prepare",
      "name": "准备水文数据",
      "description": "处理和验证水文时间序列数据，转换为模型可用的netCDF格式",
      "tool_name": "prepare_data",
      "type": "simple",
      "parameters": {
        "data_dir": "{{DATA_DIR}}",
        "target_data_scale": "D"
      },
      "dependencies": [],
      "conditions": {
        "retry_count": 2,
        "timeout": 300
      },
      "expected_output": "处理后的数据文件路径和统计信息"
    },
    {
      "task_id": "task_calibrate",
      "name": "率定GR4J模型",
      "description": "使用SCE-UA算法对GR4J水文模型进行参数率定",
      "tool_name": "calibrate_model",
      "type": "simple",
      "parameters": {
        "data_type": "owndata",
        "data_dir": "{{DATA_DIR}}",
        "result_dir": "{{RESULT_DIR}}",
        "exp_name": "complete_workflow_exp",
        "cv_fold": 1,
        "warmup": 720,
        "periods": ["2000-01-01", "2023-12-31"],
        "train_period": ["2000-01-01", "2018-12-31"],
        "test_period": ["2019-01-01", "2023-12-31"],
        "basin_ids": ["{{BASIN_ID}}"],
        "model": {
          "name": "gr4j",
          "source_type": "sources",
          "source_book": "HF",
          "kernel_size": 15,
          "time_interval_hours": 24
        },
        "param_range_file": "{{PARAM_RANGE_FILE}}",
        "algorithm": {
          "name": "SCE_UA",
          "random_seed": 1234,
          "rep": 50,
          "ngs": 15,
          "kstop": 3,
          "peps": 0.1,
          "pcento": 0.1
        },
        "loss": {
          "type": "time_series",
          "obj_func": "RMSE",
          "events": null
        }
      },
      "dependencies": ["task_prepare"],
      "conditions": {
        "retry_count": 1,
        "timeout": 1800
      },
      "expected_output": "率定后的模型参数文件和配置信息"
    },
    {
      "task_id": "task_evaluate",
      "name": "评估率定后的模型",
      "description": "评估已率定的GR4J模型在训练期和测试期的性能指标",
      "tool_name": "evaluate_model",
      "type": "simple",
      "parameters": {
        "result_dir": "{{RESULT_DIR}}/complete_workflow_exp"
      },
      "dependencies": ["task_calibrate"],
      "conditions": {
        "retry_count": 2,
        "timeout": 600
      },
      "expected_output": "模型性能评估指标和结果文件"
    }
  ],
  "targets": [
    {
      "type": "performance_goal",
      "metric": "nse",
      "threshold": 0.5,
      "comparison": ">=",
      "max_iterations": 1,
      "description": "NSE指标应大于等于0.5"
    }
  ],
  "metadata": {
    "estimated_duration": "10分钟",
    "complexity": "高",
    "pipeline_type": "complete_hydro_modeling",
    "features": {
      "has_dependencies": true,
      "has_parameter_references": true,
      "has_performance_target": true,
      "sequential_execution": true
    }
  }
}
```

## 标准任务配置说明

### 第一步：数据准备 (prepare_data)

**用途**: 将原始CSV格式的水文数据转换为标准化的NetCDF格式

**关键参数**:
- `data_dir`: 原始数据目录路径
- `target_data_scale`: "D"（日尺度）或"H"（小时尺度）

**典型配置**:
```json
{
  "tool_name": "prepare_data",
  "parameters": {
    "data_dir": "/path/to/camels_data/basin_id",
    "target_data_scale": "D"
  },
  "timeout": 300,
  "retry_count": 2
}
```

**预期输出**: 格式化的时序数据文件和数据质量报告

### 第二步：模型率定 (calibrate_model)

**用途**: 使用优化算法寻找最优模型参数

**关键参数配置**:

**基础设置**:
```json
{
  "data_type": "owndata",
  "result_dir": "/path/to/results",
  "exp_name": "my_experiment",
  "cv_fold": 1,
  "warmup": 720
}
```

**时间设置**:
```json
{
  "periods": ["2000-01-01", "2023-12-31"],
  "train_period": ["2000-01-01", "2018-12-31"],
  "test_period": ["2019-01-01", "2023-12-31"]
}
```

**模型配置**:
```json
{
  "model": {
    "name": "gr4j",
    "source_type": "sources",
    "source_book": "HF",
    "kernel_size": 15,
    "time_interval_hours": 24
  }
}
```

**优化算法配置**:
```json
{
  "algorithm": {
    "name": "SCE_UA",
    "random_seed": 1234,
    "rep": 50,
    "ngs": 15,
    "kstop": 3,
    "peps": 0.1,
    "pcento": 0.1
  }
}
```

### 第三步：模型评估 (evaluate_model)

**用途**: 计算训练期和测试期的性能指标

**关键参数**:
```json
{
  "tool_name": "evaluate_model",
  "parameters": {
    "result_dir": "/path/to/results/experiment_name"
  }
}
```

**预期输出**: NSE、KGE、RMSE等性能指标和可视化图表

## 参数配置最佳实践

### 数据质量要求
- **最小数据长度**: 5年连续数据
- **训练/测试比例**: 建议7:3或8:2
- **暖机期设置**: 至少2年（720天）
- **数据完整性**: 缺失率不超过5%

### 算法参数调优

**快速测试配置**（开发阶段）:
```json
{
  "algorithm": {
    "rep": 20,
    "ngs": 10,
    "kstop": 3
  }
}
```

**标准配置**（正式研究）:
```json
{
  "algorithm": {
    "rep": 50,
    "ngs": 15,
    "kstop": 3
  }
}
```

**高精度配置**（发表论文）:
```json
{
  "algorithm": {
    "rep": 100,
    "ngs": 20,
    "kstop": 5
  }
}
```

### 超时时间建议

**任务类型与超时设置**:
- **数据准备**: 300秒（5分钟）
- **模型率定**: 1800秒（30分钟，标准配置）
- **模型评估**: 600秒（10分钟）

## 模型类型扩展

### XAJ模型配置示例

```json
{
  "model": {
    "name": "xaj",
    "source_type": "sources",
    "source_book": "HF",
    "kernel_size": 15,
    "time_interval_hours": 24
  },
  "algorithm": {
    "name": "SCE_UA",
    "rep": 80,
    "ngs": 20,
    "kstop": 5
  }
}
```

### LSTM模型配置示例

```json
{
  "model": {
    "name": "lstm",
    "source_type": "sources",
    "source_book": "HF",
    "kernel_size": 10,
    "time_interval_hours": 24,
    "hidden_size": 256,
    "dropout": 0.1
  }
}
```

## 批量处理模板

### 多流域批量建模

```json
{
  "workflow_id": "batch_multi_basin_modeling",
  "name": "多流域批量建模工作流",
  "description": "对多个流域执行标准建模流程",
  "execution_mode": "sequential",
  "global_parameters": {
    "basin_list": ["11532500", "11478500", "11381500"],
    "base_data_dir": "/data/camels",
    "base_result_dir": "/results/batch_run"
  },
  "tasks": [
    {
      "task_id": "batch_prepare",
      "name": "批量数据准备",
      "tool_name": "prepare_data",
      "type": "simple",
      "parameters": {
        "data_dir": "{{base_data_dir}}/{{basin_id}}",
        "target_data_scale": "D",
        "batch_mode": true,
        "basin_list": "{{basin_list}}"
      }
    },
    {
      "task_id": "batch_calibrate",
      "name": "批量模型率定",
      "tool_name": "calibrate_model",
      "type": "simple",
      "parameters": {
        "data_type": "owndata",
        "data_dir": "{{base_data_dir}}",
        "result_dir": "{{base_result_dir}}",
        "exp_name": "batch_experiment",
        "basin_ids": "{{basin_list}}",
        "model": {"name": "gr4j"},
        "algorithm": {"name": "SCE_UA", "rep": 30}
      },
      "dependencies": ["batch_prepare"]
    },
    {
      "task_id": "batch_evaluate",
      "name": "批量性能评估",
      "tool_name": "evaluate_model",
      "type": "simple",
      "parameters": {
        "result_dir": "{{base_result_dir}}/batch_experiment",
        "batch_mode": true,
        "generate_summary": true
      },
      "dependencies": ["batch_calibrate"]
    }
  ]
}
```

## 性能优化建议

### 并行处理优化
- 独立任务可以并行执行（如多流域处理）
- 合理设置任务依赖关系避免不必要的串行等待
- 利用系统多核资源进行算法内部并行

### 存储优化
- 合理规划结果存储路径结构
- 定期清理中间文件释放存储空间
- 使用压缩格式存储大型时序数据

### 监控和日志
- 设置合理的超时时间防止死锁
- 启用详细日志记录便于问题诊断
- 监控系统资源使用情况

## 常见问题和解决方案

### 问题1：数据格式不兼容
**症状**: prepare_data任务失败，提示数据格式错误
**解决**: 检查原始数据CSV文件格式，确保包含必需的列名和时间格式

### 问题2：率定收敛慢或不收敛
**症状**: calibrate_model任务超时或性能指标很差
**解决**: 调整算法参数（增加rep和ngs），或检查数据质量

### 问题3：评估结果异常
**症状**: evaluate_model产生极端的性能指标值
**解决**: 检查率定结果文件完整性，确认时间段设置正确

## 扩展和定制

### 添加自定义指标
```json
{
  "custom_metrics": {
    "bias": true,
    "rmse_log": true,
    "peak_timing": true
  }
}
```

### 集成可视化
```json
{
  "visualization": {
    "time_series_plot": true,
    "scatter_plot": true,
    "performance_summary": true,
    "export_format": ["png", "pdf"]
  }
}
```

### 结果后处理
```json
{
  "post_processing": {
    "export_parameters": true,
    "generate_report": true,
    "archive_results": true
  }
}
```

顺序执行模式是水文建模工作流的基础模式，具有高效、稳定、易调试的特点。通过合理配置参数和优化流程设计，可以满足大多数日常建模需求。