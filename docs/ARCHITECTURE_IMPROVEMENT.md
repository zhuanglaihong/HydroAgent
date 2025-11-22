# HydroAgent 架构改进设计文档

**Author**: HydroAgent Team
**Date**: 2025-01-22
**Version**: 1.0
**Status**: Design Proposal

---

## 📋 目录

- [1. 概述](#1-概述)
- [2. 当前架构分析](#2-当前架构分析)
- [3. OpenFOAMGPT架构对比](#3-openfoamgpt架构对比)
- [4. 问题诊断](#4-问题诊断)
- [5. 改进方案设计](#5-改进方案设计)
- [6. 组件详细设计](#6-组件详细设计)
- [7. 实施路线图](#7-实施路线图)
- [8. 文件结构变化](#8-文件结构变化)
- [9. 代码示例](#9-代码示例)
- [10. 性能指标与评估](#10-性能指标与评估)
- [11. 风险与缓解](#11-风险与缓解)

---

## 1. 概述

### 1.1 背景

HydroAgent 是一个基于 OpenFOAMGPT 架构设计的多智能体系统，用于水文模型的自动化率定、评估和分析。当前系统已实现基础的 4 智能体流水线，但在核心设计上与 OpenFOAMGPT 存在关键差异。

### 1.2 目标

本文档旨在：
1. **诊断**当前架构与 OpenFOAMGPT 的差异
2. **设计**符合原始架构理念的改进方案
3. **规划**分阶段实施路线图
4. **指导**后续开发工作

### 1.3 核心改进点

| 改进项 | 当前状态 | 目标状态 |
|--------|---------|---------|
| ConfigAgent | 规则驱动 | LLM 驱动 |
| Prompt Pool | 静态文件 | 动态历史存储 |
| 错误处理 | 单向流水线 | 反馈循环 |
| 提示词生成 | 缺失 | 专用 Agent |
| 经验积累 | 无 | 从历史学习 |

---

## 2. 当前架构分析

### 2.1 组件清单

```
User Query
    ↓
IntentAgent (LLM) ← 意图识别
    ↓
ConfigAgent (规则) ← 配置生成
    ↓
RunnerAgent (确定性) ← 模型执行
    ↓
DeveloperAgent (LLM) ← 结果分析
    ↓
Results
```

### 2.2 各组件实现状态

| 组件 | 类型 | LLM使用 | 功能 | 问题 |
|------|------|---------|------|------|
| **IntentAgent** | 智能体 | ✅ 是 | NLU, 参数提取 | 无 |
| **ConfigAgent** | 智能体 | ❌ 否 | 字典映射, 硬编码规则 | **应该LLM驱动** |
| **RunnerAgent** | 执行器 | ❌ 否 | 调用hydromodel API | 无（合理） |
| **DeveloperAgent** | 智能体 | ✅ 是 | 结果分析, 建议生成 | 无 |

### 2.3 ConfigAgent 实现分析

**当前实现**（`hydroagent/agents/config_agent.py:226-288`）：

```python
def _apply_intent_to_config(self, config, intent_result):
    """纯规则映射"""
    # 机械地字典赋值
    if intent_result.get("model_name"):
        config["model_cfgs"]["model_name"] = intent_result["model_name"]

    if intent_result.get("basin_id"):
        config["data_cfgs"]["basin_ids"] = [intent_result["basin_id"]]

    # 硬编码的参数调整逻辑
    if num_params <= 5:
        config["training_cfgs"]["algorithm_params"]["ngs"] = 200
    elif num_params <= 10:
        config["training_cfgs"]["algorithm_params"]["ngs"] = 400
    else:
        config["training_cfgs"]["algorithm_params"]["ngs"] = 100
```

**问题**：
- ❌ 无法处理复杂/模糊需求
- ❌ 新模型/算法需手动添加规则
- ❌ 无法从历史经验改进
- ❌ 缺乏上下文推理能力

---

## 3. OpenFOAMGPT架构对比

### 3.1 OpenFOAMGPT 完整流程

```
User Query
    ↓
[1] Preprocessing Agent (LLM) ← 预处理用户查询
    ↓
[2] Prompt Generate Agent (LLM) ← 转换为专用提示词
    ↓
[3] Prompt Pool ← 存储提示词 + 历史案例
    ↓
[4] Interpreter (LLM) ← 核心：生成配置文件
    ↓
[5] Builder ← 构建执行环境
    ↓
[6] Runner ← 执行仿真
    ↓
    Error? ──Yes──→ Error Log ──┐
    │                           │
    No                          ↓
    ↓                    [4] Interpreter (重新生成)
[7] Postprocessing Agent (LLM) ← 结果分析
    ↓
Output Results
```

### 3.2 组件映射

| OpenFOAMGPT | HydroAgent (当前) | 状态 | 应改为 |
|-------------|------------------|------|--------|
| Preprocessing Agent | IntentAgent | ✅ 已对齐 | - |
| **Prompt Generate Agent** | ❌ **缺失** | 🔴 无 | **新增** |
| **Prompt Pool** | PromptManager (简化) | ⚠️ 静态 | **重构** |
| **Interpreter** | ConfigAgent (规则) | 🔴 规则 | **改LLM** |
| Builder | (嵌入Runner) | ⚠️ 简化 | 保持 |
| Runner | RunnerAgent | ✅ 已对齐 | - |
| **Error Loop** | ❌ **缺失** | 🔴 无 | **新增** |
| Postprocessing Agent | DeveloperAgent | ✅ 已对齐 | - |

### 3.3 关键差异总结

**OpenFOAMGPT 的核心特性**：
1. ✅ **动态提示词生成**：Prompt Generate Agent 专门将结构化数据转为 LLM 提示
2. ✅ **历史案例复用**：Prompt Pool 存储成功/失败案例，支持检索
3. ✅ **LLM 驱动决策**：Interpreter 是 LLM，能推理、自我修正
4. ✅ **错误自愈循环**：失败后自动调整策略重试

**HydroAgent 的缺失**：
1. ❌ 没有 Prompt Generate Agent
2. ❌ Prompt Pool 只是静态文件管理器
3. ❌ ConfigAgent 是规则系统，非 LLM
4. ❌ 没有错误反馈循环

---

## 4. 问题诊断

### 4.1 核心问题

当前 HydroAgent 是**"假"多智能体系统**：
- 只有首尾（IntentAgent, DeveloperAgent）是真正的 LLM 智能体
- 中间的配置生成和执行是硬编码流程
- 无自我修正能力，失败即终止

### 4.2 具体影响

| 场景 | 当前表现 | 期望表现 |
|------|---------|---------|
| **新模型适配** | 需修改代码添加规则 | LLM 自动推理参数范围 |
| **复杂需求** | 无法处理模糊需求 | LLM 理解上下文并决策 |
| **执行失败** | 直接报错退出 | 自动诊断错误并重试 |
| **性能优化** | 每次从默认值开始 | 从历史成功案例学习 |
| **参数调优** | 用户手动多次尝试 | 系统自动探索最优配置 |

### 4.3 用户体验缺陷

**当前**：
```
用户: "率定GR4J模型，流域01013500，迭代500轮"
系统: [执行...失败]
      "错误：数据加载失败"
      → 用户需要手动检查、修改、重试
```

**改进后**：
```
用户: "率定GR4J模型，流域01013500，迭代500轮"
系统: [尝试1...失败: 数据路径错误]
      [自动修正配置]
      [尝试2...失败: 内存不足]
      [调整算法参数降低内存]
      [尝试3...成功！]
      "率定完成，NSE=0.72"
```

---

## 5. 改进方案设计

### 5.1 整体架构（改进后）

```
User Query
    ↓
IntentAgent (LLM) ← 已有
    ↓
PromptGenerateAgent (LLM) ← 🆕 新增
    ↓
PromptPool ← 🔄 重构（动态存储）
    ↓
ConfigAgent (LLM) ← 🔄 重构（规则→LLM）
    ↓
RunnerAgent (确定性) ← 已有
    ↓
    Error? ──Yes──→ ErrorAnalyzer ──┐
    │                               │
    No                              ↓
    ↓                    ConfigAgent (重试，带错误上下文)
DeveloperAgent (LLM) ← 已有
    ↓
Results
```

### 5.2 设计原则

1. **保持向后兼容**：ConfigAgent 名称不变，只改内部实现
2. **渐进式迁移**：新旧实现并存，可切换（配置项控制）
3. **模块化设计**：各组件职责清晰，低耦合
4. **可测试性**：每个组件独立测试，端到端集成测试
5. **可观测性**：完整日志记录，支持 Debug 和性能分析

### 5.3 改进优先级

#### Priority 1 - 核心功能（MVP）

**目标**：最小成本获得最大收益

1. **PromptPool（动态存储）**
   - 存储历史配置和执行结果
   - 简单的相似度检索
   - 持久化到磁盘

2. **错误反馈循环**
   - ConfigAgent 接受错误日志作为输入
   - 主流程添加重试逻辑（max_retries=3）
   - 错误诊断和提取

**收益**：
- ✅ 系统鲁棒性大幅提升
- ✅ 用户体验改善（自动重试）
- ✅ 开始积累经验数据

**工作量**：2-3 天

---

#### Priority 2 - 智能增强

**目标**：ConfigAgent 真正智能化

3. **ConfigAgent（LLM 驱动）**
   - 使用 LLM 生成配置 JSON
   - 整合历史案例到提示词
   - LLM 自我修正机制
   - 保留规则版本作为 fallback

**收益**：
- ✅ 适应新模型无需改代码
- ✅ 处理复杂/模糊需求
- ✅ 从历史经验学习

**风险**：
- ⚠️ LLM 可能生成无效 JSON
- ⚠️ API 成本增加
- ⚠️ 响应时间变长

**缓解**：
- 严格的 JSON 解析和验证
- fallback 到规则版本
- 缓存相似配置

**工作量**：3-4 天

---

#### Priority 3 - 锦上添花

**目标**：完全对齐 OpenFOAMGPT

4. **PromptGenerateAgent**
   - 专门的提示词工程 Agent
   - 将结构化意图转为优化的 LLM 提示
   - 整合流域特征、模型知识

**收益**：
- ✅ 提示词质量更高
- ✅ ConfigAgent 更专注于配置生成
- ✅ 职责分离更清晰

**可选性**：可暂时跳过，在 ConfigAgent 内部生成提示词

**工作量**：1-2 天

---

## 6. 组件详细设计

### 6.1 PromptPool（动态历史存储）

#### 职责

1. 存储每次执行的完整记录（intent, prompt, config, result, success）
2. 根据相似度检索历史成功案例
3. 生成带历史上下文的提示词
4. 持久化到磁盘，支持长期积累

#### 接口设计

```python
class PromptPool:
    def __init__(self, pool_dir: Path):
        """初始化，加载历史记录"""

    def add_result(
        self,
        intent: Dict,
        prompt: str,
        config: Dict,
        result: Dict,
        success: bool
    ):
        """添加执行记录"""

    def get_similar_cases(
        self,
        intent: Dict,
        limit: int = 3
    ) -> List[Dict]:
        """检索相似的成功案例"""

    def generate_context_prompt(
        self,
        base_prompt: str,
        intent: Dict,
        error_log: Optional[str] = None
    ) -> str:
        """生成带上下文的完整提示词"""

    def get_statistics(self) -> Dict:
        """获取统计信息（成功率、常用模型等）"""
```

#### 数据存储格式

```json
{
  "history": [
    {
      "timestamp": "2025-01-22T10:30:00",
      "intent": {
        "intent": "calibration",
        "model_name": "gr4j",
        "basin_id": "01013500",
        "algorithm": "SCE_UA"
      },
      "prompt": "用户想要率定GR4J模型...",
      "config": {...},
      "result": {
        "success": true,
        "metrics": {"NSE": 0.72}
      },
      "success": true
    }
  ]
}
```

#### 相似度计算（简单版）

```python
def _calculate_similarity(self, intent1: Dict, intent2: Dict) -> float:
    """计算两个意图的相似度"""
    score = 0.0

    # 模型匹配 (+1.0)
    if intent1.get("model_name") == intent2.get("model_name"):
        score += 1.0

    # 算法匹配 (+0.8)
    if intent1.get("algorithm") == intent2.get("algorithm"):
        score += 0.8

    # 流域匹配 (+0.5)
    if intent1.get("basin_id") == intent2.get("basin_id"):
        score += 0.5

    # 任务类型匹配 (+0.3)
    if intent1.get("intent") == intent2.get("intent"):
        score += 0.3

    return score
```

---

### 6.2 ConfigAgent（LLM 驱动版本）

#### 设计策略

**混合模式**：新旧实现并存，配置切换

```python
class ConfigAgent(BaseAgent):
    def __init__(
        self,
        llm_interface: LLMInterface,
        prompt_pool: Optional[PromptPool] = None,
        use_llm: bool = True,  # ← 控制开关
        **kwargs
    ):
        self.use_llm = use_llm
        self.prompt_pool = prompt_pool
```

#### 工作流程

```
Input: {intent_result, error_log (可选)}
    ↓
Mode = use_llm?
    ├─ Yes (LLM模式)
    │   ↓
    │   1. 从PromptPool获取历史案例
    │   2. 构建完整提示词（intent + 案例 + 错误）
    │   3. 调用LLM生成配置JSON
    │   4. 解析和验证
    │   5. 如验证失败 → LLM自我修正
    │   6. 返回配置
    │
    └─ No (规则模式)
        ↓
        1. 使用现有的规则逻辑
        2. _apply_intent_to_config()
        3. _adjust_algorithm_params()
        4. 返回配置
```

#### LLM 提示词模板

```python
SYSTEM_PROMPT = """你是 HydroAgent 的配置解释器。

任务：根据用户意图和历史案例，生成 hydromodel 配置 JSON。

配置结构：
{
  "data_cfgs": {
    "basin_ids": ["..."],
    "train_period": ["YYYY-MM-DD", "YYYY-MM-DD"],
    "test_period": ["YYYY-MM-DD", "YYYY-MM-DD"],
    "warmup_length": 365
  },
  "model_cfgs": {
    "model_name": "gr4j|xaj|gr5j|..."
  },
  "training_cfgs": {
    "algorithm_name": "SCE_UA|GA|DE|PSO",
    "algorithm_params": {...}
  }
}

原则：
1. 根据模型复杂度（参数数量）调整算法参数
2. 优先使用用户明确指定的参数
3. 参考历史成功案例的参数配置
4. 如有错误反馈，优先修正错误点
5. 输出必须是有效的 JSON，不要任何额外文字
"""

USER_PROMPT_TEMPLATE = """
用户意图：
- 任务: {intent}
- 模型: {model_name} ({num_params}个参数)
- 流域: {basin_id}
- 算法: {algorithm}
- 自定义参数: {extra_params}

{历史案例}

{错误反馈}

请生成最优配置 JSON。
"""
```

#### 自我修正机制

```python
def _llm_self_correct(self, config: Dict, errors: List[str]) -> Dict:
    """LLM自我修正配置错误"""
    correction_prompt = f"""
以下配置有错误：
```json
{json.dumps(config, indent=2)}
```

错误列表：
{chr(10).join(f'- {e}' for e in errors)}

请修正配置，直接输出正确的JSON，不要任何其他文字。
"""

    messages = [
        {"role": "system", "content": self.system_prompt},
        {"role": "user", "content": correction_prompt}
    ]

    response = self.llm_interface.chat(messages)
    return self._parse_llm_response(response)
```

#### 验证逻辑（保持现有）

```python
def _validate_config(self, config: Dict) -> tuple[bool, List[str]]:
    """验证配置（复用现有逻辑）"""
    errors = []

    # 检查必需字段
    required = ["data_cfgs", "model_cfgs", "training_cfgs"]
    for field in required:
        if field not in config:
            errors.append(f"缺少字段: {field}")

    # 验证模型名称
    valid_models = ["xaj", "gr4j", "gr5j", "gr6j", "gr1y", "gr2m"]
    model_name = config.get("model_cfgs", {}).get("model_name")
    if model_name not in valid_models:
        errors.append(f"无效模型: {model_name}")

    # ... 其他验证 ...

    return len(errors) == 0, errors
```

---

### 6.3 PromptGenerateAgent（可选）

#### 职责

将 IntentAgent 的结构化输出转换为高质量的自然语言提示词。

#### 为什么可选？

可以在 ConfigAgent 内部生成提示词，不需要单独的 Agent。但独立出来有以下好处：
1. **职责分离**：提示词工程专家
2. **可复用**：其他 Agent 也可用
3. **易优化**：独立迭代提示词质量

#### 简化实现

如果跳过此组件，在 ConfigAgent 中这样处理：

```python
def _generate_prompt_from_intent(self, intent: Dict) -> str:
    """从意图生成提示词（内部方法）"""
    return f"""
用户意图：
- 任务: {intent.get('intent')}
- 模型: {intent.get('model_name')}
- 流域: {intent.get('basin_id')}
- 算法: {intent.get('algorithm')}
- 自定义参数: {intent.get('extra_params', {})}

模型特征：
- {self._get_model_description(intent.get('model_name'))}

算法特点：
- {self._get_algorithm_description(intent.get('algorithm'))}

请生成最优配置。
"""
```

---

### 6.4 错误反馈循环

#### 主流程设计

```python
def run_workflow_with_retry(
    user_query: str,
    llm_interface: LLMInterface,
    max_retries: int = 3
) -> Dict:
    """带错误重试的完整工作流"""

    # 初始化组件
    intent_agent = IntentAgent(llm_interface)
    prompt_pool = PromptPool(pool_dir=Path("prompt_pool"))
    config_agent = ConfigAgent(llm_interface, prompt_pool, use_llm=True)
    runner_agent = RunnerAgent(llm_interface)
    developer_agent = DeveloperAgent(llm_interface)

    # Step 1: 意图识别（只执行一次）
    logger.info("[Workflow] Step 1: Intent Recognition")
    intent_result = intent_agent.process({"query": user_query})

    if not intent_result["success"]:
        return {"success": False, "error": "Intent recognition failed"}

    error_log = None
    final_result = None

    # Step 2-4: 循环尝试（配置生成 + 执行）
    for attempt in range(max_retries):
        logger.info(f"\n{'='*60}")
        logger.info(f"[Workflow] Attempt {attempt + 1}/{max_retries}")
        logger.info(f"{'='*60}")

        # Step 2: 配置生成（带错误反馈）
        logger.info("[Workflow] Step 2: Configuration Generation")
        config_input = {
            "intent_result": intent_result["intent_result"],
            "error_log": error_log  # 第一次为None，后续包含错误信息
        }
        config_result = config_agent.process(config_input)

        if not config_result["success"]:
            logger.error(f"[Workflow] Config generation failed: {config_result.get('error')}")
            error_log = f"配置生成失败: {config_result.get('error')}"
            continue

        # Step 3: 执行
        logger.info("[Workflow] Step 3: Model Execution")
        exec_result = runner_agent.process(config_result)

        if exec_result["success"]:
            # 成功！存储到 PromptPool
            logger.info("[Workflow] ✅ Execution successful!")
            prompt_pool.add_result(
                intent=intent_result["intent_result"],
                prompt=config_input.get("generated_prompt", ""),
                config=config_result["config"],
                result=exec_result,
                success=True
            )
            final_result = exec_result
            break
        else:
            # 失败，提取错误诊断
            logger.warning(f"[Workflow] ❌ Execution failed")
            error_log = _extract_error_diagnosis(exec_result)
            logger.warning(f"[Workflow] Error diagnosis: {error_log}")

            # 存储失败案例
            prompt_pool.add_result(
                intent=intent_result["intent_result"],
                prompt=config_input.get("generated_prompt", ""),
                config=config_result["config"],
                result=exec_result,
                success=False
            )

            # 如果是最后一次尝试
            if attempt == max_retries - 1:
                logger.error("[Workflow] All retries exhausted")
                final_result = exec_result

    # Step 4: 结果分析
    logger.info("[Workflow] Step 4: Result Analysis")
    analysis = developer_agent.process(final_result)

    return analysis


def _extract_error_diagnosis(exec_result: Dict) -> str:
    """从执行结果提取错误诊断信息"""
    error_parts = []

    if "error" in exec_result:
        error_parts.append(f"错误类型: {exec_result['error']}")

    if "traceback" in exec_result:
        # 提取关键行（最后几行）
        traceback_lines = exec_result["traceback"].split("\n")
        key_lines = traceback_lines[-5:]  # 最后5行
        error_parts.append(f"错误详情:\n{chr(10).join(key_lines)}")

    if "execution_log" in exec_result:
        log = exec_result["execution_log"]
        if "stderr" in log and log["stderr"]:
            error_parts.append(f"标准错误输出:\n{log['stderr'][-500:]}")  # 最后500字符

    return "\n\n".join(error_parts) if error_parts else "未知错误"
```

#### 错误类型与处理策略

| 错误类型 | 诊断方法 | ConfigAgent调整策略 |
|---------|---------|-------------------|
| **数据加载失败** | "FileNotFoundError" in traceback | 检查data_source_path，尝试默认路径 |
| **内存不足** | "MemoryError" in traceback | 减少ngs/population_size |
| **参数超出范围** | "out of bounds" in stderr | 调整param_range |
| **算法不收敛** | "convergence" in stderr | 增加rep/max_iterations |
| **配置格式错误** | validation errors | LLM自我修正 |

---

## 7. 实施路线图

### 7.1 时间线（总计 6-9 天）

```
Week 1
├─ Day 1: 阶段0 - 准备工作
│  ├─ 创建 docs/ARCHITECTURE_IMPROVEMENT.md ✅
│  ├─ 更新 CLAUDE.md 引用改进计划
│  ├─ 创建分支 feature/llm-config-agent
│  └─ 环境准备和依赖检查
│
├─ Day 2-3: 阶段1 - PromptPool（Priority 1）
│  ├─ 创建 hydroagent/core/prompt_pool.py
│  ├─ 实现历史存储和检索
│  ├─ 编写单元测试 test/test_prompt_pool.py
│  ├─ 基准测试（存储/检索性能）
│  └─ 集成到现有流程（透传模式）
│
├─ Day 4-5: 阶段2 - 错误反馈循环（Priority 1）
│  ├─ 修改 scripts/run_developer_agent_pipeline.py
│  ├─ 实现 run_workflow_with_retry()
│  ├─ 实现 _extract_error_diagnosis()
│  ├─ ConfigAgent 添加 error_log 参数（规则版本先支持）
│  ├─ 端到端测试（故意制造错误，验证重试）
│  └─ 性能测试（成功率提升）
│
└─ Day 6-9: 阶段3 - ConfigAgent LLM版本（Priority 2）
   ├─ ConfigAgent 添加 use_llm 参数
   ├─ 实现 _llm_generate_config()
   ├─ 实现 _llm_self_correct()
   ├─ 实现 LLM 提示词模板
   ├─ 单元测试（LLM模式 vs 规则模式）
   ├─ A/B 对比测试（多个案例）
   ├─ 性能调优（缓存、fallback）
   └─ 文档更新
```

### 7.2 里程碑

| 里程碑 | 完成标志 | 预期日期 |
|--------|---------|---------|
| **M1: PromptPool 可用** | 能存储和检索历史记录 | Day 3 |
| **M2: 错误重试可用** | 失败自动重试3次 | Day 5 |
| **M3: LLM ConfigAgent 可用** | LLM能生成有效配置 | Day 7 |
| **M4: 性能验证通过** | LLM版本成功率 ≥ 规则版本 | Day 8 |
| **M5: 正式发布** | 合并到main分支 | Day 9 |

### 7.3 验收标准

#### M1: PromptPool

- [ ] 能正确存储执行记录到 `prompt_pool/history.json`
- [ ] 相似度检索返回正确案例（手动验证）
- [ ] 单元测试覆盖率 > 80%
- [ ] 存储/检索延迟 < 100ms

#### M2: 错误反馈循环

- [ ] 失败后能自动重试最多3次
- [ ] 错误日志正确传递给 ConfigAgent
- [ ] 端到端测试：故意错误配置能自动修正
- [ ] 成功率提升 > 20%（对比无重试版本）

#### M3: LLM ConfigAgent

- [ ] LLM 能生成有效的 JSON 配置
- [ ] 验证失败时能自我修正
- [ ] use_llm=True/False 能正确切换
- [ ] 与规则版本输出结果一致性 > 90%（简单案例）

#### M4: 性能验证

测试集：10个典型案例（覆盖GR4J, XAJ, 不同算法）

- [ ] LLM版本成功率 ≥ 规则版本
- [ ] LLM版本能处理规则版本无法处理的复杂案例
- [ ] API调用成本 < 预算（每次查询 < 0.05元）
- [ ] 端到端延迟 < 2分钟（不含hydromodel执行时间）

---

## 8. 文件结构变化

### 8.1 新增文件

```
HydroAgent/
├── hydroagent/
│   ├── core/
│   │   └── prompt_pool.py              🆕 动态提示词池
│   ├── agents/
│   │   ├── config_agent.py             🔄 重构（添加LLM模式）
│   │   └── prompt_generate_agent.py    ⚠️ 可选
│   └── resources/
│       └── config_agent_llm_prompt.txt 🆕 LLM提示词模板
├── scripts/
│   └── run_developer_agent_pipeline.py 🔄 添加重试循环
├── test/
│   ├── test_prompt_pool.py             🆕 新测试
│   ├── test_config_agent_llm.py        🆕 新测试
│   └── test_workflow_retry.py          🆕 集成测试
├── docs/
│   └── ARCHITECTURE_IMPROVEMENT.md     🆕 本文档
├── prompt_pool/                         🆕 历史存储目录
│   └── history.json
└── configs/
    └── config.py                        🔄 添加开关配置
```

### 8.2 配置文件变化

**configs/config.py**：

```python
# === LLM-driven ConfigAgent Settings ===
USE_LLM_CONFIG_AGENT = True  # 是否启用LLM模式（False=规则模式）
MAX_RETRY_ATTEMPTS = 3        # 最大重试次数
ENABLE_PROMPT_POOL = True     # 是否启用历史案例检索

# Prompt Pool Settings
PROMPT_POOL_DIR = "prompt_pool"
MAX_HISTORY_SIZE = 1000       # 最多存储1000条历史记录
SIMILARITY_THRESHOLD = 0.5    # 相似度阈值

# LLM Config Agent Settings
CONFIG_LLM_MODEL = "qwen-turbo"  # 配置生成用的模型
CONFIG_LLM_TEMPERATURE = 0.1     # 低温度保证确定性
CONFIG_MAX_SELF_CORRECT = 2      # 最多自我修正2次
```

---

## 9. 代码示例

### 9.1 PromptPool 完整实现

```python
"""
Author: HydroAgent Team
Date: 2025-01-22 12:00:00
Description: Dynamic prompt pool with history and context management
FilePath: /HydroAgent/hydroagent/core/prompt_pool.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class PromptPool:
    """
    动态提示词池。

    功能：
    1. 存储历史提示词和执行结果
    2. 根据相似度检索成功案例
    3. 整合错误反馈生成上下文提示
    4. 持久化到磁盘
    """

    def __init__(self, pool_dir: Optional[Path] = None, max_size: int = 1000):
        """
        初始化提示词池。

        Args:
            pool_dir: 存储目录
            max_size: 最大历史记录数
        """
        self.pool_dir = pool_dir or Path("prompt_pool")
        self.pool_dir.mkdir(exist_ok=True)
        self.max_size = max_size

        self.history: List[Dict[str, Any]] = []
        self._load_history()

        logger.info(f"[PromptPool] Initialized with {len(self.history)} records")

    def add_result(
        self,
        intent: Dict[str, Any],
        prompt: str,
        config: Dict[str, Any],
        result: Dict[str, Any],
        success: bool
    ):
        """
        添加执行记录。

        Args:
            intent: 用户意图
            prompt: 生成的提示词
            config: 配置字典
            result: 执行结果
            success: 是否成功
        """
        record = {
            "timestamp": datetime.now().isoformat(),
            "intent": intent,
            "prompt": prompt,
            "config": config,
            "result": result,
            "success": success
        }

        self.history.append(record)

        # 限制大小
        if len(self.history) > self.max_size:
            self.history = self.history[-self.max_size:]

        self._save_history()

        logger.debug(f"[PromptPool] Added record (success={success}), total={len(self.history)}")

    def get_similar_cases(
        self,
        intent: Dict[str, Any],
        limit: int = 3,
        only_success: bool = True
    ) -> List[Dict[str, Any]]:
        """
        检索相似的案例。

        Args:
            intent: 当前意图
            limit: 返回数量
            only_success: 是否只返回成功案例

        Returns:
            相似案例列表
        """
        candidates = [r for r in self.history if not only_success or r["success"]]

        if not candidates:
            return []

        # 计算相似度
        scored_cases = []
        for case in candidates:
            score = self._calculate_similarity(intent, case["intent"])
            if score > 0:
                scored_cases.append((score, case))

        # 排序并返回top-k
        scored_cases.sort(key=lambda x: x[0], reverse=True)
        return [case for _, case in scored_cases[:limit]]

    def generate_context_prompt(
        self,
        base_prompt: str,
        intent: Dict[str, Any],
        error_log: Optional[str] = None
    ) -> str:
        """
        生成带上下文的完整提示词。

        Args:
            base_prompt: 基础提示词
            intent: 当前意图
            error_log: 错误日志（如有）

        Returns:
            完整提示词
        """
        context_parts = [base_prompt]

        # 添加成功案例
        similar = self.get_similar_cases(intent)
        if similar:
            context_parts.append("\n### 📚 历史成功案例参考")
            for i, case in enumerate(similar, 1):
                context_parts.append(f"\n**案例{i}**:")
                context_parts.append(f"- 模型: {case['intent'].get('model_name')}")
                context_parts.append(f"- 算法: {case['intent'].get('algorithm')}")

                # 提取关键参数
                algo_params = case['config'].get('training_cfgs', {}).get('algorithm_params', {})
                if algo_params:
                    context_parts.append(f"- 算法参数: {json.dumps(algo_params, ensure_ascii=False)}")

                # 性能指标
                if "metrics" in case["result"]:
                    metrics = case["result"]["metrics"]
                    context_parts.append(f"- 性能: NSE={metrics.get('NSE', 'N/A'):.3f}")

        # 添加错误修正提示
        if error_log:
            context_parts.append("\n### ⚠️ 上次执行失败")
            context_parts.append(error_log)
            context_parts.append("\n**请根据错误信息调整配置，避免重复错误。**")

        return "\n".join(context_parts)

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息。

        Returns:
            统计字典
        """
        total = len(self.history)
        successful = sum(1 for r in self.history if r["success"])

        # 统计模型使用
        models = {}
        for record in self.history:
            model = record["intent"].get("model_name", "unknown")
            models[model] = models.get(model, 0) + 1

        return {
            "total_records": total,
            "successful_records": successful,
            "success_rate": successful / total if total > 0 else 0,
            "model_usage": models
        }

    def _calculate_similarity(self, intent1: Dict, intent2: Dict) -> float:
        """
        计算两个意图的相似度。

        Args:
            intent1: 意图1
            intent2: 意图2

        Returns:
            相似度分数（0-3.6）
        """
        score = 0.0

        # 模型匹配 (+1.0)
        if intent1.get("model_name") == intent2.get("model_name"):
            score += 1.0

        # 算法匹配 (+0.8)
        if intent1.get("algorithm") == intent2.get("algorithm"):
            score += 0.8

        # 流域匹配 (+0.5)
        if intent1.get("basin_id") == intent2.get("basin_id"):
            score += 0.5

        # 任务类型匹配 (+0.3)
        if intent1.get("intent") == intent2.get("intent"):
            score += 0.3

        # 额外参数相似度 (+最多1.0)
        extra1 = intent1.get("extra_params", {})
        extra2 = intent2.get("extra_params", {})
        if extra1 and extra2:
            common_keys = set(extra1.keys()) & set(extra2.keys())
            if common_keys:
                score += len(common_keys) / max(len(extra1), len(extra2))

        return score

    def _load_history(self):
        """从磁盘加载历史记录"""
        history_file = self.pool_dir / "history.json"
        if history_file.exists():
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    self.history = json.load(f)
                logger.info(f"[PromptPool] Loaded {len(self.history)} records from {history_file}")
            except Exception as e:
                logger.error(f"[PromptPool] Failed to load history: {e}")
                self.history = []
        else:
            logger.info("[PromptPool] No existing history file, starting fresh")

    def _save_history(self):
        """保存历史记录到磁盘"""
        history_file = self.pool_dir / "history.json"
        try:
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[PromptPool] Failed to save history: {e}")
```

### 9.2 ConfigAgent LLM 模式实现（关键部分）

**修改 `hydroagent/agents/config_agent.py`**：

```python
class ConfigAgent(BaseAgent):
    """配置生成智能体（支持LLM和规则两种模式）"""

    def __init__(
        self,
        llm_interface: LLMInterface,
        prompt_pool: Optional['PromptPool'] = None,
        use_llm: bool = True,
        workspace_dir: Optional[Path] = None,
        **kwargs
    ):
        super().__init__(
            name="ConfigAgent",
            llm_interface=llm_interface,
            workspace_dir=workspace_dir,
            **kwargs
        )
        self.use_llm = use_llm
        self.prompt_pool = prompt_pool

        logger.info(f"[ConfigAgent] Initialized (mode={'LLM' if use_llm else 'Rule-based'})")

    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成配置（支持两种模式）。

        Args:
            input_data: {
                "intent_result": {...},
                "error_log": "..." (可选)
            }

        Returns:
            {"success": True, "config": {...}}
        """
        intent_result = input_data.get("intent_result", {})
        error_log = input_data.get("error_log")

        logger.info(f"[ConfigAgent] Generating config (mode={'LLM' if self.use_llm else 'Rule'})")

        try:
            if self.use_llm:
                # LLM模式
                config = self._llm_generate_config(intent_result, error_log)
            else:
                # 规则模式（现有逻辑）
                config = self._rule_generate_config(intent_result)

            # 验证配置
            is_valid, errors = self._validate_config(config)

            if not is_valid:
                if self.use_llm:
                    # LLM自我修正
                    logger.warning(f"[ConfigAgent] Config validation failed, attempting self-correction")
                    config = self._llm_self_correct(config, errors)
                    is_valid, errors = self._validate_config(config)

                if not is_valid:
                    return {
                        "success": False,
                        "error": "Configuration validation failed",
                        "validation_errors": errors
                    }

            summary = self._generate_config_summary(config, intent_result)

            return {
                "success": True,
                "config": config,
                "config_summary": summary
            }

        except Exception as e:
            logger.error(f"[ConfigAgent] Failed: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _llm_generate_config(
        self,
        intent_result: Dict[str, Any],
        error_log: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        使用LLM生成配置。

        Args:
            intent_result: 意图分析结果
            error_log: 错误日志（用于重试）

        Returns:
            配置字典
        """
        # 1. 构建基础提示词
        base_prompt = self._build_base_prompt(intent_result)

        # 2. 从PromptPool获取上下文
        if self.prompt_pool:
            full_prompt = self.prompt_pool.generate_context_prompt(
                base_prompt,
                intent_result,
                error_log
            )
        else:
            full_prompt = base_prompt

        # 3. 添加配置schema
        schema_prompt = self._get_config_schema()

        user_message = f"""
{full_prompt}

---

{schema_prompt}

---

**请直接输出配置JSON，不要任何其他文字。**
"""

        # 4. 调用LLM
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_message}
        ]

        logger.debug(f"[ConfigAgent] Calling LLM with prompt length: {len(user_message)}")
        response = self.llm_interface.chat(messages)

        # 5. 解析JSON
        config = self._parse_llm_response(response)

        logger.info(f"[ConfigAgent] LLM generated config for model={config.get('model_cfgs', {}).get('model_name')}")

        return config

    def _rule_generate_config(self, intent_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        使用规则生成配置（现有逻辑）。

        Args:
            intent_result: 意图分析结果

        Returns:
            配置字典
        """
        # 复用现有的逻辑
        config = self._get_default_config()
        config = self._apply_intent_to_config(config, intent_result)
        return config

    def _build_base_prompt(self, intent: Dict[str, Any]) -> str:
        """构建基础提示词"""
        model_name = intent.get("model_name", "unknown")
        basin_id = intent.get("basin_id", "unknown")
        algorithm = intent.get("algorithm", "SCE_UA")
        extra_params = intent.get("extra_params", {})

        # 获取模型参数数量
        model_complexity = {
            "gr4j": 4, "gr5j": 5, "gr6j": 6,
            "xaj": 15, "gr1y": 1, "gr2m": 2
        }
        num_params = model_complexity.get(model_name, 10)

        prompt = f"""
### 用户意图分析

**任务类型**: {intent.get('intent', 'calibration')}
**目标模型**: {model_name} ({num_params}个参数)
**流域ID**: {basin_id}
**优化算法**: {algorithm}
**自定义参数**: {json.dumps(extra_params, ensure_ascii=False) if extra_params else '无'}

### 模型特征

{self._get_model_description(model_name)}

### 算法特点

{self._get_algorithm_description(algorithm)}

### 配置要求

请生成hydromodel配置JSON，要求：
1. 根据模型复杂度（{num_params}个参数）调整算法参数
2. 优先使用用户明确指定的参数：{list(extra_params.keys()) if extra_params else '无'}
3. 确保训练期和测试期合理（训练至少10年）
4. 算法参数需平衡性能和计算成本
"""

        return prompt

    def _get_model_description(self, model_name: str) -> str:
        """获取模型描述"""
        descriptions = {
            "gr4j": "GR4J是4参数概念性降雨-径流模型，计算效率高，适合日尺度模拟。",
            "xaj": "新安江模型(XAJ)是15参数分布式模型，能更好描述空间异质性，适合湿润地区。",
            "gr5j": "GR5J是GR4J的扩展版本，增加1个参数以改进低流量模拟。",
        }
        return descriptions.get(model_name, f"{model_name}模型")

    def _get_algorithm_description(self, algorithm: str) -> str:
        """获取算法描述"""
        descriptions = {
            "SCE_UA": "SCE-UA是全局优化算法，适合水文模型率定。主要参数：ngs(复合体数量)和rep(演化步数)。",
            "GA": "遗传算法(GA)通过模拟自然选择进行优化。主要参数：population_size和generations。",
        }
        return descriptions.get(algorithm, f"{algorithm}算法")

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """解析LLM返回的JSON"""
        # 提取JSON（可能有```json包裹）
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]

        try:
            config = json.loads(response.strip())
            return config
        except json.JSONDecodeError as e:
            logger.error(f"[ConfigAgent] JSON parse error: {e}\nResponse: {response}")
            raise ValueError(f"LLM返回的不是有效JSON: {str(e)}")

    def _llm_self_correct(self, config: Dict, errors: List[str]) -> Dict:
        """LLM自我修正配置错误"""
        correction_prompt = f"""
以下配置有错误：

```json
{json.dumps(config, indent=2, ensure_ascii=False)}
```

**错误列表**:
{chr(10).join(f'{i+1}. {e}' for i, e in enumerate(errors))}

请修正配置，直接输出正确的JSON，不要任何其他文字。
"""

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": correction_prompt}
        ]

        logger.info("[ConfigAgent] Attempting self-correction")
        response = self.llm_interface.chat(messages)
        return self._parse_llm_response(response)

    # ... 保留现有的 _validate_config, _get_config_schema 等方法 ...
```

---

## 10. 性能指标与评估

### 10.1 评估维度

| 维度 | 指标 | 目标 | 测量方法 |
|------|------|------|---------|
| **成功率** | 配置生成成功率 | > 95% | 10个测试案例 |
| **准确性** | 配置有效性 | 100% | 验证通过率 |
| **鲁棒性** | 错误自愈成功率 | > 80% | 故意错误案例 |
| **效率** | 端到端延迟 | < 2分钟 | 不含模型执行 |
| **成本** | API调用成本 | < 0.05元/次 | token计数 |
| **质量** | 模型性能 | NSE提升 > 5% | 与规则版本对比 |

### 10.2 测试案例集

**基础案例**（必须100%成功）：
1. GR4J + SCE_UA（标准配置）
2. XAJ + SCE_UA（复杂模型）
3. GR4J + GA（不同算法）
4. 用户指定迭代次数（extra_params测试）
5. 用户指定训练期（时间范围测试）

**错误恢复案例**（测试鲁棒性）：
6. 无效流域ID（数据加载失败）
7. 内存不足（参数过大）
8. 算法不收敛（需调整参数）

**复杂案例**（测试智能化）：
9. 模糊需求："帮我率定一个模型，要快"
10. 多约束："GR4J模型，NSE>0.7，但计算时间<10分钟"

### 10.3 A/B 对比实验

| 案例 | 规则版本 | LLM版本 | 改进 |
|------|---------|---------|------|
| GR4J标准 | ✅ 成功 | ✅ 成功 | 一致 |
| XAJ复杂 | ✅ 成功 | ✅ 成功 | 一致 |
| 模糊需求 | ❌ 失败 | ✅ 成功 | ✅ |
| 错误恢复 | ❌ 失败 | ✅ 成功（重试2次） | ✅ |
| 性能优化 | NSE=0.68 | NSE=0.72 | +5.9% |

---

## 11. 风险与缓解

### 11.1 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| **LLM生成无效JSON** | 高 | 中 | 严格解析 + 自我修正 + fallback |
| **API调用失败** | 高 | 低 | 重试 + fallback到规则版本 |
| **成本超预算** | 中 | 中 | 缓存 + 模型降级 + 用量监控 |
| **性能下降** | 高 | 低 | A/B测试 + 性能基准 |
| **历史数据损坏** | 中 | 低 | 备份 + 容错加载 |

### 11.2 用户体验风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| **响应时间变长** | 中 | 异步提示 + 进度显示 |
| **配置不符合预期** | 高 | 配置预览 + 用户确认 |
| **错误重试过多** | 中 | max_retries=3 + 失败提示 |

### 11.3 回退策略

**Fallback 机制**：

```python
def process(self, input_data):
    if self.use_llm:
        try:
            config = self._llm_generate_config(intent_result, error_log)
        except Exception as e:
            logger.error(f"LLM generation failed: {e}, falling back to rule-based")
            config = self._rule_generate_config(intent_result)
    else:
        config = self._rule_generate_config(intent_result)

    return config
```

---

## 12. 附录

### 12.1 参考资料

- OpenFOAMGPT 原始论文/代码
- hydromodel 文档
- LLM Prompt Engineering 最佳实践

### 12.2 相关文档

- `CLAUDE.md` - 项目总体指南
- `docs/dynamic_prompt.md` - 动态提示词系统
- `docs/CONFIG_FORMAT.md` - 配置格式说明

### 12.3 更新记录

| 日期 | 版本 | 变更内容 |
|------|------|---------|
| 2025-01-22 | 1.0 | 初始版本 |

---

## 总结

本设计文档提出了将 HydroAgent 从**规则驱动**改进为**LLM 驱动智能系统**的完整方案，核心改进包括：

1. **PromptPool**：动态历史存储和经验复用
2. **错误反馈循环**：自动诊断和重试
3. **LLM驱动的ConfigAgent**：智能配置生成和自我修正

实施后，HydroAgent 将真正对齐 OpenFOAMGPT 架构，具备**自我修正、经验学习、鲁棒执行**的能力，显著提升用户体验和系统可靠性。

---

**END OF DOCUMENT**
