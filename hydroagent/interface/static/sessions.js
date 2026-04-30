// sessions.js — Session state, switching, history loading, exec panel restore.
// Depends on: utils.js (mkEl, escHtml, scrollBottom, showToast, TOOL_ZH, TOOL_ICON)
// Runtime deps: injectInlineImages, openLightbox (chat.js/app.js)

// ── Session state ──────────────────────────────────────────────────────────────
// Each session: { el, history, live, tokens, serverSid }
const SESS = new Map();
let activeKey = null;
let liveKey   = null;
let _keySeq   = 0;

function newKey() { return `s${++_keySeq}`; }

function newSessData() {
  const el = document.createElement("div");
  el.style.cssText = "display:contents";  // transparent to flex layout so .msg aligns in #messages-wrap
  return { el, history: [], live: null, tokens: { total: 0, prompt: 0, compl: 0 }, runCount: 0, serverSid: null };
}

function liveSess()   { return liveKey   ? SESS.get(liveKey)   : null; }
function activeSess() { return activeKey ? SESS.get(activeKey) : null; }
function isLiveActive() { return liveKey === activeKey; }

function switchDisplay(key) {
  const wrap = document.getElementById("messages-wrap");
  // Detach current
  if (activeKey) {
    const prev = SESS.get(activeKey);
    if (prev?.el?.parentNode === wrap) wrap.removeChild(prev.el);
  }
  activeKey = key;
  const s = SESS.get(key);
  if (s) wrap.appendChild(s.el);
  // Mark active session in sidebar
  document.querySelectorAll(".session-item").forEach(el => {
    el.classList.toggle("active", el.dataset.sid === s?.serverSid);
  });
  updateTokenDisplay();
  scrollBottom();
}

function createAndSwitchNew() {
  const key = newKey();
  SESS.set(key, newSessData());
  switchDisplay(key);
  return key;
}

// ── Session context menu ───────────────────────────────────────────────────────
let _sessMenuSid = null;
let _sessMenuEl  = null;

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

  const pinned = sessions.filter(s => s.pinned);
  const rest   = sessions.filter(s => !s.pinned);
  const sorted = [...pinned, ...rest].slice(0, 10);

  sorted.forEach(s => {
    const item = mkEl("div", "session-item");
    item.title = `${s.timestamp?.slice(0,16).replace("T"," ")}  |  ${s.tool_calls || 0} tools`;
    item.dataset.sid = s.session_id;
    item.dataset.key = "";

    if (s.pinned) {
      const pinIcon = mkEl("span", "sess-pin-icon");
      pinIcon.textContent = "[pin]";
      item.appendChild(pinIcon);
    }

    const nameSpan = mkEl("span", "session-name");
    nameSpan.textContent = s.title || s.query || "(无标题)";
    item.appendChild(nameSpan);

    const moreBtn = mkEl("button", "sess-more-btn");
    moreBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="12" cy="19" r="2"/></svg>';
    moreBtn.title = "重命名 / 置顶 / 删除";
    moreBtn.addEventListener("click", e => {
      e.stopPropagation();
      _openSessMenu(s.session_id, s, moreBtn, item, nameSpan);
    });
    item.appendChild(moreBtn);

    if (as?.serverSid === s.session_id) item.classList.add("active");
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
  inp.type = "text"; inp.className = "sess-rename-input"; inp.value = oldText;
  nameSpan.replaceWith(inp); inp.focus(); inp.select();

  const okBtn = mkEl("button", "sess-rename-ok"); okBtn.textContent = "OK";
  const cancelBtn = mkEl("button", "sess-rename-cancel"); cancelBtn.textContent = "取消";
  inp.after(okBtn); okBtn.after(cancelBtn);

  function doRename() {
    const newTitle = inp.value.trim();
    if (newTitle && newTitle !== oldText) { _patchSession(sid, { title: newTitle }); }
    else { loadSessions(); }
  }
  function doCancel() {
    inp.replaceWith(nameSpan); okBtn.remove(); cancelBtn.remove();
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
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  }).catch(() => {});
  loadSessions();
}

async function _confirmDeleteSession(sid) {
  if (!confirm("确定要删除这条对话记录吗？此操作不可撤销。")) return;
  await fetch(`/api/sessions/${sid}`, { method: "DELETE" }).catch(() => {});
  const s = activeSess();
  if (s?.serverSid === sid) createAndSwitchNew();
  loadSessions();
}

// ── History session loading ────────────────────────────────────────────────────
async function loadHistorySession(sid) {
  closeCurrentPanel();
  if (activeSess()?.serverSid === sid) return;
  if (liveSess()?.serverSid === sid) { switchDisplay(liveKey); return; }

  const res = await fetch(`/api/sessions/${sid}`).catch(() => null);
  if (!res || !res.ok) return;
  const snap = await res.json();
  if (!snap.messages) return;

  const key = newKey();
  const data = newSessData();
  data.serverSid = sid;
  SESS.set(key, data);
  switchDisplay(key);

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
        td.innerHTML = `<summary>思考过程${n > 1 ? ` (${n} 步)` : ""}</summary><div class="thought-text">${thoughtArr.map((t, i) => (n > 1 ? `<div class="thought-step"><strong>步骤 ${i+1}</strong></div>` : "") + escHtml(t)).join('<hr class="thought-sep">')}</div>`;
        b.appendChild(td);
      }

      function renderToolCard(t) {
        const ok = !t.result?.error;
        const nse = t.result?.metrics?.NSE;
        const cid = `h-${Math.random().toString(36).slice(2,7)}`;
        const icon = TOOL_ICON[t.name] || "*";
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
        turns.forEach(turn => {
          renderThoughtBlock(turn.thoughts);
          if (turn.toolName) renderToolCard({ name: turn.toolName, args: turn.args, result: turn.result, elapsed: turn.elapsed });
        });
      } else {
        renderThoughtBlock(msg.thoughts);
        tools.forEach(t => renderToolCard(t));
      }

      // Images from all tool results
      const allToolObjs = turns.length > 0
        ? turns.filter(t => t.toolName).map(t => ({ result: t.result }))
        : tools;
      const imgs = allToolObjs.flatMap(t => {
        const l = t.result?.plot_files || t.result?.plot_paths || t.result?.figure_paths || [];
        return Array.isArray(l) ? l.slice(0, 3) : [];
      });
      if (imgs.length) {
        const imgWrap = mkEl("div", "msg-images");
        imgs.forEach(p => {
          const img = document.createElement("img");
          img.src = `/file?path=${encodeURIComponent(p)}`; img.alt = "plot";
          img.onerror = () => img.remove();
          img.onclick = () => openLightbox(img.src);
          imgWrap.appendChild(img);
        });
        b.appendChild(imgWrap);
      }

      if (msg.content) {
        const ans = mkEl("div", "msg-answer");
        ans.innerHTML = marked.parse(msg.content);
        injectInlineImages(ans);
        b.appendChild(ans);
      }
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
  restoreExecPanel(data.history);
}

// ── Exec panel restore ─────────────────────────────────────────────────────────
function restoreExecPanel(messages) {
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
      const icon = TOOL_ICON[tool.name] || "*";
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
          ${tool.result ? `<div class="tc-section-label">结果</div><pre class="tc-pre">${escHtml(typeof tool.result === "string" ? tool.result.slice(0,400) : JSON.stringify(tool.result,null,2).slice(0,400))}</pre>` : ""}
        </div>`;
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
  const open = body.style.display !== "none";
  body.style.display = open ? "none" : "block";
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
