"""
HydroAgent Web Server — FastAPI + WebSocket
==========================================
No npm, no build step. Serves a single HTML file with vanilla JS.

Launch:
    python -m hydroagent --server              # port 7860
    python -m hydroagent --server --port 8080
"""
import asyncio
import contextlib
import io
import json
import logging
import threading
import time
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger("hydroagent.server")

_STATIC = Path(__file__).parent / "static"

# ── Public dataset catalog ────────────────────────────────────────────────────
_PUBLIC_DATASETS = [
    {"name": "camels_us",  "label": "CAMELS-US",  "region": "美国",  "basins": 671,   "size": "14.6 GB", "dir": "CAMELS_US",  "time_units": ["1D"]},
    {"name": "camels_gb",  "label": "CAMELS-GB",  "region": "英国",  "basins": 671,   "size": "244 MB",  "dir": "CAMELS_GB",  "time_units": ["1D"]},
    {"name": "camels_br",  "label": "CAMELS-BR",  "region": "巴西",  "basins": 897,   "size": "1.4 GB",  "dir": "CAMELS_BR",  "time_units": ["1D"]},
    {"name": "camels_aus", "label": "CAMELS-AUS", "region": "澳洲",  "basins": 561,   "size": "2.1 GB",  "dir": "CAMELS_AUS", "time_units": ["1D"]},
    {"name": "camels_cl",  "label": "CAMELS-CL",  "region": "智利",  "basins": 516,   "size": "208 MB",  "dir": "CAMELS_CL",  "time_units": ["1D"]},
    {"name": "camels_de",  "label": "CAMELS-DE",  "region": "德国",  "basins": 1582,  "size": "2.2 GB",  "dir": "CAMELS_DE",  "time_units": ["1D"]},
    {"name": "camels_fr",  "label": "CAMELS-FR",  "region": "法国",  "basins": 654,   "size": "364 MB",  "dir": "CAMELS_FR",  "time_units": ["1D"]},
    {"name": "camels_ind", "label": "CAMELS-IND", "region": "印度",  "basins": 472,   "size": "529 MB",  "dir": "CAMELS_IND", "time_units": ["1D"]},
    {"name": "caravan",    "label": "Caravan",    "region": "全球",  "basins": 16299, "size": "24.8 GB", "dir": "Caravan",    "time_units": ["1D"]},
    {"name": "lamah_ce",   "label": "LamaH-CE",   "region": "中欧",  "basins": 859,   "size": "16.3 GB", "dir": "LamaH_CE",   "time_units": ["1D", "3h"]},
    {"name": "hysets",     "label": "HYSETS",     "region": "北美",  "basins": 14425, "size": "41.9 GB", "dir": "HYSETS",     "time_units": ["1D"]},
]


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
    app = FastAPI(title="HydroAgent", docs_url=None, redoc_url=None)

    if _STATIC.exists():
        app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")

    # ------------------------------------------------------------------ routes

    @app.get("/")
    async def index():
        p = _STATIC / "index.html"
        return FileResponse(str(p)) if p.exists() else HTMLResponse(
            "<h1>HydroAgent</h1><p>Missing static/index.html</p>")

    @app.get("/file")
    async def serve_file(path: str):
        """Serve local files with smart path resolution (workspace-aware)."""
        from hydroagent.utils.path_utils import resolve_path
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

    @app.delete("/api/sessions/{sid}")
    async def api_session_delete(sid: str):
        """Delete both summary and web snapshot files for a session."""
        sdir = ws_path / "sessions"
        deleted = []
        for suffix in ("_summary.json", "_web.json"):
            f = sdir / f"{sid}{suffix}"
            if f.exists():
                try:
                    f.unlink()
                    deleted.append(str(f.name))
                except Exception as e:
                    logger.warning("Failed to delete %s: %s", f, e)
        return {"ok": True, "deleted": deleted}

    from pydantic import BaseModel as _BM
    from typing import Optional as _Opt

    class _SessionPatch(_BM):
        title: _Opt[str] = None
        pinned: _Opt[bool] = None

    @app.patch("/api/sessions/{sid}")
    async def api_session_patch(sid: str, body: _SessionPatch):
        """Update title and/or pinned status in summary JSON."""
        sdir = ws_path / "sessions"
        s = sdir / f"{sid}_summary.json"
        if not s.exists():
            return JSONResponse({"error": "session not found"}, status_code=404)
        try:
            meta = json.loads(s.read_text(encoding="utf-8"))
        except Exception:
            return JSONResponse({"error": "corrupt summary"}, status_code=500)
        if body.title is not None:
            meta["title"] = body.title
        if body.pinned is not None:
            meta["pinned"] = body.pinned
        s.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True, "session_id": sid}

    @app.get("/api/skills")
    async def api_skills():
        try:
            from hydroagent.skill_registry import SkillRegistry
            # Skills live in the hydroagent package, not the workspace
            skills_dir = Path(__file__).parent.parent / "skills"
            return SkillRegistry(skills_dir).list_all()
        except Exception:
            return []

    # ── System info endpoints ─────────────────────────────────────────────────

    @app.get("/api/tools")
    async def api_tools():
        """Return list of registered tools with name, source, priority."""
        try:
            from hydroagent.tools import get_tool_registry_info
            return get_tool_registry_info()
        except Exception as e:
            logger.warning("api_tools error: %s", e)
            return []

    @app.get("/api/packages")
    async def api_packages():
        """Return hydro ecosystem packages: adapters + core hydro libs."""
        import importlib.metadata as _meta

        def _pkg_version(pkg: str) -> str:
            try:
                return _meta.version(pkg)
            except Exception:
                return ""

        def _pkg_installed(pkg: str) -> bool:
            try:
                _meta.version(pkg)
                return True
            except Exception:
                return False

        # Core hydro packages (always shown regardless of adapter status)
        CORE_HYDRO = [
            {
                "name": "hydromodel",
                "pip_name": "hydromodel",
                "label": "HydroModel",
                "role": "model",
                "description": "水文模型率定与模拟框架，支持 GR4J/GR5J/GR6J/LSTM 等模型，内置 SCE-UA/GA/scipy 多种优化算法",
                "detail": "提供 calibrate / evaluate / simulate 三类操作。HydroAgent 的核心率定能力由本包提供。支持 spotpy 接口的所有优化算法。",
            },
            {
                "name": "hydrodataset",
                "pip_name": "hydrodataset",
                "label": "HydroDataset",
                "role": "data",
                "description": "多区域公开流域数据集读取器，支持 CAMELS-US/GB/BR/AUS/CL/DE/FR 等",
                "detail": "基于 AquaFetch 自动下载并缓存为 NetCDF。通过 ~/hydro_setting.yml 配置数据路径，HydroAgent 启动时自动同步。",
                "operations": ["list_camels_basins", "check_camels_data"],
            },
            {
                "name": "hydrodatasource",
                "pip_name": "hydrodatasource",
                "label": "HydroDataSource",
                "role": "data",
                "description": "自制数据集读取器，支持用户自定义 CSV 格式流域数据，自动转换为 NC 缓存",
                "detail": "需要 attributes/、timeseries/1D/、1D_units_info.json 三类文件。在【数据集】面板可添加和转换。",
            },
        ]

        packages = []
        for p in CORE_HYDRO:
            installed = _pkg_installed(p["pip_name"])
            version = _pkg_version(p["pip_name"]) if installed else ""
            packages.append({
                "name": p["name"], "label": p["label"], "pip_name": p["pip_name"],
                "role": p["role"], "description": p["description"],
                "detail": p["detail"], "installed": installed, "version": version,
                "source": "core",
                # Preserve hardcoded operations from CORE_HYDRO (e.g. hydrodataset has
                # no adapter but its tool names are hardcoded above)
                "operations": p.get("operations", []),
            })

        # Reload external plugins so they appear without restart
        try:
            from hydroagent.adapters import reload_adapters
            reload_adapters(workspace=ws_path)
        except Exception:
            pass

        # Enrich with adapter operations and add any adapter-only entries
        try:
            from hydroagent.adapters import _adapters
            adapter_by_name = {a.name: a for a in _adapters}
            core_names = {p["name"] for p in packages}
            # Fill operations for core packages that have a matching adapter
            for p in packages:
                a = adapter_by_name.get(p["name"])
                if a:
                    p["operations"] = a.supported_operations()
                    p["zh_operations"] = dict(getattr(a, "zh_operations", {}) or {})
            # Add adapters not in CORE_HYDRO
            for a in _adapters:
                if a.name not in core_names:
                    zh_label = getattr(a, "zh_label", "") or ""
                    zh_ops   = dict(getattr(a, "zh_operations", {}) or {})
                    packages.append({
                        "name": a.name,
                        "label": zh_label or getattr(a, "description", "") or a.name,
                        "pip_name": a.name,
                        "role": "adapter",
                        "description": getattr(a, "description", ""),
                        "detail": f"外部插件 · priority={a.priority}",
                        "installed": True, "version": "",
                        "source": "adapter", "priority": a.priority,
                        "operations": a.supported_operations(),
                        "zh_operations": zh_ops,
                    })
        except Exception:
            pass

        return packages

    @app.post("/api/packages/install")
    async def api_packages_install(body: dict, background_tasks: BackgroundTasks):
        """pip install a package in the background."""
        pkg = (body.get("package") or "").strip()
        if not pkg or any(c in pkg for c in [";", "&", "|", "`", "$", "\n"]):
            return JSONResponse({"ok": False, "error": "无效包名"}, status_code=400)
        import sys, subprocess
        _install_status[pkg] = "installing"

        def _do_install():
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", pkg],
                    capture_output=True, text=True, timeout=300,
                )
                if result.returncode == 0:
                    _install_status[pkg] = "ok"
                else:
                    _install_status[pkg] = f"error:{result.stderr[-300:]}"
            except Exception as e:
                _install_status[pkg] = f"error:{e}"

        background_tasks.add_task(_do_install)
        return {"ok": True, "status": "installing"}

    @app.get("/api/packages/install-status")
    async def api_packages_install_status(package: str):
        return {"status": _install_status.get(package, "unknown")}

    _install_status: dict = {}

    # ── Plugin management (/api/plugins) ─────────────────────────────────────

    @app.get("/api/plugins")
    async def api_plugins_list():
        """List all registered external plugins (local_dir and single_file types)."""
        from hydroagent.utils.plugin_registry import PluginRegistry
        from hydroagent.adapters import _adapters
        registry = PluginRegistry(ws_path)
        plugins = registry.list_plugins()
        loaded_names = {a.name for a in _adapters}
        result = []
        for p in plugins:
            result.append({
                **p,
                "loaded": p["name"] in loaded_names,
            })
        return result

    @app.post("/api/plugins")
    async def api_plugins_add(body: dict):
        """Register a new local package or .py file as a plugin."""
        path = (body.get("path") or "").strip()
        name = (body.get("name") or None)
        description = body.get("description") or ""
        if not path:
            return JSONResponse({"ok": False, "error": "path is required"}, status_code=400)
        from hydroagent.tools.add_local_package import add_local_package
        result = add_local_package(
            path=path, name=name, description=description,
            _workspace=str(ws_path),
        )
        if result.get("success"):
            return {"ok": True, **result}
        return JSONResponse({"ok": False, "error": result.get("error")}, status_code=400)

    @app.patch("/api/plugins/{name}")
    async def api_plugins_patch(name: str, body: dict):
        """Enable or disable a registered plugin."""
        from hydroagent.utils.plugin_registry import PluginRegistry
        registry = PluginRegistry(ws_path)
        enabled = body.get("enabled")
        if enabled is None:
            return JSONResponse({"ok": False, "error": "enabled field required"}, status_code=400)
        ok = registry.enable(name) if enabled else registry.disable(name)
        if not ok:
            return JSONResponse({"ok": False, "error": f"Plugin '{name}' not found"}, status_code=404)
        return {"ok": True, "name": name, "enabled": enabled}

    @app.delete("/api/plugins/{name}")
    async def api_plugins_delete(name: str):
        """Remove a plugin from the registry."""
        from hydroagent.utils.plugin_registry import PluginRegistry
        registry = PluginRegistry(ws_path)
        ok = registry.remove(name)
        if not ok:
            return JSONResponse({"ok": False, "error": f"Plugin '{name}' not found"}, status_code=404)
        return {"ok": True, "name": name}

    @app.post("/api/plugins/{name}/reload")
    async def api_plugins_reload(name: str):
        """Hot-reload all adapters (picks up changes to a specific plugin)."""
        from hydroagent.adapters import reload_adapters, _adapters
        reload_adapters(ws_path)
        loaded = [a.name for a in _adapters]
        return {"ok": True, "loaded_adapters": loaded, "plugin_loaded": name in loaded}

    @app.get("/api/knowledge")
    async def api_knowledge():
        """Return list of knowledge files sorted by importance, with name and summary."""
        knowledge_dir = Path(__file__).parent.parent / "knowledge"
        # Priority order: calibration guide -> model parameters -> datasets -> rest
        _PRIORITY = {"calibration_guide": 0, "model_parameters": 1, "datasets": 2}
        out = []
        if knowledge_dir.exists():
            for f in sorted(knowledge_dir.iterdir(),
                            key=lambda p: (_PRIORITY.get(p.stem, 99), p.name)):
                if f.is_file() and f.suffix in (".md", ".json", ".yaml", ".yml", ".txt"):
                    try:
                        lines = f.read_text(encoding="utf-8").splitlines()
                        # Use first heading as title if available
                        title = next((l.lstrip("# ").strip() for l in lines if l.startswith("#")), f.stem)
                        summary_lines = [l.strip() for l in lines if l.strip() and not l.startswith("#")][:2]
                        summary = " ".join(summary_lines)[:120]
                    except Exception:
                        title = f.stem
                        summary = ""
                    out.append({"name": f.name, "title": title, "summary": summary})
        return out

    @app.get("/api/knowledge/{filename}")
    async def api_knowledge_file(filename: str):
        """Return content of a specific knowledge file."""
        knowledge_dir = Path(__file__).parent.parent / "knowledge"
        # Sanitize: only allow simple filenames, no path traversal
        if "/" in filename or "\\" in filename or ".." in filename:
            return JSONResponse({"error": "invalid"}, status_code=400)
        f = knowledge_dir / filename
        if not f.exists() or not f.is_file():
            return JSONResponse({"error": "not found"}, status_code=404)
        try:
            content = f.read_text(encoding="utf-8")
            return {"name": filename, "content": content}
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    @app.get("/api/memory")
    async def api_memory():
        """Return workspace MEMORY.md content and list of basin profiles."""
        memory_text = ""
        mem_file = ws_path / "MEMORY.md"
        if mem_file.exists():
            try:
                memory_text = mem_file.read_text(encoding="utf-8")[:4000]
            except Exception:
                memory_text = ""

        basin_profiles = []
        profiles_dir = ws_path / "basin_profiles"
        if profiles_dir.exists():
            for f in sorted(profiles_dir.glob("*.json")):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    # Summarise the most recent calibration record for the badge
                    records = data.get("records", [])
                    latest = records[-1] if records else {}
                    basin_profiles.append({
                        "basin_id": f.stem,
                        "model": latest.get("model", data.get("model", "")),
                        "nse": latest.get("train_nse", data.get("best_nse", data.get("nse"))),
                        "detail": data,   # full JSON for the expandable view
                    })
                except Exception:
                    basin_profiles.append({"basin_id": f.stem, "model": "", "nse": None, "detail": {}})

        return {"memory_text": memory_text, "basin_profiles": basin_profiles}

    # ── Dataset endpoints ─────────────────────────────────────────────────────

    @app.get("/api/datasets")
    async def api_datasets():
        """Return public dataset catalog with local status, plus saved custom datasets."""
        try:
            from hydroagent.config import load_config
            cfg = load_config()
            dataset_dir = cfg.get("paths", {}).get("dataset_dir") or ""
        except Exception:
            dataset_dir = ""

        dataset_base = Path(dataset_dir) if dataset_dir else Path(".")

        public = []
        for entry in _PUBLIC_DATASETS:
            check_path = dataset_base / entry["dir"]
            ready = check_path.exists() and check_path.is_dir()
            public.append({
                **entry,
                "status": "ready" if ready else "not_downloaded",
                "local_path": str(check_path) if ready else None,
            })

        # Load custom datasets from config override JSON
        override_file = ws_path / "hydroagent_config_override.json"
        custom = []
        if override_file.exists():
            try:
                override = json.loads(override_file.read_text(encoding="utf-8"))
                for ds in override.get("custom_datasets", []):
                    data_path = Path(ds.get("data_path", ""))
                    ds_name = ds.get("dataset_name", "")
                    ds_unit = ds.get("time_unit", "")
                    # NC files are stored in hydrodatasource's CACHE_DIR, not in data_path
                    if ds.get("nc_cached") or _is_nc_cached(ds_name, ds_unit):
                        cache_status = "cached"
                    elif data_path.exists():
                        cache_status = "uncached"
                    else:
                        cache_status = "missing"
                    custom.append({**ds, "cache_status": cache_status})
            except Exception:
                pass

        return {"public": public, "custom": custom}

    class _CustomDataset(_BM):
        data_path: str
        dataset_name: str
        time_unit: str = "1D"

    @app.post("/api/datasets/custom")
    async def api_datasets_custom_add(body: _CustomDataset):
        """Validate and save a custom dataset to config override JSON."""
        data_path = Path(body.data_path)
        if not data_path.exists():
            return JSONResponse({"success": False, "error": f"路径不存在: {body.data_path}"}, status_code=400)

        # Try to validate/convert using SelfMadeHydroDataset
        basin_count = 0
        try:
            from hydrodatasource.reader.data_source import SelfMadeHydroDataset
            logger.info("[dataset] converting %s at %s (time_unit=%s)",
                        body.dataset_name, data_path, body.time_unit)
            ds = SelfMadeHydroDataset(
                data_path=str(data_path),
                dataset_name=body.dataset_name,
                time_unit=[body.time_unit],
            )
            ids = ds.read_object_ids() if hasattr(ds, "read_object_ids") else []
            basin_count = len(ids) if ids is not None else 0
            logger.info("[dataset] OK: %s — %d basins", body.dataset_name, basin_count)
        except ImportError:
            logger.warning("[dataset] hydrodatasource not installed — skipping NC conversion")
        except Exception as e:
            import traceback as _tb
            logger.error("[dataset] NC conversion FAILED for %s:\n%s",
                         body.dataset_name, _tb.format_exc())
            return JSONResponse(
                {"success": False, "error": str(e), "detail": _tb.format_exc()},
                status_code=400,
            )

        # Save to override JSON
        override_file = ws_path / "hydroagent_config_override.json"
        override = {}
        if override_file.exists():
            try:
                override = json.loads(override_file.read_text(encoding="utf-8"))
            except Exception:
                override = {}
        custom_list = override.get("custom_datasets", [])
        # Remove existing entry with same (dataset_name, time_unit) — allow multiple time units
        custom_list = [d for d in custom_list if not (
            d.get("dataset_name") == body.dataset_name and d.get("time_unit") == body.time_unit
        )]
        custom_list.append({
            "data_path": str(data_path),
            "dataset_name": body.dataset_name,
            "time_unit": body.time_unit,
            "basin_count": basin_count,
        })
        override["custom_datasets"] = custom_list
        override_file.write_text(json.dumps(override, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"success": True, "basin_count": basin_count}

    @app.delete("/api/datasets/custom/{name}")
    async def api_datasets_custom_delete(name: str, time_unit: str = ""):
        """Remove a custom dataset entry. If time_unit provided, remove only that entry."""
        override_file = ws_path / "hydroagent_config_override.json"
        if not override_file.exists():
            return {"ok": True}
        try:
            override = json.loads(override_file.read_text(encoding="utf-8"))
        except Exception:
            return {"ok": True}
        if time_unit:
            override["custom_datasets"] = [
                d for d in override.get("custom_datasets", [])
                if not (d.get("dataset_name") == name and d.get("time_unit") == time_unit)
            ]
        else:
            override["custom_datasets"] = [
                d for d in override.get("custom_datasets", [])
                if d.get("dataset_name") != name
            ]
        override_file.write_text(json.dumps(override, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True}

    def _is_nc_cached(dataset_name: str, time_unit: str = "") -> bool:
        """Return True if NC cache for the given time_unit exists in hydrodatasource CACHE_DIR."""
        try:
            from hydrodatasource.reader.data_source import CACHE_DIR
            cache_dir = Path(CACHE_DIR)
            if time_unit:
                # Check for timeseries NC specific to this time_unit
                return any(cache_dir.glob(f"{dataset_name}_timeseries_{time_unit}_*.nc")) or \
                       any(cache_dir.glob(f"{dataset_name}_stations_{time_unit}_*.nc"))
            # Fallback: any timeseries NC exists
            return any(cache_dir.glob(f"{dataset_name}_timeseries_*.nc"))
        except Exception:
            return False

    def _mark_nc_cached(dataset_name: str, time_unit: str = ""):
        """Persist nc_cached=True into the override JSON for the matching entry."""
        override_file = ws_path / "hydroagent_config_override.json"
        try:
            override = json.loads(override_file.read_text(encoding="utf-8")) \
                if override_file.exists() else {}
            for ds in override.get("custom_datasets", []):
                if ds.get("dataset_name") == dataset_name and \
                        (not time_unit or ds.get("time_unit") == time_unit):
                    ds["nc_cached"] = True
                    break
            override_file.write_text(
                json.dumps(override, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as e:
            logger.warning("[dataset] _mark_nc_cached failed: %s", e)

    # cache_status dict: dataset_name -> "caching" | "ready" | "error:<msg>"
    _cache_tasks: dict = {}

    @app.post("/api/datasets/custom/{name}/cache")
    async def api_datasets_cache(name: str, background_tasks: BackgroundTasks, time_unit: str = ""):
        """Start background NC cache creation for a custom dataset + time_unit."""
        override_file = ws_path / "hydroagent_config_override.json"
        if not override_file.exists():
            return JSONResponse({"ok": False, "error": "数据集未找到"}, status_code=404)
        try:
            override = json.loads(override_file.read_text(encoding="utf-8"))
        except Exception:
            return JSONResponse({"ok": False, "error": "配置读取失败"}, status_code=500)
        # Match by (dataset_name, time_unit); fall back to first match if time_unit not given
        entries = [d for d in override.get("custom_datasets", []) if d.get("dataset_name") == name]
        if time_unit:
            entry = next((d for d in entries if d.get("time_unit") == time_unit), None)
        else:
            entry = entries[0] if entries else None
        if not entry:
            return JSONResponse({"ok": False, "error": "数据集未找到"}, status_code=404)
        task_key = f"{name}__{entry.get('time_unit', '')}"
        if _cache_tasks.get(task_key) == "caching":
            return {"ok": True, "status": "caching", "message": "转换已在进行中"}
        entry_time_unit = entry.get("time_unit", "1D")
        was_cached = _is_nc_cached(name, entry_time_unit)
        _cache_tasks[task_key] = "caching"

        def _do_cache():
            try:
                from hydrodatasource.reader.data_source import SelfMadeHydroDataset, CACHE_DIR
                data_path = Path(entry["data_path"])
                ds = SelfMadeHydroDataset(
                    data_path=str(data_path),
                    dataset_name=name,
                    time_unit=[entry_time_unit],
                )
                basin_ids = list(ds.read_object_ids()) if hasattr(ds, "read_object_ids") else []
                action = "覆盖重新生成时序NC" if was_cached else "生成"
                logger.info("[dataset] caching %s/%s (%s) — %d basins",
                            name, entry_time_unit, action, len(basin_ids))
                # Attributes NC is shared across all time units.
                # Skip only when adding a new time unit and attributes already exist.
                # On explicit re-cache (was_cached=True), always regenerate.
                attr_nc = Path(CACHE_DIR) / f"{name}_attributes.nc"
                if hasattr(ds, "cache_attributes_xrdataset"):
                    if not was_cached and attr_nc.exists():
                        logger.info("[dataset] attributes NC already exists for %s, skipping", name)
                    else:
                        ds.cache_attributes_xrdataset()
                        logger.info("[dataset] attributes NC %s for %s",
                                    "regenerated" if was_cached else "created", name)
                # Timeseries NC is per time unit — always regenerate for the requested unit
                if hasattr(ds, "cache_timeseries_xrdataset"):
                    ds.cache_timeseries_xrdataset()
                _mark_nc_cached(name, entry_time_unit)
                _cache_tasks[task_key] = "ready"
                logger.info("[dataset] cache done: %s/%s", name, entry_time_unit)
            except Exception as e:
                import traceback as _tb2
                logger.error("[dataset] cache FAILED for %s/%s:\n%s",
                             name, entry_time_unit, _tb2.format_exc())
                _cache_tasks[task_key] = f"error:{e}"

        background_tasks.add_task(_do_cache)
        return {"ok": True, "status": "caching", "was_cached": was_cached, "time_unit": entry_time_unit}

    @app.get("/api/datasets/custom/{name}/cache-status")
    async def api_datasets_cache_status(name: str, time_unit: str = ""):
        """Poll NC cache creation status for a specific (name, time_unit)."""
        task_key = f"{name}__{time_unit}"
        status = _cache_tasks.get(task_key) or _cache_tasks.get(name, "unknown")
        disk_cached = _is_nc_cached(name, time_unit)
        if disk_cached:
            _cache_tasks[task_key] = "ready"
            status = "ready"
        return {"status": status, "cached": disk_cached}

    # ── Config endpoints ──────────────────────────────────────────────────────

    @app.get("/api/config")
    async def api_config_get():
        """Return current effective config (editable fields only)."""
        try:
            from hydroagent.config import load_config
            cfg = load_config()
        except Exception:
            cfg = {}

        # Load override JSON to know what user has customized
        override_file = ws_path / "hydroagent_config_override.json"
        override = {}
        if override_file.exists():
            try:
                override = json.loads(override_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        llm = cfg.get("llm", {})
        # Mask api_key: show first 4 + last 4 chars, rest as ***
        raw_key = llm.get("api_key", "")
        if raw_key and len(raw_key) > 8:
            masked_key = raw_key[:4] + "***" + raw_key[-4:]
        elif raw_key:
            masked_key = "***"
        else:
            masked_key = ""
        return {
            "model": llm.get("model", ""),
            "base_url": llm.get("base_url", ""),
            "api_key_masked": masked_key,
            "api_key_set": bool(raw_key),
            "temperature": llm.get("temperature", 0.1),
            "max_turns": cfg.get("max_turns", 30),
            "_override": override.get("llm", {}),
        }

    class _ConfigPatch(_BM):
        model: _Opt[str] = None
        base_url: _Opt[str] = None
        api_key: _Opt[str] = None
        temperature: _Opt[float] = None
        max_turns: _Opt[int] = None

    @app.post("/api/config")
    async def api_config_save(body: _ConfigPatch):
        """Save config overrides to workspace hydroagent_config_override.json."""
        override_file = ws_path / "hydroagent_config_override.json"
        override = {}
        if override_file.exists():
            try:
                override = json.loads(override_file.read_text(encoding="utf-8"))
            except Exception:
                override = {}

        if "llm" not in override:
            override["llm"] = {}
        if body.model is not None:
            override["llm"]["model"] = body.model
        if body.base_url is not None:
            override["llm"]["base_url"] = body.base_url
        if body.api_key is not None and body.api_key != "" and "***" not in body.api_key:
            override["llm"]["api_key"] = body.api_key
            # Also persist to project-level config so load_config() picks it up next run
            from hydroagent.config import _deep_merge
            proj_cfg_path = Path(__file__).parent.parent.parent / "hydroagent_config.json"
            proj_cfg = {}
            if proj_cfg_path.exists():
                try:
                    proj_cfg = json.loads(proj_cfg_path.read_text(encoding="utf-8"))
                except Exception:
                    proj_cfg = {}
            _deep_merge(proj_cfg, {"llm": {"api_key": body.api_key}})
            proj_cfg_path.write_text(json.dumps(proj_cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        if body.temperature is not None:
            override["llm"]["temperature"] = body.temperature
        if body.max_turns is not None:
            override["max_turns"] = body.max_turns

        override_file.write_text(json.dumps(override, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True}

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
            from hydroagent.agent import HydroAgent
            agent = HydroAgent(workspace=ws_path, ui=ui)
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
                        agent_mode = msg.get("agent_mode", "react")

                        def _run():
                            try:
                                if agent_mode == "pipeline":
                                    # Plan-and-Execute: single LLM planning call,
                                    # then local execution with error recovery
                                    from hydroclaw.pipeline import run_pipeline
                                    from hydroclaw.tools import discover_tools
                                    tools = discover_tools(workspace=ws_path)
                                    result = run_pipeline(
                                        task=text,
                                        llm=agent.llm,
                                        tools=tools,
                                        ui=ui,
                                    )
                                    summary = (
                                        f"Pipeline completed: {' -> '.join(result.steps_done)}\n"
                                        if result.success else
                                        f"Pipeline failed at {result.error_step}: {result.error}\n"
                                    )
                                    emit({"type": "answer", "text": summary})
                                    emit({"type": "session_id", "id": "pipeline"})
                                else:
                                    # ReAct or Waypoint (Waypoint = ReAct for now, P3)
                                    agent.run(text, prior_messages=prior)
                                    emit({"type": "session_id", "id": agent.memory.session_id})
                            except Exception as exc:
                                err = str(exc)
                                # Classify critical errors for targeted UI alerts
                                if "429" in err or "rate_limit" in err.lower() or "quota" in err.lower():
                                    emit({"type": "error", "msg": f"[429] API 限速或额度耗尽: {err}"})
                                elif any(k in err.lower() for k in ("timeout", "connection", "network", "500", "502", "503")):
                                    emit({"type": "error", "msg": f"[网络错误] {err}"})
                                else:
                                    emit({"type": "error", "msg": err})
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
        try:
            args_preview = json.dumps(_json_safe(args), ensure_ascii=False)[:300]
        except Exception:
            args_preview = str(args)[:300]
        logger.info("[tool] >>> %s | args: %s", name, args_preview)
        self._e(type="tool_start", name=name, args=args)

    def on_tool_end(self, name, result, elapsed=None):
        if elapsed is None:
            elapsed = time.time() - self._t0
        success = result.get("success", True) if isinstance(result, dict) else True
        logger.info("[tool] <<< %s | %.2fs | success=%s", name, elapsed, success)
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
