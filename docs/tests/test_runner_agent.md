# RunnerAgent 测试说明文档

## 概述

本文档介绍 RunnerAgent（执行监控智能体）的测试方法和使用说明。RunnerAgent 负责接收 ConfigAgent 的配置dict，调用 hydromodel API 执行实际的模型率定/评估/模拟任务。

**关键特性**:
- 直接接收config dict（无需文件）
- 调用hydromodel API执行任务
- 捕获stdout/stderr输出
- 解析执行结果和性能指标
- 完整的错误处理
- 支持Mock测试模式

## 测试文件结构

```
HydroAgent/
├── test/
│   └── test_runner_agent.py              # RunnerAgent单元测试
├── scripts/
│   └── run_runner_agent_pipeline.py      # 完整3-Agent管道测试
└── docs/
    └── tests/
        └── test_runner_agent.md          # 本文档
```

## 一、单元测试

### 文件：`test/test_runner_agent.py`

#### 测试用例

| # | 测试名称 | 描述 | 验证点 |
|---|---------|------|--------|
| 1 | RunnerAgent初始化 | 初始化测试 | 参数设置、workspace配置 |
| 2 | Mock率定测试 | 模拟率定过程 | config接收、结果解析 |
| 3 | Mock评估测试 | 模拟评估过程 | 性能指标提取 |
| 4 | 错误处理测试 | 异常捕获机制 | traceback捕获 |
| 5 | 缺少配置测试 | 输入验证 | 错误信息准确性 |
| 6 | hydromodel检查 | 依赖可用性 | import检测 |

#### 运行方式

```bash
# 进入项目根目录
cd D:/project/Agent/HydroAgent

# 激活虚拟环境
.venv\Scripts\activate

# 运行测试
python test/test_runner_agent.py
```

#### 预期输出

```
======================================================================
RunnerAgent 单元测试套件
======================================================================
日志文件: D:\project\Agent\HydroAgent\logs\test_runner_agent_20251120_230000.log

======================================================================
Test Case 1: RunnerAgent 初始化测试
======================================================================
✅ RunnerAgent 初始化测试通过

======================================================================
Test Case 2: Mock 率定测试
======================================================================
✅ Mock 率定测试通过
   最佳参数: {'x1': 350.0, 'x2': 0.5, 'x3': 100.0, 'x4': 2.0}
   性能指标: {'NSE': 0.85, 'RMSE': 2.5, 'KGE': 0.82}

... (其他测试用例)

======================================================================
测试总结
======================================================================
1. ✅ PASS - RunnerAgent初始化
2. ✅ PASS - Mock率定测试
3. ✅ PASS - Mock评估测试
4. ✅ PASS - 错误处理测试
5. ✅ PASS - 缺少配置测试
6. ✅ PASS - hydromodel检查

总计: 6/6 通过
成功率: 100.0%
======================================================================
```

#### 测试详解

##### 测试1: RunnerAgent初始化

**验证点**:
- ✅ Agent名称正确
- ✅ workspace_dir设置正确
- ✅ timeout参数配置正确

##### 测试2: Mock率定测试

**核心功能**: 模拟hydromodel.calibrate()调用

```python
# Mock返回值
mock_calibrate_result = {
    "best_params": {
        "x1": 350.0,
        "x2": 0.5,
        "x3": 100.0,
        "x4": 2.0
    },
    "metrics": {
        "NSE": 0.85,
        "RMSE": 2.5,
        "KGE": 0.82
    },
    "output_files": [
        "results/calibrated_params.json",
        "results/performance_plot.png"
    ]
}
```

**验证点**:
- ✅ 接收ConfigAgent的输出dict
- ✅ 正确调用calibrate()
- ✅ 解析性能指标
- ✅ 提取最优参数
- ✅ 返回格式正确

##### 测试3: Mock评估测试

**验证点**:
- ✅ intent识别为evaluation时调用evaluate()
- ✅ 解析性能指标
- ✅ 兼容不同的结果格式

##### 测试4: 错误处理

**场景**: calibrate()抛出异常

**验证点**:
- ✅ 捕获异常不崩溃
- ✅ 返回success=False
- ✅ 包含错误信息和traceback

##### 测试6: hydromodel检查

**功能**: 检测hydromodel是否已安装

```python
is_available = runner_agent.check_hydromodel_available()
```

如果hydromodel未安装，会显示警告但测试仍通过（使用Mock模式）。

---

## 二、完整管道测试

### 文件：`scripts/run_runner_agent_pipeline.py`

#### 功能说明

这是最完整的测试工具，测试 **IntentAgent → ConfigAgent → RunnerAgent** 三段管道。

**主要功能**:
1. 从用户查询到最终执行结果的完整流程
2. 支持Mock模式（不需要hydromodel）
3. 支持Real模式（调用真实hydromodel）
4. 显示每一步的耗时
5. 可选保存配置到文件
6. 支持LLM后端切换

#### 运行方式

##### 基础用法

```bash
# Mock模式 - 推荐用于测试（不需要hydromodel）
python scripts/run_runner_agent_pipeline.py --mock

# 真实模式 - 调用真实hydromodel（需要hydromodel已安装）
python scripts/run_runner_agent_pipeline.py
```

##### 自定义查询

```bash
# 自定义查询 + Mock模式
python scripts/run_runner_agent_pipeline.py --mock "评估XAJ模型在流域11532500的性能"

# 多个查询测试
python scripts/run_runner_agent_pipeline.py --mock "率定GR4J模型"
python scripts/run_runner_agent_pipeline.py --mock "评估GR5J模型"
python scripts/run_runner_agent_pipeline.py --mock "模拟XAJ模型预测"
```

##### 使用API后端

```bash
# 使用通义千问API + Mock模式
python scripts/run_runner_agent_pipeline.py --backend api --mock

# 指定模型
python scripts/run_runner_agent_pipeline.py --backend api --model qwen-turbo --mock
```

##### 保存配置

```bash
# 保存生成的配置到JSON文件
python scripts/run_runner_agent_pipeline.py --mock --save-config
```

生成的配置会保存到：`results/{timestamp}/generated_config.json`

#### 完整流程示例

##### 1. 启动测试

```bash
python scripts/run_runner_agent_pipeline.py --mock "率定GR4J模型，流域01013500"
```

##### 2. 输出示例

```
╔══════════════════════════════════════════════════════════════╗
║            HydroAgent 完整管道测试                           ║
║     Intent → Config → Runner (3-Agent Pipeline)             ║
╚══════════════════════════════════════════════════════════════╝
日志文件: D:\project\Agent\HydroAgent\logs\full_pipeline_20251120_230000.log

✅ LLM后端: Ollama (qwen3:8b)

══════════════════════════════════════════════════════════════
查询: 率定GR4J模型，流域01013500
LLM: Ollama (qwen3:8b)
模式: Mock (不调用真实hydromodel)
══════════════════════════════════════════════════════════════

✅ Agents初始化完成

🔍 [Step 1/3] IntentAgent - 分析用户意图...
✅ Intent分析完成 (15.2s)

意图摘要:
  意图: CALIBRATION
  模型: gr4j
  流域: 01013500
  算法: SCE_UA

⚙️  [Step 2/3] ConfigAgent - 生成hydromodel配置...
✅ Config生成完成 (0.3s)

配置摘要:
=== Configuration Summary ===

Model: gr4j
Basins: 01013500
Training: 2000-01-01 to 2010-12-31
Testing: 2011-01-01 to 2015-12-31
Algorithm: SCE_UA
  - Complexes (ngs): 500
  - Evolution steps (rep): 3000
Objective: RMSE

============================

🚀 [Step 3/3] RunnerAgent - 执行hydromodel...
   使用Mock模式（模拟执行）

✅ 执行完成 (0.1s)

执行结果:
  性能指标:
    NSE: 0.85
    RMSE: 2.5
    KGE: 0.82
  最优参数:
    x1: 350.0
    x2: 0.5
    x3: 100.0
    x4: 2.0
  输出文件:
    - results/calibrated_params.json

══════════════════════════════════════════════════════════════
✅ 完整管道执行成功!
══════════════════════════════════════════════════════════════

时间统计:
  Intent分析: 15.2s
  Config生成: 0.3s
  Runner执行: 0.1s
  总计时间:   15.6s

工作目录: D:\project\Agent\HydroAgent\results\20251120_230000
日志文件: D:\project\Agent\HydroAgent\logs\full_pipeline_20251120_230000.log
══════════════════════════════════════════════════════════════
```

#### 命令行参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `query` | str | "率定GR4J模型，流域01013500" | 用户查询 |
| `--backend` | str | ollama | LLM后端 (ollama/openai/api) |
| `--model` | str | None | 模型名称 |
| `--mock` | flag | False | 使用Mock模式 |
| `--save-config` | flag | False | 保存配置到文件 |

---

## 三、Mock模式 vs Real模式

### Mock模式（推荐用于测试）

**优点**:
- ✅ 不需要安装hydromodel
- ✅ 不需要下载数据
- ✅ 执行速度快（<1秒）
- ✅ 结果可预测，便于测试

**使用场景**:
- Agent逻辑测试
- 管道对接测试
- CI/CD自动化测试
- 开发调试

**启用方式**:
```bash
python scripts/run_runner_agent_pipeline.py --mock
python test/test_runner_agent.py  # 自动使用Mock
```

### Real模式（用于实际执行）

**要求**:
- ✅ 已安装hydromodel
- ✅ 已下载数据（CAMELS等）
- ✅ 配置了~/hydro_setting.yml

**使用场景**:
- 实际模型率定
- 真实性能评估
- 生产环境使用

**启用方式**:
```bash
# 不加--mock参数即为Real模式
python scripts/run_runner_agent_pipeline.py "率定GR4J模型，流域01013500"
```

**注意**: Real模式可能需要较长时间（几分钟到几小时，取决于模型复杂度）

---

## 四、数据流

### 完整的三段管道数据流

```
┌─────────────────────────────────────────────────────────────┐
│ 1. IntentAgent                                              │
├─────────────────────────────────────────────────────────────┤
│ 输入: "率定GR4J模型，流域01013500"                          │
│                                                             │
│ 输出:                                                       │
│ {                                                           │
│   "success": True,                                          │
│   "intent_result": {                                        │
│     "intent": "calibration",                                │
│     "model_name": "gr4j",                                   │
│     "basin_id": "01013500",                                 │
│     "time_period": {...},                                   │
│     "algorithm": "SCE_UA"                                   │
│   }                                                         │
│ }                                                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. ConfigAgent                                              │
├─────────────────────────────────────────────────────────────┤
│ 输入: IntentAgent的输出                                     │
│                                                             │
│ 处理:                                                       │
│ - 获取默认配置                                              │
│ - 根据intent修改字段                                        │
│ - 调整算法参数                                              │
│ - 生成实验名称                                              │
│                                                             │
│ 输出:                                                       │
│ {                                                           │
│   "success": True,                                          │
│   "config": {                                               │
│     "data_cfgs": {                                          │
│       "basin_ids": ["01013500"],                            │
│       "train_period": [...],                                │
│       ...                                                   │
│     },                                                      │
│     "model_cfgs": {                                         │
│       "model_name": "gr4j",                                 │
│       ...                                                   │
│     },                                                      │
│     "training_cfgs": {                                      │
│       "algorithm_name": "SCE_UA",                           │
│       "algorithm_params": {                                 │
│         "ngs": 500,                                         │
│         "rep": 3000                                         │
│       },                                                    │
│       ...                                                   │
│     }                                                       │
│   }                                                         │
│ }                                                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. RunnerAgent                                              │
├─────────────────────────────────────────────────────────────┤
│ 输入: ConfigAgent的输出                                     │
│                                                             │
│ 处理:                                                       │
│ - 调用 hydromodel.calibrate(config)                         │
│ - 捕获stdout/stderr                                         │
│ - 解析执行结果                                              │
│                                                             │
│ 输出:                                                       │
│ {                                                           │
│   "success": True,                                          │
│   "mode": "calibrate",                                      │
│   "result": {                                               │
│     "status": "success",                                    │
│     "metrics": {                                            │
│       "NSE": 0.85,                                          │
│       "RMSE": 2.5,                                          │
│       "KGE": 0.82                                           │
│     },                                                      │
│     "best_params": {                                        │
│       "x1": 350.0,                                          │
│       "x2": 0.5,                                            │
│       "x3": 100.0,                                          │
│       "x4": 2.0                                             │
│     },                                                      │
│     "output_files": [...]                                   │
│   },                                                        │
│   "execution_log": {                                        │
│     "stdout": "...",                                        │
│     "stderr": "..."                                         │
│   }                                                         │
│ }                                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 五、常见问题

### Q1: Mock模式和Real模式有什么区别？

**A**:

**Mock模式**:
- 使用`unittest.mock`模拟hydromodel函数
- 返回预设的模拟结果
- 不需要hydromodel和数据
- 执行速度快（<1秒）

**Real模式**:
- 真正调用hydromodel API
- 返回真实的率定/评估结果
- 需要hydromodel和数据
- 执行时间长（分钟到小时）

### Q2: 如何判断是否需要使用Mock模式？

**A**: 以下情况使用Mock模式：
- ✅ 测试Agent逻辑
- ✅ 测试管道对接
- ✅ CI/CD自动化
- ✅ 快速验证修改
- ✅ hydromodel未安装

以下情况使用Real模式：
- 真实模型率定
- 实际性能评估
- 生产环境使用

### Q3: RunnerAgent如何接收配置？

**A**: 直接接收config dict，无需文件

```python
# ConfigAgent输出
config_result = {
    "success": True,
    "config": {...}  # dict格式
}

# RunnerAgent接收
runner_result = runner_agent.process(config_result)
```

**不需要**:
- ❌ 保存配置到YAML文件
- ❌ 传递文件路径
- ❌ 读取配置文件

### Q4: 如何查看执行日志？

**A**: 三种方式

1. **控制台输出**: 直接显示
2. **日志文件**: `logs/full_pipeline_YYYYMMDD_HHMMSS.log`
3. **execution_log**: RunnerAgent返回值中的`execution_log`字段

```python
result = runner_agent.process(config)
print(result["execution_log"]["stdout"])  # 标准输出
print(result["execution_log"]["stderr"])  # 错误输出
```

### Q5: 执行失败时如何调试？

**A**: 检查以下内容

1. **查看错误信息**:
```python
if not result["success"]:
    print(result["error"])        # 错误描述
    print(result["traceback"])    # 完整traceback
```

2. **查看日志文件**: `logs/` 目录下的最新日志

3. **检查配置**: 使用 `--save-config` 保存配置检查

4. **逐步调试**:
```bash
# 先测试Intent
python test/test_intent_agent.py

# 再测试Config
python test/test_config_agent.py

# 最后测试Runner
python test/test_runner_agent.py
```

### Q6: 如何添加新的性能指标？

**A**: 修改`_parse_calibration_result()`方法

hydromodel返回的指标会自动提取，无需修改RunnerAgent代码。

如需自定义解析逻辑：

```python
# 在 runner_agent.py 中
def _parse_calibration_result(self, result):
    parsed = {...}

    # 添加自定义指标提取逻辑
    if "custom_metric" in result:
        parsed["custom_metric"] = result["custom_metric"]

    return parsed
```

### Q7: 支持哪些执行模式？

**A**: 三种模式

| 模式 | Intent | 对应函数 |
|------|--------|---------|
| 率定 | calibration | `calibrate()` |
| 评估 | evaluation | `evaluate()` |
| 模拟 | simulation | `calibrate()` (预测模式) |

自动根据Intent结果选择执行模式。

### Q8: 如何设置执行超时？

**A**: 在初始化时设置

```python
runner_agent = RunnerAgent(
    llm_interface=llm,
    workspace_dir=workspace_dir,
    timeout=7200  # 2小时
)
```

默认超时: 3600秒（1小时）

---

## 六、性能指标说明

### 常见性能指标

| 指标 | 全称 | 范围 | 最优值 | 说明 |
|------|------|------|--------|------|
| NSE | Nash-Sutcliffe Efficiency | (-∞, 1] | 1 | 模拟效果，>0.5为可接受 |
| RMSE | Root Mean Square Error | [0, +∞) | 0 | 均方根误差，越小越好 |
| KGE | Kling-Gupta Efficiency | (-∞, 1] | 1 | 综合指标，>0.5为良好 |
| PBIAS | Percent Bias | (-∞, +∞) | 0 | 百分比偏差，<±25%为良好 |

### 指标解读

**NSE (纳什效率系数)**:
- > 0.75: 优秀
- 0.65 - 0.75: 良好
- 0.50 - 0.65: 可接受
- < 0.50: 不满意

**PBIAS (偏差百分比)**:
- < ±10%: 非常好
- ±10% - ±15%: 良好
- ±15% - ±25%: 满意
- > ±25%: 不满意

---

## 七、下一步

### 已完成
- ✅ IntentAgent 测试
- ✅ ConfigAgent 测试
- ✅ RunnerAgent 测试
- ✅ Intent → Config → Runner 管道测试

### 待实现
- ⏳ DeveloperAgent（结果分析）
- ⏳ Orchestrator（完整编排）
- ⏳ 多轮对话支持
- ⏳ 端到端集成测试

---

**文档版本**: v1.0
**最后更新**: 2025-11-20
**作者**: zhuanglaihong & Claude
