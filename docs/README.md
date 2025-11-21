# HydroAgent 文档中心

## 📚 文档结构

### 测试文档 (Test Documentation)
- [IntentAgent 测试说明](tests/test_intent_agent.md) - 自然语言理解智能体测试指南

### 配置文档 (Configuration Documentation)
- [配置文件示例](../configs/example_config.yaml) - hydromodel 标准配置格式

### 项目文档 (Project Documentation)
- [CLAUDE.md](../CLAUDE.md) - Claude Code 项目指南
- [HydroAgent 设计规划](../HydroAgent.md) - 多智能体系统设计文档

## 📖 快速导航

### 开发者指南

#### 1. 环境配置
```bash
# 安装依赖
uv sync

# 激活虚拟环境
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac
```

#### 2. 配置 LLM
**选项 A: Ollama (本地)**
```bash
ollama serve
ollama pull qwen3:8b
```

**选项 B: 通义千问 API (云端)**
- 配置 API Key 在环境变量或测试文件中

#### 3. 运行测试
```bash
# IntentAgent 测试
python test/test_intent_agent.py
```

### 配置格式说明

HydroAgent 使用 hydromodel 的 **简化配置格式** (Simplified Config Format)：

```yaml
data:
  dataset: "camels_us"
  basin_ids: ["01013500"]
  train_period: ["2000-01-01", "2010-12-31"]
  test_period: ["2011-01-01", "2015-12-31"]
  warmup_length: 365

model:
  name: "gr4j"

training:
  algorithm: "SCE_UA"
  loss: "RMSE"
  SCE_UA:
    rep: 5000
    ngs: 1000

evaluation:
  metrics: ["NSE", "RMSE", "KGE"]
```

该格式会被 `load_simplified_config()` 转换为统一格式。

详见：[example_config.yaml](../configs/example_config.yaml)

## 🧪 测试套件

### IntentAgent 测试
- **文件**: `test/test_intent_agent.py`
- **文档**: [IntentAgent 测试说明](tests/test_intent_agent.md)
- **覆盖范围**:
  - ✅ 中文查询解析
  - ✅ 英文查询解析
  - ✅ 混合语言查询
  - ✅ 意图分类 (calibration/evaluation/simulation/extension)
  - ✅ 实体提取 (model_name, basin_id, time_period)
  - ✅ 错误处理

## 🏗️ 项目架构

```
HydroAgent/
├── hydroagent/              # 核心包
│   ├── core/               # 基础类 (BaseAgent, LLMInterface)
│   ├── agents/             # 智能体层
│   │   ├── orchestrator.py       # 中央编排器
│   │   ├── intent_agent.py       # 意图智能体 ✅
│   │   ├── config_agent.py       # 配置智能体
│   │   ├── runner_agent.py       # 执行智能体
│   │   └── developer_agent.py    # 开发者智能体
│   ├── utils/              # 工具层
│   │   ├── schema_validator.py   # 配置校验
│   │   ├── result_parser.py      # 结果解析
│   │   ├── error_handler.py      # 错误处理
│   │   └── code_sandbox.py       # 代码沙箱
│   └── resources/          # 资源层
│       ├── schema_definition.json
│       ├── api_signatures.yaml
│       └── few_shot_prompts.py
├── test/                   # 测试代码
│   └── test_intent_agent.py
├── docs/                   # 文档
│   ├── README.md          # 本文件
│   └── tests/             # 测试文档
└── configs/                # 配置示例
    └── example_config.yaml
```

## 🎯 开发路线图

### Phase 1: 意图理解 ✅ (已完成)
- ✅ IntentAgent 实现
- ✅ 自然语言查询解析
- ✅ 实体提取和验证
- ✅ 完整测试套件

### Phase 2: 配置生成 (进行中)
- ConfigAgent 实现
- YAML 配置生成
- 参数范围调整
- Schema 校验集成

### Phase 3: 执行与监控
- RunnerAgent 实现
- hydromodel 调用封装
- 执行监控和日志
- 错误捕获和反馈

### Phase 4: 结果分析
- DeveloperAgent 实现
- 边界效应检测
- 性能指标分析
- 代码生成功能

### Phase 5: 系统集成
- Orchestrator 完整编排逻辑
- 多轮对话支持
- 自适应优化 (Experiment 2)
- 端到端测试

## 📊 性能基准

### IntentAgent (qwen3:8b)
- 单查询响应时间: 2-5秒
- 意图识别准确率: >90%
- 实体提取准确率: >85%
- 测试通过率: >90%

## 🔗 相关链接

- [hydromodel](https://github.com/OuyangWenyu/hydromodel) - 底层水文模型库
- [Claude Code](https://claude.ai/code) - AI 编程助手
- [Ollama](https://ollama.ai/) - 本地 LLM 运行环境

## 📝 更新日志

### 2025-01-20
- ✅ 完成 IntentAgent 实现和测试
- ✅ 更新配置格式为 hydromodel 标准格式
- ✅ 创建完整测试套件
- ✅ 重组文档结构 (docs/ 和 test/ 分离)

---

**最后更新**: 2025-01-20
**维护者**: zhuanglaihong & Claude
