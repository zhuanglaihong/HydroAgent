# HydroAgent 架构设计（终版）

**Author**: HydroAgent Team
**Date**: 2025-01-24 (Last Updated)
**Version**: 3.1 (Implementation Complete - Phase 1-4)
**Status**: Core Implementation Complete, Testing in Progress

---

## 📋 目录

- [1. 实施状态概览](#1-实施状态概览)
- [2. 设计理念](#2-设计理念)
- [3. 核心实验场景](#3-核心实验场景)
- [4. 系统架构](#4-系统架构)
- [5. 组件详细设计](#5-组件详细设计)
- [6. 数据流与协作](#6-数据流与协作)
- [7. 实验场景实现](#7-实验场景实现)
- [8. 已知问题与修复](#8-已知问题与修复)
- [9. 实施计划](#9-实施计划)

---

## 1. 实施状态概览

### 1.1 总体进度

| Phase | 状态 | 完成时间 | 说明 |
|-------|------|---------|------|
| **Phase 1: IntentAgent增强** | ✅完成 | 2025-01-22 | 支持7种任务类型，信息补全功能 |
| **Phase 2: TaskPlanner** | ✅完成 | 2025-01-22 | 任务拆解，提示词生成，PromptPool |
| **Phase 3: InterpreterAgent** | ✅完成 | 2025-01-24 | LLM配置生成，支持custom_analysis |
| **Phase 4: RunnerAgent & DeveloperAgent增强** | ✅完成 | 2025-01-24 | 代码生成，统计分析，迭代优化 |
| **Phase 5: 端到端验验证* | 🔄 进行中 | 预计2025-01-25 | 实验1-5全面测试 |

### 1.2 实验验证状态

| 实验 | 状态 | 测试结果 | 备注 |
|------|------|---------|------|
| **实验1：标准流域验验证* | ✅通过 | NSE=0.68 (Good) | 已修复JSON解析和config使用问题 |
| **实验2A：全信息率定** | ✅通过 | 参数提取正常 | - |
| **实验2B：缺省信息补全** | ✅通过 | 信息自动补全 | - |
| **实验2C：自定义数据** | 🟡 待测试 | - | - |
| **实验3：参数自适应优化** | ✅修复完成 | 迭代逻辑重构 | 修复了线性架构问题 |
| **实验4：代码生成扩扩展* | ✅修复完成 | custom_analysis路由正常 | 已修复task_type路由和最小化配置 |
| **实验5：稳定性验验证* | 🟡 待测试 | - | - |

### 1.3 核心功能实现清单

#### IntentAgent
- ✅ 7种任务类型识别（standard, info_completion, iterative, repeated, extended, batch, custom_data）
- ✅ 信息补全（model_name, algorithm, time_period, data_source）
- ✅ 提取扩展分析需求（runoff_coefficient, FDC等）
- ✅ 提取重复次数和自定义数据路径

#### TaskPlanner
- ✅ 任务拆解逻辑（所有7种task_type）
- ✅ 提示词生成（每个子任务）
- ✅ 依赖关系管理（dependencies字段）
- ✅ PromptPool（历史案例管理）
- ✅ **为custom_analysis任务添加task_type字段**（2025-01-24修复）

#### InterpreterAgent
- ✅ LLM驱动的配置生成
- ✅ 配置验证和自我修正（最多3次）
- ✅ 动态加载algorithm参数（config.py）
- ✅ **支持custom_analysis最小化配置**（2025-01-24新增）
- ✅ **双重验证逻辑**（hydromodel任务 vs custom_analysis任务）

#### RunnerAgent
- ✅ 标准率定执行
- ✅ 自动评估（calibration后）
- ✅ 边界检查重率定（实验3）
- ✅ 统计分析（实验5）
- ✅ **custom_analysis模式识别**（2025-01-24修复）
- ✅ 智能参数范围调整

#### DeveloperAgent
- ✅ 结果分析和建议生成
- ✅ **完整代码生成工作流**（2025-01-24完成）
- ✅ **_handle_custom_analysis_and_generate_code()**
- ✅ **_build_task_description()预定义模板**
- ✅ **双LLM架构（通用LLM + 代码LLM）**

### 1.4 最近修复（2025-01-24）

#### 实验4: Custom Analysis任务路由问题
**问题**：
- TaskPlanner创建的custom_analysis任务parameters缺少`task_type`字段
- InterpreterAgent为custom_analysis生成完整hydromodel配置，导致`data_source_type: "custom"`错误
- RunnerAgent无法识别custom_analysis模式，误识别为"calibrate"

**修复**：
1. **TaskPlanner (task_planner.py:397)**：添加 `"task_type": "custom_analysis"` 到parameters
2. **InterpreterAgent (interpreter_agent.py:93-189, 393-405, 270-272)**：
   - 更新system prompt，区分hydromodel任务和custom_analysis任务
   - 为custom_analysis生成最小化配置（只包含task_metadata）
   - 修改validation逻辑，支持最小化配置验证
   - 修改workspace设置，只对hydromodel任务设置output_dir
3. **RunnerAgent (runner_agent.py:267-276)**：添加custom_analysis模式的特殊日志处理

**测试验验证*：`test/test_exp4_fixes.py` 全部通过

#### 实验3: 迭代优化架构问题
**问题**：两次率定使用相同参数范围，NSE值相同

**修复**：TaskPlanner创建单一iterative任务而非两个独立任务，RunnerAgent内部循环处理

#### 实验1: JSON解析和Config使用
**问题**：
- LLM返回markdown包裹的JSON导致解析失败
- InterpreterAgent使用hardcoded参数而非config.py

**修复**：
- llm_interface.py：添加markdown code block提取
- interpreter_agent.py：动态加载config.py参数

---

## 2. 设计理念

### 2.1 核心原则

> **实验驱动，分层决策，职责清晰**

1. **战略与战术分离：IntentAgent决策"要做什么"，TaskPlanner决策"怎么做"
2. **任务拆解与配置生成分离：TaskPlanner拆解任务，InterpreterAgent生成config
3. **逻辑复杂性与执行复杂性隔离：TaskPlanner处理组合逻辑，Runner只负责执行
4. **支持5个核心实验：所有设计围绕实际实验需求展开

### 2.2 设计目标

| 实验 | 核心需求| 架构支持 |
|------|---------|---------|
| **实验1：标准流域验证** | 简单任务直接执行| IntentAgent识别 直接执行 |
| **实验2：通用性鲁棒性** | 信息补全、多种输入| IntentAgent补全 + Interpreter智能生成 |
| **实验3：参数自适应** | 两阶段迭代优化| TaskPlanner拆解 + 错误反馈 |
| **实验4：代码生成扩展** | 超出hydromodel功能 | DeveloperAgent编写额外脚本 |
| **实验5：稳定性验证** | 重复实验统计 | TaskPlanner生成多个子任务|

---

## 3. 核心实验场景

### 实验1：标准流域验证（简单任务）

**用户输入**
```
"率定流域 01013500，使用标准XAJ 模型
```

**系统行为**
1. IntentAgent → 识别标准率定"任务
2. TaskPlanner → 无需拆解，生成单一提示词
3. InterpreterAgent → 生成config
4. RunnerAgent → 执行率定
5. DeveloperAgent → 分析结果，NSE > 0.8

---

### 实验2：通用性与鲁棒性（信息补全

**场景A - 全信息**
```
"使用 SCE-UA 算法，设→rep=5000, ngs=1000，率定CAMELS_US 01013500 流域，时期1990-2000
```

**场景B - 缺省信息**
```
"帮我率定流域 01013500
```
- IntentAgent识别：CAMELS_US流域，补全默认算法、时间范围

**场景C - 模糊信息**
```
"用我 D → my_data 文件夹里的数据跑一下模型
```
- IntentAgent识别：自定义数据，推断data_source_type
- InterpreterAgent生成适配的config

---

### 实验3：参数自适应优化（两阶段迭代

**用户输入**
```
"率定流域 01013500，如果参数收敛到边界，自动调整范围重新率定
```

**系统行为**
1. IntentAgent → 识别迭代优化"任务
2. TaskPlanner → 拆解为两阶段
   - Phase 1: 粗率定（宽泛参数范围，rep=500
   - Phase 2: 精率定（调整后的参数范围，rep=2000
3. RunnerAgent → 执行Phase 1
4. DeveloperAgent → 分析是否触发边界效应
5. 如触TaskPlanner生成Phase 2提示词（调整param_range
6. InterpreterAgent → 生成新config（param_range_refined.yaml
7. RunnerAgent → 执行Phase 2
8. DeveloperAgent → 对比NSE提升

---

### 实验4：代码生成与工具扩展（超出功能）

**用户输入**
```
"率定完成后，请帮我计算流域的径流系数，并画一张流路历时线(FDC)
```

**系统行为**
1. IntentAgent → 识别率定 + 扩展分析"任务
2. TaskPlanner → 拆解为：
   - Task 1: 标准率定
   - Task 2: 额外分析（超出hydromodel功能
3. RunnerAgent → 执行Task 1
4. DeveloperAgent → 识别Task 2需要代码生
5. DeveloperAgent → 编写 `calc_runoff_coef.py` `plot_fdc.py`
6. RunnerAgent → 执行额外脚本
7. DeveloperAgent → 汇总所有果

---

### 实验5：稳定性验证（重复实证

**用户输入**
```
"重复率定流域 01013500 十次，使用不同随机种子
```

**系统行为**
1. IntentAgent → 识别重复实验"任务
2. TaskPlanner → 拆解0个子任务
   ```python
   [
       {"basin": "01013500", "random_seed": 1},
       {"basin": "01013500", "random_seed": 2},
       ...
       {"basin": "01013500", "random_seed": 10}
   ]
   ```
3. InterpreterAgent → 为每个子任务生成config
4. RunnerAgent → 批量执行
5. DeveloperAgent → 计算NSE均值和标准

---

## 3. 系统架构

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Query                               │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                   IntentAgent (战略决策✅                       │
│ 职责✅                                                          │
│ 1. 提取关键信息（模型、流域、算法、参数等✅                        │
✅ 2. 决策任务类型：标准定| 信息补全 | 迭代优化 | 重复实验 | 扩展功能✅
│ 3. 补全缺失信息（默认值、推断）                                    │
│ 输出：{"task_type": "...", "intent_data": {...}}                │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│             TaskPlanner (战术拆解层，原ConfigAgent)              │
│ 职责✅                                                          │
│ 1. 根据task_type决定是否拆解                                      │
│ 2. 处理变量组合、逻辑依赖                                          │
│ 3. 为每个子任务生成提示词（Prompt✅                               │
│ 输出：[{"subtask_id": 1, "prompt": "...", "params": {...}}, ...] │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                     Prompt Pool                                 │
│ 职责✅                                                          │
│ 1. 存储每个子任务的提示词                                         │
│ 2. 历史成功案例参考（相似任务检索）                                 │
│ 3. 提示词模板理                                                │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│             InterpreterAgent (配置生成层，新件                │
│ 职责✅                                                          │
│ 1. 根据提示词生成hydromodel格式的config                           │
│ 2. 验证config有效✅                                             │
│ 3. 自我修正（如验证失败✅                                         │
│ 输出：{"config": {...}, "config_file": "config.yaml"}           │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                   RunnerAgent (执行✅                          │
│ 职责✅                                                          │
│ 1. 执行hydromodel.calibrate/evaluate                            │
│ 2. 执行额外的Python脚本（如DeveloperAgent生成的）                  │
│ 3. 捕获错误和日✅                                                │
│ 输出：{"success": True/False, "result": {...}, "error": "..."}  │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
                    ┌────────┴────────
                    │  Error?        │
                    └────┬────────┬───
                    Yes → No
                         │       │
            ┌──────────────── ┌──────────────────────
            │反馈给TaskPlanner✅ ✅ DeveloperAgent      │
            │✅Interpreter  ✅ ✅ (后处理分析层)        │
            │重新生成config   ✅ ✅ 1. 分析结果          │
            └──────────────── → 2. 生成报告          ↓
 → 3. 编写额外代码（验）│
                                │ 4. 统计分析（证  │
                                └──────────────────────
                                         ↓
                                  Final Results
```

### 3.2 组件对比（旧 vs 新）

| 组件 | 旧构| 新构| 变化 |
|------|--------|--------|------|
| IntentAgent | 只提取息| **提取信息 + 决策任务类型** | 增强 |
| ConfigAgent | 规则生成config | **TaskPlanner** (任务拆解 + 提示词生 | 🔄 **改名+重构** |
| ( | - | **InterpreterAgent** (LLM生成config) | 🆕 **新增** |
| RunnerAgent | 执行hydromodel | 执行hydromodel + 额外脚本 | 增强 |
| DeveloperAgent | 结果分析 | 结果分析 + 代码生成 + 统计 | 增强 |
| PromptManager | 静态文件理| **Prompt Pool** (动态存+ 索 | 🔄 **重构** |

---

## 4. 组件详细设计

### 4.1 IntentAgent（战略决策

#### 职责扩展

**原职*：提取关键息
```python
{
    "intent": "calibration",
    "model_name": "gr4j",
    "basin_id": "01013500",
    "algorithm": "SCE_UA"
}
```

**新职*：提取息+ **决策任务类型**
```python
{
    "intent": "calibration",
    "task_type": "iterative_optimization",  # 🆕 任务类型
    "model_name": "gr4j",
    "basin_id": "01013500",
    "algorithm": "SCE_UA",
    "extra_params": {...},
    "strategy": {  # 🆕 战略信息
        "phases": ["coarse_calibration", "fine_calibration"],
        "trigger": "boundary_effect"
    }
}
```

#### 任务类型分类

```python
TASK_TYPES = {
    "standard_calibration": "标准单任务定,
    "info_completion": "缺省信息补全型定,
    "iterative_optimization": "两阶段迭代优化,
    "repeated_experiment": "重复实验（多随机种子,
    "extended_analysis": "扩展分析（超出hydromodel功能,
    "batch_processing": "批量处理（多流域/多算法）"
}
```

#### 决策逻辑

```python
def decide_task_type(self, user_query: str, extracted_info: Dict) -> str:
    """决策任务类型"""

    # 检测关键词
    if "重复" in user_query or "多次" in user_query:
        return "repeated_experiment"

    if "迭代" in user_query or "边界" in user_query or "调整范围" in user_query:
        return "iterative_optimization"

    if "径流系数" in user_query or "FDC" in user_query:
        return "extended_analysis"

    # 检测信息完备度
    required_fields = ["model_name", "basin_id", "algorithm"]
    missing = [f for f in required_fields if not extracted_info.get(f)]
    if missing:
        return "info_completion"

    # 检测批量务
    if len(extracted_info.get("basins", [])) > 1 or len(extracted_info.get("algorithms", [])) > 1:
        return "batch_processing"

    return "standard_calibration"
```

#### 信息补全

```python
def complete_missing_info(self, extracted_info: Dict) -> Dict:
    """补全缺失信息"""

    # 补全模型
    if not extracted_info.get("model_name"):
        extracted_info["model_name"] = "xaj"  # 默认XAJ

    # 补全算法
    if not extracted_info.get("algorithm"):
        extracted_info["algorithm"] = "SCE_UA"

    # 补全时间范围
    if not extracted_info.get("train_period"):
        # 从数据集获取可用时间，取 → 0
        extracted_info["train_period"] = ["1990-01-01", "2000-12-31"]

    # 识别流域ID格式 → 推断数据
    basin_id = extracted_info.get("basin_id", "")
    if basin_id.startswith("0") and len(basin_id) == 8:
        extracted_info["data_source"] = "camels_us"

    return extracted_info
```

---

### 4.2 TaskPlanner（战术拆解层，原ConfigAgent

#### 核心职责

1. **任务拆解**：根据task_type决定是否拆解
2. **组合逻辑**：处理多流域、多算法、多时段的笛卡尔
3. **提示词生*：为每个子任务生成详细的提示词
4. **依赖管理**：处理阶段性任务的依赖关系（如实验3的两阶段

#### 接口设计

```python
class TaskPlanner(BaseAgent):
    """任务规划智能体（原ConfigAgent""

    def process(self, input_data: Dict) -> Dict:
        """
        处理任务规划

        Args:
            input_data: {
                "intent_result": {
                    "task_type": "...",
                    "intent_data": {...}
                }
            }

        Returns:
            {
                "success": True,
                "tasks": [
                    {
                        "subtask_id": 1,
                        "prompt": "...",
                        "params": {...},
                        "dependencies": []  # 依赖的子任务ID
                    },
                    ...
                ]
            }
        """
        intent_result = input_data["intent_result"]
        task_type = intent_result["task_type"]

        if task_type == "standard_calibration":
            # 简单任务，不解
            return self._create_single_task(intent_result)

        elif task_type == "repeated_experiment":
            # 重复实验，生成N个相同任务（不同随机种子
            return self._create_repeated_tasks(intent_result)

        elif task_type == "iterative_optimization":
            # 两阶段任务，Phase 2依赖Phase 1
            return self._create_iterative_tasks(intent_result)

        elif task_type == "batch_processing":
            # 批量任务，笛卡尔
            return self._create_batch_tasks(intent_result)

        elif task_type == "extended_analysis":
            # 标准任务 + 额外分析
            return self._create_extended_tasks(intent_result)

        else:
            return self._create_single_task(intent_result)
```

#### 示例：重复实验解

```python
def _create_repeated_tasks(self, intent: Dict) -> Dict:
    """创建重复实验任务（证""
    n_repeats = intent.get("n_repeats", 10)

    tasks = []
    for i in range(1, n_repeats + 1):
        task = {
            "subtask_id": i,
            "prompt": self._generate_prompt(intent, seed=i),
            "params": {
                "model_name": intent["intent_data"]["model_name"],
                "basin_id": intent["intent_data"]["basin_id"],
                "algorithm": intent["intent_data"]["algorithm"],
                "random_seed": i  # 不同随机种子
            },
            "dependencies": []
        }
        tasks.append(task)

    return {"success": True, "tasks": tasks}
```

#### 提示词生

```python
def _generate_prompt(self, intent: Dict, **kwargs) -> str:
    """为子任务生成提示词""

    template = """
    ### 任务描述
    用户需要{intent}，目标流域为{basin_id}

    ### 配置要求
    - 模型: {model_name}
    - 算法: {algorithm}
    - 随机种子: {random_seed}

    ### 参考历
    {历史成功案例}

    请生成hydromodel配置JSON个
    """

    # 从Prompt Pool获取历史案例
    similar_cases = self.prompt_pool.get_similar_cases(intent)

    prompt = template.format(
        intent=intent["intent_data"]["intent"],
        basin_id=intent["intent_data"]["basin_id"],
        model_name=intent["intent_data"]["model_name"],
        algorithm=intent["intent_data"]["algorithm"],
        random_seed=kwargs.get("seed", 1),
        历史成功案例=self._format_cases(similar_cases)
    )

    return prompt
```

---

### 4.3 Prompt Pool（提示词存储

#### 职责

1. 存储每个子任务的提示词
2. 存储历史成功案例
3. 相似任务索
4. 提示词模板理

#### 数据结构

```python
{
    "prompts": {
        "task_1": {
            "prompt": "...",
            "params": {...},
            "timestamp": "2025-01-22T10:00:00"
        },
        ...
    },
    "history": [
        {
            "task_type": "standard_calibration",
            "intent": {...},
            "config": {...},
            "result": {"NSE": 0.85},
            "success": True
        },
        ...
    ],
    "templates": {
        "standard_calibration": "...",
        "iterative_optimization": "...",
        ...
    }
}
```

#### 简化验

```python
class PromptPool:
    """提示词池（简化版""

    def __init__(self, pool_dir: Path):
        self.pool_dir = pool_dir
        self.prompts = {}
        self.history = []
        self.max_history = 50

    def store_prompt(self, task_id: str, prompt: str, params: Dict):
        """存储子任务提示词"""
        self.prompts[task_id] = {
            "prompt": prompt,
            "params": params,
            "timestamp": datetime.now().isoformat()
        }

    def get_similar_cases(self, intent: Dict, limit: int = 3) -> List[Dict]:
        """检索相似成功例""
        # 简单匹配：相同模型 + 相同算法
        similar = []
        for case in self.history:
            if (case["intent"].get("model_name") == intent.get("model_name") and
                case["intent"].get("algorithm") == intent.get("algorithm") and
                case["success"]):
                similar.append(case)

        return similar[-limit:]  # 返回最近的N个

    def add_history(self, task_type: str, intent: Dict, config: Dict, result: Dict, success: bool):
        """添加历史记录"""
        self.history.append({
            "task_type": task_type,
            "intent": intent,
            "config": config,
            "result": result,
            "success": success,
            "timestamp": datetime.now().isoformat()
        })

        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
```

---

### 4.4 InterpreterAgent（配置生成层，新组件

#### 职责

**专注于一件事**：根据提示词生成hydromodel格式的config

#### 为什么独立出来？

| 职责 | 负责组件 |
|------|---------|
| 任务拆解、组合逻辑 | TaskPlanner |
| **Config JSON生成** | **InterpreterAgent** 专业|
| 执行hydromodel | RunnerAgent |

#### 接口设计

```python
class InterpreterAgent(BaseAgent):
    """配置解释器（新组件）"""

    def process(self, input_data: Dict) -> Dict:
        """
        生成hydromodel config

        Args:
            input_data: {
                "prompt": "...",  # 来自TaskPlanner
                "params": {...},  # 子任务参
                "error_log": "..." (可选，用于重试)
            }

        Returns:
            {
                "success": True,
                "config": {...},
                "config_file": "config.yaml" (可
            }
        """
        prompt = input_data["prompt"]
        params = input_data["params"]
        error_log = input_data.get("error_log")

        # 构建完整提示词
        full_prompt = self._build_full_prompt(prompt, error_log)

        # LLM生成config
        config = self._llm_generate_config(full_prompt)

        # 验证
        is_valid, errors = self._validate_config(config, params)

        if not is_valid:
            # 自我修正
            config = self._llm_self_correct(config, errors)

        return {
            "success": True,
            "config": config
        }

    def _build_full_prompt(self, base_prompt: str, error_log: Optional[str]) -> str:
        """构建完整提示词""
        parts = [base_prompt]

        # 添加config schema
        parts.append(self._get_config_schema())

        # 添加错误反馈
        if error_log:
            parts.append(f"\n### ⚠️ 上次执行失败\n{error_log}\n请修正配置)

        return "\n\n".join(parts)

    def _llm_generate_config(self, prompt: str) -> Dict:
        """LLM生成config"""
        messages = [
            {"role": "system", "content": "你是hydromodel配置生成器，输出有效JSON个},
            {"role": "user", "content": prompt}
        ]

        response = self.llm_interface.chat(messages)
        config = self._parse_json(response)

        return config

    def _validate_config(self, config: Dict, params: Dict) -> tuple[bool, List[str]]:
        """验证config"""
        errors = []

        # 必需字段
        if "data_cfgs" not in config:
            errors.append("缺少data_cfgs")

        # 参数一致
        if config.get("model_cfgs", {}).get("model_name") != params.get("model_name"):
            errors.append(f"模型不一 → 期望{params.get('model_name')}")

        return len(errors) == 0, errors

    def _llm_self_correct(self, config: Dict, errors: List[str]) -> Dict:
        """LLM自我修正"""
        prompt = f"配置有错\n{json.dumps(config, indent=2)}\n\n错误:\n{errors}\n\n请修正

        messages = [
            {"role": "system", "content": "修正hydromodel配置错误},
            {"role": "user", "content": prompt}
        ]

        response = self.llm_interface.chat(messages)
        return self._parse_json(response)
```

---

### 4.5 RunnerAgent（执行

#### 增强功能

**原功*：执行hydromodel

**新功*
1. 执行hydromodel
2. **执行DeveloperAgent生成的额外本*（证
3. 捕获更详细的错误信息

```python
class RunnerAgent(BaseAgent):
    """执行智能体（增强版）"""

    def process(self, input_data: Dict) -> Dict:
        """
        执行任务

        Args:
            input_data: {
                "config": {...},
                "extra_scripts": ["script1.py", "script2.py"]  # 🆕 可
            }

        Returns:
            {
                "success": True/False,
                "result": {...},
                "extra_results": {...},  # 🆕 额外脚本的果
                "error": "..."
            }
        """
        config = input_data["config"]
        extra_scripts = input_data.get("extra_scripts", [])

        # 执行hydromodel
        result = self._run_calibration(config)

        if not result["success"]:
            return result

        # 执行额外脚本（证
        extra_results = {}
        for script in extra_scripts:
            logger.info(f"[RunnerAgent] Executing extra script: {script}")
            script_result = self._run_script(script, result["calibration_dir"])
            extra_results[script] = script_result

        return {
            "success": True,
            "result": result,
            "extra_results": extra_results
        }

    def _run_script(self, script_path: str, work_dir: str) -> Dict:
        """执行额外的Python脚本"""
        import subprocess

        try:
            output = subprocess.run(
                [sys.executable, script_path],
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=300
            )

            return {
                "success": output.returncode == 0,
                "stdout": output.stdout,
                "stderr": output.stderr
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
```

---

### 4.6 DeveloperAgent（后处理层）

#### 增强功能

**原功*：结果分离+ 建议生成

**新功*
1. 结果分析
2. **代码生成**（验：超出hydromodel功能
3. **统计分析**（验：重复实验的NSE标准差）
4. **边界效应索*（验：触发迭代优化）

```python
class DeveloperAgent(BaseAgent):
    """开发分析智能体（增强版""

    def process(self, input_data: Dict) -> Dict:
        """
        分析结果 + 可选代码生成

        Args:
            input_data: {
                "task_type": "...",
                "results": [...],  # 可能是多个子任务的果
                "needs": ["runoff_coefficient", "FDC"]  # 🆕 需要额外分析的内容
            }

        Returns:
            {
                "analysis": "...",
                "generated_scripts": [...],  # 🆕 生成的本
                "statistics": {...}  # 🆕 统计结果（证
            }
        """
        task_type = input_data["task_type"]
        results = input_data["results"]
        needs = input_data.get("needs", [])

        # 标准分析
        analysis = self._analyze_results(results)

        # 代码生成（证
        generated_scripts = []
        if needs:
            generated_scripts = self._generate_analysis_scripts(needs, results)

        # 统计分析（证
        statistics = {}
        if task_type == "repeated_experiment":
            statistics = self._compute_statistics(results)

        # 边界效应检测（实验3
        boundary_detected = False
        if task_type == "iterative_optimization":
            boundary_detected = self._detect_boundary_effect(results[0])

        return {
            "analysis": analysis,
            "generated_scripts": generated_scripts,
            "statistics": statistics,
            "boundary_detected": boundary_detected
        }

    def _generate_analysis_scripts(self, needs: List[str], results: List[Dict]) -> List[str]:
        """生成额外分析脚本（证""
        scripts = []

        for need in needs:
            if need == "runoff_coefficient":
                script = self._llm_generate_script(
                    task="计算径流系数",
                    input_files=results[0]["output_files"],
                    output_file="runoff_coefficient.txt"
                )
                scripts.append(script)

            elif need == "FDC":
                script = self._llm_generate_script(
                    task="绘制流路历时曲线",
                    input_files=results[0]["output_files"],
                    output_file="FDC.png"
                )
                scripts.append(script)

        return scripts

    def _llm_generate_script(self, task: str, input_files: List[str], output_file: str) -> str:
        """使用LLM生成Python脚本"""
        prompt = f"""
        请编写Python脚本完成以下任务

        任务: {task}
        输入文件: {input_files}
        输出文件: {output_file}

        要求
        1. 使用xarray读取.nc文件或pandas读取.csv文件
        2. 包含必要的错误理
        3. 输出结果到指定件
        4. 直接输出可执行的Python代码，不要解
        """

        response = self.llm_interface.chat([
            {"role": "system", "content": "你是Python脚本生成专家},
            {"role": "user", "content": prompt}
        ])

        # 保存脚本
        script_path = Path(f"generated_{task}.py")
        script_path.write_text(response)

        return str(script_path)

    def _compute_statistics(self, results: List[Dict]) -> Dict:
        """计算统计指标（证""
        nse_values = [r["metrics"]["NSE"] for r in results]

        return {
            "mean_NSE": np.mean(nse_values),
            "std_NSE": np.std(nse_values),
            "min_NSE": np.min(nse_values),
            "max_NSE": np.max(nse_values),
            "n_samples": len(nse_values)
        }

    def _detect_boundary_effect(self, result: Dict) -> bool:
        """检测参数是否收敛到边界（证""
        # 读取best_params和param_range
        best_params = result["best_params"]
        # param_range = ...  # 需要从文件读取

        # 检测是否接近边
        for param, value in best_params.items():
            # if value接近param_range的上界或下界:
            #     return True
            pass

        return False
```

---

## 5. 数据流与协作

### 5.1 完整数据

```python
# 用户输入
user_query = "率定流域 01013500，如果参数收敛到边界，自动调整范围重新率定

# Step 1: IntentAgent（战略决策）
intent_result = intent_agent.process({"query": user_query})
# 输出:
# {
#     "task_type": "iterative_optimization",
#     "intent_data": {
#         "intent": "calibration",
#         "model_name": "xaj",
#         "basin_id": "01013500",
#         "algorithm": "SCE_UA"
#     },
#     "strategy": {
#         "phases": ["coarse", "fine"],
#         "trigger": "boundary_effect"
#     }
# }

# Step 2: TaskPlanner（战术拆解）
plan_result = task_planner.process({"intent_result": intent_result})
# 输出:
# {
#     "tasks": [
#         {
#             "subtask_id": 1,
#             "phase": "coarse",
#             "prompt": "粗定..",
#             "params": {"rep": 500, ...}
#         },
#         {
#             "subtask_id": 2,
#             "phase": "fine",
#             "prompt": "精定..",
#             "params": {"rep": 2000, ...},
#             "dependencies": [1],  # 依赖务
#             "condition": "boundary_detected"  # 条件执行
#         }
#     ]
# }

# Step 3: 执行Phase 1
## 3.1 InterpreterAgent生成config
config1 = interpreter_agent.process({
    "prompt": plan_result["tasks"][0]["prompt"],
    "params": plan_result["tasks"][0]["params"]
})

## 3.2 RunnerAgent执行
result1 = runner_agent.process({"config": config1["config"]})

## 3.3 DeveloperAgent分析
analysis1 = developer_agent.process({
    "task_type": "iterative_optimization",
    "results": [result1]
})

# Step 4: 检查是否需要Phase 2
if analysis1["boundary_detected"]:
    # 执行Phase 2
    ## 4.1 TaskPlanner调整提示词（包含边界信息
    adjusted_prompt = task_planner.adjust_prompt(
        plan_result["tasks"][1]["prompt"],
        boundary_info=analysis1["boundary_params"]
    )

    ## 4.2 InterpreterAgent生成新config（调整param_range
    config2 = interpreter_agent.process({
        "prompt": adjusted_prompt,
        "params": plan_result["tasks"][1]["params"]
    })

    ## 4.3 RunnerAgent执行
    result2 = runner_agent.process({"config": config2["config"]})

    ## 4.4 DeveloperAgent对比分析
    final_analysis = developer_agent.process({
        "task_type": "iterative_optimization",
        "results": [result1, result2]
    })
else:
    final_analysis = analysis1

# 返回最终果
return final_analysis
```

---

## 6. 实验场景实现

### 实验1：标准流域证

**流程**
```
用户 → IntentAgent (识别为standard_calibration)
    TaskPlanner (不拆解，单一任务)
    InterpreterAgent (生成config)
    RunnerAgent (执行)
    DeveloperAgent (分析，NSE > 0.8)
```

---

### 实验2：通用性与性

**场景A**（全信息）：
```
IntentAgent → 直接提取 无需补全
```

**场景B**（缺省信息）
```
IntentAgent → 识别CAMELS_US 补全算法、期
```

**场景C**（模糊信息）
```
IntentAgent → 识别路径 推断data_source_type
InterpreterAgent → 检查文件夹结构 生成适配config
```

---

### 实验3：参数自适应优化

**流程**
```
IntentAgent → task_type="iterative_optimization"
    
TaskPlanner → 拆解为Phase1 + Phase2（条件依赖）
    
Phase 1:
  InterpreterAgent → config (宽泛范围, rep=500)
  RunnerAgent → 执行
  DeveloperAgent → 检测边界效
    
  If boundary_detected:
    Phase 2:
      TaskPlanner → 调整提示词（包含边界信息
      InterpreterAgent → 新config (调整范围, rep=2000)
      RunnerAgent → 执行
      DeveloperAgent → 对比NSE提升
```

---

### 实验4：代码生成与工具扩展

**流程**
```
IntentAgent → task_type="extended_analysis", needs=["runoff_coefficient", "FDC"]
    
TaskPlanner → 拆解为Task1(标准率定) + Task2(扩展分析)
    
Task 1:
  InterpreterAgent → config
  RunnerAgent → 执行率定
    
Task 2:
  DeveloperAgent → 识别需要代码生
  DeveloperAgent → LLM生成 calc_runoff_coef.py, plot_fdc.py
  RunnerAgent → 执行额外脚本
  DeveloperAgent → 汇总果
```

---

### 实验5：稳定性证

**流程**
```
IntentAgent → task_type="repeated_experiment", n_repeats=10
    
TaskPlanner → 拆解0个子任务（不同随机种子）
    
For each task:
  InterpreterAgent → config (random_seed=i)
  RunnerAgent → 执行
    
DeveloperAgent → 计算mean_NSE, std_NSE
```

---

## 7. 实施计划

### Phase 1: IntentAgent增强-3天）

**Day 1-2**:
- [ ] 实现任务类型决策逻辑
- [ ] 实现信息补全功能
- [ ] 单元测试 → 个实验场景的intent识别

**Day 3**:
- [ ] 集成测试
- [ ] 文档更新

---

### Phase 2: TaskPlanner（原ConfigAgent重构-4天）

**Day 4-5**:
- [ ] 重命名ConfigAgent → TaskPlanner
- [ ] 实现任务拆解逻辑 → 个task_type
- [ ] 实现提示词生

**Day 6-7**:
- [ ] 实现Prompt Pool（简化版
- [ ] 单元测试
- [ ] 集成测试

---

### Phase 3: InterpreterAgent（新组件-3天）

**Day 8-9**:
- [ ] 创建InterpreterAgent
- [ ] 实现LLM生成config
- [ ] 实现验证和自我修

**Day 10**:
- [ ] 单元测试
- [ ] 与TaskPlanner集成测试

---

### Phase 4: RunnerAgent & DeveloperAgent增强-3天）

**Day 11-12**:
- [ ] RunnerAgent支持执行额外脚本
- [ ] DeveloperAgent实现代码生成
- [ ] DeveloperAgent实现统计分析
- [ ] DeveloperAgent实现边界索

**Day 13**:
- [ ] 单元测试
- [ ] 集成测试

---

### Phase 5: 端到端验证（3-5天）

**Day 14-18**:
- [ ] 实验1：标准流域证
- [ ] 实验2：通用性鲁棒性（3个场景）
- [ ] 实验3：参数自适应优化
- [ ] 实验4：代码生成展
- [ ] 实验5：稳定性证
- [ ] 性能调优
- [ ] 文档完善

---

## 8. 已知问题与修复记录

### 8.1 实验4: Custom Analysis任务路由问题（ 2025-01-24修复）

#### 问题现象
- RunnerAgent误将custom_analysis识别为"calibrate"模式
- hydromodel报错：`ValueError: Unsupported data_type: custom`
- 代码生成功能未被触发

#### 修复内容
1. **TaskPlanner**: 为custom_analysis任务添加`task_type`字段到parameters (task_planner.py:397)
2. **InterpreterAgent**: 支持最小化配置生成 (interpreter_agent.py:93-189, 393-405, 270-272)
3. **RunnerAgent**: 添加custom_analysis模式日志处理 (runner_agent.py:267-276)

#### 测试验证
`test/test_exp4_fixes.py` 全部通过

---

### 8.2 实验3: 迭代优化架构问题（ 2025-01-22修复）

#### 问题现象
两次率定使用相同参数范围，NSE值相同

#### 修复方案
TaskPlanner创建单一iterative任务，RunnerAgent内部循环处理

详见：`docs/ITERATIVE_OPTIMIZATION_REDESIGN.md`

---

### 8.3 实验1: JSON解析和Config使用（ 2025-01-22修复）

#### 问题1: JSON解析失败
LLM返回markdown包裹的JSON

**修复**: llm_interface.py添加markdown提取逻辑

#### 问题2: 硬编码参数
InterpreterAgent使用hardcoded "rep: 5000"

**修复**: 动态加载config.py参数

---

## 9. 总结

### 核心改进

| 改进| 旧构| 新构|
|--------|--------|--------|
| **IntentAgent** | 只提取息| 提取 + **决策任务类型** |
| **ConfigAgent** | 规则生成config | **TaskPlanner** (任务拆解) |
| **(** | - | **InterpreterAgent** (LLM生成config) |
| **Prompt Pool** | 静态件| 动态存+ 历史索|
| **DeveloperAgent** | 分析 | 分析 + **代码生成** + 统计 |
| **错误反馈** | | TaskPlanner/Interpreter → Runner |

### 设计优势

1. **职责清晰**：战略（IntentAgent）→ 战术（TaskPlanner）→ 配置（Interpreter）→ 执行（Runner
2. **复杂性隔离：逻辑复杂性（TaskPlanner）与执行复杂性（Runner）分离
3. **实验驱动**：所有设计围 → 个核心验
4. **可扩展：新增任务类型只需扩展TaskPlanner的拆解逻辑

---

**END OF DOCUMENT**
