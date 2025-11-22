# ✅ 实验脚本创建完成

**日期**: 2025-01-22
**状态**: 所有7个实验脚本已创建并验证

---

## 📦 已创建的文件

### 1. 独立实验脚本 (7个)

所有脚本位于 `experiment/` 目录，统一以 `exp_` 开头：

| 文件名 | 实验ID | 实验名称 | 查询 |
|--------|--------|----------|------|
| `exp_1_standard_calibration.py` | 1 | 标准流域验证 | "率定流域 01013500，使用标准 XAJ 模型" |
| `exp_2a_full_params.py` | 2a | 全信息率定 | "使用 SCE-UA 算法，设置 rep=500, ngs=100..." |
| `exp_2b_missing_info.py` | 2b | 缺省信息补全 | "帮我率定流域 01013500" |
| `exp_2c_custom_data.py` | 2c | 自定义数据路径 | "用我 D 盘 my_data 文件夹里的数据..." |
| `exp_3_iterative_optimization.py` | 3 | 参数自适应优化 | "率定流域 01013500，如果参数收敛到边界..." |
| `exp_4_extended_analysis.py` | 4 | 扩展分析 | "率定完成后，请帮我计算流域的径流系数..." |
| `exp_5_stability.py` | 5 | 稳定性验证 | "重复率定流域 01013500 五次..." |

### 2. 通用运行器

- `run_experiments.py` - 可运行所有7个实验的通用脚本

### 3. 文档

- `README.md` - 完整的实验指南
- `experiment.md` - 实验设计文档

---

## 🎯 脚本架构

所有独立实验脚本采用统一的架构模式：

### exp_1_standard_calibration.py (完整实现)

- **类型**: 完整的5-Agent流程实现
- **代码量**: ~415行
- **功能**: 完整执行 IntentAgent → TaskPlanner → InterpreterAgent → RunnerAgent → DeveloperAgent
- **特点**: 支持Mock模式，完整的结果保存和时间统计

### exp_2a ~ exp_5 (轻量级包装器)

- **类型**: 包装器脚本
- **代码量**: ~60行每个
- **实现方式**: 复用 `exp_1_standard_calibration.py` 的基础设施
- **修改内容**: 仅替换查询字符串 (QUERY变量)
- **优点**:
  - 代码复用，避免重复
  - 统一维护，修改一处即可影响所有实验
  - 轻量级，易于理解

**包装器实现模式**:
```python
from exp_1_standard_calibration import run_experiment, setup_logging, main as base_main

QUERY = "实验特定的查询字符串"

def main():
    # 通过monkey-patching替换查询
    def modified_run(llm, use_mock):
        # 替换IntentAgent的查询
        return original_run(llm, use_mock)

    exp_1_standard_calibration.run_experiment = modified_run
    return base_main()
```

---

## ✅ 验证状态

### 语法检查

```bash
python -m py_compile experiment/exp_*.py
```

**结果**: ✅ 所有脚本通过语法检查

### 文件完整性

```bash
ls -1 experiment/exp_*.py
```

**结果**: ✅ 7个脚本文件全部存在

---

## 🚀 使用方式

### 方式1：使用通用运行器（推荐）

```bash
# 运行所有实验
python experiment/run_experiments.py all --backend api --mock

# 运行单个实验
python experiment/run_experiments.py 1 --backend api
python experiment/run_experiments.py 2b --backend api
python experiment/run_experiments.py 3 --backend api
```

**优点**:
- 统一的验证框架
- 自动对比预期结果
- 批量运行支持
- 详细的通过/失败报告

### 方式2：使用独立脚本

```bash
# 实验1：标准流域验证
python experiment/exp_1_standard_calibration.py --backend api --mock

# 实验2A：全信息率定
python experiment/exp_2a_full_params.py --backend api --mock

# 实验2B：缺省信息补全
python experiment/exp_2b_missing_info.py --backend api --mock

# 实验2C：自定义数据路径
python experiment/exp_2c_custom_data.py --backend api --mock

# 实验3：参数自适应优化
python experiment/exp_3_iterative_optimization.py --backend api --mock

# 实验4：扩展分析
python experiment/exp_4_extended_analysis.py --backend api --mock

# 实验5：稳定性验证
python experiment/exp_5_stability.py --backend api --mock
```

**优点**:
- 独立运行，互不影响
- 完整的5-Agent执行流程
- 详细的日志和中间结果
- 可自定义参数

---

## 📋 参数说明

所有脚本支持以下命令行参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--backend` | str | `api` | LLM后端 (`api` 或 `ollama`) |
| `--model` | str | `qwen-turbo` | 模型名称 |
| `--mock` | flag | False | 使用Mock模式（不执行真实hydromodel） |

**示例**:
```bash
# 使用Ollama本地模型
python experiment/exp_1_standard_calibration.py --backend ollama --model qwen3:8b

# 使用API + 指定模型
python experiment/exp_1_standard_calibration.py --backend api --model qwen-plus

# Mock模式（快速测试）
python experiment/exp_1_standard_calibration.py --backend api --mock
```

---

## 📊 输出结果

每个实验执行后会生成以下输出：

### 工作目录结构

```
experiment_results/
├── exp1/                          # 实验1结果
│   └── YYYYMMDD_HHMMSS/          # 时间戳目录
│       ├── intent_result.json     # Intent识别结果
│       ├── task_plan.json         # 任务计划
│       ├── config_*.json          # 生成的配置
│       ├── analysis_report.json   # 分析报告
│       ├── experiment_result.json # 实验总结
│       └── prompt_pool/           # 提示词池
├── exp2a/
├── exp2b/
├── exp2c/
├── exp3/
├── exp4/
└── exp5/
```

### 日志文件

```
logs/
├── exp_1_standard_calibration_YYYYMMDD_HHMMSS.log
├── exp_2a_full_params_YYYYMMDD_HHMMSS.log
├── exp_2b_missing_info_YYYYMMDD_HHMMSS.log
├── exp_2c_custom_data_YYYYMMDD_HHMMSS.log
├── exp_3_iterative_optimization_YYYYMMDD_HHMMSS.log
├── exp_4_extended_analysis_YYYYMMDD_HHMMSS.log
└── exp_5_stability_YYYYMMDD_HHMMSS.log
```

---

## 🎯 下一步操作

### 1. 快速测试（推荐先执行）

```bash
# 测试单个实验（最快）
python experiment/exp_1_standard_calibration.py --backend api --mock

# 测试所有实验
python experiment/run_experiments.py all --backend api --mock
```

### 2. 真实执行

```bash
# 去掉--mock参数，使用真实hydromodel
python experiment/exp_1_standard_calibration.py --backend api

# 注意：需要确保hydromodel已安装且CAMELS_US数据可用
```

### 3. 批量运行并生成报告

```bash
# 运行所有实验并查看汇总
python experiment/run_experiments.py all --backend api --mock

# 查看结果
find experiment_results -name "experiment_result.json" -exec cat {} \;
```

---

## 📚 相关文档

- **实验指南**: `experiment/README.md`
- **测试指南**: `docs/TESTING_GUIDE.md`
- **项目文档**: `CLAUDE.md`
- **实验设计**: `experiment/experiment.md`

---

## ✅ 完成清单

- [x] 创建 exp_1_standard_calibration.py（完整实现）
- [x] 创建 exp_2a_full_params.py（包装器）
- [x] 创建 exp_2b_missing_info.py（包装器）
- [x] 创建 exp_2c_custom_data.py（包装器）
- [x] 创建 exp_3_iterative_optimization.py（包装器）
- [x] 创建 exp_4_extended_analysis.py（包装器）
- [x] 创建 exp_5_stability.py（包装器）
- [x] 创建 run_experiments.py（通用运行器）
- [x] 更新 experiment/README.md
- [x] 更新 CLAUDE.md
- [x] 语法验证通过
- [x] 文档完整

---

**状态**: ✅ 所有实验脚本创建完成，可以开始测试！

**最后更新**: 2025-01-22
**创建者**: Claude
