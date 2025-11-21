# IntentAgent 测试说明

## 测试文件
- `test_intent_agent.py` - IntentAgent 自然语言理解完整测试

## 运行测试

### 前提条件

**选项1：使用 Ollama 本地模型（推荐）**
```bash
# 1. 确保 Ollama 服务正在运行
ollama serve

# 2. 确认 qwen3:8b 模型已安装
ollama list

# 3. 如果没有，拉取模型
ollama pull qwen3:8b
```

**选项2：使用通义千问云端API**
- 确保在 `test_intent_agent.py` 中配置了有效的 API Key
- 或设置环境变量 `QWEN_API_KEY`

### 运行测试

```bash
# 在项目根目录下运行
python test/test_intent_agent.py
```

### 测试内容

测试包含4个部分：

1. **基础功能测试** - 测试 IntentAgent 的基本查询解析
2. **综合查询测试** - 8个测试用例，覆盖各种场景：
   - 完整的中文查询
   - 完整的英文查询
   - 模糊查询（缺失信息）
   - 评估意图
   - 扩展任务（可视化等）
   - 模拟任务
   - 指定算法的查询
3. **中英文混合测试** - 测试混合语言输入
4. **错误处理测试** - 测试边界情况和异常处理

### 测试输出

- 控制台输出：实时显示测试进度和结果
- 日志文件：`logs/test_intent_agent_YYYYMMDD_HHMMSS.log`

### 预期结果

所有测试用例应该能够：
- ✅ 正确识别意图（calibration/evaluation/simulation/extension）
- ✅ 提取模型名称（gr4j, xaj等）
- ✅ 提取流域ID
- ✅ 解析时间段
- ✅ 识别缺失信息
- ✅ 给出合理的置信度分数

### 示例输出

```
[TEST] Test 1: Basic IntentAgent Functionality
==================================================

[TEST] Query: 率定GR4J模型，流域01013500

[PASS] Success!
   Intent: calibration
   Model: gr4j
   Basin: 01013500
   Confidence: 0.90
```

### 故障排除

**问题1：Ollama 连接失败**
```
Error: Connection refused to localhost:11434
```
**解决**：
```bash
# 启动 Ollama 服务
ollama serve
```

**问题2：模型未找到**
```
Error: model 'qwen3:8b' not found
```
**解决**：
```bash
# 下载模型
ollama pull qwen3:8b
```

**问题3：通义千问API失败**
```
Error: Invalid API key
```
**解决**：
- 检查 API Key 是否正确
- 确认API账户有足够余额

## 测试用例说明

### 测试用例 1
```python
Query: "率定GR4J模型，流域01013500，2000到2010年"
Expected:
  - intent: calibration
  - model_name: gr4j
  - basin_id: 01013500
  - has_time_period: True
```

### 测试用例 2
```python
Query: "I want to calibrate XAJ model for basin camels_11532500 from 2005 to 2015"
Expected:
  - intent: calibration
  - model_name: xaj
  - basin_id: camels_11532500
  - has_time_period: True
```

### 测试用例 3
```python
Query: "帮我优化一下水文模型参数"
Expected:
  - intent: calibration
  - model_name: None (missing)
  - basin_id: None (missing)
  - has_missing_info: True
```

... （更多测试用例详见代码）

## 性能基准

在 qwen3:8b (Ollama) 上的预期性能：
- 单个查询响应时间：2-5秒
- 意图识别准确率：>90%
- 实体提取准确率：>85%
- 整体测试通过率：>90%

## 下一步

测试通过后，可以继续开发：
1. ConfigAgent - 配置生成智能体
2. RunnerAgent - 执行监控智能体
3. DeveloperAgent - 结果分析智能体
