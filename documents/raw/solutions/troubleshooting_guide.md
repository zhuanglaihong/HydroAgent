# 水文建模工具故障排除指南

## 概述
本指南提供了使用HydroAgent水文建模工具时可能遇到的常见问题、错误诊断方法和解决方案。按照错误类型分类，提供系统性的故障排除流程。

## 错误分类和诊断流程

### 1. 数据相关错误

#### 1.1 数据文件找不到
**错误信息**: `FileNotFoundError: [Errno 2] No such file or directory`

**可能原因**:
- 数据目录路径不正确
- 文件名不匹配预期格式
- 权限不足

**诊断步骤**:
```bash
# 检查目录是否存在
ls -la /path/to/data/directory

# 检查文件权限
ls -la /path/to/data/directory/basin_*.csv

# 检查文件格式
head -5 /path/to/data/directory/basin_*.csv
```

**解决方案**:
1. 确认使用绝对路径
2. 检查文件名格式：`basin_{basin_id}.csv`
3. 确保文件可读权限
4. 验证CSV文件包含必需列：date, prcp, pet, flow

#### 1.2 数据格式错误
**错误信息**: `KeyError: 'prcp'` 或 `ValueError: time data does not match format`

**诊断检查清单**:
```python
# 检查CSV文件头部
import pandas as pd
df = pd.read_csv('basin_12345.csv')
print(df.columns.tolist())  # 应包含: ['date', 'prcp', 'pet', 'flow']
print(df.head())
print(df.dtypes)
```

**标准CSV格式要求**:
```csv
date,prcp,pet,flow,et
2000-01-01,4.26,1.89,12.5,1.2
2000-01-02,0.0,2.11,11.8,1.8
```

**解决方案**:
1. 确保列名准确：`date`, `prcp`, `pet`, `flow`
2. 日期格式使用ISO标准：`YYYY-MM-DD`
3. 数值列不包含非数字字符
4. 检查编码格式(推荐UTF-8)

#### 1.3 数据质量问题
**错误信息**: 工具执行成功但结果质量差(NSE < 0.3)

**诊断方法**:
```python
# 数据质量检查
import pandas as pd
import numpy as np

df = pd.read_csv('basin_12345.csv')
print(f"数据长度: {len(df)}")
print(f"降水缺失率: {df['prcp'].isna().sum() / len(df) * 100:.2f}%")
print(f"流量缺失率: {df['flow'].isna().sum() / len(df) * 100:.2f}%")
print(f"降水极值: {df['prcp'].min():.2f} - {df['prcp'].max():.2f}")
print(f"流量极值: {df['flow'].min():.2f} - {df['flow'].max():.2f}")
```

**质量控制标准**:
- 缺失数据 < 10%
- 降水量非负值
- 流量非负值
- 数据时间序列连续

### 2. 模型率定错误

#### 2.1 优化算法不收敛
**错误信息**: 率定完成但性能很差，或算法提前停止

**诊断参数检查**:
```json
{
  "algorithm": {
    "rep": "是否太小? 建议 > 300",
    "kstop": "是否太严格? 建议5-15",
    "peps": "是否太严格? 建议0.01-0.05",
    "pcento": "是否太严格? 建议0.01-0.05"
  }
}
```

**解决方案**:
1. **增加迭代次数**: `rep: 500-1000`
2. **放宽收敛条件**: `peps: 0.05, pcento: 0.05`
3. **调整群体大小**: `ngs: 20-50`
4. **检查参数范围**: 确保物理合理性

#### 2.2 内存不足错误
**错误信息**: `MemoryError` 或系统响应缓慢

**内存需求估算**:
- 小型数据集(< 10年): 2GB RAM
- 中型数据集(10-20年): 4GB RAM
- 大型数据集(> 20年): 8GB+ RAM

**解决方案**:
1. **减少数据量**: 缩短时间序列长度
2. **降低算法参数**: 减小`rep`和`ngs`值
3. **分批处理**: 将大任务分解为小任务
4. **增加系统内存**: 硬件升级

#### 2.3 参数值异常
**错误信息**: 参数超出合理物理范围

**GR4J参数合理范围**:
```
X1 (土壤蓄水容量): 10-3000 mm
X2 (地下水交换系数): -10-10 mm/day
X3 (最大地下水蓄水容量): 10-1000 mm
X4 (单位线时间参数): 0.5-10 days
```

**解决方案**:
1. 检查参数范围配置文件
2. 增加率定迭代次数
3. 使用多个随机种子测试稳定性
4. 检查数据质量和预处理过程

### 3. 配置和路径错误

#### 3.1 路径配置错误
**错误信息**: 各种路径相关的FileNotFoundError

**路径配置最佳实践**:
```json
{
  "正确": "/absolute/path/to/data",
  "错误": "./relative/path/to/data",
  "错误": "relative/path/to/data",
  "Windows正确": "C:/Users/data/basin",
  "Windows错误": "C:\\Users\\data\\basin"
}
```

**路径验证方法**:
```python
import os
from pathlib import Path

data_dir = "/path/to/your/data"
print(f"路径存在: {os.path.exists(data_dir)}")
print(f"是目录: {os.path.isdir(data_dir)}")
print(f"可读: {os.access(data_dir, os.R_OK)}")

# 列出目录内容
if os.path.exists(data_dir):
    print("目录内容:", os.listdir(data_dir))
```

#### 3.2 权限错误
**错误信息**: `PermissionError: [Errno 13] Permission denied`

**解决方案**:
```bash
# Linux/Mac
chmod 755 /path/to/data/directory
chmod 644 /path/to/data/directory/*.csv

# 检查当前用户权限
ls -la /path/to/data/directory
```

### 4. 依赖和环境错误

#### 4.1 Python包依赖错误
**错误信息**: `ImportError` 或 `ModuleNotFoundError`

**必需依赖检查**:
```python
# 检查关键依赖
import sys
required_packages = ['numpy', 'pandas', 'xarray', 'netcdf4', 'scipy']

for package in required_packages:
    try:
        __import__(package)
        print(f"✓ {package}")
    except ImportError:
        print(f"✗ {package} - 需要安装")
```

**解决方案**:
```bash
# 更新依赖
uv sync
# 或
pip install -r requirements.txt
```

#### 4.2 环境配置错误
**错误信息**: 水文模型库导入失败

**环境检查**:
```python
# 检查hydromodel可用性
try:
    from hydromodel.models.model_config import MODEL_PARAM_DICT
    print("✓ hydromodel 可用")
    print(f"支持的模型: {list(MODEL_PARAM_DICT.keys())}")
except ImportError as e:
    print(f"✗ hydromodel 不可用: {e}")
```

### 5. 工作流执行错误

#### 5.1 任务超时
**错误信息**: `TimeoutError` 或任务被强制终止

**超时时间建议**:
```json
{
  "prepare_data": 180,      // 3分钟
  "get_model_params": 60,   // 1分钟
  "calibrate_model": 3600,  // 1小时
  "evaluate_model": 300     // 5分钟
}
```

**根据数据量调整**:
- 小数据集 (< 5年): 基础时间 × 0.5
- 中数据集 (5-15年): 基础时间 × 1.0
- 大数据集 (> 15年): 基础时间 × 2.0

#### 5.2 依赖关系错误
**错误信息**: 任务执行顺序错误或依赖不满足

**正确依赖设置**:
```json
{
  "task_1": {"dependencies": []},
  "task_2": {"dependencies": ["task_1"]},
  "task_3": {"dependencies": ["task_1", "task_2"]},
  "task_4": {"dependencies": ["task_3"]}
}
```

**验证方法**:
```python
# 检查工作流依赖图
def validate_dependencies(workflow):
    tasks = {task["task_id"]: task for task in workflow["tasks"]}
    for task in workflow["tasks"]:
        for dep in task.get("dependencies", []):
            if dep not in tasks:
                print(f"错误: {task['task_id']} 依赖不存在的任务 {dep}")
```

### 6. 性能和结果质量问题

#### 6.1 模型性能差
**症状**: NSE < 0.5, R² < 0.6

**诊断流程**:
1. **检查数据质量** (见1.3节)
2. **验证时间段划分**:
   - 率定期是否足够长(> 5年)
   - 验证期是否合理(> 2年)
   - 预热期是否充分(日尺度 ≥ 1年)

3. **检查模型适用性**:
   - 流域特征与模型假设匹配
   - 气候条件是否适合所选模型

**解决策略**:
```json
// 增加率定强度
{
  "algorithm": {
    "rep": 1000,
    "ngs": 50,
    "kstop": 15
  },
  "warmup": 730  // 增加预热期
}
```

#### 6.2 结果不稳定
**症状**: 重复运行结果差异很大

**稳定性测试**:
```json
// 使用不同随机种子测试
{
  "test_seeds": [1234, 5678, 9012, 3456, 7890],
  "algorithm": {
    "random_seed": "依次使用各个种子"
  }
}
```

**提高稳定性**:
1. 增加`rep`参数
2. 使用多次运行平均结果
3. 检查数据质量和预处理一致性

## 快速诊断检查清单

### 开始故障排除前的5分钟检查
- [ ] 文件路径是否为绝对路径
- [ ] CSV文件是否包含必需列名
- [ ] 数据目录是否可访问
- [ ] 时间段设置是否合理
- [ ] 内存和磁盘空间是否充足

### 数据质量快速验证
```bash
# 快速检查脚本
head -5 /path/to/basin_*.csv  # 检查格式
wc -l /path/to/basin_*.csv    # 检查数据量
grep -c "," /path/to/basin_*.csv  # 检查分隔符
```

### 性能基准对比
| 指标 | 可接受 | 良好 | 优秀 |
|------|--------|------|------|
| NSE训练期 | > 0.50 | > 0.65 | > 0.75 |
| NSE验证期 | > 0.40 | > 0.55 | > 0.65 |
| 训练验证差异 | < 0.20 | < 0.15 | < 0.10 |

## 高级故障排除

### 日志分析
```python
# 查看详细错误日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 在工作流中启用调试模式
{
  "global_settings": {
    "debug_mode": True,
    "log_level": "DEBUG"
  }
}
```

### 性能分析
```python
# 内存使用监控
import psutil
import os

def monitor_memory():
    process = psutil.Process(os.getpid())
    memory_mb = process.memory_info().rss / 1024 / 1024
    print(f"内存使用: {memory_mb:.2f} MB")
```

### 问题报告模板
当需要寻求帮助时，请包含以下信息：
1. 错误信息完整文本
2. 数据基本信息(时间范围、流域数量)
3. 使用的参数配置
4. 系统环境(OS、内存、Python版本)
5. 已尝试的解决方案