"""
Experiment 1 - Standard Calibration Baseline
=============================================
目的：验证工具链正确性，建立 NSE/KGE 基线，供 Exp2/Exp6 作对照。
方法：直接调用工具函数（不走 LLM 对话），排除 LLM 随机性。
设计：5 流域 × 2 模型 × SCE-UA 算法。

论文对应：Section 4.2
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

# ── 实验配置 ──────────────────────────────────────────────────────────────

BASINS = [
    ("12025000", "Fish River, ME",        "humid_cold"),
    ("03439000", "French Broad River, NC", "humid_warm"),
    ("06043500", "Gallatin River, MT",     "semiarid_mountain"),
    ("08101000", "Cowhouse Creek, TX",      "semiarid_flashy"),
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


def run_experiment() -> dict:
    from hydroclaw.config import load_config
    from hydroclaw.skills.calibration.calibrate import calibrate_model
    from hydroclaw.skills.evaluation.evaluate import evaluate_model
    from hydroclaw.tools.validate import validate_basin

    cfg = load_config()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    for basin_id, basin_name, climate_zone in BASINS:
        for model_name in MODELS:
            combo = f"{model_name}_{basin_id}"
            logger.info(f"── {combo} ({basin_name}) ──")

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
                "error": None,
            }

            try:
                # Step 1: 验证流域数据
                val = validate_basin(basin_ids=[basin_id], _cfg=cfg)
                if not val.get("valid"):
                    record["error"] = f"Validation failed: {val.get('invalid_basins')}"
                    results.append(record)
                    continue

                # Step 2: 率定
                out_dir = str(OUTPUT_DIR / combo)
                t0 = time.time()
                cal = calibrate_model(
                    basin_ids=[basin_id],
                    model_name=model_name,
                    algorithm=ALGORITHM,
                    output_dir=out_dir,
                    _cfg=cfg,
                )
                record["calibration_time_s"] = round(time.time() - t0, 2)

                if not cal.get("success"):
                    record["error"] = cal.get("error", "calibration failed")
                    results.append(record)
                    continue

                record["best_params"] = cal.get("best_params", {})
                record["train_metrics"] = cal.get("train_metrics", {})

                # Step 3: 测试期评估
                evl = evaluate_model(
                    calibration_dir=cal.get("calibration_dir", out_dir),
                    _cfg=cfg,
                )
                if evl.get("success"):
                    record["test_metrics"] = evl.get("metrics", {})

                record["success"] = True

            except Exception as e:
                logger.error(f"Exception for {combo}: {e}", exc_info=True)
                record["error"] = str(e)

            results.append(record)
            def _fmt(v): return f"{v:.3f}" if isinstance(v, (int, float)) else "N/A"
            if record["success"]:
                logger.info(
                    f"  train NSE={_fmt(record['train_metrics'].get('NSE'))}  "
                    f"test NSE={_fmt(record.get('test_metrics', {}).get('NSE'))}  "
                    f"time={record['calibration_time_s']:.0f}s"
                )
            else:
                logger.info(f"  FAILED: {record['error']}")

    return {
        "experiment": "exp1_standard_calibration",
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
    f.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    logger.info(f"Saved -> {f}")


def print_summary(results: dict):
    data = results["results"]
    print(f"\n{'='*90}")
    print(f"  Exp1: Standard Calibration  "
          f"({results['n_success']}/{results['n_total']} successful)")
    print(f"{'='*90}")
    print(f"{'Basin':<12} {'Model':<6} {'Zone':<20} "
          f"{'Train NSE':>10} {'Test NSE':>10} {'Train KGE':>10} {'Time(s)':>8}")
    print("-" * 90)
    def _f(v): return f"{v:.4f}" if isinstance(v, (int, float)) else "N/A"
    for r in data:
        tn = _f(r["train_metrics"].get("NSE"))
        ts = _f(r.get("test_metrics", {}).get("NSE"))
        tk = _f(r["train_metrics"].get("KGE"))
        flag = "" if r["success"] else " [FAIL]"
        print(
            f"{r['basin_id']:<12} {r['model_name']:<6} {r['climate_zone']:<20} "
            f"{tn:>10} {ts:>10} {tk:>10} {r['calibration_time_s']:>8.1f}{flag}"
        )

    # 按气候区统计均值
    print(f"\n  Mean NSE by climate zone:")
    from collections import defaultdict
    zone_nse: dict = defaultdict(list)
    for r in data:
        if r["success"] and r["train_metrics"].get("NSE") is not None:
            zone_nse[r["climate_zone"]].append(r["train_metrics"]["NSE"])
    for zone, vals in zone_nse.items():
        print(f"    {zone:<22} mean train NSE = {sum(vals)/len(vals):.3f}")


def main():
    setup_logging()
    logger.info("Starting Exp1: Standard Calibration")
    results = run_experiment()
    save_results(results)
    print_summary(results)
    logger.info("Exp1 complete")


if __name__ == "__main__":
    main()
