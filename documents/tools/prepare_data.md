# 数据准备工具示例代码

## 工具名称
prepare_data - 水文数据准备和预处理工具

## 功能描述
处理和验证水文时间序列数据，将CSV/TXT格式的原始数据转换为模型可用的netCDF格式。

## 核心实现代码

```python
"""
数据准备工具核心实现
"""
import os
import sys
from pathlib import Path
from typing import Dict, Any
import logging

from hydromodel.datasets.data_preprocess import process_and_save_data_as_nc

class PrepareDataTool:
    """数据准备工具"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def execute(self, parameters: Dict[str, Any]):
        """
        执行数据准备

        Args:
            parameters: 包含以下字段
                - data_dir: 数据目录路径
                - target_data_scale: 时间尺度 ('D'日, 'M'月, 'Y'年)

        Returns:
            执行结果字典
        """
        data_dir = parameters.get("data_dir")
        target_data_scale = parameters.get("target_data_scale", "D")

        # 检查数据目录
        if not os.path.exists(data_dir):
            return {"success": False, "error": f"数据目录不存在: {data_dir}"}

        # 处理数据
        success = process_and_save_data_as_nc(
            folder_path=data_dir,
            target_data_scale=target_data_scale,
            save_folder=data_dir
        )

        if success:
            # 检查生成的nc文件
            data_path = Path(data_dir)
            nc_files = list(data_path.glob("*.nc"))

            return {
                "success": True,
                "data_dir": data_dir,
                "processed_files": [f.name for f in nc_files],
                "file_count": len(nc_files),
                "target_data_scale": target_data_scale
            }
        else:
            return {"success": False, "error": "数据处理失败"}
```

## 使用示例

### 示例1: 基本用法
```python
# 准备日尺度数据
result = prepare_data_tool.execute({
    "data_dir": "data/camels_11532500",
    "target_data_scale": "D"
})

if result["success"]:
    print(f"成功处理 {result['file_count']} 个文件")
    print(f"输出文件: {result['processed_files']}")
```

### 示例2: 月尺度数据
```python
# 准备月尺度数据
result = prepare_data_tool.execute({
    "data_dir": "data/monthly_basin",
    "target_data_scale": "M"
})
```

## 输入数据格式要求

### CSV文件格式
水文数据CSV文件应包含以下列：
- date: 日期列 (格式: YYYY-MM-DD)
- prcp: 降雨量 (mm)
- et: 蒸发量 (mm)
- flow: 径流量 (mm或m³/s)

示例数据：
```csv
date,prcp,et,flow
2000-01-01,5.2,2.3,10.5
2000-01-02,0.0,2.1,9.8
2000-01-03,12.5,2.4,15.2
```

## 输出文件说明

生成的netCDF文件包含：
- time: 时间维度
- prcp: 降雨量变量
- tmean或pet: 蒸发量变量
- streamflow: 径流量变量

## 常见问题

### 1. 数据目录不存在
确保提供的路径是绝对路径或正确的相对路径

### 2. 缺少必要文件
检查数据目录是否包含CSV或TXT格式的数据文件

### 3. 数据格式错误
确保CSV文件包含必需的列（date, prcp, et, flow）

## 参数说明

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| data_dir | string | 是 | - | 数据目录路径 |
| target_data_scale | string | 否 | "D" | 时间尺度: D(日), M(月), Y(年) |

## 返回值说明

成功时返回：
```python
{
    "success": True,
    "data_dir": "处理的数据目录",
    "processed_files": ["文件列表"],
    "file_count": 文件数量,
    "target_data_scale": "时间尺度"
}
```

失败时返回：
```python
{
    "success": False,
    "error": "错误信息"
}
```
