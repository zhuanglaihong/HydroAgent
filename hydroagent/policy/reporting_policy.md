# Reporting Policy

**Every calibration report must include:**
- Basin ID and model name
- Result directory path (calibration_dir)
- Calibrated parameter values
- Training period NSE / KGE (and period dates)
- Test period NSE / KGE (and period dates)

**Clarity rules:**
- Clearly label which values come from tool output vs. your own interpretation
- If a metric is unavailable, state why (e.g., "evaluate_model not yet run")
- Quality labels: NSE >= 0.75 Excellent / >= 0.65 Good / >= 0.50 Fair / < 0.50 Poor

**On failure:**
- State the failure type (data / workflow / parameter / model — see failure_modes.md)
- Include the specific error or symptom observed
- Provide at least one concrete next-step recommendation
- Do NOT output only "failed" without explanation
