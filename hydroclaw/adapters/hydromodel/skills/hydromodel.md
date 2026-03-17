# hydromodel Package Adapter

The `hydromodel` package handles all standard hydrological model calibration,
evaluation, and visualization tasks. It supports CAMELS-US/GB/BR/AUS datasets
and selfmade datasets via hydrodatasource.

## Supported models
- `gr4j`, `gr5j`, `gr6j` (GR family, 4-6 parameters)
- `xaj` (Xinanjiang model, 5 parameters)

## Supported algorithms
- `SCE_UA` (Shuffled Complex Evolution, recommended)
- `GA` (Genetic Algorithm)
- `scipy` (gradient-based, fast but may miss global optimum)

## Typical workflow

```
calibrate_model(basin_ids=["12025000"], model_name="gr4j", algorithm="SCE_UA")
  -> returns calibration_dir, best_params

evaluate_model(calibration_dir=<dir>, eval_period=train_period)
  -> returns NSE/KGE/RMSE for training period

evaluate_model(calibration_dir=<dir>)
  -> returns NSE/KGE/RMSE for test period (default)

visualize(calibration_dir=<dir>)
  -> generates hydrograph and scatter plots in <dir>/figures/
```

## Key parameter notes

### SCE_UA algorithm_params
- `rep`: total evaluations (default 750; use 1500+ for higher quality)
- `ngs`: number of complexes (default 200; rule of thumb: 2 x n_params)
- `kstop`: convergence criterion (default 10, rarely needs changing)

### data_source values
- `camels_us` (default), `camels_gb`, `camels_br`, `camels_aus`
- `selfmadehydrodataset` (or `selfmade`) for custom datasets

## Post-calibration evaluation
`calibrate_model` does NOT return NSE/KGE metrics directly.
Always call `evaluate_model` afterward to obtain performance metrics.

## Boundary check heuristic
If NSE < 0.4 after calibration, call
`read_file(<calibration_dir>/calibration_results.json)` to check if
parameter values are near their boundary limits. If so, consider expanding
the parameter range via `param_range_file` or using `llm_calibrate` for
adaptive range adjustment.
