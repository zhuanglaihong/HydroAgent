# DeveloperAgent 测试说明文档

## 概述

本文档介绍 DeveloperAgent（结果分析智能体）的测试方法和使用说明。DeveloperAgent 负责接收 RunnerAgent 的执行结果，进行详细分析并提供改进建议。

**关键特性**:
- 自动分析 RunnerAgent 输出
- 评估模型性能质量（优秀/良好/可接受/不满意）
- 提取性能指标和最优参数
- 生成改进建议
- 执行日志摘要
- 支持代码生成（Experiment 3）

## 测试文件结构

```
HydroAgent/
├── test/
│   └── test_developer_agent.py              # DeveloperAgent单元测试
├── scripts/
│   └── run_developer_agent_pipeline.py           # 完整4-Agent管道测试
└── docs/
    └── tests/
        └── test_developer_agent.md           # 本文档
```

## 一、单元测试

### 文件：`test/test_developer_agent.py`

#### 测试用例

| # | 测试名称 | 描述 | 验证点 |
|---|---------|------|--------|
| 1 | DeveloperAgent初始化 | 初始化测试 | 参数设置、workspace配置 |
| 2 | 分析率定结果 | 分析calibration结果 | 质量评估、指标提取 |
| 3 | 分析评估结果 | 分析evaluation结果 | 性能分析、指标提取 |
| 4 | 处理执行失败 | 处理RunnerAgent失败 | 错误处理机制 |
| 5 | 生成改进建议 | 低NSE场景建议 | 建议生成逻辑 |
| 6 | 执行日志摘要 | 日志分析功能 | 日志统计准确性 |

#### 运行方式

```bash
# 进入项目根目录
cd D:/project/Agent/HydroAgent

# 激活虚拟环境
.venv\Scripts\activate

# 运行测试
python test/test_developer_agent.py
```

#### 预期输出

```
======================================================================
DeveloperAgent 单元测试套件
======================================================================
日志文件: D:\project\Agent\HydroAgent\logs\test_developer_agent_20251121_110000.log

======================================================================
Test Case 1: DeveloperAgent 初始化测试
======================================================================
✅ DeveloperAgent 初始化测试通过

======================================================================
Test Case 2: 分析率定结果测试
======================================================================
✅ 率定结果分析测试通过
   质量评估: 优秀 (Excellent)
   NSE: 0.85
   参数数量: 4

... (其他测试用例)

======================================================================
测试总结
======================================================================
1. ✅ PASS - DeveloperAgent初始化
2. ✅ PASS - 分析率定结果
3. ✅ PASS - 分析评估结果
4. ✅ PASS - 处理执行失败
5. ✅ PASS - 生成改进建议
6. ✅ PASS - 执行日志摘要

总计: 6/6 通过
成功率: 100.0%
======================================================================
```

#### 测试详解

##### 测试1: DeveloperAgent初始化

**验证点**:
- ✅ Agent名称正确
- ✅ workspace_dir设置正确
- ✅ enable_code_gen参数配置正确

##### 测试2: 分析率定结果

**核心功能**: 自动分析RunnerAgent的率定输出

**Mock输入**:
```python
{
    "success": True,
    "mode": "calibrate",
    "result": {
        "metrics": {"NSE": 0.85, "RMSE": 2.5, "KGE": 0.82},
        "best_params": {"x1": 350.0, "x2": 0.5, ...}
    }
}
```

**验证点**:
- ✅ 接收RunnerAgent输出
- ✅ 提取性能指标
- ✅ 质量评估正确（NSE>0.75 → 优秀）
- ✅ 提取最优参数

##### 测试3: 分析评估结果

**验证点**:
- ✅ 识别evaluate模式
- ✅ 提取performance指标
- ✅ 质量评估准确

##### 测试4: 处理执行失败

**场景**: RunnerAgent执行失败

**验证点**:
- ✅ 捕获RunnerAgent错误
- ✅ 返回success=False
- ✅ 包含runner_error信息

##### 测试5: 生成改进建议

**场景**: NSE较低（0.55）、PBIAS偏高（30%）

**验证点**:
- ✅ 自动检测性能不佳
- ✅ 生成改进建议
- ✅ 建议内容合理

**示例建议**:
```
1. NSE较低，建议增加训练时期长度或调整参数范围
2. PBIAS=30.00%偏高，模型存在系统性偏差
```

##### 测试6: 执行日志摘要

**功能**: 总结stdout/stderr输出

**验证点**:
- ✅ 统计stdout行数
- ✅ 统计stderr行数
- ✅ 检测是否有错误

---

## 二、完整4-Agent管道测试

### 文件：`scripts/run_developer_agent_pipeline.py`

#### 功能说明

这是最完整的测试工具，测试 **IntentAgent → ConfigAgent → RunnerAgent → DeveloperAgent** 四段管道。

**主要功能**:
1. 从用户查询到结果分析的完整流程
2. 支持Mock模式（不需要hydromodel）
3. 支持Real模式（调用真实hydromodel）
4. 显示每一步的耗时
5. 自动生成分析报告
6. 可选保存配置和分析结果

#### 运行方式

##### 基础用法

```bash
# Mock模式 - 推荐用于测试（不需要hydromodel）
python scripts/run_developer_agent_pipeline.py --mock

# 真实模式 - 调用真实hydromodel（需要hydromodel已安装）
python scripts/run_developer_agent_pipeline.py
```

##### 自定义查询

```bash
# 自定义查询 + Mock模式
python scripts/run_developer_agent_pipeline.py --mock "评估XAJ模型在流域11532500的性能"

# 多个查询测试
python scripts/run_developer_agent_pipeline.py --mock "率定GR4J模型"
python scripts/run_developer_agent_pipeline.py --mock "评估GR5J模型"
```

##### 使用API后端

```bash
# 使用通义千问API + Mock模式
python scripts/run_developer_agent_pipeline.py --backend api --mock

# 指定模型
python scripts/run_developer_agent_pipeline.py --backend api --model qwen-turbo --mock
```

##### 保存结果

```bash
# 保存配置和分析结果
python scripts/run_developer_agent_pipeline.py --mock --save-config --save-analysis

# 隐藏进度条（后台模式）
python scripts/run_developer_agent_pipeline.py --mock --no-progress
```

生成的文件会保存到：`results/{timestamp}/`
- `generated_config.json` - 生成的配置
- `analysis_report.json` - 分析报告

#### 完整流程示例

##### 1. 启动测试

```bash
python scripts/run_developer_agent_pipeline.py --mock "率定GR4J模型，流域01013500"
```

##### 2. 输出示例

```
╔══════════════════════════════════════════════════════════════╗
║            HydroAgent 完整4-Agent管道测试                    ║
║     Intent → Config → Runner → Developer                    ║
╚══════════════════════════════════════════════════════════════╝
日志文件: D:\project\Agent\HydroAgent\logs\full_agent_pipeline_20251121_110000.log

✅ LLM后端: 通义千问 API (qwen-turbo)

✅ 4个Agents初始化完成

🔍 [Step 1/4] IntentAgent - 分析用户意图...
✅ Intent分析完成 (15.2s)

意图摘要:
  意图: CALIBRATION
  模型: gr4j
  流域: 01013500
  算法: SCE_UA

⚙️  [Step 2/4] ConfigAgent - 生成hydromodel配置...
✅ Config生成完成 (0.3s)

配置摘要:
=== Configuration Summary ===
Model: gr4j
Basins: 01013500
Training: 2000-01-01 to 2010-12-31
Testing: 2011-01-01 to 2015-12-31
Algorithm: SCE_UA
============================

🚀 [Step 3/4] RunnerAgent - 执行hydromodel...
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

📊 [Step 4/4] DeveloperAgent - 分析结果...
✅ 分析完成 (0.2s)

======================================================================
分析报告:
======================================================================

📈 质量评估: 优秀 (Excellent)

🎯 性能指标:
  NSE: 0.85
  RMSE: 2.5
  KGE: 0.82
  PBIAS: 5.2

🔧 最优参数: 4 个

💡 改进建议:
  (NSE > 0.75，无需改进建议)

📝 执行日志:
  输出行数: 3
  错误行数: 0

======================================================================

======================================================================
✅ 完整4-Agent管道执行成功!
======================================================================

时间统计:
  Intent分析: 15.2s
  Config生成: 0.3s
  Runner执行: 0.1s
  Developer分析: 0.2s
  总计时间:   15.8s

工作目录: D:\project\Agent\HydroAgent\results\20251121_110000
日志文件: D:\project\Agent\HydroAgent\logs\full_agent_pipeline_20251121_110000.log
======================================================================
```

#### 命令行参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `query` | str | "率定GR4J模型..." | 用户查询 |
| `--backend` | str | api | LLM后端 (ollama/openai/api) |
| `--model` | str | None | 模型名称 |
| `--mock` | flag | False | 使用Mock模式 |
| `--save-config` | flag | False | 保存配置到文件 |
| `--save-analysis` | flag | False | 保存分析报告到文件 |
| `--no-progress` | flag | False | 不显示hydromodel进度 |

---

## 三、数据流

### 完整的四段管道数据流

```
┌─────────────────────────────────────────────────────────────┐
│ 1. IntentAgent                                              │
├─────────────────────────────────────────────────────────────┤
│ 输入: "率定GR4J模型，流域01013500"                          │
│ 输出: {"intent": "calibration", "model_name": "gr4j", ...} │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. ConfigAgent                                              │
├─────────────────────────────────────────────────────────────┤
│ 输入: IntentAgent的输出                                     │
│ 输出: {"config": {"data_cfgs": {...}, ...}}                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. RunnerAgent                                              │
├─────────────────────────────────────────────────────────────┤
│ 输入: ConfigAgent的输出                                     │
│ 处理: 调用 hydromodel.calibrate(config)                    │
│ 输出: {                                                     │
│   "success": True,                                          │
│   "mode": "calibrate",                                      │
│   "result": {                                               │
│     "metrics": {"NSE": 0.85, ...},                          │
│     "best_params": {...}                                    │
│   }                                                         │
│ }                                                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. DeveloperAgent                                           │
├─────────────────────────────────────────────────────────────┤
│ 输入: RunnerAgent的输出                                     │
│                                                             │
│ 处理:                                                       │
│ - 提取性能指标                                              │
│ - 评估质量（优秀/良好/可接受/不满意）                        │
│ - 生成改进建议                                              │
│ - 总结执行日志                                              │
│                                                             │
│ 输出: {                                                     │
│   "success": True,                                          │
│   "analysis": {                                             │
│     "quality": "优秀 (Excellent)",                          │
│     "metrics": {...},                                       │
│     "parameters": {...},                                    │
│     "recommendations": [...],                               │
│     "execution_summary": {...}                              │
│   }                                                         │
│ }                                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 四、质量评估标准

DeveloperAgent根据NSE值自动评估模型质量：

| NSE范围 | 质量评估 | 说明 |
|---------|---------|------|
| > 0.75 | 优秀 (Excellent) | 模型性能非常好 |
| 0.65 - 0.75 | 良好 (Good) | 模型性能良好 |
| 0.50 - 0.65 | 可接受 (Acceptable) | 模型性能可接受 |
| < 0.50 | 不满意 (Unsatisfactory) | 需要改进 |

### 其他评估指标

**PBIAS (偏差百分比)**:
- < ±10%: 非常好
- ±10% - ±15%: 良好
- ±15% - ±25%: 满意
- > ±25%: 不满意 → 会生成改进建议

**RMSE (均方根误差)**:
- 越小越好
- 相对值，需与实际数据范围比较

**KGE (Kling-Gupta效率系数)**:
- > 0.75: 优秀
- 0.65 - 0.75: 良好
- 0.50 - 0.65: 可接受
- < 0.50: 不满意

---

## 五、常见问题

### Q1: DeveloperAgent如何自动对接RunnerAgent？

**A**: DeveloperAgent的`process()`方法会自动检测输入类型：

```python
if "result" in input_data and isinstance(input_data.get("result"), dict):
    # RunnerAgent输出 - 自动分析模式
    return self._analyze_runner_output(input_data)
```

只需直接传入RunnerAgent的输出即可：
```python
runner_result = runner_agent.process(config)
developer_result = developer_agent.process(runner_result)  # 自动识别
```

### Q2: 如何查看详细的分析报告？

**A**: 使用`--save-analysis`参数保存JSON格式报告：

```bash
python scripts/run_developer_agent_pipeline.py --mock --save-analysis
```

报告位置：`results/{timestamp}/analysis_report.json`

### Q3: 改进建议是如何生成的？

**A**: 基于规则和LLM结合：

1. **规则检测**:
   - NSE < 0.65 → "建议增加训练时期长度"
   - |PBIAS| > 25% → "模型存在系统性偏差"

2. **LLM生成**（可选）:
   - 使用`_generate_recommendations()`方法
   - 基于完整分析结果生成深度建议

### Q4: 如何手动分析结果目录？

**A**: 使用手动配置模式：

```python
developer_agent.process({
    "mode": "analyze",
    "result_dir": Path("path/to/results")
})
```

### Q5: 代码生成功能如何使用？

**A**: 在初始化时启用，并使用`generate_code`模式：

```python
developer_agent = DeveloperAgent(
    llm_interface=llm,
    enable_code_gen=True  # 启用代码生成
)

result = developer_agent.process({
    "mode": "generate_code",
    "task_description": "创建一个参数敏感性分析脚本"
})
```

### Q6: 如何调试DeveloperAgent？

**A**: 查看日志文件：

```bash
# 查看最新日志
ls -lrt logs/ | tail -1

# 实时查看日志
tail -f logs/test_developer_agent_YYYYMMDD_HHMMSS.log
```

日志包含详细的分析过程和错误信息。

### Q7: 执行日志摘要包含哪些信息？

**A**:
- `stdout_lines`: 标准输出行数
- `stderr_lines`: 错误输出行数
- `has_errors`: 是否有错误（bool）

用于快速判断hydromodel执行是否正常。

### Q8: 能否在不同阶段重新分析？

**A**: 可以！保存RunnerAgent的输出后，随时重新分析：

```python
# 保存Runner输出
with open("runner_output.json", "w") as f:
    json.dump(runner_result, f)

# 稍后重新分析
with open("runner_output.json", "r") as f:
    runner_result = json.load(f)

developer_result = developer_agent.process(runner_result)
```

---

## 六、下一步

### 已完成
- ✅ IntentAgent 测试
- ✅ ConfigAgent 测试
- ✅ RunnerAgent 测试
- ✅ DeveloperAgent 测试
- ✅ Intent → Config → Runner → Developer 完整管道测试

### 待实现
- ⏳ Orchestrator（完整编排）
- ⏳ 多轮对话支持
- ⏳ 可视化功能增强
- ⏳ 边界效应检测完善

---

**文档版本**: v1.0
**最后更新**: 2025-11-21
**作者**: zhuanglaihong & Claude
