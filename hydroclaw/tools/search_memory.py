"""
Author: HydroClaw Team
Date: 2026-03-10
Description: Memory search tool - retrieves relevant conversation history,
             basin calibration records, and knowledge snippets on demand.
             Agent calls this tool reactively instead of loading all history upfront.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Maximum characters per result snippet
_SNIPPET_MAX_CHARS = 400


def search_memory(
    query: str,
    sources: list[str] | None = None,
    after: str | None = None,
    before: str | None = None,
    max_results: int = 5,
    _workspace: Path | None = None,
) -> dict:
    """Search conversation history, basin calibration records, and knowledge docs.

    Call this tool when you need to recall previous results or context, e.g.:
    - "What NSE did we get for basin X last time?"
    - "Which model worked best for semiarid basins?"
    - "What parameters did we use for gr4j before?"

    Args:
        query: Natural language search query
        sources: Sources to search. Any subset of ["sessions", "basin_profiles", "knowledge"].
                 Defaults to all three.
        after: Only return results after this date, format "YYYY-MM-DD"
        before: Only return results before this date, format "YYYY-MM-DD"
        max_results: Maximum number of results to return (default 5)

    Returns:
        {"results": [...], "total_found": int, "query": str}
        Each result: {"source": str, "title": str, "timestamp": str, "content": str, "score": float}
    """
    if _workspace is None:
        return {"error": "workspace not available", "results": [], "total_found": 0}

    sources = sources or ["sessions", "basin_profiles", "knowledge"]
    tokens = _tokenize(query)

    after_dt = _parse_date(after)
    before_dt = _parse_date(before)

    candidates = []

    if "sessions" in sources:
        candidates.extend(_search_sessions(_workspace, tokens, after_dt, before_dt))

    if "basin_profiles" in sources:
        candidates.extend(_search_basin_profiles(_workspace, tokens))
        candidates.extend(_search_basin_index(_workspace, tokens))

    if "knowledge" in sources:
        knowledge_dir = Path(__file__).parent.parent / "knowledge"
        candidates.extend(_search_knowledge(knowledge_dir, tokens))

    # Sort by score descending, return top-K
    candidates.sort(key=lambda x: x["score"], reverse=True)
    top = candidates[:max_results]

    logger.info(f"search_memory: query='{query}', found {len(candidates)} candidates, returning {len(top)}")

    return {
        "query": query,
        "results": top,
        "total_found": len(candidates),
    }


search_memory.__agent_hint__ = (
    "Call this when you need to recall previous calibration results, past conversations, "
    "or relevant knowledge snippets. Especially useful when user says '上次/之前/还记得'. "
    "sources=['sessions'] for conversation history, ['basin_profiles'] for calibration records, "
    "['knowledge'] for documentation. Returns ranked results with content snippets."
)


# ── Source searchers ──────────────────────────────────────────────────────────

def _search_sessions(
    workspace: Path,
    tokens: list[str],
    after_dt: datetime | None,
    before_dt: datetime | None,
) -> list[dict]:
    """Search session JSONL logs for relevant tool calls."""
    sessions_dir = workspace / "sessions"
    if not sessions_dir.exists():
        return []

    results = []
    for jsonl_file in sorted(sessions_dir.glob("*.jsonl"), reverse=True)[:20]:
        try:
            entries = []
            with open(jsonl_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entries.append(json.loads(line))
        except Exception:
            continue

        # Filter by date
        ts_str = jsonl_file.stem  # "20260310_172530"
        ts = _parse_session_ts(ts_str)
        if after_dt and ts and ts < after_dt:
            continue
        if before_dt and ts and ts > before_dt:
            continue

        # Score each entry, collect best
        for entry in entries:
            text = _entry_to_text(entry)
            score = _bm25_score(tokens, _tokenize(text))
            if score > 0:
                snippet = _make_snippet(text, tokens)
                results.append({
                    "source": "sessions",
                    "title": f"Session {ts_str} / {entry.get('tool', '?')}",
                    "timestamp": entry.get("timestamp", ts_str),
                    "content": snippet,
                    "score": score,
                })

    return results


def _search_basin_profiles(workspace: Path, tokens: list[str]) -> list[dict]:
    """Search basin profile JSON records."""
    profiles_dir = workspace / "basin_profiles"
    if not profiles_dir.exists():
        return []

    results = []
    for profile_file in profiles_dir.glob("*.json"):
        if profile_file.name == "basin_index.json":
            continue
        try:
            with open(profile_file, encoding="utf-8") as f:
                profile = json.load(f)
        except Exception:
            continue

        basin_id = profile.get("basin_id", profile_file.stem)
        climate_attrs = profile.get("climate_attrs", {})
        for rec in profile.get("records", []):
            text = _profile_record_to_text(basin_id, rec, climate_attrs)
            score = _bm25_score(tokens, _tokenize(text))
            if score > 0:
                results.append({
                    "source": "basin_profiles",
                    "title": f"Basin {basin_id} / {rec.get('model', '?').upper()} ({rec.get('algorithm', '?')})",
                    "timestamp": rec.get("calibrated_at", ""),
                    "content": text[:_SNIPPET_MAX_CHARS],
                    "score": score,
                })

    return results


def _search_basin_index(workspace: Path, tokens: list[str]) -> list[dict]:
    """Search basin_index.json for cross-basin semantic queries.

    Enables queries like "semiarid basins" or "basins with area > 1000".
    Each matching basin entry becomes one result with a summary of all models.
    """
    index_file = workspace / "basin_profiles" / "basin_index.json"
    if not index_file.exists():
        return []

    try:
        with open(index_file, encoding="utf-8") as f:
            index = json.load(f)
    except Exception:
        return []

    results = []
    for entry in index.get("basins", []):
        text = _index_entry_to_text(entry)
        score = _bm25_score(tokens, _tokenize(text))
        if score > 0:
            nse_str = ", ".join(
                f"{m}={v:.3f}" for m, v in entry.get("best_nse_by_model", {}).items()
            )
            summary = (
                f"Basin {entry['basin_id']} | "
                f"climate={entry.get('climate_type', '?')} | "
                f"area={entry.get('area_km2', '?')}km2 | "
                f"best NSE: {nse_str or 'N/A'} | "
                f"{entry.get('record_count', 0)} calibration(s)"
            )
            results.append({
                "source": "basin_index",
                "title": f"Basin index / {entry['basin_id']}",
                "timestamp": index.get("updated_at", ""),
                "content": summary[:_SNIPPET_MAX_CHARS],
                "score": score * 1.2,  # Slight boost: index entries are pre-summarized
            })
    return results


def _index_entry_to_text(entry: dict) -> str:
    """Serialize a basin index entry to searchable text."""
    parts = [
        f"basin={entry.get('basin_id', '')}",
        f"climate={entry.get('climate_type', '')}",
        f"land={entry.get('land_use', '')}",
    ]
    if entry.get("area_km2") is not None:
        area = entry["area_km2"]
        parts.append(f"area={area}")
        # Add human-readable size label for keyword matching
        if isinstance(area, (int, float)):
            if area < 500:
                parts.append("small_basin")
            elif area < 5000:
                parts.append("medium_basin")
            else:
                parts.append("large_basin")
    for model, nse in entry.get("best_nse_by_model", {}).items():
        parts.append(f"model={model} nse={nse:.3f}")
    return " ".join(parts)


def _search_knowledge(knowledge_dir: Path, tokens: list[str]) -> list[dict]:
    """Search knowledge .md files at section granularity."""
    if not knowledge_dir.exists():
        return []

    results = []
    for md_file in knowledge_dir.glob("*.md"):
        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        sections = _split_sections(text)
        for title, content in sections:
            score = _bm25_score(tokens, _tokenize(content))
            if score > 0:
                results.append({
                    "source": "knowledge",
                    "title": f"{md_file.stem} / {title}",
                    "timestamp": "",
                    "content": content[:_SNIPPET_MAX_CHARS],
                    "score": score,
                })

    return results


# ── Scoring & utilities ───────────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    """Tokenize text: lowercase, split on whitespace and punctuation."""
    text = text.lower()
    # Keep basin IDs (8 digits), NSE values, and word tokens
    tokens = re.findall(r'\d{8}|\d+\.\d+|\w+', text)
    return [t for t in tokens if len(t) >= 2]


def _bm25_score(query_tokens: list[str], doc_tokens: list[str]) -> float:
    """Simple BM25-inspired term overlap score."""
    if not query_tokens or not doc_tokens:
        return 0.0
    doc_set = set(doc_tokens)
    doc_len = len(doc_tokens)
    k1, b = 1.5, 0.75
    avg_dl = 50  # rough average doc length in tokens

    score = 0.0
    for t in set(query_tokens):
        tf = doc_tokens.count(t)
        if tf == 0:
            continue
        tf_norm = tf * (k1 + 1) / (tf + k1 * (1 - b + b * doc_len / avg_dl))
        score += tf_norm  # IDF omitted (small corpus)
    return round(score, 3)


def _make_snippet(text: str, tokens: list[str]) -> str:
    """Return a snippet of text centered around the first token match."""
    text_lower = text.lower()
    best_pos = len(text)
    for t in tokens:
        pos = text_lower.find(t)
        if 0 <= pos < best_pos:
            best_pos = pos

    start = max(0, best_pos - 80)
    end = min(len(text), best_pos + _SNIPPET_MAX_CHARS - 80)
    snippet = text[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet


def _split_sections(md_text: str) -> list[tuple[str, str]]:
    """Split markdown into (title, content) sections by ## headers."""
    sections = []
    current_title = "intro"
    current_lines = []
    for line in md_text.split("\n"):
        if line.startswith("## "):
            if current_lines:
                sections.append((current_title, "\n".join(current_lines).strip()))
            current_title = line.lstrip("#").strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((current_title, "\n".join(current_lines).strip()))
    return [(t, c) for t, c in sections if c]


def _entry_to_text(entry: dict) -> str:
    """Serialize a session log entry to searchable text."""
    parts = [f"tool={entry.get('tool', '')}"]
    args = entry.get("arguments", {})
    if isinstance(args, dict):
        for k, v in args.items():
            if isinstance(v, (str, int, float, list)):
                parts.append(f"{k}={v}")
    result = entry.get("result_summary", {})
    if isinstance(result, dict):
        for k in ("NSE", "KGE", "best_nse", "success", "error", "calibration_dir"):
            if k in result:
                parts.append(f"{k}={result[k]}")
    elif isinstance(result, str):
        parts.append(result[:200])
    return " | ".join(parts)


def _profile_record_to_text(
    basin_id: str, rec: dict, climate_attrs: dict | None = None
) -> str:
    """Serialize a basin profile record to searchable text."""
    nse = rec.get("train_nse")
    nse_str = f"{nse:.3f}" if isinstance(nse, float) else str(nse)
    params = rec.get("best_params", {})
    params_str = " ".join(
        f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}"
        for k, v in params.items()
    )
    parts = [
        f"basin={basin_id}",
        f"model={rec.get('model', '?')}",
        f"algorithm={rec.get('algorithm', '?')}",
        f"train_nse={nse_str}",
        f"kge={rec.get('train_kge', 'N/A')}",
        f"date={rec.get('calibrated_at', '')[:10]}",
    ]
    if params_str:
        parts.append(f"params: {params_str}")
    if climate_attrs:
        for k, v in climate_attrs.items():
            if v is not None:
                parts.append(f"{k}={v}")
    return " ".join(parts)


def _parse_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None


def _parse_session_ts(ts_str: str) -> datetime | None:
    try:
        return datetime.strptime(ts_str[:15], "%Y%m%d_%H%M%S")
    except ValueError:
        return None
