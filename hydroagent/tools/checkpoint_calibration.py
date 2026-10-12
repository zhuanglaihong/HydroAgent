"""ReAct tools for a persistent basin experiment, with no nested LLM client."""
from __future__ import annotations

import json
import subprocess
import sys
import time
import uuid
from pathlib import Path


def _call(operation, arguments, workspace, cancelled):
    if operation == 'start':
        deadline = time.time()+arguments.get('cfg', {}).get('checkpoint_experiment', {}).get('wall_budget_seconds', 30)
    else:
        from hydroagent.research.session import study_path
        from hydroagent.research.budget import read_json
        deadline = read_json(study_path(workspace or '.', arguments['study_id'])/'session.json').get('deadline_at')
    payload = json.dumps({'workspace': str(Path(workspace or '.').resolve()), 'operation': operation, 'arguments': arguments})
    # Interpreter and module are code-owned, never supplied by the model.
    with subprocess.Popen([sys.executable, '-X', 'utf8', '-m', 'hydroagent.research.cli'], stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding='utf-8',
                          cwd=str(Path(__file__).resolve().parents[2])) as process:
        first = True
        while True:
            try:
                out, _ = process.communicate(input=payload if first else None, timeout=.25)
                break
            except subprocess.TimeoutExpired:
                first = False
                if (cancelled and cancelled()) or (deadline is not None and time.time() >= deadline):
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    return {'success': False, 'study_id': arguments.get('study_id', arguments.get('allocated_study_id')),
                            'error': 'Scientific subprocess cancelled/deadline; inspect and reconcile pending execution before resuming'}
        result = json.loads(out)
        return result


def start_calibration_study(basin_id: str, _workspace: Path | None = None, _cfg: dict | None = None,
                            _cancelled=None) -> dict:
    """Start ONE deployment-authorized basin study and its first search segment.

    Args:
        basin_id: Basin in checkpoint_experiment.basin_ids; budget comes only from deployment.
    """
    cfg = _cfg or {}
    # Send only scientific settings, not LLM credentials, into the executor.
    scientific = {k: cfg[k] for k in ('checkpoint_experiment', 'defaults', 'paths', 'algorithms') if k in cfg}
    return _call('start', {'basin_id': basin_id, 'cfg': scientific,
                           'allocated_study_id': str(uuid.uuid4())}, _workspace, _cancelled)


def inspect_calibration_study(study_id: str, _workspace: Path | None = None) -> dict:
    """Read persistent basin memory, population evidence and actual call ledger; no model calls.

    Args:
        study_id: Identifier returned by start_calibration_study.
    """
    from hydroagent.research.service import inspect_study
    return inspect_study(_workspace or Path('.'), study_id)


def advance_calibration_study(study_id: str, checkpoint_id: int, action: str, call_limit: int,
                              decision: dict, ranges: dict | None = None, settings: dict | None = None,
                              keep_count: int | None = None, _workspace: Path | None = None, _cancelled=None) -> dict:
    """Execute one Agent decision: continue, warm_restart, cold_restart or stop.

    Args:
        study_id: Existing basin study; never creates a new budget.
        checkpoint_id: Exact revision returned by inspect; stale decisions are rejected.
        action: continue preserves state; warm_restart retains candidates; cold_restart resamples; stop freezes.
        call_limit: New search call TARGET; safe-step checkpoints may overshoot by <=2, global cap never does. Use 0 for stop.
        decision: Strings evidence, hypothesis, prediction, falsification submitted BEFORE execution.
        ranges: Optional complete ordered physical bounds; restart only, inside frozen outer bounds.
        settings: Optional ngs/kstop/peps/pcento/random_seed changes; restart only; rep is unsupported.
        keep_count: Required for warm_restart; actual retained candidate IDs are returned in memory.
    """
    return _call('advance', {'study_id': study_id, 'checkpoint_id': checkpoint_id, 'action': action,
                            'call_limit': call_limit, 'decision': decision, 'ranges': ranges,
                            'settings': settings, 'keep_count': keep_count}, _workspace, _cancelled)


def probe_calibration_study(study_id: str, checkpoint_id: int, parameters: dict, prediction: str,
                            _workspace: Path | None = None, _cancelled=None) -> dict:
    """Run one separately charged CALIBRATION-only local probe; never promotes a search champion.

    Args:
        study_id: Existing study.
        checkpoint_id: Current revision.
        parameters: Complete physical vector within current search bounds.
        prediction: Prediction recorded before the simulation; not proof of global sensitivity.
    """
    return _call('probe', {'study_id': study_id, 'checkpoint_id': checkpoint_id,
                          'parameters': parameters, 'prediction': prediction}, _workspace, _cancelled)


def finalize_calibration_study(study_id: str, _workspace: Path | None = None, _cancelled=None) -> dict:
    """After decisions are frozen, evaluate the SAME search champion on calibration and held-out periods.

    Args:
        study_id: Terminal study. Requires two reserved auxiliary calls; test results cannot guide another search.
    """
    return _call('finalize', {'study_id': study_id}, _workspace, _cancelled)
