"""
HydroClaw Web UI - Streamlit Browser Interface
===============================================
Launch:  streamlit run hydroclaw/web_app.py
Or via:  python -m hydroclaw --web
"""

import contextlib
import io
import json
import logging
import queue
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="HydroClaw",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# i18n strings
# ---------------------------------------------------------------------------
_STRINGS = {
    "zh": {
        "title":          "HydroClaw - 水文模型智能率定助手",
        "subtitle":       "水文模型率定 · 评估 · 分析",
        "input":          "输入问题（例：率定GR4J模型，流域12025000）",
        "new_chat":       "新对话",
        "token_usage":    "Token 用量",
        "prompt":         "输入",
        "completion":     "输出",
        "total":          "累计",
        "skills":         "可用功能",
        "history":        "历史对话",
        "no_history":     "暂无历史",
        "task_panel":     "执行状态",
        "agent_idle":     "待命",
        "agent_thinking": "LLM 推理中...",
        "agent_running":  "工具执行中",
        "tool_calls":     "工具调用",
        "load_session":   "加载到对话",
        "close":          "关闭",
        "skills_page":    "技能详情",
        "back_to_chat":   "返回对话",
        "skill_detail":   "技能详情",
        "tool_calls_n":   lambda n: f"工具调用 ({n} 步)",
        "running_label":  "运行中",
        "batch_progress": "批量任务进度",
        "done":           "完成",
        "failed":         "失败",
        "pending":        "待执行",
        "thinking":       "思考过程",
        "tool_detail":    "输出详情",
        "tool_args":      "工具参数",
        "tool_result":    "执行结果",
    },
    "en": {
        "title":          "HydroClaw - Hydrological Model Calibration Agent",
        "subtitle":       "Calibration · Evaluation · Analysis",
        "input":          "Ask HydroClaw (e.g. Calibrate GR4J for basin 12025000)",
        "new_chat":       "New Chat",
        "token_usage":    "Token Usage",
        "prompt":         "Prompt",
        "completion":     "Completion",
        "total":          "Total",
        "skills":         "Available Skills",
        "history":        "History",
        "no_history":     "No history yet",
        "task_panel":     "Execution Status",
        "agent_idle":     "Idle",
        "agent_thinking": "LLM reasoning...",
        "agent_running":  "Running tool",
        "tool_calls":     "Tool Calls",
        "load_session":   "Load into chat",
        "close":          "Close",
        "skills_page":    "Skills",
        "back_to_chat":   "Back to chat",
        "skill_detail":   "Skill Detail",
        "tool_calls_n":   lambda n: f"Tool calls ({n} steps)",
        "running_label":  "Running",
        "batch_progress": "Batch Progress",
        "done":           "done",
        "failed":         "failed",
        "pending":        "pending",
        "thinking":       "Thinking",
        "tool_detail":    "Details",
        "tool_args":      "Parameters",
        "tool_result":    "Result",
    },
}

def _t(key: str, *args):
    lang = st.session_state.get("lang", "zh")
    v = _STRINGS[lang][key]
    return v(*args) if callable(v) else v


# ---------------------------------------------------------------------------
# CSS (supports dark/light via data-theme)
# ---------------------------------------------------------------------------
_CSS_LIGHT = """
    --bg:           #ffffff;
    --bg-side:      #f8fafc;
    --bg-panel:     #f1f5f9;
    --border:       #e2e8f0;
    --text:         #1e293b;
    --text-muted:   #64748b;
    --accent:       #2563eb;
    --tool-ok:      #16a34a;
    --tool-err:     #dc2626;
    --tool-run:     #2563eb;
    --nse-good-bg:  #dcfce7; --nse-good-fg: #166534;
    --nse-ok-bg:    #fef9c3; --nse-ok-fg:   #854d0e;
    --nse-bad-bg:   #fee2e2; --nse-bad-fg:  #991b1b;
"""
_CSS_DARK = """
    --bg:           #0f172a;
    --bg-side:      #1e293b;
    --bg-panel:     #1e293b;
    --border:       #334155;
    --text:         #e2e8f0;
    --text-muted:   #94a3b8;
    --accent:       #60a5fa;
    --tool-ok:      #4ade80;
    --tool-err:     #f87171;
    --tool-run:     #60a5fa;
    --nse-good-bg:  #14532d; --nse-good-fg: #bbf7d0;
    --nse-ok-bg:    #713f12; --nse-ok-fg:   #fef08a;
    --nse-bad-bg:   #7f1d1d; --nse-bad-fg:  #fecaca;
"""

_CSS_BASE = """
<style>
:root { VARS_PLACEHOLDER }

/* Layout */
body, .stApp { background: var(--bg) !important; color: var(--text); }
[data-testid="stSidebar"] {
    background: var(--bg-side) !important;
    border-right: 1px solid var(--border);
    min-width: 260px; max-width: 260px;
}
[data-testid="stMainBlockContainer"] { background: var(--bg) !important; }
.stChatMessage { background: var(--bg) !important; }

/* Tool rows */
.tool-row { padding: 3px 0; font-size: 0.86rem; font-family: monospace; line-height: 1.5; }
.t-ok  { color: var(--tool-ok);  font-weight: 600; }
.t-err { color: var(--tool-err); font-weight: 600; }
.t-run { color: var(--tool-run); font-weight: 600; }
.t-hint{ color: var(--text-muted); margin-left: 8px; }
.t-sec { color: var(--text-muted); font-size: 0.80rem; margin-left: 4px; }

/* NSE badges */
.nse-good { background:var(--nse-good-bg); color:var(--nse-good-fg);
            padding:1px 6px; border-radius:4px; font-weight:700; font-size:0.84rem; }
.nse-ok   { background:var(--nse-ok-bg);   color:var(--nse-ok-fg);
            padding:1px 6px; border-radius:4px; font-weight:700; font-size:0.84rem; }
.nse-bad  { background:var(--nse-bad-bg);  color:var(--nse-bad-fg);
            padding:1px 6px; border-radius:4px; font-weight:700; font-size:0.84rem; }

/* Right panel */
.exec-panel { background: var(--bg-panel); border-radius: 8px;
              border: 1px solid var(--border); padding: 10px 12px; }
.panel-title{ font-weight: 600; font-size: 0.9rem; color: var(--text);
              margin-bottom: 6px; }
.status-dot-run  { display:inline-block; width:8px; height:8px; border-radius:50%;
                   background: var(--tool-run); margin-right:6px;
                   animation: pulse 1s infinite; }
.status-dot-idle { display:inline-block; width:8px; height:8px; border-radius:50%;
                   background: var(--text-muted); margin-right:6px; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }

/* Sidebar section headers */
.sidebar-section { font-weight: 600; font-size: 0.85rem;
                   color: var(--text-muted); text-transform: uppercase;
                   letter-spacing: 0.05em; margin: 8px 0 4px 0; }

/* Hide Streamlit chrome (toolbar, header bar, footer) */
#MainMenu, footer { visibility: hidden; }
[data-testid="stToolbar"]   { display: none !important; }
header[data-testid="stHeader"] { display: none !important; }
.stApp > header             { display: none !important; }
.block-container { padding-top: 1rem; }

/* Exec panel: left border + sticky so it stays at top while chat scrolls */
.panel-col-border {
    position: sticky;
    top: 1rem;
    border-left: 1px solid var(--border);
    padding-left: 12px;
    max-height: 90vh;
    overflow-y: auto;
}

/* Thinking block */
.thought-block {
    background: var(--bg-panel);
    border-left: 3px solid var(--accent);
    padding: 6px 10px;
    margin: 4px 0;
    border-radius: 0 4px 4px 0;
    font-size: 0.82rem;
    color: var(--text-muted);
    white-space: pre-wrap;
    word-break: break-word;
}

/* Skill guide content: downscale headings so they don't dominate */
.skill-guide h1, .skill-guide h2, .skill-guide h3 {
    font-size: 0.9rem !important;
    font-weight: 600 !important;
    margin: 6px 0 2px 0 !important;
}
.skill-guide p, .skill-guide li { font-size: 0.85rem !important; }

/* Fix chat input at bottom of viewport (Streamlit 1.32+) */
[data-testid="stChatInputContainer"],
[data-testid="stBottom"] {
    position: sticky !important;
    bottom: 0 !important;
    z-index: 200 !important;
    background: var(--bg) !important;
    padding: 4px 0 !important;
}
/* Padding so messages don't hide behind sticky input */
[data-testid="stMainBlockContainer"] { padding-bottom: 70px !important; }
</style>
"""

def _inject_css():
    css = _CSS_BASE.replace("VARS_PLACEHOLDER", _CSS_DARK)
    st.markdown(css, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Web logging setup (file-based, configured once per session)
# ---------------------------------------------------------------------------

def _setup_web_logging():
    """Write hydroclaw logs to logs/hydroclaw_web_YYYYMMDD.log."""
    log_dir = Path(st.session_state.get("workspace", ".")) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"hydroclaw_web_{datetime.now().strftime('%Y%m%d')}.log"

    logger = logging.getLogger("hydroclaw")
    # Avoid adding duplicate handlers on hot-reload
    if any(isinstance(h, logging.FileHandler) for h in logger.handlers):
        return
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(str(log_file), encoding="utf-8")
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    ))
    logger.addHandler(fh)
    logger.info("Web session started. Log -> %s", log_file)


# ---------------------------------------------------------------------------
# Tool labels
# ---------------------------------------------------------------------------
_TOOL_LABELS = {
    "validate_basin":    "validate_basin",
    "calibrate_model":   "calibrate_model",
    "evaluate_model":    "evaluate_model",
    "visualize":         "visualize",
    "llm_calibrate":     "llm_calibrate",
    "batch_calibrate":   "batch_calibrate",
    "compare_models":    "compare_models",
    "generate_code":     "generate_code",
    "run_code":          "run_code",
    "create_skill":      "create_skill",
    "create_task_list":  "create_task_list",
    "get_pending_tasks": "get_pending_tasks",
    "update_task":       "update_task",
    "read_file":         "read_file",
    "inspect_dir":       "inspect_dir",
    "ask_user":          "ask_user",
    "search_memory":     "search_memory",
}

_TOOL_LABELS_ZH = {
    "validate_basin":    "验证流域数据",
    "calibrate_model":   "执行模型率定",
    "evaluate_model":    "评估模型性能",
    "visualize":         "生成可视化图形",
    "llm_calibrate":     "LLM 智能率定",
    "batch_calibrate":   "批量率定流域",
    "compare_models":    "多模型对比",
    "generate_code":     "生成分析代码",
    "run_code":          "执行分析脚本",
    "create_skill":      "创建新技能",
    "create_task_list":  "创建任务计划",
    "get_pending_tasks": "获取待执行任务",
    "update_task":       "更新任务状态",
    "read_file":         "读取文件",
    "inspect_dir":       "查看目录",
    "ask_user":          "向用户提问",
    "search_memory":     "检索历史记忆",
}

def _tool_label(name: str) -> str:
    if st.session_state.get("lang", "zh") == "zh":
        return _TOOL_LABELS_ZH.get(name, name)
    return name


# ---------------------------------------------------------------------------
# Session history helpers
# ---------------------------------------------------------------------------

def _sessions_dir() -> Path:
    return Path(st.session_state.get("workspace", ".")) / "sessions"


def _list_sessions(limit: int = 30) -> list[dict]:
    sdir = _sessions_dir()
    if not sdir.exists():
        return []
    summaries = []
    for f in sdir.glob("*_summary.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            summaries.append(d)
        except Exception:
            pass
    summaries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return summaries[:limit]


def _load_web_snapshot(session_id: str) -> dict | None:
    """Load full web conversation state saved by _save_web_snapshot()."""
    web_path = _sessions_dir() / f"{session_id}_web.json"
    if web_path.exists():
        try:
            return json.loads(web_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def _load_session_messages(session_id: str) -> list[dict]:
    # Prefer full web snapshot (no truncation)
    snap = _load_web_snapshot(session_id)
    if snap:
        return snap.get("messages", [])

    # Fallback: rebuild from JSONL summary (legacy / agent-only sessions)
    sdir = _sessions_dir()
    msgs = []
    summary_path = sdir / f"{session_id}_summary.json"
    if not summary_path.exists():
        return msgs
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        return msgs

    query = summary.get("query", "")
    if query:
        msgs.append({"role": "user", "content": query})

    tool_log = []
    jsonl_path = sdir / f"{session_id}.jsonl"
    if jsonl_path.exists():
        try:
            for line in jsonl_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                entry = json.loads(line)
                tool_name = entry.get("tool", "")
                if tool_name:
                    rs = entry.get("result_summary", {})
                    tool_log.append({
                        "name":    tool_name,
                        "label":   _TOOL_LABELS_ZH.get(tool_name, tool_name),
                        "args":    {},
                        "status":  "done",
                        "elapsed": None,
                        "result":  rs if isinstance(rs, dict) else {},
                    })
        except Exception:
            pass

    preview = summary.get("final_response_preview", "")
    if preview:
        suffix = "...(已截断，完整内容请重新对话)" if len(preview) >= 500 else ""
        msgs.append({
            "role":    "assistant",
            "content": preview + suffix,
            "tools":   tool_log,
        })
    return msgs


def _save_web_snapshot():
    """Persist full web conversation state to disk so it survives page reloads."""
    agent = st.session_state.get("agent")
    if not agent:
        return
    try:
        sid  = agent.memory.session_id
        snap = {
            "session_id":   sid,
            "messages":     st.session_state.messages,
            "all_tool_log": st.session_state.all_tool_log,
            "token_total":  st.session_state.token_total,
            "token_prompt": st.session_state.token_prompt,
            "token_compl":  st.session_state.token_compl,
        }
        sdir = _sessions_dir()
        sdir.mkdir(parents=True, exist_ok=True)
        (sdir / f"{sid}_web.json").write_text(
            json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logging.getLogger("hydroclaw").debug("Web snapshot saved: %s", sid)
    except Exception as exc:
        logging.getLogger("hydroclaw").warning("Web snapshot save failed: %s", exc)


# ---------------------------------------------------------------------------
# StreamlitUI bridge
# ---------------------------------------------------------------------------

class StreamlitUI:
    mode = "user"

    def __init__(self, event_queue: queue.Queue):
        self._q  = event_queue   # direct reference - NOT via st.session_state
        self._t0 = 0.0

    def _put(self, type_: str, **kw):
        self._q.put({"type": type_, **kw})

    def on_query(self, query: str):        self._put("query", query=query)
    def on_answer(self, text: str, total_turns: int): self._put("answer", text=text, turns=total_turns)
    def on_error(self, msg: str):          self._put("error", msg=msg)
    def on_max_turns(self):                self._put("error", msg="Max turns reached.")
    def dev_log(self, msg: str):           pass
    def print_banner(self, *a, **kw):     pass

    def on_thought(self, text: str, turn: int):
        if text and text.strip():
            self._put("thought", text=text.strip(), turn=turn)

    def on_tool_start(self, name: str, args: dict):
        self._t0 = time.time()
        self._put("tool_start", name=name, args=args)

    def on_tool_end(self, name: str, result: dict, elapsed: float | None = None):
        if elapsed is None:
            elapsed = time.time() - self._t0
        self._put("tool_end", name=name, result=result, elapsed=elapsed)

    def on_task_progress(self, workspace):
        state_file = Path(str(workspace)) / "task_state.json"
        if state_file.exists():
            try:
                data = json.loads(state_file.read_text(encoding="utf-8"))
                self._put("task_progress", data=data)
            except Exception:
                pass

    def on_session_summary(self, total_turns: int, elapsed_s: float, tokens: dict):
        self._put("session_summary", turns=total_turns, elapsed=elapsed_s, tokens=tokens)

    def on_calibration_progress(self, pct: float, elapsed: float,
                                eval_count: int, rep: int,
                                algo: str, round_label: str = ""):
        self._put("calibration_progress", pct=pct, elapsed=elapsed,
                  eval_count=eval_count, rep=rep, algo=algo, round_label=round_label)

    @contextmanager
    def thinking(self, turn: int):
        self._put("thinking_start", turn=turn)
        try:
            yield
        finally:
            self._put("thinking_end", turn=turn)

    @contextmanager
    def suppress_tool_output(self, name: str):
        null_io = io.StringIO()
        with contextlib.redirect_stdout(null_io), contextlib.redirect_stderr(null_io):
            yield

    def ask_user(self, question: str, context: str | None = None) -> str:
        evt      = threading.Event()
        answer_q = queue.Queue()   # dedicated answer channel; avoids event_queue collision
        self._put("ask_user", question=question, context=context,
                  event=evt, answer_q=answer_q)
        evt.wait(timeout=300)
        return answer_q.get_nowait() if not answer_q.empty() else ""


# ---------------------------------------------------------------------------
# State init
# ---------------------------------------------------------------------------

def _init_state():
    defaults = {
        "messages":         [],
        "event_queue":      None,   # initialized below
        "agent_thread":     None,
        "agent_running":    False,
        "token_total":      0,
        "token_prompt":     0,
        "token_compl":      0,
        "tool_log":         [],     # current-run tool entries
        "all_tool_log":     [],     # accumulated across turns in this conversation
        "thinking":         False,
        "current_tool":     None,
        "task_data":        None,
        "ask_user_q":       None,
        "ask_user_answer":  "",
        "agent":            None,
        "workspace":        ".",
        "view_session_id":  None,
        "view":             "chat", # "chat" | "skills"
        "lang":             "zh",
        "theme":            "dark",
        "last_nse":         None,
        "current_thought":  "",
        "show_token_warn":       False,
        "token_warn_acked":      False,
        "conv_id":               None,
        "calibration_progress":  None,  # {pct, elapsed, eval_count, rep, algo, round_label}

    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    # Queue must be a real Queue object, not None
    if st.session_state.event_queue is None:
        st.session_state.event_queue = queue.Queue()


def _get_agent():
    if st.session_state.agent is None:
        from hydroclaw.agent import HydroClaw
        workspace = Path(st.session_state.workspace)
        ui_bridge = StreamlitUI(st.session_state.event_queue)
        st.session_state.agent = HydroClaw(workspace=workspace, ui=ui_bridge)
    return st.session_state.agent


# ---------------------------------------------------------------------------
# Chat history -> prior messages for agent context
# ---------------------------------------------------------------------------

def _build_prior_messages(messages: list[dict]) -> list[dict]:
    """Convert recent web chat messages to LLM message format for agent context.

    Includes calibration_dir, NSE, and other key results in assistant messages
    so the agent remembers what was done in previous turns.
    """
    prior = []
    for msg in messages[-10:]:   # last 5 exchanges (10 messages)
        role    = msg["role"]
        content = msg.get("content", "")
        if role == "user":
            prior.append({"role": "user", "content": content})
        elif role == "assistant":
            # Append key tool results as context so agent doesn't ask again
            extras = []
            for t in (msg.get("tools") or []):
                result = t.get("result") or {}
                cal_dir = result.get("calibration_dir", "")
                nse     = (result.get("metrics") or {}).get("NSE")
                if cal_dir:
                    extras.append(f"calibration_dir={cal_dir}")
                if isinstance(nse, float):
                    extras.append(f"NSE={nse:.4f}")
            extra_str = ""
            if extras:
                extra_str = "\n\n[Previous tool results: " + "; ".join(extras) + "]"
            prior.append({"role": "assistant", "content": content + extra_str})
    return prior


# ---------------------------------------------------------------------------
# Background runner  (CRITICAL: capture queue ref before thread starts)
# ---------------------------------------------------------------------------

def _run_agent_background(query: str):
    agent      = _get_agent()
    event_q    = st.session_state.event_queue   # capture here, in main thread
    prior      = _build_prior_messages(st.session_state.messages)

    def _worker():
        try:
            agent.run(query, prior_messages=prior)
        except Exception as e:
            event_q.put({"type": "error", "msg": str(e)})
        finally:
            try:
                tok = agent.llm.tokens.summary()
            except Exception:
                tok = {}
            event_q.put({"type": "done", "tokens": tok})

    t = threading.Thread(target=_worker, daemon=True, name="hydroclaw-agent")
    st.session_state.agent_thread  = t
    st.session_state.agent_running = True
    st.session_state.tool_log      = []
    st.session_state.all_tool_log  = []    # reset per-query: right panel shows current query only
    st.session_state.thinking      = False
    st.session_state.current_tool  = None
    st.session_state.current_thought = ""
    # Assign a conversation id for token tracking if not set
    if st.session_state.conv_id is None:
        st.session_state.conv_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    t.start()


# ---------------------------------------------------------------------------
# Event processor
# ---------------------------------------------------------------------------

def _process_events() -> bool:
    changed = False
    q: queue.Queue = st.session_state.event_queue
    while not q.empty():
        try:
            ev = q.get_nowait()
        except queue.Empty:
            break
        changed = True
        t = ev["type"]

        if t == "thinking_start":
            st.session_state.thinking     = True
            st.session_state.current_tool = None

        elif t == "thinking_end":
            st.session_state.thinking = False

        elif t == "thought":
            st.session_state.current_thought = ev.get("text", "")

        elif t == "tool_start":
            entry = {
                "name":           ev["name"],
                "label":          _TOOL_LABELS_ZH.get(ev["name"], ev["name"]),
                "args":           ev.get("args", {}),
                "status":         "running",
                "elapsed":        None,
                "result":         None,
                "ts":             time.time(),
                "thought_before": st.session_state.current_thought,
            }
            st.session_state.current_thought = ""   # consumed
            st.session_state.tool_log.append(entry)
            st.session_state.all_tool_log.append(entry)
            st.session_state.current_tool = ev["name"]

        elif t == "calibration_progress":
            st.session_state.calibration_progress = ev

        elif t == "tool_end":
            # Clear calibration progress when tool finishes
            if ev.get("name") in ("calibrate_model", "llm_calibrate"):
                st.session_state.calibration_progress = None
            for entry in reversed(st.session_state.tool_log):
                if entry["name"] == ev["name"] and entry["status"] == "running":
                    entry["status"]  = "error" if (ev.get("result") or {}).get("error") else "done"
                    entry["elapsed"] = ev.get("elapsed")
                    entry["result"]  = ev.get("result") or {}
                    # track last NSE
                    nse = (entry["result"].get("metrics") or {}).get("NSE")
                    if nse is not None:
                        st.session_state.last_nse = nse
                    break
            st.session_state.current_tool = None

        elif t == "task_progress":
            st.session_state.task_data = ev.get("data")

        elif t == "ask_user":
            st.session_state.ask_user_q = ev

        elif t == "answer":
            st.session_state.messages.append({
                "role":    "assistant",
                "content": ev["text"],
                "tools":   list(st.session_state.tool_log),
            })
            st.session_state.tool_log       = []
            st.session_state.current_tool   = None
            st.session_state.current_thought = ""

        elif t == "error":
            st.session_state.messages.append({
                "role":    "assistant",
                "content": f"**[ERR]** {ev['msg']}",
                "tools":   list(st.session_state.tool_log),
            })
            st.session_state.tool_log       = []
            st.session_state.current_tool   = None
            st.session_state.current_thought = ""

        elif t == "done":
            st.session_state.agent_running = False
            st.session_state.thinking      = False
            st.session_state.current_tool  = None
            tok = ev.get("tokens", {})
            st.session_state.token_total  += tok.get("total_tokens",    0)
            st.session_state.token_prompt += tok.get("prompt_tokens",   0)
            st.session_state.token_compl  += tok.get("completion_tokens", 0)
            # 1M token warning
            if (st.session_state.token_total >= 1_000_000
                    and not st.session_state.token_warn_acked):
                st.session_state.show_token_warn = True
            # Persist full conversation state so it survives page reload / session switch
            _save_web_snapshot()

    return changed


# ---------------------------------------------------------------------------
# Render helpers
# ---------------------------------------------------------------------------

def _nse_badge_html(nse) -> str:
    if not isinstance(nse, (int, float)):
        return ""
    cls = "nse-good" if nse >= 0.75 else ("nse-ok" if nse >= 0.5 else "nse-bad")
    return f'<span class="{cls}">{nse:.3f}</span>'


def _render_tool_log_html(tool_log: list) -> str:
    lines = []
    for e in tool_log:
        icon = {"done": "[OK]", "error": "[ERR]", "running": "..."}[e["status"]]
        cls  = {"done": "t-ok", "error": "t-err", "running": "t-run"}[e["status"]]
        sec  = (f'<span class="t-sec">{e["elapsed"]:.1f}s</span>'
                if e.get("elapsed") else "")
        nse  = (e.get("result") or {}).get("metrics", {}).get("NSE")
        hint = (f'<span class="t-hint">{_nse_badge_html(nse)}</span>' if nse else "")
        label = _tool_label(e["name"])
        lines.append(
            f'<div class="tool-row">'
            f'<span class="{cls}">{icon}</span> {label}{sec}{hint}'
            f'</div>'
        )
    return "\n".join(lines)


def _render_result_card(result: dict, name: str):
    if name not in ("calibrate_model", "llm_calibrate", "evaluate_model"):
        return
    metrics = result.get("metrics") or {}
    params  = result.get("best_params") or {}
    if not metrics and not params:
        return
    c1, c2 = st.columns(2)
    with c1:
        rows = {k: v for k, v in metrics.items()
                if k in ("NSE", "KGE", "RMSE", "Bias") and isinstance(v, float)}
        if rows:
            st.markdown("**Metrics**")
            md = "| Metric | Value |\n|--------|-------|\n" + "".join(
                f"| {k} | {v:.4f} |\n" for k, v in rows.items())
            st.markdown(md)
    with c2:
        if params:
            st.markdown("**Best Params**")
            md = "| Param | Value |\n|-------|-------|\n" + "".join(
                f"| {k} | {v:.4f} |\n" for k, v in params.items())
            st.markdown(md)


def _render_message(msg: dict):
    role = msg["role"]
    with st.chat_message(role):
        st.markdown(msg["content"])
        tools = msg.get("tools", [])

        # Collect all image paths from tool results and show inline gallery
        all_images: list[str] = []
        for e in tools:
            result = e.get("result") or {}
            for fp in (result.get("plot_paths") or result.get("figure_paths") or [])[:4]:
                if fp and fp not in all_images:
                    all_images.append(fp)

        if all_images:
            valid = [fp for fp in all_images if Path(str(fp)).exists()]
            if valid:
                if len(valid) == 1:
                    try:
                        st.image(valid[0], use_container_width=True)
                    except Exception:
                        pass
                else:
                    cols = st.columns(2)
                    for i, fp in enumerate(valid[:6]):
                        try:
                            with cols[i % 2]:
                                st.image(fp, use_container_width=True)
                        except Exception:
                            pass

        if not tools:
            return

        with st.expander(_t("tool_calls_n", len(tools)), expanded=False):
            for e in tools:
                # Show LLM thought before this tool (image 6 style)
                thought = e.get("thought_before", "")
                if thought:
                    with st.expander(_t("thinking"), expanded=False):
                        st.markdown(
                            f'<div class="thought-block">{thought}</div>',
                            unsafe_allow_html=True,
                        )

                # Tool row: dot + name + time + NSE badge
                icon  = {"done": "[OK]", "error": "[ERR]", "running": "..."}[e["status"]]
                cls   = {"done": "t-ok",  "error": "t-err",  "running": "t-run"}[e["status"]]
                label = _tool_label(e["name"])
                elapsed = f" {e['elapsed']:.1f}s" if e.get("elapsed") else ""
                nse     = (e.get("result") or {}).get("metrics", {}).get("NSE")
                nse_html = _nse_badge_html(nse) if nse else ""
                st.markdown(
                    f'<div class="tool-row">'
                    f'<span class="{cls}">{icon}</span> {label}'
                    f'<span class="t-sec">{elapsed}</span>{nse_html}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # Detail expander: args + result (image 8 style)
                clean_args = {k: v for k, v in (e.get("args") or {}).items()
                              if not k.startswith("_")}
                result = e.get("result")
                if clean_args or result:
                    with st.expander(_t("tool_detail"), expanded=False):
                        if clean_args:
                            st.caption(_t("tool_args"))
                            st.code(
                                json.dumps(clean_args, ensure_ascii=False, indent=2),
                                language="json",
                            )
                        if result:
                            st.caption(_t("tool_result"))
                            st.code(
                                json.dumps(result, ensure_ascii=False, indent=2),
                                language="json",
                            )
                            # Inline metric cards for calibration results
                            if e["name"] in ("calibrate_model", "llm_calibrate", "evaluate_model"):
                                _render_result_card(result, e["name"])


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def _render_sidebar():
    with st.sidebar:
        # Header
        st.markdown(f"**HydroClaw**")
        st.caption(_t("subtitle"))

        # Language toggle
        lang  = st.session_state.lang
        label = "EN" if lang == "zh" else "ZH"
        if st.button(label, use_container_width=True, key="lang_btn"):
            st.session_state.lang = "en" if lang == "zh" else "zh"
            st.rerun()

        st.divider()

        # Token usage
        st.markdown(f'<div class="sidebar-section">{_t("token_usage")}</div>',
                    unsafe_allow_html=True)
        prompt = st.session_state.token_prompt
        compl  = st.session_state.token_compl
        total  = st.session_state.token_total
        c1, c2 = st.columns(2)
        with c1:
            st.metric(_t("prompt"),     f"{prompt/1000:.1f}K" if prompt >= 1000 else str(prompt))
        with c2:
            st.metric(_t("completion"), f"{compl/1000:.1f}K"  if compl  >= 1000 else str(compl))
        total_label = f"{total/1000:.1f}K" if total >= 1000 else str(total)
        st.progress(min(total / 200000, 1.0), text=f"{_t('total')}: {total_label}")
        st.divider()

        # History (above skills)
        st.markdown(f'<div class="sidebar-section">{_t("history")}</div>',
                    unsafe_allow_html=True)
        sessions = _list_sessions(20)
        if sessions:
            for s in sessions:
                sid   = s.get("session_id", "")
                query = s.get("query", "")
                ts    = s.get("timestamp", "")[:16].replace("T", " ")
                n     = s.get("tool_calls", 0)
                title = (query[:38] + "...") if len(query) > 38 else query
                if st.button(title, key=f"h_{sid}", help=f"{ts}  |  {n} tools",
                             use_container_width=True):
                    st.session_state.view_session_id = sid
                    st.session_state.view = "chat"
                    st.rerun()
        else:
            st.caption(_t("no_history"))
        st.divider()

        # Skills (single collapsible expander; click skill name -> detail page)
        agent = st.session_state.get("agent")
        skill_list = (agent.skill_registry.list_all()
                      if agent and hasattr(agent, "skill_registry")
                      else _default_skills())
        with st.expander(_t("skills"), expanded=False):
            for sk in skill_list:
                if st.button(sk["name"], key=f"sk_{sk['name']}", use_container_width=True):
                    st.session_state.view           = "skills"
                    st.session_state.selected_skill = sk
                    st.rerun()
        st.divider()

        # New chat
        if st.button(_t("new_chat"), use_container_width=True, type="primary"):
            st.session_state.messages         = []
            st.session_state.all_tool_log     = []
            st.session_state.token_total      = 0
            st.session_state.token_prompt     = 0
            st.session_state.token_compl      = 0
            st.session_state.agent            = None
            st.session_state.event_queue      = queue.Queue()
            st.session_state.view_session_id  = None
            st.session_state.last_nse         = None
            st.session_state.task_data        = None
            st.session_state.conv_id          = None
            st.session_state.show_token_warn  = False
            st.session_state.token_warn_acked = False
            st.session_state.current_thought  = ""
            st.rerun()


def _default_skills() -> list[dict]:
    return [
        {"name": "Standard Calibration",  "description": "SCE-UA/GA/scipy parameter optimization for GR4J/XAJ/GR5J/GR6J.", "when_to_use": "User asks to calibrate a model on a basin."},
        {"name": "LLM Calibration",        "description": "Multi-round calibration with LLM-guided parameter range adjustment.", "when_to_use": "User wants intelligent / autonomous calibration."},
        {"name": "Batch Calibration",      "description": "Calibrate multiple basins or models in one autonomous batch run.", "when_to_use": "User specifies 2+ basins or models."},
        {"name": "Model Comparison",       "description": "Compare NSE/KGE across models side-by-side.", "when_to_use": "User wants to know which model fits best."},
        {"name": "Code Analysis",          "description": "Generate and execute custom Python analysis scripts.", "when_to_use": "User wants custom plots, statistics, or data exploration."},
        {"name": "Visualization",          "description": "Produce hydrograph, scatter, FDC, and parameter box-plots.", "when_to_use": "User asks for figures or plots."},
    ]


# ---------------------------------------------------------------------------
# Execution panel (right column)
# ---------------------------------------------------------------------------

def _render_exec_panel():
    st.markdown('<div class="panel-col-border">', unsafe_allow_html=True)

    lang     = st.session_state.get("lang", "zh")
    running  = st.session_state.agent_running
    thinking = st.session_state.thinking
    cur_tool = st.session_state.current_tool
    tool_log = st.session_state.all_tool_log

    # Status + Stop button
    if running:
        dot = '<span class="status-dot-run"></span>'
        if thinking:
            status_text = _t("agent_thinking")
        elif cur_tool:
            status_text = f'{_t("agent_running")}: {_tool_label(cur_tool)}'
        else:
            status_text = _t("running_label")
    else:
        dot = '<span class="status-dot-idle"></span>'
        status_text = _t("agent_idle")

    hdr_col, stop_col = st.columns([3, 1])
    with hdr_col:
        st.markdown(
            f'<div class="panel-title">{_t("task_panel")}</div>'
            f'<div style="font-size:0.87rem;margin-bottom:4px">{dot}{status_text}</div>',
            unsafe_allow_html=True,
        )
    with stop_col:
        if running:
            stop_label = "停止" if lang == "zh" else "Stop"
            if st.button(stop_label, key="stop_btn", use_container_width=True):
                agent_obj = st.session_state.get("agent")
                if agent_obj and hasattr(agent_obj, "request_stop"):
                    agent_obj.request_stop()
                st.rerun()

    # Calibration progress bar
    cp = st.session_state.get("calibration_progress")
    if running and cp and cur_tool in ("calibrate_model", "llm_calibrate"):
        pct   = cp.get("pct", 0.0)
        elaps = cp.get("elapsed", 0.0)
        evcnt = cp.get("eval_count", 0)
        rep   = cp.get("rep", 0)
        algo  = cp.get("algo", "")
        rlbl  = cp.get("round_label", "")
        prefix = f"{rlbl} " if rlbl else ""
        if evcnt > 0 and rep > 0:
            bar_text = f"{prefix}{algo} {evcnt}/{rep} ({pct:.0f}%) · {elaps:.0f}s"
        else:
            bar_text = f"{prefix}{algo} {elaps:.0f}s"
        st.progress(min(pct / 100.0, 1.0), text=bar_text)

    # Tool detail cards (image 8 style) — most recent first
    if tool_log:
        lbl_args   = "工具参数" if lang == "zh" else "Parameters"
        lbl_result = "执行结果" if lang == "zh" else "Result"

        for e in reversed(tool_log[-12:]):
            icon  = {"done": "[OK]", "error": "[ERR]", "running": "..."}[e["status"]]
            label = _tool_label(e["name"])
            elapsed = f" {e['elapsed']:.1f}s" if e.get("elapsed") else ""
            nse = (e.get("result") or {}).get("metrics", {}).get("NSE")
            nse_str = f"  NSE={nse:.3f}" if isinstance(nse, float) else ""
            header = f"{icon} {label}{elapsed}{nse_str}"

            with st.expander(header, expanded=False):
                clean_args = {k: v for k, v in (e.get("args") or {}).items()
                              if not k.startswith("_")}
                if clean_args:
                    st.caption(lbl_args)
                    st.code(
                        json.dumps(clean_args, ensure_ascii=False, indent=2),
                        language="json",
                    )
                if e.get("result"):
                    st.caption(lbl_result)
                    st.code(
                        json.dumps(e["result"], ensure_ascii=False, indent=2),
                        language="json",
                    )

    # Batch task progress
    if st.session_state.task_data:
        st.divider()
        data  = st.session_state.task_data
        tasks = data.get("tasks", [])
        if tasks:
            total   = len(tasks)
            done    = sum(1 for t in tasks if t["status"] == "done")
            failed  = sum(1 for t in tasks if t["status"] == "failed")
            pending = total - done - failed
            st.markdown(f"**{_t('batch_progress')}**")
            st.progress(done / total)
            st.caption(
                f"{done} {_t('done')}  /  {failed} {_t('failed')}  /  "
                f"{pending} {_t('pending')}  (total {total})"
            )
            for task in tasks[-10:]:
                icon = {"done": "[OK]", "failed": "[ERR]",
                        "running": "...", "pending": "   "}.get(task["status"], "?")
                desc = task.get("description", task["id"])[:40]
                nse  = (task.get("result") or {}).get("NSE")
                nse_str = f" NSE={nse:.3f}" if isinstance(nse, float) else ""
                st.caption(f"{icon} {desc}{nse_str}")

    st.markdown('</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Skills detail page
# ---------------------------------------------------------------------------

def _render_skills_page():
    if st.button(f"<- {_t('back_to_chat')}", key="back_btn"):
        st.session_state.view = "chat"
        st.rerun()

    lang = st.session_state.get("lang", "zh")
    st.markdown(f"### {_t('skills_page')}")
    st.divider()

    agent      = st.session_state.get("agent")
    skill_list = (agent.skill_registry.list_all()
                  if agent and hasattr(agent, "skill_registry")
                  else _default_skills())

    selected = st.session_state.get("selected_skill")

    # Labels
    lbl_desc  = "描述"         if lang == "zh" else "Description"
    lbl_when  = "适用场景"     if lang == "zh" else "When to use"
    lbl_tools = "调用工具"     if lang == "zh" else "Tools"
    lbl_guide = "查看完整指南" if lang == "zh" else "Full guide"
    lbl_err   = "无法加载指南" if lang == "zh" else "Could not load guide."

    for sk in skill_list:
        is_sel = selected and selected["name"] == sk["name"]
        with st.expander(sk["name"], expanded=is_sel):
            desc = sk.get("description", "")
            when = sk.get("when_to_use", "")
            tools_used = sk.get("tools", [])

            if desc:
                st.caption(f"**{lbl_desc}**: {desc}")
            if when:
                st.caption(f"**{lbl_when}**: {when}")
            if tools_used:
                st.caption(f"**{lbl_tools}**: {', '.join(tools_used)}")

            # Try to load skill.md for full detail
            # web_app.py is in interface/, skills are in hydroclaw/skills/
            _skills_root = Path(__file__).parent.parent / "skills"
            skill_md_path = (_skills_root /
                             sk["name"].lower().replace(" ", "_") / "skill.md")
            if not skill_md_path.exists():
                skills_dir = _skills_root
                if not skills_dir.exists():
                    skills_dir = None
                for d in (skills_dir.iterdir() if skills_dir else []):
                    if d.is_dir() and (d.name in sk["name"].lower() or
                                       sk["name"].lower() in d.name):
                        candidate = d / "skill.md"
                        if candidate.exists():
                            skill_md_path = candidate
                            break

            if skill_md_path.exists():
                with st.expander(lbl_guide, expanded=False):
                    try:
                        content = skill_md_path.read_text(encoding="utf-8")
                        # Wrap in .skill-guide to downscale headings via CSS
                        st.markdown(
                            f'<div class="skill-guide">{content}</div>',
                            unsafe_allow_html=True,
                        )
                    except Exception:
                        st.caption(lbl_err)


# ---------------------------------------------------------------------------
# Session history preview
# ---------------------------------------------------------------------------

def _maybe_show_session_preview():
    sid = st.session_state.get("view_session_id")
    if not sid:
        return
    with st.expander(f"History: {sid}", expanded=True):
        msgs = _load_session_messages(sid)
        if msgs:
            for msg in msgs:
                _render_message(msg)
        else:
            st.caption("Could not load session.")
        c1, c2 = st.columns(2)
        with c1:
            if st.button(_t("load_session"), key="load_h"):
                snap = _load_web_snapshot(sid)
                if snap:
                    # Full restore: messages + tool log + token counts
                    st.session_state.messages     = snap.get("messages", [])
                    st.session_state.all_tool_log = snap.get("all_tool_log", [])
                    st.session_state.token_total  = snap.get("token_total", 0)
                    st.session_state.token_prompt = snap.get("token_prompt", 0)
                    st.session_state.token_compl  = snap.get("token_compl", 0)
                else:
                    # Legacy fallback: rebuild from JSONL
                    msgs = _load_session_messages(sid)
                    st.session_state.messages = msgs
                    st.session_state.all_tool_log = [
                        t for m in msgs for t in m.get("tools", [])
                    ]
                st.session_state.view_session_id = None
                st.rerun()
        with c2:
            if st.button(_t("close"), key="close_h"):
                st.session_state.view_session_id = None
                st.rerun()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _render_token_warning():
    """1M token warning: shown inline above chat when triggered."""
    if not st.session_state.show_token_warn:
        return
    lang = st.session_state.get("lang", "zh")
    total = st.session_state.token_total
    if lang == "zh":
        msg  = f"已累计使用 **{total/1e6:.2f}M tokens**，达到 100 万 token 阈值。"
        cont = "继续对话"
        stop = "停止当前任务"
    else:
        msg  = f"Token usage reached **{total/1e6:.2f}M tokens** (1M threshold)."
        cont = "Continue"
        stop = "Stop current task"

    st.warning(msg)
    c1, c2 = st.columns(2)
    with c1:
        if st.button(cont, key="tok_warn_cont", type="primary", use_container_width=True):
            st.session_state.token_warn_acked = True
            st.session_state.show_token_warn  = False
            st.rerun()
    with c2:
        if st.button(stop, key="tok_warn_stop", use_container_width=True):
            agent_obj = st.session_state.get("agent")
            if agent_obj and hasattr(agent_obj, "request_stop"):
                agent_obj.request_stop()
            st.session_state.show_token_warn  = False
            st.session_state.token_warn_acked = True
            st.rerun()


def main():
    _init_state()
    _inject_css()

    # Setup file logging once per session
    if not st.session_state.get("_logging_setup"):
        _setup_web_logging()
        st.session_state["_logging_setup"] = True

    # Process ALL pending events at the very start of each render cycle.
    # This ensures exec panel and chat both see up-to-date state.
    events_changed = _process_events()

    _render_sidebar()

    # Skills page view
    if st.session_state.view == "skills":
        _render_skills_page()
        return

    # --- Chat view: split into chat (left) + exec panel (right) ---
    col_chat, col_panel = st.columns([3, 1], gap="medium")

    with col_panel:
        _render_exec_panel()

    with col_chat:
        st.markdown(f"### {_t('title')}")
        st.divider()

        _render_token_warning()
        _maybe_show_session_preview()

        for msg in st.session_state.messages:
            _render_message(msg)

        live_placeholder = st.empty()

        # ask_user form — shown when agent needs user input
        if st.session_state.ask_user_q:
            aq = st.session_state.ask_user_q
            with st.form("ask_user_form", clear_on_submit=True):
                if aq.get("context"):
                    st.caption(aq["context"])
                st.markdown(f"**{aq['question']}**")
                answer    = st.text_input("回答", label_visibility="collapsed")
                submitted = st.form_submit_button("Submit")
                if submitted:
                    ans = answer.strip()
                    if ans:
                        # Send via dedicated per-request queue (avoids event_queue collision)
                        aq["answer_q"].put(ans)
                        aq["event"].set()
                        st.session_state.ask_user_q = None
                        st.rerun()

        # Auto-refresh while agent is running
        if st.session_state.agent_running:
            tool_log = st.session_state.tool_log
            thought  = st.session_state.current_thought
            if tool_log or thought or st.session_state.thinking:
                with live_placeholder.container():
                    with st.chat_message("assistant"):
                        # Thinking / thought display (image 6 style)
                        if st.session_state.thinking and not thought:
                            st.markdown(
                                f'<div class="thought-block">'
                                f'{_t("agent_thinking")}</div>',
                                unsafe_allow_html=True,
                            )
                        if thought:
                            with st.expander(_t("thinking"), expanded=True):
                                st.markdown(
                                    f'<div class="thought-block">{thought}</div>',
                                    unsafe_allow_html=True,
                                )
                        # Live tool call lines (image 7 style)
                        for e in tool_log:
                            icon  = {"done": "[OK]", "error": "[ERR]", "running": "..."}[e["status"]]
                            cls   = {"done": "t-ok", "error": "t-err", "running": "t-run"}[e["status"]]
                            label = _tool_label(e["name"])
                            elapsed = f" {e['elapsed']:.1f}s" if e.get("elapsed") else ""
                            nse = (e.get("result") or {}).get("metrics", {}).get("NSE")
                            nse_html = _nse_badge_html(nse) if nse else ""
                            st.markdown(
                                f'<div class="tool-row">'
                                f'<span class="{cls}">{icon}</span> {label}'
                                f'<span class="t-sec">{elapsed}</span>{nse_html}'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                            # Progress bar for calibration tools
                            cp = st.session_state.get("calibration_progress")
                            if (e["status"] == "running"
                                    and e["name"] in ("calibrate_model", "llm_calibrate")
                                    and cp):
                                pct  = cp.get("pct", 0.0)
                                elap = cp.get("elapsed", 0.0)
                                evc  = cp.get("eval_count", 0)
                                rep  = cp.get("rep", 0)
                                algo = cp.get("algo", "")
                                rlbl = cp.get("round_label", "")
                                pfx  = f"{rlbl} " if rlbl else ""
                                if evc > 0 and rep > 0:
                                    txt = f"{pfx}{algo} {evc}/{rep} ({pct:.0f}%) · {elap:.0f}s"
                                else:
                                    txt = f"{pfx}{algo} 进行中... {elap:.0f}s"
                                st.progress(min(pct / 100.0, 1.0), text=txt)
            time.sleep(0.3)
            st.rerun()
        else:
            live_placeholder.empty()
            if events_changed:
                st.rerun()

        # Chat input
        if prompt := st.chat_input(
            _t("input"),
            disabled=st.session_state.agent_running,
        ):
            # Append only — do NOT render immediately to avoid duplicate.
            # The message loop above will render it on the next rerun.
            st.session_state.messages.append({"role": "user", "content": prompt})
            _run_agent_background(prompt)
            st.rerun()


if __name__ == "__main__":
    main()
