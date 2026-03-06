"""
Author: HydroClaw Team
Date: 2026-02-09
Description: Experiment 2 - LLM-guided calibration vs standard calibration.
             Demonstrates that LLM range adjustment improves performance on
             basins where parameters hit boundaries.
             Directly calls tool functions for reproducibility.
FilePath: /HydroAgent/scripts/exp2_llm_calibration.py
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────

# "Difficult" basins where parameters tend to hit boundaries
# (select based on Exp1 results, or use these known tricky ones)
BASINS = [
    "06043500",  # Gallatin River, MT - mountainous, snowmelt-driven
    "08167500",  # Guadalupe River, TX - semi-arid, flashy
    "12025000",  # Fish River, ME - baseline comparison
]

MODEL = "gr4j"  # GR4J has interpretable boundary effects (4 params)
MAX_ROUNDS = 5
NSE_TARGET = 0.75

OUTPUT_DIR = Path("results/paper/exp2")


def setup_logging():
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    log_file = logs_dir / f"exp2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


def run_experiment() -> dict:
    """Compare standard calibration vs LLM-guided calibration."""
    from hydroclaw.config import load_config
    from hydroclaw.llm import LLMClient
    from hydroclaw.tools.calibrate import calibrate_model
    from hydroclaw.tools.evaluate import evaluate_model
    from hydroclaw.tools.llm_calibrate import llm_calibrate

    cfg = load_config()
    llm = LLMClient(cfg["llm"])
    results = []

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for basin_id in BASINS:
        logger.info(f"{'='*60}")
        logger.info(f"Basin: {basin_id}")
        logger.info(f"{'='*60}")

        record = {
            "basin_id": basin_id,
            "model_name": MODEL,
            "standard": {},
            "llm_guided": {},
        }

        # ── A) Standard calibration (single SCE-UA run, default ranges) ──
        logger.info(f"[A] Standard calibration for {basin_id}")
        std_output_dir = str(OUTPUT_DIR / f"standard_{MODEL}_{basin_id}")

        t0 = time.time()
        std_result = calibrate_model(
            basin_ids=[basin_id],
            model_name=MODEL,
            algorithm="SCE_UA",
            output_dir=std_output_dir,
            _cfg=cfg,
        )
        std_time = round(time.time() - t0, 2)

        std_entry = {
            "success": std_result.get("success", False),
            "metrics": std_result.get("metrics", {}),
            "best_params": std_result.get("best_params", {}),
            "calibration_time_s": std_time,
            "calibration_dir": std_result.get("calibration_dir", ""),
        }

        # Evaluate on test period
        if std_result.get("success"):
            eval_result = evaluate_model(
                calibration_dir=std_result.get("calibration_dir", std_output_dir),
                _cfg=cfg,
            )
            if eval_result.get("success"):
                std_entry["test_metrics"] = eval_result.get("metrics", {})

        # Detect boundary effects
        std_entry["boundary_hits"] = _detect_boundaries(
            std_entry["best_params"], MODEL
        )

        record["standard"] = std_entry
        logger.info(
            f"[A] Standard: NSE={std_entry['metrics'].get('NSE', 'N/A')}, "
            f"boundaries={std_entry['boundary_hits']}"
        )

        # ── B) LLM-guided calibration (multi-round with range adjustment) ──
        logger.info(f"[B] LLM-guided calibration for {basin_id}")
        llm_output_dir = str(OUTPUT_DIR / f"llm_{MODEL}_{basin_id}")

        t0 = time.time()
        llm_result = llm_calibrate(
            basin_ids=[basin_id],
            model_name=MODEL,
            max_rounds=MAX_ROUNDS,
            nse_target=NSE_TARGET,
            algorithm="SCE_UA",
            _workspace=Path(llm_output_dir),
            _cfg=cfg,
            _llm=llm,
        )
        llm_time = round(time.time() - t0, 2)

        llm_entry = {
            "success": llm_result.get("success", False),
            "best_nse": llm_result.get("best_nse"),
            "best_params": llm_result.get("best_params", {}),
            "rounds": llm_result.get("rounds", 0),
            "history": llm_result.get("history", []),
            "calibration_time_s": llm_time,
            "calibration_dir": llm_result.get("calibration_dir", ""),
        }

        # Evaluate on test period
        if llm_result.get("success") and llm_result.get("calibration_dir"):
            eval_result = evaluate_model(
                calibration_dir=llm_result["calibration_dir"],
                _cfg=cfg,
            )
            if eval_result.get("success"):
                llm_entry["test_metrics"] = eval_result.get("metrics", {})

        record["llm_guided"] = llm_entry
        logger.info(
            f"[B] LLM-guided: best_NSE={llm_entry.get('best_nse', 'N/A')}, "
            f"rounds={llm_entry.get('rounds', 0)}"
        )

        # ── Summary ──
        std_nse = std_entry["metrics"].get("NSE", -999)
        llm_nse = llm_entry.get("best_nse", -999)
        improvement = llm_nse - std_nse if isinstance(std_nse, (int, float)) and isinstance(llm_nse, (int, float)) else None
        record["nse_improvement"] = improvement
        logger.info(f"NSE improvement: {improvement}")

        # Token usage from LLM
        record["llm_token_usage"] = llm.tokens.summary()

        results.append(record)

    return {
        "experiment": "exp2_llm_calibration",
        "timestamp": datetime.now().isoformat(),
        "basins": BASINS,
        "model": MODEL,
        "max_rounds": MAX_ROUNDS,
        "nse_target": NSE_TARGET,
        "results": results,
    }


def _detect_boundaries(best_params: dict, model_name: str) -> list[dict]:
    """Detect which parameters hit their default range boundaries."""
    from hydroclaw.tools.llm_calibrate import DEFAULT_PARAM_RANGES

    default_ranges = DEFAULT_PARAM_RANGES.get(model_name, {})
    hits = []

    for name, value in best_params.items():
        if name not in default_ranges:
            continue
        lo, hi = default_ranges[name]
        span = hi - lo
        if span <= 0:
            continue

        lo_pct = (value - lo) / span * 100
        hi_pct = (hi - value) / span * 100

        if lo_pct < 5:
            hits.append({"param": name, "value": value, "boundary": "lower", "pct_from_bound": round(lo_pct, 2)})
        elif hi_pct < 5:
            hits.append({"param": name, "value": value, "boundary": "upper", "pct_from_bound": round(hi_pct, 2)})

    return hits


def save_results(results: dict):
    output_file = OUTPUT_DIR / "exp2_results.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"Results saved to {output_file}")


def print_summary(results: dict):
    print(f"\n{'='*80}")
    print(f"  Experiment 2: LLM-Guided Calibration vs Standard")
    print(f"{'='*80}\n")

    header = f"{'Basin':<12} {'Std NSE':>8} {'LLM NSE':>8} {'Improve':>8} {'Rounds':>7} {'Boundaries'}"
    print(header)
    print("-" * 75)

    for r in results["results"]:
        std_nse = r["standard"]["metrics"].get("NSE", "N/A")
        llm_nse = r["llm_guided"].get("best_nse", "N/A")
        improve = r.get("nse_improvement")
        rounds = r["llm_guided"].get("rounds", 0)
        boundaries = ", ".join(
            f"{h['param']}({h['boundary'][0]})" for h in r["standard"].get("boundary_hits", [])
        ) or "none"

        std_str = f"{std_nse:.4f}" if isinstance(std_nse, (int, float)) else str(std_nse)
        llm_str = f"{llm_nse:.4f}" if isinstance(llm_nse, (int, float)) else str(llm_nse)
        imp_str = f"{improve:+.4f}" if isinstance(improve, (int, float)) else "N/A"

        print(f"{r['basin_id']:<12} {std_str:>8} {llm_str:>8} {imp_str:>8} {rounds:>7} {boundaries}")

    # NSE trajectory per basin
    print(f"\nNSE trajectory per basin (LLM rounds):")
    for r in results["results"]:
        history = r["llm_guided"].get("history", [])
        trajectory = [f"R{h.get('round', '?')}:{h.get('nse', 'N/A'):.3f}"
                      for h in history if isinstance(h.get("nse"), (int, float))]
        print(f"  {r['basin_id']}: {' -> '.join(trajectory) or 'no data'}")

    # Parameter range changes
    print(f"\nParameter range adjustments (LLM rounds):")
    for r in results["results"]:
        history = r["llm_guided"].get("history", [])
        if len(history) > 1:
            print(f"  {r['basin_id']}:")
            for h in history:
                ranges = h.get("param_ranges", {})
                if ranges:
                    range_str = ", ".join(f"{k}:[{v[0]:.1f},{v[1]:.1f}]" for k, v in ranges.items())
                    print(f"    Round {h.get('round', '?')}: {range_str}")


def main():
    setup_logging()
    logger.info("Starting Experiment 2: LLM-Guided Calibration")
    results = run_experiment()
    save_results(results)
    print_summary(results)
    logger.info("Experiment 2 complete")


if __name__ == "__main__":
    main()
