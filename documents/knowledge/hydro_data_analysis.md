# 水文数据分析知识库

## 水文数据分析基础

### 常用Python库
```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import xarray as xr
```

### 读取水文数据

#### CSV格式数据读取
```python
def load_hydro_data(file_path):
    """
    读取水文CSV数据

    Args:
        file_path: CSV文件路径

    Returns:
        DataFrame with columns: date, prcp, et, flow
    """
    df = pd.read_csv(file_path, parse_dates=['date'])
    df.set_index('date', inplace=True)
    return df

# 使用示例
data = load_hydro_data('data/basin_data.csv')
```

#### NetCDF格式数据读取
```python
def load_nc_data(nc_file_path):
    """读取NetCDF格式的水文数据"""
    ds = xr.open_dataset(nc_file_path)
    # 提取变量
    prcp = ds['prcp'].values
    et = ds['pet'].values  # 或 'tmean'
    flow = ds['streamflow'].values
    time = pd.to_datetime(ds['time'].values)

    # 转换为DataFrame
    df = pd.DataFrame({
        'prcp': prcp,
        'et': et,
        'flow': flow
    }, index=time)

    return df
```

## 数据质量分析

### 1. 缺失值检查
```python
def check_missing_values(df):
    """
    检查数据缺失情况

    Returns:
        dict: 缺失值统计
    """
    missing_stats = {
        'total_records': len(df),
        'missing_counts': df.isnull().sum().to_dict(),
        'missing_percentage': (df.isnull().sum() / len(df) * 100).to_dict(),
        'complete_records': df.dropna().shape[0]
    }

    return missing_stats

# 使用示例
missing_info = check_missing_values(data)
print(f"降雨数据缺失: {missing_info['missing_percentage']['prcp']:.2f}%")
```

### 2. 异常值检测
```python
def detect_outliers(series, method='iqr', threshold=3):
    """
    检测异常值

    Args:
        series: 数据序列
        method: 'iqr' 或 'zscore'
        threshold: 阈值

    Returns:
        dict: 异常值信息
    """
    if method == 'iqr':
        Q1 = series.quantile(0.25)
        Q3 = series.quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        outliers = series[(series < lower_bound) | (series > upper_bound)]
    elif method == 'zscore':
        z_scores = np.abs((series - series.mean()) / series.std())
        outliers = series[z_scores > threshold]

    return {
        'outlier_count': len(outliers),
        'outlier_indices': outliers.index.tolist(),
        'outlier_values': outliers.values.tolist()
    }
```

### 3. 数据完整性检查
```python
def check_data_integrity(df):
    """
    检查数据完整性

    Returns:
        dict: 完整性报告
    """
    integrity_report = {
        'date_range': {
            'start': df.index.min(),
            'end': df.index.max(),
            'total_days': (df.index.max() - df.index.min()).days
        },
        'negative_values': {
            'prcp': (df['prcp'] < 0).sum(),
            'flow': (df['flow'] < 0).sum()
        },
        'zero_values': {
            'prcp': (df['prcp'] == 0).sum(),
            'flow': (df['flow'] == 0).sum()
        }
    }

    return integrity_report
```

## 统计特征分析

### 1. 基础统计量
```python
def calculate_basic_statistics(df):
    """
    计算基础统计量

    Returns:
        dict: 统计结果
    """
    stats = {}

    for col in ['prcp', 'et', 'flow']:
        if col in df.columns:
            stats[col] = {
                'mean': df[col].mean(),
                'median': df[col].median(),
                'std': df[col].std(),
                'min': df[col].min(),
                'max': df[col].max(),
                'q25': df[col].quantile(0.25),
                'q75': df[col].quantile(0.75)
            }

    return stats

# 使用示例
statistics = calculate_basic_statistics(data)
print(f"年均降雨量: {statistics['prcp']['mean'] * 365:.2f} mm")
```

### 2. 时间序列特征
```python
def analyze_temporal_patterns(df):
    """
    分析时间序列模式

    Returns:
        dict: 时间模式分析结果
    """
    df_copy = df.copy()
    df_copy['year'] = df_copy.index.year
    df_copy['month'] = df_copy.index.month
    df_copy['season'] = df_copy['month'].map({
        12: 'winter', 1: 'winter', 2: 'winter',
        3: 'spring', 4: 'spring', 5: 'spring',
        6: 'summer', 7: 'summer', 8: 'summer',
        9: 'autumn', 10: 'autumn', 11: 'autumn'
    })

    patterns = {
        'monthly_mean': df_copy.groupby('month')['flow'].mean().to_dict(),
        'seasonal_mean': df_copy.groupby('season')['flow'].mean().to_dict(),
        'annual_total_prcp': df_copy.groupby('year')['prcp'].sum().to_dict(),
        'annual_mean_flow': df_copy.groupby('year')['flow'].mean().to_dict()
    }

    return patterns
```

## 极端事件识别

### 1. 极端降雨事件
```python
def identify_extreme_rainfall_events(df, threshold=30.0):
    """
    识别极端降雨事件

    Args:
        df: 数据框
        threshold: 降雨阈值 (mm/day)

    Returns:
        DataFrame: 极端事件列表
    """
    extreme_events = df[df['prcp'] > threshold].copy()
    extreme_events['event_id'] = range(1, len(extreme_events) + 1)

    # 计算事件特征
    extreme_events['intensity'] = extreme_events['prcp']
    extreme_events['duration'] = 1  # 单日事件

    events_summary = {
        'total_events': len(extreme_events),
        'max_intensity': extreme_events['prcp'].max(),
        'mean_intensity': extreme_events['prcp'].mean(),
        'events_per_year': len(extreme_events) / (
            (df.index.max() - df.index.min()).days / 365.25
        ),
        'events_list': extreme_events[['prcp']].to_dict('records')
    }

    return events_summary
```

### 2. 洪水事件识别
```python
def identify_flood_events(df, percentile=95):
    """
    识别洪水事件（高流量事件）

    Args:
        df: 数据框
        percentile: 百分位阈值

    Returns:
        dict: 洪水事件信息
    """
    threshold = df['flow'].quantile(percentile / 100)
    flood_events = df[df['flow'] > threshold].copy()

    # 识别连续洪水事件
    flood_events['date_diff'] = flood_events.index.to_series().diff().dt.days
    flood_events['event_group'] = (flood_events['date_diff'] > 1).cumsum()

    event_stats = []
    for group_id in flood_events['event_group'].unique():
        group = flood_events[flood_events['event_group'] == group_id]
        event_stats.append({
            'start_date': group.index.min(),
            'end_date': group.index.max(),
            'duration': len(group),
            'peak_flow': group['flow'].max(),
            'total_volume': group['flow'].sum()
        })

    return {
        'threshold': threshold,
        'total_flood_events': len(event_stats),
        'event_details': event_stats
    }
```

## 降雨-径流关系分析

### 1. 相关性分析
```python
def analyze_rainfall_runoff_correlation(df, max_lag=10):
    """
    分析降雨-径流相关性

    Args:
        df: 数据框
        max_lag: 最大滞后天数

    Returns:
        dict: 相关性分析结果
    """
    correlations = {}

    # 计算不同滞后的相关系数
    for lag in range(max_lag + 1):
        if lag == 0:
            corr = df['prcp'].corr(df['flow'])
        else:
            corr = df['prcp'].shift(lag).corr(df['flow'])
        correlations[f'lag_{lag}'] = corr

    # 找到最优滞后
    best_lag = max(correlations, key=correlations.get)
    best_corr = correlations[best_lag]

    return {
        'correlations': correlations,
        'best_lag': int(best_lag.split('_')[1]),
        'best_correlation': best_corr,
        'interpretation': 'Strong' if abs(best_corr) > 0.7 else
                         'Moderate' if abs(best_corr) > 0.4 else 'Weak'
    }

# 使用示例
correlation_analysis = analyze_rainfall_runoff_correlation(data, max_lag=7)
print(f"最优滞后: {correlation_analysis['best_lag']} 天")
print(f"相关系数: {correlation_analysis['best_correlation']:.4f}")
```

### 2. 径流系数分析
```python
def calculate_runoff_coefficient(df):
    """
    计算径流系数

    Returns:
        dict: 径流系数统计
    """
    # 计算总降雨和总径流
    total_prcp = df['prcp'].sum()
    total_flow = df['flow'].sum()

    # 计算不同时间尺度的径流系数
    df_copy = df.copy()
    df_copy['year'] = df_copy.index.year
    df_copy['month'] = df_copy.index.month

    annual_rc = df_copy.groupby('year').apply(
        lambda x: x['flow'].sum() / x['prcp'].sum() if x['prcp'].sum() > 0 else 0
    )

    monthly_rc = df_copy.groupby(['year', 'month']).apply(
        lambda x: x['flow'].sum() / x['prcp'].sum() if x['prcp'].sum() > 0 else 0
    )

    return {
        'overall_runoff_coefficient': total_flow / total_prcp if total_prcp > 0 else 0,
        'annual_mean_rc': annual_rc.mean(),
        'annual_std_rc': annual_rc.std(),
        'monthly_mean_rc': monthly_rc.mean(),
        'monthly_std_rc': monthly_rc.std()
    }
```

## 数据可视化

### 1. 时间序列图
```python
def plot_timeseries(df, output_path='timeseries_plot.png'):
    """
    绘制降雨-径流时间序列图

    Args:
        df: 数据框
        output_path: 输出文件路径
    """
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    # 降雨图（倒置）
    axes[0].bar(df.index, df['prcp'], color='skyblue', width=1)
    axes[0].set_ylabel('Precipitation (mm/day)', fontsize=12)
    axes[0].invert_yaxis()
    axes[0].grid(True, alpha=0.3)

    # 径流图
    axes[1].plot(df.index, df['flow'], color='steelblue', linewidth=1)
    axes[1].set_ylabel('Streamflow (mm/day)', fontsize=12)
    axes[1].set_xlabel('Date', fontsize=12)
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()

    return output_path
```

### 2. 月均值柱状图
```python
def plot_monthly_statistics(df, output_path='monthly_stats.png'):
    """
    绘制月平均统计图

    Args:
        df: 数据框
        output_path: 输出文件路径
    """
    df_copy = df.copy()
    df_copy['month'] = df_copy.index.month

    monthly_stats = df_copy.groupby('month').agg({
        'prcp': 'mean',
        'flow': 'mean'
    })

    fig, ax1 = plt.subplots(figsize=(10, 6))

    x = np.arange(1, 13)
    width = 0.35

    ax1.bar(x - width/2, monthly_stats['prcp'], width,
            label='Precipitation', color='skyblue')
    ax1.set_xlabel('Month', fontsize=12)
    ax1.set_ylabel('Precipitation (mm/day)', color='skyblue', fontsize=12)
    ax1.tick_params(axis='y', labelcolor='skyblue')

    ax2 = ax1.twinx()
    ax2.bar(x + width/2, monthly_stats['flow'], width,
            label='Streamflow', color='steelblue')
    ax2.set_ylabel('Streamflow (mm/day)', color='steelblue', fontsize=12)
    ax2.tick_params(axis='y', labelcolor='steelblue')

    ax1.set_xticks(x)
    ax1.set_xticklabels(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                         'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])
    ax1.grid(True, alpha=0.3)

    plt.title('Monthly Average Precipitation and Streamflow', fontsize=14)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()

    return output_path
```

## 完整分析示例

```python
def comprehensive_hydro_analysis(data_path, output_dir='analysis_results'):
    """
    综合水文数据分析

    Args:
        data_path: 数据文件路径
        output_dir: 输出目录

    Returns:
        dict: 完整分析结果
    """
    import os
    os.makedirs(output_dir, exist_ok=True)

    # 读取数据
    df = load_hydro_data(data_path)

    # 1. 数据质量检查
    missing_info = check_missing_values(df)
    integrity_info = check_data_integrity(df)

    # 2. 统计分析
    basic_stats = calculate_basic_statistics(df)
    temporal_patterns = analyze_temporal_patterns(df)

    # 3. 极端事件识别
    extreme_rainfall = identify_extreme_rainfall_events(df, threshold=30)
    flood_events = identify_flood_events(df, percentile=95)

    # 4. 降雨-径流关系
    correlation_analysis = analyze_rainfall_runoff_correlation(df, max_lag=7)
    runoff_coef = calculate_runoff_coefficient(df)

    # 5. 可视化
    plot_timeseries(df, f'{output_dir}/timeseries.png')
    plot_monthly_statistics(df, f'{output_dir}/monthly_stats.png')

    # 整合结果
    results = {
        'data_quality': {
            'missing_values': missing_info,
            'integrity': integrity_info
        },
        'statistics': {
            'basic': basic_stats,
            'temporal': temporal_patterns
        },
        'extreme_events': {
            'rainfall': extreme_rainfall,
            'floods': flood_events
        },
        'rainfall_runoff': {
            'correlation': correlation_analysis,
            'runoff_coefficient': runoff_coef
        },
        'visualizations': {
            'timeseries': f'{output_dir}/timeseries.png',
            'monthly_stats': f'{output_dir}/monthly_stats.png'
        }
    }

    # 保存JSON结果
    import json
    with open(f'{output_dir}/analysis_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)

    return results
```

## 最佳实践建议

1. **数据预处理**：始终先检查数据质量和完整性
2. **异常值处理**：使用合适的方法识别和处理异常值
3. **时间对齐**：确保降雨和径流数据时间对齐
4. **单位一致性**：统一数据单位（推荐mm/day）
5. **结果验证**：交叉验证分析结果的合理性
6. **可视化**：使用图表直观展示分析结果
7. **文档记录**：详细记录分析步骤和参数选择
