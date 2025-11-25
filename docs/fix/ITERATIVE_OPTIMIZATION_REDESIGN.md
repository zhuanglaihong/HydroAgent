# 实验3迭代优化架构重新设计

**Date**: 2025-01-24
**Issue**: 当前架构无法实现真正的循环迭代，两次率定使用相同参数范围

---

## 🐛 当前架构的问题

### 错误的线性流程：

```
IntentAgent: 识别为 iterative_optimization
     ↓
TaskPlanner: 创建2个独立任务
     - task_1_phase1: 初始率定
     - task_2_phase2: 边界感知重率定
     ↓
InterpreterAgent: 一次性生成2个独立配置
     - config_1: 使用默认参数范围
     - config_2: 使用默认参数范围（❌ 没有使用task1的结果！）
     ↓
RunnerAgent: 线性执行
     - process(config_1) → NSE=0.08
     - process(config_2) → NSE=0.08（❌ 参数范围没变，结果相同！）
```

**问题**：
1. ❌ 两个配置在生成时是独立的，config_2不知道config_1的结果
2. ❌ 无法根据第一次的NSE决定是否继续迭代
3. ❌ 无法动态调整迭代次数
4. ❌ 参数范围调整逻辑（adjust_param_range_from_previous_calibration）从未被调用

---

## ✅ 正确的循环架构设计

### 方案A: RunnerAgent内部循环 (推荐)

**核心思想**：迭代优化是一个**原子操作**，应该在RunnerAgent内部完成，而不是拆分成多个独立任务。

```
IntentAgent: 识别为 iterative_optimization
     ↓
TaskPlanner: 创建1个特殊任务
     - task_id: "iterative_boundary_optimization"
     - task_type: "boundary_check_recalibration"
     - parameters: {
           "max_iterations": 5,
           "nse_threshold": 0.5,
           "initial_range_scale": 0.6,
           "min_nse_improvement": 0.01
       }
     ↓
InterpreterAgent: 生成初始配置
     - 使用默认参数范围
     - 标记 task_type = "boundary_check_recalibration"
     ↓
RunnerAgent: 内部循环迭代 ⭐
     │
     ├─ 第1轮率定:
     │   ├─ 使用初始参数范围
     │   ├─ calibrate() → NSE=0.08
     │   ├─ evaluate()
     │   └─ 保存到: xaj_iteration_1/
     │
     ├─ 检查停止条件:
     │   ├─ NSE >= 0.5? → NO
     │   ├─ 达到最大轮数? → NO
     │   └─ 连续无改善? → NO → 继续
     │
     ├─ 调整参数范围:
     │   ├─ adjust_param_range_from_previous_calibration(
     │   │       prev_dir = "xaj_iteration_1/",
     │   │       range_scale = 0.6  # 初始60%
     │   │   )
     │   └─ 生成新的 adjusted_param_range.yaml
     │
     ├─ 第2轮率定:
     │   ├─ 使用调整后的参数范围
     │   ├─ calibrate(param_range_file = adjusted_param_range.yaml)
     │   ├─ NSE = 0.15 (改善了!)
     │   └─ 保存到: xaj_iteration_2/
     │
     ├─ 检查停止条件:
     │   ├─ NSE >= 0.5? → NO
     │   ├─ NSE改善 = 0.15 - 0.08 = 0.07 > 0.01 → 有改善
     │   └─ 继续
     │
     ├─ 调整参数范围:
     │   ├─ range_scale = 0.6 × 0.7 = 0.42  # 动态缩小
     │   └─ 以第2轮最佳参数为中心
     │
     ├─ 第3轮率定:
     │   ├─ range_scale = 0.42
     │   ├─ NSE = 0.35
     │   └─ 保存到: xaj_iteration_3/
     │
     ├─ ... (继续迭代)
     │
     └─ 最终停止 (达到NSE阈值或最大轮数):
         └─ 返回汇总结果:
             {
                 "success": True,
                 "iterations": [
                     {"round": 1, "nse": 0.08, "range_scale": 1.0},
                     {"round": 2, "nse": 0.15, "range_scale": 0.6},
                     {"round": 3, "nse": 0.35, "range_scale": 0.42},
                     {"round": 4, "nse": 0.52, "range_scale": 0.29}
                 ],
                 "final_nse": 0.52,
                 "stop_reason": "converged",
                 "best_calibration_dir": "xaj_iteration_4/"
             }
     ↓
DeveloperAgent: 分析迭代历史和最终结果
```

---

## 🔧 具体实现步骤

### Step 1: 修改 TaskPlanner

**文件**: `hydroagent/agents/task_planner.py`

**当前逻辑** (错误):
```python
elif task_type == "iterative_optimization":
    # 创建2个独立任务
    subtasks = [
        {"task_id": "task_1_phase1", ...},
        {"task_id": "task_2_phase2", ...}
    ]
```

**修改为**:
```python
elif task_type == "iterative_optimization":
    # 创建1个循环迭代任务
    subtasks = [{
        "task_id": "iterative_boundary_optimization",
        "task_type": "boundary_check_recalibration",
        "description": "迭代式参数优化（内部循环直到收敛）",
        "parameters": {
            "max_iterations": 5,
            "nse_threshold": 0.5,
            "min_nse_improvement": 0.01,
            "initial_range_scale": 0.6,
            "range_scale_decay": 0.7,
            "consecutive_no_improvement_limit": 2
        },
        "prompt": f"""
你需要生成一个用于迭代优化的hydromodel配置。

任务：对流域 {basin_id} 进行参数率定，如果NSE未达标，系统会自动循环迭代优化。

迭代策略：
- 最大迭代次数: 5轮
- NSE目标阈值: 0.5
- 初始参数范围: 使用默认范围
- 后续迭代: 系统会自动调整参数范围

请生成初始率定配置（标准格式）。
        """
    }]
```

---

### Step 2: 重写 RunnerAgent._run_boundary_check_recalibration()

**文件**: `hydroagent/agents/runner_agent.py`

**新的实现逻辑**:

```python
def _run_boundary_check_recalibration(
    self,
    config: Dict[str, Any],
    parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """
    执行边界感知的迭代率定。

    在RunnerAgent内部进行循环迭代，每轮：
    1. 执行率定
    2. 评估NSE
    3. 检查停止条件
    4. 如果继续，调整参数范围并进入下一轮
    """
    # 提取迭代参数
    max_iterations = parameters.get("max_iterations", 5)
    nse_threshold = parameters.get("nse_threshold", 0.5)
    min_improvement = parameters.get("min_nse_improvement", 0.01)
    initial_range_scale = parameters.get("initial_range_scale", 0.6)
    scale_decay = parameters.get("range_scale_decay", 0.7)
    no_improvement_limit = parameters.get("consecutive_no_improvement_limit", 2)

    logger.info(f"[RunnerAgent] 开始迭代优化 (max_iter={max_iterations}, nse_target={nse_threshold})")

    # 迭代历史记录
    iteration_history = []
    best_nse = -999.0
    consecutive_no_improvement = 0
    current_config = config.copy()

    for iteration in range(1, max_iterations + 1):
        logger.info(f"\n{'='*70}")
        logger.info(f"[RunnerAgent] 迭代轮次 {iteration}/{max_iterations}")
        logger.info(f"{'='*70}")

        # 当前轮次的range_scale
        current_range_scale = initial_range_scale * (scale_decay ** (iteration - 1))
        logger.info(f"[RunnerAgent] 参数范围缩放比例: {current_range_scale:.2%}")

        # === 步骤1: 执行率定 ===
        # 修改experiment_name以区分每轮
        current_config["training_cfgs"]["experiment_name"] = f"xaj_iteration_{iteration}"

        logger.info(f"[RunnerAgent] 开始第{iteration}轮率定...")
        calib_result = self._run_calibration(current_config)

        if not calib_result.get("success"):
            logger.error(f"[RunnerAgent] 第{iteration}轮率定失败")
            break

        # === 步骤2: 评估NSE ===
        eval_result = self._run_evaluation_after_calibration(
            calib_result["calibration_dir"],
            current_config
        )

        current_nse = eval_result.get("nse", -999.0)
        logger.info(f"[RunnerAgent] 第{iteration}轮NSE: {current_nse:.4f}")

        # 记录本轮结果
        iteration_history.append({
            "round": iteration,
            "nse": current_nse,
            "range_scale": current_range_scale if iteration > 1 else 1.0,
            "calibration_dir": calib_result["calibration_dir"],
            "best_params": calib_result.get("best_params", {})
        })

        # === 步骤3: 检查停止条件 ===

        # 条件1: NSE达到阈值
        if current_nse >= nse_threshold:
            logger.info(f"[RunnerAgent] ✅ NSE达到阈值 ({current_nse:.4f} >= {nse_threshold}), 停止迭代")
            stop_reason = "converged"
            break

        # 条件2: 达到最大轮数
        if iteration >= max_iterations:
            logger.info(f"[RunnerAgent] ⚠️  达到最大迭代次数 ({max_iterations}), 停止迭代")
            stop_reason = "max_iterations_reached"
            break

        # 条件3: NSE无改善
        nse_improvement = current_nse - best_nse
        if nse_improvement < min_improvement:
            consecutive_no_improvement += 1
            logger.warning(
                f"[RunnerAgent] NSE改善不足 ({nse_improvement:.4f} < {min_improvement}), "
                f"连续无改善次数: {consecutive_no_improvement}/{no_improvement_limit}"
            )

            if consecutive_no_improvement >= no_improvement_limit:
                logger.warning(
                    f"[RunnerAgent] ❌ 连续{no_improvement_limit}轮无改善, "
                    "建议人工调整参数范围或算法设置"
                )
                stop_reason = "no_improvement"
                break
        else:
            consecutive_no_improvement = 0
            best_nse = current_nse
            logger.info(f"[RunnerAgent] ✅ NSE改善: {nse_improvement:+.4f}")

        # === 步骤4: 调整参数范围，准备下一轮 ===
        logger.info(f"[RunnerAgent] 准备第{iteration+1}轮: 调整参数范围...")

        prev_calib_dir = calib_result["calibration_dir"]
        adjusted_range_yaml = self.workspace_dir / f"adjusted_param_range_iter_{iteration+1}.yaml"

        try:
            adjusted_ranges = self.adjust_param_range_from_previous_calibration(
                prev_calibration_dir=prev_calib_dir,
                range_scale=initial_range_scale * (scale_decay ** iteration),  # 下一轮的scale
                output_yaml_path=str(adjusted_range_yaml)
            )

            # 更新config，使用新的参数范围文件
            current_config["training_cfgs"]["param_range_file"] = str(adjusted_range_yaml)
            logger.info(f"[RunnerAgent] ✅ 参数范围已调整，保存到: {adjusted_range_yaml}")

        except Exception as e:
            logger.error(f"[RunnerAgent] 参数范围调整失败: {e}")
            stop_reason = "range_adjustment_failed"
            break

    # === 返回汇总结果 ===
    final_iteration = iteration_history[-1] if iteration_history else {}

    return {
        "success": True,
        "mode": "boundary_check_recalibration",
        "iterations": iteration_history,
        "total_rounds": len(iteration_history),
        "final_nse": final_iteration.get("nse", -999.0),
        "stop_reason": stop_reason,
        "best_calibration_dir": final_iteration.get("calibration_dir"),
        "best_params": final_iteration.get("best_params", {}),
        "nse_improvement": final_iteration.get("nse", -999.0) - iteration_history[0].get("nse", -999.0) if len(iteration_history) > 1 else 0.0
    }
```

---

### Step 3: 修改 RunnerAgent.process()

**确保正确调用新的循环逻辑**:

```python
def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
    # ... (前面的代码不变)

    # 检测任务类型
    task_type = parameters.get("task_type")

    if task_type == "boundary_check_recalibration":
        # ⭐ 调用循环迭代逻辑
        return self._run_boundary_check_recalibration(config, parameters)

    elif mode == "calibrate":
        # 标准率定流程
        return self._run_calibration_with_evaluation(config)

    # ... (其他模式)
```

---

## 📊 预期效果

### 修改前（错误）:
```
第1轮: 默认范围 → NSE=0.08
第2轮: 默认范围 → NSE=0.08 (❌ 相同)
```

### 修改后（正确）:
```
第1轮: 默认范围[0.1, 1.0] → NSE=0.08, 最佳K=0.936
第2轮: 调整范围[0.655, 1.0] (以0.936为中心, 60%长度) → NSE=0.25 ✅
第3轮: 调整范围[0.796, 1.0] (42%长度) → NSE=0.38 ✅
第4轮: 调整范围[0.866, 1.0] (29%长度) → NSE=0.52 ✅ 达标!
停止原因: converged
```

---

## 🎯 架构优势

### 为什么选择RunnerAgent内部循环？

1. **迭代是原子操作**：参数优化的循环迭代是一个不可分割的过程
2. **减少LLM调用**：不需要每轮都调用TaskPlanner/InterpreterAgent
3. **实时决策**：每轮结束后立即根据NSE决定是否继续
4. **完整的上下文**：RunnerAgent可以访问上一轮的所有输出文件
5. **符合当前架构**：最小化修改，复用现有的adjust_param_range方法

### 与中央编排器循环的对比：

| 方案 | RunnerAgent内部循环 | 中央编排器循环 (BaseExperiment) |
|------|---------------------|--------------------------------|
| 修改范围 | TaskPlanner + RunnerAgent | BaseExperiment + TaskPlanner + InterpreterAgent + RunnerAgent |
| LLM调用次数 | 3次 (Intent + Plan + Interpret) | 每轮都要3次 (15次for 5轮) |
| 实时决策 | ✅ 每轮立即判断 | ❌ 需要返回上层再决策 |
| 代码复杂度 | ⭐⭐⭐ 中等 | ⭐⭐⭐⭐⭐ 很高 |
| 可维护性 | ✅ 高 (逻辑集中) | ❌ 低 (逻辑分散) |

---

## 🚀 实施计划

1. ✅ 设计文档完成
2. ⬜ 修改 TaskPlanner (iterative_optimization分支)
3. ⬜ 重写 RunnerAgent._run_boundary_check_recalibration()
4. ⬜ 测试实验3
5. ⬜ 更新 docs/ITERATIVE_OPTIMIZATION.md
6. ⬜ 更新 CLAUDE.md

---

**Last Updated**: 2025-01-24
**Status**: Design Complete, Ready for Implementation
