---
name: Runoff Coefficient and FDC Analysis
description: 计算流域径流系数和流量历时曲线(FDC)的分析工具，支持年/月尺度径流系数计算、FDC特征值提取及可视化
keywords: [runoff_coefficient, fdc, flow_duration_curve, hydrology, camels, calibration, q90, q50, q10]
tools: [runoff_fdc_analysis]
when_to_use: 需要评估流域水文响应特征、分析径流-降水关系或生成流量历时曲线时
---

## Runoff Coefficient and FDC Analysis 工作流

本技能用于流域水文特征分析，包括径流系数计算和流量历时曲线(FDC)生成，适用于CAMELS数据集分析或模型率定结果评估。

### 适用场景

- **流域水文特征评估**：计算长期径流系数，评估流域产水能力
- **模型率定验证**：对比观测与模拟径流的FDC特征
- **生态流量分析**：提取Q90、Q50、Q10等特征流量用于生态需水评估
- **气候变化影响研究**：分析不同时期径流系数的变化趋势

### 输入数据要求

| 数据类型 | 格式 | 必需字段 |
|---------|------|---------|
| 径流数据 | CSV/DataFrame | datetime索引, 流量列(m³/s或mm) |
| 降水数据 | CSV/DataFrame | datetime索引, 降水量(mm) |

> **注意**：径流和降水数据时间分辨率需一致（建议日尺度），且时间范围需重叠。

### 核心功能与参数

#### 1. 径流系数计算 (`calculate_runoff_coefficient`)

计算年尺度或月尺度径流系数（径流深/降水量）。