"""Observable summaries; thresholds are proposed policy values, not standards."""
import numpy as np


def summary_population(engine, backend, outer):
    x, values = engine.population()
    valid = np.isfinite(values)
    x, values = x[valid], values[valid]
    if not len(x):
        return {'evaluated_population_size': 0}
    physical = np.array([list(backend.physical(row).values()) for row in x])
    low = np.array([outer[k][0] for k in backend.names])
    width = np.array([outer[k][1]-outer[k][0] for k in backend.names])
    z = (physical-low)/width
    spreads = np.quantile(z, .9, axis=0)-np.quantile(z, .1, axis=0)
    distance = float(np.sqrt(np.mean((z-z.mean(axis=0))**2)))
    small = int(np.sum(spreads <= .05))
    elite = x[np.argsort(values)[:max(1, int(np.ceil(.2*len(x))))]]
    return {'evaluated_population_size': len(x), 'geometric_range_current_bounds': engine.gnrng,
            'rms_spread_fixed_outer_bounds': distance,
            'p90_minus_p10_fixed_outer_bounds': dict(zip(backend.names, spreads.tolist())),
            'small_spread_dimensions': small,
            'concentrated_candidate_flag': small >= int(np.ceil(.8*len(spreads))) and distance <= .03,
            'boundary_fraction_elite': {k: {'lower': float(np.mean(elite[:, j] <= .05)),
                                          'upper': float(np.mean(elite[:, j] >= .95))} for j, k in enumerate(backend.names)},
            'threshold_status': 'development candidates: 5% per-axis, 3% RMS; not universal hydrological thresholds'}


def progress(records, window=500):
    completed = [r for r in records if r['event'] == 'completed' and r['category'] == 'search']
    started = sum(r['event'] == 'started' and r['category'] == 'search' for r in records)
    # use persisted SEARCH index, not total calls including probes
    result = []
    for end in (started-window, started):
        if end < window:
            continue
        before = [r['objective'] for r in completed if r['search_index'] <= end-window]
        after = [r['objective'] for r in completed if r['search_index'] <= end]
        if before and after and min(before) > 0:
            result.append({'end_search_call': end, 'window_calls': window,
                           'best_before': min(before), 'best_after': min(after),
                           'improvement_percent': 100*(min(before)-min(after))/min(before)})
    return {'global_champion_windows': result,
            'caveat': 'After intervention, global plateau alone is not evidence that the new phase is stagnant.'}
