# 模型率定工具示例代码

## 工具名称
calibrate_model - 水文模型参数率定工具

## 功能描述
使用SCE-UA算法对水文模型（如GR4J、XAJ等）进行参数率定，找到最优参数组合。

## 核心实现代码

```python
"""
模型率定工具核心实现
"""
import os
import yaml
import numpy as np
from pathlib import Path
from typing import Dict, Any
from hydromodel.models.model_dict import MODEL_DICT
from hydromodel.datasets.data_preprocess import cross_val_split_tsdata, _get_pe_q_from_ts
from hydromodel.trainers.calibrate_sceua import calibrate_by_sceua

class CalibrateModelTool:
    """水文模型率定工具"""

    def execute(self, parameters: Dict[str, Any]):
        """
        执行模型率定

        Args:
            parameters: 包含以下字段
                - data_dir: 数据目录
                - result_dir: 结果保存目录
                - exp_name: 实验名称
                - basin_ids: 流域ID列表
                - model: 模型配置
                - periods: 整体时间段
                - calibrate_period: 率定时间段
                - test_period: 测试时间段
                - warmup: 预热期长度
                - algorithm: 优化算法配置
                - loss: 损失函数配置

        Returns:
            执行结果字典
        """
        # 提取参数
        data_type = parameters.get("data_type", "owndata")
        data_dir = parameters["data_dir"]
        result_dir = parameters.get("result_dir", "result")
        exp_name = parameters.get("exp_name", "exp_calibration")
        basin_ids = parameters["basin_ids"]

        model = parameters.get("model", {
            "name": "gr4j",
            "source_type": "sources",
            "source_book": "HF",
            "kernel_size": 15,
            "time_interval_hours": 24
        })

        periods = parameters.get("periods", ["2000-01-01", "2023-12-31"])
        calibrate_period = parameters.get("calibrate_period", ["2000-01-01", "2018-12-31"])
        test_period = parameters.get("test_period", ["2019-01-01", "2023-12-31"])
        warmup = parameters.get("warmup", 720)
        cv_fold = parameters.get("cv_fold", 1)

        algorithm = parameters.get("algorithm", {
            "name": "SCE_UA",
            "random_seed": 1234,
            "rep": 100,
            "ngs": 30,
            "kstop": 5,
            "peps": 0.05,
            "pcento": 0.05
        })

        loss = parameters.get("loss", {
            "type": "time_series",
            "obj_func": "RMSE",
            "events": None
        })

        # 设置保存路径
        result_path = Path(result_dir) / exp_name
        result_path.mkdir(parents=True, exist_ok=True)

        # 准备数据
        train_and_test_data = cross_val_split_tsdata(
            data_type, data_dir, cv_fold,
            calibrate_period, test_period, periods,
            warmup, basin_ids
        )

        # 执行率定
        if cv_fold <= 1:
            p_and_e, qobs = _get_pe_q_from_ts(train_and_test_data[0])
            calibrate_by_sceua(
                basin_ids,
                p_and_e.astype(np.float64),
                qobs.astype(np.float64),
                str(result_path / "sceua_gr_model"),
                warmup,
                model=model,
                algorithm=algorithm,
                loss=loss
            )
        else:
            for i in range(cv_fold):
                train_data, _ = train_and_test_data[i]
                p_and_e_cv, qobs_cv = _get_pe_q_from_ts(train_data)
                model_save_dir = str(result_path / f"sceua_gr_model_cv{i+1}")
                calibrate_by_sceua(
                    basin_ids, p_and_e_cv, qobs_cv,
                    model_save_dir, warmup,
                    model=model, algorithm=algorithm, loss=loss
                )

        # 保存配置
        config = {
            "data_type": data_type,
            "data_dir": data_dir,
            "result_dir": str(result_path),
            "exp_name": exp_name,
            "basin_ids": basin_ids,
            "model": model,
            "periods": periods,
            "calibrate_period": calibrate_period,
            "test_period": test_period,
            "warmup": warmup,
            "cv_fold": cv_fold,
            "algorithm": algorithm,
            "loss": loss
        }

        with open(result_path / "config.yaml", "w") as f:
            yaml.dump(config, f)

        return {
            "success": True,
            "result_dir": str(result_path),
            "exp_name": exp_name,
            "model_name": model["name"],
            "basin_count": len(basin_ids),
            "cv_fold": cv_fold
        }
```

## 使用示例

### 示例1: 基本GR4J模型率定
```python
result = calibrate_model_tool.execute({
    "data_dir": "data/camels_11532500",
    "result_dir": "result",
    "exp_name": "gr4j_calibration",
    "basin_ids": ["11532500"],
    "model": {
        "name": "gr4j",
        "source_type": "sources",
        "source_book": "HF"
    },
    "periods": ["2000-01-01", "2020-12-31"],
    "calibrate_period": ["2000-01-01", "2015-12-31"],
    "test_period": ["2016-01-01", "2020-12-31"],
    "warmup": 720,
    "algorithm": {
        "name": "SCE_UA",
        "rep": 100,
        "ngs": 30
    }
})
```

### 示例2: 交叉验证率定
```python
result = calibrate_model_tool.execute({
    "data_dir": "data/multiple_basins",
    "result_dir": "result",
    "exp_name": "cv_calibration",
    "basin_ids": ["basin1", "basin2", "basin3"],
    "cv_fold": 5,
    "model": {"name": "xaj"}
})
```

### 示例3: 自定义优化算法参数
```python
result = calibrate_model_tool.execute({
    "data_dir": "data/camels_11532500",
    "basin_ids": ["11532500"],
    "algorithm": {
        "name": "SCE_UA",
        "random_seed": 42,
        "rep": 200,      # 增加重复次数
        "ngs": 40,       # 增加复形数量
        "kstop": 10,     # 增加停止标准
        "peps": 0.01,    # 更严格的收敛标准
        "pcento": 0.01
    },
    "loss": {
        "type": "time_series",
        "obj_func": "NSE",  # 使用NSE作为目标函数
        "events": None
    }
})
```

## 参数说明

### 必需参数
| 参数 | 类型 | 说明 |
|------|------|------|
| data_dir | string | 数据目录路径 |
| basin_ids | list[string] | 流域ID列表 |

### 可选参数
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| result_dir | string | "result" | 结果保存目录 |
| exp_name | string | "exp_calibration" | 实验名称 |
| warmup | int | 720 | 预热期长度（天） |
| cv_fold | int | 1 | 交叉验证折数 |

### 模型配置 (model)
```python
{
    "name": "gr4j",              # 模型名称: gr4j, xaj, gr2m等
    "source_type": "sources",    # 数据源类型
    "source_book": "HF",         # 数据源书
    "kernel_size": 15,           # 卷积核大小
    "time_interval_hours": 24    # 时间间隔（小时）
}
```

### 算法配置 (algorithm)
```python
{
    "name": "SCE_UA",      # 优化算法名称
    "random_seed": 1234,   # 随机种子
    "rep": 100,            # 重复次数（影响收敛）
    "ngs": 30,             # 复形数量
    "kstop": 5,            # 停止标准
    "peps": 0.05,          # 参数收敛阈值
    "pcento": 0.05         # 目标函数收敛阈值
}
```

### 损失函数配置 (loss)
```python
{
    "type": "time_series",  # 损失类型
    "obj_func": "RMSE",     # 目标函数: RMSE, NSE, KGE等
    "events": None          # 事件选择（可选）
}
```

## 输出结果说明

### 成功返回
```python
{
    "success": True,
    "result_dir": "result/exp_calibration",
    "exp_name": "exp_calibration",
    "model_name": "gr4j",
    "basin_count": 1,
    "cv_fold": 1
}
```

### 生成的文件结构
```
result/exp_calibration/
├── config.yaml                 # 配置文件
├── param_range.yaml           # 参数范围
└── sceua_gr_model/            # 率定结果
    ├── best_params.txt        # 最优参数
    ├── best_simulation.npy    # 最优模拟结果
    └── calibration_log.txt    # 率定日志
```

## SCE-UA算法参数调优建议

### 快速测试配置（低精度）
```python
algorithm = {
    "rep": 50,
    "ngs": 15,
    "kstop": 3
}
```

### 标准配置（中等精度）
```python
algorithm = {
    "rep": 100,
    "ngs": 30,
    "kstop": 5
}
```

### 高精度配置（耗时较长）
```python
algorithm = {
    "rep": 200,
    "ngs": 40,
    "kstop": 10,
    "peps": 0.01,
    "pcento": 0.01
}
```

## 常见问题

### 1. 率定时间过长
- 减少rep和ngs参数
- 缩短率定时间段
- 减少basin数量

### 2. 参数不收敛
- 增加rep参数
- 调整kstop、peps、pcento参数
- 检查数据质量

### 3. 内存不足
- 减少cv_fold
- 分批处理流域
- 缩短时间序列长度

## 最佳实践

1. **数据准备**：确保数据已预处理为nc格式
2. **预热期设置**：建议至少365天（日模型）或12个月（月模型）
3. **时间段划分**：训练集和测试集比例通常为7:3
4. **算法参数**：根据计算资源和时间要求选择合适配置
5. **结果保存**：使用有意义的exp_name便于管理
