---
name: Code Analysis
description: 生成并执行自定义 Python 分析脚本（FDC、径流系数、季节分析等）
keywords: [分析, analysis, fdc, 径流系数, runoff, 代码, code, 自定义, 脚本, script, 基流, 计算]
tools: [generate_code, run_code, inspect_dir, read_file]
when_to_use: 需要超出标准工具能力的自定义分析时
---

## 目标

生成可直接运行的 Python 分析脚本，执行并返回结果（数值 + 图形）。

成功标志：代码运行无错误，结果已输出（数值打印或图片保存），路径告知用户。

## 判断框架

### 何时选择代码生成（而非现有工具）

| 场景 | 用现有工具 | 用代码生成 |
|------|-----------|-----------|
| 标准率定/评估 | calibrate_model / evaluate_model | |
| 标准可视化（过程线/散点图）| visualize | |
| FDC（流量历时曲线）| | generate_code |
| 基流分离（BFI 指数）| | generate_code |
| 季节性分析（月均流量）| | generate_code |
| 自定义统计计算 | | generate_code |
| 多变量相关分析 | | generate_code |

### 生成代码时，需要给 `generate_code` 哪些信息

1. **任务描述**：具体要计算什么、输入是什么
2. **`data_path`**：从 `validate_basin` 结果的 `data_path` 字段取得，**必须传入**（生成代码内部用 hydrodataset 读数据）
3. **`calibration_dir`**（可选）：如果需要读取率定输出，传入对应目录路径
4. **`output_filename`**（可选）：生成脚本的文件名

> **关键**：`validate_basin` 返回的 `data_path` 就是 CAMELS 数据集根目录。将其作为 `data_path` 参数传给 `generate_code`，生成的脚本会用 `hydrodataset` 正确读取 NetCDF 数据，**不需要猜 CSV 路径**。

### 执行代码后，如何判断结果是否正确

- `run_code` 返回 `stdout` → 读取打印内容
- `run_code` 返回 `output_files` → 检查图片/CSV 是否生成
- 若脚本报错（`stderr` 非空）→ 分析错误原因，修改代码后重试

### 代码质量要求

生成的脚本必须：
- 包含所有 `import`，完整可运行
- 使用 `matplotlib.use("Agg")`（无 GUI 环境）
- 将图片保存到文件（不调用 `plt.show()`）
- 包含基本错误处理（`try/except`），失败时打印有意义的错误信息
- 数值结果用 `print()` 输出，方便 `run_code` 捕获

### 绝对禁止：使用模拟/随机数据

**严禁**在生成的代码中使用以下任何方式替代真实数据：
- `np.random`、`np.random.seed()`、随机生成的流量/降水序列
- 硬编码的示例数值数组（如 `streamflow = [1.2, 2.3, ...]`）
- 任何形式的"演示数据"、"示例数据"

若 `validate_basin` 返回的 `data_path` 中找不到数据文件，**代码必须抛出 `FileNotFoundError`** 并打印明确的错误信息，而不是 fallback 到模拟数据。

```python
# 正确示范：数据不存在时报错而非模拟
if not data_file.exists():
    raise FileNotFoundError(f"CAMELS data not found: {data_file}. Check data_path={data_path}")
```

### 何时需要观测文件

| 情况 | 操作 |
|------|------|
| **需要 CAMELS 流域数据（径流/降水）** | **先调用 `validate_basin(basin_id)`，从返回结果取 `data_path`，传给 `generate_code(data_path=...)` 参数** |
| 不知道率定输出在哪个路径 | `inspect_dir(workspace)` 或 `inspect_dir(calibration_dir)` |
| 脚本中需要读取 CSV，不确定列名 | `read_file(target_csv)` 预览结构 |
| 代码运行后不确定图片在哪 | `inspect_dir(output_dir)` |

> **警告**：不要用 `inspect_dir` 猜测 CAMELS 数据路径。CAMELS 数据是 NetCDF 格式，通过 `hydrodataset` 库读取，**不是 CSV 文件**。`validate_basin` 返回的 `data_path` 是数据集根目录，把它传给 `generate_code(data_path=...)` 即可，生成的脚本会自动用 `hydrodataset` 读数据。

## 异常处理

| 异常 | 处理 |
|------|------|
| 脚本 import 失败（包不存在）| 换用标准库或 numpy/pandas 实现 |
| 路径不存在 | 调整脚本中的路径，或先 `inspect_dir` 确认 |
| 图片未生成 | 检查是否调用了 `plt.savefig()`，backend 是否为 Agg |
| 数值结果为空 | 检查数据过滤条件是否过于严格 |

## 支持的常见分析类型

- **FDC**（流量历时曲线）：对流量排序，计算超越概率
- **径流系数**：`Q_annual / P_annual`，按年计算后取均值
- **基流分离**：使用数字滤波法（Eckhardt）计算 BFI
- **季节分析**：按月聚合，计算月均流量和季节性系数
- **自定义可视化**：任意形式的 matplotlib 图形
