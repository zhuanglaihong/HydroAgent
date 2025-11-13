# 水文建模代码生成模式

## 代码生成基本原则

### 1. 标准代码结构
```python
"""
模块/脚本描述
"""
import 必要的库
from 特定模块 import 特定函数

# 常量定义
CONSTANT_NAME = value

def main_function(parameters):
    """
    主函数文档字符串

    Args:
        param1: 参数1描述
        param2: 参数2描述

    Returns:
        返回值描述
    """
    try:
        # 1. 参数验证
        validate_parameters(parameters)

        # 2. 数据加载
        data = load_data(parameters['data_path'])

        # 3. 数据处理
        processed_data = process_data(data)

        # 4. 执行核心逻辑
        results = execute_logic(processed_data)

        # 5. 保存结果
        save_results(results, parameters['output_path'])

        return {
            'success': True,
            'results': results
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

if __name__ == '__main__':
    # 使用示例
    pass
```

## 常见任务代码模式

### 模式1: 数据统计分析
```python
def statistical_analysis_template(data_path, output_path):
    """
    数据统计分析模板

    适用场景：计算均值、中位数、标准差等统计指标

    Args:
        data_path: 输入数据路径
        output_path: 输出结果路径
    """
    import pandas as pd
    import numpy as np

    # 读取数据
    df = pd.read_csv(data_path, parse_dates=['date'])
    df.set_index('date', inplace=True)

    # 计算统计指标
    statistics = {}
    for column in df.columns:
        statistics[column] = {
            'mean': df[column].mean(),
            'median': df[column].median(),
            'std': df[column].std(),
            'min': df[column].min(),
            'max': df[column].max(),
            'q25': df[column].quantile(0.25),
            'q75': df[column].quantile(0.75)
        }

    # 保存结果
    result_df = pd.DataFrame(statistics).T
    result_df.to_csv(output_path)

    return statistics
```

### 模式2: 时间序列特征提取
```python
def temporal_feature_extraction_template(data_path, output_path):
    """
    时间序列特征提取模板

    适用场景：提取月度、季度、年度特征

    Args:
        data_path: 输入数据路径
        output_path: 输出结果路径
    """
    import pandas as pd

    # 读取数据
    df = pd.read_csv(data_path, parse_dates=['date'])
    df.set_index('date', inplace=True)

    # 添加时间特征
    df['year'] = df.index.year
    df['month'] = df.index.month
    df['day_of_year'] = df.index.dayofyear

    # 计算月平均
    monthly_mean = df.groupby(['year', 'month']).mean()

    # 计算年度总和/平均
    annual_stats = df.groupby('year').agg({
        'prcp': 'sum',  # 年降雨总量
        'flow': 'mean'  # 年平均径流
    })

    # 保存结果
    monthly_mean.to_csv(f"{output_path}_monthly.csv")
    annual_stats.to_csv(f"{output_path}_annual.csv")

    return {
        'monthly': monthly_mean.to_dict(),
        'annual': annual_stats.to_dict()
    }
```

### 模式3: 数据可视化
```python
def visualization_template(data_path, output_path):
    """
    数据可视化模板

    适用场景：生成时间序列图、柱状图、散点图

    Args:
        data_path: 输入数据路径
        output_path: 输出图片路径
    """
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    # 读取数据
    df = pd.read_csv(data_path, parse_dates=['date'])
    df.set_index('date', inplace=True)

    # 创建图形
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    # 子图1: 降雨
    axes[0].bar(df.index, df['prcp'], color='skyblue', width=1)
    axes[0].set_ylabel('Precipitation (mm/day)', fontsize=12)
    axes[0].invert_yaxis()  # 降雨图倒置
    axes[0].grid(True, alpha=0.3)
    axes[0].set_title('Precipitation', fontsize=14)

    # 子图2: 径流
    axes[1].plot(df.index, df['flow'], color='steelblue', linewidth=1)
    axes[1].set_ylabel('Streamflow (mm/day)', fontsize=12)
    axes[1].set_xlabel('Date', fontsize=12)
    axes[1].grid(True, alpha=0.3)
    axes[1].set_title('Streamflow', fontsize=14)

    # 格式化x轴日期
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    axes[1].xaxis.set_major_locator(mdates.YearLocator())

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()

    return output_path
```

### 模式4: 事件识别
```python
def event_identification_template(data_path, threshold, output_path):
    """
    事件识别模板

    适用场景：识别极端降雨、洪水等事件

    Args:
        data_path: 输入数据路径
        threshold: 事件阈值
        output_path: 输出结果路径
    """
    import pandas as pd
    import json

    # 读取数据
    df = pd.read_csv(data_path, parse_dates=['date'])
    df.set_index('date', inplace=True)

    # 识别事件（以降雨为例）
    events = df[df['prcp'] > threshold].copy()
    events['event_id'] = range(1, len(events) + 1)

    # 计算事件统计
    event_stats = {
        'total_events': len(events),
        'max_intensity': float(events['prcp'].max()),
        'mean_intensity': float(events['prcp'].mean()),
        'events_per_year': len(events) / (
            (df.index.max() - df.index.min()).days / 365.25
        ),
        'event_dates': events.index.strftime('%Y-%m-%d').tolist(),
        'event_intensities': events['prcp'].tolist()
    }

    # 保存详细事件列表
    events.to_csv(f"{output_path}_events.csv")

    # 保存统计信息
    with open(f"{output_path}_stats.json", 'w') as f:
        json.dump(event_stats, f, indent=2)

    return event_stats
```

### 模式5: 相关性分析
```python
def correlation_analysis_template(data_path, var1, var2, max_lag, output_path):
    """
    相关性分析模板

    适用场景：分析两个变量之间的相关关系和滞后效应

    Args:
        data_path: 输入数据路径
        var1: 变量1名称
        var2: 变量2名称
        max_lag: 最大滞后期
        output_path: 输出结果路径
    """
    import pandas as pd
    import numpy as np
    import json

    # 读取数据
    df = pd.read_csv(data_path, parse_dates=['date'])
    df.set_index('date', inplace=True)

    # 计算不同滞后的相关系数
    correlations = {}
    for lag in range(max_lag + 1):
        if lag == 0:
            corr = df[var1].corr(df[var2])
        else:
            corr = df[var1].shift(lag).corr(df[var2])
        correlations[f'lag_{lag}'] = float(corr)

    # 找到最优滞后
    best_lag = max(correlations, key=correlations.get)
    best_corr = correlations[best_lag]

    results = {
        'variable1': var1,
        'variable2': var2,
        'max_lag_tested': max_lag,
        'correlations': correlations,
        'best_lag': int(best_lag.split('_')[1]),
        'best_correlation': best_corr,
        'interpretation': (
            'Strong' if abs(best_corr) > 0.7 else
            'Moderate' if abs(best_corr) > 0.4 else
            'Weak'
        )
    }

    # 保存结果
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)

    return results
```

## 复杂任务组合模式

### 组合模式1: 完整数据分析流程
```python
def comprehensive_analysis_pipeline(data_path, output_dir):
    """
    完整数据分析流程

    包含：数据加载 -> 质量检查 -> 统计分析 -> 事件识别 -> 可视化

    Args:
        data_path: 输入数据路径
        output_dir: 输出目录
    """
    import os
    import pandas as pd
    import json
    os.makedirs(output_dir, exist_ok=True)

    # 步骤1: 加载数据
    df = pd.read_csv(data_path, parse_dates=['date'])
    df.set_index('date', inplace=True)

    # 步骤2: 数据质量检查
    quality_report = {
        'total_records': len(df),
        'missing_values': df.isnull().sum().to_dict(),
        'date_range': {
            'start': df.index.min().strftime('%Y-%m-%d'),
            'end': df.index.max().strftime('%Y-%m-%d')
        }
    }

    # 步骤3: 统计分析
    statistics = {}
    for col in df.columns:
        statistics[col] = {
            'mean': float(df[col].mean()),
            'std': float(df[col].std()),
            'min': float(df[col].min()),
            'max': float(df[col].max())
        }

    # 步骤4: 事件识别
    extreme_rainfall = df[df['prcp'] > 30.0]
    events = {
        'count': len(extreme_rainfall),
        'dates': extreme_rainfall.index.strftime('%Y-%m-%d').tolist(),
        'intensities': extreme_rainfall['prcp'].tolist()
    }

    # 步骤5: 可视化
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(df.index, df['flow'], label='Streamflow')
    ax.set_xlabel('Date')
    ax.set_ylabel('Streamflow (mm/day)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    plot_path = os.path.join(output_dir, 'streamflow_timeseries.png')
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    plt.close()

    # 整合结果
    results = {
        'quality_report': quality_report,
        'statistics': statistics,
        'extreme_events': events,
        'visualizations': [plot_path]
    }

    # 保存结果
    with open(os.path.join(output_dir, 'analysis_results.json'), 'w') as f:
        json.dump(results, f, indent=2)

    return results
```

### 组合模式2: 自适应参数优化
```python
def adaptive_calibration_pipeline(data_analysis_results, base_config):
    """
    根据数据分析结果自适应调整模型率定配置

    Args:
        data_analysis_results: 数据分析结果
        base_config: 基础配置

    Returns:
        优化后的配置
    """
    import copy

    adapted_config = copy.deepcopy(base_config)

    # 根据数据特征调整参数
    if 'statistics' in data_analysis_results:
        flow_stats = data_analysis_results['statistics'].get('flow', {})

        # 如果径流变异性高，增加算法迭代次数
        if flow_stats.get('std', 0) / flow_stats.get('mean', 1) > 0.5:
            adapted_config['algorithm']['rep'] = int(
                adapted_config['algorithm']['rep'] * 1.5
            )
            adapted_config['algorithm']['ngs'] = int(
                adapted_config['algorithm']['ngs'] * 1.2
            )

    # 根据极端事件调整
    if 'extreme_events' in data_analysis_results:
        event_count = data_analysis_results['extreme_events'].get('count', 0)

        # 如果极端事件多，可能需要更严格的收敛标准
        if event_count > 20:
            adapted_config['algorithm']['peps'] = 0.01
            adapted_config['algorithm']['pcento'] = 0.01

    return adapted_config
```

## 错误处理最佳实践

### 标准错误处理模式
```python
def robust_function_template(parameters):
    """
    带完整错误处理的函数模板

    Args:
        parameters: 输入参数

    Returns:
        dict: 执行结果
    """
    import logging

    # 设置日志
    logger = logging.getLogger(__name__)

    try:
        # 1. 参数验证
        required_params = ['data_path', 'output_path']
        for param in required_params:
            if param not in parameters:
                raise ValueError(f"Missing required parameter: {param}")

        # 2. 文件存在性检查
        import os
        if not os.path.exists(parameters['data_path']):
            raise FileNotFoundError(
                f"Data file not found: {parameters['data_path']}"
            )

        # 3. 执行核心逻辑
        result = execute_core_logic(parameters)

        # 4. 结果验证
        if result is None:
            raise RuntimeError("Core logic returned None")

        return {
            'success': True,
            'result': result,
            'message': 'Execution completed successfully'
        }

    except FileNotFoundError as e:
        logger.error(f"File error: {e}")
        return {
            'success': False,
            'error': str(e),
            'error_type': 'FileNotFoundError'
        }

    except ValueError as e:
        logger.error(f"Parameter error: {e}")
        return {
            'success': False,
            'error': str(e),
            'error_type': 'ValueError'
        }

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {
            'success': False,
            'error': str(e),
            'error_type': 'UnexpectedException'
        }

def execute_core_logic(parameters):
    """核心逻辑实现"""
    # 实现具体逻辑
    pass
```

## 代码生成提示词建议

### 生成数据分析代码的提示词模板
```
请生成Python代码来完成以下任务：
[任务描述]

要求：
1. 使用pandas读取CSV数据，包含字段：date, prcp, et, flow
2. 数据路径：[data_path]
3. 输出路径：[output_path]
4. 需要计算：[具体分析内容]
5. 包含完整的错误处理
6. 添加适当的注释
7. 返回JSON格式的结果

参考以下代码模式：
[插入相关代码模式]
```

### 生成可视化代码的提示词模板
```
请生成Python代码来创建以下可视化：
[可视化描述]

要求：
1. 使用matplotlib绘图
2. 图片大小：12x8英寸
3. 分辨率：300 DPI
4. 包含坐标轴标签和标题
5. 保存为PNG格式
6. 输出路径：[output_path]

参考标准可视化模式
```

## 代码质量检查清单

生成代码应满足：
- [ ] 包含完整的文档字符串
- [ ] 参数类型和返回值说明清晰
- [ ] 有完善的错误处理
- [ ] 使用合适的数据结构
- [ ] 代码可读性好，有适当注释
- [ ] 遵循PEP 8编码规范
- [ ] 函数功能单一，职责明确
- [ ] 避免硬编码，使用参数传递
- [ ] 资源正确释放（文件、连接等）
- [ ] 输出格式统一（JSON/CSV）
