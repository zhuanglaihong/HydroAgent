# Calibration Policy

**Required order for every calibration task:**
1. validate_basin — confirm data availability
2. calibrate_model — obtain parameters
3. evaluate_model(train_period) — training performance
4. evaluate_model(test_period) — generalization performance

**Parameter boundaries:**
- If a parameter hits its boundary (within 5% of limit): explain why before expanding range
- Boundary hit + NSE < 0.65: recommend llm_calibrate or wider param_range_file
- Repeated boundary hits across runs: consider model-basin mismatch, not just range expansion

**Iteration limits:**
- If NSE shows no improvement across 3+ retry attempts: stop and report, do not loop indefinitely
- If repeated retries fail: consider switching model (GR4J -> GR5J, XAJ -> HBV) before reruns

**Reporting:**
- Train NSE acceptable but test NSE poor: explicitly report "overfitting / poor generalization"
  Do NOT claim the calibration succeeded
- A completed calibrate_model call is NOT a completed calibration task
  The task is complete only when both train and test metrics are obtained
