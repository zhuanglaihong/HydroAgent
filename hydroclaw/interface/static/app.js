marked.setOptions({ breaks: true, gfm: true });

const TOOL_ZH = {
  validate_basin:"验证流域数据", calibrate_model:"执行模型率定", evaluate_model:"评估模型性能",
  visualize:"生成可视化", llm_calibrate:"LLM 智能率定", batch_calibrate:"批量率定",
  compare_models:"多模型对比", generate_code:"生成分析代码", run_code:"执行分析脚本",
  create_skill:"创建新技能", read_file:"读取文件", inspect_dir:"查看目录",
  ask_user:"向用户提问", search_memory:"检索历史记忆", save_basin_profile:"保存流域档案",
};
const TOOL_ICON = {
  calibrate_model:"⚙", evaluate_model:"📊", llm_calibrate:"🤖",
  visualize:"📈", validate_basin:"✅", batch_calibrate:"🔄",
  compare_models:"⚖", generate_code:"💻", run_code:"▶",
  create_skill:"✨", read_file:"📄", inspect_dir:"📁",
  ask_user:"❓", search_memory:"🔍", save_basin_profile:"💾",
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
async function loadSessions() {
  const res = await fetch("/api/sessions").catch(() => null);
  if (!res || !res.ok) return;
  const sessions = await res.json();
  const el = document.getElementById("session-list");
  el.innerHTML = "";
  const as = activeSess();
  const ls = liveSess();
  sessions.slice(0, 40).forEach(s => {
    const item = mkEl("div", "session-item");
    item.title = `${s.timestamp?.slice(0,16).replace("T"," ")}  |  ${s.tool_calls || 0} tools`;
    item.dataset.sid = s.session_id;
    item.dataset.key = "";  // placeholder
    const nameSpan = mkEl("span", "session-name");
    nameSpan.textContent = s.query || "(无标题)";
    item.appendChild(nameSpan);
    // Active state
    if (as?.serverSid === s.session_id) item.classList.add("active");
    // Running dot for live session
    if (ls?.serverSid === s.session_id) {
      const dot = mkEl("span", "running-dot");
      item.insertBefore(dot, nameSpan);
    }
    item.onclick = () => loadHistorySession(s.session_id);
    el.appendChild(item);
  });
  // Scroll list to top (newest sessions are first)
  el.scrollTop = 0;
}

async function loadHistorySession(sid) {
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
        // New format: interleaved thought → tool → thought → tool → (final thought)
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

// ── Skills Panel ──────────────────────────────────────────────────────────────
let _allSkills = [];

function openSkillsPanel() {
  document.getElementById("skills-panel").style.display = "flex";
  if (_allSkills.length === 0) fetchSkillCards();
}
function closeSkillsPanel() {
  document.getElementById("skills-panel").style.display = "none";
}
// Close on backdrop click
document.getElementById("skills-panel").addEventListener("click", function(e) {
  if (e.target === this) closeSkillsPanel();
});

function fetchSkillCards() {
  fetch("/api/skills").then(r => r.json()).then(skills => {
    _allSkills = skills;
    renderSkillCards(skills);
  }).catch(() => {});
}

function filterSkillCards() {
  const q = document.getElementById("skills-search").value.toLowerCase();
  renderSkillCards(q ? _allSkills.filter(s =>
    s.name.toLowerCase().includes(q) || s.description.toLowerCase().includes(q)
  ) : _allSkills);
}

function renderSkillCards(skills) {
  const grid = document.getElementById("skills-grid");
  grid.innerHTML = "";
  if (!skills.length) {
    grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;color:var(--text2);padding:40px">暂无技能</div>';
    return;
  }
  skills.forEach(s => {
    const card = document.createElement("div");
    card.className = "skill-card";
    card.innerHTML = `
      <div class="skill-card-header">
        <div class="skill-card-name">
          <span class="skill-card-icon">⚙</span>
          <span>${escHtml(s.name)}</span>
        </div>
        <div class="skill-toggle" title="已启用"></div>
      </div>
      <div class="skill-card-desc">${escHtml(s.description || "暂无描述")}</div>
      <div class="skill-card-meta">
        <span class="skill-badge">内置</span>
        <span>·</span>
        <span>${s.when_to_use ? escHtml(s.when_to_use.slice(0, 40)) + (s.when_to_use.length > 40 ? "…" : "") : ""}</span>
      </div>
    `;
    // Toggle click: visual only (skills are always active in HydroClaw)
    const toggle = card.querySelector(".skill-toggle");
    toggle.addEventListener("click", e => {
      e.stopPropagation();
      toggle.classList.toggle("off");
      toggle.title = toggle.classList.contains("off") ? "已禁用" : "已启用";
    });
    card.addEventListener("click", e => {
      if (e.target === toggle) return;
      showSkillDetail(s);
    });
    grid.appendChild(card);
  });
}

function showSkillDetail(s) {
  document.getElementById("skill-modal-title").textContent = s.name;
  document.getElementById("skill-modal-desc").textContent = s.description || "";
  document.getElementById("skill-modal-body").innerHTML =
    (s.when_to_use ? `<p><strong>适用场景：</strong>${escHtml(s.when_to_use)}</p>` : "") +
    `<p><strong>示例：</strong></p><ul>` +
    (s.example_queries || getDefaultExamples(s.name)).map(q =>
      `<li><code>${escHtml(q)}</code></li>`).join("") +
    `</ul>`;
  document.getElementById("skill-use-btn").onclick = () => {
    closeSkillModal();
    closeSkillsPanel();
    const ex = (s.example_queries || getDefaultExamples(s.name))[0];
    if (ex) { const inp = document.getElementById("input"); inp.value = ex; inp.focus(); }
  };
  document.getElementById("skill-modal").classList.add("open");
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
  closeSkillsPanel();
  const parts = [`请帮我创建一个新技能：\n名称：${name}\n描述：${desc}`];
  if (when) parts.push(`适用场景：${when}`);
  const inp = document.getElementById("input");
  inp.value = parts.join("\n");
  inp.focus();
  inp.dispatchEvent(new Event("input"));
  showToast("技能描述已填入，点击发送创建");
}

function closeSkillModal(e) {
  if (e && e.target !== document.getElementById("skill-modal")) return;
  document.getElementById("skill-modal").classList.remove("open");
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
