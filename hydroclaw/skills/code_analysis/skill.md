---
name: Code Analysis
description: 生成并执行自定义 Python 分析脚本（FDC、径流系数、季节分析等）
keywords: [分析, analysis, fdc, 径流系数, runoff, 代码, code, 自定义, 脚本, script, 基流]
tools: [generate_code, run_code]
when_to_use: 需要自定义分析逻辑，超出标准工具能力范围时
---

## 自定义分析工作流

当用户要求进行自定义分析、计算特定指标、或生成分析代码时使用此工作流。

### 支持的分析类型

- **径流系数计算** (Runoff Coefficient)
- **流量历时曲线** (Flow Duration Curve, FDC)
- **季节性分析** (Seasonal decomposition)
- **基流分离** (Baseflow separation)
- **自定义可视化**

### 执行步骤

1. 如果需要率定数据，先完成率定流程
2. 调用 `generate_code` 生成 Python 分析脚本
3. 调用 `run_code` 执行脚本
4. 将执行结果反馈给用户

### 代码生成要求

生成的代码应该：
- 完整可运行（包含所有 import）
- 使用 matplotlib 绘图（Agg backend）
- 包含错误处理
- 结果保存到文件
