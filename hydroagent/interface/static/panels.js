// panels.js — Side-panel loaders: skills, tools, packages, knowledge, memory,
//             datasets, config, and the openPagePanel/closeCurrentPanel routing.
// Depends on: utils.js (mkEl, escHtml, TOOL_ZH, TOOL_ZH_DESC, etc.)
// Runtime deps: closeCurrentPanel, showToast, buildToolbar, _preloadCounts (toolbar.js)

// ── System panels bootstrap ────────────────────────────────────────────────────
const _panelLoaded = {};
function _lazyLoad(key, fn) {
  if (_panelLoaded[key]) return;
  _panelLoaded[key] = true;
  fn();
}

async function loadSystemPanels() {
  _loadSkills();     // pre-load skills count badge
  _preloadCounts();  // pre-load other nav count badges
  buildToolbar();    // populate quick-action toolbar above input
}

// ── Panel routing ──────────────────────────────────────────────────────────────
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
  document.querySelectorAll(".s-nav-item").forEach(el => el.classList.remove("active"));
  document.querySelectorAll(`.s-nav-item[onclick*="'${id}'"]`).forEach(el => el.classList.add("active"));
  document.querySelectorAll(".session-item").forEach(el => el.classList.remove("active"));
  switch (id) {
    case "skills":    __loadSkills();   break;
    case "tools":     __loadTools();    break;
    case "packages":  __loadPackages(); break;
    case "knowledge": __loadKnowledge();break;
    case "memory":    __loadMemory();   break;
    case "datasets":  _loadDatasets();  break;
    case "config":    _loadConfig();    break;
  }
}

function closeCurrentPanel() {
  _currentPanelId = null;
  document.getElementById("panel-view").style.display = "none";
  document.getElementById("chat-view").style.display = "flex";
  document.querySelectorAll(".s-nav-item").forEach(el => el.classList.remove("active"));
}

// ── Skills panel ───────────────────────────────────────────────────────────────
let _skillsCache = [];

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
    const builtIn = skills.filter(s => s.when_to_use);
    const custom  = skills.filter(s => !s.when_to_use);
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
            ${kws  ? `<div class="item-detail-row">关键词：${escHtml(kws)}</div>` : ""}
            ${tools? `<div class="item-detail-row">工具：<span style="font-family:var(--font-mono);font-size:.75rem">${escHtml(tools)}</span></div>` : ""}
            ${cnt  ? `<pre class="tool-doc-pre" style="margin-top:6px">${escHtml(cnt)}</pre>` : ""}
          </div>
        </details>`;
      }).join("");
    };
    body.innerHTML = '<div class="panel-h2">可用技能</div>'
      + renderSkillGroup("内置技能", builtIn)
      + renderSkillGroup("自定义技能", custom);
  } catch (e) {
    if (body) body.innerHTML = '<div class="s-empty">加载失败</div>';
  }
}

function useSkill(name) {
  const s = _skillsCache.find(x => x.name === name);
  if (!s) return;
  const examples = s.example_queries?.length ? s.example_queries : getDefaultExamples(s.name);
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
  } catch (e) { /* count badge stays empty */ }
}

// ── Tools panel ────────────────────────────────────────────────────────────────
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
    const core    = tools.filter(t => t.priority >= 20);
    const skill   = tools.filter(t => t.priority >= 10 && t.priority < 20);
    const dynamic = tools.filter(t => t.priority < 10);
    const renderGroup = (label, list) => {
      if (!list.length) return "";
      return `<div class="panel-h3">${label}</div>` + list.map(t => {
        const zhName   = t.zh_name || TOOL_ZH[t.name] || t.name;
        const zhDesc   = t.zh_desc || TOOL_ZH_DESC[t.name] || "";
        const zhDetail = TOOL_ZH_DETAIL[t.name] || "";
        const tier     = TOOL_TIER[t.priority] || `p${t.priority}`;
        const detail   = zhDetail || (t.doc ? t.doc.trim() : "");
        return `<details class="tool-item">
          <summary class="tool-item-summary">
            <span class="tool-item-name">${escHtml(zhName)}</span>
            <span class="tool-item-desc">${zhDesc ? escHtml(zhDesc) : ""}</span>
            <span class="s-item-badge tool-item-badge">${tier}</span>
          </summary>
          <div class="tool-item-doc">
            <div class="item-code-id">function: ${escHtml(t.name)}</div>
            ${detail ? `<pre class="tool-doc-pre" style="margin-top:5px">${escHtml(detail)}</pre>` : ""}
          </div>
        </details>`;
      }).join("");
    };
    body.innerHTML = '<div class="panel-h2">已注册工具</div>'
      + renderGroup("核心工具", core) + renderGroup("技能工具", skill) + renderGroup("动态工具", dynamic);
  } catch (e) {
    body.innerHTML = '<div class="s-empty">加载失败</div>';
    if (countEl) countEl.textContent = "";
  }
}

// ── Packages panel ─────────────────────────────────────────────────────────────
async function __loadPackages() {
  const body = document.getElementById("panel-view-body");
  const countEl = document.getElementById("sd-packages-count");
  if (!body) return;
  try {
    const [pkgRes, pluginRes] = await Promise.all([
      fetch("/api/packages"),
      fetch("/api/plugins"),
    ]);
    if (!pkgRes.ok) throw new Error("packages fetch failed");
    const pkgs    = await pkgRes.json();
    const plugins = pluginRes.ok ? await pluginRes.json() : [];

    const installedPkgs = pkgs.filter(p => p.installed);
    const missingPkgs   = pkgs.filter(p => !p.installed);
    const localPlugins  = plugins.filter(p => p.type === "local_dir" || p.type === "single_file");

    if (countEl) countEl.textContent = (installedPkgs.length + localPlugins.length) || "";

    const ROLE_LABEL = { model: "模型框架", data: "数据读取", adapter: "适配器" };
    let html = '<div class="panel-h2">已安装水文包</div>';
    if (!installedPkgs.length) html += '<div class="s-empty">暂无已安装水文包</div>';
    html += installedPkgs.map(p => {
      const ops = Array.isArray(p.operations) ? p.operations : [];
      const zhOps = p.zh_operations || {};
      const opListHtml = ops.length ? `<div class="pkg-op-list">${ops.map(op => {
        const toolName = OP_TO_TOOL[op] || op;
        const zhName = zhOps[op] || zhOps[toolName] || TOOL_ZH[toolName] || TOOL_ZH[op] || op;
        const zhDesc = TOOL_ZH_DESC[toolName] || "";
        return `<div class="pkg-op-item">
          <span class="pkg-op-fn">${escHtml(toolName)}</span>
          <span class="pkg-op-zh">${escHtml(zhName)}</span>
          ${zhDesc ? `<span class="pkg-op-desc">${escHtml(zhDesc)}</span>` : ""}
        </div>`;
      }).join("")}</div>` : "";
      const detailHtml = p.detail
        ? `<div class="item-detail-row" style="margin-top:${ops.length ? "8px" : "0"}">${escHtml(p.detail)}</div>` : "";
      return `<details class="tool-item">
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

    // ── Local plugins section ────────────────────────────────────────────────
    html += '<div class="panel-h2">本地插件</div>';
    if (!localPlugins.length) {
      html += '<div class="s-empty">暂未注册本地插件。在下方填写路径以添加。</div>';
    } else {
      html += localPlugins.map(p => {
        const safeName = escHtml(p.name).replace(/'/g, "&#39;");
        const typeLabel = p.type === "single_file" ? "单文件工具" : "本地目录包";
        const statusBadge = p.enabled
          ? `<span class="s-item-badge badge-ready" style="flex-shrink:0">已启用</span>`
          : `<span class="s-item-badge badge-gray" style="flex-shrink:0">已禁用</span>`;
        const loadedBadge = p.loaded
          ? `<span class="s-item-badge" style="flex-shrink:0;background:var(--ok-bg,#e8f5e9);color:var(--ok,#2e7d32)">已加载</span>`
          : "";
        return `<details class="tool-item">
          <summary class="tool-item-summary">
            <span class="tool-item-name">${escHtml(p.name)}</span>
            <span class="tool-item-desc" style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escHtml(p.description || p.path)}</span>
            <span class="s-item-badge" style="flex-shrink:0">${typeLabel}</span>
            ${statusBadge}
            ${loadedBadge}
          </summary>
          <div class="tool-item-doc">
            <div class="item-code-id">path: ${escHtml(p.path)}</div>
            ${p.adapter_path ? `<div class="item-detail-row" style="margin-top:4px">adapter: ${escHtml(p.adapter_path)}</div>` : ""}
            ${p.added_at ? `<div class="item-detail-row" style="margin-top:4px;color:var(--text2)">注册于 ${escHtml(p.added_at.slice(0,16).replace("T"," "))}</div>` : ""}
            <div style="display:flex;gap:6px;margin-top:8px">
              <button class="s-btn s-btn-xs" onclick="togglePlugin('${safeName}', ${!p.enabled})">${p.enabled ? "禁用" : "启用"}</button>
              <button class="s-btn s-btn-xs" onclick="reloadPlugin('${safeName}')">重载</button>
              <button class="s-btn s-btn-xs s-btn-danger" onclick="removePlugin('${safeName}')">移除</button>
            </div>
          </div>
        </details>`;
      }).join("");
    }

    html += `<div class="panel-h2" style="margin-top:16px">注册本地目录包</div>
      <div class="s-add-form" style="flex-direction:column;align-items:stretch;gap:6px">
        <div style="font-size:.78rem;color:var(--text2);line-height:1.5">
          填写包含 <code>hydroclaw_adapter.py</code> 的目录路径，Agent 将自动加载其中定义的适配器与工具。
        </div>
        <input class="s-input" id="plugin-path" placeholder="例：D:/project/autohydro  或  /home/user/myhydro">
        <input class="s-input" id="plugin-name" placeholder="插件名称（可选，留空自动从目录名推断）">
        <input class="s-input" id="plugin-desc" placeholder="简要描述（可选）">
        <div style="display:flex;gap:6px">
          <button class="s-btn s-btn-primary" onclick="registerLocalPlugin()">注册插件</button>
        </div>
        <div id="plugin-register-msg" style="font-size:.76rem;padding:3px 0;color:var(--text2)"></div>
      </div>`;

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
    html += `<div class="panel-h2">pip 安装自定义包</div>
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

async function registerLocalPlugin() {
  const path = document.getElementById("plugin-path")?.value.trim();
  const name = document.getElementById("plugin-name")?.value.trim() || undefined;
  const desc = document.getElementById("plugin-desc")?.value.trim() || "";
  const msgEl = document.getElementById("plugin-register-msg");
  if (!path) { if (msgEl) msgEl.textContent = "请填写目录路径"; return; }
  if (msgEl) msgEl.textContent = "注册中...";
  try {
    const res = await fetch("/api/plugins", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, name, description: desc }),
    });
    const data = await res.json();
    if (!data.ok) {
      if (msgEl) msgEl.textContent = "注册失败: " + (data.error || "未知错误");
      return;
    }
    if (msgEl) msgEl.textContent = `插件 "${data.name || name || path}" 注册成功，已热加载`;
    showToast("本地插件注册成功");
    await __loadPackages();
  } catch (e) {
    if (msgEl) msgEl.textContent = "请求失败: " + e.message;
  }
}

async function togglePlugin(name, enable) {
  const res = await fetch(`/api/plugins/${encodeURIComponent(name)}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled: enable }),
  }).catch(() => null);
  if (!res?.ok) { showToast("操作失败"); return; }
  showToast(enable ? `插件 ${name} 已启用` : `插件 ${name} 已禁用`);
  await __loadPackages();
}

async function reloadPlugin(name) {
  const res = await fetch(`/api/plugins/${encodeURIComponent(name)}/reload`, {
    method: "POST",
  }).catch(() => null);
  if (!res?.ok) { showToast("重载失败"); return; }
  showToast(`插件 ${name} 已重载`);
  await __loadPackages();
}

async function removePlugin(name) {
  if (!confirm(`确定要移除插件 "${name}" 吗？此操作不可撤销。`)) return;
  const res = await fetch(`/api/plugins/${encodeURIComponent(name)}`, {
    method: "DELETE",
  }).catch(() => null);
  if (!res?.ok) { showToast("移除失败"); return; }
  showToast(`插件 ${name} 已移除`);
  await __loadPackages();
}

async function installPkg(pkgName) {
  const nameEl = document.getElementById("pkg-install-name");
  const pkg = pkgName || nameEl?.value.trim();
  const msgEl = document.getElementById("pkg-install-msg");
  if (!pkg) { if (msgEl) msgEl.textContent = "请填写包名"; return; }
  if (msgEl) msgEl.textContent = `正在安装 ${pkg}...`;
  try {
    const res = await fetch("/api/packages/install", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ package: pkg }),
    });
    const data = await res.json();
    if (!data.ok) { if (msgEl) msgEl.textContent = "错误: " + (data.error || "未知"); return; }
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
      } else { setTimeout(poll, 3000); }
    };
    setTimeout(poll, 3000);
  } catch (e) {
    if (msgEl) msgEl.textContent = "请求失败: " + e.message;
  }
}

// ── Knowledge panel ────────────────────────────────────────────────────────────
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
        const safeName = escHtml(k.name).replace(/'/g, "&#39;");
        const safeId   = escHtml(k.name).replace(/\./g, "-").replace(/[^a-zA-Z0-9_-]/g, "_");
        const zhTitle  = KNOW_ZH[k.name] || k.title || k.name;
        return `<details class="tool-item know-item" id="know-${safeId}" ontoggle="onKnowToggle(event,'${safeName}','${safeId}')">
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
      bodyEl.dataset.loaded = "";
      bodyEl.innerHTML = `<div class="s-empty">加载失败: ${escHtml(e.message)}</div>`;
    });
}

// ── Memory panel ───────────────────────────────────────────────────────────────
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
    let html = '<div class="panel-h2">工作区记忆</div>';
    if (data.memory_text) {
      const preview = data.memory_text.split("\n").slice(0, 8).join("\n").trim();
      html += `<div class="s-item s-item-col"><span class="s-item-name">MEMORY.md</span><pre class="s-item-pre">${escHtml(preview)}</pre></div>`;
    } else {
      html += '<div class="s-empty">无工作区记忆</div>';
    }
    if (bpCount > 0) {
      html += '<div class="panel-h2">流域档案</div>';
      html += data.basin_profiles.map(bp => {
        const nseStr = bp.nse != null ? `NSE ${Number(bp.nse).toFixed(3)}` : "";
        const detailJson = bp.detail ? JSON.stringify(bp.detail, null, 2) : "";
        return `<details class="tool-item">
          <summary class="tool-item-summary">
            <span class="tool-item-name">流域 ${escHtml(bp.basin_id)}</span>
            ${bp.model ? `<span class="s-item-badge">${escHtml(bp.model.toUpperCase())}</span>` : ""}
            ${nseStr ? `<span class="s-item-badge" style="color:var(--ok);font-weight:700">${escHtml(nseStr)}</span>` : ""}
          </summary>
          ${detailJson ? `<div class="tool-item-doc"><pre class="tc-pre" style="max-height:280px;overflow-y:auto">${escHtml(detailJson)}</pre></div>` : ""}
        </details>`;
      }).join("");
    }
    body.innerHTML = html;
  } catch (e) {
    body.innerHTML = '<div class="s-empty">加载失败</div>';
    if (countEl) countEl.textContent = "";
  }
}

// ── Datasets panel ─────────────────────────────────────────────────────────────
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
01013500,1234.5,850.2</pre>
  <div class="ds-help-title" style="margin-top:10px">timeseries/1D/01013500.csv 示例</div>
  <pre class="ds-help-pre">time,precipitation,temperature,streamflow
2000-01-01,5.2,15.3,12.4</pre>
  <div class="ds-help-title" style="margin-top:10px">1D_units_info.json 示例</div>
  <pre class="ds-help-pre">{"precipitation":"mm/d","temperature":"C","streamflow":"mm/d"}</pre>
</div>`;

async function _loadDatasets() {
  const body = document.getElementById("panel-view-body");
  if (!body) return;
  try {
    const res = await fetch("/api/datasets");
    if (!res.ok) throw new Error("fetch failed");
    const data = await res.json();
    let html = '<div class="panel-h2">公开数据集</div>';
    (data.public || []).forEach(d => {
      const ready = d.status === "ready";
      const units = Array.isArray(d.time_units) ? d.time_units : [];
      const unitBadges = units.map(u => `<span class="s-item-badge badge-gray" style="font-size:.72rem">${escHtml(u)}</span>`).join("");
      html += `<div class="s-item">
        <span class="s-item-name">${escHtml(d.label)}</span>${unitBadges}
        <span class="s-item-meta">${d.region} · ${d.basins} 流域 · ${d.size}</span>
        <span class="s-item-badge ${ready ? "badge-ready" : "badge-gray"}">${ready ? "就绪" : "未下载"}</span>
      </div>`;
    });
    if (data.custom?.length > 0) {
      html += '<div class="panel-h2">自定义数据集</div>';
      data.custom.forEach(d => {
        const dsKey = d.dataset_name + "__" + (d.time_unit || "");
        const isCaching = (window._dsCache || {})[dsKey] === "caching";
        let statusLabel, statusCls;
        if (isCaching)                      { statusLabel = "转换中..."; statusCls = "badge-warn"; }
        else if (d.cache_status === "cached")   { statusLabel = "就绪";      statusCls = "badge-ready"; }
        else if (d.cache_status === "uncached")  { statusLabel = "未转换";   statusCls = "badge-warn"; }
        else                                { statusLabel = "路径缺失"; statusCls = "badge-gray"; }
        const canCache = !isCaching && d.cache_status !== "missing";
        const cacheBtnLabel = d.cache_status === "cached" ? "重新转NC" : "转为NC";
        const safeN = escHtml(d.dataset_name).replace(/'/g, "&#39;");
        const safeU = escHtml(d.time_unit || "").replace(/'/g, "&#39;");
        html += `<div class="s-item" id="ds-item-${escHtml(dsKey)}">
          <span class="s-item-name">${escHtml(d.dataset_name)}</span>
          ${d.time_unit ? `<span class="s-item-badge badge-gray" style="font-size:.72rem;margin-left:4px">${escHtml(d.time_unit)}</span>` : ""}
          ${d.basin_count ? `<span class="s-item-meta">${d.basin_count} 流域</span>` : ""}
          <span class="s-item-badge ${statusCls}" id="ds-badge-${escHtml(dsKey)}">${statusLabel}</span>
          ${canCache ? `<button class="s-btn s-btn-xs" onclick="cacheDataset('${safeN}','${safeU}',${d.cache_status === "cached"})">${cacheBtnLabel}</button>` : ""}
          <button class="s-item-del-btn" title="删除" onclick="deleteCustomDataset('${safeN}','${safeU}')">×</button>
        </div>`;
      });
    }
    html += `<div class="panel-h2" style="display:flex;align-items:center;justify-content:space-between">
      <span>添加自定义数据集</span>
      <button class="s-btn s-btn-xs" onclick="toggleDsHelp()">数据格式说明</button>
    </div>
    <div class="s-add-form" id="custom-ds-form">
      <div></div>
      <div id="ds-help-panel" style="display:none">${_DS_FORMAT_HELP}</div>
      <input class="s-input" id="cds-path" placeholder="父目录路径，例：D:\\project\\data">
      <input class="s-input" id="cds-name" placeholder="数据集文件夹名称，例：songliao_event">
      <select class="s-input" id="cds-unit">
        <option value="1D">1D（日数据）</option>
        <option value="1h">1h（小时数据）</option>
        <option value="3h">3h（3小时数据）</option>
        <option value="8D">8D（8日数据）</option>
      </select>
      <button class="s-btn s-btn-primary" onclick="addCustomDataset()">验证并转换为NC</button>
      <div id="cds-msg" style="font-size:.76rem;padding:4px 0;color:var(--text2)"></div>
    </div>`;
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
  const path  = document.getElementById("cds-path")?.value.trim();
  const name  = document.getElementById("cds-name")?.value.trim();
  const unit  = document.getElementById("cds-unit")?.value || "1D";
  const msgEl = document.getElementById("cds-msg");
  if (!path || !name) { if (msgEl) msgEl.textContent = "请填写路径和名称"; return; }
  if (msgEl) msgEl.textContent = "验证中...";
  try {
    const res = await fetch("/api/datasets/custom", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data_path: path, dataset_name: name, time_unit: unit }),
    });
    const data = await res.json();
    if (!data.success) {
      if (msgEl) {
        msgEl.textContent = "错误: " + (data.error || "未知错误");
        if (data.detail) { msgEl.title = data.detail; msgEl.style.cursor = "help"; console.error("[dataset NC]", data.detail); }
      }
      return;
    }
    if (msgEl) msgEl.textContent = `结构验证通过${data.basin_count ? "，发现 " + data.basin_count + " 个流域" : ""}，正在转换为NC…`;
    await _loadDatasets();
    cacheDataset(name, msgEl);
  } catch (e) {
    if (msgEl) msgEl.textContent = "请求失败: " + e.message;
  }
}

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
    if (!data.ok) { window._dsCache[dsKey] = "error"; if (msgEl) msgEl.textContent = "启动失败: " + (data.error || "未知"); return; }
    if (data.was_cached && msgEl) msgEl.textContent = `${name}（${time_unit}）：已有 NC 缓存，覆盖重新生成中…`;
    _pollCacheStatus(name, time_unit, msgEl);
  } catch (e) {
    window._dsCache[dsKey] = "error";
    if (msgEl) msgEl.textContent = "请求失败: " + e.message;
  }
}

async function _pollCacheStatus(name, time_unit, msgEl) {
  const dsKey = name + "__" + (time_unit || "");
  let attempts = 0;
  const poll = async () => {
    if (attempts++ > 180) { if (msgEl) msgEl.textContent = "转换超时，请检查数据格式后重试"; return; }
    try {
      const url = `/api/datasets/custom/${encodeURIComponent(name)}/cache-status` +
                  (time_unit ? `?time_unit=${encodeURIComponent(time_unit)}` : "");
      const res = await fetch(url);
      const data = await res.json();
      if (data.status === "ready" || data.cached) {
        window._dsCache[dsKey] = "ready";
        if (msgEl) msgEl.textContent = `NC 转换完成（${time_unit || name}），数据集就绪！`;
        await _loadDatasets(); return;
      }
      if (data.status?.startsWith("error:")) {
        window._dsCache[dsKey] = "error";
        if (msgEl) msgEl.textContent = "转换失败: " + data.status.slice(6);
        await _loadDatasets(); return;
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

// ── Config panel ───────────────────────────────────────────────────────────────
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
        <label class="s-form-label">API Key ${cfg.api_key_set ? '<span style="color:var(--ok);font-size:.75rem">已配置</span>' : '<span style="color:var(--text2);font-size:.75rem">未配置</span>'}</label>
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
      </div>`;
  } catch (e) {
    body.innerHTML = '<div class="s-empty">加载失败</div>';
  }
}

async function saveConfig() {
  const model       = document.getElementById("cfg-model")?.value.trim();
  const baseUrl     = document.getElementById("cfg-base-url")?.value.trim();
  const apiKey      = document.getElementById("cfg-api-key")?.value.trim();
  const temperature = parseFloat(document.getElementById("cfg-temperature")?.value || "0.1");
  const maxTurns    = parseInt(document.getElementById("cfg-max-turns")?.value || "30", 10);
  const msgEl       = document.getElementById("cfg-msg");
  const payload     = { model, base_url: baseUrl, temperature, max_turns: maxTurns };
  if (apiKey) payload.api_key = apiKey;
  try {
    const res = await fetch("/api/config", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (msgEl) msgEl.textContent = data.ok ? "已保存（重启后生效）" : "保存失败";
  } catch (e) {
    if (msgEl) msgEl.textContent = "请求失败: " + e.message;
  }
}

// ── Create skill modal ─────────────────────────────────────────────────────────
function getDefaultExamples(name) {
  const map = {
    calibration:     ["率定GR4J模型，流域12025000", "用SCE-UA算法率定GR6J，流域01013500"],
    llm_calibration: ["用LLM智能率定GR4J，流域12025000"],
    evaluation:      ["评估模型结果，流域12025000"],
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
