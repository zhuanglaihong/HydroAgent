"""
Experiment 2 - LLM Calibration vs Standard vs Zhu et al. (Hybrid Agent+Script)
================================================================================
Purpose: Validate HydroClaw's LLM parameter-range adjustment mechanism against
         standard SCE-UA and the Zhu et al. 2026 direct-proposal baseline.
Method:  Three-arm comparison:
  A. Standard SCE-UA (agent-driven)           <- baseline
  B. Zhu et al. 2026 (scripted)              <- external reference (must be scripted
                                                to faithfully reproduce the method)
  C. HydroClaw LLM range adjustment (agent-driven) <- our method

Note on Method B:  Zhu et al.'s "LLM as optimizer" approach requires precise
  control over LLM prompt format, narrow parameter ranges (+-3%), and iteration
  counting. This cannot be expressed as a free-form NL query without changing
  the method semantics. Method B is intentionally kept as a scripted reference.

Basins: Gallatin (semiarid/mountain) + Cowhouse (semiarid/flashy) + Fish River
        (control). Semi-arid basins are chosen for clear boundary effects.

Paper:   Section 4.3 - LLM Calibration Comparison
Reference: Zhu et al. 2026 (GRL), doi:10.1029/2025GL120043
           NHRI 2025, doi:10.14042/j.cnki.32.1309.2025.05.009
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import logging
import re
import time
import tempfile
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

logger = logging.getLogger(__name__)

# ── Experiment configuration ─────────────────────────────────────────────────

BASINS = [
    ("12025000", "Fish River, ME",      "humid_cold"),
    ("11532500", "Smith River, CA",     "mediterranean"),
    ("06043500", "Gallatin River, MT",  "semiarid_mountain"),
]
# Design rationale (revised):
# - GR4J (4 params): well-studied, established defaults, LLM has strong prior knowledge.
#   GR5J was dropped because extra param didn't add experimental value once framing
#   shifted from "who gets higher NSE" to "autonomous workflow demonstration".
# - NSE_TARGET=0.80: above GR4J baseline for Fish (~0.789), forces Method C to run
#   multiple LLM-guided rounds rather than stopping at round 1. Key: we want to see
#   C autonomously detect "not there yet" and keep adjusting — not a trivial early stop.
# - Gallatin (semiarid_mountain): GR4J NSE≈-0.12, structurally poor fit.
#   Shows agent correctly escalates to llm_calibrate and persists, even when
#   the model-basin mismatch limits achievable NSE regardless of calibration method.
# - Core comparison metric: tool_sequence correctness and automation (0 human loops),
#   NOT NSE superiority. C≈A in NSE is the EXPECTED and ACCEPTABLE outcome,
#   consistent with Zhu et al. 2026 (DeepSeek-R1 NSE == SCE-UA NSE, 32% fewer evals).

MODEL = "gr4j"
ZHU_MAX_ITERS = 15
LLM_MAX_ROUNDS = 5
NSE_TARGET = 0.80
# SCE-UA budget constants — used to compute total evaluations for efficiency comparison
SCE_UA_REP_DEFAULT = 750   # A method: single run rep
SCE_UA_NGS_DEFAULT = 200   # A method: ngs
OUTPUT_DIR = Path("results/paper/exp2")


def setup_logging():
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(logs_dir / f"exp2_{ts}.log", encoding="utf-8"),
        ],
    )


# ── Log extraction helpers (shared with Exp1 pattern) ────────────────────────

def _extract_from_log(memory_log: list[dict]) -> dict:
    """Extract calibration_dir, best_params, tool_sequence from agent memory log.

    Handles two cases:
    - llm_calibrate succeeded: extract best_nse, rounds, nse_history directly
    - llm_calibrate failed (timeout/error): agent may have fallen back to calibrate_model;
      extract calibration_dir from the best successful calibrate_model call instead,
      and record llm_calibrate_failed=True
    """
    result = {
        "calibration_dir": "",
        "best_params": {},
        "tool_sequence": [],
        "llm_calibrate_best_nse": None,
        "nse_history": [],
        "rounds": None,
        "llm_calibrate_failed": False,
    }
    # Track all successful calibrate_model dirs to fall back to first if needed
    calibrate_model_dirs = []

    for entry in memory_log:
        tool = entry.get("tool", "")
        result["tool_sequence"].append(tool)
        r = entry.get("result_summary", {})
        if not isinstance(r, dict):
            continue

        if tool == "llm_calibrate":
            if r.get("success"):
                # llm_calibrate succeeded: take its data and clear any earlier failure flag
                cal_dir = r.get("calibration_dir", "")
                if cal_dir:
                    result["calibration_dir"] = str(cal_dir)
                result["best_params"] = r.get("best_params", {})
                result["llm_calibrate_best_nse"] = r.get("best_nse")
                result["rounds"] = r.get("rounds")
                result["nse_history"] = r.get("nse_history", [])
                result["llm_calibrate_failed"] = False  # reset: earlier failure was retried
            elif r.get("error"):
                # llm_calibrate failed (wrong args, timeout, etc.)
                result["llm_calibrate_failed"] = True
                logger.warning(f"llm_calibrate failed in log: {r.get('error', '')[:100]}")

        elif tool == "calibrate_model" and r.get("success"):
            cal_dir = r.get("calibration_dir", "")
            if cal_dir:
                calibrate_model_dirs.append(str(cal_dir))
            result["best_params"] = r.get("best_params", {})

    # If calibration_dir still empty (no llm_calibrate, or all llm_calibrate failed),
    # fall back to the last successful calibrate_model dir
    if not result["calibration_dir"] and calibrate_model_dirs:
        result["calibration_dir"] = calibrate_model_dirs[-1]
        logger.info(f"Using calibrate_model fallback calibration_dir: {calibrate_model_dirs[-1]}")

    return result


def _evaluate_from_disk(cal_dir: str, cfg: dict) -> tuple[dict, dict]:
    """Read calibration config and evaluate train + test periods from disk."""
    from hydroclaw.skills.evaluation.evaluate import evaluate_model
    try:
        import yaml
        config_file = Path(cal_dir) / "calibration_config.yaml"
        if not config_file.exists():
            logger.warning(f"calibration_config.yaml not found in {cal_dir}")
            return {}, {}
        with open(config_file, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        train_period = config["data_cfgs"]["train_period"]
        train_evl = evaluate_model(
            calibration_dir=cal_dir, eval_period=train_period, _cfg=cfg
        )
        test_evl = evaluate_model(
            calibration_dir=cal_dir, eval_period=None, _cfg=cfg
        )
        train_m = train_evl.get("metrics", {}) if train_evl.get("success") else {}
        test_m = test_evl.get("metrics", {}) if test_evl.get("success") else {}
        return train_m, test_m
    except Exception as e:
        logger.warning(f"Post-run evaluation failed for {cal_dir}: {e}")
        return {}, {}


# ── Method B: Zhu et al. 2026 (scripted) ─────────────────────────────────────

def _zhu_method(basin_id: str, model_name: str, llm, cfg: dict, output_dir: str) -> dict:
    """Reproduce Zhu et al. 2026: LLM directly proposes parameter values, iteratively.

    This is kept as a scripted method (not agent-driven) because:
    1. The method requires tight control over LLM prompt format and temperature
    2. The narrow range trick (+-3% span) must be applied programmatically
    3. Expressing this as a natural language query would change method semantics

    Implementation:
    1. LLM proposes specific parameter values from physical knowledge + history
    2. Values are converted to a +-3% range, passed to scipy calibration
    3. Best NSE across ZHU_MAX_ITERS iterations is recorded
    """
    from hydroclaw.skills.calibration.calibrate import calibrate_model
    from hydroclaw.skills.evaluation.evaluate import evaluate_model
    from hydroclaw.skills.llm_calibration.llm_calibrate import DEFAULT_PARAM_RANGES
    import yaml

    param_ranges = DEFAULT_PARAM_RANGES.get(model_name, {})
    history = []
    best_nse = -999.0
    best_result = {}

    for iteration in range(ZHU_MAX_ITERS):
        # LLM proposes parameter values
        history_text = "\n".join(
            f"  Iter {h['iter']}: proposed={h['proposed']}  NSE={h['nse']:.4f}"
            for h in history[-5:]
        ) if history else "(no previous iterations)"

        prompt = (
            f"You are calibrating a {model_name.upper()} hydrological model for basin {basin_id}.\n"
            f"Parameter physical ranges: {json.dumps(param_ranges)}\n\n"
            f"Previous iterations:\n{history_text}\n\n"
            f"Based on the history and hydrological knowledge, propose specific parameter VALUES "
            f"to maximize Nash-Sutcliffe Efficiency (NSE). "
            f"Reply ONLY with a JSON object like: "
            f'{{"{list(param_ranges.keys())[0]}": 250.0, ...}}'
        )
        messages = [
            {"role": "system", "content": "Expert hydrologist. Reply with valid JSON only."},
            {"role": "user", "content": prompt},
        ]

        try:
            response = llm._chat_text(messages, temperature=0.2)
            text = response.text or ""
            match = re.search(r"\{[^{}]+\}", text, re.DOTALL)
            if not match:
                logger.warning(f"Zhu iter {iteration}: no JSON found in LLM response: {text[:200]}")
                continue
            proposed = json.loads(match.group())
        except Exception as e:
            logger.warning(f"Zhu iter {iteration}: LLM parse error: {e}")
            continue

        # Log LLM's actual proposal to verify it's proposing diverse values
        logger.info(f"  Zhu iter {iteration}: LLM proposed: {proposed}")

        # Convert proposed values to narrow +-3% range
        tight_ranges = {}
        param_names = []
        for k, v in proposed.items():
            if k not in param_ranges:
                continue
            lo, hi = param_ranges[k]
            margin = (hi - lo) * 0.03
            r_lo = max(lo, float(v) - margin)
            r_hi = min(hi, float(v) + margin)
            if r_lo >= r_hi:
                r_lo, r_hi = lo, hi
            tight_ranges[k] = [r_lo, r_hi]
            param_names.append(k)

        if not tight_ranges:
            continue

        range_yaml = {
            model_name: {
                "param_name": param_names,
                "param_range": tight_ranges,
            }
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as tf:
            yaml.dump(range_yaml, tf, allow_unicode=True)
            range_file = tf.name

        # Use scipy method from config (default: SLSQP), keep iterations low (point evaluation)
        scipy_method = cfg.get("algorithms", {}).get("scipy", {}).get("method", "SLSQP")
        iter_dir = str(Path(output_dir) / f"iter_{iteration:02d}")
        result = calibrate_model(
            basin_ids=[basin_id],
            model_name=model_name,
            algorithm="scipy",
            param_range_file=range_file,
            output_dir=iter_dir,
            algorithm_params={"method": scipy_method, "max_iterations": 30},
            _cfg=cfg,
        )

        # calibrate_model does not return NSE - must call evaluate_model explicitly
        nse = -999.0
        if result.get("success") and result.get("calibration_dir"):
            evl = evaluate_model(
                calibration_dir=result["calibration_dir"],
                eval_period=result.get("train_period"),
                _cfg=cfg,
            )
            if evl.get("success"):
                v = evl.get("metrics", {}).get("NSE", -999.0)
                nse = v if isinstance(v, float) else -999.0

        history.append({
            "iter": iteration,
            "proposed": proposed,           # LLM's original proposal (for history context)
            "params": result.get("best_params", proposed),  # scipy result within narrow range
            "nse": nse,
        })

        if nse > best_nse:
            best_nse = nse
            best_result = result

        logger.info(f"  Zhu iter {iteration}: train NSE={nse:.4f}")

        if isinstance(nse, float) and nse >= NSE_TARGET:
            logger.info(f"  Zhu: target NSE reached at iter {iteration}")
            break

    return {
        "success": bool(best_result.get("success")),
        "best_nse": best_nse if best_nse > -998.0 else None,
        "best_params": best_result.get("best_params", {}),
        "calibration_dir": best_result.get("calibration_dir", ""),
        "train_period": best_result.get("train_period"),
        "test_period": best_result.get("test_period"),
        "iterations": len(history),
        "nse_history": [h["nse"] for h in history],
        "proposed_history": [h["proposed"] for h in history],  # for diversity analysis
        "method": "zhu_direct_propose",
        "scipy_method": scipy_method,  # record which scipy method was used
    }


# ── Method A and C: Agent-driven runners ─────────────────────────────────────

def _run_method_a(basin_id: str, cfg: dict) -> dict:
    """Method A: Standard SCE-UA via HydroClaw agent.

    Agent autonomously performs: validate_basin -> calibrate_model -> evaluate_model.
    """
    from hydroclaw.agent import HydroClaw
    from hydroclaw.interface.ui import ConsoleUI

    task_workspace = OUTPUT_DIR / f"A_{MODEL}_{basin_id}"
    task_workspace.mkdir(parents=True, exist_ok=True)

    query = (
        f"请率定GR4J模型，流域{basin_id}，使用SCE-UA算法，"
        f"输出目录保存在 {task_workspace}。"
        f"完成后评估训练期和测试期NSE指标。"
    )

    agent = HydroClaw(workspace=task_workspace, ui=ConsoleUI(mode="dev"))
    t0 = time.time()
    try:
        agent.run(query)
    except Exception as e:
        logger.error(f"Method A agent error for {basin_id}: {e}", exc_info=True)
        return {"success": False, "error": str(e), "calibration_time_s": round(time.time() - t0, 2)}

    cal_time = round(time.time() - t0, 2)
    log_info = _extract_from_log(agent.memory._log)

    entry = {
        "success": False,
        "best_params": log_info["best_params"],
        "tool_sequence": log_info["tool_sequence"],
        "calibration_time_s": cal_time,
        "train_metrics": {},
        "test_metrics": {},
        "boundary_hits": [],
    }

    cal_dir = log_info.get("calibration_dir", "")
    if cal_dir and Path(cal_dir).exists():
        train_m, test_m = _evaluate_from_disk(cal_dir, cfg)
        entry["train_metrics"] = train_m
        entry["test_metrics"] = test_m
        entry["success"] = bool(train_m.get("NSE") is not None)

    # Detect parameter boundary hits
    if entry["best_params"]:
        from hydroclaw.skills.llm_calibration.llm_calibrate import DEFAULT_PARAM_RANGES
        entry["boundary_hits"] = _detect_boundaries(
            entry["best_params"], MODEL, DEFAULT_PARAM_RANGES
        )

    return entry


def _run_method_c(basin_id: str, cfg: dict, llm) -> dict:
    """Method C: HydroClaw LLM range adjustment via agent.

    Agent uses llm_calibrate tool with iterative range adjustment.
    Query is phrased to trigger the llm_calibration skill.
    """
    from hydroclaw.agent import HydroClaw
    from hydroclaw.interface.ui import ConsoleUI

    task_workspace = OUTPUT_DIR / f"C_{MODEL}_{basin_id}"
    task_workspace.mkdir(parents=True, exist_ok=True)

    query = (
        f"请用LLM智能率定GR4J模型，流域{basin_id}，目标NSE>={NSE_TARGET}，"
        f"最多{LLM_MAX_ROUNDS}轮参数范围调整，使用SCE-UA算法，"
        f"输出目录保存在 {task_workspace}。"
        f"完成后评估训练期和测试期NSE。"
    )

    agent = HydroClaw(workspace=task_workspace, ui=ConsoleUI(mode="dev"))
    t0 = time.time()
    try:
        agent.run(query)
    except Exception as e:
        logger.error(f"Method C agent error for {basin_id}: {e}", exc_info=True)
        return {"success": False, "error": str(e), "calibration_time_s": round(time.time() - t0, 2)}

    cal_time = round(time.time() - t0, 2)
    log_info = _extract_from_log(agent.memory._log)

    entry = {
        "success": False,
        "best_nse": log_info.get("llm_calibrate_best_nse"),
        "best_params": log_info["best_params"],
        "rounds": log_info.get("rounds"),   # None if llm_calibrate failed
        "tool_sequence": log_info["tool_sequence"],
        "calibration_time_s": cal_time,
        "test_metrics": {},
        "nse_history": log_info.get("nse_history", []),  # from result_summary directly
        "llm_calibrate_failed": log_info.get("llm_calibrate_failed", False),
    }

    # Record if agent didn't call llm_calibrate at all, or if it failed
    if "llm_calibrate" not in log_info["tool_sequence"]:
        entry["error"] = "Agent did not call llm_calibrate (wrong skill selected)"
        logger.warning(f"Method C: agent did not call llm_calibrate for {basin_id}")
    elif log_info.get("llm_calibrate_failed"):
        entry["error"] = "llm_calibrate timed out; agent fell back to direct calibrate_model"
        logger.warning(f"Method C: llm_calibrate failed for {basin_id}, using fallback calibration_dir")

    cal_dir = log_info.get("calibration_dir", "")
    if cal_dir and Path(cal_dir).exists():
        _, test_m = _evaluate_from_disk(cal_dir, cfg)
        entry["test_metrics"] = test_m
        entry["success"] = bool(
            entry.get("best_nse") is not None or test_m.get("NSE") is not None
        )

    return entry


# ── Boundary detection ────────────────────────────────────────────────────────

def _detect_boundaries(best_params: dict, model_name: str, default_ranges: dict) -> list:
    ranges = default_ranges.get(model_name, {})
    hits = []
    for name, value in best_params.items():
        if name not in ranges:
            continue
        lo, hi = ranges[name]
        span = hi - lo
        if span <= 0:
            continue
        lo_pct = (value - lo) / span * 100
        hi_pct = (hi - value) / span * 100
        if lo_pct < 5:
            hits.append({"param": name, "boundary": "lower", "pct": round(lo_pct, 1)})
        elif hi_pct < 5:
            hits.append({"param": name, "boundary": "upper", "pct": round(hi_pct, 1)})
    return hits


# ── Main experiment ───────────────────────────────────────────────────────────

def run_experiment() -> dict:
    from hydroclaw.config import load_config
    from hydroclaw.llm import LLMClient

    cfg = load_config()
    llm = LLMClient(cfg["llm"])
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    logger.info(
        f"LLM config: model={cfg['llm']['model']}, "
        f"base_url={cfg['llm']['base_url']}, "
        f"timeout={cfg['llm']['timeout']}s, "
        f"max_retries={cfg['llm']['max_retries']}"
    )

    results = []

    for basin_id, basin_name, climate_zone in BASINS:
        logger.info(f"\n{'='*60}")
        logger.info(f"Basin: {basin_id} ({basin_name})")
        logger.info(f"{'='*60}")

        record = {
            "basin_id": basin_id,
            "basin_name": basin_name,
            "climate_zone": climate_zone,
            "model": MODEL,
            "method_A": {},
            "method_B": {},
            "method_C": {},
        }

        # Method A: Standard SCE-UA (agent-driven)
        logger.info("[A] Standard SCE-UA (agent-driven)")
        a_entry = _run_method_a(basin_id, cfg)
        record["method_A"] = a_entry
        logger.info(
            f"  A: train NSE={a_entry.get('train_metrics', {}).get('NSE', 'N/A')}, "
            f"test NSE={a_entry.get('test_metrics', {}).get('NSE', 'N/A')}, "
            f"boundary_hits={len(a_entry.get('boundary_hits', []))}, "
            f"tools={a_entry.get('tool_sequence', [])}"
        )

        # Method B: Zhu et al. (scripted - reproduces specific external method)
        logger.info("[B] Zhu et al. 2026 direct parameter proposal (scripted)")
        b_dir = str(OUTPUT_DIR / f"B_{MODEL}_{basin_id}")
        t0 = time.time()
        b_entry = _zhu_method(basin_id, MODEL, llm, cfg, b_dir)
        b_entry["calibration_time_s"] = round(time.time() - t0, 2)

        # Evaluate train+test for Method B's best iteration
        b_cal_dir = b_entry.get("calibration_dir", "")
        if b_entry.get("success") and b_cal_dir and Path(b_cal_dir).exists():
            b_tr, b_te = _evaluate_from_disk(b_cal_dir, cfg)
            b_entry["train_metrics"] = b_tr
            b_entry["test_metrics"] = b_te
            b_entry["best_nse"] = b_tr.get("NSE", b_entry.get("best_nse"))

        record["method_B"] = b_entry
        logger.info(
            f"  B: train NSE={b_entry.get('best_nse', 'N/A')}, "
            f"test NSE={b_entry.get('test_metrics', {}).get('NSE', 'N/A')}, "
            f"iters={b_entry.get('iterations', 0)}"
        )

        # Method C: HydroClaw LLM range adjustment (agent-driven)
        logger.info("[C] HydroClaw LLM range adjustment (agent-driven)")
        c_entry = _run_method_c(basin_id, cfg, llm)
        record["method_C"] = c_entry
        logger.info(
            f"  C: train NSE={c_entry.get('best_nse', 'N/A')}, "
            f"test NSE={c_entry.get('test_metrics', {}).get('NSE', 'N/A')}, "
            f"rounds={c_entry.get('rounds', 0)}, "
            f"tools={c_entry.get('tool_sequence', [])}"
        )

        # Delta comparisons
        nse_a = a_entry.get("train_metrics", {}).get("NSE")
        nse_b = b_entry.get("best_nse")
        nse_c = c_entry.get("best_nse")
        record["delta_B_vs_A"] = (
            round(nse_b - nse_a, 4)
            if isinstance(nse_b, float) and isinstance(nse_a, float) else None
        )
        record["delta_C_vs_A"] = (
            round(nse_c - nse_a, 4)
            if isinstance(nse_c, float) and isinstance(nse_a, float) else None
        )
        record["delta_C_vs_B"] = (
            round(nse_c - nse_b, 4)
            if isinstance(nse_c, float) and isinstance(nse_b, float) else None
        )

        results.append(record)

    return {
        "experiment": "exp2_llm_calibration",
        "mode": "hybrid (A+C agent-driven, B scripted)",
        "timestamp": datetime.now().isoformat(),
        "model": MODEL,
        "algorithm_A": "SCE_UA (agent-driven)",
        "algorithm_B": f"Zhu_direct_propose (scripted, max {ZHU_MAX_ITERS} iters)",
        "algorithm_C": f"HydroClaw_range_adjustment (agent-driven, max {LLM_MAX_ROUNDS} rounds)",
        "nse_target": NSE_TARGET,
        "results": results,
        "llm_token_usage": llm.tokens.summary(),
    }


def save_results(results: dict):
    f = OUTPUT_DIR / "exp2_results.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    f.write_text(
        json.dumps(results, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    logger.info(f"Saved -> {f}")


def _estimate_c_total_evals(rounds: int) -> int:
    """Estimate total SCE-UA function evaluations for C method across all rounds.

    Adaptive budget schedule: round 1=100%, 2=75%, 3=60%, 4+=50% of rep_default.
    """
    scales = [1.0, 0.75, 0.60, 0.50]
    total = 0
    for i in range(rounds or 0):
        scale = scales[min(i, len(scales) - 1)]
        total += int(SCE_UA_REP_DEFAULT * scale)
    return total


def print_summary(results: dict):
    data = results["results"]
    print(f"\n{'='*100}")
    print(f"  Exp2: Autonomous LLM Calibration  ({results['mode']})")
    print(f"{'='*100}")
    print(f"  A = Standard SCE-UA (agent, 1 run)  |  B = Zhu et al. 2026 (scripted)")
    print(f"  C = HydroClaw LLM-guided (agent, multi-round, autonomous)")
    print(f"  Key metric: C achieves equivalent NSE to A with ZERO human intervention")
    print(f"  (NSE superiority is NOT the goal — automation equivalence is)")
    print()

    print("  [NSE Results - A/B/C should be comparable]")
    header = (
        f"{'Basin':<12} {'Zone':<20} "
        f"{'A(tr)':>7} {'B(tr)':>7} {'C(tr)':>7} "
        f"{'dC-A':>7} {'C_rn':>5} {'A_eval':>7} {'C_eval':>7} {'eval_ratio':>10}"
    )
    print(header)
    print("-" * 100)

    for r in data:
        a_nse = r["method_A"].get("train_metrics", {}).get("NSE")
        b_nse = r["method_B"].get("best_nse")
        c_nse = r["method_C"].get("best_nse")
        fmt = lambda v: f"{v:.4f}" if isinstance(v, float) else "N/A"
        dfmt = lambda v: f"{v:+.4f}" if isinstance(v, float) else "N/A"
        c_rounds = r["method_C"].get("rounds") or 0
        a_eval = SCE_UA_REP_DEFAULT
        c_eval = _estimate_c_total_evals(c_rounds)
        ratio_str = f"{c_eval/a_eval:.1f}x" if a_eval > 0 else "N/A"
        print(
            f"{r['basin_id']:<12} {r['climate_zone']:<20} "
            f"{fmt(a_nse):>7} {fmt(b_nse):>7} {fmt(c_nse):>7} "
            f"{dfmt(r.get('delta_C_vs_A')):>7} "
            f"{c_rounds:>5} {a_eval:>7} {c_eval:>7} {ratio_str:>10}"
        )

    print()
    print("  [Test NSE - generalization]")
    hdr2 = f"{'Basin':<12} {'Zone':<20} {'A(test)':>8} {'B(test)':>8} {'C(test)':>8}"
    print(hdr2)
    print("-" * 60)
    for r in data:
        a_test = r["method_A"].get("test_metrics", {}).get("NSE")
        b_test = r["method_B"].get("test_metrics", {}).get("NSE")
        c_test = r["method_C"].get("test_metrics", {}).get("NSE")
        fmt = lambda v: f"{v:.4f}" if isinstance(v, float) else "N/A"
        print(
            f"{r['basin_id']:<12} {r['climate_zone']:<20} "
            f"{fmt(a_test):>8} {fmt(b_test):>8} {fmt(c_test):>8}"
        )

    print(f"\n  NSE trajectory (Method C - each round uses different random seed):")
    for r in data:
        hist = r["method_C"].get("nse_history", [])
        traj = " -> ".join(f"{v:.3f}" for v in hist if isinstance(v, float))
        seeds = " | ".join(
            f"r{i+1}:seed={1234+i*137}" for i in range(len(hist))
        )
        print(f"    {r['basin_id']}: {traj or 'no data'}")
        if hist:
            print(f"      ({seeds})")

    print(f"\n  [Automation story: tool sequences]")
    print(f"  A (standard): user must know algorithm params, check results, decide to retry")
    print(f"  C (autonomous): agent handles multi-round decision loop, zero human intervention")
    for r in data:
        a_tools = "->".join(r["method_A"].get("tool_sequence", []))
        c_tools = "->".join(r["method_C"].get("tool_sequence", []))
        print(f"    {r['basin_id']} A: {a_tools}")
        print(f"    {r['basin_id']} C: {c_tools}")

    tokens = results.get("llm_token_usage", {})
    print(f"\n  LLM: {tokens.get('calls', 0)} calls, {tokens.get('total_tokens', 0)} tokens")
    print(f"  Note: C uses more total SCE-UA evaluations than A due to multi-round design.")
    print(f"        Trade-off: computational cost for full autonomy (no human calibration loops).")


def main():
    setup_logging()
    logger.info("Starting Exp2: LLM Calibration Comparison (Hybrid Agent+Script)")
    results = run_experiment()
    save_results(results)
    print_summary(results)
    logger.info("Exp2 complete")


if __name__ == "__main__":
    main()
