"""
HydroClaw Web Server — FastAPI + WebSocket
==========================================
No npm, no build step. Serves a single HTML file with vanilla JS.

Launch:
    python -m hydroclaw --server              # port 7860
    python -m hydroclaw --server --port 8080
"""
import asyncio
import contextlib
import io
import json
import logging
import threading
import time
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger("hydroclaw.server")

_STATIC = Path(__file__).parent / "static"


def _json_safe(obj):
    """Recursively convert non-JSON-serializable values to strings."""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    return str(obj)


def create_app(workspace: str = ".") -> FastAPI:
    ws_path = Path(workspace).resolve()
    app = FastAPI(title="HydroClaw", docs_url=None, redoc_url=None)

    if _STATIC.exists():
        app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")

    # ------------------------------------------------------------------ routes

    @app.get("/")
    async def index():
        p = _STATIC / "index.html"
        return FileResponse(str(p)) if p.exists() else HTMLResponse(
            "<h1>HydroClaw</h1><p>Missing static/index.html</p>")

    @app.get("/file")
    async def serve_file(path: str):
        """Serve local files with smart path resolution (workspace-aware)."""
        from hydroclaw.utils.path_utils import resolve_path
        resolved = resolve_path(path, ws_path)
        if resolved and resolved.is_file():
            return FileResponse(str(resolved))
        return HTMLResponse("Not found", status_code=404)

    @app.get("/api/sessions")
    async def api_sessions():
        sdir = ws_path / "sessions"
        out = []
        if sdir.exists():
            for f in sorted(sdir.glob("*_summary.json"),
                            key=lambda x: x.stat().st_mtime, reverse=True)[:30]:
                try:
                    out.append(json.loads(f.read_text(encoding="utf-8")))
                except Exception:
                    pass
        return out

    @app.get("/api/sessions/{sid}")
    async def api_session_get(sid: str):
        sdir = ws_path / "sessions"
        # Prefer full web snapshot (saved by JS after each run)
        p = sdir / f"{sid}_web.json"
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
        # Fallback: reconstruct from summary.json (legacy / first-time load)
        s = sdir / f"{sid}_summary.json"
        if s.exists():
            try:
                meta = json.loads(s.read_text(encoding="utf-8"))
                q = meta.get("query", "")
                ans = meta.get("final_response_preview", "")
                msgs = []
                if q:
                    msgs.append({"role": "user", "content": q})
                if ans:
                    msgs.append({"role": "assistant", "content": ans +
                                 ("\n\n*(历史摘要，完整内容不可用)*" if len(ans) >= 490 else ""),
                                 "tools": []})
                return {"session_id": sid, "messages": msgs}
            except Exception:
                pass
        return {}

    @app.post("/api/sessions/{sid}")
    async def api_session_save(sid: str, data: dict):
        """Client POSTs full message history here so it survives page reloads."""
        sdir = ws_path / "sessions"
        sdir.mkdir(parents=True, exist_ok=True)
        (sdir / f"{sid}_web.json").write_text(
            json.dumps({"session_id": sid, **data}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return {"ok": True}

    @app.get("/api/skills")
    async def api_skills():
        try:
            from hydroclaw.skill_registry import SkillRegistry
            # Skills live in the hydroclaw package, not the workspace
            skills_dir = Path(__file__).parent.parent / "skills"
            return SkillRegistry(skills_dir).list_all()
        except Exception:
            return []

    # --------------------------------------------------------------- websocket

    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket):
        await websocket.accept()
        loop = asyncio.get_running_loop()
        out_q: asyncio.Queue = asyncio.Queue()

        def emit(ev: dict):
            """Thread-safe: put event from sync agent thread into async queue."""
            loop.call_soon_threadsafe(out_q.put_nowait, _json_safe(ev))

        ui = _ServerUI(emit)
        try:
            from hydroclaw.agent import HydroClaw
            agent = HydroClaw(workspace=ws_path, ui=ui)
        except Exception as exc:
            await websocket.send_json({"type": "error", "msg": f"Agent init failed: {exc}"})
            return

        agent_future = None

        async def _sender():
            while True:
                ev = await out_q.get()
                try:
                    await websocket.send_json(ev)
                except WebSocketDisconnect:
                    return
                except Exception as exc:
                    logger.warning("send_json failed (skipping event): %s", exc)

        async def _receiver():
            nonlocal agent_future
            try:
                async for raw in websocket.iter_text():
                    try:
                        msg = json.loads(raw)
                    except Exception:
                        continue
                    t = msg.get("type", "")

                    if t == "query":
                        text = msg.get("text", "").strip()
                        if not text:
                            continue
                        if agent_future and not agent_future.done():
                            await websocket.send_json(
                                {"type": "error", "msg": "Agent is already running."})
                            continue
                        prior = msg.get("prior_messages") or None

                        def _run():
                            try:
                                agent.run(text, prior_messages=prior)
                                emit({"type": "session_id", "id": agent.memory.session_id})
                            except Exception as exc:
                                msg = str(exc)
                                # Classify critical errors for targeted UI alerts
                                if "429" in msg or "rate_limit" in msg.lower() or "quota" in msg.lower():
                                    emit({"type": "error", "msg": f"[429] API 限速或额度耗尽: {msg}"})
                                elif any(k in msg.lower() for k in ("timeout", "connection", "network", "500", "502", "503")):
                                    emit({"type": "error", "msg": f"[网络错误] {msg}"})
                                else:
                                    emit({"type": "error", "msg": msg})
                            finally:
                                try:
                                    tok = agent.llm.tokens.summary()
                                except Exception:
                                    tok = {}
                                emit({"type": "done", "tokens": tok})

                        agent_future = loop.run_in_executor(None, _run)

                    elif t == "user_answer":
                        ui.provide_user_answer(msg.get("text", ""))
                    elif t == "stop":
                        if hasattr(agent, "request_stop"):
                            agent.request_stop()
                        # Acknowledge stop immediately so the UI knows it was received.
                        # The agent will actually stop between tool calls; if calibration
                        # is running inside a tool it will complete first (spotpy is blocking).
                        await websocket.send_json({"type": "stopping"})
                    elif t == "ping":
                        await websocket.send_json({"type": "pong"})
            except WebSocketDisconnect:
                pass

        try:
            await asyncio.gather(_sender(), _receiver())
        except WebSocketDisconnect:
            if hasattr(agent, "request_stop"):
                agent.request_stop()

    return app


# ---------------------------------------------------------------- UI bridge

class _ServerUI:
    """Bridges the synchronous agent thread and the async WebSocket queue."""
    mode = "user"

    def __init__(self, emit):
        self._emit = emit
        self._t0 = 0.0
        self._ans_evt = threading.Event()
        self._ans = ""

    def _e(self, **kw):
        self._emit(kw)

    def on_query(self, q):                pass
    def on_answer(self, text, turns):     self._e(type="answer", text=text)
    def on_error(self, msg):              self._e(type="error", msg=msg)
    def on_max_turns(self):               self._e(type="error", msg="Max turns reached.")
    def dev_log(self, msg):               pass
    def print_banner(self, *a, **kw):     pass

    def on_thought(self, text, turn):
        if text and text.strip():
            self._e(type="thought", text=text.strip())

    def on_tool_start(self, name, args):
        self._t0 = time.time()
        self._e(type="tool_start", name=name, args=args)

    def on_tool_end(self, name, result, elapsed=None):
        if elapsed is None:
            elapsed = time.time() - self._t0
        self._e(type="tool_end", name=name, result=result, elapsed=round(elapsed, 2))

    def on_calibration_progress(self, pct, elapsed, eval_count, rep,
                                algo, round_label=""):
        self._e(type="calibration_progress", pct=pct, elapsed=round(elapsed, 1),
                eval_count=eval_count, rep=rep, algo=algo, round_label=round_label)

    def on_task_progress(self, workspace):  pass
    def on_session_summary(self, *a, **kw): pass

    def ask_user(self, question, context=None):
        self._ans_evt.clear()
        self._ans = ""
        self._e(type="ask_user", question=question, context=context or "")
        self._ans_evt.wait(timeout=300)
        return self._ans

    def provide_user_answer(self, text: str):
        self._ans = text
        self._ans_evt.set()

    @contextlib.contextmanager
    def thinking(self, turn):
        self._e(type="thinking_start")
        try:
            yield
        finally:
            self._e(type="thinking_end")

    @contextlib.contextmanager
    def suppress_tool_output(self, name):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            yield
