// utils.js — Constants, lookup tables, and pure utility functions.
// Loaded first; no dependencies on other modules.

marked.setOptions({ breaks: true, gfm: true });

// Maps adapter/package operation names -> tool function names (for display)
const OP_TO_TOOL = {
  calibrate:           "calibrate_model",
  evaluate:            "evaluate_model",
  simulate:            "run_simulation",
  visualize:           "visualize",
  list_basins:         "list_basins",
  read_data:           "read_dataset",
  convert_to_nc:       "convert_dataset_to_nc",
  list_camels_basins:  "list_camels_basins",
  check_camels_data:   "check_camels_data",
};

const TOOL_ZH = {
  validate_basin:"验证流域数据", calibrate_model:"执行模型率定", evaluate_model:"评估模型性能",
  visualize:"生成可视化", llm_calibrate:"LLM 智能率定", batch_calibrate:"批量率定",
  compare_models:"多模型对比", generate_code:"生成分析代码", run_code:"执行分析脚本",
  create_skill:"创建新技能", read_file:"读取文件", inspect_dir:"查看目录",
  ask_user:"向用户提问", search_memory:"检索历史记忆", save_basin_profile:"保存流域档案",
  simulate:"径流模拟", run_simulation:"径流模拟", observe:"观察工作区",
  record_error_solution:"记录错误解决方案",
  create_adapter:"创建水文包适配器", install_package:"安装 Python 包",
  register_package:"注册已安装包",
  add_local_package:"注册本地目录包", add_local_tool:"注册单文件工具",
  derive_formula:"推导产流公式", run_pipeline:"运行推导管道",
  create_task_list:"创建任务列表", get_pending_tasks:"获取待办任务",
  add_task:"动态添加任务", update_task:"更新任务状态",
  list_basins:"列出流域", read_dataset:"读取数据集", convert_dataset_to_nc:"转换为 NC",
  list_camels_basins:"列出 CAMELS 流域", check_camels_data:"检查数据可用性",
};

const TOOL_ZH_DESC = {
  calibrate_model:   "使用 SCE-UA/GA/scipy 等算法对水文模型进行参数率定",
  evaluate_model:    "计算已率定模型在指定时段的 NSE、KGE 等性能指标",
  llm_calibrate:     "LLM 驱动的智能率定：自动识别问题参数并迭代调整范围",
  visualize:         "生成径流过程线、散点图等率定结果可视化图表",
  simulate:          "用率定参数对指定时段进行径流模拟，输出预测流量序列",
  validate_basin:    "验证流域 ID 是否有效、时段数据是否完整可用",
  generate_code:     "根据任务描述生成可直接执行的 Python 分析脚本",
  run_code:          "在工作区安全沙盒中执行 Python 代码并捕获输出结果",
  batch_calibrate:   "对多个流域和多种模型并行批量执行率定任务",
  compare_models:    "并排对比多个模型在同一流域的率定效果与指标",
  create_skill:      "根据描述动态生成新的工作流技能文件，扩展 Agent 能力",
  read_file:         "读取工作区内文本、JSON、YAML 等文件的内容",
  inspect_dir:       "查看指定目录的文件列表与结构，辅助路径定位",
  ask_user:          "当信息不足时暂停并向用户提问，等待用户输入后继续",
  search_memory:     "检索跨会话的历史操作记录与流域率定经验",
  save_basin_profile:"将本次率定的参数与指标保存为流域长期档案",
  create_adapter:    "为新水文包生成标准适配器骨架文件",
  install_package:   "通过 pip 安装额外的 Python 水文工具包",
  register_package:  "将已安装包注册为可用适配器",
  record_error_solution: "记录遇到的错误及解决方案，构建错误知识库",
  observe:           "观察工作区状态与任务进度",
  run_simulation:    "使用率定参数对指定时段进行径流模拟，输出预测流量序列",
  create_task_list:  "为批量实验创建多步骤任务计划，自动跳过已完成任务",
  get_pending_tasks: "获取下一个待执行的任务及整体进度概览",
  add_task:          "根据中间结果动态向任务列表追加新任务",
  update_task:       "将任务标记为已完成或失败，记录 NSE/KGE 等指标",
  list_basins:          "列出自定义数据集中所有流域的 ID 列表",
  read_dataset:         "读取自定义数据集的属性或时序数据",
  convert_dataset_to_nc:"将自定义数据集的 CSV 原始文件转换为 NetCDF 缓存，加速后续读取",
  list_camels_basins:   "列出指定 CAMELS 数据集中所有可用流域的 ID",
  check_camels_data:    "验证 CAMELS 数据集是否已下载到本地、指定流域是否存在",
};

const TOOL_ZH_DETAIL = {
  calibrate_model:
    `输入：模型名称（gr4j/gr5j/gr6j/lstm）、流域 ID 列表、训练/测试时段、优化算法。\n` +
    `支持算法：SCE-UA（默认）、GA（遗传算法）、scipy minimize。\n` +
    `输出：率定参数文件 calibration_config.yaml，存放在工作区 results/ 目录下。`,
  evaluate_model:
    `读取 calibrate_model 输出的 calibration_config.yaml，在指定时段运行模型并计算指标。\n` +
    `默认指标：NSE（纳什效率系数）、KGE（Kling-Gupta 效率系数）、bias（偏差）。\n` +
    `eval_period 留空时自动使用率定配置中的测试期。`,
  llm_calibrate:
    `区别于传统率定：LLM 分析每轮结果，判断哪些参数处于边界值，自动收窄/扩展参数范围。\n` +
    `多轮迭代直到 NSE 不再显著提升或达到最大轮数。\n` +
    `适用场景：标准率定结果 NSE < 0.5，或参数初始范围不合理时。`,
  validate_basin:
    `检查流域 ID 格式（8 位数字）是否在 CAMELS 数据集中存在。\n` +
    `同时验证指定时段内的降水、气温、流量数据是否完整（无大段缺失）。\n` +
    `建议在 calibrate_model 之前调用，避免因数据问题导致率定中途失败。`,
  generate_code:
    `调用 LLM 生成完整的 Python 脚本，包含导入语句、数据读取、分析逻辑、结果输出。\n` +
    `生成后代码保存在工作区，可直接由 run_code 执行。`,
  run_code:
    `在受限沙盒中执行指定路径的 Python 脚本，stdout/stderr 实时捕获并截断（防上下文爆炸）。\n` +
    `工作目录为当前工作区，可读取工作区内所有文件。`,
};

const TOOL_TIER = {20: "核心", 10: "技能", 5: "动态"};

const KNOW_ZH = {
  "calibration_guide.md": "率定策略指南",
  "model_parameters.md":  "模型参数知识库",
  "datasets.md":          "数据集说明",
  "error_solutions.json": "错误解决方案",
};

const TOOL_ICON = {
  calibrate_model:"\u2699", evaluate_model:"\uD83D\uDCCA", llm_calibrate:"\uD83E\uDD16",
  visualize:"\uD83D\uDCC8", validate_basin:"\u2705", batch_calibrate:"\uD83D\uDD04",
  compare_models:"\u2696", generate_code:"\uD83D\uDCBB", run_code:"\u25B6",
  create_skill:"\u2728", read_file:"\uD83D\uDCC4", inspect_dir:"\uD83D\uDCC1",
  ask_user:"\u2753", search_memory:"\uD83D\uDD0D", save_basin_profile:"\uD83D\uDCBE",
  simulate:"\uD83D\uDCA7", observe:"\uD83D\uDC41", record_error_solution:"\uD83D\uDCDD",
  add_local_package:"\uD83D\uDD0C", add_local_tool:"\uD83D\uDD27",
  derive_formula:"\uD83E\uDDEA", run_pipeline:"\uD83D\uDE80",
};

// ── Pure utilities ─────────────────────────────────────────────────────────────
function mkEl(tag, cls) { const el = document.createElement(tag); if (cls) el.className = cls; return el; }
function escHtml(s) { return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }
function scrollBottom() { const w = document.getElementById("messages-wrap"); requestAnimationFrame(() => { w.scrollTop = w.scrollHeight; }); }
function fmtTokens(t) {
  if (t >= 1_000_000) return (t / 1_000_000).toFixed(2) + "M";
  if (t >= 1000) return (t / 1000).toFixed(1) + "K";
  return String(t);
}

let _toastTimer = null;
function showToast(msg, ms = 2800) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.remove("show"), ms);
}
