# hydrodatasource Adapter — 自定义数据集操作

本适配器处理 `data_source="selfmade"` 或 `"custom"` 的自定义数据集，通过 `hydrodatasource.reader.data_source.SelfMadeHydroDataset` 读取数据。

## 支持的操作

| 操作 | 工具函数 | 说明 |
|------|----------|------|
| list_basins | `list_basins(data_path, dataset_name)` | 列出数据集中的所有流域 ID |
| read_data | `read_dataset(data_path, dataset_name, mode)` | 读取属性或时序数据 |
| convert_to_nc | `convert_dataset_to_nc(data_path, dataset_name)` | 将 CSV 原始数据转换为 NetCDF 缓存 |

## 典型使用场景

### 查询自定义数据集流域列表
```python
list_basins(
    data_path="/path/to/my_dataset",
    dataset_name="my_dataset",
    time_unit="1D"
)
```
返回：`{"success": True, "basin_ids": ["01010000", ...], "count": 42}`

### 转换 NC 缓存（首次使用前必须执行）
```python
convert_dataset_to_nc(
    data_path="/path/to/my_dataset",
    dataset_name="my_dataset",
    time_unit="1D"
)
```

### 读取属性数据
```python
read_dataset(
    data_path="/path/to/my_dataset",
    dataset_name="my_dataset",
    mode="attributes",          # 或 "timeseries"
    basin_ids=["01010000"]      # None = 所有流域
)
```

## 数据目录结构要求
```
my_dataset/
├── attributes/           # CSV 属性文件
│   └── my_dataset.csv
└── timeseries/           # 时序 CSV 文件（按流域 ID 命名）
    ├── 01010000.csv
    └── ...
```

## 注意事项
- `data_source` 必须为 `"selfmade"` 或 `"custom"` 才能路由到本适配器
- 建议在率定前先运行 `convert_dataset_to_nc` 创建 NetCDF 缓存以提升读取速度
- `time_unit` 默认 `"1D"`（日尺度）
