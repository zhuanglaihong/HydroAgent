"""
Experiment 1 - Standard Calibration Baseline (Agent-Driven)
============================================================
Purpose: Verify that HydroClaw agent correctly executes the full calibration
         workflow from natural language, and establish NSE/KGE baselines.
Method:  HydroClaw agent receives a natural language calibration query.
         Agent autonomously decides: validate_basin -> calibrate_model -> evaluate_model.
Design:  5 basins x 2 models x SCE-UA.

Paper:   Section 4.2 - Standard Calibration Baseline
Demonstrates: Agent-driven workflow planning and execution reliability.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import logging
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
OUTPUT_DIR = Path("results/paper/exp1")


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
    """Read calibration config and evaluate both train and test periods from disk.

    This is called AFTER the agent run to get precise, structured metrics
    regardless of which exact evaluate_model calls the agent made.
    """
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


# ── Single task runner ────────────────────────────────────────────────────────

def run_single_task(
    basin_id: str, basin_name: str, climate_zone: str,
    model_name: str, cfg: dict,
) -> dict:
    """Run one calibration task through the HydroClaw agent.

    The agent receives a natural language query and autonomously decides:
    validate_basin -> calibrate_model -> evaluate_model (train + test).
    After the run, metrics are extracted from the agent's tool call log
    and verified by reading calibration outputs from disk.
    """
    from hydroclaw.agent import HydroClaw
    from hydroclaw.ui import ConsoleUI

    combo = f"{model_name}_{basin_id}"
    task_workspace = OUTPUT_DIR / combo
    task_workspace.mkdir(parents=True, exist_ok=True)

    # Natural language query - agent decides the full workflow
    query = (
        f"请率定{model_name.upper()}模型，流域{basin_id}，使用SCE-UA算法。"
        f"请先验证流域数据，然后进行率定，最后分别评估训练期和测试期的NSE和KGE指标，"
        f"输出目录请保存在 {task_workspace}。"
    )

    agent = HydroClaw(
        workspace=task_workspace,
        ui=ConsoleUI(mode="dev"),  # dev mode: show tool calls, suppress verbose output
    )

    record = {
        "basin_id": basin_id,
        "basin_name": basin_name,
        "climate_zone": climate_zone,
        "model_name": model_name,
        "algorithm": ALGORITHM,
        "success": False,
        "train_metrics": {},
        "test_metrics": {},
        "best_params": {},
        "calibration_time_s": 0,
        "tool_sequence": [],
        "agent_turns": 0,
        "error": None,
    }

    t0 = time.time()
    try:
        agent.run(query)
    except Exception as e:
        logger.error(f"Agent run failed for {combo}: {e}", exc_info=True)
        record["error"] = str(e)
        record["calibration_time_s"] = round(time.time() - t0, 2)
        return record

    record["calibration_time_s"] = round(time.time() - t0, 2)
    record["agent_turns"] = len(agent.memory._log)

    # Extract calibration_dir and tool sequence from agent log
    log_info = _extract_from_log(agent.memory._log)
    record["tool_sequence"] = log_info["tool_sequence"]
    record["best_params"] = log_info["best_params"]

    # Verify and collect metrics from disk (reliable, independent of agent's evaluate calls)
    cal_dir = log_info.get("calibration_dir", "")
    if cal_dir and Path(cal_dir).exists():
        train_m, test_m = _evaluate_from_disk(cal_dir, cfg)
        record["train_metrics"] = train_m
        record["test_metrics"] = test_m
        record["success"] = bool(train_m.get("NSE") is not None)
        if not record["success"]:
            record["error"] = "Calibration completed but evaluation failed"
    else:
        record["success"] = False
        record["error"] = f"No valid calibration_dir in agent log (got: '{cal_dir}')"

    return record


# ── Main experiment ───────────────────────────────────────────────────────────

def run_experiment() -> dict:
    from hydroclaw.config import load_config

    cfg = load_config()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    for basin_id, basin_name, climate_zone in BASINS:
        for model_name in MODELS:
            combo = f"{model_name}_{basin_id}"
            logger.info(f"── {combo} ({basin_name}) ──")

            record = run_single_task(basin_id, basin_name, climate_zone, model_name, cfg)
            results.append(record)

            def _fmt(v):
                return f"{v:.3f}" if isinstance(v, (int, float)) else "N/A"

            if record["success"]:
                tr_nse = _fmt(record["train_metrics"].get("NSE"))
                te_nse = _fmt(record["test_metrics"].get("NSE"))
                logger.info(
                    f"  train NSE={tr_nse}  test NSE={te_nse}  "
                    f"time={record['calibration_time_s']:.0f}s  "
                    f"tools={record['tool_sequence']}"
                )
            else:
                logger.info(
                    f"  FAILED: {record['error']}  "
                    f"tools={record['tool_sequence']}"
                )

    return {
        "experiment": "exp1_standard_calibration",
        "mode": "agent_driven",
        "timestamp": datetime.now().isoformat(),
        "basins": [b[0] for b in BASINS],
        "models": MODELS,
        "algorithm": ALGORITHM,
        "results": results,
        "n_total": len(results),
        "n_success": sum(1 for r in results if r["success"]),
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
    data = results["results"]
    print(f"\n{'='*100}")
    print(
        f"  Exp1: Standard Calibration (Agent-Driven)  "
        f"({results['n_success']}/{results['n_total']} successful)"
    )
    print(f"{'='*100}")
    print(
        f"{'Basin':<12} {'Model':<6} {'Zone':<20} "
        f"{'Train NSE':>10} {'Test NSE':>10} {'Train KGE':>10} "
        f"{'Time(s)':>8} {'Turns':>6} {'Tools':>40}"
    )
    print("-" * 120)

    def _f(v):
        return f"{v:.4f}" if isinstance(v, (int, float)) else "N/A"

    for r in data:
        tr_nse = _f(r["train_metrics"].get("NSE"))
        te_nse = _f(r.get("test_metrics", {}).get("NSE"))
        tr_kge = _f(r["train_metrics"].get("KGE"))
        tools = "->".join(r.get("tool_sequence", []))
        flag = "" if r["success"] else " [FAIL]"
        print(
            f"{r['basin_id']:<12} {r['model_name']:<6} {r['climate_zone']:<20} "
            f"{tr_nse:>10} {te_nse:>10} {tr_kge:>10} "
            f"{r['calibration_time_s']:>8.1f} {r.get('agent_turns', 0):>6} "
            f"{tools[:40]:>40}{flag}"
        )

    # Mean NSE by climate zone
    print(f"\n  Mean Train NSE by climate zone:")
    from collections import defaultdict
    zone_nse: dict = defaultdict(list)
    for r in data:
        if r["success"] and r["train_metrics"].get("NSE") is not None:
            zone_nse[r["climate_zone"]].append(r["train_metrics"]["NSE"])
    for zone, vals in zone_nse.items():
        print(f"    {zone:<22} mean = {sum(vals)/len(vals):.3f}  (n={len(vals)})")

    # Tool sequence analysis
    print(f"\n  Tool sequence analysis (agent autonomy check):")
    expected = {"validate_basin", "calibrate_model", "evaluate_model"}
    for r in data:
        called = set(r.get("tool_sequence", []))
        hit = expected & called
        miss = expected - called
        status = "OK" if "calibrate_model" in called else "MISSING_CALIBRATE"
        print(f"    {r['basin_id']} {r['model_name']:<6}: {status}  hit={hit}  miss={miss}")


def main():
    setup_logging()
    logger.info("Starting Exp1: Standard Calibration (Agent-Driven)")
    results = run_experiment()
    save_results(results)
    print_summary(results)
    logger.info("Exp1 complete")


if __name__ == "__main__":
    main()
