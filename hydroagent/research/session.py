"""Durable basin session shared by baseline, rules and ReAct tools."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import random
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import spotpy

from .backend import HydromodelBackend
from .budget import Ledger, ExecutionStop, atomic_json, read_json
from .checkpoint import random_snapshot, restore_random
from .evidence import progress, summary_population
from .diagnostics import champion_diagnostics
from .sceua_runner import CheckpointSCEUA


def driver_fingerprint():
    digest = hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob('*.py')):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def study_path(workspace, study_id):
    if str(uuid.UUID(study_id)) != study_id:
        raise ValueError('Invalid study id')
    root = Path(workspace).resolve() / 'result' / 'checkpoint_studies'
    return root / study_id


@contextmanager
def owned_lock(directory):
    path = directory / 'execution.lock'
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        path.unlink()


def validate_settings(settings):
    if set(settings) != {'ngs', 'kstop', 'peps', 'pcento', 'random_seed'}:
        raise ValueError('Only ngs/kstop/peps/pcento/random_seed are supported; rep is not the external budget')
    for key, lo, hi in (('ngs', 2, 50), ('kstop', 2, 200), ('random_seed', 0, 2**31-1)):
        if type(settings[key]) is not int or not lo <= settings[key] <= hi:
            raise ValueError(f'Invalid {key}')
    for key in ('peps', 'pcento'):
        if isinstance(settings[key], bool) or not np.isfinite(settings[key]) or not 0 < settings[key] <= 1:
            raise ValueError(f'Invalid {key}')


def validate_ranges(ranges, outer):
    if list(ranges) != list(outer):
        raise ValueError('All parameter names in their original order are required')
    for k, pair in ranges.items():
        if not isinstance(pair, list) or len(pair) != 2 or not all(type(v) in (float, int) and np.isfinite(v) for v in pair):
            raise ValueError(f'Invalid {k} bounds')
        if not outer[k][0] <= pair[0] < pair[1] <= outer[k][1]:
            raise ValueError(f'{k} outside frozen outer bounds')


class CandidateSetup:
    def __init__(self, backend, ledger, cancelled=lambda: False, deadline_at=None):
        self.backend, self.ledger, self.cancelled = backend, ledger, cancelled
        self.params = backend.parameters
        self.deadline_at = deadline_at

    def parameters(self):
        return spotpy.parameter.generate(self.params)

    def evaluation(self):
        return self.backend.observations

    def evaluate(self, normalized, category='search'):
        if self.cancelled():
            raise ExecutionStop('cancelled')
        if self.deadline_at is not None and time.time() >= self.deadline_at:
            raise ExecutionStop('wall_deadline')
        physical = self.backend.physical(normalized)
        call_id = self.ledger.start(category, physical)
        before = time.monotonic()
        try:
            q = self.backend.simulate(normalized)
            value = self.backend.score(q)
            if not np.isfinite(value):
                raise ValueError('Nonfinite score')
            obs = np.asarray(self.backend.observations).ravel()
            sim = np.asarray(q).ravel()
            nse = float(1-np.sum((sim-obs)**2)/np.sum((obs-obs.mean())**2)) if np.var(obs) > 0 else None
            pbias = float(100*(sim.sum()-obs.sum())/obs.sum()) if obs.sum() > 0 else None
            if category == 'search' and (self.ledger.best_search is None or value < self.ledger.best_search['objective']):
                temp = self.ledger.directory/'champion_series.tmp'
                forcing = np.asarray(getattr(self.backend, 'scored_forcing', np.empty((0, 2))))
                dates = np.asarray(getattr(self.backend, 'dates', []), dtype='U10')
                with temp.open('wb') as stream:
                    np.savez_compressed(stream, call_id=call_id, obs=obs, sim=sim, forcing=forcing, dates=dates)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temp, self.ledger.directory/'champion_series.npz')
            self.ledger.complete(call_id, category, value, physical, NSE=nse, PBIAS=pbias,
                                 eligible=self.deadline_at is None or time.time() <= self.deadline_at,
                                 search_index=self.ledger.counts()['search']['started'], seconds=time.monotonic()-before)
            return q, value
        except Exception as error:
            self.ledger.fail(call_id, category, error)
            raise

    def simulation(self, vector):
        return self.evaluate(np.asarray(list(vector)))[0]

    def objectivefunction(self, simulation, evaluation, params=None):
        return self.backend.score(simulation)


class Session:
    def __init__(self, directory, backend_factory=HydromodelBackend, cancelled=lambda: False):
        self.directory = Path(directory)
        self.document = read_json(self.directory / 'session.json')
        if self.document.get('driver_fingerprint') != driver_fingerprint():
            raise ValueError('Research driver changed; revalidate before reusing this checkpoint')
        if (self.directory / 'pending_decision.json').exists():
            raise RuntimeError('Interrupted submitted decision requires reconciliation; automatic replay forbidden')
        d = self.document
        self.ledger = Ledger(self.directory, d['search_limit'], d['auxiliary_limit'])
        total = sum(v['started'] for v in self.ledger.counts().values())
        if total != d['checkpoint_started_calls']:
            raise RuntimeError('Calls exist beyond the committed checkpoint; reconcile interruption, do not replay')
        self.backend = backend_factory(d['config'], d['ranges'], self.directory)
        if self.backend.signature != d['scientific_signature']:
            raise ValueError('Scientific backend/data changed; old state and cached scores cannot be reused')
        self.setup = CandidateSetup(self.backend, self.ledger, cancelled, d.get('deadline_at'))
        self.engine = CheckpointSCEUA(self.setup, d['settings'], d['engine'])

    @classmethod
    def create(cls, directory, config, search_limit, auxiliary_limit, settings,
               outer_ranges, backend_factory=HydromodelBackend, arm='A', wall_budget_seconds=None):
        if type(search_limit) is not int or search_limit <= 0 or type(auxiliary_limit) is not int or auxiliary_limit < 0:
            raise ValueError('Explicit positive search budget and nonnegative auxiliary budget required')
        validate_settings(settings)
        validate_ranges(outer_ranges, outer_ranges)
        if search_limit < (2*len(outer_ranges)+1)*settings['ngs']:
            raise ValueError('Budget cannot initialize the whole population')
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=False)
        started_at = time.time()
        deadline_at = started_at + wall_budget_seconds if wall_budget_seconds is not None else None
        backend = backend_factory(config, outer_ranges, directory)
        ledger = Ledger(directory, search_limit, auxiliary_limit)
        engine = CheckpointSCEUA(CandidateSetup(backend, ledger, deadline_at=deadline_at), settings)
        document = {'schema_version': 1, 'study_id': directory.name, 'basin': config['data_cfgs']['basin_ids'][0],
                    'arm': arm, 'config': config, 'search_limit': search_limit, 'auxiliary_limit': auxiliary_limit,
                    'outer_ranges': outer_ranges, 'ranges': copy.deepcopy(outer_ranges), 'settings': settings,
                    'scientific_signature': backend.signature, 'runtime': getattr(backend, 'runtime', {}),
                    'revision': 0, 'phase': 1, 'phase_start_search_call': 0, 'checkpoint_started_calls': 0,
                    'engine': engine.snapshot(), 'history': [], 'terminal': False, 'started_at': started_at,
                    'deadline_at': deadline_at, 'driver_fingerprint': driver_fingerprint()}
        atomic_json(directory / 'session.json', document)
        session = object.__new__(cls)
        session.directory, session.document = directory, document
        session.backend, session.ledger, session.engine = backend, ledger, engine
        session.setup = engine.setup
        return session

    def summary(self):
        complete = [r for r in self.ledger.records if r['event'] == 'completed' and r['category'] == 'search' and r.get('eligible', True)]
        champion = min(complete, key=lambda r: r['objective']) if complete else None
        phase_records = [r for r in complete if r['search_index'] > self.document['phase_start_search_call']]
        phase_best = min(phase_records, key=lambda r: r['objective']) if phase_records else None
        return {'success': not str(self.engine.reason).startswith('scientific_error'),
                'scientific_completed': (self.directory/'final.json').exists(),
                'study_id': self.document['study_id'], 'checkpoint_id': self.document['revision'],
                'basin': self.document['basin'], 'arm': self.document['arm'], 'terminal': self.document['terminal'],
                'stop_reason': self.engine.reason, 'search_remaining': self.ledger.remaining_search(),
                'calls': self.ledger.counts(), 'optimizer_counter': self.engine.optimizer_counter,
                'champion': champion, 'phase_best': phase_best,
                'hydrological_diagnostics': champion_diagnostics(self.directory, champion),
                'population': summary_population(self.engine, self.backend, self.document['outer_ranges']),
                'progress': progress(self.ledger.records), 'ranges': self.document['ranges'],
                'settings': self.document['settings'], 'runtime': self.document['runtime'],
                'experiment_memory': self.document['history'],
                'artifacts': {'session': str(self.directory/'session.json'), 'calls': str(self.ledger.path)},
                'interpretation': 'Checkpoint targets are soft (<=2-call overshoot); global search cap is hard. Convergence is not proof of global optimality.'}

    def save(self):
        self.document['engine'] = self.engine.snapshot()
        self.document['checkpoint_started_calls'] = sum(v['started'] for v in self.ledger.counts().values())
        self.document['revision'] += 1
        atomic_json(self.directory / 'session.json', self.document)
        result = self.summary()
        atomic_json(self.directory / 'summary.json', result)
        return result

    def advance(self, checkpoint_id, action, call_limit, decision, ranges=None, settings=None, keep_count=None):
        if self.document['terminal']:
            raise ValueError('Study is terminal')
        if checkpoint_id != self.document['revision']:
            raise ValueError('Stale checkpoint; inspect current state before another decision')
        if action not in ('continue', 'warm_restart', 'cold_restart', 'stop'):
            raise ValueError('Unsupported action')
        for key in ('evidence', 'hypothesis', 'prediction', 'falsification'):
            if not isinstance(decision.get(key), str) or not decision[key].strip():
                raise ValueError(f'Decision requires {key}')
        if action == 'stop':
            if call_limit != 0:
                raise ValueError('Stop must request zero further calls')
            if ranges is not None or settings is not None or keep_count is not None:
                raise ValueError('Stop cannot change controls')
            self.engine.reason = 'agent_stop'
            self.document['terminal'] = True
        else:
            if type(call_limit) is not int or not 0 < call_limit <= self.ledger.remaining_search():
                raise ValueError('Next call target must fit the remaining search grant')
            new_ranges = copy.deepcopy(ranges or self.document['ranges'])
            new_settings = {**self.document['settings'], **(settings or {})}
            validate_ranges(new_ranges, self.document['outer_ranges'])
            validate_settings(new_settings)
            if action == 'continue' and (new_ranges != self.document['ranges'] or new_settings != self.document['settings'] or keep_count is not None):
                raise ValueError('Continue preserves all controls; changed controls require explicit restart')
            if action == 'continue' and self.engine.reason:
                raise ValueError('Algorithm converged; choose an explicit restart or stop')
            size = (2*len(new_ranges)+1)*new_settings['ngs']
            if action != 'continue':
                if action == 'cold_restart' and call_limit < size:
                    raise ValueError('Cold segment target is below initialization cost')
                if action == 'warm_restart' and (type(keep_count) is not int or not 1 <= keep_count < size):
                    raise ValueError('Warm restart requires an explicit keep_count below population size')
        record = {'checkpoint': checkpoint_id, 'action': action, 'requested_call_target': call_limit,
                  'decision': decision, 'calls_before': self.ledger.counts(), 'phase_before': self.document['phase'],
                  'champion_before': self.ledger.best_search}
        # A committed intent is durable before science; interrupted intents are not replayed.
        atomic_json(self.directory / 'pending_decision.json', record)
        try:
            if action not in ('continue', 'stop'):
                self._restart(new_ranges, new_settings, action, keep_count, call_limit, record)
            if action != 'stop':
                before = record['calls_before']['search']['started']
                self.engine.advance(min(before+call_limit, self.document['search_limit']))
            if self.engine.reason in ('search_budget_exhausted', 'cancelled', 'wall_deadline'):
                self.document['terminal'] = True
        except ExecutionStop as error:
            self.engine.reason = str(error)
            self.document['terminal'] = True
        except Exception as error:
            self.engine.reason = f'scientific_error:{type(error).__name__}'
            self.document['terminal'] = True
            record['error'] = str(error)
        record.update(calls_after=self.ledger.counts(), reason=self.engine.reason,
                      effective_ranges=self.document['ranges'], effective_settings=self.document['settings'],
                      champion_after=self.ledger.best_search,
                      actual_champion_improvement=(record['champion_before']['objective']-self.ledger.best_search['objective'])
                       if record['champion_before'] and self.ledger.best_search else None)
        self.document['history'].append(record)
        result = self.save()
        (self.directory/'pending_decision.json').unlink()
        return result

    def _restart(self, ranges, settings, action, keep_count, call_limit, record):
        backend = type(self.backend)(self.document['config'], ranges, self.directory)
        if backend.signature != self.document['scientific_signature']:
            raise ValueError('Restart changed the scientific problem')
        self.backend = backend
        self.setup = CandidateSetup(backend, self.ledger, self.setup.cancelled, self.document.get('deadline_at'))
        self.engine = CheckpointSCEUA(self.setup, settings)
        self.document.update(ranges=ranges, settings=settings, phase=self.document['phase']+1,
                             phase_start_search_call=record['calls_before']['search']['started'])
        if action == 'warm_restart':
            pool = [r for r in self.ledger.records if r['event'] == 'completed' and r['category'] == 'search' and r.get('eligible', True)
                    and all(ranges[k][0] <= r['parameters'][k] <= ranges[k][1] for k in ranges)]
            pool.sort(key=lambda r: (r['objective'], r['call_id']))
            unique = {}
            for r in pool:
                unique.setdefault(tuple(r['parameters'].values()), r)
            pool = list(unique.values())[:max(keep_count*3, keep_count)]
            chosen = []
            if pool:
                chosen.append(pool.pop(0))
            while pool and len(chosen) < keep_count:
                next_record = max(pool, key=lambda r: min(np.linalg.norm(backend.normalize(r['parameters'])-backend.normalize(c['parameters'])) for c in chosen))
                chosen.append(next_record)
                pool.remove(next_record)
            size = len(self.engine.x)
            if call_limit < size-len(chosen):
                raise ValueError('Warm segment target is below actual fill cost')
            points = [backend.normalize(r['parameters']) for r in chosen]
            scores = [r['objective'] for r in chosen]
            record['retained_call_ids'] = [r['call_id'] for r in chosen]
            for row in self.engine.x[:size-len(chosen)]:
                q, score = self.setup.evaluate(row)
                points.append(row.copy())
                scores.append(score)
            self.engine.inject_population(points, scores)

    def probe(self, checkpoint_id, physical, prediction):
        if checkpoint_id != self.document['revision'] or self.document['terminal']:
            raise ValueError('Stale or terminal checkpoint')
        if not prediction.strip():
            raise ValueError('Record a prediction before running the probe')
        if self.document['auxiliary_limit']-sum(v['started'] for k, v in self.ledger.counts().items() if k != 'search') <= 2:
            raise ValueError('Two auxiliary calls are reserved for final evaluation')
        validate_ranges(self.document['ranges'], self.document['outer_ranges'])
        if set(physical) != set(self.backend.names) or not all(self.document['outer_ranges'][k][0] <= physical[k] <= self.document['outer_ranges'][k][1] for k in physical):
            raise ValueError('Probe requires a complete legal physical parameter vector')
        # Restrict to current bounds because this backend's normalized interface uses them.
        if not all(self.document['ranges'][k][0] <= physical[k] <= self.document['ranges'][k][1] for k in physical):
            raise ValueError('Probe outside current bounds is unsupported; no silent clipping')
        rng = random_snapshot()
        atomic_json(self.directory / 'pending_decision.json', {'action': 'probe', 'prediction': prediction})
        try:
            q, value = self.setup.evaluate(self.backend.normalize(physical), 'probe')
        except Exception as error:
            restore_random(rng)
            self.document['history'].append({'action': 'probe', 'prediction': prediction, 'error': str(error)})
            result = self.save()
            (self.directory/'pending_decision.json').unlink()
            raise
        finally:
            restore_random(rng)
        self.document['history'].append({'action': 'probe', 'prediction': prediction, 'parameters': physical,
                                        'objective': value, 'call_id': self.ledger.records[-1]['call_id']})
        result = self.save()
        (self.directory/'pending_decision.json').unlink()
        return result

    def finalize(self):
        if not self.document['terminal']:
            raise ValueError('Stop/freeze decisions before reading the held-out period')
        if (self.directory/'final.json').exists():
            return read_json(self.directory/'final.json')
        champion = self.summary()['champion']
        if champion is None:
            raise ValueError('No valid search candidate to deliver')
        counts = self.ledger.counts()
        if self.document['auxiliary_limit']-sum(v['started'] for k, v in counts.items() if k != 'search') < 2:
            raise ValueError('Reserve two auxiliary calls for calibration and held-out final evaluation')
        atomic_json(self.directory/'pending_decision.json', {'action': 'finalize', 'champion_call_id': champion['call_id']})
        results = {}
        try:
            for role in ('calibration', 'test'):
                config = copy.deepcopy(self.document['config'])
                if role == 'test':
                    config['data_cfgs']['train_period'] = config['data_cfgs']['test_period']
                backend = type(self.backend)(config, self.document['outer_ranges'], self.directory)
                setup = CandidateSetup(backend, self.ledger, self.setup.cancelled, self.document.get('deadline_at'))
                q, value = setup.evaluate(backend.normalize(champion['parameters']), 'final')
                if not self.ledger.records[-1].get('eligible', True):
                    raise ExecutionStop('final_result_crossed_wall_deadline')
                results[role] = self.ledger.records[-1]
                np.save(self.directory/f'final_{role}_q.npy', q)
                np.save(self.directory/f'final_{role}_obs.npy', backend.observations)
            result = {'success': True, 'scientific_completed': True, 'study_id': self.document['study_id'],
                      'champion': champion, 'evaluation': results, 'calls': self.ledger.counts(),
                      'search_stop_reason': self.engine.reason,
                      'search_execution_failed': str(self.engine.reason).startswith('scientific_error')}
            atomic_json(self.directory/'final.json', result)
            self.document['final_result'] = result
            self.save()
            (self.directory/'pending_decision.json').unlink()
            return result
        except Exception as error:
            self.document['history'].append({'action': 'finalize', 'error': str(error), 'partial_evaluation': results})
            self.save()
            (self.directory/'pending_decision.json').unlink()
            raise
