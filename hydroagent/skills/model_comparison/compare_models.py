"""
Author: HydroAgent Team
Date: 2026-03-06
Description: Model comparison tool - compares multiple models on the same basin(s).
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def compare_models(
    basin_ids: list[str],
    model_names: list[str],
    algorithm: str = "SCE_UA",
    train_period: list[str] | None = None,
    test_period: list[str] | None = None,
    algorithm_params: dict | None = None,
    output_base_dir: str | None = None,
    _workspace: Path | None = None,
    _cfg: dict | None = None,
) -> dict:
    """Compare multiple hydrological models on the same basin(s).

    Runs calibrate_model + evaluate_model for each model-basin combination and
    returns a comparison table sorted by NSE descending.

    Args:
        basin_ids: CAMELS basin ID list
        model_names: List of model names to compare, e.g. ["gr4j", "xaj", "gr5j"]
        algorithm: Optimization algorithm ("SCE_UA", "GA", "scipy")
        train_period: Training period ["YYYY-MM-DD", "YYYY-MM-DD"]
        test_period: Testing period ["YYYY-MM-DD", "YYYY-MM-DD"]
        algorithm_params: Algorithm parameter overrides
        output_base_dir: Base directory for all output subdirectories

    Returns:
        {"comparison": [...], "best_model": str, "summary_table": str, "success": bool}
    """
    from hydroagent.skills.calibration.calibrate import calibrate_model
    from hydroagent.skills.evaluation.evaluate import evaluate_model

    base_dir = Path(output_base_dir) if output_base_dir else (_workspace or Path("results"))
    base_dir.mkdir(parents=True, exist_ok=True)

    comparison = []
    total = len(model_names) * len(basin_ids)
    done = 0

    for model_name in model_names:
        for basin_id in basin_ids:
            done += 1
            label = f"{model_name}/{basin_id}"
            logger.info(f"[{done}/{total}] Calibrating {label}")

            output_dir = str(base_dir / f"{model_name}_{algorithm}_{basin_id}")

            calib_result = calibrate_model(
                basin_ids=[basin_id],
                model_name=model_name,
                algorithm=algorithm,
                train_period=train_period,
                test_period=test_period,
                algorithm_params=algorithm_params,
                output_dir=output_dir,
                _workspace=_workspace,
                _cfg=_cfg,
            )

            if not calib_result.get("success"):
                logger.warning(f"Calibration failed for {label}: {calib_result.get('error')}")
                comparison.append({
                    "model": model_name,
                    "basin_id": basin_id,
                    "error": calib_result.get("error"),
                })
                continue

            # Evaluate on test period
            eval_result = evaluate_model(
                calibration_dir=calib_result["calibration_dir"],
                test_period=test_period,
                _workspace=_workspace,
                _cfg=_cfg,
            )

            metrics = eval_result.get("metrics", {}) if eval_result.get("success") else calib_result.get("metrics", {})

            comparison.append({
                "model": model_name,
                "basin_id": basin_id,
                "algorithm": algorithm,
                "NSE": metrics.get("NSE"),
                "RMSE": metrics.get("RMSE"),
                "KGE": metrics.get("KGE"),
                "best_params": calib_result.get("best_params", {}),
                "calibration_dir": calib_result.get("calibration_dir", ""),
            })

    # Sort by NSE descending (None last)
    comparison.sort(
        key=lambda x: x.get("NSE") if x.get("NSE") is not None else -999,
        reverse=True,
    )

    # Find best model overall
    best_model = None
    best_nse = -999
    for row in comparison:
        nse = row.get("NSE")
        if nse is not None and nse > best_nse:
            best_nse = nse
            best_model = row["model"]

    # Build markdown summary table
    summary_table = _build_table(comparison)

    logger.info(f"Comparison complete: {len(comparison)} runs, best={best_model} (NSE={best_nse:.4f})")

    return {
        "comparison": comparison,
        "best_model": best_model,
        "best_nse": best_nse,
        "summary_table": summary_table,
        "success": any(r.get("NSE") is not None for r in comparison),
    }


compare_models.__agent_hint__ = (
    "Calibrates AND evaluates multiple models on the same basin. "
    "Returns best_model, best_nse, and per-model comparison table. "
    "Use this instead of calling calibrate_model + evaluate_model in a loop."
)


def _build_table(comparison: list[dict]) -> str:
    """Build a markdown comparison table."""
    header = "| 模型 | 流域 | 算法 | NSE | RMSE | KGE |"
    sep = "|------|------|------|-----|------|-----|"
    rows = [header, sep]
    for r in comparison:
        nse = f"{r['NSE']:.4f}" if r.get("NSE") is not None else "N/A"
        rmse = f"{r['RMSE']:.4f}" if r.get("RMSE") is not None else "N/A"
        kge = f"{r['KGE']:.4f}" if r.get("KGE") is not None else "N/A"
        rows.append(f"| {r['model']} | {r['basin_id']} | {r.get('algorithm', 'N/A')} | {nse} | {rmse} | {kge} |")
    return "\n".join(rows)
