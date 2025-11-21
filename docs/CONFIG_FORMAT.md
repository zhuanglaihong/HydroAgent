# HydroAgent 配置格式说明

## 两种配置格式

### 1. **简化格式 (Simplified Format)** - 仅用于文件配置

**用途**: 给最终用户手写配置文件使用
**文件**: `configs/example_config.yaml`
**处理**: 通过 `load_simplified_config()` 转换为统一格式

```yaml
# 简化格式 - 用户友好
data:
  dataset: "camels_us"
  basin_ids: ["01013500"]
  train_period: ["2000-01-01", "2010-12-31"]
  test_period: ["2011-01-01", "2015-12-31"]
  warmup_length: 365

model:
  name: "gr4j"
  params:
    source_type: "sources"

training:
  algorithm: "SCE_UA"
  loss: "RMSE"
  SCE_UA:
    rep: 5000
    ngs: 1000

evaluation:
  metrics: ["NSE", "RMSE", "KGE"]
```

### 2. **统一格式 (Unified Format)** - hydromodel API 接受的格式

**用途**: hydromodel 内部使用
**来源**: `get_default_calibration_config()` 返回值
**使用**: 直接传递给 calibrate() 函数

```python
# 统一格式 - API 格式
{
    "data_cfgs": {
        "data_source_type": "camels_us",
        "data_source_path": None,
        "basin_ids": ["01013500"],
        "warmup_length": 365,
        "variables": [
            "precipitation",
            "potential_evapotranspiration",
            "streamflow"
        ],
        "train_period": ["2000-01-01", "2010-12-31"],
        "test_period": ["2011-01-01", "2015-12-31"]
    },
    "model_cfgs": {
        "model_name": "gr4j",
        "model_params": {
            "source_type": "sources",
            "source_book": "HF",
            "kernel_size": 15
        }
    },
    "training_cfgs": {
        "algorithm_name": "SCE_UA",
        "algorithm_params": {
            "rep": 5000,
            "ngs": 1000
        },
        "loss_config": {
            "type": "time_series",
            "obj_func": "RMSE"
        },
        "output_dir": "results",
        "experiment_name": None,
        "random_seed": 1234,
        "save_config": True
    },
    "evaluation_cfgs": {
        "metrics": ["NSE", "RMSE", "KGE", "PBIAS"],
        "save_results": True,
        "plot_results": True
    }
}
```

## HydroAgent 的配置流程

### ❌ 错误理解

```
用户输入 → IntentAgent → ConfigAgent → 生成 YAML 文件 → RunnerAgent 读取文件 → 调用 hydromodel
```

### ✅ 正确流程

```
用户输入: "率定GR4J模型，流域01013500"
  ↓
IntentAgent (解析意图)
  ↓
  返回 dict: {
    "intent": "calibration",
    "model_name": "gr4j",
    "basin_id": "01013500",
    ...
  }
  ↓
ConfigAgent (修改默认配置)
  ↓
  1. config = get_default_calibration_config()  # 获取默认 dict
  2. config["model_cfgs"]["model_name"] = "gr4j"  # 修改字段
  3. config["data_cfgs"]["basin_ids"] = ["01013500"]
  ↓
  返回 dict: config  # 不是 YAML 文件！
  ↓
RunnerAgent (执行)
  ↓
  直接传递 dict: calibrate(config)  # 不需要读取文件
```

## ConfigAgent 的关键设计

### 核心原则

1. **不生成文件** - ConfigAgent 返回的是 dict，不是 YAML 文件路径
2. **基于默认值** - 从 `get_default_calibration_config()` 获取默认配置
3. **修改字段** - 只修改用户指定的字段，其他保持默认
4. **直接传递** - config dict 直接传给下游 Agent，不经过文件系统

### 代码示例

```python
from hydroagent.agents import IntentAgent, ConfigAgent
from hydroagent.core.llm_interface import create_llm_interface

# 1. 创建 LLM 后端
llm = create_llm_interface('ollama', 'qwen3:8b')

# 2. 解析用户意图
intent_agent = IntentAgent(llm)
intent_result = intent_agent.process({
    "query": "率定GR4J模型，流域01013500"
})["intent_result"]

# 3. 生成配置 dict
config_agent = ConfigAgent(llm)
config_result = config_agent.process({
    "intent_result": intent_result
})

# 4. 获取配置 dict (不是文件路径！)
config_dict = config_result["config"]

# 5. 直接传递给 hydromodel
from hydromodel.trainers.unified_calibrate import calibrate
result = calibrate(config_dict)  # 传递 dict，不是文件路径
```

### ConfigAgent 工作流程

```python
def process(self, input_data):
    # Step 1: 获取默认配置
    config = self._get_default_config()
    # 返回: get_default_calibration_config() 的结果

    # Step 2: 应用用户意图
    config = self._apply_intent_to_config(config, intent_result)
    # 修改: config["model_cfgs"]["model_name"] = "gr4j"
    #      config["data_cfgs"]["basin_ids"] = ["01013500"]
    #      config["data_cfgs"]["train_period"] = [...]

    # Step 3: 验证配置
    is_valid, errors = self._validate_config(config)

    # Step 4: 返回配置 dict
    return {
        "success": True,
        "config": config,  # 返回 dict，不是文件路径！
        "config_summary": "..."
    }
```

## 字段映射关系

| 简化格式 (YAML) | 统一格式 (dict) | 说明 |
|----------------|----------------|------|
| `data.dataset` | `data_cfgs.data_source_type` | 数据集类型 |
| `data.path` | `data_cfgs.data_source_path` | 数据路径 |
| `data.basin_ids` | `data_cfgs.basin_ids` | 流域列表 |
| `data.train_period` | `data_cfgs.train_period` | 训练时段 |
| `data.test_period` | `data_cfgs.test_period` | 测试时段 |
| `data.warmup_length` | `data_cfgs.warmup_length` | 预热期 |
| `model.name` | `model_cfgs.model_name` | 模型名称 |
| `model.params.*` | `model_cfgs.model_params.*` | 模型参数 |
| `training.algorithm` | `training_cfgs.algorithm_name` | 算法名称 |
| `training.loss` | `training_cfgs.loss_config.obj_func` | 损失函数 |
| `training.SCE_UA` | `training_cfgs.algorithm_params` | 算法参数 |
| `evaluation.metrics` | `evaluation_cfgs.metrics` | 评估指标 |

## 何时使用简化格式

简化格式**仅用于**以下场景：

1. **用户手写配置文件** - 存储在 `configs/` 目录
2. **配置模板** - 作为示例给用户参考
3. **持久化存储** - 保存用户自定义配置

简化格式**不用于**：

1. ❌ Agent 之间传递配置
2. ❌ 调用 hydromodel API
3. ❌ 内存中的配置操作

## 何时使用统一格式

统一格式用于：

1. ✅ Agent 内部处理
2. ✅ 调用 hydromodel API
3. ✅ 配置修改和验证
4. ✅ 传递给下游组件

## 配置转换

如果需要从简化格式转换为统一格式：

```python
from hydromodel.configs.config_manager import load_simplified_config

# 从 YAML 文件加载
unified_config = load_simplified_config("configs/example_config.yaml")

# 从 dict 加载
simplified_dict = {
    "data": {...},
    "model": {...},
    "training": {...},
    "evaluation": {...}
}
unified_config = load_simplified_config(simple_config=simplified_dict)
```

## 总结

| 方面 | 简化格式 | 统一格式 |
|-----|---------|---------|
| 用途 | 用户配置文件 | API 调用 |
| 存储位置 | 文件系统 | 内存 |
| 谁使用 | 最终用户 | Agent/hydromodel |
| 格式 | YAML | Python dict |
| 转换 | `load_simplified_config()` | `get_default_calibration_config()` |
| ConfigAgent | ❌ 不生成 | ✅ 生成和修改 |

---

**关键要点**: ConfigAgent 操作的是 **统一格式 dict**，不生成 YAML 文件！
