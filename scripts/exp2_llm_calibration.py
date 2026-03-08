"""
Experiment 2 - LLM 参数范围调整 vs 标准率定 vs Zhu et al. 直接提议法
=====================================================================
目的：验证 HydroClaw LLM 参数范围调整机制的有效性，并与文献方法直接对比。
方法：三路对比实验
  A. Standard SCE-UA（固定默认范围）           ← 基线
  B. Zhu et al. 2026 风格（LLM 直接提议参数值，迭代评估）
  C. HydroClaw LLM 范围调整（参数范围迭代扩展 + SCE-UA）  ← 本文方法

选流域：Gallatin + Guadalupe（半干旱/山区，参数容易碰边界）+ Fish River（对照）

论文对应：Section 4.3
参考文献：Zhu et al. 2026 (GRL), doi:10.1029/2025GL120043
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

# ── 实验配置 ──────────────────────────────────────────────────────────────

BASINS = [
    ("06043500", "Gallatin River, MT",  "semiarid_mountain"),  # 困难：高山积雪
    ("08101000", "Cowhouse Creek, TX",  "semiarid_flashy"),    # 困难：半干旱闪洪
    ("12025000", "Fish River, ME",      "humid_cold"),         # 对照：易率定流域
]

MODEL = "gr4j"            # GR4J：4参数，边界效应最直观
ZHU_MAX_ITERS = 15        # Zhu et al. 风格：LLM 最多提议 15 次
LLM_MAX_ROUNDS = 5        # HydroClaw：最多 5 轮范围调整
NSE_TARGET = 0.75
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


# ── Method B: Zhu et al. 风格实现 ─────────────────────────────────────────

def _zhu_method(basin_id: str, model_name: str, llm, cfg: dict, output_dir: str) -> dict:
    """Simulate Zhu et al. 2026: LLM 直接提议参数值，迭代评估。

    实现逻辑：
    1. LLM 根据模型物理含义和历史结果提议参数值
    2. 将提议值转换为极窄参数范围（±3% range span），用 scipy 单步评估
    3. 迭代最多 ZHU_MAX_ITERS 次，保留最优 NSE
    4. 返回与 Method A/C 相同结构的结果 dict

    注：这是对 Zhu et al. 方法的精神性复现，体现"LLM 作为优化器"的核心思路。
    """
    from hydroclaw.skills.calibration.calibrate import calibrate_model
    from hydroclaw.skills.llm_calibration.llm_calibrate import DEFAULT_PARAM_RANGES
    import yaml

    param_ranges = DEFAULT_PARAM_RANGES.get(model_name, {})
    history = []
    best_nse = -999.0
    best_result = {}

    for iteration in range(ZHU_MAX_ITERS):
        # ── LLM 提议参数值 ───────────────────────────────────────────────
        history_text = "\n".join(
            f"  Iter {h['iter']}: params={h['params']}  NSE={h['nse']:.4f}"
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
                continue
            proposed = json.loads(match.group())
        except Exception as e:
            logger.warning(f"Zhu iter {iteration}: LLM parse error: {e}")
            continue

        # ── 将提议值转换为极窄范围，用 scipy 评估 ────────────────────────
        tight_ranges = {}
        for k, v in proposed.items():
            if k not in param_ranges:
                continue
            lo, hi = param_ranges[k]
            margin = (hi - lo) * 0.03   # ±3% range span
            tight_ranges[k] = [max(lo, float(v) - margin), min(hi, float(v) + margin)]
            if tight_ranges[k][0] >= tight_ranges[k][1]:
                tight_ranges[k] = [lo, hi]  # fallback to full range

        if not tight_ranges:
            continue

        # 写临时 YAML 参数范围文件
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as tf:
            yaml.dump({model_name: tight_ranges}, tf)
            range_file = tf.name

        iter_dir = str(Path(output_dir) / f"iter_{iteration:02d}")
        result = calibrate_model(
            basin_ids=[basin_id],
            model_name=model_name,
            algorithm="scipy",
            param_range_file=range_file,
            output_dir=iter_dir,
            algorithm_params={"method": "L-BFGS-B", "options": {"maxiter": 30}},
            _cfg=cfg,
        )

        nse = result.get("metrics", {}).get("NSE", -999)
        history.append({
            "iter": iteration,
            "params": result.get("best_params", proposed),
            "nse": nse if isinstance(nse, float) else -999,
        })

        if isinstance(nse, float) and nse > best_nse:
            best_nse = nse
            best_result = result

        logger.info(f"  Zhu iter {iteration}: NSE={nse:.4f}" if isinstance(nse, float) else
                    f"  Zhu iter {iteration}: failed")

        if isinstance(nse, float) and nse >= NSE_TARGET:
            logger.info(f"  Zhu: target NSE reached at iter {iteration}")
            break

    return {
        "success": bool(best_result.get("success")),
        "best_nse": best_nse if best_nse > -999 else None,
        "best_params": best_result.get("best_params", {}),
        "train_metrics": best_result.get("train_metrics", {}),
        "iterations": len(history),
        "nse_history": [h["nse"] for h in history],
        "method": "zhu_direct_propose",
    }


# ── Main experiment ───────────────────────────────────────────────────────

def run_experiment() -> dict:
    from hydroclaw.config import load_config
    from hydroclaw.llm import LLMClient
    from hydroclaw.skills.calibration.calibrate import calibrate_model
    from hydroclaw.skills.evaluation.evaluate import evaluate_model
    from hydroclaw.skills.llm_calibration.llm_calibrate import llm_calibrate, DEFAULT_PARAM_RANGES
    from hydroclaw.tools.validate import validate_basin

    cfg = load_config()
    llm = LLMClient(cfg["llm"])
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
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
            "method_A": {},   # Standard SCE-UA
            "method_B": {},   # Zhu et al.
            "method_C": {},   # HydroClaw
        }

        # 验证流域
        val = validate_basin(basin_ids=[basin_id], _cfg=cfg)
        if not val.get("valid"):
            logger.warning(f"  Validation failed for {basin_id}")
            results.append(record)
            continue

        # ── Method A: 标准 SCE-UA ────────────────────────────────────────
        logger.info("[A] Standard SCE-UA")
        a_dir = str(OUTPUT_DIR / f"A_{MODEL}_{basin_id}")
        t0 = time.time()
        a_cal = calibrate_model(
            basin_ids=[basin_id], model_name=MODEL,
            algorithm="SCE_UA", output_dir=a_dir, _cfg=cfg,
        )
        a_time = round(time.time() - t0, 2)
        a_entry = {
            "success": a_cal.get("success", False),
            "train_metrics": a_cal.get("train_metrics", {}),
            "best_params": a_cal.get("best_params", {}),
            "calibration_time_s": a_time,
        }
        if a_cal.get("success"):
            a_evl = evaluate_model(calibration_dir=a_cal.get("calibration_dir", a_dir), _cfg=cfg)
            if a_evl.get("success"):
                a_entry["test_metrics"] = a_evl.get("metrics", {})
            # 检测参数边界命中
            a_entry["boundary_hits"] = _detect_boundaries(
                a_entry["best_params"], MODEL, DEFAULT_PARAM_RANGES
            )
        record["method_A"] = a_entry
        logger.info(f"  A: train NSE={a_entry['train_metrics'].get('NSE', 'N/A')}, "
                    f"boundary_hits={len(a_entry.get('boundary_hits', []))}")

        # ── Method B: Zhu et al. 直接提议法 ─────────────────────────────
        logger.info("[B] Zhu et al. direct parameter proposal")
        b_dir = str(OUTPUT_DIR / f"B_{MODEL}_{basin_id}")
        t0 = time.time()
        b_entry = _zhu_method(basin_id, MODEL, llm, cfg, b_dir)
        b_entry["calibration_time_s"] = round(time.time() - t0, 2)
        record["method_B"] = b_entry
        logger.info(f"  B: best NSE={b_entry.get('best_nse', 'N/A')}, "
                    f"iters={b_entry.get('iterations', 0)}")

        # ── Method C: HydroClaw LLM 范围调整 ─────────────────────────────
        logger.info("[C] HydroClaw LLM range adjustment")
        c_dir = OUTPUT_DIR / f"C_{MODEL}_{basin_id}"
        c_dir.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        c_cal = llm_calibrate(
            basin_ids=[basin_id], model_name=MODEL,
            max_rounds=LLM_MAX_ROUNDS, nse_target=NSE_TARGET,
            algorithm="SCE_UA",
            _workspace=c_dir, _cfg=cfg, _llm=llm,
        )
        c_time = round(time.time() - t0, 2)
        c_entry = {
            "success": c_cal.get("success", False),
            "best_nse": c_cal.get("best_nse"),
            "best_params": c_cal.get("best_params", {}),
            "rounds": c_cal.get("rounds", 0),
            "nse_history": [h.get("nse") for h in c_cal.get("history", [])],
            "range_adjustments": len(c_cal.get("history", [])) - 1,
            "calibration_time_s": c_time,
        }
        if c_cal.get("success") and c_cal.get("calibration_dir"):
            c_evl = evaluate_model(calibration_dir=c_cal["calibration_dir"], _cfg=cfg)
            if c_evl.get("success"):
                c_entry["test_metrics"] = c_evl.get("metrics", {})
        record["method_C"] = c_entry
        logger.info(f"  C: best NSE={c_entry.get('best_nse', 'N/A')}, "
                    f"rounds={c_entry.get('rounds', 0)}")

        # ── NSE 提升对比 ─────────────────────────────────────────────────
        nse_a = a_entry["train_metrics"].get("NSE")
        nse_b = b_entry.get("best_nse")
        nse_c = c_entry.get("best_nse")
        record["delta_B_vs_A"] = round(nse_b - nse_a, 4) if isinstance(nse_b, float) and isinstance(nse_a, float) else None
        record["delta_C_vs_A"] = round(nse_c - nse_a, 4) if isinstance(nse_c, float) and isinstance(nse_a, float) else None
        record["delta_C_vs_B"] = round(nse_c - nse_b, 4) if isinstance(nse_c, float) and isinstance(nse_b, float) else None

        results.append(record)

    return {
        "experiment": "exp2_llm_calibration",
        "timestamp": datetime.now().isoformat(),
        "model": MODEL,
        "algorithm_A": "SCE_UA",
        "algorithm_B": f"Zhu_direct_propose (max {ZHU_MAX_ITERS} iters)",
        "algorithm_C": f"HydroClaw_range_adjustment (max {LLM_MAX_ROUNDS} rounds)",
        "nse_target": NSE_TARGET,
        "results": results,
        "llm_token_usage": llm.tokens.summary(),
    }


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


def save_results(results: dict):
    f = OUTPUT_DIR / "exp2_results.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    logger.info(f"Saved -> {f}")


def print_summary(results: dict):
    data = results["results"]
    print(f"\n{'='*90}")
    print(f"  Exp2: LLM Calibration Comparison  (model={results['model']})")
    print(f"{'='*90}")
    print(f"  A = Standard SCE-UA  |  B = Zhu et al. 2026  |  C = HydroClaw (ours)")
    print()

    header = (f"{'Basin':<12} {'Zone':<20} "
              f"{'A NSE':>8} {'B NSE':>8} {'C NSE':>8} "
              f"{'ΔB-A':>7} {'ΔC-A':>7} {'ΔC-B':>7} "
              f"{'Bounds':>6} {'B iters':>7} {'C rnds':>7}")
    print(header)
    print("-" * 95)

    for r in data:
        a_nse = r["method_A"].get("train_metrics", {}).get("NSE")
        b_nse = r["method_B"].get("best_nse")
        c_nse = r["method_C"].get("best_nse")
        fmt = lambda v: f"{v:.4f}" if isinstance(v, float) else "N/A"
        dfmt = lambda v: f"{v:+.4f}" if isinstance(v, float) else "N/A"
        bounds = len(r["method_A"].get("boundary_hits", []))
        print(
            f"{r['basin_id']:<12} {r['climate_zone']:<20} "
            f"{fmt(a_nse):>8} {fmt(b_nse):>8} {fmt(c_nse):>8} "
            f"{dfmt(r.get('delta_B_vs_A')):>7} "
            f"{dfmt(r.get('delta_C_vs_A')):>7} "
            f"{dfmt(r.get('delta_C_vs_B')):>7} "
            f"{bounds:>6} "
            f"{r['method_B'].get('iterations', 0):>7} "
            f"{r['method_C'].get('rounds', 0):>7}"
        )

    print(f"\n  NSE trajectory (Method C - HydroClaw range adjustment):")
    for r in data:
        hist = r["method_C"].get("nse_history", [])
        traj = " -> ".join(f"{v:.3f}" for v in hist if isinstance(v, float))
        print(f"    {r['basin_id']}: {traj or 'no data'}")

    tokens = results.get("llm_token_usage", {})
    print(f"\n  LLM: {tokens.get('calls', 0)} calls, {tokens.get('total_tokens', 0)} tokens")


def main():
    setup_logging()
    logger.info("Starting Exp2: LLM Calibration Comparison")
    results = run_experiment()
    save_results(results)
    print_summary(results)
    logger.info("Exp2 complete")


if __name__ == "__main__":
    main()
