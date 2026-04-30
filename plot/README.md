# plot/ — 论文配图工作目录

> 更新：2026-04-07 | 论文目标期刊：GMD 或 JoH

---

## 一、实验结果数据总览

所有原始结果在 `results/paper/`，读取时均需 `encoding='utf-8'`（系统默认 GBK 会报错）。

### Exp1：标准率定基线

**文件**：`results/paper/exp1/exp1_results.json`

5 流域 × 2 模型，Agent 驱动 SCE-UA 率定，结果如下：

| 流域 | 气候区 | GR4J train NSE | GR4J test NSE | XAJ train NSE | XAJ test NSE |
|------|--------|---------------|--------------|--------------|-------------|
| 12025000 Fish R. ME | 湿润冷 | 0.784 | 0.748 | 0.724 | 0.776 |
| 11532500 | 湿润 | 0.704 | 0.741 | 0.592 | 0.577 |
| 08101000 | 半干旱 | 0.512 | -0.625 | 0.098 | -1.034 |
| 06043500 | 半干旱 | -0.108 | -0.180 | 0.096 | 0.119 |
| 03439000 French Broad NC | 湿润暖 | -2.296 | -0.872 | 0.105 | 0.064 |

每个结果条目字段：`basin_id / model_name / success / train_metrics / test_metrics / best_params / calibration_time_s`

指标字段：`NSE / KGE / RMSE / Bias / Corr / R2 / FHV / FLV`（train 和 test 各一份）

率定结果目录：`results/paper/exp1/gr4j_<basin_id>/`、`xaj_<basin_id>/`（含模拟流量时间序列）

**已知问题**：
- 03439000 GR4J 的 NSE=-2.296（训练期），远低于气候学均值，属于模型不适配或数据问题
- 08101000 test NSE 远差于 train（GR4J: 0.512 -> -0.625），明显过拟合
- 这两个流域的失败结果**不应隐藏**，发散色系 colormap 需体现负 NSE

---

### Exp2：LLM 参数范围调控 vs 基线

**文件**：`results/paper/exp2/exp2_results.json`

3 流域（12025000 / 11532500 / 06043500），模型 GR4J，三路对比：

| 流域 | 方法A (SCE-UA 基线) test NSE | 方法B (Zhu直接提议) test NSE | 方法C (HydroClaw范围调控) test NSE |
|------|-----------------------------|-----------------------------|----------------------------------|
| 12025000 | 0.748 | 0.758 | 0.748 |
| 11532500 | 0.741 | 0.748 | 0.741 |
| 06043500 | -0.181 | -0.120 | -0.149 |

各方法字段：`success / best_params / tool_sequence / calibration_time_s / train_metrics / test_metrics`

方法C 专有字段：`nse_history`（每轮 NSE）/ `rounds` / `llm_calibrate_failed`

**已知问题**：
- 方法C 的 `train_metrics` 为 null（仅有 test_metrics），`rounds` 为 null
- 方法C 的 `nse_history` 全轮相同（Agent 未实现有效范围扩展，5轮 NSE 均等于 A 方法首轮结果）
- 这意味着 Exp2 的核心叙事是"三路方法 NSE 相当"，而非"方法C 有显著提升"
- 方法B `test_metrics` 存在，但 `train_metrics` 需从 `results/paper/exp2/B_<model>_<basin>/` 目录读取

---

### Exp3：Agent 能力广度

**文件**：`results/paper/exp3/exp3_results.json`

结构：`sections -> A / B / C`，Section A 为自然语言鲁棒性测试

Section A 每条结果字段：
```
id / category / description / query
expected_tools / expected_first / actual_tools
first_tool_correct / tool_match / success
response_preview / time_s / error
```

**注意**：description 和 query 字段中文为乱码（原始数据存储问题），但 actual_tools 列表正常

Section A 可用数据：`actual_tools` 序列（可用于甘特图）、`tool_match` 布尔值、`first_tool_correct`

Section B/C 结构待确认（动态 Skill 生成 / 自驱动规划结果）

---

### Exp4：知识层消融 K0-K4 + 认知框架评估

**文件**：`results/paper/exp4/exp4_results.json`

结构：`main_ablation` + `adversarial_robustness`

条件：K0 / K1 / K2 / K3 / K4（+认知框架，水文学家.skill，★新增）

场景：T1 标准率定 / T2 边界检测 / T3 代码分析 / T4 认知诊断（★新增）

**T1-T3 结果**（K0-K4，tool_match 均为 1.0）：

| 条件 | tool_match_rate | avg_tokens | avg_time_s |
|------|----------------|-----------|-----------|
| K0 无知识 | 1.0 | 96,799 | 98.8s |
| K1 +Skill | 1.0 | 82,939 | 82.6s |
| K2 +领域知识 | 1.0 | 73,257 | 82.5s |
| K3 +记忆（三层完整）| 1.0 | 72,961 | 78.0s |
| K4 +认知框架（四层完整）| 1.0 | 78,290 | 90.4s |

**T4 认知评估结果**（K0-K4 全部参与）：

| 条件 | PhysScore | CorrectConclusion | 代表性关键词 |
|------|-----------|-----------------|------------|
| K0 | 0.233 | True | 产流、模型结构、蒸散发 |
| K1 | 0.333 | True | +汇流、基流、半干旱 |
| K2 | 0.400 | True | +超渗、蓄满、产流机制 |
| K3 | 0.333 | True | 略降（记忆检索分散注意力）|
| K4 | **0.533** | True | +退水、结构性、runoff、baseflow（完整水文响应链）|

**已有结论（K0-K4）**：
- 工具选择准确率全为 1.0，知识注入不影响工具序列（工作流规划在 K0 已饱和）
- token 效率 K0→K3 单调递减（96K→73K，-25%），知识越丰富推理越直接
- K4 token 代价低（+7% vs K3），认知框架轻量注入
- **T4 核心结论**：K4 物理推理分 0.533（K0 的 2.3 倍），唯一覆盖完整水文响应链词汇
- K2 > K1（领域知识使 Agent 进入机制性推理层）；K3 略降 K2（记忆检索双刃剑效应）

---

## 二、待绘制图表清单

### P0：必须有（缺了审稿人会要求补）

#### Fig.1 — 系统架构图
- **类型**：手绘流程图（draw.io 或 PowerPoint，导出为 PDF/PNG）
- **内容**：五层大脑-脊椎-四肢模型 + 七段式 system prompt 动态拼装 + ReAct Loop 示意
- **参考**：AQUAH 论文 Figure 1，AI4Water GMD Figure 1
- **注意**：不要画 UML，用模块框 + 箭头 + 颜色分层，一张图说清楚"用户一句话 -> 工具调用 -> 结果"

#### Fig.2 — Exp1 NSE 热力图（流域×模型矩阵）
- **类型**：imshow 热力图，两个子图（train / test）
- **数据**：`exp1_results.json`，5×2 矩阵
- **关键修复**：`vmin=-0.5, vmax=1.0`，colormap 用 `RdYlGn`（发散，以 0 为中心），不要 `vmin=0.3`
- **标注**：每格写数值，NSE<0 的格子加粗边框或标红色文字
- **子标题**：(a) Training period  (b) Test period

#### Fig.3 — 代表性流域水文过程线
- **类型**：双子图时间序列（上图线性，下图对数坐标）
- **数据**：`results/paper/exp1/gr4j_12025000/` 目录中的模拟径流 CSV（需确认具体文件名）
- **内容**：Q_obs（黑线）vs Q_sim（蓝线），差值阴影，右上角文本框标 NSE/KGE 值
- **选 2 个流域**：一个好的（12025000，NSE=0.748）+ 一个差的（03439000 或 08101000，展示局限性）
- **说明**：这是水文论文的核心证明图，没有它会被要求补

---

### P1：重要（体现 Agent 智能的核心证据）

#### Fig.4 — 工具调用序列甘特图（Exp3-A）
- **类型**：横向彩色色块甘特图
- **数据**：`exp3_results.json -> sections -> A -> results -> actual_tools`
- **布局**：每行=一个查询场景（A01-A06），横轴=调用步骤，每个工具一种颜色
- **工具颜色方案**：
  ```
  validate_basin   -> #4878CF  (蓝)
  calibrate_model  -> #D65F5F  (红)
  evaluate_model   -> #6ACC65  (绿)
  llm_calibrate    -> #FF9F40  (橙)
  read_file        -> #C4AD66  (黄棕)
  inspect_dir      -> #d9d9d9  (灰)
  generate_code    -> #82C4E0  (浅蓝)
  visualize        -> #956CB4  (紫)
  ```
- **右侧标注**：tool_match=True 打勾，False 打叉

#### Fig.5 — Exp2 三路方法对比柱状图
- **类型**：分组柱状图（3 组×3 条柱）
- **数据**：`exp2_results.json`，3 流域，方法 A/B/C
- **关键修复**：方法B train NSE 需从 `results/paper/exp2/B_gr4j_<basin>/` 目录读取，不能用 JSON 中的 null
- **说明**：主结论是三路方法 NSE 相当（C ≈ A），体现自动化流程不损失精度
- **可加小图**：方法C 的工具调用序列条（validate_basin -> llm_calibrate -> evaluate_model），展示智能调控路径

#### Fig.6 — Exp4 知识消融：两图并排
- **左图**：token 效率（K0-K4 五条件，柱高=avg_tokens T1-T3 均值，折线=tool_match_rate 恒为 1.0）
  - 体现"知识增加不提升准确率但 K3 大幅增加 token；K4 token 增量较小"
  - 数据：`exp4_results.json -> main_ablation -> stats_by_condition`
- **右图**：T4 认知评估对比（K0 / K3 / K4 三条件）
  - 双指标柱状：`physical_reasoning_score` + `correct_conclusion`（bool 转 0/1）
  - 体现认知框架（K4）在推理质量上的价值
  - 数据：`results[condition_id=K*/scenario_id=T4]`
- **备注**：K2 token 反比 K1 少需在图注解释（领域知识减少无效推理轮次）

---

### P2：可选增强（有条件再做）

#### Fig.7 — 参数边界蜘蛛图（Exp2）
- **类型**：雷达图 / 平行坐标
- **数据**：各方法 `best_params`，归一化到 [0,1]（0=下界，1=上界）
- **作用**：参数触边界的视觉证明（值接近 1.0 = 上边界）

#### Fig.8 — Exp1 流量历时曲线（FDC）
- **类型**：对数 y 轴，横轴超过概率（0-100%）
- **数据**：率定结果目录中的模拟流量序列
- **作用**：评估高流量和低流量的拟合情况（补充 NSE 关注峰流的不足）

---

## 三、已有代码

`plot_paper_figures.py`（从 `experiment/` 目录移入此处）— 已实现 Fig.2/Fig.5/Fig.6 的初版，有以下已知 bug：

| Bug | 位置 | 修复方法 |
|-----|------|---------|
| Fig.2 热力图 vmin=0.3 截断负 NSE | 热力图绘制行 | 改为 `vmin=-0.5, cmap='RdYlGn'` |
| Fig.5 方法B train NSE 全为 0 | exp2 数据读取 | 从 `B_gr4j_<basin>/` 目录读取，而非 JSON 中的 null |
| Fig.6 消融柱状图四条等高 | exp4 绘图逻辑 | 改为绘制 avg_tokens，tool_match_rate 作右轴折线 |

---

## 四、绘图规范（投 GMD/JoH 的格式要求）

- **字体**：Times New Roman 或 Helvetica，正文 10pt，轴标签 9pt，图题 9pt bold
- **分辨率**：最终提交 ≥ 300 DPI（GMD 要求 PDF 矢量图）
- **色盲友好**：不要红绿区分，用 RdYlBu 或 viridis
- **图幅**：单栏 8.3cm，双栏 17cm（GMD 标准）
- **图注**：每张图写完整 caption，格式：`Figure N. [主标题]. [子图说明]. [数据来源说明].`
- **代码**：每张图的绘图代码放独立 `.py` 文件，命名 `fig{N}_{描述}.py`，统一 `savefig(dpi=300, bbox_inches='tight')`

---

## 五、优先级与工作顺序

```
第一步（写论文前必须有）：
  [x] 确认 results/paper/ 数据完整性
  [ ] Fig.1 架构图（手绘，不依赖代码）
  [ ] Fig.2 修复 NSE 热力图
  [ ] Fig.3 水文过程线（需找率定目录中的模拟径流文件）

第二步（Methods/Results 章节配图）：
  [ ] Fig.4 工具调用甘特图（Exp3 核心证据）
  [ ] Fig.5 修复三路对比柱状图
  [ ] Fig.6 重做知识消融图（改为 token 效率）

第三步（Discussion 补充，有时间再做）：
  [ ] Fig.7 参数边界蜘蛛图
  [ ] Fig.8 流量历时曲线
```
