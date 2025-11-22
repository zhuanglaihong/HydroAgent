# HydroAgent 测试指南
# Testing Guide for HydroAgent

**版本**: v2.1
**日期**: 2025-01-22

---

## 📋 目录

1. [测试概述](#测试概述)
2. [环境准备](#环境准备)
3. [单元测试](#单元测试)
4. [集成测试](#集成测试)
5. [端到端测试](#端到端测试)
6. [实验验证](#实验验证)
7. [故障排除](#故障排除)

---

## 测试概述

HydroAgent提供三个级别的测试：

| 测试级别 | 目的 | 耗时 | LLM调用 |
|---------|------|------|---------|
| **单元测试** | 测试单个组件 | 快（1-5分钟） | 是 |
| **集成测试** | 测试组件协作 | 中（5-15分钟） | 是 |
| **端到端测试** | 测试完整流程 | 长（15-60分钟） | 是 + hydromodel |

---

## 环境准备

### 1. 安装依赖

```bash
# 使用uv安装所有依赖
uv sync

# 激活虚拟环境
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac
```

### 2. 配置API密钥

创建 `configs/definitions_private.py`（如果还没有）：

```bash
# 从模板复制
cp configs/example_definitions_private.py configs/definitions_private.py

# 编辑配置文件
# Windows: notepad configs/definitions_private.py
# Linux/Mac: nano configs/definitions_private.py
```

设置API密钥：

```python
# configs/definitions_private.py

# 通义千问API（推荐用于测试）
OPENAI_API_KEY = "sk-your-qwen-api-key-here"
OPENAI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 或者使用Ollama本地模型（无需API密钥）
OLLAMA_BASE_URL = "http://localhost:11434"
```

### 3. 验证环境

```bash
python -c "import hydromodel; print(f'hydromodel version: {hydromodel.__version__}')"
```

如果hydromodel未安装，测试仍可运行（使用mock模式）。

---

## 单元测试

单元测试验证单个Agent的功能。

### 测试 IntentAgent

测试意图识别和任务决策功能。

```bash
# 使用API后端（推荐）
python test/test_intent_agent.py --backend api

# 使用Ollama本地模型
python test/test_intent_agent.py --backend ollama

# 指定模型
python test/test_intent_agent.py --backend api --model qwen-plus
```

**预期输出**：
- ✅ 9个测试用例全部通过
- 正确识别task_type（standard_calibration, info_completion等）
- 正确提取参数（模型、流域、算法）
- 正确补全缺失信息

### 测试 TaskPlanner

测试任务拆解和提示词生成功能。

```bash
python test/test_task_planner.py
```

**预期输出**：
- ✅ 7个测试用例全部通过
- 正确拆解不同task_type
- 正确数量的子任务
- 正确的依赖关系

### 测试 InterpreterAgent

测试LLM驱动的配置生成功能。

```bash
# 使用API后端
python test/test_interpreter_agent.py --backend api

# 使用Ollama
python test/test_interpreter_agent.py --backend ollama --model qwen3:8b
```

**预期输出**：
- ✅ 3个测试用例全部通过
- 正确生成hydromodel配置JSON
- 包含所有必需字段（data_cfgs, model_cfgs, training_cfgs）
- 配置验证通过

---

## 集成测试

集成测试验证多个Agent的协作。

### 完整4-Agent流程（旧pipeline）

```bash
# 使用Mock模式（不执行真实hydromodel）
python scripts/run_developer_agent_pipeline.py --backend api --mock

# 使用真实hydromodel
python scripts/run_developer_agent_pipeline.py --backend api

# 自定义查询
python scripts/run_developer_agent_pipeline.py --backend api "率定GR5J模型，流域01013500"
```

### 新5-Agent流程（Phase 2架构）

```bash
# 使用Mock模式
python scripts/run_new_pipeline.py --backend api --mock

# 使用真实hydromodel
python scripts/run_new_pipeline.py --backend api

# 保存所有中间结果
python scripts/run_new_pipeline.py --backend api --save-all
```

**预期输出**：
- ✅ 所有5个Agent顺序执行
- IntentAgent → TaskPlanner → InterpreterAgent → RunnerAgent → DeveloperAgent
- 生成配置、执行率定、输出分析报告

---

## 端到端测试

端到端测试验证完整的实验场景（Experiment 1-5）。

### 运行所有实验测试

```bash
# 测试所有5个实验
python test/test_experiments_e2e.py --backend api

# 测试所有实验（Ollama）
python test/test_experiments_e2e.py --backend ollama
```

### 测试单个实验

```bash
# 实验1：标准流域验证
python test/test_experiments_e2e.py --backend api --experiment 1

# 实验2B：缺省信息补全
python test/test_experiments_e2e.py --backend api --experiment 2b

# 实验3：参数自适应优化
python test/test_experiments_e2e.py --backend api --experiment 3

# 实验4：扩展分析
python test/test_experiments_e2e.py --backend api --experiment 4

# 实验5：稳定性验证
python test/test_experiments_e2e.py --backend api --experiment 5
```

### 测试内容

#### 实验1：标准流域验证

**查询**: `"率定流域 01013500，使用标准 XAJ 模型"`

**验证点**：
- ✅ task_type = `standard_calibration`
- ✅ 生成1个子任务
- ✅ 正确生成XAJ模型配置

#### 实验2B：缺省信息补全

**查询**: `"帮我率定流域 01013500"`

**验证点**：
- ✅ task_type = `info_completion`
- ✅ 自动补全model_name（默认xaj）
- ✅ 自动补全algorithm（默认SCE_UA）
- ✅ 自动补全time_period

#### 实验3：参数自适应优化

**查询**: `"率定流域 01013500，如果参数收敛到边界，自动调整范围重新率定"`

**验证点**：
- ✅ task_type = `iterative_optimization`
- ✅ 生成2个子任务（phase1 + phase2）
- ✅ phase2依赖phase1
- ✅ 提取strategy信息

#### 实验4：扩展分析

**查询**: `"率定完成后，请帮我计算流域的径流系数，并画一张流路历时曲线 FDC"`

**验证点**：
- ✅ task_type = `extended_analysis`
- ✅ 提取needs = [`runoff_coefficient`, `FDC`]
- ✅ 生成3个子任务（1 calibration + 2 analyses）
- ✅ 分析任务依赖率定任务

#### 实验5：稳定性验证

**查询**: `"重复率定流域 01013500 十次，使用不同随机种子"`

**验证点**：
- ✅ task_type = `repeated_experiment`
- ✅ 提取n_repeats = 10
- ✅ 生成11个子任务（10 repeats + 1 statistical_analysis）
- ✅ 统计分析依赖所有重复任务

---

## 实验验证

完整验证实验1-5（需要真实hydromodel）。

### 实验1：标准流域验证

```bash
python scripts/run_new_pipeline.py --backend api \
  "率定流域 01013500，使用标准 XAJ 模型" \
  --save-all
```

**成功标准**：
- NSE > 0.5
- 生成calibration_results.json
- 生成参数文件

### 实验2A：全信息率定

```bash
python scripts/run_new_pipeline.py --backend api \
  "使用 SCE-UA 算法，设置 rep=500, ngs=100，率定 CAMELS_US 的 01013500 流域" \
  --save-all
```

### 实验2B：缺省信息补全

```bash
python scripts/run_new_pipeline.py --backend api \
  "帮我率定流域 01013500" \
  --save-all
```

**验证**：自动补全模型、算法、时间段

### 实验3：参数自适应优化

```bash
python scripts/run_new_pipeline.py --backend api \
  "率定流域 01013500，如果参数收敛到边界，自动调整范围重新率定" \
  --save-all
```

**验证**：
- 执行Phase 1率定
- 检查参数边界
- 如有边界参数，执行Phase 2

### 实验4：扩展分析

```bash
python scripts/run_new_pipeline.py --backend api \
  "率定完成后，请帮我计算流域的径流系数，并画一张流路历时曲线 FDC" \
  --save-all
```

**验证**：
- 执行标准率定
- DeveloperAgent生成自定义分析代码
- 执行代码并输出结果

### 实验5：稳定性验证

```bash
# 注意：此实验耗时较长（约30-60分钟）
python scripts/run_new_pipeline.py --backend api \
  "重复率定流域 01013500 五次，使用不同随机种子" \
  --save-all
```

**验证**：
- 执行5次率定（不同random_seed）
- 计算NSE统计（mean, std, CV）
- 评估稳定性（CV < 0.1为稳定）

---

## 故障排除

### 常见问题

#### 1. API密钥错误

**症状**：
```
❌ Intent分析失败: Authentication failed
```

**解决**：
- 检查 `configs/definitions_private.py` 中的API_KEY
- 确认API密钥有效且有余额

#### 2. hydromodel未安装

**症状**：
```
ImportError: No module named 'hydromodel'
```

**解决**：
```bash
# 安装hydromodel
pip install hydromodel

# 或使用mock模式测试
python test/test_experiments_e2e.py --backend api --mock
```

#### 3. LLM返回格式错误

**症状**：
```
❌ IntentAgent失败: Failed to parse JSON from LLM response
```

**解决**：
- 尝试使用不同的模型（如qwen-plus）
- 检查temperature设置（降低temperature）
- 查看日志中的原始LLM响应

#### 4. 配置验证失败

**症状**：
```
❌ Config生成失败: Validation failed
```

**解决**：
- 查看详细的validation_errors
- 检查是否缺少必需字段
- 查看InterpreterAgent的self-correction日志

### 查看日志

所有测试都会在 `logs/` 目录生成详细日志：

```bash
# 查看最新的日志
ls -lt logs/

# 查看特定测试的日志
cat logs/test_e2e_all_20251122_203000.log

# 搜索错误
grep "ERROR" logs/test_e2e_all_*.log
```

### 调试模式

增加日志级别以获取更多信息：

```python
# 在测试脚本开头添加
import logging
logging.getLogger().setLevel(logging.DEBUG)
```

---

## 快速测试命令

### 最小测试（快速验证）

```bash
# 仅测试IntentAgent（最快）
python test/test_intent_agent.py --backend api

# 仅测试TaskPlanner（无需LLM调用多次）
python test/test_task_planner.py
```

### 完整测试（完整验证）

```bash
# 端到端测试所有实验
python test/test_experiments_e2e.py --backend api

# 完整pipeline测试（包含真实hydromodel执行）
python scripts/run_new_pipeline.py --backend api --save-all
```

### 性能测试

```bash
# 测试并记录执行时间
time python test/test_experiments_e2e.py --backend api
```

---

## 测试检查清单

运行完整测试前，确认以下事项：

- [ ] 虚拟环境已激活
- [ ] API密钥已配置（或使用Ollama）
- [ ] hydromodel已安装（或使用--mock）
- [ ] 有足够的磁盘空间（至少1GB用于结果）
- [ ] 网络连接正常（用于API调用）

---

## 测试结果解读

### 单元测试

**成功示例**：
```
✅ SUCCESS
  🎯 Task Type:  standard_calibration
  Intent:        CALIBRATION
  Model:         xaj
  Basin:         01013500
```

**失败示例**：
```
❌ FAILED: Config validation failed
  Validation errors:
    - Missing required section: data_cfgs
```

### 端到端测试

**成功示例**：
```
======================================================================
✅ 实验1测试通过
======================================================================
```

**失败示例**：
```
⚠️  预期task_type为'standard_calibration'，实际为'info_completion'
```

---

## 持续集成

未来计划添加CI/CD支持：

```yaml
# .github/workflows/test.yml (示例)
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run tests
        run: |
          uv sync
          python test/test_experiments_e2e.py --backend api --mock
```

---

## 联系与反馈

- **Issues**: https://github.com/anthropics/claude-code/issues
- **文档**: README.md, CLAUDE.md

---

**最后更新**: 2025-01-22
**测试框架版本**: v2.1
