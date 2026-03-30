# 使用指南

> 版本：v2.6 | 日期：2026-03-25

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

### 终端模式

```bash
# 交互模式（多轮对话）
python -m hydroclaw

# 单次查询
python -m hydroclaw "率定GR4J模型，流域12025000"

# 开发者模式（显示完整工具日志 + LLM 推理步骤）
python -m hydroclaw --dev

# 指定配置和工作目录
python -m hydroclaw -c my_config.json -w results/exp_A "率定GR4J模型，流域12025000"
```

| 参数 | 说明 |
|------|------|
| `query` | 查询内容，省略则进入交互模式 |
| `--dev` | 开发者模式：显示完整工具调用日志 |
| `-c, --config` | JSON 配置文件路径 |
| `-w, --workspace` | 工作目录（结果、记忆隔离） |

---

## Web 服务模式

```bash
python -m hydroclaw --server          # 启动 FastAPI Web 服务（默认端口 7860）
python -m hydroclaw --server --port 8080  # 自定义端口
```

浏览器将自动打开 `http://localhost:7860`，提供：

- **对话界面**：自然语言提问，实时流式显示 Agent 推理和工具调用过程
- **工具 / 技能 / 知识库**：侧边栏展示所有可用工具、Skill 和领域知识，点击可展开详情
- **数据集管理**：查看已支持的公开数据集状态，添加/转换自定义数据集
- **历史对话**：最近 10 条历史会话，点击可加载

## 交互模式命令

进入交互模式后，除了直接输入自然语言查询，还支持以下斜杠命令：

| 命令 | 说明 |
|------|------|
| `/tasks` | 显示当前批量任务列表（任务 ID、描述、状态、NSE 结果） |
| `/pause` | 请求暂停——Agent 在当前步骤完成后停下，任务进度自动保存 |
| `/resume` | 恢复上次未完成的批量任务，已完成的任务自动跳过 |
| `/help` | 列出所有可用命令 |
| `/quit` | 安全退出——若有未完成任务会提示确认，并说明可用 `/resume` 续跑 |

**Ctrl+C**：立即中断当前正在运行的任务（率定进度条等），返回输入提示符。任务状态已持久化，可用 `/resume` 继续。

> **暂停说明**：`/pause` 在两次工具调用之间生效（即 Agent 完成当前 LLM 推理步骤后），
> 无法在 SCE-UA 进度条运行期间立即中断——此时请用 Ctrl+C。

### 批量任务工作流示例

```
You> 比较 GR4J 和 XAJ 在流域 12025000 和 03439000 上的率定性能，给出报告

  > 创建任务计划
  任务进度 [++++++++............] 0%  0 完成 / 4 待执行  共 4 个

  > 执行模型率定  GR4J  |  SCE_UA  |  12025000
  任务进度 [++++++++++++++......] 25%  1 完成 / 3 待执行  共 4 个
  ...

You> /tasks          ← 随时查看进度

  任务列表  2/4 完成
  目标：比较 GR4J 和 XAJ 在流域 12025000 和 03439000 上的率定性能
  + task_001  率定GR4J，流域12025000   done    0.721
  + task_002  率定XAJ，流域12025000    done    0.683
    task_003  率定GR4J，流域03439000   pending
    task_004  率定XAJ，流域03439000    pending

You> /pause          ← 暂停后可继续对话或退出
已请求暂停。Agent 将在当前任务完成后暂停，任务状态已自动保存。

You> /resume         ← 下次启动后继续
恢复任务：2 个待执行 / 2/4 已完成
```

---

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

### 10. 注册本地水文包

```
You> 帮我注册本地包 D:/project/autohydro，包名 autohydro
```

Agent 会调用 `add_local_package`，将包写入 `plugins.json` 并热加载，之后即可驱动该包执行计算。

### 11. 委派子代理

批量任务中，Agent 可以委派每个单流域任务给专用的子代理（上下文隔离）：

```
You> 用子代理并行率定流域 12025000 和 03439000，模型 GR4J
```

Agent 自动调用 `spawn_agent("calibrate-worker", ...)` 两次，每个子代理独立运行，不共享历史上下文。

---

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

**强制诊断模式**（NSE 偏低时让 Agent 主动观测）：

```
You> 率定结果 results/gr4j_12025000 的 NSE 偏低，帮我检查参数是否触边界
```

Agent 会调用 `read_file` 直接读取参数文件，自主诊断边界情况。

**英文查询同样支持**：

```
You> Calibrate GR4J for basin 12025000 using SCE-UA, target NSE 0.75
```
