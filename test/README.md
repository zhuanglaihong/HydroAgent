# Test 文件夹说明文档

## 概述

test文件夹包含了项目的各种测试文件，涵盖了水文模型工具、RAG系统、Ollama集成等多个方面的测试。这些测试文件用于验证项目的各个组件是否正常工作。

## 🚀 推荐测试顺序

### 快速验证流程
```bash
# 1. 基础集成测试（必须先通过）⭐
python test/test_ollama_integration.py granite3-dense:8b

# 2. 详细工具测试（在基础测试通过后运行）🎯
python test/test_individual_tools.py
```

### 完整测试流程  
```bash
# 1. 基础功能测试
python test/test_basic_tools.py
python test/test_tools.py

# 2. 集成测试（核心）
python test/test_ollama_integration.py granite3-dense:8b

# 3. 详细验证
python test/test_individual_tools.py

# 4. 高级测试
python test/test_tool_support.py
python test/test_rag_system.py
```

⚠️ **重要**: `test_individual_tools.py` 必须在 `test_ollama_integration.py` 成功后运行

**新增功能**:
- **综合工具使用测试**: 全面诊断工具系统问题，包括工具注册、代理工具使用、模型工具理解等
- **工具调用验证**: 直接测试工具是否正确注册和可用
- **代理行为分析**: 检查代理是否真正使用工具而不是基于自己的知识回答

## 文件结构

```
test/
├── README.md                           # 本说明文档
├── test_tools.py                      # 水文模型工具测试
├── test_basic_tools.py                # 基本工具功能测试
├── test_ollama_integration.py         # Ollama集成测试
├── test_tool_decorator.py             # 工具装饰器测试
├── test_rag_system.py                 # RAG系统测试
├── test_tool_support.py  # 模型工具支持验证测试（包含综合工具使用测试）
├── calibrate_gr.py                    # GR模型率定脚本
├── evaluate_gr.py                     # GR模型评估脚本
└── prepare_data.py                    # 数据准备脚本
```

## 测试文件详细说明

### 1. test_tools.py
**功能**: 测试所有水文模型 LangChain 工具
**主要测试内容**:
- 工具模块导入测试
- 工具实例化测试
- 工具参数模式测试
- 工具调用方法测试
- LangChain工具集成测试

**运行方式**:
```bash
python test/test_tools.py
```

### 2. test_basic_tools.py
**功能**: 基本工具功能测试
**主要测试内容**:
- 基本模块导入测试
- Pydantic模型测试
- 工具结构测试
- 文件结构测试
- 简单函数测试

**运行方式**:
```bash
python test/test_basic_tools.py
```

### 3. test_ollama_integration.py ⭐
**功能**: 测试 Ollama 与 LangChain 水文模型工具的集成（基础验证）
**主要测试内容**:
- Ollama配置测试
- LangChain工具测试
- Ollama LLM测试
- 智能体创建测试（单工具验证）

**运行方式**:
```bash
# 运行所有测试（使用自动选择的模型）
python test/test_ollama_integration.py

# 指定模型进行测试（推荐）
python test/test_ollama_integration.py granite3-dense:8b
```

**关键特性**:
- **基础功能验证**: 确保 Ollama 服务、模型和工具加载正常
- **单工具验证**: 使用 get_model_params 工具验证基本调用能力
- **优化配置应用**: 为 granite3-dense:8b 自动应用最佳配置
- **前置条件检查**: 为后续详细测试提供基础保障

**成功标志**: 所有 4 项测试通过，确认系统可以正常运行

### 4. test_individual_tools.py 🎯
**功能**: 测试 LLM 是否可以调用每一个水文模型工具（详细验证）
**主要测试内容**:
- 单个工具独立调用测试
- 工具参数传递验证
- 工具结果返回检查
- 关键词匹配验证
- 详细错误分析

**前置条件**:
⚠️ **必须先运行 test_ollama_integration.py 确保基础功能正常**

**运行方式**:
```bash
# 确保前置测试通过
python test/test_ollama_integration.py granite3-dense:8b

# 然后运行详细工具测试
python test/test_individual_tools.py
```

**测试策略**:
- **单工具代理**: 为每个工具创建独立的代理，避免工具选择困难
- **优化配置**: 应用经过验证的 granite3-dense:8b 最佳配置
- **英文提示**: 针对 granite 模型使用英文提示模板
- **关键词验证**: 检查工具返回结果是否包含预期内容

**测试工具列表**:
1. **get_model_params** - 获取模型参数信息
2. **prepare_data** - 准备水文数据
3. **calibrate_model** - 率定水文模型  
4. **evaluate_model** - 评估水文模型

**成功标志**: 所有 4 个工具都能被正确调用并返回有效结果

### 5. test_tool_decorator.py
**功能**: 测试 @tool 装饰器功能 - 支持类方法和函数式工具
**主要测试内容**:
- 工具导入测试
- 类工具实例化测试
- 函数式工具导入测试
- 工具属性测试
- 工具调用测试
- 工具比较测试

**运行方式**:
```bash
python test/test_tool_decorator.py
```

### 6. test_rag_system.py
**功能**: RAG系统测试模块 - 测试文档加载、向量存储、检索和生成功能
**主要测试内容**:
- 文档加载器测试
- 向量存储测试
- 检索器测试
- 生成器测试
- RAG系统集成测试

**运行方式**:
```bash
python test/test_rag_system.py
```

### 7. test_tool_support.py
**功能**: 验证 Ollama 模型是否支持工具调用，并测试工具使用情况
**主要测试内容**:
- 测试所有可用模型
- 验证工具调用功能
- 识别支持/不支持工具的模型
- 直接测试工具调用
- 测试代理是否真正使用工具
- 测试模型对工具的理解能力
- 提供模型推荐

**运行方式**:
```bash
# 测试所有可用模型
python test/test_tool_support.py

# 测试特定模型
python test/test_tool_support.py llama3:8b

# 运行综合测试（包括工具使用测试）
python test/test_tool_support.py --comprehensive
```

**新增功能**:
- **直接工具调用测试**: 验证工具是否正确注册和可用
- **代理工具使用测试**: 检查代理是否真的使用工具而不是基于自己的知识回答
- **模型工具理解测试**: 验证模型是否理解工具的使用方式
- **综合测试**: 一次性运行所有测试并生成总结报告

### 8. test_ollama_tool_execution.py
**功能**: 专门测试 Ollama 是否真正执行工具并返回结果
**主要测试内容**:
- 直接工具调用验证
- 代理工具执行验证
- 模型理解能力测试
- 水文模型工具实际执行测试
- 工具执行日志追踪
- 结果返回验证

**运行方式**:
```bash
# 运行完整的工具执行测试
python test/test_ollama_tool_execution.py
```

**测试特点**:
- **执行日志追踪**: 每个工具调用都会记录执行日志，确保真正被执行
- **结果验证**: 检查代理回复是否包含工具执行的实际结果
- **多层次测试**: 从直接调用到代理调用的全流程验证
- **问题诊断**: 详细的错误分析和问题定位

**解决的核心问题**:
- 验证 LLM 是否真正调用工具而不只是返回工具定义
- 确认工具执行后的结果是否正确返回给用户
- 诊断为什么代理可能只输出 `{"type":"function",...}` 而不执行工具

### 9. test_quick_tool_verification.py
**功能**: 快速验证工具调用修复的简化测试脚本
**主要测试内容**:
- 使用修复后配置的简单工具调用验证
- 水文模型工具快速验证
- 工具调用流程完整性检查

**运行方式**:
```bash
# 快速验证修复效果
python test/test_quick_tool_verification.py
```

**测试特点**:
- **快速验证**: 专注于验证修复后的工具调用是否正常工作
- **简化流程**: 使用最简单的测试用例快速定位问题
- **实时反馈**: 立即显示工具是否被执行和结果是否返回
- **修复验证**: 验证 `early_stopping_method="force"` 和增加的迭代次数是否解决了问题

**✅ 验证成功的配置**:
- **首选模型**: `granite3-dense:8b` (验证完全支持工具调用)
- **优化配置**: temperature=0.1, top_p=0.8, num_ctx=8192
- **英文提示**: granite 模型使用英文提示效果更佳
- **AgentExecutor**: early_stopping_method="force", max_iterations=5


## 水文模型脚本

### 10. calibrate_gr.py
**功能**: GR模型率定脚本
**主要功能**:
- 支持多种GR模型率定（GR4J、GR5J等）
- 支持交叉验证
- 支持自定义参数范围
- 支持多种算法和损失函数

**使用方法**:
```bash
python test/calibrate_gr.py --model gr4j --data_dir data/camels_11532500
```

**主要参数**:
- `--model`: 模型名称
- `--data_dir`: 数据目录
- `--result_dir`: 结果保存目录
- `--exp`: 实验名称
- `--cv_fold`: 交叉验证折数

### 11. evaluate_gr.py
**功能**: GR模型评估脚本
**主要功能**:
- 评估率定后的模型性能
- 支持训练集和测试集评估
- 生成评估结果和图表

**使用方法**:
```bash
python test/evaluate_gr.py --result_dir result --exp exp_11532500
```

**主要参数**:
- `--result_dir`: 结果目录
- `--exp`: 实验名称
- `--cv_fold`: 交叉验证折数

### 12. prepare_data.py
**功能**: 数据准备脚本
**主要功能**:
- 处理原始水文数据
- 支持不同时间尺度（日、月、年）
- 保存为NetCDF格式

**使用方法**:
```bash
python test/prepare_data.py --origin_data_dir data/camels_11532500 --target_data_scale D
```

**主要参数**:
- `--origin_data_dir`: 原始数据目录
- `--target_data_scale`: 目标时间尺度（D/M/Y）

## 🎯 测试运行指南

> **注意：** 运行测试前请确保已正确安装所有依赖，并启动相关服务（如 Ollama）。

### 测试脚本说明

#### 1. 水文模型工具相关测试

- **基础环境与功能测试**  
  在运行完整的水文模型工具测试前，建议先验证基本环境和依赖是否正常：

  ```bash
  python test/test_basic_tools.py
  ```

- **水文模型工具集成测试**  
  检查水文模型工具的整体功能：

  ```bash
  python test/test_tools.py
  ```
- **工具装饰器功能测试**  
  检查 langchain tool 装饰器的功能实现：

  ```bash
  python test/test_tool_decorator.py
  ```
#### 2. 大语言模型相关测试

- **Ollama 集成测试**  
  验证与 Ollama 的集成能力：

  ```bash
  python test/test_ollama_integration.py
  ```

- **模型工具支持验证**  
  验证当前安装的模型是否支持工具调用：

  ```bash
  python test/test_tool_support.py
  ```

  > **注意：** 如果遇到 "does not support tools" 错误，请运行此测试来找到支持工具的模型。

- **综合工具使用测试**  
  全面测试工具系统是否正常工作：

  ```bash
  python test/test_tool_support.py --comprehensive
  ```

  > **功能：** 此测试会检查工具注册、代理工具使用、模型工具理解等多个方面，帮助诊断为什么代理没有使用工具的问题。



#### 3. RAG 知识库相关测试

- **RAG 系统测试**  
  验证知识库导入与检索功能：

  ```bash
  python test/test_rag_system.py
  ```

## 测试结果说明

### 成功标志
- ✅ 表示测试通过
- 📋 表示信息输出
- 🎯 表示关键步骤
- ⚙️ 表示配置信息

### 失败标志
- ❌ 表示测试失败
- ⚠️ 表示警告信息

## 常见问题解决

### 1. 模型不支持工具调用
**错误信息**: `does not support tools (status code: 400)`

**解决方案**:
1. 运行模型工具支持验证测试：
   ```bash
   python test/test_tool_support.py
   ```

2. 下载支持工具的模型：
   ```bash
   # 推荐模型
   ollama pull llama3:8b
   ollama pull llama3.2:7b
   ollama pull deepseek-coder
   ```

3. 更新 `tool/ollama_config.py` 中的模型列表

**当前支持工具的模型**:
- **Llama3 系列**: `llama3:8b`, `llama3.2:7b`, `llama3.2:3b`, `llama3.1:8b`
- **代码模型**: `deepseek-coder`, `codellama`, `codellama:7b`
- **其他模型**: `mistral:7b`, `qwen2.5:7b`, `phi3:mini`

### 2. Ollama 服务未启动
**错误信息**: `Connection refused` 或 `Ollama 服务未运行`

**解决方案**:
1. 启动 Ollama 服务：
   ```bash
   ollama serve
   ```

2. 检查服务状态：
   ```bash
   curl http://localhost:11434/api/tags
   ```

### 3. 水文模型模块导入失败
**错误信息**: `ModuleNotFoundError: No module named 'hydromodel'`

**解决方案**:
1. 确保在项目根目录运行测试
2. 检查 Python 路径设置
3. 安装缺失的依赖包

### 4. 代理创建失败
**错误信息**: `Input to ChatPromptTemplate is missing variables`

**解决方案**:
1. 检查 `tool/langchain_agent.py` 中的提示模板
2. 确保使用支持工具的模型
3. 验证工具配置是否正确

### 5. 代理没有使用工具
**问题描述**: 代理基于自己的知识回答问题，而不是调用工具

**解决方案**:
1. 运行综合测试诊断问题：
   ```bash
   python test/test_tool_support.py --comprehensive
   ```

2. 检查工具是否正确注册：
   - 验证工具装饰器是否正确应用
   - 检查工具参数模式是否正确
   - 确认工具在代理中正确加载

3. 检查模型是否真的支持工具：
   - 使用支持工具的模型（如 llama3:8b）
   - 验证模型配置是否正确

4. 优化提示词：
   - 在 `tool/langchain_agent.py` 中明确要求使用工具
   - 提供具体的工具使用指导

5. 检查工具调用日志：
   - 启用详细日志查看工具调用过程
   - 确认工具是否被正确调用

