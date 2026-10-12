"""Deployment-granted studies. Agent arguments cannot renew research budgets."""
from __future__ import annotations

import copy
import hashlib
import json
import uuid
from pathlib import Path

from .budget import Ledger, atomic_json, read_json
from .session import Session, owned_lock, study_path, validate_settings


def create_study(workspace, cfg, basin_id, allocated_study_id=None):
    grant = cfg.get('checkpoint_experiment')
    if not isinstance(grant, dict) or not grant.get('enabled'):
        raise ValueError('An explicit checkpoint_experiment research grant is required')
    if basin_id not in grant.get('basin_ids', []):
        raise ValueError('Basin is not authorized by deployment')
    grant_id = grant.get('grant_id', '')
    if not grant_id or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in grant_id):
        raise ValueError('Deployment grant_id must be a nonempty safe identifier')
    for key in ('search_budget_calls', 'first_segment_calls', 'max_studies', 'wall_budget_seconds'):
        if type(grant.get(key)) is not int or grant[key] <= 0:
            raise ValueError(f'Explicit positive {key} required')
    if type(grant.get('auxiliary_budget_calls')) is not int or grant['auxiliary_budget_calls'] < 2:
        raise ValueError('At least two auxiliary calls must be authorized for final scoring')
    if grant['first_segment_calls'] > grant['search_budget_calls']:
        raise ValueError('First segment exceeds total search grant')
    settings = copy.deepcopy(grant.get('sceua', {}))
    validate_settings(settings)
    from hydroagent.config import build_hydromodel_config
    from hydromodel.models.model_config import read_model_param_dict
    model_name = grant.get('model_name', 'xaj_mz')
    # Reuse existing configuration assembly; only deployment sets data/model/objective.
    config = build_hydromodel_config([basin_id], model_name=model_name, algorithm='SCE_UA',
                                    obj_func='RMSE', cfg=cfg)
    from datetime import date
    train = [date.fromisoformat(x) for x in config['data_cfgs']['train_period']]
    test = [date.fromisoformat(x) for x in config['data_cfgs']['test_period']]
    if train[0] > train[1] or test[0] > test[1] or not (train[1] < test[0] or test[1] < train[0]):
        raise ValueError('Calibration and final test periods must be valid and disjoint')
    native = read_model_param_dict()[model_name]
    outer = {name: list(native['param_range'][name]) for name in native['param_name']}
    if grant.get('outer_ranges') is not None:
        outer = {k: grant['outer_ranges'][k] for k in native['param_name']}
    if (2*len(outer)+1)*settings['ngs'] > grant['first_segment_calls']:
        raise ValueError('First segment must accommodate full population initialization')
    from .session import validate_ranges
    validate_ranges(outer, outer)
    grants = Path(workspace).resolve()/'result'/'checkpoint_grants'/grant_id
    grants.mkdir(parents=True, exist_ok=True)
    # Include science and dataset path in the grant identity, excluding provider credentials.
    identity_config = copy.deepcopy(config)
    identity_config['data_cfgs']['basin_ids'] = grant['basin_ids']
    identity_config['training_cfgs'].pop('output_dir', None)
    digest = hashlib.sha256(json.dumps({'grant': grant, 'science': identity_config}, sort_keys=True).encode()).hexdigest()
    with owned_lock(grants):
        receipt_path = grants/'grant.json'
        receipt = read_json(receipt_path) if receipt_path.exists() else {'fingerprint': digest, 'studies': []}
        if receipt['fingerprint'] != digest:
            raise ValueError('Grant changed; choose a separately authorized grant_id')
        if len(receipt['studies']) >= grant['max_studies']:
            raise ValueError('All authorized study slots consumed; no automatic repeat')
        study_id = allocated_study_id or str(uuid.uuid4())
        study_path(workspace, study_id)  # validate code-owned identifier before consuming a slot
        receipt['studies'].append({'study_id': study_id, 'basin': basin_id})
        atomic_json(receipt_path, receipt)
    directory = study_path(workspace, study_id)
    config['training_cfgs']['output_dir'] = str(directory)
    config['training_cfgs']['algorithm_params'] = dict(settings)
    session = Session.create(directory, config, grant['search_budget_calls'], grant['auxiliary_budget_calls'],
                             settings, outer, arm=grant.get('arm', 'A'), wall_budget_seconds=grant['wall_budget_seconds'])
    with owned_lock(directory):
        result = session.advance(0, 'continue', grant['first_segment_calls'],
                                 {'evidence': 'deployment initial configuration', 'hypothesis': 'Establish common initial search',
                                  'prediction': 'Produce initial candidate evidence', 'falsification': 'Model/optimizer execution failure'})
    return result


def inspect_study(workspace, study_id):
    directory = study_path(workspace, study_id)
    document = read_json(directory/'session.json')
    result = read_json(directory/'summary.json') if (directory/'summary.json').exists() else {}
    ledger = Ledger(directory, document['search_limit'], document['auxiliary_limit'])
    return {**result, 'success': True, 'study_id': study_id, 'checkpoint_id': document['revision'],
            'calls': ledger.counts(), 'search_remaining': ledger.remaining_search(),
            'experiment_memory': document['history'], 'terminal': document['terminal'],
            'scientific_completed': (directory/'final.json').exists(),
            'requires_reconciliation': (directory/'pending_decision.json').exists() or
                sum(v['started'] for v in ledger.counts().values()) != document['checkpoint_started_calls']}


def execute(workspace, operation, arguments):
    if operation == 'start':
        return create_study(workspace, arguments['cfg'], arguments['basin_id'], arguments.get('allocated_study_id'))
    if operation == 'inspect':
        return inspect_study(workspace, arguments['study_id'])
    directory = study_path(workspace, arguments['study_id'])
    with owned_lock(directory):
        session = Session(directory)
        if operation == 'advance':
            if session.document['arm'] == 'B0' and arguments['action'] not in ('continue', 'stop'):
                raise ValueError('Continuous baseline may not restart')
            return session.advance(arguments['checkpoint_id'], arguments['action'], arguments['call_limit'],
                                   arguments['decision'], arguments.get('ranges'), arguments.get('settings'), arguments.get('keep_count'))
        if operation == 'probe':
            return session.probe(arguments['checkpoint_id'], arguments['parameters'], arguments['prediction'])
        if operation == 'finalize':
            return session.finalize()
        raise ValueError('Unsupported research operation')
