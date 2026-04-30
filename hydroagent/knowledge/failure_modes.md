# Hydrology Calibration Failure Modes

Use this reference when diagnosing unexpected results or tool errors.
Match symptoms to a failure class, then follow the recovery steps.

---

## Class A: Data Failures

### A1 — Data missing / basin not found
Symptom: validate_basin returns valid=False; calibrate_model reports file not found
Diagnosis: Check basin ID format (must be 8 digits); verify DATASET_DIR points to CAMELS_US parent
Recovery: Correct basin ID or fix configs/definitions_private.py DATASET_DIR

### A2 — Insufficient time range
Symptom: calibrate_model succeeds but evaluate_model returns NaN or very short period
Diagnosis: Check data coverage vs. requested train/test period
Recovery: Shorten period or choose a basin with longer record

### A3 — Variable mismatch / incomplete forcing
Symptom: NSE = -999 or model output all zeros
Diagnosis: Read calibration_results.json; check if all required forcings are present (prcp, tmax, tmin, dayl, srad, swe, vp)
Recovery: Use validate_basin to confirm variable list; report missing variables to user

### A4 — Unit error
Symptom: NSE << -1; simulated flow order-of-magnitude different from observed
Diagnosis: Check if precipitation is in mm vs. m, or flow in m3/s vs. mm/d
Recovery: Report discrepancy; recommend user check unit conventions in their data

---

## Class B: Workflow Failures

### B1 — Calibration run but not evaluated
Symptom: calibrate_model returned success but no metrics available
Diagnosis: evaluate_model was not called after calibration
Recovery: Call evaluate_model(calibration_dir, eval_period=train_period) then test_period

### B2 — Result directory exists but output incomplete
Symptom: evaluate_model fails with "config not found"; calibration_dir appears valid
Diagnosis: inspect_dir(calibration_dir) — check if calibration_results.json and calibration_config.yaml exist
Recovery: If files missing, re-run calibrate_model; if config exists but metrics file missing, re-run evaluate_model

### B3 — Path reference error
Symptom: read_file fails; inspect_dir shows empty directory
Diagnosis: Agent used a constructed path instead of the tool-returned calibration_dir
Recovery: Use the exact calibration_dir value returned by calibrate_model; do not construct paths manually

---

## Class C: Parameter Failures

### C1 — Parameter hits boundary
Symptom: Best parameter within 5% of its declared bound (e.g., x1=1980 when max=2000)
Diagnosis: Optimizer hit wall; true optimum may lie outside current range
Recovery: Try llm_calibrate to iteratively expand range; or provide a wider param_range_file

### C2 — Unreasonable parameter range
Symptom: NSE poor despite calibration completing; parameters at extreme values
Diagnosis: Check if param_range_file covers the physically meaningful range for this climate type
Recovery: Compare with knowledge/model_parameters.md; adjust range to match basin's climate regime

### C3 — Optimization stagnation
Symptom: NSE unchanged across 3+ retry attempts with the same algorithm
Diagnosis: Algorithm converged to local minimum
Recovery: Switch algorithm (SCE_UA -> GA or scipy); or increase population size (ngs parameter)

---

## Class D: Model-Basin Mismatch

### D1 — Model structurally unsuitable
Symptom: NSE consistently < 0.4 despite varied parameter ranges and algorithms
Diagnosis: The model's runoff generation mechanism does not match basin's dominant process
Recovery: Try alternative model (GR4J -> XAJ for humid basins; GR4J -> GR5J for semiarid)
Reference: knowledge/model_parameters.md for climate-model matching guidance

### D2 — Train-test split failure (overfitting)
Symptom: Train NSE >= 0.75 but test NSE < 0.5
Diagnosis: Model overfits training period; may indicate non-stationarity or data quality issue
Recovery: Report explicitly as "poor generalization"; recommend longer training period or regularization

### D3 — Numerical divergence
Symptom: NSE = NaN or -inf; tool returns error during model run
Diagnosis: Parameter combination caused numerical instability (e.g., x4 near 0 for GR4J)
Recovery: Narrow parameter range to avoid degenerate values; check calibration_results.json for which iteration failed
