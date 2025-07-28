# 水文模型智能助手使用指南

## 简介

这是一个基于 LangChain 和 Ollama 的水文模型智能助手，能够根据用户的问题自动选择和调用合适的水文建模工具。

## 快速开始

1. 确保 Ollama 服务正在运行
2. 安装推荐模型：
   ```bash
   ollama pull granite3-dense:8b
   ```
3. 运行智能助手：
   ```bash
   python script/Agent.py -i
   ```

## 可用工具及测试问题

### 1. get_model_params - 获取模型参数信息

适用场景：查询模型参数、配置信息、模型说明等

测试问题示例：
- "What are the parameters of gr4j model?"
- "Tell me about the parameters of xaj model"
- "What is the valid range for gr4j parameters?"
- "Show me the configuration of gr6j model"
- "What parameters does hymod model use?"
- "Explain the parameters of gr2m model"

### 2. prepare_data - 准备水文数据

适用场景：数据准备、处理、格式转换等

测试问题示例：
- "I need to prepare hydrological data"
- "Help me prepare data from the default data directory"
- "Process the data in the project data folder: data/camels_11532500"
- "Can you prepare the data for model calibration?"
- "Convert my data for hydrological modeling"
- "Prepare basin data for model training"

### 3. calibrate_model - 率定水文模型

适用场景：模型训练、参数优化、自动率定等

测试问题示例：
- "Calibrate gr4j model with default parameters"
- "Help me calibrate the gr4j model"
- "Train hymod model with my data"
- "Optimize gr5j parameters"
- "Run model calibration for gr3j"
- "Perform automatic calibration for my model"

### 4. evaluate_model - 评估模型性能

适用场景：模型评估、性能分析、结果验证等

测试问题示例：
- "Evaluate the calibrated model in result\exp_11532500"
- "Check model performance"
- "How well does the model perform?"
- "Show me the evaluation metrics"
- "Analyze model results"
- "Validate model performance"

## 复杂任务示例

### 完整率定流程
```
1. "What parameters does gr4j model have?"
2. "Prepare data from the camels_11532500 folder"
3. "Calibrate gr4j model using this data"
4. "Evaluate the calibration results"
```

### 模型对比分析
```
1. "Show me the parameters of both gr4j and xaj models"
2. "Prepare data for model comparison"
3. "Calibrate both models"
4. "Compare their performance metrics"
```

## 使用技巧

1. **明确任务类型**：使用关键词帮助智能助手选择正确的工具
   - 参数相关：parameters, config, what is
   - 数据相关：prepare, process, data
   - 率定相关：calibrate, train, optimize
   - 评估相关：evaluate, performance, metrics

2. **提供完整信息**：
   - 指定模型类型（如 gr4j, xaj 等）
   - 提供数据路径
   - 说明特殊要求或参数

3. **使用自动率定模式**：
   ```bash
   python script/Agent.py -a gr4j data/camels_11532500
   ```

4. **保存会话记录**：
   在交互模式下使用 `save session.json` 保存对话历史

## 常见问题解决

1. 如果工具调用失败：
   - 检查数据路径是否正确
   - 确认模型名称拼写正确
   - 查看错误信息中的具体原因

2. 如果模型响应不准确：
   - 使用更明确的关键词
   - 分步骤提问
   - 确保问题聚焦于单个任务

3. 如果需要重新开始：
   - 使用 Ctrl+C 退出当前会话
   - 重新启动智能助手

## 开发者说明

- 模型配置在 `tool/ollama_config.py`
- 工具定义在 `tool/langchain_tool.py`
- 智能体逻辑在 `script/Agent.py`

## 注意事项

1. 推荐使用 granite3-dense:8b 模型
2. 确保数据格式符合要求
3. 大型数据集处理可能需要较长时间
4. 保持网络连接稳定

## 默认配置

1. **数据目录**：
   - 默认路径：在 `definitions.py` 中定义的 `DATASET_DIR`
   - 可以通过参数指定其他路径

2. **默认参数**：
   - 默认模型：`gr4j`
   - 默认时间尺度：`D`（日尺度）
   - 默认结果目录：在 `definitions.py` 中定义的 `RESULT_DIR`

3. **如何修改默认值**：
   - 在问题中明确指定：`"Prepare data from path/to/my/data"`
   - 使用命令行参数：`-a gr6j my/data/path`
   - 修改 `definitions.py` 中的常量
   - 创建 `definitions_private.py` 设置个人配置 