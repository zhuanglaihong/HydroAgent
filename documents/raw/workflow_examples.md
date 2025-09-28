# HydroAgent 工作流示例库

本文档提供HydroAgent系统中各种工作流的详细示例和使用指南。所有示例均基于实际测试通过的工作流配置。

## 数据路径配置

在使用工作流前，请根据`definitions.py`中的路径定义配置数据路径：

```python
# 主要路径配置
PROJECT_DIR = "D:\\MCP\\HydroAgent"          # 项目根目录
DATASET_DIR = "D:\\MCP\\HydroAgent\\data"    # 数据集目录
RESULT_DIR = "D:\\MCP\\HydroAgent\\result"   # 结果输出目录
```

## React模式自动优化工作流

### 基本配置
```json
{
  "workflow_id": "react_hydro_optimization",
  "name": "React模式水文模型自动优化工作流",
  "execution_mode": "react",
  "targets": [{
    "type": "performance_goal",
    "metric": "nse",
    "threshold": 0.7,
    "comparison": ">=",
    "max_iterations": 5
  }]
}
```

### 任务配置

#### 1. 数据准备任务（条件执行）
```json
{
  "task_id": "task_prepare",
  "name": "准备水文数据",
  "tool_name": "prepare_data",
  "type": "simple",
  "parameters": {
    "data_dir": "{DATASET_DIR}/camels_11532500",
    "target_data_scale": "D"
  },
  "conditions": {
    "execute_iterations": "first_only"
  }
}
```

**特性**：
- `execute_iterations: "first_only"` - 只在第一次迭代执行
- 支持的条件值：`"all"`, `"first_only"`, `"skip_first"`, `[1,3,5]`

#### 2. 模型率定任务
```json
{
  "task_id": "task_calibrate",
  "name": "率定GR4J模型",
  "tool_name": "calibrate_model",
  "type": "simple",
  "parameters": {
    "data_type": "owndata",
    "data_dir": "{DATASET_DIR}/camels_11532500",
    "result_dir": "{RESULT_DIR}",
    "model": {
      "name": "gr4j",
      "source_type": "sources",
      "source_book": "HF"
    },
    "algorithm": {
      "name": "SCE_UA",
      "rep": 30,
      "ngs": 10
    }
  },
  "dependencies": ["task_prepare"]
}
```

#### 3. 模型评估任务
```json
{
  "task_id": "task_evaluate",
  "name": "评估模型性能",
  "tool_name": "evaluate_model",
  "type": "simple",
  "parameters": {
    "result_dir": "{RESULT_DIR}/react_optimization"
  },
  "dependencies": ["task_calibrate"]
}
```

### React配置
```json
{
  "react_config": {
    "enable_feedback": true,
    "max_iterations": 5,
    "timeout_minutes": 5,
    "target_metric": "nse",
    "target_threshold": 0.7,
    "iteration_strategy": "parameter_adjustment",
    "feedback_source": "task_evaluate",
    "adjustment_tasks": ["task_calibrate"],
    "monitoring_tasks": ["task_evaluate"]
  }
}
```

## 顺序执行工作流

### 简单顺序工作流
```json
{
  "workflow_id": "sequential_hydro_basic",
  "name": "顺序执行水文建模工作流",
  "execution_mode": "sequential",
  "tasks": [
    {
      "task_id": "prepare",
      "tool_name": "prepare_data",
      "parameters": {
        "data_dir": "{DATASET_DIR}/camels_11532500"
      }
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

## 支持的水文模型

### GR系列模型
- **GR1Y**: 年尺度雨径流模型
- **GR2M**: 月尺度雨径流模型
- **GR4J**: 日尺度雨径流模型（推荐）
- **GR5J**: 增强版日尺度模型
- **GR6J**: 高级日尺度模型

### XAJ模型
```json
{
  "model": {
    "name": "xaj",
    "source_type": "sources",
    "source_book": "HF"
  }
}
```

## 算法配置

### SCE-UA算法（推荐）
```json
{
  "algorithm": {
    "name": "SCE_UA",
    "random_seed": 1234,
    "rep": 30,        // 重复次数
    "ngs": 10,        // 复合体数量
    "kstop": 3,       // 停止条件
    "peps": 0.1,      // 收敛精度
    "pcento": 0.1     // 百分比收敛
  }
}
```

### GA算法
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

## 性能指标配置

### 支持的评估指标
- **NSE**: Nash-Sutcliffe效率系数（推荐）
- **R2**: 决定系数
- **RMSE**: 均方根误差
- **KGE**: Kling-Gupta效率
- **Bias**: 偏差
- **Corr**: 相关系数

### 损失函数配置
```json
{
  "loss": {
    "type": "time_series",
    "obj_func": "RMSE",    // 或 "NSE", "KGE"
    "events": null
  }
}
```

## 数据格式要求

### 输入数据结构
```
data_dir/
├── basin_[id].csv          # 主要时间序列数据
├── basin_[id]_monthly.csv  # 月尺度数据（可选）
├── basin_[id]_yearly.csv   # 年尺度数据（可选）
└── basin_attributes.csv    # 流域属性数据
```

### CSV文件格式
```csv
date,prcp,tmean,pet,streamflow
2000-01-01,2.5,5.2,1.8,10.5
2000-01-02,0.0,6.1,2.1,9.8
```

## 路径变量替换

工作流支持以下路径变量自动替换：
- `{PROJECT_DIR}` → definitions.py中的PROJECT_DIR
- `{DATASET_DIR}` → definitions.py中的DATASET_DIR
- `{RESULT_DIR}` → definitions.py中的RESULT_DIR

## 执行模式说明

### Sequential模式
- 按依赖关系顺序执行任务
- 适合标准的建模流程
- 不支持迭代优化

### React模式
- 目标导向的迭代执行
- 自动评估目标达成情况
- 支持参数调整和重新率定
- 智能跳过不必要的重复任务

## 最佳实践

1. **数据准备优化**: 使用条件执行避免重复数据处理
2. **路径配置**: 使用路径变量确保可移植性
3. **目标设置**: NSE >= 0.7 是水文模型的合理目标
4. **算法选择**: SCE-UA算法在大多数情况下表现良好
5. **超时控制**: 设置合理的任务和工作流超时时间

## 故障排除

### 常见问题
1. **路径不存在**: 检查definitions.py中的路径配置
2. **数据格式错误**: 确保CSV文件包含必需的列
3. **模型收敛失败**: 调整算法参数或增加迭代次数
4. **内存不足**: 减少算法的rep和ngs参数值

### 调试建议
1. 使用`--debug`参数运行工作流
2. 查看详细的日志文件
3. 验证输入数据的完整性
4. 检查模型参数范围配置