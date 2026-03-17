"""
Author: HydroClaw Team
Date: 2026-02-08
Description: Model calibration tool - routes to the appropriate PackageAdapter.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def calibrate_model(
    basin_ids: list[str],
    model_name: str = "xaj",
    algorithm: str = "SCE_UA",
    train_period: list[str] | None = None,
    test_period: list[str] | None = None,
    algorithm_params: dict | None = None,
    param_range_file: str | None = None,
    output_dir: str | None = None,
    data_source: str = "camels_us",
    _workspace: Path | None = None,
    _cfg: dict | None = None,
    _ui=None,
    _round_label: str = "",
) -> dict:
    """Calibrate a hydrological model using the specified algorithm.

    Calls the appropriate package adapter (e.g. hydromodel) for parameter
    optimization (SCE-UA, GA, scipy). Results are saved to the output directory.

    Args:
        basin_ids: CAMELS basin ID list, e.g. ["12025000"]
        model_name: Model name ("gr4j", "xaj", "gr5j", "gr6j")
        algorithm: Optimization algorithm ("SCE_UA", "GA", "scipy")
        train_period: Training period ["YYYY-MM-DD", "YYYY-MM-DD"]
        test_period: Testing period ["YYYY-MM-DD", "YYYY-MM-DD"]
        algorithm_params: Dict of algorithm parameter overrides. Must be a dict, NOT a string.
            Pass None to use project defaults (recommended for most cases).
            SCE_UA keys: rep (total evaluations), ngs (complexes), kstop (convergence steps).
              e.g. {"rep": 200, "ngs": 50} for a quick test, {"rep": 1500, "ngs": 300} for
              high-quality results. Default: rep=750, ngs=200.
            GA keys: pop_size, n_generations. e.g. {"pop_size": 20, "n_generations": 10}.
            scipy keys: method ("SLSQP"/"L-BFGS-B"), max_iterations. e.g. {"method": "SLSQP", "max_iterations": 30}.
        param_range_file: Path to custom parameter range YAML file for boundary expansion
        output_dir: Output directory for results
        data_source: Dataset type ("camels_us", "camels_gb", "selfmade", ...)

    Returns:
        {"best_params": {...}, "calibration_dir": "...", "output_files": [...]}
    """
    from hydroclaw.adapters import get_adapter

    adapter = get_adapter(data_source, model_name)
    return adapter.execute("calibrate",
        workspace=_workspace or Path("."),
        model_name=model_name,
        algorithm=algorithm,
        basin_ids=basin_ids,
        train_period=train_period,
        test_period=test_period,
        algorithm_params=algorithm_params,
        param_range_file=param_range_file,
        output_dir=output_dir,
        _cfg=_cfg,
        _ui=_ui,
        _round_label=_round_label,
    )


calibrate_model.__agent_hint__ = (
    "Returns calibration_dir and best_params -- NO metrics (NSE/KGE). "
    "Must call evaluate_model(calibration_dir=...) separately to get metrics. "
    "If NSE is low, check if params hit boundaries via read_file(calibration_results.json)."
)
