# 记忆系统

> 版本：v2.6 | 日期：2026-03-25

HydroAgent 有三层记忆，覆盖从当前对话到跨会话的信息持久化。

## 三层记忆概览

| 层级 | 存储位置 | 生命周期 | 内容 |
|------|----------|---------|------|
| 会话内 | `messages[]`（内存） | 随对话结束清空 | 当前对话的工具调用历史 |
| 跨会话通用 | `<workspace>/MEMORY.md` | 永久 | Agent 自主积累的通用经验 |
| 流域档案 | `<workspace>/basin_profiles/<id>.json` | 永久 | 每个流域的历史率定记录 |

## 流域档案（Basin Profiles）

### 自动保存

每次 `calibrate_model` 或 `llm_calibrate` 成功后，由 **PostToolUse hook** 自动触发 `save_basin_profile`，无需手动调用：

```json
{
  "basin_id": "12025000",
  "records": [
    {
      "model": "gr4j",
      "algorithm": "SCE_UA",
      "train_nse": 0.783,
      "train_kge": 0.833,
      "train_rmse": 1.45,
      "best_params": {
        "x1": 1180.6,
        "x2": -3.94,
        "x3": 36.9,
        "x4": 1.22
      },
      "calibrated_at": "2026-03-07T14:30:00"
    }
  ]
}
```

同一流域多次率定的记录会追加（append），不会覆盖历史。

### 自动注入上下文

`agent._build_context()` 用正则从查询中提取8位流域 ID，将该流域的历史档案注入 system prompt：

```
[Basin Profile: 12025000]
- gr4j / SCE_UA: train_NSE=0.783, KGE=0.833
- best_params: x1=1180.6, x2=-3.94, x3=36.9, x4=1.22
- calibrated_at: 2026-03-07
```

LLM 读到这段信息后可以：
- **加速收敛**：以历史最优参数缩窄搜索范围
- **稳定性判断**：多次率定结果接近则认为已收敛，避免重复率定
- **异常检测**：若新率定的参数与历史差异极大，主动提示用户

### 手动读写档案

```python
from hydroagent.memory import Memory

mem = Memory(workspace="results/my_workspace")

# 读取流域档案
profile = mem.load_basin_profile("12025000")
print(profile["records"][-1]["train_nse"])   # 最近一次的 NSE

# 手动写入（一般由系统自动调用）
mem.save_basin_profile(
    basin_id="12025000",
    model_name="gr4j",
    best_params={"x1": 1180.6, "x2": -3.94, "x3": 36.9, "x4": 1.22},
    metrics={"NSE": 0.783, "KGE": 0.833, "RMSE": 1.45},
    algorithm="SCE_UA",
)

# 格式化为 LLM 可读的上下文字符串
ctx = mem.format_basin_profiles_for_context(["12025000", "03439000"])
print(ctx)
```

## 对抗先验检测

如果历史档案中存在异常值（如 NSE=0.97 或极端参数），LLM 在分析时会识别并预警：

```
You> 分析流域12025000的历史率定档案，给出下次率定建议

HydroAgent> 注意：历史档案中 x1=1998.0（接近参数上界2000），
           x2=-9.8（接近下界-10），且 NSE=0.97 异常偏高，
           疑似存在过拟合或参数范围设置问题。建议重新率定并检查数据质量。
```

## 跨会话通用记忆（MEMORY.md）

Agent 在对话中发现的重要经验会写入 `<workspace>/MEMORY.md`，下次对话时自动注入。

典型内容：
- 某个流域的特殊水文特性
- 常见错误的解决方案
- 用户偏好的工作方式

MEMORY.md 由 Agent 自主维护，用户也可以手动编辑。

## 会话日志

每次对话自动保存 JSONL 格式的工具调用日志：

```
sessions/
└── 20260307_143000.jsonl    # 时间戳命名
```

每行一条记录：

```json
{"tool": "calibrate_model", "args": {"basin_ids": ["12025000"], "model_name": "gr4j"}, "result": {"success": true, "train_nse": 0.783}, "timestamp": "..."}
```

用于回溯调试和断点续跑分析。

## 错误知识库（error_kb）

`record_error_solution(error, solution)` 将错误-解决方案对写入 `<workspace>/error_solutions.json`，
累计形成可检索的本地知识库。Agent 在遇到相似错误时可调用 `search_memory` 检索已有解决方案。

## 工作目录隔离

不同实验使用独立 workspace，流域档案和记忆互不干扰：

```bash
python -m hydroagent -w results/exp_A "率定GR4J模型，流域12025000"
python -m hydroagent -w results/exp_B "率定GR4J模型，流域12025000"
```

```
results/exp_A/basin_profiles/12025000.json   # 实验 A 的档案
results/exp_B/basin_profiles/12025000.json   # 实验 B 的档案（互不影响）
```
