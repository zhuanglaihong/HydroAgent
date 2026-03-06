# CLAUDE.md

> 项目：HydroClaw（从 HydroAgent 重建）| 状态：主动开发中 | 日期：2026-03-06

## 项目背景

之前做了一个多 Agent 水文智能体系统（HydroAgent，5个 Agent + Orchestrator 状态机），过度工程化、难以维护。
受 OpenClaw 启发，重建为轻量 Agentic Loop 架构，命名 **HydroClaw**，以此写一篇论文。

## 最终目标

用自然语言驱动的 LLM Agentic Loop，让水文学者一句话完成完整的模型率定-评估-分析流程。
支持批量任务（多模型×多流域），具备跨会话记忆和动态工具扩展能力。

---

## 当前架构（已实现）

### 核心包：`hydroclaw/`

```
hydroclaw/
├── agent.py          # Agentic Loop 核心（ReAct 模式）
├── llm.py            # LLM 客户端（Function Calling + Prompt fallback）
├── memory.py         # 记忆系统（会话日志 + 跨会话 MEMORY.md）
├── config.py         # 配置加载 + hydromodel config 构建
├── cli.py            # CLI 入口
├── __main__.py       # python -m hydroclaw 入口
├── tools/            # 工具集（自动发现）
│   ├── __init__.py       # 自动注册 + schema 生成
│   ├── calibrate.py      # 标准率定（SCE-UA/GA/scipy）
│   ├── llm_calibrate.py  # LLM 智能率定（参数范围迭代调整）★
│   ├── evaluate.py       # 模型评估
│   ├── simulate.py       # 模型模拟
│   ├── validate.py       # 流域数据验证
│   ├── visualize.py      # 可视化
│   ├── generate_code.py  # 代码生成
│   ├── run_code.py       # 代码执行
│   └── create_tool.py    # 动态工具生成（元工具）★
├── skills/           # 工作流指引（按查询关键词注入）
│   ├── system.md         # 系统基础 prompt
│   ├── calibration.md    # 标准率定流程
│   ├── llm_calibration.md # LLM 智能率定流程
│   ├── iterative.md      # 迭代优化
│   ├── comparison.md     # 多模型对比
│   ├── batch.md          # 批量任务
│   └── analysis.md       # 代码分析
└── knowledge/        # 结构化领域知识（按查询关键词注入）★
    ├── model_parameters.md  # 模型参数物理含义 + 典型范围
    └── calibration_guide.md # 率定策略 + 诊断经验
```

### 论文核心创新点对应代码

| 创新点 | 实现位置 | 状态 |
|--------|----------|------|
| 水文领域 Agentic Loop | `agent.py` | ✅ |
| 智能参数范围迭代调整 | `tools/llm_calibrate.py` | ✅ |
| 领域知识形式化注入 | `knowledge/` + `agent._load_domain_knowledge()` | ✅ |
| 动态工具自动生成 | `tools/create_tool.py` | ✅ |

---

## 开发进度

- ✅ Phase 1：修复参数范围（补全 gr5j/gr6j）、修正 skill 描述
- ✅ Phase 2：建立 `knowledge/` 结构化知识库，接入 agent 上下文
- 🔲 Phase 3：流域档案记忆（Memory 升级，basin-specific knowledge）
- 🔲 Phase 4：实验脚本（论文实验场景）

## 关键配置

LLM：Qwen/DeepSeek API（`configs/definitions_private.py` 中的 `OPENAI_API_KEY`）
数据：CAMELS-US（`DATASET_DIR`）
结果：`RESULT_DIR`

## 运行方式

```bash
python -m hydroclaw "率定GR4J模型，流域12025000"
python -m hydroclaw  # 交互模式
```
