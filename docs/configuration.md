# 配置系统

## 配置层级

优先级从低到高（高优先级覆盖低优先级）：

```
1. hydroclaw/config.py  DEFAULTS      <- 项目内部兜底，完整带注释，不建议直接修改
2. configs/model_config.py            <- 用户常用参数（算法轮次、目标函数等）
3. configs/private.py                 <- 私密配置（API Key、数据集路径）
4. 环境变量  LLM_API_KEY              <- CI/服务器场景
5. HydroClaw(config_path="x.json")   <- 单次运行级覆盖
```

**日常使用只需修改 `configs/model_config.py` 和 `configs/private.py`。**

## 配置文件说明

### configs/private.py — 私密配置

```python
# LLM API（必填）
OPENAI_API_KEY  = "sk-your-api-key"
OPENAI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 数据与结果路径（必填）
DATASET_DIR = r"D:\data"       # ⚠️ 填数据集的【父目录】，不是数据集本身
RESULT_DIR  = r"D:\results"
PROJECT_DIR = r"D:\project\Agent\HydroAgent"
CACHE_DIR   = r""              # 可选，留空则默认在 DATASET_DIR 下创建 cache/
```

此文件已加入 `.gitignore`，不会提交到仓库。

> **关于 `DATASET_DIR` 的路径规则：**
>
> HydroClaw 使用的 [AquaFetch](https://github.com/hyex-research/AquaFetch) 会在传入路径后**自动拼接数据集类名**（如 `CAMELS_US`）。
> 因此 `DATASET_DIR` 必须填数据集文件夹的**父目录**：
>
> ```
> DATASET_DIR = D:\data          ← 填这里（父目录）
>                  └── CAMELS_US\ ← AquaFetch 自动找这里
>                       └── camels_*.nc
> ```
>
> 如果填成 `D:\data\CAMELS_US`，AquaFetch 会去找 `D:\data\CAMELS_US\CAMELS_US\`，导致找不到数据并重新下载。
>
> **`~/hydro_setting.yml` 无需手动配置。** HydroClaw 启动时会根据 `DATASET_DIR` 和 `CACHE_DIR` 自动生成/更新此文件。

### configs/model_config.py — 用户自定义参数

```python
DEFAULT_TRAIN_PERIOD = ["2000-01-01", "2009-12-31"]
DEFAULT_TEST_PERIOD  = ["2010-01-01", "2014-12-31"]
DEFAULT_WARMUP_DAYS  = 365

DEFAULT_OBJ_FUNC = "NSE"   # NSE / KGE / RMSE

DEFAULT_SCE_UA_PARAMS = {
    "rep": 1000,   # 评估次数，越大越精确
    "ngs": 200,
    ...
}
```

更细粒度的参数说明见 `hydroclaw/config.py` 中的注释。

### hydroclaw/config.py — 内部完整默认值

项目级兜底配置，确保在 `configs/` 未设置任何参数时也能正常运行。
每个字段都有详细注释，可作为参数参考文档使用。

## 配置字段详解

### LLM 配置

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `model` | `"deepseek-v3.1"` | 模型名称 |
| `base_url` | dashscope URL | API 端点（兼容 OpenAI 格式） |
| `api_key` | 无 | API Key（优先从环境变量读取） |
| `temperature` | `0.1` | 低温度 = 更确定性的工具调用决策 |
| `max_tokens` | `20000` | 最大输出 token |
| `timeout` | `60` | API 超时秒数 |
| `supports_function_calling` | `null` | null = 自动检测；false = 强制 Prompt 降级 |

### 水文模型默认参数

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `model` | `"xaj"` | 默认水文模型：gr4j / gr5j / gr6j / xaj |
| `algorithm` | `"SCE_UA"` | 默认率定算法：SCE_UA / GA / scipy |
| `obj_func` | `"NSE"` | 目标函数：NSE / KGE / RMSE |
| `train_period` | `["2000-01-01", "2009-12-31"]` | 率定训练期 |
| `test_period` | `["2010-01-01", "2014-12-31"]` | 评估测试期 |
| `warmup` | `365` | 预热天数（从训练期开始前计算） |

### SCE-UA 算法参数

| 参数 | 默认值（configs） | 说明 |
|------|-------------------|------|
| `rep` | `1000` | 最大函数评估次数，建议 >= 1000 |
| `ngs` | `200` | 复形数量，建议 = 参数数 × 2~5 |
| `kstop` | `500` | 连续无改进的演化步数（停止条件） |
| `peps` | `0.1` | 参数空间收敛阈值 |
| `pcento` | `0.1` | 目标函数变化百分比收敛阈值 |
| `random_seed` | `1234` | 随机种子（固定保证可复现） |

### GA 算法参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `pop_size` | `40` | 种群大小 |
| `n_generations` | `25` | 最大代数 |
| `cx_prob` | `0.7` | 交叉概率 |
| `mut_prob` | `0.2` | 变异概率 |

### Agent 配置

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `max_turns` | `30` | Agentic Loop 最大轮次 |

## hydromodel 配置构建

`build_hydromodel_config()` 将 HydroClaw 参数转换为 hydromodel 格式：

```python
# HydroClaw 调用
calibrate_model(basin_ids=["12025000"], model_name="gr4j", algorithm="SCE_UA")

# 内部生成的 hydromodel 配置
{
    "data_cfgs": {
        "data_source_type": "camels_us",
        "basin_ids": ["12025000"],
        "train_period": ["2000-01-01", "2009-12-31"],
        "test_period":  ["2010-01-01", "2014-12-31"],
        "warmup_length": 365,
        "variables": ["precipitation", "potential_evapotranspiration", "streamflow"]
    },
    "model_cfgs": {"model_name": "gr4j"},
    "training_cfgs": {
        "algorithm_name": "SCE_UA",
        "algorithm_params": {"rep": 1000, "ngs": 200, ...},
        "loss_config": {"type": "time_series", "obj_func": "spotpy_nashsutcliffe"},  # NSE → 自动映射
        "output_dir": "results/gr4j_12025000",
        "random_seed": 1234
    }
}
```

## 结果目录结构

每次率定输出：

```
results/gr4j_12025000/
├── calibration_results.json     # 最优参数 + 收敛信息
├── basins_norm_params.csv        # 归一化参数（优化器内部使用）
├── basins_denorm_params.csv      # 物理量纲参数（实际参数值）
├── calibration_config.yaml       # 本次率定的完整配置
├── 12025000_sceua.csv            # SCE-UA 优化轨迹
├── train_metrics/
│   └── basins_metrics.csv        # 训练期评估指标（NSE/KGE/RMSE等）
└── test_metrics/
    └── basins_metrics.csv        # 测试期评估指标
```
