"""
Author: HydroClaw Team
Date: 2026-03-06
Description: Batch calibration tool - calibrates multiple basins and aggregates results.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def batch_calibrate(
    basin_ids: list[str],
    model_name: str = "xaj",
    algorithm: str = "SCE_UA",
    train_period: list[str] | None = None,
    test_period: list[str] | None = None,
    algorithm_params: dict | None = None,
    repeat_runs: int = 1,
    random_seeds: list[int] | None = None,
    output_base_dir: str | None = None,
    _workspace: Path | None = None,
    _cfg: dict | None = None,
) -> dict:
    """Batch calibrate multiple basins and aggregate performance metrics.

    Runs calibrate_model + evaluate_model for each basin (and optionally multiple
    random seeds for stability analysis). Returns a summary table.

    Args:
        basin_ids: List of CAMELS basin IDs to calibrate
        model_name: Hydrological model name ("gr4j", "xaj", "gr5j", "gr6j")
        algorithm: Optimization algorithm ("SCE_UA", "GA", "scipy")
        train_period: Training period ["YYYY-MM-DD", "YYYY-MM-DD"]
        test_period: Testing period ["YYYY-MM-DD", "YYYY-MM-DD"]
        algorithm_params: Base algorithm parameter overrides
        repeat_runs: Number of repeated runs per basin (for stability analysis), default 1
        random_seeds: Specific random seeds for each run; auto-generated if not given
        output_base_dir: Base directory for all output subdirectories

    Returns:
        {"results": [...], "summary": {...}, "success": bool}
    """
    from hydroclaw.skills.calibration.calibrate import calibrate_model
    from hydroclaw.skills.evaluation.evaluate import evaluate_model

    base_dir = Path(output_base_dir) if output_base_dir else (_workspace or Path("results"))
    base_dir.mkdir(parents=True, exist_ok=True)

    # Generate seeds if not provided
    if repeat_runs > 1 and not random_seeds:
        random_seeds = [1234 + i * 1111 for i in range(repeat_runs)]
    elif not random_seeds:
        random_seeds = [1234]

    results = []
    all_nse = []
    failed = []

    total = len(basin_ids) * repeat_runs
    done = 0

    for basin_id in basin_ids:
        for run_idx, seed in enumerate(random_seeds[:repeat_runs]):
            done += 1
            run_label = f"{basin_id}_run{run_idx + 1}" if repeat_runs > 1 else basin_id
            logger.info(f"[{done}/{total}] Calibrating {run_label} (seed={seed})")

            params = dict(algorithm_params or {})
            params["random_seed"] = seed

            output_dir = str(base_dir / f"{model_name}_{algorithm}_{run_label}")

            calib_result = calibrate_model(
                basin_ids=[basin_id],
                model_name=model_name,
                algorithm=algorithm,
                train_period=train_period,
                test_period=test_period,
                algorithm_params=params,
                output_dir=output_dir,
                _workspace=_workspace,
                _cfg=_cfg,
            )

            if not calib_result.get("success"):
                logger.warning(f"Calibration failed for {run_label}: {calib_result.get('error')}")
                failed.append({"basin_id": basin_id, "run": run_idx + 1, "error": calib_result.get("error")})
                continue

            # Evaluate on test period
            eval_result = evaluate_model(
                calibration_dir=calib_result["calibration_dir"],
                test_period=test_period,
                _workspace=_workspace,
                _cfg=_cfg,
            )

            metrics = eval_result.get("metrics", {}) if eval_result.get("success") else calib_result.get("metrics", {})
            nse = metrics.get("NSE", None)
            if nse is not None:
                all_nse.append(nse)

            results.append({
                "basin_id": basin_id,
                "run": run_idx + 1,
                "seed": seed,
                "NSE": nse,
                "RMSE": metrics.get("RMSE"),
                "KGE": metrics.get("KGE"),
                "calibration_dir": calib_result.get("calibration_dir", ""),
            })

    # Build summary statistics
    summary = {
        "total_runs": total,
        "successful": len(results),
        "failed": len(failed),
    }
    if all_nse:
        summary["NSE_mean"] = round(sum(all_nse) / len(all_nse), 4)
        summary["NSE_max"] = round(max(all_nse), 4)
        summary["NSE_min"] = round(min(all_nse), 4)
        if len(all_nse) > 1:
            import statistics
            summary["NSE_std"] = round(statistics.stdev(all_nse), 4)

    logger.info(f"Batch complete: {len(results)}/{total} successful, NSE mean={summary.get('NSE_mean', 'N/A')}")

    return {
        "results": results,
        "summary": summary,
        "failed": failed,
        "success": len(results) > 0,
    }
