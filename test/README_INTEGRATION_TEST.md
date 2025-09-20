# HydroAgent 完整系统集成测试

## 测试概述

本测试验证HydroAgent系统的完整工作流程，从用户查询到最终执行的端到端集成：

```
用户查询 → 知识库检索(RAG) → 工作流生成 → MCP工具执行
```

### 测试场景

**主要测试查询**: "整理数据camels_11532500流域，用其率定GR4J模型，并评估模型"

**预期流程**:
1. **知识库检索**: 使用HydroRAG系统检索相关工具文档
2. **工作流生成**: 使用Ollama+工作流生成器创建任务序列
3. **MCP工具执行**: 依次执行prepare_data、calibrate_model、evaluate_model

## 系统要求

### 必需组件

1. **Ollama服务** (运行在localhost:11434)
   - qwen3:8b模型 (用于对话和推理)
   - bge-large:335m模型 (用于文本嵌入)

2. **Python依赖**
   ```bash
   pip install ollama pandas numpy xarray
   ```

3. **测试数据**
   - CAMELS数据集 (basin_11532500)
   - 位置: `data/camels_11532500/`
   - 必需文件: `basin_11532500.csv`, `basin_attributes.csv`

4. **知识库**
   - HydroRAG向量数据库
   - 位置: `documents/vector_db/`

### 可选组件

- `basin_11532500_monthly.csv`
- `basin_11532500_yearly.csv` 
- `attributes.nc`
- `timeseries.nc`

## 运行测试

### 方法1: 快速测试

```bash
# 进入test目录
cd test

# 运行完整集成测试
python run_integration_test.py
```

### 方法2: 详细测试

```bash
# 直接运行主测试文件
python test_complete_workflow_integration.py
```

### 方法3: 组件检查

```bash
# 仅检查系统组件状态
python -c "
import asyncio
from test_complete_workflow_integration import SystemComponentChecker

async def check():
    checker = SystemComponentChecker()
    print('检查Ollama...', checker.check_ollama_connection())
    print('检查RAG...', checker.check_hydrorag_system())
    print('检查工作流...', checker.check_workflow_generator())
    print('检查MCP工具...', checker.check_mcp_tools())
    print('检查数据...', checker.check_data_availability())

asyncio.run(check())
"
```

## 测试流程详解

### 阶段1: 系统组件检查

测试会首先验证所有必要组件:

- ✅ **Ollama连接**: 验证qwen3:8b和bge-large:335m模型
- ✅ **HydroRAG系统**: 测试知识库检索功能
- ✅ **工作流生成器**: 验证工作流创建能力
- ✅ **MCP工具**: 检查所有4个水文工具可用性
- ✅ **测试数据**: 确认CAMELS数据集完整性

### 阶段2: 完整流程测试

#### 步骤1: 知识库检索
```
用户查询: "整理数据camels_11532500流域，用其率定GR4J模型，并评估模型"
↓
增强查询: 添加工具相关关键词
↓
RAG检索: 从向量数据库检索相关文档片段
↓
结果: 8个相关知识片段，包含工具使用说明
```

#### 步骤2: 工作流生成
```
输入: 用户查询 + RAG检索结果
↓
意图分析: 识别为完整建模流程
↓
CoT推理: 逐步分解任务
↓
工作流组装: 创建任务序列
↓
结果: 包含3个任务的工作流
  - Task1: prepare_data (数据预处理)
  - Task2: calibrate_model (模型率定)  
  - Task3: evaluate_model (模型评估)
```

#### 步骤3: MCP工具执行
```
任务队列: [prepare_data, calibrate_model, evaluate_model]
↓
依次执行每个MCP工具
↓
结果: 执行成功率和详细结果
```

## 预期结果

### 成功指标

- ✅ 所有组件检查通过
- ✅ 知识库检索到相关片段 (≥5个)
- ✅ 工作流生成成功 (3个任务)
- ✅ 至少50%的任务执行成功
- ✅ 总耗时 < 5分钟

### 输出文件

- **日志文件**: `test/integration_test.log`
- **结果文件**: `test/integration_test_results.json`

### 示例成功输出

```
🚀 HydroAgent完整系统集成测试
============================================================
测试查询: 整理数据camels_11532500流域，用其率定GR4J模型，并评估模型

=== 系统组件检查 ===
✅ Ollama连接成功，模型可用
✅ HydroRAG系统正常，检索到12个知识片段
✅ 工作流生成器正常，生成了1个任务
✅ MCP工具正常，可用工具: get_model_params, prepare_data, calibrate_model, evaluate_model
✅ 测试数据完整

=== 步骤1：知识库检索 ===
✅ 知识检索完成，找到8个相关片段，耗时2.40秒

=== 步骤2：工作流生成 ===
✅ 工作流生成成功
   - 工作流ID: wf_complete_modeling_001
   - 任务数量: 3
   - 验证问题: 0
   - 生成时间: 32.15秒

=== 步骤3：MCP工具执行 ===
执行任务: 数据预处理 (工具: prepare_data)
   ✅ 任务成功，耗时15.23秒
执行任务: 模型率定 (工具: calibrate_model)  
   ✅ 任务成功，耗时180.45秒
执行任务: 模型评估 (工具: evaluate_model)
   ✅ 任务成功，耗时25.12秒

✅ 工具执行完成
   - 总任务数: 3
   - 成功任务: 3
   - 成功率: 100.0%
   - 总耗时: 220.80秒

🎉 完整测试流程完成
总耗时: 255.35秒

📊 测试总结
============================================================
用户查询: 整理数据camels_11532500流域，用其率定GR4J模型，并评估模型
总体成功: ✅
总耗时: 255.35秒
测试时间: 2025-09-20 11:30:15
```

## 故障排除

### 常见问题

1. **Ollama连接失败**
   ```bash
   # 启动Ollama服务
   ollama serve
   
   # 下载所需模型
   ollama pull qwen3:8b
   ollama pull bge-large:335m
   ```

2. **知识库为空**
   ```bash
   # 重新构建向量数据库
   cd hydrorag
   python demo_hydrorag.py
   ```

3. **测试数据缺失**
   ```bash
   # 检查数据目录
   ls -la data/camels_11532500/
   
   # 确保包含必需文件
   - basin_11532500.csv
   - basin_attributes.csv
   ```

4. **MCP工具失败**
   ```bash
   # 检查hydromodel依赖
   pip install -r requirements.txt
   
   # 测试单个工具
   python -c "
   from hydromcp.tools import HydroModelMCPTools
   tools = HydroModelMCPTools()
   print(tools.get_model_params('gr4j'))
   "
   ```

### 调试模式

设置环境变量启用详细日志:

```bash
export HYDROAGENT_DEBUG=1
python run_integration_test.py
```

## 扩展测试

### 添加新测试用例

编辑 `test_config.py` 中的 `test_queries` 添加新的测试场景。

### 自定义参数

修改 `test_config.py` 中的配置参数来调整测试行为。

### 批量测试

```python
# 运行所有测试用例
from test_complete_workflow_integration import CompleteWorkflowTester
from test_config import TEST_CONFIG

async def run_all_tests():
    tester = CompleteWorkflowTester()
    await tester.setup_components()
    
    for test_case in TEST_CONFIG["test_queries"]:
        print(f"测试: {test_case['description']}")
        await tester.run_complete_test(test_case["query"])
```

## 结果分析

测试结果保存在 `integration_test_results.json` 中，包含:

- 各阶段耗时统计
- 工具执行成功率
- 错误详情和建议
- 系统性能指标

可用于系统优化和问题诊断。
