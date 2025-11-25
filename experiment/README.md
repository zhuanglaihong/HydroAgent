# HydroAgent 实验指南

**版本**: v2.0
**更新日期**: 2025-01-24

本目录包含HydroAgent的核心实验脚本，分为2大类共7个实验（实验1-2已重构）。

## 📋 实验列表

### 实验1：基础功能验证

| 实验ID | 脚本文件 | 查询示例 | 验证目标 |
|-------|---------|---------|---------|
| **1A** | `exp_1a_standard.py` | "率定流域 01013500，使用 GR4J 模型..." | 标准流程，完整信息 |
| **1B** | `exp_1b_info_completion.py` | "帮我率定流域 01013500" | 缺省信息智能补全 |
| **1C** | `exp_1c_error_handling.py` | "率定流域 99999999" (错误ID) | 错误处理鲁棒性 |

### 实验2：稳定性与批量处理

| 实验ID | 脚本文件 | 查询示例 | 验证目标 |
|-------|---------|---------|---------|
| **2A** | `exp_2a_repeated_calibration.py` | "重复执行20次率定..." | 单流域稳定性（20次） |
| **2B** | `exp_2b_multi_basin.py` | "批量率定10个流域..." | 多流域性能对比 |
| **2C** | `exp_2c_multi_algorithm.py` | "分别使用 SCE-UA、DE、PSO、GA..." | 多算法对比 |

### 实验3-4：高级功能

| 实验ID | 脚本文件 | 验证目标 |
|-------|---------|---------|
| **3** | `exp_3_iterative_optimization.py` | 参数自适应优化 |
| **4** | `exp_4_extended_analysis.py` | 代码生成与扩展分析 |

## 🚀 快速开始

### 第一步：环境准备

```bash
# 激活虚拟环境
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# 确保配置文件存在
# 复制 configs/example_definitions_private.py 到 configs/definitions_private.py
# 并填写API Key
```

### 第二步：运行实验（推荐顺序）

```bash
# 1. 基础功能验证（推荐Mock模式快速验证）
python experiment/exp_1a_standard.py --backend api --mock
python experiment/exp_1b_info_completion.py --backend api --mock
python experiment/exp_1c_error_handling.py --backend api --mock

# 2. 稳定性和批量（建议真实执行或减少参数）
python experiment/exp_2a_repeated_calibration.py --backend api --repetitions 5  # 先测试5次
python experiment/exp_2b_multi_basin.py --backend api --mock
python experiment/exp_2c_multi_algorithm.py --backend api --mock

# 3. 高级功能
python experiment/exp_3_iterative_optimization.py --backend api --mock
python experiment/exp_4_extended_analysis.py --backend api --mock
```

### 常用参数

- `--backend api`: 使用API（qwen-turbo）
- `--backend ollama`: 使用本地Ollama（qwen3:8b）
- `--mock`: Mock模式（不运行真实hydromodel，快速验证流程）
- `--repetitions N`: 重复次数（仅实验2A，默认20）
- `--basins "ID1,ID2"`: 自定义流域列表（仅实验2B）
- `--algorithms "A1,A2"`: 自定义算法列表（仅实验2C）

# 实验3：参数自适应优化
python experiment/exp_3_iterative_optimization.py --backend api --mock

# 实验4：扩展分析
python experiment/exp_4_extended_analysis.py --backend api --mock

# 实验5：稳定性验证（耗时较长）
python experiment/exp_5_stability.py --backend api --mock
```

## 📊 实验详情

### 实验1：标准流域验证

**目标**：验证系统能够正确执行标准的单流域率定任务

**查询**：
```
"率定流域 01013500，使用标准 XAJ 模型"
```

**预期结果**：
- ✅ task_type = `standard_calibration`
- ✅ 生成1个子任务
- ✅ 正确生成XAJ模型配置
- ✅ NSE > 0.5（如使用真实hydromodel）

**运行**：
```bash
python experiment/run_experiments.py 1 --backend api
```

---

### 实验2A：全信息率定

**目标**：验证系统能够正确提取用户指定的所有参数

**查询**：
```
"使用 SCE-UA 算法，设置 rep=500, ngs=100，率定 CAMELS_US 的 01013500 流域，时间 1990-2000"
```

**预期结果**：
- ✅ 正确提取 rep=500
- ✅ 正确提取 ngs=100
- ✅ 正确提取训练期 1990-2000

**运行**：
```bash
python experiment/run_experiments.py 2a --backend api
```

---

### 实验2B：缺省信息补全

**目标**：验证系统能够自动补全缺失的信息

**查询**：
```
"帮我率定流域 01013500"
```

**预期结果**：
- ✅ task_type = `info_completion`
- ✅ 自动补全 model_name（默认xaj）
- ✅ 自动补全 algorithm（默认SCE_UA）
- ✅ 自动补全 time_period

**运行**：
```bash
python experiment/run_experiments.py 2b --backend api
```

---

### 实验2C：自定义数据路径

**目标**：验证系统能够识别并使用自定义数据路径

**查询**：
```
"用我 D 盘 my_data 文件夹里的数据跑一下模型"
```

**预期结果**：
- ✅ task_type = `custom_data`
- ✅ 正确提取数据路径
- ✅ 配置中data_source_type = "custom"

**运行**：
```bash
python experiment/run_experiments.py 2c --backend api
```

---

### 实验3：参数自适应优化

**目标**：验证系统能够执行两阶段迭代优化

**查询**：
```
"率定流域 01013500，如果参数收敛到边界，自动调整范围重新率定"
```

**预期结果**：
- ✅ task_type = `iterative_optimization`
- ✅ 生成2个子任务（phase1 + phase2）
- ✅ phase2依赖phase1
- ✅ 提取strategy信息

**运行**：
```bash
python experiment/run_experiments.py 3 --backend api
```

---

### 实验4：扩展分析

**目标**：验证系统能够识别并计划扩展分析任务

**查询**：
```
"率定完成后，请帮我计算流域的径流系数，并画一张流路历时曲线 FDC"
```

**预期结果**：
- ✅ task_type = `extended_analysis`
- ✅ 提取needs = [`runoff_coefficient`, `FDC`]
- ✅ 生成3个子任务（1 calibration + 2 analyses）
- ✅ 分析任务依赖率定任务

**运行**：
```bash
python experiment/run_experiments.py 4 --backend api
```

---

### 实验5：稳定性验证

**目标**：验证系统能够执行重复实验并进行统计分析

**查询**：
```
"重复率定流域 01013500 五次，使用不同随机种子"
```

**预期结果**：
- ✅ task_type = `repeated_experiment`
- ✅ 提取n_repeats = 5
- ✅ 生成6个子任务（5 repeats + 1 statistical_analysis）
- ✅ 统计分析依赖所有重复任务

**运行**：
```bash
python experiment/run_experiments.py 5 --backend api
```

---

## 📁 输出结果

实验结果保存在 `experiment_results/` 目录：

```
experiment_results/
├── exp1/                          # 实验1结果
│   └── YYYYMMDD_HHMMSS/          # 时间戳目录
│       ├── intent_result.json     # Intent识别结果
│       ├── task_plan.json         # 任务计划
│       ├── config_*.json          # 生成的配置
│       ├── experiment_result.json # 实验总结
│       └── prompt_pool/           # 提示词池
├── exp2a/
├── exp2b/
├── exp2c/
├── exp3/
├── exp4/
└── exp5/
```

## 🔍 查看结果

```bash
# 查看最新实验结果
ls -lt experiment_results/exp1/

# 查看实验总结
cat experiment_results/exp1/YYYYMMDD_HHMMSS/experiment_result.json

# 查看Intent识别结果
cat experiment_results/exp1/YYYYMMDD_HHMMSS/intent_result.json
```

## 📊 验证标准

每个实验都会验证以下内容：

1. **task_type匹配** - 是否正确识别任务类型
2. **子任务数量** - 是否生成正确数量的子任务
3. **配置生成** - 是否成功生成所有配置
4. **特定验证** - 各实验的特定验证点（如参数提取、依赖关系等）

## 🎯 成功标准

实验通过的标志：

```
✅ 实验1通过!
======================================================================
验证结果:
  ✅ task_type
  ✅ subtask_count
  ✅ configs_generated

总耗时: 12.3s
```

## ⚠️ 注意事项

1. **API密钥**：确保 `configs/definitions_private.py` 中配置了API密钥
2. **Mock模式**：首次测试建议使用 `--mock` 参数，避免执行真实hydromodel
3. **真实执行**：如需真实执行，确保hydromodel已安装且CAMELS_US数据可用
4. **日志文件**：所有日志保存在 `logs/` 目录

## 🔧 故障排除

### 问题1：API密钥错误

```
❌ API key未配置
```

**解决**：编辑 `configs/definitions_private.py`，设置OPENAI_API_KEY

### 问题2：task_type不匹配

```
⚠️  任务类型不匹配（预期: standard_calibration）
```

**解决**：
1. 检查查询是否包含关键词
2. 查看logs中的详细日志
3. 尝试使用不同的LLM模型

### 问题3：配置生成失败

```
❌ 配置生成失败
```

**解决**：
1. 查看logs中的validation_errors
2. 检查InterpreterAgent的self-correction日志
3. 尝试降低temperature参数

## 📚 相关文档

- **测试指南**：`docs/TESTING_GUIDE.md`
- **架构文档**：`docs/ARCHITECTURE_V3_FINAL.md`
- **项目文档**：`CLAUDE.md`
- **实验定义**：`experiment/experiment.md`

## 🚀 批量运行

运行所有实验并生成报告：

```bash
# 运行所有实验
python experiment/run_experiments.py all --backend api --mock

# 查看所有结果
find experiment_results -name "experiment_result.json" -exec cat {} \;
```

---

**最后更新**: 2025-01-22
**实验框架版本**: v3.0
