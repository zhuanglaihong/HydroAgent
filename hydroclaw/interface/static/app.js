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
  create_task_list:"创建任务列表", get_pending_tasks:"获取待办任务",
  add_task:"动态添加任务", update_task:"更新任务状态",
  list_basins:"列出流域", read_dataset:"读取数据集", convert_dataset_to_nc:"转换为 NC",
  list_camels_basins:"列出 CAMELS 流域", check_camels_data:"检查数据可用性",
};
// Short one-line Chinese descriptions for the tools panel
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
// Multi-paragraph Chinese detail descriptions
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
  calibrate_model:"⚙", evaluate_model:"📊", llm_calibrate:"🤖",
  visualize:"📈", validate_basin:"✅", batch_calibrate:"🔄",
  compare_models:"⚖", generate_code:"💻", run_code:"▶",
  create_skill:"✨", read_file:"📄", inspect_dir:"📁",
  ask_user:"❓", search_memory:"🔍", save_basin_profile:"💾",
  simulate:"💧", observe:"👁", record_error_solution:"📝",
};

// ── Session management ───────────────────────────────────────────────────────
// Each session has its own messages <div> (swapped in/out of #messages-wrap)
// liveKey  = which session is currently executing (agent running)
// activeKey = which session is displayed to user
// They can differ: user switches away while agent still runs in background
const SESS = new Map(); // key -> {el, history, tokens, live, toolSeq, runCount, serverSid}
let activeKey = null;
let liveKey   = null;
let _keySeq   = 0;

function newKey() { return `s${++_keySeq}`; }

function newSessData() {
  const el = document.createElement("div");
  el.style.cssText = "display:contents";
  return { el, history: [], tokens: { total: 0, prompt: 0, compl: 0 }, live: null, toolSeq: 0, runCount: 0, serverSid: null };
}

function liveSess()   { return liveKey   ? SESS.get(liveKey)   : null; }
function activeSess() { return activeKey ? SESS.get(activeKey) : null; }
function isLiveActive() { return liveKey === activeKey; }

// Swap messages-wrap to show session key's messages
function switchDisplay(key) {
  if (key === activeKey) return;
  const wrap = document.getElementById("messages-wrap");
  // Detach current
  if (activeKey && SESS.has(activeKey)) {
    const cur = SESS.get(activeKey);
    if (cur.el.parentNode === wrap) wrap.removeChild(cur.el);
  }
  activeKey = key;
  const s = SESS.get(key);
  if (s) {
    wrap.appendChild(s.el);
    updateTokenDisplay();
    scrollBottom();
    // Highlight active session in sidebar
    document.querySelectorAll(".session-item").forEach(el => {
      el.classList.toggle("active", el.dataset.key === key || el.dataset.sid === s.serverSid);
    });
    // Restore exec panel for the newly active session
    restoreExecPanel(s.history);
  }
}

// Create brand-new empty session and display it
function createAndSwitchNew() {
  const key = newKey();
  SESS.set(key, newSessData());
  switchDisplay(key);
  return key;
}

// ── Theme ────────────────────────────────────────────────────────────────────
const _theme = { val: localStorage.getItem("hc_theme") || "light" };
function setTheme(t) {
  _theme.val = t;
  document.body.dataset.theme = t;
  document.getElementById("theme-btn").textContent = t === "dark" ? "浅色" : "深色";
  localStorage.setItem("hc_theme", t);
}
setTheme(_theme.val);
document.getElementById("theme-btn").onclick = () => setTheme(_theme.val === "dark" ? "light" : "dark");

// ── Sidebar collapse ──────────────────────────────────────────────────────────
function setSidebarCollapsed(v) {
  document.getElementById("sidebar").classList.toggle("collapsed", v);
  localStorage.setItem("hc_sb_collapsed", v ? "1" : "0");
}
setSidebarCollapsed(localStorage.getItem("hc_sb_collapsed") === "1");
document.getElementById("sidebar-collapse-btn").onclick = () =>
  setSidebarCollapsed(!document.getElementById("sidebar").classList.contains("collapsed"));

// ── Exec panel collapse ───────────────────────────────────────────────────────
function setExecCollapsed(v) {
  document.getElementById("exec-panel").classList.toggle("collapsed", v);
  localStorage.setItem("hc_exec_collapsed", v ? "1" : "0");
}
setExecCollapsed(localStorage.getItem("hc_exec_collapsed") !== "0"); // default collapsed
document.getElementById("exec-collapse-btn").onclick = () =>
  setExecCollapsed(!document.getElementById("exec-panel").classList.contains("collapsed"));

// ── WebSocket ─────────────────────────────────────────────────────────────────
let _ws = null;
function connect() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  _ws = new WebSocket(`${proto}//${location.host}/ws`);
  _ws.onopen  = () => { setConn(true); _ws.send(JSON.stringify({ type: "ping" })); };
  _ws.onclose = () => { setConn(false); setTimeout(connect, 3000); };
  _ws.onerror = () => _ws.close();
  _ws.onmessage = e => { try { handleEvent(JSON.parse(e.data)); } catch (_) {} };
}
function setConn(ok) {
  document.getElementById("conn-dot").className = ok ? "connected" : "";
  document.getElementById("conn-label").textContent = ok ? "已连接" : "重连中...";
}

// ── Event handler ─────────────────────────────────────────────────────────────
function handleEvent(ev) {
  // Silently ignore stale events after stop (liveKey already cleared)
  if (!["pong", "session_id"].includes(ev.type) && liveKey === null) return;
  switch (ev.type) {
    case "thinking_start": setRunning(true); ensureLive(); showThinking(); break;
    case "thinking_end":   hideThinking(); break;
    case "thought":        addThought(ev.text); break;
    case "tool_start":     ensureLive(); addToolCard(ev.name, ev.args); setStatus(`工具: ${TOOL_ZH[ev.name] || ev.name}`); break;
    case "tool_end":       updateToolCard(ev.name, ev.result, ev.elapsed); break;
    case "calibration_progress": updateCalProgress(ev); break;
    case "answer":         finalizeMessage(ev.text); break;
    case "ask_user":       showAskUser(ev.question, ev.context); break;
    case "session_id":     if (liveSess()) liveSess().serverSid = ev.id; break;
    case "error":
      appendError(ev.msg);
      setRunning(false);
      // Critical error banners
      if (/429|rate.?limit|quota/i.test(ev.msg)) {
        showToast("API 限速（429），Token 可能已耗尽，请稍后重试", 7000);
      } else if (/5\d\d|timeout|connection|network/i.test(ev.msg)) {
        showToast("服务端错误，请检查网络或重试", 5000);
      }
      break;
    case "done":           onDone(ev.tokens); break;
    case "stopping":       setStatus("停止中，等待当前工具完成…"); break;
    case "pong":           break;
  }
}

// ── Send ──────────────────────────────────────────────────────────────────────
function sendQuery() {
  const input = document.getElementById("input");
  const text = input.value.trim();
  if (!text || !_ws || _ws.readyState !== 1) return;
  if (liveKey && liveKey !== activeKey) {
    showToast("后台任务执行中，请等待完成或先切换回该对话"); return;
  }
  // Ensure we have an active session
  if (!activeKey) createAndSwitchNew();
  liveKey = activeKey;
  addUserMessage(text);
  input.value = ""; input.style.height = "auto";
  _ws.send(JSON.stringify({ type: "query", text, prior_messages: buildPrior() }));
  setRunning(true);
  // Expand exec panel, add run label
  setExecCollapsed(false);
  const ls = liveSess();
  ls.runCount = (ls.runCount || 0) + 1;
  const log = document.getElementById("exec-log");
  const empty = document.getElementById("exec-empty");
  if (empty) empty.remove();
  const lbl = mkEl("div", "exec-run-label");
  lbl.textContent = `# 运行 ${ls.runCount}`;
  log.appendChild(lbl);
}

function sendStop() {
  if (!liveKey) return;
  if (_ws && _ws.readyState === 1) {
    _ws.send(JSON.stringify({ type: "stop" }));
  }
  // Immediately finalize the current message and release the UI
  const s = liveSess();
  if (s) {
    ensureLive();
    hideThinking();
    const note = mkEl("div", "msg-answer");
    note.innerHTML = "<em>*(任务已后台继续运行，率定将完成后自动保存)*</em>";
    if (s.live) {
      s.live.bubble.appendChild(note);
      s.history.push({ role: "assistant", content: "*(任务已后台继续运行，率定将完成后自动保存)*", turns: s.live.turns || [], tools: s.live.toolResults || [], thoughts: s.live.thoughtSteps || [] });
      s.live = null;
    }
  }
  setStatus("任务挂后台，率定继续运行");
  onDone(null);
}

// ── Message building (all operate on liveSess()) ──────────────────────────────
function addUserMessage(text) {
  const s = activeSess(); // user message goes to active (= live at this moment)
  if (!s) return;
  const el = mkEl("div", "msg user");
  const bubble = mkEl("div", "msg-bubble");
  bubble.textContent = text;
  el.appendChild(bubble);
  s.el.appendChild(el);
  s.history.push({ role: "user", content: text });
  if (isLiveActive()) scrollBottom();
}

function ensureLive() {
  const s = liveSess();
  if (!s || s.live) return;
  const el = mkEl("div", "msg assistant");
  const bubble = mkEl("div", "msg-bubble");
  el.appendChild(bubble);
  s.el.appendChild(el);
  s.live = { el, bubble, toolCards: {}, thoughtEl: null, thoughtSteps: [], curThoughtSteps: [],
             pendingThoughts: [], turns: [],
             thinkingEl: null, imagesEl: null, toolResults: [] };
  s.toolSeq = s.toolSeq || 0;
  if (isLiveActive()) scrollBottom();
}

function showThinking() {
  const live = liveSess()?.live;
  if (!live || live.thinkingEl) return;
  const el = mkEl("div", "thinking-block");
  el.innerHTML = '<div class="spinner"></div><span>LLM 推理中...</span>';
  live.thinkingEl = el;
  live.bubble.appendChild(el);
}
function hideThinking() {
  const live = liveSess()?.live;
  if (live?.thinkingEl) { live.thinkingEl.remove(); live.thinkingEl = null; }
}

function addThought(text) {
  const live = liveSess()?.live;
  if (!live) return;
  hideThinking();
  // Track for structured turn data
  live.pendingThoughts = live.pendingThoughts || [];
  live.pendingThoughts.push(text);
  // Create a new thought block for each agent turn (reset after each tool call)
  if (!live.thoughtEl) {
    const el = document.createElement("details");
    el.className = "thought-block";
    live.thoughtEl = el;
    live.curThoughtSteps = [];
    live.thoughtSteps = live.thoughtSteps || [];  // all steps for history
    live.bubble.appendChild(el);  // in-sequence, NOT prepend
  }
  live.curThoughtSteps.push(text);
  live.thoughtSteps.push(text);
  const steps = live.curThoughtSteps;
  const n = steps.length;
  live.thoughtEl.innerHTML = `<summary>思考过程${n > 1 ? ` (${n} 步)` : ''}</summary><div class="thought-text">${steps.map((t, i) => (n > 1 ? `<div class="thought-step"><strong>步骤 ${i+1}</strong></div>` : '') + escHtml(t)).join('<hr class="thought-sep">')}</div>`;
  if (isLiveActive()) scrollBottom();
}

function addToolCard(name, args) {
  const s = liveSess();
  if (!s?.live) return;
  hideThinking();
  // Finalize pending thoughts into structured turn entry
  s.live.pendingThoughts = s.live.pendingThoughts || [];
  s.live.turns = s.live.turns || [];
  const cleanArgsForTurn = Object.fromEntries(Object.entries(args || {}).filter(([k]) => !k.startsWith("_")));
  s.live.turns.push({ thoughts: [...s.live.pendingThoughts], toolName: name, args: cleanArgsForTurn, result: null, elapsed: null });
  s.live.pendingThoughts = [];
  // Reset thought block so next "thought" event starts a new one (new turn)
  s.live.thoughtEl = null;
  s.live.curThoughtSteps = [];
  const id = `tc-${s.toolSeq++}`;
  const label = TOOL_ZH[name] || name;
  const icon  = TOOL_ICON[name] || "⚙";
  const cleanArgs = Object.fromEntries(Object.entries(args || {}).filter(([k]) => !k.startsWith("_")));

  // Chat card (mini tool card in the bubble)
  const ctc = mkEl("div", "chat-tc");
  ctc.id = `ctc-${id}`;
  ctc.innerHTML = `
    <div class="chat-tc-row" onclick="ctcToggle('${id}')">
      <span class="chat-tc-icon">${icon}</span>
      <span class="chat-tc-name">${label}</span>
      <span class="chat-tc-badge running" id="ctc-${id}-b">运行中</span>
      <span class="chat-tc-time" id="ctc-${id}-t"></span>
      <span class="chat-tc-arrow" id="ctc-${id}-a">▶</span>
    </div>
    <div class="chat-tc-body" id="ctc-${id}-body" style="display:none">
      <pre class="chat-tc-pre">${escHtml(JSON.stringify(Object.fromEntries(Object.entries(args||{}).filter(([k])=>!k.startsWith('_'))), null, 2))}</pre>
    </div>
  `;
  ctc.addEventListener("click", e => {
    if (!e.target.closest('.chat-tc-row')) return;
    setExecCollapsed(false);
    const c = document.getElementById(id);
    if (c) c.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  });
  s.live.bubble.appendChild(ctc);

  // Full card in exec panel
  const card = mkEl("div", "tool-card");
  card.dataset.name = name; card.dataset.status = "running"; card.id = id;
  card.innerHTML = `
    <div class="tc-header" onclick="toggleCard('${id}')">
      <span class="tc-icon">${icon}</span>
      <span class="tc-name">${label}</span>
      <span class="tc-status running" id="${id}-status">运行中...</span>
      <span class="tc-chevron open" id="${id}-chev">▶</span>
    </div>
    <div class="tc-body open" id="${id}-body">
      ${Object.keys(cleanArgs).length ? `<div class="tc-section-label">参数</div><div class="tc-code">${escHtml(JSON.stringify(cleanArgs, null, 2))}</div>` : ""}
      <div id="${id}-progress"></div>
      <div id="${id}-result"></div>
    </div>`;
  document.getElementById("exec-log").appendChild(card);
  s.live.toolCards[name] = { id, ctc, args: cleanArgs };
  if (isLiveActive()) scrollBottom();
}

function ctcToggle(id) {
  const body = document.getElementById(`ctc-${id}-body`);
  const arrow = document.getElementById(`ctc-${id}-a`);
  if (!body) return;
  const open = body.style.display !== 'none';
  body.style.display = open ? 'none' : 'block';
  if (arrow) arrow.style.transform = open ? '' : 'rotate(90deg)';
}

function updateToolCard(name, result, elapsed) {
  const s = liveSess();
  const entry = s?.live?.toolCards[name];
  const id = entry ? (typeof entry === 'string' ? entry : entry.id) : null;
  const ok = !(result?.error);
  const statusText = ok ? (elapsed ? `${elapsed}s` : "完成") : "失败";

  // Update exec panel card
  const card = id ? document.getElementById(id) : null;
  if (card) {
    card.dataset.status = ok ? "done" : "error";
    const st = document.getElementById(`${id}-status`);
    if (st) { st.className = `tc-status ${ok ? "done" : "error"}`; st.textContent = statusText; }
    const prog = document.getElementById(`${id}-progress`);
    if (prog) prog.innerHTML = "";
    const nse = result?.metrics?.NSE;
    if (typeof nse === "number") {
      const cls = nse >= .75 ? "nse-good" : nse >= .5 ? "nse-ok" : "nse-bad";
      const hdr = card.querySelector(".tc-header");
      const badge = mkEl("span", `tc-nse ${cls}`);
      badge.textContent = `NSE ${nse.toFixed(3)}`;
      hdr.insertBefore(badge, hdr.querySelector(".tc-chevron"));
    }
    const res = document.getElementById(`${id}-result`);
    if (res && result) res.innerHTML = `<div class="tc-section-label">执行结果</div><div class="tc-code">${escHtml(JSON.stringify(result, null, 2))}</div>`;
    // Auto-collapse after completion
    const body = document.getElementById(`${id}-body`);
    const chev = document.getElementById(`${id}-chev`);
    if (body) { body.classList.remove("open"); }
    if (chev) { chev.classList.remove("open"); }
  }

  // Update chat card badge and time
  const ctcEntry = entry && typeof entry === 'object' ? entry.ctc : null;
  if (ctcEntry) {
    const badge = document.getElementById(`ctc-${id}-b`);
    const timeEl = document.getElementById(`ctc-${id}-t`);
    if (badge) { badge.textContent = ok ? "完成" : "失败"; badge.className = `chat-tc-badge ${ok ? "ok" : "err"}`; }
    if (timeEl) timeEl.textContent = elapsed ? `${elapsed}s` : "";
  }

  // Images in live session's bubble (handle all key names used by tools)
  const _imgList = result?.plot_files || result?.plot_paths || result?.figure_paths || [];
  const imgs = Array.isArray(_imgList) ? _imgList.slice(0, 6) : [];
  if (imgs.length && s?.live) {
    if (!s.live.imagesEl) {
      s.live.imagesEl = mkEl("div", `msg-images${imgs.length === 1 ? " single" : ""}`);
      s.live.bubble.appendChild(s.live.imagesEl);
    }
    imgs.forEach(p => {
      const img = document.createElement("img");
      img.src = `/file?path=${encodeURIComponent(String(p))}`; img.alt = "plot";
      img.onclick = () => openLightbox(img.src);
      s.live.imagesEl.appendChild(img);
    });
  }
  if (s?.live) {
    s.live.toolResults = s.live.toolResults || [];
    const tcEntry = s.live.toolCards[name];
    s.live.toolResults.push({ name, args: tcEntry?.args || {}, result: result || {}, elapsed });
    // Save result into structured turns
    if (s.live.turns) {
      const turn = [...s.live.turns].reverse().find(t => t.toolName === name && t.result === null);
      if (turn) { turn.result = result || {}; turn.elapsed = elapsed; }
    }
  }
  if (isLiveActive()) scrollBottom();
}

function updateCalProgress(ev) {
  const s = liveSess();
  const entry = s?.live && (s.live.toolCards["calibrate_model"] || s.live.toolCards["llm_calibrate"]);
  if (!entry) return;
  const id = typeof entry === 'string' ? entry : entry.id;
  const el = document.getElementById(`${id}-progress`);
  if (!el) return;
  const pct = Math.min(ev.pct || 0, 99);
  const lbl = ev.eval_count > 0 && ev.rep > 0
    ? `${ev.round_label ? ev.round_label + " · " : ""}${ev.algo} ${ev.eval_count}/${ev.rep} (${pct.toFixed(0)}%) · ${ev.elapsed}s`
    : `${ev.round_label ? ev.round_label + " · " : ""}${ev.algo} 进行中... ${ev.elapsed}s`;
  el.innerHTML = `<div class="cal-progress"><div class="cal-progress-label">${escHtml(lbl)}</div><div class="cal-progress-bar-wrap"><div class="cal-progress-bar" style="width:${pct}%"></div></div></div>`;
}

function finalizeMessage(text) {
  const s = liveSess();
  if (!s) return;
  ensureLive();
  hideThinking();
  // Finalize any trailing thought (after last tool, before answer)
  s.live.pendingThoughts = s.live.pendingThoughts || [];
  s.live.turns = s.live.turns || [];
  if (s.live.pendingThoughts.length > 0) {
    s.live.turns.push({ thoughts: [...s.live.pendingThoughts], toolName: null, args: null, result: null, elapsed: null });
    s.live.pendingThoughts = [];
  }
  const ansEl = mkEl("div", "msg-answer");
  ansEl.innerHTML = marked.parse(text || "");
  s.live.bubble.appendChild(ansEl);
  s.history.push({ role: "assistant", content: text, turns: s.live.turns, tools: s.live.toolResults || [], thoughts: s.live.thoughtSteps || [] });
  s.live = null;
  if (isLiveActive()) {
    scrollBottom();
    setTimeout(scrollBottom, 100);  // force after render
  }
}

function appendError(msg) {
  const s = liveSess();
  if (!s) return;
  ensureLive();
  hideThinking();
  const el = mkEl("div", "msg-answer");
  el.style.color = "var(--err)";
  el.textContent = "[ERR] " + msg;
  s.live.bubble.appendChild(el);
  s.live = null;
  if (isLiveActive()) scrollBottom();
}

// ── Ask User ──────────────────────────────────────────────────────────────────
function showAskUser(question, context) {
  const bar = document.getElementById("ask-user-bar");
  document.getElementById("ask-user-q").textContent = (context ? context + "\n" : "") + question;
  bar.style.display = "block";
  document.getElementById("ask-user-input").focus();
}
document.getElementById("ask-user-submit").onclick = submitAnswer;
document.getElementById("ask-user-input").addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submitAnswer(); }
});
function submitAnswer() {
  const inp = document.getElementById("ask-user-input");
  const ans = inp.value.trim();
  if (!ans) return;
  _ws.send(JSON.stringify({ type: "user_answer", text: ans }));
  inp.value = "";
  document.getElementById("ask-user-bar").style.display = "none";
}

// ── Done / status ─────────────────────────────────────────────────────────────
function onDone(tokens) {
  const s = liveSess();
  if (s && tokens) {
    s.tokens.total  += tokens.total_tokens     || 0;
    s.tokens.prompt += tokens.prompt_tokens    || 0;
    s.tokens.compl  += tokens.completion_tokens || 0;
  }
  const wasBackground = !isLiveActive();
  liveKey = null;
  setRunning(false);
  setStatus("待命");
  updateTokenDisplay();
  if (wasBackground) {
    // Find the sidebar item for that session and show unread dot
    document.querySelectorAll(".session-item").forEach(el => {
      if (el.dataset.sid === s?.serverSid) {
        el.querySelector(".running-dot")?.remove(); // remove pulsing, replace with static ok
        const dot = mkEl("span", "");
        dot.style.cssText = "width:6px;height:6px;border-radius:50%;background:var(--ok);flex-shrink:0;display:inline-block;margin-left:auto";
        el.appendChild(dot);
      }
    });
    showToast("后台任务已完成，点击对话查看结果");
  }
  saveSnapshot().then(() => loadSessions());
}

// ── Running state + timer ─────────────────────────────────────────────────────
let _runStart = 0;
let _timerInterval = null;

function setRunning(v) {
  document.getElementById("input").disabled = v && isLiveActive();
  document.getElementById("send-btn").disabled = v && isLiveActive();
  document.getElementById("status-dot").className = `status-dot${v ? " running" : ""}`;
  const stopBtn = document.getElementById("stop-btn");
  stopBtn.classList.toggle("active", v);
  const timer = document.getElementById("elapsed-timer");
  if (v) {
    _runStart = Date.now();
    timer.style.display = "inline";
    _timerInterval = setInterval(() => {
      const s = Math.floor((Date.now() - _runStart) / 1000);
      timer.textContent = s < 60 ? `${s}s` : `${Math.floor(s/60)}m${s%60}s`;
    }, 1000);
  } else {
    clearInterval(_timerInterval);
    timer.style.display = "none";
  }
  // Update sidebar running dot
  document.querySelectorAll(".session-item .running-dot").forEach(el => el.remove());
  if (v && liveKey) {
    const s = SESS.get(liveKey);
    document.querySelectorAll(".session-item").forEach(el => {
      if (el.dataset.sid === s?.serverSid || el.dataset.key === liveKey) {
        el.insertBefore(Object.assign(mkEl("span", "running-dot"), {}), el.firstChild);
      }
    });
  }
}
function setStatus(t) { document.getElementById("status-text").textContent = t; }
const TOKEN_MAX = 1_000_000;
let _tokenAlerted = false;
function fmtTokens(t) {
  if (t >= 1_000_000) return (t / 1_000_000).toFixed(2) + "M";
  if (t >= 1000) return (t / 1000).toFixed(1) + "K";
  return String(t);
}
function updateTokenDisplay() {
  const t = activeSess()?.tokens?.total || 0;
  document.getElementById("token-display").textContent = `${fmtTokens(t)} / 1M`;
  document.getElementById("token-bar").style.width = Math.min(t / TOKEN_MAX * 100, 100) + "%";
  if (t >= TOKEN_MAX && !_tokenAlerted) {
    _tokenAlerted = true;
    showToast("Token 用量已达 1M 上限，后续请求可能失败", 6000);
  } else if (t >= TOKEN_MAX * 0.9 && !_tokenAlerted) {
    showToast("Token 用量已超过 90%，请注意剩余额度", 4000);
  }
}

// ── Toast ─────────────────────────────────────────────────────────────────────
let _toastTimer = null;
function showToast(msg, ms = 2800) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.remove("show"), ms);
}

// ── Sessions ──────────────────────────────────────────────────────────────────
// Active context menu state
let _sessMenuSid = null;
let _sessMenuEl = null;

function _closeSessMenu() {
  if (_sessMenuEl) { _sessMenuEl.remove(); _sessMenuEl = null; }
  _sessMenuSid = null;
}

document.addEventListener("click", e => {
  if (_sessMenuEl && !_sessMenuEl.contains(e.target)) _closeSessMenu();
});

async function loadSessions() {
  const res = await fetch("/api/sessions").catch(() => null);
  if (!res || !res.ok) return;
  const sessions = await res.json();
  const el = document.getElementById("session-list");
  el.innerHTML = "";
  const as = activeSess();
  const ls = liveSess();

  // Sort: pinned first, then by order (server returns by recency)
  const pinned = sessions.filter(s => s.pinned);
  const rest   = sessions.filter(s => !s.pinned);
  const sorted = [...pinned, ...rest].slice(0, 10);

  sorted.forEach(s => {
    const item = mkEl("div", "session-item");
    item.title = `${s.timestamp?.slice(0,16).replace("T"," ")}  |  ${s.tool_calls || 0} tools`;
    item.dataset.sid = s.session_id;
    item.dataset.key = "";  // placeholder

    // Pin icon
    if (s.pinned) {
      const pinIcon = mkEl("span", "sess-pin-icon");
      pinIcon.textContent = "📌";
      item.appendChild(pinIcon);
    }

    const nameSpan = mkEl("span", "session-name");
    nameSpan.textContent = s.title || s.query || "(无标题)";
    item.appendChild(nameSpan);

    // action menu button - always in DOM, shown via CSS
    const moreBtn = mkEl("button", "sess-more-btn");
    moreBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="12" cy="19" r="2"/></svg>';
    moreBtn.title = "重命名 / 置顶 / 删除";
    moreBtn.addEventListener("click", e => {
      e.stopPropagation();
      _openSessMenu(s.session_id, s, moreBtn, item, nameSpan);
    });
    item.appendChild(moreBtn);

    // Active state
    if (as?.serverSid === s.session_id) item.classList.add("active");
    // Running dot for live session
    if (ls?.serverSid === s.session_id) {
      const dot = mkEl("span", "running-dot");
      item.insertBefore(dot, nameSpan);
    }
    item.onclick = (e) => {
      if (e.target === moreBtn || moreBtn.contains(e.target)) return;
      if (item.classList.contains("sess-renaming")) return;
      loadHistorySession(s.session_id);
    };
    el.appendChild(item);
  });
  // Scroll list to top (newest sessions are first)
  el.scrollTop = 0;
}

function _openSessMenu(sid, meta, anchorEl, itemEl, nameSpan) {
  _closeSessMenu();
  _sessMenuSid = sid;

  const menu = mkEl("div", "sess-menu");
  menu.innerHTML = `
    <div class="sess-menu-item" data-action="rename">重命名</div>
    <div class="sess-menu-item" data-action="pin">${meta.pinned ? "取消置顶" : "置顶"}</div>
    <div class="sess-menu-item sess-menu-item-danger" data-action="delete">删除</div>
  `;
  _sessMenuEl = menu;
  document.body.appendChild(menu);

  // Position near anchor
  const rect = anchorEl.getBoundingClientRect();
  menu.style.top = (rect.bottom + 4) + "px";
  menu.style.left = Math.max(4, rect.left - 80) + "px";

  menu.addEventListener("click", e => {
    const action = e.target.dataset.action;
    if (!action) return;
    _closeSessMenu();
    if (action === "rename") {
      _startRename(sid, itemEl, nameSpan);
    } else if (action === "pin") {
      _patchSession(sid, { pinned: !meta.pinned });
    } else if (action === "delete") {
      _confirmDeleteSession(sid);
    }
  });
}

function _startRename(sid, itemEl, nameSpan) {
  itemEl.classList.add("sess-renaming");
  const oldText = nameSpan.textContent;
  const inp = document.createElement("input");
  inp.type = "text";
  inp.className = "sess-rename-input";
  inp.value = oldText;
  nameSpan.replaceWith(inp);
  inp.focus();
  inp.select();

  const okBtn = mkEl("button", "sess-rename-ok");
  okBtn.textContent = "OK";
  const cancelBtn = mkEl("button", "sess-rename-cancel");
  cancelBtn.textContent = "取消";

  inp.after(okBtn);
  okBtn.after(cancelBtn);

  function doRename() {
    const newTitle = inp.value.trim();
    if (newTitle && newTitle !== oldText) {
      _patchSession(sid, { title: newTitle });
    } else {
      loadSessions();
    }
  }

  function doCancel() {
    inp.replaceWith(nameSpan);
    okBtn.remove();
    cancelBtn.remove();
    itemEl.classList.remove("sess-renaming");
  }

  okBtn.onclick = e => { e.stopPropagation(); doRename(); };
  cancelBtn.onclick = e => { e.stopPropagation(); doCancel(); };
  inp.addEventListener("keydown", e => {
    if (e.key === "Enter") { e.preventDefault(); doRename(); }
    if (e.key === "Escape") { e.preventDefault(); doCancel(); }
  });
}

async function _patchSession(sid, body) {
  await fetch(`/api/sessions/${sid}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).catch(() => {});
  loadSessions();
}

async function _confirmDeleteSession(sid) {
  if (!confirm("确定要删除这条对话记录吗？此操作不可撤销。")) return;
  await fetch(`/api/sessions/${sid}`, { method: "DELETE" }).catch(() => {});
  // If this session is active, clear the display
  const s = activeSess();
  if (s?.serverSid === sid) {
    createAndSwitchNew();
  }
  loadSessions();
}

async function loadHistorySession(sid) {
  closeCurrentPanel();
  // If already displaying this session, just scroll
  if (activeSess()?.serverSid === sid) return;
  // Check if liveKey session is this sid (i.e., currently running this session)
  if (liveSess()?.serverSid === sid) {
    // Switch back to the running session
    switchDisplay(liveKey);
    return;
  }

  const res = await fetch(`/api/sessions/${sid}`).catch(() => null);
  if (!res || !res.ok) return;
  const snap = await res.json();
  if (!snap.messages) return;

  // Create a new session slot for displaying history
  const key = newKey();
  const data = newSessData();
  data.serverSid = sid;
  SESS.set(key, data);
  switchDisplay(key);

  // Render messages into data.el
  snap.messages.forEach(msg => {
    if (msg.role === "user") {
      const el = mkEl("div", "msg user");
      const b = mkEl("div", "msg-bubble");
      b.textContent = msg.content || "";
      el.appendChild(b);
      data.el.appendChild(el);
      data.history.push({ role: "user", content: msg.content });
    } else if (msg.role === "assistant") {
      const el = mkEl("div", "msg assistant");
      const b = mkEl("div", "msg-bubble");

      function renderThoughtBlock(thoughtArr) {
        if (!thoughtArr || !thoughtArr.length) return;
        const td = document.createElement("details");
        td.className = "thought-block";
        const n = thoughtArr.length;
        td.innerHTML = `<summary>思考过程${n > 1 ? ` (${n} 步)` : ''}</summary><div class="thought-text">${thoughtArr.map((t, i) => (n > 1 ? `<div class="thought-step"><strong>步骤 ${i+1}</strong></div>` : '') + escHtml(t)).join('<hr class="thought-sep">')}</div>`;
        b.appendChild(td);
      }
      function renderToolCard(t) {
        const ok = !t.result?.error;
        const nse = t.result?.metrics?.NSE;
        const cid = `h-${Math.random().toString(36).slice(2,7)}`;
        const icon = TOOL_ICON[t.name] || "⚙";
        const label = TOOL_ZH[t.name] || t.name;
        const nseBadge = typeof nse === "number"
          ? `<span class="tc-nse ${nse>=.75?"nse-good":nse>=.5?"nse-ok":"nse-bad"}">NSE ${nse.toFixed(3)}</span>` : "";
        const ctc = mkEl("div", "chat-tc");
        ctc.innerHTML = `
          <div class="chat-tc-row" onclick="ctcToggle('${cid}')">
            <span class="chat-tc-icon">${icon}</span>
            <span class="chat-tc-name">${label}</span>
            ${nseBadge}
            <span class="chat-tc-badge ${ok ? "ok" : "err"}">${ok ? "完成" : "失败"}</span>
            <span class="chat-tc-time">${t.elapsed ? t.elapsed + "s" : ""}</span>
            <span class="chat-tc-arrow" id="${cid}-a">▶</span>
          </div>
          <div class="chat-tc-body" id="${cid}-body" style="display:none">
            ${t.args && Object.keys(t.args).length ? `<div class="tc-section-label">参数</div><pre class="chat-tc-pre">${escHtml(JSON.stringify(t.args, null, 2))}</pre>` : ""}
            ${t.result ? `<div class="tc-section-label">执行结果</div><pre class="chat-tc-pre">${escHtml(JSON.stringify(t.result, null, 2).slice(0, 600))}</pre>` : ""}
          </div>`;
        b.appendChild(ctc);
      }

      const turns = msg.turns || [];
      const tools = msg.tools || [];

      if (turns.length > 0) {
        // New format: interleaved thought -> tool -> thought -> tool -> (final thought)
        turns.forEach(turn => {
          renderThoughtBlock(turn.thoughts);
          if (turn.toolName) renderToolCard({ name: turn.toolName, args: turn.args, result: turn.result, elapsed: turn.elapsed });
        });
      } else {
        // Legacy format: all thoughts first, then all tools
        renderThoughtBlock(msg.thoughts);
        tools.forEach(t => renderToolCard(t));
      }

      // Images from all tools
      const allToolObjs = turns.length > 0
        ? turns.filter(t => t.toolName).map(t => ({ result: t.result }))
        : tools;
      const imgs = allToolObjs.flatMap(t => { const l = t.result?.plot_files || t.result?.plot_paths || t.result?.figure_paths || []; return Array.isArray(l) ? l.slice(0, 3) : []; });
      if (imgs.length) {
        const imgWrap = mkEl("div", `msg-images${imgs.length===1?" single":""}`);
        imgs.forEach(p => { const img = document.createElement("img"); img.src = `/file?path=${encodeURIComponent(p)}`; img.onclick = () => openLightbox(img.src); imgWrap.appendChild(img); });
        b.appendChild(imgWrap);
      }
      if (msg.content) { const ans = mkEl("div", "msg-answer"); ans.innerHTML = marked.parse(msg.content); b.appendChild(ans); }
      el.appendChild(b);
      data.el.appendChild(el);
      data.history.push({ role: "assistant", content: msg.content, turns: msg.turns || [], tools, thoughts: msg.thoughts || [] });
    }
  });
  if (snap.token_total) {
    data.tokens = { total: snap.token_total || 0, prompt: snap.token_prompt || 0, compl: snap.token_compl || 0 };
  }
  updateTokenDisplay();
  scrollBottom();
  // Restore exec panel for this history session
  restoreExecPanel(data.history);
}

// ── Exec panel restore for historical sessions ────────────────────────────────
function restoreExecPanel(messages) {
  // Don't restore if agent is currently running
  if (liveKey) return;
  const log = document.getElementById("exec-log");
  log.innerHTML = "";
  const empty = mkEl("div", "");
  empty.id = "exec-empty";
  log.appendChild(empty);
  empty.style.display = "none";

  let hasTools = false;
  let runIdx = 0;
  (messages || []).forEach(msg => {
    // Collect tools from either turns (new) or tools (legacy)
    let toolList = [];
    if (msg.role === "assistant") {
      if (msg.turns && msg.turns.length > 0) {
        toolList = msg.turns.filter(t => t.toolName).map(t => ({ name: t.toolName, args: t.args, result: t.result, elapsed: t.elapsed }));
      } else if (msg.tools && msg.tools.length > 0) {
        toolList = msg.tools;
      }
    }
    if (toolList.length === 0) return;
    hasTools = true;
    runIdx++;
    const lbl = mkEl("div", "exec-run-label");
    lbl.textContent = `# 运行 ${runIdx}`;
    log.appendChild(lbl);
    toolList.forEach(tool => {
      if (!tool || !tool.name) return;
      const id = `h-tc-${Math.random().toString(36).slice(2,7)}`;
      const label = TOOL_ZH[tool.name] || tool.name;
      const icon = TOOL_ICON[tool.name] || "⚙";
      const card = mkEl("div", "tc-wrap");
      const elapsed = tool.elapsed || null;
      const badge = elapsed ? `<span class="tc-badge ok">${elapsed}s</span>` : `<span class="tc-badge ok">完成</span>`;
      card.innerHTML = `
        <div class="tc-header" onclick="tcToggle('${id}')">
          <span class="tc-icon">${icon}</span>
          <span class="tc-label">${label}</span>
          ${badge}
          <span class="tc-chevron" id="${id}-chev">▶</span>
        </div>
        <div class="tc-body" id="${id}-body" style="display:none">
          ${tool.args ? `<div class="tc-section-label">参数</div><pre class="tc-pre">${escHtml(JSON.stringify(tool.args, null, 2))}</pre>` : ""}
          ${tool.result ? `<div class="tc-section-label">结果</div><pre class="tc-pre">${escHtml(typeof tool.result === 'string' ? tool.result.slice(0,400) : JSON.stringify(tool.result,null,2).slice(0,400))}</pre>` : ""}
        </div>
      `;
      log.appendChild(card);
    });
  });

  if (!hasTools) {
    empty.style.display = "";
    empty.textContent = "暂无执行记录";
  }
}

function tcToggle(id) {
  const body = document.getElementById(`${id}-body`);
  const chev = document.getElementById(`${id}-chev`);
  if (!body) return;
  const open = body.style.display !== 'none';
  body.style.display = open ? 'none' : 'block';
  if (chev) chev.classList.toggle("open", !open);
}

async function saveSnapshot() {
  const s = liveKey ? SESS.get(liveKey) : (activeKey ? SESS.get(activeKey) : null);
  if (!s?.serverSid) return;
  const snap = { messages: s.history, token_total: s.tokens.total, token_prompt: s.tokens.prompt, token_compl: s.tokens.compl };
  await fetch(`/api/sessions/${s.serverSid}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(snap),
  }).catch(() => {});
}

// ── System panels ─────────────────────────────────────────────────────────────
const _panelLoaded = {};
function _lazyLoad(key, fn) {
  if (_panelLoaded[key]) return;
  _panelLoaded[key] = true;
  fn();
}

async function loadSystemPanels() {
  _loadSkills();   // pre-load skills count on sidebar
  _preloadCounts(); // pre-load count badges for other nav items
}

// Pre-load count badges without rendering full content
async function _preloadCounts() {
  try {
    const [tools, pkgs, know, mem] = await Promise.all([
      fetch("/api/tools").then(r => r.json()).catch(() => []),
      fetch("/api/packages").then(r => r.json()).catch(() => []),
      fetch("/api/knowledge").then(r => r.json()).catch(() => []),
      fetch("/api/memory").then(r => r.json()).catch(() => ({})),
    ]);
    const el = id => document.getElementById(id);
    if (el("sd-tools-count"))    el("sd-tools-count").textContent    = tools.length    || "";
    if (el("sd-packages-count")) el("sd-packages-count").textContent = pkgs.length     || "";
    if (el("sd-knowledge-count"))el("sd-knowledge-count").textContent= know.length     || "";
    const bp = (mem?.basin_profiles || []).length;
    if (el("sd-memory-count"))   el("sd-memory-count").textContent   = bp > 0 ? `${bp} 流域` : "";
  } catch(e) {}
}

// Panel metadata
const _PAGE_PANELS = {
  skills:   { title: "技能",    subtitle: "为您的智能体提供预封装且可重复的最佳实践与工具" },
  tools:    { title: "工具",    subtitle: "已注册的工具函数及优先级" },
  packages: { title: "水文包",   subtitle: "已集成的水文工具包，包括模型框架与数据读取库" },
  knowledge:{ title: "知识库",  subtitle: "水文领域结构化知识文件" },
  memory:   { title: "记忆",    subtitle: "跨会话记忆与流域档案" },
  datasets: { title: "数据集",  subtitle: "公共水文数据集与自定义数据集管理" },
  config:   { title: "模型配置",subtitle: "LLM 接口与参数配置" },
};
let _currentPanelId = null;

// Switch #main to panel view, hiding chat
function openPagePanel(id) {
  const meta = _PAGE_PANELS[id];
  if (!meta) return;
  _currentPanelId = id;
  document.getElementById("chat-view").style.display = "none";
  const pv = document.getElementById("panel-view");
  pv.style.display = "flex";
  document.getElementById("panel-view-title").textContent = meta.title;
  document.getElementById("panel-view-subtitle").textContent = meta.subtitle;
  const body = document.getElementById("panel-view-body");
  body.innerHTML = '<div class="s-empty">加载中...</div>';
  // Highlight active nav item
  document.querySelectorAll(".s-nav-item").forEach(el => el.classList.remove("active"));
  document.querySelectorAll(`.s-nav-item[onclick*="'${id}'"]`).forEach(el => el.classList.add("active"));
  // Deactivate session items
  document.querySelectorAll(".session-item").forEach(el => el.classList.remove("active"));
  switch(id) {
    case "skills":   __loadSkills();          break;
    case "tools":    __loadTools();          break;
    case "packages": __loadPackages();       break;
    case "knowledge":__loadKnowledge();      break;
    case "memory":   __loadMemory();         break;
    case "datasets": _loadDatasets();        break;
    case "config":   _loadConfig();          break;
  }
}

// Return to chat view (called when switching to a session)
function closeCurrentPanel() {
  _currentPanelId = null;
  document.getElementById("panel-view").style.display = "none";
  document.getElementById("chat-view").style.display = "flex";
  // Remove nav item highlights
  document.querySelectorAll(".s-nav-item").forEach(el => el.classList.remove("active"));
}

// Skills: simple list like tools (clicking a skill pastes its example into input)
async function __loadSkills() {
  const body = document.getElementById("panel-view-body");
  const countEl = document.getElementById("sd-skills-count");
  if (!body) return;
  try {
    const res = await fetch("/api/skills");
    if (!res.ok) throw new Error("fetch failed");
    const skills = await res.json();
    _skillsCache = skills;
    if (countEl) countEl.textContent = skills.length || "";
    if (!skills.length) { body.innerHTML = '<div class="panel-h2">可用技能</div><div class="s-empty">暂无技能</div>'; return; }
    const builtIn  = skills.filter(s => s.when_to_use);
    const custom   = skills.filter(s => !s.when_to_use);
    const renderSkillGroup = (label, list) => {
      if (!list.length) return "";
      return `<div class="panel-h3">${label}</div>` + list.map(s => {
        const kws   = (s.keywords || []).join("、");
        const tools = (s.tools || []).join(", ");
        const cnt   = s.content ? s.content.trim() : "";
        return `<details class="tool-item">
          <summary class="tool-item-summary">
            <span class="tool-item-name">${escHtml(s.name)}</span>
            <span class="tool-item-desc">${escHtml(s.description || "")}</span>
            <span class="s-item-badge tool-item-badge">${s.when_to_use ? "内置" : "自定义"}</span>
          </summary>
          <div class="tool-item-doc">
            <div class="item-code-id">skill: ${escHtml(s.id)}</div>
            ${s.when_to_use ? `<div class="item-detail-row">适用场景：${escHtml(s.when_to_use)}</div>` : ""}
            ${kws ? `<div class="item-detail-row">关键词：${escHtml(kws)}</div>` : ""}
            ${tools ? `<div class="item-detail-row">工具：<span style="font-family:var(--font-mono);font-size:.75rem">${escHtml(tools)}</span></div>` : ""}
            ${cnt ? `<pre class="tool-doc-pre" style="margin-top:6px">${escHtml(cnt)}</pre>` : ""}
          </div>
        </details>`;
      }).join("");
    };
    body.innerHTML = '<div class="panel-h2">可用技能</div>'
      + renderSkillGroup("内置技能", builtIn)
      + renderSkillGroup("自定义技能", custom);
  } catch(e) {
    if (body) body.innerHTML = '<div class="s-empty">加载失败</div>';
  }
}
function useSkill(name) {
  const s = _skillsCache.find(x => x.name === name);
  if (!s) return;
  const examples = s.example_queries && s.example_queries.length ? s.example_queries : getDefaultExamples(s.name);
  const inp = document.getElementById("input");
  if (inp && examples[0]) { inp.value = examples[0]; inp.focus(); }
  closeCurrentPanel();
}

async function _loadSkills() {
  const countEl = document.getElementById("sd-skills-count");
  try {
    const res = await fetch("/api/skills");
    if (!res.ok) throw new Error("fetch failed");
    const skills = await res.json();
    _skillsCache = skills;
    if (countEl) countEl.textContent = skills.length || "";
  } catch(e) {
    // silently fail — count badge stays empty
  }
}
let _skillsCache = [];

async function __loadTools() {
  const body = document.getElementById("panel-view-body");
  const countEl = document.getElementById("sd-tools-count");
  if (!body) return;
  try {
    const res = await fetch("/api/tools");
    if (!res.ok) throw new Error("fetch failed");
    const tools = await res.json();
    if (countEl) countEl.textContent = tools.length;
    if (!tools.length) { body.innerHTML = '<div class="panel-h2">已注册工具</div><div class="s-empty">暂无工具</div>'; return; }
    // Group by priority tier
    const core    = tools.filter(t => t.priority >= 20);
    const skill   = tools.filter(t => t.priority >= 10 && t.priority < 20);
    const dynamic = tools.filter(t => t.priority < 10);
    let html = '<div class="panel-h2">已注册工具</div>';
    const renderGroup = (label, list) => {
      if (!list.length) return "";
      return `<div class="panel-h3">${label}</div>` + list.map(t => {
        const zhName   = t.zh_name || TOOL_ZH[t.name] || t.name;
        const zhDesc   = t.zh_desc || TOOL_ZH_DESC[t.name] || "";
        const zhDetail = TOOL_ZH_DETAIL[t.name] || "";
        const tier     = TOOL_TIER[t.priority] || `p${t.priority}`;
        const hasDetail = zhDetail.length > 0 || (t.doc && t.doc.trim().length > 0);
        const detailContent = zhDetail || (t.doc ? t.doc.trim() : "");
        return `<details class="tool-item">
          <summary class="tool-item-summary">
            <span class="tool-item-name">${escHtml(zhName)}</span>
            <span class="tool-item-desc">${zhDesc ? escHtml(zhDesc) : ""}</span>
            <span class="s-item-badge tool-item-badge">${tier}</span>
          </summary>
          <div class="tool-item-doc">
            <div class="item-code-id">function: ${escHtml(t.name)}</div>
            ${detailContent ? `<pre class="tool-doc-pre" style="margin-top:5px">${escHtml(detailContent)}</pre>` : ""}
          </div>
        </details>`;
      }).join("");
    };
    html += renderGroup("核心工具", core) + renderGroup("技能工具", skill) + renderGroup("动态工具", dynamic);
    body.innerHTML = html;
  } catch (e) {
    body.innerHTML = '<div class="s-empty">加载失败</div>';
    if (countEl) countEl.textContent = "";
  }
}

async function __loadPackages() {
  const body = document.getElementById("panel-view-body");
  const countEl = document.getElementById("sd-packages-count");
  if (!body) return;
  try {
    const res = await fetch("/api/packages");
    if (!res.ok) throw new Error("fetch failed");
    const pkgs = await res.json();
    if (countEl) countEl.textContent = pkgs.filter(p => p.installed).length || "";

    const ROLE_LABEL = { model: "模型框架", data: "数据读取", adapter: "适配器" };
    const installedPkgs = pkgs.filter(p => p.installed);
    const missingPkgs   = pkgs.filter(p => !p.installed);

    let html = '<div class="panel-h2">已安装水文包</div>';
    if (!installedPkgs.length) html += '<div class="s-empty">暂无已安装水文包</div>';
    html += installedPkgs.map(p => {
      const ops = Array.isArray(p.operations) ? p.operations : [];
      const opListHtml = ops.length ? `
        <div class="pkg-op-list">
          ${ops.map(op => {
            const toolName = OP_TO_TOOL[op] || op;
            const zhName   = TOOL_ZH[toolName] || toolName;
            const zhDesc   = TOOL_ZH_DESC[toolName] || "";
            return `<div class="pkg-op-item">
              <span class="pkg-op-fn">${escHtml(toolName)}</span>
              <span class="pkg-op-zh">${escHtml(zhName)}</span>
              ${zhDesc ? `<span class="pkg-op-desc">${escHtml(zhDesc)}</span>` : ""}
            </div>`;
          }).join("")}
        </div>` : "";
      const detailHtml = p.detail
        ? `<div class="item-detail-row" style="margin-top:${ops.length ? "8px" : "0"}">${escHtml(p.detail)}</div>`
        : "";
      return `
      <details class="tool-item">
        <summary class="tool-item-summary">
          <span class="tool-item-name">${escHtml(p.label || p.name)}</span>
          <span class="tool-item-desc">${escHtml(p.description)}</span>
          <span class="s-item-badge badge-ready" style="flex-shrink:0">${escHtml(ROLE_LABEL[p.role] || p.role)}</span>
          ${p.version ? `<span class="s-item-badge" style="flex-shrink:0">v${escHtml(p.version)}</span>` : ""}
        </summary>
        ${(opListHtml || detailHtml) ? `<div class="tool-item-doc">
          <div class="item-code-id">adapter: ${escHtml(p.name)}</div>
          ${opListHtml}${detailHtml}
        </div>` : ""}
      </details>`;
    }).join("");

    if (missingPkgs.length) {
      html += '<div class="panel-h2">未安装（可选）</div>';
      html += missingPkgs.map(p => `
        <div class="s-item">
          <span class="s-item-name">${escHtml(p.label || p.name)}</span>
          <span class="tool-item-desc" style="flex:1;color:var(--text2);font-size:.78rem">${escHtml(p.description)}</span>
          <span class="s-item-badge badge-gray">未安装</span>
          <button class="s-btn s-btn-xs" onclick="installPkg('${escHtml(p.pip_name).replace(/'/g,"&#39;")}')">安装</button>
        </div>`).join("");
    }

    html += `<div class="panel-h2" style="display:flex;align-items:center;justify-content:space-between">
        <span>安装自定义包</span>
      </div>
      <div class="s-add-form">
        <input class="s-input" id="pkg-install-name" placeholder="包名或 pip 安装字符串，例：hydrotools==1.0.0">
        <button class="s-btn s-btn-primary" onclick="installPkg()">pip install</button>
        <div id="pkg-install-msg" style="font-size:.76rem;padding:3px 0;color:var(--text2)"></div>
      </div>`;

    body.innerHTML = html;
  } catch (e) {
    body.innerHTML = '<div class="s-empty">加载失败</div>';
    if (countEl) countEl.textContent = "";
  }
}

async function installPkg(pkgName) {
  const nameEl = document.getElementById("pkg-install-name");
  const pkg = pkgName || nameEl?.value.trim();
  const msgEl = document.getElementById("pkg-install-msg");
  if (!pkg) { if (msgEl) msgEl.textContent = "请填写包名"; return; }
  if (msgEl) msgEl.textContent = `正在安装 ${pkg}…`;
  try {
    const res = await fetch("/api/packages/install", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ package: pkg }),
    });
    const data = await res.json();
    if (!data.ok) { if (msgEl) msgEl.textContent = "错误: " + (data.error || "未知"); return; }
    // Poll
    let tries = 0;
    const poll = async () => {
      if (tries++ > 60) { if (msgEl) msgEl.textContent = "安装超时，请手动检查"; return; }
      const sr = await fetch(`/api/packages/install-status?package=${encodeURIComponent(pkg)}`).catch(() => null);
      if (!sr) { setTimeout(poll, 3000); return; }
      const sd = await sr.json();
      if (sd.status === "ok") {
        if (msgEl) msgEl.textContent = `${pkg} 安装成功，刷新页面后生效`;
        await __loadPackages();
      } else if (sd.status?.startsWith("error:")) {
        if (msgEl) msgEl.textContent = "安装失败: " + sd.status.slice(6);
      } else {
        setTimeout(poll, 3000);
      }
    };
    setTimeout(poll, 3000);
  } catch (e) {
    if (msgEl) msgEl.textContent = "请求失败: " + e.message;
  }
}

async function __loadKnowledge() {
  const body = document.getElementById("panel-view-body");
  const countEl = document.getElementById("sd-knowledge-count");
  if (!body) return;
  try {
    const res = await fetch("/api/knowledge");
    if (!res.ok) throw new Error("fetch failed");
    const items = await res.json();
    if (countEl) countEl.textContent = items.length;
    if (!items.length) { body.innerHTML = '<div class="panel-h2">领域知识文件</div><div class="s-empty">暂无知识文件</div>'; return; }
    body.innerHTML = '<div class="panel-h2">领域知识文件</div>'
      + items.map(k => {
        const safeName = escHtml(k.name).replace(/'/g,"&#39;");
        const safeId   = escHtml(k.name).replace(/\./g,"-").replace(/[^a-zA-Z0-9_-]/g,"_");
        const zhTitle = KNOW_ZH[k.name] || k.title || k.name;
        return `
      <details class="tool-item know-item" id="know-${safeId}" ontoggle="onKnowToggle(event,'${safeName}','${safeId}')">
        <summary class="tool-item-summary know-summary">
          <span class="know-title">${escHtml(zhTitle)}</span>
          <span class="tool-item-desc"></span>
          <span class="know-filename">${escHtml(k.name)}</span>
        </summary>
        <div class="know-body" id="know-body-${safeId}">
          <div class="s-empty" style="font-style:normal">点击展开加载内容</div>
        </div>
      </details>`;
      }).join("");
  } catch (e) {
    body.innerHTML = '<div class="s-empty">加载失败</div>';
    if (countEl) countEl.textContent = "";
  }
}

function onKnowToggle(event, name, safeId) {
  if (!event.target.open) return;
  const bodyEl = document.getElementById(`know-body-${safeId}`);
  if (!bodyEl || bodyEl.dataset.loaded) return;
  bodyEl.dataset.loaded = "1";
  bodyEl.innerHTML = `<div class="s-empty" style="font-style:normal">加载中...</div>`;
  fetch(`/api/knowledge/${encodeURIComponent(name)}`)
    .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
    .then(data => {
      const mdHtml = (typeof marked !== "undefined")
        ? marked.parse(data.content || "")
        : `<pre class="tool-doc-pre">${escHtml(data.content || "")}</pre>`;
      bodyEl.innerHTML = `<div class="know-content"><div class="item-code-id" style="margin-bottom:8px">file: ${escHtml(name)}</div>${mdHtml}</div>`;
    })
    .catch(e => {
      bodyEl.dataset.loaded = "";  // allow retry on next open
      bodyEl.innerHTML = `<div class="s-empty">加载失败: ${escHtml(e.message)}</div>`;
    });
}

async function __loadMemory() {
  const body = document.getElementById("panel-view-body");
  const countEl = document.getElementById("sd-memory-count");
  if (!body) return;
  try {
    const res = await fetch("/api/memory");
    if (!res.ok) throw new Error("fetch failed");
    const data = await res.json();
    const bpCount = (data.basin_profiles || []).length;
    if (countEl) countEl.textContent = bpCount > 0 ? `${bpCount} 流域` : "";

    let html = "";
    html += '<div class="panel-h2">工作区记忆</div>';
    if (data.memory_text) {
      const preview = data.memory_text.split("\n").slice(0, 8).join("\n").trim();
      html += `<div class="s-item s-item-col"><span class="s-item-name">MEMORY.md</span><pre class="s-item-pre">${escHtml(preview)}</pre></div>`;
    } else {
      html += '<div class="s-empty">无工作区记忆</div>';
    }
    if (bpCount > 0) {
      html += '<div class="panel-h2">流域档案</div>';
      html += data.basin_profiles.map(bp => `
        <div class="s-item">
          <span class="s-item-name">${escHtml(bp.basin_id)}</span>
          <span class="s-item-badge">${escHtml(bp.model || "")}</span>
          ${bp.nse != null ? `<span class="s-item-badge" style="color:var(--ok)">NSE ${Number(bp.nse).toFixed(3)}</span>` : ""}
        </div>
      `).join("");
    }
    body.innerHTML = html;
  } catch (e) {
    body.innerHTML = '<div class="s-empty">加载失败</div>';
    if (countEl) countEl.textContent = "";
  }
}

// ── Datasets panel ────────────────────────────────────────────────────────────
const _DS_FORMAT_HELP = `
<div class="ds-help-box">
  <div class="ds-help-title">目录结构要求</div>
  <pre class="ds-help-pre">数据集根目录/
├── attributes/
│   └── attributes.csv          # 必需：basin_id, area 等属性
├── timeseries/
│   ├── 1D/                     # 按时间单位命名的子目录
│   │   ├── 01013500.csv        # 每个流域一个文件（文件名=basin_id）
│   │   └── ...
│   └── 1D_units_info.json      # 各列的单位说明
└── shapes/                     # 可选：流域边界 shapefile</pre>
  <div class="ds-help-title" style="margin-top:10px">attributes.csv 示例</div>
  <pre class="ds-help-pre">basin_id,area,elevation
01013500,1234.5,850.2
01022500,2340.8,920.1</pre>
  <div class="ds-help-title" style="margin-top:10px">timeseries/1D/01013500.csv 示例</div>
  <pre class="ds-help-pre">time,precipitation,temperature,streamflow
2000-01-01,5.2,15.3,12.4
2000-01-02,0.0,16.1,11.8</pre>
  <div class="ds-help-title" style="margin-top:10px">1D_units_info.json 示例</div>
  <pre class="ds-help-pre">{"precipitation":"mm/d","temperature":"°C","streamflow":"mm/d"}</pre>
</div>`;

async function _loadDatasets() {
  const body = document.getElementById("panel-view-body");
  if (!body) return;
  try {
    const res = await fetch("/api/datasets");
    if (!res.ok) throw new Error("fetch failed");
    const data = await res.json();
    let html = "";

    // Public datasets
    html += '<div class="panel-h2">公开数据集</div>';
    (data.public || []).forEach(d => {
      const ready = d.status === "ready";
      const units = Array.isArray(d.time_units) ? d.time_units : [];
      const unitBadges = units.map(u =>
        `<span class="s-item-badge badge-gray" style="font-size:.72rem">${escHtml(u)}</span>`
      ).join("");
      html += `
        <div class="s-item">
          <span class="s-item-name">${escHtml(d.label)}</span>
          ${unitBadges}
          <span class="s-item-meta">${d.region} · ${d.basins} 流域 · ${d.size}</span>
          <span class="s-item-badge ${ready ? "badge-ready" : "badge-gray"}">${ready ? "就绪" : "未下载"}</span>
        </div>
      `;
    });

    // Custom datasets
    if (data.custom && data.custom.length > 0) {
      html += '<div class="panel-h2">自定义数据集</div>';
      data.custom.forEach(d => {
        // unique key per (dataset_name, time_unit)
        const dsKey = d.dataset_name + "__" + (d.time_unit || "");
        const isCaching = (window._dsCache || {})[dsKey] === "caching";
        let statusLabel, statusCls;
        if (isCaching) {
          statusLabel = "转换中..."; statusCls = "badge-warn";
        } else if (d.cache_status === "cached") {
          statusLabel = "就绪"; statusCls = "badge-ready";
        } else if (d.cache_status === "uncached") {
          statusLabel = "未转换"; statusCls = "badge-warn";
        } else {
          statusLabel = "路径缺失"; statusCls = "badge-gray";
        }
        const canCache = !isCaching && d.cache_status !== "missing";
        const cacheBtnLabel = d.cache_status === "cached" ? "重新转NC" : "转为NC";
        const safeN = escHtml(d.dataset_name).replace(/'/g,"&#39;");
        const safeU = escHtml(d.time_unit || "").replace(/'/g,"&#39;");
        html += `
          <div class="s-item" id="ds-item-${escHtml(dsKey)}">
            <span class="s-item-name">${escHtml(d.dataset_name)}</span>
            ${d.time_unit ? `<span class="s-item-badge badge-gray" style="font-size:.72rem;margin-left:4px">${escHtml(d.time_unit)}</span>` : ""}
            ${d.basin_count ? `<span class="s-item-meta">${d.basin_count} 流域</span>` : ""}
            <span class="s-item-badge ${statusCls}" id="ds-badge-${escHtml(dsKey)}">${statusLabel}</span>
            ${canCache ? `<button class="s-btn s-btn-xs" onclick="cacheDataset('${safeN}','${safeU}',${d.cache_status === "cached"})">${cacheBtnLabel}</button>` : ""}
            <button class="s-item-del-btn" title="删除此条目" onclick="deleteCustomDataset('${safeN}','${safeU}')">×</button>
          </div>
        `;
      });
    }

    // Add custom dataset form
    html += `<div class="panel-h2" style="display:flex;align-items:center;justify-content:space-between">
        <span>添加自定义数据集</span>
        <button class="s-btn s-btn-xs" onclick="toggleDsHelp()">数据格式说明</button>
      </div>
      <div class="s-add-form" id="custom-ds-form">
        <div></div>
        <div id="ds-help-panel" style="display:none">${_DS_FORMAT_HELP}</div>
        <input class="s-input" id="cds-path" placeholder="父目录路径，例：D:\\project\\data（数据集文件夹的上一级）">
        <input class="s-input" id="cds-name" placeholder="数据集名称，即父目录下的文件夹名，例：songliao_event">
        <select class="s-input" id="cds-unit">
          <option value="1D">1D（日数据）</option>
          <option value="1h">1h（小时数据）</option>
          <option value="3h">3h（3小时数据）</option>
          <option value="8D">8D（8日数据）</option>
        </select>
        <button class="s-btn s-btn-primary" onclick="addCustomDataset()">验证并转换为NC</button>
        <div id="cds-msg" style="font-size:.76rem;padding:4px 0;color:var(--text2)"></div>
      </div>
    `;

    body.innerHTML = html;
  } catch (e) {
    body.innerHTML = '<div class="s-empty">加载失败</div>';
  }
}

function toggleDsHelp() {
  const el = document.getElementById("ds-help-panel");
  if (el) el.style.display = el.style.display === "none" ? "block" : "none";
}

async function addCustomDataset() {
  const path = document.getElementById("cds-path")?.value.trim();
  const name = document.getElementById("cds-name")?.value.trim();
  const unit = document.getElementById("cds-unit")?.value || "1D";
  const msgEl = document.getElementById("cds-msg");
  if (!path || !name) { if (msgEl) msgEl.textContent = "请填写路径和名称"; return; }
  if (msgEl) msgEl.textContent = "验证中...";
  try {
    const res = await fetch("/api/datasets/custom", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data_path: path, dataset_name: name, time_unit: unit }),
    });
    const data = await res.json();
    if (!data.success) {
      if (msgEl) {
        msgEl.textContent = "错误: " + (data.error || "未知错误");
        if (data.detail) {
          msgEl.title = data.detail;  // hover shows full traceback
          msgEl.style.cursor = "help";
          // Also log to console for easy debugging
          console.error("[dataset NC]", data.detail);
        }
      }
      return;
    }
    if (msgEl) msgEl.textContent = `结构验证通过${data.basin_count ? "，发现 " + data.basin_count + " 个流域" : ""}，正在转换为NC文件…`;
    await _loadDatasets();
    // Start NC caching
    cacheDataset(name, msgEl);
  } catch (e) {
    if (msgEl) msgEl.textContent = "请求失败: " + e.message;
  }
}

// Track ongoing cache tasks
window._dsCache = window._dsCache || {};

async function cacheDataset(name, time_unit, isOverwrite, msgEl) {
  window._dsCache = window._dsCache || {};
  const dsKey = name + "__" + (time_unit || "");
  window._dsCache[dsKey] = "caching";
  const badge = document.getElementById(`ds-badge-${dsKey}`);
  if (badge) { badge.textContent = "转换中..."; badge.className = "s-item-badge badge-warn"; }
  if (!msgEl) msgEl = document.getElementById("cds-msg");
  try {
    const url = `/api/datasets/custom/${encodeURIComponent(name)}/cache` +
                (time_unit ? `?time_unit=${encodeURIComponent(time_unit)}` : "");
    const res = await fetch(url, { method: "POST" });
    const data = await res.json();
    if (!data.ok) {
      window._dsCache[dsKey] = "error";
      if (msgEl) msgEl.textContent = "启动失败: " + (data.error || "未知错误");
      return;
    }
    if (data.was_cached && msgEl) {
      msgEl.textContent = `${name}（${time_unit}）：已有 NC 缓存，覆盖重新生成中…`;
    }
    _pollCacheStatus(name, time_unit, msgEl);
  } catch (e) {
    window._dsCache[dsKey] = "error";
    if (msgEl) msgEl.textContent = "请求失败: " + e.message;
  }
}

async function _pollCacheStatus(name, time_unit, msgEl) {
  const dsKey = name + "__" + (time_unit || "");
  let attempts = 0;
  const maxAttempts = 180; // up to 15 min (5s interval)
  const poll = async () => {
    if (attempts++ > maxAttempts) {
      if (msgEl) msgEl.textContent = "转换超时，请检查数据格式后重试";
      return;
    }
    try {
      const url = `/api/datasets/custom/${encodeURIComponent(name)}/cache-status` +
                  (time_unit ? `?time_unit=${encodeURIComponent(time_unit)}` : "");
      const res = await fetch(url);
      const data = await res.json();
      if (data.status === "ready" || data.cached) {
        window._dsCache[dsKey] = "ready";
        if (msgEl) msgEl.textContent = `NC 转换完成（${time_unit || name}），数据集就绪！`;
        await _loadDatasets();
        return;
      }
      if (data.status && data.status.startsWith("error:")) {
        window._dsCache[dsKey] = "error";
        if (msgEl) msgEl.textContent = "转换失败: " + data.status.slice(6);
        await _loadDatasets();
        return;
      }
    } catch (_) {}
    setTimeout(poll, 5000);
  };
  setTimeout(poll, 5000);
}

async function deleteCustomDataset(name, time_unit) {
  const label = time_unit ? `"${name}"（${time_unit}）` : `"${name}"`;
  if (!confirm(`确定删除自定义数据集 ${label}？`)) return;
  const url = `/api/datasets/custom/${encodeURIComponent(name)}` +
              (time_unit ? `?time_unit=${encodeURIComponent(time_unit)}` : "");
  await fetch(url, { method: "DELETE" }).catch(() => {});
  _loadDatasets();
}

// ── Config panel ──────────────────────────────────────────────────────────────
async function _loadConfig() {
  const body = document.getElementById("panel-view-body");
  if (!body) return;
  try {
    const res = await fetch("/api/config");
    if (!res.ok) throw new Error("fetch failed");
    const cfg = await res.json();
    const keyPlaceholder = cfg.api_key_set ? cfg.api_key_masked : "输入 API Key…";
    body.innerHTML = `
      <div class="panel-h2">LLM 配置</div>
      <div class="s-form">
        <label class="s-form-label">模型名称</label>
        <input class="s-input" id="cfg-model" value="${escHtml(cfg.model || "")}">
        <label class="s-form-label">API Base URL</label>
        <input class="s-input" id="cfg-base-url" value="${escHtml(cfg.base_url || "")}">
        <label class="s-form-label">API Key ${cfg.api_key_set ? '<span style="color:var(--ok);font-size:.75rem">✓ 已配置</span>' : '<span style="color:var(--text2);font-size:.75rem">未配置</span>'}</label>
        <div style="display:flex;gap:6px;align-items:center">
          <input class="s-input" id="cfg-api-key" type="password" placeholder="${escHtml(keyPlaceholder)}" autocomplete="new-password" style="flex:1">
          <button class="s-btn" style="white-space:nowrap;padding:6px 10px;font-size:.78rem"
            onclick="(()=>{const i=document.getElementById('cfg-api-key');i.type=i.type==='password'?'text':'password'})()">显示</button>
        </div>
        <div style="font-size:.74rem;color:var(--text2);margin:-4px 0 6px">留空则不修改已有密钥</div>
        <label class="s-form-label">Temperature <span id="cfg-temp-val">${Number(cfg.temperature || 0.1).toFixed(2)}</span></label>
        <input type="range" class="s-range" id="cfg-temperature" min="0" max="2" step="0.01" value="${cfg.temperature || 0.1}"
          oninput="document.getElementById('cfg-temp-val').textContent=Number(this.value).toFixed(2)">
        <label class="s-form-label">最大轮次 (max_turns)</label>
        <input class="s-input" id="cfg-max-turns" type="number" min="1" max="100" value="${cfg.max_turns || 30}">
        <button class="s-btn s-btn-primary" onclick="saveConfig()">保存配置</button>
        <div id="cfg-msg" style="font-size:.76rem;padding:2px 0;color:var(--text2)"></div>
      </div>
    `;
  } catch (e) {
    body.innerHTML = '<div class="s-empty">加载失败</div>';
  }
}

async function saveConfig() {
  const model      = document.getElementById("cfg-model")?.value.trim();
  const baseUrl    = document.getElementById("cfg-base-url")?.value.trim();
  const apiKey     = document.getElementById("cfg-api-key")?.value.trim();
  const temperature = parseFloat(document.getElementById("cfg-temperature")?.value || "0.1");
  const maxTurns   = parseInt(document.getElementById("cfg-max-turns")?.value || "30", 10);
  const msgEl      = document.getElementById("cfg-msg");
  const payload = { model, base_url: baseUrl, temperature, max_turns: maxTurns };
  if (apiKey) payload.api_key = apiKey;  // only send if non-empty
  try {
    const res = await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (data.ok) {
      if (msgEl) msgEl.textContent = "已保存（重启后生效）";
    } else {
      if (msgEl) msgEl.textContent = "保存失败";
    }
  } catch (e) {
    if (msgEl) msgEl.textContent = "请求失败: " + e.message;
  }
}

function getDefaultExamples(name) {
  const map = {
    calibration: ["率定GR4J模型，流域12025000", "用SCE-UA算法率定GR6J，流域01013500"],
    llm_calibration: ["用LLM智能率定GR4J，流域12025000"],
    evaluation: ["评估模型结果，流域12025000"],
  };
  for (const k of Object.keys(map)) { if (name.toLowerCase().includes(k)) return map[k]; }
  return [name + " 流域12025000"];
}

function openCreateSkill() {
  document.getElementById("cs-name").value = "";
  document.getElementById("cs-desc").value = "";
  document.getElementById("cs-when").value = "";
  document.getElementById("create-skill-modal").classList.add("open");
}

function closeCreateSkillModal(e) {
  if (e && e.target !== document.getElementById("create-skill-modal")) return;
  document.getElementById("create-skill-modal").classList.remove("open");
}

function submitCreateSkill() {
  const name = document.getElementById("cs-name").value.trim();
  const desc = document.getElementById("cs-desc").value.trim();
  const when = document.getElementById("cs-when").value.trim();
  if (!name || !desc) { showToast("请填写技能名称和功能描述"); return; }
  document.getElementById("create-skill-modal").classList.remove("open");
  closeCurrentPanel();
  const parts = [`请帮我创建一个新技能：\n名称：${name}\n描述：${desc}`];
  if (when) parts.push(`适用场景：${when}`);
  const inp = document.getElementById("input");
  inp.value = parts.join("\n");
  inp.focus();
  inp.dispatchEvent(new Event("input"));
  showToast("技能描述已填入，点击发送创建");
}


// ── Prior messages ────────────────────────────────────────────────────────────
function buildPrior() {
  const history = activeSess()?.history || [];
  return history.slice(-10).map(m => {
    if (m.role === "user") return { role: "user", content: m.content };
    const extras = (m.tools || []).flatMap(t => {
      const r = t.result || {}, out = [];
      if (r.calibration_dir) out.push(`calibration_dir=${r.calibration_dir}`);
      const nse = r.metrics?.NSE;
      if (typeof nse === "number") out.push(`NSE=${nse.toFixed(4)}`);
      return out;
    });
    const extra = extras.length ? `\n\n[Previous results: ${extras.join("; ")}]` : "";
    return { role: "assistant", content: (m.content || "") + extra };
  });
}

// ── New chat ──────────────────────────────────────────────────────────────────
document.getElementById("new-chat-btn").onclick = () => {
  closeCurrentPanel();
  const key = createAndSwitchNew();
  updateTokenDisplay();
  setStatus("待命");
  if (!liveKey) {
    document.getElementById("exec-log").innerHTML = '<div id="exec-empty">暂无执行记录</div>';
  }
  document.querySelectorAll(".session-item").forEach(e => e.classList.remove("active"));
};

// ── Keyboard ──────────────────────────────────────────────────────────────────
document.getElementById("input").addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendQuery(); }
});
document.getElementById("input").addEventListener("input", function() {
  this.style.height = "auto";
  this.style.height = Math.min(this.scrollHeight, 120) + "px";
});

// ── Tool card toggle ──────────────────────────────────────────────────────────
function toggleCard(id) {
  const body = document.getElementById(`${id}-body`);
  const chev = document.getElementById(`${id}-chev`);
  if (!body) return;
  const open = body.classList.toggle("open");
  if (chev) chev.classList.toggle("open", open);
}

// ── Lightbox ──────────────────────────────────────────────────────────────────
function openLightbox(src) { document.getElementById("lightbox-img").src = src; document.getElementById("lightbox").classList.add("open"); }
function closeLightbox() { document.getElementById("lightbox").classList.remove("open"); }

// ── Utils ─────────────────────────────────────────────────────────────────────
function mkEl(tag, cls) { const el = document.createElement(tag); if (cls) el.className = cls; return el; }
function escHtml(s) { return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }
function scrollBottom() { const w = document.getElementById("messages-wrap"); requestAnimationFrame(() => { w.scrollTop = w.scrollHeight; }); }

// ── Init ──────────────────────────────────────────────────────────────────────
createAndSwitchNew(); // start with one empty session
connect();
loadSessions();
loadSystemPanels();
