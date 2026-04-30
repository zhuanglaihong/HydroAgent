# Exp2 设计文档

> 更新：2026-04-10 | 对应论文 Section 4.3

---

## 一、核心主张（论文要验证的事）

**LLM 智能率定的本质是模拟人工经验**。

人工专家率定水文模型时做两件事：
1. **先验知识**：根据流域气候特征（湿润 / 干旱 / 地中海型），提前判断哪些参数范围合理
2. **自适应调整**：看到率定结果后，根据参数是否触边界、NSE 是否合理，主动缩窄或扩展搜索空间

实验要证明的是：**Agent 能像人类水文专家一样完成上述两步，且在 NSE 上优于纯脚本方法（B），不低于标准 SCE-UA（A）**。

关键：Agent 的行为不是写死在工具函数里的脚本，而是 Agent 学习方法论后自主调用工具、推理、决策的结果。

---

## 二、为什么旧版 Method C 没有改善

**旧策略**：`llm_calibrate()` 内部固定写死"运行 SCE-UA → 看边界 → 调范围"

问题根源：**被动等待，无先验，逻辑在工具内部**。

- LLM 没有拿到流域属性，无法在第 1 轮就做有意义的范围调整
- SCE-UA 在默认范围内已收敛（no boundary hits），LLM 无从触发调整
- 这是脚本行为，不是 Agent 行为，无法体现"模拟人工经验"的论文主张

---

## 三、新实验设计

### 3.1 流域选择（3 个，代表不同气候区）

| 流域 | 气候区 | 选择理由 |
|------|--------|---------|
| 12025000 Fish River, ME | 湿润寒冷 | exp1 表现好，参照流域 |
| 11532500 Smith River, CA | 地中海 | 强季节性，参数空间有挑战 |
| 03439000 French Broad, NC | 湿润暖 | exp1 XAJ KGE=-0.110，默认范围不贴合，先验知识有改善空间 |

### 3.2 三路方法定义

| 方法 | 名称 | 执行方式 | 本质 |
|------|------|---------|------|
| **A** | SCE-UA 标准基线 | Agent 驱动，**1 次运行**，默认参数范围 | "不懂流域"的标准实践 |
| **B** | Zhu et al. 脚本复现 | 纯脚本，LLM 直接猜参数值，±3% 范围，≤15轮 | 外部对照，LLM 直接提议参数 |
| **C** | HydroAgent LLM 率定 | Agent 驱动，先验+自适应（见下） | 模拟人类专家经验 |

> Method A 改为 **1 次运行**，代表"标准实践"，不取多次最优。

### 3.3 主指标

**主指标：NSE（test 期）**，次指标：KGE（test 期）

---

## 四、新 Method C 架构：工具 + 知识 + Agent 自主决策

### 架构原则

不把逻辑写死在工具函数里，而是：
- **工具层**：提供能力（读属性、跑率定、调整范围）
- **知识层**：教方法（skill.md + knowledge 文件告诉 Agent 该怎么做）
- **Agent**：自主决策，学会像人一样操作

### 新增工具：`get_basin_attributes`

`validate_basin` 只返回数据路径和时段有效性，**不含气候属性**。
需新建轻量工具读取 CAMELS 属性文件：

```python
get_basin_attributes(basin_id: str) -> dict
# 返回：aridity, runoff_ratio, baseflow_index,
#        p_seasonality, frac_snow, climate_zone 等
# 数据来源：camels_clim.txt + camels_hydro.txt
```

### `param_ranges` 传入方式

`llm_calibrate` 已支持外部传入参数范围：

```python
llm_calibrate(
    basin_ids=["12025000"],
    model_name="xaj",
    param_ranges={"K": [0.7, 1.0], "SM": [30, 80], ...},  # Agent 推理后传入
    max_rounds=5,
)
```

Agent 在调用 `llm_calibrate` 之前，先查属性、推理，再把得到的范围作为参数传入。
工具内部的迭代循环以这个范围为起点，不再使用默认范围。

### Agent 的工作流程（由 skill.md 教导）

```
Step 1: get_basin_attributes(basin_id)
        → 拿到 aridity / runoff_ratio / BFI / frac_snow

Step 2: Agent 推理（依据 knowledge/xaj_param_guide.md 中的领域知识）
        例：湿润流域 → K 偏高(0.7-1.0), SM 较大, CG 接近1.0
            地中海   → KG 较高, CS 较小
            湿润暖   → 类湿润冷但 frac_snow 少, L 可偏小

Step 3: llm_calibrate(param_ranges=推理结果, ...)
        → 工具内部 LLM 基于 Round 结果做自适应调整（触界检测+参数收敛固定）
```

这个流程中，Step 1-2 是 Agent 自主决策，体现"先验知识"；
Step 3 工具内部的多轮迭代体现"自适应调整"。

### 知识层需要准备的内容

| 文件 | 内容 |
|------|------|
| `skills/llm_calibration/skill.md` | 重写工作流：Step 1 先查属性，Step 2 推理范围，Step 3 调用工具 |
| `knowledge/xaj_param_guide.md` | XAJ 各参数物理含义 + 不同气候区的典型取值范围 |

---

## 五、实验记录（论文数据需求）

exp2 脚本需额外记录以下字段，用于论文说明 Agent 真正做了 basin-aware 推理：

```json
{
  "basin_id": "12025000",
  "basin_attributes": {
    "aridity": 0.52, "runoff_ratio": 0.54, "baseflow_index": 0.73
  },
  "method_C": {
    "initial_param_ranges_llm": {"K": [0.7,1.0], "SM": [30,100], ...},
    "initial_param_ranges_default": {"K": [0.1,1.0], "SM": [1,100], ...},
    "range_delta": {"K": [-0.6, 0], "SM": [+29, 0], ...},
    "nse_history": [0.71, 0.75, 0.76, 0.76, 0.76],
    "fixed_params_by_round": {2: ["CG","CI"], 3: ["L","IM"]},
    "rounds": 5,
    "test_nse": 0.76
  }
}
```

关键字段：
- `initial_param_ranges_llm` vs `initial_param_ranges_default`：对比说明 Agent 做了有意义的范围收窄
- `range_delta`：量化先验知识的"收窄程度"
- `fixed_params_by_round`：说明 Agent 做了参数固定决策
- `nse_history`：轨迹曲线，展示逐轮改善过程

---

## 六、预期结论

| 流域 | 预期 C vs A | 预期 C vs B | 论文意义 |
|------|------------|------------|---------|
| 12025000 | C ≈ A 或略优 | C >> B | 好流域上 LLM 不损失精度 |
| 11532500 | C ≈ A 或略优 | C >> B | 地中海季节性同样适用 |
| 03439000 | C > A（预期+0.1）| C >> B | 困难流域体现先验知识价值 |

Method B 在 15 参数 XAJ 上必然失效（±3% 猜值策略在高维空间无效），C >> B 是结构性优势。

---

## 七、实现清单（待开发）

- [ ] 新建 `hydroagent/tools/basin_attrs.py`：`get_basin_attributes` 工具，读 CAMELS 属性
- [ ] 新建 `hydroagent/knowledge/xaj_param_guide.md`：XAJ 参数气候区对照知识
- [ ] 重写 `hydroagent/skills/llm_calibration/skill.md`：加入 3 步工作流
- [ ] `llm_calibrate.py`：确认 `param_ranges` 外部传入生效，补充参数固定逻辑
- [ ] `experiment/exp2_llm_calibration.py`：
      流域改为 12025000/11532500/03439000，Model=XAJ，N_SEEDS_A=1，
      记录 basin_attributes + initial_param_ranges_llm + fixed_params_by_round
