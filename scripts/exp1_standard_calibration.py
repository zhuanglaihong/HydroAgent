"""
Author: HydroClaw Team
Date: 2026-02-09
Description: Experiment 1 - Standard calibration across multiple basins and models.
             Validates basic system functionality and records performance metrics.
             Directly calls tool functions (no LLM dialogue) for reproducibility.
FilePath: /HydroAgent/scripts/exp1_standard_calibration.py
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path

# Force non-GUI matplotlib backend
import matplotlib
matplotlib.use("Agg")

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────

# Representative CAMELS basins (different climate zones, areas)
BASINS = [
    "01013500",  # Fish River, ME (humid, cold, 1450 km²)
    "03439000",  # French Broad River, NC (humid, warm, 2448 km²)
    "06043500",  # Gallatin River, MT (semi-arid, mountainous, 2168 km²)
    "08167500",  # Guadalupe River, TX (semi-arid, 3406 km²)
    "11532500",  # Smith River, CA (Mediterranean, 1553 km²)
]

MODELS = ["gr4j", "xaj"]

OUTPUT_DIR = Path("results/paper/exp1")


def setup_logging():
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    log_file = logs_dir / f"exp1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


def run_experiment() -> dict:
    """Run standard calibration for all basin × model combinations."""
    from hydroclaw.config import load_config
    from hydroclaw.tools.calibrate import calibrate_model
    from hydroclaw.tools.evaluate import evaluate_model
    from hydroclaw.tools.validate import validate_basin

    cfg = load_config()
    results = []
    tool_call_log = []

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for basin_id in BASINS:
        for model_name in MODELS:
            combo_id = f"{model_name}_{basin_id}"
            logger.info(f"{'='*60}")
            logger.info(f"Starting: {combo_id}")
            logger.info(f"{'='*60}")

            record = {
                "basin_id": basin_id,
                "model_name": model_name,
                "combo_id": combo_id,
                "success": False,
                "train_metrics": {},
                "test_metrics": {},
                "best_params": {},
                "calibration_time_s": 0,
                "tool_calls": [],
            }

            try:
                # Step 1: Validate basin
                t0 = time.time()
                val_result = validate_basin(
                    basin_ids=[basin_id], _cfg=cfg
                )
                tool_call_log.append({
                    "combo_id": combo_id,
                    "tool": "validate_basin",
                    "time_s": round(time.time() - t0, 2),
                })
                record["tool_calls"].append("validate_basin")

                if not val_result.get("valid"):
                    logger.warning(f"Basin {basin_id} validation failed: {val_result}")
                    record["error"] = f"Validation failed: {val_result.get('invalid_basins')}"
                    results.append(record)
                    continue

                # Step 2: Calibrate
                output_dir = str(OUTPUT_DIR / combo_id)
                t0 = time.time()
                cal_result = calibrate_model(
                    basin_ids=[basin_id],
                    model_name=model_name,
                    algorithm="SCE_UA",
                    output_dir=output_dir,
                    _cfg=cfg,
                )
                cal_time = round(time.time() - t0, 2)
                tool_call_log.append({
                    "combo_id": combo_id,
                    "tool": "calibrate_model",
                    "time_s": cal_time,
                })
                record["tool_calls"].append("calibrate_model")
                record["calibration_time_s"] = cal_time

                if not cal_result.get("success"):
                    logger.warning(f"Calibration failed for {combo_id}: {cal_result.get('error')}")
                    record["error"] = cal_result.get("error", "Unknown")
                    results.append(record)
                    continue

                record["best_params"] = cal_result.get("best_params", {})
                record["train_metrics"] = cal_result.get("metrics", {})

                # Step 3: Evaluate on test period
                calib_dir = cal_result.get("calibration_dir", output_dir)
                t0 = time.time()
                eval_result = evaluate_model(
                    calibration_dir=calib_dir,
                    _cfg=cfg,
                )
                tool_call_log.append({
                    "combo_id": combo_id,
                    "tool": "evaluate_model",
                    "time_s": round(time.time() - t0, 2),
                })
                record["tool_calls"].append("evaluate_model")

                if eval_result.get("success"):
                    record["test_metrics"] = eval_result.get("metrics", {})
                else:
                    logger.warning(f"Evaluation failed for {combo_id}: {eval_result.get('error')}")

                record["success"] = True
                record["calibration_dir"] = calib_dir

            except Exception as e:
                logger.error(f"Exception for {combo_id}: {e}", exc_info=True)
                record["error"] = str(e)

            results.append(record)
            logger.info(
                f"Finished {combo_id}: success={record['success']}, "
                f"train_NSE={record['train_metrics'].get('NSE', 'N/A')}, "
                f"test_NSE={record['test_metrics'].get('NSE', 'N/A')}, "
                f"time={record['calibration_time_s']}s"
            )

    return {
        "experiment": "exp1_standard_calibration",
        "timestamp": datetime.now().isoformat(),
        "basins": BASINS,
        "models": MODELS,
        "results": results,
        "tool_call_log": tool_call_log,
        "total_combinations": len(BASINS) * len(MODELS),
        "successful": sum(1 for r in results if r["success"]),
    }


def save_results(results: dict):
    """Save results to JSON for plot_paper_figures.py."""
    output_file = OUTPUT_DIR / "exp1_results.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"Results saved to {output_file}")


def print_summary(results: dict):
    """Print a human-readable summary table."""
    print(f"\n{'='*80}")
    print(f"  Experiment 1: Standard Calibration Results")
    print(f"  {results['successful']}/{results['total_combinations']} combinations successful")
    print(f"{'='*80}\n")

    header = f"{'Basin':<12} {'Model':<8} {'Train NSE':>10} {'Test NSE':>10} {'Train RMSE':>11} {'Test RMSE':>11} {'Time(s)':>8}"
    print(header)
    print("-" * len(header))

    for r in results["results"]:
        train_nse = r["train_metrics"].get("NSE", "N/A")
        test_nse = r["test_metrics"].get("NSE", "N/A")
        train_rmse = r["train_metrics"].get("RMSE", "N/A")
        test_rmse = r["test_metrics"].get("RMSE", "N/A")

        train_nse_str = f"{train_nse:.4f}" if isinstance(train_nse, (int, float)) else str(train_nse)
        test_nse_str = f"{test_nse:.4f}" if isinstance(test_nse, (int, float)) else str(test_nse)
        train_rmse_str = f"{train_rmse:.4f}" if isinstance(train_rmse, (int, float)) else str(train_rmse)
        test_rmse_str = f"{test_rmse:.4f}" if isinstance(test_rmse, (int, float)) else str(test_rmse)

        status = "" if r["success"] else " FAIL"
        print(
            f"{r['basin_id']:<12} {r['model_name']:<8} "
            f"{train_nse_str:>10} {test_nse_str:>10} "
            f"{train_rmse_str:>11} {test_rmse_str:>11} "
            f"{r['calibration_time_s']:>8.1f}{status}"
        )

    # Tool call sequence summary
    print(f"\nTool call sequence per combination:")
    for r in results["results"][:1]:
        print(f"  {' -> '.join(r['tool_calls'])}")

    print(f"\nTotal tool calls: {len(results['tool_call_log'])}")
    total_time = sum(t["time_s"] for t in results["tool_call_log"])
    print(f"Total execution time: {total_time:.1f}s")


def main():
    setup_logging()
    logger.info("Starting Experiment 1: Standard Calibration")
    results = run_experiment()
    save_results(results)
    print_summary(results)
    logger.info("Experiment 1 complete")


if __name__ == "__main__":
    main()
