# 开发指南

## 项目结构

```
HydroAgent/
├── hydroclaw/                    # 核心包
│   ├── agent.py                  # Agentic Loop（ReAct 核心）
│   ├── llm.py                    # LLM 客户端（Function Calling + Prompt 降级）
│   ├── memory.py                 # 记忆系统（会话日志 + 流域档案 + MEMORY.md）
│   ├── config.py                 # 配置加载 + hydromodel 配置构建
│   ├── skill_registry.py         # Skill 自动扫描与匹配
│   ├── cli.py                    # CLI 入口（交互模式 + 单次查询）
│   ├── ui.py                     # Rich 终端 UI
│   ├── setup_wizard.py           # 首次运行配置向导
│   ├── __main__.py               # python -m hydroclaw 入口
│   │
│   ├── tools/                    # 独立工具（不属于特定 Skill）
│   │   ├── __init__.py           # 工具发现引擎 + Schema 生成
│   │   ├── validate.py           # validate_basin()
│   │   ├── simulate.py           # run_simulation()
│   │   └── create_skill.py       # create_skill()（元工具）
│   │
│   ├── skills/                   # Skill 包（工作流指引 + 工具实现）
│   │   ├── system.md             # 系统基础 prompt
│   │   ├── calibration/
│   │   │   ├── skill.md          # 率定工作流指引
│   │   │   └── calibrate.py      # calibrate_model()
│   │   ├── evaluation/
│   │   │   ├── skill.md
│   │   │   └── evaluate.py       # evaluate_model()
│   │   ├── llm_calibration/
│   │   │   ├── skill.md
│   │   │   └── llm_calibrate.py  # llm_calibrate()
│   │   ├── batch_calibration/
│   │   │   ├── skill.md
│   │   │   └── batch_calibrate.py
│   │   ├── code_analysis/
│   │   │   ├── skill.md
│   │   │   ├── generate_code.py  # generate_code()
│   │   │   └── run_code.py       # run_code()
│   │   ├── model_comparison/
│   │   │   ├── skill.md
│   │   │   └── compare_models.py
│   │   └── visualization/
│   │       ├── skill.md
│   │       └── visualize.py      # visualize()
│   │
│   ├── knowledge/                # 结构化领域知识（按需注入）
│   │   ├── model_parameters.md   # 参数物理含义 + 典型范围
│   │   └── calibration_guide.md  # 率定策略 + 诊断经验
│   │
│   └── utils/
│       ├── basin_validator.py
│       └── result_parser.py      # 解析 hydromodel 输出
│
├── configs/
│   ├── config.py                 # 用户自定义参数（算法、时段、目标函数）
│   ├── definitions_private.py    # 私密配置（API Key、路径，已 gitignore）
│   └── example_definitions_private.py
│
├── scripts/                      # 论文实验脚本
│   ├── exp1_standard_calibration.py
│   ├── exp2_llm_calibration.py
│   ├── exp3_scenario_robustness.py
│   ├── exp4_create_skill.py
│   ├── exp5_memory.py
│   ├── exp6_knowledge_ablation.py
│   ├── plot_paper_figures.py
│   └── README.md
│
├── docs/                         # 项目文档
├── results/                      # 率定结果（gitignore）
├── logs/                         # 运行日志（gitignore）
└── sessions/                     # 会话 JSONL 记录（gitignore）
```

## 添加新工具

### 方式 1: 独立工具（tools/ 目录）

适用于通用的、不属于特定工作流的工具：

```python
# hydroclaw/tools/my_tool.py
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def my_tool(
    basin_ids: list[str],
    param_a: str = "default",
    _workspace: Path | None = None,
    _cfg: dict | None = None,
) -> dict:
    """One-line description for LLM to understand this tool.

    Args:
        basin_ids: CAMELS basin ID list
        param_a: Description of param_a

    Returns:
        {"result": ..., "success": bool}
    """
    try:
        return {"result": "done", "success": True}
    except Exception as e:
        logger.error(f"my_tool failed: {e}", exc_info=True)
        return {"error": str(e), "success": False}
```

### 方式 2: 创建新 Skill（skills/ 目录）

适用于有明确工作流场景的功能，包含指引文档 + 工具实现：

```
hydroclaw/skills/my_skill/
├── skill.md      # 工作流指引，LLM 在匹配关键词时读取
└── my_tool.py    # 工具实现，自动发现注册
```

`skill.md` 头部格式：

```markdown
---
keywords: [关键词1, 关键词2, keyword3]
---

## My Skill 工作流

当用户需要 XXX 时使用此工作流。

### 步骤
1. 调用 `validate_basin` 验证流域
2. 调用 `my_tool` 执行分析
3. 输出结果摘要
```

### 内部参数约定

| 参数 | 注入值 | 使用场景 |
|------|--------|---------|
| `_workspace` | 当前工作目录 Path | 文件读写 |
| `_cfg` | 全局配置 dict | API Key、默认参数 |
| `_llm` | LLMClient 实例 | 需要调用 LLM 的工具 |

## 代码规范

### 工具函数规范

1. 每个文件一个公开入口函数（辅助函数以 `_` 开头）
2. 必须有完整类型注解（工具发现依赖此生成 Schema）
3. 必须有 Google-style docstring（Args + Returns）
4. 返回 `dict`，包含 `success` 键
5. 捕获异常返回 `{"error": "...", "success": False}`，不要 raise
6. 外部包在函数体内 lazy import（避免启动时报 ImportError）

```python
# 正确：lazy import
def my_tool(...):
    try:
        import spotpy
        ...
    except ImportError:
        return {"error": "spotpy not installed", "success": False}
```

### 日志规范

```python
import logging
logger = logging.getLogger(__name__)

logger.info("Normal operation info")
logger.warning("Something unexpected but recoverable")
logger.error("Error occurred", exc_info=True)   # exc_info=True 会附带堆栈
```

### 类型注解

所有公开函数必须完整注解（Schema 生成依赖此）：

```python
# 正确
def my_func(name: str, count: int = 10, ids: list[str] | None = None) -> dict:

# 错误（Schema 类型推断失败）
def my_func(name, count=10):
```

## 测试

### 快速验证工具发现

```python
from hydroclaw.tools import reload_tools, get_tool_schemas

tools = reload_tools()
print("Registered tools:", sorted(tools.keys()))

schemas = get_tool_schemas()
for s in schemas:
    print(f"  {s['function']['name']}: {list(s['function']['parameters']['properties'].keys())}")
```

### 单工具测试

```python
from hydroclaw.tools.validate import validate_basin
result = validate_basin(basin_ids=["12025000", "99999999"])
print(result)
# {"valid_basins": ["12025000"], "invalid_basins": ["99999999"], "valid": true}
```

### 完整流程测试

```bash
python -m hydroclaw "验证流域12025000是否存在" -v
```

`-v` 显示完整工具调用日志。

## 调试

### 查看当前工具注册状态

```bash
python -c "from hydroclaw.tools import reload_tools; t = reload_tools(); print(sorted(t.keys()))"
```

### 查看会话记录

```bash
# 最近的会话
ls sessions/

# 工具调用详情（JSONL 格式，每行一条记录）
python -c "
import json
for line in open('sessions/最新会话.jsonl'):
    print(json.loads(line))
"
```

### 常见问题

**工具未被发现**：
- 函数名或文件名不能以 `_` 开头
- 检查 import 是否报错：`python -c "from hydroclaw.skills.xxx.yyy import zzz"`

**Schema 参数类型错误**：
- `list[str]` -> `"array"`，`dict` -> `"object"`，`str | None` -> `"string"`
- 未注解的参数会被推断为 `"string"`

**Skill 未匹配**：
- 检查 `skill.md` 头部 `keywords` 字段是否包含查询中的关键词
- 运行 `python -c "from hydroclaw.skill_registry import SkillRegistry; r = SkillRegistry(); print(r.list_skills())"`
