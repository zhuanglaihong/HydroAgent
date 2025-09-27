# 工作流模板代码库

## 概述
本文档提供了各种水文建模工作流的完整JSON模板，可以直接复制使用或作为基础进行修改。所有模板都经过验证，包含详细的参数说明。

## 模板1：标准GR4J日率定模板

```json
{
  "workflow_id": "gr4j_daily_standard_{{timestamp}}",
  "name": "GR4J日尺度标准率定",
  "description": "适用于大多数日尺度流域径流模拟的标准配置",
  "mode": "sequential",
  "global_settings": {
    "error_handling": "stop_on_error",
    "timeout": 3600,
    "save_intermediate_results": true
  },
  "metadata": {
    "template_version": "1.0",
    "recommended_for": ["日尺度径流模拟", "中小型流域", "常规研究"],
    "data_requirements": "至少5年连续日数据"
  },
  "tasks": [
    {
      "task_id": "step_1_prepare_data",
      "name": "数据预处理",
      "type": "simple",
      "tool_name": "prepare_data",
      "parameters": {
        "data_dir": "{{DATA_DIR}}",
        "target_data_scale": "D"
      },
      "dependencies": [],
      "timeout": 120,
      "retry_count": 1,
      "description": "将原始CSV数据转换为NetCDF格式"
    },
    {
      "task_id": "step_2_get_model_info",
      "name": "获取GR4J模型信息",
      "type": "simple",
      "tool_name": "get_model_params",
      "parameters": {
        "model_name": "gr4j"
      },
      "dependencies": ["step_1_prepare_data"],
      "timeout": 60,
      "retry_count": 1,
      "description": "获取GR4J模型的4个参数定义和范围"
    },
    {
      "task_id": "step_3_calibrate",
      "name": "模型参数率定",
      "type": "simple",
      "tool_name": "calibrate_model",
      "parameters": {
        "data_type": "owndata",
        "data_dir": "{{DATA_DIR}}",
        "exp_name": "gr4j_standard_{{BASIN_ID}}",
        "model": {
          "name": "gr4j",
          "source_type": "sources",
          "source_book": "HF",
          "kernel_size": 15,
          "time_interval_hours": 24
        },
        "basin_ids": ["{{BASIN_ID}}"],
        "periods": ["{{FULL_START_DATE}}", "{{FULL_END_DATE}}"],
        "calibrate_period": ["{{CALIB_START_DATE}}", "{{CALIB_END_DATE}}"],
        "test_period": ["{{TEST_START_DATE}}", "{{TEST_END_DATE}}"],
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
      "dependencies": ["step_1_prepare_data", "step_2_get_model_info"],
      "timeout": 1800,
      "retry_count": 0,
      "description": "使用SCE-UA算法率定GR4J模型参数"
    },
    {
      "task_id": "step_4_evaluate",
      "name": "模型性能评估",
      "type": "simple",
      "tool_name": "evaluate_model",
      "parameters": {
        "result_dir": "{{RESULT_DIR}}/gr4j_standard_{{BASIN_ID}}",
        "exp_name": "evaluation_{{BASIN_ID}}",
        "cv_fold": 1
      },
      "dependencies": ["step_3_calibrate"],
      "timeout": 300,
      "retry_count": 1,
      "description": "计算训练期和验证期的各种性能指标"
    }
  ],
  "variables": {
    "DATA_DIR": "/path/to/basin/data",
    "RESULT_DIR": "/path/to/results",
    "BASIN_ID": "basin_001",
    "FULL_START_DATE": "2000-01-01",
    "FULL_END_DATE": "2020-12-31",
    "CALIB_START_DATE": "2000-01-01",
    "CALIB_END_DATE": "2015-12-31",
    "TEST_START_DATE": "2016-01-01",
    "TEST_END_DATE": "2020-12-31"
  }
}
```

## 模板2：多模型并行比较模板

```json
{
  "workflow_id": "multi_model_comparison_{{timestamp}}",
  "name": "多模型并行性能比较",
  "description": "并行比较GR4J和XAJ模型在同一流域的表现",
  "mode": "parallel",
  "global_settings": {
    "error_handling": "continue_on_error",
    "timeout": 7200,
    "max_parallel_tasks": 4
  },
  "metadata": {
    "template_version": "1.0",
    "recommended_for": ["模型选择研究", "方法比较", "论文发表"],
    "models_compared": ["GR4J", "XAJ"]
  },
  "tasks": [
    {
      "task_id": "prepare_shared_data",
      "name": "共享数据预处理",
      "type": "simple",
      "tool_name": "prepare_data",
      "parameters": {
        "data_dir": "{{DATA_DIR}}",
        "target_data_scale": "D"
      },
      "dependencies": [],
      "timeout": 180,
      "retry_count": 1
    },
    {
      "task_id": "get_gr4j_params",
      "name": "获取GR4J参数信息",
      "type": "simple",
      "tool_name": "get_model_params",
      "parameters": {
        "model_name": "gr4j"
      },
      "dependencies": ["prepare_shared_data"],
      "timeout": 60,
      "retry_count": 1
    },
    {
      "task_id": "get_xaj_params",
      "name": "获取XAJ参数信息",
      "type": "simple",
      "tool_name": "get_model_params",
      "parameters": {
        "model_name": "xaj"
      },
      "dependencies": ["prepare_shared_data"],
      "timeout": 60,
      "retry_count": 1
    },
    {
      "task_id": "calibrate_gr4j",
      "name": "GR4J模型率定",
      "type": "simple",
      "tool_name": "calibrate_model",
      "parameters": {
        "data_type": "owndata",
        "data_dir": "{{DATA_DIR}}",
        "exp_name": "comparison_gr4j_{{BASIN_ID}}",
        "model": {
          "name": "gr4j",
          "source_type": "sources",
          "source_book": "HF",
          "time_interval_hours": 24
        },
        "basin_ids": ["{{BASIN_ID}}"],
        "periods": ["{{FULL_START_DATE}}", "{{FULL_END_DATE}}"],
        "calibrate_period": ["{{CALIB_START_DATE}}", "{{CALIB_END_DATE}}"],
        "test_period": ["{{TEST_START_DATE}}", "{{TEST_END_DATE}}"],
        "warmup": 365,
        "algorithm": {
          "name": "SCE_UA",
          "random_seed": 1234,
          "rep": 400,
          "ngs": 25
        }
      },
      "dependencies": ["prepare_shared_data", "get_gr4j_params"],
      "timeout": 1500,
      "retry_count": 0
    },
    {
      "task_id": "calibrate_xaj",
      "name": "XAJ模型率定",
      "type": "simple",
      "tool_name": "calibrate_model",
      "parameters": {
        "data_type": "owndata",
        "data_dir": "{{DATA_DIR}}",
        "exp_name": "comparison_xaj_{{BASIN_ID}}",
        "model": {
          "name": "xaj",
          "source_type": "sources",
          "source_book": "HF",
          "time_interval_hours": 24
        },
        "basin_ids": ["{{BASIN_ID}}"],
        "periods": ["{{FULL_START_DATE}}", "{{FULL_END_DATE}}"],
        "calibrate_period": ["{{CALIB_START_DATE}}", "{{CALIB_END_DATE}}"],
        "test_period": ["{{TEST_START_DATE}}", "{{TEST_END_DATE}}"],
        "warmup": 365,
        "algorithm": {
          "name": "SCE_UA",
          "random_seed": 1234,
          "rep": 600,
          "ngs": 45
        }
      },
      "dependencies": ["prepare_shared_data", "get_xaj_params"],
      "timeout": 2400,
      "retry_count": 0
    },
    {
      "task_id": "evaluate_gr4j",
      "name": "GR4J性能评估",
      "type": "simple",
      "tool_name": "evaluate_model",
      "parameters": {
        "result_dir": "{{RESULT_DIR}}/comparison_gr4j_{{BASIN_ID}}",
        "exp_name": "eval_gr4j"
      },
      "dependencies": ["calibrate_gr4j"],
      "timeout": 300
    },
    {
      "task_id": "evaluate_xaj",
      "name": "XAJ性能评估",
      "type": "simple",
      "tool_name": "evaluate_model",
      "parameters": {
        "result_dir": "{{RESULT_DIR}}/comparison_xaj_{{BASIN_ID}}",
        "exp_name": "eval_xaj"
      },
      "dependencies": ["calibrate_xaj"],
      "timeout": 300
    }
  ]
}
```

## 模板3：快速原型测试模板

```json
{
  "workflow_id": "quick_prototype_{{timestamp}}",
  "name": "快速原型测试",
  "description": "用于快速验证和调试的轻量级配置",
  "mode": "sequential",
  "global_settings": {
    "error_handling": "continue_on_error",
    "timeout": 900,
    "debug_mode": true
  },
  "metadata": {
    "template_version": "1.0",
    "recommended_for": ["开发调试", "快速验证", "参数测试"],
    "execution_time": "5-15分钟"
  },
  "tasks": [
    {
      "task_id": "quick_prepare",
      "name": "快速数据准备",
      "type": "simple",
      "tool_name": "prepare_data",
      "parameters": {
        "data_dir": "{{DATA_DIR}}",
        "target_data_scale": "D"
      },
      "timeout": 60,
      "retry_count": 1
    },
    {
      "task_id": "quick_calibrate",
      "name": "快速率定测试",
      "type": "simple",
      "tool_name": "calibrate_model",
      "parameters": {
        "data_type": "owndata",
        "data_dir": "{{DATA_DIR}}",
        "exp_name": "quick_test_{{BASIN_ID}}",
        "model": {
          "name": "gr4j"
        },
        "basin_ids": ["{{BASIN_ID}}"],
        "periods": ["{{QUICK_START_DATE}}", "{{QUICK_END_DATE}}"],
        "calibrate_period": ["{{QUICK_START_DATE}}", "{{QUICK_CALIB_END_DATE}}"],
        "test_period": ["{{QUICK_TEST_START_DATE}}", "{{QUICK_END_DATE}}"],
        "warmup": 90,
        "algorithm": {
          "name": "SCE_UA",
          "random_seed": 1234,
          "rep": 50,
          "ngs": 10,
          "kstop": 3,
          "peps": 0.1,
          "pcento": 0.1
        }
      },
      "dependencies": ["quick_prepare"],
      "timeout": 300,
      "retry_count": 0
    }
  ],
  "variables": {
    "DATA_DIR": "/path/to/test/data",
    "BASIN_ID": "test_basin",
    "QUICK_START_DATE": "2018-01-01",
    "QUICK_END_DATE": "2020-12-31",
    "QUICK_CALIB_END_DATE": "2019-12-31",
    "QUICK_TEST_START_DATE": "2020-01-01"
  }
}
```

## 模板4：月尺度预测模板

```json
{
  "workflow_id": "monthly_prediction_{{timestamp}}",
  "name": "月尺度径流预测",
  "description": "使用GR2M模型进行月尺度长期径流预测",
  "mode": "sequential",
  "global_settings": {
    "error_handling": "stop_on_error",
    "timeout": 1800
  },
  "metadata": {
    "template_version": "1.0",
    "recommended_for": ["水资源规划", "长期预测", "月尺度分析"],
    "time_scale": "monthly"
  },
  "tasks": [
    {
      "task_id": "prepare_monthly",
      "name": "月尺度数据准备",
      "type": "simple",
      "tool_name": "prepare_data",
      "parameters": {
        "data_dir": "{{DATA_DIR}}",
        "target_data_scale": "M"
      },
      "timeout": 120,
      "retry_count": 1
    },
    {
      "task_id": "get_gr2m_params",
      "name": "获取GR2M参数",
      "type": "simple",
      "tool_name": "get_model_params",
      "parameters": {
        "model_name": "gr2m"
      },
      "dependencies": ["prepare_monthly"],
      "timeout": 60
    },
    {
      "task_id": "calibrate_monthly",
      "name": "月尺度模型率定",
      "type": "simple",
      "tool_name": "calibrate_model",
      "parameters": {
        "data_type": "owndata",
        "data_dir": "{{DATA_DIR}}",
        "exp_name": "gr2m_monthly_{{BASIN_ID}}",
        "model": {
          "name": "gr2m",
          "time_interval_hours": 720
        },
        "basin_ids": ["{{BASIN_ID}}"],
        "periods": ["{{MONTHLY_START}}", "{{MONTHLY_END}}"],
        "calibrate_period": ["{{MONTHLY_START}}", "{{MONTHLY_CALIB_END}}"],
        "test_period": ["{{MONTHLY_TEST_START}}", "{{MONTHLY_END}}"],
        "warmup": 12,
        "algorithm": {
          "name": "SCE_UA",
          "rep": 300,
          "ngs": 15
        }
      },
      "dependencies": ["prepare_monthly", "get_gr2m_params"],
      "timeout": 900
    },
    {
      "task_id": "evaluate_monthly",
      "name": "月尺度评估",
      "type": "simple",
      "tool_name": "evaluate_model",
      "parameters": {
        "result_dir": "{{RESULT_DIR}}/gr2m_monthly_{{BASIN_ID}}"
      },
      "dependencies": ["calibrate_monthly"],
      "timeout": 300
    }
  ],
  "variables": {
    "MONTHLY_START": "1990-01-01",
    "MONTHLY_END": "2020-12-31",
    "MONTHLY_CALIB_END": "2010-12-31",
    "MONTHLY_TEST_START": "2011-01-01"
  }
}
```

## 模板5：交叉验证稳定性测试

```json
{
  "workflow_id": "cross_validation_{{timestamp}}",
  "name": "交叉验证稳定性测试",
  "description": "使用5折交叉验证评估模型稳定性和泛化能力",
  "mode": "sequential",
  "global_settings": {
    "error_handling": "continue_on_error",
    "timeout": 10800
  },
  "metadata": {
    "template_version": "1.0",
    "recommended_for": ["模型稳定性评估", "论文发表", "方法验证"],
    "cross_validation_folds": 5
  },
  "tasks": [
    {
      "task_id": "prepare_cv_data",
      "name": "交叉验证数据准备",
      "type": "simple",
      "tool_name": "prepare_data",
      "parameters": {
        "data_dir": "{{DATA_DIR}}",
        "target_data_scale": "D"
      },
      "timeout": 180
    },
    {
      "task_id": "cv_calibrate",
      "name": "5折交叉验证率定",
      "type": "simple",
      "tool_name": "calibrate_model",
      "parameters": {
        "data_type": "owndata",
        "data_dir": "{{DATA_DIR}}",
        "exp_name": "cv_analysis_{{BASIN_ID}}",
        "model": {
          "name": "gr4j"
        },
        "basin_ids": ["{{BASIN_ID}}"],
        "periods": ["{{CV_START_DATE}}", "{{CV_END_DATE}}"],
        "warmup": 365,
        "cv_fold": 5,
        "algorithm": {
          "name": "SCE_UA",
          "random_seed": 42,
          "rep": 400,
          "ngs": 25
        }
      },
      "dependencies": ["prepare_cv_data"],
      "timeout": 9000
    },
    {
      "task_id": "cv_evaluate",
      "name": "交叉验证评估",
      "type": "simple",
      "tool_name": "evaluate_model",
      "parameters": {
        "result_dir": "{{RESULT_DIR}}/cv_analysis_{{BASIN_ID}}",
        "cv_fold": 5
      },
      "dependencies": ["cv_calibrate"],
      "timeout": 600
    }
  ]
}
```

## 模板使用指南

### 1. 变量替换
所有模板中的 `{{VARIABLE_NAME}}` 需要替换为实际值：

```python
# Python示例
template = template.replace("{{DATA_DIR}}", "/actual/path/to/data")
template = template.replace("{{BASIN_ID}}", "basin_12345")
template = template.replace("{{TIMESTAMP}}", "20241201_143022")
```

### 2. 时间段配置指导

**日尺度标准配置**:
- 总时间段: 15-20年
- 率定期: 总时间的70-75%
- 验证期: 总时间的25-30%
- 预热期: 365天

**月尺度标准配置**:
- 总时间段: 20-30年
- 率定期: 总时间的70-75%
- 验证期: 总时间的25-30%
- 预热期: 12个月

### 3. 算法参数调优指导

**开发阶段** (快速测试):
```json
{
  "rep": 50-100,
  "ngs": 10-15,
  "kstop": 3-5
}
```

**研究阶段** (标准精度):
```json
{
  "rep": 300-500,
  "ngs": 20-30,
  "kstop": 8-12
}
```

**生产阶段** (高精度):
```json
{
  "rep": 800-1000,
  "ngs": 40-50,
  "kstop": 15-20
}
```

### 4. 资源需求估算

| 模板类型 | 内存需求 | 时间需求 | CPU核数 |
|----------|----------|----------|---------|
| 快速原型 | 2GB | 5-15分钟 | 1-2 |
| 标准率定 | 4GB | 20-40分钟 | 2-4 |
| 多模型比较 | 6GB | 60-120分钟 | 4-8 |
| 交叉验证 | 8GB | 180-300分钟 | 4-8 |

### 5. 自定义修改建议

**修改流域数量**:
```json
"basin_ids": ["basin_001", "basin_002", "basin_003"]
```

**修改目标函数**:
```json
"loss": {
  "obj_func": "RMSE"  // 或 "KGE", "NSE"
}
```

**修改并行度**:
```json
"global_settings": {
  "max_parallel_tasks": 4  // 根据CPU核数调整
}
```