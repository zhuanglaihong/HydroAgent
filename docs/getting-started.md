# 快速开始

## 环境要求

- Python >= 3.11
- [hydromodel](https://github.com/OuyangWenyu/hydromodel) 已安装
- CAMELS-US 数据集（首次运行时通过 hydrodataset 自动下载）
- 一个 LLM API Key（支持 DeepSeek、Qwen、OpenAI 等 OpenAI 兼容接口）

## 安装

```bash
git clone https://github.com/your-org/HydroAgent.git
cd HydroAgent

# 安装 uv 包管理器（如果没有）
pip install uv

# 安装所有依赖
uv sync

# 激活虚拟环境
.venv\Scripts\activate     # Windows
source .venv/bin/activate   # Linux/macOS
```

## 配置

### 1. 创建私有配置文件

```bash
cp configs/example_definitions_private.py configs/definitions_private.py
```

### 2. 填入 API Key 和数据路径

编辑 `configs/definitions_private.py`：

```python
# LLM API（必填）
OPENAI_API_KEY = "sk-your-api-key"
OPENAI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 数据路径（可选，hydrodataset 会自动管理）
DATASET_DIR = r"D:\data\camels_us"
RESULT_DIR = r"D:\results"
PROJECT_DIR = r"D:\project\Agent\HydroAgent"
```

### 3. （可选）使用 JSON 配置

也可以创建 `hydroclaw.json`：

```json
{
  "llm": {
    "model": "deepseek-v3.1",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "api_key": "sk-your-api-key"
  },
  "defaults": {
    "model": "gr4j",
    "algorithm": "SCE_UA"
  }
}
```

运行时指定：`python -m hydroclaw -c hydroclaw.json`

## 首次运行

### 交互模式

```bash
python -m hydroclaw
```

进入对话界面后输入自然语言查询：

```
HydroClaw - Hydrological Model Calibration Agent
Type your query (Chinese or English). Type 'quit' to exit.

You> 率定GR4J模型，流域12025000
```

### 单次查询

```bash
python -m hydroclaw "率定GR4J模型，流域12025000，SCE-UA算法"
```

### 命令行参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `query` | 查询内容（省略则进入交互模式） | `"率定GR4J..."` |
| `-c, --config` | 配置文件路径 | `-c config.json` |
| `-w, --workspace` | 工作目录 | `-w results/exp1` |
| `-v, --verbose` | 详细日志输出 | `-v` |
| `--log-file` | 指定日志文件 | `--log-file run.log` |

### 验证安装

运行一个简单的流域验证来确认一切正常：

```bash
python -m hydroclaw "验证流域12025000是否存在"
```

如果输出显示流域有效，说明数据集和 API 配置都正常。

## 常见问题

### API Key 无效

```
Error: openai.AuthenticationError
```

检查 `configs/definitions_private.py` 中的 `OPENAI_API_KEY` 是否正确。

### 找不到数据集

```
Error: Dataset not found
```

确认 `DATASET_DIR` 路径正确，或让 hydrodataset 自动下载：

```python
import hydrodataset
hydrodataset.download("camels_us")
```

### LLM 不支持 Function Calling

HydroClaw 会自动检测并降级到 Prompt 模式，无需手动配置。如果想强制使用 Prompt 模式：

```json
{
  "llm": {
    "supports_function_calling": false
  }
}
```

## 下一步

- [使用指南](usage.md) — 了解所有使用场景
- [架构文档](architecture.md) — 理解系统设计
- [工具参考](tools.md) — 查看所有可用工具
