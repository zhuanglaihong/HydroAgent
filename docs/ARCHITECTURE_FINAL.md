# HydroAgent 架构设计文档

**Author**: HydroAgent Team
**Date**: 2025-11-26
**Version**: 4.0
**Status**: Production Ready

---

## 📋 目录

- [1. 系统概览](#1-系统概览)
- [2. 设计理念](#2-设计理念)
- [3. 核心实验场景](#3-核心实验场景)
- [4. 系统架构](#4-系统架构)
- [5. 组件详细设计](#5-组件详细设计)
- [6. 数据流与协作](#6-数据流与协作)
- [7. 实验实现要点](#7-实验实现要点)
- [8. 已知问题与修复](#8-已知问题与修复)
- [9. 未来规划](#9-未来规划)

---

## 1. 系统概览

### 1.1 当前状态（v4.0）

| 组件 | 状态 | 说明 |
|------|------|------|
| **5-Agent架构** | ✅完成 | IntentAgent → TaskPlanner → InterpreterAgent → RunnerAgent → DeveloperAgent |
| **8个核心实验** | ✅验证通过 | 基础功能3个、稳定性批量3个、高级功能2个 |
| **双LLM模式** | ✅完成 | 通用模型（分析）+ 代码专用模型（生成） |
| **自适应优化** | ✅完成 | 参数边界检测、动态范围调整 |
| **代码生成** | ✅完成 | 径流系数、FDC曲线、自定义分析 |

### 1.2 实验验证状态

**实验1：基础功能验证**
- ✅ **1A** - 标准流程：完整信息率定
- ✅ **1B** - 信息补全：自动填充缺失参数
- ✅ **1C** - 错误处理：异常情况鲁棒性

**实验2：稳定性与批量**
- ✅ **2A** - 重复率定：单流域多次执行（20次）
- ✅ **2B** - 多流域：批量处理10个流域
- ✅ **2C** - 多算法：对比 SCE-UA/PSO/GA

**实验3-4：高级功能**
- ✅ **3** - 自适应优化：参数边界检测与动态调整（range_scale: 60%→15%）
- ✅ **4** - 智能代码生成：双LLM（qwen-turbo + qwen-coder-turbo）

### 1.3 核心功能清单

**IntentAgent**
- 8种任务类型识别（standard, info_completion, iterative, repeated, extended, batch, custom_data, error_handling）
- 信息自动补全（model, algorithm, time_period, data_source）
- 扩展分析需求提取（runoff_coefficient, FDC等）

**TaskPlanner**
- 任务拆解（支持所有8种task_type）
- 提示词生成（每个子任务定制化prompt）
- 依赖关系管理（dependency tracking）
- PromptPool历史案例管理

**InterpreterAgent**
- LLM驱动配置生成（支持自我修正，最多3次）
- 双重验证逻辑（hydromodel任务 vs custom_analysis任务）
- 动态加载算法参数（config.py）

**RunnerAgent**
- 标准率定执行
- 自动评估（calibration后）
- 迭代优化执行（实验3）
- 统计分析（实验2A）
- 智能参数范围调整（以最优参数为中心）

**DeveloperAgent**
- 结果分析和建议生成
- 双LLM代码生成（思考分析 + 代码生成）
- 支持任务：径流系数、FDC、自定义水文指标

---

## 2. 设计理念

### 2.1 核心原则

> **实验驱动，分层决策，职责清晰**

1. **战略与战术分离**：IntentAgent决策"要做什么"，TaskPlanner决策"怎么做"
2. **任务拆解与配置生成分离**：TaskPlanner拆解任务，InterpreterAgent生成config
3. **逻辑复杂性与执行复杂性隔离**：TaskPlanner处理组合逻辑，RunnerAgent只负责执行
4. **支持8个核心实验**：所有设计围绕实际实验需求展开

### 2.2 设计目标

| 实验 | 核心需求 | 架构支持 |
|------|---------|---------|
| **实验1A-1C** | 标准流程、信息补全、错误处理 | IntentAgent识别 + Interpreter智能生成 |
| **实验2A-2C** | 重复实验、多流域、多算法 | TaskPlanner拆解 + 批量执行 |
| **实验3** | 参数自适应优化 | TaskPlanner拆解 + RunnerAgent迭代执行 |
| **实验4** | 代码生成扩展 | DeveloperAgent双LLM生成脚本 |

---

## 3. 核心实验场景

### 3.1 实验1A：标准流域验证（简单任务）

**用户输入**
```
"率定流域 01013500，使用标准 XAJ 模型"
```

**系统行为**
```
IntentAgent → 识别"standard_calibration"任务
      ↓
TaskPlanner → 无需拆解，生成单一提示词
      ↓
InterpreterAgent → 生成hydromodel配置
      ↓
RunnerAgent → 执行率定
      ↓
DeveloperAgent → 分析结果（NSE=0.68, Good）
```

### 3.2 实验2A：重复率定（稳定性验证）

**用户输入**
```
"重复率定流域 01013500 二十次，使用不同随机种子"
```

**系统行为**
```
IntentAgent → 识别"repeated_experiment"，提取n_repeats=20
      ↓
TaskPlanner → 拆解为21个子任务：
              - 20个 repetition_N 子任务（独立执行）
              - 1个 statistical_analysis 子任务（依赖前20个）
      ↓
InterpreterAgent → 为每个repetition生成配置（不同random_seed）
      ↓
RunnerAgent → 执行20次率定
      ↓
DeveloperAgent → 统计分析（mean NSE, std, CI）
```

### 3.3 实验3：参数自适应优化（迭代优化）

**用户输入**
```
"率定流域 01013500，如果参数收敛到边界，自动调整范围重新率定"
```

**系统行为**
```
IntentAgent → 识别"iterative_optimization"
      ↓
TaskPlanner → 创建单一iterative任务（不拆解为多个phase）
      ↓
InterpreterAgent → 生成初始配置
      ↓
RunnerAgent → 内部循环迭代执行：
              Iter 0: 默认范围（100%） → NSE=0.42
              Iter 1: 缩小至60% → NSE=0.48 ✅
              Iter 2: 缩小至42% → NSE=0.51 ✅ 达标停止
              （智能停止条件：NSE达标/连续无改善/迭代上限）
      ↓
DeveloperAgent → 分析最优结果
```

**关键机制**：
- **动态range_scale调整**：60% → 42% → 29% → 20% → 15%
- **以最优参数为中心**：根据上一轮最优参数生成新的YAML范围文件
- **智能停止**：NSE>0.75 或 改善<0.001 或 达到最大迭代次数

### 3.4 实验4：智能代码生成（扩展分析）

**用户输入**
```
"率定完成后，请帮我计算流域的径流系数，并画一张 FDC 曲线"
```

**系统行为**
```
IntentAgent → 识别"extended_analysis"，提取needs=["runoff_coefficient", "FDC"]
      ↓
TaskPlanner → 拆解为3个子任务：
              - subtask_1: standard_calibration（执行率定）
              - subtask_2: custom_analysis - runoff_coefficient（依赖1）
              - subtask_3: custom_analysis - FDC（依赖1）
      ↓
InterpreterAgent → 为subtask_1生成hydromodel配置
                   为subtask_2/3生成最小化配置（只含task_metadata）
      ↓
RunnerAgent → 执行subtask_1率定
      ↓
DeveloperAgent → 处理subtask_2/3：
                 【通用LLM】思考分析需求
                       ↓
                 【代码LLM】生成完整Python脚本：
                       - runoff_coefficient_analysis.py
                       - plot_fdc.py
                 自动保存到 generated_code/
```

**双LLM架构**：
- **API模式**：qwen-turbo（通用）+ qwen-coder-turbo（代码生成）
- **Ollama模式**：qwen3:8b（通用）+ deepseek-coder:6.7b（代码生成）

---

## 4. 系统架构

### 4.1 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        用户输入（自然语言）                      │
└───────────────────────────┬─────────────────────────────────┘
                            ↓
┌───────────────────────────────────────────────────────────────┐
│ 1. IntentAgent（战略决策层）                                    │
│    - 任务类型识别（8种task_type）                               │
│    - 信息提取 + 补全                                           │
│    - 扩展需求识别                                              │
│    Output: intent_result (task_type, extracted_info, ...)     │
└───────────────────────────┬───────────────────────────────────┘
                            ↓
┌───────────────────────────────────────────────────────────────┐
│ 2. TaskPlanner（战术拆解层）                                    │
│    - 任务拆解（1个或多个subtask）                               │
│    - 提示词生成（为每个subtask）                                │
│    - 依赖关系管理                                              │
│    - PromptPool历史管理                                       │
│    Output: task_plan (subtasks[], dependencies)               │
└───────────────────────────┬───────────────────────────────────┘
                            ↓
┌───────────────────────────────────────────────────────────────┐
│ 3. InterpreterAgent（配置生成层）                               │
│    - LLM生成hydromodel配置（for standard/calibration）         │
│    - 最小化配置（for custom_analysis）                         │
│    - 自我修正（最多3次）                                        │
│    - 配置验证                                                 │
│    Output: configs[] (每个subtask一个config)                  │
└───────────────────────────┬───────────────────────────────────┘
                            ↓
┌───────────────────────────────────────────────────────────────┐
│ 4. RunnerAgent（执行层）                                        │
│    - 标准率定执行                                              │
│    - 自动评估（calibration后）                                 │
│    - 迭代优化执行（内部循环）                                   │
│    - 统计分析                                                 │
│    Output: execution_results (params, metrics, ...)           │
└───────────────────────────┬───────────────────────────────────┘
                            ↓
┌───────────────────────────────────────────────────────────────┐
│ 5. DeveloperAgent（分析 + 代码生成层）                           │
│    - 结果分析（NSE, RMSE, 建议）                                │
│    - 代码生成（custom_analysis）                               │
│      - 通用LLM：思考分析                                       │
│      - 代码LLM：生成Python脚本                                 │
│    Output: analysis_report / generated_code                   │
└───────────────────────────────────────────────────────────────┘
```

### 4.2 目录结构

```
HydroAgent/
├── hydroagent/
│   ├── core/
│   │   ├── base_agent.py         # BaseAgent抽象类
│   │   ├── llm_interface.py      # LLM API封装
│   │   ├── checkpoint_manager.py # Checkpoint系统
│   │   └── prompt_pool.py        # PromptPool管理
│   ├── agents/
│   │   ├── intent_agent.py       # 意图识别
│   │   ├── task_planner.py       # 任务规划
│   │   ├── interpreter_agent.py  # 配置生成
│   │   ├── runner_agent.py       # 模型执行
│   │   ├── developer_agent.py    # 分析+代码生成
│   │   └── orchestrator.py       # 编排器（统一接口）
│   ├── utils/
│   │   └── error_handler.py      # 错误处理
│   └── resources/
│       └── *.txt                 # 提示词模板
├── configs/
│   ├── definitions.py            # 公共配置
│   ├── definitions_private.py    # 私有配置（API keys）
│   └── config.py                 # 全局参数
├── experiment/
│   ├── base_experiment.py        # 实验基类
│   ├── exp_1a_standard.py        # 实验1A
│   ├── exp_1b_info_completion.py # 实验1B
│   ├── exp_1c_error_handling.py  # 实验1C
│   ├── exp_2a_repeated_calibration.py  # 实验2A
│   ├── exp_2b_multi_basin.py     # 实验2B
│   ├── exp_2c_multi_algorithm.py # 实验2C
│   ├── exp_3_iterative_optimization.py # 实验3
│   └── exp_4_extended_analysis.py      # 实验4
├── scripts/
│   ├── run_developer_agent_pipeline.py  # 主入口（已废弃，推荐run.py）
│   └── run.py                    # 新入口（使用Orchestrator）
└── test/
    └── test_*.py                 # 各组件测试
```

---

## 5. 组件详细设计

### 5.1 IntentAgent（战略决策）

**核心职责**
1. 任务类型识别（8种task_type）
2. 信息提取（model, basin, algorithm, params）
3. 信息补全（自动填充缺失字段）
4. 扩展需求识别（runoff_coefficient, FDC等）

**主要接口**
```python
class IntentAgent(BaseAgent):
    def process(self, user_query: str) -> Dict:
        """
        Input: 用户自然语言查询
        Output: {
            "task_type": str,           # 8种类型之一
            "model_name": str,
            "basin_ids": List[str],
            "algorithm": str,
            "extra_params": Dict,
            "extended_needs": List[str],  # 仅extended_analysis
            "n_repeats": int,             # 仅repeated_experiment
            "data_path": str,             # 仅custom_data
            ...
        }
        """
```

**任务类型分类**
```python
TASK_TYPES = {
    "standard_calibration": "标准单任务率定",
    "info_completion": "缺省信息补全型率定",
    "iterative_optimization": "参数自适应迭代优化",
    "repeated_experiment": "重复实验（多随机种子）",
    "extended_analysis": "扩展分析（超出hydromodel功能）",
    "batch_processing": "批量处理（多流域/多算法）",
    "custom_data": "自定义数据路径",
    "error_handling": "错误处理测试"
}
```

**决策逻辑**（简化版）
- 检测关键词：重复/多次 → `repeated_experiment`
- 检测关键词：迭代/边界/调整范围 → `iterative_optimization`
- 检测关键词：径流系数/FDC → `extended_analysis`
- 检测信息完备度：缺失字段 → `info_completion`
- 检测批量：多流域/多算法 → `batch_processing`
- 默认 → `standard_calibration`

**信息补全机制**
- 补全model_name：默认 `xaj`
- 补全algorithm：默认 `SCE_UA`
- 补全time_period：从数据集获取可用时间（1990-2000）
- 推断data_source：根据basin_id格式（8位数字 → CAMELS_US）

### 5.2 TaskPlanner（战术拆解）

**核心职责**
1. 任务拆解（根据task_type）
2. 提示词生成（为每个subtask定制化）
3. 依赖关系管理
4. PromptPool历史案例管理

**主要接口**
```python
class TaskPlanner(BaseAgent):
    def process(self, intent_result: Dict) -> Dict:
        """
        Input: IntentAgent的输出
        Output: {
            "subtasks": [
                {
                    "id": str,
                    "type": str,  # calibration/evaluation/custom_analysis/statistical_analysis
                    "parameters": Dict,
                    "dependencies": List[str],
                    "generated_prompt": str
                },
                ...
            ]
        }
        """
```

**任务拆解策略**

| task_type | 拆解策略 | subtask数量 | 示例 |
|-----------|---------|------------|------|
| `standard_calibration` | 不拆解 | 1 | subtask_1: calibration |
| `info_completion` | 不拆解 | 1 | subtask_1: calibration |
| `iterative_optimization` | **不拆解** | 1 | subtask_1: iterative（内部循环） |
| `repeated_experiment` | N+1拆解 | N+1 | N个repetition + 1个statistical_analysis |
| `extended_analysis` | 1+M拆解 | 1+M | 1个calibration + M个custom_analysis |
| `batch_processing` | K拆解 | K | K个calibration（多流域/多算法） |

**关键设计点**：
- **实验3不拆解为多个phase**：TaskPlanner创建单一`iterative`任务，RunnerAgent内部循环处理
- **依赖关系**：custom_analysis和statistical_analysis依赖calibration任务
- **提示词生成**：根据subtask类型和parameters动态生成

**PromptPool**
- 存储历史成功案例
- 格式：`{task_type: [examples]}`
- Few-shot学习：为InterpreterAgent提供参考

### 5.3 InterpreterAgent（配置生成）

**核心职责**
1. LLM生成hydromodel配置（for standard/calibration任务）
2. 最小化配置（for custom_analysis任务）
3. 配置验证和自我修正（最多3次）

**主要接口**
```python
class InterpreterAgent(BaseAgent):
    def process(self, subtask: Dict, prompt_from_planner: str) -> Dict:
        """
        Input: TaskPlanner生成的单个subtask
        Output: hydromodel配置字典 或 最小化配置
        """
```

**双重逻辑**

**1. hydromodel任务**（calibration/evaluation）
```python
# System Prompt（简化）
"Generate complete hydromodel config with:
 - data_cfgs: {basin_ids, train_period, test_period, ...}
 - model_cfgs: {model_name, model_params}
 - training_cfgs: {algorithm, params, epochs}
 Output MUST be valid JSON."

# 生成完整配置
config = llm.generate(system_prompt, user_prompt)

# 验证配置（必需字段检查）
errors = validate_config(config)
if errors and attempt < 3:
    # 自我修正
    config = llm.correct(config, errors)
```

**2. custom_analysis任务**
```python
# System Prompt（简化）
"For custom_analysis tasks, generate minimal config:
 {
   'task_metadata': {
     'analysis_type': 'runoff_coefficient',
     'description': '...'
   }
 }"

# 生成最小化配置
minimal_config = llm.generate(system_prompt, user_prompt)

# 验证（只检查task_metadata存在）
```

**验证逻辑**
- hydromodel任务：检查`data_cfgs`, `model_cfgs`, `training_cfgs`
- custom_analysis任务：只检查`task_metadata`

**动态参数加载**
```python
# 从config.py加载算法默认参数
from configs.config import DEFAULT_SCE_UA_PARAMS, DEFAULT_PSO_PARAMS
# 合并用户指定参数和默认参数
final_params = {**DEFAULT_SCE_UA_PARAMS, **user_extra_params}
```

### 5.4 RunnerAgent（执行）

**核心职责**
1. 标准率定执行
2. 自动评估（calibration后）
3. 迭代优化执行（内部循环，实验3）
4. 统计分析（实验2A）
5. custom_analysis模式识别（跳过hydromodel执行）

**主要接口**
```python
class RunnerAgent(BaseAgent):
    def process(self, config: Dict, subtask: Dict) -> Dict:
        """
        Input: InterpreterAgent的配置 + subtask信息
        Output: {
            "execution_mode": str,  # calibrate/evaluate/iterative/skip
            "results": Dict,
            "metrics": Dict,
            ...
        }
        """
```

**执行模式**

**1. 标准率定**
```python
if subtask['type'] == 'calibration':
    # 执行率定
    calibrate(config)
    # 自动执行评估
    evaluate(config)
    # 解析结果
    results = parse_results()
```

**2. 迭代优化**（实验3）
```python
if subtask['type'] == 'iterative':
    iteration = 0
    range_scales = [1.0, 0.6, 0.42, 0.29, 0.2, 0.15]

    while iteration < max_iterations:
        # 使用当前range_scale执行率定
        config['training_cfgs']['param_range_file'] = f'param_range_iter{iteration}.yaml'
        calibrate(config)
        evaluate(config)

        # 检查停止条件
        if nse > 0.75:  # 达到优秀阈值
            break
        if abs(nse - prev_nse) < 0.001:  # 连续无改善
            break

        # 调整参数范围（以最优参数为中心）
        iteration += 1
        new_range = generate_param_range(
            best_params,
            range_scale=range_scales[iteration]
        )
        save_yaml(new_range, f'param_range_iter{iteration}.yaml')
```

**3. custom_analysis模式**
```python
if subtask.get('parameters', {}).get('task_type') == 'custom_analysis':
    # 跳过hydromodel执行
    return {"execution_mode": "skip", "message": "custom_analysis任务"}
```

**4. 统计分析**（实验2A）
```python
if subtask['type'] == 'statistical_analysis':
    # 聚合所有repetition结果
    all_nse = [subtask_results[i]['nse'] for i in range(n_repeats)]
    # 计算统计指标
    stats = {
        "mean_nse": np.mean(all_nse),
        "std_nse": np.std(all_nse),
        "ci_95": confidence_interval(all_nse, 0.95)
    }
    return stats
```

**智能参数范围调整机制**（实验3）
- **动态range_scale**：60% → 42% → 29% → 20% → 15%
- **以最优参数为中心**：`new_min = best_param - (max-min)*range_scale/2`
- **保持物理意义**：确保新范围在原始范围内
- **自动生成YAML**：每次迭代生成新的`param_range_iterN.yaml`

### 5.5 DeveloperAgent（分析 + 代码生成）

**核心职责**
1. 结果分析（NSE评估、建议生成）
2. 代码生成（custom_analysis任务）
3. 双LLM架构（通用模型思考 + 代码模型生成）

**主要接口**
```python
class DeveloperAgent(BaseAgent):
    def process(self, subtask: Dict, results: Dict) -> Dict:
        """
        Input: subtask + RunnerAgent结果
        Output: 分析报告 或 生成的代码
        """
```

**双LLM代码生成工作流**

**1. 检测custom_analysis任务**
```python
if subtask.get('parameters', {}).get('task_type') == 'custom_analysis':
    return _handle_custom_analysis_and_generate_code(subtask, results)
```

**2. 构建任务描述**
```python
# 预定义模板
TASK_TEMPLATES = {
    "runoff_coefficient": "计算流域径流系数（总径流量/总降水量）",
    "FDC": "绘制流量历时曲线（Flow Duration Curve）",
    ...
}

task_desc = TASK_TEMPLATES.get(analysis_type, "自定义分析")
```

**3. 通用LLM思考分析**
```python
# 使用通用模型（qwen-turbo / qwen3:8b）
system_prompt = "你是水文分析专家，分析用户需求并规划实现步骤"
user_prompt = f"任务：{task_desc}\n可用数据：{available_data}"

thought = general_llm.generate(system_prompt, user_prompt)
```

**4. 代码LLM生成脚本**
```python
# 使用代码专用模型（qwen-coder-turbo / deepseek-coder:6.7b）
code_system_prompt = """
生成完整的Python脚本：
- 包含type hints
- 详细注释
- 错误处理
- 进度提示
- 结果保存
"""

code_user_prompt = f"""
任务：{task_desc}
思考分析：{thought}
生成完整可运行的Python脚本。
"""

code = code_llm.generate(code_system_prompt, code_user_prompt)
```

**5. 保存代码**
```python
# 保存到 generated_code/
output_path = f"generated_code/{analysis_type}_analysis.py"
save_code(code, output_path)
```

**配置**
```python
# API模式
GENERAL_MODEL = "qwen-turbo"
CODE_MODEL = "qwen-coder-turbo"

# Ollama模式
GENERAL_MODEL = "qwen3:8b"
CODE_MODEL = "deepseek-coder:6.7b"
```

**结果分析**（标准任务）
```python
def _analyze_standard_results(results: Dict) -> str:
    nse = results['metrics']['NSE']

    # NSE质量评估
    if nse > 0.75:
        quality = "优秀（Excellent）"
    elif nse > 0.65:
        quality = "良好（Good）"
    elif nse > 0.50:
        quality = "一般（Fair）"
    else:
        quality = "较差（Poor）"

    # 生成建议
    suggestions = []
    if nse < 0.75:
        suggestions.append("可考虑延长训练期或增加迭代轮数")
    if params_at_boundary:
        suggestions.append("部分参数收敛到边界，建议调整参数范围")

    report = f"""
📊 质量评估: {quality}
   NSE={nse:.2f}, RMSE={rmse:.2f}

🔧 最优参数: {len(params)} 个
   {format_params(params)}

💡 改进建议:
{format_suggestions(suggestions)}
"""
    return report
```

### 5.6 Orchestrator（编排器）

**核心职责**
- 统一入口：协调5个Agent的执行
- 流程编排：IntentAgent → TaskPlanner → InterpreterAgent → RunnerAgent → DeveloperAgent
- 错误处理：捕获异常，提供友好提示
- 结果聚合：收集所有subtask结果

**主要接口**
```python
class Orchestrator:
    def process(self, user_query: str, backend: str = "api") -> Dict:
        """
        Input: 用户查询 + LLM后端选择
        Output: {
            "intent_result": Dict,
            "task_plan": Dict,
            "subtask_results": List[Dict],
            "final_analysis": str
        }
        """

        # 1. IntentAgent
        intent_result = self.intent_agent.process(user_query)

        # 2. TaskPlanner
        task_plan = self.task_planner.process(intent_result)

        # 3-5. 遍历所有subtask
        subtask_results = []
        for subtask in task_plan['subtasks']:
            # 3. InterpreterAgent生成配置
            config = self.interpreter_agent.process(subtask, subtask['generated_prompt'])

            # 4. RunnerAgent执行
            exec_result = self.runner_agent.process(config, subtask)

            # 5. DeveloperAgent分析
            analysis = self.developer_agent.process(subtask, exec_result)

            subtask_results.append({
                "subtask": subtask,
                "config": config,
                "execution": exec_result,
                "analysis": analysis
            })

        return {"subtask_results": subtask_results, ...}
```

**使用示例**
```bash
# 方式1：直接使用Orchestrator
python run.py --query "率定流域01013500" --backend api

# 方式2：交互模式
python run.py --backend api
> 请输入查询：率定流域01013500
```

---

## 6. 数据流与协作

### 6.1 完整数据流

```
用户输入
  ↓
[IntentAgent]
  Output: intent_result = {
    task_type: "repeated_experiment",
    model_name: "gr4j",
    basin_ids: ["01013500"],
    algorithm: "SCE_UA",
    n_repeats: 20
  }
  ↓
[TaskPlanner]
  Input: intent_result
  Output: task_plan = {
    subtasks: [
      {id: "subtask_1", type: "calibration", parameters: {repetition: 1}},
      {id: "subtask_2", type: "calibration", parameters: {repetition: 2}},
      ...
      {id: "subtask_20", type: "calibration", parameters: {repetition: 20}},
      {id: "subtask_21", type: "statistical_analysis", dependencies: ["subtask_1", ..., "subtask_20"]}
    ]
  }
  ↓
[InterpreterAgent] (for each subtask)
  Input: subtask_1 + generated_prompt
  Output: config_1 = {
    data_cfgs: {...},
    model_cfgs: {...},
    training_cfgs: {algorithm: "SCE_UA", random_seed: 1, ...}
  }
  ↓
[RunnerAgent] (for each subtask)
  Input: config_1 + subtask_1
  Output: result_1 = {
    execution_mode: "calibrate",
    best_params: [0.77, 0.00023, 0.30, 0.70],
    metrics: {NSE: 0.68, RMSE: 1.45}
  }
  ↓
[DeveloperAgent] (for each subtask)
  Input: subtask_1 + result_1
  Output: analysis_1 = "📊 Repetition 1: NSE=0.68 (Good)"

  (对于subtask_21 - statistical_analysis)
  Input: subtask_21 + all_results
  Output: stats_analysis = """
  📊 统计分析（20次重复）
     Mean NSE: 0.67 ± 0.03
     95% CI: [0.64, 0.70]
     稳定性：良好
  """
```

### 6.2 组件协作时序图

```
User → Orchestrator → IntentAgent → TaskPlanner → InterpreterAgent → RunnerAgent → DeveloperAgent
  |         |              |             |                |                |               |
  |         |              |             |                |                |               |
  query     process()      process()     process()        process()        process()       process()
  |         |              |             |                |                |               |
  |         |        intent_result       |                |                |               |
  |         |  <------------|             |                |                |               |
  |         |              |      task_plan              |                |               |
  |         |              | <-----------|                |                |               |
  |         |              |             |                |                |               |
  |         |              |             |    (for each subtask)          |               |
  |         |              |             |       config                   |               |
  |         |              |             | <--------------|                |               |
  |         |              |             |                |   exec_result  |               |
  |         |              |             |                | <--------------|               |
  |         |              |             |                |                |   analysis    |
  |         |              |             |                |                | <-------------|
  |         |              |             |                |                |               |
  |         |   final_result (aggregated)                                  |               |
  | <-------|--------------|-------------|----------------|----------------|---------------|
  |
 Display
```

### 6.3 关键协作点

**1. IntentAgent → TaskPlanner**
- 传递：task_type, extracted_info（model, basin, algorithm, extra_params, extended_needs, n_repeats等）
- TaskPlanner根据task_type选择拆解策略

**2. TaskPlanner → InterpreterAgent**
- 传递：subtask（含type, parameters, generated_prompt）
- InterpreterAgent根据subtask type选择配置生成策略（完整配置 vs 最小化配置）

**3. InterpreterAgent → RunnerAgent**
- 传递：config（hydromodel配置 或 最小化配置）
- RunnerAgent根据subtask.parameters.task_type决定执行模式（calibrate/evaluate/skip）

**4. RunnerAgent → DeveloperAgent**
- 传递：execution_results（params, metrics, mode）
- DeveloperAgent根据subtask.parameters.task_type选择处理方式（分析 vs 代码生成）

**5. 依赖关系处理**
- TaskPlanner标记dependencies
- Orchestrator按拓扑排序执行subtasks
- 后续任务可访问依赖任务的results

---

## 7. 实验实现要点

### 7.1 实验3：迭代优化关键点

**设计决策**：TaskPlanner不拆解为多个phase，RunnerAgent内部循环

**原因**：
- 参数范围调整需要上一轮最优参数
- 停止条件需要连续NSE比较
- 拆解会导致状态传递复杂

**实现**：
```python
# TaskPlanner (task_planner.py)
if task_type == "iterative_optimization":
    subtasks = [{
        "id": "subtask_1",
        "type": "iterative",  # 特殊类型
        "parameters": {
            "model_name": "gr4j",
            "basin_id": "01013500",
            "max_iterations": 5
        }
    }]

# RunnerAgent (runner_agent.py)
if subtask['type'] == 'iterative':
    # 内部循环执行
    for i in range(max_iterations):
        calibrate_with_range_scale(range_scales[i])
        if should_stop():
            break
```

### 7.2 实验4：代码生成关键点

**设计决策**：custom_analysis任务跳过hydromodel执行

**原因**：
- custom_analysis需要的是代码生成，不需要率定
- 避免InterpreterAgent生成无效的hydromodel配置

**实现**：
```python
# TaskPlanner为custom_analysis添加task_type字段
subtask['parameters']['task_type'] = 'custom_analysis'

# InterpreterAgent识别custom_analysis，生成最小化配置
if 'custom_analysis' in prompt:
    config = {"task_metadata": {"analysis_type": "runoff_coefficient"}}

# RunnerAgent识别custom_analysis，跳过执行
if subtask.get('parameters', {}).get('task_type') == 'custom_analysis':
    return {"execution_mode": "skip"}

# DeveloperAgent处理custom_analysis，调用双LLM生成代码
if subtask.get('parameters', {}).get('task_type') == 'custom_analysis':
    return _handle_custom_analysis_and_generate_code(subtask, results)
```

### 7.3 实验2A：重复实验关键点

**设计决策**：N+1拆解，最后一个subtask做统计分析

**实现**：
```python
# TaskPlanner
subtasks = []
for i in range(n_repeats):
    subtasks.append({
        "id": f"subtask_{i+1}",
        "type": "calibration",
        "parameters": {"repetition": i+1}
    })
# 添加统计分析任务
subtasks.append({
    "id": f"subtask_{n_repeats+1}",
    "type": "statistical_analysis",
    "dependencies": [f"subtask_{i+1}" for i in range(n_repeats)]
})

# RunnerAgent识别statistical_analysis
if subtask['type'] == 'statistical_analysis':
    # 从依赖任务获取所有NSE
    all_nse = [prev_results[dep]['nse'] for dep in subtask['dependencies']]
    stats = compute_statistics(all_nse)
    return stats
```

---

## 8. 已知问题与修复

### 8.1 实验4：Custom Analysis任务路由问题（2025-01-24已修复）

**问题**：
- TaskPlanner创建的custom_analysis任务parameters缺少`task_type`字段
- InterpreterAgent为custom_analysis生成完整hydromodel配置，导致验证错误
- RunnerAgent无法识别custom_analysis模式，误识别为"calibrate"

**修复**：
1. **TaskPlanner**：添加 `"task_type": "custom_analysis"` 到parameters
2. **InterpreterAgent**：区分hydromodel任务和custom_analysis任务，为后者生成最小化配置
3. **RunnerAgent**：添加custom_analysis模式识别逻辑

**测试**：`test/test_exp4_fixes.py` 全部通过

### 8.2 实验3：迭代优化架构问题（2025-01-23已修复）

**问题**：两次率定使用相同参数范围，NSE值相同

**修复**：TaskPlanner创建单一iterative任务，RunnerAgent内部循环处理

### 8.3 实验1：JSON解析和Config使用（2025-01-22已修复）

**问题**：
- LLM返回markdown包裹的JSON导致解析失败
- InterpreterAgent使用hardcoded参数而非config.py

**修复**：
- llm_interface.py：添加markdown code block提取
- interpreter_agent.py：动态加载config.py参数

---

## 9. 未来规划

### 9.1 Checkpoint/Resume系统

**目标**：支持长任务中断恢复

**计划**：
- CheckpointManager：保存/加载任务进度
- Orchestrator集成：自动checkpoint after每个subtask
- 命令行支持：`--resume SESSION_ID`

**用例**：
- 批量率定20个流域，中断后从第11个继续
- 100次重复实验，暂停后恢复

### 9.2 RAG知识库集成

**目标**：知识增强的工作流生成

**计划**：
- 向量数据库（FAISS）：存储历史实验、论文知识
- 知识检索：为IntentAgent/TaskPlanner提供参考
- 动态prompt：根据检索结果调整提示词

### 9.3 Web界面

**目标**：Gradio/Streamlit UI

**功能**：
- 交互式查询输入
- 实时进度显示
- 结果可视化（图表、参数分布）
- 历史实验管理

### 9.4 多流域并行处理

**目标**：提升批量处理性能

**计划**：
- 并行执行独立subtasks
- 资源管理（CPU/GPU分配）
- 进度聚合显示

---

## 附录

### A. 配置文件说明

**configs/definitions_private.py**（用户创建）
```python
# API配置
OPENAI_API_KEY = "sk-your-qwen-api-key"
OPENAI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 路径配置
PROJECT_DIR = r"D:\your\path\to\HydroAgent"
DATASET_DIR = r"D:\your\path\to\data"
RESULT_DIR = r"D:\your\path\to\results"
```

**configs/config.py**（全局参数）
```python
# LLM配置
DEFAULT_MODEL = "qwen-turbo"
CODE_MODEL = "qwen-coder-turbo"  # 代码专用模型
TEMPERATURE = 0.1

# 数据配置
DEFAULT_TRAIN_PERIOD = ["1985-10-01", "1995-09-30"]
DEFAULT_TEST_PERIOD = ["2005-10-01", "2014-09-30"]

# 算法默认参数
DEFAULT_SCE_UA_PARAMS = {"rep": 1000, "ngs": 300, "kstop": 500}
DEFAULT_PSO_PARAMS = {"max_iterations": 500, "swarm_size": 50}

# 性能阈值
NSE_EXCELLENT = 0.75
NSE_GOOD = 0.65
NSE_FAIR = 0.50
```

### B. 常用命令

```bash
# 交互模式
python run.py --backend api

# 单次查询
python run.py --query "率定流域01013500" --backend api

# 运行实验
python experiment/exp_1a_standard.py --backend api --mock
python experiment/exp_3_iterative_optimization.py --backend api
python experiment/exp_4_extended_analysis.py --backend api --model qwen-turbo --code-model qwen-coder-turbo

# 测试
python test/test_intent_agent.py --backend api
python test/test_developer_agent_pipeline.py
```

### C. 输出结构

```
results/
└── YYYYMMDD_HHMMSS/                    # 会话时间戳
    └── gr4j_SCE_UA_YYYYMMDD_HHMMSS/    # 实验时间戳
        ├── calibration_results.json    # 率定结果
        ├── calibration_config.yaml     # 配置
        ├── basins_metrics.csv          # 评估指标
        ├── param_range_iter0.yaml      # 参数范围（实验3）
        ├── param_range_iter1.yaml
        └── gr4j_evaluation_results.nc  # 评估结果

generated_code/                         # 生成的代码（实验4）
├── runoff_coefficient_analysis.py
└── plot_fdc.py

logs/                                   # 日志
└── run_YYYYMMDD_HHMMSS.log
```

---

**最后更新**: 2025-11-26
**架构版本**: v4.0
**文档维护**: HydroAgent Team
