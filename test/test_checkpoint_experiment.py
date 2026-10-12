"""No paid LLM/CAMELS runs. Native SPOTPY, fixture hydrology, real XAJ/synthetic inputs."""
import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

import numpy as np
import spotpy

from hydroagent.research.budget import Ledger, atomic_json
from hydroagent.research.session import Session, CandidateSetup
from hydroagent.research.sceua_runner import CheckpointSCEUA
from hydroagent.research.service import inspect_study

SETTINGS = dict(ngs=2, kstop=100, peps=1e-12, pcento=1e-12, random_seed=34)
RANGES = dict(a=[0., 1.], b=[0., 1.])
CONFIG = {'data_cfgs': {'basin_ids': ['fixture'], 'train_period': ['train'], 'test_period': ['test']}}
DECISION = dict(evidence='checkpoint population', hypothesis='continue optimization',
                prediction='Evaluate more candidates', falsification='No improvement in a defined window')


class FixtureBackend:
    def __init__(self, config, ranges, directory):
        self.names = list(ranges)
        self.ranges = ranges
        self.parameters = [spotpy.parameter.Uniform(k, low=0, high=1) for k in self.names]
        self.observations = np.array([1., 1.5, 2., 1.2])
        self.signature = 'fixed-fixture-science'
        self.runtime = {'integration': 'synthetic fixture'}

    def physical(self, normalized):
        return {k: self.ranges[k][0]+float(v)*(self.ranges[k][1]-self.ranges[k][0]) for k, v in zip(self.names, normalized)}

    def normalize(self, physical):
        return np.array([(physical[k]-self.ranges[k][0])/(self.ranges[k][1]-self.ranges[k][0]) for k in self.names])

    def simulate(self, normalized):
        p = list(self.physical(normalized).values())
        return np.array([1+p[0], 1+p[1], 1+p[0]*p[1], 1+p[0]+p[1]])

    def score(self, q):
        return float(np.sqrt(np.mean((q-self.observations)**2)))


class NativeSetup:
    def __init__(self):
        self.backend = FixtureBackend(CONFIG, RANGES, None)
        self.sequence = []

    def parameters(self):
        return spotpy.parameter.generate(self.backend.parameters)

    def simulation(self, vector):
        vector = np.asarray(list(vector))
        self.sequence.append(vector.copy())
        return self.backend.simulate(vector)

    def evaluation(self):
        return self.backend.observations

    def objectivefunction(self, simulation, evaluation, params=None):
        return self.backend.score(simulation)


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.directory = self.root/'study'

    def tearDown(self):
        self.temp.cleanup()

    def create(self, limit=400, auxiliary=8, backend=FixtureBackend):
        return Session.create(self.directory, copy.deepcopy(CONFIG), limit, auxiliary, dict(SETTINGS), copy.deepcopy(RANGES), backend)

    def run_advance(self, session, calls, action='continue', **kwargs):
        return session.advance(session.document['revision'], action, calls, DECISION, **kwargs)

    def test_native_candidate_sequence_equivalence(self):
        native_setup = NativeSetup()
        with contextlib.redirect_stdout(io.StringIO()):
            native = spotpy.algorithms.sceua(native_setup, dbformat='ram', save_sim=False,
                                            db_precision=np.float64, random_state=SETTINGS['random_seed'])
            native.sample(1000000, **{k: SETTINGS[k] for k in ('ngs', 'kstop', 'peps', 'pcento')}, max_loop_inc=3)
            session = self.create()
            self.run_advance(session, len(native_setup.sequence))
        sequence = [session.backend.normalize(r['parameters']) for r in session.ledger.records if r['event'] == 'started']
        np.testing.assert_array_equal(sequence, native_setup.sequence)
        self.assertEqual(session.engine.nloop, 3)

    def test_pause_disk_restore_mid_complex_matches_continuous(self):
        with contextlib.redirect_stdout(io.StringIO()):
            continuous = self.create()
            self.run_advance(continuous, 103)
            expected = [r['parameters'] for r in continuous.ledger.records if r['event'] == 'started']
            other = self.root/'paused'
            paused = Session.create(other, CONFIG, 400, 8, SETTINGS, RANGES, FixtureBackend)
            self.run_advance(paused, 11)
            self.assertGreater(paused.engine.step, 0)
            paused = Session(other, FixtureBackend)
            remaining = len(expected)-paused.ledger.counts()['search']['started']
            self.run_advance(paused, remaining)
        actual = [r['parameters'] for r in paused.ledger.records if r['event'] == 'started']
        self.assertEqual(actual, expected)
        np.testing.assert_array_equal(paused.engine.population()[0], continuous.engine.population()[0])
        np.testing.assert_array_equal(paused.engine.population()[1], continuous.engine.population()[1])

    def test_global_cap_and_unaccepted_trials_are_accounted(self):
        with contextlib.redirect_stdout(io.StringIO()):
            session = self.create(limit=37)
            result = self.run_advance(session, 37)
        self.assertEqual(result['calls']['search']['started'], 37)
        self.assertEqual(result['calls']['search']['completed'], 37)
        self.assertTrue(result['terminal'])
        self.assertEqual(result['stop_reason'], 'search_budget_exhausted')
        self.assertGreater(result['optimizer_counter'], 37)
        self.assertEqual(result['champion']['objective'], min(r['objective'] for r in session.ledger.records if r['event'] == 'completed'))

    def test_warm_restart_reuses_ids_and_remaps_physical_bounds(self):
        with contextlib.redirect_stdout(io.StringIO()):
            session = self.create()
            self.run_advance(session, 35)
            previous = session.ledger.counts()['search']['started']
            result = self.run_advance(session, 25, action='warm_restart', ranges=dict(a=[0., .7], b=[0., 1.]), keep_count=3)
        history = result['experiment_memory'][-1]
        self.assertEqual(len(history['retained_call_ids']), 3)
        self.assertTrue(all(i <= previous for i in history['retained_call_ids']))
        self.assertEqual(result['ranges']['a'], [0., .7])
        self.assertLessEqual(result['calls']['search']['started']-previous, 27)
        self.assertEqual(session.engine.initial_index, 10)

    def test_stale_checkpoint_and_changed_continue_rejected_before_calls(self):
        with contextlib.redirect_stdout(io.StringIO()):
            session = self.create()
        with self.assertRaisesRegex(ValueError, 'Stale'):
            session.advance(99, 'continue', 20, DECISION)
        with self.assertRaisesRegex(ValueError, 'preserves'):
            self.run_advance(session, 20, settings={'ngs': 3})
        self.assertEqual(session.ledger.counts()['search']['started'], 0)

    def test_failed_simulation_charged_and_champion_retained(self):
        with contextlib.redirect_stdout(io.StringIO()):
            session = self.create()
            self.run_advance(session, 20)
            old = session.summary()['champion']
            with patch.object(session.backend, 'simulate', side_effect=RuntimeError('structured upstream failure')):
                result = self.run_advance(session, 5)
        self.assertEqual(result['calls']['search']['failed'], 1)
        self.assertEqual(result['champion'], old)
        self.assertTrue(result['terminal'])
        self.assertIn('structured upstream failure', result['experiment_memory'][-1]['error'])

    def test_interrupted_call_cannot_silently_replay(self):
        with contextlib.redirect_stdout(io.StringIO()):
            session = self.create()
        session.ledger.start('search', dict(a=.2, b=.4))
        with self.assertRaisesRegex(RuntimeError, 'reconcile'):
            Session(self.directory, FixtureBackend)

    def test_probe_does_not_advance_search_rng_or_promote_champion(self):
        with contextlib.redirect_stdout(io.StringIO()):
            session = self.create()
            self.run_advance(session, 20)
            expected_rng = session.engine.snapshot()['random']
            champion = session.summary()['champion']
            before = session.ledger.counts()['search']['started']
            result = session.probe(session.document['revision'], dict(a=.1, b=.2), 'Test local response')
        self.assertEqual(result['calls']['search']['started'], before)
        self.assertEqual(result['calls']['probe']['started'], 1)
        self.assertEqual(result['champion'], champion)
        self.assertEqual(json.dumps(result['experiment_memory'][-1]['parameters']), json.dumps(dict(a=.1, b=.2)))
        from hydroagent.research.budget import json_value
        self.assertEqual(json_value(session.engine.snapshot()['random']), json_value(expected_rng))

    def test_holdout_requires_freeze_and_final_calls_separate(self):
        with contextlib.redirect_stdout(io.StringIO()):
            session = self.create()
            self.run_advance(session, 20)
            with self.assertRaisesRegex(ValueError, 'freeze'):
                session.finalize()
            self.run_advance(session, 0, 'stop')
            result = session.finalize()
        self.assertTrue(result['scientific_completed'])
        self.assertEqual(result['calls']['final']['started'], 2)
        with self.assertRaisesRegex(ValueError, 'terminal'):
            self.run_advance(session, 1)
        self.assertEqual(session.finalize(), result)

    def test_real_xaj_with_synthetic_forcing(self):
        from hydromodel.models.model_config import read_model_param_dict
        from hydromodel.models.xaj import xaj
        config = read_model_param_dict()['xaj_mz']
        names = config['param_name']
        ranges = config['param_range']
        class RealXAJBackend(FixtureBackend):
            def __init__(self, cfg, ranges, directory):
                self.names, self.ranges = list(ranges), ranges
                self.parameters = [spotpy.parameter.Uniform(k, low=0, high=1) for k in self.names]
                self.observations = np.linspace(.1, 1, 25)
                self.signature = 'real-xaj-synthetic-forcing'
                self.runtime = {'integration': 'real XAJ with synthetic inputs, not CAMELS'}
            def simulate(self, normalized):
                forcing = np.zeros((30, 1, 2))
                forcing[:, 0, 0] = np.where(np.arange(30)%4 == 0, 12., 1.)
                forcing[:, 0, 1] = 2.
                q, _ = xaj(forcing, np.asarray(normalized)[None, :], name='xaj_mz', warmup_length=5)
                return np.asarray(q).ravel()
        with contextlib.redirect_stdout(io.StringIO()):
            real = Session.create(self.root/'real', CONFIG, 65, 2, SETTINGS,
                                  {k: list(ranges[k]) for k in names}, RealXAJBackend)
            result = self.run_advance(real, 65)
        self.assertEqual(result['calls']['search']['started'], 65)
        self.assertIsNotNone(result['champion'])
        self.assertTrue(np.isfinite(result['champion']['objective']))

    def test_actual_hydromodel_interface_with_synthetic_data_loader(self):
        from hydromodel.trainers import unified_calibrate
        from hydromodel.models.model_config import read_model_param_dict
        from hydroagent.research.backend import HydromodelBackend
        class Loader:
            def __init__(self, config):
                self.basin_ids = ['fixture']
            def load_data(self):
                forcing = np.zeros((30, 1, 2))
                forcing[:, 0, 0] = np.where(np.arange(30)%4 == 0, 12., 1.)
                forcing[:, 0, 1] = 2.
                return forcing, np.linspace(.1, 1, 30)[:, None, None]
            def get_basin_configs(self):
                return {'fixture': {'basin_area': 1000.}}
        config = {'data_cfgs': {'basin_ids': ['fixture'], 'warmup_length': 5,
                               'train_period': ['2000-01-01', '2000-01-30'], 'test_period': ['2001-01-01', '2001-01-30']},
                  'model_cfgs': {'model_name': 'xaj_mz'},
                  'training_cfgs': {'loss_config': {'type': 'time_series', 'obj_func': 'RMSE'}}}
        native = read_model_param_dict()['xaj_mz']
        ranges = {k: list(native['param_range'][k]) for k in native['param_name']}
        with patch.object(unified_calibrate, 'UnifiedDataLoader', Loader), contextlib.redirect_stdout(io.StringIO()):
            session = Session.create(self.root/'interface', config, 65, 2, SETTINGS, ranges, HydromodelBackend)
            result = self.run_advance(session, 65)
        self.assertTrue(result['success'], str(result['experiment_memory'][-1].get('error')))
        self.assertEqual(result['calls']['search']['started'], 65)
        self.assertTrue(result['hydrological_diagnostics']['available'])
        self.assertEqual(result['hydrological_diagnostics']['candidate_call_id'], result['champion']['call_id'])

    def test_no_grant_start_tool_rejected_in_subprocess(self):
        from hydroagent.tools.checkpoint_calibration import start_calibration_study
        result = start_calibration_study('not-authorized', _workspace=self.root, _cfg={})
        self.assertFalse(result['success'])
        self.assertIn('grant', result['error'])

    def test_deployment_slot_cannot_be_renewed_by_repeated_start(self):
        from hydroagent.research import service
        cfg = {'checkpoint_experiment': {'enabled': True, 'grant_id': 'fixture-only', 'basin_ids': ['fixture'],
               'model_name': 'xaj_mz', 'max_studies': 1, 'search_budget_calls': 100, 'auxiliary_budget_calls': 2,
               'wall_budget_seconds': 60, 'first_segment_calls': 65, 'sceua': SETTINGS},
               'defaults': {'train_period': ['2000-01-01', '2000-01-30'], 'test_period': ['2001-01-01', '2001-01-30'],
                            'data_source': 'camels_us'}, 'paths': {'dataset_dir': str(self.root)}, 'algorithms': {}}
        original = Session.create
        def create_fixture(*args, **kwargs):
            return original(*args, backend_factory=FixtureBackend, **kwargs)
        with patch.object(Session, 'create', side_effect=create_fixture), contextlib.redirect_stdout(io.StringIO()):
            first = service.create_study(self.root, cfg, 'fixture')
            with self.assertRaisesRegex(ValueError, 'slots consumed'):
                service.create_study(self.root, cfg, 'fixture')
        self.assertEqual(first['calls']['search']['started'], 65)
        self.assertEqual(len(json.loads((self.root/'result/checkpoint_grants/fixture-only/grant.json').read_text())['studies']), 1)

    def test_cancel_and_wall_deadline_stop_without_new_model_calls(self):
        with contextlib.redirect_stdout(io.StringIO()):
            session = self.create()
            session.setup.cancelled = lambda: True
            result = self.run_advance(session, 20)
        self.assertEqual(result['stop_reason'], 'cancelled')
        self.assertEqual(result['calls']['search']['started'], 0)
        with contextlib.redirect_stdout(io.StringIO()):
            expired = Session.create(self.root/'expired', CONFIG, 100, 2, SETTINGS, RANGES, FixtureBackend)
            expired.setup.deadline_at = 0
            result = self.run_advance(expired, 20)
        self.assertEqual(result['stop_reason'], 'wall_deadline')
        self.assertEqual(result['calls']['search']['started'], 0)


class AgentMemoryTests(unittest.TestCase):
    def test_existing_agent_loop_preserves_memory_and_rejects_premature_completion(self):
        from hydroagent.agent import HydroAgent
        from hydroagent.llm import LLMResponse, ToolCall, TokenTracker
        from hydroagent.memory import Memory
        with tempfile.TemporaryDirectory() as tmp:
            agent = object.__new__(HydroAgent)
            agent.workspace = Path(tmp)
            agent.cfg, agent.max_turns = {}, 10
            agent._stop_requested = agent._pause_requested = False
            agent._checkpoint_study_id = 'existing-study'
            agent.memory = Memory(agent.workspace)
            agent.tool_schemas = []
            agent.ui = Mock()
            agent.ui.thinking.side_effect = lambda *a: contextlib.nullcontext()
            agent.ui.suppress_tool_output.side_effect = lambda *a: contextlib.nullcontext()
            agent._build_context = lambda query, **kw: [{'role': 'system', 'content': 'base'}, {'role': 'user', 'content': query}]
            agent._maybe_compress_history = lambda messages: messages[:2]
            agent._get_task_status_note = lambda: ''
            state = {'study_id': 'existing-study', 'checkpoint_id': 1, 'champion': {'objective': .5},
                     'scientific_completed': False, 'experiment_memory': [{'decision': 'retained hypothesis'}]}
            submitted = []
            def execute(name, arguments):
                submitted.append(name)
                state['experiment_memory'].append({'decision': name})
                if name == 'finalize_calibration_study':
                    state['scientific_completed'] = True
                return dict(state, success=True)
            agent._execute_tool = execute
            answers = iter([LLMResponse(text='premature completion'),
                            LLMResponse(tool_calls=[ToolCall('advance_calibration_study', {}, '1')]),
                            LLMResponse(tool_calls=[ToolCall('finalize_calibration_study', {}, '2')]),
                            LLMResponse(text='scientifically completed')])
            agent.llm = Mock()
            agent.llm.tokens = TokenTracker()
            agent.llm.supports_function_calling = True
            agent.llm.needs_reasoning_echo = False
            def chat(messages, **kw):
                self.assertEqual(messages[1]['content'], 'supervise the same basin')
                self.assertIn('retained hypothesis', messages[-1]['content'])
                if submitted:
                    self.assertIn(submitted[-1], messages[-1]['content'])
                return next(answers)
            agent.llm.chat.side_effect = chat
            with patch('hydroagent.research.service.inspect_study', side_effect=lambda *a: state):
                result = agent.run('supervise the same basin')
            self.assertEqual(result, 'scientifically completed')
            self.assertEqual(submitted, ['advance_calibration_study', 'finalize_calibration_study'])
            self.assertEqual(agent.llm.chat.call_count, 4)

    def test_registered_tools_have_no_budget_argument_and_memory_survives_compression(self):
        from hydroagent.tools import fn_to_schema
        from hydroagent.tools.checkpoint_calibration import start_calibration_study
        from hydroagent.agent import HydroAgent
        schema = fn_to_schema(start_calibration_study)
        self.assertEqual(set(schema['function']['parameters']['properties']), {'basin_id'})
        agent = object.__new__(HydroAgent)
        agent._checkpoint_study_id = 'existing-study'
        agent.workspace = Path('.')
        document = dict(study_id='existing-study', checkpoint_id=3, experiment_memory=[{'decision': 'old hypothesis', 'actual_gain': .01}])
        with patch('hydroagent.research.service.inspect_study', return_value=document):
            messages = agent._with_checkpoint_memory([{'role': 'system', 'content': 'base'}, {'role': 'user', 'content': 'original basin task'}])
            messages = agent._with_checkpoint_memory(messages)
        self.assertEqual(len(messages), 3)
        self.assertIn('old hypothesis', messages[-1]['content'])
        self.assertIn('actual_gain', messages[-1]['content'])


if __name__ == '__main__':
    unittest.main()
