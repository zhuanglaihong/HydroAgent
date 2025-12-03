# HydroAgent 系统逻辑分析文档
# System Logic Analysis Document

**Author**: Claude
**Date**: 2025-12-03
**Version**: v3.5
**Status**: Current Architecture Analysis

---

## 目录 (Table of Contents)

1. [系统概述](#1-系统概述)
2. [Orchestrator协调机制](#2-orchestrator协调机制)
3. [5-Agent流水线详解](#3-5-agent流水线详解)
4. [任务类型与拆解策略](#4-任务类型与拆解策略)
5. [LLM vs 规则驱动边界](#5-llm-vs-规则驱动边界)
6. [固定模式工作流程](#6-固定模式工作流程)
7. [设计哲学与权衡](#7-设计哲学与权衡)
8. [常见问题解答](#8-常见问题解答)

---

## 1. 系统概述

### 1.1 核心定位

HydroAgent是一个**混合架构**的智能多Agent系统:
- **战略层**: LLM驱动的意图识别和配置生成
- **战术层**: 规则驱动的任务拆解和执行编排
- **执行层**: 固定API调用(hydromodel)
- **分析层**: LLM驱动的结果分析和报告生成

### 1.2 系统架构图

```
用户查询 (Natural Language)
      ↓
┌─────────────────────────────────────────────┐
│         Orchestrator (协调器)                │
│  - 会话管理                                  │
│  - 流程编排                                  │
│  - Checkpoint管理                           │
└─────────────────────────────────────────────┘
      ↓
┌─────────────────────────────────────────────┐
│  Step 1: IntentAgent (意图识别)             │
│  🤖 LLM驱动                                 │
│  - 识别task_type                            │
│  - 提取参数(basin_id, model, algorithm)     │
│  - 推断缺失信息                              │
└─────────────────────────────────────────────┘
      ↓
┌─────────────────────────────────────────────┐
│  Step 2: TaskPlanner (任务规划)             │
│  ⚙️ 规则驱动                                 │
│  - 基于task_type选择拆解策略                 │
│  - 生成子任务列表                            │
│  - 为每个子任务生成提示词                     │
└─────────────────────────────────────────────┘
      ↓
┌─────────────────────────────────────────────┐
│  Step 3: InterpreterAgent (配置生成)        │
│  🤖 LLM驱动                                 │
│  - 解析TaskPlanner的提示词                  │
│  - 生成hydromodel配置JSON                   │
│  - LLM自检和修正                            │
└─────────────────────────────────────────────┘
      ↓
┌─────────────────────────────────────────────┐
│  Step 4: RunnerAgent (执行)                 │
│  ⚙️ 固定执行 + 代码生成                      │
│  - 调用hydromodel API                       │
│  - 监控进度和日志                            │
│  - (可选)生成自定义分析代码                  │
└─────────────────────────────────────────────┘
      ↓
┌─────────────────────────────────────────────┐
│  Step 5: DeveloperAgent (分析)              │
│  🤖 LLM驱动                                 │
│  - 分析执行结果                              │
│  - 生成改进建议                              │
│  - 绘制可视化图表                            │
└─────────────────────────────────────────────┘
      ↓
┌─────────────────────────────────────────────┐
│  Step 6: Session Summary (会话总结)         │
│  🤖 LLM驱动 (新增功能 v3.5)                 │
│  - 收集会话信息                              │
│  - 生成智能总结报告                          │
│  - 保存到session_summary.md                │
└─────────────────────────────────────────────┘
```

**图例**:
- 🤖 = LLM驱动的智能决策
- ⚙️ = 规则驱动的确定性逻辑

---

## 2. Orchestrator协调机制

### 2.1 核心职责

Orchestrator是HydroAgent的**中央协调器**(Central Coordinator),负责:

1. **会话管理** (Session Management)
   - 创建独立的工作目录(`results/session_YYYYMMDD_HHMMSS_UUID/`)
   - 维护会话状态和上下文
   - 管理会话历史记录

2. **流程编排** (Pipeline Orchestration)
   - 顺序调用5个Agent
   - 传递数据和上下文
   - 处理Agent间的依赖关系

3. **错误处理** (Error Handling)
   - 捕获Agent执行异常
   - 使用`handle_pipeline_error`集中处理错误
   - 记录失败阶段和错误信息

4. **Checkpoint管理** (Checkpoint Management)
   - 在关键阶段保存检查点
   - 支持中断后恢复执行
   - 跳过已完成的子任务

### 2.2 协调流程伪代码

```python
def orchestrator_process(query):
    # 0. 初始化会话
    session_id = start_new_session()
    workspace = create_workspace(session_id)

    # 1. Intent识别
    intent_result = intent_agent.process(query)
    checkpoint.save_intent(intent_result)

    # 2. 任务规划
    task_plan = task_planner.process(intent_result)
    checkpoint.save_task_plan(task_plan)

    # 3. 配置生成(逐任务)
    configs = []
    for subtask in task_plan.subtasks:
        config = interpreter_agent.process(subtask)
        configs.append(config)

    # 4. 执行(逐任务,支持checkpoint恢复)
    results = []
    for i, config in enumerate(configs):
        if checkpoint.is_completed(task_id):
            results.append(checkpoint.load_result(task_id))
            continue

        result = runner_agent.process(config)
        checkpoint.mark_completed(task_id, result)
        results.append(result)

    # 5. 结果分析
    analysis = developer_agent.process({
        "subtask_results": results,
        "task_plan": task_plan,
        "intent": intent_result
    })

    # 6. 会话总结 (新增 v3.5)
    session_summary = developer_agent.generate_session_summary({
        "session_id": session_id,
        "query": query,
        "intent": intent_result,
        "task_plan": task_plan,
        "execution_results": results,
        "analysis": analysis,
        "elapsed_time": total_time
    })

    return {
        "success": True,
        "results": results,
        "analysis": analysis,
        "session_summary": session_summary
    }
```

### 2.3 关键设计决策

**Q: 为什么Orchestrator不直接使用LLM?**
A: Orchestrator是**确定性流程编排器**,其职责是:
- 管理会话状态
- 按固定顺序调用Agent
- 处理错误和恢复

这些任务需要**可预测性和可靠性**,不适合使用LLM(可能产生幻觉或不稳定输出)。

**Q: 为什么需要Checkpoint机制?**
A: 支持以下场景:
- **长时间任务**: 批量率定20+流域,可能运行数小时
- **资源限制**: 避免因临时故障重头开始
- **成本控制**: LLM调用和计算资源昂贵,应避免重复执行

---

## 3. 5-Agent流水线详解

### 3.1 IntentAgent (意图识别)

**输入**: 用户自然语言查询
```
"率定GR4J模型,流域01013500,使用SCE-UA算法,迭代500轮"
```

**处理方式**: 🤖 **LLM驱动**
- 使用LLM进行语义理解
- 提取关键参数
- 推断任务类型

**输出**: 结构化意图
```json
{
  "task_type": "standard_calibration",
  "model_name": "gr4j",
  "basin_id": "01013500",
  "algorithm": "SCE_UA",
  "extra_params": {"rep": 500},
  "confidence": 0.95
}
```

**LLM的作用**:
- ✅ 自然语言理解(NLU)
- ✅ 实体识别(NER)
- ✅ 中文关键词映射("迭代500轮" → `rep=500`)
- ✅ 推断缺失信息

**局限性**:
- ❌ 依赖LLM质量(需要good prompt engineering)
- ❌ 可能产生幻觉(如错误的basin_id)
- ❌ 需要验证机制(basin_id validation)

---

### 3.2 TaskPlanner (任务规划)

**输入**: IntentAgent的输出(包含task_type)

**处理方式**: ⚙️ **规则驱动**
- 基于task_type选择拆解策略
- 使用硬编码的拆解函数

**拆解策略映射**:
```python
decomposition_methods = {
    "standard_calibration": _decompose_standard_calibration,
    "info_completion": _decompose_info_completion,
    "iterative_optimization": _decompose_iterative_optimization,
    "repeated_experiment": _decompose_repeated_experiment,
    "extended_analysis": _decompose_extended_analysis,
    "batch_processing": _decompose_batch_processing,
    "custom_data": _decompose_custom_data,
    "auto_iterative_calibration": _decompose_auto_iterative_calibration,
}
```

**输出**: 子任务列表 + 提示词
```json
{
  "subtasks": [
    {
      "task_id": "task_1",
      "task_type": "calibration",
      "description": "率定GR4J模型...",
      "prompt": "Generate hydromodel config for calibration with model=gr4j, basin=01013500, algorithm=SCE_UA, rep=500...",
      "parameters": {...},
      "dependencies": []
    }
  ]
}
```

**为什么使用规则驱动而非LLM?**

| 维度 | 规则驱动 | LLM驱动 |
|------|----------|---------|
| **可预测性** | ✅ 100%确定性 | ❌ 可能产生幻觉 |
| **可维护性** | ✅ 逻辑清晰,易调试 | ❌ Prompt工程复杂 |
| **性能** | ✅ 毫秒级 | ❌ 秒级(LLM调用) |
| **成本** | ✅ 零成本 | ❌ API调用费用 |
| **灵活性** | ❌ 新模式需要编码 | ✅ 可能理解新模式 |

**设计决策**: TaskPlanner的任务是**逻辑拆解**,不需要创造性思维,因此使用规则驱动更优。

**拆解示例** (iterative_optimization):
```python
def _decompose_iterative_optimization(intent):
    """两阶段迭代优化"""
    subtasks = [
        SubTask(
            task_id="task_1",
            description="Phase 1: 初始率定",
            prompt="Calibrate with default param_range...",
            parameters={"phase": 1, "range_scale": 0.6}
        ),
        SubTask(
            task_id="task_2",
            description="Phase 2: 参数范围调整后再率定",
            prompt="Calibrate with adjusted param_range centered on previous best_params...",
            parameters={"phase": 2, "range_scale": 0.15},
            dependencies=["task_1"]  # 依赖task_1的结果
        )
    ]
    return {"subtasks": subtasks}
```

---

### 3.3 InterpreterAgent (配置生成)

**输入**: TaskPlanner的子任务提示词
```
"Generate hydromodel config for calibration with model=gr4j, basin=01013500, algorithm=SCE_UA, rep=500..."
```

**处理方式**: 🤖 **LLM驱动**
- LLM解析提示词
- 生成符合hydromodel API规范的JSON配置
- 自检和修正(通过ConfigValidator和LLMConfigReviewer)

**输出**: hydromodel配置字典
```json
{
  "data_cfgs": {
    "basin_ids": ["01013500"],
    "train_period": ["1985-10-01", "1995-09-30"],
    "test_period": ["2005-10-01", "2014-09-30"],
    "data_source_type": "camels_us"
  },
  "model_cfgs": {
    "model_name": "gr4j",
    "model_hyperparam": {}
  },
  "training_cfgs": {
    "algorithm_name": "SCE_UA",
    "algorithm_param": {
      "rep": 500,
      "ngs": 7,
      "kstop": 3
    }
  }
}
```

**LLM的关键作用**:
- ✅ 灵活理解多样化的提示词
- ✅ 填充默认值(从config.py学习)
- ✅ 处理复杂参数组合
- ✅ 自我修正(通过LLMConfigReviewer)

**自检机制**:
```python
# 1. 规则验证 (快速,硬编码检查)
validation_result = ConfigValidator.validate(config)

# 2. LLM验证 (智能,语义检查)
if validation_result["has_warnings"]:
    review_result = LLMConfigReviewer.review(
        config=config,
        user_query=original_query,
        validation_warnings=validation_result["warnings"]
    )

    if review_result["has_issues"]:
        # LLM修正配置
        corrected_config = LLM.correct_config(config, review_result)
```

**示例: LLM发现的语义错误**
```
用户查询: "率定流域01013500,训练期2010-2015,测试期2010-2015"
      ↓
ConfigValidator: ✅ 通过(格式正确)
      ↓
LLMConfigReviewer: ❌ 发现问题
   "train_period和test_period重叠,这不符合水文模型验证的best practice"
      ↓
返回错误给用户,要求明确意图
```

**为什么InterpreterAgent必须使用LLM?**

假设使用规则驱动的配置生成:
```python
# 规则方法(旧的ConfigAgent)
if task_type == "calibration":
    config = {
        "basin_ids": [intent["basin_id"]],
        "model_name": intent["model_name"],
        "algorithm_name": intent.get("algorithm", "SCE_UA"),
        ...
    }
```

**问题**:
- ❌ 无法处理复杂的用户意图("如果NSE<0.7,则缩小参数范围")
- ❌ 无法推断隐式信息("用默认训练期" → 需要知道defaults)
- ❌ 缺乏灵活性(新的参数组合需要修改代码)
- ❌ 无法进行语义验证

**LLM方法的优势**:
- ✅ 理解自然语言意图
- ✅ 动态推断默认值
- ✅ 发现语义错误
- ✅ 适应新的hydromodel版本(通过prompt更新)

---

### 3.4 RunnerAgent (执行)

**输入**: InterpreterAgent的配置字典

**处理方式**: ⚙️ **固定执行** + 🤖 **代码生成**(可选)

**执行模式**:

#### 模式1: 标准hydromodel调用
```python
import hydromodel

result = hydromodel.calibrate(
    data_cfgs=config["data_cfgs"],
    model_cfgs=config["model_cfgs"],
    training_cfgs=config["training_cfgs"]
)
```

#### 模式2: 自定义代码生成 (extended_analysis)
```python
# 用户查询: "率定完成后,计算径流系数,画FDC曲线"

# Step 1: RunnerAgent识别需要代码生成
if "custom_analysis" in subtask["task_type"]:
    # Step 2: 使用code_llm生成代码
    code = CodeGenerator.generate(
        llm=self.code_llm,  # qwen-coder-turbo / deepseek-coder
        analysis_type="runoff_coefficient",
        context={...}
    )

    # Step 3: 执行生成的代码
    result = execute_generated_code(code, workspace_dir)
```

**RunnerAgent中LLM的作用**:
- ❌ **不用于决策**(执行流程是固定的)
- ✅ **仅用于代码生成**(extended_analysis模式)
- ❌ **不用于参数调整**(参数调整由param_range_adjuster规则完成)

**为什么Runner不使用LLM进行决策?**

RunnerAgent的核心职责是**可靠执行**:
- 调用hydromodel API(确定性操作)
- 捕获stdout/stderr(IO操作)
- 解析结果文件(规则解析)
- 管理超时和错误(系统操作)

这些都是**确定性任务**,不需要LLM的不确定性。

**代码生成是例外** (extended_analysis):
- 用户需求: "计算径流系数" → 不是hydromodel的内置功能
- 解决方案: 使用code_llm生成Python脚本
- 设计: 双LLM架构
  - 通用LLM (qwen-turbo): 理解需求
  - 代码LLM (qwen-coder-turbo): 生成代码

---

### 3.5 DeveloperAgent (分析)

**输入**: RunnerAgent的执行结果

**处理方式**: 🤖 **LLM驱动**

**核心功能**:
1. **结果分析** (LLM)
   - 评估性能指标(NSE, RMSE, etc.)
   - 判断模型质量(优秀/良好/可接受/不满意)
   - 检测边界效应(参数是否触碰范围边界)

2. **建议生成** (LLM)
   - 基于结果提出改进建议
   - 推荐下一步行动
   - 诊断潜在问题

3. **可视化** (规则 + LLM)
   - 使用PlottingToolkit绘制图表(规则驱动)
   - LLM决定需要哪些图表(智能选择)

4. **报告生成** (规则)
   - 使用ReportGenerator生成Markdown报告

**LLM的作用示例**:
```python
# 输入: 执行结果
result = {
    "metrics": {"NSE": 0.68, "RMSE": 2.5},
    "best_params": {"x1": 350.0, "x2": 0.5}
}

# LLM分析
analysis = LLM.analyze(f"""
分析以下水文模型率定结果:
- NSE = 0.68
- RMSE = 2.5

请评估质量并提供改进建议。
""")

# LLM输出
{
  "quality": "良好 (Good)",
  "recommendations": [
    "NSE接近良好水平(0.7),可考虑增加训练期长度",
    "建议将rep从500增加到1000以探索更优参数",
    "可尝试调整参数范围,x1可能偏大"
  ]
}
```

**智能可视化决策**(实验5 - 重复率定):
```python
# DeveloperAgent使用LLM决定需要哪些图表
llm_response = LLM.generate("""
你是水文模型专家。分析以下重复率定数据,建议2-4个最有价值的图表:
- 数据: 20次重复率定的NSE值, 4个参数的分布

可选图表类型:
1. time_series: NSE随重复ID的变化
2. histogram: NSE分布直方图
3. boxplot: 参数分布箱线图

请以JSON格式返回建议的图表。
""")

# LLM智能选择
{
  "suggested_plots": [
    {"plot_type": "time_series", "data_key": "NSE", "title": "NSE Stability"},
    {"plot_type": "boxplot", "data_key": "x1", "title": "Parameter x1 Distribution"}
  ]
}
```

**为什么DeveloperAgent必须使用LLM?**
- ✅ 需要专业领域知识(水文模型best practices)
- ✅ 需要推理和诊断能力(为什么NSE低?)
- ✅ 需要生成自然语言建议(可读性)
- ✅ 需要适应新场景(规则无法覆盖所有情况)

---

## 4. 任务类型与拆解策略

### 4.1 任务类型列表

| Task Type | 描述 | 实验编号 | 子任务数 | 示例查询 |
|-----------|------|---------|---------|---------|
| **standard_calibration** | 标准单流域率定 | Exp 1 | 1 | "率定流域01013500" |
| **info_completion** | 缺省信息补全 | Exp 2b | 1 | "帮我率定流域..." |
| **iterative_optimization** | 迭代参数优化 | Exp 3 | 2+ | "如果参数触碰边界..." |
| **repeated_experiment** | 重复率定验证 | Exp 5 | N | "重复率定10次" |
| **extended_analysis** | 扩展分析 | Exp 4 | 1+M | "率定后计算径流系数" |
| **batch_processing** | 批量处理 | Exp 2a | N×M | "率定10个流域" |
| **custom_data** | 自定义数据 | Exp 2c | 1 | "用D盘my_data..." |
| **auto_iterative_calibration** | 自动迭代率定 | v4.0 | 动态 | "自动迭代直到NSE>0.75" |

### 4.2 拆解策略详解

#### 策略1: standard_calibration
```
用户查询: "率定GR4J模型,流域01013500"

TaskPlanner拆解:
└── task_1: Calibration
    - 参数: model=gr4j, basin=01013500, algorithm=SCE_UA
    - 依赖: 无
```

#### 策略2: iterative_optimization
```
用户查询: "如果参数收敛到边界,则调整参数范围后重新率定"

TaskPlanner拆解:
├── task_1: Phase 1 初始率定
│   - 参数: range_scale=0.6 (默认范围的60%)
│   - 依赖: 无
│
└── task_2: Phase 2 调整后率定
    - 参数: range_scale=0.15 (以最佳参数为中心,±15%范围)
    - 依赖: task_1 (需要task_1的best_params)
```

**关键实现**:
```python
# RunnerAgent在task_2执行前:
previous_best_params = load_result("task_1")["best_params"]

# 调用param_range_adjuster (规则驱动)
new_param_range = adjust_from_previous_calibration(
    previous_best_params=previous_best_params,
    range_scale=0.15  # 从60%缩小到15%
)

# 更新配置
config["model_cfgs"]["param_range_file"] = new_param_range_yaml
```

#### 策略3: repeated_experiment
```
用户查询: "重复率定10次,验证稳定性"

TaskPlanner拆解:
├── task_1: Repetition 1 (random_seed=1234)
├── task_2: Repetition 2 (random_seed=5678)
├── task_3: Repetition 3 (random_seed=9012)
│   ...
└── task_10: Repetition 10 (random_seed=...)
```

**后处理**:
- DeveloperAgent调用PostProcessingEngine
- 生成稳定性分析报告(stability_summary.csv)
- 绘制NSE箱线图
- 计算变异系数(CV)

#### 策略4: batch_processing
```
用户查询: "批量率定流域01013500, 01022500, 01030500"

TaskPlanner拆解:
├── task_1: Basin 01013500
├── task_2: Basin 01022500
└── task_3: Basin 01030500
```

**后处理**:
- 生成multi_basin_summary.csv
- 绘制metrics对比图
- 生成basin_ranking.json

### 4.3 任务依赖管理

**线性依赖** (iterative_optimization):
```
task_1 → task_2 → task_3
```

**并行执行** (batch_processing):
```
task_1 ↘
task_2 → (并行,无依赖)
task_3 ↗
```

**混合依赖** (extended_analysis):
```
task_1 (calibration)
    ↓
    ├→ task_2a (custom_analysis: 径流系数)
    └→ task_2b (custom_analysis: FDC曲线)
```

**实现**:
```python
# Orchestrator检查依赖
for subtask in subtasks:
    # 等待依赖任务完成
    for dep_task_id in subtask["dependencies"]:
        wait_until_completed(dep_task_id)

    # 执行当前任务
    result = runner_agent.process(subtask)
```

---

## 5. LLM vs 规则驱动边界

### 5.1 系统分层与驱动方式

```
┌────────────────────────────────────────┐
│  战略层 (Strategic Layer)             │
│  🤖 LLM驱动                            │
│  - 意图识别 (IntentAgent)              │
│  - 语义理解                            │
│  - 参数推断                            │
└────────────────────────────────────────┘
              ↓
┌────────────────────────────────────────┐
│  战术层 (Tactical Layer)               │
│  ⚙️ 规则驱动                           │
│  - 任务拆解 (TaskPlanner)              │
│  - 逻辑编排                            │
│  - 依赖管理                            │
└────────────────────────────────────────┘
              ↓
┌────────────────────────────────────────┐
│  配置层 (Configuration Layer)          │
│  🤖 LLM驱动                            │
│  - 配置生成 (InterpreterAgent)         │
│  - 语义验证                            │
│  - 自我修正                            │
└────────────────────────────────────────┘
              ↓
┌────────────────────────────────────────┐
│  执行层 (Execution Layer)              │
│  ⚙️ 固定执行 (+ 🤖 代码生成)           │
│  - API调用 (RunnerAgent)               │
│  - 进度监控                            │
│  - 结果解析                            │
└────────────────────────────────────────┘
              ↓
┌────────────────────────────────────────┐
│  分析层 (Analysis Layer)               │
│  🤖 LLM驱动                            │
│  - 结果分析 (DeveloperAgent)           │
│  - 建议生成                            │
│  - 报告撰写                            │
└────────────────────────────────────────┘
```

### 5.2 LLM作用点详解

| 组件 | LLM使用场景 | 具体作用 | 是否必须 |
|------|------------|---------|---------|
| **IntentAgent** | 意图识别 | NLU, NER, 参数提取 | ✅ 必须 |
| **TaskPlanner** | - | (不使用LLM) | ❌ - |
| **InterpreterAgent** | 配置生成 | 提示词→JSON, 语义验证 | ✅ 必须 |
| **RunnerAgent** | 代码生成 | 生成自定义分析代码 | ⚠️ 可选 |
| **DeveloperAgent** | 结果分析 | 质量评估, 建议生成, 图表选择 | ✅ 必须 |
| **DeveloperAgent** | 会话总结 | 生成session_summary.md | ✅ 必须 |

### 5.3 为什么不全部使用LLM?

**成本考虑**:
- LLM API调用费用高昂
- 一次完整流程可能调用LLM 5-10次
- 规则驱动的部分(TaskPlanner)成本为零

**可靠性考虑**:
- TaskPlanner的逻辑拆解需要100%确定性
- LLM可能产生幻觉(如错误的子任务数量)
- 规则驱动保证可预测性

**性能考虑**:
- TaskPlanner使用规则: 毫秒级
- 如果使用LLM: 秒级
- 对于批处理任务,性能差异显著

**可维护性考虑**:
- 规则驱动的逻辑清晰,易于调试
- LLM驱动需要复杂的prompt engineering
- 团队协作时,规则代码更易理解

### 5.4 混合架构的优势

HydroAgent采用**混合架构** (Hybrid Architecture):
- **战略决策**: LLM驱动(灵活性)
- **战术执行**: 规则驱动(可靠性)
- **配置生成**: LLM驱动(智能性)
- **实际执行**: 固定API调用(确定性)
- **结果分析**: LLM驱动(专业性)

**优势**:
- ✅ 平衡了灵活性和可靠性
- ✅ 控制了成本和性能
- ✅ 保证了可维护性
- ✅ 支持快速迭代(规则部分易于修改)

**对比纯LLM方案**:
| 方面 | 混合架构 | 纯LLM架构 |
|------|---------|----------|
| 成本 | 中等 | 高 |
| 可靠性 | 高 | 中等 |
| 灵活性 | 高 | 非常高 |
| 可预测性 | 高 | 低 |
| 维护性 | 高 | 中等 |

---

## 6. 固定模式工作流程

### 6.1 模式1: standard_calibration

**完整流程**:
```
用户查询: "率定GR4J模型,流域01013500,使用SCE-UA算法,迭代500轮"
      ↓
IntentAgent (LLM):
   识别: task_type = "standard_calibration"
   提取: model=gr4j, basin=01013500, algorithm=SCE_UA, rep=500
      ↓
TaskPlanner (规则):
   拆解为1个子任务: task_1
   生成提示词: "Generate config for calibration..."
      ↓
InterpreterAgent (LLM):
   解析提示词 → 生成hydromodel配置JSON
   验证配置 → ConfigValidator + LLMConfigReviewer
      ↓
RunnerAgent (固定):
   调用: hydromodel.calibrate(config)
   监控进度条, 捕获日志
   解析结果: calibration_results.json
      ↓
DeveloperAgent (LLM):
   分析: NSE=0.75 → 质量="良好"
   建议: ["增加训练期", "调整参数范围"]
   生成报告: analysis_report.md
      ↓
Session Summary (LLM):
   收集会话信息
   生成: session_summary.md
```

### 6.2 模式2: iterative_optimization

**完整流程**:
```
用户查询: "如果参数收敛到边界,则调整参数范围后重新率定"
      ↓
IntentAgent (LLM):
   识别: task_type = "iterative_optimization"
   提取: model, basin, strategy={phases: 2}
      ↓
TaskPlanner (规则):
   拆解为2个子任务:
   - task_1: Phase 1 (range_scale=0.6)
   - task_2: Phase 2 (range_scale=0.15, depends_on=task_1)
      ↓
InterpreterAgent (LLM):
   为task_1生成配置 → config_task1.json
   为task_2生成配置 → config_task2.json (暂不包含param_range)
      ↓
RunnerAgent (固定):
   执行task_1:
      hydromodel.calibrate(config_task1)
      结果: best_params_1, NSE_1

   边界检测 (规则):
      检测best_params_1是否触碰边界

   参数范围调整 (规则):
      new_range = adjust_from_previous_calibration(
          best_params_1,
          range_scale=0.15
      )
      保存: param_range_adjusted.yaml

   执行task_2:
      更新config_task2的param_range
      hydromodel.calibrate(config_task2)
      结果: best_params_2, NSE_2
      ↓
DeveloperAgent (LLM):
   对比NSE_1和NSE_2
   分析改进率: (NSE_2 - NSE_1) / NSE_1 * 100%
   绘制NSE收敛图: nse_convergence.png
   生成报告: analysis_report.md
```

**关键点**:
- TaskPlanner定义了2阶段结构(规则)
- RunnerAgent在两阶段之间调整参数范围(规则)
- DeveloperAgent分析整体收敛性(LLM)

### 6.3 模式3: extended_analysis

**完整流程**:
```
用户查询: "率定完成后,请帮我计算流域的径流系数,并画FDC曲线"
      ↓
IntentAgent (LLM):
   识别: task_type = "extended_analysis"
   提取:
      - base_task = "calibration"
      - analysis_needs = ["runoff_coefficient", "fdc_curve"]
      ↓
TaskPlanner (规则):
   拆解为3个子任务:
   - task_1: Calibration
   - task_2: Custom analysis - runoff_coefficient
   - task_3: Custom analysis - fdc_curve
   依赖: task_2和task_3都依赖task_1
      ↓
InterpreterAgent (LLM):
   task_1: 生成标准率定配置
   task_2: 生成最小配置(仅metadata)
   task_3: 生成最小配置(仅metadata)
      ↓
RunnerAgent (固定 + LLM代码生成):
   执行task_1:
      hydromodel.calibrate(config)

   执行task_2 (代码生成):
      识别: custom_analysis类型
      使用code_llm生成代码:
         def calculate_runoff_coefficient(basin_id, period):
             # LLM生成的完整Python脚本
             streamflow_data = load_streamflow(basin_id, period)
             precipitation_data = load_precipitation(basin_id, period)
             rc = sum(streamflow) / sum(precipitation)
             return rc

      执行代码:
         result = execute_generated_code(code, workspace)

      保存输出:
         runoff_coefficient_result.json

   执行task_3 (代码生成):
      类似task_2,生成FDC绘图代码
      ↓
DeveloperAgent (LLM):
   分析task_1的率定结果
   整合task_2和task_3的自定义分析
   生成综合报告
```

**代码生成流程细节**:
```python
# RunnerAgent._execute_custom_analysis_task

# Step 1: 分析任务需求
analysis_type = parse_analysis_type(subtask["description"])
# "计算径流系数" → analysis_type = "runoff_coefficient"

# Step 2: 构建代码生成prompt
prompt = build_code_generation_prompt(
    analysis_type=analysis_type,
    context={
        "basin_id": config["basin_ids"][0],
        "train_period": config["train_period"],
        "result_dir": workspace_dir
    }
)

# Step 3: 使用code_llm生成代码
code = self.code_llm.generate(prompt)
# 返回完整Python脚本,包含type hints, 错误处理, 文档注释

# Step 4: 代码验证和沙箱执行
validated_code = CodeSandbox.validate(code)
result = CodeSandbox.execute(
    code=validated_code,
    workspace_dir=workspace_dir,
    timeout=300
)

# Step 5: 保存生成的代码和结果
save_code(code, workspace_dir / "generated_code" / f"{analysis_type}.py")
save_result(result, workspace_dir / f"{analysis_type}_result.json")
```

---

## 7. 设计哲学与权衡

### 7.1 核心设计原则

**1. 分离关注点 (Separation of Concerns)**
- 每个Agent负责单一职责
- IntentAgent: 理解"要做什么"
- TaskPlanner: 决定"如何拆解"
- InterpreterAgent: 生成"具体配置"
- RunnerAgent: 执行"实际操作"
- DeveloperAgent: 分析"结果和建议"

**2. 混合架构 (Hybrid Architecture)**
- 战略层使用LLM(灵活性)
- 战术层使用规则(可靠性)
- 配置层使用LLM(智能性)
- 执行层使用固定调用(确定性)

**3. 可观测性 (Observability)**
- 每个阶段保存checkpoint
- 完整日志记录到logs/
- 结果文件结构化存储
- Session summary统一总结

**4. 可扩展性 (Extensibility)**
- 新任务模式: 添加TaskPlanner拆解函数
- 新模型支持: 更新InterpreterAgent的prompt
- 新分析需求: 扩展DeveloperAgent的后处理器

### 7.2 设计权衡分析

#### 权衡1: 为什么不全部使用LLM?

**方案A: 全LLM驱动** (如AutoGPT)
```
用户查询 → LLM规划 → LLM生成config → LLM监控执行 → LLM分析
```

**优势**:
- ✅ 极高灵活性
- ✅ 可能发现新模式
- ✅ 自适应能力强

**劣势**:
- ❌ 成本高(每步都调用LLM)
- ❌ 可靠性低(LLM可能幻觉)
- ❌ 调试困难(不确定性高)
- ❌ 性能差(LLM调用慢)

**方案B: 混合架构** (HydroAgent当前)
```
LLM(Intent) → 规则(Plan) → LLM(Config) → 固定(Execute) → LLM(Analyze)
```

**优势**:
- ✅ 平衡成本和性能
- ✅ 核心流程可靠
- ✅ 易于调试和维护
- ✅ 可预测性高

**劣势**:
- ❌ 新模式需要编码(不如全LLM灵活)
- ❌ 规则部分维护成本

**结论**: 对于生产环境,混合架构更优。

---

#### 权衡2: TaskPlanner为什么使用规则而非LLM?

**实验对比**:

**规则驱动** (当前方案):
```python
def _decompose_iterative_optimization(intent):
    return [
        SubTask("task_1", phase=1, range_scale=0.6),
        SubTask("task_2", phase=2, range_scale=0.15, deps=["task_1"])
    ]
```
- 耗时: <1ms
- 成功率: 100%
- 成本: $0

**LLM驱动** (实验方案):
```python
llm_response = LLM.generate("""
请将以下任务拆解为子任务:
"如果参数收敛到边界,则调整参数范围后重新率定"

返回子任务列表的JSON格式。
""")
```
- 耗时: 2-5s
- 成功率: 90% (可能产生错误的子任务数量或依赖关系)
- 成本: $0.001-0.01/次

**结论**: 对于逻辑拆解任务,规则驱动更优。

---

#### 权衡3: Runner是否应该使用LLM进行决策?

**场景**: 参数范围调整

**方案A: LLM决策**
```python
llm_decision = LLM.generate(f"""
上一次率定的最优参数为: {best_params}
参数范围为: {param_range}

是否需要调整参数范围? 如果需要,请给出新的范围。
""")

if llm_decision["should_adjust"]:
    new_range = llm_decision["new_range"]
```

**方案B: 规则决策** (当前方案)
```python
boundary_effects = detect_boundary_effects(best_params, param_range)

if boundary_effects:
    new_range = adjust_from_previous_calibration(
        best_params,
        range_scale=0.15
    )
```

**对比**:
| 方面 | LLM决策 | 规则决策 |
|------|---------|---------|
| 可靠性 | 中等(可能出错) | 高(确定性算法) |
| 成本 | 高($) | 低(0) |
| 速度 | 慢(秒级) | 快(毫秒级) |
| 可解释性 | 低(黑盒) | 高(算法清晰) |

**结论**: 对于有明确算法的任务,使用规则决策更优。

---

### 7.3 何时使用LLM vs 规则?

**使用LLM的场景**:
- ✅ 自然语言理解(NLU, NER)
- ✅ 语义验证(配置是否合理?)
- ✅ 创造性任务(代码生成, 建议生成)
- ✅ 需要领域知识的判断(质量评估)
- ✅ 输出需要自然语言表达(报告撰写)

**使用规则的场景**:
- ✅ 逻辑拆解(任务分解)
- ✅ 确定性计算(参数调整)
- ✅ 状态管理(流程编排)
- ✅ 格式转换(JSON解析)
- ✅ 性能关键路径(热点代码)

**混合使用的场景**:
- ⚙️+🤖 可视化决策: 规则绘图 + LLM选择图表类型
- ⚙️+🤖 配置生成: LLM生成 + 规则验证
- ⚙️+🤖 代码生成: LLM生成 + 沙箱执行(规则)

---

## 8. 常见问题解答

### Q1: Runner只是固定执行,那LLM有什么用?

**A**: Runner的**核心职责是可靠执行**,不需要LLM决策。但LLM在以下环节发挥关键作用:

1. **IntentAgent**: 理解用户意图
   ```
   "帮我率定..." → 推断出model, basin, algorithm
   ```

2. **InterpreterAgent**: 生成hydromodel配置
   ```
   提示词 → 完整的JSON配置(包含所有必需字段)
   ```

3. **RunnerAgent**: 代码生成(extended_analysis)
   ```
   "计算径流系数" → 生成可执行Python脚本
   ```

4. **DeveloperAgent**: 结果分析
   ```
   执行结果 → 质量评估 + 改进建议
   ```

**类比**:
- Runner = 工厂流水线(固定操作)
- LLM = 工程师(理解需求, 设计方案, 分析结果)

---

### Q2: 为什么不直接让LLM生成hydromodel代码?

**方案A**: LLM生成hydromodel调用代码
```python
llm_code = LLM.generate("""
请生成调用hydromodel率定GR4J模型的Python代码。
""")

# LLM可能生成:
code = """
from hydromodel import calibrate
result = calibrate(
    model="gr4j",
    basin="01013500",
    algorithm="SCE_UA"
)
"""

exec(code)  # 执行LLM生成的代码
```

**问题**:
- ❌ LLM可能生成错误的API调用
- ❌ 参数名可能拼写错误
- ❌ 缺少必需字段
- ❌ 安全风险(exec执行不可信代码)
- ❌ 难以调试和维护

**方案B**: LLM生成配置 + 固定代码执行 (当前方案)
```python
config = LLM.generate_config(...)  # LLM生成配置JSON
validated_config = ConfigValidator.validate(config)  # 规则验证

# 固定的、经过测试的执行代码
result = hydromodel.calibrate(
    data_cfgs=validated_config["data_cfgs"],
    model_cfgs=validated_config["model_cfgs"],
    training_cfgs=validated_config["training_cfgs"]
)
```

**优势**:
- ✅ 执行代码经过充分测试
- ✅ 配置经过严格验证
- ✅ 安全可控
- ✅ 易于调试

---

### Q3: 如果要支持新的任务模式怎么办?

**示例**: 用户需要"多模型对比"功能

**步骤1**: 在IntentAgent中识别新模式
```python
# IntentAgent的prompt中添加:
"""
新任务类型:
- multi_model_comparison: 使用多个模型率定同一流域并对比性能
"""
```

**步骤2**: 在TaskPlanner中添加拆解策略
```python
# task_planner.py

def _decompose_multi_model_comparison(intent):
    """拆解多模型对比任务"""
    models = intent.get("models", ["gr4j", "xaj", "gr6j"])
    basin_id = intent["basin_id"]

    subtasks = []
    for i, model in enumerate(models, 1):
        subtasks.append(SubTask(
            task_id=f"task_{i}",
            task_type="calibration",
            description=f"Calibrate {model} for basin {basin_id}",
            parameters={"model_name": model, "basin_id": basin_id}
        ))

    return {"subtasks": subtasks}

# 注册到decomposition_methods
self.decomposition_methods["multi_model_comparison"] = self._decompose_multi_model_comparison
```

**步骤3**: 在DeveloperAgent中添加后处理
```python
# post_processor.py

def _process_multi_model_comparison(subtask_results, ...):
    """生成多模型对比报告"""
    # 提取各模型的NSE
    model_nses = {}
    for result in subtask_results:
        model = result["model_name"]
        nse = result["metrics"]["NSE"]
        model_nses[model] = nse

    # 生成对比图
    plot_model_comparison(model_nses)

    # 生成排名JSON
    ranking = sorted(model_nses.items(), key=lambda x: x[1], reverse=True)
    save_json(ranking, "model_ranking.json")
```

**总结**: 新模式需要修改代码,但流程清晰,易于扩展。

---

### Q4: 系统的性能瓶颈在哪里?

**性能分析**:

```
完整流程耗时分布:
├── IntentAgent (LLM):        2-5秒   (10%)
├── TaskPlanner (规则):       <1毫秒  (0%)
├── InterpreterAgent (LLM):   3-8秒   (15%)
├── RunnerAgent (hydromodel): 60-600秒 (70%)
│   └── hydromodel.calibrate: 大部分时间
└── DeveloperAgent (LLM):     5-10秒  (5%)
```

**瓶颈**: RunnerAgent调用hydromodel API(70%时间)

**优化方向**:
1. ✅ 已支持Checkpoint(避免重复执行)
2. ⚠️ 待实现并行执行(batch_processing时多流域并行)
3. ⚠️ 待实现算法参数优化(减少rep,平衡性能和质量)

**非瓶颈**: LLM调用(只占30%,且已优化prompt长度)

---

### Q5: 如何确保LLM生成的配置正确?

**多层验证机制**:

1. **结构验证** (ConfigValidator, 规则驱动)
   ```python
   errors = ConfigValidator.validate_structure(config)
   # 检查: 必需字段, 数据类型, 值范围
   ```

2. **语义验证** (LLMConfigReviewer, LLM驱动)
   ```python
   issues = LLMConfigReviewer.review(config, user_query)
   # 检查: train/test period重叠, 不合理的参数组合
   ```

3. **用户确认** (可选)
   ```python
   if issues:
       raise ValueError(f"配置存在问题: {issues}")
       # 返回给用户,要求明确意图
   ```

4. **执行前检查** (RunnerAgent)
   ```python
   # 再次验证配置完整性
   assert all(key in config for key in required_keys)
   ```

**示例**: 发现重叠时期
```
用户: "训练期2010-2015,测试期2010-2015"
      ↓
ConfigValidator: ✅ 通过(格式正确)
      ↓
LLMConfigReviewer: ❌ 检测到语义错误
   "train_period和test_period完全重叠,这违反了模型验证原则"
      ↓
返回错误,要求用户明确是否有意为之
```

---

### Q6: 系统如何处理失败和恢复?

**失败处理策略**:

1. **阶段性Checkpoint**
   ```
   Intent → [Checkpoint] → Plan → [Checkpoint] → Config → [Checkpoint] → Execute
   ```

2. **任务级Checkpoint** (多任务时)
   ```
   task_1 → [✅ Checkpoint] → task_2 → [✅ Checkpoint] → task_3
              ↑ 已完成           ↓ 失败
   ```

3. **错误分类和处理**
   ```python
   try:
       result = runner_agent.process(config)
   except ValidationError as e:
       # 配置错误 → 返回InterpreterAgent修正
       corrected_config = interpreter_agent.correct(config, error=e)
   except TimeoutError as e:
       # 超时 → 记录并继续下一任务
       mark_subtask_failed(task_id, error=e)
   except Exception as e:
       # 未知错误 → 记录详细traceback, 保存checkpoint
       checkpoint.save_error(task_id, error=e, traceback=...)
   ```

4. **恢复执行**
   ```bash
   # 用户中断后恢复
   python scripts/run_with_checkpoint.py \
     --resume results/session_20251203_143000_abc123

   # 系统自动跳过已完成的task_1, task_2
   # 从失败的task_3继续执行
   ```

---

### Q7: 会话总结(Session Summary)如何工作?

**新增功能** (v3.5 - 2025-12-03):

**目标**: 为每次对话生成统一的智能总结报告

**组件**:
1. **SessionSummaryCollector** (utils/session_summary.py)
   - 收集会话信息(任务、时间、路径)
   - 统计执行情况(成功/失败数)
   - 扫描工作目录,收集文件列表

2. **SessionSummaryGenerator** (utils/session_summary.py)
   - 使用LLM生成Markdown格式报告
   - 包含6个章节(概述、任务详情、时间统计、完成情况、建议、文件路径)

3. **集成点** (Orchestrator Step 6)
   ```python
   # 在Step 5 (DeveloperAgent分析)之后
   session_summary = developer_agent.generate_session_summary(
       orchestrator_output=result,
       session_id=session_id,
       query=query
   )

   # 保存到: workspace/session_summary.md
   ```

**报告结构**:
```markdown
# HydroAgent 会话总结报告

## 1. 执行概述
- 会话ID: session_20251203_143000
- 查询: "率定GR4J模型..."
- 任务类型: standard_calibration
- 完成情况: 1/1 成功

## 2. 任务详情
- task_1: 率定GR4J模型 (✅ 成功)
  - NSE: 0.75
  - RMSE: 2.3

## 3. 时间统计
- Intent识别: 3.2秒
- 任务规划: <1毫秒
- 配置生成: 5.1秒
- 执行: 125.3秒
- 分析: 7.2秒
- 总计: 140.8秒

## 4. 完成情况与质量评估
- 质量: 良好 (Good)
- 建议: [...LLM生成...]

## 5. 改进建议
1. ...
2. ...

## 6. 文件路径
- 日志: logs/run_*.log
- 结果: results/session_*/task_1/calibration_results.json
- 配置: results/session_*/task_1/calibration_config.yaml
- 报告: results/session_*/analysis_report.md
```

**优势**:
- ✅ 统一的报告格式(所有任务类型)
- ✅ LLM智能总结(不是简单模板)
- ✅ 包含完整信息(时间、路径、建议)
- ✅ 自动生成(无需手动编写)

---

## 附录: 系统演化历史

### v1.0 - 基础架构 (2023-2025)
- 4-Agent: Intent → Config → Runner → Developer
- 规则驱动的ConfigAgent

### v2.0 - 任务规划层 (2025-11)
- 引入TaskPlanner(战略/战术分离)
- 支持多任务拆解

### v3.0 - LLM配置生成 (2025-11)
- ConfigAgent → InterpreterAgent
- LLM驱动的配置生成
- LLMConfigReviewer语义验证

### v3.5 - 会话总结 (2025-12-03, 当前版本)
- ✅ 新增SessionSummaryGenerator
- ✅ 统一的会话总结报告
- ✅ LLM智能总结

### v4.0 (规划中)
- 可视化绘图增强
- 自动迭代率定改进
- Web UI (Gradio)

---

## 参考文档

- [CLAUDE.md](../CLAUDE.md) - 项目总览和开发指南
- [ARCHITECTURE_FINAL.md](ARCHITECTURE_FINAL.md) - 详细架构设计
- [TESTING_GUIDE.md](TESTING_GUIDE.md) - 测试指南
- [v4.0_improvements_summary.md](v4.0_improvements_summary.md) - v4.0改进计划

---

**文档维护者**: Claude
**最后更新**: 2025-12-03
**版本**: v3.5
