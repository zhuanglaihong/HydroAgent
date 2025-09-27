# 常见水文建模场景解决方案

## 概述
本文档提供了水文建模中最常见的6种场景的完整解决方案。每个场景都包含具体的工作流配置、参数设置和预期结果，可以直接作为模板使用。

## 场景1：单流域日尺度GR4J模型率定

### 场景描述
对单个流域进行GR4J模型的日尺度径流模拟率定，这是最基础和最常用的场景。

### 解决方案
```json
{
  "workflow_id": "single_basin_gr4j_daily",
  "name": "单流域GR4J日尺度率定",
  "description": "对单个流域进行GR4J模型日尺度径流模拟",
  "mode": "sequential",
  "global_settings": {
    "error_handling": "stop_on_error",
    "timeout": 3600
  },
  "tasks": [
    {
      "task_id": "prepare",
      "name": "数据预处理",
      "type": "simple",
      "tool_name": "prepare_data",
      "parameters": {
        "data_dir": "/path/to/basin/data",
        "target_data_scale": "D"
      },
      "timeout": 120,
      "retry_count": 1
    },
    {
      "task_id": "get_params",
      "name": "获取GR4J参数信息",
      "type": "simple",
      "tool_name": "get_model_params",
      "parameters": {
        "model_name": "gr4j"
      },
      "dependencies": ["prepare"],
      "timeout": 60,
      "retry_count": 1
    },
    {
      "task_id": "calibrate",
      "name": "GR4J模型率定",
      "type": "simple",
      "tool_name": "calibrate_model",
      "parameters": {
        "data_type": "owndata",
        "data_dir": "/path/to/basin/data",
        "exp_name": "gr4j_single_basin",
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
          "obj_func": "NSE"
        }
      },
      "dependencies": ["prepare", "get_params"],
      "timeout": 1800,
      "retry_count": 0
    },
    {
      "task_id": "evaluate",
      "name": "模型性能评估",
      "type": "simple",
      "tool_name": "evaluate_model",
      "parameters": {
        "result_dir": "/path/to/results/gr4j_single_basin",
        "exp_name": "gr4j_evaluation"
      },
      "dependencies": ["calibrate"],
      "timeout": 300,
      "retry_count": 1
    }
  ]
}
```

### 预期结果
- 训练期 NSE: 0.65-0.85
- 验证期 NSE: 0.55-0.75
- 执行时间: 20-40分钟

## 场景2：多模型并行比较

### 场景描述
同时率定GR4J和新安江(XAJ)模型，比较它们在同一流域的性能。

### 解决方案
```json
{
  "workflow_id": "multi_model_comparison",
  "name": "多模型并行比较",
  "description": "并行比较GR4J和XAJ模型性能",
  "mode": "parallel",
  "global_settings": {
    "error_handling": "continue_on_error",
    "timeout": 7200,
    "max_parallel_tasks": 2
  },
  "tasks": [
    {
      "task_id": "prepare_data",
      "name": "数据预处理",
      "type": "simple",
      "tool_name": "prepare_data",
      "parameters": {
        "data_dir": "/path/to/basin/data",
        "target_data_scale": "D"
      },
      "timeout": 120,
      "retry_count": 1
    },
    {
      "task_id": "gr4j_params",
      "name": "获取GR4J参数",
      "type": "simple",
      "tool_name": "get_model_params",
      "parameters": {
        "model_name": "gr4j"
      },
      "dependencies": ["prepare_data"],
      "timeout": 60,
      "retry_count": 1
    },
    {
      "task_id": "xaj_params",
      "name": "获取XAJ参数",
      "type": "simple",
      "tool_name": "get_model_params",
      "parameters": {
        "model_name": "xaj"
      },
      "dependencies": ["prepare_data"],
      "timeout": 60,
      "retry_count": 1
    },
    {
      "task_id": "gr4j_calibrate",
      "name": "GR4J模型率定",
      "type": "simple",
      "tool_name": "calibrate_model",
      "parameters": {
        "data_type": "owndata",
        "data_dir": "/path/to/basin/data",
        "exp_name": "gr4j_comparison",
        "model": {
          "name": "gr4j"
        },
        "basin_ids": ["basin_001"],
        "periods": ["2000-01-01", "2020-12-31"],
        "calibrate_period": ["2000-01-01", "2015-12-31"],
        "test_period": ["2016-01-01", "2020-12-31"],
        "warmup": 365,
        "algorithm": {
          "name": "SCE_UA",
          "random_seed": 1234,
          "rep": 300,
          "ngs": 20
        }
      },
      "dependencies": ["prepare_data", "gr4j_params"],
      "timeout": 1200,
      "retry_count": 0
    },
    {
      "task_id": "xaj_calibrate",
      "name": "XAJ模型率定",
      "type": "simple",
      "tool_name": "calibrate_model",
      "parameters": {
        "data_type": "owndata",
        "data_dir": "/path/to/basin/data",
        "exp_name": "xaj_comparison",
        "model": {
          "name": "xaj"
        },
        "basin_ids": ["basin_001"],
        "periods": ["2000-01-01", "2020-12-31"],
        "calibrate_period": ["2000-01-01", "2015-12-31"],
        "test_period": ["2016-01-01", "2020-12-31"],
        "warmup": 365,
        "algorithm": {
          "name": "SCE_UA",
          "random_seed": 1234,
          "rep": 500,
          "ngs": 50
        }
      },
      "dependencies": ["prepare_data", "xaj_params"],
      "timeout": 2400,
      "retry_count": 0
    },
    {
      "task_id": "gr4j_evaluate",
      "name": "GR4J性能评估",
      "type": "simple",
      "tool_name": "evaluate_model",
      "parameters": {
        "result_dir": "/path/to/results/gr4j_comparison"
      },
      "dependencies": ["gr4j_calibrate"],
      "timeout": 300
    },
    {
      "task_id": "xaj_evaluate",
      "name": "XAJ性能评估",
      "type": "simple",
      "tool_name": "evaluate_model",
      "parameters": {
        "result_dir": "/path/to/results/xaj_comparison"
      },
      "dependencies": ["xaj_calibrate"],
      "timeout": 300
    }
  ]
}
```

## 场景3：月尺度长期预测

### 场景描述
使用GR2M模型进行月尺度的长期径流预测，适用于水资源规划。

### 解决方案
```json
{
  "workflow_id": "monthly_prediction",
  "name": "月尺度长期预测",
  "description": "使用GR2M模型进行月尺度径流预测",
  "mode": "sequential",
  "global_settings": {
    "error_handling": "stop_on_error",
    "timeout": 1800
  },
  "tasks": [
    {
      "task_id": "prepare",
      "name": "月尺度数据预处理",
      "type": "simple",
      "tool_name": "prepare_data",
      "parameters": {
        "data_dir": "/path/to/basin/data",
        "target_data_scale": "M"
      },
      "timeout": 120,
      "retry_count": 1
    },
    {
      "task_id": "get_params",
      "name": "获取GR2M参数",
      "type": "simple",
      "tool_name": "get_model_params",
      "parameters": {
        "model_name": "gr2m"
      },
      "dependencies": ["prepare"],
      "timeout": 60,
      "retry_count": 1
    },
    {
      "task_id": "calibrate",
      "name": "GR2M模型率定",
      "type": "simple",
      "tool_name": "calibrate_model",
      "parameters": {
        "data_type": "owndata",
        "data_dir": "/path/to/basin/data",
        "exp_name": "gr2m_monthly",
        "model": {
          "name": "gr2m",
          "time_interval_hours": 720
        },
        "basin_ids": ["basin_001"],
        "periods": ["1990-01-01", "2020-12-31"],
        "calibrate_period": ["1990-01-01", "2010-12-31"],
        "test_period": ["2011-01-01", "2020-12-31"],
        "warmup": 12,
        "algorithm": {
          "name": "SCE_UA",
          "rep": 200,
          "ngs": 10
        }
      },
      "dependencies": ["prepare", "get_params"],
      "timeout": 900,
      "retry_count": 0
    },
    {
      "task_id": "evaluate",
      "name": "月尺度评估",
      "type": "simple",
      "tool_name": "evaluate_model",
      "parameters": {
        "result_dir": "/path/to/results/gr2m_monthly"
      },
      "dependencies": ["calibrate"],
      "timeout": 300
    }
  ]
}
```

## 场景4：快速原型验证

### 场景描述
用于快速测试和验证的轻量级配置，适用于开发阶段的快速迭代。

### 解决方案
```json
{
  "workflow_id": "quick_prototype",
  "name": "快速原型验证",
  "description": "快速测试配置，用于开发和调试",
  "mode": "sequential",
  "global_settings": {
    "error_handling": "continue_on_error",
    "timeout": 600
  },
  "tasks": [
    {
      "task_id": "prepare",
      "name": "快速数据准备",
      "type": "simple",
      "tool_name": "prepare_data",
      "parameters": {
        "data_dir": "/path/to/test/data",
        "target_data_scale": "D"
      },
      "timeout": 60,
      "retry_count": 1
    },
    {
      "task_id": "calibrate",
      "name": "快速率定",
      "type": "simple",
      "tool_name": "calibrate_model",
      "parameters": {
        "data_type": "owndata",
        "data_dir": "/path/to/test/data",
        "exp_name": "quick_test",
        "model": {
          "name": "gr4j"
        },
        "basin_ids": ["test_basin"],
        "periods": ["2018-01-01", "2020-12-31"],
        "calibrate_period": ["2018-01-01", "2019-12-31"],
        "test_period": ["2020-01-01", "2020-12-31"],
        "warmup": 90,
        "algorithm": {
          "name": "SCE_UA",
          "rep": 50,
          "ngs": 10,
          "kstop": 3
        }
      },
      "dependencies": ["prepare"],
      "timeout": 300,
      "retry_count": 0
    }
  ]
}
```

## 场景5：高精度生产环境率定

### 场景描述
用于生产环境的高精度率定配置，追求最佳性能和稳定性。

### 关键配置差异
```json
"algorithm": {
  "name": "SCE_UA",
  "random_seed": 1234,
  "rep": 1000,        // 更多迭代
  "ngs": 50,          // 更大群体
  "kstop": 20,        // 更严格停止条件
  "peps": 0.001,      // 更高精度
  "pcento": 0.001
},
"warmup": 730,        // 2年预热期
"timeout": 3600       // 1小时超时
```

## 场景6：交叉验证模型稳定性测试

### 场景描述
使用交叉验证评估模型在不同时间段的稳定性和泛化能力。

### 解决方案
```json
{
  "workflow_id": "cross_validation_stability",
  "name": "交叉验证稳定性测试",
  "description": "使用交叉验证评估模型稳定性",
  "mode": "sequential",
  "tasks": [
    {
      "task_id": "calibrate_cv",
      "name": "交叉验证率定",
      "type": "simple",
      "tool_name": "calibrate_model",
      "parameters": {
        "cv_fold": 5,        // 5折交叉验证
        "algorithm": {
          "rep": 300,
          "random_seed": 42    // 固定种子确保可重现
        }
      },
      "timeout": 7200        // 需要更长时间
    }
  ]
}
```

## 场景选择指导

### 根据数据量选择
- **< 5年数据**: 场景4 (快速原型)
- **5-15年数据**: 场景1 (标准率定)
- **> 15年数据**: 场景5 (高精度) 或 场景6 (交叉验证)

### 根据计算资源选择
- **有限资源**: 场景4, rep=50-100
- **中等资源**: 场景1, rep=300-500
- **充足资源**: 场景5, rep=1000+

### 根据应用目的选择
- **快速测试**: 场景4
- **日常研究**: 场景1
- **模型比较**: 场景2
- **长期规划**: 场景3
- **生产应用**: 场景5
- **论文发表**: 场景6

## 性能基准

### 不同场景的预期性能
| 场景 | 训练期NSE | 验证期NSE | 执行时间 | 资源需求 |
|------|-----------|-----------|----------|----------|
| 快速原型 | 0.50-0.70 | 0.40-0.60 | 5-10分钟 | 低 |
| 标准率定 | 0.65-0.80 | 0.55-0.70 | 20-40分钟 | 中 |
| 高精度 | 0.70-0.85 | 0.60-0.75 | 60-120分钟 | 高 |
| 交叉验证 | 0.60-0.75 | 0.55-0.70 | 120-300分钟 | 高 |

### 质量控制标准
- 训练期和验证期NSE差值 < 0.15
- 参数值在合理物理范围内
- 算法收敛稳定(kstop达到停止条件)