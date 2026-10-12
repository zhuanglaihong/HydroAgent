"""Calibration-only signatures from the saved champion; no extra model runs."""
from pathlib import Path
import numpy as np


def champion_diagnostics(directory, champion):
    path = Path(directory)/'champion_series.npz'
    if champion is None or not path.exists():
        return {'available': False}
    with np.load(path, allow_pickle=False) as data:
        if int(data['call_id']) != champion['call_id']:
            return {'available': False, 'reason': 'Series does not belong to the recorded champion'}
        obs, sim = data['obs'], data['sim']
        forcing, dates = data['forcing'], data['dates']
    result = {'available': True, 'role': 'calibration', 'candidate_call_id': champion['call_id'],
              'PBIAS': champion['PBIAS'], 'NSE': champion['NSE'],
              'continuity_balance': 'Unavailable: outlet bias is not audited P-ET-dS closure',
              'low_flow': [{'exceedance_probability': p, 'observed': float(np.quantile(obs, 1-p)),
                            'simulated': float(np.quantile(sim, 1-p))} for p in (.5, .9, .95)]}
    if len(dates) == len(obs):
        month = np.array([str(d)[5:7] for d in dates])
        result['monthly_bias'] = [{'month': m, 'PBIAS': float(100*(sim[month==m].sum()-obs[month==m].sum())/obs[month==m].sum())
                                  if obs[month==m].sum() > 0 else None} for m in sorted(set(month))]
    result['high_flow_windows'] = []
    threshold = float(np.quantile(obs, .95))
    chosen = []
    for i in np.argsort(-obs):
        i = int(i)
        if i < 7 or i+7 >= len(obs) or obs[i] < threshold or any(abs(i-j) <= 14 for j in chosen):
            continue
        if obs[i] < obs[i-1] or obs[i] < obs[i+1]:
            continue
        chosen.append(i)
        a, b = i-7, i+8
        peak = a+int(np.argmax(sim[a:b]))
        result['high_flow_windows'].append({'observed_peak_index': i, 'peak_day_error': peak-i,
            'peak_bias_percent': float(100*(sim[peak]-obs[i])/obs[i]) if obs[i] > 0 else None})
        if len(chosen) == 5:
            break
    if forcing.shape == (len(obs), 2):
        result['paired_precipitation_sum'] = float(forcing[:, 0].sum())
        result['recession_segments'] = []
        dry = forcing[:, 0] <= .1
        start = None
        for i in range(3, len(obs)+1):
            good = i < len(obs) and dry[i-2:i+1].all() and obs[i-1] >= obs[i] > 0 and sim[i-1:i+1].min() > 0
            if good and start is None:
                start = i
            elif not good and start is not None:
                if i-start >= 4:
                    o = float(np.mean(np.log(obs[start-1:i-1]/obs[start:i])))
                    s = float(np.mean(np.log(sim[start-1:i-1]/sim[start:i])))
                    result['recession_segments'].append({'start_index': start-1, 'end_index': i-1,
                                                         'observed_log_decay': o, 'simulated_log_decay': s})
                start = None
        result['recession_segments'] = sorted(result['recession_segments'], key=lambda s: -(s['end_index']-s['start_index']))[:5]
    result['caveat'] = 'Daily high-flow and dry-weather recession proxies; not direct groundwater observations or global sensitivity.'
    return result
