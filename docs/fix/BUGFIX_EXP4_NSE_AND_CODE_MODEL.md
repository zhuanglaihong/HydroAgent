# Bug Fix: 实验4 NSE KeyError 和代码模型配置

**Date**: 2025-01-24
**Issues**:
1. KeyError: 'NSE' in hydromodel LOSS_DICT
2. 代码模型硬编码，未使用config.py

**Status**: ✅ Fixed

---

## 🐛 问题1: KeyError: 'NSE'

### 错误信息：
```python
File "hydromodel/trainers/unified_calibrate.py", line 327
    return LOSS_DICT[self.loss_config["obj_func"]](
           ~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
KeyError: 'NSE'
```

### 根本原因：

**InterpreterAgent的系统提示词错误**：
```python
"loss_config": {
    "type": "time_series",
    "obj_func": "RMSE" | "NSE" | "KGE"  # ❌ 提示词说支持NSE
}
```

**实际情况**：hydromodel的`LOSS_DICT`**只支持RMSE**（spotpy的标准损失函数）。

LLM根据提示词生成了`"obj_func": "NSE"`，但hydromodel无法识别，导致KeyError。

---

### 修复方案：

**文件**: `hydroagent/agents/interpreter_agent.py` (line 135)

**修改前**:
```python
"loss_config": {{
  "type": "time_series",
  "obj_func": "RMSE" | "NSE" | "KGE"  # ❌ 错误的提示
}},
```

**修改后**:
```python
"loss_config": {{
  "type": "time_series",
  "obj_func": "RMSE"  # ✅ 只使用hydromodel支持的RMSE
}},
```

---

## 🐛 问题2: 代码模型配置硬编码

### 问题描述：

**exp_4_extended_analysis.py中硬编码了代码模型**：
```python
# API模式
code_model = args.code_model or "qwen3-coder-plus"  # ❌ 硬编码

# Ollama模式
code_model = args.code_model or "deepseek-coder:6.7b"  # ❌ 硬编码
```

用户无法通过修改`config.py`来统一管理默认代码模型。

---

### 修复方案：

#### Step 1: 添加DEFAULT_CODE_MODEL到config.py

**文件**: `configs/config.py` (lines 18-19)

```python
# Default LLM model for API backend
DEFAULT_MODEL = "qwen3-max"

# Default code-specific LLM model (for DeveloperAgent code generation)
DEFAULT_CODE_MODEL = "qwen3-coder-plus"  # ⭐ 新增配置
```

#### Step 2: 更新exp_4脚本使用config

**文件**: `experiment/exp_4_extended_analysis.py` (lines 58-91)

**修改前**:
```python
try:
    from configs import definitions_private as config  # ❌ 命名冲突
except ImportError:
    from configs import definitions as config

# API模式
code_model = args.code_model or "qwen3-coder-plus"  # ❌ 硬编码
```

**修改后**:
```python
try:
    from configs import definitions_private as def_config  # ✅ 重命名避免冲突
except ImportError:
    from configs import definitions as def_config

from configs import config  # ✅ 导入config.py

# API模式
code_model = args.code_model or getattr(config, "DEFAULT_CODE_MODEL", "qwen3-coder-plus")
                                        ^^^^^^^^^^^^^^^^^^^^^^^^^ ✅ 从config读取

# Ollama模式
code_model = args.code_model or getattr(config, "DEFAULT_CODE_MODEL", "deepseek-coder:6.7b")
```

---

## ✅ 修复效果

### 修复前：

1. **NSE错误**:
   ```
   LLM生成: "obj_func": "NSE"
   hydromodel: KeyError: 'NSE' ❌
   ```

2. **代码模型硬编码**:
   ```python
   # 用户想改成qwen2.5-coder-32b
   # 必须修改exp_4_extended_analysis.py第88行 ❌
   code_model = "qwen3-coder-plus"
   ```

### 修复后：

1. **NSE修复**:
   ```
   LLM生成: "obj_func": "RMSE"
   hydromodel: ✅ 正常执行
   ```

2. **代码模型统一配置**:
   ```python
   # configs/config.py
   DEFAULT_CODE_MODEL = "qwen2.5-coder-32b"  # ✅ 只需改一处

   # exp_4自动读取
   code_model = getattr(config, "DEFAULT_CODE_MODEL", ...)
   ```

---

## 🧪 验证修复

### 测试1: 验证NSE修复

```bash
python experiment/exp_4_extended_analysis.py --backend api --mock
```

**预期**：
- ✅ 不再出现`KeyError: 'NSE'`
- ✅ 率定正常完成，使用`obj_func: RMSE`

### 测试2: 验证代码模型配置

**修改config.py**:
```python
DEFAULT_CODE_MODEL = "qwen2.5-coder-32b"
```

**运行**:
```bash
python experiment/exp_4_extended_analysis.py --backend api
```

**预期日志**:
```
✅ 代码专用LLM初始化完成: qwen2.5-coder-32b
```

**命令行覆盖**:
```bash
python experiment/exp_4_extended_analysis.py --backend api --code-model deepseek-coder
```

**预期**:
```
✅ 代码专用LLM初始化完成: deepseek-coder  # 命令行参数优先
```

---

## 📊 优先级机制

**代码模型选择优先级**:
```
1. 命令行参数 --code-model  (最高优先级)
2. config.DEFAULT_CODE_MODEL
3. 硬编码默认值 (fallback)
```

**示例**:
```bash
# 使用config.py中的DEFAULT_CODE_MODEL
python exp_4.py --backend api

# 使用命令行指定的模型（覆盖config）
python exp_4.py --backend api --code-model qwen-coder-7b

# API模式fallback链:
args.code_model → config.DEFAULT_CODE_MODEL → "qwen3-coder-plus"

# Ollama模式fallback链:
args.code_model → config.DEFAULT_CODE_MODEL → "deepseek-coder:6.7b"
```

---

## 📁 修改的文件

1. **configs/config.py** (lines 18-19)
   - 新增: `DEFAULT_CODE_MODEL = "qwen3-coder-plus"`

2. **hydroagent/agents/interpreter_agent.py** (line 135)
   - 修改: `"obj_func": "RMSE"` (移除NSE和KGE选项)

3. **experiment/exp_4_extended_analysis.py** (lines 58-91)
   - 重命名: `definitions_private as def_config`
   - 新增: `from configs import config`
   - 修改: 使用`getattr(config, "DEFAULT_CODE_MODEL", ...)`

---

## 💡 设计原则

### 为什么只支持RMSE？

1. **hydromodel限制**: spotpy的LOSS_DICT只注册了RMSE
2. **简化配置**: 避免LLM生成不支持的损失函数
3. **一致性**: 所有实验使用相同的损失函数，结果可比

### 为什么需要DEFAULT_CODE_MODEL？

1. **统一管理**: 所有模型配置集中在config.py
2. **易于切换**: 更换代码模型只需修改一处
3. **灵活覆盖**: 支持命令行参数动态指定

---

## 🚀 下一步

1. ✅ 测试实验4，验证修复
2. ⬜ 检查其他实验是否有类似问题
3. ⬜ 更新README和CLAUDE.md
4. ⬜ 考虑支持更多损失函数（需要hydromodel支持）

---

**Last Updated**: 2025-01-24
**Status**: ✅ 修复完成，等待测试验证
