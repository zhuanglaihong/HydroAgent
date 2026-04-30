# 快速开始

> 版本：v2.6 | 日期：2026-03-25

## 环境要求

- Python >= 3.11
- [hydromodel](https://github.com/OuyangWenyu/hydromodel) 已安装
- CAMELS-US 数据集（需提前下载并配置路径）
- 一个 LLM API Key（支持 DeepSeek、Qwen、OpenAI 等 OpenAI 兼容接口）

## 安装

```bash
git clone https://github.com/your-org/HydroAgent.git
cd HydroAgent

# 创建虚拟环境并安装依赖（使用 pip，不要用 uv）
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt  # Linux/macOS

# 激活虚拟环境
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # Linux/macOS
```

> **注意**：本项目不使用 uv（已知 uv 在部分环境下会崩溃）。向 `.venv` 安装包统一用 `.venv/Scripts/python.exe -m pip install <包名>`。

## 配置

> **首次使用必须完成此步骤**，否则无法连接 LLM 和读取数据。

### 第一步：填入 API Key 和数据路径

复制模板并编辑：

```bash
cp configs/example_private.py configs/private.py
```

编辑 `configs/private.py`：

```python
# LLM API（必填）
OPENAI_API_KEY  = "sk-your-api-key"
OPENAI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 数据路径（必填）
DATASET_DIR = r"D:\data"    # ⚠️ 填数据集的【父目录】，不是数据集本身
                             #   数据在 D:\data\CAMELS_US\ → 填 D:\data
RESULT_DIR  = r"D:\results"
PROJECT_DIR = r"D:\project\Agent\HydroAgent"
CACHE_DIR   = r""           # 可选，留空则自动在 DATASET_DIR 下创建 cache/
```

此文件已加入 `.gitignore`，不会提交到仓库。

> **路径注意事项：** `DATASET_DIR` 必须填数据集文件夹的**父目录**。
> HydroAgent 依赖的 AquaFetch 会自动在该目录下拼接 `CAMELS_US/` 等子目录名，
> 如果填成数据集目录本身，会导致 AquaFetch 找不到数据并重新触发下载。
>
> **无需手动配置 `~/hydro_setting.yml`**，HydroAgent 启动时会自动根据 `configs/private.py` 中的路径生成该文件。

### 第二步：（可选）调整算法参数

编辑 `configs/model_config.py` 修改常用参数：

```python
DEFAULT_OBJ_FUNC = "NSE"        # 目标函数

DEFAULT_SCE_UA_PARAMS = {
    "rep": 1000,                # 迭代轮次，越大越精确
    "ngs": 200,
    ...
}
```

> 更细粒度的参数说明见 `hydroagent/config.py` 中的注释。

## 首次运行

### 验证安装

```bash
python -m hydroagent "验证流域12025000是否存在"
```

如果输出显示流域有效，说明数据集路径和 API 配置都正常。

### 交互模式

```bash
python -m hydroagent
```

进入对话界面后直接输入自然语言查询：

```
You> 率定GR4J模型，流域12025000
```

HydroAgent 会自动：验证流域 -> 执行率定 -> 评估结果 -> 汇报 NSE/KGE 等指标。

### 单次查询

```bash
python -m hydroagent "率定GR4J模型，流域12025000，SCE-UA算法"
```

## 常见问题

### API Key 无效

```
Error: openai.AuthenticationError
```

检查 `configs/private.py` 中的 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL` 是否匹配。

### 找不到数据集 / 重新触发下载

```
Error: Dataset not found / Basin not in dataset
```

确认 `DATASET_DIR` 填的是数据集的**父目录**（如 `D:\data`，而非 `D:\data\CAMELS_US`）。
AquaFetch 会在该目录下自动拼接 `CAMELS_US/` 子目录，如果填错层级会找不到已有数据并触发重新下载。

### LLM 不支持 Function Calling

HydroAgent 会自动检测并降级到 Prompt 模式，无需手动配置。如需强制使用 Prompt 模式，在 `configs/definitions_private.py` 中添加：

```python
# 或在 configs/config.py 中设置
# HydroAgent(config_path="x.json") 时也可在 JSON 中设置
```

或创建 `hydroagent_config.json`：

```json
{
  "llm": {
    "supports_function_calling": false
  }
}
```

### Train NSE 为空

确保 `configs/model_config.py` 中的 `DEFAULT_OBJ_FUNC = "NSE"`（而不是 RMSE）。率定完成后系统会自动在训练期和测试期分别评估，结果保存到 `train_metrics/` 和 `test_metrics/` 子目录。

## Web 服务模式

```bash
python -m hydroagent --server          # 启动 Web 服务（默认端口 7860）
python -m hydroagent --server --port 8080
```

浏览器自动打开 `http://localhost:7860`，提供对话界面、工具/技能面板、水文包管理、历史会话等功能。

## 下一步

- [使用指南](usage.md) — 所有使用场景示例
- [工具参考](tools.md) — 所有可用工具详解
- [架构文档](architecture.md) — 系统设计原理（详细技术文档）
- [配置参考](configuration.md) — 所有配置项说明
- [记忆系统](memory.md) — 跨会话流域档案机制
- [Skill 参考](skills.md) — Skill 工具 API 与编写规范
