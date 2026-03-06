# 配置系统

## 配置加载优先级

从高到低：

1. **命令行参数** — `-c config.json`
2. **JSON 配置文件** — `hydroclaw.json`
3. **HydroAgent 兼容配置** — `configs/definitions_private.py` → `configs/definitions.py`
4. **环境变量** — `LLM_API_KEY`
5. **内置默认值** — `hydroclaw/config.py` 中的 `DEFAULTS`

## 配置方式

### 方式 1: HydroAgent 兼容（推荐）

如果已有 HydroAgent 配置，HydroClaw 会自动读取：

```python
# configs/definitions_private.py
OPENAI_API_KEY = "sk-your-api-key"
OPENAI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DATASET_DIR = r"D:\data\camels_us"
RESULT_DIR = r"D:\results"
PROJECT_DIR = r"D:\project\Agent\HydroAgent"
```

### 方式 2: JSON 配置文件

```json
{
  "llm": {
    "model": "deepseek-v3.1",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "api_key": "sk-your-api-key",
    "temperature": 0.1,
    "max_tokens": 20000,
    "timeout": 60,
    "supports_function_calling": null
  },
  "defaults": {
    "model": "xaj",
    "algorithm": "SCE_UA",
    "train_period": ["2000-01-01", "2009-12-31"],
    "test_period": ["2010-01-01", "2014-12-31"],
    "warmup": 365
  },
  "algorithms": {
    "SCE_UA": {"rep": 500, "ngs": 200, "kstop": 500, "peps": 0.1, "pcento": 0.1, "random_seed": 1234},
    "GA": {"pop_size": 40, "n_generations": 25, "cx_prob": 0.7, "mut_prob": 0.2, "random_seed": 1234},
    "scipy": {"method": "SLSQP", "max_iterations": 500}
  },
  "paths": {
    "dataset_dir": "D:\\data\\camels_us",
    "results_dir": "results",
    "project_dir": null
  },
  "max_turns": 30
}
```

### 方式 3: 环境变量

```bash
export LLM_API_KEY="sk-your-api-key"
python -m hydroclaw
```

环境变量名由 `llm.api_key_env` 配置项控制，默认为 `LLM_API_KEY`。

## 配置字段详解

### LLM 配置

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `model` | str | `"deepseek-v3.1"` | 模型名称 |
| `base_url` | str | dashscope URL | API 端点 |
| `api_key` | str | 无 | API Key |
| `temperature` | float | `0.1` | 温度参数（低=更确定） |
| `max_tokens` | int | `20000` | 最大输出 token |
| `timeout` | int | `60` | API 超时秒数 |
| `supports_function_calling` | bool/null | `null` | Function Calling 支持，null=自动检测 |

### 默认水文参数

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `model` | `"xaj"` | 默认水文模型 |
| `algorithm` | `"SCE_UA"` | 默认率定算法 |
| `train_period` | `["2000-01-01", "2009-12-31"]` | 训练期 |
| `test_period` | `["2010-01-01", "2014-12-31"]` | 测试期 |
| `warmup` | `365` | 预热天数 |

### 算法默认参数

**SCE-UA**:

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `rep` | 500 | 采样次数 |
| `ngs` | 200 | 复合体数量 |
| `kstop` | 500 | 停止标准步数 |
| `random_seed` | 1234 | 随机种子 |

**GA**:

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `pop_size` | 40 | 种群大小 |
| `n_generations` | 25 | 代数 |
| `random_seed` | 1234 | 随机种子 |

### Agent 配置

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `max_turns` | `30` | Agentic Loop 最大轮数 |

## hydromodel 配置构建

`build_hydromodel_config()` 将 HydroClaw 的参数转换为 hydromodel 期望的配置格式：

```python
# HydroClaw 调用
calibrate_model(basin_ids=["12025000"], model_name="gr4j", algorithm="SCE_UA")

# 内部生成的 hydromodel 配置
{
    "data_cfgs": {
        "data_source_type": "camels_us",
        "basin_ids": ["12025000"],
        "train_period": ["2000-01-01", "2009-12-31"],
        "test_period": ["2010-01-01", "2014-12-31"],
        "warmup_length": 365,
        "variables": ["precipitation", "potential_evapotranspiration", "streamflow"]
    },
    "model_cfgs": {"model_name": "gr4j"},
    "training_cfgs": {
        "algorithm_name": "SCE_UA",
        "algorithm_params": {"rep": 500, "ngs": 200, ...},
        "output_dir": "results/gr4j_SCE_UA_12025000",
        "random_seed": 1234
    }
}
```

用户指定的参数覆盖默认值，未指定的使用默认值。
