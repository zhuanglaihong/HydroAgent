# HydroAgent: 智能水文建模多智能体系统

<div align="center">

![HydroAgent Logo](https://img.shields.io/badge/HydroAgent-v4.0-blue?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTEyIDJMMTMuMDkgOC4yNkwyMCA5TDEzLjA5IDE1Ljc0TDEyIDIyTDEwLjkxIDE1Ljc0TDQgOUwxMC45MSA4LjI2TDEyIDJaIiBmaWxsPSIjMDA3OEQ0Ii8+Cjwvc3ZnPgo=)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg?style=for-the-badge&logo=python)](https://python.org)
[![HydroModel](https://img.shields.io/badge/HydroModel-v0.3+-orange.svg?style=for-the-badge)](https://github.com/OuyangWenyu/hydromodel)

**基于多智能体协作的智能水文建模解决方案**

[🚀 快速开始](#-快速开始) • [🏗️ 系统架构](#️-系统架构) • [🧪 实验系统](#-实验系统) • [📖 开发文档](#-开发文档)

</div>



---

## 🌟 项目概览

HydroAgent 是一个基于多智能体协作的智能水文建模系统，通过自然语言理解、自动配置生成、模型执行和结果分析，实现从用户意图到水文模拟的端到端自动化。系统采用分层决策架构（战略→战术→执行），支持参数自适应优化、代码自动生成等高级功能。

### 🎯 核心价值

- **🎤 自然语言交互**: 支持中英文对话式任务描述，降低水文建模技术门槛
- **🧠 智能决策**: 三层决策架构（Intent→TaskPlanner→Interpreter），自动规划复杂任务
- **🔄 端到端自动化**: 从意图识别到结果分析全流程自动化，无需手动编写配置
- **🔧 自适应优化**: 参数边界检测与范围动态调整，提高率定成功率
- **💻 代码生成**: 超出 hydromodel 原生功能时自动生成 Python 脚本
- **🔌 多后端支持**: 灵活切换 API 后端和本地模型，兼顾性能与成本

### 📊 技术指标

| 指标 | 规格 | 说明 |
|------|------|------|
| **支持模型** | 6+ 水文模型 | GR1Y, GR2M, GR4J, GR5J, GR6J, XAJ |
| **支持算法** | 3+ 优化算法 | SCE-UA, scipy, GA |
| **智能体数量** | 5 个专用智能体 | Intent, TaskPlanner, Interpreter, Runner, Developer |
| **中文理解** | 95%+ 准确率 | 支持"迭代500轮"等自然表达 |
| **配置生成** | 100% 自动化 | 无需手动编写 hydromodel 配置 |
| **代码生成** | 双 LLM 架构 | 通用模型分析 + 代码专用模型生成 |
| **历史案例** | 50 条自动记忆 | Prompt Pool 自动学习成功经验 |

---

## 🚀 快速开始

### 环境要求

```bash
# 系统要求
Python >= 3.11
内存 >= 8GB (推荐 16GB+)
存储 >= 10GB (CAMELS 数据集)
```

### 一键安装

#### 使用 uv（推荐）
```bash
# 克隆仓库
git clone https://github.com/your-org/HydroAgent.git
cd HydroAgent

# 安装 uv 包管理器
pip install uv

# 同步依赖
uv sync

# 激活虚拟环境
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS
```

#### 验证安装
```bash
python -c "import hydromodel; print('✅ hydromodel 安装成功!')"
python -c "from hydroagent.agents.intent_agent import IntentAgent; print('✅ HydroAgent 安装成功!')"
```

### ⚙️ 配置说明

#### 📄 API 后端配置（推荐）

1. 复制配置模板：
```bash
cp configs/example_definitions_private.py configs/definitions_private.py
```

2. 编辑 `configs/definitions_private.py`：
```python
# API 配置（通义千问）
OPENAI_API_KEY = "sk-your-qwen-api-key"
OPENAI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 本地路径
PROJECT_DIR = r"D:\your\path\to\HydroAgent"
DATASET_DIR = r"D:\your\path\to\camels_data"
RESULT_DIR = r"D:\your\path\to\results"
```

**获取 API Key**:
- 阿里云通义千问: https://dashscope.aliyuncs.com/
- 支持模型: `qwen-turbo`, `qwen-plus`, `qwen-coder-turbo`（代码生成）

#### 🐋 Ollama 本地模型配置

```bash
# 安装 Ollama
# Windows: https://ollama.ai/download
# Linux: curl -fsSL https://ollama.ai/install.sh | sh

# 拉取模型
ollama pull qwen3:8b              # 通用分析模型
ollama pull deepseek-coder:6.7b   # 代码生成专用模型
```

配置 `definitions_private.py`:
```python
OLLAMA_BASE_URL = "http://localhost:11434"
```

### 30秒体验

```python
# 方式1: 命令行交互模式
python scripts/run_developer_agent_pipeline.py --backend api

# 方式2: 单次查询模式
python scripts/run_developer_agent_pipeline.py --backend api \
    "率定GR4J模型，流域01013500，使用SCE-UA算法，迭代500轮"

# 方式3: 使用 Ollama 本地模型
python scripts/run_developer_agent_pipeline.py --backend ollama \
    "率定GR4J模型，流域01013500"
```

**示例对话**:
```
🎤 用户: 率定GR4J模型，流域01013500，使用SCE-UA算法，迭代500轮

🧠 IntentAgent:
   ✅ 任务类型: CALIBRATION
   ✅ 模型: gr4j
   ✅ 流域: 01013500
   ✅ 算法: SCE_UA (rep=500)

📋 TaskPlanner:
   ✅ 拆解为 1 个子任务
   ✅ 生成执行提示词（含历史成功案例）

⚙️  InterpreterAgent:
   ✅ 生成 hydromodel 配置字典
   ✅ 训练期: 1985-10-01 ~ 1995-09-30
   ✅ 测试期: 2005-10-01 ~ 2014-09-30

🚀 RunnerAgent:
   SCE-UA Progress: 100%|███████████| 500/500 [02:15<00:00]
   ✅ 率定完成: NSE_train = 0.72
   ✅ 自动评估: NSE_test = 0.65

📊 DeveloperAgent:
   质量评估: 良好 (Good)
   最优参数: x1=0.77, x2=0.0002, x3=0.30, x4=0.70
   改进建议:
     1. 模型性能接近良好水平，可考虑延长训练期
     2. 建议在更多流域验证参数迁移性
     3. 可尝试增加迭代轮数到 800-1000 轮进一步优化
```

**输出文件** (位于 `results/session_xxx/`):
```
📄 calibration_results.json       # 率定结果和最优参数
📄 basins_metrics.csv              # 性能指标 (NSE, RMSE, etc.)
📄 01013500_GR4J_simulated.nc      # NetCDF 格式模拟结果
📊 analysis_report.txt             # 专家分析报告
```

---

## 🏗️ 系统架构

### 🔄 5-Agent 分层架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Orchestrator (编排器)                     │
│           统筹调度、会话管理、Checkpoint/Resume              │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
    │ 战略决策层   │  │ 战术规划层   │  │ 配置生成层   │
    └─────────────┘  └─────────────┘  └─────────────┘
         │                  │                  │
         ▼                  ▼                  ▼
  IntentAgent      TaskPlanner      InterpreterAgent
  意图识别         任务拆解           配置生成
  (LLM)           (LLM + Pool)        (LLM)
    "做什么"         "怎么做"          "具体参数"
         │                  │                  │
         └──────────────────┼──────────────────┘
                            ▼
              ┌─────────────────────────┐
              │      执行与分析层         │
              └─────────────────────────┘
                     │            │
                     ▼            ▼
              RunnerAgent   DeveloperAgent
              模型执行       结果分析+代码生成
              (Deterministic) (Dual-LLM)
                     │            │
                     └──────┬─────┘
                            ▼
                  📊 分析报告 + 结果文件
```

### 🧠 智能体职责分工

<table>
<tr>
<td width="50%">

#### 1️⃣ IntentAgent (意图智能体)
**角色**: 战略决策者

**输入**:
```
"率定GR4J模型，流域01013500，迭代500轮"
```

**输出**:
```json
{
  "task_type": "standard_calibration",
  "model_name": "gr4j",
  "basin_id": "01013500",
  "algorithm": "SCE_UA",
  "extra_params": {"rep": 500},
  "confidence": 0.95
}
```

**特点**:
- ✅ 中文关键词识别 ("迭代500轮" → `rep=500`)
- ✅ 算法参数 Schema 注入
- ✅ 支持模糊查询补全

---

#### 2️⃣ TaskPlanner (任务规划智能体)
**角色**: 战术规划者

**功能**:
- ✅ 多任务拆解（如：率定 → 边界检查 → 重新率定）
- ✅ 依赖关系管理
- ✅ Prompt Pool 历史案例检索

**示例**:
```
实验3: "如果参数收敛到边界，调整范围重新率定"
  ↓
Task 1: Phase1 率定
Task 2: 边界检查（依赖 Task 1）
Task 3: Phase2 重新率定（依赖 Task 2, 条件执行）
```

**Prompt Pool 工作机制**:
```python
# 1. 检索相似案例
similar_cases = prompt_pool.get_similar_cases(
    intent={"model": "gr4j", "algorithm": "SCE_UA"},
    limit=2
)

# 2. 增强提示词
enhanced_prompt = base_prompt + """
### 📚 历史成功案例
案例1: gr4j + SCE_UA (rep=500) → NSE=0.75
案例2: gr4j + DE (max_gen=100) → NSE=0.68
"""
```

</td>
<td width="50%">

#### 3️⃣ InterpreterAgent (配置智能体)
**角色**: 配置生成专家

**输入**: TaskPlanner 的子任务 + 提示词

**输出**: 完整的 hydromodel 配置字典
```python
{
  "data_cfgs": {
    "basin_ids": ["01013500"],
    "train_period": ["1985-10-01", "1995-09-30"],
    "test_period": ["2005-10-01", "2014-09-30"]
  },
  "model_cfgs": {"model_name": "gr4j"},
  "training_cfgs": {
    "algorithm": "SCE_UA",
    "algorithm_params": {"rep": 500, "ngs": 200}
  }
}
```

**特点**:
- ✅ 使用 `configs/config.py` 默认值
- ✅ 算法复杂度自适应（模型参数数量）
- ✅ 支持自定义数据路径

---

#### 4️⃣ RunnerAgent (执行智能体)
**角色**: 模型执行器

**模式**:
1. **Calibrate**: 参数率定
2. **Evaluate**: 性能评估
3. **Simulate**: 模拟预测
4. **Code Generation**: 代码生成（v4.0 新增）

**执行流程**:
```python
# 1. 率定
runner.calibrate(config) → best_params

# 2. 自动评估
runner.evaluate(config, best_params) → metrics

# 3. 结构化结果
{
  "best_params": {...},
  "metrics": {"NSE": 0.65, "RMSE": 1.45},
  "output_files": ["*.nc", "*.csv", "*.json"]
}
```

**输出过滤**:
- 终端只显示进度条
- 完整日志保存到 `logs/`

---

#### 5️⃣ DeveloperAgent (分析智能体)
**角色**: 结果分析专家 + 代码生成器

**双 LLM 架构**（v4.0）:
```
通用 LLM (qwen-turbo / qwen3:8b)
  → 结果分析、质量评估、建议生成

代码专用 LLM (qwen-coder-turbo / deepseek-coder:6.7b)
  → Python 脚本生成（FDC、径流系数等）
```

**分析报告示例**:
```
📊 质量评估: 良好 (Good)
   NSE=0.68 (阈值: 0.65)
   RMSE=1.45

🔧 最优参数: 4 个
   x1=0.77, x2=0.0002, x3=0.30, x4=0.70

💡 改进建议:
  1. 模型性能合理，接近良好水平
  2. 可考虑延长训练期或增加迭代轮数
  3. 建议在更多流域验证参数迁移性
```

**代码生成能力**:
- 径流系数计算
- 流量历时曲线 (FDC)
- 水量平衡分析
- 季节性分析

</td>
</tr>
</table>

### 🛠️ 核心技术栈

<table>
<tr>
<td width="33%">

**🧠 AI 框架**
- Claude 3.5 Sonnet (API)
- Qwen-Turbo / Qwen-Plus
- Qwen-Coder-Turbo (代码生成)
- Ollama (本地部署)

</td>
<td width="33%">

**💧 水文建模**
- hydromodel (核心模型库)
- hydrodataset (CAMELS 数据)
- hydroutils (工具函数)
- spotpy (优化算法)

</td>
<td width="33%">

**🗄️ 数据与存储**
- NetCDF4 / xarray
- GeoPandas / Shapely
- JSON / YAML
- Checkpoint Manager

</td>
</tr>
</table>

### ⚡ 核心特性

#### 1. Prompt Pool (提示词池)

**位置**: `hydroagent/core/prompt_pool.py`
**使用者**: TaskPlanner

**功能**:
```python
# 自动记忆成功案例
prompt_pool.add_history(
    task_type="calibration",
    intent={"model": "gr4j", "algorithm": "SCE_UA"},
    config={...},
    result={"NSE": 0.75},
    success=True
)

# 检索相似案例（简单规则匹配）
similar = prompt_pool.get_similar_cases(
    intent={"model": "gr4j", "algorithm": "SCE_UA"},
    limit=3
)
# 匹配规则: 模型名(+1.0) + 算法(+0.8) + 任务类型(+0.7) + 流域(+0.5)

# 生成增强提示词
enhanced = prompt_pool.generate_context_prompt(
    base_prompt="请生成配置...",
    intent=current_intent,
    error_log=previous_error  # 避免重复错误
)
```

**优势**:
- ✅ 零向量计算，无需嵌入模型
- ✅ 自动保存最近 50 条案例
- ✅ 失败案例也记录，用于错误避免

---

#### 2. Checkpoint/Resume (中断恢复)

**位置**: `hydroagent/core/checkpoint_manager.py`
**集成**: Orchestrator

**使用场景**:
```bash
# 启动长任务
python scripts/run_with_checkpoint.py \
  --query "批量率定20个流域" --backend api

# 中断 (Ctrl+C)
^C 检测到中断，保存 checkpoint...

# 恢复
python scripts/run_with_checkpoint.py \
  --resume results/session_xxx --backend api

# 输出
✅ 跳过已完成任务: task_1, task_2
🚀 从 task_3 继续执行...
```

**Checkpoint 内容**:
```json
{
  "intent": {...},
  "task_plan": {
    "subtasks": [
      {"task_id": "task_1", "status": "completed"},
      {"task_id": "task_2", "status": "completed"},
      {"task_id": "task_3", "status": "pending"}
    ]
  },
  "results": {...}
}
```

---

#### 3. 参数范围动态调整 (实验3)

**位置**: `hydroagent/utils/param_range_adjuster.py`

**算法**:
```python
# 1. 检测边界参数
boundary_params = check_boundary_convergence(
    best_params={"x1": 0.99, "x2": 0.002},
    param_ranges={"x1": [0.0, 1.0], "x2": [0.0, 0.01]},
    threshold=0.1  # 距离边界 < 10%
)
# → x1 收敛到上界 (0.99 vs 1.0)

# 2. 扩展范围
new_ranges = adjust_ranges(
    old_ranges={"x1": [0.0, 1.0]},
    best_params={"x1": 0.99},
    strategy="extend"  # 扩展 60%
)
# → x1: [0.0, 1.6]

# 3. 或缩小范围（围绕最优值）
new_ranges = adjust_ranges(
    old_ranges={"x1": [0.0, 1.6]},
    best_params={"x1": 0.95},
    strategy="shrink",
    scale=0.15  # 缩小到 15%
)
# → x1: [0.807, 1.093]
```

---

#### 4. 双 LLM 代码生成 (实验4)

**架构**:
```
用户查询: "率定完成后，计算径流系数并画FDC曲线"
    ↓
IntentAgent 识别: task_type = "extended_analysis"
    ↓
DeveloperAgent:
  - 分析任务: 通用 LLM (qwen-turbo)
  - 生成代码: 代码专用 LLM (qwen-coder-turbo)
    ↓
生成 2 个 Python 脚本:
  - generated_code/runoff_coefficient_analysis.py
  - generated_code/plot_fdc.py
```

**代码质量**:
- ✅ Type hints
- ✅ 详细注释
- ✅ 错误处理
- ✅ 中文字体配置（matplotlib）

---

## 🧪 实验系统

HydroAgent 提供了 8 个核心实验，验证系统各项功能：

### 实验1：基础功能验证

| 实验ID | 脚本文件 | 查询示例 | 验证目标 |
|-------|---------|---------|---------|
| **1A** | `exp_1a_standard.py` | "率定流域 01013500，使用 GR4J 模型..." | 标准流程，完整信息 |
| **1B** | `exp_1b_info_completion.py` | "帮我率定流域 01013500" | 缺省信息智能补全 |
| **1C** | `exp_1c_error_handling.py` | "率定流域 99999999" (错误ID) | 错误处理鲁棒性 |

### 实验2：稳定性与批量处理

| 实验ID | 脚本文件 | 查询示例 | 验证目标 |
|-------|---------|---------|---------|
| **2A** | `exp_2a_repeated_calibration.py` | "重复执行20次率定..." | 单流域稳定性（20次） |
| **2B** | `exp_2b_multi_basin.py` | "批量率定10个流域..." | 多流域性能对比 |
| **2C** | `exp_2c_multi_algorithm.py` | "分别使用 SCE-UA、PSO、GA..." | 多算法对比 |

### 实验3-4：高级功能

| 实验ID | 脚本文件 | 验证目标 |
|-------|---------|---------|
| **3** | `exp_3_iterative_optimization.py` | 参数自适应优化 |
| **4** | `exp_4_extended_analysis.py` | 代码生成与扩展分析 |


---

## 📖 开发文档

### 📂 项目结构

```
HydroAgent/
├── hydroagent/                 # 核心包
│   ├── core/                  # 基础设施
│   │   ├── base_agent.py      # BaseAgent 抽象类
│   │   ├── llm_interface.py   # LLM API 封装
│   │   ├── prompt_pool.py     # 提示词池
│   │   └── checkpoint_manager.py  # Checkpoint 系统
│   ├── agents/                # 5 个智能体
│   │   ├── intent_agent.py
│   │   ├── task_planner.py
│   │   ├── interpreter_agent.py
│   │   ├── runner_agent.py
│   │   ├── developer_agent.py
│   │   └── orchestrator.py    # 编排器
│   ├── utils/                 # 工具模块
│   │   ├── prompt_manager.py  # 动态提示词管理
│   │   ├── code_generator.py  # 代码生成工具
│   │   ├── param_range_adjuster.py  # 参数范围调整
│   │   └── ...
│   └── resources/             # 静态资源
│       ├── algorithm_params_schema.txt
│       ├── config_agent_prompt.txt
│       └── ...
├── configs/                   # 配置文件
│   ├── definitions.py         # 公共配置
│   ├── definitions_private.py # 私有配置（不入库）
│   ├── example_definitions_private.py  # 配置模板
│   └── config.py              # 全局参数
├── scripts/                   # 入口脚本
│   ├── run_developer_agent_pipeline.py  # 主入口
│   └── run_with_checkpoint.py  # Checkpoint 模式
├── experiment/                # 实验脚本
│   ├── base_experiment.py     # 实验基类
│   ├── exp_1_standard_calibration.py
│   ├── exp_3_iterative_optimization.py
│   └── ...
├── test/                      # 测试
└── docs/                      # 文档
    ├── ARCHITECTURE_FINAL.md  # 最终架构设计
    ├── CHECKPOINT_SYSTEM.md   # Checkpoint 文档
    └── v4.0_improvements_summary.md
```

### 🔧 开发规范

#### 文件头标准（必需）
```python
"""
Author: [Your Name]
Date: [Creation Date YYYY-MM-DD HH:MM:SS]
LastEditTime: [Last Edit YYYY-MM-DD HH:MM:SS]
LastEditors: [Editor Name]
Description: [Brief description of file purpose]
FilePath: /HydroAgent/path/to/file.py
Copyright (c) 2023-2025 HydroAgent. All rights reserved.
"""
```

#### 日志标准
```python
import logging
from pathlib import Path
from datetime import datetime

logs_dir = Path(__file__).parent.parent / "logs"
logs_dir.mkdir(exist_ok=True)

log_file = logs_dir / f"test_{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)
```

### 🎓 核心概念

#### 配置加载优先级
```
1. configs/definitions_private.py  (用户私有配置)
2. configs/definitions.py          (项目默认配置)
3. configs/config.py               (全局参数)
4. 环境变量
5. 硬编码默认值
```

#### 动态提示词公式
```
Final Prompt = Static Template
             + Schema Constraints
             + Dynamic Context
             + Iterative Feedback
             + Historical Cases (Prompt Pool)
```

---

## 📚 参考资源

### 🌐 相关项目
- **[hydromodel](https://github.com/OuyangWenyu/hydromodel)** - 核心水文模型库
- **[hydrodataset](https://github.com/OuyangWenyu/hydrodataset)** - CAMELS 数据管理

### 📖 技术文档
- **CLAUDE.md** - Claude Code 使用指南（项目级提示词）
- **docs/ARCHITECTURE_FINAL.md** - 完整系统架构设计
- **experiment/README.md** - 实验系统详细说明

### 🔗 在线资源
- **通义千问 API**: https://dashscope.aliyuncs.com/
- **Ollama 官网**: https://ollama.ai/
- **CAMELS 数据集**: https://ral.ucar.edu/solutions/products/camels

---

<div align="center">

**🌊 HydroAgent - 让水文建模更智能、更自动、更高效 🌊**


</div>
