"""Hydromodel remains the scientific backend; no XAJ equations are copied."""
from __future__ import annotations

import copy
import hashlib
import importlib.metadata
import inspect
import json
from pathlib import Path

import numpy as np
import yaml


class HydromodelBackend:
    def __init__(self, config, ranges, directory):
        import hydromodel
        from hydromodel.trainers import unified_calibrate as module
        klass = getattr(module, 'UnifiedCalibrator', None) or getattr(module, 'UnifiedModelSetup', None)
        if klass is None:
            raise ValueError('Hydromodel does not expose a supported unified model setup')
        config = copy.deepcopy(config)
        self.name = config['model_cfgs']['model_name']
        parameter_file = directory / 'active_ranges.yaml'
        parameter_file.write_text(yaml.safe_dump({self.name: {'param_name': list(ranges), 'param_range': ranges}}, sort_keys=False), encoding='utf-8')
        config['training_cfgs']['param_range_file'] = str(parameter_file)
        model = {'name': self.name, **config['model_cfgs'].get('model_params', {}),
                 self.name: {'param_name': list(ranges), 'param_range': ranges}}
        self.model = klass(data_config=config['data_cfgs'], model_config=model,
                           loss_config=config['training_cfgs']['loss_config'], training_config=config['training_cfgs'])
        self.model.set_basin_index(0)
        self.names = self.model.get_parameter_names()
        if self.names != list(ranges):
            raise ValueError('Hydromodel parameter order differs from the frozen experiment')
        self.ranges = ranges
        self.parameters = self.model.params
        self.observations = self.model.true_obs
        self.scored_forcing = np.asarray(self.model.p_and_e)[-len(self.observations):, 0, :2]
        start, end = config['data_cfgs']['train_period']
        calendar = np.arange(np.datetime64(start), np.datetime64(end)+np.timedelta64(1, 'D'))
        self.dates = calendar[-len(self.observations):].astype(str).tolist() if len(calendar) == len(self.model.p_and_e) else []
        if not np.isfinite(self.observations).all() or np.var(self.observations) <= 0:
            raise ValueError('This research protocol requires finite, nonconstant observations; no silent mask changes')
        digest = hashlib.sha256()
        for array in (self.model.p_and_e, self.observations):
            array = np.ascontiguousarray(array)
            digest.update(str((array.shape, array.dtype)).encode())
            digest.update(array.tobytes())
        root = Path(hydromodel.__file__).parent
        for path in sorted(root.rglob('*.py')):
            digest.update(str(path.relative_to(root)).encode())
            digest.update(path.read_bytes())
        from spotpy.algorithms import sceua
        digest.update(Path(inspect.getfile(sceua)).read_bytes())
        for package in ('hydromodel', 'spotpy', 'numpy'):
            digest.update(f'{package}:{importlib.metadata.version(package)}'.encode())
        digest.update(json.dumps({'data': config['data_cfgs'], 'model': config['model_cfgs'],
                                  'loss': config['training_cfgs']['loss_config']}, sort_keys=True).encode())
        self.signature = digest.hexdigest()
        self.runtime = {'hydromodel_path': str(root), 'hydromodel_version': importlib.metadata.version('hydromodel'),
                        'spotpy_version': importlib.metadata.version('spotpy'), 'interface': klass.__name__}

    def physical(self, normalized):
        return {name: self.ranges[name][0] + float(value)*(self.ranges[name][1]-self.ranges[name][0])
                for name, value in zip(self.names, normalized)}

    def normalize(self, physical):
        return np.array([(physical[k]-self.ranges[k][0])/(self.ranges[k][1]-self.ranges[k][0]) for k in self.names])

    def simulate(self, normalized):
        q = np.asarray(self.model.simulate(np.asarray(normalized)), dtype=float)
        if q.shape != self.observations.shape or not np.isfinite(q).all() or (q < 0).any():
            raise ValueError('Invalid hydromodel simulation; no fallback output accepted')
        return q

    def score(self, q):
        raw = np.asarray(self.model.calculate_objective(q, self.observations), dtype=float).ravel()
        if raw.size != 1:
            raise ValueError('Expected exactly one basin objective; multi-basin reduction is unsupported')
        value = float(raw[0])
        if not np.isfinite(value):
            raise ValueError('Nonfinite objective')
        return value
