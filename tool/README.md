# 水文模型 LangChain 工具（本地 Ollama 版本）

这个模块将您的水文模型 MCP 工具集成到 LangChain 框架中，使用本地 Ollama 大模型，使其可以与 LangChain 代理和链式调用一起使用。

## 功能特性

### 🔧 可用工具

1. **get_model_params** - 获取模型参数信息
   - 输入：模型名称（如 'gr4j', 'xaj', 'sac-sma'）
   - 输出：参数名称和范围

2. **prepare_data** - 准备水文数据
   - 输入：数据目录路径、时间尺度
   - 输出：数据处理状态

3. **calibrate_model** - 率定水文模型
   - 输入：模型配置、数据路径、时间范围等
   - 输出：率定结果和保存路径

4. **evaluate_model** - 评估模型性能
   - 输入：结果目录路径
   - 输出：评估指标（R2等）

### 🤖 本地 Ollama 支持

- 自动检测可用的 Ollama 模型
- 智能选择最佳模型（优先使用较小的模型）
- 针对不同模型类型优化配置参数
- 支持多种模型：llama2, deepseek-coder, codellama, qwen2.5 等

## 安装依赖

```bash
# 安装 LangChain 相关依赖
pip install langchain langchain-core langchain-ollama

# 安装水文模型依赖
pip install hydromodel

# 安装 Ollama（如果还没有安装）
# 访问 https://ollama.ai/ 下载并安装
```

## 推荐使用uv安装环境

```bash
pip install uv

uv sync

.venv\Scripts\activate

```

## 安装和配置 Ollama

### 1. 安装 Ollama

访问 [Ollama 官网](https://ollama.ai/) 下载并安装。

### 2. 下载模型

```bash
# 首选模型（经过验证，工具调用效果最佳）
ollama pull granite3-dense:8b

# 备选模型
ollama pull llama3-groq-tool-use:8b
ollama pull llama3:8b
ollama pull llama3.2:7b
ollama pull deepseek-coder
```

### 3. 启动 Ollama 服务

```bash
# 启动 Ollama 服务
ollama serve
```

## 使用方法

### 1. 检查 Ollama 状态

```bash
# 检查 Ollama 服务状态
python tool/langchain_agent.py --mode status
```

### 2. 测试本地 LLM

```bash
# 测试本地 Ollama LLM
python tool/langchain_agent.py --mode llm
```

### 3. 基本使用

```python
from tool.langchain_tool import get_hydromodel_tools, HydroModelTools
from tool.ollama_config import create_ollama_llm_with_config

# 获取工具列表
tools = get_hydromodel_tools()

# 创建本地 Ollama LLM
llm = create_ollama_llm_with_config()

# 创建工具实例
tools_instance = HydroModelTools()

# 使用工具
result = tools_instance.get_model_params("gr4j")
print(result)
```

### 4. 在 LangChain 代理中使用

```python
from tool.langchain_agent import create_hydromodel_agent

# 创建代理
agent = create_hydromodel_agent()

# 使用代理
response = agent.invoke({
    "input": "请帮我率定一个 gr4j 模型"
})
print(response['output'])
```

### 5. 运行示例

```bash
# 工具测试
python test/test_tools.py

# 运行工作流程示例
python tool/langchain_agent.py --mode workflow

# 交互式聊天
python tool/langchain_agent.py --mode chat

# 测试单个工具
python tool/langchain_agent.py --mode test

# 测试 LLM
python tool/langchain_agent.py --mode llm

# 检查状态
python tool/langchain_agent.py --mode status
```

### 6. 完整集成测试

```bash
# 运行完整的集成测试
python test/test_ollama_integration.py
```

## 工具参数说明

### ModelParamsInput
- `model_name`: 模型名称（必需）

### PrepareDataInput
- `data_dir`: 数据目录路径（默认：项目数据目录）
- `target_data_scale`: 时间尺度，'D'/'M'/'Y'（默认：'D'）

### CalibrateModelInput
- `data_type`: 数据类型（默认：'owndata'）
- `data_dir`: 数据目录（默认：项目数据目录）
- `result_dir`: 结果保存目录（可选）
- `exp_name`: 实验名称（默认：'exp_11532500'）
- `model_name`: 模型名称（默认：'gr4j'）
- `basin_ids`: 流域ID列表（默认：['11532500']）
- `periods`: 整个时间段（默认：['2013-01-01', '2023-12-31']）
- `calibrate_period`: 率定时间段（默认：['2013-01-01', '2018-12-31']）
- `test_period`: 测试时间段（默认：['2019-01-01', '2023-12-31']）
- `warmup`: 预热期长度（默认：720）
- `cv_fold`: 交叉验证折数（默认：1）

### EvaluateModelInput
- `result_dir`: 率定结果保存目录（必需）
- `exp_name`: 实验名称（默认：'exp_11532500'）
- `cv_fold`: 交叉验证折数（默认：1）

## Ollama 模型配置

系统会自动为不同模型类型选择最佳配置：

### Llama2 系列
- `temperature`: 0.7
- `top_p`: 0.9
- `num_ctx`: 4096
- `repeat_penalty`: 1.1

### 代码模型（DeepSeek-Coder, CodeLlama）
- `temperature`: 0.3
- `top_p`: 0.95
- `num_ctx`: 8192
- `repeat_penalty`: 1.1

### Qwen2.5 系列
- `temperature`: 0.7
- `top_p`: 0.9
- `num_ctx`: 4096/8192
- `repeat_penalty`: 1.1

## 示例对话

```
用户: 请告诉我 gr4j 模型的参数信息
助手: gr4j 模型有 4 个参数：X1, X2, X3, X4。参数范围如下...

用户: 我想准备水文数据
助手: 我将帮您准备水文数据。使用默认数据目录...

用户: 请帮我率定一个 gr4j 模型
助手: 我将为您率定 gr4j 模型。使用默认参数...

用户: 评估刚才率定的模型
助手: 我将评估刚才率定的模型。结果显示训练期 R2 为 0.85...
```

## 错误处理

工具包含完善的错误处理机制：

- **Ollama 服务检查**: 自动检测服务状态
- **模型可用性检查**: 验证模型是否正确下载
- **模块导入失败**: 给出警告和解决建议
- **数据目录检查**: 验证路径是否存在
- **模型率定失败**: 返回详细错误堆栈
- **评估失败**: 返回错误原因

## 性能优化

### 模型选择策略
1. 优先选择较小的模型（7B 优先于 13B）
2. 根据任务类型选择合适模型（代码任务选择代码模型）
3. 自动测试模型可用性

### 内存管理
- 自动调整上下文窗口大小
- 根据模型类型优化参数
- 支持流式输出减少内存占用

## 故障排除

### 常见问题

1. **Ollama 服务未运行**
   ```bash
   # 启动服务
   ollama serve
   ```

2. **模型下载失败**
   ```bash
   # 重新下载模型
   ollama pull llama2:7b
   ```

3. **内存不足**
   - 使用较小的模型（7B 而不是 13B）
   - 减少 `num_ctx` 参数
   - 关闭其他占用内存的程序

4. **工具导入失败**
   - 检查 hydromodel 是否正确安装
   - 确认 Python 路径设置正确

5. **代理创建失败**
   - 检查 Ollama 服务状态
   - 确认模型已正确下载
   - 验证网络连接

### 调试命令

```bash
# 检查 Ollama 状态
python tool/langchain_agent.py --mode status

# 测试 LLM
python tool/langchain_agent.py --mode llm

```

## 扩展功能

您可以轻松扩展这个框架：

1. **添加新模型支持**: 在 `ollama_config.py` 中添加新模型配置
2. **自定义工具**: 在 `langchain_tool.py` 中添加新工具
3. **优化提示模板**: 修改系统提示以获得更好的效果
4. **集成其他组件**: 添加向量数据库、文档加载器等

## 关于 tool 装饰器

本项目采用**双重方法设计模式**，同时提供带装饰器和不带装饰器的方法：

### 1. 原始方法（`_raw` 后缀）
```python
def get_model_params_raw(self, model_name: str) -> Dict[str, Any]:
    """原始业务逻辑实现"""
    # 直接调用，用于测试和调试
```

**特点：** 直接调用、易于测试、不依赖框架

### 2. 装饰器方法（`@tool`）
```python
@tool("get_model_params", args_schema=ModelParamsInput)
def get_model_params(model_name: str) -> Dict[str, Any]:
    """LangChain 工具包装器"""
    temp_instance = HydroModelTools()
    return temp_instance.get_model_params_raw(model_name)
```

**特点：** LangChain 集成、参数验证、类型安全

### 使用场景

- **开发/测试**：使用原始方法 `get_model_params_raw()`
- **生产环境**：使用装饰器方法 `get_model_params()`
- **LangChain 集成**：通过 `get_hydromodel_tools()` 获取工具列表
