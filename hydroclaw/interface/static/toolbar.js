// toolbar.js — Quick-action toolbar above the chat input.
// Depends on: utils.js (escHtml, TOOL_ZH, showToast)

// Three category buttons: 率定 | 评估/分析 | 其他
// Each opens a dropdown; selecting an option stores a hidden hint that is
// prepended to the actual query sent to the server (not shown in chat).

const _TB_CATS = ["率定", "评估/分析", "其他"];

const _TB_PRESETS = {
  "率定": [
    { label: "GR4J 标准率定",   hint: "[快捷操作] 用户想率定GR4J模型，请执行calibrate_model(model_name='gr4j')。流域ID需从用户输入中获取，若未提供请询问。" },
    { label: "XAJ 率定",        hint: "[快捷操作] 用户想率定XAJ模型，请执行calibrate_model(model_name='xaj')。流域ID需从用户输入中获取，若未提供请询问。" },
    { label: "GR6J 率定",       hint: "[快捷操作] 用户想率定GR6J模型，请执行calibrate_model(model_name='gr6j')。流域ID需从用户输入中获取，若未提供请询问。" },
    { label: "LLM 智能率定",    hint: "[快捷操作] 用户想使用LLM智能率定，请执行llm_calibrate工具。流域ID和模型名需从用户输入中获取，若未提供请询问。" },
    { label: "批量率定",         hint: "[快捷操作] 用户想批量率定多个流域，请先询问流域ID列表和模型名称，然后逐一执行率定。" },
  ],
  "评估/分析": [
    { label: "评估已率定模型",   hint: "[快捷操作] 用户想评估已率定模型的性能，请执行evaluate_model工具。流域ID和模型名需从用户输入或上下文中获取。" },
    { label: "多模型对比",       hint: "[快捷操作] 用户想对比多个模型（如GR4J和XAJ），请依次评估并汇总NSE等指标进行对比。流域ID需从用户输入中获取。" },
    { label: "生成可视化",       hint: "[快捷操作] 用户想生成径流过程线或其他可视化图表，请执行visualize工具。流域ID需从用户输入中获取。" },
    { label: "读取已有结果",     hint: "[快捷操作] 用户想查看已有的率定或评估结果，请先list_basins或读取workspace中的文件。" },
  ],
};

// { cat: string|null, optIdx: number|null }
const _tbState = { cat: null, optIdx: null };

async function buildToolbar() {
  const bar = document.getElementById("input-toolbar");
  if (!bar) return;

  // Load external package operations for "其他" category
  let extOpts = [];
  try {
    const pkgs = await fetch("/api/packages").then(r => r.json()).catch(() => []);
    for (const pkg of pkgs) {
      if (pkg.source === "adapter" || pkg.source === "local_dir" || pkg.source === "single_file") {
        const zhOps = pkg.zh_operations || {};
        for (const op of (pkg.operations || [])) {
          const label = zhOps[op] || TOOL_ZH[op] || op;
          const pkgLabel = pkg.label || pkg.name;
          extOpts.push({ label: `${pkgLabel}: ${label}`, hint: `[快捷操作] 用户想使用${pkgLabel}的${label}功能，请调用对应工具。所需参数从用户输入中获取，若未提供请询问。` });
        }
      }
    }
  } catch (_) {}

  _TB_PRESETS["其他"] = [
    { label: "生成代码",   hint: "[快捷操作] 用户想生成水文分析代码，请使用generate_code工具，需先了解具体需求。" },
    { label: "运行代码",   hint: "[快捷操作] 用户想运行代码，请使用run_code工具，需先确认代码内容。" },
    ...extOpts,
  ];

  _renderToolbar(bar);
}

function _renderToolbar(bar) {
  const parts = _TB_CATS.map(cat => {
    const isActive = _tbState.cat === cat;
    const opts = _TB_PRESETS[cat] || [];
    const selOpt = isActive && _tbState.optIdx !== null ? opts[_tbState.optIdx] : null;

    let btnContent;
    if (selOpt) {
      btnContent = `<span class="tb-sel-label">${escHtml(selOpt.label)}</span><span class="tb-clear-btn" onclick="clearToolbarCat(event,'${escHtml(cat)}')" title="取消">x</span>`;
    } else {
      btnContent = `${escHtml(cat)}<span class="tb-arrow">${isActive ? "▲" : "▼"}</span>`;
    }

    const ddItems = opts.map((o, i) =>
      `<div class="tb-dd-item${isActive && _tbState.optIdx === i ? " selected" : ""}" onclick="selectToolbarOption('${escHtml(cat)}',${i})">${escHtml(o.label)}</div>`
    ).join("");

    return `<div class="tb-cat-wrap">
      <button class="tb-btn${isActive ? " active" : ""}" onclick="toggleToolbarDropdown('${escHtml(cat)}')">${btnContent}</button>
      ${isActive && !selOpt ? `<div class="tb-dropdown"><div class="tb-dd-scroll">${ddItems}</div></div>` : ""}
    </div>`;
  });
  bar.innerHTML = parts.join("");
}

function toggleToolbarDropdown(cat) {
  const bar = document.getElementById("input-toolbar");
  if (!bar) return;
  if (_tbState.cat === cat && _tbState.optIdx !== null) return;
  _tbState.cat = (_tbState.cat === cat) ? null : cat;
  if (_tbState.cat === cat) _tbState.optIdx = null;
  _renderToolbar(bar);
}

function selectToolbarOption(cat, idx) {
  const bar = document.getElementById("input-toolbar");
  if (!bar) return;
  _tbState.cat = cat;
  _tbState.optIdx = idx;
  _renderToolbar(bar);
}

function clearToolbarCat(evt, cat) {
  evt.stopPropagation();
  const bar = document.getElementById("input-toolbar");
  if (!bar) return;
  if (_tbState.cat === cat) { _tbState.cat = null; _tbState.optIdx = null; }
  _renderToolbar(bar);
}

function getToolbarHint() {
  if (_tbState.cat === null || _tbState.optIdx === null) return "";
  const opts = _TB_PRESETS[_tbState.cat] || [];
  const opt = opts[_tbState.optIdx];
  return opt ? opt.hint : "";
}

// Pre-load count badges without rendering full panel content
async function _preloadCounts() {
  try {
    const [tools, pkgs, know, mem] = await Promise.all([
      fetch("/api/tools").then(r => r.json()).catch(() => []),
      fetch("/api/packages").then(r => r.json()).catch(() => []),
      fetch("/api/knowledge").then(r => r.json()).catch(() => []),
      fetch("/api/memory").then(r => r.json()).catch(() => ({})),
    ]);
    const el = id => document.getElementById(id);
    if (el("sd-tools-count"))     el("sd-tools-count").textContent     = tools.length    || "";
    if (el("sd-packages-count"))  el("sd-packages-count").textContent  = pkgs.length     || "";
    if (el("sd-knowledge-count")) el("sd-knowledge-count").textContent = know.length     || "";
    const bp = (mem?.basin_profiles || []).length;
    if (el("sd-memory-count"))    el("sd-memory-count").textContent    = bp > 0 ? `${bp} 流域` : "";
  } catch(e) {}
}
