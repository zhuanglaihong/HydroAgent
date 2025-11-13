# 模型评估工具示例代码

## 工具名称
evaluate_model - 水文模型性能评估工具

## 功能描述
评估已率定的水文模型在训练期和测试期的性能，计算多种评估指标（NSE、R2、RMSE等）。

## 核心实现代码

```python
"""
模型评估工具核心实现
"""
import os
import yaml
import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional
from hydromodel.trainers.evaluate import Evaluator, read_yaml_config
from hydromodel.datasets.data_preprocess import cross_val_split_tsdata

class EvaluateModelTool:
    """水文模型评估工具"""

    def execute(self, parameters: Dict[str, Any]):
        """
        执行模型评估

        Args:
            parameters: 包含以下字段
                - result_dir: 率定结果目录
                - exp_name: 实验名称（可选）
                - cv_fold: 交叉验证折数（可选）

        Returns:
            执行结果字典
        """
        result_dir = parameters["result_dir"]
        exp_name = parameters.get("exp_name", "exp_evaluation")

        # 读取配置文件
        config_path = os.path.join(result_dir, "config.yaml")
        cali_config = read_yaml_config(config_path)

        # 从配置获取参数
        data_type = cali_config.get("data_type")
        data_dir = cali_config.get("data_dir")
        cv_fold = parameters.get("cv_fold") or cali_config.get("cv_fold", 1)
        train_period = cali_config.get("calibrate_period")
        test_period = cali_config.get("test_period")
        periods = cali_config.get("periods") or cali_config.get("period")
        warmup = cali_config.get("warmup", 720)
        basin_ids = cali_config.get("basin_ids") or cali_config.get("basin_id")

        where_save = Path(result_dir)

        # 准备评估数据
        train_and_test_data = cross_val_split_tsdata(
            data_type, data_dir, cv_fold,
            train_period, test_period, periods,
            warmup, basin_ids
        )

        # 执行评估
        if cv_fold <= 1:
            cali_dir = where_save
            param_dir = os.path.join(cali_dir, "sceua_gr_model")
            train_data = train_and_test_data[0]
            test_data = train_and_test_data[1]
            self._evaluate(cali_dir, param_dir, train_data, test_data)
        else:
            for i in range(cv_fold):
                cali_dir = where_save
                fold_dir = os.path.join(cali_dir, f"sceua_gr_model_cv{i+1}")
                train_data = train_and_test_data[i][0]
                test_data = train_and_test_data[i][1]
                self._evaluate(cali_dir, fold_dir, train_data, test_data)

        # 读取评估指标
        evaluation_results = {}

        if cv_fold <= 1:
            param_dir = os.path.join(where_save, "sceua_gr_model")
            train_metrics = self._read_metrics(
                os.path.join(param_dir, "train", "basins_metrics.csv")
            )
            test_metrics = self._read_metrics(
                os.path.join(param_dir, "test", "basins_metrics.csv")
            )

            evaluation_results = {
                "train_metrics": train_metrics,
                "test_metrics": test_metrics,
                "train_R2": train_metrics.get("R2"),
                "test_R2": test_metrics.get("R2"),
            }
        else:
            fold_results = []
            for i in range(cv_fold):
                fold_dir = os.path.join(where_save, f"sceua_gr_model_cv{i+1}")
                train_metrics = self._read_metrics(
                    os.path.join(fold_dir, "train", "basins_metrics.csv")
                )
                test_metrics = self._read_metrics(
                    os.path.join(fold_dir, "test", "basins_metrics.csv")
                )
                fold_results.append({
                    "fold": i + 1,
                    "train_metrics": train_metrics,
                    "test_metrics": test_metrics
                })

            evaluation_results["cv_results"] = fold_results
            evaluation_results["cv_fold"] = cv_fold

        return {
            "success": True,
            "result_dir": str(where_save),
            "exp_name": exp_name,
            "cv_fold": cv_fold,
            "evaluation_results": evaluation_results
        }

    def _evaluate(self, cali_dir: str, param_dir: str, train_data, test_data):
        """执行单次评估"""
        eval_train_dir = os.path.join(param_dir, "train")
        eval_test_dir = os.path.join(param_dir, "test")

        train_eval = Evaluator(cali_dir, param_dir, eval_train_dir)
        test_eval = Evaluator(cali_dir, param_dir, eval_test_dir)

        qsim_train, qobs_train, etsim_train = train_eval.predict(train_data)
        qsim_test, qobs_test, etsim_test = test_eval.predict(test_data)

        train_eval.save_results(train_data, qsim_train, qobs_train, etsim_train)
        test_eval.save_results(test_data, qsim_test, qobs_test, etsim_test)

    def _read_metrics(self, csv_path: str) -> Dict[str, float]:
        """读取所有评估指标"""
        try:
            df = pd.read_csv(csv_path)
            metrics = {}
            if not df.empty:
                for col in df.columns:
                    if col != "basin_id":
                        metrics[col] = float(df.loc[0, col])
            return metrics
        except Exception as e:
            return {}
```

## 使用示例

### 示例1: 评估单个率定结果
```python
result = evaluate_model_tool.execute({
    "result_dir": "result/gr4j_calibration"
})

if result["success"]:
    eval_results = result["evaluation_results"]
    print(f"训练期NSE: {eval_results['train_metrics']['NSE']:.4f}")
    print(f"测试期NSE: {eval_results['test_metrics']['NSE']:.4f}")
    print(f"训练期R2: {eval_results['train_R2']:.4f}")
    print(f"测试期R2: {eval_results['test_R2']:.4f}")
```

### 示例2: 评估交叉验证结果
```python
result = evaluate_model_tool.execute({
    "result_dir": "result/cv_calibration",
    "cv_fold": 5
})

if result["success"]:
    cv_results = result["evaluation_results"]["cv_results"]
    for fold_result in cv_results:
        fold = fold_result["fold"]
        test_nse = fold_result["test_metrics"]["NSE"]
        print(f"Fold {fold} 测试期NSE: {test_nse:.4f}")
```

### 示例3: 获取详细指标
```python
result = evaluate_model_tool.execute({
    "result_dir": "result/exp_calibration"
})

train_metrics = result["evaluation_results"]["train_metrics"]
test_metrics = result["evaluation_results"]["test_metrics"]

print("训练期指标:")
for metric, value in train_metrics.items():
    print(f"  {metric}: {value:.4f}")

print("\n测试期指标:")
for metric, value in test_metrics.items():
    print(f"  {metric}: {value:.4f}")
```

## 参数说明

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| result_dir | string | 是 | - | 率定结果目录，应包含config.yaml |
| exp_name | string | 否 | "exp_evaluation" | 实验名称 |
| cv_fold | int | 否 | 从config读取 | 交叉验证折数 |

## 返回值说明

### 单折评估结果
```python
{
    "success": True,
    "result_dir": "result/exp_calibration",
    "exp_name": "exp_evaluation",
    "cv_fold": 1,
    "evaluation_results": {
        "train_metrics": {
            "NSE": 0.85,
            "R2": 0.87,
            "RMSE": 2.45,
            "KGE": 0.82,
            "Bias": 0.05
        },
        "test_metrics": {
            "NSE": 0.78,
            "R2": 0.80,
            "RMSE": 3.12,
            "KGE": 0.75,
            "Bias": -0.08
        },
        "train_R2": 0.87,
        "test_R2": 0.80
    }
}
```

### 交叉验证评估结果
```python
{
    "success": True,
    "result_dir": "result/cv_calibration",
    "exp_name": "exp_evaluation",
    "cv_fold": 5,
    "evaluation_results": {
        "cv_results": [
            {
                "fold": 1,
                "train_metrics": {...},
                "test_metrics": {...}
            },
            {
                "fold": 2,
                "train_metrics": {...},
                "test_metrics": {...}
            },
            ...
        ],
        "cv_fold": 5
    }
}
```

## 评估指标说明

### NSE (Nash-Sutcliffe Efficiency)
- 范围: (-∞, 1]
- 完美值: 1
- 可接受: > 0.5
- 良好: > 0.7
- 优秀: > 0.85

### R2 (决定系数)
- 范围: [0, 1]
- 完美值: 1
- 可接受: > 0.6
- 良好: > 0.75
- 优秀: > 0.9

### RMSE (均方根误差)
- 范围: [0, +∞)
- 完美值: 0
- 单位: 与观测值相同
- 越小越好

### KGE (Kling-Gupta Efficiency)
- 范围: (-∞, 1]
- 完美值: 1
- 可接受: > 0.5
- 良好: > 0.75

### Bias (偏差)
- 范围: (-∞, +∞)
- 完美值: 0
- 正值: 高估
- 负值: 低估

## 输出文件说明

评估完成后生成的文件结构：
```
result/exp_calibration/sceua_gr_model/
├── train/
│   ├── basins_metrics.csv      # 训练期评估指标
│   ├── flow_pred.npy          # 训练期模拟径流
│   └── flow_obs.npy           # 训练期观测径流
└── test/
    ├── basins_metrics.csv      # 测试期评估指标
    ├── flow_pred.npy          # 测试期模拟径流
    └── flow_obs.npy           # 测试期观测径流
```

## 常见问题

### 1. config.yaml不存在
确保提供的result_dir是率定结果目录，且包含配置文件

### 2. 评估指标异常（如NSE为负）
- 检查率定是否成功
- 检查数据质量
- 检查参数是否合理

### 3. 找不到模型参数文件
确保率定过程已完成并保存了参数文件

## 评估结果解读

### 良好的模型性能特征
1. NSE > 0.7
2. 训练期和测试期性能差异不大（< 0.15）
3. Bias接近0
4. R2 > 0.75

### 问题诊断
- 训练期好，测试期差：可能过拟合
- NSE很低：模型结构不合适或数据有问题
- Bias很大：系统性偏差，检查数据单位和质量
- RMSE很大：预测值与观测值偏差大

## 最佳实践

1. **评估时机**：在率定完成后立即评估
2. **多指标评估**：综合考虑NSE、R2、KGE等多个指标
3. **训练测试对比**：关注训练期和测试期性能差异
4. **可视化**：绘制模拟与观测对比图
5. **结果保存**：妥善保存评估结果用于后续分析
