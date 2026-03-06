# 开发指南

## 项目结构

```
hydroclaw/
├── agent.py              # Agentic Loop 核心（~70 行关键逻辑）
├── llm.py                # LLM 客户端（Function Calling + Prompt 降级）
├── config.py             # 配置加载 + hydromodel 配置构建
├── memory.py             # 会话记忆（JSONL + MEMORY.md）
├── cli.py                # CLI 入口（交互模式 + 单次查询）
├── __main__.py           # python -m hydroclaw 入口
├── tools/                # 工具函数（自动发现）
│   ├── __init__.py       # 自动发现引擎 + Schema 生成
│   ├── calibrate.py      # 传统算法率定
│   ├── evaluate.py       # 模型评估
│   ├── validate.py       # 流域验证
│   ├── simulate.py       # 模型模拟
│   ├── visualize.py      # 可视化
│   ├── llm_calibrate.py  # LLM 智能率定
│   ├── generate_code.py  # 代码生成
│   ├── run_code.py       # 代码执行
│   └── create_tool.py    # 元工具：自动创建新工具
├── skills/               # LLM 工作流指引（Markdown）
│   ├── system.md         # 系统人设
│   ├── calibration.md    # 标准率定
│   ├── iterative.md      # 迭代优化
│   ├── comparison.md     # 多模型对比
│   ├── batch.md          # 批量处理
│   └── analysis.md       # 自定义分析
└── utils/                # 工具函数
    ├── basin_validator.py
    └── result_parser.py
```

## 添加新工具

### 方式 1: 手动添加（开发者）

在 `hydroclaw/tools/` 下创建 `.py` 文件：

```python
"""
Author: Your Name
Date: 2026-XX-XX
Description: Brief description.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def my_tool(
    basin_ids: list[str],
    param_a: str = "default",
    param_b: int | None = None,
    _workspace: Path | None = None,
    _cfg: dict | None = None,
) -> dict:
    """One-line description of what this tool does.

    Args:
        basin_ids: CAMELS basin ID list
        param_a: Description of param_a
        param_b: Optional integer parameter

    Returns:
        {"result": ..., "success": bool}
    """
    try:
        # 实现逻辑
        return {"result": "done", "success": True}
    except Exception as e:
        logger.error(f"my_tool failed: {e}", exc_info=True)
        return {"error": str(e), "success": False}
```

**规范要求**：

1. 一个文件一个公开函数（工具入口）
2. 辅助函数以 `_` 开头
3. 必须有完整的类型注解和 Google-style docstring
4. 返回 `dict`，包含 `success` 键
5. 错误处理：捕获异常，返回 `{"error": "...", "success": False}`
6. 外部包在函数体内 lazy import

### 方式 2: LLM 自动创建（运行时）

用户在对话中请求，LLM 调用 `create_tool` 自动生成。

### 内部参数约定

| 参数 | 注入值 | 使用场景 |
|---|---|---|
| `_workspace` | 当前工作目录 Path | 文件读写 |
| `_cfg` | 全局配置 dict | 读取 API Key、默认参数 |
| `_llm` | LLMClient 实例 | 需要 LLM 推理的工具 |

## 添加新 Skill

Skill 是 Markdown 文件，用自然语言告诉 LLM 在特定场景下该怎么做。

### 创建 Skill 文件

在 `hydroclaw/skills/` 下创建 `.md` 文件：

```markdown
## 我的场景工作流

当用户要求 XXX 时使用此工作流。

### 步骤

1. 首先调用 `validate_basin` 验证流域
2. 然后调用 `my_tool` 执行分析
3. 最后用中文输出报告

### 注意事项

- 提醒 LLM 注意的关键点
- 错误处理建议
```

### 注册 Skill

在 `agent.py` 的 `_match_skill` 方法中添加关键词映射：

```python
skill_map = {
    ...
    "my_skill.md": ["我的关键词", "my_keyword"],
}
```

## 代码规范

### 文件头

```python
"""
Author: HydroClaw Team
Date: YYYY-MM-DD
Description: Brief description.
"""
```

### 日志

```python
import logging
logger = logging.getLogger(__name__)

logger.info("Important info")
logger.debug("Debug details")
logger.warning("Warning message")
logger.error("Error message", exc_info=True)
```

### 错误处理

工具函数：返回错误 dict，不要 raise

```python
# 正确
return {"error": f"Failed: {e}", "success": False}

# 错误
raise RuntimeError(f"Failed: {e}")
```

### 类型注解

所有公开函数必须有完整类型注解（工具发现依赖此生成 Schema）。

```python
# 正确
def my_func(name: str, count: int = 10) -> dict:

# 错误（缺少类型注解，Schema 生成为 "string"）
def my_func(name, count=10):
```

## 测试

### 工具发现测试

```python
from hydroclaw.tools import reload_tools, get_tool_schemas

tools = reload_tools()
print(f"Tools: {sorted(tools.keys())}")

schemas = get_tool_schemas()
for s in schemas:
    print(f"  {s['function']['name']}: {len(s['function']['parameters']['properties'])} params")
```

### 单工具测试

```python
from hydroclaw.tools.validate import validate_basin
result = validate_basin(basin_ids=["12025000"])
print(result)
```

### 完整流程测试

```bash
python -m hydroclaw "验证流域12025000" -v
```

## 调试

### 启用详细日志

```bash
python -m hydroclaw -v
```

### 查看会话记录

```bash
# 查看最近的会话
ls sessions/

# 查看工具调用详情
cat sessions/20260209_143000.jsonl
```

### 常见问题

**工具未被发现**：
- 检查函数名是否以 `_` 开头（会被跳过）
- 检查文件名是否以 `_` 开头（会被跳过）
- 检查 import 是否有错误（`python -c "from hydroclaw.tools.xxx import yyy"`）

**Schema 类型不对**：
- 确保使用了类型注解
- `list[str]` → `"array"`，`dict` → `"object"`
- `X | None` 会自动展开为 `X` 的类型
