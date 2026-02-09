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
