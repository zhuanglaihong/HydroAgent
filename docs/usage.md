# 使用指南

## 首次使用前：配置密钥与路径

运行前必须先填写 `configs/private.py`（复制模板）：

```bash
cp configs/example_private.py configs/private.py
```

编辑 `configs/private.py`，填入必填项：

```python
OPENAI_API_KEY  = "sk-your-api-key"          # LLM API Key（必填）
OPENAI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"  # API 端点
DATASET_DIR     = r"D:\your\path\to\CAMELS_US"  # CAMELS-US 数据集路径（必填）
RESULT_DIR      = r"D:\your\path\to\results"    # 结果输出目录（必填）
```

> 该文件已加入 `.gitignore`，不会提交到仓库。

算法参数（可选）在 `configs/model_config.py` 中调整，如修改 SCE-UA 迭代次数或目标函数。

---

## 启动方式

```bash
# 交互模式（多轮对话）
python -m hydroclaw

# 单次查询
python -m hydroclaw "率定GR4J模型，流域12025000"

# 指定配置和工作目录
python -m hydroclaw -c my_config.json -w results/exp_A "率定GR4J模型，流域12025000"
```

| 参数 | 说明 |
|------|------|
| `query` | 查询内容，省略则进入交互模式 |
| `-c, --config` | JSON 配置文件路径 |
| `-w, --workspace` | 工作目录（结果、记忆隔离） |
| `-v, --verbose` | 显示完整工具调用日志 |

## 场景示例

### 1. 标准率定

```
You> 率定GR4J模型，流域12025000，SCE-UA算法
```

HydroClaw 自动执行：验证流域 -> 率定 -> 训练期评估 -> 测试期评估 -> 总结报告。

**指定更多参数**：

```
You> 率定XAJ模型，流域11532500，GA算法，种群大小50，训练期2000-2008，测试期2009-2014
```

### 2. LLM 智能率定

```
You> 智能率定GR4J模型，流域06043500，目标NSE 0.75
```

流程：
- Round 1：默认参数范围 -> SCE-UA 优化 -> LLM 分析参数边界情况
- Round 2：LLM 扩展触界参数范围 -> 重新率定
- 重复直到 NSE 达标或无法继续改善

适合参数容易触碰边界的半干旱/山区流域。

### 3. 多模型对比

```
You> 用GR4J和XAJ两个模型分别率定流域12025000，对比哪个更好
```

LLM 分别率定两个模型，比较 NSE/KGE 等指标，给出推荐意见。

### 4. 批量率定

```
You> 批量率定流域12025000、03439000、11532500，使用GR4J模型
```

LLM 逐流域执行率定和评估，最后汇总对比表格。

### 5. 参数边界诊断

```
You> 流域06043500的GR4J率定效果不好，参数可能碰到了边界，帮我检查一下
```

LLM 读取 llm_calibration Skill，自动检查参数距边界距离，决定是否需要扩展范围重新率定。

### 6. 仅评估（不重新率定）

```
You> 评估一下 results/gr4j_12025000 这个率定结果的测试期表现
```

直接调用 `evaluate_model`，不触发率定流程。

### 7. 自定义代码分析

```
You> 帮我计算流域12025000的月均径流变化曲线并输出图片
```

LLM 调用 `generate_code` 生成分析脚本，再用 `run_code` 执行。

### 8. 动态创建 Skill

```
You> 我需要一个做参数敏感性分析的工具，用SALib包
```

如果该功能不存在，LLM 调用 `create_skill` 自动生成：
- `hydroclaw/skills/sensitivity_analysis/skill.md`
- `hydroclaw/skills/sensitivity_analysis/tool.py`

新工具立即注册，当前对话即可使用。

### 9. 利用历史档案加速率定

```
You> 再次率定流域12025000的GR4J模型，看看能不能比上次更好
```

如果该流域曾率定过，system prompt 中会自动注入历史档案（参数值、NSE），LLM 可以：
- 以历史最优参数作为先验缩小搜索范围
- 判断是否已经收敛无需重复率定

## 语言支持

- 中文查询 -> 中文回答
- 英文查询 -> 英文回答
- 技术术语保留原文（NSE、KGE、SCE-UA 等）

## 输出位置

| 位置 | 内容 |
|------|------|
| `results/<model>_<basin>/` | 率定参数、评估指标、优化轨迹 |
| `results/<model>_<basin>/train_metrics/` | 训练期指标 |
| `results/<model>_<basin>/test_metrics/` | 测试期指标 |
| `<workspace>/basin_profiles/<id>.json` | 流域跨会话档案 |
| `sessions/` | 会话 JSONL 日志 |
| `logs/` | 运行日志 |
| `generated_code/` | LLM 生成的分析脚本 |

## 常用技巧

**控制迭代轮数**：

```
You> 率定GR4J模型，流域12025000，只需100轮迭代
```

**隔离不同实验**（不同 workspace 互不干扰）：

```bash
python -m hydroclaw -w results/exp_gr4j "率定GR4J模型，流域12025000"
python -m hydroclaw -w results/exp_xaj  "率定XAJ模型，流域12025000"
```

**英文查询同样支持**：

```
You> Calibrate GR4J for basin 12025000 using SCE-UA, target NSE 0.75
```
