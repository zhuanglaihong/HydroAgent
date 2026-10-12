"""Durable accounting at the model-call boundary, not SPOTPY postprocessing."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import numpy as np


def json_value(value):
    if isinstance(value, np.ndarray):
        return json_value(value.tolist())
    if isinstance(value, np.generic):
        return json_value(value.item())
    if isinstance(value, dict):
        return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def atomic_json(path: Path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('w', encoding='utf-8') as stream:
        json.dump(json_value(value), stream, ensure_ascii=False, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


class ExecutionStop(Exception):
    """Budget or cancellation; never algorithm convergence."""


class Ledger:
    def __init__(self, directory: Path, search_limit: int, auxiliary_limit: int):
        self.path = directory / 'calls.jsonl'
        self.directory = directory
        self.limits = {'search': search_limit, 'auxiliary': auxiliary_limit}
        self.records = []
        if self.path.exists():
            # A torn record is an explicit reconciliation error, never ignored.
            self.records = [json.loads(line) for line in self.path.read_text(encoding='utf-8').splitlines()]
        self._counts = {k: {'started': 0, 'completed': 0, 'failed': 0} for k in ('search', 'probe', 'diagnostic', 'final')}
        for record in self.records:
            self._counts[record['category']][record['event']] += 1
        self.best_search = None
        for record in self.records:
            self._consider(record)

    def _consider(self, record):
        if record['category'] == 'search' and record['event'] == 'completed' and record.get('eligible', True):
            if self.best_search is None or record['objective'] < self.best_search['objective']:
                self.best_search = record

    def append(self, record):
        record = {**record, 'at': time.time()}
        with self.path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(json_value(record), ensure_ascii=False, allow_nan=False) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        self.records.append(record)
        self._counts[record['category']][record['event']] += 1
        self._consider(record)

    def counts(self):
        return {k: dict(v) for k, v in self._counts.items()}

    def start(self, category, physical):
        counts = self.counts()
        bucket = 'search' if category == 'search' else 'auxiliary'
        used = counts['search']['started'] if bucket == 'search' else sum(v['started'] for k, v in counts.items() if k != 'search')
        if used >= self.limits[bucket]:
            raise ExecutionStop(f'{bucket}_budget_exhausted')
        call_id = sum(v['started'] for v in counts.values()) + 1
        self.append({'event': 'started', 'category': category, 'call_id': call_id, 'parameters': physical})
        return call_id

    def remaining_search(self):
        return self.limits['search'] - self.counts()['search']['started']

    def complete(self, call_id, category, objective, physical, **extra):
        self.append({'event': 'completed', 'call_id': call_id, 'category': category,
                     'objective': objective, 'parameters': physical, **extra})

    def fail(self, call_id, category, error):
        self.append({'event': 'failed', 'call_id': call_id, 'category': category,
                     'error_type': type(error).__name__, 'error': str(error)})
