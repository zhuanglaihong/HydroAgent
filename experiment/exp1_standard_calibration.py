"""
Experiment 1 - Standard Calibration Baseline (Agent-Driven)
============================================================
Purpose: Verify that HydroAgent agent correctly executes the full calibration
         workflow from natural language, and establish KGE/NSE baselines.
Method:  HydroAgent agent receives a natural language calibration query.
         Agent autonomously decides: validate_basin -> calibrate_model -> evaluate_model.
Design:  5 basins x 2 models x SCE-UA x N_SEEDS independent runs.

Statistical design:
  - N_SEEDS=3 independent runs per basin-model combo to capture algorithm variance
  - Primary metric: KGE (Kling-Gupta Efficiency), secondary: NSE
    Rationale: KGE is more balanced across bias/correlation/variability components
    than NSE (see Knoben et al. 2019, HESS, doi:10.5194/hess-23-4323-2019)
  - Report mean +/- std across runs

Data periods (CAMELS-US, documented for reproducibility):
  - Warm-up:   1980-01-01 to 1984-12-31 (5 years, avoids cold-start bias)
  - Train:     1985-01-01 to 2000-12-31
  - Test:      2001-01-01 to 2014-12-31
  (Actual periods loaded from calibration_config.yaml written by hydromodel)

Paper:   Section 4.2 - Standard Calibration Baseline
Demonstrates: Agent-driven workflow planning and execution reliability.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import logging
import statistics
import time
from datetime import datetime

import matplotlib
matplotlib.use("Agg")

logger = logging.getLogger(__name__)

# ── Experiment configuration ─────────────────────────────────────────────────

BASINS = [
    ("12025000", "Fish River, ME",        "humid_cold"),
    ("03439000", "French Broad River, NC", "humid_warm"),
    ("06043500", "Gallatin River, MT",     "semiarid_mountain"),
    ("08101000", "Cowhouse Creek, TX",     "semiarid_flashy"),
    ("11532500", "Smith River, CA",        "mediterranean"),
]

MODELS = ["gr4j", "xaj"]
ALGORITHM = "SCE_UA"
N_SEEDS = 3          # independent runs per basin-model combo for mean+/-std
OUTPUT_DIR = Path("results/paper/exp1")

# Expected tool call sequence for correctness check
EXPECTED_TOOLS = {"validate_basin", "calibrate_model", "evaluate_model"}


def setup_logging():
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(logs_dir / f"exp1_{ts}.log", encoding="utf-8"),
        ],
    )


# ── Failure classification ────────────────────────────────────────────────────

def _classify_failure(record: dict) -> str:
    """Classify why a run failed into one of five categories.

    Categories (for failure mode analysis in Discussion section):
      WRONG_SKILL      - agent never called calibrate_model (skill mismatch)
      CALIBRATION_ERR  - calibrate_model called but optimizer failed
      EVALUATION_ERR   - calibration succeeded but post-evaluation failed
      CONTEXT_OVERFLOW - agent hit token/context limit
      AGENT_ERROR      - unhandled exception in agent loop
    """
    if record.get("success"):
        return "none"
    tools = set(record.get("tool_sequence", []))
    err = str(record.get("error", "")).lower()

    if "calibrate_model" not in tools and "llm_calibrate" not in tools:
        return "WRONG_SKILL"
    if "context" in err or "token" in err or "length" in err or "too long" in err:
        return "CONTEXT_OVERFLOW"
    if "calibration" in err or "optimizer" in err or "nan" in err or "no valid" in err:
        return "CALIBRATION_ERR"
    if "evaluation" in err or "metrics" in err or "yaml" in err:
        return "EVALUATION_ERR"
    return "AGENT_ERROR"


# ── Log extraction helpers ────────────────────────────────────────────────────

def _extract_from_log(memory_log: list[dict]) -> dict:
    """Extract calibration_dir, best_params, tool_sequence from agent memory log."""
    result = {
        "calibration_dir": "",
        "best_params": {},
        "tool_sequence": [],
    }
    for entry in memory_log:
        tool = entry.get("tool", "")
        result["tool_sequence"].append(tool)
        r = entry.get("result_summary", {})
        if not isinstance(r, dict):
            continue
        if tool in ("calibrate_model", "llm_calibrate") and r.get("success"):
            cal_dir = r.get("calibration_dir", "")
            if cal_dir:
                result["calibration_dir"] = str(cal_dir)
            result["best_params"] = r.get("best_params", {})
    return result


def _evaluate_from_disk(cal_dir: str, cfg: dict) -> tuple[dict, dict]:
    """Read calibration config and evaluate both train and test periods from disk."""
    from hydroagent.skills.evaluation.evaluate import evaluate_model
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


# ── Single task runner ────────────────────────────────────────────────────────

def run_single_task(
    basin_id: str, basin_name: str, climate_zone: str,
    model_name: str, run_idx: int, cfg: dict,
) -> dict:
    """Run one calibration task through the HydroAgent agent (single independent run).

    run_idx: 0-based index, used for workspace isolation across repeated runs.
    Each run uses a fresh agent and fresh workspace, so SCE-UA random initialization
    varies naturally (no explicit seed needed for inter-run variance).
    """
    from hydroagent.agent import HydroAgent
    from hydroagent.interface.ui import ConsoleUI

    combo = f"{model_name}_{basin_id}"
    task_workspace = OUTPUT_DIR / combo / f"run{run_idx + 1}"
    task_workspace.mkdir(parents=True, exist_ok=True)

    query = (
        f"请率定{model_name.upper()}模型，流域{basin_id}，使用SCE-UA算法。"
        f"请先验证流域数据，然后进行率定，最后分别评估训练期和测试期的KGE和NSE指标，"
        f"输出目录请保存在 {task_workspace}。"
    )

    agent = HydroAgent(workspace=task_workspace, ui=ConsoleUI(mode="dev"))

    record = {
        "basin_id": basin_id,
        "basin_name": basin_name,
        "climate_zone": climate_zone,
        "model_name": model_name,
        "algorithm": ALGORITHM,
        "run_idx": run_idx,
        "success": False,
        "train_metrics": {},
        "test_metrics": {},
        "best_params": {},
        "wall_time_s": 0.0,
        "total_tokens": 0,
        "agent_turns": 0,
        "tool_sequence": [],
        "failure_type": "none",
        "error": None,
    }

    t0 = time.time()
    try:
        agent.run(query)
    except Exception as e:
        logger.error(f"Agent run failed for {combo} run{run_idx+1}: {e}", exc_info=True)
        record["error"] = str(e)
        record["wall_time_s"] = round(time.time() - t0, 2)
        record["failure_type"] = _classify_failure(record)
        return record

    record["wall_time_s"] = round(time.time() - t0, 2)
    record["agent_turns"] = len(agent.memory._log)

    # Token usage for this run
    try:
        tok = agent.llm.tokens.summary()
        record["total_tokens"] = tok.get("total_tokens", 0)
    except Exception:
        pass

    log_info = _extract_from_log(agent.memory._log)
    record["tool_sequence"] = log_info["tool_sequence"]
    record["best_params"] = log_info["best_params"]

    cal_dir = log_info.get("calibration_dir", "")
    if cal_dir and Path(cal_dir).exists():
        train_m, test_m = _evaluate_from_disk(cal_dir, cfg)
        record["train_metrics"] = train_m
        record["test_metrics"] = test_m
        # KGE is primary; NSE as fallback check
        record["success"] = bool(
            train_m.get("KGE") is not None or train_m.get("NSE") is not None
        )
        if not record["success"]:
            record["error"] = "Calibration completed but evaluation failed"
    else:
        record["success"] = False
        record["error"] = f"No valid calibration_dir in agent log (got: '{cal_dir}')"

    record["failure_type"] = _classify_failure(record)
    return record


# ── Aggregation helpers ───────────────────────────────────────────────────────

def _stats(vals: list) -> dict:
    """Compute mean +/- std over a list of floats (skips None)."""
    clean = [v for v in vals if isinstance(v, (int, float))]
    if not clean:
        return {"mean": None, "std": None, "n": 0}
    mean = statistics.mean(clean)
    std = statistics.stdev(clean) if len(clean) > 1 else 0.0
    return {"mean": round(mean, 4), "std": round(std, 4), "n": len(clean)}


def _aggregate_runs(combo_runs: list[dict]) -> dict:
    """Compute mean +/- std metrics across N_SEEDS independent runs for one basin-model combo."""
    first = combo_runs[0]
    agg = {
        "basin_id": first["basin_id"],
        "basin_name": first["basin_name"],
        "climate_zone": first["climate_zone"],
        "model_name": first["model_name"],
        "n_runs": len(combo_runs),
        "n_success": sum(1 for r in combo_runs if r["success"]),
        # KGE is the primary metric
        "kge_train": _stats([r["train_metrics"].get("KGE") for r in combo_runs if r["success"]]),
        "kge_test":  _stats([r["test_metrics"].get("KGE")  for r in combo_runs if r["success"]]),
        # NSE as secondary
        "nse_train": _stats([r["train_metrics"].get("NSE") for r in combo_runs if r["success"]]),
        "nse_test":  _stats([r["test_metrics"].get("NSE")  for r in combo_runs if r["success"]]),
        "wall_time_s_mean": round(statistics.mean(r["wall_time_s"] for r in combo_runs), 1),
        "total_tokens_sum": sum(r.get("total_tokens", 0) for r in combo_runs),
        "failure_types": [r["failure_type"] for r in combo_runs if not r["success"]],
        "tool_sequences": [r.get("tool_sequence", []) for r in combo_runs],
    }
    return agg


# ── Main experiment ───────────────────────────────────────────────────────────

def run_experiment() -> dict:
    from hydroagent.config import load_config

    cfg = load_config()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results_flat = []   # all individual runs (for detailed analysis)
    results_agg = []    # aggregated per combo (for table display)

    for basin_id, basin_name, climate_zone in BASINS:
        for model_name in MODELS:
            combo = f"{model_name}_{basin_id}"
            logger.info(f"\n{'='*60}")
            logger.info(f"Combo: {combo} ({basin_name}, {climate_zone})")
            logger.info(f"{'='*60}")

            combo_runs = []
            for run_idx in range(N_SEEDS):
                logger.info(f"  -- Run {run_idx+1}/{N_SEEDS} --")
                record = run_single_task(
                    basin_id, basin_name, climate_zone, model_name, run_idx, cfg
                )
                combo_runs.append(record)
                results_flat.append(record)

                def _fmt(v):
                    return f"{v:.3f}" if isinstance(v, (int, float)) else "N/A"

                if record["success"]:
                    logger.info(
                        f"  Run{run_idx+1}: train KGE={_fmt(record['train_metrics'].get('KGE'))} "
                        f"NSE={_fmt(record['train_metrics'].get('NSE'))}  "
                        f"test KGE={_fmt(record['test_metrics'].get('KGE'))}  "
                        f"time={record['wall_time_s']:.0f}s  tokens={record['total_tokens']}"
                    )
                else:
                    logger.info(
                        f"  Run{run_idx+1}: FAILED [{record['failure_type']}] {record['error']}"
                    )

            agg = _aggregate_runs(combo_runs)
            results_agg.append(agg)
            logger.info(
                f"  Aggregated: KGE_train={agg['kge_train']['mean']}+/-{agg['kge_train']['std']} "
                f"KGE_test={agg['kge_test']['mean']}+/-{agg['kge_test']['std']} "
                f"({agg['n_success']}/{agg['n_runs']} success)"
            )

    return {
        "experiment": "exp1_standard_calibration",
        "mode": "agent_driven",
        "timestamp": datetime.now().isoformat(),
        "basins": [b[0] for b in BASINS],
        "models": MODELS,
        "algorithm": ALGORITHM,
        "n_seeds": N_SEEDS,
        "primary_metric": "KGE (Knoben et al. 2019)",
        "data_periods": "Train: 1985-2000, Test: 2001-2014, Warmup: 1980-1984",
        "results_agg": results_agg,
        "results_flat": results_flat,
        "n_total_runs": len(results_flat),
        "n_success_runs": sum(1 for r in results_flat if r["success"]),
    }


def save_results(results: dict):
    f = OUTPUT_DIR / "exp1_results.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    f.write_text(
        json.dumps(results, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    logger.info(f"Saved -> {f}")


def print_summary(results: dict):
    data = results["results_agg"]
    n_total = results["n_total_runs"]
    n_ok = results["n_success_runs"]

    print(f"\n{'='*110}")
    print(
        f"  Exp1: Standard Calibration (Agent-Driven, {N_SEEDS} runs/combo)  "
        f"({n_ok}/{n_total} runs successful)"
    )
    print(f"  Primary metric: KGE | Secondary: NSE  "
          f"[format: mean +/- std over {N_SEEDS} independent runs]")
    print(f"{'='*110}")
    print(
        f"{'Basin':<12} {'Model':<6} {'Zone':<20} "
        f"{'KGE_train':>14} {'KGE_test':>14} "
        f"{'NSE_train':>14} {'NSE_test':>14} "
        f"{'OK':>4} {'Time(s)':>8} {'Tokens':>8}"
    )
    print("-" * 110)

    def _ms(d: dict) -> str:
        """Format mean+/-std dict."""
        if d["mean"] is None:
            return "    N/A"
        return f"{d['mean']:.3f}+/-{d['std']:.3f}"

    for r in data:
        ok_str = f"{r['n_success']}/{r['n_runs']}"
        print(
            f"{r['basin_id']:<12} {r['model_name']:<6} {r['climate_zone']:<20} "
            f"{_ms(r['kge_train']):>14} {_ms(r['kge_test']):>14} "
            f"{_ms(r['nse_train']):>14} {_ms(r['nse_test']):>14} "
            f"{ok_str:>4} {r['wall_time_s_mean']:>8.1f} {r['total_tokens_sum']:>8}"
        )

    # Mean KGE by climate zone
    print(f"\n  Mean Train KGE by climate zone (across models, {N_SEEDS} runs each):")
    from collections import defaultdict
    zone_kge: dict = defaultdict(list)
    for r in data:
        v = r["kge_train"]["mean"]
        if v is not None:
            zone_kge[r["climate_zone"]].append(v)
    for zone, vals in zone_kge.items():
        print(f"    {zone:<25} mean = {statistics.mean(vals):.3f}  (n={len(vals)} combos)")

    # Tool sequence correctness
    print(f"\n  Tool sequence correctness (agent autonomy check):")
    for r in data:
        seqs = r.get("tool_sequences", [])
        match_count = sum(
            1 for seq in seqs
            if "calibrate_model" in seq and "evaluate_model" in seq
        )
        consistency = sum(
            1 for i in range(len(seqs) - 1) if seqs[i] == seqs[i+1]
        )
        print(
            f"    {r['basin_id']} {r['model_name']:<5}: "
            f"full_seq_ok={match_count}/{len(seqs)}  "
            f"sequence_consistent={consistency}/{max(len(seqs)-1, 1)}"
        )

    # Failure analysis
    all_failures = []
    for r in data:
        all_failures.extend(r.get("failure_types", []))
    if all_failures:
        from collections import Counter
        print(f"\n  Failure type breakdown:")
        for ftype, count in Counter(all_failures).most_common():
            print(f"    {ftype:<20} {count} run(s)")


def main():
    setup_logging()
    logger.info(f"Starting Exp1: Standard Calibration (N_SEEDS={N_SEEDS})")
    results = run_experiment()
    save_results(results)
    print_summary(results)
    logger.info("Exp1 complete")


if __name__ == "__main__":
    main()
