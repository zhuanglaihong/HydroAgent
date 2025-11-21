# ConfigAgent 测试说明文档

## 概述

本文档介绍 ConfigAgent（配置生成智能体）的测试方法和使用说明。ConfigAgent 负责接收 IntentAgent 的输出，生成 hydromodel API 所需的配置字典。

**关键特性**:
- 基于用户意图修改默认配置
- 智能调整算法参数（根据模型复杂度）
- 自动填充缺失字段
- 完整的配置验证
- 返回 dict 格式（不生成文件）

## 测试文件结构

```
HydroAgent/
├── test/
│   └── test_config_agent.py              # ConfigAgent单元测试
├── scripts/
│   ├── test_config_agent_interactive.py  # ConfigAgent交互测试
│   ├── run_agent_interactive.py          # Intent→Config管道交互测试
│   └── test_agent_pipeline.py            # Intent→Config管道快速测试
└── docs/
    └── tests/
        └── test_config_agent.md          # 本文档
```

## 一、单元测试

### 文件：`test/test_config_agent.py`

#### 测试用例

| # | 测试名称 | 描述 | 验证点 |
|---|---------|------|--------|
| 1 | 基础功能测试 | GR4J模型率定（完整配置） | 配置生成、字段映射、算法参数 |
| 2 | 复杂模型测试 | XAJ模型率定（15参数） | 复杂模型参数自动调整 |
| 3 | 缺失信息处理 | 缺少时间段的配置 | 默认值填充机制 |
| 4 | 评估任务配置 | GR6J模型评估 | 评估任务配置生成 |
| 5 | 配置验证功能 | 最小配置测试 | 配置结构验证 |
| 6 | 实验名称生成 | 自动生成实验名 | 命名规范验证 |

#### 运行方式

```bash
# 进入项目根目录
cd D:/project/Agent/HydroAgent

# 激活虚拟环境
.venv\Scripts\activate

# 运行测试
python test/test_config_agent.py
```

#### 预期输出

```
======================================================================
ConfigAgent 单元测试套件
======================================================================
日志文件: D:\project\Agent\HydroAgent\logs\test_config_agent_20251120_223000.log

======================================================================
Test Case 1: 基础功能测试 - GR4J模型率定
======================================================================
✅ 基础功能测试通过

配置摘要:
  模型: gr4j
  流域: ['01013500']
  训练期: ['2000-01-01', '2010-12-31']
  测试期: ['2011-01-01', '2015-12-31']
  算法: SCE_UA
  算法参数: ngs=500, rep=3000
  输出目录: D:\project\Agent\HydroAgent\results\test_config_agent
  实验名称: gr4j_SCE_UA_20251120_223000

... (其他测试用例)

======================================================================
测试总结
======================================================================
1. ✅ PASS - 基础功能测试
2. ✅ PASS - 复杂模型测试
3. ✅ PASS - 缺失信息处理
4. ✅ PASS - 评估任务配置
5. ✅ PASS - 配置验证功能
6. ✅ PASS - 实验名称生成

总计: 6/6 通过
成功率: 100.0%
======================================================================
```

#### 测试详解

##### 测试1: 基础功能测试

**输入** (模拟IntentAgent输出):
```python
{
    "success": True,
    "intent_result": {
        "intent": "calibration",
        "model_name": "gr4j",
        "basin_id": "01013500",
        "time_period": {
            "train": ["2000-01-01", "2010-12-31"],
            "test": ["2011-01-01", "2015-12-31"]
        },
        "algorithm": "SCE_UA",
        "missing_info": [],
        "clarifications_needed": [],
        "confidence": 0.95
    }
}
```

**验证点**:
- ✅ 模型名称映射正确: `gr4j`
- ✅ 流域ID转换为列表: `["01013500"]`
- ✅ 时间段正确映射到 `data_cfgs`
- ✅ 算法参数根据GR4J复杂度调整: `ngs=500, rep=3000`
- ✅ 自动生成实验名称和输出目录

##### 测试2: 复杂模型测试 (XAJ)

**关键验证**: XAJ有15个参数，算法参数应该自动调整为更多迭代
- ✅ `ngs=1500` (vs GR4J的500)
- ✅ `rep=8000` (vs GR4J的3000)

**参数调整规则**:
```python
if num_params <= 5:        # 简单模型 (GR4J, GR5J)
    ngs=500, rep=3000
elif num_params <= 10:     # 中等模型 (GR6J)
    ngs=1000, rep=5000
else:                      # 复杂模型 (XAJ)
    ngs=1500, rep=8000
```

##### 测试3: 缺失信息处理

**场景**: Intent结果中缺少时间段信息

**验证点**:
- ✅ 使用默认训练期和测试期
- ✅ 配置仍然有效
- ✅ 不会因为缺失信息而失败

##### 测试6: 实验名称生成

**格式**: `{model}_{algorithm}_{timestamp}`

**示例**: `gr4j_SCE_UA_20251120_223000`

**验证**:
- ✅ 包含模型名称
- ✅ 包含算法名称
- ✅ 包含时间戳（唯一性）

---

## 二、ConfigAgent 交互式测试

### 文件：`scripts/test_config_agent_interactive.py`

#### 功能说明

这是一个独立的 ConfigAgent 测试工具，提供预设的 Intent 结果供测试。

**主要功能**:
1. 选择预设的 Intent 结果
2. 输入自定义 JSON 格式的 Intent
3. 查看配置摘要
4. 查看详细配置
5. 保存配置到 JSON 文件

#### 运行方式

```bash
python scripts/test_config_agent_interactive.py
```

#### 使用流程

##### 1. 启动程序

```
╔══════════════════════════════════════════════════════════════╗
║              ConfigAgent 交互式测试工具                      ║
║           测试配置生成智能体的参数调整和验证功能              ║
╚══════════════════════════════════════════════════════════════╝

预设Intent结果:
────────────────────────────────────────────────────────────────
1. GR4J模型率定（完整配置）
   模型: gr4j, 流域: 01013500, 意图: calibration
2. XAJ模型率定（复杂模型）
   模型: xaj, 流域: camels_11532500, 意图: calibration
3. GR5J模型（缺少时间段）
   模型: gr5j, 流域: 01022500, 意图: calibration
4. GR6J模型评估
   模型: gr6j, 流域: 01030500, 意图: evaluation
5. 最小配置（仅模型名）
   模型: gr1y, 流域: N/A, 意图: calibration
0. 自定义Intent结果（输入JSON）
q. 退出
────────────────────────────────────────────────────────────────

请选择 (0-5, q退出):
```

##### 2. 选择测试用例

输入 `1` 选择 "GR4J模型率定"

##### 3. 查看Intent结果

```
【Intent Result】
────────────────────────────────────────────────────────────
意图: CALIBRATION
模型: gr4j
流域: 01013500
算法: SCE_UA
时间段:
  训练: 2000-01-01 到 2010-12-31
  测试: 2011-01-01 到 2015-12-31
────────────────────────────────────────────────────────────
```

##### 4. 查看配置结果

```
【Config Generation Result】
════════════════════════════════════════════════════════════
状态: ✅ 成功
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
════════════════════════════════════════════════════════════

显示详细配置？(y/n):
```

##### 5. 查看详细配置 (可选)

输入 `y` 查看完整配置：

```
【详细配置】
────────────────────────────────────────────────────────────
数据配置 (data_cfgs):
  数据源类型: camels_us
  流域列表: ['01013500']
  训练期: ['2000-01-01', '2010-12-31']
  测试期: ['2011-01-01', '2015-12-31']
  预热期长度: 365 天
  变量: precipitation, potential_evapotranspiration, streamflow

模型配置 (model_cfgs):
  模型名称: gr4j
  模型参数: {'source_type': 'sources', 'source_book': 'HF', 'kernel_size': 15}

训练配置 (training_cfgs):
  算法名称: SCE_UA
  算法参数:
    rep: 3000
    ngs: 500
  损失函数: RMSE
  输出目录: D:\project\Agent\HydroAgent\results\...
  实验名称: gr4j_SCE_UA_20251120_223000
  随机种子: 1234

评估配置 (evaluation_cfgs):
  评估指标: NSE, RMSE, KGE, PBIAS
  保存结果: True
  绘制结果: True
────────────────────────────────────────────────────────────
```

##### 6. 保存配置 (可选)

```
保存配置到JSON文件？(y/n): y
✅ 配置已保存到: D:\project\Agent\HydroAgent\results\test_config_agent\config_20251120_223000.json
```

#### 自定义Intent输入 (选项0)

选择 `0` 可以输入自定义JSON格式的Intent结果：

```
请选择 (0-5, q退出): 0

请输入Intent结果（JSON格式）:
示例:
{
  "intent": "calibration",
  "model_name": "gr4j",
  "basin_id": "01013500",
  ...
}

输入JSON（可以多行，以空行结束）:
{
  "intent": "calibration",
  "model_name": "gr4j",
  "basin_id": "01013500",
  "time_period": {
    "train": ["2000-01-01", "2010-12-31"],
    "test": ["2011-01-01", "2015-12-31"]
  },
  "algorithm": "SCE_UA",
  "missing_info": [],
  "clarifications_needed": [],
  "confidence": 0.95
}
[按Enter输入空行]
```

---

## 三、Intent → Config 管道测试

### 完整管道交互测试

#### 文件：`scripts/run_agent_interactive.py`

这是最全面的测试工具，测试完整的 **IntentAgent → ConfigAgent** 管道。

#### 运行方式

```bash
# 使用 Ollama（默认）
python scripts/run_agent_interactive.py

# 使用通义千问 API（从配置文件读取）
python scripts/run_agent_interactive.py --backend api

# 使用通义千问 API + 指定参数
python scripts/run_agent_interactive.py \
  --backend api \
  --api-key sk-your-key \
  --base-url https://dashscope.aliyuncs.com/compatible-mode/v1
```

#### 使用流程

##### 1. 启动界面

```
╔══════════════════════════════════════════════════════════════╗
║                   HydroAgent Interactive                     ║
║                   Intent → Config → Runner                   ║
╚══════════════════════════════════════════════════════════════╝
Log file: D:\project\Agent\HydroAgent\logs\interactive_agent_20251120_223000.log

Initializing agents...
✅ LLM backend: Ollama (qwen3:8b)
✅ IntentAgent initialized
✅ ConfigAgent initialized
✅ Workspace: D:\project\Agent\HydroAgent\results\20251120_223000

════════════════════════════════════════════════════════════════
Ready! Enter your queries below.
Commands:
  'quit' or 'exit' - Exit the program
  'clear' - Clear screen
  'help' - Show help
════════════════════════════════════════════════════════════════

[Query #1]
You:
```

##### 2. 输入查询

```
You: 率定GR4J模型，流域01013500

🔍 [Step 1/2] Analyzing intent...
```

##### 3. 查看Intent结果

```
═══════════════════════════════════════════════════════════════
【Intent Analysis Result】
───────────────────────────────────────────────────────────────
Status: ✅ SUCCESS
Time: 15.2s

Intent:     CALIBRATION
Model:      gr4j
Basin:      01013500
Algorithm:  SCE_UA
Confidence: 0.95

Time Period:
  Train: 2000-01-01 to 2010-12-31
  Test:  2011-01-01 to 2015-12-31

═══════════════════════════════════════════════════════════════
```

##### 4. 查看Config结果

```
⚙️  [Step 2/2] Generating configuration...

═══════════════════════════════════════════════════════════════
【Config Generation Result】
───────────────────────────────────────────────────────────────
Status: ✅ SUCCESS
Time: 0.3s

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
═══════════════════════════════════════════════════════════════

Show full config dict? (y/n):
```

##### 5. 查看完整配置 (可选)

```
Show full config dict? (y/n): y

──────────────────────────────────────────────────────────────
【Config Dict (JSON)】
──────────────────────────────────────────────────────────────
{
  "data_cfgs": {
    "data_source_type": "camels_us",
    "basin_ids": ["01013500"],
    "train_period": ["2000-01-01", "2010-12-31"],
    ...
  },
  "model_cfgs": {
    "model_name": "gr4j",
    ...
  },
  ...
}
──────────────────────────────────────────────────────────────

✅ Total time: 15.5s
   - Intent: 15.2s
   - Config: 0.3s

✅ Ready for RunnerAgent!
   Config can be passed directly to hydromodel.calibrate()
```

##### 6. 继续测试

```
[Query #2]
You: 评估XAJ模型的性能

... (重复流程)
```

#### 命令说明

交互模式支持的命令：

| 命令 | 说明 |
|------|------|
| `quit` / `exit` / `q` | 退出程序 |
| `clear` | 清屏 |
| `help` | 显示帮助信息 |

---

### 快速管道测试

#### 文件：`scripts/test_agent_pipeline.py`

用于快速测试单个查询的完整管道。

#### 运行方式

```bash
# 运行默认测试用例
python scripts/test_agent_pipeline.py

# 测试自定义查询
python scripts/test_agent_pipeline.py "率定GR4J模型，流域01013500"

# 使用API后端
python scripts/test_agent_pipeline.py --backend api "Calibrate XAJ model"
```

#### 默认测试用例

运行 `python scripts/test_agent_pipeline.py` 会测试以下3个查询：

1. **中文率定查询**: "率定GR4J模型，流域01013500"
2. **英文率定查询**: "Calibrate XAJ model for basin camels_11532500 from 2000 to 2010"
3. **中文评估查询**: "评估GR5J模型的性能"

#### 输出示例

```
======================================================================
HydroAgent Pipeline Test: IntentAgent → ConfigAgent
======================================================================

✅ LLM backend initialized: Ollama (qwen3:8b)

======================================================================
Test 1/3
======================================================================

======================================================================
Testing Query: 率定GR4J模型，流域01013500
LLM Backend: Ollama (qwen3:8b)
======================================================================

[1/3] Initializing agents...
✅ Agents initialized

[2/3] IntentAgent analyzing query...
✅ Intent analysis complete (15.2s)

Intent Result:
{
  "intent": "calibration",
  "model_name": "gr4j",
  "basin_id": "01013500",
  ...
}

[3/3] ConfigAgent generating config...
✅ Config generation complete (0.3s)

Config Summary:
=== Configuration Summary ===
...
============================

Config Overview:
  Model: gr4j
  Basins: ['01013500']
  Train Period: ['2000-01-01', '2010-12-31']
  Algorithm: SCE_UA
  Output Dir: D:\project\Agent\HydroAgent\results\test

======================================================================
✅ Pipeline Complete! Config ready for RunnerAgent.
======================================================================

Press Enter to continue to next test...
```

#### 总结报告

```
======================================================================
Test Summary
======================================================================
1. ✅ PASS - 率定GR4J模型，流域01013500
2. ✅ PASS - Calibrate XAJ model for basin camels_11532500...
3. ✅ PASS - 评估GR5J模型的性能

Total: 3/3 passed
======================================================================
```

---

## 四、常见问题

### Q1: 如何切换LLM后端？

**A**: 使用 `--backend` 参数

```bash
# 使用Ollama（默认）
python scripts/run_agent_interactive.py

# 使用通义千问API
python scripts/run_agent_interactive.py --backend api
```

**配置文件自动读取**: API key 和 base URL 会从以下位置读取（按优先级）：
1. 命令行参数 (`--api-key`, `--base-url`)
2. `configs/definitions_private.py`
3. 环境变量 `OPENAI_API_KEY`

### Q2: 如何验证配置是否正确？

**A**: 三种验证方式

1. **单元测试验证**:
   ```bash
   python test/test_config_agent.py
   ```

2. **查看配置摘要**: 运行交互式脚本时显示的 Config Summary

3. **查看详细配置**: 在交互模式中选择 `y` 显示完整配置

### Q3: ConfigAgent需要LLM吗？

**A**: 当前版本不需要

ConfigAgent 的核心逻辑是纯Python代码，基于规则修改配置dict。虽然初始化时需要传入 LLM interface，但实际处理过程不调用LLM。

未来版本可能会添加LLM辅助功能（如智能参数推荐）。

### Q4: 如何调整算法参数？

**A**: 自动调整机制

ConfigAgent 会根据模型复杂度自动调整 SCE-UA 算法参数：

```python
# 在 _adjust_algorithm_params() 中
if num_params <= 5:        # 简单模型
    ngs=500, rep=3000
elif num_params <= 10:     # 中等模型
    ngs=1000, rep=5000
else:                      # 复杂模型
    ngs=1500, rep=8000
```

如需手动调整，可以在 ConfigAgent 处理后修改返回的 config dict。

### Q5: 配置缺失字段怎么办？

**A**: 使用默认值

ConfigAgent 会智能填充缺失字段：
- 缺少模型名 → 使用默认模型
- 缺少流域 → 使用默认流域
- 缺少时间段 → 使用默认时间段

测试用例3演示了这个功能。

### Q6: 日志文件在哪里？

**A**: 所有测试都会在 `logs/` 目录生成日志文件

格式: `logs/test_config_agent_YYYYMMDD_HHMMSS.log`

示例:
```
logs/
├── test_config_agent_20251120_223000.log
├── interactive_agent_20251120_223100.log
└── ...
```

---

## 五、配置字段映射

### Intent Result → Config Dict

| Intent字段 | Config字段 | 说明 |
|-----------|-----------|------|
| `model_name` | `model_cfgs.model_name` | 模型名称 |
| `basin_id` | `data_cfgs.basin_ids[0]` | 流域ID（转为列表） |
| `time_period.train` | `data_cfgs.train_period` | 训练时段 |
| `time_period.test` | `data_cfgs.test_period` | 测试时段 |
| `algorithm` | `training_cfgs.algorithm_name` | 算法名称 |
| - | `training_cfgs.algorithm_params` | 根据模型自动调整 |
| - | `training_cfgs.experiment_name` | 自动生成 |
| - | `training_cfgs.output_dir` | 使用workspace_dir |

### 模型复杂度映射

| 模型 | 参数数量 | ngs | rep |
|------|---------|-----|-----|
| gr4j | 4 | 500 | 3000 |
| gr5j | 5 | 500 | 3000 |
| gr6j | 6 | 1000 | 5000 |
| xaj | 15 | 1500 | 8000 |
| xaj_mz | 15 | 1500 | 8000 |
| gr1y | 1 | 500 | 3000 |
| gr2m | 2 | 500 | 3000 |

---

## 六、下一步

### 已完成
- ✅ IntentAgent 测试
- ✅ ConfigAgent 测试
- ✅ Intent → Config 管道测试

### 进行中
- 🔄 RunnerAgent 开发
- 🔄 完整的 Intent → Config → Runner 管道

### 待实现
- ⏳ DeveloperAgent
- ⏳ Orchestrator 完整编排

---

**文档版本**: v1.0
**最后更新**: 2025-11-20
**作者**: zhuanglaihong & Claude
